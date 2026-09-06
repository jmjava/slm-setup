# Local acceptance results — 2026-09-06

This is a dated baseline for the current same-machine profile. It separates
deterministic unit tests from calls that used the real Ollama runtime through
the stdio MCP server.

It is **not** evidence about Halo hardware, multi-file refactoring, or general
model quality.

## Environment

- Ollama 0.33.3 on loopback only
- Fast model: `qwen3.5:9b`
- Strong model: `devstral-small-2`
- Context: 16K tokens
- No public listener, tunnel, hostname, or LAN address

The strong model reported split placement after the live refactor check:
46% CPU and 54% GPU. Hardware identifiers are intentionally omitted.

## Deterministic unit suite

Command:

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
```

Result: **36 tests passed**.

These tests mock Ollama HTTP calls. They cover environment parsing, client
request/response behavior, model selection, error conversion, and deployment
safety. They do not prove that Ollama is running or that a model can generate
usable code.

## Live MCP discovery and generation

Command:

```bash
PYTHONPATH=src .venv/bin/python scripts/prove_acceptance.py
```

Observed result:

- The stdio MCP session listed all six `local_*` tools.
- `local_status` reached real Ollama and found both configured models.
- `local_generate_tests` returned a fenced pytest file for a synthetic
  `add()` function.
- A5/A6 passed in 50.6 seconds wall-clock.

The A6 checker validates the response shape; it does not execute the generated
pytest file. The semantic refactor check below provides stronger evidence.

## Live semantic refactor

Commands:

```bash
PYTHONPATH=src .venv/bin/python scripts/prove_refactor_acceptance.py --model fast
PYTHONPATH=src .venv/bin/python scripts/prove_refactor_acceptance.py --model strong
```

The script sends a synthetic Python module containing repeated whitespace
normalization to the real `local_refactor` MCP tool. It requires extraction to
a module-level helper, parses the returned module, executes it, and checks
three behavior-preservation cases.

Final accepted runs:

- Fast model: **pass**, 6.7 seconds wall-clock.
- Strong model: **pass**, 25.6 seconds wall-clock.

These are single observed runs, not averages or latency percentiles.

## Protocol-development observations

The first task said only "private helper." The strong model returned a nested
helper that preserved behavior, while the checker expected a module-level
helper. That was a test-specification ambiguity, not evidence of a semantic
model failure. The task and assertion were aligned by requiring a
"module-level (top-level) private helper."

Under the clarified requirement:

- The fast model missed the requested fenced-file format once, then passed on
  the next run.
- The strong model passed its first clarified run.

Reporting these attempts avoids presenting a successful retry as pass-at-one.

## Deployment safety

Command:

```bash
PYTHONPATH=src .venv/bin/python scripts/check_deployment_safety.py
```

Result: **pass**. The configured URL was loopback, the configured model tags
matched the documented official-library tags, the environment file was
gitignored, committed text contained no non-placeholder private addresses, and
the configured Ollama port listened on loopback rather than a wildcard.

## What this supports

The evidence supports these narrow claims:

- The current stdio MCP bridge can reach a real local Ollama runtime.
- Both configured models can complete one bounded, single-file refactor while
  preserving the tested behavior.
- Prompt precision and output-format adherence need to be part of acceptance.

It does not yet support these broader claims:

- Larger models on Halo improve `local_refactor` quality.
- Either model is reliable on broad or multi-file refactors.
- The observed timings predict another machine or backend.
- A single successful semantic case establishes a general success rate.

The next useful step is a committed corpus of representative localized and
multi-file refactors, run repeatedly through the same semantic checks on the
current host and later on Halo.
