"""
Coverage tests for src/api/serializers/npc_ai.py

Targets uncovered lines: 82, 218, 307, 370-371, 426

Fast win — 6 lines, mostly branch paths in helper methods.
"""

from unittest.mock import MagicMock
from src.api.serializers.npc_ai import (
    DialogueStateSerializer,
    NPCAIStateSerializer,
    NPCBehaviorProfileSerializer,
    QuestStateSerializer,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _npc(**kwargs):
    n = MagicMock()
    n.name = kwargs.get("name", "TestNPC")
    n.hp = kwargs.get("hp", 80)
    n.maxhp = kwargs.get("maxhp", 100)
    n.in_combat = kwargs.get("in_combat", False)
    n.current_behavior = kwargs.get("current_behavior", "idle")
    n.behavior_stack = kwargs.get("behavior_stack", [])
    n.last_interaction_time = kwargs.get("last_interaction_time", None)
    n.x = kwargs.get("x", 0)
    n.y = kwargs.get("y", 0)

    # Optional attributes — delete them to test hasattr fallbacks
    for attr in [
        "mood",
        "aggression",
        "trust",
        "memory",
        "dialogue_flags",
        "player_knows_npc",
        "personality_archetype",
        "personality_traits",
        "intelligence",
        "courage",
        "friendliness",
        "idle_behavior",
        "combat_behavior",
        "social_behavior",
        "response_type",
        "combat_preference",
        "defense_priority",
        "flee_at_health_percent",
        "likes",
        "dislikes",
        "fears",
        "desires",
        "friends",
        "enemies",
        "neutral_npcs",
        "reputation",
        "combat_skill",
        "magic_skill",
        "stealth_skill",
        "persuasion_skill",
        "tracking_skill",
    ]:
        if attr not in kwargs:
            # Remove mock auto-attribute so hasattr returns False
            try:
                delattr(n, attr)
            except AttributeError:
                pass
    for attr, val in kwargs.items():
        setattr(n, attr, val)
    return n


def _player(**kwargs):
    p = MagicMock()
    p.active_quests = kwargs.get("active_quests", [])
    p.completed_quests = kwargs.get("completed_quests", [])
    return p


# ===========================================================================
# NPCAIStateSerializer
# ===========================================================================


class TestNPCAIStateSerializer:
    def test_serialize_healthy_idle_npc(self):
        npc = _npc()
        result = NPCAIStateSerializer.serialize_npc_ai_state(npc)
        assert result["npc_id"] == "TestNPC"
        assert result["current_behavior"] == "idle"
        assert result["emotion_state"] == "neutral"
        assert result["aggression_level"] == 0.5
        assert result["trust_level"] == 0.5
        assert result["memory"] == []

    def test_serialize_npc_in_combat(self):
        npc = _npc(in_combat=True)
        result = NPCAIStateSerializer.serialize_npc_ai_state(npc)
        assert result["emotion_state"] == "angry"
        assert result["aggression_level"] == 1.0

    def test_serialize_npc_low_hp_fearful(self):
        # hp < 30% of maxhp → fearful  (line 82 branch)
        npc = _npc(hp=20, maxhp=100)
        result = NPCAIStateSerializer.serialize_npc_ai_state(npc)
        assert result["emotion_state"] == "fearful"

    def test_serialize_npc_with_mood(self):
        npc = _npc(mood="happy")
        result = NPCAIStateSerializer.serialize_npc_ai_state(npc)
        assert result["emotion_state"] == "happy"

    def test_serialize_npc_with_aggression(self):
        npc = _npc(aggression=0.8)
        result = NPCAIStateSerializer.serialize_npc_ai_state(npc)
        assert result["aggression_level"] == 0.8

    def test_serialize_npc_with_trust(self):
        npc = _npc(trust=0.9)
        result = NPCAIStateSerializer.serialize_npc_ai_state(npc)
        assert result["trust_level"] == 0.9

    def test_serialize_npc_with_memory(self):
        memory = [
            {
                "event": "met_player",
                "timestamp": "2026-01-01",
                "context": "dungeon",
                "importance": 0.7,
            }
        ]
        npc = _npc(memory=memory)
        result = NPCAIStateSerializer.serialize_npc_ai_state(npc)
        assert len(result["memory"]) == 1
        assert result["memory"][0]["event"] == "met_player"

    def test_serialize_npc_memory_limited_to_10(self):
        memory = [
            {"event": f"event_{i}", "timestamp": None, "context": "", "importance": 0.5}
            for i in range(15)
        ]
        npc = _npc(memory=memory)
        result = NPCAIStateSerializer.serialize_npc_ai_state(npc)
        assert len(result["memory"]) == 10

    def test_serialize_npc_list(self):
        npcs = [_npc(name="Guard"), _npc(name="Merchant")]
        result = NPCAIStateSerializer.serialize_npc_list(npcs)
        assert len(result) == 2
        assert result[0]["name"] == "Guard"
        assert result[1]["name"] == "Merchant"

    def test_health_status_wounded(self):
        npc = _npc(hp=30, maxhp=100)
        result = NPCAIStateSerializer.serialize_npc_ai_state(npc)
        assert result["health_status"]["status"] == "wounded"

    def test_health_status_healthy(self):
        npc = _npc(hp=80, maxhp=100)
        result = NPCAIStateSerializer.serialize_npc_ai_state(npc)
        assert result["health_status"]["status"] == "healthy"


# ===========================================================================
# DialogueStateSerializer
# ===========================================================================


class TestDialogueStateSerializer:
    def test_serialize_dialogue_state_default_tree(self):
        npc = _npc(name="Amelia")
        result = DialogueStateSerializer.serialize_dialogue_state(npc)
        assert result["npc_id"] == "Amelia"
        assert result["current_node"] == "start"
        assert "options" in result
        assert "conversation_history" in result

    def test_serialize_dialogue_state_custom_tree(self):
        npc = _npc()
        tree = {
            "id": "custom_tree",
            "nodes": {
                "start": {"text": "Custom greeting", "options": []},
            },
        }
        result = DialogueStateSerializer.serialize_dialogue_state(
            npc, dialogue_tree=tree
        )
        assert result["dialogue_tree"] == "custom_tree"

    def test_serialize_dialogue_state_custom_node(self):
        npc = _npc()
        tree = {
            "id": "t1",
            "nodes": {
                "start": {"text": "Hello", "options": []},
                "backstory": {"text": "My story", "options": []},
            },
        }
        result = DialogueStateSerializer.serialize_dialogue_state(
            npc, dialogue_tree=tree, current_node="backstory"
        )
        assert result["current_node"] == "backstory"
        assert result["current_text"] == "My story"

    def test_serialize_dialogue_state_with_history(self):
        npc = _npc()
        history = [
            {"player": "Hi", "npc": "Hello"},
            {"player": "Bye", "npc": "Farewell"},
        ]
        result = DialogueStateSerializer.serialize_dialogue_state(
            npc, conversation_history=history
        )
        assert len(result["conversation_history"]) == 2

    def test_serialize_dialogue_state_history_truncated_to_5(self):
        npc = _npc()
        history = [{"player": f"msg {i}", "npc": f"resp {i}"} for i in range(10)]
        result = DialogueStateSerializer.serialize_dialogue_state(
            npc, conversation_history=history
        )
        assert len(result["conversation_history"]) == 5

    def test_serialize_dialogue_options(self):
        npc = _npc(name="Guard")
        result = DialogueStateSerializer.serialize_dialogue_options(npc)
        assert result["npc_id"] == "Guard"
        assert "options" in result
        assert "current_text" in result

    def test_serialize_dialogue_options_custom_tree(self):
        # Line 218 branch: dialogue_tree provided
        npc = _npc()
        tree = {
            "id": "custom",
            "nodes": {
                "start": {
                    "text": "Need something?",
                    "options": [{"id": 1, "text": "Yes", "next": "help"}],
                }
            },
        }
        result = DialogueStateSerializer.serialize_dialogue_options(
            npc, dialogue_tree=tree, current_node="start"
        )
        assert result["current_text"] == "Need something?"
        assert len(result["options"]) == 1

    def test_npc_with_player_knows_npc(self):
        npc = _npc(player_knows_npc=True)
        result = DialogueStateSerializer.serialize_dialogue_state(npc)
        assert result["relationship"]["known"] is True

    def test_npc_with_trust_attribute(self):
        npc = _npc(trust=0.75)
        result = DialogueStateSerializer.serialize_dialogue_state(npc)
        assert result["relationship"]["trust"] == 0.75

    def test_get_node_text_missing_node(self):
        tree = {"nodes": {"start": {"text": "Hi", "options": []}}}
        text = DialogueStateSerializer._get_node_text(tree, "nonexistent")
        assert text == "..."

    def test_get_dialogue_options_missing_node(self):
        tree = {"nodes": {}}
        opts = DialogueStateSerializer._get_dialogue_options(tree, "start")
        assert opts == []


# ===========================================================================
# QuestStateSerializer
# ===========================================================================


class TestQuestStateSerializer:
    def _quest(self, **kwargs):
        base = {
            "id": "q1",
            "title": "Find the Sword",
            "description": "Search the dungeon",
            "status": "active",
            "progress": 0,
            "objectives": [],
            "rewards": {"gold": 100},
            "started_at": None,
            "completed_at": None,
            "deadline": None,
            "giver": "Old Man",
            "tags": ["main"],
            "can_abandon": True,
        }
        base.update(kwargs)
        return base

    def test_serialize_basic_quest(self):
        quest = self._quest()
        result = QuestStateSerializer.serialize_quest(quest)
        assert result["quest_id"] == "q1"
        assert result["title"] == "Find the Sword"
        assert result["status"] == "active"
        assert result["objectives"] == []

    def test_serialize_quest_with_objectives(self):
        objectives = [
            {
                "id": "o1",
                "text": "Enter dungeon",
                "completed": True,
                "progress": 1,
                "type": "explore",
            },
            {
                "id": "o2",
                "text": "Find sword",
                "completed": False,
                "progress": 0,
                "type": "collect",
            },
        ]
        quest = self._quest(objectives=objectives)
        result = QuestStateSerializer.serialize_quest(quest)
        assert len(result["objectives"]) == 2
        assert result["objectives"][0]["completed"] is True

    def test_serialize_active_quests_empty(self):
        player = _player()
        result = QuestStateSerializer.serialize_active_quests(player)
        assert result == []

    def test_serialize_active_quests_populated(self):
        quests = [self._quest(id="q1"), self._quest(id="q2", title="Another Quest")]
        player = _player(active_quests=quests)
        result = QuestStateSerializer.serialize_active_quests(player)
        assert len(result) == 2

    def test_serialize_completed_quests(self):
        # Lines 370-371
        quests = [self._quest(id="done_1", status="completed")]
        player = _player(completed_quests=quests)
        result = QuestStateSerializer.serialize_completed_quests(player)
        assert len(result) == 1
        assert result[0]["status"] == "completed"

    def test_serialize_completed_quests_empty(self):
        player = _player(completed_quests=[])
        result = QuestStateSerializer.serialize_completed_quests(player)
        assert result == []

    def test_serialize_quest_progress(self):
        objectives = [
            {"completed": True},
            {"completed": False},
            {"completed": True},
        ]
        quest = self._quest(
            objectives=objectives,
            progress=66,
            current_step="Search room",
            next_step="Fight boss",
        )
        result = QuestStateSerializer.serialize_quest_progress(quest)
        assert result["objectives_completed"] == 2
        assert result["objectives_total"] == 3
        assert result["progress"] == 66

    def test_serialize_quest_progress_no_started_at(self):
        quest = self._quest(started_at=None)
        result = QuestStateSerializer.serialize_quest_progress(quest)
        assert result["time_elapsed"] is None

    def test_serialize_quest_progress_with_started_at(self):
        quest = self._quest(started_at="2026-01-01T12:00:00")
        result = QuestStateSerializer.serialize_quest_progress(quest)
        assert result["time_elapsed"] == 0.0

    def test_serialize_objectives_defaults(self):
        objectives = [{}]  # Empty dict — all defaults
        result = QuestStateSerializer._serialize_objectives(objectives)
        assert result[0]["id"] == "obj_0"
        assert result[0]["text"] == "Unknown"
        assert result[0]["completed"] is False
        assert result[0]["type"] == "task"


# ===========================================================================
# NPCBehaviorProfileSerializer
# ===========================================================================


class TestNPCBehaviorProfileSerializer:
    def test_serialize_behavior_profile_defaults(self):
        npc = _npc()
        result = NPCBehaviorProfileSerializer.serialize_behavior_profile(npc)
        assert result["npc_id"] == "TestNPC"
        assert "personality" in result
        assert "behaviors" in result
        assert "combat_style" in result
        assert "preferences" in result
        assert "relationships" in result
        assert "skills" in result

    def test_get_personality_defaults(self):
        npc = _npc()
        result = NPCBehaviorProfileSerializer._get_personality(npc)
        assert result["archetype"] == "neutral"
        assert result["traits"] == []
        assert result["intelligence"] == 0.5

    def test_get_behaviors_defaults(self):
        npc = _npc()
        result = NPCBehaviorProfileSerializer._get_behaviors(npc)
        assert result["idle_behavior"] == "wander"
        assert result["combat_behavior"] == "aggressive"

    def test_get_combat_style_defaults(self):
        npc = _npc()
        result = NPCBehaviorProfileSerializer._get_combat_style(npc)
        assert result["preference"] == "melee"
        assert result["flee_threshold"] == 0.1

    def test_get_preferences_defaults(self):
        npc = _npc()
        result = NPCBehaviorProfileSerializer._get_preferences(npc)
        assert result["likes"] == []
        assert result["dislikes"] == []

    def test_get_relationships_defaults(self):
        npc = _npc()
        result = NPCBehaviorProfileSerializer._get_relationships(npc)
        assert result["friends"] == []
        assert result["enemies"] == []
        assert result["reputation"] == {}

    def test_get_skills_defaults(self):
        # Line 426 area
        npc = _npc()
        result = NPCBehaviorProfileSerializer._get_skills(npc)
        assert result["combat"] == 0.5
        assert result["magic"] == 0.5
        assert result["stealth"] == 0.5
        assert result["persuasion"] == 0.5
        assert result["tracking"] == 0.5

    def test_serialize_npc_with_custom_attributes(self):
        npc = _npc(
            personality_archetype="warrior",
            personality_traits=["brave", "loyal"],
            combat_preference="ranged",
            aggression=0.9,
            likes=["gold"],
            enemies=["bandits"],
            combat_skill=0.85,
        )
        result = NPCBehaviorProfileSerializer.serialize_behavior_profile(npc)
        assert result["personality"]["archetype"] == "warrior"
        assert result["personality"]["traits"] == ["brave", "loyal"]
        assert result["combat_style"]["preference"] == "ranged"
        assert result["preferences"]["likes"] == ["gold"]
        assert result["skills"]["combat"] == 0.85
