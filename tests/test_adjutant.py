import pytest
from unittest.mock import MagicMock, patch
from npc._adjutant import TheAdjutant
from npc._enemies import Slime

class MockPlayer:
    def __init__(self):
        self.hp = 100
        self.maxhp = 100
        self.heat = 1.0
        self.fatigue = 10
        self.maxfatigue = 10
        self.level = 1
        self.exp = 0
        self.exp_to_level = 100
        self.strength = 10
        self.finesse = 10
        self.speed = 10
        self.endurance = 10
        self.charisma = 10
        self.intelligence = 10
        self.faith = 10
        self.strength_base = 10
        self.finesse_base = 10
        self.speed_base = 10
        self.endurance_base = 10
        self.charisma_base = 10
        self.intelligence_base = 10
        self.faith_base = 10
        self.known_moves = []
        self.map = None
        self.recall_friends = MagicMock()

def test_adjutant_basic_properties():
    adj = TheAdjutant()
    assert adj.name == "The Adjutant"
    assert adj.keywords == ["talk", "set", "adjust", "configure", "help"]
    assert adj.pronouns["personal"] == "it"
    assert len(adj.known_moves) > 0

@patch("builtins.print")
def test_adjutant_keyword_dispatches(mock_print):
    adj = TheAdjutant()
    player = MockPlayer()
    
    with patch.object(adj, "_adjutant_menu") as mock_menu:
        adj.talk(player)
        adj.set(player)
        adj.adjust(player)
        adj.configure(player)
        adj.help(player)
        assert mock_menu.call_count == 5

@patch("builtins.print")
def test_adjutant_menu_exit(mock_print):
    adj = TheAdjutant()
    player = MockPlayer()
    
    with patch("builtins.input", side_effect=["0"]):
        adj._adjutant_menu(player)

@patch("builtins.print")
def test_adjutant_menu_set_hp(mock_print):
    adj = TheAdjutant()
    player = MockPlayer()

    # Test valid HP change
    with patch("builtins.input", side_effect=["1", "15", "30", "0"]):
        adj._adjutant_menu(player)
        assert player.maxhp == 30
        assert player.hp == 15

    # Test invalid input handling
    with patch("builtins.input", side_effect=["1", "invalid", "0"]):
        adj._adjutant_menu(player)

@patch("builtins.print")
def test_adjutant_menu_set_level_and_exp(mock_print):
    adj = TheAdjutant()
    player = MockPlayer()

    with patch("builtins.input", side_effect=["2", "10", "500", "0"]):
        adj._adjutant_menu(player)
        assert player.level == 10
        assert player.exp == 500

    with patch("builtins.input", side_effect=["2", "invalid", "0"]):
        adj._adjutant_menu(player)

@patch("builtins.print")
def test_adjutant_menu_set_attributes(mock_print):
    adj = TheAdjutant()
    player = MockPlayer()

    # Input: choice "3", strength->15, finesse->(blank/skip), others invalid/blank, then exit
    with patch("builtins.input", side_effect=["3", "15", "", "invalid", "", "", "", "", "0"]):
        adj._adjutant_menu(player)
        assert player.strength == 15
        assert player.strength_base == 15

@patch("builtins.print")
def test_adjutant_menu_set_heat(mock_print):
    adj = TheAdjutant()
    player = MockPlayer()

    with patch("builtins.input", side_effect=["4", "2.5", "0"]):
        adj._adjutant_menu(player)
        assert player.heat == 2.5

    with patch("builtins.input", side_effect=["4", "invalid", "0"]):
        adj._adjutant_menu(player)

@patch("builtins.print")
def test_adjutant_menu_restore(mock_print):
    adj = TheAdjutant()
    player = MockPlayer()
    player.hp = 5
    player.fatigue = 2

    with patch("builtins.input", side_effect=["5", "0"]):
        adj._adjutant_menu(player)
        assert player.hp == 100
        assert player.fatigue == 10

@patch("builtins.print")
def test_adjutant_menu_learn_all_skills(mock_print):
    adj = TheAdjutant()
    player = MockPlayer()

    # Successful skills learning
    with patch("functions.learn_all_skills_from_skilltree") as mock_learn:
        with patch("builtins.input", side_effect=["6", "0"]):
            adj._adjutant_menu(player)
            assert mock_learn.called

    # Exception handling
    with patch("functions.learn_all_skills_from_skilltree", side_effect=Exception("Failed")):
        with patch("builtins.input", side_effect=["6", "0"]):
            adj._adjutant_menu(player)

@patch("builtins.print")
def test_adjutant_menu_list_moves(mock_print):
    adj = TheAdjutant()
    player = MockPlayer()
    
    # Empty moves
    player.known_moves = []
    with patch("builtins.input", side_effect=["7", "0"]):
        adj._adjutant_menu(player)

    # With moves
    move = MagicMock()
    move.name = "Thrust"
    player.known_moves = [move]
    with patch("builtins.input", side_effect=["7", "0"]):
        adj._adjutant_menu(player)

