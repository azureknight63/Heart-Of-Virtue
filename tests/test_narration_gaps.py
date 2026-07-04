"""Coverage for remaining gaps in src/narration.py.

Targets (line numbers as of this writing):
    77-78    narrate(): listener callback exception is swallowed
    94       emit(): alias delegates to narrate()
    125-128  _emit_control(): listener callback exception is swallowed
    156      say(): `enter` normalized to a list when not already one
    175-176  begin_conversation(): dict member id/speaker resolution
    277-278  collect(): returns [] with no active buffer, else a copy
"""

import src.narration as narration


def test_narrate_listener_exception_is_swallowed():
    """Lines 77-78: a raising listener callback must not break narrate()."""

    def bad_listener(entry):
        raise RuntimeError("listener boom")

    with narration.capture_narration(listener=bad_listener) as messages:
        narration.narrate("Hello there")

    assert len(messages) == 1
    assert messages[0]["text"] == "Hello there"


def test_emit_delegates_to_narrate():
    """Line 94: emit() is a thin alias for narrate()."""
    with narration.capture_narration() as messages:
        narration.emit("Emitted text", color="cyan", mtype="combat")

    assert len(messages) == 1
    assert messages[0]["text"] == "Emitted text"
    assert messages[0]["color"] == "cyan"
    assert messages[0]["type"] == "combat"


def test_emit_control_listener_exception_is_swallowed():
    """Lines 125-128: a raising listener callback must not break _emit_control()."""

    def bad_listener(entry):
        raise RuntimeError("listener boom")

    with narration.capture_narration(listener=bad_listener) as messages:
        narration.end_conversation()

    assert len(messages) == 1
    assert messages[0]["type"] == "conversation_end"


def test_say_enter_normalized_to_list():
    """Line 156: a single `enter` dict is wrapped into a list."""
    with narration.capture_narration() as messages:
        narration.say(
            "Hello", speaker="npc1", enter={"id": "npc1", "side": "left"}
        )

    assert messages[0]["enter"] == [{"id": "npc1", "side": "left"}]


def test_say_leave_as_list_passthrough():
    """Companion branch to line 156-158: `leave` already a list is used as-is."""
    with narration.capture_narration() as messages:
        narration.say(
            "Bye",
            speaker="npc1",
            leave=[{"id": "npc1"}],
        )

    assert messages[0]["exit"] == [{"id": "npc1"}]


def test_begin_conversation_dict_member_with_id():
    """Lines 175-176: dict cast member resolves id via `.get("id")`."""
    with narration.capture_narration() as messages:
        narration.begin_conversation(
            [{"id": "jean", "side": "left", "emotion": "happy", "name": "Jean Claire"}]
        )

    entry = messages[0]
    assert entry["type"] == "conversation_begin"
    roster = entry["cast"]
    assert roster[0]["id"] == "jean"
    assert roster[0]["name"] == "Jean Claire"
    assert roster[0]["side"] == "left"
    assert roster[0]["emotion"] == "happy"


def test_begin_conversation_dict_member_falls_back_to_speaker_key():
    """Lines 175-176: when 'id' is absent, falls back to `.get("speaker")`."""
    with narration.capture_narration() as messages:
        narration.begin_conversation([{"speaker": "gorran", "side": "right"}])

    roster = messages[0]["cast"]
    assert roster[0]["id"] == "gorran"
    assert roster[0]["name"] == "gorran"  # no explicit 'name' -> defaults to cid


def test_begin_conversation_tuple_member_still_works():
    """Sanity check: non-dict (tuple) cast members still work alongside dicts."""
    with narration.capture_narration() as messages:
        narration.begin_conversation([("jean", "left", "neutral"), {"id": "gorran"}])

    roster = messages[0]["cast"]
    assert roster[0]["id"] == "jean"
    assert roster[1]["id"] == "gorran"


def test_collect_outside_capture_returns_empty_list():
    """Line 277-278: collect() with no active capture returns []."""
    assert narration.collect() == []


def test_collect_inside_capture_returns_copy_of_buffer():
    """Line 277-278: collect() inside an active capture returns the messages."""
    with narration.capture_narration() as messages:
        narration.narrate("Buffered message")
        collected = narration.collect()

    assert collected == messages
    assert collected is not messages  # collect() returns a copy, not the live list
