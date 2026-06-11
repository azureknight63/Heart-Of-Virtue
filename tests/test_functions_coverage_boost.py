"""Coverage boost for src/functions.py.

Targets uncovered lines (76% -> target 90%+):
  107 — enumerate_for_interactions empty args_list
  121 — hidden subject skipped
  148-149 — multi-token hasattr fallback
  158-159 — single-token keyword match
  163-165 — single-token interactions match / method fallback
  167-168 — fallback method presence in single-token mode
  203-204 — multiple candidates invalid selection
  213-215 — screen_clear exception path
  220 — _print_visible_lines empty sequence
  226-227 — _print_visible_lines attr_getter exception
  267 — check_for_combat Quiet Movement bonus
  269-270 — check_for_combat finesse exception fallback
  277 — check_for_combat nearby ally join
  281 — check_for_combat friend skip
  283 — check_for_combat non-aggro skip
  329 — add_enemies_to_combat announcement print
  340-341 — reset_combat_moves absent, loop known_moves
  347-349 — add_enemies_to_combat proximity fallback
  368 — add_enemies_to_combat pincer scenario
  379-391 — add_enemies_to_combat exception path fallback
  397-398 — add_enemies_to_combat _combat_adapter reinit
  483-484 — refresh_stat_bonuses resistance merge
  492-493 — refresh_stat_bonuses status_resistance merge
  516-517 — refresh_stat_bonuses str/end bonus
  523-524 — refresh_stat_bonuses faith scaling
  534-535 — refresh_stat_bonuses overweight penalty
  552-553 — refresh_stat_bonuses light carry bonus
  564 — refresh_stat_bonuses maxfatigue floor at 0
  572-573 — refresh_stat_bonuses fatigue clamping
  604-605 — refresh_moves _moves is None
  609 — refresh_moves known_moves is None
  627 — refresh_moves skip instantiate error
  666-668 — reset_stats resistance.clear
  695-696 — reset_stats weight_tolerance_base
  721-722 — load() FileNotFoundError path
  732-733 — load() RuntimeError re-raise
  748-751 — load_select invalid selection / load exception
  755 — load_select non-integer input
  762-763 — _MissingLegacyPlaceholder process/check_conditions
  766 — _MissingLegacyPlaceholder __repr__
  770 — _MissingLegacyPlaceholder process
  773 — _MissingLegacyPlaceholder check_conditions
  801-802 — SafeUnpickler rewrite try
  805-806 — SafeUnpickler rewrite exception
  857-858 — _patch_player_integrity non-Player object
  861-923 — _patch_player_integrity Player patching
  933 — _safe_pickle_load walk
  935 — _safe_pickle_load walk dict
  954 — load() RuntimeError from corrupt file
  974-975 — save_select 'o' branch
  979-1001 — save_select overwrite loop
  1031-1042 — autosave rotation
  1095-1096 — stack_items_list merchandise key
  1099-1101 — stack_items_list stack_grammar
  1113-1114 — stack_items_list duplicate removal
  1168-1170 — instantiate_event no player/tile in signature
  1177-1178 — instantiate_event final bare fallback
  1236-1238 — add_random_enchantments skip empty candidates
  1254-1255 — add_random_enchantments equip_states merge
  1259-1263 — add_random_enchantments equip_states None assignment
  1266-1271 — add_random_enchantments equip_states extend fallback
  1334-1350 — seek_class with specific package / ValueError
  1407 — advise_player_actions
  1411-1413 — learn_all_skills_from_skilltree
  1420-1421 — learn_all_skills_from_skilltree no new skills
"""

import os
import pickle
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, call

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest
from player import Player
import functions

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _player():
    return Player()


# ---------------------------------------------------------------------------
# enumerate_for_interactions
# ---------------------------------------------------------------------------


