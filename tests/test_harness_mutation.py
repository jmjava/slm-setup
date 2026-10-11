"""Behavior tests for the harness module. Mutmut runs this file in CI."""

from __future__ import annotations

import asyncio
import unittest
from dataclasses import replace
from unittest.mock import MagicMock, patch

from local_coding_slm.eval.cases import CASES_BY_ID, WHITESPACE_GOLDEN
from local_coding_slm.eval.harness import (
    campaign_pass_end,
    format_orchestrated,
    format_summary,
    harness_exit_code,
    orchestrated_pass_end,
)
from local_coding_slm.eval.orchestrate import JobResult, OrchestrationJob
from local_coding_slm.eval.policy import FORMAT_SUFFIX, AttemptPlan
from local_coding_slm.eval.record import AttemptRecord
from local_coding_slm.eval.review import accept
from local_coding_slm.eval.routing import mechanical_signals
import local_coding_slm.eval.harness as harness


def _row(**kwargs: object) -> AttemptRecord:
    base: dict[str, object] = {
        "job": "jobA",
        "case_id": "whitespace_extract",
        "attempt": 1,
        "model": "fast",
        "suffix": "",
        "passed": True,
        "first_failure": None,
        "mcp_ms": 2.0,
        "score_ms": 0.5,
        "elapsed_ms": 1.0,
        "response_chars": 10,
        "backend": "stub",
        "profile": "golden",
        "layers": {"format": "pass"},
    }
    base.update(kwargs)
    return AttemptRecord(**base)  # type: ignore[arg-type]


def _job(**kwargs: object) -> JobResult:
    base: dict[str, object] = {
        "job": "keep_one",
        "case_id": "",
        "delegated": False,
        "route_reason": "incident_debug",
        "outcome": "kept_on_premium",
        "applied": True,
        "apply_source": "premium",
        "applied_text": "stay",
        "blocked": None,
        "local_models": (),
        "local_suffixes": (),
        "local_attempts": 0,
        "review_decision": None,
        "review_reviewer": None,
        "local_passed": None,
        "local_review_notes": "",
    }
    base.update(kwargs)
    return JobResult(**base)  # type: ignore[arg-type]


class _Block:
    def __init__(self, text: str | None) -> None:
        self.text = text


class _Tool:
    def __init__(self, blocks: list[object]) -> None:
        self.content = blocks


class _Session:
    def __init__(self, tools: list[_Tool]) -> None:
        self._tools = list(tools)
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def call_tool(self, name: str, payload: dict[str, object]) -> _Tool:
        self.calls.append((name, dict(payload)))
        return self._tools.pop(0)


def _golden_tool() -> _Tool:
    mid = len(WHITESPACE_GOLDEN) // 2
    return _Tool(
        [
            object(),
            _Block(None),
            _Block(""),
            _Block(WHITESPACE_GOLDEN[:mid]),
            _Block(WHITESPACE_GOLDEN[mid:]),
        ]
    )


def _text_tool(text: str) -> _Tool:
    return _Tool([_Block(text)])


