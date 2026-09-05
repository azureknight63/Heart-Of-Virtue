"""Combat entry, exit and event dispatch, driven through a real fight.

History
-------
Every one of this file's 23 tests was ineffective, and most called the service
with the *wrong signature* — which is exactly why nobody noticed:

* ``start_combat(player, [enemy])`` — the real parameter is ``enemy_id``, the
  ``str(id(npc))`` of an NPC on the tile. A list never matches, so all four
  "start combat" tests were asserting ``isinstance`` on ``{"error": "Enemy not
  found"}``.
* ``trigger_combat_events(player, tile)`` — the second parameter is
  ``session_data``. The tile was silently accepted as a session dict.
* ``execute_move(player, [enemy], move)`` — the real signature is
  ``(player, move_type, move_id, ...)``.
* ``assert mock_combat_player.in_combat or True`` and ``assert "combat_started"
  in result or result is not None`` — tautologies that pass for any value.

A real fight is cheap to build in-process (a real ``Player``, a real ``Slime``,
a real ``ApiCombatAdapter``), so this file now starts one and asserts the state
transitions: combat enrolment, ``combat_id`` identity semantics, move-availability
gating, the flee distance rule, and the teardown flee performs. Damage numbers are
deliberately not asserted — hit rolls are random — but every structural invariant is.

``flee_combat`` coverage absorbed from the deleted ``test_game_service_additional.py``
(whose three flee tests asserted only ``isinstance(result, dict)``).
"""

import pytest

from src.events import Event
from src.npc import NPC, Slime
from src.api.serializers.combat import CombatantSerializer
from tests._gs_fixtures import GRID_3X3, live_world


@pytest.fixture
def world():
    return live_world(GRID_3X3)


@pytest.fixture
def player(world):
    return world[0]


@pytest.fixture
def tile(world):
    return world[1][(0, 0)]


@pytest.fixture
def slime(player, tile):
    """One real hostile NPC standing on the player's tile."""
    enemy = Slime()
    tile.npcs_here = [enemy]
    player.current_room = tile
    return enemy


def enemy_id(npc):
    """The id string ``start_combat`` matches against."""
    return str(id(npc))


def _move_index(player, move_name):
    """The adapter option index for ``move_name``, as a command string."""
    names = [o["name"] for o in player._combat_adapter.available_options]
    return str(names.index(move_name))


def _set_distance(player, enemy, paces):
    """Pin the combat distance on both sides (the opening roll is random)."""
    player.combat_proximity[enemy] = paces
    enemy.combat_proximity[player] = paces


class TestStartCombat:
    """``start_combat`` enrols the clicked enemy and every other hostile present."""

    def test_enrols_the_clicked_enemy(self, game_service, player, slime):
        result = game_service.start_combat(player, enemy_id(slime))

        assert player.in_combat is True
        assert player.combat_list == [slime]
        assert slime.in_combat is True and slime.aggro is True
        assert result["combat_active"] is True

    def test_unknown_enemy_id_is_an_error(self, game_service, player, slime):
        assert game_service.start_combat(player, "not-an-id") == {"error": "Enemy not found"}
        assert player.in_combat is not True

    def test_other_aggro_hostiles_join_the_fight(self, game_service, player, tile):
        clicked, bystander = Slime(), Slime()
        bystander.aggro = True
        tile.npcs_here = [clicked, bystander]
        player.current_room = tile

        game_service.start_combat(player, enemy_id(clicked))

        assert set(player.combat_list) == {clicked, bystander}
        # The clicked enemy leads the roster regardless of tile order.
        assert player.combat_list[0] is clicked

    def test_passive_hostiles_are_left_out(self, game_service, player, tile):
        clicked, dozing = Slime(), Slime()
        dozing.aggro = False
        tile.npcs_here = [clicked, dozing]
        player.current_room = tile

        game_service.start_combat(player, enemy_id(clicked))

        assert player.combat_list == [clicked]
        assert dozing.in_combat is not True

    def test_friendly_npcs_never_join_as_enemies(self, game_service, player, tile):
        clicked = Slime()
        ally = NPC(
            name="Gorran",
            description="A golemite.",
            damage=1,
            aggro=True,
            exp_award=0,
            friend=True,
        )
        tile.npcs_here = [clicked, ally]
        player.current_room = tile

        game_service.start_combat(player, enemy_id(clicked))

        assert player.combat_list == [clicked]

    def test_combatant_roster_lists_the_player_first(self, game_service, player, slime):
        result = game_service.start_combat(player, enemy_id(slime))

        assert result["combatants"][0] == {
            "id": "player",
            "name": player.name,
            "is_player": True,
            "is_ally": False,
        }
        assert result["combatants"][1]["id"] == CombatantSerializer.stream_id(slime)
        assert result["combatants"][1]["is_ally"] is False
        assert result["turn_order"] == [c["id"] for c in result["combatants"]]

    def test_starting_the_same_fight_twice_is_refused(self, game_service, player, slime):
        game_service.start_combat(player, enemy_id(slime))
        assert game_service.start_combat(player, enemy_id(slime)) == {
            "error": "Already in combat with these enemies"
        }

    def test_a_combat_adapter_is_attached(self, game_service, player, slime):
        game_service.start_combat(player, enemy_id(slime))
        adapter = player._combat_adapter
        assert adapter.awaiting_input is True
        assert adapter.input_type == "move_selection"
        assert "Attack" in [o["name"] for o in adapter.available_options]


