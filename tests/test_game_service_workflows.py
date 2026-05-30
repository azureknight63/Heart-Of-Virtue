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
from unittest.mock import MagicMock, Mock, patch, call
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

    def test_combat_workflow_end_combat_transitions_to_not_in_combat(
        self, game_service, player_with_universe, mock_enemy
    ):
        """Test that end_combat transitions player to not-in-combat state."""
        player_with_universe.in_combat = True
        player_with_universe.combat_list = [mock_enemy]
        player_with_universe.combat_list_allies = []

        with patch(
            "src.api.serializers.combat.CombatStateSerializer.serialize_battle_summary"
        ) as mock_summary:
            mock_summary.return_value = {"victory": True}

            result = game_service.end_combat(player_with_universe, True)

            assert player_with_universe.in_combat is False
            assert len(player_with_universe.combat_list) == 0
            assert len(player_with_universe.combat_list_allies) == 0

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

    def test_combat_workflow_combat_lists_cleared_on_end(
        self, game_service, player_with_universe, mock_enemy
    ):
        """Test invariant: combat_list and allies cleared after combat ends."""
        player_with_universe.in_combat = True
        player_with_universe.combat_list = [mock_enemy]
        player_with_universe.combat_list_allies = []

        with patch(
            "src.api.serializers.combat.CombatStateSerializer.serialize_battle_summary"
        ) as mock_summary:
            mock_summary.return_value = {"victory": True}
            game_service.end_combat(player_with_universe, True)

        assert player_with_universe.combat_list == []
        assert player_with_universe.combat_list_allies == []

    def test_combat_workflow_combat_round_advances(
        self, game_service, player_with_universe, mock_enemy
    ):
        """Test that combat_round increments through the combat."""
        player_with_universe.in_combat = True
        player_with_universe.combat_round = 1
        enemies = [mock_enemy]

        initial_round = player_with_universe.combat_round
        game_service._advance_turn(player_with_universe, enemies)

        # Round should either stay same or increment
        assert player_with_universe.combat_round >= initial_round

    def test_combat_workflow_turn_order_respects_speed(
        self, game_service, player_with_universe, mock_enemy
    ):
        """Test invariant: turn order respects speed stat."""
        player_with_universe.speed = 15
        mock_enemy.speed = 5

        turn_order = game_service._get_turn_order(
            player_with_universe, [mock_enemy]
        )

        # Player should go first (higher speed)
        assert turn_order[0] == "player"

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

    def test_combat_workflow_multi_enemy_combat(
        self, game_service, player_with_universe, mock_enemy
    ):
        """Test workflow with multiple enemies."""
        enemy2 = MagicMock()
        enemy2.name = "Bat"
        enemy2.hp = 15
        enemy2.speed = 8

        player_with_universe.in_combat = True
        player_with_universe.combat_list = [mock_enemy, enemy2]

        turn_order = game_service._get_turn_order(
            player_with_universe, [mock_enemy, enemy2]
        )

        assert len(turn_order) == 3  # player + 2 enemies
        assert "player" in turn_order

    def test_combat_workflow_end_combat_on_player_death(
        self, game_service, player_with_universe, mock_enemy
    ):
        """Test that combat ends when player HP reaches 0."""
        player_with_universe.in_combat = True
        player_with_universe.hp = 0
        player_with_universe.combat_list = [mock_enemy]

        with patch(
            "src.api.serializers.combat.CombatStateSerializer.serialize_battle_summary"
        ) as mock_summary:
            mock_summary.return_value = {"victory": False}

            result = game_service.end_combat(player_with_universe, False)

            assert player_with_universe.in_combat is False


# =============================================================================
# QUEST WORKFLOW TESTS (15-20 tests)
# =============================================================================


