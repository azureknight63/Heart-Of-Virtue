"""Rendering helpers for numbers that appear in both engine prose and prompts.

Deliberately dependency-free — standard library only, no imports from ``src.``
or ``ai.`` — following the ``src/env_bootstrap.py`` and ``src/text_safety.py``
precedent. ``src/states.py`` must be importable without dragging in the
provider stack and ``ai/combat_strategist.py`` must be importable without
dragging in the game engine, so a rule the two share can only live somewhere
that depends on neither.

``pct`` used to be spelled twice, byte-identically, as a private ``_pct`` in
each of those modules — and the whole point of both copies is that a threshold
and the prose quoting it cannot disagree. Two copies of the renderer is one
rounding-mode change away from the drift they exist to prevent.
"""


def pct(fraction: float) -> str:
    """Render a 0-1 fraction as the integer percentage prose quotes.

    ``0.25`` -> ``"25%"``. Rounds half away from zero rather than truncating,
    so a threshold written as ``0.075`` reads as ``8%`` and not ``7%``.
    """
    return f"{int(round(fraction * 100))}%"
