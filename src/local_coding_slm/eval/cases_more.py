"""Third-wave corpus: more extract/rename/split/implement/test/prose cases.

Imported last from cases.py so test helpers exist. Golden strings are
fixtures for the scorer and stub Ollama, not live model dumps.
"""

from __future__ import annotations

import ast

from local_coding_slm.eval.score import BehaviorCheck, EvalCase

# --- extract Person dataclass (precise + vague, same checker) ---

PEOPLE_SOURCE = '''\
from dataclasses import dataclass


@dataclass
class Person:
    name: str
    age: int


def as_person(name: str, age: int) -> Person:
    return Person(name=name, age=age)


def label(person: Person) -> str:
    return f"{person.name}:{person.age}"


def tagged(name: str, age: int) -> str:
    return label(as_person(name, age))
'''

EXTRACT_DATACLASS_TASK = (
    "Extract the Person dataclass and as_person helper from people.py "
    "into a new file person_model.py. people.py should import them so "
    "tagged() still returns name:age. Return fenced files person_model.py "
    "and people.py, no prose."
)

EXTRACT_DATACLASS_TASK_VAGUE = "Move the person type into its own module."

EXTRACT_DATACLASS_GOLDEN = '''\
```python
# person_model.py
from dataclasses import dataclass


@dataclass
class Person:
    name: str
    age: int


def as_person(name: str, age: int) -> Person:
    return Person(name=name, age=age)
```

```python
# people.py
from person_model import Person, as_person


def label(person: Person) -> str:
    return f"{person.name}:{person.age}"


def tagged(name: str, age: int) -> str:
    return label(as_person(name, age))
```
'''

EXTRACT_DATACLASS_NESTED = '''\
```python
# person_model.py
def unused() -> None:
    return None
```

```python
# people.py
from dataclasses import dataclass


def wrap() -> None:
    @dataclass
    class Person:
        name: str
        age: int

    def as_person(name: str, age: int) -> Person:
        return Person(name=name, age=age)

    def label(person: Person) -> str:
        return f"{person.name}:{person.age}"

    def tagged(name: str, age: int) -> str:
        return label(as_person(name, age))
```
'''


def _top_level_names(tree: ast.AST) -> set[str]:
    return (
        {
            node.name
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.ClassDef))
        }
        if isinstance(tree, ast.Module)
        else set()
    )


def _person_must_move(by_path: dict[str, str]) -> str | None:
    try:
        model = ast.parse(by_path.get("person_model.py", ""))
        people = ast.parse(by_path.get("people.py", ""))
    except SyntaxError as exc:
        return f"unparseable Python: {exc.msg}"
    if "Person" not in _top_level_names(model):
        return "person_model.py is missing module-level Person"
    if "as_person" not in _top_level_names(model):
        return "person_model.py is missing as_person"
    if "Person" in _top_level_names(people):
        return "Person is still defined in people.py"
    people_src = by_path.get("people.py", "")
    if "from person_model import" not in people_src:
        return "people.py must import from person_model"
    return None


# --- rename fetch → load across three files ---

HTTP_SOURCE = "def fetch(url: str) -> str:\n    return url.upper()\n"

SERVICE_SOURCE = (
    "from http_client import fetch\n\n"
    "def load_item(url: str) -> str:\n"
    "    return fetch(url)\n"
)

MAIN_SOURCE = (
    "from service import load_item\n\n"
    "def run(url: str) -> str:\n"
    "    return load_item(url)\n"
)

RENAME_THREE_TASK = (
    "Rename fetch to load in http_client.py, service.py, and main.py. "
    "Keep load_item and run working. Do not keep fetch as a wrapper. "
    "Return three fenced Python files with those path comments, no prose."
)

RENAME_THREE_GOLDEN = '''\
```python
# http_client.py
def load(url: str) -> str:
    return url.upper()
```

```python
# service.py
from http_client import load


def load_item(url: str) -> str:
    return load(url)
```

```python
# main.py
from service import load_item


def run(url: str) -> str:
    return load_item(url)
```
'''

RENAME_THREE_PARTIAL = '''\
```python
# http_client.py
def load(url: str) -> str:
    return url.upper()
```
'''


