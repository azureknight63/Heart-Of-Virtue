"""Swapping weapons mid-combat costs beats (#671).

The swap is a real ``Move`` -- ``SwapWeapon`` in ``src/moves/_utility.py`` --
cast through ``ApiCombatAdapter`` like any other, so its price is its own
``stage_beat`` and the beat/cooldown machinery charges it. The weapon choice is
a selection set as an attribute on the move (``move.weapon``) before its stage
runs, the same convention ``Wait.duration`` and ``Turn.target_direction`` use.
The equip itself is the engine's ``Player.equip_item``; nothing here
re-derives stats.

The free ``/inventory/equip`` side-route is closed to weapons for the length of
a fight, otherwise the beat cost could simply be walked around.
"""

from unittest.mock import MagicMock

import pytest

from src import items, moves
from src.api.combat_adapter import ApiCombatAdapter
from src.combatant import wire_handle
from src.moves import SwapWeapon, UseItem
from src.moves._utility import SWAP_WEAPON_STAGE_BEATS
from src.narration import capture_narration
from src.npc import Slime
from src.player import Player


def _armed_player():
    """Jean holding a Dagger with a Shortsword in his pack."""
    player = Player()
    dagger = items.Dagger()
    sword = items.Shortsword()
    player.inventory.extend([dagger, sword])
    with capture_narration():
        player.equip_item(item_object=dagger)
    assert player.eq_weapon is dagger, "fixture: dagger not equipped"
    return player, dagger, sword


def _swap_move(player):
    return next(m for m in player.known_moves if isinstance(m, SwapWeapon))


# ---------------------------------------------------------------------------
# The move itself
# ---------------------------------------------------------------------------


class TestSwapWeaponMove:
    def test_every_new_player_knows_it(self):
        assert any(isinstance(m, SwapWeapon) for m in Player().known_moves)

    def test_it_is_a_castable_utility_move_with_a_known_animation(self):
        move = SwapWeapon(Player())
        assert not move.passive
        assert move.category == "Utility"
        assert move.web_animation == "pulse"
        assert move.targeted is False

    def test_its_total_beat_cost_matches_use_item(self):
        """Digging a weapon out of the pack is priced like digging out a
        potion -- the same bag, the same hands."""
        player = Player()
        swap_total = sum(SwapWeapon(player).stage_beat)
        assert swap_total == sum(UseItem(player).stage_beat)
        assert swap_total > 0, "a free swap is the bug this issue exists to prevent"
        assert list(SWAP_WEAPON_STAGE_BEATS) == SwapWeapon(player).stage_beat

    def test_stage_beat_is_a_fresh_list_per_instance(self):
        """Moves mutate their own stage_beat (Wait, Disrupt); a shared tuple
        or list would leak one cast's changes into every other Jean."""
        a, b = SwapWeapon(Player()), SwapWeapon(Player())
        assert a.stage_beat is not b.stage_beat
        a.stage_beat[2] = 99
        assert b.stage_beat[2] == SWAP_WEAPON_STAGE_BEATS[2]

    def test_offers_only_unequipped_owned_weapons(self):
        player, dagger, sword = _armed_player()
        shop_axe = items.Shortsword(merchandise=True)
        potion = items.Restorative()
        player.inventory.extend([shop_axe, potion])
        assert _swap_move(player).swappable_weapons() == [sword]

    def test_not_viable_without_another_weapon(self):
        player = Player()
        dagger = items.Dagger()
        player.inventory.append(dagger)
        with capture_narration():
            player.equip_item(item_object=dagger)
        assert _swap_move(player).viable() is False

    def test_viable_with_another_weapon(self):
        player, _dagger, _sword = _armed_player()
        assert _swap_move(player).viable() is True

    def test_execute_equips_the_chosen_weapon_through_the_engine(self):
        player, dagger, sword = _armed_player()
        move = _swap_move(player)
        move.weapon = sword
        with capture_narration():
            move.execute(player)
        assert player.eq_weapon is sword
        assert sword.isequipped is True
        assert dagger.isequipped is False
        # Selection is consumed, so the next cast cannot silently reuse it.
        assert move.weapon is None

    def test_execute_without_a_selection_equips_nothing(self):
        """The adapter settles the choice before casting; the move itself
        never guesses (maintainer decision 2026-09-24)."""
        player, dagger, _sword = _armed_player()
        move = _swap_move(player)
        with capture_narration():
            move.execute(player)
        assert player.eq_weapon is dagger

    def test_a_stale_selection_equips_nothing_rather_than_an_unchosen_weapon(self):
        """A weapon that left the pack between choice and execute (sold,
        dropped, stolen) must not be equipped out of thin air -- and nor may
        a weapon the player never chose (maintainer decision 2026-09-24)."""
        player, dagger, _sword = _armed_player()
        ghost = items.Longsword()  # never in the inventory
        move = _swap_move(player)
        move.weapon = ghost
        with capture_narration():
            move.execute(player)
        assert ghost.isequipped is False
        assert player.eq_weapon is dagger

    def test_execute_with_nothing_to_swap_to_changes_nothing(self):
        player = Player()
        move = _swap_move(player)
        before = player.eq_weapon
        with capture_narration():
            move.execute(player)
        assert player.eq_weapon is before


