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
