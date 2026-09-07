"""Non-seed corpus: multi-file refactors plus local_code / explain / review.

These cases stay bounded. They are not whole-repo rewrites. Golden strings are
fixtures for the scorer and stub Ollama, not live model dumps.
"""

from __future__ import annotations

import ast

from local_coding_slm.eval.score import BehaviorCheck, EvalCase

# --- move clamp into bounds.py and fix imports ---

MATH_OPS_SOURCE = """\
def clamp(value: int, lo: int, hi: int) -> int:
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value


def mean(xs: list[int]) -> float:
    return sum(xs) / len(xs) if xs else 0.0
"""

REPORT_SOURCE = """\
from math_ops import clamp, mean


def summarize(xs: list[int], lo: int, hi: int) -> float:
    capped = [clamp(x, lo, hi) for x in xs]
    return mean(capped)
"""

MOVE_FUNCTION_TASK = (
    "Move clamp from math_ops.py into a new module bounds.py. "
    "Keep mean in math_ops.py. Update report.py so it imports clamp from "
    "bounds and mean from math_ops. Preserve summarize() behavior. "
    "Return three fenced Python files with path comments bounds.py, "
    "math_ops.py, and report.py, no prose."
)

MOVE_FUNCTION_GOLDEN = '''\
```python
# bounds.py
def clamp(value: int, lo: int, hi: int) -> int:
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value
```

```python
# math_ops.py
def mean(xs: list[int]) -> float:
    return sum(xs) / len(xs) if xs else 0.0
```

```python
# report.py
from bounds import clamp
from math_ops import mean


def summarize(xs: list[int], lo: int, hi: int) -> float:
    capped = [clamp(x, lo, hi) for x in xs]
    return mean(capped)
```
'''

MOVE_FUNCTION_PARTIAL = '''\
```python
# bounds.py
def clamp(value: int, lo: int, hi: int) -> int:
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value
```

```python
# math_ops.py
def mean(xs: list[int]) -> float:
    return sum(xs) / len(xs) if xs else 0.0
```
'''


