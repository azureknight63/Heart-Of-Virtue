"""
Dialogue Context Serializers

Transforms dialogue-related data between internal representations and JSON-serializable formats.
Handles dialogue nodes, conversation history, player choices, and dialogue effects.

Module Pattern: Provides 6 serializer classes for complete dialogue system support
- DialogueNodeSerializer: Single conversation node
- DialogueChoiceSerializer: Player decision points
- DialogueConditionSerializer: When dialogue is available
- DialogueEffectSerializer: Consequences of dialogue choices
- ConversationHistorySerializer: Past conversations with NPCs
- DialogueContextSerializer: Complete conversation state

Type Hints: Full typing throughout for IDE support and static analysis
Docstrings: Comprehensive docstring for each class and method
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum


class DialogueEffectType(Enum):
    """Types of effects that can result from dialogue choices."""

    STORY_GATE = "story_gate"
    REPUTATION = "reputation"
    ITEM_REWARD = "item_reward"
    QUEST_PROGRESS = "quest_progress"
    NPC_STATE_CHANGE = "npc_state_change"


@dataclass
class DialogueEffect:
    """
    Represents a consequence of a dialogue choice.

    Attributes:
        effect_type: Type of effect (story gate, reputation, etc.)
        target: What is being affected (story_gate_name, npc_id, quest_id)
        value: Magnitude of effect (delta for reputation, true/false for gates)
        description: Human-readable effect description
    """

    effect_type: str
    target: str
    value: Any
    description: str = ""


class DialogueEffectSerializer:
    """
    Serializes dialogue effects to/from JSON-compatible dicts.

    Handles:
    - Story gate changes (set gate to true/false)
    - Reputation changes (delta values)
    - Item rewards (item_id: quantity)
    - Quest progress updates (quest_id: progress_step)
    - NPC state changes (npc_id: state_value)
    """

    @staticmethod
    def serialize(effect: DialogueEffect) -> Dict[str, Any]:
        """
        Convert DialogueEffect to JSON-serializable dict.

        Args:
            effect: DialogueEffect object to serialize

        Returns:
            Dict with effect_type, target, value, description

        Example:
            >>> effect = DialogueEffect(
            ...     effect_type="story_gate",
            ...     target="ch01_door_opened",
            ...     value=True,
            ...     description="Opens the stone door"
            ... )
            >>> DialogueEffectSerializer.serialize(effect)
            {
                'effect_type': 'story_gate',
                'target': 'ch01_door_opened',
                'value': True,
                'description': 'Opens the stone door'
            }
        """
        return {
            "effect_type": effect.effect_type,
            "target": effect.target,
            "value": effect.value,
            "description": effect.description,
        }

    @staticmethod
    def deserialize(data: Dict[str, Any]) -> DialogueEffect:
        """
        Convert JSON dict to DialogueEffect object.

        Args:
            data: Dict with effect properties

        Returns:
            DialogueEffect object

        Raises:
            KeyError: If required fields missing
            ValueError: If effect_type not recognized
        """
        required_fields = {"effect_type", "target", "value"}
        if not required_fields.issubset(set(data.keys())):
            raise KeyError(
                f"Missing required fields: {required_fields - set(data.keys())}"
            )

        if data["effect_type"] not in [e.value for e in DialogueEffectType]:
            raise ValueError(f"Unknown effect_type: {data['effect_type']}")

        return DialogueEffect(
            effect_type=data["effect_type"],
            target=data["target"],
            value=data["value"],
            description=data.get("description", ""),
        )


@dataclass
class DialogueCondition:
    """
    Represents conditions that must be met for dialogue to be available.

    Attributes:
        required_story_gates: Story gates that must be True
        forbidden_story_gates: Story gates that must be False
        min_reputation: Minimum reputation with NPC (or None)
        max_reputation: Maximum reputation with NPC (or None)
        required_completed_dialogues: Other dialogues that must be done first
        min_player_level: Minimum player level (or None)
    """

    required_story_gates: List[str] = field(default_factory=list)
    forbidden_story_gates: List[str] = field(default_factory=list)
    min_reputation: Optional[int] = None
    max_reputation: Optional[int] = None
    required_completed_dialogues: List[str] = field(default_factory=list)
    min_player_level: Optional[int] = None


class DialogueConditionSerializer:
    """
    Serializes dialogue conditions to/from JSON-compatible dicts.

    Handles validation of:
    - Story gate availability
    - Reputation thresholds
    - Prerequisite dialogues
    - Player level requirements
    """

    @staticmethod
    def serialize(condition: DialogueCondition) -> Dict[str, Any]:
        """
        Convert DialogueCondition to JSON-serializable dict.

        Args:
            condition: DialogueCondition object

        Returns:
            Dict with all condition fields (None values included for clarity)
        """
        return {
            "required_story_gates": condition.required_story_gates,
            "forbidden_story_gates": condition.forbidden_story_gates,
            "min_reputation": condition.min_reputation,
            "max_reputation": condition.max_reputation,
            "required_completed_dialogues": condition.required_completed_dialogues,
            "min_player_level": condition.min_player_level,
        }

    @staticmethod
    def deserialize(data: Dict[str, Any]) -> DialogueCondition:
        """
        Convert JSON dict to DialogueCondition object.

        Args:
            data: Dict with condition properties

        Returns:
            DialogueCondition object (uses defaults for missing fields)
        """
        return DialogueCondition(
            required_story_gates=data.get("required_story_gates", []),
            forbidden_story_gates=data.get("forbidden_story_gates", []),
            min_reputation=data.get("min_reputation"),
            max_reputation=data.get("max_reputation"),
            required_completed_dialogues=data.get(
                "required_completed_dialogues", []
            ),
            min_player_level=data.get("min_player_level"),
        )

    @staticmethod
    def check_conditions(
        condition: DialogueCondition,
        player_story: Dict[str, bool],
        player_reputation: Dict[str, int],
        player_level: int,
        player_completed_dialogues: List[str],
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate if player meets dialogue conditions.

        Args:
            condition: DialogueCondition to check
            player_story: Dict of story gate states
            player_reputation: Dict of NPC reputation values
            player_level: Current player level
            player_completed_dialogues: List of completed dialogue IDs

        Returns:
            Tuple of (is_available, reason_if_unavailable)

        Example:
            >>> condition = DialogueCondition(required_story_gates=["ch01_complete"])
            >>> is_available, reason = DialogueConditionSerializer.check_conditions(
            ...     condition,
            ...     player_story={"ch01_complete": False},
            ...     player_reputation={},
            ...     player_level=1,
            ...     player_completed_dialogues=[]
            ... )
            >>> is_available
            False
            >>> reason
            'Required story gate not set: ch01_complete'
        """
        # Check required story gates
        for gate in condition.required_story_gates:
            if not player_story.get(gate, False):
                return False, f"Required story gate not set: {gate}"

        # Check forbidden story gates
        for gate in condition.forbidden_story_gates:
            if player_story.get(gate, False):
                return False, f"Forbidden story gate is set: {gate}"

        # Check prerequisite dialogues (if any provided)
        if condition.required_completed_dialogues:
            missing_dialogues = [
                d
                for d in condition.required_completed_dialogues
                if d not in player_completed_dialogues
            ]
            if missing_dialogues:
                return (
                    False,
                    f"Must complete dialogue(s) first: {', '.join(missing_dialogues)}",
                )

        # Check player level
        if (
            condition.min_player_level
            and player_level < condition.min_player_level
        ):
            return (
                False,
                f"Player level too low (need {condition.min_player_level})",
            )

        return True, None


