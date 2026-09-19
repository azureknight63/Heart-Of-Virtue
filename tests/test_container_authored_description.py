"""Opening a container must not destroy its map-authored description.

Issue #629. ``Container.refresh_description`` rebuilt ``self.description``
from one of three templates every time it ran, and ``Container.open`` and
``Container.take_all`` both call it. Every one of the 47 shipped
``Container``-family placements authors a description, so the first time a
player opened one, prose written for that tile was replaced by
``"A <nickname>. Inside are the following things: ..."``.

The loss is persisted, not merely cosmetic: ``Player.universe`` is pickled
into the save, so the overwrite survives the session.

"Exploration is the UI" (CLAUDE.md design pillar 4) makes that a defect: the
authored line is the only place a tile's durable evidence is written down.

The guard below is derived from the shipped maps rather than a hand-written
list, and the derivation is asserted non-empty — a scan that matches nothing
approves of everything.

The second half of the file is the anti-regression half, and it is the half
that matters most: a container that never had authored prose must STILL get
its contents listing regenerated, including incrementally after a single item
is taken (``GameService`` refreshes on every take). A guard that only checked
"authored text survives" would be satisfied by deleting the feature.
"""

from types import SimpleNamespace

import pytest

from src.items import Antidote, Draught, Restorative
from src.objects import Container, Crate, Shelf
from src.player import Player
from tests._map_scan import (
    MIN_CONTAINER_PLACEMENTS,
    container_placements,
    map_files,
)


def _authored_container_placements():
    """``(map_name, coord, props)`` for shipped containers with authored prose.

    The base ``Container`` is what gets constructed from these, not the
    resolved subclass: ``Crate``/``Shelf``/``SupplyTent`` take
    ``player``/``tile`` positionally and expose no ``description`` kwarg, and a
    try/except fallback in a guard is how the rows most likely to be wrong stop
    being covered. Their own hardcoded descriptions are covered explicitly
    below instead.
    """
    return [
        (placement.map_name, placement.coord, placement.props)
        for placement, _cls in container_placements()
        if placement.props.get("description")
    ]


#: One spelling of the map-derived case list for the two parametrized guards
#: below, which ran byte-identical decorators. Built once at import, as both
#: decorators did.
_AUTHORED_CASES = [
    pytest.param(*p, id=f"{p[0]}:{p[1]}:{p[2].get('name', 'Container')}")
    for p in _authored_container_placements()
]


def _stocked(**kwargs):
    """A container holding three distinct (non-stacking) items.

    Closed unless the caller passes ``start_open=True``, which most callers
    here do: the loot and single-take paths only run on an open container.
    """
    kwargs.setdefault("inventory", [Restorative(), Antidote(), Draught()])
    return Container(**kwargs)


def _player_for(container):
    """A real ``Player`` standing on a tile that holds ``container``."""
    player = Player()
    player.inventory = []
    tile = SimpleNamespace(
        x=1, y=1, npcs_here=[], objects_here=[container], items_here=[]
    )
    container.player = player
    container.tile = tile
    return player


# ---------------------------------------------------------------------------
# Derivation guard
# ---------------------------------------------------------------------------


def test_the_authored_container_population_is_not_empty():
    placements = _authored_container_placements()
    assert len(placements) >= MIN_CONTAINER_PLACEMENTS, (
        "map scan found almost no Container placements carrying an authored "
        "description — the scan broke, and every assertion below is now "
        f"vacuous. Found: {placements}"
    )


# ---------------------------------------------------------------------------
# The regression itself
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("map_name,coord,props", _AUTHORED_CASES)
def test_opening_a_shipped_container_keeps_its_authored_description(
    map_name, coord, props
):
    container = _stocked(
        name=props.get("name", "Container"),
        nickname=props.get("nickname", "container"),
        description=props["description"],
    )
    container.open()
    assert container.description == props["description"], (
        f"{map_name} {coord} lost its authored description on open()"
    )


@pytest.mark.parametrize("map_name,coord,props", _AUTHORED_CASES)
def test_looting_a_shipped_container_keeps_its_authored_description(
    map_name, coord, props
):
    container = _stocked(
        name=props.get("name", "Container"),
        nickname=props.get("nickname", "container"),
        description=props["description"],
        start_open=True,
    )
    player = _player_for(container)
    container.take_all(player)
    assert container.inventory == [], "take_all did not actually take anything"
    assert container.description == props["description"], (
        f"{map_name} {coord} lost its authored description on take_all()"
    )


def test_authored_description_survives_a_single_item_take():
    """The per-item refresh path too.

    That is ``GameService._dispatch_interaction`` in
    ``src/api/services/game_service.py``, which refreshes the parent container
    after every single-item take.
    """
    authored = "A squat stone coffer, sealed with a carved disc lock."
    container = _stocked(nickname="archive coffer", description=authored,
                         start_open=True)
    container.inventory.pop(0)
    container.refresh_description()
    assert container.description == authored


