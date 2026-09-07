"""Score a candidate against a case at independent layers.

Layers are scored in order. A later layer is ``skip`` when an earlier
required layer failed. ``passed`` is true only when transport, format,
structure, and behavior all pass. A skipped executable layer is not a pass:
that is how a unified-diff-only response is distinguished from a refactor
that preserved behavior.
"""

from __future__ import annotations

import ast
import importlib.util
import sys
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

from local_coding_slm.eval.extract import ExtractedFile, TransportError, extract_files

LayerName = str


@dataclass(frozen=True)
class LayerResult:
    name: LayerName
    status: str  # pass | fail | skip
    message: str


@dataclass(frozen=True)
class EvalResult:
    case_id: str
    layers: tuple[LayerResult, ...]
    files: tuple[ExtractedFile, ...] = ()

    def layer(self, name: LayerName) -> LayerResult:
        for item in self.layers:
            if item.name == name:
                return item
        raise KeyError(name)

    @property
    def passed(self) -> bool:
        return all(self.layer(name).status == "pass" for name in ("transport", "format", "structure", "behavior"))

    @property
    def first_failure(self) -> LayerResult | None:
        for item in self.layers:
            if item.status == "fail":
                return item
            if item.status == "skip" and item.name in {"structure", "behavior"}:
                return item
        return None


@dataclass(frozen=True)
class BehaviorCheck:
    """Call ``module.function(*args)`` after loading extracted files as modules."""

    module: str
    function: str
    args: tuple[Any, ...]
    expected: Any


@dataclass(frozen=True)
class EvalCase:
    id: str
    tool: str
    task: str
    files: tuple[dict[str, str], ...]
    language: str = "python"
    style: str = ""
    required_paths: tuple[str, ...] = ()
    required_top_level: tuple[str, ...] = ()
    behavior: tuple[BehaviorCheck, ...] = ()
    extra_structure: Callable[[dict[str, str]], str | None] | None = None
    behavior_fn: Callable[[dict[str, str]], None] | None = None


def score_candidate(text: str, case: EvalCase) -> EvalResult:
    layers: list[LayerResult] = []
    files: tuple[ExtractedFile, ...] = ()

    try:
        extracted = extract_files(text)
    except TransportError as exc:
        layers.extend(
            [
                LayerResult("transport", "fail", str(exc)),
                LayerResult("format", "skip", "skipped after transport failure"),
                LayerResult("structure", "skip", "skipped after transport failure"),
                LayerResult("behavior", "skip", "skipped after transport failure"),
            ]
        )
        return EvalResult(case.id, tuple(layers), files)
    except ValueError as exc:
        layers.extend(
            [
                LayerResult("transport", "pass", "candidate is not an ERROR payload"),
                LayerResult("format", "fail", str(exc)),
                LayerResult("structure", "skip", "skipped after format failure"),
                LayerResult("behavior", "skip", "skipped after format failure"),
            ]
        )
        return EvalResult(case.id, tuple(layers), files)

    layers.append(LayerResult("transport", "pass", "candidate is not an ERROR payload"))

    if not extracted:
        layers.extend(
            [
                LayerResult("format", "fail", "extractor returned no files"),
                LayerResult("structure", "skip", "skipped after format failure"),
                LayerResult("behavior", "skip", "skipped after format failure"),
            ]
        )
        return EvalResult(case.id, tuple(layers), files)

    files = tuple(extracted)
    kinds = {item.kind for item in files}
    if kinds == {"diff"}:
        layers.extend(
            [
                LayerResult("format", "pass", "unified diff parsed; executable layers need fenced files"),
                LayerResult("structure", "skip", "diff-only responses are not executed"),
                LayerResult("behavior", "skip", "diff-only responses are not executed"),
            ]
        )
        return EvalResult(case.id, tuple(layers), files)

    if "fence" not in kinds:
        layers.extend(
            [
                LayerResult("format", "fail", f"unsupported extract kinds: {sorted(kinds)}"),
                LayerResult("structure", "skip", "skipped after format failure"),
                LayerResult("behavior", "skip", "skipped after format failure"),
            ]
        )
        return EvalResult(case.id, tuple(layers), files)

    by_path = {item.path: item.content for item in files if item.kind == "fence"}
    by_path = _alias_single_unknown(by_path, case)
    missing = [path for path in case.required_paths if path not in by_path]
    if missing:
        layers.append(
            LayerResult(
                "format",
                "fail",
                "missing required fenced path(s): " + ", ".join(missing),
            )
        )
        layers.append(LayerResult("structure", "skip", "skipped after format failure"))
        layers.append(LayerResult("behavior", "skip", "skipped after format failure"))
        return EvalResult(case.id, tuple(layers), files)

    layers.append(
        LayerResult(
            "format",
            "pass",
            f"{len(by_path)} fenced file(s): " + ", ".join(sorted(by_path)),
        )
    )

    structure_error = _structure_error(by_path, case)
    if structure_error:
        layers.append(LayerResult("structure", "fail", structure_error))
        layers.append(LayerResult("behavior", "skip", "skipped after structure failure"))
        return EvalResult(case.id, tuple(layers), files)

    layers.append(LayerResult("structure", "pass", _structure_ok_message(case)))

    merged = {item["path"]: item["content"] for item in case.files}
    merged.update(by_path)

    if case.behavior_fn is None and not case.behavior:
        layers.append(LayerResult("behavior", "pass", "no executable checks on this case"))
        return EvalResult(case.id, tuple(layers), files)

    try:
        if case.behavior_fn is not None:
            case.behavior_fn(merged)
            detail = "custom executable check passed"
        else:
            _run_behavior(merged, case.behavior)
            detail = f"{len(case.behavior)} executed check(s) matched"
    except Exception as exc:
        layers.append(LayerResult("behavior", "fail", f"{type(exc).__name__}: {exc}"))
        return EvalResult(case.id, tuple(layers), files)

    layers.append(LayerResult("behavior", "pass", detail))
    return EvalResult(case.id, tuple(layers), files)


