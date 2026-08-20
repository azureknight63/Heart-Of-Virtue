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


# --- The positional-colour trap ---------------------------------------------
# ``narrate(*parts, color=None, ...)`` joins its POSITIONAL parts like print, so a
# colour passed positionally silently becomes part of the message text instead of
# the structured ``color`` field. ``cprint(text, color)`` keeps the old positional
# signature. CLAUDE.md flags this as a live gotcha; these tests pin both halves so
# nobody "harmonises" the two signatures without noticing what breaks.


def test_narrate_positional_colour_is_swallowed_into_the_text():
    with narration.capture_narration() as messages:
        narration.narrate("Danger", "red")

    assert messages[0]["text"] == "Danger red"
    assert "color" not in messages[0]


def test_narrate_keyword_colour_is_a_structured_field():
    with narration.capture_narration() as messages:
        narration.narrate("Danger", color="red")

    assert messages[0]["text"] == "Danger"
    assert messages[0]["color"] == "red"


def test_cprint_keeps_the_positional_colour_signature():
    """cprint(text, color) is the neotermcolor-compatible shim, unlike narrate()."""
    with narration.capture_narration() as messages:
        narration.cprint("Danger", "red")

    assert messages[0]["text"] == "Danger"
    assert messages[0]["color"] == "red"


def test_narrate_joins_multiple_parts_with_sep_and_merges_meta():
    with narration.capture_narration() as messages:
        narration.narrate("a", "b", "c", sep="-", mtype="combat", attrs=["bold"], beat=7)

    entry = messages[0]
    assert entry["text"] == "a-b-c"
    assert entry["type"] == "combat"
    assert entry["attrs"] == ["bold"]
    assert entry["beat"] == 7


def test_narrate_strips_ansi_from_the_structured_text():
    with narration.capture_narration() as messages:
        narration.narrate("plain \x1b[31mred bit\x1b[0m tail")

    assert messages[0]["text"] == "plain red bit tail"


# --- Capture / echo switching -----------------------------------------------
# The combat adapter reads this buffer through a live listener, so which of
# {buffer, stdout, listeners} is active at any moment is load-bearing.


def test_capture_suppresses_stdout_and_restores_the_echo_afterwards(capsys):
    with narration.capture_narration() as messages:
        narration.narrate("inside the capture")
    narration.narrate("outside the capture")

    out = capsys.readouterr().out
    assert "inside the capture" not in out
    assert "outside the capture" in out
    assert [m["text"] for m in messages] == ["inside the capture"]


def test_capture_with_echo_true_both_records_and_prints(capsys):
    with narration.capture_narration(echo=True) as messages:
        narration.narrate("both places")

    assert [m["text"] for m in messages] == ["both places"]
    assert "both places" in capsys.readouterr().out


def test_nested_captures_do_not_leak_into_each_other():
    with narration.capture_narration() as outer:
        narration.narrate("outer-before")
        with narration.capture_narration() as inner:
            narration.narrate("inner-only")
        narration.narrate("outer-after")

    assert [m["text"] for m in outer] == ["outer-before", "outer-after"]
    assert [m["text"] for m in inner] == ["inner-only"]


def test_listener_fires_live_and_is_removed_when_the_capture_exits():
    seen = []

    with narration.capture_narration(listener=seen.append):
        narration.narrate("first")
        # The adapter attributes animations as messages arrive, not at exit.
        assert [e["text"] for e in seen] == ["first"]
        narration.end_conversation()
        assert seen[-1]["type"] == "conversation_end"

    with narration.capture_narration():
        narration.narrate("after the listener was popped")

    assert [e.get("text") for e in seen if "text" in e] == ["first"]


def test_blank_message_is_not_recorded_but_still_echoes_a_newline(capsys):
    """Whitespace-only text is skipped structurally; the stdout echo keeps spacing."""
    with narration.capture_narration(echo=True) as messages:
        narration.narrate("   ")

    assert messages == []
    assert capsys.readouterr().out == "   \n"


def test_control_entries_outside_a_capture_are_dropped_not_echoed(capsys):
    narration.begin_conversation([("jean", "left", "neutral")])
    narration.end_conversation()

    assert capsys.readouterr().out == ""
    assert narration.collect() == []


# --- Stage-op builders -------------------------------------------------------


def test_exit_op_omits_span_unless_given():
    assert narration.exit_op("gorran") == {"id": "gorran", "transition": "fade"}
    assert narration.exit_op("gorran", transition="instant", span=3) == {
        "id": "gorran",
        "transition": "instant",
        "span": 3,
    }


def test_enter_op_defers_side_and_normalizes_an_unknown_emotion():
    assert narration.enter_op("gorran", emotion="furious") == {
        "id": "gorran",
        "name": "gorran",
        "side": None,  # None => resolved by the API layer's party rule
        "emotion": "neutral",
        "transition": "fade",
    }


def test_exit_character_emits_the_same_shape_as_exit_op_plus_a_type():
    with narration.capture_narration() as messages:
        narration.exit_character("gorran", span=2)

    assert messages[0] == {"type": "stage_exit", **narration.exit_op("gorran", span=2)}