# ---------------------------------------------------------------------------
# Crate / Shelf — the behaviour change this fix carries with it
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("cls", [Crate, Shelf], ids=lambda c: c.__name__)
def test_hardcoded_subclass_descriptions_are_also_preserved(cls):
    """``Crate``/``Shelf`` hardcode a non-default description in ``__init__``.

    They expose no ``description`` kwarg, so authored prose reaches them only
    through the loader's post-construction ``setattr`` — which means the guard
    cannot distinguish their hardcoded line from an authored one, and their
    descriptions stop being overwritten too. That is beyond the literal bug and
    is pinned here deliberately: the contents still reach the client
    structurally through the serializer's ``contents``/``item_count``.
    """
    container = cls(player=None, tile=None)
    original = container.description
    assert original, f"{cls.__name__} has no hardcoded description to preserve"
    container.inventory = [Restorative()]
    container.refresh_description()
    assert container.description == original


# ---------------------------------------------------------------------------
# Anti-regression: generic containers must STILL regenerate
# ---------------------------------------------------------------------------


def test_default_description_container_lists_contents_on_open():
    container = _stocked(nickname="old chest")
    before = container.description
    container.open()
    assert container.description != before
    assert "Inside are the following things" in container.description
    for item in container.inventory:
        assert item.description in container.description


def test_default_description_container_reports_empty_after_take_all():
    container = _stocked(nickname="old chest", start_open=True)
    player = _player_for(container)
    container.take_all(player)
    assert "empty" in container.description.lower()


def test_default_description_container_regenerates_after_each_single_take():
    """Incremental regeneration — the subtle case.

    After ``open()`` the description is a listing that embeds the *pre-take*
    inventory, so it no longer equals the constructor default. A guard that
    only compared against the default would freeze the listing here, and the
    web client's per-item refresh would silently stop working.
    """
    container = _stocked(nickname="old chest")
    container.open()
    while container.inventory:
        dropped = container.inventory.pop(0)
        container.refresh_description()
        assert dropped.description not in container.description, (
            "listing still names an item that was taken"
        )
        for remaining in container.inventory:
            assert remaining.description in container.description
    assert "empty" in container.description.lower()


def test_every_generated_template_carries_one_of_the_markers():
    """Positive half of the shape test: the markers are what we produce.

    Without this, ``_GENERATED_MARKERS`` could drift away from the templates
    and the guard below would keep passing while recognising nothing.
    """
    seen = set()
    states = (
        Container(nickname="old chest"),                      # closed
        _stocked(nickname="old chest", start_open=True),      # open, holding
        Container(nickname="old chest", start_open=True),     # open, empty
    )
    for container in states:
        container.refresh_description()
        matched = [
            m for m in Container._GENERATED_MARKERS if m in container.description
        ]
        assert matched, f"{container.description!r} carries no generated marker"
        seen.update(matched)
    assert seen == set(Container._GENERATED_MARKERS), (
        f"templates no longer produce every marker: missing "
        f"{set(Container._GENERATED_MARKERS) - seen}"
    )


def test_no_authored_map_prose_looks_generated():
    """Negative half: the markers appear nowhere an author could have written.

    This is the premise the shape test rests on. A marker phrase turning up in
    authored map prose would make ``_description_is_generic`` overwrite that
    prose — the #629 bug again — so the whole map corpus is scanned as text
    rather than just the ``description`` props: a marker in an idle message or
    an NPC line is a warning that the phrase has stopped being distinctive.
    """
    paths = map_files()
    assert len(paths) >= 10, f"map scan found almost no maps: {paths}"
    offenders = [
        (path.name, marker)
        for path in paths
        for marker in Container._GENERATED_MARKERS
        if marker in path.read_text(encoding="utf-8")
    ]
    assert not offenders, (
        "shipped map prose contains a phrase refresh_description treats as "
        f"its own output, and would overwrite: {offenders}"
    )


# A save written before #629 holds containers whose ``description`` IS a
# generated listing -- the templates below are the pre-fix spellings, article
# bug and all -- and which carry no bookkeeping attribute saying so. The guard
# has to recognise those by SHAPE or it freezes them forever, which is worse
# than the bug it was written to fix: the player empties the container and the
# description shipped to the client goes on naming items that are gone.
_PRE_FIX_DESCRIPTIONS = {
    "closed": (
        "A old chest which may or may not have things inside. You can try "
        "to UNLOCK (if locked), OPEN, or LOOT it."
    ),
    "empty": "A old chest. It's empty. Very sorry.",
    "stocked": (
        "A old chest. Inside are the following things: \n\n"
        "A small vial of some long-forgotten remedy."
    ),
}


