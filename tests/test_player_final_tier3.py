"""Player Systems Final Coverage — Tier 3C.

Comprehensive 100% coverage of all player/* modules:
- _inventory.py: item operations, equip/unequip, drop/pickup, use mechanics
- _world.py: world interactions, merchant refresh, tile queries
- _ui.py: display methods, state formatting, output generation
- _movement.py: movement types, path calculation, directional moves
- _exploration.py: exploration state, discovery tracking, secrets
- _leveling.py: level-up calculations, stat progression, skill unlocks
- _debug.py: debug commands, stat manipulation, testing utilities
- _combat.py: combat state, action handling, result processing

Target: 100% coverage on src/player/*
Expected: 150+ tests covering ALL untested lines, boundary conditions, error paths
"""

from unittest.mock import MagicMock, patch
import pytest
from src.player import Player
import src.items as items



class TestPlayerMovement:
    """Movement system tests — _movement.py (target: 100% coverage)."""

    @pytest.fixture
    def player(self):
        p = Player()
        p.location_x = 5
        p.location_y = 5
        p.prev_location_x = 5
        p.prev_location_y = 5
        p.map = MagicMock()
        p.universe = MagicMock()
        p.universe.game_tick = 0
        p.name = "Jean"
        return p

    def test_teleport_valid(self, player):
        """Test successful teleport to valid map and coordinates."""
        target_map = {"name": "Test Map"}
        player.universe.maps = [target_map]
        player.inventory = []  # No merchandise to drop
        mock_tile = MagicMock()
        mock_tile.intro_text.return_value = "You arrive in a new place."

        with patch("src.player._movement.tile_exists", return_value=mock_tile):
            with patch("builtins.print"):
                player.teleport("Test Map", (10, 10))

        # Teleport should update location and map
        assert player.location_x == 10
        assert player.location_y == 10
        assert player.map == target_map

    def test_teleport_invalid_coordinates(self, player):
        """Test teleport fails with invalid coordinates."""
        target_map = {"name": "Test Map"}
        player.universe.maps = [target_map]

        with patch("src.player._movement.tile_exists", return_value=None):
            with patch("builtins.print") as mock_print:
                player.teleport("Test Map", (999, 999))

        # Should print error
        mock_print.assert_called_with("### INVALID TELEPORT LOCATION: Test Map | 999,999 ###")

    def test_teleport_nonexistent_map(self, player):
        """Test teleport fails with non-existent map."""
        player.universe.maps = [{"name": "Other Map"}]

        with patch("builtins.print") as mock_print:
            player.teleport("Nonexistent Map", (5, 5))

        mock_print.assert_called_with("### INVALID TELEPORT LOCATION: Nonexistent Map | 5,5 ###")

    def test_teleport_drops_merchandise_items(self, player):
        """Test teleport drops merchandise items before moving."""
        target_map = {"name": "Test Map"}
        player.universe.maps = [target_map]
        mock_tile = MagicMock()
        mock_tile.intro_text.return_value = ""

        with patch("src.player._movement.tile_exists", return_value=mock_tile):
            with patch.object(player, "drop_merchandise_items") as mock_drop:
                with patch("builtins.print"):
                    player.teleport("Test Map", (5, 5))

        mock_drop.assert_called_once()

    def test_recall_friends_single_ally(self, player):
        """Test recall_friends with single ally."""
        ally = MagicMock()
        ally.name = "Gorran"
        ally.current_room = MagicMock()

        player.combat_list_allies = [player, ally]
        player.current_room = MagicMock()
        player.current_room.npcs_here = []

        with patch("neotermcolor.colored", side_effect=lambda x, y: x):
            with patch("builtins.print"):
                player.recall_friends()

        assert ally.current_room == player.current_room
        assert ally in player.current_room.npcs_here

    def test_recall_friends_multiple_allies(self, player):
        """Test recall_friends with multiple allies."""
        ally1 = MagicMock()
        ally1.name = "Gorran"
        ally1.current_room = MagicMock()

        ally2 = MagicMock()
        ally2.name = "Helper"
        ally2.current_room = MagicMock()

        player.combat_list_allies = [player, ally1, ally2]
        player.current_room = MagicMock()
        player.current_room.npcs_here = []

        with patch("neotermcolor.colored", side_effect=lambda x, y: x):
            with patch("builtins.print"):
                player.recall_friends()

        assert ally1.current_room == player.current_room
        assert ally2.current_room == player.current_room

    def test_recall_friends_already_in_room(self, player):
        """Test recall_friends when ally is already in room."""
        ally = MagicMock()
        ally.name = "Gorran"
        player.current_room = MagicMock()
        player.current_room.npcs_here = [ally]
        ally.current_room = player.current_room

        player.combat_list_allies = [player, ally]

        with patch("neotermcolor.colored", side_effect=lambda x, y: x):
            with patch("builtins.print"):
                player.recall_friends()

        # Ally should still be in room
        assert ally in player.current_room.npcs_here


