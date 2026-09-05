"""Unit tests for defensive deployment safety checks."""

from __future__ import annotations

import unittest

from local_coding_slm.safety import (
    CheckResult,
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

    def test_empty_fails(self) -> None:
        self.assertEqual(classify_base_url("").status, "fail")


class TestClassifyModelTag(unittest.TestCase):
    def test_starter_tags_pass(self) -> None:
        self.assertEqual(classify_model_tag("fast", "qwen3.5:9b").status, "pass")
        self.assertEqual(classify_model_tag("strong", "devstral-small-2").status, "pass")

    def test_path_or_url_fails(self) -> None:
        self.assertEqual(classify_model_tag("fast", "https://example.com/model.gguf").status, "fail")
        self.assertEqual(classify_model_tag("fast", "/tmp/mystery.gguf").status, "fail")
        self.assertEqual(classify_model_tag("fast", "user/trojan-finetune").status, "fail")

    def test_unknown_library_name_warns(self) -> None:
        self.assertEqual(classify_model_tag("fast", "some-random-coder:7b").status, "warn")

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

    def test_missing_listener_warns(self) -> None:
        result = classify_local_listeners([])
        self.assertEqual(result.status, "warn")


class TestHygiene(unittest.TestCase):
    def test_placeholder_ips_pass(self) -> None:
        result = classify_tracked_ipv4(
            [("spec.md", "example 192.168.0.0/16 and 192.0.2.0/24 and 127.0.0.1")]
        )
        self.assertEqual(result.status, "pass")

    def test_real_private_ip_fails(self) -> None:
        result = classify_tracked_ipv4([("README.md", "use 10.0.0.65")])
        self.assertEqual(result.status, "fail")

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

    def test_check_result_ok(self) -> None:
        self.assertTrue(CheckResult("n", "warn", "m").ok)
        self.assertFalse(CheckResult("n", "fail", "m").ok)


if __name__ == "__main__":
    unittest.main()
