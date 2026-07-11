"""Tests for TheAdjutant's debug operations.

The legacy terminal input() menu was replaced by parametrized operation methods
(driven by the test-only debug blueprint). These tests exercise those methods
directly.
"""

from unittest.mock import MagicMock, patch

from src.npc._adjutant import TheAdjutant
from src.npc._enemies import Slime


class MockPlayer:
    def __init__(self):
        self.hp = 100
        self.maxhp = 100
        self.heat = 1.0
        self.fatigue = 10
        self.maxfatigue = 10
        self.level = 1
        self.exp = 0
        self.exp_to_level = 100
        for attr in ("strength", "finesse", "speed", "endurance",
                     "charisma", "intelligence", "faith"):
            setattr(self, attr, 10)
            setattr(self, attr + "_base", 10)
        self.known_moves = []
        self.map = None


def _arena_player(coords=(1, 0), npcs=None):
    """A MockPlayer whose map has a single loaded arena tile at `coords`."""
    player = MockPlayer()
    tile = MagicMock()
    tile.npcs_here = list(npcs) if npcs else []
    player.map = {coords: tile}
    return player, tile


def test_adjutant_basic_properties():
    adj = TheAdjutant()
    assert adj.name == "The Adjutant"
    assert adj.keywords == ["talk", "set", "adjust", "configure", "help"]
    assert adj.pronouns["personal"] == "it"
    assert len(adj.known_moves) > 0


def test_keyword_verbs_narrate_without_menu():
    adj = TheAdjutant()
    player = MockPlayer()
    with patch("src.npc._adjutant.narrate") as mock_narrate:
        adj.talk(player)
        adj.set(player)
        adj.adjust(player)
        adj.configure(player)
        adj.help(player)
    assert mock_narrate.call_count == 5
    # No terminal menu lingering.
    assert not hasattr(adj, "_adjutant_menu")


# --- Player stat operations -------------------------------------------------

def test_player_state_returns_stats():
    adj = TheAdjutant()
    player = MockPlayer()
    state = adj.player_state(player)
    assert state["hp"] == 100
    assert state["level"] == 1
    assert state["attributes"]["strength"] == 10


def test_set_hp_clamps():
    adj = TheAdjutant()
    player = MockPlayer()
    result = adj.set_hp(player, 15, 30)
    assert player.maxhp == 30 and player.hp == 15
    assert result["hp"] == 15
    # hp clamped to maxhp
    adj.set_hp(player, 999, 50)
    assert player.hp == 50


def test_set_level():
    adj = TheAdjutant()
    player = MockPlayer()
    adj.set_level(player, 10, 500)
    assert player.level == 10 and player.exp == 500
    adj.set_level(player, 250, -5)
    assert player.level == 100 and player.exp == 0


def test_set_attributes_updates_known_and_ignores_unknown():
    adj = TheAdjutant()
    player = MockPlayer()
    result = adj.set_attributes(player, {"strength": 15, "bogus": 99})
    assert player.strength == 15 and player.strength_base == 15
    assert result["updated"] == {"strength": 15}


def test_set_attributes_accepts_base_suffixed_names():
    """Regression: passing 'speed_base' previously silently no-op'd —
    set_attributes only matched bare names, so the value was dropped while
    the call still reported success with an empty 'updated' dict."""
    adj = TheAdjutant()
    player = MockPlayer()
    result = adj.set_attributes(player, {"speed_base": 50})
    assert player.speed == 50 and player.speed_base == 50
    assert result["updated"] == {"speed": 50}


def test_set_attributes_base_suffix_normalizes_to_bare_key():
    adj = TheAdjutant()
    player = MockPlayer()
    result = adj.set_attributes(
        player, {"strength_base": 20, "finesse": 25, "bogus_base": 1}
    )
    assert player.strength == 20 and player.strength_base == 20
    assert player.finesse == 25 and player.finesse_base == 25
    assert result["updated"] == {"strength": 20, "finesse": 25}


def test_set_attributes_bare_suffix_only_is_ignored():
    """An attr that is exactly '_base' (all suffix, no stat name) normalizes
    to the empty string, which isn't in PLAYER_ATTRS, so it's safely skipped."""
    adj = TheAdjutant()
    player = MockPlayer()
    result = adj.set_attributes(player, {"_base": 99})
    assert result["updated"] == {}


def test_set_heat_clamps():
    adj = TheAdjutant()
    player = MockPlayer()
    adj.set_heat(player, 2.5)
    assert player.heat == 2.5
    adj.set_heat(player, 99)
    assert player.heat == 10.0


def test_restore_full():
    adj = TheAdjutant()
    player = MockPlayer()
    player.hp, player.fatigue = 5, 2
    adj.restore(player)
    assert player.hp == 100 and player.fatigue == 10


def test_learn_all_skills_delegates():
    adj = TheAdjutant()
    player = MockPlayer()
    with patch("src.functions.learn_all_skills_from_skilltree") as mock_learn:
        result = adj.learn_all_skills(player)
        assert mock_learn.called
        assert result["success"] is True


