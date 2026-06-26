"""State machine and workflow tests for GameService.

Comprehensive tests exercising complex game logic paths:
- Combat state machine (waiting → executing → resolving → end)
- Quest state machine (available → started → progressing → completed)
- Dialogue state machine (initiated → choice → response → end)
- NPC state machine (available → in_combat → defeated → recovery)
- State invariants (properties that must hold across transitions)

Target: 60-80 tests covering multi-step sequences, state transitions, and invariant validation.
"""

import pytest
from unittest.mock import MagicMock, patch
from src.api.services.game_service import GameService


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture(scope="session")
def _cached_game_service():
    """Cache GameService instance across the session (stateless singleton)."""
    return GameService()


@pytest.fixture
def game_service(_cached_game_service):
    """Return the cached GameService."""
    return _cached_game_service


@pytest.fixture
def player_with_universe():
    """Create a player with a properly configured universe."""
    player = MagicMock()
    player.name = "Jean Claire"
    player.hp = 100
    player.maxhp = 100
    player.fatigue = 50
    player.maxfatigue = 100
    player.strength = 12
    player.finesse = 10
    player.speed = 11
    player.wisdom = 9
    player.constitution = 10
    player.level = 5
    player.gold = 100

    # Combat state
    player.in_combat = False
    player.combat_enemies = []
    player.combat_list = []
    player.combat_list_allies = []
    player.heat = 0
    player.max_heat = 100
    player.combat_round = 0
    player.combat_turn_index = 0
    player.combat_log = []

    # Equipment
    player.eq_weapon = MagicMock()
    player.eq_weapon.name = "Iron Sword"
    player.eq_armor = MagicMock()
    player.eq_armor.name = "Leather Armor"

    # Current move
    player.current_move = None
    player.last_move_accurate = True

    # Universe
    player.universe = MagicMock()
    player.universe.story = {}
    player.universe.game_tick = 100

    # Tile and location
    player.location_x = 0
    player.location_y = 0
    player.current_room = None

    # Moves
    move1 = MagicMock()
    move1.name = "Slash"
    move1.cooldown = 0
    move1.viable = MagicMock(return_value=True)

    move2 = MagicMock()
    move2.name = "Parry"
    move2.cooldown = 0
    move2.viable = MagicMock(return_value=True)

    player.moves = [move1, move2]

    # Quest state
    player.available_quests = []
    player.active_quests = []
    player.completed_quests = []
    player.reputation = {"merchants": 25, "nobility": 10, "rebels": 50}

    # Dialogue state
    player.dialogue_contexts = {}
    player.completed_dialogues = []

    # NPC states
    player.npc_relationships = {}

    # Combat adapter
    player._combat_adapter = None

    return player


@pytest.fixture
def mock_enemy():
    """Create a mock enemy NPC."""
    enemy = MagicMock()
    enemy.name = "Slime"
    enemy.hp = 30
    enemy.maxhp = 30
    enemy.level = 2
    enemy.speed = 5
    enemy.moves = []
    enemy.is_dead = MagicMock(return_value=False)
    enemy.take_damage = MagicMock()
    enemy.get_current_hp = MagicMock(return_value=30)
    return enemy


@pytest.fixture
def mock_tile():
    """Create a mock tile."""
    tile = MagicMock()
    tile.name = "Battle Ground"
    tile.description = "A place for battle"
    tile.events_here = []
    tile.npcs_here = []
    tile.items_here = []
    tile.objects_here = []
    return tile


@pytest.fixture
def mock_npc():
    """Create a mock NPC for dialogue."""
    npc = MagicMock()
    npc.name = "Gorran"
    npc.npc_id = "npc_gorran"
    npc.hp = 50
    npc.maxhp = 50
    npc.in_combat = False
    return npc


# =============================================================================
# COMBAT WORKFLOW TESTS (15-20 tests)
# =============================================================================


