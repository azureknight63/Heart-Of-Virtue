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


def test_react_emits_stage_react_control_entry():
    from src.narration import capture_narration, react

    with capture_narration() as msgs:
        react("Amelia", "SAD")  # unknown-case emotion -> normalized

    assert len(msgs) == 1
    assert msgs[0] == {"type": "stage_react", "reactions": {"Amelia": "sad"}}


def test_react_accepts_a_reactions_dict_for_multiple_characters():
    from src.narration import capture_narration, react

    with capture_narration() as msgs:
        react(reactions={"Amelia": "happy", "Gorran": "skeptical"})

    assert msgs[0]["reactions"] == {"Amelia": "happy", "Gorran": "skeptical"}


def test_react_requires_speaker_or_reactions():
    from src.narration import react

    with pytest.raises(ValueError):
        react()


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


def test_conversation_carries_the_first_roster_not_the_last(game_service):
    """A capture with several begin_conversation() calls reports the FIRST cast.

    ConversationStage seeds every member of ``conversation.cast`` with
    enteredAt = -1 (on stage from beat 0), so a later roster here would put
    characters on screen before the prose introduces them and would make the
    enter op emitted for them a no-op.
    """
    from src.narration import capture_narration, begin_conversation, say

    with capture_narration() as msgs:
        begin_conversation([("Jean", "left", "neutral"), ("Mara", "right", "neutral")])
        say("Crossing west?", "Mara", "neutral")
        begin_conversation(
            [
                ("Jean", "left", "neutral"),
                ("Mara", "right", "curious"),
                ("Gorran", "left", "neutral"),
            ]
        )
        say("Never had one this close.", "Mara", "curious")

    _out, segments, conversation = game_service._capture_conversation(
        msgs, FakePlayer()
    )

    assert [c["id"] for c in conversation["cast"]] == ["Jean", "Mara"]
    # Gorran is still fully represented — just via an enter op on the beat that
    # follows the second begin_conversation, not by being on stage from beat 0.
    entered = [op["id"] for s in segments for op in s.get("enter", [])]
    assert entered == ["Gorran"]
    assert segments[1]["enter"][0]["id"] == "Gorran"


def test_sequential_begins_diff_against_the_previous_roster(game_service):
    """Enter/exit ops diff against the immediately-preceding cast.

    Regression guard for the first-roster fix: diffing against the retained
    FIRST cast instead would miss the departure of a character who joined in an
    intermediate begin_conversation (the Liss beat in IronAndOathIntro).
    """
    from src.narration import capture_narration, begin_conversation, say

    with capture_narration() as msgs:
        begin_conversation([("Jean", "left", "neutral"), ("Kaelen", "right", "neutral")])
        say("Welcome to Iron & Oath.", "Kaelen", "happy")
        begin_conversation(
            [
                ("Jean", "left", "neutral"),
                ("Kaelen", "right", "neutral"),
                ("Liss", "right", "surprised"),
            ]
        )
        say("Eek!", "Liss", "surprised")
        begin_conversation([("Jean", "left", "neutral"), ("Kaelen", "right", "neutral")])
        say("That girl's got more nerve than sense.", "Kaelen", "happy")

    _out, segments, conversation = game_service._capture_conversation(
        msgs, FakePlayer()
    )

    assert [c["id"] for c in conversation["cast"]] == ["Jean", "Kaelen"]
    entered = [op["id"] for s in segments for op in s.get("enter", [])]
    exited = [op["id"] for s in segments for op in s.get("exit", [])]
    assert entered == ["Liss"]
    assert exited == ["Liss"]


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


def test_react_attaches_to_the_next_beat(game_service):
    from src.narration import capture_narration, narrate, react

    with capture_narration() as msgs:
        react("Amelia", "sad")
        narrate("She looks away.")

    _out, segments, _conv = game_service._capture_conversation(msgs, FakePlayer())
    assert len(segments) == 1
    assert segments[0]["reactions"] == {"Amelia": "sad"}
    assert segments[0]["text"] == "She looks away."
    assert "speaker" not in segments[0]


def test_react_merges_with_a_speaker_beats_own_reactions(game_service):
    from src.narration import capture_narration, react, say

    with capture_narration() as msgs:
        react("Gorran", "skeptical")
        say("It'll be fine.", "Jean", "neutral", reactions={"Amelia": "sad"})

    _out, segments, _conv = game_service._capture_conversation(msgs, FakePlayer())
    assert len(segments) == 1
    assert segments[0]["reactions"] == {"Gorran": "skeptical", "Amelia": "sad"}


