"""
Integration tests for Tactical Strategist AI and Enhanced Combat Visualization.

These tests verify the complete flow from combat initialization through AI suggestions
to move execution and status effect display.
"""

import json
import threading
import time
from unittest.mock import patch

from src.combatant import wire_handle
from src.api.serializers.combat import CombatantSerializer


def create_mock_move(name="Attack"):
    """Create a simple mock move for testing."""
    class SimpleMockMove:
        def __init__(self):
            self.name = name
            self.fatigue_cost = 10
            self.current_stage = 0
            self.beats_left = 0
            self.targeted = True
            self.passive = False
            self.user = None
            self.target = None
            self.mvrange = (0, 5)
            self.verbose_targeting = False
            self.weight = 1 # Added for serialization
            self.current_beat = 0
            self.stage_beat = [1, 1, 1, 1]
            self.stage_announce = ["", "", "", ""]
            self.xp_gain = 0
            self.description = "Mock move"

        def viable(self):
            return True

        def cast(self):
            pass

        def advance(self, user):
            if self.current_stage > 0:
                self.current_stage = 0
                user.current_move = None

        def beats_until_resolve(self):
            """Mirror Move.beats_until_resolve — the serializer calls it.

            Real moves (src/moves/_base.py) all expose this; a double that
            doesn't is not a stand-in for one.
            """
            if self.current_stage not in (0, 1):
                return None
            return self.beats_left

    return SimpleMockMove()


def create_test_enemy(name, hp=30):
    """Create a test enemy with proper initialization."""
    from src.npc import NPC

    enemy = NPC(
        name=name,
        description=f"Test enemy: {name}",
        damage=5,
        aggro=True,
        exp_award=15,
        maxhp=hp,
        speed=5
    )
    enemy.known_moves = [create_mock_move()]
    enemy.friend = False
    enemy.default_proximity = 2
    return enemy


def ensure_player_room(player):
    """Ensure player has a current_room with npcs_here list."""
    if not hasattr(player, 'current_room') or player.current_room is None:
        class MockRoom:
            def __init__(self):
                self.npcs_here = []
        player.current_room = MockRoom()
    # Ensure melee moves are viable for tests
    player.default_proximity = 2


def use_mock_attack(player):
    """Swap the player's real Attack for a deterministic double, and return it.

    The double resolves in one beat and deals nothing, which keeps these
    tests about the API surface rather than about damage rolls. The returned
    instance is also the only handle on what the adapter chose to target.
    """
    for i, move in enumerate(player.known_moves):
        if getattr(move, "name", None) == "Attack":
            mock_attack = create_mock_move("Attack")
            mock_attack.user = player
            player.known_moves[i] = mock_attack
            return mock_attack
    raise AssertionError("player has no Attack move to substitute")


def pin_melee_range(player, *enemies):
    """Pin the battlefield to melee range before a move is executed.

    ``/api/combat/start`` seeds battlefield positions from the coordinate
    grid, which is randomised. An enemy spawned outside the move's ``mvrange``
    is filtered out of ``_get_available_targets``, and the move is then
    refused with "No valid targets available for this move" — so every test
    here that actually *executes* a move is a coin flip without this
    (measured: 5 runs, 0-2 failures each).

    Only those tests need it. A test that merely inspects the payload from
    ``/api/combat/start`` executes no move, so pinning proximity there does
    nothing at all.
    """
    player.combat_proximity = {enemy: 2 for enemy in enemies}
    for enemy in enemies:
        enemy.combat_proximity = {player: 2}


def drain_suggestions(player, timeout=5.0):
    """Block until the async suggestion worker has published its result.

    ``CombatAdapter.refresh_suggestions`` sets ``suggested_moves`` to ``[]``
    and then computes on a daemon thread. Reading the list straight after the
    HTTP response therefore observes the *cleared* list, never the result —
    which is how a test named "suggestions increase" was satisfied by
    ``0 >= 0``.

    The wait is on ``threading.Event.wait``, deliberately not ``time.sleep``:
    ``tests/api/conftest.py`` starts a process-wide ``patch('time.sleep')`` at
    import and never stops it, so a sleep here is a no-op ``MagicMock`` that
    additionally never releases the GIL — the whole spin can finish inside one
    interpreter switch interval with the worker never scheduled.
    """
    deadline = time.monotonic() + timeout
    idle = threading.Event()
    while getattr(player, "suggestions_loading", False):
        if time.monotonic() > deadline:
            break
        idle.wait(0.02)
    assert not getattr(player, "suggestions_loading", False), (
        "suggestion worker did not finish"
    )


