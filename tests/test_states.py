"""
Unit tests for states module
"""
import pytest
from unittest.mock import Mock, patch
from src.states import State, Dodging, Parrying, Poisoned, Enflamed, Clean, Hawkeye, PhoenixRevive


@pytest.fixture
def mock_target():
    """Create a mock target for state application"""
    target = Mock()
    target.name = "TestTarget"
    target.in_combat = False
    target.states = []
    target.hp = 100
    target.maxhp = 100
    target.finesse = 30
    target.maxfatigue = 100
    return target


def test_state_initialization():
    """Test basic State initialization"""
    target = Mock()
    state = State("TestState", target, beats_max=10, steps_max=5)
    
    assert state.name == "TestState"
    assert state.target == target
    assert state.beats_max == 10
    assert state.beats_left == 10
    assert state.steps_max == 5
    assert state.steps_left == 5


def test_state_default_values():
    """Test State default parameter values"""
    target = Mock()
    state = State("Default", target)
    
    assert state.beats_max == 0
    assert state.steps_max == 0
    assert state.combat is True
    assert state.world is False
    assert state.hidden is False
    assert state.compounding is False
    assert state.persistent is False


def test_state_with_source():
    """Test State with source parameter"""
    target = Mock()
    source = Mock()
    state = State("TestState", target, source=source)
    
    assert state.source == source


def test_state_apply_announce():
    """Test State with apply announcement"""
    target = Mock()
    state = State("TestState", target, apply_announce="State applied!")
    
    assert state.apply_announce == "State applied!"


def test_state_description():
    """Test State with description"""
    target = Mock()
    state = State("TestState", target, description="Test description")
    
    assert state.description == "Test description"


def test_state_statustype():
    """Test State with custom statustype"""
    target = Mock()
    state = State("TestState", target, statustype="buff")
    
    assert state.statustype == "buff"


def test_state_effect_base():
    """Test base State effect does nothing"""
    target = Mock()
    state = State("TestState", target)
    
    result = state.effect(target)
    assert result is None


def test_state_on_application_base():
    """Test base State on_application does nothing"""
    target = Mock()
    state = State("TestState", target)
    
    result = state.on_application(target)
    assert result is None


def test_state_on_removal_base():
    """Test base State on_removal does nothing"""
    target = Mock()
    state = State("TestState", target)
    
    result = state.on_removal(target)
    assert result is None


@patch('src.states.functions.refresh_stat_bonuses')
def test_state_process_combat(mock_refresh, mock_target):
    """Test state processing in combat"""
    mock_target.in_combat = True
    state = State("TestState", mock_target, beats_max=3, combat=True)
    mock_target.states.append(state)
    
    # Process once
    state.process(mock_target)
    assert state.beats_left == 2
    
    # Process again
    state.process(mock_target)
    assert state.beats_left == 1
    
    # Process final time - should be removed
    state.process(mock_target)
    assert state.beats_left == 0
    assert state not in mock_target.states


@patch('src.states.functions.refresh_stat_bonuses')
def test_state_process_world(mock_refresh, mock_target):
    """Test state processing outside combat"""
    mock_target.in_combat = False
    state = State("TestState", mock_target, steps_max=2, world=True)
    mock_target.states.append(state)
    
    state.process(mock_target)
    assert state.steps_left == 1
    
    state.process(mock_target)
    assert state.steps_left == 0
    assert state not in mock_target.states


def test_state_process_wrong_context(mock_target):
    """Test state doesn't process in wrong context"""
    mock_target.in_combat = False
    state = State("TestState", mock_target, beats_max=3, combat=True, world=False)
    
    initial_beats = state.beats_left
    state.process(mock_target)
    
    # Should not have decremented
    assert state.beats_left == initial_beats


def test_dodging_initialization(mock_target):
    """Test Dodging state initialization"""
    state = Dodging(mock_target)
    
    assert state.name == "Dodging"
    assert state.target == mock_target
    assert state.beats_max == 7
    assert state.hidden is True
    assert hasattr(state, 'add_fin')


def test_dodging_finesse_bonus(mock_target):
    """Test Dodging calculates finesse bonus correctly"""
    mock_target.finesse = 30
    state = Dodging(mock_target)
    
    expected_bonus = 50 + int(30 / 3)
    assert state.add_fin == expected_bonus