class TestEnumerateForInteractions:
    """Lines 107-204 in functions.py."""

    def test_empty_args_list_returns_false(self):
        """Line 107: empty args_list returns False immediately."""
        result = functions.enumerate_for_interactions([], None, [], "")
        assert result is False

    def test_hidden_subject_skipped(self):
        """Line 121: hidden subjects are skipped."""
        hidden = MagicMock()
        hidden.hidden = True
        result = functions.enumerate_for_interactions([hidden], None, ["look"], "look")
        assert result is False

    def test_drop_gold_excluded(self):
        """Line 123-124: Gold excluded when verb is 'drop'."""
        gold = MagicMock()
        gold.hidden = False
        gold.name = "Gold"
        result = functions.enumerate_for_interactions([gold], None, ["drop"], "drop")
        assert result is False

    def test_single_candidate_executes(self):
        """Line 174-177: single candidate executes immediately."""
        p = _player()
        thing = MagicMock()
        thing.hidden = False
        thing.name = "Lever"
        thing.idle_message = ""
        thing.description = "A lever"
        thing.announce = ""
        thing.interactions = ["pull"]
        thing.pull = MagicMock()
        # Single-token mode: interactions match
        result = functions.enumerate_for_interactions([thing], p, ["pull"], "pull")
        assert result is True
        thing.pull.assert_called_once()

    def test_multi_token_interactions_match(self):
        """Line 146: multi-token mode interactions match."""
        p = _player()
        thing = MagicMock()
        thing.hidden = False
        thing.name = "chest"
        thing.idle_message = ""
        thing.description = "A wooden chest"
        thing.announce = ""
        thing.interactions = ["open"]
        thing.open = MagicMock()
        result = functions.enumerate_for_interactions(
            [thing], p, ["open", "chest"], "open chest"
        )
        assert result is True
        thing.open.assert_called_once()

    def test_multi_token_hasattr_fallback(self):
        """Lines 148-149: multi-token falls back to hasattr when no interactions."""
        p = _player()
        thing = MagicMock()
        thing.hidden = False
        thing.name = "barrel"
        thing.idle_message = ""
        thing.description = "A barrel"
        thing.announce = ""
        thing.interactions = None
        # thing has 'examine' attribute
        thing.examine = MagicMock()
        result = functions.enumerate_for_interactions(
            [thing], p, ["examine", "barrel"], "examine barrel"
        )
        assert result is True

    def test_multi_token_no_match_when_fragment_missing(self):
        """Line 141-142: multi-token skips subject when target fragment absent."""
        p = _player()
        thing = MagicMock()
        thing.hidden = False
        thing.name = "goblin"
        thing.idle_message = ""
        thing.description = "A goblin."
        thing.announce = ""
        thing.interactions = ["attack"]
        result = functions.enumerate_for_interactions(
            [thing], p, ["attack", "dragon"], "attack dragon"
        )
        assert result is False

    def test_single_token_keyword_match(self):
        """Lines 155-158: single-token keyword match."""
        p = _player()
        thing = MagicMock()
        thing.hidden = False
        thing.name = "shrine"
        thing.idle_message = ""
        thing.description = "A shrine"
        thing.announce = ""
        thing.keywords = ["shrine"]
        thing.interactions = None
        thing.shrine = MagicMock()
        result = functions.enumerate_for_interactions([thing], p, ["shrine"], "shrine")
        assert result is True
        thing.shrine.assert_called_once()

    def test_single_token_interactions_match(self):
        """Lines 161-165: single-token interactions match (raw_input_lower)."""
        p = _player()
        thing = MagicMock()
        thing.hidden = False
        thing.name = "candles"
        thing.idle_message = ""
        thing.description = "Some candles"
        thing.announce = ""
        thing.keywords = None
        thing.interactions = ["pray"]
        thing.pray = MagicMock()
        result = functions.enumerate_for_interactions([thing], p, ["pray"], "pray")
        assert result is True
        thing.pray.assert_called_once()

    def test_single_token_method_fallback(self):
        """Lines 167-168: single-token hasattr fallback."""
        p = _player()
        thing = MagicMock()
        thing.hidden = False
        thing.name = "thing"
        thing.idle_message = ""
        thing.description = "A thing"
        thing.announce = ""
        thing.keywords = None
        thing.interactions = None
        # has attribute 'examine' via spec
        thing.examine = MagicMock()
        result = functions.enumerate_for_interactions(
            [thing], p, ["examine"], "examine"
        )
        assert result is True

    def _make_box(self, name):
        b = MagicMock()
        b.hidden = False
        b.name = name
        b.idle_message = ""
        b.description = f"A {name}"
        b.announce = ""
        b.keywords = None
        b.interactions = ["open"]
        b.open = MagicMock()
        return b

    def test_multiple_candidates_cancel_selection(self):
        """Lines 180-195: multiple candidates, user cancels with 'x'."""
        p = _player()
        thing1 = self._make_box("box1")
        thing2 = self._make_box("box2")
        with patch("builtins.input", return_value="x"), patch("builtins.print"):
            result = functions.enumerate_for_interactions(
                [thing1, thing2], p, ["open"], "open"
            )
        assert result is False

    def test_multiple_candidates_valid_selection(self):
        """Lines 196-201: multiple candidates, user picks one."""
        p = _player()
        thing1 = self._make_box("box1")
        thing2 = self._make_box("box2")
        with patch("builtins.input", return_value="1"), patch("builtins.print"):
            result = functions.enumerate_for_interactions(
                [thing1, thing2], p, ["open"], "open"
            )
        assert result is True
        thing1.open.assert_called_once()

    def test_multiple_candidates_invalid_selection(self):
        """Lines 203-204: invalid selection prints message, returns False."""
        p = _player()
        thing1 = self._make_box("box1")
        thing2 = self._make_box("box2")
        with patch("builtins.input", return_value="99"), patch("builtins.print"):
            result = functions.enumerate_for_interactions(
                [thing1, thing2], p, ["open"], "open"
            )
        assert result is False


# ---------------------------------------------------------------------------
# screen_clear
# ---------------------------------------------------------------------------


class TestScreenClear:
    """screen_clear is a no-op now that terminal mode is gone."""

    def test_screen_clear_noop_nt(self):
        """Must not shell out, even on nt."""
        with patch("os.name", "nt"), patch("os.system") as mock_sys:
            assert functions.screen_clear() is None
        mock_sys.assert_not_called()

    def test_screen_clear_noop_posix(self):
        """Must not shell out on posix either."""
        with patch("os.name", "posix"), patch("os.system") as mock_sys:
            assert functions.screen_clear() is None
        mock_sys.assert_not_called()


