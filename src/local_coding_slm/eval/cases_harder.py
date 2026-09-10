"""Harder multi-file refactor cases for Phase 3 quality measurement.

These stay bounded (2–3 files). They isolate failure modes the seed and
extended corpus do not: leftover type aliases, catch-site drift, field
aliases, a leftover keyword-parameter alias, and a public facade that
must survive a helper signature change.

Golden strings are fixtures for the scorer and stub Ollama, not live
model dumps. Live rates are not claimed here.
"""

from __future__ import annotations

import ast

from local_coding_slm.eval.score import BehaviorCheck, EvalCase

HARDER_CASE_IDS: tuple[str, ...] = (
    "rename_exception_across_files",
    "rename_dataclass_field",
    "widen_return_keep_facade",
    "rename_kwarg_across_files",
)


def _top_level_classes(tree: ast.AST) -> set[str]:
    return (
        {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
        if isinstance(tree, ast.Module)
        else set()
    )


def _name_used(tree: ast.AST, name: str) -> bool:
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == name:
            return True
        if isinstance(node, ast.Attribute) and node.attr == name:
            return True
    return False


def _raises_named(tree: ast.AST, name: str) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Raise) or node.exc is None:
            continue
        exc = node.exc
        if isinstance(exc, ast.Call) and isinstance(exc.func, ast.Name) and exc.func.id == name:
            return True
        if isinstance(exc, ast.Name) and exc.id == name:
            return True
    return False


def _excepts_named(tree: ast.AST, name: str) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler) or node.type is None:
            continue
        if isinstance(node.type, ast.Name) and node.type.id == name:
            return True
    return False


def _function_arg_names(tree: ast.AST, name: str) -> tuple[set[str], bool]:
    if not isinstance(tree, ast.Module):
        return set(), False
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or node.name != name:
            continue
        names = {arg.arg for arg in node.args.posonlyargs}
        names.update(arg.arg for arg in node.args.args)
        names.update(arg.arg for arg in node.args.kwonlyargs)
        if node.args.vararg is not None:
            names.add(node.args.vararg.arg)
        has_kwargs = node.args.kwarg is not None
        if node.args.kwarg is not None:
            names.add(node.args.kwarg.arg)
        return names, has_kwargs
    return set(), False


def _keyword_used(tree: ast.AST, name: str) -> bool:
    return any(
        isinstance(node, ast.keyword) and node.arg == name for node in ast.walk(tree)
    )


def _function_returns_tuple(tree: ast.AST, name: str) -> bool:
    if not isinstance(tree, ast.Module):
        return False
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or node.name != name:
            continue
        for child in ast.walk(node):
            if isinstance(child, ast.Return) and isinstance(child.value, ast.Tuple):
                return True
    return False


# --- rename QuotaError -> LimitError across raise and catch ---

ERRORS_SOURCE = """\
class QuotaError(Exception):
    pass
"""

STORE_SOURCE = """\
from errors import QuotaError


def reserve(n: int) -> str:
    if n > 3:
        raise QuotaError("too many")
    return f"ok:{n}"
"""

CHECKOUT_SOURCE = """\
from errors import QuotaError
from store import reserve


def buy(n: int) -> str:
    try:
        return reserve(n)
    except QuotaError:
        return "denied"
"""

RENAME_EXCEPTION_TASK = (
    "Rename QuotaError to LimitError in errors.py, store.py, and checkout.py. "
    "Do not keep QuotaError as a class, alias, or except-name. "
    "store.reserve must still raise the renamed error when n > 3. "
    "checkout.buy must catch LimitError and keep returning 'denied'. "
    "Preserve buy(2)=='ok:2', buy(3)=='ok:3', and buy(4)=='denied'. "
    "Return three fenced Python files with path comments errors.py, store.py, "
    "and checkout.py, no prose."
)

RENAME_EXCEPTION_GOLDEN = '''\
```python
# errors.py
class LimitError(Exception):
    pass
```

```python
# store.py
from errors import LimitError


def reserve(n: int) -> str:
    if n > 3:
        raise LimitError("too many")
    return f"ok:{n}"
```

```python
# checkout.py
from errors import LimitError
from store import reserve


def buy(n: int) -> str:
    try:
        return reserve(n)
    except LimitError:
        return "denied"
```
'''

RENAME_EXCEPTION_PARTIAL = '''\
```python
# errors.py
class LimitError(Exception):
    pass
```

```python
# store.py
from errors import LimitError


def reserve(n: int) -> str:
    if n > 3:
        raise LimitError("too many")
    return f"ok:{n}"
```
'''

