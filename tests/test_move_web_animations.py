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

    The constants live in ``src/api/schemas/combat_beat.py`` (the wire-protocol
    home) so both the adapter and the beat streamer share one definition.
    """
    from src.api.schemas.combat_beat import (
        DEFAULT_ANIMATION,
        DEFAULT_DAMAGE_ANIMATION,
    )

    frontend_types = _frontend_animation_types()
    for substituted in (DEFAULT_ANIMATION, DEFAULT_DAMAGE_ANIMATION):
        assert substituted in frontend_types, (
            f"{substituted!r} is not a key of ANIMATION_CONFIGS"
        )


def _type_literal_offenders(source):
    """Adapter-chosen animation-type literals hardcoded in ``source``.

    Two shapes: an ``animation_type = "x"`` assignment (name or attribute
    target, any quote style), and a string-literal ``"type"`` value inside any
    dict literal that ALSO carries a ``"source_id"`` key — which animation
    payloads carry and log entries (whose own ``"type": "combat"`` literal is
    legitimate) do not. AST-based, so key ORDER and formatting cannot dodge
    it: the first regex version required ``"source_id"`` to sit immediately
    after ``"type"``, so a payload spelled with the keys reordered, or with
    another key between them, sailed straight past — the enumeration-shaped
    guard failure this codebase keeps rediscovering. (An earlier version
    still matched only double-quoted assignments, missing exactly how
    ``_npc_try_heal_ally`` hardcoded ``"pulse"``.)
    """
    import ast

    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                name = (
                    target.id
                    if isinstance(target, ast.Name)
                    else getattr(target, "attr", None)
                )
                if (
                    name == "animation_type"
                    and isinstance(node.value, ast.Constant)
                    and isinstance(node.value.value, str)
                ):
                    found.append(node.value.value)
        elif isinstance(node, ast.Dict):
            keys = {
                key.value
                for key in node.keys
                if isinstance(key, ast.Constant)
            }
            if "type" not in keys or "source_id" not in keys:
                continue
            for key, value in zip(node.keys, node.values):
                if (
                    isinstance(key, ast.Constant)
                    and key.value == "type"
                    and isinstance(value, ast.Constant)
                    and isinstance(value.value, str)
                ):
                    found.append(value.value)
    return found


_API_FILES = (
    _ROOT / "src" / "api" / "combat_adapter.py",
    _ROOT / "src" / "api" / "combat_beat_stream.py",
)


def test_the_adapter_substitutes_no_type_this_test_does_not_know_about():
    """A structural backstop for the test above.

    The behavioural contract can only check the constants it imports, so a new
    hardcoded animation-type literal in the adapter would slip past it. Pin the
    fallbacks to named constants instead: this fails if a string literal is
    ever assigned to ``animation_type`` (either quote style) or hardcoded as a
    ``"type"`` value in an animation payload again. Paths are repo-rooted, not
    cwd-relative — a cwd-relative read silently scans nothing when pytest runs
    from another directory.
    """
    offenders = {}
    for path in _API_FILES:
        found = _type_literal_offenders(path.read_text(encoding="utf-8"))
        if found:
            offenders[path.name] = found
    assert not offenders, (
        "these hardcoded animation types bypass the frontend contract "
        f"check above; give them a module constant instead: {offenders}"
    )


def test_the_type_literal_scan_can_actually_find_something():
    """Positive control: every known offender spelling must match the scan."""
    known_spellings = [
        'animation_type = "attack"',
        "animation_type = 'pulse'",
        'self.animation_type = "sweep"',
        'x = {"type": "pulse",\n     "source_id": s}',
        "x = {'type': 'attack', 'source_id': s}",
        # Key order must not matter...
        'x = {"source_id": s, "type": "pulse"}',
        # ...and neither may keys sitting between the two.
        'x = {"type": "pulse", "move_name": n, "source_id": s}',
    ]
    for spelling in known_spellings:
        assert _type_literal_offenders(spelling), (
            f"the scan no longer matches a known shape: {spelling}"
        )
    # ...and it does not fire on a constant-backed assignment, a payload built
    # from a variable, or a log ENTRY's legitimate "type": "combat" literal
    # (log entries carry no "source_id" key).
    assert not _type_literal_offenders("animation_type = DEFAULT_ANIMATION")
    assert not _type_literal_offenders(
        'x = {"type": animation_type,\n     "source_id": s}'
    )
    assert not _type_literal_offenders('x = {"type": "combat", "timestamp": now}')