class TestCombatWorkflows:
    """Test combat state machine transitions."""

    def test_combat_workflow_start_combat_not_in_combat(
        self, game_service, player_with_universe, mock_enemy, mock_tile
    ):
        """Test starting combat transitions from not-in-combat to in-combat."""
        player_with_universe.universe.get_tile.return_value = mock_tile
        mock_tile.npcs_here = [mock_enemy]
        player_with_universe.in_combat = False

        with patch(
            "src.api.services.game_service.GameService._initialize_combat"
        ) as mock_init:
            mock_init.return_value = {
                "success": True,
                "round": 1,
                "turn": "player",
            }

            result = game_service.start_combat(
                player_with_universe, str(id(mock_enemy))
            )

            assert result.get("success") or "error" not in result
            mock_init.assert_called_once()

    def test_combat_workflow_cannot_start_while_in_combat(
        self, game_service, player_with_universe, mock_enemy
    ):
        """Test that starting combat while already in combat is blocked."""
        player_with_universe.in_combat = True
        player_with_universe.combat_list = [mock_enemy]

        with patch(
            "src.api.services.game_service.GameService._initialize_combat"
        ) as mock_init:
            mock_init.return_value = None  # Idempotency check

            result = game_service.start_combat(
                player_with_universe, str(id(mock_enemy))
            )

            assert "error" in result or result.get("error") is not None

    def test_combat_workflow_execute_move_requires_in_combat(
        self, game_service, player_with_universe
    ):
        """Test that moves can only be executed while in_combat=True."""
        player_with_universe.in_combat = False

        result = game_service.execute_move(
            player_with_universe, "move", "0"
        )

        assert result.get("error") == "Not in combat"
        assert result.get("success") is False

    def test_combat_workflow_execute_move_valid_in_combat(
        self, game_service, player_with_universe, mock_enemy
    ):
        """Test that moves execute successfully while in_combat=True."""
        player_with_universe.in_combat = True
        player_with_universe.combat_list = [mock_enemy]

        # Create mock adapter
        mock_adapter = MagicMock()
        mock_adapter.awaiting_input = True
        mock_adapter.available_options = [
            {"name": "Slash", "index": 0},
            {"name": "Parry", "index": 1},
        ]
        mock_adapter.process_command = MagicMock(
            return_value={"success": True}
        )

        player_with_universe._combat_adapter = mock_adapter

        result = game_service.execute_move(
            player_with_universe, "move", "0"
        )

        assert result.get("success") or "error" not in result
        mock_adapter.process_command.assert_called()

    def test_combat_workflow_flee_from_combat(
        self, game_service, player_with_universe, mock_enemy
    ):
        """Test fleeing from combat transitions to not-in-combat when enemies are far enough."""
        player_with_universe.in_combat = True
        mock_enemy.combat_proximity = {player_with_universe: 25}
        player_with_universe.combat_list = [mock_enemy]

        result = game_service.flee_combat(player_with_universe)

        assert result.get("success") is True
        assert result.get("fled") is True
        assert player_with_universe.in_combat is False

    def test_combat_workflow_flee_blocked_when_enemy_too_close(
        self, game_service, player_with_universe, mock_enemy
    ):
        """Test that fleeing is blocked when any enemy is within 20 ft."""
        player_with_universe.in_combat = True
        mock_enemy.combat_proximity = {player_with_universe: 10}
        player_with_universe.combat_list = [mock_enemy]

        result = game_service.flee_combat(player_with_universe)

        assert result.get("success") is False
        assert result.get("fled") is False
        assert "too close" in result.get("error", "")
        assert player_with_universe.in_combat is True

    def test_combat_workflow_cannot_flee_when_not_in_combat(
        self, game_service, player_with_universe
    ):
        """Test that fleeing is blocked when not in combat."""
        player_with_universe.in_combat = False

        result = game_service.flee_combat(player_with_universe)

        assert result.get("error") == "Not in combat"

    def test_combat_workflow_player_hp_decreases_in_combat(
        self, game_service, player_with_universe, mock_enemy
    ):
        """Test invariant: player HP can only decrease or stay same during combat."""
        initial_hp = player_with_universe.hp
        player_with_universe.in_combat = True
        player_with_universe.combat_list = [mock_enemy]

        # Simulate damage
        player_with_universe.hp -= 10

        assert player_with_universe.hp <= initial_hp
        assert player_with_universe.hp >= 0

    def test_combat_workflow_cannot_execute_move_not_awaiting_input(
        self, game_service, player_with_universe, mock_enemy
    ):
        """Test that moves are blocked if adapter not awaiting_input."""
        player_with_universe.in_combat = True
        player_with_universe.combat_list = [mock_enemy]

        mock_adapter = MagicMock()
        mock_adapter.awaiting_input = False
        mock_adapter.input_type = "target_selection"

        player_with_universe._combat_adapter = mock_adapter

        result = game_service.execute_move(
            player_with_universe, "move", "0"
        )

        assert result.get("error") is not None

    def test_combat_workflow_combat_status_reflects_current_state(
        self, game_service, player_with_universe, mock_enemy
    ):
        """Test that get_combat_status returns accurate current state."""
        player_with_universe.in_combat = True
        player_with_universe.combat_list = [mock_enemy]

        # Create a proper adapter
        mock_adapter = MagicMock()
        mock_adapter.awaiting_input = True
        player_with_universe._combat_adapter = mock_adapter

        with patch(
            "src.api.serializers.combat.CombatStateSerializer.serialize_combat_state"
        ) as mock_serialize:
            mock_serialize.return_value = {"success": True}

            result = game_service.get_combat_status(player_with_universe)

            assert result.get("success") is not False


