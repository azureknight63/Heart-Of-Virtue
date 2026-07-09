"""Tests for staged-conversation segment building (event dialogue portraits).

Covers:
- narration.say / begin_conversation / enter_character / exit_character emit
  correctly-shaped structured entries
- GameService._capture_conversation turns those entries into segments + a
  conversation roster, preserves output_text, and leaves untagged events alone
- party-rule side resolution (Jean / party -> left, others -> right)
- the Ch01 Amelia memory canary produces the expected staged conversation
"""

import pytest
from unittest.mock import patch


@pytest.fixture
def game_service():
    from src.api.services.game_service import GameService

    return GameService()


class FakePlayer:
    """Minimal player stand-in for side resolution."""

    def __init__(self, name="Jean", allies=None):
        self.name = name
        # combat_list_allies normally includes the player at index 0
        self.combat_list_allies = allies if allies is not None else []


# --------------------------------------------------------------------------- #
# narration authoring helpers
# --------------------------------------------------------------------------- #


def test_say_emits_dialogue_entry_with_normalized_emotion():
    from src.narration import capture_narration, say

    with capture_narration() as msgs:
        say("Hello there.", "Jean", "FURIOUS")  # unknown emotion -> neutral

    assert len(msgs) == 1
    entry = msgs[0]
    assert entry["type"] == "dialogue"
    assert entry["speaker"] == "Jean"
    assert entry["emotion"] == "neutral"
    assert entry["text"] == "Hello there."


def test_say_carries_reactions_and_exit_ops():
    from src.narration import capture_narration, say

    with capture_narration() as msgs:
        say(
            "...but some...",
            "Jean",
            "sad",
            reactions={"Amelia": "SAD"},
            leave={"id": "Amelia", "transition": "fade", "span": 3},
        )

    entry = msgs[0]
    assert entry["reactions"] == {"Amelia": "sad"}
    assert entry["exit"] == [{"id": "Amelia", "transition": "fade", "span": 3}]


def test_say_thought_flag_defaults_false_and_can_be_set():
    from src.narration import capture_narration, say

    with capture_narration() as msgs:
        say("You worry too much, dear.", "Jean", "happy")
        say("He'd expected a rumble. Not that.", "Jean", "surprised", thought=True)

    spoken, thought = msgs
    assert "thought" not in spoken
    assert thought["thought"] is True


def test_stage_control_helpers_emit_control_entries():
    from src.narration import (
        capture_narration,
        begin_conversation,
        enter_character,
        exit_character,
        end_conversation,
    )

    with capture_narration() as msgs:
        begin_conversation([("Jean", "left", "neutral")])
        enter_character("Mara", side=None, emotion="happy")
        exit_character("Mara", span=2)
        end_conversation()

    types = [m.get("type") for m in msgs]
    assert types == [
        "conversation_begin",
        "stage_enter",
        "stage_exit",
        "conversation_end",
    ]
    assert msgs[0]["cast"][0]["id"] == "Jean"
    assert msgs[2]["span"] == 2


# --------------------------------------------------------------------------- #
# GameService._capture_conversation
# --------------------------------------------------------------------------- #


def test_untagged_messages_yield_no_segments(game_service):
    msgs = [
        {"text": "A plain line.", "type": "narration"},
        {"text": "Another plain line.", "type": "narration"},
    ]
    out, segments, conversation = game_service._capture_conversation(msgs, FakePlayer())
    assert conversation is None
    assert segments == []
    assert out == "A plain line.\nAnother plain line."


