"""
Tests to improve coverage in src/states.py.
Targets the remaining 43 uncovered lines: compound() and on_removal() methods
for Enflamed, Slimed, Resonant, Petrified, Hollowed, and Fervent states.
"""
import os
import sys
import pytest
from unittest.mock import MagicMock, patch


from src.narration import capture_narration
import src.states as states
from src.states import (
    Enflamed, Slimed, Resonant, Petrified, Hollowed, Fervent, PhoenixRevive, Death
)


# ---------------------------------------------------------------------------
# Minimal fake target for all state tests
# ---------------------------------------------------------------------------
class FakeTarget:
    """Lightweight stand-in for a Player/NPC with all attributes states access."""
    def __init__(self):
        self.name = "Jean"
        self.hp = 100
        self.maxhp = 100
        self.fatigue = 100
        self.maxfatigue = 100
        self.in_combat = True
        self.finesse = 50
        self.protection = 40
        self.strength = 60
        self.speed = 30
        self.faith = 5
        self.charisma = 5
        self.endurance = 5
        self.states = []


# Patch functions.refresh_stat_bonuses globally for the whole module
@pytest.fixture(autouse=True)
def patch_refresh(monkeypatch):
    monkeypatch.setattr("src.functions.refresh_stat_bonuses", MagicMock())


# ---------------------------------------------------------------------------
# Enflamed.compound() — issue #343: stacks (capped) + duration refresh,
# replacing the old escalating tick/duration-multiplier design.
# ---------------------------------------------------------------------------
def test_enflamed_compound_adds_stack_and_refreshes_duration():
    target = FakeTarget()
    state = Enflamed(target)
    state.beats_left = 5  # simulate partway through the burn

    with patch('src.states.cprint'):
        state.compound(target)

    assert state.stacks == 2
    assert state.beats_left == state.beats_max


def test_enflamed_compound_caps_at_max_stacks():
    """Reapplying beyond ENFLAMED_MAX_STACKS keeps stacks capped, not unbounded."""
    target = FakeTarget()
    state = Enflamed(target)

    with patch('src.states.cprint'):
        for _ in range(states.ENFLAMED_MAX_STACKS + 2):
            state.compound(target)

    assert state.stacks == states.ENFLAMED_MAX_STACKS



# ---------------------------------------------------------------------------
# Slimed.on_removal() — lines 337-339
# ---------------------------------------------------------------------------
def test_slimed_on_removal():
    """on_removal only announces; the protection penalty is declarative
    (add_protection summed by refresh_stat_bonuses) and is never mutated
    directly by on_removal."""
    target = FakeTarget()
    state = Slimed(target)
    original_protection = target.protection

    with patch('src.states.cprint') as mock_cprint:
        state.on_removal(target)

    assert target.protection == original_protection
    assert mock_cprint.called


# ---------------------------------------------------------------------------
# Slimed.compound() — lines 351-358
# ---------------------------------------------------------------------------
def test_slimed_compound():
    target = FakeTarget()
    state = Slimed(target)
    state.beats_max = 50
    state.beats_left = 50
    state.steps_max = 20
    state.steps_left = 20
    original_add_fin = state.add_fin
    original_add_protection = state.add_protection

    with patch('src.states.cprint'):
        state.compound(target)

    # add_fin should decrease
    assert state.add_fin < original_add_fin
    # add_protection should also deepen (issue #259 follow-up: compound() must
    # worsen every declarative penalty the state carries, not just add_fin)
    assert state.add_protection < original_add_protection
    # beats_max *= 1.1
    assert state.beats_max == int(50 * 1.1)


# ---------------------------------------------------------------------------
# Resonant.on_removal() — line 392-396
# ---------------------------------------------------------------------------
def test_resonant_on_removal():
    """The wail's departure is announced by name.

    ``mock_cprint.called`` -- the old assertion -- was satisfied by any string
    at all, including the *application* line (the two are adjacent methods with
    near-identical bodies, which is exactly where a copy-paste slips through).
    """
    target = FakeTarget()
    state = Resonant(target)

    with capture_narration() as messages:
        state.on_removal(target)

    assert [(m["text"], m["color"]) for m in messages] == [
        (
            f"The wail fades from {target.name}. "
            "The silence, when it comes, is sudden.",
            "white",
        )
    ]


