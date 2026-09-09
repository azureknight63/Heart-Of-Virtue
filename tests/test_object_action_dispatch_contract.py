"""Contract test: every map-authored object keyword must resolve to a callable.

Object keywords are authored per *placement* in ``src/resources/maps/*.json``
(``props.keywords``, which the loader ``setattr``s straight onto the instance,
replacing whatever the class computed). The frontend renders one button per
keyword. Nothing validated those keywords against the class that had to
implement them, and ``GameService.interact_with_target`` dispatched them with a
bare ``getattr(target, action)`` — so an authored verb the class never
implemented raised ``AttributeError`` into the broad ``except``, which handed
the player the exception text:

    Error executing action: 'WallInscription' object has no attribute 'touch'

Issue #553. A census of the shipped maps found 31 such (placement, keyword)
rows across 8 distinct (class, keyword) pairs — ``WallInscription`` with
inspect/view/check/look/touch and ``Container`` with search/look/lift.

This test re-derives that population from the map JSON and the classes
themselves — there is no hand-written list of expected keywords, and the
derivation is asserted non-empty (and roughly the right size) so it cannot
silently stop matching and approve everything.

It mirrors ``interact_with_target``'s dispatch order, which is the thing under
contract:

  1. ``Passageway`` + ``session_data`` -> queues a transition event (no getattr)
  2. ``Container`` + a verb in ``Container.LOOK_INSIDE_VERBS`` -> ``open()``
  3. everything else -> ``resolve_interaction(target, action)``

Only step 3 is a real function call, so steps 1 and 2 are expressed here as the
same two engine facts the service branches on.
"""

import importlib
import inspect
import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.objects import Container, Passageway  # noqa: E402

_MAPS_DIR = _ROOT / "src" / "resources" / "maps"


class _StubTile:
    """Stand-in tile. Object constructors only ever store it."""

    def __init__(self):
        self.objects_here = []
        self.items_here = []
        self.npcs_here = []
        self.events_here = []


def _a_player():
    from src.player import Player

    return Player()


_PLAYER = None


def _player():
    global _PLAYER
    if _PLAYER is None:
        _PLAYER = _a_player()
    return _PLAYER


#: Classes that could only be built through the ``cls.__new__`` fallback.
#: Asserted empty below: a fallback instance is uninitialized, so its keywords
#: and its instance-bound aliases are missing and the contract would quietly
#: weaken for that class instead of failing.
_FALLBACK_CLASSES = set()


def _instantiate(cls):
    """Build an instance of ``cls`` the way the map loader does.

    ``Universe._deserialize_saved_instance`` filters authored props to the real
    constructor signature, injects ``player``/``tile`` when accepted, and falls
    back to ``cls.__new__`` + a bare ``__init__`` if construction raises. This
    mirrors that, because instance-level aliases matter: ``Passageway.__init__``
    binds each word of its own name to ``self.enter`` via ``setattr``.

    The fallback exists to mirror the loader, not to be used: every class in
    the shipped maps constructs normally today, and
    :func:`test_no_placement_needed_the_uninitialized_fallback` keeps it that
    way.
    """
    kwargs = {}
    try:
        params = inspect.signature(cls.__init__).parameters
    except (TypeError, ValueError):  # pragma: no cover - builtins only
        params = {}
    if "player" in params:
        kwargs["player"] = _player()
    if "tile" in params:
        kwargs["tile"] = _StubTile()
    try:
        return cls(**kwargs)
    except Exception:
        _FALLBACK_CLASSES.add(cls.__name__)
        instance = cls.__new__(cls)
        try:
            instance.__init__()
        except Exception:
            pass
        return instance


