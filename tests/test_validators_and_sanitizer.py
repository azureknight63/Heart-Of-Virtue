"""
Tests for src/api/services/validators.py and src/api/utils/input_sanitizer.py.

Both modules are pure functions with no Flask/DB dependencies — they take
in plain Python values and return (bool, str|None) or (str, str|None) tuples.
"""

import pytest

from src.api.services.validators import (
    validate_required_fields,
    validate_direction,
    validate_item_index,
)
from src.api.utils.input_sanitizer import sanitize_event_input

# ---------------------------------------------------------------------------
# validate_required_fields
# ---------------------------------------------------------------------------


class TestValidateRequiredFields:
    def test_all_fields_present(self):
        ok, err = validate_required_fields({"a": 1, "b": 2}, ["a", "b"])
        assert ok is True
        assert err is None

    def test_missing_one_field(self):
        ok, err = validate_required_fields({"a": 1}, ["a", "b"])
        assert ok is False
        assert "b" in err

    def test_missing_multiple_fields(self):
        ok, err = validate_required_fields({}, ["x", "y"])
        assert ok is False
        assert "x" in err
        assert "y" in err

    def test_field_value_is_none_counts_as_missing(self):
        ok, err = validate_required_fields({"a": None}, ["a"])
        assert ok is False
        assert err == "Missing required fields: a"

    @pytest.mark.parametrize("falsy", [0, "", False, [], {}])
    def test_falsy_but_present_values_are_accepted(self, falsy):
        # Only None counts as missing. A `not data[f]` implementation would
        # reject a legitimate quantity of 0 or an intentionally blank string.
        assert validate_required_fields({"a": falsy}, ["a"]) == (True, None)

    def test_non_dict_body(self):
        ok, err = validate_required_fields("not a dict", ["a"])
        assert ok is False
        assert "JSON object" in err

    def test_empty_required_list(self):
        ok, err = validate_required_fields({"a": 1}, [])
        assert ok is True
        assert err is None

    def test_extra_fields_allowed(self):
        assert validate_required_fields({"a": 1, "extra": 99}, ["a"]) == (True, None)

    @pytest.mark.parametrize("body", [None, [], "x", 3])
    def test_non_dict_bodies_are_all_rejected(self, body):
        # ensure_dict() coerces these to {} upstream, but validators must not
        # depend on that -- a raw list body reaching `f not in data` would
        # otherwise silently pass for a required field named like an element.
        ok, err = validate_required_fields(body, ["a"])
        assert ok is False
        assert err == "Request body must be a JSON object"


# ---------------------------------------------------------------------------
# validate_direction
# ---------------------------------------------------------------------------


class TestValidateDirection:
    @pytest.mark.parametrize(
        "d",
        [
            "north",
            "south",
            "east",
            "west",
            "northeast",
            "northwest",
            "southeast",
            "southwest",
        ],
    )
    def test_valid_directions(self, d):
        ok, err = validate_direction(d)
        assert ok is True
        assert err is None

    @pytest.mark.parametrize("d", ["North", "SOUTH", "East", "NorthEast"])
    def test_case_insensitive(self, d):
        ok, err = validate_direction(d)
        assert ok is True

    def test_invalid_direction(self):
        ok, err = validate_direction("up")
        assert ok is False
        assert "up" in err

    def test_empty_string(self):
        ok, err = validate_direction("")
        assert ok is False
        assert "Invalid direction ''" in err

    def test_error_lists_every_accepted_direction(self):
        # The message is the only place the client learns the accepted set, so
        # a direction added to `valid_directions` but omitted from the message
        # is a real (if quiet) API regression.
        ok, err = validate_direction("up")
        assert ok is False
        for accepted in "north south east west northeast northwest southeast southwest".split():
            assert accepted in err, f"{accepted} missing from error message"
            assert validate_direction(accepted) == (True, None)

    def test_whitespace_is_not_trimmed(self):
        # validate_direction lowercases but does not strip, so " north" is
        # rejected. Callers must strip before validating.
        ok, _ = validate_direction(" north")
        assert ok is False


# ---------------------------------------------------------------------------
# validate_item_index
# ---------------------------------------------------------------------------