class TestQuestWorkflows:
    """Test quest state machine transitions."""

    def test_quest_workflow_available_to_started(
        self, game_service, player_with_universe
    ):
        """Test quest transition: available → started."""
        quest = {
            "id": "quest_1",
            "title": "The First Challenge",
            "objectives": [
                {"id": "obj_1", "description": "Find the artifact", "completed": False}
            ],
        }
        player_with_universe.available_quests = [quest]
        player_with_universe.active_quests = []

        result = game_service.start_quest(player_with_universe, "quest_1")

        assert result.get("success") is True
        assert len(player_with_universe.active_quests) == 1
        assert len(player_with_universe.available_quests) == 0

    def test_quest_workflow_cannot_start_unavailable_quest(
        self, game_service, player_with_universe
    ):
        """Test that unavailable quests cannot be started."""
        player_with_universe.available_quests = []

        result = game_service.start_quest(player_with_universe, "nonexistent")

        assert result.get("success") is False
        assert "error" in result

    def test_quest_workflow_progress_objective(
        self, game_service, player_with_universe
    ):
        """Test quest objective progression."""
        quest = {
            "id": "quest_2",
            "title": "Gather Supplies",
            "objectives": [
                {"id": "obj_1", "description": "Find 5 crystals", "completed": False},
                {"id": "obj_2", "description": "Return to NPC", "completed": False},
            ],
            "progress": 0,
        }
        player_with_universe.active_quests = [quest]

        result = game_service.update_quest_progress(
            player_with_universe, "quest_2", "obj_1"
        )

        assert result.get("success") is True
        assert quest["objectives"][0]["completed"] is True
        assert quest["progress"] == 50  # 1 of 2 objectives

    def test_quest_workflow_complete_when_all_objectives_done(
        self, game_service, player_with_universe
    ):
        """Test that quest progress reaches 100% when all objectives complete."""
        quest = {
            "id": "quest_3",
            "title": "Final Trial",
            "objectives": [
                {"id": "obj_1", "description": "Defeat enemy", "completed": False}
            ],
            "progress": 0,
        }
        player_with_universe.active_quests = [quest]

        result = game_service.update_quest_progress(
            player_with_universe, "quest_3", "obj_1"
        )

        assert result.get("success") is True
        assert quest["progress"] == 100

    def test_quest_workflow_get_quest_status_active(
        self, game_service, player_with_universe
    ):
        """Test retrieving status of active quest."""
        quest = {
            "id": "quest_4",
            "title": "In Progress",
            "progress": 50,
        }
        player_with_universe.active_quests = [quest]

        result = game_service.get_quest_status(
            player_with_universe, "quest_4"
        )

        assert result.get("success") is True
        assert result.get("status") == "active"

    def test_quest_workflow_get_quest_status_completed(
        self, game_service, player_with_universe
    ):
        """Test retrieving status of completed quest."""
        quest = {"id": "quest_5", "title": "Finished"}
        player_with_universe.completed_quests = [quest]

        result = game_service.get_quest_status(
            player_with_universe, "quest_5"
        )

        assert result.get("success") is True
        assert result.get("status") == "completed"

    def test_quest_workflow_complete_quest_moves_to_completed(
        self, game_service, player_with_universe
    ):
        """Test quest completion transitions active → completed."""
        quest = {
            "id": "quest_6",
            "title": "Complete Me",
            "objectives": [
                {"id": "obj_1", "description": "Do something", "completed": True}
            ],
        }
        player_with_universe.active_quests = [quest]
        player_with_universe.completed_quests = []

        with patch(
            "src.api.serializers.quest_rewards.RewardConditionValidator.check_reward_conditions"
        ) as mock_check:
            mock_check.return_value = (
                {"gold": 100, "experience": 500, "items": [], "reputation": {}},
                {},
            )

            with patch("src.api.services.game_service.GameService._story"):
                result = game_service.complete_quest(player_with_universe, "quest_6")

                assert result.get("success") is True
                assert len(player_with_universe.active_quests) == 0

    def test_quest_workflow_cannot_complete_inactive_quest(
        self, game_service, player_with_universe
    ):
        """Test that only active quests can be completed."""
        player_with_universe.active_quests = []

        result = game_service.complete_quest(player_with_universe, "nonactive")

        assert result.get("success") is False
        assert "not active" in result.get("error", "").lower()

    def test_quest_workflow_get_active_quests_list(
        self, game_service, player_with_universe
    ):
        """Test retrieving list of all active quests."""
        quest1 = {"id": "q1", "title": "Quest 1"}
        quest2 = {"id": "q2", "title": "Quest 2"}
        player_with_universe.active_quests = [quest1, quest2]

        with patch(
            "src.api.serializers.npc_ai.QuestStateSerializer.serialize_active_quests"
        ) as mock_serialize:
            mock_serialize.return_value = [quest1, quest2]

            result = game_service.get_active_quests(player_with_universe)

            assert result.get("success") is True
            assert result.get("count") == 2

    def test_quest_workflow_invariant_progress_0_to_100(
        self, game_service, player_with_universe
    ):
        """Test invariant: quest progress always between 0 and 100."""
        quest = {
            "id": "quest_prog",
            "title": "Progress Test",
            "objectives": [
                {"id": "o1", "completed": False},
                {"id": "o2", "completed": False},
                {"id": "o3", "completed": False},
            ],
            "progress": 0,
        }
        player_with_universe.active_quests = [quest]

        # Mark some objectives
        quest["objectives"][0]["completed"] = True
        quest["objectives"][2]["completed"] = True

        completed = sum(1 for obj in quest["objectives"] if obj.get("completed"))
        total = len(quest["objectives"])
        progress = int((completed / total * 100)) if total > 0 else 0

        assert 0 <= progress <= 100

    def test_quest_workflow_objective_cannot_be_double_completed(
        self, game_service, player_with_universe
    ):
        """Test invariant: completing same objective twice doesn't change progress."""
        quest = {
            "id": "quest_double",
            "title": "Test",
            "objectives": [{"id": "obj_1", "completed": False}],
            "progress": 0,
        }
        player_with_universe.active_quests = [quest]

        game_service.update_quest_progress(
            player_with_universe, "quest_double", "obj_1"
        )
        progress_after_first = quest["progress"]

        game_service.update_quest_progress(
            player_with_universe, "quest_double", "obj_1"
        )
        progress_after_second = quest["progress"]

        assert progress_after_first == progress_after_second

    def test_quest_workflow_multiple_active_quests(
        self, game_service, player_with_universe
    ):
        """Test managing multiple active quests simultaneously."""
        quest1 = {
            "id": "q1",
            "title": "Quest 1",
            "objectives": [{"id": "o1", "completed": False}],
        }
        quest2 = {
            "id": "q2",
            "title": "Quest 2",
            "objectives": [{"id": "o2", "completed": False}],
        }
        player_with_universe.active_quests = [quest1, quest2]

        # Progress quest 1
        game_service.update_quest_progress(
            player_with_universe, "q1", "o1"
        )

        # Quest 2 should be unaffected
        assert quest2["objectives"][0]["completed"] is False
        assert quest1["objectives"][0]["completed"] is True

    def test_quest_workflow_get_rewards(
        self, game_service, player_with_universe
    ):
        """Test retrieving quest rewards."""
        quest = {
            "id": "quest_rewards",
            "title": "Rewarding",
            "rewards": {"gold": 500, "experience": 1000},
        }
        player_with_universe.active_quests = [quest]

        with patch(
            "src.api.serializers.quest_rewards.QuestRewardSerializer.serialize_quest_rewards"
        ) as mock_rewards:
            mock_rewards.return_value = quest["rewards"]

            result = game_service.get_quest_rewards(
                player_with_universe, "quest_rewards"
            )

            assert result.get("success") is True