# ---------------------------------------------------------------------------
# Adapter: cast/advance through the real beat machinery
# ---------------------------------------------------------------------------


def _combat(player):
    enemy = Slime()
    adapter = ApiCombatAdapter(player)
    with capture_narration():
        adapter.initialize_combat([enemy])
    player.combat_list = [enemy]
    player.combat_list_allies = [player]
    player.combat_proximity = {enemy: 30}
    return adapter, enemy


class TestSwapWeaponThroughAdapter:
    def test_select_weapon_swaps_and_spends_beats(self, monkeypatch):
        player, dagger, sword = _armed_player()
        adapter, _enemy = _combat(player)
        # Keep the Slime from acting so the only thing spending beats is the
        # swap (NPC moves roll unseeded dice).
        monkeypatch.setattr(adapter, "_process_npc_turns", lambda: None)
        beat_before = player.combat_beat

        with capture_narration():
            result = adapter.process_command(
                {"type": "select_weapon", "item_id": wire_handle(sword)}
            )

        assert "error" not in result, result
        assert player.eq_weapon is sword
        assert dagger.isequipped is False
        assert player.combat_beat - beat_before > 0, "the swap must cost beats"

    def test_the_swap_costs_what_use_item_costs(self, monkeypatch):
        player, _dagger, sword = _armed_player()
        adapter, _enemy = _combat(player)
        monkeypatch.setattr(adapter, "_process_npc_turns", lambda: None)
        start = player.combat_beat
        with capture_narration():
            adapter.process_command(
                {"type": "select_weapon", "item_id": wire_handle(sword)}
            )
        swap_cost = player.combat_beat - start

        other, _d, _s = _armed_player()
        other.inventory.append(items.Restorative())  # UseItem needs something to use
        other_adapter, _e = _combat(other)
        monkeypatch.setattr(other_adapter, "_process_npc_turns", lambda: None)
        start = other.combat_beat
        with capture_narration():
            used = other_adapter.process_command(
                {"type": "select_move_and_target", "move_name": "Use Item"}
            )
        assert "error" not in used, used
        assert swap_cost > 0
        assert swap_cost == other.combat_beat - start

    def test_an_unknown_weapon_is_refused_without_touching_state(self):
        player, dagger, _sword = _armed_player()
        adapter, _enemy = _combat(player)
        beat_before = player.combat_beat

        result = adapter.process_command(
            {"type": "select_weapon", "item_id": "not-a-handle"}
        )

        assert "error" in result
        assert player.eq_weapon is dagger
        assert player.current_move is None
        assert player.combat_beat == beat_before
        assert adapter.input_type == "move_selection"

    def test_the_equipped_weapon_is_not_a_swap_target(self):
        player, dagger, _sword = _armed_player()
        adapter, _enemy = _combat(player)
        result = adapter.process_command(
            {"type": "select_weapon", "item_id": wire_handle(dagger)}
        )
        assert "error" in result
        assert player.current_move is None

    @pytest.mark.parametrize("bad", [None, 7, "", ["x"]])
    def test_a_malformed_item_id_is_refused(self, bad):
        player, _dagger, _sword = _armed_player()
        adapter, _enemy = _combat(player)
        result = adapter.process_command({"type": "select_weapon", "item_id": bad})
        assert "error" in result
        assert player.current_move is None

    def test_select_weapon_outside_move_selection_is_refused(self):
        player, _dagger, sword = _armed_player()
        adapter, _enemy = _combat(player)
        adapter.input_type = "target_selection"
        result = adapter.process_command(
            {"type": "select_weapon", "item_id": wire_handle(sword)}
        )
        assert "error" in result

    def test_a_player_without_the_move_is_refused(self):
        """The adapter's own guard, should the move be missing mid-fight.
        (A fight backfills it for a pre-#671 save -- see the follow-ups.)"""
        player, dagger, sword = _armed_player()
        adapter, _enemy = _combat(player)
        player.known_moves = [m for m in player.known_moves if not isinstance(m, SwapWeapon)]
        result = adapter.process_command(
            {"type": "select_weapon", "item_id": wire_handle(sword)}
        )
        assert "error" in result
        assert player.eq_weapon is dagger

    def test_available_moves_publish_the_weapon_choices(self):
        player, _dagger, sword = _armed_player()
        adapter, _enemy = _combat(player)
        entry = next(
            m for m in adapter._get_available_moves() if m["name"] == "Swap Weapon"
        )
        assert entry["available"] is True
        assert entry["weapon_options"] == [
            {"id": wire_handle(sword), "name": sword.name}
        ]
        assert sum(entry["stage_beats"].values()) == sum(SWAP_WEAPON_STAGE_BEATS)

    def test_with_nothing_to_swap_to_the_move_is_unavailable(self):
        player = Player()
        adapter, _enemy = _combat(player)
        entry = next(
            m for m in adapter._get_available_moves() if m["name"] == "Swap Weapon"
        )
        assert entry["available"] is False
        assert entry["reason"]
        assert entry["weapon_options"] == []

    def test_other_moves_carry_no_weapon_options_key(self):
        player, _dagger, _sword = _armed_player()
        adapter, _enemy = _combat(player)
        wait = next(m for m in adapter._get_available_moves() if m["name"] == "Wait")
        assert "weapon_options" not in wait