class TestValidateItemIndex:
    def test_valid_index(self):
        ok, err = validate_item_index(2, 5)
        assert ok is True

    def test_zero_index_valid(self):
        ok, err = validate_item_index(0, 3)
        assert ok is True

    def test_index_equals_max(self):
        ok, err = validate_item_index(5, 5)
        assert ok is False
        assert err == "Invalid item index 5. Inventory has 5 items"

    def test_negative_index(self):
        ok, err = validate_item_index(-1, 5)
        assert ok is False
        assert err == "Invalid item index -1. Inventory has 5 items"

    def test_empty_inventory_rejects_index_zero(self):
        # max_items == 0 must reject 0, not accept it: `idx >= max_items`.
        ok, err = validate_item_index(0, 0)
        assert ok is False
        assert "Inventory has 0 items" in err

    def test_string_coercible(self):
        assert validate_item_index("1", 5) == (True, None)

    def test_float_truncates_toward_zero(self):
        # int(2.9) == 2, so a fractional index is accepted at its floor rather
        # than rejected. Pinned as the current contract.
        assert validate_item_index(2.9, 5) == (True, None)

    @pytest.mark.parametrize("bad", ["abc", None, [1], {"a": 1}])
    def test_non_integer_rejected(self, bad):
        ok, err = validate_item_index(bad, 5)
        assert ok is False
        assert err == "Item index must be a valid integer"

    @pytest.mark.parametrize("flag", [True, False])
    def test_bool_rejected(self, flag):
        # bool is an int subclass (True == 1, False == 0) so both would
        # otherwise sail through int() as valid indices 1 and 0. The message
        # must be the type error, not the range error -- assert it, because
        # `err is not None` passed either way.
        ok, err = validate_item_index(flag, 5)
        assert ok is False
        assert err == "Item index must be a valid integer"


# ---------------------------------------------------------------------------
# sanitize_event_input
# ---------------------------------------------------------------------------


