import pytest
from unittest.mock import MagicMock, patch, ANY
from src.api.combat_adapter import ApiCombatAdapter
from src.player import Player

class MockMove:
    def __init__(self, name, passive=False, viable=True):
        self.name = name
        self.passive = passive
        self._viable = viable
        self.fatigue_cost = 0
        self.current_stage = 0
        self.targeted = False
        self.user = None
        self.target = None
        self.description = "Test move"
        self.category = "Offensive"
    
    def viable(self):
        return self._viable
    
    def cast(self):
        pass
        
    def advance(self, user):
        user.current_move = None

@pytest.fixture
def player():
    p = Player()
    p.name = "Jean"
    p.known_moves = [
        MockMove("Slash"),
        MockMove("Quiet Guard", passive=True),
        MockMove("Dodge")
    ]
    p.combat_log = []
    p.last_move_summary = ""
    p.combat_beat = 1
    return p

@pytest.fixture
def adapter(player):
    with patch('src.api.combat_adapter.CombatStrategist') as mock_strat_cls:
        mock_strat = mock_strat_cls.return_value
        mock_strat.get_suggestions.return_value = [
            {"move_name": "Slash", "score": 90, "reasoning": "Strong attack."}
        ]
        adapter = ApiCombatAdapter(player)
        return adapter

def test_available_moves_filters_passives(adapter, player):
    moves = adapter._get_available_moves()
    # Slash and Dodge should be present, Quiet Guard should be filtered out
    names = [m["name"] for m in moves]
    assert "Slash" in names
    assert "Dodge" in names
    assert "Quiet Guard" not in names

def test_refresh_suggestions_count(adapter, player):
    # Base count is 1
    with patch('threading.Thread') as mock_thread, \
         patch.object(adapter.strategist, 'get_suggestions', return_value=[]) as mock_get:
        # Make the thread run synchronously
        mock_thread.side_effect = lambda target, **kwargs: MagicMock(start=lambda: target())
        
        adapter.refresh_suggestions()
        mock_get.assert_called_with(ANY, max_suggestions=1)

    # Add Strategic Insight (increases count by 1)
    player.known_moves.append(MockMove("Strategic Insight", passive=True))
    with patch('threading.Thread') as mock_thread, \
         patch.object(adapter.strategist, 'get_suggestions', return_value=[]) as mock_get:
        mock_thread.side_effect = lambda target, **kwargs: MagicMock(start=lambda: target())
        
        adapter.refresh_suggestions()
        mock_get.assert_called_with(ANY, max_suggestions=2)

    # Add Master Tactician (increases count by 1 more)
    player.known_moves.append(MockMove("Master Tactician", passive=True))
    with patch('threading.Thread') as mock_thread, \
         patch.object(adapter.strategist, 'get_suggestions', return_value=[]) as mock_get:
        mock_thread.side_effect = lambda target, **kwargs: MagicMock(start=lambda: target())
        
        adapter.refresh_suggestions()
        mock_get.assert_called_with(ANY, max_suggestions=3)

def test_handle_combined_selection(adapter, player):
    adapter.input_type = "move_selection"
    adapter.awaiting_input = True
    
    # Mocking _execute_move instead of doing full combat processing
    with patch.object(adapter, '_execute_move', return_value={"success": True}) as mock_exec:
        result = adapter._handle_combined_selection("Slash", "enemy_123")
        
        selected_move = player.current_move
        assert selected_move.name == "Slash"
        # Check if target ID was parsed (ApiCombatAdapter usually does this manually, let's just check if it tried to find target)
        # Note: If no combatants exist, it would return error. Let's add a dummy enemy.
        mock_exec.assert_called()

def test_process_command_routes_combined_action(adapter):
    adapter.awaiting_input = True
    with patch.object(adapter, '_handle_combined_selection', return_value={"success": True}) as mock_handle:
        cmd = {
            "type": "select_move_and_target",
            "move_name": "Slash",
            "target_id": "enemy_1"
        }
        adapter.process_command(cmd)
        mock_handle.assert_called_with("Slash", "enemy_1")

def test_last_move_summary_capture(adapter, player):
    player.combat_log = [
        {"message": "Jean used Slash!", "type": "player_action"},
        {"message": "Jean hit Rat for 5 damage.", "type": "combat"}
    ]
    
    # Simulate end of move execution
    with patch.object(adapter, 'get_combat_state', return_value={}):
        adapter.player.combat_list = [] # Exit loop
        adapter._execute_move(player.known_moves[0])
    
    assert "Jean used Slash!" in player.last_move_summary
    assert "Jean hit Rat for 5 damage." in player.last_move_summary