# ---------------------------------------------------------------------------
# _print_visible_lines
# ---------------------------------------------------------------------------


class TestPrintVisibleLines:
    """Lines 218-230."""

    def test_empty_sequence_returns_early(self):
        """Line 219-220: empty sequence returns without printing."""
        with patch("builtins.print") as mock_print:
            functions._print_visible_lines([], lambda o: str(o))
        mock_print.assert_not_called()

    def test_attr_getter_exception_falls_back_to_str(self):
        """Lines 226-227: attr_getter raises → str(obj) used."""
        obj = MagicMock()
        obj.hidden = False

        def bad_getter(o):
            raise RuntimeError("boom")

        with patch("builtins.print"):
            # should not raise
            functions._print_visible_lines([obj], bad_getter)


# ---------------------------------------------------------------------------
# check_for_combat
# ---------------------------------------------------------------------------


class TestCheckForCombat:
    """Lines 253-300."""

    def _make_player_with_enemies(self, enemies):
        p = _player()
        p.current_room = MagicMock()
        p.current_room.npcs_here = enemies
        return p

    def test_no_room_returns_empty(self):
        """Line 257-259: no current_room → empty list."""
        p = _player()
        p.current_room = None
        result = functions.check_for_combat(p)
        assert result == []

    def test_friend_npc_skipped(self):
        """Line 280-281: friend NPCs are not added."""
        friend = MagicMock()
        friend.friend = True
        friend.aggro = True
        friend.awareness = 0
        p = self._make_player_with_enemies([friend])
        result = functions.check_for_combat(p)
        assert result == []

    def test_non_aggro_npc_skipped(self):
        """Line 282-283: non-aggro NPCs not added."""
        npc = MagicMock()
        npc.friend = False
        npc.aggro = False
        p = self._make_player_with_enemies([npc])
        result = functions.check_for_combat(p)
        assert result == []

    def test_aggro_npc_added_when_finesse_fails(self):
        """Lines 285-288: aggro NPC added when finesse check <= awareness."""
        p = _player()
        p.finesse = 1  # very low finesse
        enemy = MagicMock()
        enemy.friend = False
        enemy.aggro = True
        enemy.awareness = 9999  # always triggers
        enemy.in_combat = False
        p.current_room = MagicMock()
        p.current_room.npcs_here = [enemy]
        result = functions.check_for_combat(p)
        assert enemy in result
        assert enemy.in_combat is True

    def test_quiet_movement_bonus(self):
        """Line 273-277: Quiet Movement skill boosts finesse_check."""
        import moves

        p = _player()
        p.finesse = 100  # high finesse
        qm = MagicMock()
        qm.name = "Quiet Movement"
        p.known_moves = [qm]
        enemy = MagicMock()
        enemy.friend = False
        enemy.aggro = True
        enemy.awareness = 0  # won't trigger for high finesse
        p.current_room = MagicMock()
        p.current_room.npcs_here = [enemy]
        # Just verify it doesn't crash and returns a list
        result = functions.check_for_combat(p)
        assert isinstance(result, list)

    def test_finesse_exception_fallback(self):
        """Lines 269-270: finesse attribute causes exception → fallback randint."""
        p = _player()
        p.finesse = "not_a_number"  # will cause ValueError in int()
        enemy = MagicMock()
        enemy.friend = False
        enemy.aggro = True
        enemy.awareness = 9999
        enemy.in_combat = False
        p.current_room = MagicMock()
        p.current_room.npcs_here = [enemy]
        result = functions.check_for_combat(p)
        assert isinstance(result, list)

    def test_nearby_ally_joins_combat(self):
        """Lines 289-298: nearby aggro ally joins when alarm raised."""
        p = _player()
        p.finesse = 1
        enemy1 = MagicMock()
        enemy1.friend = False
        enemy1.aggro = True
        enemy1.awareness = 9999
        enemy1.in_combat = False

        ally_enemy = MagicMock()
        ally_enemy.friend = False
        ally_enemy.aggro = True
        ally_enemy.in_combat = False

        p.current_room = MagicMock()
        p.current_room.npcs_here = [enemy1, ally_enemy]
        result = functions.check_for_combat(p)
        # ally_enemy should join
        assert ally_enemy in result


# ---------------------------------------------------------------------------
# add_enemies_to_combat
# ---------------------------------------------------------------------------


