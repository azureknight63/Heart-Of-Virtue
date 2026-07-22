"""Event serialization for API responses."""

from typing import Dict, Any, List


class EventSerializer:
    """Serialize game events to JSON-safe dictionaries."""

    @staticmethod
    def serialize(event: Any) -> Dict[str, Any]:
        """Serialize a single event.

        Args:
            event: Event object to serialize

        Returns:
            Dictionary with event data
        """
        if not event:
            return {}

        event_data = {
            "id": str(id(event)),
            "type": type(event).__name__,
            "description": getattr(event, "description", ""),
        }

        # Event metadata
        if hasattr(event, "name"):
            event_data["name"] = event.name
        if hasattr(event, "repeat"):
            event_data["repeat"] = event.repeat
        if hasattr(event, "one_time_only"):
            event_data["one_time_only"] = event.one_time_only

        # Event triggered state
        if hasattr(event, "triggered"):
            event_data["triggered"] = event.triggered
        if hasattr(event, "completed"):
            event_data["completed"] = event.completed

        # Event categories/tags
        if hasattr(event, "event_type"):
            event_data["event_type"] = event.event_type

        # Hidden/difficulty
        if hasattr(event, "hidden"):
            event_data["hidden"] = event.hidden
        if hasattr(event, "hide_factor"):
            event_data["hide_factor"] = event.hide_factor

        # Optional display delay configuration
        if hasattr(event, "delay_mode") and event.delay_mode:
            event_data["delay_mode"] = event.delay_mode
            event_data["delay_duration"] = getattr(event, "delay_duration", 3000)

        # Optional presentation hint (e.g. "memory_flash") so the client can
        # wrap the event in dedicated UI flair.
        if getattr(event, "presentation", None):
            event_data["presentation"] = event.presentation

        return event_data

    @staticmethod
    def serialize_list(events: List[Any]) -> List[Dict[str, Any]]:
        """Serialize multiple events.

        Args:
            events: List of events

        Returns:
            List of serialized event dictionaries
        """
        if not events:
            return []

        return [EventSerializer.serialize(event) for event in events]

    @staticmethod
    def serialize_with_input(event: Any) -> Dict[str, Any]:
        """Serialize event with user input requirements.

        Args:
            event: Event object to serialize

        Returns:
            Dictionary with event and input requirement data
        """
        event_data = EventSerializer.serialize(event)

        # Preserve API event ID if set (critical for multi-stage events)
        if hasattr(event, "api_event_id") and event.api_event_id:
            event_data["event_id"] = event.api_event_id

        # Check if event requires input
        needs_input = EventSerializer._detect_input_requirement(event)
        event_data["needs_input"] = needs_input

        if needs_input:
            # Input type (choice, text, number)
            if hasattr(event, "input_type"):
                event_data["input_type"] = event.input_type
            else:
                # Infer input type from event class
                event_data["input_type"] = EventSerializer._infer_input_type(event)

            # Input prompt text
            if hasattr(event, "input_prompt"):
                event_data["input_prompt"] = event.input_prompt
            elif hasattr(event, "get_input_prompt"):
                event_data["input_prompt"] = event.get_input_prompt()
            else:
                event_data["input_prompt"] = "Please make your choice:"

            # Input options for choice-type inputs
            if event_data["input_type"] == "choice":
                if hasattr(event, "input_options"):
                    event_data["input_options"] = event.input_options
                elif hasattr(event, "get_input_options"):
                    event_data["input_options"] = event.get_input_options()
                else:
                    event_data["input_options"] = []

            # Numeric input bounds
            if event_data["input_type"] == "number":
                if hasattr(event, "input_min"):
                    event_data["input_min"] = event.input_min
                if hasattr(event, "input_max"):
                    event_data["input_max"] = event.input_max

            # Text input constraints
            if event_data["input_type"] == "text":
                if hasattr(event, "input_max_length"):
                    event_data["input_max_length"] = event.input_max_length
                else:
                    event_data["input_max_length"] = 500

        return event_data

    @staticmethod
    def _detect_input_requirement(event: Any) -> bool:
        """Detect if an event requires user input.

        Args:
            event: Event object to check

        Returns:
            True if event requires input
        """
        # Check for explicit needs_input flag
        if hasattr(event, "needs_input") and event.needs_input:
            return True

        # Check for requires_input method
        if hasattr(event, "requires_input") and callable(event.requires_input):
            try:
                return event.requires_input()
            except Exception:
                pass

        # Check by event class name (known input-requiring events)
        # NPCSpawnerEvent is intentionally excluded: it spawns NPCs silently and
        # never sets needs_input=True, so it must not be treated as interactive.
        event_type = type(event).__name__
        input_requiring_events = [
            "WhisperingStatue",
            "StMichael",
            "DialogueChoice",
            "MerchantNegotiation",
            "PuzzleEvent",
            "RiddleEvent",
            "CombatEvent",
        ]

        return event_type in input_requiring_events

    @staticmethod
    def _infer_input_type(event: Any) -> str:
        """Infer the type of input required by an event.

        Args:
            event: Event object

        Returns:
            Input type: 'choice', 'text', or 'number'
        """
        # Check for input_options or choices
        if (
            hasattr(event, "input_options")
            or hasattr(event, "get_input_options")
            or hasattr(event, "choices")
        ):
            return "choice"

        # Check for numeric input requirements
        if hasattr(event, "input_min") and hasattr(event, "input_max"):
            return "number"

        # Default to choice for most interactive events
        return "choice"
