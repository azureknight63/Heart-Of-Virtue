import os
import sys
import pytest
from unittest.mock import MagicMock, patch

# Ensure both project root and src directory are on path for direct module imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

from npc._friends import (
    Mynx, Gorran, GronditePasserby, GronditeWorker,
    GronditeElder, GronditeConclaveElder, Mara, Devet, Liss
)
from items import Item
import moves

# Fakes
class FakeUniverse:
    def __init__(self):
        self.story = {}

class FakeRoom:
    def __init__(self, universe):
        self.universe = universe
        self.events_here = []

class FakePlayer:
    def __init__(self, universe):
        self.universe = universe
        self.combat_list = []

def test_mynx_basic_and_combat(monkeypatch):
    # Mock NpcIdle to raise exception to cover line 82-83
    orig_idle = moves.NpcIdle
    def faulty_idle(*args, **kwargs):
        raise Exception("Failed to init NpcIdle")
    monkeypatch.setattr(moves, 'NpcIdle', faulty_idle)
    
    m_faulty = Mynx()
    assert m_faulty.known_moves == []
    
    # Restore NpcIdle
    monkeypatch.setattr(moves, 'NpcIdle', orig_idle)

    # 1. Init with defaults
    m = Mynx()
    assert m.name.startswith("Mynx")
    assert "creature" in m.description
    assert m.can_enter_combat() is False
    
    # 2. Init with name/desc
    m2 = Mynx("CustomName", "CustomDesc")
    assert m2.name == "CustomName"
    assert m2.description == "CustomDesc"
    
    # 3. combat_engage does nothing
    player = FakePlayer(FakeUniverse())
    m.combat_engage(player)
    assert m.in_combat is False

def test_mynx_interaction_verbs():
    m = Mynx()
    player = FakePlayer(FakeUniverse())
    
    # Mock interact_with_player
    m.interact_with_player = MagicMock(return_value="interaction_result")
    
    # talk, pet, play
    assert m.talk(player, prompt="hi") == "interaction_result"
    m.interact_with_player.assert_called_with(player, prompt="hi", structured=False)
    
    assert m.pet(player) == "interaction_result"
    m.interact_with_player.assert_called_with(player, prompt="pet", structured=False)
    
    assert m.play(player) == "interaction_result"
    m.interact_with_player.assert_called_with(player, prompt="play", structured=False)
    
    # play with item
    assert m.play(player, item="ball") == "interaction_result"
    m.interact_with_player.assert_called_with(player, prompt="play with ball", structured=False)

def test_mynx_talk_exception(capsys):
    m = Mynx()
    player = FakePlayer(FakeUniverse())
    # Force interact_with_player to raise exception
    m.interact_with_player = MagicMock(side_effect=Exception("interaction failed"))
    
    res = m.talk(player)
    assert res is None
    out = capsys.readouterr().out
    assert "makes a confused chitter" in out

def test_gorran_name_property():
    g = Gorran()
    u = FakeUniverse()
    r = FakeRoom(u)
    g.current_room = r
    
    # defaults
    assert g.name == "Rock-Man"
    
    # story conditions
    u.story["gorran_first"] = "1"
    assert g.name == "Gorran"
    
    u.story["gorran_first"] = "0"
    u.story["gorran_language_stage"] = "1"
    assert g.name == "Gorran"
    
    # Name setter
    g.name = "CustomGorran"
    u.story.clear()
    assert g.name == "CustomGorran"
    
    # player_ref fallback path
    g.current_room = None
    g.player_ref = FakePlayer(u)
    u.story["gorran_first"] = "1"
    assert g.name == "Gorran"

def test_gorran_wounded_flavor():
    g = Gorran()
    # verify it returns one of the strings
    flavor = g.wounded_flavor()
    assert isinstance(flavor, str)
    assert len(flavor) > 0

