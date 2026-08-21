"""Unit tests for src.loot_tables.

These exercise the real ``src.items`` registry rather than a mocked
``inspect.getmembers``: ``Loot.random_equipment``'s whole job is to pick a name
out of that registry whose ``level`` matches the request, so mocking the
registry away leaves nothing worth asserting.
"""
import inspect
import random
from unittest.mock import Mock, patch

import pytest

import src.items as items
from src.loot_tables import Loot
from src.narration import capture_narration


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

# The loot tables are constant data; one instance is safe to share module-wide.
@pytest.fixture(scope="module")
def loot_instance():
    return Loot()


def _real_item_names_at_level(level):
    """Names in the live ``src.items`` registry whose class ``level`` matches."""
    return {
        name for name, obj in inspect.getmembers(items)
        if inspect.isclass(obj) and getattr(obj, "level", None) == level
    }


class _RecordingTile:
    """Minimal stand-in for a Tile that records spawn_item calls."""

    def __init__(self):
        self.calls = []

    def spawn_item(self, name, amt=1, hidden=False, hfactor=0):
        self.calls.append(
            {"name": name, "amt": amt, "hidden": hidden, "hfactor": hfactor}
        )
        # Return a real engine item so downstream enchanting has a real target.
        return getattr(items, name)()


# ---------------------------------------------------------------------------
# Loot table data
# ---------------------------------------------------------------------------

def test_loot_tables_are_per_instance_not_shared():
    """Each Loot() must own its tables; a shared dict would let one NPC's
    loot mutation bleed into every other NPC's drop table."""
    a, b = Loot(), Loot()
    assert a.lev0 is not b.lev0
    a.lev0["Gold"]["chance"] = 999
    assert b.lev0["Gold"]["chance"] == 50


@pytest.mark.parametrize("table,key,chance,qty", [
    ("lev0", "Gold", 50, "r25-50"),
    ("lev0", "Restorative", 25, 1),
    ("lev0", "Draught", 25, 1),
    ("lev0", "Equipment_0_1", 10, 1),
    ("lev1", "Gold", 50, "r50-100"),
    ("lev1", "Restorative", 25, "r1-3"),
    ("lev1", "Draught", 25, "r1-3"),
    ("lev1", "Equipment_0_0", 40, 1),
    ("lev1", "Equipment_1_0", 10, 1),
])
def test_loot_entry_values(loot_instance, table, key, chance, qty):
    entry = getattr(loot_instance, table)[key]
    assert entry == {"chance": chance, "qty": qty}


def test_lev0_and_lev1_have_exactly_the_expected_keys(loot_instance):
    assert set(loot_instance.lev0) == {
        "Gold", "Restorative", "Draught", "Equipment_0_1"}
    assert set(loot_instance.lev1) == {
        "Gold", "Restorative", "Draught", "Equipment_0_0", "Equipment_1_0"}


def test_lev1_is_strictly_richer_than_lev0(loot_instance):
    """lev1 is the higher-tier table: same drop chance for gold but a bigger
    roll range, and stackable restoratives instead of a single one."""
    lev0_lo, lev0_hi = (int(x) for x in
                        loot_instance.lev0["Gold"]["qty"][1:].split("-"))
    lev1_lo, lev1_hi = (int(x) for x in
                        loot_instance.lev1["Gold"]["qty"][1:].split("-"))
    assert lev1_lo >= lev0_hi
    assert lev1_hi > lev0_hi
    assert loot_instance.lev0["Restorative"]["qty"] == 1
    assert loot_instance.lev1["Restorative"]["qty"] == "r1-3"


@pytest.mark.parametrize("table", ["lev0", "lev1"])
def test_every_entry_is_a_well_formed_drop_spec(loot_instance, table):
    """chance is a 1-100 int; qty is either a positive int or an 'rLO-HI'
    range whose bounds are ordered and positive."""
    for name, spec in getattr(loot_instance, table).items():
        assert set(spec) == {"chance", "qty"}, name
        assert isinstance(spec["chance"], int) and not isinstance(
            spec["chance"], bool), name
        assert 0 < spec["chance"] <= 100, name
        qty = spec["qty"]
        if isinstance(qty, str):
            assert qty.startswith("r"), name
            lo, hi = (int(x) for x in qty[1:].split("-"))
            assert 0 < lo <= hi, name
        else:
            assert isinstance(qty, int) and qty > 0, name