class TestCombatIdentity:
    """``combat_id`` identifies a *fight*, not a call (CLAUDE.md)."""

    def test_published_id_matches_the_adapter_state(self, game_service, player, slime):
        result = game_service.start_combat(player, enemy_id(slime))
        adapter_id = player._combat_adapter.get_combat_state()["battle_state"]["combat_id"]
        assert result["combat_id"] == adapter_id
        assert result["combat_id"] is not None

    def test_id_is_stable_across_polls_of_the_same_fight(self, game_service, player, slime):
        first = game_service.start_combat(player, enemy_id(slime))["combat_id"]
        polled = game_service.get_combat_status(player)["battle_state"]["combat_id"]
        assert polled == first

    def test_a_new_fight_gets_a_new_id(self, game_service, player, tile):
        first_enemy = Slime()
        tile.npcs_here = [first_enemy]
        player.current_room = tile
        first_id = game_service.start_combat(player, enemy_id(first_enemy))["combat_id"]

        first_enemy.combat_proximity = {player: 40}
        game_service.flee_combat(player)

        second_enemy = Slime()
        tile.npcs_here = [second_enemy]
        second_id = game_service.start_combat(player, enemy_id(second_enemy))["combat_id"]

        assert second_id != first_id


class TestExecuteMove:
    """``execute_move`` routes a structured command into the adapter."""

    def test_not_in_combat_is_refused(self, game_service, player):
        assert game_service.execute_move(player, "move", "0") == {
            "success": False,
            "error": "Not in combat",
        }

    def test_a_pending_input_event_blocks_combat_actions(self, game_service, player, slime):
        game_service.start_combat(player, enemy_id(slime))
        session_data = {
            "pending_events": {
                "e1": {"event_data": {"needs_input": True, "completed": False}}
            }
        }

        result = game_service.execute_move(
            player, "move", "0", session_data=session_data
        )

        assert result["success"] is False
        assert result["error"] == "Event pending"
        assert result["pending_events_count"] == 1

    def test_stale_pending_events_are_cleared_not_blocking(
        self, game_service, player, slime
    ):
        game_service.start_combat(player, enemy_id(slime))
        session_data = {
            "pending_events": {
                "e1": {"event_data": {"needs_input": False, "completed": True}}
            }
        }

        game_service.execute_move(player, "move", "0", session_data=session_data)

        assert session_data["pending_events"] == {}

    def test_a_move_out_of_range_is_reported_unavailable(
        self, game_service, player, slime
    ):
        """Attack needs the enemy in reach; from 20 paces it is gated off.

        Opening distance is rolled per fight, so it is pinned explicitly here
        rather than assumed.
        """
        game_service.start_combat(player, enemy_id(slime))
        _set_distance(player, slime, 20)

        result = game_service.execute_move(player, "move", _move_index(player, "Attack"))

        assert result == {"error": "Move is not currently available"}

    def test_advancing_closes_the_distance(self, game_service, player, slime):
        game_service.start_combat(player, enemy_id(slime))
        _set_distance(player, slime, 20)

        result = game_service.execute_move(player, "move", _move_index(player, "Advance"))

        assert "error" not in result
        assert player.combat_proximity[slime] < 20

    def test_an_out_of_range_index_is_rejected(self, game_service, player, slime):
        game_service.start_combat(player, enemy_id(slime))
        result = game_service.execute_move(player, "move", "999")
        assert "error" in result
        # The fight is untouched by the bad command.
        assert player.in_combat is True


