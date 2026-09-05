"""Merge .env lines into an environment mapping. Empty values count as unset."""

from __future__ import annotations

from collections.abc import Iterable, MutableMapping


def merge_dotenv(lines: Iterable[str], environ: MutableMapping[str, str]) -> None:
    """Apply KEY=value lines. Comments and blanks are ignored.

    A missing key or an empty string is treated as unset so Cursor
    ``${env:NAME}`` interpolation cannot block a real value from ``.env``.
    Already-set non-empty values win.
    """
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if not key:
            continue
        current = environ.get(key)
        if current is None or current == "":
            environ[key] = value
