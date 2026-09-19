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
from tests._map_scan import object_placements, resolve_class


def _authored_container_placements():
    """``(map_name, coord, props)`` for shipped containers with authored prose.

    The base ``Container`` is what gets constructed from these, not the
    resolved subclass: ``Crate``/``Shelf``/``SupplyTent`` take
    ``player``/``tile`` positionally and expose no ``description`` kwarg, and a
    try/except fallback in a guard is how the rows most likely to be wrong stop
    being covered. Their own hardcoded descriptions are covered explicitly
    below instead.
    """
    out = []
    for placement in object_placements():
        cls = resolve_class(placement)
        if not (isinstance(cls, type) and issubclass(cls, Container)):
            continue
        if placement.props.get("description"):
            out.append((placement.map_name, placement.coord, placement.props))
    return out


def _stocked(**kwargs):
    """A closed container holding three distinct (non-stacking) items."""
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
    assert len(placements) > 20, (
        "map scan found almost no Container placements carrying an authored "
        "description — the scan broke, and every assertion below is now "
        f"vacuous. Found: {placements}"
    )


# ---------------------------------------------------------------------------
# The regression itself
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "map_name,coord,props",
    [
        pytest.param(*p, id=f"{p[0]}:{p[1]}:{p[2].get('name', 'Container')}")
        for p in _authored_container_placements()
    ],
)
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


@pytest.mark.parametrize(
    "map_name,coord,props",
    [
        pytest.param(*p, id=f"{p[0]}:{p[1]}:{p[2].get('name', 'Container')}")
        for p in _authored_container_placements()
    ],
)
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
    """The per-item refresh path (``GameService`` line ~2583) too."""
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


def test_closed_default_container_still_gets_the_closed_template():
    container = Container(nickname="old chest")
    container.description = Container._DEFAULT_DESCRIPTION
    container.refresh_description()
    assert "OPEN" in container.description


def test_the_default_description_constant_matches_the_constructor_default():
    """The constant and the ``__init__`` default cannot be allowed to drift."""
    assert Container().description == Container._DEFAULT_DESCRIPTION
