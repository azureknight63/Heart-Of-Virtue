"""
Additional coverage for src/npc/_friends.py — Gorran.talk() branches.

Targets uncovered lines 199-283 (gorran_first and gorran_language_stage paths).
"""

import sys
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
import pytest

if "tkinter" not in sys.modules:
    sys.modules["tkinter"] = MagicMock()
    sys.modules["tkinter.ttk"] = MagicMock()
    sys.modules["tkinter.font"] = MagicMock()

src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


def _make_room(story=None):
    """Mock room with universe.story attached."""
    if story is None:
        story = {"gorran_first": "0", "gorran_language_stage": "0"}
    room = Mock()
    room.universe = Mock()
    room.universe.story = story
    room.events_here = []
    return room


def _make_player():
    p = Mock()
    p.universe = Mock()
    p.universe.story = {}
    return p


class TestGorranTalk:
    def _make_gorran(self, story=None):
        from src.npc._friends import Gorran

        g = Gorran()
        g.current_room = _make_room(story)
        return g

    def test_gorran_first_talk_triggers_intro_event(self):
        """gorran_first == '0': appends AfterGorranIntro event and sets flag."""
        gorran = self._make_gorran({"gorran_first": "0", "gorran_language_stage": "0"})
        player = _make_player()

        with patch("builtins.print"), patch("src.npc._friends.functions") as mock_funcs:
            mock_event_cls = Mock(return_value=Mock())
            mock_funcs.seek_class = Mock(return_value=mock_event_cls)
            gorran.talk(player)

        assert gorran.current_room.universe.story["gorran_first"] == "1"
        assert len(gorran.current_room.events_here) > 0

    def test_gorran_first_talk_returns_early(self):
        """gorran_first == '0': should return after setting flag (no stage logic)."""
        gorran = self._make_gorran({"gorran_first": "0", "gorran_language_stage": "0"})
        player = _make_player()

        with patch("builtins.print"), patch("src.npc._friends.functions") as mock_funcs:
            mock_funcs.seek_class = Mock(return_value=Mock(return_value=Mock()))
            gorran.talk(player)

        # gorran_language_stage should not have changed
        assert gorran.current_room.universe.story.get("gorran_language_stage") == "0"

    def test_gorran_talk_stage0_prints_gesture_response(self, capsys):
        """gorran_first == '1', stage 0: prints gesture response."""
        gorran = self._make_gorran({"gorran_first": "1", "gorran_language_stage": "0"})
        player = _make_player()
        gorran.talk(player)
        out = capsys.readouterr().out
        assert len(out) > 0

    def test_gorran_talk_stage1_prints_silence_response(self, capsys):
        """Stage 1: prints 'silence has different texture' response."""
        gorran = self._make_gorran({"gorran_first": "1", "gorran_language_stage": "1"})
        player = _make_player()
        gorran.talk(player)
        out = capsys.readouterr().out
        assert len(out) > 0

    def test_gorran_talk_stage2_prints_word_response(self, capsys):
        """Stage 2: prints single-word response."""
        gorran = self._make_gorran({"gorran_first": "1", "gorran_language_stage": "2"})
        player = _make_player()
        gorran.talk(player)
        out = capsys.readouterr().out
        assert len(out) > 0

    def test_gorran_talk_stage3_prints_phrase_response(self, capsys):
        """Stage 3+: prints short-phrase response."""
        gorran = self._make_gorran({"gorran_first": "1", "gorran_language_stage": "3"})
        player = _make_player()
        gorran.talk(player)
        out = capsys.readouterr().out
        assert len(out) > 0

    def test_gorran_talk_stage4_prints_phrase_response(self, capsys):
        """Stage 4: same else branch as stage 3."""
        gorran = self._make_gorran({"gorran_first": "1", "gorran_language_stage": "4"})
        player = _make_player()
        gorran.talk(player)
        out = capsys.readouterr().out
        assert len(out) > 0

    def test_gorran_name_property_returns_rock_man_before_intro(self):
        """Before gorran_first is set, name is 'Rock-Man'."""
        from src.npc._friends import Gorran

        g = Gorran()
        g.current_room = _make_room({"gorran_first": "0", "gorran_language_stage": "0"})
        assert g.name == "Rock-Man"

    def test_gorran_name_property_returns_gorran_after_intro(self):
        """After gorran_first == '1', name is 'Gorran'."""
        from src.npc._friends import Gorran

        g = Gorran()
        g.current_room = _make_room({"gorran_first": "1", "gorran_language_stage": "0"})
        assert g.name == "Gorran"

    def test_gorran_name_property_uses_player_ref_when_no_current_room(self):
        """Falls back to player_ref.universe.story if current_room is None."""
        from src.npc._friends import Gorran

        g = Gorran()
        g.current_room = None
        p = Mock()
        p.universe = Mock()
        p.universe.story = {"gorran_first": "1"}
        g.player_ref = p
        assert g.name == "Gorran"

    def test_gorran_name_returns_rock_man_when_no_story_context(self):
        """Without story context, name falls back to stored _name."""
        from src.npc._friends import Gorran

        g = Gorran()
        g.current_room = None
        if hasattr(g, "player_ref"):
            del g.player_ref
        assert g.name == "Rock-Man"

    def test_gorran_wounded_flavor_returns_string(self):
        """wounded_flavor() returns a non-empty string."""
        from src.npc._friends import Gorran

        g = Gorran()
        g.current_room = None
        if hasattr(g, "player_ref"):
            del g.player_ref
        result = g.wounded_flavor()
        assert isinstance(result, str)
        assert len(result) > 0