# ---------------------------------------------------------------------------
# random_equipment -- against the real items registry
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("level", [0, 1, 2, 3, 4])
def test_random_equipment_only_ever_spawns_an_item_of_the_requested_level(level):
    """The whole point of the level filter: no off-level item may be spawned."""
    expected = _real_item_names_at_level(level)
    assert expected, f"registry has no level-{level} items to test against"

    tile = _RecordingTile()
    rng = random.Random(1234)
    seen = set()
    with patch("src.loot_tables.random.randint",
               side_effect=lambda a, b: rng.randint(a, b)):
        for _ in range(40):
            drop = Loot.random_equipment(tile, level, 0)
            assert drop.__class__.level == level
            seen.add(tile.calls[-1]["name"])
    assert seen <= expected
    # Selection must actually vary rather than latching onto one candidate.
    assert len(seen) > 1


def test_random_equipment_accepts_a_string_level():
    """``level`` is int()-cast, so a serialized '1' from map JSON still works."""
    tile = _RecordingTile()
    drop = Loot.random_equipment(tile, "1", 0)
    assert drop.__class__.level == 1
    assert tile.calls[-1]["name"] in _real_item_names_at_level(1)


def test_random_equipment_spawn_parameters_are_fixed():
    tile = _RecordingTile()
    Loot.random_equipment(tile, 1, 0)
    assert len(tile.calls) == 1
    call = tile.calls[0]
    assert call["amt"] == 1
    assert call["hidden"] is False
    assert call["hfactor"] == 0


def test_random_equipment_selection_covers_the_whole_candidate_range():
    """``randint`` must be called with the inclusive 0..len-1 bounds; an
    off-by-one here would make the last candidate unreachable (or IndexError)."""
    tile = _RecordingTile()
    with patch("src.loot_tables.random.randint", return_value=0) as randint:
        Loot.random_equipment(tile, 1, 0)
    lo, hi = randint.call_args[0]
    assert lo == 0
    assert hi == len(_real_item_names_at_level(1)) - 1


def test_random_equipment_passes_enchantment_pool_through():
    tile = _RecordingTile()
    with patch("src.loot_tables.functions.add_random_enchantments") as ench:
        drop = Loot.random_equipment(tile, 1, 5)
    ench.assert_called_once_with(drop, 5)


def test_random_equipment_falls_back_to_zero_enchantment_on_bad_input():
    """A non-numeric enchantment must narrate the error and degrade to 0
    rather than propagating a ValueError out of the drop path."""
    tile = _RecordingTile()
    with capture_narration() as messages:
        with patch("src.loot_tables.functions.add_random_enchantments") as ench:
            drop = Loot.random_equipment(tile, 1, "invalid")
    ench.assert_called_once_with(drop, 0)
    assert any("###ERR" in m["text"] and "invalid" in m["text"]
               for m in messages), messages


def test_random_equipment_accepts_numeric_string_enchantment():
    tile = _RecordingTile()
    with capture_narration() as messages:
        with patch("src.loot_tables.functions.add_random_enchantments") as ench:
            drop = Loot.random_equipment(tile, 1, "3")
    ench.assert_called_once_with(drop, 3)
    assert not [m for m in messages if "###ERR" in m["text"]]


def test_random_equipment_returns_the_spawned_item():
    """The return value must be the object the tile actually spawned, not a
    freshly constructed one -- callers enchant and place the returned drop."""
    tile = Mock()
    sentinel = items.Dagger()
    tile.spawn_item.return_value = sentinel
    with patch("src.loot_tables.functions.add_random_enchantments"):
        assert Loot.random_equipment(tile, 1, 0) is sentinel