def _fetch_must_drop(by_path: dict[str, str]) -> str | None:
    try:
        http = ast.parse(by_path.get("http_client.py", ""))
    except SyntaxError as exc:
        return f"http_client.py is not parseable: {exc.msg}"
    names = _top_level_names(http)
    if "fetch" in names:
        return "http_client.py still defines fetch; expected a rename to load"
    if "load" not in names:
        return "http_client.py is missing load"
    service = by_path.get("service.py", "")
    if "from http_client import load" not in service:
        return "service.py must import load from http_client"
    if "from http_client import fetch" in service:
        return "service.py still imports fetch"
    return None


# --- split retries/timeout into settings.py ---

WORKER_SOURCE = '''\
def fetch_with_policy(url: str) -> str:
    retries = 3
    timeout = 30
    return f"{url}:{retries}:{timeout}"
'''

SPLIT_SETTINGS_TASK = (
    "Move retries and timeout constants from worker.py into settings.py. "
    "worker.py should import them. fetch_with_policy must still return "
    "url:retries:timeout. Return fenced files settings.py and worker.py."
)

SPLIT_SETTINGS_GOLDEN = '''\
```python
# settings.py
retries = 3
timeout = 30
```

```python
# worker.py
from settings import retries, timeout


def fetch_with_policy(url: str) -> str:
    return f"{url}:{retries}:{timeout}"
```
'''

SPLIT_SETTINGS_MONOLITH = '''\
```python
# worker.py
def fetch_with_policy(url: str) -> str:
    retries = 3
    timeout = 30
    return f"{url}:{retries}:{timeout}"
```
'''


def _settings_split(by_path: dict[str, str]) -> str | None:
    missing = [path for path in ("settings.py", "worker.py") if path not in by_path]
    if missing:
        return "missing " + ", ".join(missing)
    worker = by_path["worker.py"]
    if "retries = 3" in worker or "timeout = 30" in worker:
        return "retries/timeout still assigned in worker.py"
    if "from settings import" not in worker:
        return "worker.py must import from settings"
    return None


# --- implement slugify ---

IMPLEMENT_SLUG_TASK = (
    "Write a Python function slugify(text) in slug.py. Spaces become hyphens "
    "and the result is lowercase. slugify('Hello World') must equal "
    "'hello-world'. Return one fenced file with a path comment."
)

IMPLEMENT_SLUG_GOLDEN = '''\
```python
# slug.py
def slugify(text: str) -> str:
    return "-".join(text.lower().split())
```
'''

IMPLEMENT_SLUG_NO_HYPHEN = '''\
```python
# slug.py
def slugify(text: str) -> str:
    return text.lower()
```
'''

# --- implement median ---

IMPLEMENT_MEDIAN_TASK = (
    "Write a Python function median(values) in stats_fn.py for an odd-length "
    "list of ints. median([1, 3, 2]) must equal 2. Return one fenced file "
    "with a path comment."
)

IMPLEMENT_MEDIAN_GOLDEN = '''\
```python
# stats_fn.py
def median(values: list[int]) -> int:
    ordered = sorted(values)
    return ordered[len(ordered) // 2]
```
'''

IMPLEMENT_MEDIAN_FIRST = '''\
```python
# stats_fn.py
def median(values: list[int]) -> int:
    return values[0]
```
'''

# --- generated tests that must execute ---

CLAMP_IMPL = '''\
def clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))
'''

MEDIAN_IMPL = '''\
def median(values: list[int]) -> int:
    ordered = sorted(values)
    return ordered[len(ordered) // 2]
'''

TEST_CLAMP_TASK = (
    "Write pytest tests that execute clamp for in-range and out-of-range "
    "values. Return a fenced file named test_clamp.py. Include every import. "
    "Do not change clamp.py."
)

TEST_CLAMP_GOLDEN = '''\
```python
# test_clamp.py
from clamp import clamp


def test_clamp_inside() -> None:
    assert clamp(3, 0, 5) == 3


def test_clamp_below() -> None:
    assert clamp(-2, 0, 5) == 0


def test_clamp_above() -> None:
    assert clamp(9, 0, 5) == 5
```
'''

TEST_CLAMP_SHAPE_ONLY = '''\
```python
# test_clamp.py
from clamp import clamp

def test_clamp():
    assert clamp(3, 0, 5) == 99
```
'''

