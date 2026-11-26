# Halo live results — 2026-11-25

Same machine: Cursor and Ollama are both on the Halo.
`host_class=halo-395`, `backend=vulkan`. Loopback
`http://127.0.0.1:11434` only. No SSH forward. No hostname, LAN address,
or account name.

These rows are the first GPU sessions for corpus commit
`1c15fe3393964f3aa5f8251f3d44c5fcfa4e17a5`. They are not a frozen Part A
estimate. An earlier same-day CPU harness is not averaged in (see below).

Harness policy and reporting choices are grounded in the Sources section of
[evaluation-protocol.md](evaluation-protocol.md#sources).

## Models

Official Ollama library tags only. Ollama 0.40.17. `OLLAMA_NUM_CTX=16384`.

| Role | Tag | Digest | Params | Quant | Size |
| --- | --- | --- | --- | --- | --- |
| fast | `qwen3.5:9b` | `56671c2ab9385f9cfcb404638e32cd62d88e3501d44822208363c010179a3c90` | 9.0B | Q4_K_M | 6550825550 bytes |
| strong | `devstral-small-2` (installed as `devstral-small-2:latest`) | `24277f07f62db8f9cb68e9dfc679ea1818a7fbac47a50eff0a701d3f645b63c8` | 24.0B | Q4_K_M | 15177374099 bytes |

## Backend

Vulkan, not ROCm. During the short chats and all three sessions below,
`ollama ps` showed both tags at **100% GPU**, context 16384 (runner sizes
6.2 GB and 17 GB). The runtime log named Vulkan on an 8060S-class GPU and
offloaded every layer (33/33 fast, 41/41 strong).

Earlier the same evening the service was still dropping the integrated GPU
(`ollama ps` **100% CPU**, `vram=0`). One harness session ran then and its
tail hit connection refused when the service restarted into Vulkan. That
session is not in the table: pass@1 3/16, pass@end 8/16, escalated 13/16,
37 attempts, mcp_ms p50 16859 ms. Do not average it with the Vulkan rows.

## Decode rate and time to first token

Direct `/api/chat` with thinking disabled, `num_ctx=16384`, models already
resident. These are not harness wall times. Two-token samples read higher
and are not the headline.

| Model | Eval tokens | tok/s | Prompt tokens | Prompt eval (TTFT, resident) |
| --- | --- | --- | --- | --- |
| `qwen3.5:9b` | 111 | 37.79 | 28 | 0.103 s |
| `devstral-small-2` | 64 | 15.11 | 571 | 0.193 s |

A resident fast "pong" prompt (19 tokens) had prompt eval 0.050 s.
The MCP client does not send `think: false`. On `qwen3.5:9b`, the predict
budget can be spent in the thinking channel and leave `content` empty.
Those replies are 39 characters: `ERROR: Ollama returned an empty message`.
The scorer counts them as transport. That is a client interaction with
this tag, not a loss of GPU placement.

## Memory

With both tags resident at 16384 context on Vulkan, `ollama ps` reported
6.2 GB and 17 GB. The service cgroup peak after the Vulkan restart was
10683367424 bytes and does not include every Vulkan allocation.
The earlier CPU placement cgroup peak, with both tags in system RAM, was
43805028352 bytes.

## Acceptance

A8 and A9 were not run.

| ID | Result | Evidence |
| --- | --- | --- |
| A1 | Pass | `/api/tags` lists `qwen3.5:9b` and `devstral-small-2:latest` |
| A2 | Pass | Fast chat completed; `ollama ps` 100% GPU at context 16384 |
| A3 | Pass | Strong chat completed; `ollama ps` 100% GPU |
| A4 | Pass | Listener is `127.0.0.1:11434` only. Connect to the LAN address on port 11434 failed with connection refused (errno 111). Loopback connect succeeded. The SSH half of A4 does not apply: Cursor is on this Halo |
| A5 | Pass | `local_status` via stdio: `ok=true`, both tags present, host `127.0.0.1` |
| A6 | Fail | One fast `local_generate_tests` shot for `test_add_execute`. Format and structure passed. Behavior failed: `FileNotFoundError` for `test_add.py` in the scorer temp dir. The fence path was `tests/test_add.py`. Not pass@1 |
| A7 | Pass | Cursor called `local_explain` on a two-line `add` function. At `max_tokens` 700 the tool returned a one-sentence explanation. Budgets of 80 and 200 returned an empty message. Reload Cursor so the user-level MCP entry is what a multi-root workspace loads |
| A11 | Pass | Tracked private-address hits are documented placeholders and unit-test literals. Email hits are example domains. Deployment checker `committed_ips` passed |
| A12 | Pass | `scripts/check_deployment_safety.py`: loopback URL, official tags, `.env` ignored, listener on loopback. Printed `PASS deployment safety` |
| A13 | Pass | Vulkan placement above. Both starter tags stayed on GPU at context 16384. Not ROCm |

## Stdio smoke

Before the Vulkan restart (CPU placement), a minimal MCP client called
`local_status` (0.013 s; strong tag not pulled yet), `local_code` on a toy
`add` (16.2 s, fenced function), and `local_refactor` renaming it to
`sum_pair` (9.5 s). Token rates are the table above, not the MCP payload.
After the pull, `local_status` reported both tags present.

## Live harness

```bash
.venv/bin/python scripts/run_harness.py --backend live --out eval-runs/halo-395-gpu-sN
```

Full 16-case corpus, one repeat, fast then one same-model repair then strong.
`pass@1` counts only attempt 1. Raw `eval-runs/` stays gitignored.
Wall clock was about 7.0, 6.7, and 6.3 minutes.

| Session | Cases | Attempts | pass@1 | pass@end | Escalated | mcp_ms p50 | mcp_ms max | First-failure counts |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| gpu-s1 | 16 | 36 | 0.19 (3/16) | 0.69 (11/16) | 0.56 | 9373 | 39790 | format 19, structure 2, behavior 1, transport 3 |
| gpu-s2 | 16 | 36 | 0.31 (5/16) | 0.69 (11/16) | 0.62 | 9713 | 32943 | format 19, structure 5, transport 1 |
| gpu-s3 | 16 | 36 | 0.31 (5/16) | 0.62 (10/16) | 0.69 | 8674 | 24821 | format 20, structure 3, behavior 1, transport 2 |

Pooled across the three sessions: **pass@1 = 13/48 (0.27)**, **pass@end = 32/48 (0.67)**.
Attempt-1 outcomes over 48 case-sessions: pass 13, format 27, transport 5,
structure 3. All-attempt failure counts over 108 attempts: format 58,
structure 10, transport 6, behavior 2. The pool is a sum of three sessions,
not a fourth independent run.

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

## `run_eval.py --live` (one shot, no repair)

```bash
.venv/bin/python scripts/run_eval.py --live --model fast
.venv/bin/python scripts/run_eval.py --live --model strong
```

`eval-runs/live-status.json` is `{"skipped": false}`.

Fast: 6/16 passed, exit 10. First failures: format 6, structure 2,
transport 2 (empty message). Passes: `whitespace_extract`,
`extract_shared_parser`, `split_pipeline`, `implement_clamp`,
`rename_dataclass_field`, `rename_kwarg_across_files`.

Strong: 9/16 passed, exit 7. First failures: format 6, structure 1.
No empty-message transport on this shot. Passes add
`test_add_execute`, `move_function_imports`, `explain_clamp`,
`review_login`, `rename_exception_across_files`,
`rename_env_var_across_files`, and drop `split_pipeline`,
`rename_dataclass_field`, and `rename_kwarg_across_files` relative to
the fast shot. `whitespace_extract` passed both shots.
`whitespace_extract_vague` and `multi_file_rename` failed both.

## Prompt contract

`whitespace_extract` and `whitespace_extract_vague` share one oracle.
The precise task passed on attempt 1 in all three harness sessions,
including structure. The vague task never passed. When a vague reply did
parse, structure failed (session 1 attempts 2 and 3; session 2 attempts 1
and 3; session 3 all three attempts). Format failures still appear on the
vague task, so the gap is not structure-only.

## Limits

Three sessions on one corpus commit. Format misses dominate attempt 1, so
pass@end is carried by repair and escalation. Empty thinking replies count
as transport failures. A6's single fast shot failed behavior and is not
folded into the harness pass@1. These rates do not support a general
quality, speed, or multi-language claim.
