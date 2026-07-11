import builtins
import os
import random
import types
import inspect
import src.functions as functions
import importlib


class DummyPlayer:
    def __init__(self):
        self.flags = []
        self.known_moves = []
        self.inventory = []
        self.states = []
        self.preferences = {"arrow": "None"}
        self.current_room = None
        self.finesse = 10
        self.finesse_base = 10
        self.strength_base = 5
        self.endurance_base = 5
        self.maxhp_base = 10
        self.maxfatigue_base = 20
        self.speed_base = 3
        self.charisma_base = 1
        self.intelligence_base = 1
        self.faith_base = 1
        self.resistance_base = {"fire": 1.0}
        self.status_resistance_base = {"generic": 0.0}
        self.resistance = {}
        self.status_resistance = {}
        self.weight_tolerance_base = 10
        self.weight_tolerance = 10
        self.weight_current = 0
        self.name = "Jean"
        self.eq_weapon = types.SimpleNamespace(range=(1, 2))

    # Called by refresh_stat_bonuses for Jean
    def refresh_weight(self):
        pass


# ---------- execute_arbitrary_method / confirm ----------

def test_execute_arbitrary_method_zero_and_one_arg(monkeypatch):
    called = {}

    def zero():
        called['zero'] = True

    def one(p):
        called['one'] = p is player

    player = DummyPlayer()
    functions.execute_arbitrary_method(zero, player)
    functions.execute_arbitrary_method(one, player)
    assert called == {'zero': True, 'one': True}


# ---------- enumerate_for_interactions ----------

# ---------- screen_clear ----------

def test_screen_clear_is_noop(monkeypatch):
    # Terminal clearing was retired with terminal mode; screen_clear is now a
    # no-op that must not shell out to the OS.
    calls = []
    monkeypatch.setattr(os, 'system', lambda cmd: calls.append(cmd) or 0)
    assert functions.screen_clear() is None
    assert calls == []


# ---------- check_for_combat ----------

def test_check_for_combat_detection(monkeypatch):
    player = DummyPlayer()

    class Enemy:
        def __init__(self, name, awareness):
            self.name = name
            self.awareness = awareness
            self.aggro = True
            self.friend = False
            self.alert_message = ' spots Jean!'
            self.in_combat = False

    e1 = Enemy('Goblin', 999)  # guaranteed detection
    e2 = Enemy('Goblin Ally', 5)
    room = types.SimpleNamespace(npcs_here=[e1, e2])
    player.current_room = room
    # Finesse roll low
    monkeypatch.setattr(random, 'randint', lambda a, b: a)
    result = functions.check_for_combat(player)
    assert e1 in result and e2 in result and all(e.in_combat for e in (e1, e2))


# ---------- refresh_stat_bonuses / reset_stats ----------

def test_refresh_stat_bonuses_items_and_states():
    player = DummyPlayer()

    class BonusItem:
        def __init__(self):
            self.isequipped = True
            self.add_str = 2
            self.add_resistance = {"fire": 0.5}
            self.add_status_resistance = {"generic": 0.25}

    class BonusState:
        add_fin = 3

    player.inventory.append(BonusItem())
    player.states.append(BonusState())
    # Set weight_current to low value for +25% fatigue bonus
    player.weight_current = 0
    functions.refresh_stat_bonuses(player)
    # Strength base 5 +2 item
    assert player.strength == 7
    # Finesse base 10 +3 state
    assert player.finesse == 13
    assert player.resistance['fire'] == 1.5  # base 1.0 + 0.5
    assert player.status_resistance['generic'] == 0.25  # clamped >=0
    # Max fatigue increased by 25%
    assert player.maxfatigue > player.maxfatigue_base

    # Overweight penalty path
    player.weight_current = player.weight_tolerance + 2  # overweight by 2
    pre_penalty_base = player.maxfatigue_base
    functions.refresh_stat_bonuses(player)
    # After overweight penalty maxfatigue not negative
    assert player.maxfatigue >= 0
    assert player.maxfatigue <= pre_penalty_base + 10  # sanity bound