# ---------------------------------------------------------------------------
# Petrified.effect() drain > 0 path — lines 457-465
# ---------------------------------------------------------------------------
def test_petrified_effect_fatigue_drain():
    target = FakeTarget()
    target.maxfatigue = 100
    target.fatigue = 100
    state = Petrified(target)
    # Force tick to trigger on the execute_on cycle
    state.tick = state.execute_on - 1  # next call makes tick % execute_on == 0

    with patch('src.states.cprint'):
        state.effect(target)

    # fatigue should have been drained (5% of 100 = 5)
    assert target.fatigue == 95


def test_petrified_effect_zero_drain():
    """If maxfatigue is 0, drain=0 → cprint not called for fatigue message."""
    target = FakeTarget()
    target.maxfatigue = 0
    target.fatigue = 0
    state = Petrified(target)
    state.tick = state.execute_on - 1

    with patch('src.states.cprint') as mock_cprint:
        state.effect(target)

    # drain = int(0 * 0.05) = 0 → the inner "if drain > 0: cprint" is skipped
    # cprint should NOT be called for the drain message
    # (though the drain itself is still calculated)
    assert target.fatigue == 0


# ---------------------------------------------------------------------------
# Petrified.compound() — lines 467-478
# ---------------------------------------------------------------------------
def test_petrified_compound():
    target = FakeTarget()
    state = Petrified(target)
    state.beats_max = 30
    state.beats_left = 30
    state.steps_max = 20
    state.steps_left = 20
    original_add_fin = state.add_fin
    original_add_speed = state.add_speed
    original_add_protection = state.add_protection

    with patch('src.states.cprint'):
        state.compound(target)

    # Both stat penalties deepen
    assert state.add_fin < original_add_fin
    assert state.add_speed < original_add_speed
    # add_protection is a buff for Petrified, so it should grow more positive
    # on reapplication (issue #259 follow-up: compound() must worsen/deepen
    # every declarative bonus, not just add_fin/add_speed)
    assert state.add_protection > original_add_protection
    assert state.beats_max == int(30 * 1.1)


# ---------------------------------------------------------------------------
# Hollowed.on_removal() — lines 516-518
# ---------------------------------------------------------------------------
def test_hollowed_on_removal():
    target = FakeTarget()
    state = Hollowed(target)
    with patch('src.states.cprint') as mock_cprint:
        state.on_removal(target)
    assert mock_cprint.call_count == 2  # two cprint calls


# ---------------------------------------------------------------------------
# Fervent.on_removal() — lines 562-568
# ---------------------------------------------------------------------------
def test_fervent_on_removal():
    target = FakeTarget()
    state = Fervent(target)
    with patch('src.states.cprint') as mock_cprint:
        state.on_removal(target)
    assert mock_cprint.called
    assert "fire" in mock_cprint.call_args[0][0].lower() or \
           "cost" in mock_cprint.call_args[0][0].lower() or \
           "gutters" in mock_cprint.call_args[0][0].lower()


# ---------------------------------------------------------------------------
# Fervent.compound() — lines 584-589
# ---------------------------------------------------------------------------
def test_fervent_compound():
    target = FakeTarget()
    state = Fervent(target)
    state.beats_max = 40
    state.beats_left = 40
    original_add_str = state.add_str
    original_add_endurance = state.add_endurance

    with patch('src.states.cprint'):
        state.compound(target)

    # add_str increases
    assert state.add_str > original_add_str
    # add_endurance decreases by 2
    assert state.add_endurance == original_add_endurance - 2
    # beats_left capped at beats_max
    assert state.beats_left <= state.beats_max


# ---------------------------------------------------------------------------
# Death — issue #350, the WailWraith's Death Knell execute
# ---------------------------------------------------------------------------
def test_death_on_application_zeroes_hp():
    """Death is a one-shot kill, not a DoT: on_application sets hp straight
    to 0 rather than ticking damage over beats."""
    target = FakeTarget()
    target.hp = 87
    state = Death(target)
    assert state.statustype == "death"

    with patch('src.states.cprint'):
        state.on_application(target)

    assert target.hp == 0


def test_death_has_no_ongoing_effect():
    """effect() is a no-op (inherited from State) — Death does all its work
    in on_application, so a stray process() call after application (e.g. if
    combat continues for a beat before the defeat check runs) must not do
    anything further."""
    target = FakeTarget()
    target.hp = 0
    state = Death(target)
    state.effect(target)  # should not raise or change hp
    assert target.hp == 0
