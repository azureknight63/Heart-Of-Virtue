import copy
import math
import os, sys
# Ensure project root and src directory are on sys.path for isolated test invocation
_CURRENT = os.path.dirname(__file__)
_PROJECT_ROOT = os.path.abspath(os.path.join(_CURRENT, '..'))
_SRC_DIR = os.path.join(_PROJECT_ROOT, 'src')
for _p in (_PROJECT_ROOT, _SRC_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)
try:
    import src.functions as functions
except ModuleNotFoundError:  # fallback if src not discoverable in isolated test invocation
    import functions  # type: ignore

class MockItem:
    def __init__(self, **attrs):
        for k, v in attrs.items():
            setattr(self, k, v)
        # ensure isequipped attribute present for equipped items
        if 'isequipped' not in attrs:
            self.isequipped = True

class MockState:
    def __init__(self, **attrs):
        for k, v in attrs.items():
            setattr(self, k, v)

class MockTarget:
    def __init__(self, name="Jean"):
        # base stats
        self.name = name
        self.strength_base = 10
        self.finesse_base = 5
        self.maxhp_base = 100
        self.maxfatigue_base = 100
        self.speed_base = 8
        self.endurance_base = 10
        self.charisma_base = 3
        self.intelligence_base = 7
        self.faith_base = 2
        self.weight_tolerance_base = 40
        self.weight_current = 0  # default below 50% capacity
        # mutable stats (will be overwritten by reset_stats)
        self.strength = None
        self.finesse = None
        self.maxhp = None
        self.maxfatigue = None
        self.speed = None
        self.endurance = None
        self.charisma = None
        self.intelligence = None
        self.faith = None
        self.weight_tolerance = None
        # resistances
        self.resistance_base = {"fire": 1.0, "ice": 1.0, "pure": 1.0}
        self.status_resistance_base = {"generic": 1.0, "poison": 1.0}
        self.resistance = {}
        self.status_resistance = {}
        # containers
        self.inventory = []
        self.states = []

    def refresh_weight(self):  # simple deterministic stub
        # weight_current remains as set in tests; could compute sum(item.weight) if needed
        return


def snapshot(target):
    return {
        'strength': target.strength,
        'finesse': target.finesse,
        'maxhp': target.maxhp,
        'maxfatigue': target.maxfatigue,
        'speed': target.speed,
        'endurance': target.endurance,
        'charisma': target.charisma,
        'intelligence': target.intelligence,
        'faith': target.faith,
        'weight_tolerance': target.weight_tolerance,
        'resistance': copy.deepcopy(target.resistance),
        'status_resistance': copy.deepcopy(target.status_resistance),
    }


def test_refresh_stat_bonuses_baseline_idempotent():
    t = MockTarget()
    functions.refresh_stat_bonuses(t)
    first = snapshot(t)
    # call again with no changes
    functions.refresh_stat_bonuses(t)
    second = snapshot(t)
    assert first == second
    # base stats match *_base values
    assert t.strength == t.strength_base
    assert t.maxhp == t.maxhp_base
    # Jean weight_tolerance recomputed: base + (STR+END)/2
    expected_wt = t.weight_tolerance_base + round((t.strength + t.endurance)/2, 2)
    assert math.isclose(t.weight_tolerance, expected_wt)
    # Under 50% capacity => +25% maxfatigue
    base_plus = t.maxfatigue_base + (t.maxfatigue_base * 0.25)
    assert math.isclose(t.maxfatigue, base_plus, rel_tol=1e-6)


def test_refresh_stat_bonuses_equipped_item_and_state_bonuses():
    t = MockTarget()
    sword = MockItem(isequipped=True, add_str=5, add_endurance=5, add_resistance={"fire": 0.2}, add_status_resistance={"generic": -0.5})
    haste_state = MockState(add_speed=3)
    t.inventory.append(sword)
    t.states.append(haste_state)
    functions.refresh_stat_bonuses(t)
    # Strength & endurance increased
    assert t.strength == t.strength_base + 5
    assert t.endurance == t.endurance_base + 5
    # Speed increased by state
    assert t.speed == t.speed_base + 3
    # Resistances updated only for provided keys
    assert t.resistance['fire'] == 1.0 + 0.2
    # Absent keys unchanged
    assert t.resistance['ice'] == 1.0
    # Status resistance cannot go below 0 after clamp; generic reduced by 0.5 to 0.5
    assert t.status_resistance['generic'] == 0.5


def test_refresh_stat_bonuses_negative_status_clamped():
    t = MockTarget()
    bad_item = MockItem(isequipped=True, add_status_resistance={"poison": -2.0})  # drives below zero
    t.inventory.append(bad_item)
    functions.refresh_stat_bonuses(t)
    assert t.status_resistance['poison'] == 0  # clamped


def test_refresh_stat_bonuses_weight_bonus_with_added_fatigue():
    t = MockTarget()
    stam_item = MockItem(isequipped=True, add_maxfatigue=20)
    t.inventory.append(stam_item)
    functions.refresh_stat_bonuses(t)
    # base + item bonus then +25%
    pre_bonus = t.maxfatigue_base + 20
    expected = pre_bonus + (pre_bonus * 0.25)
    assert math.isclose(t.maxfatigue, expected, rel_tol=1e-6)


def test_refresh_stat_bonuses_overweight_penalty():
    t = MockTarget()
    # Add strength & endurance bonuses to alter weight_tolerance formula too
    heavy_item = MockItem(isequipped=True, add_str=10, add_endurance=10)
    t.inventory.append(heavy_item)
    # Make Jean overweight after recalculation: We'll set weight_current after computing expected tolerance
    # Run once to compute new tolerance & then adjust weight_current for second run
    functions.refresh_stat_bonuses(t)
    wt = t.weight_tolerance  # after bonuses
    # Set overweight by 10 lbs
    t.weight_current = wt + 10
    # Also reset maxfatigue to base to isolate penalty effect (simulate base condition before call)
    t.maxfatigue = t.maxfatigue_base
    # Re-run (function resets stats first anyway)
    functions.refresh_stat_bonuses(t)
    # Calculate expected: base maxfatigue (100) - overweight(10)*10 = 0 floor or 0? Wait base 100 - 100 = 0
    # Because bonuses to maxfatigue are absent aside from overweight penalty (no add_maxfatigue)
    assert t.maxfatigue == 0


def test_refresh_stat_bonuses_non_jean_no_weight_logic():
    t = MockTarget(name="Goblin")
    # give an equipped bonus
    club = MockItem(isequipped=True, add_str=3)
    t.inventory.append(club)
    functions.refresh_stat_bonuses(t)
    assert t.strength == t.strength_base + 3
    # weight_tolerance should just equal base (non-Jean) OR be absent if not set
    assert t.weight_tolerance == t.weight_tolerance_base
    # maxfatigue should not get +25% bonus (no Jean logic)
    assert t.maxfatigue == t.maxfatigue_base


def test_refresh_stat_bonuses_ignores_unknown_resistance_keys():
    t = MockTarget()
    itm = MockItem(isequipped=True, add_resistance={"fire": 0.1, "plasma": 9.9})
    t.inventory.append(itm)
    functions.refresh_stat_bonuses(t)
    # fire updated, plasma ignored (not in base dict)
    assert t.resistance['fire'] == 1.1
    assert 'plasma' not in t.resistance
