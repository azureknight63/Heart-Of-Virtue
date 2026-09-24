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

It mirrors ``_dispatch_interaction``'s arm order, which is the thing under
contract. In code order:

  1. ``Container`` + a verb in ``Container.LOOK_INSIDE_VERBS`` -> ``open()``
  2. a verb in ``_CONTAINER_ITEM_VERBS`` on a container's item -> transfer
  3. a demo-end ``Passageway`` + a CROSSING verb -> ends the demo
  4. any OTHER ``Passageway`` + ``session_data`` + a verb that CROSSES
     (``enter``, its delegators, the name words, the placement's declared
     ``crossing_keywords``) -> queues a transition event
  5. everything else -> ``resolve_interaction(target, action)``

Only arm 5 is a real attribute lookup, so the others are expressed here as the
engine facts the service branches on. Arm 3 is why a demo-end passageway is
NOT waved through below: a non-crossing verb on it falls all the way to arm 5
and is refused in fiction, so approving every ``Passageway`` unconditionally
would make this guard fail open for exactly the object this branch made
special (``tests/test_ferry_demo_end.py`` pins that behaviour).

Arm 4's verb test is issue #620, and the mirror below used to be missing it
in the same way: it returned True for EVERY non-demo-end ``Passageway``,
which was accurate while arm 4 keyed off the target's type alone and fails
open now that it does not. #630 then dropped arm 4's "or the placement
advertises it" half: a crossing verb is declared (``crossing_keywords``), so
the mirror has to build each placement WITH its authored list props, or the
three placements that declare one would read as undispatchable here.
"""

import functools
import inspect
import re
import sys
from pathlib import Path
from typing import NamedTuple

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src import map_placeholders  # noqa: E402
from src.objects import Container, Passageway, resolve_interaction  # noqa: E402
from tests._js_scan import FRONTEND_SRC  # noqa: E402
from tests._map_scan import (  # noqa: E402
    class_ref,
    map_data,
    object_placements,
    resolve_class,
    tiles,
)


class _StubTile:
    """Stand-in tile. Object constructors only ever store it."""

    def __init__(self):
        self.objects_here = []
        self.items_here = []
        self.npcs_here = []
        self.events_here = []


@functools.lru_cache(maxsize=1)
def _player():
    """One real Player for every constructor that wants one.

    Cached because building a Player mutates module-level item and merchant
    registries, so one per module is meaningfully cheaper and quieter than one
    per placement.
    """
    from src.player import Player

    return Player()


def _instantiate(cls, props=None):
    """Build an instance of ``cls`` the way the map loader does.

    ``Universe._deserialize_saved_instance`` filters authored props to the real
    constructor signature, injects ``player``/``tile`` when accepted, and falls
    back to ``cls.__new__`` + a bare ``__init__`` if construction raises. This
    mirrors that, because the authored name matters: a ``Passageway``'s name
    words resolve to ``enter`` (through ``instance_keyword_aliases``), so an
    instance built without its name advertises none of them.

    The authored props are filtered in here rather than dropped. They used to
    be: every instance was built with ``player``/``tile`` only, so a
    ``Passageway`` came back named "Passageway" and bound NONE of its
    placement's name words. Six shipped aliases (``ferry``, ``landing``,
    ``camp``, ``boundary``, ``tent``, ``jambo``) therefore resolved to nothing
    here while resolving fine in the game, and the mirror's old unconditional
    "every Passageway is dispatchable" hid it completely. Only the scalar
    props are passed: the loader deserializes nested payloads first, and this
    scan deliberately does not walk them. A list of strings a class declares
    authored is plain data too (``crossing_keywords``, #630) and is passed.

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
    authored_lists = map_placeholders.authored_param_names(cls)
    for key, value in (props or {}).items():
        if key not in params:
            continue
        if isinstance(value, (str, int, float, bool, type(None))) or (
            key in authored_lists
            and isinstance(value, list)
            and all(isinstance(v, str) for v in value)
        ):
            kwargs[key] = value
    if "player" in params:
        kwargs["player"] = _player()
    if "tile" in params:
        kwargs["tile"] = _StubTile()
    try:
        return cls(**kwargs), False
    except Exception:
        instance = cls.__new__(cls)
        try:
            instance.__init__()
        except Exception:
            pass
        return instance, True


def _object_placements():
    """Every object placement in every shipped map, instantiated.

    Returns ``(rows, fallback_classes)``. A row is
    ``(map_name, coord, cls, display_name, keywords, instance)`` where
    ``keywords`` is the *effective* set: authored ``props.keywords`` replace
    the class-computed list, because the loader ``setattr``s every prop.

    ``fallback_classes`` is returned rather than accumulated in a module
    global. It used to be one, written as a side effect of the scan and read by
    an assertion further down -- correct only because the scan happened to run
    exactly once at import, and silently stale the moment anyone moved it into
    a fixture.

    The map walk lives in :mod:`tests._map_scan`, shared by the guards over
    authored objects and events.
    """
    rows = []
    fallbacks = set()
    for placement in object_placements():
        cls = resolve_class(placement)
        props = placement.props
        instance, used_fallback = _instantiate(cls, props)
        if used_fallback:
            fallbacks.add(cls.__name__)
        if "keywords" in props:
            keywords = list(props["keywords"] or [])
        else:
            keywords = list(getattr(instance, "keywords", []) or [])
        # Put them back on the instance, which is what the loader's
        # ``setattr`` of the authored props does, so the mirror sees the
        # placement as the game does. (Arm 4 reads only whether a verb
        # crosses since #630; the three passageways whose crossing verb their
        # name does not contain declare it in ``crossing_keywords``.)
        instance.keywords = keywords
        rows.append((
            placement.map_name,
            placement.coord,
            cls,
            props.get("name") or placement.class_name,
            keywords,
            instance,
        ))
    return rows, fallbacks


_PLACEMENTS, _FALLBACK_CLASSES = _object_placements()


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

    Every branch below is DERIVED from the engine fact the matching arm keys
    off. The passageway branch used to be ``return True`` for every non-demo-end
    ``Passageway`` — true at the time, because arm 4 keyed off the target's
    TYPE and never looked at the verb, but a mirror that asserts nothing about
    the verb fails open the moment the arm starts asking about one. Issue #620
    made it ask, and the question now lives in the engine
    (``Passageway.accepts_step_through``), so this calls it rather than
    retyping it -- the retyped copy is what failed open.
    """
    from src.objects import resolve_interaction

    handler = resolve_interaction(instance, keyword)

    look_inside = getattr(Container, "LOOK_INSIDE_VERBS", frozenset())
    if issubclass(cls, Container) and keyword in look_inside:
        return True                                          # arm 1
    # Arm 2 has no placement of its own: a container's items are authored
    # inside its inventory, never as a placement on the tile.
    if issubclass(cls, Passageway):
        if instance.is_demo_edge():
            # Arm 3 takes the crossing verbs; everything else on the demo edge
            # falls past arm 4 (which excludes it) to arm 5.
            if instance.is_crossing_handler(handler):
                return True                                  # arm 3
        elif instance.accepts_step_through(handler):
            return True                                      # arm 4
    return handler is not None                               # arm 5


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

    # `enter` itself, and the placement's own authored name words, must answer
    # through that entry. The name words are DATA since #620's follow-up --
    # `passage.ferry` is deliberately no longer an attribute, because an
    # instance-stored callable is exactly what a restored save could forge --
    # so they are reached the way the dispatch reaches them.
    assert passage.is_crossing_handler(passage.enter)
    assert passage.is_crossing_handler(resolve_interaction(passage, "ferry"))

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
    that class rather than failing. Every shipped placement constructs
    normally today; if that changes, fix the construction, don't accept the
    fallback. (No count here on purpose: the suite only asserts ``> 100``, so a
    number written into the prose goes stale the next time a map gains an
    object and nothing notices.)
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
    answers "which verbs open it". They agree by CONSTRUCTION now --
    ``LOOK_INSIDE_VERBS`` splats ``_DEFAULT_LOOK_INSIDE_ALIASES``, which is
    also what seeds ``action_aliases`` (src/objects.py) -- so this reads a
    real ``Container()`` to catch the case that construction cannot: a verb
    added to ``action_aliases`` alone would ship a default button with no
    dispatch behind it, which is #553 again on a container nobody authored.
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


# ---------------------------------------------------------------------------
# The verbs the CLIENT sends that no placement advertises — issue #609
# ---------------------------------------------------------------------------
#
# Everything above asks "does every authored keyword resolve to something".
# #609 is the other direction, and nothing was asking it: the client renders a
# TAKE ALL button on every open container holding more than one item,
# regardless of what the placement authors, while ``GameService._verb_refusal`` accepts a verb only when the
# target ADVERTISES it in ``keywords`` or it sits on that service's
# ``_ALLOWED_INTERACTION_VERBS``.
#
# ``Container.__init__`` does advertise it (``keywords.extend(["loot",
# "take_all"])``), which is why a container built here would pass — but the map
# loader ``setattr``s the placement's authored ``keywords`` straight over that
# list, and most shipped placements author one without ``take_all`` (the
# assertion below names every one it finds). So the button was dead almost
# everywhere, answering "There's no way for Jean to
# take_all the Dusty Satchel."
#
# Both halves of the derivation below are therefore external to the service and
# to this file: the verb is read out of the component that sends it, and the
# targets are built from the shipped maps by the engine's own loader.

_INTERACT_PANEL = FRONTEND_SRC / "components" / "InteractPanel.jsx"

#: The container TAKE ALL button in ``InteractPanel.jsx``: ONE ``<GameButton``
#: element, from its opening tag through its ``onClick`` verb literal to its
#: own label, with no other ``<GameButton`` anywhere inside. Anchoring on the
#: element (rather than just on "the nearest ``handleActionClick`` before the
#: label") is what stops a silent wrong capture: if that button ever stops
#: passing its verb inline, this matches nothing and
#: :func:`_client_take_all_verb` fails, instead of quietly reading a
#: neighbouring button's verb and testing the wrong thing.
#:
#: The label is matched case-sensitively, so the tile-level "Take All Items"
#: control -- a different path (``take_all_ground``, handled client-side) --
#: cannot be picked up here.
_TAKE_ALL_BUTTON = re.compile(
    r"<GameButton\b(?:(?!<GameButton).)*?"
    r"handleActionClick\(\s*'([A-Za-z_]+)'\s*\)"
    r"(?:(?!<GameButton).)*?>\s*TAKE ALL\s*<",
    re.DOTALL,
)


@functools.lru_cache(maxsize=1)
def _client_take_all_verb():
    """The verb the container TAKE ALL button sends, read off the component.

    Derived, never transcribed: the claim under test is that the client emits
    a verb the server refuses, so the verb has to come from the client. Exactly
    one match must exist — a renamed verb, a deleted button or a second TAKE
    ALL control fails here, naming itself, rather than quietly leaving these
    tests pinning a spelling nothing sends any more.
    """
    matches = _TAKE_ALL_BUTTON.findall(
        _INTERACT_PANEL.read_text(encoding="utf-8")
    )
    assert len(matches) == 1, (
        f"expected exactly one container TAKE ALL button in "
        f"{_INTERACT_PANEL.name}, found {len(matches)}: {matches}. The verb "
        "these tests assert on is read from that button, so it has to be "
        "unambiguous."
    )
    return matches[0]


def _container_payloads():
    """``(map_name, coord, ref, payload)`` for every shipped container.

    Built on the shared parse (``map_data``/``tiles``/``class_ref``) rather
    than a second glob — see ``tests/_map_scan``'s docstring. The raw payload
    rides along because the loader below takes the payload, not a summary of
    it.
    """
    rows = []
    for path, decoded in map_data():
        for coord, tile_data in tiles(decoded):
            for payload in tile_data.get("objects") or []:
                ref = class_ref(payload)
                if ref is None:
                    continue
                if issubclass(map_placeholders.resolve_class(ref.dotted), Container):
                    rows.append((path.name, coord, ref, payload))
    return rows


class _LoadedContainer(NamedTuple):
    """One shipped container placement and the instance the loader built.

    A NamedTuple rather than a bare 4-tuple so the assertions below read
    ``row.instance`` instead of ``row[3]`` -- the rows are unpacked in several
    places and one transposed index would silently test a coordinate string
    for keywords.
    """

    map_name: str
    coord: str
    name: str
    instance: object


@functools.lru_cache(maxsize=1)
def _loaded_containers():
    """Every shipped container, built the way the game builds it.

    ``Universe._deserialize_saved_instance`` IS the map-load path: the class
    trust gate, the constructor-signature filter, then the ``setattr`` of every
    remaining authored prop — and that last step is the one that replaces the
    constructor's ``keywords``. Constructing ``Container(...)`` here instead
    would leave the inherited ``take_all`` in place and this whole section
    would pass while every shipped placement failed, which is the defect.

    ``Universe()`` loads no maps of its own, so it is cheap; its ``player`` is
    what the loader injects into constructors that accept one.

    Called from inside tests rather than at import, so the autouse terminal
    patch is in place for the narration the constructors emit.
    """
    from src.universe import Universe

    universe = Universe(player=_player())
    rows = []
    for map_name, coord, ref, payload in _container_payloads():
        instance = universe._deserialize_saved_instance(payload, tile=_StubTile())
        assert instance is not None, (
            f"the engine loader refused {map_name} {coord} {ref.dotted} — "
            "the shipped map would load an emptier world than this test thinks"
        )
        name = ref.props.get("name") or ref.class_name
        rows.append(_LoadedContainer(map_name, coord, name, instance))
    return tuple(rows)


def _gate_refusal(target, verb):
    """What ``GameService._verb_refusal`` answers for one verb on one target.

    The gate is the thing under contract, so it is called for real; the request
    is the service's own ``_InteractionRequest``, and this gate reads only its
    ``target`` and ``action``. Imported lazily for the reason the module
    docstring gives: reverting the fix must produce these tests' assertion
    failures, not a collection error.
    """
    from src.api.services.game_service import GameService, _InteractionRequest

    request = _InteractionRequest(
        player=None,
        target=target,
        target_id="",
        tile=None,
        action=verb,
        quantity=None,
        session_data=None,
    )
    return GameService()._verb_refusal(request)


def test_the_clients_take_all_verb_names_a_real_container_method():
    """Cross-check of the client-side derivation against the engine.

    Not ``== "take_all"``: a literal here would be this file agreeing with
    itself. What matters is that whatever the button sends resolves to
    something callable on a container — if it ever stops doing so, the button
    is #553 again and the contract below would be asserting about a verb the
    engine cannot serve either.
    """
    from src.objects import resolve_interaction

    verb = _client_take_all_verb()
    assert verb and verb.strip() == verb
    assert resolve_interaction(Container(), verb) is not None, (
        f"the TAKE ALL button sends {verb!r}, which resolves to nothing "
        "callable on a Container"
    )


def test_shipped_containers_lose_the_constructors_take_all_keyword():
    """The population the allow-list has to carry, proved non-empty.

    ``Container.__init__`` advertises the verb, so a target that still carries
    it passes the gate through the ADVERTISED arm and says nothing about the
    allow-list. This is the positive control for the contract below: if the
    loader ever stopped dropping the keyword — or this scan stopped finding
    containers — that contract would pass vacuously for a gate that accepts
    nothing at all.
    """
    verb = _client_take_all_verb()
    assert verb in Container().keywords, (
        f"Container.__init__ no longer advertises {verb!r}; the premise of "
        "this section (the loader drops an inherited keyword) has changed"
    )

    loaded = _loaded_containers()
    assert len(loaded) > 20, (
        f"only {len(loaded)} container placements found — the map scan broke"
    )
    unadvertised = [
        row for row in loaded
        if verb not in (getattr(row.instance, "keywords", None) or [])
    ]
    assert len(unadvertised) > 20, (
        f"only {len(unadvertised)} of {len(loaded)} shipped containers fail to "
        f"advertise {verb!r} — the contract below no longer exercises the "
        "service's allow-list, so it is not testing #609 any more"
    )


def test_the_reported_container_is_in_the_scan():
    """grondia (1, 3) 'Dusty Satchel' — the placement #609 was filed against."""
    verb = _client_take_all_verb()
    hits = [
        row for row in _loaded_containers()
        if row.map_name == "grondia.json" and row.coord == "(1, 3)"
        and row.name == "Dusty Satchel"
    ]
    assert len(hits) == 1, (
        "the exact placement issue #609 was reproduced against is no longer "
        "in the scan — if it was renamed or removed, update this anchor "
        "deliberately"
    )
    assert verb not in hits[0].instance.keywords, (
        f"the Dusty Satchel now advertises {verb!r} itself, so it no longer "
        "reproduces the reported bug — pick another anchor rather than "
        "deleting this one"
    )


def test_every_shipped_container_accepts_the_clients_take_all():
    """The contract: the button the client always renders is never refused.

    One aggregate assertion so the failure names every placement, the way
    ``test_no_authored_keyword_anywhere_is_undispatchable`` does.
    """
    verb = _client_take_all_verb()
    refused = [
        f"{map_name} {coord} {name!r}"
        for map_name, coord, name, instance in _loaded_containers()
        if _gate_refusal(instance, verb) is not None
    ]
    assert not refused, (
        f"GameService refuses the client's {verb!r} on {len(refused)} shipped "
        f"container placements (issue #609): {refused}. The frontend renders "
        "TAKE ALL for every open container holding more than one item, "
        "regardless of authored keywords, so "
        "the verb belongs on _ALLOWED_INTERACTION_VERBS — do not fix this by "
        "authoring the keyword into the maps."
    )


def test_take_all_dispatches_on_every_shipped_container():
    """Passing the gate is half of it; the verb must also resolve on the target.

    ``_dispatch_interaction`` falls through to ``resolve_interaction`` for this
    verb, and a target that resolves nothing is refused in fiction there
    instead — the same player-visible failure one branch later. That the
    dispatch then hands the items over is the end-to-end test below.
    """
    from src.objects import resolve_interaction

    verb = _client_take_all_verb()
    unimplemented = [
        f"{map_name} {coord} {name!r}"
        for map_name, coord, name, instance in _loaded_containers()
        if resolve_interaction(instance, verb) is None
    ]
    assert not unimplemented, (
        f"{verb!r} resolves to nothing callable on: {unimplemented}"
    )


def test_take_all_on_the_reported_container_moves_its_contents_to_jean():
    """Through the gate and ``_dispatch_interaction``, in the order
    ``interact_with_target`` runs them, on the placement #609 was reproduced
    against: the verb is accepted, and the arm it lands in hands the items over.

    A fresh instance, not the cached ``_loaded_containers()`` row: this test
    opens and empties the satchel, and ``pytest-randomly`` shuffles the order
    in which its siblings read that shared object. Opened first, because the
    button lives in the Container Contents panel -- the player clicks TAKE ALL
    on an open container.
    """
    from src.api.services.game_service import GameService, _InteractionRequest
    from src.items import Restorative
    from src.player import Player
    from src.universe import Universe

    payload = next(
        payload for map_name, coord, ref, payload in _container_payloads()
        if map_name == "grondia.json" and coord == "(1, 3)"
        and ref.props.get("name") == "Dusty Satchel"
    )
    satchel = Universe(player=_player())._deserialize_saved_instance(
        payload, tile=_StubTile()
    )
    satchel.open()
    tonic = Restorative()
    satchel.inventory.append(tonic)
    jean = Player()
    verb = _client_take_all_verb()

    assert _gate_refusal(satchel, verb) is None
    outcome = GameService()._dispatch_interaction(_InteractionRequest(
        player=jean,
        target=satchel,
        target_id="",
        tile=None,
        action=verb,
        quantity=None,
        session_data=None,
    ))

    assert outcome.refusal is None, outcome.refusal
    assert tonic not in satchel.inventory
    assert [i for i in jean.inventory if i.name == tonic.name]


def test_the_gate_still_refuses_an_unadvertised_public_method():
    """The #334 guarantee the #609 fix must not have widened.

    ``Container.process_events`` is a real, public, callable method that no
    placement authors as a keyword — exactly the arbitrary-attribute dispatch
    the allow-list exists to stop. It is also the negative control for the
    contract above: the gate genuinely refuses something, so "not refused" is
    a fact about ``take_all`` rather than about a gate that waves everything
    through.
    """
    from src.objects import resolve_interaction

    containers = [row.instance for row in _loaded_containers()]
    assert containers, "no containers loaded — see the population guard above"
    sample = containers[0]

    assert resolve_interaction(sample, "process_events") is not None, (
        "process_events is no longer a callable attribute, so it is no longer "
        "the hazard this control stands for — pick another public method"
    )
    assert "process_events" not in (getattr(sample, "keywords", None) or [])

    refusals = [
        _gate_refusal(instance, "process_events") for instance in containers
    ]
    assert all(r is not None for r in refusals), (
        "GameService accepted 'process_events' as an interaction verb — the "
        "allow-list has been widened past the container verbs the client "
        "sends, re-opening issue #334"
    )
