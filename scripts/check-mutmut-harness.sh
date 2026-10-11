#!/usr/bin/env bash
# mutmut on src/local_coding_slm/eval/harness.py only.
# mutmut 3 exits 0 when mutants survive. Fail unless every mutant was killed.
# Do not write a survived ceiling.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
rm -rf mutants
run_log="$(mktemp)"
trap 'rm -f "$run_log"' EXIT
mutmut run --max-children 2 | tee "$run_log"
if ! grep -E '\([1-9][0-9]* files mutated' "$run_log" >/dev/null; then
  echo "mutmut: harness.py was not mutated" >&2
  exit 1
fi
mutmut export-cicd-stats
if ! python3 scripts/check-mutmut-harness.py; then
  mutmut results || true
  exit 1
fi
