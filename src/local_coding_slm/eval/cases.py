"""Committed evaluation corpus. Cases are executable Python, not model dumps.

Live MCP output stays in dated notes. The artifact here is the protocol:
the same scorer runs against fixtures (CI / cloud) and live Ollama (workstation).
"""

from __future__ import annotations

import ast
from dataclasses import dataclass

from local_coding_slm.eval.score import BehaviorCheck, EvalCase

WHITESPACE_SOURCE = """\
def normalize_user(name: str, email: str) -> tuple[str, str]:
    cleaned_name = " ".join(name.strip().split())
    cleaned_email = " ".join(email.strip().split()).lower()
    return cleaned_name, cleaned_email
"""

WHITESPACE_TASK = (
    "Extract the repeated whitespace normalization into a "
    "module-level (top-level) private helper named "
    "_normalize_whitespace. Preserve the exact behavior "
    "and public function signature. Return one complete "
    "fenced Python file and no prose."
)

WHITESPACE_TASK_VAGUE = (
    "Extract the repeated whitespace normalization into a private helper "
    "named _normalize_whitespace. Preserve behavior."
)

WHITESPACE_GOLDEN = '''\
```python
# user_text.py
def _normalize_whitespace(value: str) -> str:
    return " ".join(value.strip().split())


def normalize_user(name: str, email: str) -> tuple[str, str]:
    cleaned_name = _normalize_whitespace(name)
    cleaned_email = _normalize_whitespace(email).lower()
    return cleaned_name, cleaned_email
```
'''

WHITESPACE_NESTED = '''\
```python
# user_text.py
def normalize_user(name: str, email: str) -> tuple[str, str]:
    def _normalize_whitespace(value: str) -> str:
        return " ".join(value.strip().split())

    cleaned_name = _normalize_whitespace(name)
    cleaned_email = _normalize_whitespace(email).lower()
    return cleaned_name, cleaned_email
```
'''

WHITESPACE_BEHAVIOR_BREAK = '''\
```python
# user_text.py
def _normalize_whitespace(value: str) -> str:
    return value.strip()


def normalize_user(name: str, email: str) -> tuple[str, str]:
    return _normalize_whitespace(name), _normalize_whitespace(email).lower()
```
'''

WHITESPACE_NO_FENCE = (
    "def _normalize_whitespace(value: str) -> str:\n"
    '    return " ".join(value.strip().split())\n'
)

WHITESPACE_CHECKS = (
    BehaviorCheck(
        "user_text",
        "normalize_user",
        ("  Ada   Lovelace ", " ADA@EXAMPLE.COM "),
        ("Ada Lovelace", "ada@example.com"),
    ),
    BehaviorCheck(
        "user_text",
        "normalize_user",
        ("\tGrace\nHopper", " G@EXAMPLE.COM "),
        ("Grace Hopper", "g@example.com"),
    ),
    BehaviorCheck("user_text", "normalize_user", ("", ""), ("", "")),
)

CALC_SOURCE = """\
def add(a: int, b: int) -> int:
    return a + b
"""

USE_SOURCE = """\
from calc import add


def total(xs: list[int]) -> int:
    s = 0
    for x in xs:
        s = add(s, x)
    return s
"""

MULTI_FILE_TASK = (
    "Rename add to plus in both files. Update the import and every call. "
    "Do not keep add as a wrapper. Preserve total() behavior. "
    "Return two fenced Python files with path comments calc.py and use.py, no prose."
)

MULTI_FILE_GOLDEN = '''\
```python
# calc.py
def plus(a: int, b: int) -> int:
    return a + b
```

```python
# use.py
from calc import plus


def total(xs: list[int]) -> int:
    s = 0
    for x in xs:
        s = plus(s, x)
    return s
```
'''

MULTI_FILE_PARTIAL = '''\
```python
# calc.py
def plus(a: int, b: int) -> int:
    return a + b
```
'''

ADD_SOURCE = "def add(a: int, b: int) -> int:\n    return a + b\n"

TEST_ADD_TASK = (
    "Write pytest unit tests for add(). Cover two positives and one negative. "
    "Return a single fenced file named test_add.py. Include every import. "
    "Do not change add.py."
)

TEST_ADD_GOLDEN = '''\
```python
# test_add.py
from add import add


def test_add_two_positives() -> None:
    assert add(2, 3) == 5


def test_add_another_positive() -> None:
    assert add(10, 1) == 11


def test_add_negative() -> None:
    assert add(-2, 5) == 3
```
'''

TEST_ADD_SHAPE_ONLY = '''\
```python
# test_add.py
from add import add

def test_add():
    assert add(1, 1) == 3
```
'''


