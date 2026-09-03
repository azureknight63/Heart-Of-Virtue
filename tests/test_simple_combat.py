"""End-to-end combat-adapter initialization against **real** engine objects.

This file used to be a bare script: it built a ``MockPlayer``/``MockNPC`` at
import time, called ``initialize_combat`` inside a ``try``, and ``print``ed
either "TEST PASSED" or a traceback. It contained no test function and no
assertion, so pytest collected zero tests from it and it could not fail no
matter how badly the adapter broke -- a crash printed a traceback and the run
stayed green.

It is now the adapter's real-object smoke suite. Everything below drives a real
``Player`` and real ``NPC``s through ``ApiCombatAdapter`` and asserts on the
JSON the client actually receives, including the ``combat_id`` lifecycle the
client relies on to distinguish "new fight" from "same fight, next beat".
"""

import pytest

from src.api.combat_adapter import ApiCombatAdapter
from src.npc import Slime
from tests._combat_fixtures import engage, make_npc, make_player


def _alert_count(player, name):
    """How many "<name> appears!"-style roster alerts the log carries."""
    return sum(
        1
        for entry in player.combat_log
        if entry.get("type") == "system" and name in entry.get("message", "")
    )


@pytest.fixture
def player():
    return make_player()


@pytest.fixture
def slime():
    return make_npc(Slime, name="Test Slime", hp=20, maxhp=20)


@pytest.fixture
def adapter(player, slime):
    engage(player, [slime])
    adapter = ApiCombatAdapter(player)
    adapter.initialize_combat([slime])
    return adapter


class TestInitializeCombatPayload:
    """The shape and content of what ``initialize_combat`` hands the client."""

    def test_reports_combat_active_with_no_error(self, player, slime):
        engage(player, [slime])
        result = ApiCombatAdapter(player).initialize_combat([slime])

        assert "error" not in result, result.get("details")
        assert result["combat_active"] is True

    def test_opens_awaiting_a_move_selection(self, adapter):
        battle_state = adapter.get_combat_state()["battle_state"]

        assert battle_state["awaiting_input"] is True
        assert battle_state["input_type"] == "move_selection"

    def test_available_options_are_exactly_the_players_non_passive_moves(
        self, adapter, player
    ):
        options = adapter.get_combat_state()["battle_state"]["available_options"]

        assert options, "combat opened with no selectable move"
        offered = [opt["name"] for opt in options]
        expected = [
            move.name
            for move in player.known_moves
            if not getattr(move, "passive", False)
        ]
        # Passives are never castable and must not reach the move panel; every
        # other known move is listed (unavailable ones carry a reason, below).
        assert offered == expected

    def test_unavailable_options_carry_a_reason_and_available_ones_do_not(
        self, adapter
    ):
        options = adapter.get_combat_state()["battle_state"]["available_options"]

        # The panel greys out an option using `available`, and shows `reason`
        # as the tooltip -- an unavailable option with no reason renders as a
        # dead button with no explanation.
        for opt in options:
            if opt["available"]:
                assert opt["reason"] is None, opt["name"]
            else:
                assert opt["reason"], f"{opt['name']} unavailable with no reason"

    def test_option_index_round_trips_to_the_players_move_list(self, adapter, player):
        options = adapter.get_combat_state()["battle_state"]["available_options"]

        for opt in options:
            assert player.known_moves[opt["index"]].name == opt["name"]
            assert opt["id"] == str(opt["index"])

    def test_enemy_is_serialized_with_live_hp(self, adapter, slime):
        enemies = adapter.get_combat_state()["battle_state"]["enemies"]

        assert [e["name"] for e in enemies] == ["Test Slime"]
        assert enemies[0]["hp"] == 20
        assert enemies[0]["max_hp"] == 20

    def test_enemy_hp_in_payload_tracks_the_real_npc(self, adapter, slime):
        slime.hp = 7

        enemies = adapter.get_combat_state()["battle_state"]["enemies"]

        assert enemies[0]["hp"] == 7, "serializer cached hp instead of reading it live"

    def test_player_block_reflects_the_real_player(self, adapter, player):
        payload = adapter.get_combat_state()["battle_state"]["player"]

        assert payload["hp"] == player.hp
        assert payload["max_hp"] == player.maxhp
        assert payload["name"] == player.name

    def test_opening_log_is_populated(self, adapter):
        log = adapter.get_combat_state()["log"]

        assert log, "combat opened with an empty log"
        assert all("message" in entry for entry in log)