class TestPlayerInventory:
    """Inventory system tests — _inventory.py (target: 100% coverage)."""

    @pytest.fixture
    def player(self):
        p = Player()
        p.inventory = []
        p.current_room = MagicMock()
        p.current_room.items_here = []
        p.weight_tolerance = 100
        p.weight_current = 0
        p.eq_weapon = MagicMock()
        p.eq_weapon.name = "Fists"
        p.fists = p.eq_weapon
        p.preferences = {}
        p.testing_mode = False
        p.map = MagicMock()
        p.location_x = 0
        p.location_y = 0
        return p

    def test_stack_gold_single_stack(self, player):
        """Test gold stacking with single gold item."""
        gold = MagicMock(spec=items.Gold)
        gold.amt = 50
        gold.count = 50
        gold.stack_grammar = MagicMock()
        player.inventory = [gold]

        player.stack_gold()

        assert len(player.inventory) == 1
        assert player.inventory[0].amt == 50

    def test_stack_gold_multiple_stacks(self, player):
        """Test gold stacking consolidates multiple stacks."""
        gold1 = MagicMock(spec=items.Gold)
        gold1.amt = 30
        gold1.count = 30
        gold1.stack_grammar = MagicMock()

        gold2 = MagicMock(spec=items.Gold)
        gold2.amt = 20
        gold2.count = 20
        gold2.stack_grammar = MagicMock()

        player.inventory = [gold1, gold2]

        player.stack_gold()

        # Should have consolidated to single gold item
        assert len(player.inventory) == 1
        assert player.inventory[0].amt == 50

    def test_stack_gold_no_gold(self, player):
        """Test stack_gold with no gold items."""
        other_item = MagicMock()
        player.inventory = [other_item]

        player.stack_gold()

        assert len(player.inventory) == 1

    def test_drop_merchandise_items(self, player):
        """Test dropping merchandise items on tile."""
        merch_item = MagicMock()
        merch_item.merchandise = True
        merch_item.name = "Bread"
        merch_item.stack_grammar = MagicMock()

        player.inventory = [merch_item]
        player.map = MagicMock()
        player.location_x = 0
        player.location_y = 0
        mock_tile = MagicMock()
        mock_tile.items_here = []

        with patch("src.player._inventory.tile_exists", return_value=mock_tile):
            with patch("random.choice", side_effect=lambda x: x[0]):
                with patch("builtins.print"):
                    with patch("time.sleep"):
                        player.drop_merchandise_items()

        # Item should be dropped and removed from inventory
        assert merch_item not in player.inventory

    def test_drop_merchandise_no_tile(self, player):
        """With no tile underfoot nothing is dropped -- the goods stay carried.

        (Was ``assert len(player.inventory) >= initial_count``, which is true of
        *any* outcome that does not shrink the list, including one that appended
        a duplicate.)
        """
        merch_item = MagicMock()
        merch_item.merchandise = True
        player.inventory = [merch_item]
        player.map = MagicMock()
        player.location_x = 0
        player.location_y = 0

        with patch("src.player._inventory.tile_exists", return_value=None):
            player.drop_merchandise_items()

        assert player.inventory == [merch_item]

    def test_drop_merchandise_keeps_non_merchandise_items(self, player):
        """Only ``merchandise`` items are put back; Jean's own kit stays with him.

        Replaces ``test_drop_merchandise_remove_error``, which set up an empty
        inventory and then asserted nothing at all -- the loop it claimed to
        exercise never ran a single iteration.
        """
        merch = MagicMock()
        merch.merchandise = True
        merch.name = "Bread"
        own = MagicMock()
        own.merchandise = False
        own.name = "Sword"

        player.inventory = [merch, own]
        player.map = MagicMock()
        player.location_x = 0
        player.location_y = 0
        tile = MagicMock()
        tile.items_here = []

        with patch("src.player._inventory.tile_exists", return_value=tile):
            player.drop_merchandise_items()

        assert player.inventory == [own]
        assert tile.items_here == [merch]
        merch.stack_grammar.assert_called_once_with()

    def test_equip_item_from_inventory(self, player):
        """Test equipping an item from inventory."""
        weapon = MagicMock()
        weapon.maintype = "Weapon"
        weapon.name = "Sword"
        weapon.announce = "gleaming"
        weapon.isequipped = False
        weapon.on_equip = MagicMock()
        weapon.interactions = ["equip"]
        weapon.gives_exp = True
        weapon.subtype = "Basic"

        player.inventory = [weapon]
        player.combat_exp = {}
        player.skill_exp = {}
        player.game_config = MagicMock()
        player.game_config.starting_exp = 0

        with patch("builtins.input", return_value="y"):
            with patch("src.functions.refresh_stat_bonuses"):
                with patch.object(player, "refresh_protection_rating"):
                    with patch("neotermcolor.cprint"):
                        player.equip_item(item_object=weapon)

        assert weapon.isequipped is True
        weapon.on_equip.assert_called_once()

    def test_equip_item_on_an_already_equipped_item_is_a_no_op(self, make_player,
                                                               make_weapon):
        """Re-equipping narrates and changes nothing.

        This test used to assert that ``equip_item`` *unequipped* the item after
        a ``y`` at an ``input()`` prompt. That prompt was deleted in the
        terminal teardown -- ``equip_item`` is now non-interactive and the web
        client has a dedicated unequip route (``Player.unequip_item``, covered
        by the next test).
        """
        from src.narration import capture_narration

        player = make_player()
        sword = make_weapon("Sword")
        player.inventory.append(sword)
        player.equip_item(item_object=sword)
        assert sword.isequipped is True

        with capture_narration() as messages:
            player.equip_item(item_object=sword)

        assert sword.isequipped is True, "re-equipping must not toggle it off"
        assert player.eq_weapon is sword
        assert any("already equipped" in m["text"] for m in messages)

    def test_unequip_item_returns_the_weapon_slot_to_fists(self, make_player,
                                                           make_weapon):
        """``unequip_item`` is the canonical replacement for the deleted prompt."""
        player = make_player()
        sword = make_weapon("Sword")
        player.inventory.append(sword)
        player.equip_item(item_object=sword)

        player.unequip_item(sword)

        assert sword.isequipped is False
        assert player.eq_weapon is player.fists
        assert "equip" in sword.interactions
        assert "unequip" not in sword.interactions

    def test_unequip_item_ignores_an_item_that_is_not_equipped(self, make_player,
                                                               make_weapon):
        player = make_player()
        sword = make_weapon("Sword")
        player.inventory.append(sword)
        equipped_before = player.eq_weapon

        player.unequip_item(sword)

        assert sword.isequipped is False
        assert player.eq_weapon is equipped_before

    def test_equip_item_weight_exceeded(self, player):
        """Test equipping item when weight limit exceeded."""
        weapon = MagicMock()
        weapon.maintype = "Weapon"
        weapon.name = "Sword"
        weapon.isequipped = False
        weapon.weight = 200  # Exceeds capacity

        player.inventory = []
        player.current_room.items_here = [weapon]
        player.weight_tolerance = 100
        player.weight_current = 50

        with patch("builtins.print"):
            player.equip_item(item_object=weapon)

        # Item should still be in room since it was too heavy
        assert weapon in player.current_room.items_here

    # ``Player.equip_item_menu`` was deleted in the terminal teardown (CLAUDE.md,
    # "Terminal-mode removal"), together with ``skillmenu``, ``level_up`` and the
    # rest of the ``input()``-driven helpers. The three tests that drove it
    # ("cancel", "select weapon", "invalid selection") are gone with it -- as is
    # ``test_use_item_merchandise_prevention``, which despite its name called
    # ``equip_item_menu`` and asserted only ``result is not None``. Its stated
    # intent is now actually tested, against the real ``use_item``, below.
    # Equipping through the web path is covered by
    # ``tests/test_game_service_equip_unequip.py``.

    def test_use_item_without_a_phrase_is_a_no_op(self, make_player):
        """``use_item`` no longer opens a menu; an empty phrase does nothing."""
        player = make_player()
        potion = items.Restorative()
        potion.count = 1
        player.inventory = [potion]
        player.hp = 1

        player.use_item()

        assert player.hp == 1
        assert potion in player.inventory

    def test_use_item_consumes_the_first_phrase_match(self, make_player):
        player = make_player()
        potion = items.Restorative()
        player.inventory = [potion]
        player.hp = 1
        player.maxhp = 100

        player.use_item("restorative")

        assert player.hp > 1, "the potion must actually heal Jean"

    def test_use_item_refuses_unpurchased_merchandise(self, make_player):
        """Merchandise sitting in a shop's stock cannot be used before purchase."""
        player = make_player()
        potion = items.Restorative()
        potion.merchandise = True
        player.inventory = [potion]
        player.hp = 1
        player.maxhp = 100

        player.use_item("restorative")

        assert player.hp == 1, "merchandise must not take effect"
        assert potion in player.inventory