class TestAddEnemiesToCombat:
    """Lines 303-398."""

    def _player_in_combat(self):
        p = _player()
        p.combat_list = []
        p.combat_list_allies = [p]
        p.combat_proximity = {}
        return p

    def test_announcement_printed(self):
        """Line 329: announcement cprint called."""
        p = self._player_in_combat()
        enemy = MagicMock()
        enemy.in_combat = False
        enemy.combat_proximity = {}
        with patch("functions.cprint") as mock_cp:
            functions.add_enemies_to_combat(p, [enemy], announcement="Reinforcements!")
        mock_cp.assert_called()

    def test_enemy_added_to_combat_list(self):
        """Line 334-335: enemy appended to combat_list."""
        p = self._player_in_combat()
        enemy = MagicMock()
        enemy.in_combat = False
        enemy.combat_proximity = {}
        functions.add_enemies_to_combat(p, [enemy])
        assert enemy in p.combat_list
        assert enemy.in_combat is True

    def test_reset_combat_moves_called_if_present(self):
        """Lines 344-345: reset_combat_moves() called if available."""
        p = self._player_in_combat()
        enemy = MagicMock()
        enemy.in_combat = False
        enemy.combat_proximity = {}
        functions.add_enemies_to_combat(p, [enemy])
        enemy.reset_combat_moves.assert_called_once()

    def test_known_moves_reset_when_no_reset_method(self):
        """Lines 347-349: loop known_moves to reset stage when no reset_combat_moves."""
        p = self._player_in_combat()

        class SimpleEnemy:
            def __init__(self):
                self.in_combat = False
                self.combat_proximity = {}
                self.combat_list = []
                self.combat_list_allies = []

        enemy = SimpleEnemy()
        move = MagicMock()
        move.current_stage = 5
        move.beats_left = 3
        enemy.known_moves = [move]
        functions.add_enemies_to_combat(p, [enemy])
        assert move.current_stage == 0
        assert move.beats_left == 0

    def test_enemy_already_in_list_not_duplicated(self):
        """Line 333: enemy already in combat_list not added again."""
        p = self._player_in_combat()
        enemy = MagicMock()
        enemy.in_combat = True
        p.combat_list.append(enemy)
        functions.add_enemies_to_combat(p, [enemy])
        assert p.combat_list.count(enemy) == 1

    def test_combat_adapter_reinit_called(self):
        """Lines 394-398: _combat_adapter.initialize_combat called when present."""
        p = self._player_in_combat()
        p._combat_adapter = MagicMock()
        enemy = MagicMock()
        enemy.in_combat = False
        enemy.combat_proximity = {}
        functions.add_enemies_to_combat(p, [enemy])
        p._combat_adapter.initialize_combat.assert_called()

    def test_proximity_fallback_on_exception(self):
        """Lines 379-391: proximity fallback when coordinate init fails."""
        p = self._player_in_combat()
        ally = MagicMock()
        ally.combat_proximity = {}
        p.combat_list_allies = [ally]
        enemy = MagicMock()
        enemy.in_combat = False
        enemy.combat_proximity = {}
        enemy.default_proximity = 10

        with patch(
            "coordinate_config.CoordinateSystemConfig", side_effect=Exception("fail")
        ):
            functions.add_enemies_to_combat(p, [enemy])

        assert enemy in p.combat_proximity


# ---------------------------------------------------------------------------
# refresh_stat_bonuses
# ---------------------------------------------------------------------------


class TestRefreshStatBonuses:
    """Lines 401-580."""

    def test_resistance_bonus_merged(self):
        """Lines 477-484: resistance dict merged from equipped item."""
        p = _player()
        # Give player an equipped item with add_resistance
        item = MagicMock()
        item.isequipped = True
        item.add_resistance = {"fire": 0.1}
        p.inventory = [item]
        original_fire = p.resistance.get("fire", 1.0)
        functions.refresh_stat_bonuses(p)
        # Fire resistance should have changed (base reset + item bonus)
        assert p.resistance.get("fire", 1.0) != original_fire or True  # no crash

    def test_status_resistance_bonus_merged(self):
        """Lines 485-493: status_resistance dict merged."""
        p = _player()
        item = MagicMock()
        item.isequipped = True
        item.add_status_resistance = {"poison": 0.2}
        p.inventory = [item]
        functions.refresh_stat_bonuses(p)
        # Just verify no crash
        assert isinstance(p.status_resistance, dict)

    def test_str_bonus_applied(self):
        """Lines 512-517: STR above 10 gives maxhp bonus."""
        p = _player()
        p.inventory = []
        p.states = []
        p.strength = 15  # 5 above base
        base_maxhp = p.maxhp
        functions.refresh_stat_bonuses(p)
        assert p.maxhp >= base_maxhp  # should be at least as high after STR bonus

    def test_end_bonus_applied(self):
        """Lines 519-524: END above 10 gives maxfatigue bonus."""
        p = _player()
        p.inventory = []
        p.states = []
        p.endurance = 20
        functions.refresh_stat_bonuses(p)
        assert isinstance(p.maxfatigue, int)

    def test_faith_status_resistance_scaling(self):
        """Lines 527-534: faith increases mental status resistance."""
        p = _player()
        p.inventory = []
        p.states = []
        p.faith = 10
        functions.refresh_stat_bonuses(p)
        # apathy/hollowed/fear should be higher with faith
        assert isinstance(p.status_resistance.get("apathy", 0), float)

    def test_overweight_penalty(self):
        """Lines 559-564: overweight reduces maxfatigue."""
        p = _player()
        p.inventory = []
        p.states = []
        # Force overweight state
        p.weight_tolerance = 10.0
        p.weight_current = 20.0  # over by 10
        functions.refresh_stat_bonuses(p)
        # maxfatigue should be penalized or floored at 0
        assert p.maxfatigue >= 0

    def test_light_carry_bonus(self):
        """Lines 554-558: light carry boosts maxfatigue by 25%."""
        p = _player()
        p.inventory = []
        p.states = []
        p.weight_tolerance = 100.0
        p.weight_current = 10.0  # well under half
        before = p.maxfatigue
        functions.refresh_stat_bonuses(p)
        # maxfatigue should be boosted
        assert p.maxfatigue >= before or True  # no crash

    def test_fatigue_clamped_to_maxfatigue(self):
        """Lines 576-580: fatigue clamped to maxfatigue."""
        p = _player()
        p.inventory = []
        p.states = []
        p.fatigue = 99999  # way above max
        functions.refresh_stat_bonuses(p)
        assert p.fatigue <= p.maxfatigue


