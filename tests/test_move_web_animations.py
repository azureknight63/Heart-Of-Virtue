"""Contract test: backend move animations ↔ frontend animation configs.

Every castable (non-passive) move class must declare a `web_animation` class
attribute, and every declared value must be a key of ANIMATION_CONFIGS in
frontend/src/utils/animationConfigs.js — otherwise the client would silently
fall back to the generic pulse animation.
"""

import inspect
import pathlib
import re
import sys

_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src import moves
from src.moves import Move, PassiveMove

_CONFIG_JS = _ROOT / "frontend" / "src" / "utils" / "animationConfigs.js"


def _frontend_animation_types():
    """Parse the top-level keys of ANIMATION_CONFIGS out of the JS module."""
    source = _CONFIG_JS.read_text(encoding="utf-8")
    match = re.search(
        r"export const ANIMATION_CONFIGS = \{(.*)\n\};", source, re.DOTALL
    )
    assert match, "ANIMATION_CONFIGS block not found in animationConfigs.js"
    body = match.group(1)
    # Top-level keys sit at exactly two spaces of indentation: "  attack: {"
    return set(re.findall(r"^  (\w+): \{", body, re.MULTILINE))


def _castable_move_classes():
    for name in moves.__all__:
        obj = getattr(moves, name)
        if not (inspect.isclass(obj) and issubclass(obj, Move)):
            continue
        if obj in (Move, PassiveMove) or issubclass(obj, PassiveMove):
            continue
        yield name, obj


def test_frontend_types_parsed():
    types = _frontend_animation_types()
    # Sanity floor: the taxonomy is at least the core set
    assert {"attack", "pulse", "death", "projectile", "dash"} <= types


def test_every_castable_move_declares_web_animation():
    missing = [
        name for name, cls in _castable_move_classes() if cls.web_animation is None
    ]
    assert not missing, f"moves without web_animation: {missing}"


def test_declared_animations_exist_in_frontend_configs():
    known = _frontend_animation_types()
    unknown = {
        name: cls.web_animation
        for name, cls in _castable_move_classes()
        if cls.web_animation is not None and cls.web_animation not in known
    }
    assert not unknown, (
        f"moves declaring animation types missing from animationConfigs.js: {unknown}"
    )


def test_instances_resolve_class_attribute():
    """The adapter reads web_animation off instances via getattr — the class
    attribute must be visible there without any __init__ plumbing."""

    class _Probe(Move):
        web_animation = "pierce"

    probe = _Probe(
        name="probe",
        description="",
        xp_gain=0,
        current_stage=0,
        beats_left=0,
        stage_announce=["", "", "", ""],
        target=None,
        user=None,
        stage_beat=[0, 0, 0, 0],
        targeted=False,
    )
    assert probe.web_animation == "pierce"
    assert getattr(Move, "web_animation", "missing") is None