TEST_MEDIAN_TASK = (
    "Write pytest tests that execute median for odd-length integer lists. "
    "Return a fenced file named test_stats_fn.py. Include every import. "
    "Do not change stats_fn.py."
)

TEST_MEDIAN_GOLDEN = '''\
```python
# test_stats_fn.py
from stats_fn import median


def test_median_middle() -> None:
    assert median([1, 3, 2]) == 2


def test_median_single() -> None:
    assert median([7]) == 7
```
'''

TEST_MEDIAN_SHAPE_ONLY = '''\
```python
# test_stats_fn.py
from stats_fn import median

def test_median():
    assert median([1, 3, 2]) == 1
```
'''


def _has_test_functions(by_path: dict[str, str]) -> str | None:
    from local_coding_slm.eval.cases import _has_test_functions as shared

    return shared(by_path)


def _run_generated_tests(merged: dict[str, str]) -> None:
    from local_coding_slm.eval.cases import _run_generated_tests as shared

    shared(merged)


# --- explain mean (prose) ---

MEAN_SOURCE = '''\
def mean(values: list[int]) -> float:
    return sum(values) / len(values)
'''

EXPLAIN_MEAN_TASK = (
    "Explain what mean does in mean.py in two or three sentences. Name the "
    "function and that it divides the sum by the length. Do not rewrite the code."
)

EXPLAIN_MEAN_GOLDEN = (
    "mean(values) adds the numbers and divides that sum by the length of the "
    "list, which is the arithmetic average."
)

EXPLAIN_MEAN_VAGUE = "This helper is useful in several places."


def _explain_mentions_average(merged: dict[str, str]) -> None:
    text = merged["_prose"].lower()
    if "average" not in text and "sum" not in text and "divid" not in text:
        raise AssertionError("explanation never mentions average, sum, or divide")


# --- review missing zero check (prose) ---

DIV_SOURCE = '''\
def ratio(a: int, b: int) -> float:
    return a / b
'''

REVIEW_DIVZERO_TASK = (
    "First-pass review of ratio() in div.py. Flag the missing zero-denominator "
    "check. Do not rewrite the function."
)

REVIEW_DIVZERO_GOLDEN = (
    "ratio() divides a by b with no zero-denominator check, so b == 0 raises. "
    "Guard the divisor before dividing."
)

REVIEW_DIVZERO_LGTM = "Looks good to me. No issues."


def _review_flags_zero(merged: dict[str, str]) -> None:
    text = merged["_prose"].lower()
    if "zero" not in text and "denominator" not in text and "divis" not in text:
        raise AssertionError("review did not flag a zero/denominator/division issue")