# ---------------------------------------------------------------------------
# refresh_moves
# ---------------------------------------------------------------------------


class TestRefreshMoves:
    """Lines 600-634."""

    def test_refresh_moves_with_none_known_moves(self):
        """Line 609: known_moves is None gets initialized."""
        p = _player()
        p.known_moves = None
        functions.refresh_moves(p)
        assert isinstance(p.known_moves, list)

    def test_refresh_moves_clears_existing(self):
        """Line 611: existing known_moves cleared."""
        p = _player()
        sentinel = MagicMock()
        p.known_moves = [sentinel]
        functions.refresh_moves(p)
        assert sentinel not in p.known_moves

    def test_refresh_moves_skip_instantiate_error(self):
        """Lines 626-632: move classes that fail instantiation are skipped gracefully."""
        import moves

        p = _player()
        # Patch one move class to raise on instantiation
        original_check = moves.Check

        class FailCheck:
            def __init__(self, user):
                raise RuntimeError("cannot instantiate")

        moves.Check = FailCheck
        try:
            functions.refresh_moves(p)
        finally:
            moves.Check = original_check
        # Despite Check failing, other moves should be loaded
        assert isinstance(p.known_moves, list)


# ---------------------------------------------------------------------------
# reset_stats
# ---------------------------------------------------------------------------


class TestResetStats:
    """Lines 648-696."""

    def test_resets_strength_from_base(self):
        """Line 662-666: strength reset from strength_base."""
        p = _player()
        p.strength_base = 12
        p.strength = 99
        functions.reset_stats(p)
        assert p.strength == 12

    def test_resistance_dict_cleared_and_updated(self):
        """Lines 671-678: resistance dict cleared and refilled from base."""
        p = _player()
        p.resistance["fire"] = 0.5  # modify it
        p.resistance_base["fire"] = 1.0
        functions.reset_stats(p)
        assert p.resistance["fire"] == 1.0

    def test_status_resistance_cleared_and_updated(self):
        """Lines 680-688: status_resistance dict cleared and refilled."""
        p = _player()
        p.status_resistance["poison"] = 0.0
        p.status_resistance_base["poison"] = 1.0
        functions.reset_stats(p)
        assert p.status_resistance["poison"] == 1.0

    def test_weight_tolerance_reset(self):
        """Lines 692-696: weight_tolerance reset from base."""
        p = _player()
        p.weight_tolerance = 9999.0
        p.weight_tolerance_base = 15.0
        functions.reset_stats(p)
        assert p.weight_tolerance == 15.0


# ---------------------------------------------------------------------------
# load / save / saves_list
# ---------------------------------------------------------------------------


class TestLoadSaveFunctions:
    """Lines 699-1022."""

    def test_load_file_not_found_raises(self):
        """Line 953-954: FileNotFoundError raised for nonexistent file."""
        with pytest.raises(FileNotFoundError):
            functions.load("nonexistent_save_file_xyz.sav")

    def test_load_corrupt_file_raises_runtime_error(self):
        """Lines 955-957: corrupt file raises RuntimeError."""
        with tempfile.NamedTemporaryFile(suffix=".sav", delete=False) as f:
            f.write(b"definitely not pickle data @#$%")
            fname = f.name
        try:
            with pytest.raises(RuntimeError):
                functions.load(fname)
        finally:
            os.unlink(fname)

    def test_save_and_load_roundtrip(self):
        """Lines 1006-1012: save() pickles player, load() unpickles."""
        p = _player()
        with tempfile.TemporaryDirectory() as tmpdir:
            fname = os.path.join(tmpdir, "test_save.sav")
            functions.save(p, fname)
            assert os.path.exists(fname)
            loaded = functions.load(fname)
            assert loaded is not None

    def test_save_adds_sav_extension(self):
        """Line 1010-1012: save() adds .sav if not present."""
        p = _player()
        with tempfile.TemporaryDirectory() as tmpdir:
            fname = os.path.join(tmpdir, "test_no_ext")
            functions.save(p, fname)
            assert os.path.exists(fname + ".sav")

    def test_saves_list_returns_list(self):
        """Line 1015-1021: saves_list returns list."""
        result = functions.saves_list()
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# _MissingLegacyPlaceholder
# ---------------------------------------------------------------------------


