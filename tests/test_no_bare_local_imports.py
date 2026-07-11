"""Static guard: every local import in src/ and tests/ uses the canonical
`src.` path.

Generalizes tests/test_narration_import_consistency.py to all local engine
modules. Bare imports (`import items`, `from functions import ...`) resolve to
a SEPARATE module object from `src.items` / `src.functions` whenever src/ is
on sys.path, splitting classes and module-level state across the API/engine
boundary (see issue #271). With src/import_sync.py and the conftest aliasing
hooks retired, nothing collapses that split at runtime any more — this static
check is the guard.

AST-based so docstrings and comments can't false-positive.
"""

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
_TESTS = _ROOT / "tests"

# Top-level local module/package names under src/ that must only be imported
# via the `src.` prefix (or a relative import inside their own package).
# 'api' is included for tests/ scanning via _LOCAL_AND_API (bare `from api...`
# also resolves to a duplicate when src/ is on sys.path).
_LOCAL_MODULES = frozenset(
    p.stem if p.is_file() else p.name
    for p in _SRC.iterdir()
    if (p.suffix == ".py" and p.stem != "__init__")
    or (p.is_dir() and (p / "__init__.py").exists())
)


def _is_dynamic_import_call(node):
    """Match importlib.import_module(...) / import_module(...) / __import__(...)."""
    func = node.func
    if isinstance(func, ast.Name):
        return func.id in ("import_module", "__import__")
    if isinstance(func, ast.Attribute):
        return func.attr == "import_module"
    return False


def _bare_import_offenders(root, modules):
    offenders = []
    for py in sorted(root.rglob("*.py")):
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        except SyntaxError:
            continue  # scratch/broken scripts are not import-graph citizens
        rel = py.relative_to(_ROOT)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".", 1)[0] in modules:
                        offenders.append(f"{rel}:{node.lineno} import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if (
                    node.level == 0
                    and node.module
                    and node.module.split(".", 1)[0] in modules
                ):
                    offenders.append(
                        f"{rel}:{node.lineno} from {node.module} import ..."
                    )
            elif isinstance(node, ast.Call) and _is_dynamic_import_call(node):
                # Constant-string dynamic imports must be canonical too;
                # computed names go through functions.canonical_module_name.
                if node.args and isinstance(node.args[0], ast.Constant):
                    name = node.args[0].value
                    if (
                        isinstance(name, str)
                        and name.split(".", 1)[0] in modules
                    ):
                        offenders.append(
                            f"{rel}:{node.lineno} import_module({name!r})"
                        )
    return offenders


def test_no_bare_local_imports_in_src():
    offenders = _bare_import_offenders(_SRC, _LOCAL_MODULES)
    assert not offenders, (
        "Bare local imports found in src/ (must use the canonical `src.` path — "
        "bare imports create duplicate module objects with separate classes and "
        "state whenever src/ is on sys.path): " + "; ".join(offenders)
    )


def test_no_bare_local_imports_in_tests():
    offenders = _bare_import_offenders(_TESTS, _LOCAL_MODULES | {"api"})
    assert not offenders, (
        "Bare local imports found in tests/ (must use the canonical `src.` "
        "path — the conftest bare<->src aliasing hook is retired, so a bare "
        "import loads a duplicate module whose classes don't match the "
        "engine's): " + "; ".join(offenders)
    )


def test_no_src_dir_on_sys_path_in_tests():
    """No test file may put the src/ directory itself on sys.path.

    Doing so makes bare module names importable process-wide for the rest of
    the pytest run, silently masking bare-import regressions in every test
    that runs afterwards. Only the project root belongs on sys.path (the
    conftests handle that).
    """
    import re

    pattern = re.compile(r"sys\.path\.(insert|append)\(.*['\"]src['\"]")
    offenders = []
    for py in sorted(_TESTS.rglob("*.py")):
        if py.name == "test_no_bare_local_imports.py":
            continue
        for i, line in enumerate(py.read_text(encoding="utf-8").splitlines(), 1):
            if pattern.search(line):
                offenders.append(f"{py.relative_to(_ROOT)}:{i}")
    assert not offenders, (
        "Test files putting src/ on sys.path (masks bare-import regressions "
        "for the whole pytest run): " + "; ".join(offenders)
    )


def test_legacy_bare_modules_covers_all_src_modules():
    """functions.LEGACY_BARE_MODULES must not drift behind the src/ tree.

    Persisted data (map JSON __module__/__class_type__, legacy pickles) stores
    bare module names; canonical_module_name() only rewrites names in that
    frozenset. A new top-level module missing from it would silently fail to
    resolve when referenced by map or save data. ('api' is excluded — it never
    appears in persisted engine data.)
    """
    from src.functions import LEGACY_BARE_MODULES

    missing = _LOCAL_MODULES - {"api"} - LEGACY_BARE_MODULES
    assert not missing, (
        "Top-level src/ modules missing from functions.LEGACY_BARE_MODULES "
        f"(persisted bare-name references to them won't resolve): {sorted(missing)}"
    )