def test_capture_builds_conversation_and_segments(game_service):
    from src.narration import (
        capture_narration,
        begin_conversation,
        say,
        narrate,
    )

    with capture_narration() as msgs:
        begin_conversation([("Jean", "left", "neutral"), ("Amelia", "right", "happy")])
        narrate("A woman's voice, soft and warm.")
        say(
            "You always were too stubborn.",
            "Amelia",
            "happy",
            reactions={"Jean": "happy"},
        )
        say(
            "...but some...",
            "Jean",
            "sad",
            leave={"id": "Amelia", "transition": "fade", "span": 3},
        )

    out, segments, conversation = game_service._capture_conversation(msgs, FakePlayer())

    # Roster with resolved sides
    assert conversation is not None
    cast = {c["id"]: c for c in conversation["cast"]}
    assert cast["Jean"]["side"] == "left"
    assert cast["Amelia"]["side"] == "right"

    # Three text beats (the begin op is a control entry, not a segment)
    assert len(segments) == 3
    assert all(s["in_conversation"] for s in segments)

    narration_beat, amelia_beat, jean_beat = segments
    assert "speaker" not in narration_beat  # plain narration
    assert amelia_beat["speaker"] == "Amelia"
    assert amelia_beat["emotion"] == "happy"
    assert amelia_beat["reactions"] == {"Jean": "happy"}
    assert jean_beat["speaker"] == "Jean"
    assert jean_beat["exit"] == [{"id": "Amelia", "transition": "fade", "span": 3}]

    # output_text still flattens every spoken/narrated line
    assert "A woman's voice, soft and warm." in out
    assert "...but some..." in out


def test_side_resolution_party_vs_stranger(game_service):
    class Ally:
        name = "Gorran"

    player = FakePlayer(name="Jean", allies=[Ally()])

    assert game_service._resolve_conversation_side("Jean", player) == "left"
    assert game_service._resolve_conversation_side("Gorran", player) == "left"
    assert game_service._resolve_conversation_side("Amelia", player) == "right"
    # No char -> right (defensive default)
    assert game_service._resolve_conversation_side(None, player) == "right"


def test_explicit_side_overrides_party_rule(game_service):
    from src.narration import capture_narration, begin_conversation

    # A stranger explicitly placed on the left should stay left.
    with capture_narration() as msgs:
        begin_conversation([("Stranger", "left", "neutral")])

    _out, _segs, conversation = game_service._capture_conversation(msgs, FakePlayer())
    assert conversation["cast"][0]["side"] == "left"


def test_capture_propagates_thought_flag_onto_segment(game_service):
    from src.narration import capture_narration, say

    with capture_narration() as msgs:
        say("Not now. Keep moving.", "Jean", "neutral")
        say("He'd expected a rumble. Not that.", "Jean", "surprised", thought=True)

    _out, segments, _conv = game_service._capture_conversation(msgs, FakePlayer())
    spoken, thought = segments
    assert "thought" not in spoken
    assert thought["thought"] is True


def test_trailing_stage_op_attaches_to_last_segment(game_service):
    from src.narration import capture_narration, say, exit_character

    with capture_narration() as msgs:
        say("Farewell.", "Jean", "sad")
        exit_character("Amelia", transition="instant")

    _out, segments, _conv = game_service._capture_conversation(msgs, FakePlayer())
    assert len(segments) == 1
    assert segments[-1]["exit"] == [{"id": "Amelia", "transition": "instant"}]


# --------------------------------------------------------------------------- #
# Canary: Ch01 Amelia memory
# --------------------------------------------------------------------------- #


