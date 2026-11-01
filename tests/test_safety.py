"""Unit tests for defensive deployment safety checks."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from local_coding_slm.safety import (
    CheckResult,
    OFFICIAL_LIBRARY_TAGS,
    classify_base_url,
    classify_env_example,
    classify_env_ignored,
    classify_local_listeners,
    classify_model_tag,
    classify_tracked_ipv4,
    parse_proc_net_listen_ports,
    run_checks,
    worst_status,
)


class TestClassifyBaseUrl(unittest.TestCase):
    def test_loopback_passes(self) -> None:
        self.assertEqual(classify_base_url("http://127.0.0.1:11434").status, "pass")
        self.assertEqual(classify_base_url("http://localhost:11434").status, "pass")

    def test_wildcard_fails(self) -> None:
        self.assertEqual(classify_base_url("http://0.0.0.0:11434").status, "fail")

    def test_tunnel_fails(self) -> None:
        self.assertEqual(classify_base_url("https://abc.ngrok.io").status, "fail")

    def test_public_ip_fails(self) -> None:
        self.assertEqual(classify_base_url("http://8.8.8.8:11434").status, "fail")

    def test_private_lan_warns(self) -> None:
        self.assertEqual(classify_base_url("http://192.168.1.10:11434").status, "warn")

    def test_hostname_non_loopback_non_private_fails(self) -> None:
        result = classify_base_url("https://my-ollama.evil.com")
        self.assertEqual(result.status, "fail")
        self.assertIn("hostname", result.message)

    def test_userinfo_and_decimal_ip_tricks_fail(self) -> None:
        cases = (
            "http://127.0.0.1@evil.com",
            "http://2130706433",
            "http://2130706433:11434",
        )
        for url in cases:
            with self.subTest(url=url):
                result = classify_base_url(url)
                self.assertEqual(result.status, "fail", result.message)

    def test_userinfo_on_loopback_fails(self) -> None:
        result = classify_base_url("http://user@127.0.0.1:11434")
        self.assertEqual(result.status, "fail")
        self.assertIn("userinfo", result.message)

    def test_empty_fails(self) -> None:
        self.assertEqual(classify_base_url("").status, "fail")

    def test_wildcard_spellings_and_non_unicast_fail(self) -> None:
        """Unspecified and reserved addresses are also private; they must not warn."""
        cases = (
            "http://[::0]:11434",
            "http://[0:0:0:0:0:0:0:0]:11434",
            "http://[::ffff:0.0.0.0]:11434",
            "http://255.255.255.255:11434",
            "http://[0.0.0.0]:11434",
        )
        for url in cases:
            with self.subTest(url=url):
                result = classify_base_url(url)
                self.assertEqual(result.status, "fail", result.message)

    def test_link_local_url_fails(self) -> None:
        """Link-local addresses are also private, so they must not warn."""
        cases = (
            "http://169.254.169.254:11434",
            "http://[fe80::1]:11434",
            "http://[::ffff:169.254.169.254]:11434",
            "http://[fe80::1%25eth0]:11434",
        )
        for url in cases:
            with self.subTest(url=url):
                result = classify_base_url(url)
                self.assertEqual(result.status, "fail", result.message)


class TestClassifyModelTag(unittest.TestCase):
    def test_starter_tags_pass(self) -> None:
        self.assertEqual(classify_model_tag("fast", "qwen3.5:9b").status, "pass")
        self.assertEqual(classify_model_tag("strong", "devstral-small-2").status, "pass")

    def test_path_or_url_fails(self) -> None:
        self.assertEqual(classify_model_tag("fast", "https://example.com/model.gguf").status, "fail")
        self.assertEqual(classify_model_tag("fast", "/tmp/mystery.gguf").status, "fail")
        self.assertEqual(classify_model_tag("fast", "user/trojan-finetune").status, "fail")

    def test_unknown_library_name_fails(self) -> None:
        result = classify_model_tag("fast", "some-random-coder:7b")
        self.assertEqual(result.status, "fail")
        self.assertIn("OFFICIAL_LIBRARY_TAGS", result.message)

    def test_official_family_unlisted_variant_fails(self) -> None:
        result = classify_model_tag("fast", "qwen2.5-coder:32b")
        self.assertEqual(result.status, "fail")
        self.assertNotEqual(classify_model_tag("fast", "qwen2.5-coder:7b").status, "fail")

    def test_allowlist_length_changes_classify_accept_reject(self) -> None:
        extra = "brand-new-coder:7b"
        self.assertEqual(classify_model_tag("fast", extra).status, "fail")
        lengthened = OFFICIAL_LIBRARY_TAGS | {extra}
        with patch("local_coding_slm.safety.OFFICIAL_LIBRARY_TAGS", lengthened):
            self.assertEqual(classify_model_tag("fast", extra).status, "pass")
        shortened = OFFICIAL_LIBRARY_TAGS - {"qwen3.5:9b"}
        with patch("local_coding_slm.safety.OFFICIAL_LIBRARY_TAGS", shortened):
            self.assertEqual(classify_model_tag("fast", "qwen3.5:9b").status, "fail")
        self.assertEqual(classify_model_tag("fast", "qwen3.5:9b").status, "pass")

    def test_empty_fails(self) -> None:
        self.assertEqual(classify_model_tag("fast", "  ").status, "fail")


class TestLocalListen(unittest.TestCase):
    def test_parse_loopback_listen(self) -> None:
        # 127.0.0.1:11434 LISTEN  (11434 = 0x2CAA, 127.0.0.1 = 0100007F)
        text = (
            "  sl  local_address rem_address   st\n"
            "   0: 0100007F:2CAA 00000000:0000 0A 00000000:00000000\n"
        )
        self.assertEqual(parse_proc_net_listen_ports(text), [("127.0.0.1", 11434)])

    def test_wildcard_listen_fails(self) -> None:
        result = classify_local_listeners([("0.0.0.0", 11434)])
        self.assertEqual(result.status, "fail")

    def test_loopback_listen_passes(self) -> None:
        result = classify_local_listeners([("127.0.0.1", 11434)])
        self.assertEqual(result.status, "pass")

    def test_non_loopback_listen_fails(self) -> None:
        """Public, LAN, and disguised wildcard binds must not pass."""
        cases = (
            [("8.8.8.8", 11434)],
            [("192.168.1.10", 11434)],
            [("0:0:0:0:0:0:0:0", 11434)],
            [("::ffff:0.0.0.0", 11434)],
            [("169.254.169.254", 11434)],
        )
        for rows in cases:
            with self.subTest(rows=rows):
                result = classify_local_listeners(rows)
                self.assertEqual(result.status, "fail", result.message)

    def test_missing_listener_warns(self) -> None:
        result = classify_local_listeners([])
        self.assertEqual(result.status, "warn")

    def test_unparsed_listen_address_fails(self) -> None:
        """A LISTEN row whose address cannot be parsed is not 'Ollama is down'."""
        text = (
            "  sl  local_address rem_address   st\n"
            "   0: GGGGGGGG:2CAA 00000000:0000 0A 00000000:00000000\n"
        )
        result = classify_local_listeners(parse_proc_net_listen_ports(text))
        self.assertEqual(result.status, "fail", result.message)

    def test_lowercase_listen_state_fails_when_not_loopback(self) -> None:
        """State 0a is LISTEN. A wildcard row must not be dropped as 'not listening'."""
        text = (
            "  sl  local_address rem_address   st\n"
            "   0: 00000000:2CAA 00000000:0000 0a 00000000:00000000\n"
        )
        result = classify_local_listeners(parse_proc_net_listen_ports(text))
        self.assertEqual(result.status, "fail", result.message)


class TestHygiene(unittest.TestCase):
    def test_placeholder_ips_pass(self) -> None:
        result = classify_tracked_ipv4(
            [("spec.md", "example 192.168.0.0/16 and 192.0.2.0/24 and 127.0.0.1")]
        )
        self.assertEqual(result.status, "pass")

    def test_real_private_ip_fails(self) -> None:
        result = classify_tracked_ipv4([("README.md", "use 10.0.0.65")])
        self.assertEqual(result.status, "fail")

    def test_leading_zero_ipv4_fails(self) -> None:
        """A dotted quad Python rejects is still an address if an octet has a leading zero."""
        for text in ("010.010.010.010", "008.008.008.008"):
            with self.subTest(text=text):
                result = classify_tracked_ipv4([("README.md", f"host {text}")])
                self.assertEqual(result.status, "fail")
                self.assertIn(text, result.message)

    def test_integer_form_url_host_fails(self) -> None:
        """Decimal and hex URL hosts are addresses even though they are not dotted quads."""
        for text in ("http://134744072:11434", "http://0x08080808/"):
            with self.subTest(text=text):
                result = classify_tracked_ipv4([("README.md", f"OLLAMA_BASE_URL={text}")])
                self.assertEqual(result.status, "fail")
        loopback = classify_tracked_ipv4([("README.md", "see http://2130706433/")])
        self.assertEqual(loopback.status, "pass")

    def test_committed_workflow_yaml_ip_fails(self) -> None:
        """GitHub workflow YAML is committed text, so an address there must fail."""
        import subprocess
        import tempfile
        from pathlib import Path

        from local_coding_slm.safety import git_tracked_text_files

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow = root / ".github" / "workflows"
            workflow.mkdir(parents=True)
            (workflow / "deploy.yml").write_text("host: 8.8.8.8\n", encoding="utf-8")
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
            result = classify_tracked_ipv4(git_tracked_text_files(root))
        self.assertEqual(result.status, "fail")
        self.assertIn("8.8.8.8", result.message)

    def test_env_example_ok(self) -> None:
        text = "OLLAMA_BASE_URL=http://127.0.0.1:11434\n# http://<inference-host>:11434\n"
        self.assertEqual(classify_env_example(text).status, "pass")

    def test_env_ignored(self) -> None:
        self.assertEqual(classify_env_ignored(True).status, "pass")
        self.assertEqual(classify_env_ignored(False).status, "fail")


class TestRunChecks(unittest.TestCase):
    def test_safe_deployment_no_fail(self) -> None:
        results = run_checks(
            environ={
                "OLLAMA_BASE_URL": "http://127.0.0.1:11434",
                "OLLAMA_FAST_MODEL": "qwen3.5:9b",
                "OLLAMA_STRONG_MODEL": "devstral-small-2",
            },
            listen_rows=[("127.0.0.1", 11434)],
            tracked=[("spec.md", "http://127.0.0.1:11434")],
            env_ignored=True,
            env_example_text="OLLAMA_BASE_URL=http://127.0.0.1:11434\n",
        )
        self.assertEqual(worst_status(results), "pass")

    def test_git_ls_files_failure_fails_closed(self) -> None:
        """A failed git listing is not an empty tree with no addresses."""
        import subprocess
        from pathlib import Path

        safe = {
            "environ": {
                "OLLAMA_BASE_URL": "http://127.0.0.1:11434",
                "OLLAMA_FAST_MODEL": "qwen3.5:9b",
                "OLLAMA_STRONG_MODEL": "devstral-small-2",
            },
            "listen_rows": [("127.0.0.1", 11434)],
            "env_ignored": True,
            "env_example_text": "OLLAMA_BASE_URL=http://127.0.0.1:11434\n",
            "root": Path("/tmp/not-a-repo"),
        }
        failed = subprocess.CompletedProcess(["git", "ls-files", "-z"], 1, b"", b"fatal")
        with patch("local_coding_slm.safety.subprocess.run", return_value=failed):
            results = run_checks(**safe)
        ips = next(item for item in results if item.name == "committed_ips")
        self.assertEqual(ips.status, "fail")
        self.assertIn("could not read", ips.message)
        with patch("local_coding_slm.safety.subprocess.run", side_effect=OSError("git missing")):
            raised = run_checks(**safe)
        missing = next(item for item in raised if item.name == "committed_ips")
        self.assertEqual(missing.status, "fail")

    def test_unreadable_tracked_file_fails_closed(self) -> None:
        """A tracked text file that cannot be decoded is not an empty tree."""
        import subprocess
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "notes.md").write_bytes(b"see 8.8.8.8 \xff\n")
            subprocess.run(["git", "init"], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "add", "-A"], cwd=root, check=True, capture_output=True)
            results = run_checks(
                environ={
                    "OLLAMA_BASE_URL": "http://127.0.0.1:11434",
                    "OLLAMA_FAST_MODEL": "qwen3.5:9b",
                    "OLLAMA_STRONG_MODEL": "devstral-small-2",
                },
                listen_rows=[("127.0.0.1", 11434)],
                env_ignored=True,
                env_example_text="OLLAMA_BASE_URL=http://127.0.0.1:11434\n",
                root=root,
            )
        ips = next(item for item in results if item.name == "committed_ips")
        self.assertEqual(ips.status, "fail")
        self.assertIn("could not read", ips.message)

    def test_unofficial_library_tag_fails_run_checks(self) -> None:
        results = run_checks(
            environ={
                "OLLAMA_BASE_URL": "http://127.0.0.1:11434",
                "OLLAMA_FAST_MODEL": "some-random-coder:7b",
                "OLLAMA_STRONG_MODEL": "devstral-small-2",
            },
            skip_listen=True,
            tracked=[],
            env_ignored=True,
            env_example_text="OLLAMA_BASE_URL=http://127.0.0.1:11434\n",
        )
        self.assertEqual(worst_status(results), "fail")
        names = {item.name: item for item in results}
        self.assertEqual(names["OLLAMA_FAST_MODEL"].status, "fail")

    def test_trojan_shaped_tag_fails(self) -> None:
        results = run_checks(
            environ={
                "OLLAMA_BASE_URL": "http://127.0.0.1:11434",
                "OLLAMA_FAST_MODEL": "./weights/backdoor.gguf",
                "OLLAMA_STRONG_MODEL": "devstral-small-2",
            },
            skip_listen=True,
            tracked=[],
            env_ignored=True,
            env_example_text="OLLAMA_BASE_URL=http://127.0.0.1:11434\n",
        )
        self.assertEqual(worst_status(results), "fail")
        names = {item.name: item for item in results}
        self.assertEqual(names["OLLAMA_FAST_MODEL"].status, "fail")

    def test_hostname_url_fails_run_checks(self) -> None:
        results = run_checks(
            environ={
                "OLLAMA_BASE_URL": "https://my-ollama.evil.com",
                "OLLAMA_FAST_MODEL": "qwen3.5:9b",
                "OLLAMA_STRONG_MODEL": "devstral-small-2",
            },
            skip_listen=True,
            tracked=[],
            env_ignored=True,
            env_example_text="OLLAMA_BASE_URL=http://127.0.0.1:11434\n",
        )
        self.assertEqual(worst_status(results), "fail")
        names = {item.name: item for item in results}
        self.assertEqual(names["base_url"].status, "fail")

    def test_userinfo_and_decimal_ip_fail_run_checks(self) -> None:
        for url in ("http://127.0.0.1@evil.com", "http://2130706433:11434"):
            with self.subTest(url=url):
                results = run_checks(
                    environ={
                        "OLLAMA_BASE_URL": url,
                        "OLLAMA_FAST_MODEL": "qwen3.5:9b",
                        "OLLAMA_STRONG_MODEL": "devstral-small-2",
                    },
                    skip_listen=True,
                    tracked=[],
                    env_ignored=True,
                    env_example_text="OLLAMA_BASE_URL=http://127.0.0.1:11434\n",
                )
                self.assertEqual(worst_status(results), "fail")
                names = {item.name: item for item in results}
                self.assertEqual(names["base_url"].status, "fail")

    def test_check_result_ok(self) -> None:
        self.assertTrue(CheckResult("n", "warn", "m").ok)
        self.assertFalse(CheckResult("n", "fail", "m").ok)


if __name__ == "__main__":
    unittest.main()
