#!/usr/bin/env bash
# Proving test: a quiet complex file passes; a hot simple file passes;
# a hot complex file fails.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHECK="${SCRIPT_DIR}/check-hotspot.py"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
git -C "$TMP" init -q
git -C "$TMP" config user.email "sa@example.test"
git -C "$TMP" config user.name "SA"

messy() {
  cat <<'PY'
def messy(x):
    if x == 1: return 1
    if x == 2: return 2
    if x == 3: return 3
    if x == 4: return 4
    if x == 5: return 5
    if x == 6: return 6
    if x == 7: return 7
    if x == 8: return 8
    if x == 9: return 9
    if x == 10: return 10
    if x == 11: return 11
    return 0
PY
}

messy > "$TMP/hot_complex.py"
messy > "$TMP/quiet_complex.py"
printf 'def ok(x):\n    return x + 1\n' > "$TMP/hot_simple.py"
for i in 1 2 3 4 5 6 7; do
  printf 'def quiet_%s(x):\n    return x\n' "$i" > "$TMP/quiet_${i}.py"
done
git -C "$TMP" add .
git -C "$TMP" commit -qm base
# Six touches puts both hot files in the top 10% (ties included).
for n in 1 2 3 4 5; do
  printf '\n# touch %s\n' "$n" >> "$TMP/hot_complex.py"
  printf '\n# touch %s\n' "$n" >> "$TMP/hot_simple.py"
  git -C "$TMP" add hot_complex.py hot_simple.py
  git -C "$TMP" commit -qm "touch $n"
done

python3 - "$CHECK" "$TMP" <<'PY'
import importlib.util
import sys

check, repo = sys.argv[1], sys.argv[2]
spec = importlib.util.spec_from_file_location("check_hotspot", check)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
top = mod.top_frequency(mod.touch_counts(__import__("pathlib").Path(repo)))
missing = {"hot_complex.py", "hot_simple.py"} - top
quiet = [name for name in top if name.startswith("quiet_")]
if missing or quiet:
    print(f"top set={sorted(top)} missing={sorted(missing)} quiet={quiet}", file=sys.stderr)
    sys.exit(1)
PY

printf '\n# quiet edit\n' >> "$TMP/quiet_complex.py"
git -C "$TMP" add quiet_complex.py
git -C "$TMP" commit -qm quiet
if ! python3 "$CHECK" --repo "$TMP" --base HEAD~1 --paths .; then
  echo "expected PASS on a quiet complex file" >&2
  exit 1
fi

printf '\n# simple edit\n' >> "$TMP/hot_simple.py"
git -C "$TMP" add hot_simple.py
git -C "$TMP" commit -qm simple
if ! python3 "$CHECK" --repo "$TMP" --base HEAD~1 --paths .; then
  echo "expected PASS on a hot file that is not complex" >&2
  exit 1
fi

printf '\n# complex edit\n' >> "$TMP/hot_complex.py"
git -C "$TMP" add hot_complex.py
git -C "$TMP" commit -qm complex
if python3 "$CHECK" --repo "$TMP" --base HEAD~1 --paths .; then
  echo "expected FAIL when a changed file is both complex and hot" >&2
  exit 1
fi
echo "test-check-hotspot: PASS"
