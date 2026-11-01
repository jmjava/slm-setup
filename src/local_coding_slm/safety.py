"""Defensive deployment checks for a private Ollama SLM.

These checks inspect *this* machine's config, git hygiene, and local listen
table. They do not scan other hosts, pull unknown weights, or try to detect
a backdoor inside a GGUF. Treat model output as untrusted even when every
check passes.
"""

from __future__ import annotations

import ipaddress
import os
import re
import subprocess
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import ParseResult, urlparse

STARTER_FAST_MODEL = "qwen3.5:9b"
STARTER_STRONG_MODEL = "devstral-small-2"

# Official Ollama library coding tags this repo is willing to name.
# Exact members pass; anything else fails. URL/path-shaped names also fail.
OFFICIAL_LIBRARY_TAGS = frozenset(
    {
        STARTER_FAST_MODEL,
        STARTER_STRONG_MODEL,
        "qwen2.5-coder:7b",
        "qwen2.5-coder:14b",
        "codellama:7b",
        "codellama:13b",
        "deepseek-coder-v2:16b",
        "llama3.1:8b",
        "mistral:7b",
        "phi4:14b",
    }
)

TUNNEL_HOST_MARKERS = (
    "ngrok",
    "trycloudflare",
    "loca.lt",
    "localhost.run",
    "serveo.net",
    "cloudflare-tunnel",
    "pagekite",
    "tunnelmole",
)

# Documented examples that may appear in committed docs.
PLACEHOLDER_IPV4 = frozenset(
    {
        "127.0.0.1",
        "192.0.2.0",
        "192.168.0.0",
    }
)

IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_INTEGER_URL_HOST_RE = re.compile(
    r"https?://(0x[0-9a-f]+|\d+)(?=[:/?#]|\s|$)",
    re.IGNORECASE,
)
UNSAFE_MODEL_RE = re.compile(r"://|[\\/]|\.\.|@", re.IGNORECASE)
# Decimal 2130706433 or 0x7f000001 disguise a dotted IPv4.
_INTEGER_FORM_IP_RE = re.compile(r"^(?:\d+|0x[0-9a-f]+)$", re.IGNORECASE)

# /proc/net/tcp state 0A = LISTEN
_LISTEN_STATE = "0A"


@dataclass(frozen=True)
class CheckResult:
    name: str
    status: str  # pass | warn | fail
    message: str

    @property
    def ok(self) -> bool:
        return self.status != "fail"


def _has_userinfo(parsed: ParseResult) -> bool:
    return parsed.username is not None or "@" in (parsed.netloc or "")


def _is_integer_form_ip(host: str) -> bool:
    return bool(_INTEGER_FORM_IP_RE.fullmatch(host))


def _base_url_fail(message: str) -> CheckResult:
    return CheckResult("base_url", "fail", message)


def _classify_parsed_url(parsed: ParseResult) -> CheckResult | None:
    if parsed.scheme not in {"http", "https"}:
        return _base_url_fail(f"OLLAMA_BASE_URL must be http(s), got scheme={parsed.scheme!r}")
    if _has_userinfo(parsed):
        return _base_url_fail("OLLAMA_BASE_URL must not include userinfo; @-form hosts are rejected")
    return None


