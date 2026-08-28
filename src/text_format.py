"""Rendering helpers for numbers that appear in both engine prose and prompts.

Deliberately dependency-free — standard library only, no imports from ``src.``
or ``ai.`` — following the ``src/env_bootstrap.py`` and ``src/text_safety.py``
precedent. ``src/states.py`` must be importable without dragging in the
provider stack and ``ai/combat_strategist.py`` must be importable without
dragging in the game engine, so a rule the two share can only live somewhere
that depends on neither.

``pct`` used to be spelled three times as a private ``_pct``: byte-identically
in each of those two modules, and a third time in ``ai/provider_digest.py`` as
``"%.0f%%"`` — a different spelling of the same arithmetic, which is worse than
a duplicate because it looks like a decision. The whole point of every copy is
that a threshold and the prose quoting it cannot disagree, and copies of the
renderer are one rounding-mode change away from the drift they exist to
prevent. All three now call this.
"""


def pct(fraction: float) -> str:
    """Render a 0-1 fraction as the integer percentage prose quotes.

    ``0.25`` -> ``"25%"``. Rounds half away from zero rather than truncating,
    so a threshold written as ``0.075`` reads as ``8%`` and not ``7%``.
    """
    return f"{int(round(fraction * 100))}%"
