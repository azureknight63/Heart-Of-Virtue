"""Unit tests for API validators."""

import sys
from pathlib import Path

# Ensure the project's src directory is on sys.path
ROOT = Path(__file__).resolve().parent.parent.parent


from src.api.services.validators import (
    validate_required_fields,
    validate_direction,
    validate_item_index,
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
    """Test valid directions, including diagonals."""
    for direction in [
        "north",
        "south",
        "east",
        "west",
        "northeast",
        "southwest",
        "NORTH",
        "South",
    ]:
        is_valid, error = validate_direction(direction)
        assert is_valid is True
        assert error is None


def test_validate_direction_invalid():
    """Test invalid direction."""
    is_valid, error = validate_direction("up")
    assert is_valid is False
    assert "Invalid direction" in error


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
    assert "Invalid item index" in error or "must be between" in error
