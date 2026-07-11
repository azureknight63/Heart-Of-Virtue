"""Static guard: every local import in src/ uses the canonical `src.` path.

Generalizes tests/test_narration_import_consistency.py to all local engine
modules. Bare imports (`import items`, `from functions import ...`) resolve to
a SEPARATE module object from `src.items` / `src.functions` whenever src/ is
on sys.path, splitting classes and module-level state across the API/engine
boundary (see issue #271). With src/import_sync.py retired, nothing collapses
that split at runtime any more — this static check is the guard.

AST-based so docstrings and comments can't false-positive.
"""

import ast
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1] / "src"

# Top-level local module/package names under src/ that must only be imported
# via the `src.` prefix (or a relative import inside their own package).
_LOCAL_MODULES = frozenset(
    p.stem if p.is_file() else p.name
    for p in _SRC.iterdir()
    if (p.suffix == ".py" and p.stem != "__init__")
    or (p.is_dir() and (p / "__init__.py").exists())
)


def test_no_bare_local_imports_in_src():
    offenders = []
    for py in sorted(_SRC.rglob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        rel = py.relative_to(_SRC.parent)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".", 1)[0] in _LOCAL_MODULES:
                        offenders.append(f"{rel}:{node.lineno} import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if (
                    node.level == 0
                    and node.module
                    and node.module.split(".", 1)[0] in _LOCAL_MODULES
                ):
                    offenders.append(f"{rel}:{node.lineno} from {node.module} import ...")
    assert not offenders, (
        "Bare local imports found in src/ (must use the canonical `src.` path — "
        "bare imports create duplicate module objects with separate classes and "
        "state whenever src/ is on sys.path): " + "; ".join(offenders)
    )