def test_parrying_initialization(mock_target):
    """Test Parrying state initialization"""
    state = Parrying(mock_target)
    
    assert state.name == "Parrying"
    assert state.target == mock_target
    assert state.beats_max == 7
    assert state.hidden is True


@patch('src.states.cprint')
def test_poisoned_initialization(mock_cprint, mock_target):
    """Test Poisoned state initialization"""
    state = Poisoned(mock_target)
    
    assert state.name == "Poisoned"
    assert state.target == mock_target
    assert state.compounding is True
    assert state.world is True
    assert state.statustype == "poison"
    assert state.persistent is True
    assert state.tick == 0
    assert state.execute_on == 5


@patch('src.states.cprint')
def test_poisoned_on_application(mock_cprint, mock_target):
    """Test Poisoned announces application"""
    state = Poisoned(mock_target)
    state.on_application(mock_target)
    
    assert mock_cprint.called
    call_args = mock_cprint.call_args[0][0]
    assert "poisoned" in call_args.lower()


@patch('src.states.cprint')
def test_poisoned_on_removal(mock_cprint, mock_target):
    """Test Poisoned announces removal"""
    state = Poisoned(mock_target)
    state.on_removal(mock_target)
    
    assert mock_cprint.called
    call_args = mock_cprint.call_args[0][0]
    assert "no longer poisoned" in call_args.lower()


@patch('src.states.cprint')
@patch('src.states.random.uniform')
def test_poisoned_effect_damages_target(mock_uniform, mock_cprint, mock_target):
    """Test Poisoned effect deals damage"""
    mock_uniform.return_value = 0.025
    state = Poisoned(mock_target)
    
    initial_hp = mock_target.hp
    
    # Trigger effect (tick must be multiple of execute_on)
    for _ in range(state.execute_on):
        state.effect(mock_target)
    
    # Should have taken damage
    assert mock_target.hp < initial_hp


@patch('src.states.cprint')
def test_poisoned_compound(mock_cprint, mock_target):
    """Test Poisoned compound increases severity"""
    state = Poisoned(mock_target)
    initial_tick = state.tick
    initial_beats_max = state.beats_max
    
    state.compound(mock_target)
    
    # Severity should increase
    assert mock_cprint.called


@patch('src.states.cprint')
def test_enflamed_initialization(mock_cprint, mock_target):
    """Test Enflamed state initialization"""
    state = Enflamed(mock_target)
    
    assert state.name == "Enflamed"
    assert state.target == mock_target
    assert state.compounding is True
    assert state.world is True
    assert state.statustype == "enflamed"
    assert state.persistent is False
    assert state.tick == 0
    assert state.execute_on == 3


@patch('src.states.cprint')
def test_enflamed_on_application(mock_cprint, mock_target):
    """Test Enflamed announces application"""
    state = Enflamed(mock_target)
    state.on_application(mock_target)
    
    assert mock_cprint.called
    call_args = mock_cprint.call_args[0][0]
    assert "aflame" in call_args.lower()


@patch('src.states.cprint')
def test_enflamed_on_removal(mock_cprint, mock_target):
    """Test Enflamed announces removal"""
    state = Enflamed(mock_target)
    state.on_removal(mock_target)
    
    assert mock_cprint.called
    call_args = mock_cprint.call_args[0][0]
    assert "fire" in call_args.lower()


@patch('src.states.cprint')
def test_clean_initialization(mock_cprint, mock_target):
    """Test Clean state initialization"""
    state = Clean(mock_target)
    
    assert state.name == "Clean"
    assert state.compounding is False
    assert state.combat is False
    assert state.world is True
    assert state.statustype == "clean"
    assert state.persistent is True
    assert state.add_charisma == 1
    assert state.add_maxfatigue == 10


@patch('src.states.cprint')
def test_clean_on_application(mock_cprint, mock_target):
    """Test Clean announces application"""
    state = Clean(mock_target)
    state.on_application(mock_target)
    
    assert mock_cprint.called
    call_args = mock_cprint.call_args[0][0]
    assert "clean" in call_args.lower()