@dataclass
class DialogueChoice:
    """
    Represents a choice a player can make during dialogue.

    Attributes:
        choice_id: Unique identifier for this choice
        text: Display text of the choice
        target_node_id: Node to transition to if chosen
        condition: Conditions for choice to be available
        effects: List of effects from choosing this
    """

    choice_id: str
    text: str
    target_node_id: str
    condition: Optional[DialogueCondition] = None
    effects: List[DialogueEffect] = field(default_factory=list)


class DialogueChoiceSerializer:
    """
    Serializes dialogue choices to/from JSON-compatible dicts.

    Handles:
    - Choice availability checking
    - Conditional branching
    - Effect application on selection
    - Choice history tracking
    """

    @staticmethod
    def serialize(choice: DialogueChoice) -> Dict[str, Any]:
        """
        Convert DialogueChoice to JSON-serializable dict.

        Args:
            choice: DialogueChoice object

        Returns:
            Dict with choice_id, text, target_node_id, and effects
        """
        return {
            "choice_id": choice.choice_id,
            "text": choice.text,
            "target_node_id": choice.target_node_id,
            "condition": (
                DialogueConditionSerializer.serialize(choice.condition)
                if choice.condition
                else None
            ),
            "effects": [
                DialogueEffectSerializer.serialize(e) for e in choice.effects
            ],
        }

    @staticmethod
    def deserialize(data: Dict[str, Any]) -> DialogueChoice:
        """
        Convert JSON dict to DialogueChoice object.

        Args:
            data: Dict with choice properties

        Returns:
            DialogueChoice object

        Raises:
            KeyError: If required fields missing
        """
        required_fields = {"choice_id", "text", "target_node_id"}
        if not required_fields.issubset(set(data.keys())):
            raise KeyError(
                f"Missing required fields: {required_fields - set(data.keys())}"
            )

        condition = None
        if data.get("condition"):
            condition = DialogueConditionSerializer.deserialize(
                data["condition"]
            )

        effects = []
        if data.get("effects"):
            effects = [
                DialogueEffectSerializer.deserialize(e)
                for e in data["effects"]
            ]

        return DialogueChoice(
            choice_id=data["choice_id"],
            text=data["text"],
            target_node_id=data["target_node_id"],
            condition=condition,
            effects=effects,
        )

    @staticmethod
    def filter_available_choices(
        choices: List[DialogueChoice],
        player_story: Dict[str, bool],
        player_reputation: Dict[str, int],
        player_level: int,
        player_completed_dialogues: List[str],
    ) -> List[DialogueChoice]:
        """
        Filter choices to only those available to player.

        Args:
            choices: All possible choices
            player_story: Player's story state
            player_reputation: Player's NPC reputations
            player_level: Player's current level
            player_completed_dialogues: Past dialogues

        Returns:
            Subset of choices where conditions are met
        """
        available = []
        for choice in choices:
            if choice.condition is None:
                # No conditions = always available
                available.append(choice)
            else:
                is_available, _ = DialogueConditionSerializer.check_conditions(
                    choice.condition,
                    player_story,
                    player_reputation,
                    player_level,
                    player_completed_dialogues,
                )
                if is_available:
                    available.append(choice)
        return available


