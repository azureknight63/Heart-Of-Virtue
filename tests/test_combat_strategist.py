import pytest
import json
from unittest.mock import MagicMock, patch
from ai.combat_strategist import CombatStrategist
from ai.llm_client import GenericLLMClient

class MockLLMClient:
    def __init__(self):
        self.provider = "ollama"
        self._available = True
    
    def available(self):
        return self._available
    
    def generate_structured(self, system_prompt, user_prompt):
        return {
            "suggestions": [
                {
                    "move_name": "Slash",
                    "target_id": "enemy_1",
                    "score": 85,
                    "reasoning": "High damage potential."
                },
                {
                    "move_name": "Dodge",
                    "target_id": None,
                    "score": 60,
                    "reasoning": "Stay safe."
                }
            ]
        }

@pytest.fixture
def strategist():
    mock_client = MockLLMClient()
    return CombatStrategist(client=mock_client)

def test_get_suggestions_success(strategist):
    ctx = {
        "player": {"hp": 100},
        "enemies": [],
        "history": [],
        "last_move": "None",
        "available_moves": []
    }
    
    suggestions = strategist.get_suggestions(ctx, max_suggestions=1)
    
    assert len(suggestions) == 1
    assert suggestions[0]["move_name"] == "Slash"
    assert suggestions[0]["score"] == 85

def test_get_suggestions_sorting(strategist):
    ctx = {}
    suggestions = strategist.get_suggestions(ctx, max_suggestions=10)
    
    assert len(suggestions) == 2
    assert suggestions[0]["score"] == 85
    assert suggestions[1]["score"] == 60

def test_get_suggestions_unavailable(strategist):
    strategist.client._available = False
    ctx = {}
    suggestions = strategist.get_suggestions(ctx)
    assert suggestions == []

def test_build_user_prompt(strategist):
    ctx = {
        "player": {
            "name": "Jean",
            "hp": 50,
            "max_hp": 100,
            "fatigue": 20,
            "max_fatigue": 150,
            "heat": 1.2,
            "x": 2, "y": 2,
            "facing": "N",
            "attributes": {"strength": 15},
            "passives": ["Strategic Insight"],
            "active_effects": [],
            "consumables": [{"name": "Health Potion", "qty": 1, "value": 50}]
        },
        "enemies": [
            {
                "name": "Bat",
                "id": "enemy_1",
                "hp": 10,
                "max_hp": 10,
                "x": 2, "y": 3,
                "distance": 5,
                "facing": "S",
                "attributes": {"strength": 5},
                "move_in_process": None
            }
        ],
        "history": ["Jean attacks Bat!", "Bat misses Jean!"],
        "last_move": "Attack",
        "available_moves": [{"name": "Slash"}, {"name": "Dodge"}]
    }
    
    prompt = strategist._build_user_prompt(ctx)
    
    assert "Jean [HP: 50/100" in prompt
    assert "Heat: 1.2" in prompt
    assert "Strategic Insight" in prompt
    assert "Health Potion" in prompt
    assert "Bat [ID: enemy_1" in prompt
    assert "Dist: 5ft" in prompt
    assert "Jean attacks Bat!" in prompt
    assert "Available Moves: Slash, Dodge" in prompt

def test_malformed_json_handling(strategist):
    with patch.object(strategist.client, 'generate_structured', return_value="not a dict"):
        suggestions = strategist.get_suggestions({})
        assert suggestions == []

def test_non_list_suggestions_handling(strategist):
    with patch.object(strategist.client, 'generate_structured', return_value={"suggestions": "invalid"}):
        suggestions = strategist.get_suggestions({})
        assert suggestions == []
