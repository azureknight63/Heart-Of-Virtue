"""Guard against the split narration-module-buffer regression.

The narration sink uses a context-local buffer (`narration._buffer`). In
production `wsgi.py` puts both the project root and `src/` on `sys.path`, so
`import narration` and `import src.narration` resolve to TWO separate module
objects with TWO separate buffers. If an emitter (e.g. objects.py chest
`open()`) and the capturer (GameService) import from different paths, the
captured buffer is empty and the interaction falls back to the generic
"Jean successfully completes the '<action>' action." message — the chest stops
showing its contents.

The test conftest aliases bare<->src modules, so this bug is INVISIBLE to
ordinary tests and only bites in production. This static check is therefore the
reliable guard: every `src/` module must import the narration sink from the
canonical `src.narration` path.
"""

from pathlib import Path

import re

_SRC = Path(__file__).resolve().parents[1] / "src"
# Matches a bare top-level narration import, e.g. "from narration import x"
# or "import narration", but NOT "from src.narration import x".
_BARE_FROM = re.compile(r"^\s*from\s+narration\s+import\b", re.MULTILINE)
_BARE_IMPORT = re.compile(r"^\s*import\s+narration\b", re.MULTILINE)


def test_no_bare_narration_imports_in_src():
    offenders = []
    for py in _SRC.rglob("*.py"):
        text = py.read_text(encoding="utf-8", errors="ignore")
        if _BARE_FROM.search(text) or _BARE_IMPORT.search(text):
            offenders.append(str(py.relative_to(_SRC.parent)))
    assert not offenders, (
        "Bare `narration` imports found (must use `src.narration` — bare imports "
        "create a separate module buffer in production, breaking narration "
        f"capture): {offenders}"
    )