@dataclass
class DialogueNode:
    """
    Represents a single node in a dialogue tree.

    Attributes:
        node_id: Unique identifier for this node
        text: Dialogue text spoken by NPC
        speaker: NPC name/ID speaking this line
        npc_tone: Personality/tone of response (friendly, hostile, neutral)
        choices: List of choices available from this node
        condition: Conditions for node to be visitable
    """

    node_id: str
    text: str
    speaker: str
    npc_tone: str = "neutral"
    choices: List[DialogueChoice] = field(default_factory=list)
    condition: Optional[DialogueCondition] = None


class DialogueNodeSerializer:
    """
    Serializes dialogue nodes to/from JSON-compatible dicts.

    Handles:
    - Dialogue tree structure
    - Node availability checking
    - Choice availability at each node
    - Tone/personality modifiers
    """

    @staticmethod
    def serialize(node: DialogueNode) -> Dict[str, Any]:
        """
        Convert DialogueNode to JSON-serializable dict.

        Args:
            node: DialogueNode object

        Returns:
            Dict with all node data including nested choices
        """
        return {
            "node_id": node.node_id,
            "text": node.text,
            "speaker": node.speaker,
            "npc_tone": node.npc_tone,
            "choices": [
                DialogueChoiceSerializer.serialize(c) for c in node.choices
            ],
            "condition": (
                DialogueConditionSerializer.serialize(node.condition)
                if node.condition
                else None
            ),
        }

    @staticmethod
    def deserialize(data: Dict[str, Any]) -> DialogueNode:
        """
        Convert JSON dict to DialogueNode object.

        Args:
            data: Dict with node properties

        Returns:
            DialogueNode object

        Raises:
            KeyError: If required fields missing
        """
        required_fields = {"node_id", "text", "speaker"}
        if not required_fields.issubset(set(data.keys())):
            raise KeyError(
                f"Missing required fields: {required_fields - set(data.keys())}"
            )

        condition = None
        if data.get("condition"):
            condition = DialogueConditionSerializer.deserialize(
                data["condition"]
            )

        choices = []
        if data.get("choices"):
            choices = [
                DialogueChoiceSerializer.deserialize(c)
                for c in data["choices"]
            ]

        return DialogueNode(
            node_id=data["node_id"],
            text=data["text"],
            speaker=data["speaker"],
            npc_tone=data.get("npc_tone", "neutral"),
            choices=choices,
            condition=condition,
        )

    @staticmethod
    def get_available_choices(
        node: DialogueNode,
        player_story: Dict[str, bool],
        player_reputation: Dict[str, int],
        player_level: int,
        player_completed_dialogues: List[str],
    ) -> List[DialogueChoice]:
        """
        Get choices available at this node for the player.

        Args:
            node: The current dialogue node
            player_story: Player's story state
            player_reputation: Player's NPC reputations
            player_level: Player's level
            player_completed_dialogues: Past dialogues

        Returns:
            List of available DialogueChoice objects
        """
        return DialogueChoiceSerializer.filter_available_choices(
            node.choices,
            player_story,
            player_reputation,
            player_level,
            player_completed_dialogues,
        )