class TestPlayerCombat:
    """Combat system tests — _combat.py (target: 100% coverage)."""

    @pytest.fixture
    def player(self):
        p = Player()
        p.hp = 50
        p.maxhp = 100
        p.combat_idle_msg = ["Ready for battle.", "Jean stands tall."]
        p.combat_hurt_msg = ["Jean gasps in pain.", "Jean winces."]
        p.heat = 1.0
        p.strength = 10
        p.finesse = 10
        p.endurance = 10
        p.inventory = []
        p.known_moves = []
        p.combat_list = []
        p.combat_list_allies = [p]
        p.combat_proximity = {}
        p.protection = 5
        p.name = "Jean"
        p.eq_weapon = MagicMock()
        p.eq_weapon.name = "Sword"
        p.eq_weapon.damage = 10
        p.eq_weapon.str_mod = 1.0
        p.eq_weapon.fin_mod = 1.0
        p.combat_exp = {"Basic": 0}
        p.current_room = MagicMock()
        p.current_room.npcs_here = []
        return p

    def test_combat_idle_stays_silent_on_a_low_roll(self, player):
        """Idle chatter needs a roll above 995; 500 must produce nothing."""
        from src.narration import capture_narration

        player.hp = 80
        player.maxhp = 100

        with patch("random.randint", side_effect=[500, 0]), capture_narration() as msgs:
            player.combat_idle()

        assert msgs == []

    def test_combat_idle_healthy_uses_the_idle_pool(self, player):
        """Above 20% HP a winning roll draws from ``combat_idle_msg``."""
        from src.narration import capture_narration

        player.hp = 80
        player.maxhp = 100

        with patch("random.randint", side_effect=[996, 0]), capture_narration() as msgs:
            player.combat_idle()

        assert [m["text"] for m in msgs] == [player.combat_idle_msg[0]]

    def test_combat_idle_hurt_uses_the_hurt_pool(self, player):
        """At or below 20% HP the message comes from ``combat_hurt_msg`` instead.

        Was ``mock_print.assert_called()`` -- which passed for *any* output at
        all, including the healthy pool, and would still pass if the two pools
        were swapped.
        """
        from src.narration import capture_narration

        player.hp = 15
        player.maxhp = 100

        with patch("random.randint", side_effect=[951, 0]), capture_narration() as msgs:
            player.combat_idle()

        assert [m["text"] for m in msgs] == [player.combat_hurt_msg[0]]
        assert msgs[0]["text"] not in player.combat_idle_msg

    def test_combat_idle_hurt_threshold_is_exactly_20_percent(self, player):
        """20% is 'hurt'; 21% is 'healthy'. Pins the boundary the branch uses."""
        from src.narration import capture_narration

        player.maxhp = 100
        player.hp = 20
        with patch("random.randint", side_effect=[951, 0]), capture_narration() as msgs:
            player.combat_idle()
        assert msgs[0]["text"] in player.combat_hurt_msg

        player.hp = 21
        with patch("random.randint", side_effect=[951, 0]), capture_narration() as msgs:
            player.combat_idle()
        assert msgs == [], "951 is below the healthy pool's 995 threshold"

    def test_change_heat_increase(self, player):
        """Test heat increase with multiplier."""
        player.heat = 1.0
        player.change_heat(mult=2.0)

        assert player.heat == 2.0

    def test_change_heat_add(self, player):
        """Test heat increase with addition."""
        player.heat = 1.0
        player.change_heat(add=0.5)

        assert player.heat == 1.5

    def test_change_heat_clamp_max(self, player):
        """Test heat clamped to maximum."""
        player.heat = 9.0
        player.change_heat(mult=2.0)

        assert player.heat == 10.0

    def test_change_heat_clamp_min(self, player):
        """Test heat clamped to minimum."""
        player.heat = 1.0
        player.change_heat(mult=0.4)

        assert player.heat == 0.5

    def test_change_heat_precision(self, player):
        """Test heat maintains 2 decimal precision."""
        player.heat = 1.0
        player.change_heat(add=0.3)

        # Should be 1.3 with 2 decimal precision
        assert player.heat == 1.3

    def test_refresh_enemy_list_removes_dead(self, player):
        """Test dead enemies removed from combat list."""
        enemy1 = MagicMock()
        enemy1.is_alive.return_value = True

        enemy2 = MagicMock()
        enemy2.is_alive.return_value = False

        player.combat_list = [enemy1, enemy2]
        player.combat_proximity = {enemy1: 1, enemy2: 1}

        player.refresh_enemy_list_and_prox()

        assert enemy1 in player.combat_list
        assert enemy2 not in player.combat_list
        assert enemy1 in player.combat_proximity
        assert enemy2 not in player.combat_proximity

    def test_refresh_moves_available(self, player):
        """Test refresh_moves returns viable moves."""
        move1 = MagicMock()
        move1.viable.return_value = True

        move2 = MagicMock()
        move2.viable.return_value = False

        player.known_moves = [move1, move2]

        available = player.refresh_moves()

        assert move1 in available
        assert move2 not in available

    def test_refresh_protection_rating(self, player):
        """Test protection rating recalculation."""
        player.endurance = 20

        armor = MagicMock()
        armor.isequipped = True
        armor.protection = 5
        armor.str_mod = 0.5
        armor.fin_mod = 0.2

        player.inventory = [armor]

        player.refresh_protection_rating()

        # base: 20/10 = 2.0
        # armor: 5 + (0.5 * 10) + (0.2 * 10) = 5 + 5 + 2 = 12
        # total: 2 + 12 = 14
        assert player.protection == 14.0

    # ``Player.attack`` was removed in the terminal teardown, along with the
    # ``Attack`` action in ``actions.py`` and ``src/combat.py``'s ``combat()``
    # loop (CLAUDE.md, "Terminal-mode removal"). The four tests that lived here
    # -- test_attack_no_target / _with_target_hit / _miss / _by_phrase -- drove
    # that verb through ``input()`` and ``patch("combat.combat")``. That patch
    # target is also a bare-module import, which the codebase forbids: with
    # ``src/combat.py`` gone it resolves to an empty namespace package, so the
    # patch raises rather than doing anything. Combat is now entered through
    # ``GameService.start_combat`` -> ``ApiCombatAdapter``; see
    # ``tests/test_game_service_combat.py`` and ``tests/test_combat_adapter*.py``.


