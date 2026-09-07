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

Known-fail fixtures are part of the corpus. They prove the scorer can
tell layers apart:

- nested helper → structure fail, behavior skipped
- wrong `assert` that still contains `def test_` → structure pass, behavior fail
- no fence → format fail
- one of two files → format fail (missing required path)
- `ERROR:` payload → transport fail
- unified diff only → format pass, structure skipped

## Commands

Fixture protocol (no GPU; this is what Cloud Agents can run):

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/run_eval.py
```

Live protocol (workstation with Ollama):

```bash
.venv/bin/python scripts/run_eval.py --live --model fast
.venv/bin/python scripts/run_eval.py --live --model strong
```

Record live rows in `docs/phase3-log.md` with result
`accepted` / `accepted with trim` / `rewritten` / `escalated` and the
**first failing layer**. Do not fold retries into pass-at-one.

`scripts/prove_refactor_acceptance.py` remains the original single-case
live script. It now uses the shared fence extractor. Prefer
`scripts/run_eval.py --live --case whitespace_extract` for new runs.

## What this may claim later

After repeated live runs, a paper may claim:

- Layer-conditional rates on this corpus (format vs structure vs behavior).
- That a vaguer prompt raises structure failures on the same oracle
  (`whitespace_extract` vs `whitespace_extract_vague`).
- That shape-only test generation overstates success relative to
  executed tests (`test_add_execute`).

It still may not claim:

- General model quality, Halo speedups, or multi-language competence.
- That cloud agents exercised the private GPU.
- A success rate from one accepted retry.

## Paper mapping

This protocol is the methods object for a short workshop paper on
**local SLMs as MCP tools**, not as a replacement model provider.
Related MCP-agent benchmarks score tool choice or final answers on
hosted servers. The question here is narrower: when a premium agent
delegates a bounded coding edit to a private 9B–24B model, which
failure layer fires, and how much of that layer is the prompt contract?
