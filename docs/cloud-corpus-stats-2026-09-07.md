# Cloud Agent 20-case corpus stats — 2026-09-07

Dated note from a Cursor Cloud Agent. This VM has **no GPU and no Ollama**.
The worker is the loopback stub. These rates measure the scorer, stub
failover policy, and stdio MCP loop. They are **not** live
`qwen3.5:9b` / `devstral-small-2` quality.

Commands (all passed):

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/run_eval.py
.venv/bin/python scripts/run_orchestration.py
.venv/bin/python scripts/run_harness.py --backend stub --profile golden --fast-ms 1 --strong-ms 1
.venv/bin/python scripts/run_harness.py --backend stub --profile observed --fast-ms 1 --strong-ms 1 --out eval-runs/observed-20
.venv/bin/python scripts/run_harness.py --backend stub --profile golden --orchestrate --fast-ms 1 --strong-ms 1
```

## Unit suite

**109 tests passed.** Fixture scoring now covers 20 cases / 41 fixtures.
`by_tool` and `by_category` rates are tested without MCP.

## Stub MCP harness (not GPU time)

Golden, 20 jobs, 20 attempts: **pass@1 = 1.00**, escalated = 0.00.

Observed, 20 jobs, 42 attempts: **pass@1 = 0.00**, **pass@end = 1.00**,
escalated = 0.40. First failures: format 6, structure 10, behavior 6.

| Tool | n | pass@1 | pass@end | escalated | first_failure |
| --- | ---: | ---: | ---: | ---: | --- |
| `local_refactor` | 10 | 0.00 | 1.00 | 0.20 | format 6, structure 6 |
| `local_code` | 3 | 0.00 | 1.00 | 1.00 | behavior 3 |
| `local_generate_tests` | 3 | 0.00 | 1.00 | 1.00 | behavior 3 |
| `local_explain` | 2 | 0.00 | 1.00 | 0.00 | structure 2 |
| `local_review` | 2 | 0.00 | 1.00 | 0.00 | structure 2 |

| Category | n | pass@1 | pass@end | escalated | first_failure |
| --- | ---: | ---: | ---: | ---: | --- |
| extract | 4 | 0.00 | 1.00 | 0.00 | format 2, structure 2 |
| prompt_contract | 2 | 0.00 | 1.00 | 1.00 | structure 4 |
| rename | 2 | 0.00 | 1.00 | 0.00 | format 2 |
| split | 2 | 0.00 | 1.00 | 0.00 | format 2 |
| implement | 3 | 0.00 | 1.00 | 1.00 | behavior 3 |
| tests | 3 | 0.00 | 1.00 | 1.00 | behavior 3 |
| explain | 2 | 0.00 | 1.00 | 0.00 | structure 2 |
| review | 2 | 0.00 | 1.00 | 0.00 | structure 2 |

Vague-prompt cases (`whitespace_extract_vague`, `extract_dataclass_vague`)
stay wrong on every fast call, so they escalate to strong (pass@3).
Implement and test cases fail behavior on the first fast reply and
escalate. Format/structure-only cases repair on fast (pass@2).

Categories label the committed corpus. They are **not** a learned
task classifier.

## Apply gate

Unchanged 13-job scripted loop: 9 delegated, 11 applied, 2 held.
Keep jobs did not call `local_*`.

## What this note is not

- Live tok/s or pass@1 on the workstation tags
- Proof that desktop Cursor's tool picker chose `local_refactor`
- A claim that stub `mcp_ms` is model latency
