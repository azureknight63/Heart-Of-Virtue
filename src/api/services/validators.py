"""Input validation helpers for API routes."""

from typing import Any, Dict, List, Optional, Tuple, Union


def validate_required_fields(
    data: Dict[str, Any], required_fields: List[str]
) -> Tuple[bool, Optional[str]]:
    """Validate that required fields are present in request data.

    Args:
        data: Request data dictionary
        required_fields: List of required field names

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(data, dict):
        return False, "Request body must be a JSON object"

    missing = [f for f in required_fields if f not in data or data[f] is None]
    if missing:
        return False, f"Missing required fields: {', '.join(missing)}"

    return True, None


def validate_direction(direction: str) -> Tuple[bool, Optional[str]]:
    """Validate movement direction.

    Args:
        direction: Direction string

    Returns:
        Tuple of (is_valid, error_message)
    """
    valid_directions = ["north", "south", "east", "west"]
    if direction.lower() not in valid_directions:
        return (
            False,
            f"Invalid direction '{direction}'. Must be one of: {', '.join(valid_directions)}",
        )
    return True, None


def validate_coordinates(x: Any, y: Any) -> Tuple[bool, Optional[str]]:
    """Validate tile coordinates.

    Args:
        x: X coordinate
        y: Y coordinate

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        x_int = int(x)
        y_int = int(y)
        if x_int < -100 or x_int > 100 or y_int < -100 or y_int > 100:
            return False, "Coordinates must be between -100 and 100"
        return True, None
    except (ValueError, TypeError):
        return False, "Coordinates must be valid integers"


def validate_item_slot(slot: str) -> Tuple[bool, Optional[str]]:
    """Validate equipment slot name.

    Args:
        slot: Equipment slot name

    Returns:
        Tuple of (is_valid, error_message)
    """
    valid_slots = [
        "head",
        "chest",
        "hands",
        "legs",
        "feet",
        "main_hand",
        "off_hand",
        "accessory1",
        "accessory2",
    ]
    if slot.lower() not in valid_slots:
        return False, f"Invalid slot '{slot}'. Must be one of: {', '.join(valid_slots)}"
    return True, None


def validate_combat_action(action: str) -> Tuple[bool, Optional[str]]:
    """Validate combat action type.

    Args:
        action: Combat action name

    Returns:
        Tuple of (is_valid, error_message)
    """
    valid_actions = ["attack", "defend", "cast", "item", "flee"]
    if action.lower() not in valid_actions:
        return (
            False,
            f"Invalid action '{action}'. Must be one of: {', '.join(valid_actions)}",
        )
    return True, None


def validate_item_index(index: Any, max_index: int) -> Tuple[bool, Optional[str]]:
    """Validate item index within inventory.

    Args:
        index: Item index
        max_index: Maximum valid index

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        idx = int(index)
        if idx < 0 or idx >= max_index:
            return False, f"Item index must be between 0 and {max_index - 1}"
        return True, None
    except (ValueError, TypeError):
        return False, "Item index must be a valid integer"


def validate_save_name(name: str) -> Tuple[bool, Optional[str]]:
    """Validate save file name.

    Args:
        name: Save file name

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not name or not isinstance(name, str):
        return False, "Save name must be a non-empty string"
    if len(name) > 50:
        return False, "Save name must be 50 characters or less"
    if any(c in name for c in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']):
        return False, "Save name contains invalid characters"
    return True, None


def validate_string_field(
    field_name: str, value: Any, max_length: int = 1000, min_length: int = 1
) -> Tuple[bool, Optional[str]]:
    """Validate a string field with length constraints.

    Args:
        field_name: Name of the field (for error messages)
        value: The value to validate
        max_length: Maximum allowed length
        min_length: Minimum allowed length

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(value, str):
        return False, f"{field_name} must be a string"
    if len(value) < min_length:
        return False, f"{field_name} must be at least {min_length} characters"
    if len(value) > max_length:
        return False, f"{field_name} must be at most {max_length} characters"
    return True, None


def validate_positive_integer(
    field_name: str, value: Any, min_value: int = 1
) -> Tuple[bool, Optional[str]]:
    """Validate a positive integer field.

    Args:
        field_name: Name of the field (for error messages)
        value: The value to validate
        min_value: Minimum allowed value

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        num = int(value)
        if num < min_value:
            return False, f"{field_name} must be at least {min_value}"
        return True, None
    except (ValueError, TypeError):
        return False, f"{field_name} must be a valid integer"


def validate_range(
    field_name: str, value: Any, min_value: Union[int, float], max_value: Union[int, float]
) -> Tuple[bool, Optional[str]]:
    """Validate a numeric value within a range.

    Args:
        field_name: Name of the field (for error messages)
        value: The value to validate
        min_value: Minimum allowed value
        max_value: Maximum allowed value

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        num = float(value)
        if num < min_value or num > max_value:
            return (
                False,
                f"{field_name} must be between {min_value} and {max_value}",
            )
        return True, None
    except (ValueError, TypeError):
        return False, f"{field_name} must be a valid number"