class ExitAndSummaryTests(unittest.TestCase):
    def test_exit_code_boundaries(self) -> None:
        self.assertEqual(harness_exit_code(1.0, 0), 1)
        self.assertEqual(harness_exit_code(0.0, 1), 1)
        self.assertEqual(harness_exit_code(-0.1, 2), 1)
        self.assertEqual(harness_exit_code(1.0, 1), 0)
        self.assertEqual(harness_exit_code(0.5, 1, min_pass_end=0.5), 0)
        self.assertEqual(harness_exit_code(0.49, 1, min_pass_end=0.5), 1)
        self.assertIsInstance(harness_exit_code(1.0, 1), int)

    def test_campaign_pass_end_counts_cases(self) -> None:
        empty_rate, empty_n = campaign_pass_end([])
        self.assertEqual((empty_rate, empty_n), (0.0, 0))
        self.assertIsInstance(empty_rate, float)
        self.assertIsInstance(empty_n, int)
        rows = [
            _row(job="a", passed=True),
            _row(job="b", passed=False, first_failure="format"),
        ]
        rate, n = campaign_pass_end(rows)
        self.assertEqual((rate, n), (0.5, 2))
        self.assertIsInstance(rate, float)
        self.assertIsInstance(n, int)

    def test_orchestrated_pass_end_ignores_kept_jobs(self) -> None:
        self.assertEqual(orchestrated_pass_end([]), (0.0, 0))
        self.assertEqual(orchestrated_pass_end([_job()]), (0.0, 0))
        delegated = _job(job="d", delegated=True)
        self.assertEqual(orchestrated_pass_end([delegated]), (0.0, 1))
        self.assertEqual(
            orchestrated_pass_end([replace(delegated, local_passed=False)]),
            (0.0, 1),
        )
        self.assertEqual(
            orchestrated_pass_end([replace(delegated, local_passed=True)]),
            (1.0, 1),
        )
        half = orchestrated_pass_end(
            [
                replace(delegated, job="a", local_passed=True),
                replace(delegated, job="b", local_passed=False),
            ]
        )
        self.assertEqual(half, (0.5, 2))

    def test_format_summary_empty_and_mixed(self) -> None:
        self.assertEqual(
            format_summary([]),
            "\n".join(
                [
                    "backend=? profile=?",
                    "cases=0 attempts=0",
                    "pass@1=0.00 pass@end=0.00 escalated=0.00",
                    "mcp_ms p50=0.0 max=0.0",
                    "first_failure={}",
                ]
            ),
        )
        rows = [
            _row(
                passed=False,
                first_failure="format",
                attempt=1,
                elapsed_ms=1.0,
                mcp_ms=2.0,
                backend="stub",
                profile="golden",
            ),
            _row(
                passed=True,
                first_failure=None,
                attempt=2,
                model="strong",
                elapsed_ms=3.5,
                mcp_ms=4.0,
                backend="live",
                profile="observed",
            ),
        ]
        self.assertEqual(
            format_summary(rows),
            "\n".join(
                [
                    "backend=stub profile=golden",
                    "cases=1 attempts=2",
                    "pass@1=0.00 pass@end=1.00 escalated=1.00",
                    "mcp_ms p50=3.0 max=4.0",
                    "first_failure={'format': 1}",
                    "  jobA: pass_at=2 attempts=2 escalated=True ms=4.5",
                ]
            ),
        )

    def test_format_orchestrated_counts_and_models(self) -> None:
        results = [
            _job(),
            _job(
                job="do_one",
                case_id="whitespace_extract",
                delegated=True,
                route_reason="mechanical",
                outcome="applied_local",
                applied=True,
                apply_source="local",
                applied_text="x",
                local_models=("fast",),
                local_attempts=1,
                review_decision="accept",
                review_reviewer="premium",
                local_passed=True,
            ),
        ]
        self.assertEqual(
            format_orchestrated(results),
            "\n".join(
                [
                    "jobs=2 applied=2 delegated=1",
                    "pass@end=1.00 delegated_jobs=1",
                    "  keep_one: delegated=False route=incident_debug "
                    "outcome=kept_on_premium source=premium models=-",
                    "  do_one: delegated=True route=mechanical "
                    "outcome=applied_local source=local models=['fast']",
                ]
            ),
        )