class TestSanitizeEventInput:
    def _session_with_event(self, event_id, input_type, **extra):
        event_data = {"input_type": input_type}
        event_data.update(extra)
        return {"pending_events": {event_id: {"event_data": event_data}}}

    # --- missing/wrong event metadata ---

    def test_no_pending_events_key(self):
        sanitized, err = sanitize_event_input("hello", {}, "evt-1")
        assert sanitized == ""
        assert err == "No pending events found"

    def test_event_id_not_found(self):
        session = {"pending_events": {"other-id": {}}}
        sanitized, err = sanitize_event_input("hello", session, "evt-1")
        assert sanitized == ""
        assert "evt-1" in err

    # --- choice input type ---

    def test_choice_valid(self):
        session = self._session_with_event(
            "e1", "choice", input_options=[{"value": "yes"}, {"value": "no"}]
        )
        sanitized, err = sanitize_event_input("yes", session, "e1")
        assert err is None
        assert sanitized == "yes"

    def test_choice_invalid_value(self):
        session = self._session_with_event(
            "e1", "choice", input_options=[{"value": "yes"}, {"value": "no"}]
        )
        sanitized, err = sanitize_event_input("maybe", session, "e1")
        assert sanitized == ""
        assert err is not None
        assert "yes" in err or "no" in err

    def test_choice_no_options(self):
        session = self._session_with_event("e1", "choice", input_options=[])
        sanitized, err = sanitize_event_input("yes", session, "e1")
        assert err == "No valid options available"
        # Note the asymmetry with every other rejection branch: this one
        # returns the stripped input rather than "". Pinned deliberately so a
        # future "consistency" edit to "" has to be a conscious decision --
        # callers that render `sanitized` on error would start showing blanks.
        assert sanitized == "yes"

    def test_choice_strips_whitespace(self):
        session = self._session_with_event(
            "e1", "choice", input_options=[{"value": "yes"}]
        )
        sanitized, err = sanitize_event_input("  yes  ", session, "e1")
        assert err is None
        assert sanitized == "yes"

    # --- number input type ---

    def test_number_valid(self):
        session = self._session_with_event("e1", "number")
        sanitized, err = sanitize_event_input("42", session, "e1")
        assert err is None
        assert sanitized == "42"

    def test_number_invalid_string(self):
        session = self._session_with_event("e1", "number")
        sanitized, err = sanitize_event_input("abc", session, "e1")
        assert sanitized == ""
        assert err is not None

    def test_number_below_min(self):
        # Bounds are produced by EventSerializer.serialize_with_input as
        # input_min/input_max — use the same keys the sanitizer reads.
        session = self._session_with_event("e1", "number", input_min=5)
        sanitized, err = sanitize_event_input("3", session, "e1")
        assert err is not None
        assert "5" in err

    def test_number_above_max(self):
        session = self._session_with_event("e1", "number", input_max=10)
        sanitized, err = sanitize_event_input("15", session, "e1")
        assert err is not None
        assert "10" in err

    def test_number_within_bounds(self):
        session = self._session_with_event(
            "e1", "number", input_min=1, input_max=10
        )
        sanitized, err = sanitize_event_input("7", session, "e1")
        assert err is None
        assert sanitized == "7"

    @pytest.mark.parametrize("raw", ["1", "5"])
    def test_number_at_boundary_is_inclusive(self, raw):
        # Both bounds are inclusive: `num < min` / `num > max` reject, so an
        # off-by-one to <=/>= would fail here rather than silently narrowing
        # every bounded prompt in the game by one value at each end.
        session = self._session_with_event("e1", "number", input_min=1, input_max=5)
        sanitized, err = sanitize_event_input(raw, session, "e1")
        assert err is None
        assert sanitized == raw

    def test_number_is_normalized_through_int(self):
        # The sanitizer returns str(int(...)), not the raw text, so surrounding
        # whitespace and leading zeros are canonicalized before an event ever
        # compares the value against an option.
        session = self._session_with_event("e1", "number")
        assert sanitize_event_input("  007  ", session, "e1") == ("7", None)
        assert sanitize_event_input("-3", session, "e1") == ("-3", None)

    def test_number_rejects_float_text(self):
        session = self._session_with_event("e1", "number")
        assert sanitize_event_input("4.5", session, "e1") == (
            "",
            "Input must be a valid number",
        )

    # --- text input type ---

    def test_text_valid(self):
        session = self._session_with_event("e1", "text")
        sanitized, err = sanitize_event_input("Hello Jean", session, "e1")
        assert err is None
        assert sanitized == "Hello Jean"

    @pytest.mark.parametrize("raw", ["", "   ", "\t\n"])
    def test_text_empty_or_whitespace_rejected(self, raw):
        # Whitespace-only input strips to "" before the emptiness check, so it
        # must be rejected too -- otherwise an event would advance on a blank.
        session = self._session_with_event("e1", "text")
        assert sanitize_event_input(raw, session, "e1") == (
            "",
            "Input cannot be empty",
        )

    def test_text_too_long(self):
        session = self._session_with_event("e1", "text")
        sanitized, err = sanitize_event_input("x" * 501, session, "e1")
        assert err is not None
        assert "500" in err

    def test_text_strips_html(self):
        session = self._session_with_event("e1", "text")
        sanitized, err = sanitize_event_input(
            "<script>alert('xss')</script>hi", session, "e1"
        )
        assert err is None
        # Pin the exact output, not just the absence of "<script>": tags are
        # stripped (strip=True) while their *text* is kept, so an assertion of
        # the form `"<script>" not in sanitized` would also pass if bleach were
        # swapped for something that merely dropped the angle brackets and left
        # `scriptalert('xss')/script` behind.
        assert sanitized == "alert('xss')hi"

    def test_text_escapes_bare_ampersand(self):
        # bleach escapes characters it cannot strip, so `&` survives as an
        # entity. Pinned because the value is stored and later re-rendered:
        # if this ever became a raw `&`, a stored `&lt;script&gt;` payload
        # could round-trip back into live markup.
        session = self._session_with_event("e1", "text")
        assert sanitize_event_input("a & b", session, "e1") == ("a &amp; b", None)

    def test_text_length_is_checked_before_stripping(self):
        # 720 raw characters that would sanitize down to 40. The length gate
        # runs on the *raw* input, so this is rejected -- fail-closed. Pinned
        # because moving the check after bleach would let a caller push 500
        # post-strip characters of arbitrary markup through the parser first.
        session = self._session_with_event("e1", "text")
        sanitized, err = sanitize_event_input("<script>x</script>" * 40, session, "e1")
        assert sanitized == ""
        assert err == "Input too long (max 500 characters)"

    def test_text_removes_null_bytes(self):
        session = self._session_with_event("e1", "text")
        sanitized, err = sanitize_event_input("hello\x00world", session, "e1")
        assert err is None
        assert "\x00" not in sanitized

    # --- unknown input type ---

    def test_unknown_type_short_input(self):
        session = self._session_with_event("e1", "unknown_type")
        assert sanitize_event_input("  test  ", session, "e1") == ("test", None)

    def test_unknown_type_still_strips_html(self):
        # The fallback branch is the one an unrecognised input_type lands in,
        # so it is exactly where an un-sanitized value would slip through. It
        # must run bleach too -- previously only `err is None` was asserted
        # here, which passed whether or not any sanitization happened at all.
        session = self._session_with_event("e1", "unknown_type")
        sanitized, err = sanitize_event_input(
            "<script>alert('xss')</script>hi", session, "e1"
        )
        assert err is None
        assert sanitized == "alert('xss')hi"

    def test_unknown_type_removes_null_bytes(self):
        session = self._session_with_event("e1", "unknown_type")
        assert sanitize_event_input("hello\x00world", session, "e1") == (
            "helloworld",
            None,
        )

    def test_unknown_type_too_long(self):
        session = self._session_with_event("e1", "mystery_type")
        assert sanitize_event_input("x" * 501, session, "e1") == (
            "",
            "Input too long (max 500 characters)",
        )

    def test_missing_input_type_defaults_to_text(self):
        # event_data.get("input_type", "text") -- an event serialized without
        # an explicit type must get the *strictest* branch (length + emptiness
        # + bleach), not the permissive fallback.
        session = {"pending_events": {"e1": {"event_data": {}}}}
        assert sanitize_event_input("", session, "e1") == (
            "",
            "Input cannot be empty",
        )
        assert sanitize_event_input("a & b", session, "e1") == ("a &amp; b", None)