def test_trailing_react_with_no_following_beat_attaches_to_last_segment(game_service):
    from src.narration import capture_narration, say, react

    with capture_narration() as msgs:
        say("Farewell.", "Jean", "sad")
        react("Amelia", "sad")

    _out, segments, _conv = game_service._capture_conversation(msgs, FakePlayer())
    assert len(segments) == 1
    assert segments[-1]["reactions"] == {"Amelia": "sad"}


def test_react_alone_produces_a_no_text_no_speaker_segment(game_service):
    from src.narration import capture_narration, react

    with capture_narration() as msgs:
        react("Amelia", "sad")

    _out, segments, _conv = game_service._capture_conversation(msgs, FakePlayer())
    assert len(segments) == 1
    assert segments[0]["text"] == ""
    assert "speaker" not in segments[0]
    assert segments[0]["reactions"] == {"Amelia": "sad"}


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


# --------------------------------------------------------------------------- #
# Pending-event recovery (GET /world/events/pending)
# --------------------------------------------------------------------------- #


def _staged_pending_player():
    """A Ch02GuideToCitadel-ready player stand-in with a live universe mock."""
    from unittest.mock import Mock

    player = FakePlayer(name="Jean")
    player.skip_dialog = False
    player.universe = Mock()
    player.universe.story = {}
    player.location_x = 0
    player.location_y = 0
    player.current_room = None
    player.in_combat = False
    player.pending_attribute_points = 0
    return player


def test_pending_event_data_carries_the_current_stages_segments(game_service):
    """A mid-conversation stage is recoverable from session pending_events.

    GET /world/events/pending replays ``event_data`` verbatim, so it must hold
    THIS stage's staged payload. Without it the client falls back to the event's
    ``description`` attribute — which Ch02GuideToCitadel stops updating after
    stage 2 — re-rendering stale prose whose Continue button then skips a stage.
    """
    from unittest.mock import Mock, patch
    from src.story.ch02 import Ch02GuideToCitadel

    player = _staged_pending_player()
    tile = Mock()
    event = Ch02GuideToCitadel(player=player, tile=tile, params=None)
    # Enter at stage 3: the first stage that narrates instead of assigning
    # self.description, with stage 2's prose left stale on the attribute.
    event._stage = 3
    stale_description = "Jean stepped through. The cavern beyond was vast"
    event.description = stale_description

    session_data = {
        "pending_events": {"evt-stage-3": {"event": event, "event_data": {}}}
    }

    with patch(
        "src.api.services.game_service.check_for_combat", return_value=[]
    ):
        result = game_service.process_event_input(
            player, "evt-stage-3", "continue", session_data
        )

    assert result["needs_input"] is True
    assert event._stage == 4  # the stage the player is now waiting on

    # world.py's GET /world/events/pending replays this dict verbatim.
    stored = session_data["pending_events"]
    assert len(stored) == 1
    pending = next(iter(stored.values()))["event_data"]
    assert pending["segments"] == result["segments"]
    assert pending["conversation"] == result["conversation"]
    assert pending["output_text"] == result["output_text"]

    # Recovered prose is stage 3's, not the stale stage-2 description.
    assert stale_description not in pending["output_text"]
    assert "Gorran turned to Jean" in pending["output_text"]
    assert any(s.get("speaker") == "Jean" for s in pending["segments"])


def test_unstaged_pending_event_data_gains_no_empty_keys(game_service):
    """An event that emits nothing keeps its pre-staging payload shape."""
    from unittest.mock import MagicMock, patch

    player = _staged_pending_player()
    event = MagicMock(spec=["process", "completed", "needs_input", "player", "tile"])
    event.completed = False
    event.needs_input = True
    event.process = lambda user_input=None: None
    session_data = {
        "pending_events": {"evt-1": {"event": event, "event_data": {}}}
    }

    with patch(
        "src.api.services.game_service.check_for_combat", return_value=[]
    ):
        game_service.process_event_input(player, "evt-1", "yes", session_data)

    stored = next(iter(session_data["pending_events"].values()))["event_data"]
    assert "segments" not in stored
    assert "conversation" not in stored
    assert "output_text" not in stored


# --------------------------------------------------------------------------- #
# Long-narration pacing (issue #123 "Break up event text")
# --------------------------------------------------------------------------- #


