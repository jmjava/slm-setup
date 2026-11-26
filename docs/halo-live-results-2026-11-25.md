# Halo live results — 2026-11-25

Same-machine Halo acceptance and three independent live harness sessions.
`host_class=halo-395`, `backend=vulkan`. Loopback Ollama only. No hostname,
LAN address, or account name.

These rows are the first GPU sessions for this corpus commit. They are not a
frozen Part A estimate. An earlier same-day harness directory was discarded
(`backend=cpu`). Its rates are omitted.

Harness policy and reporting choices are grounded in the Sources section of
[evaluation-protocol.md](evaluation-protocol.md#sources).

## Environment

- Ollama 0.40.17 on loopback
- Fast model: `qwen3.5:9b`
- Strong model: `devstral-small-2`
- Context: 16384
- Corpus commit: `1c15fe3393964f3aa5f8251f3d44c5fcfa4e17a5`
- Placement: during the short chats and all three sessions, `ollama ps`
  showed both tags at **100% GPU**, context 16384. The runtime log named
  Vulkan0 on an 8060S-class GPU and offloaded every layer. Processor was
  not 100% CPU.

## Acceptance

A4 is skipped because this profile is same-machine. A8 and A9 were not run.

| ID | Result | Evidence |
| --- | --- | --- |
| A1 | Pass | Tags list includes `qwen3.5:9b` and `devstral-small-2` |
| A2 | Pass | Warm fast chat returned in 0.1s; `ollama ps` showed 100% GPU |
| A3 | Pass | Warm strong chat returned in 0.3s; `ollama ps` showed 100% GPU |
| A4 | Skip | Same-machine. Spec skips the SSH / unauthorized-LAN check here |
| A5 | Pass | `local_status` via stdio MCP: both tags present on loopback |
| A6 | Fail | One fast `local_generate_tests` shot for `test_add_execute`. Format and structure passed; behavior failed because the generated file called `pytest.raises` without importing `pytest`. This shot is not pass@1 |
| A7 | Pass | Cursor called `local_explain` on a two-line `add` function. At `max_tokens` 700 the tool returned a one-sentence explanation. Budgets of 80 and 200 returned an empty message |
| A11 | Pass | Tracked private-address hits are documented placeholders and unit-test literals. Email hits are example domains. Deployment checker `committed_ips` passed |
| A12 | Pass | `scripts/check_deployment_safety.py`: loopback URL, official tags, `.env` ignored, listener on loopback |
| A13 | Pass | Vulkan placement above. Both starter tags stayed on GPU at context 16384 through the harness |

## Live harness

Command shape, once per new directory:

```bash
set -a && source .env && set +a
.venv/bin/python scripts/run_harness.py --backend live --out eval-runs/halo-395-gpu-sN
```

Full 16-case corpus, one repeat, fast then one same-model repair then strong.
`pass@1` counts only attempt 1. Raw `eval-runs/` stays gitignored.

| Session | Cases | Attempts | pass@1 | pass@end | Escalated | mcp_ms p50 | mcp_ms max | First-failure counts |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gpu-s1 | 16 | 36 | 0.19 (3/16) | 0.69 (11/16) | 0.56 | 9373 | 39790 | format 19, structure 2, behavior 1, transport 3 |
| gpu-s2 | 16 | 36 | 0.31 (5/16) | 0.69 (11/16) | 0.62 | 9713 | 32943 | format 19, structure 5, transport 1 |
| gpu-s3 | 16 | 36 | 0.31 (5/16) | 0.62 (10/16) | 0.69 | 8674 | 24821 | format 20, structure 3, behavior 1, transport 2 |

Pooled across the three sessions: **pass@1 = 13/48 (0.27)**, **pass@end = 32/48 (0.67)**.
Wall clock was about 7.0, 6.7, and 6.3 minutes. Attempt-1 failures over 48
case-sessions: pass 13, format 27, transport 5, structure 3. All-attempt
failure counts over 108 attempts: format 58, structure 10, transport 6,
behavior 2.

Transport failures were 39-character empty-message errors. On `qwen3.5:9b`,
the predict budget can be spent in the thinking channel and leave `content`
empty. That is a client interaction with this tag, not a loss of GPU
placement.

`pass_at` is the attempt that passed. A dash means the case was exhausted
after three attempts.

| Case | s1 | s2 | s3 | Attempt-1 failure (s1, s2, s3) |
| --- | --- | --- | --- | --- |
| `whitespace_extract` | 1 | 1 | 1 | pass, pass, pass |
| `whitespace_extract_vague` | — | — | — | format, structure, structure |
| `multi_file_rename` | — | — | — | format, format, format |
| `test_add_execute` | 3 | 3 | 1 | format, structure, pass |
| `move_function_imports` | 2 | 1 | 1 | format, pass, pass |
| `extract_shared_parser` | 3 | 3 | 3 | format, format, format |
| `split_pipeline` | 2 | 2 | 1 | format, format, pass |
| `implement_clamp` | 1 | 1 | 1 | pass, pass, pass |
| `explain_clamp` | 2 | 1 | 2 | transport, pass, transport |
| `review_login` | 2 | 2 | 2 | transport, transport, transport |
| `rename_exception_across_files` | 2 | 3 | 3 | format, format, format |
| `rename_dataclass_field` | — | — | — | format, format, format |
| `widen_return_keep_facade` | — | — | — | format, format, format |
| `rename_kwarg_across_files` | — | 1 | — | format, pass, format |
| `rename_payload_key_across_files` | 2 | — | — | format, format, format |
| `rename_env_var_across_files` | 1 | 3 | 3 | pass, format, format |

## Prompt contract

`whitespace_extract` and `whitespace_extract_vague` share one oracle.
The precise task passed on attempt 1 in all three sessions, including
structure. The vague task never passed. When a vague reply did parse,
structure failed (session 1 attempts 2 and 3; session 2 attempts 1 and 3;
session 3 all three attempts). Format failures still appear on the vague
task, so the gap is not structure-only.

## Limits

Three sessions on one corpus commit. Format misses dominate attempt 1, so
pass@end is carried by repair and escalation. Empty thinking replies count
as transport failures. A6's single fast shot failed behavior and is not
folded into the harness pass@1. These rates do not support a general
quality, speed, or multi-language claim.