class AttemptTests(unittest.TestCase):
    def test_one_attempt_records_score_timing_and_payload(self) -> None:
        case = CASES_BY_ID["whitespace_extract"]
        session = _Session([_golden_tool()])
        plan = AttemptPlan(model="fast", suffix="")
        ticks = iter([10.0, 10.00123456, 20.0, 20.00246813])
        with patch.object(harness.time, "perf_counter", lambda: next(ticks)):
            item = asyncio.run(
                harness._one_attempt(session, case, plan, "stub", "golden", "job-9", 2)
            )
        self.assertEqual(session.calls[0][0], case.tool)
        payload = session.calls[0][1]
        self.assertEqual(payload["task"], case.task)
        self.assertEqual(payload["files"], list(case.files))
        self.assertEqual(payload["language"], case.language)
        self.assertEqual(payload["model"], "fast")
        self.assertEqual(payload["max_tokens"], case.max_tokens)
        self.assertEqual(payload["style"], case.style)
        self.assertTrue(item.record.passed)
        self.assertIsNone(item.record.first_failure)
        self.assertEqual(item.record.attempt, 2)
        self.assertEqual(item.record.job, "job-9")
        self.assertEqual(item.record.case_id, case.id)
        self.assertEqual(item.record.backend, "stub")
        self.assertEqual(item.record.profile, "golden")
        self.assertEqual(item.record.suffix, "")
        self.assertEqual(item.record.response_chars, len(WHITESPACE_GOLDEN))
        self.assertEqual(item.text, WHITESPACE_GOLDEN)
        self.assertEqual(item.record.mcp_ms, 1.235)
        self.assertEqual(item.record.score_ms, 2.468)
        self.assertEqual(item.record.elapsed_ms, 3.703)
        self.assertEqual(
            item.record.layers,
            {layer.name: layer.status for layer in item.scored.layers},  # type: ignore[union-attr]
        )

    def test_one_attempt_omits_style_when_unset(self) -> None:
        case = replace(CASES_BY_ID["whitespace_extract"], style="")
        session = _Session([_text_tool("nope")])
        plan = AttemptPlan(model="strong", suffix="note")
        item = asyncio.run(
            harness._one_attempt(session, case, plan, "live", "live", "job-1", 3)
        )
        payload = session.calls[0][1]
        self.assertNotIn("style", payload)
        self.assertEqual(payload["task"], f"{case.task}\n\nnote")
        self.assertEqual(payload["model"], "strong")
        self.assertFalse(item.record.passed)
        self.assertEqual(item.record.first_failure, "format")
        self.assertEqual(item.record.suffix, "note")
        self.assertEqual(item.record.response_chars, len("nope"))

    def test_local_mcp_repairs_format_then_stops(self) -> None:
        case = CASES_BY_ID["whitespace_extract"]
        session = _Session([_text_tool("nope"), _golden_tool()])
        attempts = asyncio.run(
            harness._run_local_mcp(
                session, case, job="whitespace_extract#1", backend="stub", profile="golden"
            )
        )
        self.assertEqual(len(attempts), 2)
        self.assertEqual(attempts[0].record.attempt, 1)
        self.assertFalse(attempts[0].record.passed)
        self.assertEqual(attempts[0].record.first_failure, "format")
        self.assertEqual(attempts[0].record.model, "fast")
        self.assertEqual(attempts[0].record.suffix, "")
        self.assertEqual(attempts[1].record.attempt, 2)
        self.assertTrue(attempts[1].record.passed)
        self.assertEqual(attempts[1].record.model, "fast")
        self.assertEqual(attempts[1].record.suffix, FORMAT_SUFFIX)
        self.assertEqual(
            session.calls[1][1]["task"],
            f"{case.task}\n\n{FORMAT_SUFFIX}",
        )


class OrchestratedHarnessTests(unittest.TestCase):
    def test_keep_does_not_call_the_session(self) -> None:
        session = _Session([])
        job = OrchestrationJob(
            id="keep_one",
            signals=mechanical_signals(incident_debug=True),
            premium_keep_text="stay",
        )
        result = asyncio.run(
            harness._run_orchestrated_job(session, job, backend="live", profile="golden")
        )
        self.assertEqual(session.calls, [])
        self.assertFalse(result.delegated)
        self.assertEqual(result.outcome, "kept_on_premium")
        self.assertEqual(result.applied_text, "stay")
        self.assertTrue(result.applied)
        self.assertEqual(result.apply_source, "premium")

    def test_delegated_job_without_case_raises(self) -> None:
        job = OrchestrationJob(id="bare", signals=mechanical_signals())
        with self.assertRaises(ValueError) as caught:
            asyncio.run(
                harness._run_orchestrated_job(
                    _Session([]), job, backend="stub", profile="golden"
                )
            )
        self.assertEqual(str(caught.exception), "bare: delegated jobs need an eval_case")

    def test_security_sensitive_job_collects_local_review_notes(self) -> None:
        case = CASES_BY_ID["whitespace_extract"]
        review = _Tool([_Block("alpha"), object(), _Block("beta")])
        session = _Session([review, _golden_tool()])
        job = OrchestrationJob(
            id="sec",
            signals=mechanical_signals(security_sensitive=True),
            eval_case=case,
            review=accept(notes="apply"),
        )
        result = asyncio.run(
            harness._run_orchestrated_job(session, job, backend="stub", profile="golden")
        )
        self.assertEqual(session.calls[0][0], "local_review")
        review_payload = session.calls[0][1]
        self.assertEqual(review_payload["max_tokens"], 400)
        self.assertEqual(review_payload["model"], "fast")
        self.assertEqual(review_payload["language"], case.language)
        self.assertEqual(review_payload["files"], list(case.files))
        self.assertIn("First-pass review only", str(review_payload["task"]))
        self.assertIn(case.task, str(review_payload["task"]))
        self.assertEqual(result.local_review_notes, "alphabeta")
        self.assertTrue(result.delegated)
        self.assertTrue(result.local_passed)
        self.assertEqual(result.outcome, "applied_local")
        self.assertEqual(session.calls[1][0], case.tool)

    def test_existing_review_notes_skip_local_review(self) -> None:
        case = CASES_BY_ID["whitespace_extract"]
        session = _Session([_golden_tool()])
        job = OrchestrationJob(
            id="sec-noted",
            signals=mechanical_signals(security_sensitive=True),
            eval_case=case,
            review=accept(),
            local_review_notes="kept-notes",
        )
        result = asyncio.run(
            harness._run_orchestrated_job(session, job, backend="stub", profile="observed")
        )
        self.assertEqual([name for name, _payload in session.calls], [case.tool])
        self.assertEqual(result.local_review_notes, "kept-notes")
        self.assertTrue(result.local_passed)


