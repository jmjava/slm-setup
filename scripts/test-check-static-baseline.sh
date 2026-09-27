#!/usr/bin/env bash
# Proving test: a recorded finding passes; a new one fails; deleting the
# record while the finding remains fails. The checker does not rewrite the file.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHECK="${SCRIPT_DIR}/check-static-baseline.py"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$TMP/pkg"
cat > "$TMP/ruff.toml" <<'EOF'
target-version = "py310"

[lint]
select = ["F"]
EOF
cat > "$TMP/pkg/mod.py" <<'PY'
import os

value = 1
PY
BASELINE="$TMP/baseline.txt"
printf 'pkg/mod.py\tF401\n' > "$BASELINE"
STAMP="$(cksum "$BASELINE")"

if ! python3 "$CHECK" --root "$TMP" --config "$TMP/ruff.toml" --baseline "$BASELINE" pkg; then
  echo "expected PASS when the only finding is recorded" >&2
  exit 1
fi
if [[ "$(cksum "$BASELINE")" != "$STAMP" ]]; then
  echo "checker rewrote the baseline" >&2
  exit 1
fi

cat > "$TMP/pkg/mod.py" <<'PY'
import os
import sys

value = 1
PY
if python3 "$CHECK" --root "$TMP" --config "$TMP/ruff.toml" --baseline "$BASELINE" pkg; then
  echo "expected FAIL on a new finding" >&2
  exit 1
fi

printf '' > "$BASELINE"
cat > "$TMP/pkg/mod.py" <<'PY'
import os

value = 1
PY
if python3 "$CHECK" --root "$TMP" --config "$TMP/ruff.toml" --baseline "$BASELINE" pkg; then
  echo "expected FAIL when the record is deleted and the finding remains" >&2
  exit 1
fi

printf 'pkg/mod.py\tF401\n' > "$BASELINE"
cat > "$TMP/pkg/mod.py" <<'PY'
value = 1
PY
if ! python3 "$CHECK" --root "$TMP" --config "$TMP/ruff.toml" --baseline "$BASELINE" pkg; then
  echo "expected PASS when the finding is gone and the record is stale" >&2
  exit 1
fi

if python3 "$CHECK" --write-baseline >/dev/null 2>&1; then
  echo "expected refusal to rewrite the baseline" >&2
  exit 1
fi

echo "test-check-static-baseline: PASS"