MORE_CASES: tuple[EvalCase, ...] = (
    EvalCase(
        id="extract_dataclass",
        tool="local_refactor",
        task=EXTRACT_DATACLASS_TASK,
        files=({"path": "people.py", "content": PEOPLE_SOURCE},),
        required_paths=("person_model.py", "people.py"),
        required_top_level=("as_person", "label", "tagged"),
        extra_structure=_person_must_move,
        behavior=(
            BehaviorCheck("people", "tagged", ("Ada", 36), "Ada:36"),
        ),
        max_tokens=1200,
        category="extract",
    ),
    EvalCase(
        id="extract_dataclass_vague",
        tool="local_refactor",
        task=EXTRACT_DATACLASS_TASK_VAGUE,
        files=({"path": "people.py", "content": PEOPLE_SOURCE},),
        required_paths=("person_model.py", "people.py"),
        required_top_level=("as_person", "label", "tagged"),
        extra_structure=_person_must_move,
        behavior=(
            BehaviorCheck("people", "tagged", ("Ada", 36), "Ada:36"),
        ),
        max_tokens=1200,
        category="prompt_contract",
    ),
    EvalCase(
        id="rename_three_files",
        tool="local_refactor",
        task=RENAME_THREE_TASK,
        files=(
            {"path": "http_client.py", "content": HTTP_SOURCE},
            {"path": "service.py", "content": SERVICE_SOURCE},
            {"path": "main.py", "content": MAIN_SOURCE},
        ),
        required_paths=("http_client.py", "service.py", "main.py"),
        required_top_level=("load", "load_item", "run"),
        extra_structure=_fetch_must_drop,
        behavior=(BehaviorCheck("main", "run", ("ab",), "AB"),),
        max_tokens=1200,
        category="rename",
    ),
    EvalCase(
        id="split_settings",
        tool="local_refactor",
        task=SPLIT_SETTINGS_TASK,
        files=({"path": "worker.py", "content": WORKER_SOURCE},),
        required_paths=("settings.py", "worker.py"),
        required_top_level=("fetch_with_policy",),
        extra_structure=_settings_split,
        behavior=(BehaviorCheck("worker", "fetch_with_policy", ("x",), "x:3:30"),),
        max_tokens=1200,
        category="split",
    ),
    EvalCase(
        id="implement_slug",
        tool="local_code",
        task=IMPLEMENT_SLUG_TASK,
        files=(),
        required_paths=("slug.py",),
        required_top_level=("slugify",),
        behavior=(
            BehaviorCheck("slug", "slugify", ("Hello World",), "hello-world"),
            BehaviorCheck("slug", "slugify", ("Ada",), "ada"),
        ),
        category="implement",
    ),
    EvalCase(
        id="implement_median",
        tool="local_code",
        task=IMPLEMENT_MEDIAN_TASK,
        files=(),
        required_paths=("stats_fn.py",),
        required_top_level=("median",),
        behavior=(
            BehaviorCheck("stats_fn", "median", ([1, 3, 2],), 2),
            BehaviorCheck("stats_fn", "median", ([7],), 7),
        ),
        category="implement",
    ),
    EvalCase(
        id="test_clamp_execute",
        tool="local_generate_tests",
        task=TEST_CLAMP_TASK,
        files=({"path": "clamp.py", "content": CLAMP_IMPL},),
        style="pytest",
        extra_structure=_has_test_functions,
        behavior_fn=_run_generated_tests,
        category="tests",
    ),
    EvalCase(
        id="test_median_execute",
        tool="local_generate_tests",
        task=TEST_MEDIAN_TASK,
        files=({"path": "stats_fn.py", "content": MEDIAN_IMPL},),
        style="pytest",
        extra_structure=_has_test_functions,
        behavior_fn=_run_generated_tests,
        category="tests",
    ),
    EvalCase(
        id="explain_mean",
        tool="local_explain",
        task=EXPLAIN_MEAN_TASK,
        files=({"path": "mean.py", "content": MEAN_SOURCE},),
        expect_fences=False,
        required_phrases=("mean", "sum"),
        behavior_fn=_explain_mentions_average,
        category="explain",
    ),
    EvalCase(
        id="review_divzero",
        tool="local_review",
        task=REVIEW_DIVZERO_TASK,
        files=({"path": "div.py", "content": DIV_SOURCE},),
        expect_fences=False,
        required_phrases=("zero",),
        behavior_fn=_review_flags_zero,
        category="review",
    ),
)

MORE_GOLDEN = {
    "extract_dataclass": EXTRACT_DATACLASS_GOLDEN,
    "extract_dataclass_vague": EXTRACT_DATACLASS_GOLDEN,
    "rename_three_files": RENAME_THREE_GOLDEN,
    "split_settings": SPLIT_SETTINGS_GOLDEN,
    "implement_slug": IMPLEMENT_SLUG_GOLDEN,
    "implement_median": IMPLEMENT_MEDIAN_GOLDEN,
    "test_clamp_execute": TEST_CLAMP_GOLDEN,
    "test_median_execute": TEST_MEDIAN_GOLDEN,
    "explain_mean": EXPLAIN_MEAN_GOLDEN,
    "review_divzero": REVIEW_DIVZERO_GOLDEN,
}

MORE_OBSERVED = {
    "extract_dataclass": EXTRACT_DATACLASS_NESTED,
    "rename_three_files": RENAME_THREE_PARTIAL,
    "split_settings": SPLIT_SETTINGS_MONOLITH,
    "implement_slug": IMPLEMENT_SLUG_NO_HYPHEN,
    "implement_median": IMPLEMENT_MEDIAN_FIRST,
    "test_median_execute": TEST_MEDIAN_SHAPE_ONLY,
    "explain_mean": EXPLAIN_MEAN_VAGUE,
    "review_divzero": REVIEW_DIVZERO_LGTM,
}

MORE_PERSISTENT_FAST = {
    "extract_dataclass_vague": EXTRACT_DATACLASS_NESTED,
    "test_clamp_execute": TEST_CLAMP_SHAPE_ONLY,
}