class TestInitializeCombatResetsPerFightState:
    """``initialize_combat`` is the reset point for per-fight bookkeeping."""

    def test_beat_resets_to_one(self, player, slime):
        player.combat_beat = 47
        engage(player, [slime])

        ApiCombatAdapter(player).initialize_combat([slime])

        assert player.combat_beat == 1

    def test_stale_log_from_a_previous_fight_is_cleared(self, player, slime):
        player.combat_log = [{"message": "from the last fight"}]
        engage(player, [slime])

        ApiCombatAdapter(player).initialize_combat([slime])

        assert all(
            entry.get("message") != "from the last fight"
            for entry in player.combat_log
        )

    def test_heat_resets_to_one(self, player, slime):
        player.heat = 3.5
        engage(player, [slime])

        ApiCombatAdapter(player).initialize_combat([slime])

        assert player.heat == 1.0

    def test_previous_drops_and_summary_are_cleared(self, player, slime):
        player.combat_drops = ["a stale drop"]
        player.combat_end_summary = "stale summary"
        engage(player, [slime])

        ApiCombatAdapter(player).initialize_combat([slime])

        assert player.combat_drops == []
        assert player.combat_end_summary is None


class TestCombatIdLifecycle:
    """``combat_id`` identifies a *fight*, not a call.

    The client uses it to tell "new fight" from "same fight, next beat", so the
    two rules below are a wire contract: it must survive a reinit (wave
    transition, reinforcement spawn -- still the same fight) and change only
    when a genuinely new combat starts.
    """

    def test_combat_id_is_published_inside_battle_state(self, adapter):
        state = adapter.get_combat_state()

        assert state["battle_state"]["combat_id"] == adapter.combat_id
        assert adapter.combat_id, "combat_id was never minted"
        # It rides in battle_state specifically, because transformCombatData
        # whitelists top-level keys and would silently drop it there.
        assert "combat_id" not in state

    def test_combat_id_is_stable_across_polls(self, adapter):
        first = adapter.get_combat_state()["battle_state"]["combat_id"]
        second = adapter.get_combat_state()["battle_state"]["combat_id"]

        assert first == second

    def test_reinit_keeps_the_same_combat_id(self, adapter, player, slime):
        original = adapter.combat_id
        reinforcement = make_npc(Slime, name="Reinforcement", hp=20, maxhp=20)
        player.combat_list.append(reinforcement)
        reinforcement.combat_list = [player]
        reinforcement.combat_list_allies = [slime, reinforcement]

        adapter.initialize_combat([slime, reinforcement], reinit=True)

        assert adapter.combat_id == original, (
            "a reinforcement spawn is the same fight; changing combat_id here "
            "makes the client tear down and rebuild the battlefield"
        )

    def test_reinit_does_not_re_announce_combatants_already_fighting(
        self, adapter, player, slime
    ):
        """Issue #506: "X appears!" is for arrivals, not for the roster.

        GameService's reinit path assigns the whole new roster rather than
        just the arrivals, so every combatant already on the battlefield came
        back through the alert loop and was announced again mid-fight.
        """
        reinforcement = make_npc(Slime, name="Reinforcement", hp=20, maxhp=20)
        player.combat_list.append(reinforcement)

        adapter.initialize_combat([slime, reinforcement], reinit=True)

        assert _alert_count(player, "Test Slime") == 1
        assert _alert_count(player, "Reinforcement") == 1

    def test_re_announcement_is_blocked_even_once_the_log_has_been_trimmed(
        self, adapter, player, slime
    ):
        """_add_log_entry's (message, round, source_id) dedup masked the
        duplicate only while the round-1 entries it compares against were
        still in the log; _trim_combat_log drops them in a long fight."""
        player.combat_log.clear()

        adapter.initialize_combat([slime], reinit=True)

        assert _alert_count(player, "Test Slime") == 0

    def test_a_reinforcement_is_announced_after_an_earlier_fighter_died(
        self, adapter, player, slime
    ):
        """The skip list must not swallow genuine arrivals.

        Tracking "already announced" by ``id()`` would: the dead combatant is
        dropped from the roster and can be freed, and CPython is free to hand
        the reinforcement the same address, whereupon its arrival is silently
        skipped. The adapter holds the combatants themselves for this reason.
        """
        player.combat_list.remove(slime)
        del slime
        player.combat_log.clear()

        reinforcement = make_npc(Slime, name="Reinforcement", hp=20, maxhp=20)
        player.combat_list.append(reinforcement)
        adapter.initialize_combat([reinforcement], reinit=True)

        assert _alert_count(player, "Reinforcement") == 1

    def test_a_new_fight_announces_the_roster_again(self, adapter, player, slime):
        """Who has been announced is per-fight state, like combat_id."""
        player.combat_log.clear()
        engage(player, [slime])

        adapter.initialize_combat([slime])

        assert _alert_count(player, "Test Slime") == 1

    def test_reinit_does_not_reset_the_beat(self, adapter, player, slime):
        player.combat_beat = 6

        adapter.initialize_combat([slime], reinit=True)

        assert player.combat_beat == 6

    def test_reinit_does_not_wipe_the_running_combat_log(self, adapter, player, slime):
        # combat_id, combat_beat and combat_log are reset together in the
        # `not reinit` branch. Losing the log mid-fight would blank the
        # client's scrollback on every reinforcement wave.
        player.combat_log.append(
            {"round": 6, "message": "Jean struck the Slime!", "type": "combat"}
        )

        adapter.initialize_combat([slime], reinit=True)

        assert any(
            entry["message"] == "Jean struck the Slime!"
            for entry in player.combat_log
        )

    def test_a_new_fight_clears_the_previous_fights_log_and_beat(
        self, adapter, player
    ):
        player.combat_beat = 9
        player.combat_log.append(
            {"round": 9, "message": "stale entry", "type": "combat"}
        )
        next_enemy = make_npc(Slime, name="Second Slime", hp=20, maxhp=20)
        engage(player, [next_enemy])

        adapter.initialize_combat([next_enemy])

        assert player.combat_beat == 1
        assert not any(
            entry["message"] == "stale entry" for entry in player.combat_log
        )

    def test_a_genuinely_new_fight_mints_a_new_combat_id(self, adapter, player):
        first = adapter.combat_id
        next_enemy = make_npc(Slime, name="Second Slime", hp=20, maxhp=20)
        engage(player, [next_enemy])

        adapter.initialize_combat([next_enemy])

        assert adapter.combat_id != first
        assert adapter.combat_id

    def test_combat_id_is_persisted_on_the_player_not_the_adapter(
        self, adapter, player, slime
    ):
        # The adapter is rebuilt per request; the id has to survive that or
        # every poll would look like a new fight to the client.
        rebuilt = ApiCombatAdapter(player)

        assert rebuilt.combat_id == adapter.combat_id
        assert player.combat_adapter_state["combat_id"] == adapter.combat_id


