import os
import sys
import builtins
import pickle
import types
import importlib
import pytest
import src.functions as functions


class SimplePlayer:
    def __init__(self):
        self.name = 'Jean'
        self.inventory = []
        self.known_moves = []
        self.states = []
        self.combat_list = []
        self.combat_list_allies = []
        self.combat_events = []
        self.preferences = {"arrow": "Wooden Arrow"}
        self.resistance = {"fire": 1.0}
        self.status_resistance = {"generic": 0.0}
        # minimal bases for reset/refresh
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


def _src_dir():
    return os.path.dirname(os.path.abspath(functions.__file__))


# -------- load_select edge: no saves ---------

def test_load_select_no_files(monkeypatch):
    monkeypatch.setattr(functions, 'saves_list', lambda: [])
    assert functions.load_select() is None


# -------- load_select cancel path with one file ---------

def test_load_select_cancel(monkeypatch, tmp_path):
    base = _src_dir()
    fname = 'tmp_cov_load_cancel.sav'
    full = os.path.join(base, fname)
    with open(full, 'wb') as f:
        pickle.dump(SimplePlayer(), f, pickle.HIGHEST_PROTOCOL)
    monkeypatch.setattr(functions, 'saves_list', lambda: [fname])
    monkeypatch.setattr(builtins, 'input', lambda _='': 'x')
    assert functions.load_select() is None
    # cleanup
    try: os.remove(full)
    except Exception: pass


# -------- save_select new file and cancel paths ---------

def test_save_select_new_and_cancel(monkeypatch):
    player = SimplePlayer()
    # Sequence: create new file then exit (function returns None after loop)
    seq = iter(['n', 'tmp_cov_newfile', 'x'])
    monkeypatch.setattr(builtins, 'input', lambda _='': next(seq))
    functions.save_select(player)
    assert os.path.exists('tmp_cov_newfile.sav')
    # Cancel path
    seq2 = iter(['x'])
    monkeypatch.setattr(builtins, 'input', lambda _='': next(seq2))
    functions.save_select(player)  # should just exit
    try: os.remove('tmp_cov_newfile.sav')
    except Exception: pass


# -------- load error path (corrupt file) ---------

def test_load_corrupt_file(tmp_path):
    corrupt = tmp_path / 'corrupt_save.sav'
    with open(corrupt, 'wb') as f:
        f.write(b'not a pickle')
    with pytest.raises(RuntimeError):
        functions.load(str(corrupt))


# -------- SafeUnpickler placeholder creation ---------

def test_safe_unpickler_placeholder(tmp_path):
    # Dynamically create a temporary module 'story.fake_mod' with a class, pickle instance, then remove module
    mod_name = 'story.fake_mod'
    # Ensure synthetic 'story' package exists so pickle can import submodule
    story_pkg = types.ModuleType('story')
    story_pkg.__path__ = [os.path.join(os.path.dirname(os.path.dirname(functions.__file__)), 'src', 'story')]
    sys.modules['story'] = story_pkg
    ghost_mod = types.ModuleType(mod_name)
    # Define GhostClass at module scope (not a local closure) so pickle can locate it
    exec('class GhostClass:\n    def __init__(self):\n        self.payload = 42', ghost_mod.__dict__)
    sys.modules[mod_name] = ghost_mod
    obj = ghost_mod.GhostClass()
    pfile = tmp_path / 'legacy_missing.sav'
    with open(pfile, 'wb') as f:
        pickle.dump(obj, f, pickle.HIGHEST_PROTOCOL)
    # Remove modules so they can't be found on load
    del sys.modules[mod_name]
    del sys.modules['story']
    loaded = functions.load(str(pfile))
    # Expect placeholder class name pattern
    cls_name = loaded.__class__.__name__
    assert cls_name.startswith('LegacyMissing_story_fake_mod_GhostClass') or 'LegacyMissing story.fake_mod.GhostClass' in repr(loaded)
    # Placeholder should be hidden per generated attributes
    assert getattr(loaded, 'hidden', True) is True


# -------- _patch_player_integrity non-Player path ---------

def test_patch_player_integrity_non_player():
    dummy = object()
    assert functions._patch_player_integrity(dummy) is dummy