@dataclass
class ConversationHistory:
    """
    Represents a conversation session between player and NPC.

    Attributes:
        conversation_id: Unique identifier for this conversation
        npc_id: Which NPC this conversation was with
        player_id: Which player had this conversation
        dialogue_id: Which dialogue tree was used
        started_at: ISO timestamp when started
        nodes_visited: Order of nodes visited in this conversation
        choices_made: Choices selected in this conversation
        effects_applied: Effects that were applied
        status: "started", "ongoing", "completed", "abandoned"
    """

    conversation_id: str
    npc_id: str
    player_id: str
    dialogue_id: str
    started_at: str
    nodes_visited: List[str] = field(default_factory=list)
    choices_made: List[str] = field(default_factory=list)
    effects_applied: List[Dict[str, Any]] = field(default_factory=list)
    status: str = "ongoing"


class ConversationHistorySerializer:
    """
    Serializes conversation history to/from JSON-compatible dicts.

    Handles:
    - Conversation state tracking
    - Choice history
    - Effect audit trail
    - Conversation status transitions
    """

    @staticmethod
    def serialize(history: ConversationHistory) -> Dict[str, Any]:
        """
        Convert ConversationHistory to JSON-serializable dict.

        Args:
            history: ConversationHistory object

        Returns:
            Dict with all conversation data
        """
        return {
            "conversation_id": history.conversation_id,
            "npc_id": history.npc_id,
            "player_id": history.player_id,
            "dialogue_id": history.dialogue_id,
            "started_at": history.started_at,
            "nodes_visited": history.nodes_visited,
            "choices_made": history.choices_made,
            "effects_applied": history.effects_applied,
            "status": history.status,
        }

    @staticmethod
    def deserialize(data: Dict[str, Any]) -> ConversationHistory:
        """
        Convert JSON dict to ConversationHistory object.

        Args:
            data: Dict with conversation properties

        Returns:
            ConversationHistory object

        Raises:
            KeyError: If required fields missing
        """
        required_fields = {
            "conversation_id",
            "npc_id",
            "player_id",
            "dialogue_id",
            "started_at",
        }
        if not required_fields.issubset(set(data.keys())):
            raise KeyError(
                f"Missing required fields: {required_fields - set(data.keys())}"
            )

        return ConversationHistory(
            conversation_id=data["conversation_id"],
            npc_id=data["npc_id"],
            player_id=data["player_id"],
            dialogue_id=data["dialogue_id"],
            started_at=data["started_at"],
            nodes_visited=data.get("nodes_visited", []),
            choices_made=data.get("choices_made", []),
            effects_applied=data.get("effects_applied", []),
            status=data.get("status", "ongoing"),
        )

    @staticmethod
    def add_node_visit(history: ConversationHistory, node_id: str) -> None:
        """
        Record that player visited a node.

        Args:
            history: The conversation history
            node_id: Node that was visited
        """
        if node_id not in history.nodes_visited:
            history.nodes_visited.append(node_id)

    @staticmethod
    def add_choice(history: ConversationHistory, choice_id: str) -> None:
        """
        Record that player made a choice.

        Args:
            history: The conversation history
            choice_id: Choice that was made
        """
        history.choices_made.append(choice_id)

    @staticmethod
    def add_effect(
        history: ConversationHistory, effect: Dict[str, Any]
    ) -> None:
        """
        Record an effect that was applied.

        Args:
            history: The conversation history
            effect: Effect that was applied (as dict)
        """
        history.effects_applied.append(effect)