def _top_level_names(tree: ast.AST) -> set[str]:
    return (
        {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
        if isinstance(tree, ast.Module)
        else set()
    )


def _clamp_must_move(by_path: dict[str, str]) -> str | None:
    try:
        bounds = ast.parse(by_path.get("bounds.py", ""))
        math_ops = ast.parse(by_path.get("math_ops.py", ""))
    except SyntaxError as exc:
        return f"unparseable Python: {exc.msg}"
    if "clamp" not in _top_level_names(bounds):
        return "bounds.py is missing module-level clamp"
    if "clamp" in _top_level_names(math_ops):
        return "clamp is still defined in math_ops.py"
    if "mean" not in _top_level_names(math_ops):
        return "math_ops.py is missing mean"
    report = by_path.get("report.py", "")
    if "from bounds import clamp" not in report:
        return "report.py must import clamp from bounds"
    if "from math_ops import clamp" in report:
        return "report.py still imports clamp from math_ops"
    return None


# --- extract shared CSV field parser ---

CSV_USERS_SOURCE = """\
def parse_user(line: str) -> tuple[str, str]:
    parts = [p.strip() for p in line.split(",")]
    return parts[0], parts[1]


def user_email(line: str) -> str:
    _, email = parse_user(line)
    return email.lower()
"""

CSV_ORDERS_SOURCE = """\
def parse_order(line: str) -> tuple[str, int]:
    parts = [p.strip() for p in line.split(",")]
    return parts[0], int(parts[1])


def order_qty(line: str) -> int:
    _, qty = parse_order(line)
    return qty
"""

EXTRACT_PARSER_TASK = (
    "Extract the repeated comma-split-and-strip into a module-level function "
    "parse_fields(line) -> list[str] in a new csv_parse.py. "
    "csv_users.py and csv_orders.py must import parse_fields and keep "
    "parse_user, user_email, parse_order, and order_qty. Preserve behavior. "
    "Return three fenced Python files csv_parse.py, csv_users.py, csv_orders.py."
)

EXTRACT_PARSER_GOLDEN = '''\
```python
# csv_parse.py
def parse_fields(line: str) -> list[str]:
    return [p.strip() for p in line.split(",")]
```

```python
# csv_users.py
from csv_parse import parse_fields


def parse_user(line: str) -> tuple[str, str]:
    parts = parse_fields(line)
    return parts[0], parts[1]


def user_email(line: str) -> str:
    _, email = parse_user(line)
    return email.lower()
```

```python
# csv_orders.py
from csv_parse import parse_fields


def parse_order(line: str) -> tuple[str, int]:
    parts = parse_fields(line)
    return parts[0], int(parts[1])


def order_qty(line: str) -> int:
    _, qty = parse_order(line)
    return qty
```
'''

EXTRACT_PARSER_NESTED = '''\
```python
# csv_parse.py
def unused() -> None:
    return None
```

```python
# csv_users.py
def parse_user(line: str) -> tuple[str, str]:
    def parse_fields(line: str) -> list[str]:
        return [p.strip() for p in line.split(",")]

    parts = parse_fields(line)
    return parts[0], parts[1]


def user_email(line: str) -> str:
    _, email = parse_user(line)
    return email.lower()
```

```python
# csv_orders.py
from csv_parse import parse_fields


def parse_order(line: str) -> tuple[str, int]:
    parts = parse_fields(line)
    return parts[0], int(parts[1])


def order_qty(line: str) -> int:
    _, qty = parse_order(line)
    return qty
```
'''

EXTRACT_PARSER_NO_STRIP = '''\
```python
# csv_parse.py
def parse_fields(line: str) -> list[str]:
    return line.split(",")
```

```python
# csv_users.py
from csv_parse import parse_fields


def parse_user(line: str) -> tuple[str, str]:
    parts = parse_fields(line)
    return parts[0], parts[1]


def user_email(line: str) -> str:
    _, email = parse_user(line)
    return email.lower()
```

```python
# csv_orders.py
from csv_parse import parse_fields


def parse_order(line: str) -> tuple[str, int]:
    parts = parse_fields(line)
    return parts[0], int(parts[1])


def order_qty(line: str) -> int:
    _, qty = parse_order(line)
    return qty
```
'''


def _parser_is_module_level(by_path: dict[str, str]) -> str | None:
    try:
        tree = ast.parse(by_path.get("csv_parse.py", ""))
    except SyntaxError as exc:
        return f"csv_parse.py is not parseable: {exc.msg}"
    if "parse_fields" not in _top_level_names(tree):
        return "csv_parse.py is missing module-level parse_fields"
    users = by_path.get("csv_users.py", "")
    orders = by_path.get("csv_orders.py", "")
    if "from csv_parse import parse_fields" not in users:
        return "csv_users.py must import parse_fields from csv_parse"
    if "from csv_parse import parse_fields" not in orders:
        return "csv_orders.py must import parse_fields from csv_parse"
    return None


# --- split a one-file pipeline ---

PIPELINE_SOURCE = """\
def run(raw: str) -> str:
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    nums = [int(p) for p in parts]
    return str(sum(nums))
"""

SPLIT_PIPELINE_TASK = (
    "Split pipeline.py into three modules: load.py with parse_ints(raw) -> "
    "list[int], transform.py with total(nums) -> int, and pipeline.py with "
    "run(raw) -> str that calls both. Preserve run(' 1, 2, 3 ') == '6'. "
    "Return fenced files load.py, transform.py, and pipeline.py, no prose."
)

SPLIT_PIPELINE_GOLDEN = '''\
```python
# load.py
def parse_ints(raw: str) -> list[int]:
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return [int(p) for p in parts]
```

```python
# transform.py
def total(nums: list[int]) -> int:
    return sum(nums)
```

```python
# pipeline.py
from load import parse_ints
from transform import total


def run(raw: str) -> str:
    return str(total(parse_ints(raw)))
```
'''

SPLIT_PIPELINE_MONOLITH = '''\
```python
# pipeline.py
def run(raw: str) -> str:
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    nums = [int(p) for p in parts]
    return str(sum(nums))
```
'''


def _pipeline_split(by_path: dict[str, str]) -> str | None:
    missing = [path for path in ("load.py", "transform.py", "pipeline.py") if path not in by_path]
    if missing:
        return "missing " + ", ".join(missing)
    try:
        load = ast.parse(by_path["load.py"])
        transform = ast.parse(by_path["transform.py"])
        pipe = ast.parse(by_path["pipeline.py"])
    except SyntaxError as exc:
        return f"unparseable Python: {exc.msg}"
    if "parse_ints" not in _top_level_names(load):
        return "load.py is missing parse_ints"
    if "total" not in _top_level_names(transform):
        return "transform.py is missing total"
    if "run" not in _top_level_names(pipe):
        return "pipeline.py is missing run"
    return None


# --- local_code: implement clamp from a spec ---

IMPLEMENT_CLAMP_TASK = (
    "Write a Python function clamp(value, lo, hi) in clamp.py. "
    "It must return lo when value is below lo, hi when value is above hi, "
    "and value otherwise. Return one fenced file with a path comment."
)

IMPLEMENT_CLAMP_GOLDEN = '''\
```python
# clamp.py
def clamp(value: int, lo: int, hi: int) -> int:
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value
```
'''

IMPLEMENT_CLAMP_NO_HI = '''\
```python
# clamp.py
def clamp(value: int, lo: int, hi: int) -> int:
    if value < lo:
        return lo
    return value
```
'''


# --- local_explain (prose) ---

EXPLAIN_CLAMP_SOURCE = """\
def clamp(value: int, lo: int, hi: int) -> int:
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value
"""

EXPLAIN_CLAMP_TASK = (
    "Explain clamp() in one short paragraph. Name the function, the lo and hi "
    "bounds, and that values outside the range are clipped. Do not rewrite the code."
)

EXPLAIN_CLAMP_GOLDEN = (
    "clamp(value, lo, hi) returns lo when value is below the lower bound, "
    "hi when value is above the upper bound, and value when it already lies "
    "inside the range. Out-of-range inputs are clipped."
)

EXPLAIN_CLAMP_VAGUE = "This helper is useful in several places."


def _explain_mentions_clip(merged: dict[str, str]) -> None:
    text = merged["_prose"].lower()
    if "clip" not in text and "bound" not in text and "range" not in text:
        raise AssertionError("explanation never says values are clipped or bounded")


# --- local_review (prose, first pass only) ---

REVIEW_LOGIN_SOURCE = """\
def login(user, password):
    return user.name + password
"""

REVIEW_LOGIN_TASK = (
    "First-pass review of login(). Flag obvious null/None use of user and the "
    "missing password/auth check. Do not rewrite the function."
)

REVIEW_LOGIN_GOLDEN = (
    "login() dereferences user.name with no None check, so a missing user "
    "raises. password is concatenated rather than verified, so there is no "
    "auth check. Add a null guard and a real password test before returning."
)

REVIEW_LOGIN_LGTM = "Looks good to me. No issues."


def _review_flags_auth(merged: dict[str, str]) -> None:
    text = merged["_prose"].lower()
    if "password" not in text and "auth" not in text:
        raise AssertionError("review did not flag password/auth")
    if "none" not in text and "null" not in text:
        raise AssertionError("review did not flag None/null use of user")


EXTENDED_CASES: tuple[EvalCase, ...] = (
    EvalCase(
        id="move_function_imports",
        tool="local_refactor",
        task=MOVE_FUNCTION_TASK,
        files=(
            {"path": "math_ops.py", "content": MATH_OPS_SOURCE},
            {"path": "report.py", "content": REPORT_SOURCE},
        ),
        required_paths=("bounds.py", "math_ops.py", "report.py"),
        required_top_level=("clamp", "mean", "summarize"),
        extra_structure=_clamp_must_move,
        behavior=(
            BehaviorCheck("report", "summarize", ([1, 8, 3], 0, 5), 3.0),
            BehaviorCheck("report", "summarize", ([], 0, 5), 0.0),
        ),
        max_tokens=1200,
    ),
    EvalCase(
        id="extract_shared_parser",
        tool="local_refactor",
        task=EXTRACT_PARSER_TASK,
        files=(
            {"path": "csv_users.py", "content": CSV_USERS_SOURCE},
            {"path": "csv_orders.py", "content": CSV_ORDERS_SOURCE},
        ),
        required_paths=("csv_parse.py", "csv_users.py", "csv_orders.py"),
        required_top_level=("parse_fields", "parse_user", "user_email", "parse_order", "order_qty"),
        extra_structure=_parser_is_module_level,
        behavior=(
            BehaviorCheck("csv_users", "user_email", (" Ada , ADA@EX.com ",), "ada@ex.com"),
            BehaviorCheck("csv_orders", "order_qty", (" widget , 3 ",), 3),
        ),
        max_tokens=1200,
    ),
    EvalCase(
        id="split_pipeline",
        tool="local_refactor",
        task=SPLIT_PIPELINE_TASK,
        files=({"path": "pipeline.py", "content": PIPELINE_SOURCE},),
        required_paths=("load.py", "transform.py", "pipeline.py"),
        required_top_level=("parse_ints", "total", "run"),
        extra_structure=_pipeline_split,
        behavior=(
            BehaviorCheck("pipeline", "run", (" 1, 2, 3 ",), "6"),
            BehaviorCheck("pipeline", "run", ("",), "0"),
        ),
        max_tokens=1200,
    ),
    EvalCase(
        id="implement_clamp",
        tool="local_code",
        task=IMPLEMENT_CLAMP_TASK,
        files=(),
        required_paths=("clamp.py",),
        required_top_level=("clamp",),
        behavior=(
            BehaviorCheck("clamp", "clamp", (3, 0, 5), 3),
            BehaviorCheck("clamp", "clamp", (-2, 0, 5), 0),
            BehaviorCheck("clamp", "clamp", (9, 0, 5), 5),
        ),
    ),
    EvalCase(
        id="explain_clamp",
        tool="local_explain",
        task=EXPLAIN_CLAMP_TASK,
        files=({"path": "clamp.py", "content": EXPLAIN_CLAMP_SOURCE},),
        expect_fences=False,
        required_phrases=("clamp", "lo", "hi"),
        behavior_fn=_explain_mentions_clip,
    ),
    EvalCase(
        id="review_login",
        tool="local_review",
        task=REVIEW_LOGIN_TASK,
        files=({"path": "auth.py", "content": REVIEW_LOGIN_SOURCE},),
        expect_fences=False,
        required_phrases=("none",),
        behavior_fn=_review_flags_auth,
    ),
)

EXTENDED_GOLDEN = {
    "move_function_imports": MOVE_FUNCTION_GOLDEN,
    "extract_shared_parser": EXTRACT_PARSER_GOLDEN,
    "split_pipeline": SPLIT_PIPELINE_GOLDEN,
    "implement_clamp": IMPLEMENT_CLAMP_GOLDEN,
    "explain_clamp": EXPLAIN_CLAMP_GOLDEN,
    "review_login": REVIEW_LOGIN_GOLDEN,
}

OBSERVED_FIRST = {
    "move_function_imports": MOVE_FUNCTION_PARTIAL,
    "extract_shared_parser": EXTRACT_PARSER_NESTED,
    "split_pipeline": SPLIT_PIPELINE_MONOLITH,
    "implement_clamp": IMPLEMENT_CLAMP_NO_HI,
    "explain_clamp": EXPLAIN_CLAMP_VAGUE,
    "review_login": REVIEW_LOGIN_LGTM,
}