class CampaignTests(unittest.TestCase):
    def _cases(self) -> tuple[object, object]:
        base = CASES_BY_ID["whitespace_extract"]
        return base, replace(base, id="other_extract")

    def test_campaign_repeat_order_and_forwarded_timing(self) -> None:
        first, second = self._cases()
        session = _Session([_golden_tool() for _ in range(4)])
        captured: list[tuple[object, ...]] = []

        async def _with_session(*, backend, profile, fast_ms, strong_ms, base_url, body):
            captured.append((backend, profile, fast_ms, strong_ms, base_url))
            await body(session, backend, profile)

        with patch.object(harness, "CASES", (first, second)):
            with patch.object(harness, "_with_session", _with_session):
                rows = asyncio.run(
                    harness.run_campaign(
                        backend="stub",
                        profile="golden",
                        repeat=2,
                        fast_ms=1.5,
                        strong_ms=4.5,
                        base_url="http://127.0.0.1:9",
                    )
                )
        self.assertEqual(
            [row.job for row in rows],
            [
                f"{first.id}#1",
                f"{second.id}#1",
                f"{first.id}#2",
                f"{second.id}#2",
            ],
        )
        self.assertTrue(all(row.passed for row in rows))
        self.assertEqual(
            captured,
            [("stub", "golden", 1.5, 4.5, "http://127.0.0.1:9")],
        )

    def test_campaign_rejects_empty_selection_and_bad_repeat(self) -> None:
        first, _second = self._cases()

        async def _with_session(*, backend, profile, fast_ms, strong_ms, base_url, body):
            await body(object(), backend, profile)

        with patch.object(harness, "CASES", (first,)):
            with patch.object(harness, "_with_session", _with_session):
                with self.assertRaises(ValueError) as missing:
                    asyncio.run(
                        harness.run_campaign(
                            backend="stub",
                            profile="golden",
                            case_ids=["missing"],
                        )
                    )
                with self.assertRaises(ValueError) as repeat:
                    asyncio.run(
                        harness.run_campaign(
                            backend="stub",
                            profile="golden",
                            case_ids=[first.id],
                            repeat=0,
                        )
                    )
        self.assertEqual(str(missing.exception), "no cases selected")
        self.assertEqual(str(repeat.exception), "repeat must be >= 1")

    def test_orchestrated_campaign_filters_jobs(self) -> None:
        case = CASES_BY_ID["whitespace_extract"]
        keep = OrchestrationJob(
            id="keep_one",
            signals=mechanical_signals(incident_debug=True),
            premium_keep_text="stay",
        )
        delegated = OrchestrationJob(
            id="do_one",
            signals=mechanical_signals(),
            eval_case=case,
            review=accept(),
        )
        session = _Session([_golden_tool()])
        captured: list[tuple[object, ...]] = []

        async def _with_session(*, backend, profile, fast_ms, strong_ms, base_url, body):
            captured.append((fast_ms, strong_ms, base_url, profile))
            await body(session, backend, profile)

        with patch.object(harness, "MCP_JOBS", (keep, delegated)):
            with patch.object(harness, "_with_session", _with_session):
                both = asyncio.run(
                    harness.run_orchestrated_campaign(
                        backend="stub",
                        profile="golden",
                        fast_ms=3.0,
                        strong_ms=9.0,
                    )
                )
                only_keep = asyncio.run(
                    harness.run_orchestrated_campaign(
                        backend="stub",
                        profile="observed",
                        job_ids=["keep_one"],
                        fast_ms=3.0,
                        strong_ms=9.0,
                    )
                )
                with self.assertRaises(ValueError) as missing:
                    asyncio.run(
                        harness.run_orchestrated_campaign(
                            backend="stub",
                            profile="golden",
                            job_ids=["missing"],
                        )
                    )
        self.assertEqual([item.job for item in both], ["keep_one", "do_one"])
        self.assertFalse(both[0].delegated)
        self.assertEqual(both[0].applied_text, "stay")
        self.assertTrue(both[1].delegated)
        self.assertEqual(both[1].outcome, "applied_local")
        self.assertEqual([item.job for item in only_keep], ["keep_one"])
        self.assertEqual(session.calls[0][0], case.tool)
        self.assertEqual(captured[0], (3.0, 9.0, None, "golden"))
        self.assertEqual(str(missing.exception), "no orchestration jobs selected")