def _is_non_unicast(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Multicast, reserved, and link-local are also marked private."""
    return bool(addr.is_multicast or addr.is_reserved or addr.is_link_local)


def _classify_ip(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> CheckResult:
    if addr.is_loopback:
        return CheckResult("base_url", "pass", "OLLAMA_BASE_URL is loopback")
    # These addresses are also is_private. Check them first or a wildcard
    # spelling or a link-local address warns and the checker exits 0.
    if addr.is_unspecified:
        return _base_url_fail("OLLAMA_BASE_URL must not use a wildcard bind address")
    if _is_non_unicast(addr):
        return _base_url_fail("OLLAMA_BASE_URL is not a unicast host address")
    if addr.is_private:
        return CheckResult(
            "base_url",
            "warn",
            "OLLAMA_BASE_URL is a private LAN address; prefer SSH -L to 127.0.0.1",
        )
    return _base_url_fail("OLLAMA_BASE_URL looks public; do not put Ollama on the internet")


def _classify_host(host: str) -> CheckResult:
    if not host:
        return _base_url_fail("OLLAMA_BASE_URL has no host")
    if _is_integer_form_ip(host):
        return _base_url_fail("OLLAMA_BASE_URL must not use a decimal or integer-form IP")
    if host in {"0.0.0.0", "::", "[::]"}:
        return _base_url_fail("OLLAMA_BASE_URL must not use a wildcard bind address")
    if any(marker in host for marker in TUNNEL_HOST_MARKERS):
        return _base_url_fail("OLLAMA_BASE_URL looks like a public tunnel; do not publish Ollama")
    if host in {"localhost", "127.0.0.1", "::1"}:
        return CheckResult(
            "base_url",
            "pass",
            "OLLAMA_BASE_URL is loopback (SSH local-forward is fine)",
        )
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return _base_url_fail("OLLAMA_BASE_URL is a hostname; use 127.0.0.1 via SSH -L")
    return _classify_ip(addr)


def classify_base_url(url: str) -> CheckResult:
    """Prefer loopback. Fail wildcards, tunnels, hostnames, userinfo, and non-http(s)."""
    raw = (url or "").strip()
    if not raw:
        return _base_url_fail("OLLAMA_BASE_URL is empty")
    try:
        parsed = urlparse(raw)
    except ValueError:
        return _base_url_fail("OLLAMA_BASE_URL is not a valid http(s) URL")
    shaped = _classify_parsed_url(parsed)
    if shaped is not None:
        return shaped
    return _classify_host((parsed.hostname or "").lower())


def is_official_library_tag(tag: str) -> bool:
    """True when tag is exactly in OFFICIAL_LIBRARY_TAGS (live lookup)."""
    return (tag or "").strip() in OFFICIAL_LIBRARY_TAGS


def classify_model_tag(name: str, tag: str) -> CheckResult:
    """Reject path/URL-shaped tags and tags outside OFFICIAL_LIBRARY_TAGS.

    A clean tag is not proof the weights are clean. Unofficial GGUFs and
    one-off fine-tunes are the usual supply-chain hole for a trojaned SLM.
    Lengthening or shortening OFFICIAL_LIBRARY_TAGS changes accept/reject.
    """
    value = (tag or "").strip()
    if not value:
        return CheckResult(name, "fail", f"{name} is empty")
    if UNSAFE_MODEL_RE.search(value):
        return CheckResult(
            name,
            "fail",
            f"{name}={value!r} looks like a path or URL; use an official Ollama library tag",
        )
    if value.startswith(".") or " " in value:
        return CheckResult(
            name,
            "fail",
            f"{name}={value!r} is not a library tag",
        )
    if is_official_library_tag(value):
        return CheckResult(
            name,
            "pass",
            f"{name}={value} is an official library tag this repo documents",
        )
    return CheckResult(
        name,
        "fail",
        f"{name}={value} is not in OFFICIAL_LIBRARY_TAGS; pull only from ollama.com/library",
    )


def parse_proc_net_listen_ports(text: str) -> list[tuple[str, int]]:
    """Parse /proc/net/tcp or tcp6 LISTEN rows into (ip, port)."""
    found: list[tuple[str, int]] = []
    for line in text.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 4:
            continue
        if parts[3] != _LISTEN_STATE:
            continue
        local = parts[1]
        if ":" not in local:
            continue
        addr_hex, port_hex = local.rsplit(":", 1)
        try:
            port = int(port_hex, 16)
        except ValueError:
            continue
        ip = _hex_ip(addr_hex) or "unparsed"
        found.append((ip, port))
    return found


def _hex_ip(addr_hex: str) -> str | None:
    try:
        raw = bytes.fromhex(addr_hex)
    except ValueError:
        return None
    if len(raw) == 4:
        return ".".join(str(b) for b in raw[::-1])
    if len(raw) == 16:
        # IPv4-mapped or IPv6 stored little-endian 32-bit words.
        words = [raw[i : i + 4][::-1] for i in range(0, 16, 4)]
        packed = b"".join(words)
        return str(ipaddress.IPv6Address(packed))
    return None


def _is_loopback_ip(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip).is_loopback
    except ValueError:
        return False


def classify_local_listeners(
    rows: Sequence[tuple[str, int]],
    port: int = 11434,
) -> CheckResult:
    """Fail unless every listener on the Ollama port is loopback."""
    matching = [(ip, p) for ip, p in rows if p == port]
    if not matching:
        return CheckResult(
            "local_listen",
            "warn",
            f"no local LISTEN on :{port} (Ollama may be down or on another port)",
        )
    exposed = [ip for ip, _ in matching if not _is_loopback_ip(ip)]
    if exposed:
        return CheckResult(
            "local_listen",
            "fail",
            f"Ollama port {port} is bound on {', '.join(exposed)}; keep it on 127.0.0.1",
        )
    return CheckResult(
        "local_listen",
        "pass",
        f"Ollama port {port} is listening on {', '.join(sorted({ip for ip, _ in matching}))}",
    )


def _leading_zero_ipv4(match: str) -> bool:
    """True when a dotted quad uses a leading zero, which ipaddress rejects."""
    parts = match.split(".")
    if len(parts) != 4 or not all(part.isdigit() for part in parts):
        return False
    return any(len(part) > 1 and part.startswith("0") for part in parts)


def _is_committed_ip_hit(match: str) -> bool:
    try:
        addr = ipaddress.ip_address(match)
    except ValueError:
        return _leading_zero_ipv4(match)
    if match in PLACEHOLDER_IPV4 or addr.is_loopback or addr.is_unspecified:
        return False
    return bool(addr.is_private or addr.is_global)


def _integer_host_is_hit(host: str) -> bool:
    """Decimal and hex URL hosts are IPv4, including values ipaddress dotted form rejects."""
    try:
        number = int(host, 16) if host.lower().startswith("0x") else int(host, 10)
    except ValueError:
        return False
    if number > 0xFFFFFFFF:
        return False
    addr = ipaddress.IPv4Address(number)
    if addr.is_loopback or addr.is_unspecified:
        return False
    return bool(addr.is_private or addr.is_global)


def _committed_ip_matches(text: str) -> list[str]:
    matches = [match for match in IPV4_RE.findall(text) if _is_committed_ip_hit(match)]
    for host in _INTEGER_URL_HOST_RE.findall(text):
        if _integer_host_is_hit(host):
            matches.append(host)
    return matches


def classify_tracked_ipv4(paths_and_text: Iterable[tuple[str, str]]) -> CheckResult:
    """Fail committed files that contain non-placeholder private or public IPs."""
    hits: list[str] = []
    for path, text in paths_and_text:
        for match in _committed_ip_matches(text):
            hits.append(f"{path}:{match}")
    if hits:
        return CheckResult(
            "committed_ips",
            "fail",
            "committed files contain non-placeholder addresses: " + ", ".join(hits[:8]),
        )
    return CheckResult(
        "committed_ips",
        "pass",
        "no non-placeholder IPv4 addresses in scanned committed text",
    )


def classify_env_ignored(ignored: bool | None) -> CheckResult:
    if ignored is None:
        return CheckResult("env_gitignore", "warn", "not a git work tree; skipped .env ignore check")
    if ignored:
        return CheckResult("env_gitignore", "pass", ".env is gitignored")
    return CheckResult("env_gitignore", "fail", ".env is not gitignored")


def classify_env_example(text: str) -> CheckResult:
    if "127.0.0.1" not in text and "<inference-host>" not in text:
        return CheckResult(
            "env_example",
            "fail",
            ".env.example must show loopback or an <inference-host> placeholder",
        )
    if IPV4_RE.search(text):
        for match in IPV4_RE.findall(text):
            if match not in PLACEHOLDER_IPV4 and match != "127.0.0.1":
                return CheckResult(
                    "env_example",
                    "fail",
                    f".env.example contains a non-placeholder address {match}",
                )
    return CheckResult("env_example", "pass", ".env.example uses loopback or placeholders")


def read_local_tcp_tables(proc_root: Path | None = None) -> list[tuple[str, int]]:
    root = proc_root or Path("/proc")
    rows: list[tuple[str, int]] = []
    for name in ("net/tcp", "net/tcp6"):
        path = root / name
        if path.is_file():
            rows.extend(parse_proc_net_listen_ports(path.read_text(encoding="utf-8", errors="replace")))
    return rows


def git_is_ignored(root: Path, relpath: str) -> bool | None:
    try:
        proc = subprocess.run(
            ["git", "check-ignore", "-q", relpath],
            cwd=root,
            check=False,
            capture_output=True,
        )
    except OSError:
        return None
    if proc.returncode == 0:
        return True
    if proc.returncode == 1:
        return False
    return None


def git_tracked_text_files(root: Path) -> list[tuple[str, str]] | None:
    """Return tracked text, or None when git cannot list the tree."""
    try:
        proc = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=root,
            check=False,
            capture_output=True,
        )
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    out: list[tuple[str, str]] = []
    for rel in proc.stdout.split(b"\0"):
        if not rel:
            continue
        rel_s = rel.decode("utf-8", errors="replace")
        if rel_s.startswith("tests/"):
            continue
        path = root / rel_s
        if not path.is_file():
            continue
        if path.suffix.lower() not in {
            ".md",
            ".py",
            ".json",
            ".toml",
            ".sh",
            ".example",
            ".txt",
            ".yml",
            ".yaml",
            "",
        }:
            if path.name not in {".gitignore", ".env.example", "CLAUDE.md"}:
                continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None
        out.append((str(path.relative_to(root)), text))
    return out


def _committed_ip_result(
    repo: Path,
    tracked: Iterable[tuple[str, str]] | None,
) -> CheckResult:
    if tracked is not None:
        return classify_tracked_ipv4(list(tracked))
    files = git_tracked_text_files(repo)
    if files is None:
        return CheckResult("committed_ips", "fail", "could not read tracked files")
    return classify_tracked_ipv4(files)


def _listen_check(
    url: str,
    *,
    skip_listen: bool,
    listen_rows: Sequence[tuple[str, int]] | None,
) -> CheckResult:
    if skip_listen:
        return CheckResult("local_listen", "warn", "local listen check skipped")
    rows = list(listen_rows) if listen_rows is not None else read_local_tcp_tables()
    port = urlparse(url).port or 11434
    return classify_local_listeners(rows, port=port)


def run_checks(
    *,
    environ: Mapping[str, str] | None = None,
    root: Path | None = None,
    listen_rows: Sequence[tuple[str, int]] | None = None,
    tracked: Iterable[tuple[str, str]] | None = None,
    env_ignored: bool | None = None,
    env_example_text: str | None = None,
    skip_listen: bool = False,
) -> list[CheckResult]:
    env = environ if environ is not None else os.environ
    repo = root or Path.cwd()
    results: list[CheckResult] = []

    url = env.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    results.append(classify_base_url(url))
    results.append(classify_model_tag("OLLAMA_FAST_MODEL", env.get("OLLAMA_FAST_MODEL", STARTER_FAST_MODEL)))
    results.append(
        classify_model_tag("OLLAMA_STRONG_MODEL", env.get("OLLAMA_STRONG_MODEL", STARTER_STRONG_MODEL))
    )

    results.append(_listen_check(url, skip_listen=skip_listen, listen_rows=listen_rows))

    example = env_example_text
    example_path = repo / ".env.example"
    if example is None and example_path.is_file():
        example = example_path.read_text(encoding="utf-8")
    if example is None:
        results.append(CheckResult("env_example", "fail", ".env.example is missing"))
    else:
        results.append(classify_env_example(example))

    ignored = env_ignored if env_ignored is not None else git_is_ignored(repo, ".env")
    results.append(classify_env_ignored(ignored))

    results.append(_committed_ip_result(repo, tracked))
    return results


def worst_status(results: Sequence[CheckResult]) -> str:
    if any(item.status == "fail" for item in results):
        return "fail"
    if any(item.status == "warn" for item in results):
        return "warn"
    return "pass"