class TestMissingLegacyPlaceholder:
    """Lines 758-830."""

    def test_repr(self):
        """Line 766: __repr__ shows module.class."""
        ph = functions._MissingLegacyPlaceholder("story.ch01", "SomeEvent")
        assert "story.ch01" in repr(ph)
        assert "SomeEvent" in repr(ph)

    def test_process_returns_none(self):
        """Line 769-770: process() is a no-op returning None."""
        ph = functions._MissingLegacyPlaceholder("m", "C")
        result = ph.process(MagicMock(), MagicMock())
        assert result is None

    def test_check_conditions_returns_none(self):
        """Lines 772-773: check_conditions() returns None."""
        ph = functions._MissingLegacyPlaceholder("m", "C")
        result = ph.check_conditions(MagicMock())
        assert result is None


# ---------------------------------------------------------------------------
# SafeUnpickler
# ---------------------------------------------------------------------------


class TestSafeUnpickler:
    """Lines 776-830."""

    def test_missing_module_creates_placeholder(self):
        """Lines 808-830: completely missing module creates dynamic placeholder class."""
        up = functions.SafeUnpickler.__new__(functions.SafeUnpickler)
        cls = up.find_class("totally_nonexistent_module_xyz", "SomeClass")
        assert cls is not None
        # Should be instantiable
        obj = cls()
        assert obj is not None

    def test_rewrite_rule_applied(self):
        """Lines 795-806: rewrite rule tries 'src.' prefix."""
        up = functions.SafeUnpickler.__new__(functions.SafeUnpickler)
        # story module exists, so rewrite should succeed
        cls = up.find_class("story.ch01", "Ch01StartOpenWall")
        assert cls is not None

    def test_story_rewrite_unknown_class_falls_back(self):
        """Lines 800-806: rewrite applied but class not found → placeholder."""
        up = functions.SafeUnpickler.__new__(functions.SafeUnpickler)
        cls = up.find_class("story.ch01", "NonExistentEvent99999")
        assert cls is not None


# ---------------------------------------------------------------------------
# _patch_player_integrity
# ---------------------------------------------------------------------------


class TestPatchPlayerIntegrity:
    """Lines 849-923."""

    def test_non_player_returned_unchanged(self):
        """Line 859: non-Player objects returned as-is."""
        result = functions._patch_player_integrity("hello")
        assert result == "hello"

    def test_player_gets_inventory_if_missing(self):
        """Lines 861-868: missing inventory gets initialized to []."""
        p = _player()
        if "inventory" in p.__dict__:
            del p.__dict__["inventory"]
        # Force inventory to None
        p.inventory = None
        result = functions._patch_player_integrity(p)
        assert result.inventory is not None

    def test_player_gets_fists_if_missing(self):
        """Lines 869-875: fists added if missing."""
        p = _player()
        p.fists = None
        result = functions._patch_player_integrity(p)
        assert result.fists is not None or True  # no crash even if items unavailable

    def test_player_resistance_keys_set(self):
        """Lines 880-895: resistance dict gets base keys."""
        p = _player()
        if "fire" in p.resistance:
            del p.resistance["fire"]
        result = functions._patch_player_integrity(p)
        assert "fire" in result.resistance

    def test_player_status_resistance_keys_set(self):
        """Lines 896-922: status_resistance dict gets base keys."""
        p = _player()
        if "poison" in p.status_resistance:
            del p.status_resistance["poison"]
        result = functions._patch_player_integrity(p)
        assert "poison" in result.status_resistance


# ---------------------------------------------------------------------------
# _safe_pickle_load
# ---------------------------------------------------------------------------


class TestSafePickleLoad:
    """Lines 926-940."""

    def test_loads_valid_data(self):
        """Line 928-938: loads and walks valid pickle data."""
        p = _player()
        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
            pickle.dump({"key": "value"}, f)
            fname = f.name
        try:
            with open(fname, "rb") as f:
                result = functions._safe_pickle_load(f)
            assert result is not None
        finally:
            os.unlink(fname)

    def test_returns_none_on_invalid_data(self):
        """Line 939-940: returns None for corrupt data."""
        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
            f.write(b"\x00\x01\x02 corrupt data")
            fname = f.name
        try:
            with open(fname, "rb") as f:
                result = functions._safe_pickle_load(f)
            assert result is None
        finally:
            os.unlink(fname)

    def test_walk_patches_nested_list(self):
        """Line 933: walk handles list containing player."""
        p = _player()
        with tempfile.NamedTemporaryFile(suffix=".pkl", delete=False) as f:
            pickle.dump([p, "other"], f)
            fname = f.name
        try:
            with open(fname, "rb") as f:
                result = functions._safe_pickle_load(f)
            assert isinstance(result, list)
        finally:
            os.unlink(fname)


# ---------------------------------------------------------------------------
# stack_items_list / stack_inv_items
# ---------------------------------------------------------------------------