RENAME_EXCEPTION_ALIAS = '''\
```python
# errors.py
class LimitError(Exception):
    pass


QuotaError = LimitError
```

```python
# store.py
from errors import LimitError, QuotaError


def reserve(n: int) -> str:
    if n > 3:
        raise QuotaError("too many")
    return f"ok:{n}"
```

```python
# checkout.py
from errors import QuotaError
from store import reserve


def buy(n: int) -> str:
    try:
        return reserve(n)
    except QuotaError:
        return "denied"
```
'''

RENAME_EXCEPTION_THRESHOLD = '''\
```python
# errors.py
class LimitError(Exception):
    pass
```

```python
# store.py
from errors import LimitError


def reserve(n: int) -> str:
    if n > 2:
        raise LimitError("too many")
    return f"ok:{n}"
```

```python
# checkout.py
from errors import LimitError
from store import reserve


def buy(n: int) -> str:
    try:
        return reserve(n)
    except LimitError:
        return "denied"
```
'''


def _exception_renamed(by_path: dict[str, str]) -> str | None:
    try:
        errors = ast.parse(by_path.get("errors.py", ""))
        store = ast.parse(by_path.get("store.py", ""))
        checkout = ast.parse(by_path.get("checkout.py", ""))
    except SyntaxError as exc:
        return f"unparseable Python: {exc.msg}"
    if "LimitError" not in _top_level_classes(errors):
        return "errors.py is missing class LimitError"
    if "QuotaError" in _top_level_classes(errors):
        return "errors.py still defines QuotaError"
    for path, tree in (("errors.py", errors), ("store.py", store), ("checkout.py", checkout)):
        if _name_used(tree, "QuotaError"):
            return f"{path} still references QuotaError; do not keep an alias"
    if not _raises_named(store, "LimitError"):
        return "store.reserve must raise LimitError"
    if not _excepts_named(checkout, "LimitError"):
        return "checkout.buy must catch LimitError, not a broader Exception"
    return None


def _exception_behavior(merged: dict[str, str]) -> None:
    from local_coding_slm.eval.score import _load_module
    import sys
    import tempfile
    from pathlib import Path
    from types import ModuleType

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for rel, content in merged.items():
            dest = root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
        loaded: dict[str, ModuleType] = {}
        try:
            errors = _load_module(root, "errors", loaded)
            store = _load_module(root, "store", loaded)
            checkout = _load_module(root, "checkout", loaded)
            if hasattr(errors, "QuotaError"):
                raise AssertionError("errors.QuotaError must not remain as an alias")
            limit = getattr(errors, "LimitError", None)
            if not (isinstance(limit, type) and issubclass(limit, BaseException)):
                raise AssertionError("errors.LimitError must be an exception class")
            buy = getattr(checkout, "buy", None)
            reserve = getattr(store, "reserve", None)
            if not callable(buy) or not callable(reserve):
                raise AssertionError("buy and reserve must be callable")
            for args, expected in (((2,), "ok:2"), ((3,), "ok:3"), ((4,), "denied")):
                actual = buy(*args)
                if actual != expected:
                    raise AssertionError(f"buy{args!r}: expected {expected!r}, got {actual!r}")
            try:
                reserve(4)
            except limit:
                pass
            else:
                raise AssertionError("store.reserve(4) must raise LimitError")
        finally:
            for name, mod in list(sys.modules.items()):
                file = getattr(mod, "__file__", None)
                if file and Path(file).is_relative_to(root):
                    sys.modules.pop(name, None)
            sys.path = [p for p in sys.path if p != str(root)]


# --- rename dataclass field years -> age across producer and consumer ---

PERSON_SOURCE = """\
from dataclasses import dataclass


@dataclass
class Person:
    full_name: str
    years: int


def make_person(name: str, years: int) -> Person:
    return Person(full_name=name, years=years)
"""

GREET_SOURCE = """\
from person import make_person


def greet(name: str, years: int) -> str:
    person = make_person(name, years)
    return f"{person.full_name} ({person.years})"
"""

RENAME_FIELD_TASK = (
    "Rename the Person field years to age in person.py and greet.py. "
    "Update make_person, the constructor, and greet(). "
    "Do not keep years as a field, property, or attribute alias. "
    "Preserve greet('Ada', 36) == 'Ada (36)' and greet('', 0) == ' (0)'. "
    "Return two fenced Python files with path comments person.py and greet.py, "
    "no prose."
)

