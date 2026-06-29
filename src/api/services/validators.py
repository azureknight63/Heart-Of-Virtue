"""Input validation helpers for API routes."""

from typing import Any, Dict, List, Optional, Tuple


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

    Accepts the eight directions the engine's ``GameService.move_player``
    supports (cardinal plus diagonal).

    Args:
        direction: Direction string

    Returns:
        Tuple of (is_valid, error_message)
    """
    valid_directions = [
        "north",
        "south",
        "east",
        "west",
        "northeast",
        "northwest",
        "southeast",
        "southwest",
    ]
    if direction.lower() not in valid_directions:
        return (
            False,
            f"Invalid direction '{direction}'. Must be one of: {', '.join(valid_directions)}",
        )
    return True, None


def validate_item_index(item_index: Any, max_items: int) -> Tuple[bool, Optional[str]]:
    """Validate inventory item index.

    Args:
        item_index: Item index from request
        max_items: Total items in inventory

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        idx = int(item_index)
        if idx < 0 or idx >= max_items:
            return (
                False,
                f"Invalid item index {idx}. Inventory has {max_items} items",
            )
        return True, None
    except (ValueError, TypeError):
        return False, "Item index must be a valid integer"


def validate_npc_id(npc_id: str) -> Tuple[bool, Optional[str]]:
    """Validate NPC identifier.

    Args:
        npc_id: NPC identifier to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(npc_id, str):
        return False, "NPC ID must be a string"
    if not npc_id:
        return False, "NPC ID cannot be empty"
    if len(npc_id) > 100:
        return False, "NPC ID must be 100 characters or less"
    return True, None