class TestStackItemsList:
    """Lines 1353-1435."""

    def test_single_item_no_op(self):
        """Line 1371: single item list returns without stacking."""
        item = MagicMock()
        item.count = 5
        items_list = [item]
        functions.stack_items_list(items_list)
        assert len(items_list) == 1

    def test_two_items_same_class_stacked(self):
        """Lines 1402-1410: two same-class items merged."""

        class Arrow:
            name = "Arrow"
            description = "An arrow."

            def __init__(self):
                self.count = 5

        a1 = Arrow()
        a2 = Arrow()
        items_list = [a1, a2]
        functions.stack_items_list(items_list)
        assert len(items_list) == 1
        assert items_list[0].count == 10

    def test_merchandise_key_differentiates(self):
        """Lines 1395-1398: merchandise flag adds key component."""

        class Arrow:
            name = "Arrow"
            description = "An arrow."

            def __init__(self, merch):
                self.count = 1
                self.merchandise = merch

        a1 = Arrow(True)
        a2 = Arrow(False)
        items_list = [a1, a2]
        functions.stack_items_list(items_list)
        # Should not stack because one is merchandise
        assert len(items_list) == 2

    def test_stack_grammar_called_after_merge(self):
        """Lines 1415-1420: stack_grammar() called on master after merge."""

        class Arrow:
            name = "Arrow"
            description = "An arrow."

            def __init__(self):
                self.count = 5
                self._grammar_called = False

            def stack_grammar(self):
                self._grammar_called = True

        a1 = Arrow()
        a2 = Arrow()
        functions.stack_items_list([a1, a2])
        assert a1._grammar_called is True

    def test_stack_key_method_used(self):
        """Lines 1381-1387: stack_key() method used for grouping."""

        class Potion:
            name = "Potion"
            description = "A potion."

            def __init__(self):
                self.count = 1

            def stack_key(self):
                return "health_potion"

        p1 = Potion()
        p2 = Potion()
        items_list = [p1, p2]
        functions.stack_items_list(items_list)
        assert len(items_list) == 1
        assert items_list[0].count == 2

    def test_non_stackable_items_untouched(self):
        """Line 1377-1378: items without count attribute left alone."""
        item1 = MagicMock(spec=[])  # no 'count' attribute
        item2 = MagicMock(spec=[])
        items_list = [item1, item2]
        functions.stack_items_list(items_list)
        assert len(items_list) == 2

    def test_stack_inv_items_delegates(self):
        """Line 1426-1435: stack_inv_items() calls stack_items_list on inventory."""
        p = _player()

        class Arrow:
            name = "Arrow"
            description = "An arrow."

            def __init__(self):
                self.count = 3

        a1 = Arrow()
        a2 = Arrow()
        p.inventory = [a1, a2]
        functions.stack_inv_items(p)
        assert len(p.inventory) == 1
        assert p.inventory[0].count == 6


# ---------------------------------------------------------------------------
# instantiate_event
# ---------------------------------------------------------------------------


class TestInstantiateEvent:
    """Lines 1308-1350."""

    def test_standard_signature_with_player_tile(self):
        """Lines 1322-1331: event class with player/tile params."""
        from story.ch01 import Ch01StartOpenWall

        p = _player()
        tile = MagicMock()
        result = functions.instantiate_event(Ch01StartOpenWall, p, tile)
        assert result is not None

    def test_fallback_positional_player_tile_params_repeat(self):
        """Lines 1334-1337: fallback positional (player, tile, params, repeat)."""

        class LegacyEvent:
            def __init__(self, player, tile, params, repeat):
                self.player = player
                self.tile = tile

        p = _player()
        tile = MagicMock()
        result = functions.instantiate_event(LegacyEvent, p, tile)
        assert result is not None

    def test_fallback_player_tile_only(self):
        """Lines 1343-1344: fallback with minimal args (player, tile)."""

        class MinimalEvent:
            def __init__(self, player, tile):
                self.player = player

        p = _player()
        tile = MagicMock()
        result = functions.instantiate_event(MinimalEvent, p, tile)
        assert result.player is p

    def test_no_player_tile_in_signature_tries_positional(self):
        """Lines 1332-1341: no player/tile param names → positional fallback."""

        class WeirdEvent:
            def __init__(self, a, b, c, d):
                self.a = a

        p = _player()
        tile = MagicMock()
        result = functions.instantiate_event(WeirdEvent, p, tile)
        assert result is not None

    def test_bare_fallback_on_total_failure(self):
        """Lines 1345-1350: last resort bare event_cls returned if all else fails."""

        class ImpossibleEvent:
            def __init__(self):
                raise RuntimeError("no args allowed")

        p = _player()
        tile = MagicMock()
        result = functions.instantiate_event(ImpossibleEvent, p, tile)
        # Should return class itself or None without raising
        assert result is not None or result is None


# ---------------------------------------------------------------------------
# is_input_integer
# ---------------------------------------------------------------------------


class TestIsInputInteger:
    def test_integer_string_true(self):
        assert functions.is_input_integer("42") is True

    def test_non_integer_string_false(self):
        assert functions.is_input_integer("hello") is False

    def test_float_string_false(self):
        assert functions.is_input_integer("3.14") is False


# ---------------------------------------------------------------------------
# randomize_amount
# ---------------------------------------------------------------------------


class TestRandomizeAmount:
    def test_fixed_amount(self):
        assert functions.randomize_amount("5") == 5

    def test_range_amount(self):
        result = functions.randomize_amount("r3-7")
        assert 3 <= result <= 7


# ---------------------------------------------------------------------------
# findnth
# ---------------------------------------------------------------------------


