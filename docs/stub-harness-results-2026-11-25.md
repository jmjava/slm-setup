# Stub harness results — 2026-11-25

No GPU. Cloud / CI path only. Confirms the fixture corpus and apply gate while
Halo stays on Windows pureplay.

## Commands

```bash
PYTHONPATH=src .venv/bin/python scripts/run_harness.py \
  --backend stub --profile golden --fast-ms 1 --strong-ms 1
PYTHONPATH=src .venv/bin/python scripts/run_harness.py \
  --backend stub --profile observed --fast-ms 1 --strong-ms 1
PYTHONPATH=src .venv/bin/python scripts/run_harness.py \
  --backend stub --profile golden --orchestrate --fast-ms 1 --strong-ms 1
PYTHONPATH=src .venv/bin/python -m unittest tests.test_eval_harness tests.test_harness_exit -v
```

## Headline

| Run | Result |
| --- | --- |
| golden (16 cases) | `pass@1=1.00` `pass@end=1.00` escalated=0 |
| observed (16 cases) | `pass@1=0.00` `pass@end=1.00` escalated≈0.19; first_failure layers format/structure/behavior |
| golden + `--orchestrate` (14 jobs) | `pass@end=1.00`; 10 delegated; scripted reject/rewrite paths exercised |
| unittest harness subset | 12 tests OK |

Raw `eval-runs/` stays gitignored. This note is the committed summary.
