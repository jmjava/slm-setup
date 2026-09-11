"""Prove .local-ollama/ is gitignored so models and serve logs stay unstaged."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCAL_OLLAMA = ".local-ollama/"


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )


class LocalOllamaGitignoreTests(unittest.TestCase):
    def test_check_ignore_local_ollama_succeeds(self) -> None:
        ignore_lines = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn(LOCAL_OLLAMA, ignore_lines)
        proc = _git(["check-ignore", LOCAL_OLLAMA], ROOT)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_git_add_all_does_not_stage_local_ollama(self) -> None:
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        init = _git(["init", "-q"], tmp)
        self.assertEqual(init.returncode, 0, init.stderr)
        (tmp / ".gitignore").write_text(
            (ROOT / ".gitignore").read_text(encoding="utf-8"), encoding="utf-8"
        )
        store = tmp / ".local-ollama"
        (store / "models").mkdir(parents=True)
        (store / "serve.log").write_text("log\n", encoding="utf-8")
        (store / "serve.pid").write_text("1\n", encoding="utf-8")
        (store / "models" / "blob").write_text("weights\n", encoding="utf-8")

        check = _git(["check-ignore", LOCAL_OLLAMA], tmp)
        self.assertEqual(check.returncode, 0, check.stderr)

        added = _git(["add", "-A"], tmp)
        self.assertEqual(added.returncode, 0, added.stderr)
        staged = _git(["diff", "--cached", "--name-only"], tmp)
        self.assertEqual(staged.returncode, 0, staged.stderr)
        leaked = [
            path
            for path in staged.stdout.splitlines()
            if path == ".local-ollama" or path.startswith(".local-ollama/")
        ]
        self.assertEqual(leaked, [], staged.stdout)


if __name__ == "__main__":
    unittest.main()
