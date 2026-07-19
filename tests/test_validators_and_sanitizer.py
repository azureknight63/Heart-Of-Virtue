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
    validate_npc_id,
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

    def test_non_dict_body(self):
        ok, err = validate_required_fields("not a dict", ["a"])
        assert ok is False
        assert "JSON object" in err

    def test_empty_required_list(self):
        ok, err = validate_required_fields({"a": 1}, [])
        assert ok is True
        assert err is None

    def test_extra_fields_allowed(self):
        ok, err = validate_required_fields({"a": 1, "extra": 99}, ["a"])
        assert ok is True


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

    def test_negative_index(self):
        ok, err = validate_item_index(-1, 5)
        assert ok is False

    def test_string_coercible(self):
        ok, err = validate_item_index("1", 5)
        assert ok is True

    def test_non_numeric(self):
        ok, err = validate_item_index("abc", 5)
        assert ok is False

    def test_bool_true_rejected(self):
        # bool is an int subclass (True == 1) but is never a meaningful
        # inventory index; must be rejected like coerce_optional_index does.
        ok, err = validate_item_index(True, 5)
        assert ok is False
        assert err is not None

    def test_bool_false_rejected(self):
        ok, err = validate_item_index(False, 5)
        assert ok is False
        assert err is not None


# ---------------------------------------------------------------------------
# validate_npc_id
# ---------------------------------------------------------------------------


class TestValidateNpcId:
    def test_valid_id(self):
        ok, err = validate_npc_id("gorran_01")
        assert ok is True

    def test_empty_string(self):
        ok, err = validate_npc_id("")
        assert ok is False

    def test_too_long(self):
        ok, err = validate_npc_id("x" * 101)
        assert ok is False

    def test_exactly_100_chars(self):
        ok, err = validate_npc_id("x" * 100)
        assert ok is True

    def test_non_string(self):
        ok, err = validate_npc_id(42)
        assert ok is False
        assert "string" in err


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
        assert err is not None
        assert "No valid options" in err

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

    def test_number_at_boundary(self):
        session = self._session_with_event("e1", "number", input_min=1, input_max=5)
        s, err = sanitize_event_input("5", session, "e1")
        assert err is None

    # --- text input type ---

    def test_text_valid(self):
        session = self._session_with_event("e1", "text")
        sanitized, err = sanitize_event_input("Hello Jean", session, "e1")
        assert err is None
        assert sanitized == "Hello Jean"

    def test_text_empty_rejected(self):
        session = self._session_with_event("e1", "text")
        sanitized, err = sanitize_event_input("", session, "e1")
        assert err is not None

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
        assert "<script>" not in sanitized
        assert "hi" in sanitized

    def test_text_removes_null_bytes(self):
        session = self._session_with_event("e1", "text")
        sanitized, err = sanitize_event_input("hello\x00world", session, "e1")
        assert err is None
        assert "\x00" not in sanitized

    # --- unknown input type ---

    def test_unknown_type_short_input(self):
        session = self._session_with_event("e1", "unknown_type")
        sanitized, err = sanitize_event_input("test", session, "e1")
        assert err is None

    def test_unknown_type_too_long(self):
        session = self._session_with_event("e1", "mystery_type")
        sanitized, err = sanitize_event_input("x" * 501, session, "e1")
        assert err is not None
