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
from urllib.parse import urlparse

STARTER_FAST_MODEL = "qwen3.5:9b"
STARTER_STRONG_MODEL = "devstral-small-2"

# Official Ollama library coding tags this repo is willing to name.
# Unknown tags warn; URL/path-shaped names fail.
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
UNSAFE_MODEL_RE = re.compile(r"://|[\\/]|\.\.|@", re.IGNORECASE)

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


def classify_base_url(url: str) -> CheckResult:
    """Prefer loopback. Fail wildcards, tunnels, and non-http(s)."""
    raw = (url or "").strip()
    if not raw:
        return CheckResult("base_url", "fail", "OLLAMA_BASE_URL is empty")
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"}:
        return CheckResult(
            "base_url",
            "fail",
            f"OLLAMA_BASE_URL must be http(s), got scheme={parsed.scheme!r}",
        )
    host = (parsed.hostname or "").lower()
    if not host:
        return CheckResult("base_url", "fail", "OLLAMA_BASE_URL has no host")
    if host in {"0.0.0.0", "::", "[::]"}:
        return CheckResult(
            "base_url",
            "fail",
            "OLLAMA_BASE_URL must not use a wildcard bind address",
        )
    if any(marker in host for marker in TUNNEL_HOST_MARKERS):
        return CheckResult(
            "base_url",
            "fail",
            "OLLAMA_BASE_URL looks like a public tunnel; do not publish Ollama",
        )
    if host in {"localhost", "127.0.0.1", "::1"}:
        return CheckResult(
            "base_url",
            "pass",
            "OLLAMA_BASE_URL is loopback (SSH local-forward is fine)",
        )
    try:
        addr = ipaddress.ip_address(host)
    except ValueError:
        return CheckResult(
            "base_url",
            "warn",
            "OLLAMA_BASE_URL is a hostname; prefer 127.0.0.1 via SSH -L",
        )
    if addr.is_loopback:
        return CheckResult("base_url", "pass", "OLLAMA_BASE_URL is loopback")
    if addr.is_private:
        return CheckResult(
            "base_url",
            "warn",
            "OLLAMA_BASE_URL is a private LAN address; prefer SSH -L to 127.0.0.1",
        )
    if addr.is_unspecified or addr.is_multicast or addr.is_reserved:
        return CheckResult(
            "base_url",
            "fail",
            "OLLAMA_BASE_URL is not a unicast host address",
        )
    return CheckResult(
        "base_url",
        "fail",
        "OLLAMA_BASE_URL looks public; do not put Ollama on the internet",
    )


def classify_model_tag(name: str, tag: str) -> CheckResult:
    """Reject path/URL-shaped tags. Official pins pass; other library names warn.

    A clean tag is not proof the weights are clean. Unofficial GGUFs and
    one-off fine-tunes are the usual supply-chain hole for a trojaned SLM.
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
    official_families = {t.split(":")[0] for t in OFFICIAL_LIBRARY_TAGS}
    family = value.split(":")[0]
    if value in OFFICIAL_LIBRARY_TAGS:
        return CheckResult(
            name,
            "pass",
            f"{name}={value} is an official library tag this repo documents",
        )
    if family in official_families:
        return CheckResult(
            name,
            "warn",
            f"{name}={value} is an official family but not a starter pin; confirm it on ollama.com/library",
        )
    return CheckResult(
        name,
        "warn",
        f"{name}={value} is not in the starter allowlist; pull only from ollama.com/library",
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
        ip = _hex_ip(addr_hex)
        if ip is not None:
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


def classify_local_listeners(
    rows: Sequence[tuple[str, int]],
    port: int = 11434,
) -> CheckResult:
    """Fail if this host listens on the Ollama port at a wildcard address."""
    matching = [(ip, p) for ip, p in rows if p == port]
    if not matching:
        return CheckResult(
            "local_listen",
            "warn",
            f"no local LISTEN on :{port} (Ollama may be down or on another port)",
        )
    wild = [ip for ip, _ in matching if ip in {"0.0.0.0", "::", "::0"}]
    if wild:
        return CheckResult(
            "local_listen",
            "fail",
            f"Ollama port {port} is bound on {', '.join(wild)}; keep it on 127.0.0.1",
        )
    return CheckResult(
        "local_listen",
        "pass",
        f"Ollama port {port} is listening on {', '.join(sorted({ip for ip, _ in matching}))}",
    )


def classify_tracked_ipv4(paths_and_text: Iterable[tuple[str, str]]) -> CheckResult:
    """Fail committed files that contain non-placeholder private or public IPs."""
    hits: list[str] = []
    for path, text in paths_and_text:
        for match in IPV4_RE.findall(text):
            try:
                addr = ipaddress.ip_address(match)
            except ValueError:
                continue
            if match in PLACEHOLDER_IPV4 or addr.is_loopback or addr.is_unspecified:
                continue
            if addr.is_private or addr.is_global:
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


def git_tracked_text_files(root: Path) -> list[tuple[str, str]]:
    try:
        proc = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=root,
            check=False,
            capture_output=True,
        )
    except OSError:
        return []
    if proc.returncode != 0:
        return []
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
        if path.suffix.lower() not in {".md", ".py", ".json", ".toml", ".sh", ".example", ".txt", ""}:
            if path.name not in {".gitignore", ".env.example", "CLAUDE.md"}:
                continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        out.append((str(path.relative_to(root)), text))
    return out


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

    if skip_listen:
        results.append(CheckResult("local_listen", "warn", "local listen check skipped"))
    else:
        rows = list(listen_rows) if listen_rows is not None else read_local_tcp_tables()
        port = urlparse(url).port or 11434
        results.append(classify_local_listeners(rows, port=port))

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

    files = list(tracked) if tracked is not None else git_tracked_text_files(repo)
    results.append(classify_tracked_ipv4(files))
    return results


def worst_status(results: Sequence[CheckResult]) -> str:
    if any(item.status == "fail" for item in results):
        return "fail"
    if any(item.status == "warn" for item in results):
        return "warn"
    return "pass"