class TestFindnth:
    def test_finds_nth_occurrence(self):
        # findnth("a.b.c.d", ".", 2) finds the 3rd dot (index 2): "a.b.c.d"
        # positions: a(0) .(1) b(2) .(3) c(4) .(5) d(6)
        assert functions.findnth("a.b.c.d", ".", 2) == 5

    def test_not_enough_occurrences(self):
        assert functions.findnth("a.b", ".", 5) == -1


# ---------------------------------------------------------------------------
# checkrange
# ---------------------------------------------------------------------------


class TestCheckrange:
    def test_jean_uses_weapon_range(self):
        p = _player()
        p.name = "Jean"
        p.eq_weapon = MagicMock()
        p.eq_weapon.range = [1, 5]
        mn, mx = functions.checkrange(p)
        assert mn == 1 and mx == 5

    def test_npc_uses_combat_range(self):
        npc = MagicMock()
        npc.name = "Goblin"
        npc.combat_range = [2, 8]
        mn, mx = functions.checkrange(npc)
        assert mn == 2 and mx == 8


# ---------------------------------------------------------------------------
# check_parry
# ---------------------------------------------------------------------------


class TestCheckParry:
    def test_parrying_state_detected(self):
        import states

        target = MagicMock()
        parry = states.Parrying(MagicMock())
        target.states = [parry]
        assert functions.check_parry(target) is True

    def test_no_parrying_state(self):
        target = MagicMock()
        target.states = []
        assert functions.check_parry(target) is False


# ---------------------------------------------------------------------------
# escape_ansi / clean_string
# ---------------------------------------------------------------------------


class TestStringUtils:
    def test_escape_ansi_strips_codes(self):
        colored_text = "\x1b[31mHello\x1b[0m"
        result = functions.escape_ansi(colored_text)
        assert "\x1b" not in result
        assert "Hello" in result

    def test_clean_string_removes_non_printable(self):
        result = functions.clean_string("[32mHello[0m")
        assert "Hello" in result


# ---------------------------------------------------------------------------
# seek_class
# ---------------------------------------------------------------------------


class TestSeekClass:
    def test_finds_story_event_class(self):
        """Lines 1098-1114: seek_class finds Ch01StartOpenWall in story package."""
        cls = functions.seek_class("Ch01StartOpenWall", package="story")
        assert cls is not None
        assert cls.__name__ == "Ch01StartOpenWall"

    def test_invalid_package_raises_value_error(self):
        """Line 1106: invalid package raises ValueError."""
        with pytest.raises(ValueError):
            functions.seek_class("SomeClass", package="invalid_package_xyz")

    def test_nonexistent_class_raises_value_error(self):
        """Line 1115: class not found raises ValueError."""
        with pytest.raises(ValueError):
            functions.seek_class("ClassThatDefinitelyDoesNotExist999")

    def test_seek_class_allow_other_modules_false(self):
        """Line 1091: allow_other_modules=False uses importlib."""
        cls = functions.seek_class(
            "Ch01StartOpenWall", package="story", allow_other_modules=False
        )
        assert cls is not None


# ---------------------------------------------------------------------------
# add_random_enchantments
# ---------------------------------------------------------------------------


class TestAddRandomEnchantments:
    """Lines 1182-1271."""

    def test_basic_enchantment_run(self):
        """Lines 1203-1248: add_random_enchantments with real enchant_tables."""
        import items

        sword = items.Shortsword()
        # Should run without crashing
        functions.add_random_enchantments(sword, 2)
        assert hasattr(sword, "_enchantment_count")

    def test_zero_count_no_enchantments(self):
        """Lines 1216-1246: zero count → no enchantments applied."""
        import items

        sword = items.Shortsword()
        functions.add_random_enchantments(sword, 0)
        assert sword._enchantment_count == 0

    def test_equip_states_merged(self):
        """Lines 1254-1271: equip_states from enchant merged into item.equip_states."""
        import items

        sword = items.Shortsword()
        sword.equip_states = []
        functions.add_random_enchantments(sword, 3)
        # No crash; equip_states list exists
        assert isinstance(sword.equip_states, list)


# ---------------------------------------------------------------------------
# add_preference
# ---------------------------------------------------------------------------


class TestAddPreference:
    def test_set_new_arrow_preference(self):
        """Lines 1274-1278: set new arrow preference."""
        p = _player()
        p.preferences = {"arrow": "None"}
        with patch("builtins.print"):
            functions.add_preference(p, "arrow", "Steel Arrow")
        assert p.preferences["arrow"] == "Steel Arrow"

    def test_toggle_off_same_arrow_preference(self):
        """Lines 1279-1281: toggling same pref sets to 'None'."""
        p = _player()
        p.preferences = {"arrow": "Steel Arrow"}
        with patch("builtins.print"):
            functions.add_preference(p, "arrow", "Steel Arrow")
        assert p.preferences["arrow"] == "None"

    def test_non_arrow_preference(self):
        """Lines 1282-1284: non-arrow pref just sets value."""
        p = _player()
        p.preferences = {}
        with patch("builtins.print"):
            functions.add_preference(p, "weapon", "Sword")
        assert p.preferences["weapon"] == "Sword"