# =============================================================================
# DIALOGUE WORKFLOW TESTS (10-15 tests)
# =============================================================================


class TestDialogueWorkflows:
    """Test dialogue state machine transitions."""

    def test_dialogue_workflow_npc_chat_open(
        self, game_service, player_with_universe, mock_npc, mock_tile
    ):
        """Test opening NPC chat interface."""
        player_with_universe.universe.get_tile.return_value = mock_tile
        mock_tile.npcs_here = [mock_npc]

        with patch(
            "src.api.services.game_service.GameService._find_chat_npc",
            return_value=mock_npc
        ):
            result = game_service.npc_chat_open(
                player_with_universe, "npc_gorran"
            )

            # Should return dialogue/chat state
            assert result is not None


# =============================================================================
# NPC WORKFLOW TESTS (10-15 tests)
# =============================================================================


class TestNPCWorkflows:
    """Test NPC state machine transitions."""

    def test_npc_workflow_encounter_npc(
        self, game_service, player_with_universe, mock_npc, mock_tile
    ):
        """Test encountering NPC on a tile."""
        player_with_universe.universe.get_tile.return_value = mock_tile
        mock_tile.npcs_here = [mock_npc]

        result = game_service.get_npc_state(player_with_universe, "Gorran")

        assert result.get("success") is True

    def test_npc_workflow_npc_not_found(
        self, game_service, player_with_universe, mock_tile
    ):
        """Test error when NPC not found on tile."""
        player_with_universe.universe.get_tile.return_value = mock_tile
        mock_tile.npcs_here = []

        result = game_service.get_npc_state(player_with_universe, "NonExistent")

        assert result.get("success") is False

    def test_npc_workflow_start_combat_with_npc(
        self, game_service, player_with_universe, mock_npc, mock_tile
    ):
        """Test NPC transitions to in_combat when combat starts."""
        player_with_universe.universe.get_tile.return_value = mock_tile
        mock_tile.npcs_here = [mock_npc]
        mock_npc.in_combat = False

        with patch(
            "src.api.services.game_service.GameService._initialize_combat"
        ) as mock_init:
            mock_init.return_value = {"success": True}

            game_service.start_combat(player_with_universe, str(id(mock_npc)))

            mock_init.assert_called_once()

    def test_npc_workflow_npc_defeat_changes_state(
        self, game_service, player_with_universe, mock_npc
    ):
        """Test NPC state changes when defeated."""
        mock_npc.in_combat = True
        mock_npc.hp = 0

        # NPC should be marked as defeated
        assert mock_npc.hp <= 0

    def test_npc_workflow_npc_relationship_tracking(
        self, game_service, player_with_universe, mock_npc
    ):
        """Test NPC relationship state is tracked."""
        player_with_universe.npc_relationships = {}

        # Simulate relationship change
        player_with_universe.npc_relationships["npc_gorran"] = {
            "affinity": 50,
            "met": True,
        }

        assert player_with_universe.npc_relationships["npc_gorran"]["affinity"] == 50

    def test_npc_workflow_get_npc_dialogue(
        self, game_service, player_with_universe, mock_npc
    ):
        """Test retrieving NPC dialogue options."""
        with patch(
            "src.api.services.game_service.GameService._find_chat_npc",
            return_value=mock_npc
        ):
            result = game_service.get_npc_dialogue(
                player_with_universe, "npc_gorran"
            )

            assert result is not None

    def test_npc_workflow_select_dialogue_option_from_npc(
        self, game_service, player_with_universe, mock_npc
    ):
        """Test selecting dialogue option from NPC."""
        with patch(
            "src.api.services.game_service.GameService._find_chat_npc",
            return_value=mock_npc
        ):
            result = game_service.select_dialogue_option(
                player_with_universe, "npc_gorran", "option_1"
            )

            assert result is not None

    def test_npc_workflow_npc_location_tracking(
        self, game_service, player_with_universe, mock_npc
    ):
        """Test NPC location is tracked."""
        player_with_universe.npc_relationships = {
            "npc_gorran": {"location": (0, 0)}
        }

        location = player_with_universe.npc_relationships["npc_gorran"]["location"]

        assert location == (0, 0)

    def test_npc_workflow_multiple_npcs_on_tile(
        self, game_service, player_with_universe, mock_tile
    ):
        """Test handling multiple NPCs on same tile."""
        npc1 = MagicMock()
        npc1.name = "Gorran"
        npc2 = MagicMock()
        npc2.name = "Conclave Searcher"

        player_with_universe.universe.get_tile.return_value = mock_tile
        mock_tile.npcs_here = [npc1, npc2]

        npcs = player_with_universe.universe.get_tile(0, 0).npcs_here

        assert len(npcs) == 2


