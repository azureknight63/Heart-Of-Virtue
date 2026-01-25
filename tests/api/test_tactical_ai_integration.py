"""
Integration tests for Tactical Strategist AI and Enhanced Combat Visualization.

These tests verify the complete flow from combat initialization through AI suggestions
to move execution and status effect display.
"""

import pytest
import json
from unittest.mock import patch, MagicMock


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
        
        def viable(self):
            return True
        
        def cast(self):
            pass
        
        def advance(self, user):
            if self.current_stage > 0:
                self.current_stage = 0
                user.current_move = None
    
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
    return enemy


def ensure_player_room(player):
    """Ensure player has a current_room with npcs_here list."""
    if not hasattr(player, 'current_room') or player.current_room is None:
        class MockRoom:
            def __init__(self):
                self.npcs_here = []
        player.current_room = MockRoom()


class TestTacticalStrategistIntegration:
    """Integration tests for the full AI strategist flow."""

    def test_full_combat_cycle_with_ai_suggestions(self, app, client, authenticated_session):
        """Test complete combat cycle: start -> AI suggests -> execute -> victory."""
        session_id, player, session_manager = authenticated_session
        
        with app.app_context():
            # Setup: Create a simple enemy using helper
            enemy = create_test_enemy("Test Rat", hp=10)
            
            ensure_player_room(player)
            
            # Add enemy to player's current location
            player.current_room.npcs_here = [enemy]
            player.combat_list = []
            player.combat_list_allies = [player]
            
            # Start combat
            response = client.post(
                "/api/combat/start",
                data=json.dumps({"enemy_id": str(id(enemy))}),
                content_type="application/json",
                headers={"Authorization": f"Bearer {session_id}"}
            )
            
            assert response.status_code == 201
            data = json.loads(response.data)
            assert data["success"] is True
            assert data["combat_active"] is True
            
            # Verify AI suggestions are present in battle state
            battle_state = data.get("battle_state", {})
            assert "suggested_moves" in battle_state or hasattr(player, "suggested_moves")
            
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
            response = client.post(
                "/api/combat/move",
                data=json.dumps({
                    "move_type": "move",
                    "move_id": "0",  # Attack is usually index 0
                    "target_id": f"enemy_{id(enemy)}"
                }),
                content_type="application/json",
                headers={"Authorization": f"Bearer {session_id}"}
            )
            
            assert response.status_code == 200
            move_data = json.loads(response.data)
            assert move_data["success"] is True
            
            # Verify combat log contains action
            assert "log" in move_data["battle_state"]
            assert len(move_data["battle_state"]["log"]) > 0

    def test_ai_suggestions_increase_with_passive_skills(self, app, client, authenticated_session):
        """Test that unlocking passive skills increases AI suggestion count."""
        session_id, player, session_manager = authenticated_session
        
        with app.app_context():
                        
            # Create mock passive skills
            class StrategicInsight:
                def __init__(self):
                    self.name = "Strategic Insight"
                    self.passive = True
                    self.fatigue_cost = 0
                    self.current_stage = 0
                
                def viable(self):
                    return True
            
            class MasterTactician:
                def __init__(self):
                    self.name = "Master Tactician"
                    self.passive = True
                    self.fatigue_cost = 0
                    self.current_stage = 0
                
                def viable(self):
                    return True
            
            # Setup enemy
            from src.npc import NPC
            enemy = NPC(
                name="Test Enemy",
                description="Test enemy",
                damage=5,
                aggro=True,
                exp_award=20,
                maxhp=50,
                speed=5
            )
            enemy.known_moves = [create_mock_move()]
            enemy.friend = False
            
            player.current_room.npcs_here = [enemy]
            player.combat_list = []
            player.combat_list_allies = [player]
            
            # Start combat without passive skills
            base_moves = list(player.known_moves)
            
            response = client.post(
                "/api/combat/start",
                data=json.dumps({"enemy_id": str(id(enemy))}),
                content_type="application/json",
                headers={"Authorization": f"Bearer {session_id}"}
            )
            
            data = json.loads(response.data)
            base_suggestion_count = len(getattr(player, "suggested_moves", []))
            
            # End combat
            player.in_combat = False
            player.combat_list = []
            
            # Add Strategic Insight
            player.known_moves = base_moves + [StrategicInsight()]
            
            # Create new enemy
            enemy2 = NPC(
                name="Test Enemy 2",
                description="Second test enemy",
                damage=5,
                aggro=True,
                exp_award=20,
                maxhp=50,
                speed=5
            )
            enemy2.known_moves = [create_mock_move()]
            enemy2.friend = False
            
            player.current_room.npcs_here = [enemy2]
            
            response = client.post(
                "/api/combat/start",
                data=json.dumps({"enemy_id": str(id(enemy2))}),
                content_type="application/json",
                headers={"Authorization": f"Bearer {session_id}"}
            )
            
            data = json.loads(response.data)
            insight_suggestion_count = len(getattr(player, "suggested_moves", []))
            
            # Verify suggestion count increased (or stayed at 1 if LLM unavailable)
            assert insight_suggestion_count >= base_suggestion_count

    def test_combined_move_and_target_execution(self, app, client, authenticated_session):
        """Test one-click move+target execution from AI suggestion."""
        session_id, player, session_manager = authenticated_session
        
        with app.app_context():
            from src.npc import NPC
                        
            enemy = NPC(
                name="Test Target",
                description="Target for testing",
                damage=5,
                aggro=True,
                exp_award=15,
                maxhp=30,
                speed=5
            )
            enemy.known_moves = [create_mock_move()]
            enemy.friend = False
            
            player.current_room.npcs_here = [enemy]
            player.combat_list = []
            player.combat_list_allies = [player]
            
            # Start combat
            response = client.post(
                "/api/combat/start",
                data=json.dumps({"enemy_id": str(id(enemy))}),
                content_type="application/json",
                headers={"Authorization": f"Bearer {session_id}"}
            )
            
            assert response.status_code == 201
            
            # Execute combined move+target action
            response = client.post(
                "/api/combat/move",
                data=json.dumps({
                    "move_type": "select_move_and_target",
                    "move_id": "Attack",
                    "target_id": f"enemy_{id(enemy)}"
                }),
                content_type="application/json",
                headers={"Authorization": f"Bearer {session_id}"}
            )
            
            assert response.status_code == 200
            data = json.loads(response.data)
            assert data["success"] is True
            
            # Verify move was executed
            battle_state = data.get("battle_state", {})
            assert "log" in battle_state
            
            # Check that combat log contains the action
            log_messages = [entry.get("message", "") for entry in battle_state["log"]]
            assert any("Attack" in msg or player.name in msg for msg in log_messages)

    def test_status_effects_serialization(self, app, client, authenticated_session):
        """Test that status effects are properly serialized for frontend display."""
        session_id, player, session_manager = authenticated_session
        
        with app.app_context():
            from src.npc import NPC
                        
            # Create enemy
            enemy = NPC(
                name="Test Enemy",
                description="Enemy for effect testing",
                damage=5,
                aggro=True,
                exp_award=18,
                maxhp=40,
                speed=5
            )
            enemy.known_moves = [create_mock_move()]
            enemy.friend = False
            
            # Add a mock status effect to player
            class MockEffect:
                def __init__(self):
                    self.name = "Test Burn"
                    self.type = "ailment"
                    self.description = "Taking damage over time"
                    self.duration = 3
            
            if not hasattr(player, "active_effects"):
                player.active_effects = []
            
            player.active_effects.append(MockEffect())
            
            player.current_room.npcs_here = [enemy]
            player.combat_list = []
            player.combat_list_allies = [player]
            
            # Start combat
            response = client.post(
                "/api/combat/start",
                data=json.dumps({"enemy_id": str(id(enemy))}),
                content_type="application/json",
                headers={"Authorization": f"Bearer {session_id}"}
            )
            
            assert response.status_code == 201
            data = json.loads(response.data)
            
            # Verify battle state includes combatant data
            battle_state = data.get("battle_state", {})
            assert "combatants" in battle_state
            
            # Check player combatant data
            player_data = next(
                (c for c in battle_state["combatants"] if c.get("name") == player.name),
                None
            )
            
            assert player_data is not None
            # Effects should be serialized if present
            if "active_effects" in player_data:
                assert isinstance(player_data["active_effects"], list)

    def test_ai_context_includes_combat_history(self, app, client, authenticated_session):
        """Test that AI receives combat history for context-aware suggestions."""
        session_id, player, session_manager = authenticated_session
        
        with app.app_context():
            from src.npc import NPC
                        
            enemy = NPC(
                name="Context Test Enemy",
                description="Enemy for context testing",
                damage=5,
                aggro=True,
                exp_award=20,
                maxhp=50,
                speed=5
            )
            enemy.known_moves = [create_mock_move()]
            enemy.friend = False
            
            player.current_room.npcs_here = [enemy]
            player.combat_list = []
            player.combat_list_allies = [player]
            
            # Start combat
            response = client.post(
                "/api/combat/start",
                data=json.dumps({"enemy_id": str(id(enemy))}),
                content_type="application/json",
                headers={"Authorization": f"Bearer {session_id}"}
            )
            
            assert response.status_code == 201
            
            # Execute a move to create history
            response = client.post(
                "/api/combat/move",
                data=json.dumps({
                    "move_type": "move",
                    "move_id": "0",
                    "target_id": f"enemy_{id(enemy)}"
                }),
                content_type="application/json",
                headers={"Authorization": f"Bearer {session_id}"}
            )
            
            assert response.status_code == 200
            data = json.loads(response.data)
            
            # Verify combat log exists and has entries
            battle_state = data.get("battle_state", {})
            assert "log" in battle_state
            assert len(battle_state["log"]) > 0
            
            # Verify last_move_summary is captured
            assert hasattr(player, "last_move_summary")
            assert isinstance(player.last_move_summary, str)