@patch("builtins.print")
def test_adjutant_menu_invalid_and_combatant_flow(mock_print):
    adj = TheAdjutant()
    player = MockPlayer()
    
    with patch("builtins.input", side_effect=["99", "0"]):
        adj._adjutant_menu(player)

@patch("builtins.print")
def test_combatant_menu_options(mock_print):
    adj = TheAdjutant()
    player = MockPlayer()
    
    # Mock arena tiles
    fodder_pit_tile = MagicMock()
    fodder_pit_tile.npcs_here = []
    
    player.map = {
        (1, 0): fodder_pit_tile,
        (2, 0): None, # Not loaded
    }
    
    # Test sub-menu exit, invalid option
    with patch("builtins.input", side_effect=["8", "99", "0", "0"]):
        adj._adjutant_menu(player)

@patch("builtins.print")
def test_add_combatant(mock_print):
    adj = TheAdjutant()
    player = MockPlayer()
    
    tile = MagicMock()
    tile.npcs_here = []
    player.map = {
        (1, 0): tile
    }
    
    # 1. Pick cancel
    with patch("builtins.input", side_effect=["8", "1", "0", "0", "0"]):
        adj._adjutant_menu(player)
        assert len(tile.npcs_here) == 0

    # 2. Pick fodder pit (1), add Slime
    with patch("builtins.input", side_effect=["8", "1", "1", "Slime", "0", "0"]):
        adj._adjutant_menu(player)
        assert len(tile.npcs_here) == 1
        assert tile.npcs_here[0].__class__.__name__ == "Slime"

    # 3. Pick fodder pit (1), invalid class, empty input
    with patch("builtins.input", side_effect=["8", "1", "1", "", "0", "0"]):
        adj._adjutant_menu(player)

    with patch("builtins.input", side_effect=["8", "1", "1", "FakeClass", "0", "0"]):
        adj._adjutant_menu(player)

    # 4. Attempt to add to a non-loaded tile
    with patch("builtins.input", side_effect=["8", "1", "2", "0", "0"]): # Choose Crucible (2) which is None
        player.map = {(2, 0): None}
        adj._adjutant_menu(player)

@patch("builtins.print")
def test_remove_combatant(mock_print):
    adj = TheAdjutant()
    player = MockPlayer()
    
    tile = MagicMock()
    slime1 = Slime()
    tile.npcs_here = [slime1]
    player.map = {
        (1, 0): tile
    }
    
    # 1. Remove cancel
    with patch("builtins.input", side_effect=["8", "2", "1", "0", "0", "0"]):
        adj._adjutant_menu(player)
        assert len(tile.npcs_here) == 1

    # 2. Remove index 1
    with patch("builtins.input", side_effect=["8", "2", "1", "1", "0", "0"]):
        adj._adjutant_menu(player)
        assert len(tile.npcs_here) == 0

    # 3. Remove from empty tile
    with patch("builtins.input", side_effect=["8", "2", "1", "0", "0"]):
        adj._adjutant_menu(player)

@patch("builtins.print")
def test_clear_room(mock_print):
    adj = TheAdjutant()
    player = MockPlayer()
    
    tile = MagicMock()
    tile.npcs_here = [Slime(), Slime()]
    player.map = {
        (1, 0): tile
    }
    
    with patch("builtins.input", side_effect=["8", "3", "1", "0", "0"]):
        adj._adjutant_menu(player)
        assert len(tile.npcs_here) == 0

@patch("builtins.print")
def test_set_combatant_stats(mock_print):
    adj = TheAdjutant()
    player = MockPlayer()
    
    tile = MagicMock()
    npc = Slime()
    tile.npcs_here = [npc]
    player.map = {
        (1, 0): tile
    }
    
    # Edit NPC: hp->50, maxhp->100, aggro->false, friend->true, others blank
    inputs = [
        "8", "4", "1", "1", 
        "50", "100", "10", "5", "3", "12", "15", "8", "10", "10", "10", "10",
        "false", "true", "0", "0"
    ]
    with patch("builtins.input", side_effect=inputs):
        adj._adjutant_menu(player)
        assert npc.hp == 50
        assert npc.maxhp == 100
        assert npc.aggro is False
        assert npc.friend is True

    # Test select cancel and invalid indices
    inputs = [
        "8", "4", "1", "0", "0", "0"
    ]
    with patch("builtins.input", side_effect=inputs):
        adj._adjutant_menu(player)

    # Test when npc list empty
    tile.npcs_here = []
    inputs = [
        "8", "4", "1", "0", "0"
    ]
    with patch("builtins.input", side_effect=inputs):
        adj._adjutant_menu(player)

    # Test invalid string instead of int select
    tile.npcs_here = [npc]
    inputs = [
        "8", "4", "1", "invalid", "0", "0"
    ]
    with patch("builtins.input", side_effect=inputs):
        adj._adjutant_menu(player)

    # Test invalid stat values (should skip)
    inputs = [
        "8", "4", "1", "1",
        "invalid", "", "", "", "", "", "", "", "", "", "", "",
        "invalid_bool", "invalid_bool", "0", "0"
    ]
    with patch("builtins.input", side_effect=inputs):
        adj._adjutant_menu(player)