# ---------------------------------------------------------------------------
# GameService: the free equip route is closed to weapons mid-fight
# ---------------------------------------------------------------------------


class TestEquipRouteCombatGate:
    def _service(self):
        from src.api.services.game_service import GameService

        return GameService()

    def test_weapon_equip_is_refused_in_combat(self):
        from src.api.services.game_service import _WEAPON_SWAP_IN_COMBAT_MESSAGE

        player, dagger, sword = _armed_player()
        player.in_combat = True
        result = self._service().equip_item(player, sword)
        assert result == {"error": _WEAPON_SWAP_IN_COMBAT_MESSAGE}
        assert player.eq_weapon is dagger
        assert sword.isequipped is False

    def test_weapon_unequip_toggle_is_refused_in_combat(self):
        """Unequipping drops Jean to fists -- a weapon change like any other."""
        player, dagger, _sword = _armed_player()
        player.in_combat = True
        assert "error" in self._service().equip_item(player, dagger)
        assert "error" in self._service().unequip_item(player, dagger)
        assert player.eq_weapon is dagger
        assert dagger.isequipped is True

    def test_the_refusal_names_the_move_that_does_it(self):
        from src.api.services.game_service import _WEAPON_SWAP_IN_COMBAT_MESSAGE

        assert SwapWeapon.display_name in _WEAPON_SWAP_IN_COMBAT_MESSAGE

    def test_weapon_equip_is_free_out_of_combat(self):
        player, _dagger, sword = _armed_player()
        player.in_combat = False
        result = self._service().equip_item(player, sword)
        assert result.get("success") is True
        assert player.eq_weapon is sword

    def test_non_weapon_equip_is_refused_with_the_general_message(self):
        """Armour is exploration-only too (maintainer rule 2026-09-24, see
        tests/test_ui_gated_paths.py) -- but it is not pointed at Swap Weapon."""
        from src.api.services.game_service import _NOT_DURING_COMBAT_MESSAGE

        player = Player()
        helm = items.ClothHood()
        player.inventory.append(helm)
        player.in_combat = True
        assert self._service().equip_item(player, helm) == {"error": _NOT_DURING_COMBAT_MESSAGE}

    def test_execute_move_routes_swap_weapon_to_the_adapter(self):
        service = self._service()
        player = Player()
        player.in_combat = True
        adapter = MagicMock()
        adapter.awaiting_input = True
        adapter.process_command.return_value = {"ok": True}
        player._combat_adapter = adapter

        result = service.execute_move(
            player, "swap_weapon", "", None, None, item_id="abc"
        )

        assert result == {"ok": True}
        adapter.process_command.assert_called_once_with(
            {"type": "select_weapon", "item_id": "abc"}
        )


def test_swap_weapon_is_reexported():
    assert "SwapWeapon" in moves.__all__


# ---------------------------------------------------------------------------
# Why it is locked (#627's reason vocabulary)
# ---------------------------------------------------------------------------


class TestSwapWeaponUnavailabilityReason:
    def test_an_empty_pack_names_the_missing_spare_weapon(self):
        from src.moves._base import UnavailableReason
        player = Player()
        move = _swap_move(player)
        assert not move.viable()
        assert move.unavailability_reason() is UnavailableReason.NO_SPARE_WEAPON

    def test_a_spare_weapon_leaves_no_reason(self):
        player, _dagger, _sword = _armed_player()
        move = _swap_move(player)
        assert move.viable()
        assert move.unavailability_reason() is None

    def test_the_adapter_ships_the_specific_sentence(self):
        from src.moves._base import UNAVAILABILITY_TEXT, UnavailableReason
        player = Player()
        from src.api.combat_adapter import move_unavailability
        code, text = move_unavailability(_swap_move(player), player, False)
        assert code == UnavailableReason.NO_SPARE_WEAPON
        assert text == UNAVAILABILITY_TEXT[UnavailableReason.NO_SPARE_WEAPON]