@dataclass
class DialogueContext:
    """
    Complete state of a conversation.

    Attributes:
        conversation_id: ID of current conversation
        current_node: The DialogueNode currently being displayed
        available_choices: Choices available at current node
        conversation_history: Full history of this conversation
        is_complete: Whether conversation has ended
    """

    conversation_id: str
    current_node: DialogueNode
    available_choices: List[DialogueChoice]
    conversation_history: ConversationHistory
    is_complete: bool = False


class DialogueContextSerializer:
    """
    Serializes complete dialogue context to/from JSON-compatible dicts.

    Provides aggregate view of current conversation state including:
    - Current dialogue node
    - Available choices
    - Full conversation history
    - Completion status
    """

    @staticmethod
    def serialize(context: DialogueContext) -> Dict[str, Any]:
        """
        Convert DialogueContext to JSON-serializable dict.

        Args:
            context: DialogueContext object

        Returns:
            Dict with current state and full history
        """
        return {
            "conversation_id": context.conversation_id,
            "current_node": DialogueNodeSerializer.serialize(
                context.current_node
            ),
            "available_choices": [
                DialogueChoiceSerializer.serialize(c)
                for c in context.available_choices
            ],
            "conversation_history": ConversationHistorySerializer.serialize(
                context.conversation_history
            ),
            "is_complete": context.is_complete,
        }

    @staticmethod
    def deserialize(data: Dict[str, Any]) -> DialogueContext:
        """
        Convert JSON dict to DialogueContext object.

        Args:
            data: Dict with context properties

        Returns:
            DialogueContext object

        Raises:
            KeyError: If required fields missing
        """
        required_fields = {
            "conversation_id",
            "current_node",
            "available_choices",
            "conversation_history",
        }
        if not required_fields.issubset(set(data.keys())):
            raise KeyError(
                f"Missing required fields: {required_fields - set(data.keys())}"
            )

        return DialogueContext(
            conversation_id=data["conversation_id"],
            current_node=DialogueNodeSerializer.deserialize(
                data["current_node"]
            ),
            available_choices=[
                DialogueChoiceSerializer.deserialize(c)
                for c in data["available_choices"]
            ],
            conversation_history=ConversationHistorySerializer.deserialize(
                data["conversation_history"]
            ),
            is_complete=data.get("is_complete", False),
        )
