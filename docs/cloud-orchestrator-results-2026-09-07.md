# Cloud Agent orchestrator results — 2026-09-07

Dated note from a Cursor Cloud Agent. This VM has **no GPU and no Ollama**.
The local worker is the loopback stub. The premium role is this agent
inspecting layer results and the apply-gate outcomes. It is **not** a
desktop Cursor session against `qwen3.5:9b` / `devstral-small-2`.

Commands (all passed):

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/run_eval.py
.venv/bin/python scripts/run_orchestration.py
.venv/bin/python scripts/run_harness.py --backend stub --profile golden --fast-ms 1 --strong-ms 1
.venv/bin/python scripts/run_harness.py --backend stub --profile observed --fast-ms 1 --strong-ms 1
.venv/bin/python scripts/run_harness.py --backend stub --profile golden --orchestrate --fast-ms 1 --strong-ms 1
```

## Unit suite

**83 tests passed.** Includes fixture scoring, A6 behavior (shape-only
`def test` fails), local fast→strong policy, and MCP + apply-gate
integration.

## Fixture corpus

24 fixtures: every golden passes all four layers; known-fail fixtures
stop at the intended layer (format / structure / behavior / transport).

New executable cases exercised here: `move_function_imports`,
`extract_shared_parser`, `split_pipeline`, `implement_clamp`,
`explain_clamp`, `review_login`.

## Stub MCP harness (not GPU time)

Golden, 10 jobs, 10 attempts: **pass@1 = 1.00**, escalated = 0.00.
`mcp_ms` p50 ≈ 5 ms (loopback stub).

Observed, 10 jobs, 21 attempts: **pass@1 = 0.00**, **pass@end = 1.00**,
escalated = 0.30. First failures: format 4, structure 5, behavior 2.
Repair success is pass@2 (or pass@3 for `whitespace_extract_vague`).

## Premium review (this agent)

I treated the scripted apply-gate outcomes as the verdicts I would give
on these **stub** patches:

| Job | Route | My verdict | Why |
| --- | --- | --- | --- |
| keep_incident / architecture / live_tools / ambiguous | keep | keep on premium | Spec §8 do-not-delegate |
| mcp_extract_accept | mechanical | **accept** | Layers passed; helper is module-level |
| mcp_move_accept | mechanical | **accept** | `clamp` moved; `report.py` imports updated; oracles match |
| mcp_parser_accept | mechanical | **accept** | Shared `parse_fields`; email/qty oracles match |
| mcp_pipeline_accept | mechanical | **accept** | `run(" 1, 2, 3 ") == "6"` |
| mcp_tests_accept | mechanical | **accept** | Generated tests actually execute (A6) |
| mcp_explain_accept | mechanical | **accept** | Names clamp / lo / hi and clipping |
| mcp_code_rewrite | mechanical | **rewrite** | Local clamp is correct; I would still swap inverted bounds |
| mcp_review_notes_only | mechanical + security | **reject apply** | `local_review` flagged None/auth; that is notes, not a patch |
| mcp_reject_security | mechanical + security | **reject** | Do not apply until a human/premium pass on bounds |

Closed loop: **13 jobs, 9 delegated, 11 applied, 2 held.** Keep jobs did
not call `local_*`. Rejected jobs had passing local layers and still did
not apply.

## What this note is not

- Live tok/s, pass@1 on the workstation tags, or GPU placement
- Proof that desktop Cursor's tool picker chose `local_refactor`
- A claim that stub `mcp_ms` is model latency