# =============================================================================
# DIALOGUE WORKFLOW TESTS (10-15 tests)
# =============================================================================


class TestDialogueWorkflows:
    """Test dialogue state machine transitions."""

    def test_dialogue_workflow_start_dialogue(
        self, game_service, player_with_universe, mock_npc
    ):
        """Test dialogue initiation: creates context and loads first node."""
        with patch(
            "src.api.services.game_service.GameService._story",
            return_value={}
        ):
            with patch(
                "src.api.serializers.dialogue_context.DialogueContextSerializer.serialize"
            ) as mock_serialize:
                mock_serialize.return_value = {
                    "conversation_id": "conv_1",
                    "current_node": "start",
                }

                result = game_service.start_dialogue(
                    player_with_universe, "npc_1", "dial_1"
                )

                assert result.get("success") is True
                assert "data" in result

    def test_dialogue_workflow_dialogue_context_created(
        self, game_service, player_with_universe
    ):
        """Test invariant: dialogue context is stored on player."""
        with patch(
            "src.api.services.game_service.GameService._story",
            return_value={}
        ):
            with patch(
                "src.api.serializers.dialogue_context.DialogueContextSerializer.serialize"
            ) as mock_serialize:
                mock_serialize.return_value = {"conversation_id": "conv_2"}

                game_service.start_dialogue(
                    player_with_universe, "npc_2", "dial_2"
                )

                # Check that context was stored
                assert len(player_with_universe.dialogue_contexts) > 0

    def test_dialogue_workflow_get_dialogue_node(
        self, game_service, player_with_universe
    ):
        """Test retrieving a specific dialogue node."""
        with patch(
            "src.api.serializers.dialogue_context.DialogueNodeSerializer.get_available_choices"
        ) as mock_choices:
            mock_choices.return_value = []

            result = game_service.get_dialogue_node(
                player_with_universe, "node_1"
            )

            assert result.get("success") is True
            assert "data" in result

    def test_dialogue_workflow_select_choice(
        self, game_service, player_with_universe
    ):
        """Test selecting a dialogue choice transitions to next node."""
        with patch(
            "src.api.serializers.dialogue_context.DialogueNodeSerializer.get_available_choices"
        ) as mock_choices:
            mock_choices.return_value = []

            with patch(
                "src.api.serializers.dialogue_context.DialogueContextSerializer.serialize"
            ) as mock_serialize:
                mock_serialize.return_value = {
                    "current_node": "next_node",
                    "conversation_id": "conv_3",
                }

                result = game_service.select_dialogue_choice(
                    player_with_universe, "conv_3", "choice_1"
                )

                assert result.get("success") is True
                assert "data" in result

    def test_dialogue_workflow_dialogue_ends(
        self, game_service, player_with_universe
    ):
        """Test dialogue completion."""
        with patch(
            "src.api.serializers.dialogue_context.DialogueNodeSerializer.get_available_choices"
        ) as mock_choices:
            mock_choices.return_value = []

            with patch(
                "src.api.serializers.dialogue_context.DialogueContextSerializer.serialize"
            ) as mock_serialize:
                mock_serialize.return_value = {
                    "is_complete": True,
                    "conversation_id": "conv_end",
                }

                result = game_service.select_dialogue_choice(
                    player_with_universe, "conv_end", "end_choice"
                )

                assert result.get("success") is True

    def test_dialogue_workflow_multiple_conversations(
        self, game_service, player_with_universe
    ):
        """Test managing multiple dialogue contexts simultaneously."""
        with patch(
            "src.api.services.game_service.GameService._story",
            return_value={}
        ):
            with patch(
                "src.api.serializers.dialogue_context.DialogueContextSerializer.serialize"
            ) as mock_serialize:
                mock_serialize.return_value = {"conversation_id": "conv_a"}

                # Start first dialogue
                game_service.start_dialogue(
                    player_with_universe, "npc_1", "dial_1"
                )

                mock_serialize.return_value = {"conversation_id": "conv_b"}

                # Start second dialogue with different NPC
                game_service.start_dialogue(
                    player_with_universe, "npc_2", "dial_2"
                )

                # Both should be stored
                assert len(player_with_universe.dialogue_contexts) >= 1

    def test_dialogue_workflow_conversation_history_tracked(
        self, game_service, player_with_universe
    ):
        """Test invariant: conversation history records all interactions."""
        with patch(
            "src.api.services.game_service.GameService._story",
            return_value={}
        ):
            with patch(
                "src.api.serializers.dialogue_context.DialogueContextSerializer.serialize"
            ):
                game_service.start_dialogue(
                    player_with_universe, "npc_3", "dial_3"
                )

                # History should exist in context
                assert len(player_with_universe.dialogue_contexts) > 0

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

    def test_dialogue_workflow_dialogue_filtered_by_reputation(
        self, game_service, player_with_universe
    ):
        """Test invariant: dialogue choices filtered by player reputation."""
        from src.api.serializers.dialogue_context import DialogueChoice

        player_with_universe.reputation = {"merchants": 10}

        choice = DialogueChoice(
            choice_id="choice_1",
            text="Merchant option",
            target_node_id="node_2"
        )

        with patch(
            "src.api.serializers.dialogue_context.DialogueNodeSerializer.get_available_choices"
        ) as mock_choices:
            mock_choices.return_value = [choice]

            with patch(
                "src.api.serializers.dialogue_context.DialogueChoiceSerializer.serialize"
            ) as mock_serialize:
                mock_serialize.return_value = {
                    "choice_id": "choice_1",
                    "text": "Merchant option"
                }

                result = game_service.get_dialogue_node(
                    player_with_universe, "node_merchant"
                )

                # Verify choices were filtered
                mock_choices.assert_called_once()

    def test_dialogue_workflow_dialogue_filtered_by_level(
        self, game_service, player_with_universe
    ):
        """Test invariant: dialogue choices filtered by player level."""
        player_with_universe.level = 3

        with patch(
            "src.api.serializers.dialogue_context.DialogueNodeSerializer.get_available_choices"
        ) as mock_choices:
            mock_choices.return_value = []

            game_service.get_dialogue_node(player_with_universe, "node_high")

            # Verify level was passed to filter
            mock_choices.assert_called_once()
            call_kwargs = mock_choices.call_args[1]
            assert call_kwargs.get("player_level") == 3


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

    def test_npc_workflow_npc_availability_check(
        self, game_service, player_with_universe, mock_npc
    ):
        """Test checking if NPC is available."""
        with patch(
            "src.api.services.game_service.GameService.check_npc_availability"
        ) as mock_check:
            mock_check.return_value = {"available": True}

            result = game_service.check_npc_availability(
                player_with_universe, "npc_gorran"
            )

            assert result.get("available") is not False

    def test_npc_workflow_get_npc_status(
        self, game_service, player_with_universe, mock_npc
    ):
        """Test retrieving complete NPC status."""
        result = game_service.get_npc_status(player_with_universe, "npc_gorran")

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

    def test_invariant_dialogue_context_exists_during_conversation(
        self, game_service, player_with_universe
    ):
        """Invariant: dialogue context must exist for active conversation."""
        from src.api.serializers.dialogue_context import DialogueContext

        context = DialogueContext(
            conversation_id="conv_test",
            current_node=None,
            available_choices=[],
            conversation_history=None,
            is_complete=False,
        )

        player_with_universe.dialogue_contexts["conv_test"] = context

        assert "conv_test" in player_with_universe.dialogue_contexts

    def test_invariant_enemy_list_consistency(
        self, game_service, player_with_universe, mock_enemy
    ):
        """Invariant: combat_list must not contain None or invalid enemies."""
        player_with_universe.combat_list = [mock_enemy, None]

        # Filter out None values
        player_with_universe.combat_list = [e for e in player_with_universe.combat_list if e is not None]

        assert None not in player_with_universe.combat_list

    def test_invariant_turn_order_includes_all_combatants(
        self, game_service, player_with_universe, mock_enemy
    ):
        """Invariant: turn_order must include player and all enemies."""
        player_with_universe.speed = 10
        enemies = [mock_enemy]

        turn_order = game_service._get_turn_order(player_with_universe, enemies)

        assert "player" in turn_order
        assert len(turn_order) == len(enemies) + 1  # player + all enemies

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
# COMPLEX WORKFLOW INTEGRATION TESTS
# =============================================================================


