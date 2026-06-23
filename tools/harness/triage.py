"""Classify bug reports as fix_agent (auto-fix) or escalate (ping user)."""

from .reporter import BugReport, BugSeverity, BugCategory

# Game-engine module paths — if these appear in a traceback, the bug lives in
# engine code and should be escalated rather than auto-fixed.
# Path *fragments* — matched as substrings against traceback frames so that both
# the old single-module layout and the current package layout are covered (e.g.
# moves.py was split into src/moves/_*.py, player.py into src/player/_*.py, etc.).
# Stored with forward slashes; the traceback's backslashes are normalized before
# matching (see classify), so Windows frames like src\moves\_sword.py match too.
_ENGINE_PATHS = {
    "src/combatant.py", "src/combat_adapter.py",
    "src/moves", "src/states.py", "src/player",
    "src/npc", "src/universe.py", "src/items.py",
}


def classify(report: BugReport) -> str:
    """Return 'fix_agent' or 'escalate'.

    fix_agent  — isolated API-layer issue; safe to auto-fix.
    escalate   — engine logic, architectural, or critical; needs human sign-off.
    """
    if report.severity == BugSeverity.CRITICAL:
        return "escalate"

    if report.category == BugCategory.LOGIC:
        return "escalate"

    # If the traceback traces through engine internals, escalate.
    if report.traceback:
        normalized_tb = report.traceback.replace("\\", "/")
        for path in _ENGINE_PATHS:
            if path in normalized_tb:
                return "escalate"

    # Everything else (serialization, missing field, auth, shape) is API-layer.
    return "fix_agent"
