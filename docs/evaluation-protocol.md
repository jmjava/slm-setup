# Evaluation protocol

This is the measurement contract for Phase 3. It exists so a workshop
paper can report **where** a local SLM failed, not only whether a
single live run looked successful.

Live GPU numbers still belong in dated notes such as
[local-acceptance-results-2026-09-06.md](local-acceptance-results-2026-09-06.md).
This document is the method. The committed artifact is the executable
corpus in `src/local_coding_slm/eval/`, not a dump of model transcripts.

## Why a single pass/fail is not enough

The 2026-09-06 baseline already mixed three different events:

1. The stdio MCP bridge reached Ollama (transport).
2. The model returned something that looked like a test file (shape).
3. A refactor preserved behavior after the **task text** was tightened
   from "private helper" to "module-level (top-level) private helper."

The nested-helper reply preserved behavior. Treating that as a model
failure would have been wrong. Treating a later retry as pass-at-one
would also have been wrong. Prompt precision is part of the test
contract.

A6 in `scripts/prove_acceptance.py` still only checks that the response
contains `def test`. That is a format/shape check. Executing generated
tests is a different layer.

## Layers

Every candidate string is scored in this order. Later layers are
`skip` when an earlier required layer failed. `passed` is true only
when all four executable layers pass.

| Layer | Pass means | Typical failure |
| --- | --- | --- |
| **transport** | The payload is not `ERROR: …` | Ollama down, timeout, empty message |
| **format** | Markdown fenced files (or a unified diff) parse | Prose, missing fence, missing required path |
| **structure** | AST matches the case contract | Nested helper when the case requires module-level; missing `plus` after a rename |
| **behavior** | Extracted modules execute and match oracles | Helper extracted but whitespace rule changed; tests compile but assert the wrong value |

Unified diffs count as format-only. This repo does not apply patches, so
structure and behavior stay `skip`. That is **not** a pass. Executable
cases must return fenced files.

The same scorer runs against:

- committed fixtures (cloud / CI, no GPU)
- live `local_*` MCP output (workstation Ollama)

## Corpus

| Case id | Tool | What it isolates |
| --- | --- | --- |
| `whitespace_extract` | `local_refactor` | Single-file extract; module-level helper; three behavior oracles (the 2026-09-06 seed) |
| `whitespace_extract_vague` | `local_refactor` | **Same checker**, vaguer prompt. Measures prompt-contract, not a looser oracle |
| `multi_file_rename` | `local_refactor` | Two files must be returned; `add` → `plus`; `total([1,2,3]) == 6` |
| `test_add_execute` | `local_generate_tests` | Generated tests are imported with `add.py` and the `test_*` functions are called |
| `move_function_imports` | `local_refactor` | Move `clamp` into `bounds.py` and update `report.py` imports |
| `extract_shared_parser` | `local_refactor` | Extract `parse_fields` into `csv_parse.py`; both callers import it |
| `split_pipeline` | `local_refactor` | Split `run` into `load.py` / `transform.py` / `pipeline.py` |
| `rename_exception_across_files` | `local_refactor` | Rename `QuotaError` → `LimitError` across raise and catch; no alias |
| `rename_dataclass_field` | `local_refactor` | Rename `Person.years` → `age` in producer and consumer; no property alias |
| `widen_return_keep_facade` | `local_refactor` | `apply_discount` returns `(discounted, saved)`; `line_total` / `savings` stay ints |
| `implement_clamp` | `local_code` | Implement `clamp` from a spec, no starter file |
| `explain_clamp` | `local_explain` | Prose: names the function and bounds; mentions clipping |
| `review_login` | `local_review` | Prose first-pass: flags None and missing auth. **Not** an apply |

Known-fail fixtures are part of the corpus. They prove the scorer can
tell layers apart:

- nested helper → structure fail, behavior skipped
- wrong `assert` that still contains `def test_` → structure pass, behavior fail
- no fence → format fail
- one of two files → format fail (missing required path)
- `ERROR:` payload → transport fail
- unified diff only → format pass, structure skipped
- leftover `QuotaError` alias or `years` property → structure fail
- exception threshold or greeting format drift → behavior fail
- `apply_discount` still returns an int → structure fail; wrong `DISCOUNT_PERCENT` → behavior fail

## Measurement harness

Fixtures prove the scorer. They do not time a tool call or apply the
retry policy. `scripts/run_harness.py` does that:

1. Call the real stdio MCP server (`local_refactor` / `local_generate_tests`).
2. Score the response on the four layers.
3. Retry or escalate the way a premium agent should: fast first, one
   same-model repair (format or structure reminder), then strong.
4. Write one JSONL row per attempt: `mcp_ms`, `score_ms`, `passed`,
   `first_failure`, `pass_at`, model. No raw transcripts unless you keep
   a local copy yourself.

Two backends, one schema:

| Backend | When | What the clock measures |
| --- | --- | --- |
| `--backend stub` | Cloud / CI, no GPU | Real MCP + HTTP + scoring. Generation time is a loopback stub with scripted replies and `--fast-ms` / `--strong-ms` delays. |
| `--backend live` | Workstation with Ollama | The same loop against the configured private runtime. Those `mcp_ms` values are the paper's model timings. |

Stub profiles (deterministic **workers**, not model-quality claims):

- `golden` — first attempt returns the passing fixture. Use this to time the bridge.
- `observed` — replays the failure layers we already documented (missing fence, nested helper, partial multi-file, wrong test assert), then recovers via repair/escalation. Use this to time the policy.

