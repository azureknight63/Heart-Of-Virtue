"""Classify bug reports as fix_agent (auto-fix) or escalate (ping user)."""

from .reporter import BugReport, BugSeverity, BugCategory

# Game-engine module paths — if these appear in a traceback, the bug lives in
# engine code and should be escalated rather than auto-fixed.
_ENGINE_PATHS = {
    "src/combat.py", "src/combatant.py", "src/moves.py",
    "src/states.py", "src/player.py", "src/npc.py",
    "src/universe.py", "src/game.py",
    "src\\combat.py", "src\\combatant.py", "src\\moves.py",
    "src\\states.py", "src\\player.py", "src\\npc.py",
    "src\\universe.py", "src\\game.py",
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
        for path in _ENGINE_PATHS:
            if path in report.traceback:
                return "escalate"

    # Everything else (serialization, missing field, auth, shape) is API-layer.
    return "fix_agent"