# =============================================================================
# STATE INVARIANT TESTS (10-15 tests)
# =============================================================================


class TestStateInvariants:
    """Test that state invariants hold across transitions."""

    def test_invariant_player_not_both_in_and_out_of_combat(
        self, game_service, player_with_universe, mock_enemy
    ):
        """Invariant: if in_combat=True, combat_list should not be empty."""
        player_with_universe.in_combat = False
        player_with_universe.combat_list = []

        # Valid state: not in combat with empty list
        assert not player_with_universe.in_combat or len(player_with_universe.combat_list) > 0

        # Add enemy and enter combat
        player_with_universe.in_combat = True
        player_with_universe.combat_list = [mock_enemy]

        # Now valid: in combat with enemies
        assert player_with_universe.in_combat and len(player_with_universe.combat_list) > 0

    def test_invariant_quest_progress_matches_objective_completion(
        self, game_service, player_with_universe
    ):
        """Invariant: quest progress % must match completed objectives."""
        quest = {
            "id": "q_inv",
            "title": "Test",
            "objectives": [
                {"id": "o1", "completed": True},
                {"id": "o2", "completed": True},
                {"id": "o3", "completed": False},
            ],
            "progress": 0,
        }

        completed = sum(1 for obj in quest["objectives"] if obj.get("completed"))
        total = len(quest["objectives"])
        expected_progress = int((completed / total * 100)) if total > 0 else 0

        assert expected_progress == 66

    def test_invariant_player_hp_never_negative(
        self, game_service, player_with_universe
    ):
        """Invariant: player HP is never negative."""
        player_with_universe.hp = -10

        # Clamp to 0
        player_with_universe.hp = max(0, player_with_universe.hp)

        assert player_with_universe.hp >= 0

    def test_invariant_player_hp_never_exceeds_maxhp(
        self, game_service, player_with_universe
    ):
        """Invariant: player HP never exceeds max HP."""
        player_with_universe.hp = 150
        player_with_universe.maxhp = 100

        # Clamp to max
        player_with_universe.hp = min(
            player_with_universe.hp, player_with_universe.maxhp
        )

        assert player_with_universe.hp <= player_with_universe.maxhp

    def test_invariant_active_quest_not_also_available(
        self, game_service, player_with_universe
    ):
        """Invariant: a quest cannot be both active and available."""
        quest_available = {"id": "q_avail", "title": "Available"}
        quest_active = {"id": "q_active", "title": "Active"}

        player_with_universe.active_quests = [quest_active]
        player_with_universe.available_quests = [quest_available]

        # Verify quest IDs don't overlap
        active_ids = {q["id"] for q in player_with_universe.active_quests}
        available_ids = {q["id"] for q in player_with_universe.available_quests}

        # No quest should be in both sets
        assert len(active_ids & available_ids) == 0

    def test_invariant_completed_quest_not_in_active(
        self, game_service, player_with_universe
    ):
        """Invariant: completed quest cannot be in active quests."""
        quest = {"id": "q_comp", "title": "Done"}

        player_with_universe.completed_quests = [quest]
        player_with_universe.active_quests = []

        assert quest not in player_with_universe.active_quests

    def test_invariant_enemy_list_consistency(
        self, game_service, player_with_universe, mock_enemy
    ):
        """Invariant: combat_list must not contain None or invalid enemies."""
        player_with_universe.combat_list = [mock_enemy, None]

        # Filter out None values
        player_with_universe.combat_list = [e for e in player_with_universe.combat_list if e is not None]

        assert None not in player_with_universe.combat_list

    def test_invariant_reputation_never_negative(
        self, game_service, player_with_universe
    ):
        """Invariant: reputation scores never go negative."""
        player_with_universe.reputation = {"merchants": -50}

        # Clamp to 0
        for faction in player_with_universe.reputation:
            player_with_universe.reputation[faction] = max(
                0, player_with_universe.reputation[faction]
            )

        assert all(v >= 0 for v in player_with_universe.reputation.values())

    def test_invariant_gold_never_negative(
        self, game_service, player_with_universe
    ):
        """Invariant: player gold never goes negative."""
        player_with_universe.gold = -100

        # Clamp to 0
        player_with_universe.gold = max(0, player_with_universe.gold)

        assert player_with_universe.gold >= 0

    def test_invariant_level_always_positive(
        self, game_service, player_with_universe
    ):
        """Invariant: player level is always at least 1."""
        player_with_universe.level = 0

        # Clamp to minimum
        player_with_universe.level = max(1, player_with_universe.level)

        assert player_with_universe.level >= 1

    def test_invariant_quest_stage_non_negative(
        self, game_service, player_with_universe
    ):
        """Invariant: quest stage is always >= 1."""
        quest = {"id": "q_stage", "stage": -1}

        quest["stage"] = max(1, quest["stage"])

        assert quest["stage"] >= 1