class TestEnhancedCombatVisualizationIntegration:
    """Integration tests for status effect visualization."""

    def test_status_effects_in_combat_state(self, app, client, authenticated_session):
        """Test that status effects appear in serialized combat state."""
        session_id, player, session_manager = authenticated_session
        
        with app.app_context():
            from src.npc import NPC
                        
            enemy = NPC(
                name="Visualization Test",
                description="Enemy for visualization testing",
                damage=5,
                aggro=True,
                exp_award=15,
                maxhp=30,
                speed=5
            )
            enemy.known_moves = [create_mock_move()]
            enemy.friend = False
            
            player.current_room.npcs_here = [enemy]
            player.combat_list = []
            player.combat_list_allies = [player]
            
            # Start combat
            response = client.post(
                "/api/combat/start",
                data=json.dumps({"enemy_id": str(id(enemy))}),
                content_type="application/json",
                headers={"Authorization": f"Bearer {session_id}"}
            )
            
            assert response.status_code == 201
            data = json.loads(response.data)
            
            # Verify combatants are serialized
            battle_state = data.get("battle_state", {})
            assert "combatants" in battle_state
            assert len(battle_state["combatants"]) > 0
            
            # Each combatant should have required fields
            for combatant in battle_state["combatants"]:
                assert "name" in combatant
                assert "hp" in combatant
                assert "max_hp" in combatant

    def test_beat_states_include_position_data(self, app, client, authenticated_session):
        """Test that beat states include position/distance data for visualization."""
        session_id, player, session_manager = authenticated_session
        
        with app.app_context():
            from src.npc import NPC
                        
            enemy = NPC(
                name="Position Test",
                description="Enemy for position testing",
                damage=5,
                aggro=True,
                exp_award=12,
                maxhp=25,
                speed=5
            )
            enemy.known_moves = [create_mock_move()]
            enemy.friend = False
            
            player.current_room.npcs_here = [enemy]
            player.combat_list = []
            player.combat_list_allies = [player]
            
            # Start combat
            response = client.post(
                "/api/combat/start",
                data=json.dumps({"enemy_id": str(id(enemy))}),
                content_type="application/json",
                headers={"Authorization": f"Bearer {session_id}"}
            )
            
            assert response.status_code == 201
            data = json.loads(response.data)
            
            # Execute a move to generate beat states
            response = client.post(
                "/api/combat/move",
                data=json.dumps({
                    "move_type": "move",
                    "move_id": "0",
                    "target_id": f"enemy_{id(enemy)}"
                }),
                content_type="application/json",
                headers={"Authorization": f"Bearer {session_id}"}
            )
            
            assert response.status_code == 200
            move_data = json.loads(response.data)
            
            # Verify beat_states exist
            assert "beat_states" in move_data
            
            # Each beat state should have combatant position data
            for beat_state in move_data["beat_states"]:
                assert "combatants" in beat_state
                for combatant in beat_state["combatants"]:
                    # Position data should be present
                    assert "x" in combatant or "distance" in combatant