RENAME_FIELD_GOLDEN = '''\
```python
# person.py
from dataclasses import dataclass


@dataclass
class Person:
    full_name: str
    age: int


def make_person(name: str, age: int) -> Person:
    return Person(full_name=name, age=age)
```

```python
# greet.py
from person import make_person


def greet(name: str, age: int) -> str:
    person = make_person(name, age)
    return f"{person.full_name} ({person.age})"
```
'''

RENAME_FIELD_PARTIAL = '''\
```python
# person.py
from dataclasses import dataclass


@dataclass
class Person:
    full_name: str
    age: int


def make_person(name: str, age: int) -> Person:
    return Person(full_name=name, age=age)
```
'''

RENAME_FIELD_ALIAS = '''\
```python
# person.py
from dataclasses import dataclass


@dataclass
class Person:
    full_name: str
    age: int

    @property
    def years(self) -> int:
        return self.age


def make_person(name: str, years: int) -> Person:
    return Person(full_name=name, age=years)
```

```python
# greet.py
from person import make_person


def greet(name: str, years: int) -> str:
    person = make_person(name, years)
    return f"{person.full_name} ({person.years})"
```
'''

RENAME_FIELD_FORMAT = '''\
```python
# person.py
from dataclasses import dataclass


@dataclass
class Person:
    full_name: str
    age: int


def make_person(name: str, age: int) -> Person:
    return Person(full_name=name, age=age)
```

```python
# greet.py
from person import make_person


def greet(name: str, age: int) -> str:
    person = make_person(name, age)
    return f"{person.full_name}, age {person.age}"
```
'''


def _dataclass_fields(tree: ast.AST, class_name: str) -> set[str]:
    if not isinstance(tree, ast.Module):
        return set()
    names: set[str] = set()
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != class_name:
            continue
        for item in node.body:
            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                names.add(item.target.id)
            if isinstance(item, ast.FunctionDef) and item.name not in {"__init__", "__repr__", "__eq__"}:
                names.add(item.name)
    return names


def _field_renamed(by_path: dict[str, str]) -> str | None:
    try:
        person = ast.parse(by_path.get("person.py", ""))
        greet = ast.parse(by_path.get("greet.py", ""))
    except SyntaxError as exc:
        return f"unparseable Python: {exc.msg}"
    fields = _dataclass_fields(person, "Person")
    if "age" not in fields:
        return "Person is missing field age"
    if "years" in fields or _name_used(person, "years") or _name_used(greet, "years"):
        return "years must be fully renamed to age; do not keep an alias"
    if not _name_used(greet, "age"):
        return "greet.py must use the age field"
    return None


# --- widen apply_discount to a tuple; keep cart facade ---

PRICING_SOURCE = """\
def apply_discount(amount: int, percent: int) -> int:
    return amount - (amount * percent // 100)
"""

CART_SOURCE = """\
from pricing import apply_discount


def line_total(qty: int, unit: int) -> int:
    return apply_discount(qty * unit, 10)


def savings(qty: int, unit: int) -> int:
    raw = qty * unit
    return raw - line_total(qty, unit)
"""

WIDEN_RETURN_TASK = (
    "Change pricing.apply_discount so it returns a two-item tuple "
    "(discounted, saved) using integer division, not a single int. "
    "Extract the literal 10 into rates.py as DISCOUNT_PERCENT = 10. "
    "Update cart.py so line_total and savings keep the same public signatures "
    "and int return values by unpacking the tuple and importing "
    "DISCOUNT_PERCENT. Preserve line_total(2, 50) == 90 and "
    "savings(2, 50) == 10. Return three fenced Python files rates.py, "
    "pricing.py, and cart.py, no prose."
)

WIDEN_RETURN_GOLDEN = '''\
```python
# rates.py
DISCOUNT_PERCENT = 10
```

```python
# pricing.py
def apply_discount(amount: int, percent: int) -> tuple[int, int]:
    saved = amount * percent // 100
    return amount - saved, saved
```

```python
# cart.py
from pricing import apply_discount
from rates import DISCOUNT_PERCENT


def line_total(qty: int, unit: int) -> int:
    discounted, _saved = apply_discount(qty * unit, DISCOUNT_PERCENT)
    return discounted


def savings(qty: int, unit: int) -> int:
    _discounted, saved = apply_discount(qty * unit, DISCOUNT_PERCENT)
    return saved
```
'''