def test_refresh_stat_bonuses_applies_real_disoriented_state():
    """End-to-end check (no mocks): a real Disoriented state's declarative
    add_fin/add_protection bonuses actually reduce target.finesse/protection
    when the unmocked refresh_stat_bonuses sums them, closing the gap left
    when Disoriented stopped mutating finesse/protection directly (issue #259)."""
    from src.states import Disoriented

    player = DummyPlayer()
    player.protection = 20
    player.protection_base = 20  # lacks refresh_protection_rating; reset_stats
    # falls back to the protection_base path (mirrors a real NPC's fixed value)
    state = Disoriented(player)  # add_fin/add_protection computed from current stats
    player.states.append(state)

    functions.refresh_stat_bonuses(player)

    assert state.add_fin < 0
    assert player.finesse == player.finesse_base + state.add_fin
    assert state.add_protection < 0
    assert player.protection == player.protection_base + state.add_protection

    # Idempotency: repeated refreshes while the state remains active must not
    # keep stacking the penalty (reset_stats restores protection_base first).
    functions.refresh_stat_bonuses(player)
    assert player.protection == player.protection_base + state.add_protection

    # Removal: once the state is gone, refresh_stat_bonuses must restore
    # protection to its true base -- no double-restore, no residual penalty.
    player.states.remove(state)
    functions.refresh_stat_bonuses(player)
    assert player.protection == player.protection_base


def test_refresh_stat_bonuses_real_player_protection_survives_recompute():
    """Reproduces the exact GitHub issue #259 scenario end-to-end with a real
    Player: Disoriented's protection penalty must not be silently wiped by
    Player.refresh_protection_rating() recomputing protection from gear, and
    must not double-restore (inflate) protection when the state expires."""
    from src.player import Player
    from src.states import Disoriented

    player = Player()
    functions.refresh_stat_bonuses(player)
    baseline_protection = player.protection

    state = Disoriented(player)
    player.states.append(state)
    functions.refresh_stat_bonuses(player)

    assert state.add_protection < 0
    assert player.protection == baseline_protection + state.add_protection

    # Calling refresh_stat_bonuses again (e.g. from an equip/rest path) while
    # the debuff is still active must not re-stack or wipe the penalty.
    functions.refresh_stat_bonuses(player)
    assert player.protection == baseline_protection + state.add_protection

    # Removal restores the original value exactly -- no double-restore.
    player.states.remove(state)
    functions.refresh_stat_bonuses(player)
    assert player.protection == baseline_protection


def test_refresh_stat_bonuses_real_npc_petrified_protection_bonus():
    """Same regression as above but for a real NPC and the Petrified buff
    (positive add_protection). NPCs have no refresh_protection_rating, so this
    exercises the protection_base fallback branch in reset_stats()."""
    from src.npc import NPC
    from src.states import Petrified

    npc = NPC(name="RockRumbler", description="A lumbering creature", damage=8, aggro=70, exp_award=50, protection=30)
    functions.refresh_stat_bonuses(npc)
    baseline_protection = npc.protection

    state = Petrified(npc)
    npc.states.append(state)
    functions.refresh_stat_bonuses(npc)

    assert state.add_protection > 0
    assert npc.protection == baseline_protection + state.add_protection

    # Repeated refresh while active must not keep stacking the bonus.
    functions.refresh_stat_bonuses(npc)
    assert npc.protection == baseline_protection + state.add_protection

    # Removal restores the original value exactly -- no double-restore.
    npc.states.remove(state)
    functions.refresh_stat_bonuses(npc)
    assert npc.protection == baseline_protection


def test_refresh_stat_bonuses_protection_recompute_sees_buffed_strength():
    """Player.refresh_protection_rating() scales equipped armor's str_mod/fin_mod
    bonus by self.strength/self.finesse. That recompute must run *after*
    add_str/add_fin bonuses from states/items are summed -- otherwise armor
    bonuses silently ignore active strength/finesse buffs (the bug introduced
    by originally moving the protection-base reset into reset_stats() ahead of
    the bonus-summing loop)."""
    from src.player import Player

    player = Player()

    class StrScalingShield:
        isequipped = True
        protection = 5
        str_mod = 1.0

    player.inventory.append(StrScalingShield())
    functions.refresh_stat_bonuses(player)
    baseline_protection = player.protection

    total_str_mod = sum(
        getattr(item, "str_mod", 0) or 0
        for item in player.inventory
        if getattr(item, "isequipped", False)
    )

    class StrengthBuff:
        add_str = 20

    player.states.append(StrengthBuff())
    functions.refresh_stat_bonuses(player)

    assert player.strength == player.strength_base + 20
    expected_extra = 20 * total_str_mod
    assert player.protection == baseline_protection + expected_extra


# ---------- check_parry ----------

def test_check_parry():
    target = types.SimpleNamespace(states=[types.SimpleNamespace(name='Parrying')])
    assert functions.check_parry(target) is True
    target.states = []
    assert functions.check_parry(target) is False


# ---------- refresh_moves ----------

def test_refresh_moves():
    player = DummyPlayer()
    functions.refresh_moves(player)
    # Simply ensure known_moves is a list and any populated moves originate from src.moves
    assert isinstance(player.known_moves, list)
    for mv in player.known_moves:
        assert 'moves' in mv.__class__.__module__


