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
    if isinstance(item_index, bool):
        # bool is an int subclass (True == 1, False == 0), but a boolean is
        # never a meaningful inventory index. Reject explicitly to match
        # coerce_optional_index's handling.
        return False, "Item index must be a valid integer"
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


def ensure_dict(value: Any) -> Dict[str, Any]:
    """Return ``value`` if it is a dict, otherwise an empty dict.

    A JSON request body can legitimately parse to a list, string, or number
    (e.g. ``[1, 2]`` or ``"hi"``). Route handlers that then call ``.get()`` or
    use ``in`` on it would raise ``AttributeError``/``TypeError`` and surface as
    an HTTP 500. Coercing a non-object body to ``{}`` funnels it into the normal
    missing-field path (a structured 4xx) instead.

    Args:
        value: The parsed JSON body (possibly ``None`` or a non-object).

    Returns:
        The value unchanged when it is a dict, else an empty dict.
    """
    return value if isinstance(value, dict) else {}


def validate_string_field(
    value: Any,
    field_name: str,
    *,
    max_length: Optional[int] = None,
    allow_empty: bool = False,
) -> Tuple[bool, Optional[str]]:
    """Validate that a request field is a (optionally non-empty, bounded) string.

    Guards the many route handlers that call ``.strip()``/``.lower()`` on a
    request value: a non-string (int, list, dict, null) would otherwise raise
    ``AttributeError`` and surface as an HTTP 500. Returning a structured error
    lets the caller reply with a 4xx instead.

    Args:
        value: The raw value pulled from the request body/query.
        field_name: Human-readable name used in the error message.
        max_length: Optional maximum length (characters).
        allow_empty: When False, a blank/whitespace-only string is rejected.

    Returns:
        Tuple of (is_valid, error_message).
    """
    if not isinstance(value, str):
        return False, f"{field_name} must be a string"
    if not allow_empty and not value.strip():
        return False, f"{field_name} is required"
    if max_length is not None and len(value) > max_length:
        return False, f"{field_name} must be {max_length} characters or less"
    return True, None


def coerce_optional_index(
    value: Any, field_name: str = "item_index"
) -> Tuple[Optional[int], Optional[str]]:
    """Coerce an optional numeric index to ``int`` without crashing.

    ``None`` passes through untouched (the field was omitted). A value that
    cannot be interpreted as an integer (e.g. ``"abc"``, a list) yields a
    structured error instead of letting a later comparison raise ``TypeError``.
    Booleans are rejected explicitly — ``True``/``False`` are ``int`` subclasses
    but never a meaningful inventory index.

    Args:
        value: The raw value from the request body.
        field_name: Human-readable name used in the error message.

    Returns:
        Tuple of (index_or_None, error_message).
    """
    if value is None:
        return None, None
    if isinstance(value, bool):
        return None, f"{field_name} must be an integer"
    try:
        return int(value), None
    except (ValueError, TypeError):
        return None, f"{field_name} must be an integer"