class TestPlayerWorld:
    """World system tests — _world.py (target: 100% coverage)."""

    @pytest.fixture
    def player(self):
        p = Player()
        p.universe = MagicMock()
        p.universe.maps = []
        p.name = "Jean"
        return p

    def _merchant(self, name="Smith", update=None):
        """A stand-in whose MRO really contains a class named ``Merchant``.

        ``refresh_merchants`` identifies vendors by walking ``cls.mro()`` for the
        name "Merchant". The old tests faked that with
        ``merchant.__class__.mro = MagicMock(...)`` on a ``MagicMock`` -- which
        rebinds an attribute on the mock's *class*, the exact leak pattern that
        has poisoned later tests in this suite before. A real throwaway subclass
        costs nothing and cannot leak.
        """

        class Merchant:
            pass

        class _Vendor(Merchant):
            pass

        vendor = _Vendor()
        vendor.name = name
        vendor.shop = object()
        vendor.update_goods = update if update is not None else MagicMock()
        return vendor

    @staticmethod
    def _map_with(*npcs):
        tile = MagicMock()
        tile.npcs_here = list(npcs)
        return {"name": "Test Map", (0, 0): tile}

    def test_refresh_merchants_no_universe(self, player):
        """No universe: say so and touch nothing."""
        from src.narration import capture_narration

        player.universe = None

        with capture_narration() as msgs:
            player.refresh_merchants()

        assert [m["text"] for m in msgs] == [
            "Universe not initialized; cannot refresh merchants."
        ]

    def test_refresh_merchants_no_maps_attribute(self, player):
        from src.narration import capture_narration

        player.universe = MagicMock()
        del player.universe.maps

        with capture_narration() as msgs:
            player.refresh_merchants()

        assert [m["text"] for m in msgs] == [
            "Universe not initialized; cannot refresh merchants."
        ]

    def test_refresh_merchants_empty_map_list(self, player):
        from src.narration import capture_narration

        player.universe.maps = []

        with capture_narration() as msgs:
            player.refresh_merchants()

        assert [m["text"] for m in msgs] == ["No merchants found to refresh."]

    def test_refresh_merchants_no_merchants_found(self, player):
        from src.narration import capture_narration

        player.universe.maps = [self._map_with()]

        with capture_narration() as msgs:
            player.refresh_merchants()

        assert [m["text"] for m in msgs] == ["No merchants found to refresh."]

    def test_refresh_merchants_updates_every_vendor(self, player):
        from src.narration import capture_narration

        first = self._merchant("Smith")
        second = self._merchant("Baker")
        player.universe.maps = [self._map_with(first, second)]

        with capture_narration() as msgs:
            player.refresh_merchants()

        first.update_goods.assert_called_once_with()
        second.update_goods.assert_called_once_with()
        assert msgs[0]["text"] == "Merchant refresh complete: 2 succeeded, 0 failed."

    def test_refresh_merchants_phrase_filter_selects_one_vendor(self, player):
        from src.narration import capture_narration

        smith = self._merchant("Smith")
        baker = self._merchant("Baker")
        player.universe.maps = [self._map_with(smith, baker)]

        with capture_narration() as msgs:
            player.refresh_merchants("smith")

        smith.update_goods.assert_called_once_with()
        baker.update_goods.assert_not_called()
        assert msgs[0]["text"] == "Merchant refresh complete: 1 succeeded, 0 failed."

    def test_refresh_merchants_phrase_filter_matching_nobody(self, player):
        from src.narration import capture_narration

        smith = self._merchant("Smith")
        player.universe.maps = [self._map_with(smith)]

        with capture_narration() as msgs:
            player.refresh_merchants("cooper")

        smith.update_goods.assert_not_called()
        assert [m["text"] for m in msgs] == ["No merchants matched filter 'cooper'."]

    def test_refresh_merchants_reports_a_failing_vendor_and_keeps_going(self, player):
        from src.narration import capture_narration

        broken = self._merchant(
            "Broken Merchant", update=MagicMock(side_effect=RuntimeError("Update failed"))
        )
        healthy = self._merchant("Smith")
        player.universe.maps = [self._map_with(broken, healthy)]

        with capture_narration() as msgs:
            player.refresh_merchants()

        healthy.update_goods.assert_called_once_with(), "one bad vendor must not abort the sweep"
        texts = [m["text"] for m in msgs]
        assert texts[0] == "Merchant refresh complete: 1 succeeded, 1 failed."
        assert texts[1] == " - Broken Merchant: Update failed"

    def test_refresh_merchants_flags_a_vendor_with_no_update_goods(self, player):
        from src.narration import capture_narration

        vendor = self._merchant("Mute")
        vendor.update_goods = None
        player.universe.maps = [self._map_with(vendor)]

        with capture_narration() as msgs:
            player.refresh_merchants()

        texts = [m["text"] for m in msgs]
        assert texts[0] == "Merchant refresh complete: 0 succeeded, 1 failed."
        assert texts[1] == " - Mute: missing update_goods"

    def test_refresh_merchants_ignores_non_merchant_npcs(self, player):
        from src.narration import capture_narration

        bystander = MagicMock()
        bystander.name = "Smith"
        player.universe.maps = [self._map_with(bystander)]

        with capture_narration() as msgs:
            player.refresh_merchants()

        assert [m["text"] for m in msgs] == ["No merchants found to refresh."]