# ---------- checkrange ----------

def test_checkrange_player_vs_npc():
    player = DummyPlayer()
    player.name = 'Jean'
    player.eq_weapon.range = (2, 4)
    assert functions.checkrange(player) == (2, 4)
    npc = types.SimpleNamespace(name='Orc', combat_range=(5, 7))
    assert functions.checkrange(npc) == (5, 7)


# ---------- add_preference ----------

def test_add_preference_arrow_toggle(capsys):
    player = DummyPlayer()
    functions.add_preference(player, 'arrow', 'Steel Arrow')
    assert player.preferences['arrow'] == 'Steel Arrow'
    functions.add_preference(player, 'arrow', 'Steel Arrow')  # toggle off
    assert player.preferences['arrow'] == 'None'


# ---------- escape_ansi / clean_string ----------

def test_escape_ansi_and_clean_string():
    colored = '\x1b[31mRed Text\x1b[0m'
    assert functions.escape_ansi(colored) == 'Red Text'
    noisy = '\x1b[31mHello\x1b[0m[99mWorld'
    assert 'World' in functions.clean_string(noisy)


# ---------- instantiate_event ----------

def test_instantiate_event_variants():
    class EventUnified:
        def __init__(self, player, tile, params=None, repeat=False, name=None):
            self.player = player; self.tile = tile; self.params = params; self.repeat = repeat; self.name = name
    class EventLegacy:
        def __init__(self, player, tile, params, repeat=False):
            self.params = params; self.repeat = repeat
    class EventTransitional:
        def __init__(self, player, tile, repeat, params):
            self.repeat = repeat; self.params = params

    player = DummyPlayer(); tile = object()
    e1 = functions.instantiate_event(EventUnified, player, tile, params={'a':1}, repeat=True, name='E')
    e2 = functions.instantiate_event(EventLegacy, player, tile, params={'b':2}, repeat=False)
    e3 = functions.instantiate_event(EventTransitional, player, tile, params={'c':3}, repeat=True)
    assert isinstance(e1, EventUnified) and isinstance(e2, EventLegacy) and isinstance(e3, EventTransitional)


# ---------- stack_inv_items already covered elsewhere but add edge case ----------

def test_stack_inv_items_non_stackables_graceful():
    target = types.SimpleNamespace(inventory=[object(), object()])
    # Should not raise
    functions.stack_inv_items(target)


def test_print_slow(capsys):
    # print_slow now emits the whole line via the narration sink (no terminal
    # typewriter / time.sleep); when no capture is active it echoes to stdout.
    functions.print_slow("Hello World", speed="fast")
    captured = capsys.readouterr().out
    assert "Hello World" in captured


def test_room_print_helpers(capsys):
    class Obj:
        def __init__(self, name, idle_message=" idle"):
            self.name = name
            self.idle_message = idle_message
            self.hidden = False
            self.announce = f"{name} here"
            self.description = name
    room = types.SimpleNamespace(
        npcs_here=[Obj("Goblin", " growls")],
        items_here=[Obj("Gem")],
        objects_here=[Obj("Altar", "Altar glows")]
    )
    functions.print_npcs_in_room(room)
    functions.print_items_in_room(room)
    functions.print_objects_in_room(room)
    out = capsys.readouterr().out
    assert "Goblin growls" in out and "Gem here" in out and "Altar glows" in out


def test_save_and_load_roundtrip(tmp_path):
    player = DummyPlayer()
    filename = 'src/test_temp_save_roundtrip'
    try:
        if os.path.exists(filename + '.sav'):
            os.remove(filename + '.sav')
    except Exception:
        pass
    functions.save(player, filename)
    loaded = functions.load(filename + '.sav')
    assert getattr(loaded, '__class__', object()).__name__ == 'DummyPlayer'
    try:
        os.remove(filename + '.sav')
    except Exception:
        pass


def test_list_module_names_and_seek_class_error():
    mods = functions.list_module_names('src')
    assert isinstance(mods, list)
    # seek_class with invalid package should raise ValueError
    with pytest.raises(ValueError):
        functions.seek_class('NonExistentClass', package='not_a_pkg')


def test_await_input_is_noop(monkeypatch):
    # The blocking "press Enter" pause was retired with terminal mode;
    # await_input must no longer call input().
    called = {'input': False}
    def fake_input(prompt=''):
        called['input'] = True
        return ''
    monkeypatch.setattr(builtins, 'input', fake_input)
    assert functions.await_input() is None
    assert called['input'] is False

# Append required imports for new tests
import pytest  # noqa: E402  (placed at end intentionally for minimal diff)
