"""
Tests for src/api/services/validators.py and src/api/utils/input_sanitizer.py.

Both modules are pure functions with no Flask/DB dependencies — they take
in plain Python values and return (bool, str|None) or (str, str|None) tuples.
"""

import pytest

from src.api.services.validators import (
    validate_required_fields,
    validate_direction,
    validate_coordinates,
    validate_item_slot,
    validate_combat_action,
    validate_save_name,
    validate_string_field,
    validate_positive_integer,
    validate_range,
    validate_item_index,
    validate_equipment_slot,
    validate_weight_limit,
    validate_currency_amount,
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
    @pytest.mark.parametrize("d", ["north", "south", "east", "west"])
    def test_valid_directions(self, d):
        ok, err = validate_direction(d)
        assert ok is True
        assert err is None

    @pytest.mark.parametrize("d", ["North", "SOUTH", "East"])
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
# validate_coordinates
# ---------------------------------------------------------------------------


class TestValidateCoordinates:
    def test_valid_zero_zero(self):
        ok, err = validate_coordinates(0, 0)
        assert ok is True

    def test_valid_positive(self):
        ok, err = validate_coordinates(50, 50)
        assert ok is True

    def test_valid_negative(self):
        ok, err = validate_coordinates(-99, -100)
        assert ok is True

    def test_out_of_range_positive(self):
        ok, err = validate_coordinates(101, 0)
        assert ok is False
        assert "100" in err

    def test_out_of_range_negative(self):
        ok, err = validate_coordinates(0, -101)
        assert ok is False

    def test_string_coercible_to_int(self):
        ok, err = validate_coordinates("5", "10")
        assert ok is True

    def test_non_numeric(self):
        ok, err = validate_coordinates("abc", 0)
        assert ok is False
        assert "integer" in err

    def test_none_values(self):
        ok, err = validate_coordinates(None, None)
        assert ok is False


# ---------------------------------------------------------------------------
# validate_item_slot
# ---------------------------------------------------------------------------


class TestValidateItemSlot:
    @pytest.mark.parametrize(
        "slot",
        [
            "head",
            "chest",
            "hands",
            "legs",
            "feet",
            "main_hand",
            "off_hand",
            "accessory1",
            "accessory2",
        ],
    )
    def test_all_valid_slots(self, slot):
        ok, err = validate_item_slot(slot)
        assert ok is True

    def test_case_insensitive(self):
        ok, err = validate_item_slot("HEAD")
        assert ok is True

    def test_invalid_slot(self):
        ok, err = validate_item_slot("waist")
        assert ok is False
        assert "waist" in err


# ---------------------------------------------------------------------------
# validate_combat_action
# ---------------------------------------------------------------------------


class TestValidateCombatAction:
    @pytest.mark.parametrize("action", ["attack", "defend", "cast", "item", "flee"])
    def test_valid_actions(self, action):
        ok, err = validate_combat_action(action)
        assert ok is True

    def test_case_insensitive(self):
        ok, err = validate_combat_action("ATTACK")
        assert ok is True

    def test_invalid_action(self):
        ok, err = validate_combat_action("dodge")
        assert ok is False


# ---------------------------------------------------------------------------
# validate_save_name
# ---------------------------------------------------------------------------


class TestValidateSaveName:
    def test_valid_name(self):
        ok, err = validate_save_name("my_save_01")
        assert ok is True

    def test_empty_string(self):
        ok, err = validate_save_name("")
        assert ok is False

    def test_none_value(self):
        ok, err = validate_save_name(None)
        assert ok is False

    def test_name_too_long(self):
        ok, err = validate_save_name("a" * 51)
        assert ok is False
        assert "50" in err

    def test_exactly_50_chars(self):
        ok, err = validate_save_name("a" * 50)
        assert ok is True

    @pytest.mark.parametrize("bad_char", ["/", "\\", ":", "*", "?", '"', "<", ">", "|"])
    def test_invalid_characters(self, bad_char):
        ok, err = validate_save_name(f"save{bad_char}name")
        assert ok is False
        assert "invalid" in err.lower()


# ---------------------------------------------------------------------------
# validate_string_field
# ---------------------------------------------------------------------------


class TestValidateStringField:
    def test_valid_string(self):
        ok, err = validate_string_field("username", "Jean")
        assert ok is True

    def test_non_string(self):
        ok, err = validate_string_field("username", 123)
        assert ok is False
        assert "string" in err

    def test_too_short(self):
        ok, err = validate_string_field("username", "", min_length=1)
        assert ok is False

    def test_too_long(self):
        ok, err = validate_string_field("bio", "x" * 11, max_length=10)
        assert ok is False
        assert "10" in err

    def test_exactly_max_length(self):
        ok, err = validate_string_field("bio", "x" * 10, max_length=10)
        assert ok is True

    def test_custom_min_length(self):
        ok, err = validate_string_field("code", "ab", min_length=3)
        assert ok is False


# ---------------------------------------------------------------------------
# validate_positive_integer
# ---------------------------------------------------------------------------


class TestValidatePositiveInteger:
    def test_valid_positive(self):
        ok, err = validate_positive_integer("count", 5)
        assert ok is True

    def test_minimum_one_passes(self):
        ok, err = validate_positive_integer("count", 1)
        assert ok is True

    def test_below_minimum(self):
        ok, err = validate_positive_integer("count", 0)
        assert ok is False

    def test_string_coercible(self):
        ok, err = validate_positive_integer("count", "3")
        assert ok is True

    def test_non_numeric(self):
        ok, err = validate_positive_integer("count", "abc")
        assert ok is False

    def test_custom_min_value(self):
        ok, err = validate_positive_integer("count", 4, min_value=5)
        assert ok is False
        assert "5" in err


# ---------------------------------------------------------------------------
# validate_range
# ---------------------------------------------------------------------------


class TestValidateRange:
    def test_in_range(self):
        ok, err = validate_range("speed", 50, 0, 100)
        assert ok is True

    def test_at_min(self):
        ok, err = validate_range("speed", 0, 0, 100)
        assert ok is True

    def test_at_max(self):
        ok, err = validate_range("speed", 100, 0, 100)
        assert ok is True

    def test_below_min(self):
        ok, err = validate_range("speed", -1, 0, 100)
        assert ok is False

    def test_above_max(self):
        ok, err = validate_range("speed", 101, 0, 100)
        assert ok is False

    def test_float_value(self):
        ok, err = validate_range("ratio", 0.5, 0.0, 1.0)
        assert ok is True

    def test_non_numeric(self):
        ok, err = validate_range("speed", "fast", 0, 100)
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


# ---------------------------------------------------------------------------
# validate_equipment_slot
# ---------------------------------------------------------------------------


class TestValidateEquipmentSlot:
    @pytest.mark.parametrize(
        "slot",
        [
            "weapon",
            "shield",
            "head",
            "body",
            "legs",
            "hands",
            "feet",
            "accessory_1",
            "accessory_2",
        ],
    )
    def test_valid_slots(self, slot):
        ok, err = validate_equipment_slot(slot)
        assert ok is True

    def test_invalid_slot(self):
        ok, err = validate_equipment_slot("chest")
        assert ok is False

    def test_case_sensitive(self):
        # validate_equipment_slot does NOT call .lower() — it's case-sensitive
        ok, err = validate_equipment_slot("Head")
        assert ok is False


# ---------------------------------------------------------------------------
# validate_weight_limit
# ---------------------------------------------------------------------------


class TestValidateWeightLimit:
    def test_under_limit(self):
        ok, err = validate_weight_limit(5.0, 3.0, 10.0)
        assert ok is True

    def test_exactly_at_limit(self):
        ok, err = validate_weight_limit(7.0, 3.0, 10.0)
        assert ok is True

    def test_over_limit(self):
        ok, err = validate_weight_limit(8.0, 3.0, 10.0)
        assert ok is False
        assert "11.0" in err

    def test_zero_current_weight(self):
        ok, err = validate_weight_limit(0.0, 10.0, 10.0)
        assert ok is True


# ---------------------------------------------------------------------------
# validate_currency_amount
# ---------------------------------------------------------------------------


class TestValidateCurrencyAmount:
    def test_valid_amount(self):
        ok, err = validate_currency_amount(10, 100)
        assert ok is True

    def test_zero_amount(self):
        ok, err = validate_currency_amount(0, 100)
        assert ok is False

    def test_negative_amount(self):
        ok, err = validate_currency_amount(-5, 100)
        assert ok is False

    def test_exceeds_available(self):
        ok, err = validate_currency_amount(200, 100)
        assert ok is False
        assert "200" in err

    def test_exactly_available(self):
        ok, err = validate_currency_amount(100, 100)
        assert ok is True

    def test_non_numeric(self):
        ok, err = validate_currency_amount("much", 100)
        assert ok is False


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
        session = self._session_with_event("e1", "number", min_value=5)
        sanitized, err = sanitize_event_input("3", session, "e1")
        assert err is not None
        assert "5" in err

    def test_number_above_max(self):
        session = self._session_with_event("e1", "number", max_value=10)
        sanitized, err = sanitize_event_input("15", session, "e1")
        assert err is not None
        assert "10" in err

    def test_number_within_bounds(self):
        session = self._session_with_event("e1", "number", min_value=1, max_value=10)
        sanitized, err = sanitize_event_input("7", session, "e1")
        assert err is None
        assert sanitized == "7"

    def test_number_at_boundary(self):
        session = self._session_with_event("e1", "number", min_value=1, max_value=5)
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