def test_gorran_talk(capsys):
    g = Gorran()
    u = FakeUniverse()
    r = FakeRoom(u)
    g.current_room = r
    player = FakePlayer(u)
    
    # Mock seek_class
    dummy_event = MagicMock()
    with patch('functions.seek_class', return_value=dummy_event):
        u.story["gorran_first"] = "0"
        g.talk(player)
        assert u.story["gorran_first"] == "1"
        assert len(r.events_here) == 1
        
    # Language stages
    stages = [0, 1, 2, 3]
    for stage in stages:
        u.story["gorran_language_stage"] = str(stage)
        capsys.readouterr() # clear buffers
        g.talk(player)
        out = capsys.readouterr().out
        assert len(out) > 0

def test_grondite_citizens(capsys):
    # Passerby
    p = GronditePasserby()
    assert p.name == "Grondite"
    p.talk(None)
    assert len(capsys.readouterr().out) > 0
    
    # Worker
    w = GronditeWorker()
    assert w.name == "Grondite Worker"
    w.talk(None)
    assert len(capsys.readouterr().out) > 0
    
    # Elder
    e = GronditeElder()
    assert e.name == "Grondite Elder"
    e.talk(None)
    assert len(capsys.readouterr().out) > 0

def test_grondite_conclave_elder(capsys):
    ce = GronditeConclaveElder()
    u = FakeUniverse()
    player = FakePlayer(u)
    
    # First time
    u.story[ce._INTRO_RUN_KEY] = "0"
    with patch('time.sleep'):
        ce.talk(player)
        assert u.story[ce._INTRO_RUN_KEY] == "1"
        assert u.story["conclave_elder_disc_acknowledged"] == "1"
        out = capsys.readouterr().out
        assert "Elder turns" in out
        
    # Repeat talk
    capsys.readouterr()
    ce.talk(player)
    out = capsys.readouterr().out
    assert len(out) > 0

def test_mara_basics(capsys):
    m = Mara()
    assert m.name == "Mara"
    assert len(m.wounded_flavor()) > 0
    
    m.talk(None)
    assert len(capsys.readouterr().out) > 0

def test_mara_optimal_range():
    m = Mara()
    
    # No proximity
    assert m._get_optimal_range_to_target() is None
    
    # Proximity but no player_ref
    m.combat_proximity = {"enemy": 5}
    assert m._get_optimal_range_to_target() is None
    
    # Proximity + player_ref + enemy in proximity
    u = FakeUniverse()
    player = FakePlayer(u)
    m.player_ref = player
    enemy = object()
    player.combat_list = [enemy]
    
    # 1. Near: <= 3 -> dagger
    m.combat_proximity = {enemy: 2}
    assert m._get_optimal_range_to_target() == "dagger"
    
    # 2. Far: >= 8 -> bow
    m.combat_proximity = {enemy: 10}
    assert m._get_optimal_range_to_target() == "bow"
    
    # 3. Transition: 4-7
    m.combat_proximity = {enemy: 5}
    m.hp = 95
    m.maxhp = 95
    m.fatigue = 50
    m.maxfatigue = 50
    # healthy & energetic -> dagger
    assert m._get_optimal_range_to_target() == "dagger"
    
    # hurt -> bow
    m.hp = 30
    assert m._get_optimal_range_to_target() == "bow"
    
    # fatigued -> bow
    m.hp = 95
    m.fatigue = 10
    assert m._get_optimal_range_to_target() == "bow"

def test_mara_select_move():
    m = Mara()
    u = FakeUniverse()
    player = FakePlayer(u)
    m.player_ref = player
    
    # Mock moves
    m.known_moves = [moves.NpcIdle(m)]
    
    # No optimal range, simple selection
    m.select_move()
    assert m.current_move is not None
    
    # With optimal range "bow"
    m.combat_proximity = {"dummy_enemy": 10}
    m.select_move()
    assert m.current_move is not None

    # Cover line 777-778: weighted_moves is empty
    m.current_move = None
    m.refresh_moves = MagicMock(return_value=[])
    m.select_move()
    assert m.current_move is None

def test_devet_and_liss(capsys):
    d = Devet()
    assert d.name == "Devet"
    d.talk(None)
    assert len(capsys.readouterr().out) > 0
    
    l = Liss()
    assert l.name == "Liss"
    l.talk(None)
    assert len(capsys.readouterr().out) > 0
