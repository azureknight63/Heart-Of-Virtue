"""tests/test_player_inventory_gaps.py

Coverage tests for src/player/_inventory.py — targeting the uncovered lines:
66-67, 110, 134-141, 145-148, 161-162, 206, 236-245, 290, 311, 317, 322, 334,
339, 360, 377-380, 388, 390-401, 411, 433-434, 439-445, 449-467, 470, 488
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_player():
    """Return a real Player with a minimal tile so inventory methods can run."""
    from src.player import Player

    p = Player()
    tile = MagicMock()
    tile.items_here = []
    p.current_room = tile
    p.tile = tile
    return p


def _make_equippable(maintype="Weapon", subtype="Sword", name="TestSword"):
    """Return a mock item that behaves like an equippable."""
    item = MagicMock()
    item.name = name
    item.announce = name.lower()
    item.maintype = maintype
    item.subtype = subtype
    item.isequipped = False
    item.gives_exp = True
    item.weight = 1.0
    item.interactions = ["equip"]
    item.on_equip = MagicMock()
    item.on_unequip = MagicMock()
    return item


def _make_consumable(name="Potion"):
    """Return a mock consumable item."""
    import src.items as items_mod

    item = MagicMock(spec=items_mod.Consumable)
    item.name = name
    item.announce = name.lower()
    item.count = 1
    item.merchandise = False
    item.interactions = ["use"]
    item.use = MagicMock()
    return item


# ---------------------------------------------------------------------------
# stack_gold
# ---------------------------------------------------------------------------


def test_stack_gold_no_gold():
    """stack_gold does nothing when inventory has no Gold items."""
    p = _make_player()
    mock_item = MagicMock()
    mock_item.__class__ = type("OtherItem", (), {})
    p.inventory = [mock_item]
    original_len = len(p.inventory)
    p.stack_gold()
    assert len(p.inventory) == original_len


def test_stack_gold_multiple_stacks():
    """stack_gold consolidates multiple Gold items into one."""
    import src.items as items_mod

    p = _make_player()
    g1 = items_mod.Gold(amt=10)
    g2 = items_mod.Gold(amt=20)
    p.inventory = [g1, g2]
    p.stack_gold()
    gold_items = [i for i in p.inventory if isinstance(i, items_mod.Gold)]
    assert len(gold_items) == 1
    assert gold_items[0].amt == 30


# ---------------------------------------------------------------------------
# drop_merchandise_items
# ---------------------------------------------------------------------------


def test_drop_merchandise_items_no_tile():
    """drop_merchandise_items returns early when tile_exists returns None."""
    p = _make_player()
    merch = MagicMock()
    merch.merchandise = True
    p.inventory = [merch]
    # tile_exists will raise or return None via mock map
    p.map = {}
    p.location_x = 0
    p.location_y = 0
    with patch("src.player._inventory.tile_exists", return_value=None):
        p.drop_merchandise_items()
    # Item should still be in inventory since tile was None
    assert merch in p.inventory


def test_drop_merchandise_items_with_merch(capsys):
    """drop_merchandise_items removes merchandise items and drops them on the tile."""
    p = _make_player()
    merch = MagicMock()
    merch.merchandise = True
    merch.name = "Stolen Sword"
    merch.stack_grammar = MagicMock()
    p.inventory = [merch]
    p.map = {}
    p.location_x = 0
    p.location_y = 0
    tile = MagicMock()
    tile.items_here = []
    with patch("src.player._inventory.tile_exists", return_value=tile):
        with patch("time.sleep"):
            p.drop_merchandise_items()
    assert merch not in p.inventory
    assert merch in tile.items_here


def test_drop_merchandise_items_value_error_ignored():
    """drop_merchandise_items ignores ValueError from inventory.remove."""
    p = _make_player()
    merch = MagicMock()
    merch.merchandise = True
    merch.name = "Sword"
    p.inventory = []  # Item NOT in inventory — forces ValueError path

    class _FakeList(list):
        def remove(self, item):
            raise ValueError("not in list")

    p.inventory = _FakeList([merch])
    tile = MagicMock()
    tile.items_here = []
    p.map = {}
    p.location_x = 0
    p.location_y = 0
    with patch("src.player._inventory.narrate") as mock_narrate:
        with patch("src.player._inventory.tile_exists", return_value=tile):
            p.drop_merchandise_items()

    # The ValueError short-circuits the drop entirely: the item must NOT be
    # duplicated onto the tile, and no drop message may be narrated for it.
    assert tile.items_here == []
    assert merch in p.inventory
    mock_narrate.assert_not_called()


# ---------------------------------------------------------------------------
# equip_item — weight-too-heavy path (lines 134-141)
# ---------------------------------------------------------------------------


def test_equip_item_too_heavy():
    """equip_item prints 'too heavy' and returns when item exceeds weight capacity."""
    p = _make_player()
    p.weight_tolerance = 5.0
    p.weight_current = 4.9
    heavy = _make_equippable()
    heavy.weight = 2.0
    heavy.isequipped = False
    # item not in inventory; simulates equipping from the room
    p.inventory = []
    p.current_room.items_here = []

    with patch("src.player._inventory.cprint") as mock_cprint:
        p.equip_item(item_object=heavy)

    mock_cprint.assert_called_once()
    assert "heavy" in mock_cprint.call_args[0][0].lower()


def test_equip_item_too_heavy_returns_to_candidates(capsys):
    """When too heavy and item was in candidates, it is returned to room."""
    p = _make_player()
    p.weight_tolerance = 5.0
    p.weight_current = 4.9

    heavy = _make_equippable()
    heavy.weight = 2.0
    heavy.isequipped = False
    heavy.announce = "testsword"
    p.inventory = []
    # Put item in room so phrase search adds it to candidates
    p.current_room.items_here = [heavy]

    with patch("src.player._inventory.cprint"):
        p.equip_item(phrase="testsword")

    # Since it was too heavy, it remains in the room — and must appear exactly
    # once (the failure path previously duplicated it into items_here).
    assert heavy in p.current_room.items_here
    assert p.current_room.items_here.count(heavy) == 1


# ---------------------------------------------------------------------------
# equip_item — item already in room, weight OK (lines 144-148)
# ---------------------------------------------------------------------------


def test_equip_item_from_room():
    """equip_item picks up an item from current_room when not in inventory."""
    p = _make_player()
    p.weight_tolerance = 100.0
    p.weight_current = 0.0
    item = _make_equippable()
    item.isequipped = False
    p.inventory = []
    p.current_room.items_here = [item]

    with patch("src.player._inventory.cprint"):
        with patch("src.player._inventory.functions") as mock_funcs:
            mock_funcs.refresh_stat_bonuses = MagicMock()
            p.refresh_protection_rating = MagicMock()
            p.equip_item(item_object=item)

    assert item in p.inventory


# ---------------------------------------------------------------------------
# equip_item — parent container removal (lines 151-162)
# ---------------------------------------------------------------------------


def test_equip_item_removes_from_parent_container():
    """equip_item removes item from _parent_container if present."""
    p = _make_player()
    p.weight_tolerance = 100.0
    p.weight_current = 0.0

    container = MagicMock()
    container.inventory = []
    container.refresh_description = MagicMock()

    item = _make_equippable()
    item.isequipped = False
    item._parent_container = container
    container.inventory.append(item)
    p.inventory = []
    p.current_room.items_here = []

    with patch("src.player._inventory.cprint"):
        with patch("src.player._inventory.functions") as mock_funcs:
            mock_funcs.refresh_stat_bonuses = MagicMock()
            p.refresh_protection_rating = MagicMock()
            p.equip_item(item_object=item)

    assert item not in container.inventory
    container.refresh_description.assert_called_once()


# ---------------------------------------------------------------------------
# equip_item — testing_mode exp path (lines 235-245)
# ---------------------------------------------------------------------------


def test_equip_item_testing_mode_with_starting_exp():
    """In testing_mode with starting_exp, skill_exp is set to starting_exp."""
    p = _make_player()
    p.weight_tolerance = 100.0
    p.weight_current = 0.0
    p.testing_mode = True
    p.game_config = MagicMock()
    p.game_config.starting_exp = 500

    item = _make_equippable()
    item.isequipped = False
    item.gives_exp = True
    item.subtype = "Sword"
    p.combat_exp = {}
    p.skill_exp = {}
    p.inventory = [item]

    with patch("src.player._inventory.cprint"):
        with patch("src.player._inventory.functions") as mock_funcs:
            mock_funcs.refresh_stat_bonuses = MagicMock()
            p.refresh_protection_rating = MagicMock()
            p.equip_item(item_object=item)

    assert p.skill_exp.get("Sword") == 500


def test_equip_item_testing_mode_no_starting_exp():
    """In testing_mode without starting_exp, skill_exp is set to 9999."""
    p = _make_player()
    p.weight_tolerance = 100.0
    p.weight_current = 0.0
    p.testing_mode = True
    p.game_config = MagicMock()
    p.game_config.starting_exp = 0

    item = _make_equippable()
    item.isequipped = False
    item.gives_exp = True
    item.subtype = "Bow"
    p.combat_exp = {}
    p.skill_exp = {}
    p.inventory = [item]

    with patch("src.player._inventory.cprint"):
        with patch("src.player._inventory.functions") as mock_funcs:
            mock_funcs.refresh_stat_bonuses = MagicMock()
            p.refresh_protection_rating = MagicMock()
            p.equip_item(item_object=item)

    assert p.skill_exp.get("Bow") == 9999


# ---------------------------------------------------------------------------
# equip_item — already equipped, unequip path (lines 167-186)
# ---------------------------------------------------------------------------


def test_equip_item_already_equipped_keep():
    """When item is already equipped and user says 'n', it stays equipped."""
    p = _make_player()
    item = _make_equippable(maintype="Armor")
    item.isequipped = True
    item.interactions = ["unequip"]
    p.inventory = [item]

    with patch("builtins.input", return_value="n"):
        with patch("src.player._inventory.cprint"):
            p.equip_item(item_object=item)

    assert item.isequipped is True


# ---------------------------------------------------------------------------
# equip_item — accessory subtype replacement logic (lines 195-208)
# ---------------------------------------------------------------------------


def test_equip_item_accessory_ring_replaces_third():
    """A third Ring replaces the second Ring (count > 1 triggers replace_old)."""
    p = _make_player()
    p.weight_tolerance = 100.0
    p.weight_current = 0.0

    ring1 = _make_equippable(maintype="Accessory", subtype="Ring", name="Ring1")
    ring1.isequipped = True
    ring1.interactions = ["unequip"]

    ring2 = _make_equippable(maintype="Accessory", subtype="Ring", name="Ring2")
    ring2.isequipped = True
    ring2.interactions = ["unequip"]

    new_ring = _make_equippable(maintype="Accessory", subtype="Ring", name="Ring3")
    new_ring.isequipped = False
    new_ring.gives_exp = False

    p.inventory = [ring1, ring2, new_ring]

    with patch("src.player._inventory.cprint"):
        with patch("src.player._inventory.functions") as mock_funcs:
            mock_funcs.refresh_stat_bonuses = MagicMock()
            p.refresh_protection_rating = MagicMock()
            p.equip_item(item_object=new_ring)

    # At least one of the old rings should have been unequipped
    unequipped = [i for i in [ring1, ring2] if not i.isequipped]
    assert len(unequipped) >= 1


def test_equip_item_accessory_non_ring_replaces():
    """A second Necklace replaces the first (non-Ring/Bracelet/Earring logic)."""
    p = _make_player()
    p.weight_tolerance = 100.0
    p.weight_current = 0.0

    old_neck = _make_equippable(
        maintype="Accessory", subtype="Necklace", name="OldNeck"
    )
    old_neck.isequipped = True
    old_neck.interactions = ["unequip"]

    new_neck = _make_equippable(
        maintype="Accessory", subtype="Necklace", name="NewNeck"
    )
    new_neck.isequipped = False
    new_neck.gives_exp = False

    p.inventory = [old_neck, new_neck]

    with patch("src.player._inventory.cprint"):
        with patch("src.player._inventory.functions") as mock_funcs:
            mock_funcs.refresh_stat_bonuses = MagicMock()
            p.refresh_protection_rating = MagicMock()
            p.equip_item(item_object=new_neck)

    assert old_neck.isequipped is False
    assert new_neck.isequipped is True


# ---------------------------------------------------------------------------
# equip_item — no hasattr isequipped (no-op path)
# ---------------------------------------------------------------------------


def test_equip_item_no_isequipped_attribute():
    """equip_item ignores non-equippable items entirely."""
    p = _make_player()
    item = MagicMock(spec=[])  # no isequipped -> not equippable
    item.name = "Rock"
    p.current_room.items_here = [item]
    p.inventory = []
    weapon_before = p.eq_weapon

    p.equip_item(item_object=item)

    # Not picked up, not equipped, no weapon slot change.
    assert p.inventory == []
    assert p.current_room.items_here == [item]
    assert p.eq_weapon is weapon_before


# ---------------------------------------------------------------------------
# use_item — phrase path
# ---------------------------------------------------------------------------


def test_use_item_by_phrase_merchandise_skipped():
    """use_item skips merchandise but still uses a later legitimate match."""
    p = _make_player()
    merch_potion = _make_consumable("Healing Potion")
    merch_potion.merchandise = True
    owned_potion = _make_consumable("Healing Potion")
    p.inventory = [merch_potion, owned_potion]

    p.use_item(phrase="healing")

    merch_potion.use.assert_not_called()
    owned_potion.use.assert_called_once_with(p, user=p)


def test_use_item_by_phrase_uses_first_match_on_self():
    """A phrase match consumes the item with the player as both target and user."""
    p = _make_player()
    potion = _make_consumable("Healing Potion")
    p.inventory = [potion]

    p.use_item(phrase="healing")

    potion.use.assert_called_once_with(p, user=p)


def test_use_item_routes_effect_to_explicit_target():
    """An explicit target receives the effect; the player remains the user."""
    p = _make_player()
    ally = MagicMock()
    potion = _make_consumable("Healing Potion")
    p.inventory = [potion]

    p.use_item(phrase="healing", target=ally)

    potion.use.assert_called_once_with(ally, user=p)


def test_use_item_stops_after_first_match():
    """Only the first matching item is used, never the whole matching set."""
    p = _make_player()
    first = _make_consumable("Healing Potion")
    second = _make_consumable("Healing Draught")
    p.inventory = [first, second]

    p.use_item(phrase="healing")

    first.use.assert_called_once_with(p, user=p)
    second.use.assert_not_called()


def test_use_item_ignores_non_consumable_matches():
    """Items that are neither Consumable nor Special are never 'used'."""
    p = _make_player()
    sword = _make_equippable(name="Healing Blade")
    sword.use = MagicMock()
    p.inventory = [sword]

    p.use_item(phrase="healing")

    sword.use.assert_not_called()


def test_use_item_without_phrase_is_a_noop():
    """No phrase means no item is used — there is no terminal selection menu."""
    p = _make_player()
    potion = _make_consumable("Potion")
    p.inventory = [potion]
    p.preferences = {}
    p.in_combat = False

    assert p.use_item(phrase="") is None

    potion.use.assert_not_called()
    assert p.inventory == [potion]


def test_use_item_never_prompts_for_terminal_input():
    """Regression guard: the terminal item menu is gone; use_item must not read stdin."""
    p = _make_player()
    potion = _make_consumable("Healing Potion")
    p.inventory = [potion]

    def _boom(*_a, **_kw):
        raise AssertionError("use_item must not call input()")

    with patch("builtins.input", side_effect=_boom):
        p.use_item(phrase="")
        p.use_item(phrase="healing")

    potion.use.assert_called_once_with(p, user=p)


# ---------------------------------------------------------------------------
# refresh_weight
# ---------------------------------------------------------------------------


def test_refresh_weight_sums_items():
    """refresh_weight correctly totals weights including stacked items."""
    p = _make_player()
    item_a = MagicMock()
    item_a.weight = 2.5
    item_a.count = 3
    item_b = MagicMock()
    item_b.weight = 1.0
    del item_b.count  # no count attribute

    p.inventory = [item_a, item_b]
    p.refresh_weight()

    assert p.weight_current == round(2.5 * 3 + 1.0, 2)


# ---------------------------------------------------------------------------
# add_items_to_inventory
# ---------------------------------------------------------------------------


def test_add_items_to_inventory_weight_exceeded():
    """add_items_to_inventory drops item on ground when too heavy."""
    p = _make_player()
    p.weight_tolerance = 2.0
    p.weight_current = 1.8
    p.current_room.items_here = []

    heavy = MagicMock()
    heavy.name = "Lead Block"
    heavy.weight = 1.0
    heavy.count = 1
    del heavy.count  # no count attribute, test weight without count branch

    with patch("src.player._inventory.cprint"):
        p.add_items_to_inventory([heavy])

    assert heavy not in p.inventory
    assert heavy in p.current_room.items_here


def test_add_items_to_inventory_batch_respects_running_weight():
    """A batch cannot collectively exceed weight_tolerance.

    Two 15-weight items under a 20 capacity: the first is accepted, the second
    must be dropped once the running weight is accounted for (regression for the
    stale-weight-cap bug where both passed against the original free capacity).
    """
    p = _make_player()
    p.weight_tolerance = 20.0
    p.weight_current = 0.0
    p.inventory = []
    p.current_room.items_here = []

    first = MagicMock()
    first.name = "Boulder A"
    first.weight = 15.0
    del first.count
    second = MagicMock()
    second.name = "Boulder B"
    second.weight = 15.0
    del second.count

    with patch("src.player._inventory.cprint"):
        with patch("src.player._inventory.narrate"):
            p.add_items_to_inventory([first, second])

    assert first in p.inventory
    assert second not in p.inventory
    assert second in p.current_room.items_here


def test_add_items_to_inventory_already_in_inventory():
    """add_items_to_inventory doesn't add duplicates."""
    p = _make_player()
    p.weight_tolerance = 100.0
    p.weight_current = 0.0

    item = MagicMock()
    item.name = "Sword"
    item.weight = 1.0
    del item.count

    p.inventory = [item]

    with patch("builtins.print"):
        p.add_items_to_inventory([item])

    # Should still be in inventory exactly once
    assert p.inventory.count(item) == 1


def test_add_items_to_inventory_stacked_item():
    """add_items_to_inventory includes item label with count when count > 1."""
    p = _make_player()
    p.weight_tolerance = 100.0
    p.weight_current = 0.0

    item = MagicMock()
    item.name = "Arrow"
    item.weight = 0.1
    item.count = 5

    captured_prints = []
    with patch("builtins.print", side_effect=lambda *a: captured_prints.append(a)):
        p.add_items_to_inventory([item])

    assert item in p.inventory
    # Should mention (x5) in the print
    assert any("x5" in str(arg) for args in captured_prints for arg in args)


# ---------------------------------------------------------------------------
# stack_inv_items
# ---------------------------------------------------------------------------


def test_stack_inv_items_calls_function():
    """stack_inv_items delegates to functions.stack_inv_items."""
    p = _make_player()
    with patch("src.player._inventory.stack_inv_items") as mock_stack:
        p.stack_inv_items()
    mock_stack.assert_called_once_with(p)