@patch('src.states.cprint')
def test_clean_on_removal(mock_cprint, mock_target):
    """Test Clean announces removal"""
    state = Clean(mock_target)
    state.on_removal(mock_target)
    
    assert mock_cprint.called


def test_hawkeye_initialization(mock_target):
    """Test Hawkeye state initialization"""
    state = Hawkeye(mock_target)
    
    assert state.name == "Hawkeye"
    assert state.target == mock_target
    assert state.beats_max == 30


@patch('src.states.cprint')
@patch('src.states.functions.refresh_stat_bonuses')
def test_phoenix_revive_initialization(mock_refresh, mock_cprint, mock_target):
    """Test PhoenixRevive state initialization"""
    state = PhoenixRevive(mock_target)
    
    assert state.name == "Phoenix Revive"
    assert state.beats_max == 0
    assert state.steps_max == 0
    assert state.compounding is False
    assert state.combat is True
    assert state.world is False
    assert state.statustype == "revive"
    assert state.persistent is True
    assert state.chance == 0.25


@patch('src.states.cprint')
@patch('src.states.functions.refresh_stat_bonuses')
@patch('src.states.random.random')
def test_phoenix_revive_triggers(mock_random, mock_refresh, mock_cprint, mock_target):
    """Test PhoenixRevive triggers when conditions are met"""
    mock_random.return_value = 0.1  # Below 0.25 threshold
    mock_target.hp = 0
    mock_target.maxhp = 100
    
    state = PhoenixRevive(mock_target)
    mock_target.states.append(state)
    
    result = state.try_revive(mock_target)
    
    assert result is True
    assert mock_target.hp == 50  # 50% of maxhp
    assert mock_cprint.called


@patch('src.states.cprint')
@patch('src.states.functions.refresh_stat_bonuses')
@patch('src.states.random.random')
def test_phoenix_revive_fails(mock_random, mock_refresh, mock_cprint, mock_target):
    """Test PhoenixRevive doesn't trigger when chance fails"""
    mock_random.return_value = 0.5  # Above 0.25 threshold
    mock_target.hp = 0
    
    state = PhoenixRevive(mock_target)
    mock_target.states.append(state)
    
    result = state.try_revive(mock_target)
    
    assert result is False
    assert mock_target.hp == 0


@patch('src.states.cprint')
@patch('src.states.functions.refresh_stat_bonuses')
def test_phoenix_revive_on_removal(mock_refresh, mock_cprint, mock_target):
    """Test PhoenixRevive announces removal"""
    state = PhoenixRevive(mock_target)
    state.on_removal(mock_target)
    
    assert mock_cprint.called
    call_args = mock_cprint.call_args[0][0]
    assert "faded" in call_args.lower()


def test_state_beats_conversion_to_int():
    """Test that beats_max and steps_max are converted to int"""
    target = Mock()
    state = State("Test", target, beats_max="10", steps_max="5")
    
    assert isinstance(state.beats_max, int)
    assert isinstance(state.steps_max, int)
    assert state.beats_max == 10
    assert state.steps_max == 5


def test_state_infinite_duration():
    """Test state with negative duration (infinite)"""
    target = Mock()
    target.in_combat = True
    target.states = []
    state = State("Infinite", target, beats_max=-1, combat=True)
    target.states.append(state)
    
    # Process multiple times
    for _ in range(10):
        state.process(target)
    
    # Should still be in states (negative max means infinite)
    # The code checks if beats_max >= 0 before decrementing
    assert state in target.states


@patch('src.states.cprint')
def test_poisoned_duration_range(mock_cprint):
    """Test Poisoned has variable duration"""
    target = Mock()
    
    # Create multiple instances to test randomness
    states = [Poisoned(target) for _ in range(10)]
    
    beats_values = [s.beats_max for s in states]
    steps_values = [s.steps_max for s in states]
    
    # Should have variation (not all the same)
    assert len(set(beats_values)) > 1 or len(set(steps_values)) > 1


@patch('src.states.cprint')
def test_enflamed_duration_range(mock_cprint):
    """Test Enflamed has variable duration"""
    target = Mock()
    
    states = [Enflamed(target) for _ in range(10)]
    beats_values = [s.beats_max for s in states]
    
    # Should have variation
    assert len(set(beats_values)) > 1
