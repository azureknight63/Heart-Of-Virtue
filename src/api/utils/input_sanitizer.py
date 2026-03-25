"""Input sanitization and validation for event inputs."""

import bleach
from typing import Tuple, Optional, Dict, Any


def sanitize_event_input(
    user_input: str, session_data: Dict[str, Any], event_id: str
) -> Tuple[str, Optional[str]]:
    """Sanitize and validate user input for event processing.

    Args:
        user_input: Raw user input string
        session_data: Session dictionary containing pending events
        event_id: UUID of the event being processed

    Returns:
        Tuple of (sanitized_input, validation_error)
        - sanitized_input: Cleaned and validated input string
        - validation_error: Error message if validation fails, None otherwise
    """
    # Get event metadata to determine input type
    if "pending_events" not in session_data:
        return "", "No pending events found"

    if event_id not in session_data["pending_events"]:
        return "", f"Event {event_id} not found"

    event_data = session_data["pending_events"][event_id].get("event_data", {})
    input_type = event_data.get("input_type", "text")
    input_options = event_data.get("input_options", [])

    # Common sanitization: strip whitespace
    sanitized = user_input.strip()

    # Type-specific validation and sanitization
    if input_type == "choice":
        # Validate against whitelist of allowed options
        valid_values = [opt.get("value") for opt in input_options if "value" in opt]

        if not valid_values:
            return sanitized, "No valid options available"

        if sanitized not in valid_values:
            return "", f"Invalid choice. Please select from: {', '.join(valid_values)}"

        # Choice inputs don't need further sanitization
        return sanitized, None

    elif input_type == "number":
        # Parse as integer
        try:
            num = int(sanitized)
        except ValueError:
            return "", "Input must be a valid number"

        # Check bounds if specified in options
        min_value = event_data.get("min_value")
        max_value = event_data.get("max_value")

        if min_value is not None and num < min_value:
            return "", f"Number must be at least {min_value}"

        if max_value is not None and num > max_value:
            return "", f"Number must be at most {max_value}"

        return str(num), None

    elif input_type == "text":
        # Text input sanitization
        max_length = 500

        if len(sanitized) > max_length:
            return "", f"Input too long (max {max_length} characters)"

        if not sanitized:
            return "", "Input cannot be empty"

        # Use bleach to strip HTML/script tags
        sanitized = bleach.clean(
            sanitized, tags=[], attributes={}, strip=True  # No HTML tags allowed
        )

        # Additional safety: remove null bytes
        sanitized = sanitized.replace("\x00", "")

        return sanitized, None

    else:
        # Unknown input type - basic sanitization only
        if len(sanitized) > 500:
            return "", "Input too long (max 500 characters)"

        sanitized = bleach.clean(sanitized, tags=[], attributes={}, strip=True)
        return sanitized, None
