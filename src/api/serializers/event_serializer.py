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
    def serialize_with_conditions(event: Any) -> Dict[str, Any]:
        """Serialize event with condition/trigger information.

        Args:
            event: Event object to serialize

        Returns:
            Dictionary with event and condition data
        """
        event_data = EventSerializer.serialize(event)

        # Condition information
        if hasattr(event, "check_conditions"):
            try:
                # Attempt to get condition status (may fail if checks require context)
                event_data["has_conditions_check"] = True
            except Exception:
                event_data["has_conditions_check"] = False

        # Specific condition requirements
        if hasattr(event, "required_item"):
            event_data["required_item"] = event.required_item
        if hasattr(event, "required_level"):
            event_data["required_level"] = event.required_level
        if hasattr(event, "required_flag"):
            event_data["required_flag"] = event.required_flag
        if hasattr(event, "params"):
            event_data["params"] = str(event.params) if event.params else None

        return event_data

    @staticmethod
    def serialize_with_consequences(event: Any) -> Dict[str, Any]:
        """Serialize event with consequence/reward information.

        Args:
            event: Event object to serialize

        Returns:
            Dictionary with event and consequence data
        """
        event_data = EventSerializer.serialize_with_conditions(event)

        # Consequences and rewards
        if hasattr(event, "consequence_text"):
            event_data["consequence"] = event.consequence_text
        if hasattr(event, "consequence"):
            # Handle consequence if it's a simple value
            consequence = event.consequence
            if isinstance(consequence, (str, int, float)):
                event_data["consequence"] = consequence
            else:
                event_data["consequence"] = str(consequence)

        # Experience/gold rewards
        if hasattr(event, "experience_reward"):
            event_data["experience_reward"] = event.experience_reward
        if hasattr(event, "gold_reward"):
            event_data["gold_reward"] = event.gold_reward

        # Item rewards
        if hasattr(event, "item_rewards"):
            event_data["item_rewards"] = event.item_rewards
        if hasattr(event, "item_reward"):
            event_data["item_reward"] = event.item_reward

        # Story progression
        if hasattr(event, "story_flag"):
            event_data["story_flag"] = event.story_flag
        if hasattr(event, "chapter"):
            event_data["chapter"] = event.chapter
        if hasattr(event, "section"):
            event_data["section"] = event.section

        return event_data

    @staticmethod
    def serialize_story_event(event: Any) -> Dict[str, Any]:
        """Serialize story-specific event with narrative data.

        Args:
            event: Story event object to serialize

        Returns:
            Dictionary with story event data
        """
        event_data = EventSerializer.serialize_with_consequences(event)

        event_data["is_story_event"] = True

        # Story metadata
        if hasattr(event, "story_name"):
            event_data["story_name"] = event.story_name
        if hasattr(event, "narrative_text"):
            event_data["narrative"] = event.narrative_text

        # Dialogue
        if hasattr(event, "dialogue"):
            event_data["dialogue"] = event.dialogue
        if hasattr(event, "choices"):
            event_data["choice_count"] = len(event.choices) if event.choices else 0

        # Combat encounters
        if hasattr(event, "enemy_spawned"):
            event_data["enemy_spawned"] = event.enemy_spawned
        if hasattr(event, "encounter_type"):
            event_data["encounter_type"] = event.encounter_type

        return event_data

    @staticmethod
    def serialize_combat_event(event: Any) -> Dict[str, Any]:
        """Serialize combat-specific event.

        Args:
            event: Combat event object to serialize

        Returns:
            Dictionary with combat event data
        """
        event_data = EventSerializer.serialize(event)

        event_data["is_combat_event"] = True

        # Combat trigger info
        if hasattr(event, "trigger_on"):
            event_data["trigger_on"] = event.trigger_on
        if hasattr(event, "trigger_condition"):
            event_data["trigger_condition"] = event.trigger_condition

        # Enemy spawning
        if hasattr(event, "enemy_type"):
            event_data["enemy_type"] = event.enemy_type
        if hasattr(event, "enemy_level"):
            event_data["enemy_level"] = event.enemy_level
        if hasattr(event, "enemy_count"):
            event_data["enemy_count"] = event.enemy_count

        # Combat rewards
        if hasattr(event, "victory_message"):
            event_data["victory_message"] = event.victory_message
        if hasattr(event, "defeat_message"):
            event_data["defeat_message"] = event.defeat_message

        return event_data

    @staticmethod
    def serialize_conditional_event(event: Any) -> Dict[str, Any]:
        """Serialize event with complex conditional logic.

        Args:
            event: Conditional event object to serialize

        Returns:
            Dictionary with conditional event data
        """
        event_data = EventSerializer.serialize_with_consequences(event)

        event_data["is_conditional"] = True

        # Multiple conditions
        if hasattr(event, "conditions") and event.conditions:
            event_data["condition_count"] = len(event.conditions)

        # Branching outcomes
        if hasattr(event, "success_consequence"):
            event_data["success_consequence"] = event.success_consequence
        if hasattr(event, "failure_consequence"):
            event_data["failure_consequence"] = event.failure_consequence

        # Trigger timing
        if hasattr(event, "trigger_on_enter"):
            event_data["trigger_on_enter"] = event.trigger_on_enter
        if hasattr(event, "trigger_on_exit"):
            event_data["trigger_on_exit"] = event.trigger_on_exit
        if hasattr(event, "trigger_in_combat"):
            event_data["trigger_in_combat"] = event.trigger_in_combat

        return event_data

    @staticmethod
    def serialize_with_input(event: Any) -> Dict[str, Any]:
        """Serialize event with user input requirements.

        Args:
            event: Event object to serialize

        Returns:
            Dictionary with event and input requirement data
        """
        event_data = EventSerializer.serialize(event)

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
        event_type = type(event).__name__
        input_requiring_events = [
            "WhisperingStatue",
            "StMichael",
            "DialogueChoice",
            "MerchantNegotiation",
            "PuzzleEvent",
            "RiddleEvent",
            "CombatEvent",
            "NPCSpawnerEvent",
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