def _top_level_names(tree: ast.AST) -> set[str]:
    return (
        {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
        if isinstance(tree, ast.Module)
        else set()
    )


def _calc_must_drop_add(by_path: dict[str, str]) -> str | None:
    content = by_path.get("calc.py")
    if content is None:
        return "calc.py missing from candidate"
    tree = ast.parse(content)
    names = _top_level_names(tree)
    if "add" in names:
        return "calc.py still defines add; expected a rename to plus, not an alias"
    if "plus" not in names:
        return "calc.py is missing plus"
    return None


def _has_test_functions(by_path: dict[str, str]) -> str | None:
    names: set[str] = set()
    for path, content in by_path.items():
        if "test" not in path:
            continue
        try:
            tree = ast.parse(content)
        except SyntaxError as exc:
            return f"{path} is not parseable: {exc.msg}"
        names.update(_top_level_names(tree))
    tests = sorted(name for name in names if name.startswith("test_"))
    if not tests:
        return "no top-level test_* function in a test file"
    return None


def _run_generated_tests(merged: dict[str, str]) -> None:
    import sys
    import tempfile
    from pathlib import Path
    from types import ModuleType

    from local_coding_slm.eval.score import _load_module

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for rel, content in merged.items():
            dest = root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
        loaded: dict[str, ModuleType] = {}
        try:
            ran = 0
            for rel in merged:
                if "test" not in Path(rel).name or not rel.endswith(".py"):
                    continue
                module_name = Path(rel).stem
                module = _load_module(root, module_name, loaded)
                for name in dir(module):
                    if not name.startswith("test_"):
                        continue
                    fn = getattr(module, name)
                    if not callable(fn):
                        continue
                    try:
                        fn()
                    except AssertionError as exc:
                        raise AssertionError(f"{module_name}.{name} failed") from exc
                    ran += 1
            if ran == 0:
                raise AssertionError("no test_* functions executed")
        finally:
            for name, mod in list(sys.modules.items()):
                file = getattr(mod, "__file__", None)
                if file and Path(file).is_relative_to(root):
                    sys.modules.pop(name, None)
            sys.path = [p for p in sys.path if p != str(root)]


WHITESPACE_FILES = ({"path": "user_text.py", "content": WHITESPACE_SOURCE},)

CASES: tuple[EvalCase, ...] = (
    EvalCase(
        id="whitespace_extract",
        tool="local_refactor",
        task=WHITESPACE_TASK,
        files=WHITESPACE_FILES,
        style="Keep the code minimal and preserve type hints.",
        required_top_level=("_normalize_whitespace", "normalize_user"),
        behavior=WHITESPACE_CHECKS,
    ),
    EvalCase(
        id="whitespace_extract_vague",
        tool="local_refactor",
        task=WHITESPACE_TASK_VAGUE,
        files=WHITESPACE_FILES,
        style="Keep the code minimal and preserve type hints.",
        required_top_level=("_normalize_whitespace", "normalize_user"),
        behavior=WHITESPACE_CHECKS,
    ),
    EvalCase(
        id="multi_file_rename",
        tool="local_refactor",
        task=MULTI_FILE_TASK,
        files=(
            {"path": "calc.py", "content": CALC_SOURCE},
            {"path": "use.py", "content": USE_SOURCE},
        ),
        required_paths=("calc.py", "use.py"),
        required_top_level=("plus", "total"),
        extra_structure=_calc_must_drop_add,
        behavior=(
            BehaviorCheck("use", "total", ([1, 2, 3],), 6),
            BehaviorCheck("use", "total", ([],), 0),
        ),
    ),
    EvalCase(
        id="test_add_execute",
        tool="local_generate_tests",
        task=TEST_ADD_TASK,
        files=({"path": "add.py", "content": ADD_SOURCE},),
        style="pytest",
        extra_structure=_has_test_functions,
        behavior_fn=_run_generated_tests,
    ),
)

CASES_BY_ID = {case.id: case for case in CASES}

GOLDEN_FOR_CASE = {
    "whitespace_extract": WHITESPACE_GOLDEN,
    "whitespace_extract_vague": WHITESPACE_GOLDEN,
    "multi_file_rename": MULTI_FILE_GOLDEN,
    "test_add_execute": TEST_ADD_GOLDEN,
}


@dataclass(frozen=True)
class Fixture:
    name: str
    case_id: str
    text: str
    expect_pass: bool
    expect_first: str | None = None


FIXTURES: tuple[Fixture, ...] = (
    Fixture("whitespace_golden", "whitespace_extract", WHITESPACE_GOLDEN, True),
    Fixture(
        "whitespace_nested_helper",
        "whitespace_extract",
        WHITESPACE_NESTED,
        False,
        "structure",
    ),
    Fixture(
        "whitespace_behavior_break",
        "whitespace_extract",
        WHITESPACE_BEHAVIOR_BREAK,
        False,
        "behavior",
    ),
    Fixture(
        "whitespace_no_fence",
        "whitespace_extract",
        WHITESPACE_NO_FENCE,
        False,
        "format",
    ),
    Fixture(
        "whitespace_transport_error",
        "whitespace_extract",
        "ERROR: Ollama unreachable: connection refused",
        False,
        "transport",
    ),
    Fixture(
        "whitespace_diff_only",
        "whitespace_extract",
        (
            "--- a/user_text.py\n"
            "+++ b/user_text.py\n"
            "@@ -1,4 +1,8 @@\n"
            "+def _normalize_whitespace(value: str) -> str:\n"
            '+    return " ".join(value.strip().split())\n'
        ),
        False,
        "structure",
    ),
    Fixture("multi_file_golden", "multi_file_rename", MULTI_FILE_GOLDEN, True),
    Fixture(
        "multi_file_partial",
        "multi_file_rename",
        MULTI_FILE_PARTIAL,
        False,
        "format",
    ),
    Fixture("test_add_golden", "test_add_execute", TEST_ADD_GOLDEN, True),
    Fixture(
        "test_add_wrong_assert",
        "test_add_execute",
        TEST_ADD_SHAPE_ONLY,
        False,
        "behavior",
    ),
)