WIDEN_RETURN_PARTIAL = '''\
```python
# pricing.py
def apply_discount(amount: int, percent: int) -> tuple[int, int]:
    saved = amount * percent // 100
    return amount - saved, saved
```

```python
# cart.py
from pricing import apply_discount


def line_total(qty: int, unit: int) -> int:
    discounted, _saved = apply_discount(qty * unit, 10)
    return discounted


def savings(qty: int, unit: int) -> int:
    _discounted, saved = apply_discount(qty * unit, 10)
    return saved
```
'''

WIDEN_RETURN_INT = '''\
```python
# rates.py
DISCOUNT_PERCENT = 10
```

```python
# pricing.py
def apply_discount(amount: int, percent: int) -> int:
    return amount - (amount * percent // 100)
```

```python
# cart.py
from pricing import apply_discount
from rates import DISCOUNT_PERCENT


def line_total(qty: int, unit: int) -> int:
    return apply_discount(qty * unit, DISCOUNT_PERCENT)


def savings(qty: int, unit: int) -> int:
    raw = qty * unit
    return raw - line_total(qty, unit)
```
'''

WIDEN_RETURN_WRONG_RATE = '''\
```python
# rates.py
DISCOUNT_PERCENT = 15
```

```python
# pricing.py
def apply_discount(amount: int, percent: int) -> tuple[int, int]:
    saved = amount * percent // 100
    return amount - saved, saved
```

```python
# cart.py
from pricing import apply_discount
from rates import DISCOUNT_PERCENT


def line_total(qty: int, unit: int) -> int:
    discounted, _saved = apply_discount(qty * unit, DISCOUNT_PERCENT)
    return discounted


def savings(qty: int, unit: int) -> int:
    _discounted, saved = apply_discount(qty * unit, DISCOUNT_PERCENT)
    return saved
```
'''


def _widen_structure(by_path: dict[str, str]) -> str | None:
    try:
        rates = ast.parse(by_path.get("rates.py", ""))
        pricing = ast.parse(by_path.get("pricing.py", ""))
        cart = ast.parse(by_path.get("cart.py", ""))
    except SyntaxError as exc:
        return f"unparseable Python: {exc.msg}"
    assigned = {
        node.targets[0].id
        for node in rates.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
    }
    if "DISCOUNT_PERCENT" not in assigned:
        return "rates.py must assign DISCOUNT_PERCENT"
    if not _function_returns_tuple(pricing, "apply_discount"):
        return "apply_discount must return a two-item tuple, not a single int"
    if not _name_used(cart, "DISCOUNT_PERCENT"):
        return "cart.py must import and use DISCOUNT_PERCENT"
    return None


# --- rename send(subject=) -> send(title=); keep alert facade ---

MAIL_SOURCE = """\
def send(to: str, subject: str) -> str:
    return f"{to}:{subject}"
"""

NOTIFY_SOURCE = """\
from mail import send


def alert(addr: str, topic: str) -> str:
    return send(to=addr, subject=topic)
"""

RENAME_KWARG_TASK = (
    "Rename the subject parameter of mail.send to title in mail.py and "
    "notify.py. Update notify.alert so it calls send with title=, not "
    "subject=. Do not keep subject as a parameter, default, **kwargs "
    "shim, or keyword. alert(addr, topic) must keep the same public "
    "signature. Preserve alert('a@b', 'hi') == 'a@b:hi' and "
    "send('x', 'y') == 'x:y' (colon join). Return two fenced Python "
    "files with path comments mail.py and notify.py, no prose."
)

RENAME_KWARG_GOLDEN = '''\
```python
# mail.py
def send(to: str, title: str) -> str:
    return f"{to}:{title}"
```

```python
# notify.py
from mail import send


def alert(addr: str, topic: str) -> str:
    return send(to=addr, title=topic)
```
'''

RENAME_KWARG_PARTIAL = '''\
```python
# mail.py
def send(to: str, title: str) -> str:
    return f"{to}:{title}"
```
'''

RENAME_KWARG_ALIAS = '''\
```python
# mail.py
def send(to: str, title: str = "", subject: str = "") -> str:
    return f"{to}:{title or subject}"
```

```python
# notify.py
from mail import send


def alert(addr: str, topic: str) -> str:
    return send(to=addr, subject=topic)
```
'''

RENAME_KWARG_SEPARATOR = '''\
```python
# mail.py
def send(to: str, title: str) -> str:
    return f"{to}|{title}"
```

```python
# notify.py
from mail import send


def alert(addr: str, topic: str) -> str:
    return send(to=addr, title=topic)
```
'''