class SessionBootstrapTests(unittest.TestCase):
    def test_stub_backend_sets_loopback_and_closes_stub(self) -> None:
        made: list[tuple[dict[str, object], MagicMock]] = []

        def _factory(**kwargs: object) -> MagicMock:
            stub = MagicMock()
            stub.base_url = "http://127.0.0.1:9"
            stub.__enter__.return_value = stub
            made.append((kwargs, stub))
            return stub

        captured: dict[str, object] = {}
        seen: list[tuple[object, str, str, bool]] = []

        def _stdio(params: object) -> object:
            captured["params"] = params
            return _AsyncCM(("R", "W"))

        async def _body(session: _ReadySession, backend: str, profile: str) -> None:
            seen.append((session.read, backend, profile, session.ready))

        with patch("local_coding_slm.eval.stub_ollama.StubOllama", _factory):
            with patch("mcp.client.stdio.stdio_client", _stdio):
                with patch("mcp.ClientSession", _ReadySession):
                    with patch("mcp.StdioServerParameters", _Params):
                        asyncio.run(
                            harness._with_session(
                                backend="stub",
                                profile="observed",
                                fast_ms=1.5,
                                strong_ms=4.5,
                                base_url=None,
                                body=_body,
                            )
                        )
        self.assertEqual(seen, [("R", "stub", "observed", True)])
        self.assertEqual(made[0][0]["profile"], "observed")
        self.assertEqual(made[0][0]["fast_ms"], 1.5)
        self.assertEqual(made[0][0]["strong_ms"], 4.5)
        made[0][1].__exit__.assert_called_once_with(None, None, None)
        params = captured["params"]
        assert isinstance(params, _Params)
        self.assertEqual(params.command, __import__("sys").executable)
        self.assertEqual(
            params.args,
            [str(harness.ROOT / "src" / "local_coding_slm" / "server.py")],
        )
        self.assertEqual(params.cwd, str(harness.ROOT))
        self.assertIn(str(harness.ROOT / "src"), params.env["PYTHONPATH"])
        self.assertEqual(params.env["OLLAMA_BASE_URL"], "http://127.0.0.1:9")

    def test_live_backend_renames_profile_and_skips_stub(self) -> None:
        factory = MagicMock()
        captured: dict[str, _Params] = {}
        seen: list[str] = []

        def _stdio(params: _Params) -> object:
            captured["params"] = params
            return _AsyncCM(("R", "W"))

        async def _body(_session: object, backend: str, profile: str) -> None:
            seen.append(f"{backend}:{profile}")

        with patch.dict("os.environ", {"OLLAMA_BASE_URL": "http://example.invalid"}, clear=False):
            with patch("local_coding_slm.eval.stub_ollama.StubOllama", factory):
                with patch("mcp.client.stdio.stdio_client", _stdio):
                    with patch("mcp.ClientSession", _ReadySession):
                        with patch("mcp.StdioServerParameters", _Params):
                            asyncio.run(
                                harness._with_session(
                                    backend="live",
                                    profile="golden",
                                    fast_ms=8.0,
                                    strong_ms=25.0,
                                    base_url="http://127.0.0.1:8",
                                    body=_body,
                                )
                            )
        factory.assert_not_called()
        self.assertEqual(seen, ["live:live"])
        self.assertEqual(captured["params"].env["OLLAMA_BASE_URL"], "http://127.0.0.1:8")

    def test_live_without_base_url_leaves_ollama_env_unset(self) -> None:
        captured: dict[str, _Params] = {}

        def _stdio(params: _Params) -> object:
            captured["params"] = params
            return _AsyncCM(("R", "W"))

        async def _body(_session: object, _backend: str, profile: str) -> None:
            self.assertEqual(profile, "live")

        cleaned = {key: value for key, value in __import__("os").environ.items() if key != "OLLAMA_BASE_URL"}
        with patch.dict("os.environ", cleaned, clear=True):
            with patch("mcp.client.stdio.stdio_client", _stdio):
                with patch("mcp.ClientSession", _ReadySession):
                    with patch("mcp.StdioServerParameters", _Params):
                        asyncio.run(
                            harness._with_session(
                                backend="live",
                                profile="golden",
                                fast_ms=8.0,
                                strong_ms=25.0,
                                base_url=None,
                                body=_body,
                            )
                        )
        self.assertNotIn("OLLAMA_BASE_URL", captured["params"].env)

    def test_unknown_backend_raises_before_stdio(self) -> None:
        stdio = MagicMock()
        with patch("mcp.client.stdio.stdio_client", stdio):
            with self.assertRaises(ValueError) as caught:
                asyncio.run(
                    harness._with_session(
                        backend="nope",
                        profile="golden",
                        fast_ms=1.0,
                        strong_ms=1.0,
                        base_url=None,
                        body=_unused_body,
                    )
                )
        self.assertEqual(str(caught.exception), "backend must be 'stub' or 'live'")
        stdio.assert_not_called()

    def test_stub_closes_when_body_raises(self) -> None:
        made: list[MagicMock] = []

        def _factory(**_kwargs: object) -> MagicMock:
            stub = MagicMock()
            stub.base_url = "http://127.0.0.1:9"
            stub.__enter__.return_value = stub
            made.append(stub)
            return stub

        async def _body(_session: object, _backend: str, _profile: str) -> None:
            raise RuntimeError("boom")

        with patch("local_coding_slm.eval.stub_ollama.StubOllama", _factory):
            with patch("mcp.client.stdio.stdio_client", lambda _params: _AsyncCM(("R", "W"))):
                with patch("mcp.ClientSession", _ReadySession):
                    with patch("mcp.StdioServerParameters", _Params):
                        with self.assertRaises(RuntimeError):
                            asyncio.run(
                                harness._with_session(
                                    backend="stub",
                                    profile="golden",
                                    fast_ms=1.0,
                                    strong_ms=2.0,
                                    base_url=None,
                                    body=_body,
                                )
                            )
        made[0].__exit__.assert_called_once_with(None, None, None)


class _AsyncCM:
    def __init__(self, value: object) -> None:
        self.value = value

    async def __aenter__(self) -> object:
        return self.value

    async def __aexit__(self, *_args: object) -> bool:
        return False


class _ReadySession:
    def __init__(self, read: object, write: object) -> None:
        self.read = read
        self.write = write
        self.ready = False

    async def initialize(self) -> None:
        self.ready = True

    async def __aenter__(self) -> _ReadySession:
        return self

    async def __aexit__(self, *_args: object) -> bool:
        return False


class _Params:
    def __init__(self, *, command: str, args: list[str], env: dict[str, str], cwd: str) -> None:
        self.command = command
        self.args = args
        self.env = env
        self.cwd = cwd


async def _unused_body(_session: object, _backend: str, _profile: str) -> None:
    raise AssertionError("body should not run")
