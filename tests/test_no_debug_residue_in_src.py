"""Guard: no mutation probe or debug stub may be left behind in engine code.

Verifying that a test can actually *fail* means temporarily breaking the code it
covers -- making a method a no-op, forcing a branch, stubbing a return -- then
confirming the test goes red and restoring. That is the right technique, and
this project's workflow leans on it heavily.

The hazard is the restore step. A probe left in `src/` does not announce itself:
the suite stays green (the tests were passing before the probe and pass again
once it silently disables the thing they no longer really exercise), so the only
signal is a reviewer noticing a stray line in the diff. During one such session a
`return  # MUTANT` sat live in `src/player/__init__.py` for several minutes while
other work was being committed around it. Shipping that would have disabled real
engine behaviour with a fully green suite reporting success.

`###DEBUG###` is included because CLAUDE.md's conventions already say debug
statements carry that marker and must not be left in.

This is deliberately a plain substring scan over engine source. It is cheap,
it cannot itself be defeated by a subtle bug, and the failure message names the
file and line so the fix is obvious.
"""

import pathlib

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
SCANNED_DIRS = ("src", "ai")

# Markers that should never survive into committed engine code. Kept literal and
# short: this is a smoke alarm, not a linter.
FORBIDDEN_MARKERS = (
    "MUTANT",
    "###DEBUG###",
    "REMOVE BEFORE COMMIT",
    "DO NOT COMMIT",
)


def _python_sources():
    for directory in SCANNED_DIRS:
        root = REPO_ROOT / directory
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            yield path


def test_engine_source_carries_no_mutation_or_debug_markers():
    """No `src/` or `ai/` file contains a leftover probe marker."""
    offences = []
    for path in _python_sources():
        try:
            text = path.read_text(encoding="utf8", errors="ignore")
        except OSError:  # pragma: no cover - unreadable file is a different problem
            continue
        if not any(marker in text for marker in FORBIDDEN_MARKERS):
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            for marker in FORBIDDEN_MARKERS:
                if marker in line:
                    rel = path.relative_to(REPO_ROOT)
                    offences.append(f"  {rel}:{lineno}: {line.strip()[:100]}")

    assert not offences, (
        "Debug/mutation residue found in engine source. A probe left behind "
        "disables real behaviour while the suite still reports green:\n"
        + "\n".join(offences)
    )


def test_the_scan_actually_reaches_engine_source():
    """A scanner that silently reads nothing would pass forever.

    Pins that the walk finds a substantial number of real engine modules, so a
    broken path or an over-eager exclusion turns this red instead of quietly
    making the guard above vacuous.
    """
    sources = list(_python_sources())
    assert len(sources) > 50, f"only found {len(sources)} engine sources"
    names = {p.name for p in sources}
    assert "player.py" in names or "__init__.py" in names
    assert any(p.parts[-2] == "moves" for p in sources), "src/moves not scanned"


@pytest.mark.parametrize("marker", FORBIDDEN_MARKERS)
def test_every_marker_would_be_caught(marker, tmp_path):
    """Each configured marker is genuinely detected, not just listed."""
    probe = tmp_path / "probe.py"
    probe.write_text(f"def f():\n    return  # {marker}\n", encoding="utf8")
    text = probe.read_text(encoding="utf8")
    assert any(m in text for m in FORBIDDEN_MARKERS)
