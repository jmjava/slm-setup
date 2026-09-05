#!/usr/bin/env python3
"""Run defensive safety checks on this slm-setup deployment.

Inspects config, git hygiene, and this host's listen table. Does not scan
other machines or inspect weight files for backdoors.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from local_coding_slm.envfile import merge_dotenv  # noqa: E402
from local_coding_slm.safety import run_checks, worst_status  # noqa: E402


def _load_dotenv() -> None:
    path = ROOT / ".env"
    if path.is_file():
        merge_dotenv(path.read_text(encoding="utf-8").splitlines(), __import__("os").environ)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-listen",
        action="store_true",
        help="Skip the local Ollama bind check (CI without a listener)",
    )
    args = parser.parse_args()
    _load_dotenv()
    results = run_checks(root=ROOT, skip_listen=args.skip_listen)
    for item in results:
        print(f"{item.status.upper():4} {item.name}: {item.message}")
    status = worst_status(results)
    if status == "fail":
        print("FAIL deployment safety")
        raise SystemExit(1)
    print("PASS deployment safety" if status == "pass" else "PASS deployment safety (warnings)")
    raise SystemExit(0)


if __name__ == "__main__":
    main()