def start_combat(client, session_id, enemy):
    """POST /api/combat/start against ``enemy`` and return the parsed payload."""
    response = client.post(
        "/api/combat/start",
        data=json.dumps({"enemy_id": wire_handle(enemy)}),
        content_type="application/json",
        headers={"Authorization": f"Bearer {session_id}"},
    )
    assert response.status_code == 201, response.data
    return json.loads(response.data)


def post_move(client, session_id, move_type, move_id, target_id):
    """POST /api/combat/move and return the parsed payload.

    Asserts a 200 *and* ``success is True``: the combat route answers 200 with
    ``success=False`` for every game-logic refusal, so the status code alone
    cannot tell "the move ran" from "the move was refused".
    """
    response = client.post(
        "/api/combat/move",
        data=json.dumps({
            "move_type": move_type,
            "move_id": move_id,
            "target_id": target_id,
        }),
        content_type="application/json",
        headers={"Authorization": f"Bearer {session_id}"},
    )
    assert response.status_code == 200, response.data
    data = json.loads(response.data)
    assert data["success"] is True, response.data
    return data


class TestTacticalStrategistIntegration:
    """Integration tests for the full AI strategist flow."""

    @patch("ai.combat_strategist.CombatStrategist.get_suggestions")
    def test_full_combat_cycle_with_ai_suggestions(self, mock_suggestions, app, client, authenticated_session):
        """Test complete combat cycle: start -> AI suggests -> execute -> victory."""
        mock_suggestions.return_value = [{"move_name": "Attack", "score": 90, "reason": "High damage"}]
        session_id, player, session_manager = authenticated_session

        with app.app_context():
            # Setup: Create a simple enemy using helper
            enemy = create_test_enemy("Test Rat", hp=10)

            ensure_player_room(player)

            # Add enemy to player's current location
            player.current_room.npcs_here = [enemy]
            player.combat_list = []
            player.combat_list_allies = [player]

            use_mock_attack(player)

            data = start_combat(client, session_id, enemy)
            assert data["success"] is True
            assert data["combat_active"] is True

            pin_melee_range(player, enemy)

            # AI suggestions ride inside battle_state, where the client's
            # transformCombatData spread carries them (CLAUDE.md,
            # "transformCombatData silently drops top-level keys").
            battle_state = data["battle_state"]
            assert "suggested_moves" in battle_state
            assert "suggestions_loading" in battle_state

            # Get combat status to see current state
            response = client.get(
                "/api/combat/status",
                headers={"Authorization": f"Bearer {session_id}"}
            )

            assert response.status_code == 200
            status_data = json.loads(response.data)
            assert status_data["success"] is True
            assert status_data["combat_active"] is True

            # Execute a move (Attack)
            move_data = post_move(
                client,
                session_id,
                "move",
                "Attack",
                CombatantSerializer.stream_id(enemy),
            )

            # Verify combat log contains action
            assert "log" in move_data
            assert len(move_data["log"]) > 0

    @patch("ai.combat_strategist.CombatStrategist.get_suggestions")
    def test_ai_suggestions_increase_with_passive_skills(self, mock_suggestions, app, client, authenticated_session):
        """Unlocking Strategic Insight buys Jean one more tactical suggestion.

        The strategist is stubbed to return exactly ``max_suggestions``
        suggestions, each naming a move the adapter says is currently
        available — an unavailable name is filtered out downstream, so a stub
        answering "Move 0"/"Move 1" produces an empty list either way and the
        old ``>=`` comparison was satisfied by ``0 >= 0``.
        """
        def suggest_from_available(ctx, max_suggestions):
            names = [move["name"] for move in ctx["available_moves"]]
            if not names:
                return []
            return [
                {"move_name": names[i % len(names)], "score": 100 - i}
                for i in range(max_suggestions)
            ]

        mock_suggestions.side_effect = suggest_from_available
        session_id, player, session_manager = authenticated_session

        with app.app_context():
            import src.moves as moves

            ensure_player_room(player)

            enemy = create_test_enemy("Test Enemy", hp=50)

            player.current_room.npcs_here = [enemy]
            player.combat_list = []
            player.combat_list_allies = [player]

            use_mock_attack(player)

            # Start combat without passive skills
            base_moves = list(player.known_moves)

            start_combat(client, session_id, enemy)
            drain_suggestions(player)
            base_suggestion_count = len(player.suggested_moves)
            assert base_suggestion_count > 0, (
                "the stub produced no suggestions at all; the comparison below "
                "would be vacuous"
            )

            # End combat
            player.in_combat = False
            player.combat_list = []

            # Add the real passive, not a lookalike: the adapter walks
            # known_moves both to count suggestions and to build the move list
            # the strategist is handed.
            player.known_moves = base_moves + [moves.StrategicInsight(player)]

            enemy2 = create_test_enemy("Test Enemy 2", hp=50)
            player.current_room.npcs_here = [enemy2]

            start_combat(client, session_id, enemy2)
            drain_suggestions(player)
            insight_suggestion_count = len(player.suggested_moves)

            # Strategic Insight is worth exactly one extra suggestion.
            assert insight_suggestion_count == base_suggestion_count + 1

    @patch("ai.combat_strategist.CombatStrategist.get_suggestions")
    def test_combined_move_and_target_execution(self, mock_suggestions, app, client, authenticated_session):
        """One-click move+target must act on the enemy the client named.

        Two viable enemies are in the fight on purpose. With only one, the
        target id is not load-bearing: ``_resolve_move_target`` deliberately
        falls through to auto-resolution for an id that names nobody, and with
        a single viable target that fallback picks the same enemy — so the
        assertion held even for a fabricated id. With two, an unrecognised id
        falls through to multi-target selection instead and the move does not
        execute at all.
        """
        mock_suggestions.return_value = []
        session_id, player, session_manager = authenticated_session

        with app.app_context():
            ensure_player_room(player)

            decoy = create_test_enemy("Decoy Target", hp=30)
            named = create_test_enemy("Named Target", hp=30)

            # Seed the *universe* tile, not a mock room. `start_combat`
            # rebinds `player.current_room` to `universe.get_tile(...)` before
            # collecting the roster, so hostiles parked on a stand-in room are
            # dropped and only the clicked enemy survives — which is how this
            # test would silently fall back to the one-enemy case the target
            # id is not load-bearing in.
            tile = player.universe.get_tile(player.location_x, player.location_y)
            assert tile is not None
            tile.npcs_here = [decoy, named]
            player.current_room = tile
            player.combat_list = []
            player.combat_list_allies = [player]

            mock_attack = use_mock_attack(player)

            data = start_combat(client, session_id, decoy)
            assert len(data["battle_state"]["enemies"]) == 2, (
                "both enemies must be in the fight or auto-resolution can "
                "rescue a wrong target id"
            )

            pin_melee_range(player, decoy, named)

            # Name the *second* enemy, so even a "pick the first one" fallback
            # would resolve to the wrong combatant.
            data = post_move(
                client,
                session_id,
                "select_move_and_target",
                "Attack",
                CombatantSerializer.stream_id(named),
            )

            # The move ran against the named enemy — not queued for a target
            # prompt, and not pointed at the decoy.
            assert mock_attack.target is named
            assert data["battle_state"]["input_type"] != "target_selection"

            # Verify move was executed
            assert "log" in data

            # Check that combat log contains the action
            log_messages = [entry.get("message", "") for entry in data["log"]]
            assert any("Attack" in msg or player.name in msg for msg in log_messages)

    @patch("ai.combat_strategist.CombatStrategist.get_suggestions")
    def test_status_effects_serialization(self, mock_suggestions, app, client, authenticated_session):
        """A real engine State reaches the client as `status_effects`.

        The previous version appended a `MockEffect` to `player.active_effects`
        — an attribute that exists nowhere in `src/` — and guarded its only
        assertion with `if "active_effects" in player_data:`, which is never
        true. `CombatantSerializer` emits `status_effects`, derived from
        `combatant.states`. That is the fixture-agrees-with-fixture wire-field
        drift CLAUDE.md calls this codebase's dominant bug class.
        """
        mock_suggestions.return_value = []
        session_id, player, session_manager = authenticated_session

        with app.app_context():
            from src.states import Poisoned

            ensure_player_room(player)

            enemy = create_test_enemy("Test Enemy", hp=40)

            # Real state object on the real engine attribute.
            player.states.append(Poisoned(player))

            player.current_room.npcs_here = [enemy]
            player.combat_list = []
            player.combat_list_allies = [player]

            use_mock_attack(player)

            data = start_combat(client, session_id, enemy)

            # Verify battle state includes combatant data
            battle_state = data["battle_state"]
            assert "combatants" in battle_state

            # Check player combatant data
            player_data = next(
                (c for c in battle_state["combatants"] if c.get("name") == player.name),
                None
            )

            assert player_data is not None
            # The emitted key, asserted unconditionally.
            assert "active_effects" not in player_data
            effects = player_data["status_effects"]
            assert [effect["name"] for effect in effects] == ["Poisoned"]
            assert effects[0]["type"] == "ailment"
            assert "beats_left" in effects[0]
            assert "description" in effects[0]

    @patch("ai.combat_strategist.CombatStrategist.get_suggestions")
    def test_ai_context_includes_combat_history(self, mock_suggestions, app, client, authenticated_session):
        """Test that AI receives combat history for context-aware suggestions."""
        mock_suggestions.return_value = []
        session_id, player, session_manager = authenticated_session

        with app.app_context():
            ensure_player_room(player)

            enemy = create_test_enemy("Context Test Enemy", hp=50)

            player.current_room.npcs_here = [enemy]
            player.combat_list = []
            player.combat_list_allies = [player]

            use_mock_attack(player)

            start_combat(client, session_id, enemy)
            pin_melee_range(player, enemy)

            # Execute a move to create history
            data = post_move(
                client,
                session_id,
                "move",
                "Attack",
                CombatantSerializer.stream_id(enemy),
            )

            # Verify combat log exists and has entries
            assert "log" in data
            assert len(data["log"]) > 0

            # Verify last_move_summary is captured
            assert hasattr(player, "last_move_summary")
            assert isinstance(player.last_move_summary, str)


