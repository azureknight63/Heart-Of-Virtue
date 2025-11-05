"""Unit tests for API validators."""

import sys
from pathlib import Path

# Ensure the project's src directory is on sys.path
ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from src.api.services.validators import (
    validate_required_fields,
    validate_direction,
    validate_coordinates,
    validate_item_slot,
    validate_combat_action,
    validate_item_index,
    validate_save_name,
    validate_string_field,
    validate_positive_integer,
    validate_range,
)


def test_validate_required_fields_success():
    """Test valid required fields."""
    is_valid, error = validate_required_fields(
        {"name": "Player", "level": 1}, ["name", "level"]
    )
    assert is_valid is True
    assert error is None


def test_validate_required_fields_missing():
    """Test missing required fields."""
    is_valid, error = validate_required_fields(
        {"name": "Player"}, ["name", "level"]
    )
    assert is_valid is False
    assert "Missing required fields" in error


def test_validate_required_fields_non_dict():
    """Test non-dict data."""
    is_valid, error = validate_required_fields("invalid", ["field"])
    assert is_valid is False
    assert "must be a JSON object" in error


def test_validate_direction_valid():
    """Test valid directions."""
    for direction in ["north", "south", "east", "west", "NORTH", "South"]:
        is_valid, error = validate_direction(direction)
        assert is_valid is True
        assert error is None


def test_validate_direction_invalid():
    """Test invalid direction."""
    is_valid, error = validate_direction("northeast")
    assert is_valid is False
    assert "Invalid direction" in error


def test_validate_coordinates_valid():
    """Test valid coordinates."""
    is_valid, error = validate_coordinates(0, 0)
    assert is_valid is True
    assert error is None

    is_valid, error = validate_coordinates("50", "-50")
    assert is_valid is True
    assert error is None


def test_validate_coordinates_out_of_range():
    """Test out-of-range coordinates."""
    is_valid, error = validate_coordinates(200, 0)
    assert is_valid is False
    assert "must be between -100 and 100" in error


def test_validate_coordinates_invalid():
    """Test invalid coordinate types."""
    is_valid, error = validate_coordinates("abc", 0)
    assert is_valid is False
    assert "must be valid integers" in error


def test_validate_item_slot_valid():
    """Test valid item slots."""
    for slot in [
        "head",
        "chest",
        "hands",
        "legs",
        "feet",
        "main_hand",
        "off_hand",
        "accessory1",
        "accessory2",
    ]:
        is_valid, error = validate_item_slot(slot)
        assert is_valid is True
        assert error is None


def test_validate_item_slot_invalid():
    """Test invalid item slot."""
    is_valid, error = validate_item_slot("armor")
    assert is_valid is False
    assert "Invalid slot" in error


def test_validate_combat_action_valid():
    """Test valid combat actions."""
    for action in ["attack", "defend", "cast", "item", "flee"]:
        is_valid, error = validate_combat_action(action)
        assert is_valid is True
        assert error is None


def test_validate_combat_action_invalid():
    """Test invalid combat action."""
    is_valid, error = validate_combat_action("spell")
    assert is_valid is False
    assert "Invalid action" in error


def test_validate_item_index_valid():
    """Test valid item indices."""
    is_valid, error = validate_item_index(0, 10)
    assert is_valid is True
    assert error is None

    is_valid, error = validate_item_index("5", 10)
    assert is_valid is True
    assert error is None


def test_validate_item_index_out_of_range():
    """Test out-of-range item index."""
    is_valid, error = validate_item_index(10, 10)
    assert is_valid is False
    assert "must be between 0 and 9" in error


def test_validate_save_name_valid():
    """Test valid save names."""
    is_valid, error = validate_save_name("My Save")
    assert is_valid is True
    assert error is None


def test_validate_save_name_empty():
    """Test empty save name."""
    is_valid, error = validate_save_name("")
    assert is_valid is False
    assert "non-empty string" in error


def test_validate_save_name_too_long():
    """Test save name too long."""
    is_valid, error = validate_save_name("x" * 51)
    assert is_valid is False
    assert "50 characters" in error


def test_validate_save_name_invalid_chars():
    """Test save name with invalid characters."""
    is_valid, error = validate_save_name("My/Save")
    assert is_valid is False
    assert "invalid characters" in error


def test_validate_string_field_valid():
    """Test valid string field."""
    is_valid, error = validate_string_field("name", "Player", max_length=10)
    assert is_valid is True
    assert error is None


def test_validate_string_field_non_string():
    """Test non-string value."""
    is_valid, error = validate_string_field("name", 123)
    assert is_valid is False
    assert "must be a string" in error


def test_validate_string_field_too_short():
    """Test string too short."""
    is_valid, error = validate_string_field("name", "a", min_length=3)
    assert is_valid is False
    assert "at least 3 characters" in error


def test_validate_string_field_too_long():
    """Test string too long."""
    is_valid, error = validate_string_field("name", "x" * 11, max_length=10)
    assert is_valid is False
    assert "at most 10 characters" in error


def test_validate_positive_integer_valid():
    """Test valid positive integer."""
    is_valid, error = validate_positive_integer("level", 5)
    assert is_valid is True
    assert error is None

    is_valid, error = validate_positive_integer("level", "10")
    assert is_valid is True
    assert error is None


def test_validate_positive_integer_invalid():
    """Test invalid positive integer."""
    is_valid, error = validate_positive_integer("level", "abc")
    assert is_valid is False
    assert "must be a valid integer" in error


def test_validate_positive_integer_too_small():
    """Test positive integer too small."""
    is_valid, error = validate_positive_integer("level", 0, min_value=1)
    assert is_valid is False
    assert "at least 1" in error


def test_validate_range_valid():
    """Test valid range."""
    is_valid, error = validate_range("health", 50, 0, 100)
    assert is_valid is True
    assert error is None

    is_valid, error = validate_range("temperature", "98.6", 95.0, 105.0)
    assert is_valid is True
    assert error is None


def test_validate_range_invalid():
    """Test invalid range."""
    is_valid, error = validate_range("health", 150, 0, 100)
    assert is_valid is False
    assert "must be between 0 and 100" in error


def test_validate_range_non_numeric():
    """Test non-numeric value in range."""
    is_valid, error = validate_range("health", "abc", 0, 100)
    assert is_valid is False
    assert "must be a valid number" in error