def test_ch01_amelia_memory_produces_staged_conversation(game_service):
    from src.narration import capture_narration
    from src.story.ch01 import Ch01_Memory_Amelia

    player = FakePlayer(name="Jean")
    event = Ch01_Memory_Amelia(player=player, tile=None)

    with (
        patch("src.animations.animate_to_main_screen", return_value=None),
        patch("time.sleep", return_value=None),
    ):
        with capture_narration() as msgs:
            event.process()

    out, segments, conversation = game_service._capture_conversation(msgs, player)

    # Cast: Jean left, Amelia right
    cast = {c["id"]: c for c in conversation["cast"]}
    assert cast["Jean"]["side"] == "left"
    assert cast["Amelia"]["side"] == "right"

    # Amelia speaks the plea; Jean delivers the dismissal.
    by_text = {s["text"]: s for s in segments if s.get("speaker")}
    plea = next(s for t, s in by_text.items() if "Promise me" in t)
    dismiss = next(s for t, s in by_text.items() if "worry too much" in t)
    assert plea["speaker"] == "Amelia"
    assert dismiss["speaker"] == "Jean"

    # Amelia fades out (exit op) somewhere in the memory.
    exits = [op for s in segments for op in s.get("exit", [])]
    assert any(op["id"] == "Amelia" and op.get("span") == 3 for op in exits)

    # The event still pauses for the player's "Continue".
    assert event.needs_input is True

    # Memory Flash flair: event advertises its presentation, and the ASCII
    # border chrome is dropped from segments + output_text (the client renders
    # its own flair instead).
    assert event.presentation == "memory_flash"
    all_text = "\n".join(s["text"] for s in segments) + "\n" + out
    assert "MEMORY STIRS" not in all_text
    assert "THE MEMORY FADES" not in all_text
    assert "═" not in all_text


def test_after_the_rumbler_fight_defers_gorrans_name_until_the_reveal(game_service):
    """Canary: the naming scene doesn't leak 'Gorran' onto the portrait before
    the in-fiction reveal (his first spoken line is the reveal itself)."""
    from unittest.mock import Mock
    from src.narration import capture_narration
    from src.story.ch01 import AfterTheRumblerFight

    player = FakePlayer(name="Jean")
    player.in_combat = False
    player.combat_list_allies = []
    tile = Mock()
    tile.npcs_here = []
    event = AfterTheRumblerFight(player=player, tile=tile, params=None)

    with patch("time.sleep", return_value=None):
        with capture_narration() as msgs:
            event.process()

    out, segments, conversation = game_service._capture_conversation(msgs, player)

    cast = {c["id"]: c for c in conversation["cast"]}
    assert "Rock-Man" in cast
    assert "Gorran" not in cast  # not in the initial roster — enters mid-scene

    reveal_beat = next(s for s in segments if s.get("speaker") == "Gorran")
    assert "Go-rra-nnnnnn" in reveal_beat["text"]
    assert any(op["id"] == "Gorran" for op in reveal_beat.get("enter", []))
    assert any(op["id"] == "Rock-Man" for op in reveal_beat.get("exit", []))

    # No earlier beat is attributed to "Gorran" before the reveal.
    reveal_index = segments.index(reveal_beat)
    assert all(s.get("speaker") != "Gorran" for s in segments[:reveal_index])


def test_ch02_guide_to_citadel_stage4_produces_staged_conversation(game_service):
    """Canary: the Votha Krr introduction (Pattern C -> say()/narrate() rollout)
    builds a real staged conversation, not just a legacy description string."""
    from unittest.mock import Mock
    from src.narration import capture_narration
    from src.story.ch02 import Ch02GuideToCitadel

    class Ally:
        name = "Gorran"

    player = FakePlayer(name="Jean", allies=[Ally()])
    player.skip_dialog = False
    player.combat_list = []
    tile = Mock()
    tile.remove_event = Mock()
    event = Ch02GuideToCitadel(player=player, tile=tile, params=None)

    with capture_narration() as msgs:
        for _ in range(4):  # advance to stage 4 (Votha Krr's introduction)
            event.process()

    out, segments, conversation = game_service._capture_conversation(msgs, player)

    cast = {c["id"]: c for c in conversation["cast"]}
    assert cast["Jean"]["side"] == "left"
    assert cast["Gorran"]["side"] == "left"  # ally -> party-rule left

    # The elder is unnamed ("Elder") until his self-introduction beat, matching
    # the reveal the legacy description text preserves ("Elder: ..." then
    # "Votha Krr: ...") — his name shouldn't leak onto the portrait label early.
    elder_beats = [s for s in segments if s.get("speaker") == "Elder"]
    assert any("welcome here" in s["text"].lower() for s in elder_beats)
    votha_beats = [s for s in segments if s.get("speaker") == "Votha Krr"]
    assert any("i am elder votha krr" in s["text"].lower() for s in votha_beats)

    # The self-introduction beat swaps "Elder" out for "Votha Krr".
    reveal_beat = next(s for s in votha_beats if "i am elder votha krr" in s["text"].lower())
    assert any(op["id"] == "Votha Krr" for op in reveal_beat.get("enter", []))
    assert any(op["id"] == "Elder" for op in reveal_beat.get("exit", []))

    # Gorran leaves partway through the scene, fading out over more than one beat.
    exits = [op for s in segments for op in s.get("exit", [])]
    gorran_exit = next(op for op in exits if op["id"] == "Gorran")
    assert gorran_exit.get("span", 1) > 1


