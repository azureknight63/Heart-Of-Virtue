"""
Unit tests for states module
"""
import pytest
from unittest.mock import Mock, patch
from src.narration import capture_narration
from src.states import State, Dodging, Parrying, Poisoned, Enflamed, Clean, Hawkeye, PhoenixRevive, Slimed
from src.states import (
    DODGE_EVASION_BASE,
    DODGE_EVASION_FINESSE_DIVISOR,
    DODGE_EVASION_MIN,
)


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

    expected_bonus = DODGE_EVASION_BASE - int(30 / DODGE_EVASION_FINESSE_DIVISOR)
    assert state.add_fin == expected_bonus


def test_dodging_finesse_bonus_diminishes_with_finesse(mock_target):
    """The dodge bonus shrinks as the dodger's own finesse rises.

    Asserted as a property rather than against a literal so a balance retune
    cannot quietly restore the compounding shape this replaced: a bonus that
    *grew* with finesse let base evasion enter the to-hit expression twice and
    made high-finesse dodgers effectively unhittable.
    """
    mock_target.finesse = 4
    low = Dodging(mock_target).add_fin
    mock_target.finesse = 40
    high = Dodging(mock_target).add_fin

    assert high < low
    assert high >= DODGE_EVASION_MIN


def test_dodging_finesse_bonus_never_below_floor(mock_target):
    """An absurdly evasive combatant still gains the floor, never 0 or less."""
    mock_target.finesse = 10000
    assert Dodging(mock_target).add_fin == DODGE_EVASION_MIN


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


def test_poisoned_compound(mock_target):
    """Reapplying poison stretches duration by 10% and refills a quarter of it.

    The old body captured ``initial_tick``/``initial_beats_max``, never used
    them, and asserted only that ``cprint`` had been called -- so a compound()
    that announced worsening poison while changing nothing would have passed.
    """
    state = Poisoned(mock_target)
    # Pin the randomized duration so the arithmetic below is exact.
    state.beats_max, state.beats_left = 100, 40
    state.steps_max, state.steps_left = 60, 20
    state.tick = 8

    with capture_narration() as messages:
        state.compound(mock_target)

    assert [(m["text"], m["color"]) for m in messages] == [
        ("TestTarget's poisoning has gotten worse!", "magenta")
    ]
    assert state.tick == 10               # int(8 * 1.25)
    assert state.beats_max == 110         # int(100 * 1.1)
    assert state.steps_max == 66          # int(60 * 1.1)
    assert state.beats_left == 40 + 27    # += int(beats_max / 4)
    assert state.steps_left == 20 + 16    # += int(steps_max / 4)


def test_poisoned_compound_clamps_remaining_to_the_new_maximum(mock_target):
    state = Poisoned(mock_target)
    state.beats_max = state.beats_left = 100
    state.steps_max = state.steps_left = 60

    with capture_narration():
        state.compound(mock_target)

    assert state.beats_left == state.beats_max == 110
    assert state.steps_left == state.steps_max == 66


@patch('src.states.cprint')
def test_enflamed_initialization(mock_cprint, mock_target):
    """Test Enflamed state initialization"""
    state = Enflamed(mock_target)

    assert state.name == "Enflamed"
    assert state.target == mock_target
    assert state.compounding is True
    assert state.world is False  # combat-only; world=True caused fire to fire once then self-remove outside combat
    assert state.statustype == "enflamed"
    assert state.persistent is False
    assert state.stacks == 1
    assert state.beats_max == 25


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
@patch('src.states.functions.refresh_stat_bonuses')
def test_clean_on_application(mock_refresh, mock_cprint, mock_target):
    """Test Clean announces application and refreshes stat bonuses"""
    state = Clean(mock_target)
    state.on_application(mock_target)

    assert mock_refresh.called
    assert mock_cprint.called
    call_args = mock_cprint.call_args[0][0]
    assert "clean" in call_args.lower()


@patch('src.states.functions.refresh_stat_bonuses')
def test_clean_on_removal(mock_refresh, mock_target):
    """Clean's removal refreshes the target's bonuses and says so.

    The old body asserted only that two mocks had been *called* -- not with
    what, and not that the removal line differed from the application line
    (they are near-identical strings, and a copy-paste swap would have been
    invisible).
    """
    state = Clean(mock_target)

    with capture_narration() as messages:
        state.on_removal(mock_target)

    mock_refresh.assert_called_once_with(mock_target)
    assert [(m["text"], m["color"]) for m in messages] == [
        ("TestTarget is no longer quite so clean!", "white")
    ]


def test_slimed_statustype_is_distinct():
    """Slimed must use its own 'slimed' statustype, not 'poison', so immunity
    granted against one doesn't silently grant immunity against the other."""
    target = Mock()
    target.finesse = 30
    target.protection = 20
    state = Slimed(target)

    assert state.statustype == "slimed"
    assert state.combat is True
    assert state.world is True


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

    # beats_max <= 0 means infinite: the counter must not tick down at all.
    # Membership alone (the old assertion) would still hold for a state that
    # counted down to -10 and was simply never removed.
    assert state in target.states
    assert state.beats_left == -1


def test_state_zero_beats_max_is_permanent():
    """beats_max=0 (the default) must persist indefinitely — regression for the >= 0 bug."""
    target = Mock()
    target.in_combat = True
    target.states = []
    state = State("Permanent", target, beats_max=0, combat=True)
    target.states.append(state)

    for _ in range(20):
        state.process(target)

    assert state in target.states
    assert state.beats_left == 0
    assert target.states == [state]


@patch('src.states.cprint')
def test_poisoned_duration_range(mock_cprint, seeded):
    """Poisoned rolls its duration inside the documented bounds.

    The old test built ten instances off an unseeded RNG and asserted only that
    *some* variation existed. That pinned neither bound -- a Poisoned rolling
    beats_max in the millions, or negative, passed -- and it was one unlucky
    draw away from being flaky in the other direction.
    """
    target = Mock()

    with seeded(20260821):
        states = [Poisoned(target) for _ in range(200)]

    beats_values = [s.beats_max for s in states]
    steps_values = [s.steps_max for s in states]

    # randint(50, 150) beats / randint(20, 80) steps -- inclusive bounds.
    assert min(beats_values) >= 50 and max(beats_values) <= 150
    assert min(steps_values) >= 20 and max(steps_values) <= 80
    # 200 draws over a 101-wide range: the spread is not in doubt.
    assert len(set(beats_values)) > 1
    assert len(set(steps_values)) > 1
    # beats_left/steps_left start at their maxima, per state.
    assert all(s.beats_left == s.beats_max for s in states)
    assert all(s.steps_left == s.steps_max for s in states)


@patch('src.states.cprint')
def test_enflamed_duration_is_fixed(mock_cprint):
    """Enflamed's duration is a fixed cap (issue #343), not randomized --
    variability now comes from the per-beat early-removal chance instead."""
    target = Mock()

    states = [Enflamed(target) for _ in range(10)]
    beats_values = [s.beats_max for s in states]

    assert all(v == 25 for v in beats_values)
