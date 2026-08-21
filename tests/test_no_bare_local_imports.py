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
import functools
import re
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


# A file can only contain a bare local import if its raw text mentions the
# module name in the module position of an `import`/`from` statement, or
# performs a dynamic import. Anything else cannot produce an offending AST
# node, so it is skipped without paying for ast.parse — which dominates this
# test's runtime (~3.3s of parsing across src/ + tests/ collapses to ~0.25s).
# The filter is deliberately over-inclusive (it also matches inside strings and
# comments); the AST pass below is still the sole arbiter of what counts as an
# offense.
#
# It must never be *under*-inclusive, or an offense is skipped and the guard
# silently stops guarding. The previous pattern, `(?:import|from)\s+(\w+)`,
# captured only the FIRST name after the keyword, so a comma-separated
# `import os, items` was filtered out and never reached the AST pass — a real
# bare import the guard would have passed clean. `names` therefore captures the
# whole comma-separated tail, and each entry is reduced to its first
# dotted component (so `import src.items as items` still reads as `src`).
_IMPORT_RE = re.compile(
    r"(?<![\w.])(?:from[ \t]+(?P<mod>[\w.]+)|import[ \t]+(?P<names>[\w.,\t ]+))"
)
_DYNAMIC_IMPORT_TOKENS = ("import_module", "__import__")

_SRC_LITERAL_RE = re.compile(r"""(?<![\w.])['"]src['"]""")


def _names_tainted_by_a_src_literal(tree):
    """Names bound to an expression that mentions the string literal 'src'.

    e.g. ``_SRC_DIR = os.path.join(_PROJECT_ROOT, 'src')`` taints ``_SRC_DIR``.
    Loop variables inherit the taint from the iterable they walk, which is how
    ``for p in (_ROOT, _SRC_DIR): sys.path.insert(0, p)`` is caught.
    """
    tainted = set()
    # Two passes so a taint introduced later in the file still propagates to an
    # earlier loop (import preambles are short; correctness beats one pass).
    for _ in range(2):
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                if _SRC_LITERAL_RE.search(ast.unparse(node.value)) or any(
                    isinstance(n, ast.Name) and n.id in tainted
                    for n in ast.walk(node.value)
                ):
                    for target in node.targets:
                        for name in ast.walk(target):
                            if isinstance(name, ast.Name):
                                tainted.add(name.id)
            elif isinstance(node, ast.For):
                if _SRC_LITERAL_RE.search(ast.unparse(node.iter)) or any(
                    isinstance(n, ast.Name) and n.id in tainted
                    for n in ast.walk(node.iter)
                ):
                    for name in ast.walk(node.target):
                        if isinstance(name, ast.Name):
                            tainted.add(name.id)
    return tainted


# A file can only push the src directory if it mutates sys.path at all; the
# textual pre-check keeps the AST pass off the ~85% of test files that don't.
_SYS_PATH_MUTATION_RE = re.compile(r"sys\.path\.(?:insert|append)\s*\(")


@functools.lru_cache(maxsize=None)
def _sys_path_src_offenses(text):
    """Line numbers of ``sys.path.insert/append`` calls pushing the src dir."""
    # Both offense forms ultimately originate from a literal 'src' somewhere in
    # the file (directly in the call, or in the expression a pushed variable was
    # built from), so a file with neither marker cannot offend.
    if not _SYS_PATH_MUTATION_RE.search(text) or not _SRC_LITERAL_RE.search(text):
        return ()
    try:
        tree = ast.parse(text)
    except SyntaxError:  # pragma: no cover - defensive
        return ()
    tainted = _names_tainted_by_a_src_literal(tree)
    offenses = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in ("insert", "append")
            and ast.unparse(node.func.value).endswith("sys.path")
        ):
            continue
        args_src = " ".join(ast.unparse(a) for a in node.args)
        referenced = {
            n.id for a in node.args for n in ast.walk(a) if isinstance(n, ast.Name)
        }
        if _SRC_LITERAL_RE.search(args_src) or (referenced & tainted):
            offenses.append(node.lineno)
    return tuple(offenses)


@functools.lru_cache(maxsize=None)
def _source_files(root):
    """(path, text) for every .py under `root`, read once per session."""
    out = []
    for py in sorted(root.rglob("*.py")):
        try:
            out.append((py, py.read_text(encoding="utf-8")))
        except UnicodeDecodeError:  # pragma: no cover - defensive
            continue
    return tuple(out)


def _imported_roots(text):
    """Every top-level module name appearing in an import statement's module
    position — over-inclusive by design (strings and comments included)."""
    for match in _IMPORT_RE.finditer(text):
        module = match.group("mod")
        if module:
            yield module.split(".", 1)[0]
            continue
        for part in match.group("names").split(","):
            part = part.strip()
            if part:
                yield part.split()[0].split(".", 1)[0]


def _might_import(text, modules):
    if any(token in text for token in _DYNAMIC_IMPORT_TOKENS):
        return True
    return any(root in modules for root in _imported_roots(text))


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
    for py, text in _source_files(root):
        if not _might_import(text, modules):
            continue
        try:
            tree = ast.parse(text, filename=str(py))
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

    Checked over the AST rather than line-by-line: the previous single-line
    regex only fired when the literal "src" appeared in the same statement as
    the sys.path call, so tests/test_refresh_stat_bonuses.py's
    ``_SRC_DIR = os.path.join(_PROJECT_ROOT, 'src')`` /
    ``for _p in (_PROJECT_ROOT, _SRC_DIR): sys.path.insert(0, _p)`` preamble
    sat unnoticed. Taint now follows the variable.
    """
    offenders = []
    for py, text in _source_files(_TESTS):
        if py.name == "test_no_bare_local_imports.py":
            continue
        if "sys.path" not in text:
            continue
        for lineno in _sys_path_src_offenses(text):
            offenders.append(f"{py.relative_to(_ROOT)}:{lineno}")
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