def _kwarg_renamed(by_path: dict[str, str]) -> str | None:
    try:
        mail = ast.parse(by_path.get("mail.py", ""))
        notify = ast.parse(by_path.get("notify.py", ""))
    except SyntaxError as exc:
        return f"unparseable Python: {exc.msg}"
    args, has_kwargs = _function_arg_names(mail, "send")
    if "title" not in args:
        return "mail.send must take a title parameter"
    if "subject" in args:
        return "mail.send still accepts subject; do not keep a parameter alias"
    if has_kwargs:
        return "mail.send must not use **kwargs as a subject alias"
    for path, tree in (("mail.py", mail), ("notify.py", notify)):
        if _name_used(tree, "subject") or _keyword_used(tree, "subject"):
            return f"{path} still references subject; do not keep an alias"
    if not _keyword_used(notify, "title"):
        return "notify.alert must pass title= to send"
    return None


HARDER_CASES: tuple[EvalCase, ...] = (
    EvalCase(
        id="rename_exception_across_files",
        tool="local_refactor",
        task=RENAME_EXCEPTION_TASK,
        files=(
            {"path": "errors.py", "content": ERRORS_SOURCE},
            {"path": "store.py", "content": STORE_SOURCE},
            {"path": "checkout.py", "content": CHECKOUT_SOURCE},
        ),
        required_paths=("errors.py", "store.py", "checkout.py"),
        required_top_level=("reserve", "buy"),
        extra_structure=_exception_renamed,
        behavior_fn=_exception_behavior,
        max_tokens=1400,
    ),
    EvalCase(
        id="rename_dataclass_field",
        tool="local_refactor",
        task=RENAME_FIELD_TASK,
        files=(
            {"path": "person.py", "content": PERSON_SOURCE},
            {"path": "greet.py", "content": GREET_SOURCE},
        ),
        required_paths=("person.py", "greet.py"),
        required_top_level=("make_person", "greet"),
        extra_structure=_field_renamed,
        behavior=(
            BehaviorCheck("greet", "greet", ("Ada", 36), "Ada (36)"),
            BehaviorCheck("greet", "greet", ("", 0), " (0)"),
            BehaviorCheck("greet", "greet", ("Grace", 1), "Grace (1)"),
        ),
        max_tokens=1200,
    ),
    EvalCase(
        id="widen_return_keep_facade",
        tool="local_refactor",
        task=WIDEN_RETURN_TASK,
        files=(
            {"path": "pricing.py", "content": PRICING_SOURCE},
            {"path": "cart.py", "content": CART_SOURCE},
        ),
        required_paths=("rates.py", "pricing.py", "cart.py"),
        required_top_level=("apply_discount", "line_total", "savings"),
        extra_structure=_widen_structure,
        behavior=(
            BehaviorCheck("pricing", "apply_discount", (100, 10), (90, 10)),
            BehaviorCheck("cart", "line_total", (2, 50), 90),
            BehaviorCheck("cart", "savings", (2, 50), 10),
            BehaviorCheck("cart", "line_total", (1, 0), 0),
            BehaviorCheck("cart", "savings", (1, 0), 0),
        ),
        max_tokens=1400,
    ),
    EvalCase(
        id="rename_kwarg_across_files",
        tool="local_refactor",
        task=RENAME_KWARG_TASK,
        files=(
            {"path": "mail.py", "content": MAIL_SOURCE},
            {"path": "notify.py", "content": NOTIFY_SOURCE},
        ),
        required_paths=("mail.py", "notify.py"),
        required_top_level=("send", "alert"),
        extra_structure=_kwarg_renamed,
        behavior=(
            BehaviorCheck("notify", "alert", ("a@b", "hi"), "a@b:hi"),
            BehaviorCheck("notify", "alert", ("", ""), ":"),
            BehaviorCheck("mail", "send", ("x", "y"), "x:y"),
        ),
        max_tokens=1200,
    ),
)

HARDER_GOLDEN = {
    "rename_exception_across_files": RENAME_EXCEPTION_GOLDEN,
    "rename_dataclass_field": RENAME_FIELD_GOLDEN,
    "widen_return_keep_facade": WIDEN_RETURN_GOLDEN,
    "rename_kwarg_across_files": RENAME_KWARG_GOLDEN,
}

HARDER_OBSERVED_FIRST = {
    "rename_exception_across_files": RENAME_EXCEPTION_PARTIAL,
    "rename_dataclass_field": RENAME_FIELD_PARTIAL,
    "widen_return_keep_facade": WIDEN_RETURN_PARTIAL,
    "rename_kwarg_across_files": RENAME_KWARG_PARTIAL,
}