class TestPositionsAreEstablished:
    def test_both_sides_receive_grid_positions(self, adapter, player, slime):
        """Real coordinates inside the published grid, not just "not None".

        A spawner that dropped everyone on (0, 0) satisfies the old assertion
        and breaks every distance, facing and flanking calculation downstream.
        """
        width, height = adapter.combat_grid_size

        for unit in (player, slime):
            pos = unit.combat_position
            assert 0 <= pos.x <= width, (unit.name, pos.x)
            assert 0 <= pos.y <= height, (unit.name, pos.y)

        assert (player.combat_position.x, player.combat_position.y) != (
            slime.combat_position.x,
            slime.combat_position.y,
        ), "both combatants spawned on the same square"

    def test_proximity_is_symmetric_and_positive(self, adapter, player, slime):
        assert player.combat_proximity[slime] == slime.combat_proximity[player]
        assert player.combat_proximity[slime] > 0

    def test_grid_size_is_published_as_the_grid_width_scalar(self, adapter):
        state = adapter.get_combat_state()

        # `map_size` is the grid *width* as a bare int, not a (w, h) pair --
        # Battlefield reads `combat.map_size` as a scalar. It is republished
        # inside battle_state because transformCombatData's top-level whitelist
        # dropped the original top-level copy.
        assert state["battle_state"]["map_size"] == adapter.combat_grid_size[0]
        assert isinstance(state["battle_state"]["map_size"], int)
        assert state["battle_state"]["map_size"] > 0

    def test_spawn_coordinates_respect_the_engines_inclusive_grid_bound(
        self, adapter, player, slime
    ):
        width, height = adapter.combat_grid_size

        # The engine's grid bound is INCLUSIVE: CombatPosition.__post_init__
        # accepts `0 <= x <= bound` and clamp_position uses `min(max_w, x)`, so
        # a `width`-wide grid has width + 1 legal columns.
        #
        # KNOWN MISMATCH (reported, not fixed here): BattlefieldGrid.jsx treats
        # the same number as exclusive (`worldX < resolvedMapSize`, line ~1540),
        # so a combatant that spawns on the last legal column renders off-map.
        # This assertion pins the engine's actual behaviour rather than the
        # frontend's assumption; changing one without the other is the bug.
        for unit in (player, slime):
            assert 0 <= unit.combat_position.x <= width
            assert 0 <= unit.combat_position.y <= height