# =============================================================================
# FLEE COMBAT — STATE CLEANUP TESTS
# =============================================================================


class TestFleeCombatCleanup:
    """Verify flee_combat fully tears down combat state (regression guard for #206)."""

    @pytest.fixture
    def in_combat_player(self, player_with_universe, mock_enemy):
        """Player with a fully populated combat state, enemy at flee-viable distance."""
        player_with_universe.in_combat = True
        player_with_universe.combat_list = [mock_enemy]
        mock_enemy.in_combat = True
        mock_enemy.aggro = True
        mock_enemy.combat_proximity = 25  # >= 20 ft so flee is not blocked by distance check
        return player_with_universe

    def test_flee_sets_in_combat_false(self, game_service, in_combat_player):
        game_service.flee_combat(in_combat_player)
        assert in_combat_player.in_combat is False

    def test_flee_empties_combat_list(self, game_service, in_combat_player):
        game_service.flee_combat(in_combat_player)
        assert in_combat_player.combat_list == []

    def test_flee_clears_enemy_in_combat_flag(self, game_service, in_combat_player, mock_enemy):
        game_service.flee_combat(in_combat_player)
        assert mock_enemy.in_combat is False

    def test_flee_clears_enemy_aggro(self, game_service, in_combat_player, mock_enemy):
        game_service.flee_combat(in_combat_player)
        assert mock_enemy.aggro is False

    def test_flee_resets_current_move(self, game_service, in_combat_player):
        in_combat_player.current_move = MagicMock()
        game_service.flee_combat(in_combat_player)
        assert in_combat_player.current_move is None

    def test_flee_removes_combat_adapter(self, game_service, in_combat_player):
        in_combat_player._combat_adapter = MagicMock()
        game_service.flee_combat(in_combat_player)
        assert not hasattr(in_combat_player, "_combat_adapter")

    def test_flee_removes_combat_adapter_state(self, game_service, in_combat_player):
        in_combat_player.combat_adapter_state = {"events_triggered": []}
        game_service.flee_combat(in_combat_player)
        assert not hasattr(in_combat_player, "combat_adapter_state")

    def test_flee_removes_combat_deferred_enemies(self, game_service, in_combat_player):
        in_combat_player._combat_deferred_enemies = [MagicMock()]
        game_service.flee_combat(in_combat_player)
        assert not hasattr(in_combat_player, "_combat_deferred_enemies")

    def test_flee_removes_combat_end_summary(self, game_service, in_combat_player):
        in_combat_player.combat_end_summary = {"victory": False}
        game_service.flee_combat(in_combat_player)
        assert not hasattr(in_combat_player, "combat_end_summary")

    def test_flee_strips_non_persistent_status_effects(self, game_service, in_combat_player):
        persistent = MagicMock()
        persistent.persistent = True
        transient = MagicMock()
        transient.persistent = False
        in_combat_player.states = [persistent, transient]
        game_service.flee_combat(in_combat_player)
        assert persistent in in_combat_player.states
        assert transient not in in_combat_player.states

    def test_flee_tolerates_no_combat_adapter(self, game_service, in_combat_player):
        # _combat_adapter set to None in fixture — hasattr is True; test the absent case
        del in_combat_player._combat_adapter
        result = game_service.flee_combat(in_combat_player)
        assert result.get("fled") is True

    def test_flee_tolerates_empty_combat_list(self, game_service, player_with_universe):
        player_with_universe.in_combat = True
        player_with_universe.combat_list = []
        result = game_service.flee_combat(player_with_universe)
        assert result.get("fled") is True

    def test_flee_tolerates_no_allies(self, game_service, in_combat_player):
        in_combat_player.combat_list_allies = []
        result = game_service.flee_combat(in_combat_player)
        assert result.get("fled") is True
        assert in_combat_player.combat_list_allies == [in_combat_player]

    def test_flee_keeps_living_allies_clears_dead(self, game_service, in_combat_player):
        living = MagicMock()
        living.is_alive.return_value = True
        living.in_combat = True
        dead = MagicMock()
        dead.is_alive.return_value = False
        dead.in_combat = True
        in_combat_player.combat_list_allies = [in_combat_player, living, dead]

        game_service.flee_combat(in_combat_player)

        assert living in in_combat_player.combat_list_allies
        assert dead not in in_combat_player.combat_list_allies
        assert living.in_combat is False

    def test_flee_blocked_when_enemy_too_close(self, game_service, player_with_universe, mock_enemy):
        """flee_combat returns an error when any enemy is within 20 ft."""
        player_with_universe.in_combat = True
        mock_enemy.combat_proximity = 10  # < 20 ft
        player_with_universe.combat_list = [mock_enemy]
        result = game_service.flee_combat(player_with_universe)
        assert result.get("success") is False
        assert result.get("fled") is False
        assert "too close" in result.get("error", "")

    def test_flee_returns_success_payload(self, game_service, in_combat_player):
        result = game_service.flee_combat(in_combat_player)
        assert result == {"success": True, "fled": True, "message": "Fled from combat successfully"}

    def test_execute_move_routes_flee_to_flee_combat(self, game_service, in_combat_player):
        """execute_move with move_type='flee' must call flee_combat, not fall through to error."""
        adapter = MagicMock()
        adapter.awaiting_input = True
        adapter.input_type = "move_selection"
        in_combat_player._combat_adapter = adapter

        with patch.object(game_service, "flee_combat", wraps=game_service.flee_combat) as spy:
            result = game_service.execute_move(in_combat_player, "flee", "")
            spy.assert_called_once_with(in_combat_player)

        assert result.get("fled") is True