def _alias_single_unknown(by_path: dict[str, str], case: EvalCase) -> dict[str, str]:
    """If the model omitted a path comment on a single-file case, use the source path."""
    source_paths = [item["path"] for item in case.files if item.get("path")]
    if len(by_path) == 1 and "unknown" in by_path and len(source_paths) == 1:
        return {source_paths[0]: by_path["unknown"]}
    return by_path


def _structure_ok_message(case: EvalCase) -> str:
    bits: list[str] = []
    if case.required_top_level:
        bits.append("top-level " + ", ".join(case.required_top_level))
    if case.extra_structure is not None:
        bits.append("extra structure check")
    return "structure ok" if not bits else "; ".join(bits)


def _structure_error(by_path: dict[str, str], case: EvalCase) -> str | None:
    python_files = {
        path: content
        for path, content in by_path.items()
        if path.endswith(".py") or case.language == "python"
    }
    if case.required_top_level:
        names: set[str] = set()
        for path, content in python_files.items():
            try:
                tree = ast.parse(content)
            except SyntaxError as exc:
                return f"{path} is not parseable Python: {exc.msg}"
            names.update(_top_level_functions(tree))
        missing = [name for name in case.required_top_level if name not in names]
        if missing:
            nested = _nested_location(python_files, missing)
            if nested:
                return nested
            return "missing module-level function(s): " + ", ".join(missing)
    if case.extra_structure is not None:
        return case.extra_structure(by_path)
    return None


def _top_level_functions(tree: ast.AST) -> set[str]:
    return {node.name for node in tree.body if isinstance(node, ast.FunctionDef)} if isinstance(tree, ast.Module) else set()


def _nested_location(python_files: dict[str, str], missing: list[str]) -> str | None:
    wanted = set(missing)
    for path, content in python_files.items():
        try:
            tree = ast.parse(content)
        except SyntaxError:
            continue
        if not isinstance(tree, ast.Module):
            continue
        for outer in tree.body:
            if not isinstance(outer, ast.FunctionDef):
                continue
            nested = [
                node.name
                for node in outer.body
                if isinstance(node, ast.FunctionDef) and node.name in wanted
            ]
            if nested:
                return (
                    f"{', '.join(nested)} is nested inside {outer.name} in {path}; "
                    "the case contract requires a module-level (top-level) helper"
                )
    return None


def _run_behavior(by_path: dict[str, str], checks: Sequence[BehaviorCheck]) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for rel, content in by_path.items():
            dest = root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")
        loaded: dict[str, ModuleType] = {}
        try:
            for check in checks:
                module = _load_module(root, check.module, loaded)
                func = getattr(module, check.function, None)
                if not callable(func):
                    raise AssertionError(
                        f"{check.module}.{check.function} is not callable"
                    )
                actual = func(*check.args)
                if actual != check.expected:
                    raise AssertionError(
                        f"{check.module}.{check.function}{check.args!r}: "
                        f"expected {check.expected!r}, got {actual!r}"
                    )
        finally:
            for name, mod in list(sys.modules.items()):
                file = getattr(mod, "__file__", None)
                if file and Path(file).is_relative_to(root):
                    sys.modules.pop(name, None)
            sys.path = [p for p in sys.path if p != str(root)]


def _load_module(root: Path, name: str, loaded: dict[str, ModuleType]) -> ModuleType:
    if name in loaded:
        return loaded[name]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    path = root / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load module {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    loaded[name] = module
    return module