class TestEnhancedCombatVisualizationIntegration:
    """Integration tests for status effect visualization."""

    @patch("ai.combat_strategist.CombatStrategist.get_suggestions")
    def test_status_effects_in_combat_state(self, mock_suggestions, app, client, authenticated_session):
        """Test that status effects appear in serialized combat state."""
        mock_suggestions.return_value = []
        session_id, player, session_manager = authenticated_session

        with app.app_context():
            ensure_player_room(player)

            enemy = create_test_enemy("Visualization Test", hp=30)

            player.current_room.npcs_here = [enemy]
            player.combat_list = []
            player.combat_list_allies = [player]

            use_mock_attack(player)

            data = start_combat(client, session_id, enemy)

            # Verify combatants are serialized
            battle_state = data["battle_state"]
            assert "combatants" in battle_state
            assert len(battle_state["combatants"]) > 0

            # Each combatant should have required fields
            for combatant in battle_state["combatants"]:
                assert "name" in combatant
                assert "hp" in combatant
                assert "max_hp" in combatant
                assert "status_effects" in combatant

    @patch("ai.combat_strategist.CombatStrategist.get_suggestions")
    def test_beat_states_include_position_data(self, mock_suggestions, app, client, authenticated_session):
        """Test that beat states include position/distance data for visualization."""
        mock_suggestions.return_value = []
        session_id, player, session_manager = authenticated_session

        with app.app_context():
            ensure_player_room(player)

            enemy = create_test_enemy("Position Test", hp=25)

            player.current_room.npcs_here = [enemy]
            player.combat_list = []
            player.combat_list_allies = [player]

            use_mock_attack(player)

            start_combat(client, session_id, enemy)
            pin_melee_range(player, enemy)

            # Execute a move to generate beat states
            move_data = post_move(
                client,
                session_id,
                "move",
                "Attack",
                CombatantSerializer.stream_id(enemy),
            )

            # A move must publish at least one beat; an empty list would have
            # satisfied the loop below without checking anything.
            beat_states = move_data["beat_states"]
            assert beat_states

            # Each beat state carries the position data the battlefield grid
            # renders. `distance` and `position` are the emitted keys — there
            # is no top-level `x` on a serialized combatant, so the old
            # `"x" in combatant or "distance" in combatant` could not fail.
            for beat_state in beat_states:
                assert beat_state["combatants"]
                for combatant in beat_state["combatants"]:
                    assert "distance" in combatant
                    assert "position" in combatant