def _object_placements():
    """Every object placement in every shipped map.

    Yields ``(map_name, coord, cls, display_name, keywords)`` where
    ``keywords`` is the *effective* set: authored ``props.keywords`` replace the
    class-computed list, because the loader ``setattr``s every prop.
    """
    placements = []
    for path in sorted(_MAPS_DIR.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        for coord, tile_data in raw.items():
            if coord == "metadata" or not isinstance(tile_data, dict):
                continue
            for payload in tile_data.get("objects", []) or []:
                mod_name = payload.get("__module__")
                cls_name = payload.get("__class__")
                if not mod_name or not cls_name:
                    continue
                module = importlib.import_module(f"src.{mod_name}")
                cls = getattr(module, cls_name)
                props = payload.get("props") or {}
                instance = _instantiate(cls)
                if "keywords" in props:
                    keywords = list(props["keywords"] or [])
                else:
                    keywords = list(getattr(instance, "keywords", []) or [])
                placements.append((
                    path.name,
                    coord,
                    cls,
                    props.get("name") or cls_name,
                    keywords,
                    instance,
                ))
    return placements


_PLACEMENTS = _object_placements()


def _authored_pairs():
    """Flatten to one row per (placement, keyword)."""
    return [
        (map_name, coord, cls, name, keyword, instance)
        for map_name, coord, cls, name, keywords, instance in _PLACEMENTS
        for keyword in keywords
    ]


_PAIRS = _authored_pairs()


def _is_dispatchable(cls, instance, keyword):
    """Mirror of interact_with_target's dispatch order. See module docstring.

    The two engine names this reads are imported lazily so that reverting the
    fix produces the contract's own assertion failure (which names the offending
    pairs) rather than a collection error.
    """
    from src.objects import resolve_interaction

    if issubclass(cls, Passageway):
        return True
    look_inside = getattr(Container, "LOOK_INSIDE_VERBS", frozenset())
    if issubclass(cls, Container) and keyword in look_inside:
        return True
    return resolve_interaction(instance, keyword) is not None


def test_every_delegated_crossing_verb_is_a_crossing_handler():
    """``__init__``'s aliases and ``CROSSING_METHOD_NAMES`` name one set.

    ``go``/``leave``/``exit`` DELEGATE to ``enter`` rather than aliasing it,
    so ``is_crossing_handler`` cannot answer for them by identity against
    ``enter`` -- it consults ``CROSSING_METHOD_NAMES``. Both that tuple and
    the alias registration derive from ``_DELEGATED_CROSSING_VERBS``, and this
    is the guard that they still do: a fourth delegator added as a method and
    an alias but left out of the set re-opens #552, with a demo-end passageway
    crossable by a verb the API's gate answers False for.

    Derived from the class attribute, never a hand-kept list -- a list here
    would go stale in exactly the way it is meant to catch.
    """
    passage = Passageway(
        player=None,
        tile=None,
        name="Ferry Landing",
        teleport_map="somewhere",
        teleport_tile=(1, 1),
    )

    for verb in Passageway._DELEGATED_CROSSING_VERBS:
        assert verb in passage.action_aliases, (
            f"{verb!r} delegates to enter but __init__ never registered it "
            "as an alias, so the client is offered no button for it"
        )
        assert verb in Passageway.CROSSING_METHOD_NAMES, (
            f"{verb!r} crosses the passageway but is_crossing_handler does "
            "not count it -- a demo-end passageway is crossable by it"
        )
        handler = getattr(passage, verb, None)
        assert callable(handler), f"{verb!r} names no method on Passageway"
        assert passage.is_crossing_handler(handler), (
            f"is_crossing_handler answers False for {verb!r}"
        )

    # `enter` itself, and the instance-bound authored name words that are set
    # to `enter` directly, must answer through that entry.
    assert passage.is_crossing_handler(passage.enter)
    assert passage.is_crossing_handler(passage.ferry)

    # Negative control: a verb that does not cross must not be counted, or the
    # assertions above would pass for a predicate that returns True always.
    assert not passage.is_crossing_handler(passage.build_article_phrase)
    assert not passage.is_crossing_handler(None)


# ---------------------------------------------------------------------------
# Derivation guards — without these the contract below is fail-open.
# ---------------------------------------------------------------------------


def test_the_map_scan_found_a_real_population():
    assert len(_PLACEMENTS) > 100, (
        f"only {len(_PLACEMENTS)} object placements found — the map scan broke "
        "and the contract test below would pass vacuously"
    )
    assert len(_PAIRS) > 300, (
        f"only {len(_PAIRS)} (placement, keyword) rows found — see above"
    )


def test_the_scan_covers_the_classes_the_bug_was_reported_against():
    """#553 was reported on WallInscription and reproduced on Container."""
    from src.objects import WallInscription

    classes = {cls for _m, _c, cls, _n, _k, _i in _PLACEMENTS}
    assert WallInscription in classes
    assert any(issubclass(c, Container) for c in classes)
    assert any(issubclass(c, Passageway) for c in classes)


def test_no_placement_needed_the_uninitialized_fallback():
    """Every shipped class must construct for real.

    ``_instantiate``'s ``cls.__new__`` fallback mirrors the map loader, but an
    instance built that way has no keywords and none of its instance-bound
    aliases, so the contract below would silently stop testing anything for
    that class rather than failing. All 122 shipped placements construct
    normally today; if that changes, fix the construction, don't accept the
    fallback.
    """
    assert not _FALLBACK_CLASSES, (
        "these classes could only be built uninitialized, so the keyword "
        f"contract does not really cover them: {sorted(_FALLBACK_CLASSES)}"
    )


def test_the_reported_placement_is_in_the_scan():
    """grondia (8,4) 'Carved Lintel' with the `touch` keyword — the repro."""
    hits = [
        row for row in _PAIRS
        if row[0] == "grondia.json" and row[1] == "(8, 4)"
        and row[3] == "Carved Lintel" and row[4] == "touch"
    ]
    assert len(hits) == 1, (
        "the exact placement issue #553 was filed against is no longer in the "
        "scan — if it was renamed or removed, update this anchor deliberately"
    )


# ---------------------------------------------------------------------------
# The contract
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "map_name,coord,cls,name,keyword,instance",
    [
        pytest.param(m, c, cls, n, k, i, id=f"{m}:{c}:{n}:{k}")
        for m, c, cls, n, k, i in _PAIRS
    ],
)
def test_every_authored_keyword_is_dispatchable(
    map_name, coord, cls, name, keyword, instance
):
    # The instance travels with the row rather than being looked back up by
    # its other four fields: two placements sharing class+name+keyword on one
    # tile would otherwise both test whichever one came first.
    assert _is_dispatchable(cls, instance, keyword), (
        f"{map_name} {coord} {name!r} ({cls.__name__}) authors the keyword "
        f"{keyword!r}, which resolves to nothing callable. The frontend renders "
        f"a button for it and clicking it used to hand the player an "
        f"AttributeError (issue #553). Either implement it, add it to the "
        f"class's KEYWORD_METHOD_ALIASES, or remove the keyword from the map."
    )


def test_every_default_container_button_is_a_look_inside_verb():
    """``Container.action_aliases`` and ``LOOK_INSIDE_VERBS`` must agree.

    ``action_aliases`` answers "which buttons does a container show by
    default" and goes straight into ``keywords``; ``LOOK_INSIDE_VERBS``
    answers "which verbs open it". They overlap completely today, but by
    coincidence rather than by construction — so an alias added to one and not
    the other would ship a default button with no dispatch behind it, which is
    #553 all over again on a container nobody had to author.
    """
    container = Container()
    defaults = set(container.action_aliases)
    assert defaults, "Container stopped declaring default action aliases"
    assert defaults <= Container.LOOK_INSIDE_VERBS, (
        "default container buttons that no longer open the container: "
        f"{sorted(defaults - Container.LOOK_INSIDE_VERBS)}"
    )


def test_no_authored_keyword_anywhere_is_undispatchable():
    """The same contract as one aggregate assertion, for a readable failure."""
    broken = sorted({
        (cls.__name__, keyword)
        for _m, _c, cls, _n, keyword, instance in _PAIRS
        if not _is_dispatchable(cls, instance, keyword)
    })
    assert not broken, f"undispatchable authored (class, keyword) pairs: {broken}"
