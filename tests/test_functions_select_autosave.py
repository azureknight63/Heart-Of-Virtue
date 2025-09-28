import os
import builtins
import pickle
import time
import types
import src.functions as functions

class SimplePlayer:
    def __init__(self):
        self.name = 'Jean'
        self.time_elapsed = 5  # seconds for playtime display
        # minimal base stats for any integrity operations
        self.inventory = []
        self.known_moves = []
        self.states = []
        self.combat_list = []
        self.combat_list_allies = []
        self.combat_events = []
        self.preferences = {"arrow": "Wooden Arrow"}
        self.resistance = {"fire": 1.0}
        self.status_resistance = {"generic": 0.0}
        self.strength_base = 1
        self.finesse_base = 1
        self.maxhp_base = 1
        self.maxfatigue_base = 1
        self.speed_base = 1
        self.endurance_base = 1
        self.charisma_base = 1
        self.intelligence_base = 1
        self.faith_base = 1
        self.resistance_base = {"fire": 1.0}
        self.status_resistance_base = {"generic": 0.0}
        self.weight_tolerance_base = 5
        self.weight_tolerance = 5
        self.weight_current = 0


def _functions_dir():
    return os.path.dirname(os.path.abspath(functions.__file__))


def _write_save(name: str, obj):
    path = os.path.join(_functions_dir(), name)
    with open(path, 'wb') as f:
        pickle.dump(obj, f, pickle.HIGHEST_PROTOCOL)
    # Touch mtime to now for deterministic ordering
    os.utime(path, None)
    return path


def test_load_select_invalid_then_success(monkeypatch):
    # Create two deterministic save files
    p1 = SimplePlayer(); p2 = SimplePlayer(); p2.time_elapsed = 10
    f1 = 'cov_ls_a.sav'; f2 = 'cov_ls_b.sav'
    _write_save(f1, p1)
    time.sleep(0.01)
    _write_save(f2, p2)

    # Input sequence: invalid '99' then select '0'
    seq = iter(['99', '0'])
    monkeypatch.setattr(builtins, 'input', lambda _='': next(seq))
    loaded = functions.load_select()
    assert isinstance(loaded, SimplePlayer)
    # Cleanup
    for f in (f1, f2):
        try: os.remove(os.path.join(_functions_dir(), f))
        except Exception: pass


def test_autosave_creates_file():
    player = SimplePlayer()
    # Remove autosave1 if present (root and src) to ensure creation path
    root_target = 'autosave1.sav'
    src_target = os.path.join(_functions_dir(), 'autosave1.sav')
    for t in (root_target, src_target):
        try:
            if os.path.exists(t):
                os.remove(t)
        except Exception:
            pass
    functions.autosave(player)
    assert os.path.exists(root_target) or os.path.exists(src_target)