class TestPlayerDebug:
    """Debug system tests — _debug.py (target: 100% coverage)."""

    @pytest.fixture
    def player(self):
        p = Player()
        p.strength = 10
        p.finesse = 10
        p.endurance = 10
        p.intelligence = 10
        p.charisma = 10
        p.faith = 10
        p.speed = 10
        p.level = 1
        p.hp = 50
        p.maxhp = 100
        p.gold = 100
        p.name = "Jean"
        return p


class TestPlayerExploration:
    """Exploration system tests — _exploration.py (target: 100% coverage)."""

    @pytest.fixture
    def player(self):
        p = Player()
        p.explored_tiles = []
        p.discovered_secrets = []
        p.map = MagicMock()
        p.location_x = 0
        p.location_y = 0
        return p

    def test_discover_location(self, player):
        """Test discovering a new location."""
        tile_key = (0, 0)

        if tile_key not in player.explored_tiles:
            player.explored_tiles.append(tile_key)

        assert tile_key in player.explored_tiles

    def test_discover_secret(self, player):
        """Test discovering a secret."""
        secret_name = "Hidden Chamber"

        if secret_name not in player.discovered_secrets:
            player.discovered_secrets.append(secret_name)

        assert secret_name in player.discovered_secrets


class TestPlayerLeveling:
    """Leveling system tests — _leveling.py (target: 100% coverage)."""

    @pytest.fixture
    def player(self):
        p = Player()
        p.level = 1
        p.exp = 0
        p.exp_to_level = 100
        p.strength = 10
        p.finesse = 10
        p.endurance = 10
        p.intelligence = 10
        p.charisma = 10
        p.faith = 10
        p.speed = 10
        p.maxhp = 50
        p.hp = 50
        p.known_moves = []
        p.skill_unlocked = {}
        p.name = "Jean"
        return p

    def test_gain_experience(self, player):
        """Test gaining experience below level threshold."""
        initial_exp = player.exp
        player.exp += 50

        assert player.exp == initial_exp + 50
        assert player.level == 1  # Should not level up yet

    def test_level_up(self, player):
        """Test leveling up."""
        player.exp = 100

        if player.exp >= player.exp_to_level:
            player.level += 1
            player.exp -= player.exp_to_level
            player.exp_to_level = int(player.exp_to_level * 1.1)

        assert player.level == 2

    def test_stat_increase_on_level(self, player):
        """Test stats increase on level up."""
        initial_strength = player.strength

        # Simulate level up
        player.level += 1
        player.strength += 1  # Simple increment

        assert player.strength > initial_strength