def test_short_plain_narration_stays_unchunked(game_service):
    """A short, unstaged text block yields no segments — unaffected by chunking."""
    msgs = [
        {"text": "You step into the chamber.", "type": "narration"},
        {"text": "Dust motes drift in the light.", "type": "narration"},
    ]
    out, segments, conversation = game_service._capture_conversation(msgs, FakePlayer())
    assert conversation is None
    assert segments == []
    assert out == "You step into the chamber.\nDust motes drift in the light."


def test_long_plain_narration_is_split_into_paced_segments(game_service):
    """A long, unstaged text block is chunked into click-to-continue beats."""
    paragraphs = [
        "The vault door groans open, revealing a chamber untouched for centuries. "
        "Dust hangs thick in the stale air, and the only sound is Jean's own breathing.",
        "Along the walls, faded murals depict a war long since forgotten — armies "
        "of stone and fire clashing beneath a sky the color of an old bruise.",
        "At the center of the room, a plinth holds a single artifact, humming "
        "faintly with a light that seems to pulse in time with Jean's heartbeat.",
    ]
    long_text = "\n\n".join(paragraphs)
    msgs = [{"text": long_text, "type": "narration"}]

    out, segments, conversation = game_service._capture_conversation(msgs, FakePlayer())

    assert conversation is None
    assert out == long_text
    assert len(segments) > 1
    # Every paced beat is plain narration — no speaker, not "in conversation".
    max_chars = game_service._NARRATION_CHUNK_MAX_CHARS
    for seg in segments:
        assert "speaker" not in seg
        assert seg["in_conversation"] is False
        assert len(seg["text"]) <= max_chars
    # Reassembling the beats loses no content — every paragraph survives intact
    # somewhere in the paced text.
    reassembled = "\n\n".join(seg["text"] for seg in segments)
    for para in paragraphs:
        assert para in reassembled


def test_chunking_does_not_affect_staged_dialogue(game_service):
    """A conversation that happens to be long is left to the existing
    per-beat (say()) pacing — the plain-text chunker never runs when the
    event already used a staged feature."""
    from src.narration import capture_narration, begin_conversation, say

    long_line = "This line is long enough that, in isolation, it would exceed " \
        "the plain-narration chunk threshold if the chunker ran on it, but it " \
        "must not be split because the event is already staged via say()." * 3

    with capture_narration() as msgs:
        begin_conversation([("Jean", "left", "neutral")])
        say(long_line, "Jean", "neutral")

    out, segments, conversation = game_service._capture_conversation(msgs, FakePlayer())

    assert conversation is not None
    assert len(segments) == 1
    assert segments[0]["text"] == long_line
    assert segments[0]["speaker"] == "Jean"
    assert segments[0]["in_conversation"] is True


class TestChunkNarrationText:
    """Direct unit tests for GameService._chunk_narration_text."""

    def test_empty_text_returns_no_chunks(self, game_service):
        assert game_service._chunk_narration_text("") == []
        assert game_service._chunk_narration_text("   ") == []

    def test_short_text_returns_single_chunk_unchanged(self, game_service):
        text = "A short sentence."
        assert game_service._chunk_narration_text(text) == [text]

    def test_long_text_splits_at_paragraph_boundaries(self, game_service):
        para_a = "A" * 200
        para_b = "B" * 200
        para_c = "C" * 200
        text = f"{para_a}\n\n{para_b}\n\n{para_c}"
        chunks = game_service._chunk_narration_text(text, max_chars=250)
        assert len(chunks) >= 2
        assert all(len(c) <= 250 for c in chunks)
        # No content lost.
        assert "".join(chunks).replace("\n\n", "") == para_a + para_b + para_c

    def test_oversized_single_sentence_is_kept_intact(self, game_service):
        # A single sentence longer than max_chars can't be split further —
        # pacing is best-effort, never a mid-word truncation.
        text = "A" * 500 + "."
        chunks = game_service._chunk_narration_text(text, max_chars=100)
        assert chunks == [text]

    def test_respects_custom_max_chars(self, game_service):
        text = " ".join(f"Sentence number {i}." for i in range(30))
        chunks = game_service._chunk_narration_text(text, max_chars=80)
        assert len(chunks) > 1
        assert all(len(c) <= 80 or " " not in c for c in chunks)

    def test_single_newline_joined_messages_split_at_the_newline(self, game_service):
        """Regression: _capture_conversation joins separate narrate()/cprint()
        calls with a single "\\n" (not "\\n\\n"), and lines commonly end
        without terminal [.!?] punctuation (mid-thought, ellipses, em dashes).
        The chunker must treat those single-newline boundaries as break
        points rather than relying solely on sentence-ending punctuation —
        otherwise several such lines glue into one oversized chunk."""
        lines = [
            "Jean steps into the ruined hall",
            "Something stirs in the dark, low and guttural",
            "The torches gutter as if breathing",
            'A voice, ancient and hollow, calls out from the shadows: "Who dares?"',
        ]
        text = "\n".join(lines)
        chunks = game_service._chunk_narration_text(text, max_chars=80)
        assert len(chunks) > 1
        assert all(len(c) <= 80 for c in chunks)
        # No line's words are lost or reordered.
        reassembled = " ".join(chunks)
        for line in lines:
            assert line in reassembled.replace("\n\n", " ")


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


