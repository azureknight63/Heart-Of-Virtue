"""
Coverage tests for src/api/serializers/dialogue_context.py

Targets uncovered lines:
  90, 112-121, 173, 193, 238-267, 312, 338-352, 383-395,
  470-484, 599-611, 644, 655, 726-737

No Flask needed — pure dataclass/serializer unit tests.
"""

import pytest
from src.api.serializers.dialogue_context import (
    ConversationHistory,
    ConversationHistorySerializer,
    DialogueChoice,
    DialogueChoiceSerializer,
    DialogueCondition,
    DialogueConditionSerializer,
    DialogueContext,
    DialogueContextSerializer,
    DialogueEffect,
    DialogueEffectSerializer,
    DialogueEffectType,
    DialogueNode,
    DialogueNodeSerializer,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _effect(effect_type="story_gate", target="gate_1", value=True, description=""):
    return DialogueEffect(
        effect_type=effect_type, target=target, value=value, description=description
    )


def _condition(
    required_gates=None,
    forbidden_gates=None,
    min_rep=None,
    max_rep=None,
    required_dialogues=None,
    min_level=None,
):
    return DialogueCondition(
        required_story_gates=required_gates or [],
        forbidden_story_gates=forbidden_gates or [],
        min_reputation=min_rep,
        max_reputation=max_rep,
        required_completed_dialogues=required_dialogues or [],
        min_player_level=min_level,
    )


def _choice(
    choice_id="c1", text="Hello", target_node="node_2", condition=None, effects=None
):
    return DialogueChoice(
        choice_id=choice_id,
        text=text,
        target_node_id=target_node,
        condition=condition,
        effects=effects or [],
    )


def _node(
    node_id="n1",
    text="NPC speaks",
    speaker="Guard",
    tone="neutral",
    choices=None,
    condition=None,
):
    return DialogueNode(
        node_id=node_id,
        text=text,
        speaker=speaker,
        npc_tone=tone,
        choices=choices or [],
        condition=condition,
    )


def _history(
    conv_id="conv_1",
    npc_id="guard",
    player_id="jean",
    dialogue_id="dlg_1",
    started_at="2026-01-01T00:00:00",
):
    return ConversationHistory(
        conversation_id=conv_id,
        npc_id=npc_id,
        player_id=player_id,
        dialogue_id=dialogue_id,
        started_at=started_at,
    )


def _context(conv_id="ctx_1", node=None, choices=None, history=None, is_complete=False):
    node = node or _node()
    history = history or _history()
    return DialogueContext(
        conversation_id=conv_id,
        current_node=node,
        available_choices=choices or [],
        conversation_history=history,
        is_complete=is_complete,
    )


# ===========================================================================
# DialogueEffectSerializer
# ===========================================================================


class TestDialogueEffectSerializer:
    def test_serialize_basic(self):
        e = _effect(description="Opens the door")
        result = DialogueEffectSerializer.serialize(e)
        assert result["effect_type"] == "story_gate"
        assert result["target"] == "gate_1"
        assert result["value"] is True
        assert result["description"] == "Opens the door"

    def test_serialize_without_description(self):
        e = _effect()
        result = DialogueEffectSerializer.serialize(e)
        assert result["description"] == ""

    def test_serialize_reputation_effect(self):
        e = _effect(effect_type="reputation", target="guard_npc", value=10)
        result = DialogueEffectSerializer.serialize(e)
        assert result["effect_type"] == "reputation"
        assert result["value"] == 10

    def test_deserialize_valid(self):
        data = {
            "effect_type": "reputation",
            "target": "guard_npc",
            "value": 5,
            "description": "Gained trust",
        }
        e = DialogueEffectSerializer.deserialize(data)
        assert e.effect_type == "reputation"
        assert e.target == "guard_npc"
        assert e.value == 5
        assert e.description == "Gained trust"

    def test_deserialize_missing_required_fields_raises(self):
        # Missing 'value' — should raise KeyError (line 112-121)
        data = {"effect_type": "story_gate", "target": "gate_1"}
        with pytest.raises(KeyError):
            DialogueEffectSerializer.deserialize(data)

    def test_deserialize_missing_effect_type_raises(self):
        data = {"target": "gate_1", "value": True}
        with pytest.raises(KeyError):
            DialogueEffectSerializer.deserialize(data)

    def test_deserialize_missing_target_raises(self):
        data = {"effect_type": "story_gate", "value": True}
        with pytest.raises(KeyError):
            DialogueEffectSerializer.deserialize(data)

    def test_deserialize_unknown_effect_type_raises(self):
        # Line 118-119
        data = {"effect_type": "unknown_type", "target": "x", "value": 1}
        with pytest.raises(ValueError, match="Unknown effect_type"):
            DialogueEffectSerializer.deserialize(data)

    def test_deserialize_no_description_defaults_empty(self):
        data = {"effect_type": "item_reward", "target": "potion", "value": 2}
        e = DialogueEffectSerializer.deserialize(data)
        assert e.description == ""

    @pytest.mark.parametrize("etype", [e.value for e in DialogueEffectType])
    def test_deserialize_all_valid_effect_types(self, etype):
        data = {"effect_type": etype, "target": "t", "value": 1}
        e = DialogueEffectSerializer.deserialize(data)
        assert e.effect_type == etype

    def test_roundtrip(self):
        original = _effect(
            effect_type="quest_progress",
            target="q1",
            value="step_2",
            description="Quest advances",
        )
        serialized = DialogueEffectSerializer.serialize(original)
        restored = DialogueEffectSerializer.deserialize(serialized)
        assert restored.effect_type == original.effect_type
        assert restored.target == original.target
        assert restored.value == original.value
        assert restored.description == original.description


# ===========================================================================
# DialogueConditionSerializer
# ===========================================================================


class TestDialogueConditionSerializer:
    def test_serialize_empty_condition(self):
        cond = _condition()
        result = DialogueConditionSerializer.serialize(cond)
        assert result["required_story_gates"] == []
        assert result["forbidden_story_gates"] == []
        assert result["min_reputation"] is None
        assert result["max_reputation"] is None
        assert result["required_completed_dialogues"] == []
        assert result["min_player_level"] is None

    def test_serialize_full_condition(self):
        cond = _condition(
            required_gates=["gate_a"],
            forbidden_gates=["gate_b"],
            min_rep=10,
            max_rep=100,
            required_dialogues=["dlg_intro"],
            min_level=5,
        )
        result = DialogueConditionSerializer.serialize(cond)
        assert result["required_story_gates"] == ["gate_a"]
        assert result["min_reputation"] == 10
        assert result["min_player_level"] == 5

    def test_deserialize_minimal(self):
        data = {}
        cond = DialogueConditionSerializer.deserialize(data)
        assert cond.required_story_gates == []
        assert cond.min_reputation is None

    def test_deserialize_full(self):
        data = {
            "required_story_gates": ["gate_x"],
            "forbidden_story_gates": ["gate_y"],
            "min_reputation": 20,
            "max_reputation": 80,
            "required_completed_dialogues": ["d1", "d2"],
            "min_player_level": 3,
        }
        cond = DialogueConditionSerializer.deserialize(data)
        assert cond.required_story_gates == ["gate_x"]
        assert cond.forbidden_story_gates == ["gate_y"]
        assert cond.min_reputation == 20
        assert cond.min_player_level == 3

    # check_conditions tests (lines 238-267)

    def test_check_conditions_all_pass(self):
        cond = _condition(required_gates=["gate_a"])
        ok, reason = DialogueConditionSerializer.check_conditions(
            cond, {"gate_a": True}, {}, 5, []
        )
        assert ok is True
        assert reason is None

    def test_check_conditions_required_gate_not_set(self):
        cond = _condition(required_gates=["gate_a"])
        ok, reason = DialogueConditionSerializer.check_conditions(
            cond, {"gate_a": False}, {}, 1, []
        )
        assert ok is False
        assert "gate_a" in reason

    def test_check_conditions_required_gate_missing_key(self):
        cond = _condition(required_gates=["missing_gate"])
        ok, reason = DialogueConditionSerializer.check_conditions(cond, {}, {}, 1, [])
        assert ok is False

    def test_check_conditions_forbidden_gate_is_set(self):
        cond = _condition(forbidden_gates=["evil_gate"])
        ok, reason = DialogueConditionSerializer.check_conditions(
            cond, {"evil_gate": True}, {}, 1, []
        )
        assert ok is False
        assert "evil_gate" in reason

    def test_check_conditions_forbidden_gate_not_set_passes(self):
        cond = _condition(forbidden_gates=["evil_gate"])
        ok, reason = DialogueConditionSerializer.check_conditions(
            cond, {"evil_gate": False}, {}, 1, []
        )
        assert ok is True

    def test_check_conditions_prerequisite_missing(self):
        cond = _condition(required_dialogues=["dlg_intro"])
        ok, reason = DialogueConditionSerializer.check_conditions(cond, {}, {}, 1, [])
        assert ok is False
        assert "dlg_intro" in reason

    def test_check_conditions_prerequisite_present(self):
        cond = _condition(required_dialogues=["dlg_intro"])
        ok, reason = DialogueConditionSerializer.check_conditions(
            cond, {}, {}, 1, ["dlg_intro"]
        )
        assert ok is True

    def test_check_conditions_level_too_low(self):
        cond = _condition(min_level=10)
        ok, reason = DialogueConditionSerializer.check_conditions(cond, {}, {}, 5, [])
        assert ok is False
        assert "10" in reason

    def test_check_conditions_level_sufficient(self):
        cond = _condition(min_level=5)
        ok, reason = DialogueConditionSerializer.check_conditions(cond, {}, {}, 5, [])
        assert ok is True

    def test_check_conditions_no_requirements(self):
        cond = _condition()
        ok, reason = DialogueConditionSerializer.check_conditions(cond, {}, {}, 1, [])
        assert ok is True
        assert reason is None

    def test_roundtrip(self):
        original = _condition(
            required_gates=["g1"],
            forbidden_gates=["g2"],
            min_rep=5,
            max_rep=50,
            required_dialogues=["d1"],
            min_level=2,
        )
        serialized = DialogueConditionSerializer.serialize(original)
        restored = DialogueConditionSerializer.deserialize(serialized)
        assert restored.required_story_gates == ["g1"]
        assert restored.min_reputation == 5
        assert restored.min_player_level == 2


# ===========================================================================
# DialogueChoiceSerializer
# ===========================================================================


class TestDialogueChoiceSerializer:
    def test_serialize_no_condition_no_effects(self):
        c = _choice()
        result = DialogueChoiceSerializer.serialize(c)
        assert result["choice_id"] == "c1"
        assert result["text"] == "Hello"
        assert result["target_node_id"] == "node_2"
        assert result["condition"] is None
        assert result["effects"] == []

    def test_serialize_with_condition(self):
        cond = _condition(required_gates=["gate_x"])
        c = _choice(condition=cond)
        result = DialogueChoiceSerializer.serialize(c)
        assert result["condition"] is not None
        assert result["condition"]["required_story_gates"] == ["gate_x"]

    def test_serialize_with_effects(self):
        effects = [_effect(description="door opens")]
        c = _choice(effects=effects)
        result = DialogueChoiceSerializer.serialize(c)
        assert len(result["effects"]) == 1
        assert result["effects"][0]["description"] == "door opens"

    def test_deserialize_minimal(self):
        data = {"choice_id": "c2", "text": "Go away", "target_node_id": "end"}
        c = DialogueChoiceSerializer.deserialize(data)
        assert c.choice_id == "c2"
        assert c.condition is None
        assert c.effects == []

    def test_deserialize_missing_required_fields_raises(self):
        # Line 338-341
        data = {"choice_id": "c3", "text": "Hi"}
        with pytest.raises(KeyError):
            DialogueChoiceSerializer.deserialize(data)

    def test_deserialize_with_condition(self):
        data = {
            "choice_id": "c4",
            "text": "Test",
            "target_node_id": "n2",
            "condition": {"required_story_gates": ["gate_a"]},
        }
        c = DialogueChoiceSerializer.deserialize(data)
        assert c.condition is not None
        assert c.condition.required_story_gates == ["gate_a"]

    def test_deserialize_with_effects(self):
        data = {
            "choice_id": "c5",
            "text": "Attack",
            "target_node_id": "combat",
            "effects": [{"effect_type": "reputation", "target": "guard", "value": -5}],
        }
        c = DialogueChoiceSerializer.deserialize(data)
        assert len(c.effects) == 1
        assert c.effects[0].effect_type == "reputation"

    def test_filter_available_all_unconditioned(self):
        choices = [_choice("c1"), _choice("c2"), _choice("c3")]
        result = DialogueChoiceSerializer.filter_available_choices(
            choices, {}, {}, 1, []
        )
        assert len(result) == 3

    def test_filter_available_condition_not_met(self):
        cond = _condition(required_gates=["gate_locked"])
        gated_choice = _choice(condition=cond)
        free_choice = _choice("c2")
        result = DialogueChoiceSerializer.filter_available_choices(
            [gated_choice, free_choice], {"gate_locked": False}, {}, 1, []
        )
        assert len(result) == 1
        assert result[0].choice_id == "c2"

    def test_filter_available_condition_met(self):
        cond = _condition(required_gates=["gate_unlocked"])
        gated_choice = _choice(condition=cond)
        result = DialogueChoiceSerializer.filter_available_choices(
            [gated_choice], {"gate_unlocked": True}, {}, 1, []
        )
        assert len(result) == 1

    def test_roundtrip_no_condition(self):
        original = _choice("c9", "Goodbye", "end")
        serialized = DialogueChoiceSerializer.serialize(original)
        restored = DialogueChoiceSerializer.deserialize(serialized)
        assert restored.choice_id == "c9"
        assert restored.text == "Goodbye"
        assert restored.target_node_id == "end"


# ===========================================================================
# DialogueNodeSerializer
# ===========================================================================


class TestDialogueNodeSerializer:
    def test_serialize_minimal_node(self):
        n = _node()
        result = DialogueNodeSerializer.serialize(n)
        assert result["node_id"] == "n1"
        assert result["text"] == "NPC speaks"
        assert result["speaker"] == "Guard"
        assert result["npc_tone"] == "neutral"
        assert result["choices"] == []
        assert result["condition"] is None

    def test_serialize_node_with_condition(self):
        cond = _condition(required_gates=["g1"])
        n = _node(condition=cond)
        result = DialogueNodeSerializer.serialize(n)
        assert result["condition"] is not None

    def test_serialize_node_with_choices(self):
        choices = [_choice("c1"), _choice("c2", text="Leave")]
        n = _node(choices=choices)
        result = DialogueNodeSerializer.serialize(n)
        assert len(result["choices"]) == 2

    def test_deserialize_minimal(self):
        data = {"node_id": "n2", "text": "Hello traveller", "speaker": "Merchant"}
        n = DialogueNodeSerializer.deserialize(data)
        assert n.node_id == "n2"
        assert n.npc_tone == "neutral"
        assert n.choices == []
        assert n.condition is None

    def test_deserialize_missing_required_fields_raises(self):
        # Lines 470-473
        data = {"node_id": "n3", "text": "Missing speaker"}
        with pytest.raises(KeyError):
            DialogueNodeSerializer.deserialize(data)

    def test_deserialize_with_choices(self):
        data = {
            "node_id": "n4",
            "text": "What do you need?",
            "speaker": "Inn Keeper",
            "choices": [
                {"choice_id": "ch1", "text": "A room", "target_node_id": "room"}
            ],
        }
        n = DialogueNodeSerializer.deserialize(data)
        assert len(n.choices) == 1
        assert n.choices[0].choice_id == "ch1"

    def test_deserialize_with_condition(self):
        data = {
            "node_id": "n5",
            "text": "Secret passage?",
            "speaker": "Guard",
            "condition": {"required_story_gates": ["ch01_key_found"]},
        }
        n = DialogueNodeSerializer.deserialize(data)
        assert n.condition is not None
        assert n.condition.required_story_gates == ["ch01_key_found"]

    def test_deserialize_custom_tone(self):
        data = {
            "node_id": "n6",
            "text": "How dare you!",
            "speaker": "Knight",
            "npc_tone": "hostile",
        }
        n = DialogueNodeSerializer.deserialize(data)
        assert n.npc_tone == "hostile"

    def test_get_available_choices_no_conditions(self):
        choices = [_choice("c1"), _choice("c2")]
        n = _node(choices=choices)
        result = DialogueNodeSerializer.get_available_choices(n, {}, {}, 1, [])
        assert len(result) == 2

    def test_get_available_choices_filtered(self):
        cond = _condition(required_gates=["gate_pass"])
        locked_choice = _choice("locked", condition=cond)
        free_choice = _choice("free")
        n = _node(choices=[locked_choice, free_choice])
        result = DialogueNodeSerializer.get_available_choices(
            n, {"gate_pass": False}, {}, 1, []
        )
        assert len(result) == 1
        assert result[0].choice_id == "free"

    def test_roundtrip(self):
        original = _node("n99", "Final test", "Boss", tone="menacing")
        serialized = DialogueNodeSerializer.serialize(original)
        restored = DialogueNodeSerializer.deserialize(serialized)
        assert restored.node_id == "n99"
        assert restored.npc_tone == "menacing"


# ===========================================================================
# ConversationHistorySerializer
# ===========================================================================


class TestConversationHistorySerializer:
    def test_serialize(self):
        h = _history()
        result = ConversationHistorySerializer.serialize(h)
        assert result["conversation_id"] == "conv_1"
        assert result["npc_id"] == "guard"
        assert result["player_id"] == "jean"
        assert result["nodes_visited"] == []
        assert result["choices_made"] == []
        assert result["effects_applied"] == []
        assert result["status"] == "ongoing"

    def test_deserialize_minimal(self):
        data = {
            "conversation_id": "c1",
            "npc_id": "npc_a",
            "player_id": "jean",
            "dialogue_id": "dlg_x",
            "started_at": "2026-01-01",
        }
        h = ConversationHistorySerializer.deserialize(data)
        assert h.conversation_id == "c1"
        assert h.nodes_visited == []
        assert h.status == "ongoing"

    def test_deserialize_missing_required_fields_raises(self):
        # Lines 599-609
        data = {
            "conversation_id": "c1",
            "npc_id": "npc_a",
            # missing player_id, dialogue_id, started_at
        }
        with pytest.raises(KeyError):
            ConversationHistorySerializer.deserialize(data)

    def test_deserialize_full(self):
        data = {
            "conversation_id": "c2",
            "npc_id": "amelia",
            "player_id": "jean",
            "dialogue_id": "ch01_amelia",
            "started_at": "2026-01-01T12:00:00",
            "nodes_visited": ["n1", "n2"],
            "choices_made": ["c1"],
            "effects_applied": [
                {"effect_type": "reputation", "target": "amelia", "value": 5}
            ],
            "status": "completed",
        }
        h = ConversationHistorySerializer.deserialize(data)
        assert h.nodes_visited == ["n1", "n2"]
        assert h.status == "completed"

    def test_add_node_visit_new(self):
        h = _history()
        ConversationHistorySerializer.add_node_visit(h, "node_x")
        assert "node_x" in h.nodes_visited

    def test_add_node_visit_duplicate_ignored(self):
        h = _history()
        ConversationHistorySerializer.add_node_visit(h, "node_x")
        ConversationHistorySerializer.add_node_visit(h, "node_x")
        assert h.nodes_visited.count("node_x") == 1

    def test_add_choice(self):
        h = _history()
        ConversationHistorySerializer.add_choice(h, "choice_a")
        ConversationHistorySerializer.add_choice(h, "choice_b")
        assert "choice_a" in h.choices_made
        assert "choice_b" in h.choices_made

    def test_add_choice_allows_duplicates(self):
        # Line 644 — add_choice appends (no dedup)
        h = _history()
        ConversationHistorySerializer.add_choice(h, "same_choice")
        ConversationHistorySerializer.add_choice(h, "same_choice")
        assert h.choices_made.count("same_choice") == 2

    def test_add_effect(self):
        # Line 655
        h = _history()
        effect_data = {"effect_type": "reputation", "target": "guard", "value": 10}
        ConversationHistorySerializer.add_effect(h, effect_data)
        assert len(h.effects_applied) == 1
        assert h.effects_applied[0]["value"] == 10

    def test_roundtrip(self):
        original = _history("conv_rt", "npc_x", "jean", "dlg_rt", "2026-06-01")
        original.nodes_visited = ["n1", "n2"]
        original.choices_made = ["c1"]
        original.status = "completed"
        serialized = ConversationHistorySerializer.serialize(original)
        restored = ConversationHistorySerializer.deserialize(serialized)
        assert restored.conversation_id == "conv_rt"
        assert restored.status == "completed"
        assert restored.nodes_visited == ["n1", "n2"]


# ===========================================================================
# DialogueContextSerializer
# ===========================================================================


class TestDialogueContextSerializer:
    def test_serialize_basic(self):
        ctx = _context()
        result = DialogueContextSerializer.serialize(ctx)
        assert result["conversation_id"] == "ctx_1"
        assert "current_node" in result
        assert "available_choices" in result
        assert "conversation_history" in result
        assert result["is_complete"] is False

    def test_serialize_complete_context(self):
        ctx = _context(is_complete=True)
        result = DialogueContextSerializer.serialize(ctx)
        assert result["is_complete"] is True

    def test_serialize_with_choices(self):
        choices = [_choice("c1"), _choice("c2", text="Leave")]
        ctx = _context(choices=choices)
        result = DialogueContextSerializer.serialize(ctx)
        assert len(result["available_choices"]) == 2

    def test_deserialize_valid(self):
        ctx = _context()
        serialized = DialogueContextSerializer.serialize(ctx)
        restored = DialogueContextSerializer.deserialize(serialized)
        assert restored.conversation_id == "ctx_1"
        assert restored.is_complete is False

    def test_deserialize_missing_required_fields_raises(self):
        # Lines 726-735
        data = {
            "conversation_id": "x",
            "current_node": {
                "node_id": "n1",
                "text": "Hi",
                "speaker": "Guard",
            },
            # missing available_choices, conversation_history
        }
        with pytest.raises(KeyError):
            DialogueContextSerializer.deserialize(data)

    def test_deserialize_is_complete_defaults_false(self):
        ctx = _context()
        serialized = DialogueContextSerializer.serialize(ctx)
        # Remove is_complete to test default
        del serialized["is_complete"]
        restored = DialogueContextSerializer.deserialize(serialized)
        assert restored.is_complete is False

    def test_roundtrip_with_nested_data(self):
        effects = [
            _effect(effect_type="npc_state_change", target="amelia", value="happy")
        ]
        choices = [_choice("c1", effects=effects)]
        node = _node(
            "start", "Welcome Jean", "Amelia", tone="friendly", choices=choices
        )
        history = _history("conv_full", "amelia", "jean", "ch01_dlg", "2026-01-01")
        history.nodes_visited = ["start"]
        history.choices_made = ["c1"]
        ctx = DialogueContext(
            conversation_id="conv_full",
            current_node=node,
            available_choices=choices,
            conversation_history=history,
            is_complete=False,
        )
        serialized = DialogueContextSerializer.serialize(ctx)
        restored = DialogueContextSerializer.deserialize(serialized)
        assert restored.conversation_id == "conv_full"
        assert len(restored.available_choices) == 1
        assert restored.current_node.npc_tone == "friendly"