def test_ch02_king_slime_memory_flash_produces_thought_segments(game_service):
    """Canary: the King Slime flashback tags Jean's introspective beats as
    internal thoughts (no other character on stage — a solo memory)."""
    from unittest.mock import Mock, patch
    from src.narration import capture_narration
    from src.story.ch02 import Ch02KingSlimeMemoryFlash

    player = FakePlayer(name="Jean")
    player.universe = Mock()
    player.universe.story = {}
    tile = Mock()
    tile.events_here = []
    event = Ch02KingSlimeMemoryFlash(player=player, tile=tile)

    with (
        patch("src.animations.animate_to_main_screen", return_value=None),
        patch("time.sleep", return_value=None),
    ):
        with capture_narration() as msgs:
            event.process()

    out, segments, conversation = game_service._capture_conversation(msgs, player)

    cast = {c["id"]: c for c in conversation["cast"]}
    assert list(cast.keys()) == ["Jean"]

    thought_beats = [s for s in segments if s.get("thought")]
    assert any("Pain" in s["text"] for s in thought_beats)
    assert any("emptiness" in s["text"] for s in thought_beats)
    assert all(s["speaker"] == "Jean" for s in thought_beats)
    # No reactions are authored on a solo memory (no one else on stage).
    assert all("reactions" not in s for s in thought_beats)


def test_after_king_slime_return_stage1_produces_staged_conversation(game_service):
    """Canary: Votha Krr's fragment-acceptance scene (Pattern C -> say()/narrate()
    rollout) builds a staged conversation on stage 1."""
    from unittest.mock import Mock
    from src.narration import capture_narration
    from src.story.ch02 import AfterKingSlimeReturn

    player = FakePlayer(name="Jean")
    player.universe = Mock()
    player.universe.story = {"king_slime_defeated": "1"}
    fragment = Mock()
    fragment.__class__.__name__ = "MineralFragment"
    player.inventory = [fragment]
    tile = Mock()
    event = AfterKingSlimeReturn(player=player, tile=tile)

    with capture_narration() as msgs:
        event.process()

    out, segments, conversation = game_service._capture_conversation(msgs, player)

    cast = {c["id"]: c for c in conversation["cast"]}
    assert cast["Jean"]["side"] == "left"
    assert cast["Votha Krr"]["side"] == "right"

    by_speaker = [s for s in segments if s.get("speaker") == "Votha Krr"]
    assert any("done well" in s["text"].lower() for s in by_speaker)


def test_memory_chrome_entries_are_dropped(game_service):
    msgs = [
        {"text": "════", "type": "memory_chrome"},
        {"text": "✧ A MEMORY STIRS ✧", "type": "memory_chrome"},
        {
            "text": "A real spoken line.",
            "type": "dialogue",
            "speaker": "Jean",
            "emotion": "sad",
        },
        {"text": "════", "type": "memory_chrome"},
    ]
    out, segments, _conv = game_service._capture_conversation(msgs, FakePlayer())
    assert len(segments) == 1
    assert segments[0]["text"] == "A real spoken line."
    assert "MEMORY STIRS" not in out
    assert "═" not in out
    assert "A real spoken line." in out