# --------------------------------------------------------------------------- #
# Multi-stage staged events: one fresh, complete payload PER stage
# --------------------------------------------------------------------------- #
# The client mounts a single ConversationStage instance and re-feeds it the
# `segments` array of every stage of the same event. A stage that returned a
# truncated array, repeated the previous stage's beats, or omitted its roster
# would strand the player (CLAUDE.md: "ConversationStage reset trap"). These
# tests pin the payload contract from the backend side: each round-trip must
# hand back THIS stage's beats and nothing else, and every stage must be
# advanceable.


def _guide_to_citadel_player():
    """A player stand-in wired for a full Ch02GuideToCitadel play-through."""
    from unittest.mock import Mock

    class Ally:
        name = "Gorran"

    player = FakePlayer(name="Jean", allies=[Ally()])
    player.skip_dialog = False
    player.combat_list = []
    player.inventory = []
    player.location_x = 0
    player.location_y = 0
    player.current_room = None
    player.in_combat = False
    player.pending_attribute_points = 0
    player.teleported = None
    player.universe = Mock()
    player.universe.story = {}
    # The completion path calls trigger_tile_events on the destination tile.
    dest_tile = Mock()
    dest_tile.x, dest_tile.y = 0, 0
    dest_tile.events_here = []
    dest_tile.npcs_here = []
    player.universe.get_tile.return_value = dest_tile
    player.tile = dest_tile
    player.add_items_to_inventory = player.inventory.extend
    player.teleport = lambda m, coords: setattr(player, "teleported", (m, coords))
    return player


def _play_staged_event(game_service, player, event, answers):
    """Drive `event` to completion through process_event_input; return per-stage results.

    ``answers`` supplies the input for each round-trip; the last answer repeats
    if the event needs more. Mirrors what the client does: read the re-minted
    ``event_id`` out of each response and send it back on the next call.
    """
    from unittest.mock import patch

    session_data = {"pending_events": {"evt-0": {"event": event, "event_data": {}}}}
    event_id = "evt-0"
    results = []
    with patch("src.api.services.game_service.check_for_combat", return_value=[]):
        for i in range(20):
            answer = answers[i] if i < len(answers) else answers[-1]
            result = game_service.process_event_input(
                player, event_id, answer, session_data
            )
            assert result["success"] is True, result.get("error")
            results.append(result)
            if not result.get("needs_input"):
                break
            event_id = result["event"]["event_id"]
        else:  # pragma: no cover - only on a runaway stage machine
            raise AssertionError("event never completed within 20 stages")
    return results, session_data


