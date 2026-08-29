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


def _move_classes_defined_in_submodules():
    """Every Move subclass actually defined under src/moves/, keyed by name.

    Walks the submodules directly rather than trusting ``moves.__all__`` — the
    point of the next test is to catch a class that never made it into that
    list, which every other check in this file would then skip silently.
    """
    import importlib

    found = {}
    for path in sorted((_ROOT / "src" / "moves").glob("_*.py")):
        module = importlib.import_module(f"src.moves.{path.stem}")
        for name, obj in vars(module).items():
            if (
                inspect.isclass(obj)
                and issubclass(obj, Move)
                and obj.__module__ == module.__name__
            ):
                found[name] = obj
    return found


def test_every_move_class_is_reexported_from_the_package():
    """``src/moves/__init__.py`` must re-export every move class.

    A class missing from ``__all__`` is invisible to both contract tests in this
    file *and* to any caller doing ``moves.X`` — it would silently ship without
    a web_animation and without a UI button. The package's whole compatibility
    promise (CLAUDE.md: "callers use `import moves` unchanged") rests on this.
    """
    defined = _move_classes_defined_in_submodules()
    assert defined, "no move classes found — the submodule walk is broken"

    unexported = sorted(set(defined) - set(moves.__all__))
    assert not unexported, f"move classes missing from moves.__all__: {unexported}"

    # ...and nothing in __all__ dangles.
    dangling = [name for name in moves.__all__ if not hasattr(moves, name)]
    assert not dangling, f"moves.__all__ names nothing resolves to: {dangling}"

    # The re-export is the same object, not a stale duplicate class (which
    # would break isinstance across the API/engine boundary — CLAUDE.md).
    for name, cls in defined.items():
        assert getattr(moves, name) is cls, f"{name} re-exported as a different object"


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
        display_name = "Probe"

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


def test_adapter_substituted_animation_types_exist_in_the_frontend():
    """Types the API layer picks itself must be real configs too.

    The contract above only covers types declared on move classes. The adapter
    also chooses a type of its own whenever a move declares none — the
    damaging-move and the generic fallbacks — and an unknown type there fails
    the way every wire-name drift in this codebase fails: silently. The client
    falls back to ``pulse``, so the move would flash nothing recognisable and
    nobody would see an error.

    This used to pin ``FOLLOW_UP_IMPACT_ANIMATION``, the short flash the adapter
    substituted for every resolution after the first of a multi-target swing.
    That downgrade is gone (every target now plays the move in full, layered
    client-side), so the constant is gone with it and the two remaining
    adapter-chosen types are what this guards.
    """
    from src.api.combat_adapter import (
        DEFAULT_ANIMATION,
        DEFAULT_DAMAGE_ANIMATION,
    )

    frontend_types = _frontend_animation_types()
    for substituted in (DEFAULT_ANIMATION, DEFAULT_DAMAGE_ANIMATION):
        assert substituted in frontend_types, (
            f"{substituted!r} is not a key of ANIMATION_CONFIGS"
        )


def test_the_adapter_substitutes_no_type_this_test_does_not_know_about():
    """A structural backstop for the test above.

    The behavioural contract can only check the constants it imports, so a new
    hardcoded animation-type literal in the adapter would slip past it. Pin the
    fallbacks to named constants instead: this fails if a bare string literal is
    ever assigned to ``animation_type`` again.
    """
    import pathlib
    import re

    source = pathlib.Path("src/api/combat_adapter.py").read_text(encoding="utf-8")
    literals = re.findall(r'animation_type = "(\w+)"', source)
    assert not literals, (
        "these adapter-chosen animation types bypass the frontend contract "
        f"check above; give them a module constant instead: {literals}"
    )