def test_list_skills():
    adj = TheAdjutant()
    player = MockPlayer()
    assert adj.list_skills(player) == []
    move = MagicMock()
    move.name = "Thrust"
    player.known_moves = [move]
    assert adj.list_skills(player) == ["Thrust"]


# --- Arena combatant management ---------------------------------------------

def test_arena_rosters_reports_loaded_and_unloaded():
    player, tile = _arena_player(coords=(1, 0), npcs=[Slime()])
    adj = TheAdjutant()
    rosters = adj.arena_rosters(player)
    assert rosters["Fodder Pit"]["loaded"] is True
    assert rosters["Fodder Pit"]["npcs"][0]["name"]
    # Other arenas are not in the map -> not loaded
    assert rosters["The Crucible"]["loaded"] is False


def test_add_combatant_known_class():
    player, tile = _arena_player()
    adj = TheAdjutant()
    result = adj.add_combatant(player, "Fodder Pit", "Slime")
    assert result["success"] is True
    assert len(tile.npcs_here) == 1
    assert tile.npcs_here[0].__class__.__name__ == "Slime"


def test_add_combatant_unknown_class():
    player, tile = _arena_player()
    adj = TheAdjutant()
    result = adj.add_combatant(player, "Fodder Pit", "FakeClass")
    assert result["success"] is False
    assert len(tile.npcs_here) == 0


def test_add_combatant_unknown_arena():
    player, _ = _arena_player()
    adj = TheAdjutant()
    result = adj.add_combatant(player, "Nowhere", "Slime")
    assert result["success"] is False


def test_add_combatant_tile_not_loaded():
    player = MockPlayer()
    player.map = {}  # arena coords absent
    adj = TheAdjutant()
    result = adj.add_combatant(player, "Fodder Pit", "Slime")
    assert result["success"] is False


def test_remove_combatant():
    player, tile = _arena_player(npcs=[Slime()])
    adj = TheAdjutant()
    result = adj.remove_combatant(player, "Fodder Pit", 0)
    assert result["success"] is True
    assert len(tile.npcs_here) == 0
    # bad index
    assert adj.remove_combatant(player, "Fodder Pit", 5)["success"] is False


def test_clear_room():
    player, tile = _arena_player(npcs=[Slime(), Slime()])
    adj = TheAdjutant()
    result = adj.clear_room(player, "Fodder Pit")
    assert result["cleared"] == 2
    assert tile.npcs_here == []


def test_set_combatant_stats():
    npc = Slime()
    player, _ = _arena_player(npcs=[npc])
    adj = TheAdjutant()
    result = adj.set_combatant_stats(
        player, "Fodder Pit", 0,
        {"hp": 50, "maxhp": 100, "aggro": False, "friend": True, "bogus": 1},
    )
    assert npc.hp == 50 and npc.maxhp == 100
    assert npc.aggro is False and npc.friend is True
    assert "bogus" not in result["updated"]
    # bad index
    assert adj.set_combatant_stats(player, "Fodder Pit", 9, {})["success"] is False


# --- Additional coverage: _resolve_arena, known_moves exception, and the -----
# --- "unknown arena" / "tile not loaded" branches of remove_combatant and ---
# --- set_combatant_stats (previously only exercised for add_combatant/    ---
# --- clear_room). --------------------------------------------------------

def test_known_moves_exception_falls_back_to_empty_list():
    with patch("src.npc._adjutant.moves.NpcIdle", side_effect=RuntimeError("boom")):
        adj = TheAdjutant()
    assert adj.known_moves == []


def test_resolve_arena_accepts_coords_tuple():
    adj = TheAdjutant()
    assert adj._resolve_arena((2, 0)) == (2, 0)
    assert adj._resolve_arena([2, 0]) == (2, 0)


def test_remove_combatant_unknown_arena():
    player, _ = _arena_player()
    adj = TheAdjutant()
    result = adj.remove_combatant(player, "Nowhere", 0)
    assert result["success"] is False
    assert "Unknown arena" in result["error"]


def test_remove_combatant_tile_not_loaded():
    player = MockPlayer()
    player.map = {}
    adj = TheAdjutant()
    result = adj.remove_combatant(player, "Fodder Pit", 0)
    assert result["success"] is False
    assert "not loaded" in result["error"]


def test_set_combatant_stats_unknown_arena():
    player, _ = _arena_player(npcs=[Slime()])
    adj = TheAdjutant()
    result = adj.set_combatant_stats(player, "Nowhere", 0, {"hp": 10})
    assert result["success"] is False
    assert "Unknown arena" in result["error"]


def test_set_combatant_stats_tile_not_loaded():
    player = MockPlayer()
    player.map = {}
    adj = TheAdjutant()
    result = adj.set_combatant_stats(player, "Fodder Pit", 0, {"hp": 10})
    assert result["success"] is False
    assert "not loaded" in result["error"]