def test_guide_to_citadel_hands_every_stage_a_fresh_complete_payload(game_service):
    from src.story.ch02 import Ch02GuideToCitadel

    player = _guide_to_citadel_player()
    event = Ch02GuideToCitadel(player=player, tile=player.tile, params=None)

    results, session_data = _play_staged_event(
        game_service, player, event, ["continue"]
    )

    # Eight authored stages; the eighth is the cleanup stage that completes.
    assert len(results) == 8
    assert [r.get("needs_input") for r in results] == [True] * 7 + [False]
    assert event.completed is True
    assert session_data["pending_events"] == {}

    # Stages 1-2 are legacy description-driven; 3-7 are staged; 8 is silent cleanup.
    staged = results[2:-1]
    assert len(staged) == 5
    assert not results[-1].get("segments")
    assert all(r.get("segments") for r in staged)
    assert all(r.get("conversation") for r in staged)

    # THE soft-lock guard. Each stage must hand back a COMPLETE array that
    # starts at its own first beat — never an accumulation of what came before,
    # and never a repeat of the previous stage. A component that carries its
    # beat index across stages then has no way to appear correct by accident.
    # (Beats may legitimately recur across stages — Votha Krr's "He watched
    # Jean's face" line does — so this compares arrays, not the text pool.)
    stage_beats = [[s["text"] for s in r["segments"]] for r in staged]
    for i, texts in enumerate(stage_beats):
        assert texts, f"staged round-trip {i} returned an empty segments array"
    for i, (prev, cur) in enumerate(zip(stage_beats, stage_beats[1:])):
        assert cur[0] != prev[0], f"stage {i + 1} re-opened on stage {i}'s first beat"
        assert cur != prev, f"stage {i + 1} replayed stage {i} verbatim"
        assert cur[: len(prev)] != prev, (
            f"stage {i + 1} appended to stage {i}'s beats instead of replacing them"
        )

    # Every stage but the last is advanceable — a terminal beat with no option
    # is the soft-lock itself.
    for r in results[:-1]:
        assert r["event"]["input_options"], "a stage offered no way to continue"
    assert [o["value"] for o in results[-2]["event"]["input_options"]] == ["done"]

    # Stage content lands where the scene says it does.
    assert any(
        s.get("speaker") == "Votha Krr" and "I am Elder Votha Krr" in s["text"]
        for s in staged[1]["segments"]
    )
    assert [o["value"] for o in results[4]["event"]["input_options"]] == ["a", "b"]

    # The cleanup stage actually pays out and moves Jean.
    assert sorted(type(i).__name__ for i in player.inventory) == [
        "Antidote",
        "Restorative",
    ]
    assert player.teleported == ("grondia", (10, 5))


def test_guide_to_citadel_pending_payload_tracks_the_stage_the_player_is_on(
    game_service,
):
    """Each stage re-keys pending_events and stores THAT stage's payload.

    A stale id would make the client dedupe the new stage away; stale
    ``event_data`` would replay the previous stage's prose on reload.
    """
    from src.story.ch02 import Ch02GuideToCitadel

    player = _guide_to_citadel_player()
    event = Ch02GuideToCitadel(player=player, tile=player.tile, params=None)
    results, session_data = _play_staged_event(
        game_service, player, event, ["continue"]
    )

    ids = [r["event"]["event_id"] for r in results if r.get("needs_input")]
    assert len(set(ids)) == len(ids), "a stage reused the previous stage's event_id"
    assert "evt-0" not in ids

    # Replay the recovery read GET /world/events/pending performs at each stage.
    player2 = _guide_to_citadel_player()
    event2 = Ch02GuideToCitadel(player=player2, tile=player2.tile, params=None)
    from unittest.mock import patch

    session2 = {"pending_events": {"evt-0": {"event": event2, "event_data": {}}}}
    event_id = "evt-0"
    with patch("src.api.services.game_service.check_for_combat", return_value=[]):
        for _ in range(7):
            result = game_service.process_event_input(
                player2, event_id, "continue", session2
            )
            assert len(session2["pending_events"]) == 1
            stored_id, stored = next(iter(session2["pending_events"].items()))
            assert stored_id == result["event"]["event_id"]
            recovered = stored["event_data"]
            assert recovered.get("segments") == result.get("segments")
            assert recovered.get("conversation") == result.get("conversation")
            assert recovered.get("output_text") == result.get("output_text")
            event_id = stored_id


def test_guide_to_citadel_quest_choice_selects_different_beats(game_service):
    """Stage 6 branches on the player's answer — 'tell me more' is the long path."""
    from src.story.ch02 import Ch02GuideToCitadel

    def beats_for(answer):
        player = _guide_to_citadel_player()
        event = Ch02GuideToCitadel(player=player, tile=player.tile, params=None)
        answers = ["continue"] * 5 + [answer] + ["continue"] * 4
        results, _ = _play_staged_event(game_service, player, event, answers)
        return [s["text"] for s in results[5]["segments"]]

    long_path = beats_for("a")
    short_path = beats_for("b")

    assert any("Humans." == t for t in long_path)
    assert not any("Humans." == t for t in short_path)
    assert len(long_path) > len(short_path)
    # Both branches still converge on Votha Krr accepting the job.
    assert any("Thank you, Jean" in t for t in long_path)
    assert any("Thank you, Jean" in t for t in short_path)
