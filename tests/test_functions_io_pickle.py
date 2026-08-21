import os
import sys
import builtins
import pickle
import types
import importlib
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

# -------- load_select cancel path with one file ---------

# -------- save_select new file and cancel paths ---------

# -------- SafeUnpickler placeholder creation ---------

def test_safe_unpickler_placeholder(tmp_path, monkeypatch):
    """A save referencing a class that no longer exists loads as a tagged
    placeholder carrying the original state, instead of blowing up.

    monkeypatch.setitem is used for the synthetic modules so they are removed
    even if an assertion fails partway — the previous `del sys.modules[...]`
    only ran on the happy path, leaking a fake `story` package into every
    later test in the worker.
    """
    mod_name = 'story.fake_mod'
    story_pkg = types.ModuleType('story')
    story_pkg.__path__ = []
    monkeypatch.setitem(sys.modules, 'story', story_pkg)
    ghost_mod = types.ModuleType(mod_name)
    # Define GhostClass at module scope (not a local closure) so pickle can locate it
    exec('class GhostClass:\n    def __init__(self):\n        self.payload = 42', ghost_mod.__dict__)
    monkeypatch.setitem(sys.modules, mod_name, ghost_mod)
    pfile = tmp_path / 'legacy_missing.sav'
    with open(pfile, 'wb') as f:
        pickle.dump(ghost_mod.GhostClass(), f, pickle.HIGHEST_PROTOCOL)

    # Remove the modules so the class cannot be found on load.
    monkeypatch.delitem(sys.modules, mod_name)
    monkeypatch.delitem(sys.modules, 'story')

    with open(pfile, 'rb') as f:
        loaded = functions._safe_pickle_load(f)

    # The unpickler rewrites the bare 'story.fake_mod' path to the canonical
    # 'src.story.fake_mod' before resolution, so the placeholder carries the
    # src-prefixed name.
    assert type(loaded).__name__ == 'LegacyMissing_src_story_fake_mod_GhostClass'
    assert repr(loaded) == '<LegacyMissing src.story.fake_mod.GhostClass>'
    # The pickled state survives onto the placeholder...
    assert loaded.payload == 42
    # ...and it is tagged + hidden so the engine never renders it in the world.
    assert loaded.hidden is True
    assert getattr(loaded, '_legacy_placeholder', False) is True


# -------- _patch_player_integrity non-Player path ---------

def test_patch_player_integrity_non_player():
    dummy = object()
    assert functions._patch_player_integrity(dummy) is dummy