@pytest.mark.parametrize(
    "stale",
    list(_PRE_FIX_DESCRIPTIONS.values()),
    ids=list(_PRE_FIX_DESCRIPTIONS),
)
def test_a_pre_fix_save_regenerates_instead_of_freezing(stale):
    container = _stocked(nickname="old chest", start_open=True)
    container.description = stale
    # Whatever bookkeeping the current implementation keeps, a container
    # restored from a pre-fix pickle does not have it.
    container.__dict__.pop("_generated_description", None)
    container.refresh_description()
    assert container.description != stale, (
        "a pre-#629 generated listing was treated as authored prose and "
        "frozen -- the container can never describe its contents again"
    )
    for item in container.inventory:
        assert item.description in container.description


def test_closed_default_container_still_gets_the_closed_template():
    container = Container(nickname="old chest")
    container.refresh_description()
    assert "OPEN" in container.description


def test_the_default_description_constant_matches_the_constructor_default():
    """The constant and the ``__init__`` default cannot be allowed to drift."""
    assert Container().description == Container._DEFAULT_DESCRIPTION


def _defaults_that_do_not_match_their_constant(classes):
    """Of ``classes``, those declaring their own ``_DEFAULT_DESCRIPTION`` whose
    effective ``__init__`` does not actually default to it.

    ``Container.__init__``'s ``description`` default is bound once, when the
    class body executes, so it holds the *base* literal forever. A subclass
    that overrides the constant but inherits that ``__init__`` therefore
    constructs with the base string, which ``_description_is_generic`` --
    reading ``cls._DEFAULT_DESCRIPTION`` off the subclass -- no longer
    recognises as generic. The instance is frozen at a placeholder it never
    chose: #629's failure mode inverted.

    Reads the signature rather than constructing. The shipped subclasses all
    require ``player`` and ``tile``, so a construct-and-compare check has to
    swallow ``TypeError`` -- and that ``except`` makes the guard fail open for
    exactly the classes it exists to police.

    Takes an explicit population rather than walking ``__subclasses__()`` so
    the negative control below cannot leak a synthetic class into the real
    guard's scan.
    """
    import inspect

    offenders = []
    for cls in classes:
        if "_DEFAULT_DESCRIPTION" not in vars(cls):
            continue
        param = inspect.signature(cls.__init__).parameters.get("description")
        effective = param.default if param is not None else "<no description parameter>"
        if effective != cls._DEFAULT_DESCRIPTION:
            offenders.append((cls.__name__, cls._DEFAULT_DESCRIPTION, effective))
    return offenders


def _shipped_container_classes():
    """Every ``Container`` class defined in ``src.objects``."""
    import src.objects as objects_module

    return [
        obj
        for obj in vars(objects_module).values()
        if isinstance(obj, type) and issubclass(obj, Container)
    ]


def test_the_subclass_default_detector_actually_detects():
    """Negative control, and it is load-bearing.

    No shipped class overrides ``_DEFAULT_DESCRIPTION`` today, so the guard
    below scans a population in which nothing can be wrong -- and a scan that
    can never report approves of everything. This proves the detector speaks
    when a class does override it, for both shapes: inheriting the base
    ``__init__`` (the real trap) and declaring one with no ``description``
    parameter at all (a dead constant).
    """

    class _InheritsBaseInit(Container):
        _DEFAULT_DESCRIPTION = "An old chest, iron-banded."

    class _NoDescriptionParam(Container):
        _DEFAULT_DESCRIPTION = "A crate of some kind."

        def __init__(self, player=None, tile=None):  # pragma: no cover - fixture
            pass

    reported = [
        name
        for name, _, _ in _defaults_that_do_not_match_their_constant(
            [_InheritsBaseInit, _NoDescriptionParam]
        )
    ]
    assert reported == ["_InheritsBaseInit", "_NoDescriptionParam"], reported


def test_the_shipped_container_population_is_non_empty():
    """A scan that matches nothing approves of everything."""
    shipped = _shipped_container_classes()
    assert len(shipped) >= 4, [c.__name__ for c in shipped]


def test_no_shipped_container_overrides_the_default_without_matching_it():
    """A class may override the constant only if its ``__init__`` defaults to it.

    Fix, if this ever fails: give the class an explicit
    ``description=<its own constant>`` default, or drop the override.
    """
    offenders = _defaults_that_do_not_match_their_constant(
        _shipped_container_classes()
    )
    assert offenders == [], (
        "these Container classes declare their own _DEFAULT_DESCRIPTION but do "
        "not default to it, so refresh_description() will freeze them at a "
        f"placeholder they never chose: {offenders}"
    )