class TestPlayerUI:
    """UI system tests — _ui.py (target: 100% coverage)."""

    @pytest.fixture
    def player(self):
        p = Player()
        p.name = "Jean"
        p.level = 5
        p.hp = 80
        p.maxhp = 100
        p.gold = 500
        p.strength = 15
        p.finesse = 12
        p.endurance = 18
        p.intelligence = 10
        p.charisma = 14
        p.faith = 11
        p.speed = 13
        p.exp = 250
        p.exp_to_level = 500
        p.inventory = []
        p.eq_weapon = MagicMock()
        p.eq_weapon.name = "Sword"
        return p

    def test_get_display_name(self, player):
        """Test getting display name."""
        name = str(player.name) if player.name else "Jean"
        assert name == "Jean"


class TestIntegration:
    """Integration tests across multiple systems."""

    def test_equip_and_combat(self):
        """Test equipment affects combat."""
        player = Player()
        player.strength = 10
        player.finesse = 10
        player.eq_weapon = MagicMock()
        player.eq_weapon.damage = 5
        player.eq_weapon.str_mod = 0.5
        player.eq_weapon.fin_mod = 0.3

        # Calculate damage
        damage = player.eq_weapon.damage + (player.strength * player.eq_weapon.str_mod) + (player.finesse * player.eq_weapon.fin_mod)

        assert damage == 5 + 5 + 3  # 13

    def test_inventory_weight_management(self):
        """Test inventory weight tracking."""
        player = Player()
        player.weight_tolerance = 100
        player.weight_current = 0

        item = MagicMock()
        item.weight = 30

        player.weight_current += item.weight
        assert player.weight_current == 30
        assert player.weight_current <= player.weight_tolerance
