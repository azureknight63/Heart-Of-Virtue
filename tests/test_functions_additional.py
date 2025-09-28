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


def test_confirm_yes_no(monkeypatch):
    player = DummyPlayer()

    class Thing:
        name = "Rock"
        def examine(self, p):
            p.flags.append('examined')

    t = Thing()
    # First call: yes
    seq = iter(['y', 'n'])
    monkeypatch.setattr(builtins, 'input', lambda _='': next(seq))
    result_yes = functions.confirm(t, 'examine', player, ['examine'])
    result_no = functions.confirm(t, 'examine', player, ['examine'])
    assert result_yes is True and result_no is False and 'examined' in player.flags


# ---------- enumerate_for_interactions ----------

def test_enumerate_for_interactions_single_and_multi(monkeypatch):
    player = DummyPlayer()

    class Obj:
        def __init__(self, name):
            self.name = name
            self.interactions = ['examine']
            self.called = False
        def examine(self, p):
            self.called = True

    o1 = Obj('Apple')
    subjects = [o1]
    # Single candidate immediate execution
    handled = functions.enumerate_for_interactions(subjects, player, ['examine'], 'examine')
    assert handled and o1.called

    # Multi-candidate with selection
    o2 = Obj('Apple Core')
    o1.called = False
    o2.called = False
    subjects = [o1, o2]
    # Choose second item (input '2')
    monkeypatch.setattr(builtins, 'input', lambda _='': '2')
    handled_multi = functions.enumerate_for_interactions(subjects, player, ['examine', 'apple'], 'examine apple')
    assert handled_multi and o2.called and not o1.called

    # Cancellation path
    monkeypatch.setattr(builtins, 'input', lambda _='': 'x')
    cancelled = functions.enumerate_for_interactions(subjects, player, ['examine', 'apple'], 'examine apple')
    assert cancelled is False


# ---------- screen_clear ----------

def test_screen_clear_calls_system(monkeypatch):
    calls = []
    monkeypatch.setattr(os, 'system', lambda cmd: calls.append(cmd) or 0)
    functions.screen_clear()
    assert any(cmd in ('cls', 'clear') for cmd in calls)


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


# ---------- check_parry ----------

def test_check_parry():
    target = types.SimpleNamespace(states=[types.SimpleNamespace(name='Parrying')])
    assert functions.check_parry(target) is True
    target.states = []
    assert functions.check_parry(target) is False


# ---------- spawn_npc / spawn_item ----------

def test_spawn_helpers():
    tile = types.SimpleNamespace(npcs_here=[], items_here=[])
    functions.spawn_npc('Enemy', tile)
    functions.spawn_item('Gem', tile)
    assert tile.npcs_here == ['Enemy'] and tile.items_here == ['Gem']


# ---------- refresh_moves ----------

def test_refresh_moves():
    player = DummyPlayer()
    functions.refresh_moves(player)
    # Simply ensure known_moves is a list and any populated moves originate from src.moves
    assert isinstance(player.known_moves, list)
    for mv in player.known_moves:
        assert mv.__class__.__module__.endswith('moves')


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


def test_print_slow(monkeypatch, capsys):
    # Speed up by removing sleep
    monkeypatch.setattr(functions.time, 'sleep', lambda *_: None)
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


def test_await_input(monkeypatch):
    captured = {}
    def fake_input(prompt=''):
        captured['prompt'] = prompt
        return ''
    monkeypatch.setattr(builtins, 'input', fake_input)
    functions.await_input()
    assert '(Press Enter)' in captured.get('prompt','')

# Append required imports for new tests
import pytest  # noqa: E402  (placed at end intentionally for minimal diff)