# ---------------------------------------------------------------------------
# Scrub follow-ups (maintainer decisions, 2026-09-24)
# ---------------------------------------------------------------------------


class TestSwapWeaponScrubFollowUps:
    def test_combat_backfills_the_move_for_a_player_who_lacks_it(self):
        """A Jean from a save that predates SwapWeapon is refused free equips
        mid-fight, so the fight must hand him the move that replaces them."""
        player, _dagger, _sword = _armed_player()
        player.known_moves = [m for m in player.known_moves if not isinstance(m, SwapWeapon)]
        _combat(player)
        assert sum(isinstance(m, SwapWeapon) for m in player.known_moves) == 1

    def test_backfill_does_not_duplicate_the_move(self):
        player, _dagger, _sword = _armed_player()
        _combat(player)
        assert sum(isinstance(m, SwapWeapon) for m in player.known_moves) == 1

    def test_a_cast_with_no_choice_is_refused_when_several_weapons_are_on_offer(self):
        player, dagger, _sword = _armed_player()
        player.inventory.append(items.Longsword())
        adapter, _enemy = _combat(player)
        with capture_narration():
            result = adapter.process_command(
                {"type": "select_move_and_target", "move_name": "Swap Weapon"}
            )
        assert "error" in result
        assert player.current_move is None
        assert player.eq_weapon is dagger

    def test_a_cast_with_no_choice_draws_the_only_weapon_on_offer(self, monkeypatch):
        player, _dagger, sword = _armed_player()
        adapter, _enemy = _combat(player)
        monkeypatch.setattr(adapter, "_process_npc_turns", lambda: None)
        with capture_narration():
            result = adapter.process_command(
                {"type": "select_move_and_target", "move_name": "Swap Weapon"}
            )
            for _ in range(sum(SWAP_WEAPON_STAGE_BEATS) + 2):
                if player.eq_weapon is sword:
                    break
                adapter.process_command({"type": "advance"})
        assert "error" not in result
        assert player.eq_weapon is sword

    def test_a_generic_cast_clears_a_stale_choice_left_by_an_aborted_swap(self):
        player, dagger, sword = _armed_player()
        longsword = items.Longsword()
        player.inventory.append(longsword)
        adapter, _enemy = _combat(player)
        _swap_move(player).weapon = longsword  # left over from an aborted swap
        with capture_narration():
            result = adapter.process_command(
                {"type": "select_move_and_target", "move_name": "Swap Weapon"}
            )
        assert "error" in result
        assert _swap_move(player).weapon is None
        assert player.eq_weapon is dagger

    def test_interact_equip_of_a_floor_weapon_is_refused_mid_fight(self):
        """The UI offers no interact panel in combat, so this path is API-only;
        it must not be a free weapon change that skips SwapWeapon's beats."""
        from tests._gs_fixtures import live_world
        from src.api.services.game_service import GameService, _WEAPON_SWAP_IN_COMBAT_MESSAGE

        player, game_map = live_world()
        dagger = items.Dagger()
        player.inventory.append(dagger)
        with capture_narration():
            player.equip_item(item_object=dagger)
        floor_axe = items.Longsword()
        game_map[(0, 0)].items_here.append(floor_axe)
        player.in_combat = True

        result = GameService().interact_with_target(player, wire_handle(floor_axe), "equip")

        assert result.get("success") is False
        assert result.get("message") == _WEAPON_SWAP_IN_COMBAT_MESSAGE
        assert player.eq_weapon is dagger
        assert floor_axe in game_map[(0, 0)].items_here


class TestSelectWeaponIdScoping:
    """``select_weapon`` resolves a REAL handle only within the move's own
    offer: a merchandise weapon in the pack and a weapon outside it both have
    valid wire handles, and both must be refused before any state changes."""

    @pytest.mark.parametrize("where", ["merchandise_in_pack", "not_in_pack"])
    def test_a_real_handle_outside_the_offer_is_refused(self, where):
        player, dagger, _sword = _armed_player()
        adapter, _enemy = _combat(player)
        outsider = items.Longsword(merchandise=True) if where == "merchandise_in_pack" else items.Longsword()
        if where == "merchandise_in_pack":
            player.inventory.append(outsider)
        beat_before = player.combat_beat

        result = adapter.process_command(
            {"type": "select_weapon", "item_id": wire_handle(outsider)}
        )

        assert "error" in result
        assert player.current_move is None
        assert player.combat_beat == beat_before
        assert player.eq_weapon is dagger
        assert outsider.isequipped is False