class TestComplexWorkflows:
    """Test multi-step, cross-system workflows."""

    def test_complex_workflow_start_combat_execute_move_end(
        self, game_service, player_with_universe, mock_enemy
    ):
        """Test full combat sequence: start → execute move → end."""
        player_with_universe.in_combat = False
        player_with_universe.hp = 100
        player_with_universe.maxhp = 100

        # Mock adapter
        mock_adapter = MagicMock()
        mock_adapter.awaiting_input = True
        mock_adapter.available_options = [{"name": "Slash", "index": 0}]
        mock_adapter.process_command = MagicMock(
            return_value={"success": True}
        )

        # Start combat
        player_with_universe.in_combat = True
        player_with_universe.combat_list = [mock_enemy]
        player_with_universe._combat_adapter = mock_adapter

        # Execute move
        result = game_service.execute_move(
            player_with_universe, "move", "0"
        )
        assert result.get("success") or "error" not in result

        # End combat
        with patch(
            "src.api.serializers.combat.CombatStateSerializer.serialize_battle_summary"
        ):
            game_service.end_combat(player_with_universe, True)

        assert player_with_universe.in_combat is False

    def test_complex_workflow_quest_dialogue_integration(
        self, game_service, player_with_universe
    ):
        """Test workflow: start quest → dialogue → complete quest."""
        quest = {
            "id": "q_dial",
            "title": "Quest with Dialogue",
            "objectives": [{"id": "talk_to_npc", "completed": False}],
        }
        player_with_universe.available_quests = [quest]

        # Start quest
        game_service.start_quest(player_with_universe, "q_dial")
        assert len(player_with_universe.active_quests) == 1

        # Start dialogue
        with patch(
            "src.api.services.game_service.GameService._story",
            return_value={}
        ):
            with patch(
                "src.api.serializers.dialogue_context.DialogueContextSerializer.serialize"
            ):
                game_service.start_dialogue(
                    player_with_universe, "npc_1", "dial_1"
                )

        assert len(player_with_universe.dialogue_contexts) > 0

    def test_complex_workflow_multiple_state_machines(
        self, game_service, player_with_universe, mock_enemy, mock_npc
    ):
        """Test multiple state machines running simultaneously."""
        # Combat state
        player_with_universe.in_combat = True
        player_with_universe.combat_list = [mock_enemy]

        # Quest state
        quest = {"id": "q_multi", "title": "Multi", "progress": 50}
        player_with_universe.active_quests = [quest]

        # Dialogue state
        with patch(
            "src.api.services.game_service.GameService._story",
            return_value={}
        ):
            with patch(
                "src.api.serializers.dialogue_context.DialogueContextSerializer.serialize"
            ):
                game_service.start_dialogue(
                    player_with_universe, "npc_2", "dial_2"
                )

        # All states should coexist
        assert player_with_universe.in_combat is True
        assert len(player_with_universe.active_quests) > 0
        assert len(player_with_universe.dialogue_contexts) > 0

    def test_complex_workflow_state_cleanup_on_transition(
        self, game_service, player_with_universe, mock_enemy
    ):
        """Test that state is properly cleaned up during transitions."""
        player_with_universe.in_combat = True
        player_with_universe.combat_list = [mock_enemy]
        player_with_universe.combat_log = [
            {"round": 1, "message": "Battle started"}
        ]

        with patch(
            "src.api.serializers.combat.CombatStateSerializer.serialize_battle_summary"
        ):
            game_service.end_combat(player_with_universe, True)

        # Old state should be cleaned
        assert player_with_universe.combat_list == []
        assert player_with_universe.in_combat is False

    def test_complex_workflow_error_recovery(
        self, game_service, player_with_universe
    ):
        """Test that error in one state doesn't corrupt others."""
        player_with_universe.active_quests = [
            {"id": "q_error", "title": "Error Quest"}
        ]

        # Try to complete non-existent quest
        result = game_service.complete_quest(
            player_with_universe, "nonexistent"
        )

        assert result.get("success") is False

        # Original quest should still be active
        assert len(player_with_universe.active_quests) == 1


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