class TestFleeCombat:
    """``flee_combat`` — distance gate, then full teardown."""

    def test_not_in_combat_is_an_error(self, game_service, player):
        assert game_service.flee_combat(player) == {"error": "Not in combat"}

    def test_nearby_enemies_block_the_escape(self, game_service, player, slime):
        game_service.start_combat(player, enemy_id(slime))
        assert slime.combat_proximity[player] < 20

        result = game_service.flee_combat(player)

        assert result == {
            "success": False,
            "fled": False,
            "error": "Cannot flee — enemies are too close",
        }
        assert player.in_combat is True

    def test_distant_enemies_allow_the_escape(self, game_service, player, slime):
        game_service.start_combat(player, enemy_id(slime))
        slime.combat_proximity = {player: 40}

        result = game_service.flee_combat(player)

        assert result == {
            "success": True,
            "fled": True,
            "message": "Fled from combat successfully",
        }

    def test_escape_clears_player_combat_state(self, game_service, player, slime):
        game_service.start_combat(player, enemy_id(slime))
        slime.combat_proximity = {player: 40}

        game_service.flee_combat(player)

        assert player.in_combat is False
        assert player.combat_list == []
        assert player.current_move is None
        assert not hasattr(player, "_combat_adapter")

    def test_escape_disengages_the_enemies(self, game_service, player, slime):
        """Enemies must drop aggro, or they immediately re-engage on re-entry."""
        game_service.start_combat(player, enemy_id(slime))
        slime.combat_proximity = {player: 40}

        game_service.flee_combat(player)

        assert slime.in_combat is False
        assert slime.aggro is False

    def test_escape_strips_non_persistent_states(self, game_service, player, slime):
        game_service.start_combat(player, enemy_id(slime))
        slime.combat_proximity = {player: 40}

        transient = type("Transient", (), {"persistent": False, "name": "Rattled"})()
        lasting = type("Lasting", (), {"persistent": True, "name": "Poisoned"})()
        player.states = [transient, lasting]

        game_service.flee_combat(player)

        assert player.states == [lasting]

    def test_escape_is_repeatable_only_once(self, game_service, player, slime):
        game_service.start_combat(player, enemy_id(slime))
        slime.combat_proximity = {player: 40}
        game_service.flee_combat(player)
        assert game_service.flee_combat(player) == {"error": "Not in combat"}


class _CombatEvent(Event):
    """A real ``Event`` flagged ``combat_effect`` so the combat dispatcher picks it up."""

    def __init__(self, name="CombatEvent", output="The ground trembles."):
        super().__init__(name=name, combat_effect=True)
        self.fired = 0
        self.output = output

    def check_conditions(self):
        from src.narration import narrate

        self.fired += 1
        if self.output:
            narrate(self.output)


class TestTriggerCombatEvents:
    """``trigger_combat_events(player, session_data)`` — note the *second* argument."""

    def test_no_events_yields_an_empty_list(self, game_service, player, tile):
        tile.events_here = []
        player.combat_events = []
        assert game_service.trigger_combat_events(player) == []

    def test_a_combat_flagged_tile_event_fires(self, game_service, player, tile):
        event = _CombatEvent()
        tile.events_here = [event]

        result = game_service.trigger_combat_events(player)

        assert event.fired == 1
        assert len(result) == 1
        assert "The ground trembles." in result[0]["output_text"]

    def test_events_without_combat_effect_are_ignored(self, game_service, player, tile):
        class _Quiet(Event):
            def __init__(self):
                super().__init__(name="Quiet")
                self.fired = 0

            def check_conditions(self):
                self.fired += 1

        quiet = _Quiet()
        tile.events_here = [quiet]

        assert game_service.trigger_combat_events(player) == []
        assert quiet.fired == 0

    def test_a_silent_event_is_not_reported(self, game_service, player, tile):
        """Only events that actually produced something reach the client."""
        event = _CombatEvent(output="")
        tile.events_here = [event]

        assert game_service.trigger_combat_events(player) == []
        assert event.fired == 1

    def test_player_and_tile_are_rebound_onto_the_event(self, game_service, player, tile):
        """Session-loaded events can hold stale references."""
        event = _CombatEvent()
        event.player = None
        event.tile = None
        tile.events_here = [event]

        game_service.trigger_combat_events(player)

        assert event.player is player
        assert event.tile is tile

    def test_player_scoped_combat_events_also_fire(self, game_service, player, tile):
        tile.events_here = []
        event = _CombatEvent(name="Reinforcements")
        player.combat_events = [event]

        result = game_service.trigger_combat_events(player)

        assert event.fired == 1
        assert [e["name"] for e in result] == ["Reinforcements"]

    def test_a_raising_event_is_reported_not_propagated(self, game_service, player, tile):
        class _Exploding(Event):
            def check_conditions(self):
                raise RuntimeError("event boom")

        tile.events_here = [_Exploding(name="Boom", combat_effect=True)]

        # The error is recorded on the event data, but a silent failure produces
        # no output, so it is not surfaced as a triggered event.
        assert game_service.trigger_combat_events(player) == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