```bash
# Cloud-safe: simulated generation, real MCP measurements
.venv/bin/python scripts/run_harness.py --backend stub --profile golden
.venv/bin/python scripts/run_harness.py --backend stub --profile observed --out eval-runs/observed
.venv/bin/python scripts/run_harness.py --backend stub --profile golden --repeat 5 --out eval-runs/load

# Workstation: real Ollama
.venv/bin/python scripts/run_harness.py --backend live --out eval-runs/live-fast
```

`eval-runs/` is gitignored. Summaries may be copied into dated notes;
omit hostnames and raw completions.

Report `pass@1` separately from `pass@end`. Escalation rate is the
fraction of cases that called `strong`. Stub `mcp_ms` is not GPU
latency. Live `mcp_ms` is.

That harness is **local failover after a task was already delegated**.
It does not prove that the premium model chose to delegate, nor that it
accepted the patch.

## Premium routing and review

Spec §8 is an instruction to the premium agent, not a classifier
service. The executable contract is in `src/local_coding_slm/eval/routing.py`
and `orchestrate.py`:

1. **Route** from explicit signals (shape obvious, context fits, cheap
   to reject; plus do-not-delegate flags). Mechanical → `local_*`.
   Incident, architecture, live-tool, or vague work → keep on premium.
   Local is never called on a keep job.
2. **Local failover** uses the same `next_plan` policy as the harness
   (fast, one format/structure repair, then strong).
3. **Apply gate** requires a premium verdict (`accept` / `rewrite` /
   `reject`). A local layer-pass is not approval. `local_review` is a
   cheap SLM tool and cannot approve. Reject drops the patch. Rewrite
   applies the premium text, not the raw local output, **and is scored
   on the same four layers** before apply. Accept applies local text
   only when the four layers already passed. `.env` / credential files
   are never delegated. The reviewer sees a `ReviewPacket` (text, layer
   statuses, optional `local_review` notes), not only the raw MCP string.

CI uses a scripted reviewer. These tests do **not** call Cursor, GPT, or
Claude, and they do not prove that a live IDE agent followed the rule
file. They prove the state machine the agent is supposed to follow.

The same gate runs after **real stdio MCP** calls when you pass
`--orchestrate`. Stub Ollama still supplies the worker text. Keep jobs
never call `local_*`. Accept / rewrite / reject then run on the scored
candidate. Security-sensitive delegated jobs first call `local_review`
and attach those notes to the premium packet; that still cannot approve.

The MCP server also refuses secret filenames, private-key / token
blobs, oversized file sets, and `max_tokens` above 8192 **before**
calling Ollama. That is defense in depth if a client skips the eval
router. A function that only mentions `password` is not treated as a
secret blob.

```bash
PYTHONPATH=src .venv/bin/python -m unittest tests.test_eval_orchestrate tests.test_eval_mcp_orchestrate -v
.venv/bin/python scripts/run_orchestration.py
.venv/bin/python scripts/run_harness.py --backend stub --profile golden --orchestrate
```

## Commands

Fixture protocol (no GPU; this is what Cloud Agents can run):

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/run_eval.py
.venv/bin/python scripts/run_eval.py --suite harder
.venv/bin/python scripts/prove_multifile_refactor.py
.venv/bin/python scripts/run_orchestration.py
.venv/bin/python scripts/run_harness.py --backend stub --profile golden --orchestrate --fast-ms 1 --strong-ms 1
```

GitHub Actions (`.github/workflows/tests.yml`) runs the same no-GPU path on every push.

Live protocol (workstation with Ollama). If the server is down, `--live`
prints `SKIP live` and exits 0. That skip is not a model-quality pass:

```bash
.venv/bin/python scripts/run_eval.py --live --model fast
.venv/bin/python scripts/run_eval.py --live --suite harder --model fast
.venv/bin/python scripts/prove_multifile_refactor.py --live --model fast
.venv/bin/python scripts/run_eval.py --live --model strong
```

Record live rows in `docs/phase3-log.md` with result
`accepted` / `accepted with trim` / `rewritten` / `escalated` and the
**first failing layer**. Do not fold retries into pass-at-one.

`scripts/prove_refactor_acceptance.py` remains the original single-case
live script. It now uses the shared fence extractor. Prefer
`scripts/run_eval.py --live --case whitespace_extract` for that seed.
The harder multi-file suite is
`scripts/prove_multifile_refactor.py` (fixtures by default).

## What this may claim later

After repeated live runs, a paper may claim:

- Layer-conditional rates on this corpus (format vs structure vs behavior).
- That a vaguer prompt raises structure failures on the same oracle
  (`whitespace_extract` vs `whitespace_extract_vague`).
- That leftover type/field aliases, catch-site drift, and a helper
  signature change that breaks a public facade are distinguishable
  layers on the harder multi-file suite.
- That shape-only test generation overstates success relative to
  executed tests (`test_add_execute`; A6 now uses this checker).
- That keep-vs-delegate and accept/rewrite/reject are enforceable as a
  state machine on stub workers plus real stdio MCP.
- That a premium rewrite which fails the same oracles is not applied.

It still may not claim:

- General model quality, Halo speedups, or multi-language competence.
- That cloud agents exercised the private GPU.
- A success rate from one accepted retry.
- That a live Cursor / Copilot / Claude session actually routed or
  reviewed a patch. The orchestrator tests use scripted premium verdicts.

## Paper mapping

This protocol is the methods object for a short workshop paper on
**local SLMs as MCP tools**, not as a replacement model provider.
Related MCP-agent benchmarks score tool choice or final answers on
hosted servers. The question here is narrower: when a premium agent
delegates a bounded coding edit to a private 9B–24B model, which
failure layer fires, and how much of that layer is the prompt contract?
