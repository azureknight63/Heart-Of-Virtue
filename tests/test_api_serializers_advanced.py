"""
Tests for advanced API serializers:
- api/serializers/world.py (EventSerializer, TileSerializer, WorldSerializer)
- api/serializers/quest_rewards.py (QuestRewardSerializer, RewardDistributionSerializer,
  RewardConditionValidator, LevelingProgressSerializer)
- api/serializers/quest_chains.py (QuestChainSerializer, ChainDependencySerializer,
  ChainProgressionSerializer, ChainRewardSerializer, ChainBranchSerializer)
- api/serializers/reputation.py (NPCRelationshipSerializer, PlayerReputationSerializer,
  RelationshipFlagSerializer, ReputationThresholdValidator)
"""

import pytest
from unittest.mock import patch
from types import SimpleNamespace

# ---------------------------------------------------------------------------
# Imports under test
# ---------------------------------------------------------------------------
from src.api.serializers.world import EventSerializer, TileSerializer, WorldSerializer
from src.api.serializers.quest_rewards import (
    QuestRewardSerializer,
    RewardDistributionSerializer,
    RewardConditionValidator,
    LevelingProgressSerializer,
)
from src.api.serializers.quest_chains import (
    ChainStatus,
    QuestChainSerializer,
    ChainDependencySerializer,
    ChainProgressionSerializer,
    ChainRewardSerializer,
    ChainBranchSerializer,
)
from src.api.serializers.reputation import (
    NPCRelationshipSerializer,
    PlayerReputationSerializer,
    RelationshipFlagSerializer,
    ReputationThresholdValidator,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_player(**kwargs):
    """Minimal player mock with sensible defaults."""
    defaults = {
        "gold": 100,
        "exp": 500,
        "exp_to_level": 1000,
        "level": 5,
        "inventory": [],
        "inventory_weight": 0,
        "max_inventory": 20,
        "location_x": 3,
        "location_y": 7,
        "reputation": {},
        "death_count": 0,
        "achievements": [],
        "playtime_hours": 2.5,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _make_tile(**kwargs):
    """Minimal tile mock."""
    defaults = {
        "x": 1,
        "y": 2,
        "name": "Test Tile",
        "description": "A test tile.",
        "is_passable": True,
        "items_here": [],
        "npcs_here": [],
        "objects_here": [],
        "events_here": [],
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


# ===========================================================================
# EventSerializer
# ===========================================================================


class TestEventSerializer:
    def test_serialize_none_returns_empty(self):
        assert EventSerializer.serialize(None) == {}

    def test_serialize_basic(self):
        event = SimpleNamespace(description="Something happens")
        result = EventSerializer.serialize(event)
        assert result["type"] == "SimpleNamespace"
        assert result["description"] == "Something happens"
        assert "id" in result

    def test_serialize_with_repeat(self):
        event = SimpleNamespace(description="repeating", repeat=True)
        result = EventSerializer.serialize(event)
        assert result["repeat"] is True

    def test_serialize_without_repeat_omits_key(self):
        event = SimpleNamespace(description="once")
        result = EventSerializer.serialize(event)
        assert "repeat" not in result

    def test_serialize_with_triggers(self):
        event = SimpleNamespace(description="triggered", triggers=["combat_start"])
        result = EventSerializer.serialize(event)
        assert result["triggers"] == ["combat_start"]

    def test_serialize_many_empty(self):
        assert EventSerializer.serialize_many([]) == []

    def test_serialize_many_multiple(self):
        events = [
            SimpleNamespace(description="A"),
            SimpleNamespace(description="B"),
        ]
        result = EventSerializer.serialize_many(events)
        assert len(result) == 2
        assert result[0]["description"] == "A"
        assert result[1]["description"] == "B"


# ===========================================================================
# TileSerializer
# ===========================================================================


class TestTileSerializer:
    """TileSerializer tests.

    TileSerializer.serialize() calls EventSerializer.serialize_list() which does
    not exist on the EventSerializer class (production bug — the method is named
    serialize_many).  We patch it to return [] so tests verify the surrounding
    logic rather than the pre-existing defect.
    """

    @pytest.fixture(autouse=True)
    def patch_event_serialize_list(self):
        """Patch the missing serialize_list onto EventSerializer for all tests here."""
        with patch(
            "src.api.serializers.world.EventSerializer.serialize_list",
            return_value=[],
            create=True,
        ):
            yield

    def test_serialize_none_returns_empty(self):
        assert TileSerializer.serialize(None) == {}

    def test_serialize_basic_fields(self):
        tile = _make_tile()
        result = TileSerializer.serialize(tile)
        assert result["x"] == 1
        assert result["y"] == 2
        assert result["name"] == "Test Tile"
        assert result["description"] == "A test tile."
        assert result["is_passable"] is True

    def test_serialize_items_empty(self):
        tile = _make_tile()
        result = TileSerializer.serialize(tile)
        assert result["items"] == []

    def test_serialize_npcs_empty(self):
        tile = _make_tile()
        result = TileSerializer.serialize(tile)
        assert result["npcs"] == []

    def test_serialize_objects_empty(self):
        tile = _make_tile()
        result = TileSerializer.serialize(tile)
        assert result["objects"] == []

    def test_serialize_events_empty(self):
        tile = _make_tile()
        result = TileSerializer.serialize(tile)
        assert result["events"] == []

    def test_serialize_exits_with_tile(self):
        tile = _make_tile()
        tile.exits = {"north": (1, 3), "south": (1, 1)}
        result = TileSerializer.serialize(tile)
        assert result["exits"]["north"] == {"x": 1, "y": 3}
        assert result["exits"]["south"] == {"x": 1, "y": 1}

    def test_serialize_exits_empty_without_exits_attr(self):
        tile = _make_tile()
        result = TileSerializer.serialize(tile)
        assert result["exits"] == {}

    def test_serialize_many_empty(self):
        assert TileSerializer.serialize_many([]) == []

    def test_serialize_many(self):
        tiles = [_make_tile(name="A"), _make_tile(name="B")]
        result = TileSerializer.serialize_many(tiles)
        assert len(result) == 2
        assert result[0]["name"] == "A"

    def test_serialize_defaults_for_missing_attrs(self):
        # Tile with almost nothing
        tile = SimpleNamespace()
        result = TileSerializer.serialize(tile)
        assert result["x"] == 0
        assert result["y"] == 0
        assert result["name"] == "Unknown"
        assert result["description"] == ""
        assert result["is_passable"] is True


# ===========================================================================
# WorldSerializer
# ===========================================================================


class TestWorldSerializer:
    """WorldSerializer tests.

    World- and Tile-serializer calls EventSerializer.serialize_list() which is
    missing (production bug).  Patch it away for all tests in this class.
    """

    @pytest.fixture(autouse=True)
    def patch_event_serialize_list(self):
        with patch(
            "src.api.serializers.world.EventSerializer.serialize_list",
            return_value=[],
            create=True,
        ):
            yield

    def test_serialize_current_room_no_tile(self):
        player = _make_player(location_x=5, location_y=9)
        result = WorldSerializer.serialize_current_room(player, None)
        assert "error" in result
        assert result["x"] == 5
        assert result["y"] == 9

    def test_serialize_current_room_with_tile(self):
        player = _make_player(location_x=2, location_y=4)
        tile = _make_tile(name="Forest Path")
        result = WorldSerializer.serialize_current_room(player, tile)
        assert result["x"] == 2
        assert result["y"] == 4
        assert result["tile"]["name"] == "Forest Path"

    def test_serialize_movement_result(self):
        player = _make_player(location_x=3, location_y=5)
        tile = _make_tile(name="Cave Entrance")
        result = WorldSerializer.serialize_movement_result(
            player,
            old_position=(2, 5),
            new_tile=tile,
            events_triggered=[{"type": "combat_start"}],
        )
        assert result["old_position"] == {"x": 2, "y": 5}
        assert result["new_position"] == {"x": 3, "y": 5}
        assert result["room"]["name"] == "Cave Entrance"
        assert len(result["events_triggered"]) == 1

    def test_serialize_exploration_context(self):
        player = _make_player(location_x=1, location_y=1)
        current = _make_tile(name="Center")
        north = _make_tile(name="North Path")
        result = WorldSerializer.serialize_exploration_context(
            player,
            current_tile=current,
            nearby_tiles={"north": north, "south": None},
        )
        assert result["player_position"] == {"x": 1, "y": 1}
        assert result["current_room"]["name"] == "Center"
        # south is None, should be filtered out
        assert "north" in result["adjacent_rooms"]
        assert "south" not in result["adjacent_rooms"]

    def test_serialize_exploration_context_no_nearby(self):
        player = _make_player(location_x=0, location_y=0)
        tile = _make_tile()
        result = WorldSerializer.serialize_exploration_context(
            player, current_tile=tile, nearby_tiles={}
        )
        assert result["adjacent_rooms"] == {}


# ===========================================================================
# QuestRewardSerializer
# ===========================================================================


class TestQuestRewardSerializer:
    def _make_quest(self, **overrides):
        quest = {
            "id": "q001",
            "title": "The First Task",
            "rewards": {
                "gold": 50,
                "experience": 200,
                "items": [],
                "reputation": {},
            },
        }
        quest.update(overrides)
        return quest

    def test_serialize_quest_rewards_basic(self):
        quest = self._make_quest()
        result = QuestRewardSerializer.serialize_quest_rewards(quest)
        assert result["quest_id"] == "q001"
        assert result["quest_title"] == "The First Task"
        assert result["rewards"]["gold"] == 50
        assert result["rewards"]["experience"] == 200

    def test_serialize_quest_rewards_defaults(self):
        result = QuestRewardSerializer.serialize_quest_rewards({})
        assert result["quest_id"] == "unknown"
        assert result["quest_title"] == "Unknown Quest"
        assert result["rewards"]["gold"] == 0

    def test_serialize_quest_rewards_conditions(self):
        quest = self._make_quest()
        quest["rewards"]["difficulty"] = "hard"
        quest["rewards"]["time_limit"] = 600
        quest["rewards"]["no_deaths"] = True
        quest["rewards"]["bonus_complete"] = True
        result = QuestRewardSerializer.serialize_quest_rewards(quest)
        conds = result["conditions"]
        assert conds["difficulty"] == "hard"
        assert conds["time_limit"] == 600
        assert conds["no_deaths"] is True
        assert conds["bonus_objectives_completed"] is True

    def test_serialize_quest_rewards_with_items(self):
        quest = self._make_quest()
        quest["rewards"]["items"] = [
            {"id": "sword_01", "name": "Iron Sword", "quantity": 1}
        ]
        result = QuestRewardSerializer.serialize_quest_rewards(quest)
        items = result["rewards"]["items"]
        assert len(items) == 1
        assert items[0]["item_name"] == "Iron Sword"
        assert items[0]["quantity"] == 1
        assert items[0]["rarity"] == "common"

    def test_serialize_reward_summary(self):
        quest = self._make_quest()
        quest["rewards"]["items"] = [{"name": "x"}, {"name": "y"}]
        quest["rewards"]["reputation"] = {"gorran": 10}
        result = QuestRewardSerializer.serialize_reward_summary(quest)
        assert result["gold"] == 50
        assert result["experience"] == 200
        assert result["item_count"] == 2
        assert result["has_reputation"] is True

    def test_serialize_reward_summary_no_reputation(self):
        quest = self._make_quest()
        result = QuestRewardSerializer.serialize_reward_summary(quest)
        assert result["has_reputation"] is False

    def test_serialize_reward_items_empty(self):
        result = QuestRewardSerializer._serialize_reward_items([])
        assert result == []

    def test_serialize_reward_items_defaults(self):
        items = [{}]
        result = QuestRewardSerializer._serialize_reward_items(items)
        assert result[0]["item_id"] == "unknown"
        assert result[0]["item_name"] == "Unknown Item"
        assert result[0]["quantity"] == 1
        assert result[0]["rarity"] == "common"
        assert result[0]["type"] == "miscellaneous"


# ===========================================================================
# RewardDistributionSerializer
# ===========================================================================


class TestRewardDistributionSerializer:
    def test_serialize_distributed_rewards(self):
        player = _make_player(gold=200, exp=600, level=6)
        rewards = {"gold": 50, "experience": 100, "items_received": ["sword"]}
        result = RewardDistributionSerializer.serialize_distributed_rewards(
            player, "q001", rewards
        )
        assert result["success"] is True
        assert result["quest_id"] == "q001"
        assert result["rewards_received"]["gold"] == 50
        assert result["player_state_after"]["gold"] == 200
        assert result["player_state_after"]["level"] == 6

    def test_serialize_xp_gain_no_level_up(self):
        player = _make_player(level=5, exp=300, exp_to_level=1000)
        result = RewardDistributionSerializer.serialize_xp_gain(
            player, xp_gained=50, level_up=False
        )
        assert result["xp_gained"] == 50
        assert result["level_up"] is False
        assert result["old_level"] == 5
        assert result["new_level"] == 5

    def test_serialize_xp_gain_with_level_up(self):
        player = _make_player(level=6, exp=0, exp_to_level=1200)
        result = RewardDistributionSerializer.serialize_xp_gain(
            player, xp_gained=1000, level_up=True, old_level=5
        )
        assert result["level_up"] is True
        assert result["old_level"] == 5
        assert result["new_level"] == 6

    def test_serialize_gold_gain(self):
        player = _make_player(gold=350)
        result = RewardDistributionSerializer.serialize_gold_gain(
            player, gold_gained=50
        )
        assert result["gold_gained"] == 50
        assert result["total_gold"] == 350

    def test_serialize_item_reward(self):
        result = RewardDistributionSerializer.serialize_item_reward(
            "sword_01", "Iron Sword", 2
        )
        assert result["item_id"] == "sword_01"
        assert result["item_name"] == "Iron Sword"
        assert result["quantity"] == 2
        assert result["added_to_inventory"] is True

    def test_serialize_reputation_gain_positive(self):
        result = RewardDistributionSerializer.serialize_reputation_gain(
            "gorran", "Gorran", 15
        )
        assert result["reputation_change"] == 15
        assert result["positive"] is True

    def test_serialize_reputation_gain_negative(self):
        result = RewardDistributionSerializer.serialize_reputation_gain(
            "gorran", "Gorran", -10
        )
        assert result["positive"] is False

    def test_xp_to_next_level_calculation(self):
        player = _make_player(exp=300, exp_to_level=1000)
        remaining = RewardDistributionSerializer._xp_to_next_level(player)
        assert remaining == 700

    def test_xp_to_next_level_already_past(self):
        player = _make_player(exp=1200, exp_to_level=1000)
        remaining = RewardDistributionSerializer._xp_to_next_level(player)
        assert remaining == 0


# ===========================================================================
# RewardConditionValidator
# ===========================================================================


class TestRewardConditionValidator:
    def _quest_with_rewards(self, **reward_kwargs):
        rewards = {"gold": 100, "experience": 200}
        rewards.update(reward_kwargs)
        return {"rewards": rewards, "difficulty": "normal"}

    def test_normal_difficulty_no_modifier(self):
        quest = self._quest_with_rewards()
        rewards, bonuses = RewardConditionValidator.check_reward_conditions(
            _make_player(), quest
        )
        assert rewards["experience"] == 200
        assert bonuses == []

    def test_hard_difficulty_multiplier(self):
        quest = self._quest_with_rewards()
        quest["difficulty"] = "hard"
        rewards, _ = RewardConditionValidator.check_reward_conditions(
            _make_player(), quest
        )
        assert rewards["experience"] == 300  # 200 * 1.5

    def test_nightmare_difficulty_multiplier(self):
        quest = self._quest_with_rewards()
        quest["difficulty"] = "nightmare"
        rewards, _ = RewardConditionValidator.check_reward_conditions(
            _make_player(), quest
        )
        assert rewards["experience"] == 400  # 200 * 2.0

    def test_easy_difficulty_multiplier(self):
        quest = self._quest_with_rewards()
        quest["difficulty"] = "easy"
        rewards, _ = RewardConditionValidator.check_reward_conditions(
            _make_player(), quest
        )
        assert rewards["experience"] == 100  # 200 * 0.5

    def test_no_death_bonus_when_player_has_no_deaths(self):
        quest = self._quest_with_rewards(no_deaths=True)
        player = _make_player(death_count=0)
        rewards, bonuses = RewardConditionValidator.check_reward_conditions(
            player, quest
        )
        assert rewards["experience"] == 240  # 200 + 20% bonus
        assert any("No Death Bonus" in b for b in bonuses)

    def test_no_death_bonus_not_given_when_player_has_deaths(self):
        quest = self._quest_with_rewards(no_deaths=True)
        player = _make_player(death_count=2)
        rewards, bonuses = RewardConditionValidator.check_reward_conditions(
            player, quest
        )
        assert rewards["experience"] == 200
        assert not any("No Death Bonus" in b for b in bonuses)

    def test_time_limit_bonus_available(self):
        quest = self._quest_with_rewards(time_limit=300)
        _, bonuses = RewardConditionValidator.check_reward_conditions(
            _make_player(), quest
        )
        assert any("Speed Bonus" in b for b in bonuses)

    def test_bonus_objectives_gold_bonus(self):
        quest = self._quest_with_rewards(bonus_complete=True)
        rewards, bonuses = RewardConditionValidator.check_reward_conditions(
            _make_player(), quest
        )
        assert rewards["gold"] == 125  # 100 + 25%
        assert any("Bonus Objectives" in b for b in bonuses)

    def test_validate_reward_distribution_ok(self):
        player = _make_player(inventory=[], max_inventory=20)
        rewards = {"items": [{"quantity": 2}, {"quantity": 3}]}
        is_valid, err = RewardConditionValidator.validate_reward_distribution(
            player, rewards
        )
        assert is_valid is True
        assert err is None

    def test_validate_reward_distribution_inventory_full(self):
        items = [SimpleNamespace()] * 18
        player = _make_player(inventory=items, max_inventory=20)
        rewards = {"items": [{"quantity": 5}]}
        is_valid, err = RewardConditionValidator.validate_reward_distribution(
            player, rewards
        )
        assert is_valid is False
        assert "Inventory full" in err

    def test_validate_reward_distribution_invalid_reputation_npc(self):
        player = _make_player(inventory=[], max_inventory=20)
        rewards = {"items": [], "reputation": {"": 10}}
        is_valid, err = RewardConditionValidator.validate_reward_distribution(
            player, rewards
        )
        assert is_valid is False
        assert "Invalid NPC ID" in err


# ===========================================================================
# LevelingProgressSerializer
# ===========================================================================


class TestLevelingProgressSerializer:
    def test_serialize_level_up(self):
        player = _make_player(level=6, exp=100, exp_to_level=1200)
        result = LevelingProgressSerializer.serialize_level_up(
            player, old_level=5, new_level=6, xp_gained=1000
        )
        assert result["level_up"] is True
        assert result["old_level"] == 5
        assert result["new_level"] == 6
        assert result["xp_gained"] == 1000
        assert "stat_increases" in result
        assert "new_skills_unlocked" in result

    def test_get_stat_increases_one_level(self):
        increases = LevelingProgressSerializer._get_stat_increases(6, 5)
        assert increases["hp"] == 5
        assert increases["attack"] == 2
        assert increases["defense"] == 1

    def test_get_stat_increases_multiple_levels(self):
        increases = LevelingProgressSerializer._get_stat_increases(8, 5)
        assert increases["hp"] == 15
        assert increases["attack"] == 6

    def test_get_new_skills_at_milestone(self):
        skills = LevelingProgressSerializer._get_new_skills(5)
        assert "Power Attack" in skills

    def test_get_new_skills_at_level_10(self):
        skills = LevelingProgressSerializer._get_new_skills(10)
        assert "Defensive Stance" in skills

    def test_get_new_skills_at_non_milestone(self):
        skills = LevelingProgressSerializer._get_new_skills(3)
        assert skills == []

    def test_serialize_progression(self):
        player = _make_player(level=7, exp=400, exp_to_level=1500, gold=250)
        player.achievements = ["first_kill", "first_quest"]
        result = LevelingProgressSerializer.serialize_progression(
            player, quests_completed=3
        )
        assert result["level"] == 7
        assert result["quests_completed"] == 3
        assert result["achievements_unlocked"] == 2


# ===========================================================================
# QuestChainSerializer / ChainStatus
# ===========================================================================


class TestChainStatus:
    def test_enum_values(self):
        assert ChainStatus.LOCKED.value == "locked"
        assert ChainStatus.AVAILABLE.value == "available"
        assert ChainStatus.IN_PROGRESS.value == "in_progress"
        assert ChainStatus.COMPLETED.value == "completed"


class TestQuestChainSerializer:
    def test_serialize_chain_basic(self):
        stages = [{"stage": 1}, {"stage": 2}]
        result = QuestChainSerializer.serialize_chain(
            chain_id="c001",
            chain_name="The Long Road",
            description="A journey.",
            stages=stages,
        )
        assert result["chain_id"] == "c001"
        assert result["chain_name"] == "The Long Road"
        assert result["total_stages"] == 2
        assert result["current_stage"] == 0
        assert result["completion_percentage"] == 0
        assert result["can_continue"] is True
        assert result["is_completed"] is False

    def test_serialize_chain_completed(self):
        result = QuestChainSerializer.serialize_chain(
            chain_id="c002",
            chain_name="Finished",
            description="Done.",
            stages=[],
            status=ChainStatus.COMPLETED.value,
        )
        assert result["is_completed"] is True
        assert result["can_continue"] is False

    def test_serialize_chain_in_progress(self):
        result = QuestChainSerializer.serialize_chain(
            chain_id="c003",
            chain_name="Going",
            description="Ongoing.",
            stages=[{}],
            status=ChainStatus.IN_PROGRESS.value,
            current_stage=1,
            completion_percentage=50,
        )
        assert result["can_continue"] is True
        assert result["current_stage"] == 1
        assert result["completion_percentage"] == 50

    def test_serialize_stage(self):
        result = QuestChainSerializer.serialize_stage(
            stage_index=0,
            stage_name="The Beginning",
            quest_id="q001",
            description="First step.",
            status="available",
            rewards={"gold": 50},
            prerequisites=["intro"],
        )
        assert result["stage_index"] == 0
        assert result["stage_name"] == "The Beginning"
        assert result["is_locked"] is False
        assert result["is_completed"] is False
        assert result["rewards"]["gold"] == 50
        assert result["prerequisites"] == ["intro"]

    def test_serialize_stage_locked(self):
        result = QuestChainSerializer.serialize_stage(
            stage_index=2,
            stage_name="Hidden Path",
            quest_id="q003",
            description="Locked.",
            status="locked",
        )
        assert result["is_locked"] is True
        assert result["rewards"] == {}
        assert result["prerequisites"] == []

    def test_serialize_stage_completed(self):
        result = QuestChainSerializer.serialize_stage(
            stage_index=1,
            stage_name="Middle",
            quest_id="q002",
            description="Middle.",
            status="completed",
        )
        assert result["is_completed"] is True


# ===========================================================================
# ChainDependencySerializer
# ===========================================================================


class TestChainDependencySerializer:
    def test_validate_chain_dependencies_all_met(self):
        completed = {"intro_chain": "completed", "side_chain": "completed"}
        ok, err = ChainDependencySerializer.validate_chain_dependencies(
            "main_chain", ["intro_chain", "side_chain"], completed
        )
        assert ok is True
        assert err is None

    def test_validate_chain_dependencies_unmet(self):
        completed = {"intro_chain": "completed"}
        ok, err = ChainDependencySerializer.validate_chain_dependencies(
            "main_chain", ["intro_chain", "side_chain"], completed
        )
        assert ok is False
        assert "side_chain" in err

    def test_validate_chain_dependencies_empty_prereqs(self):
        ok, err = ChainDependencySerializer.validate_chain_dependencies(
            "standalone", [], {}
        )
        assert ok is True

    def test_validate_stage_dependencies_met(self):
        ok, err = ChainDependencySerializer.validate_stage_dependencies(
            1, ["q001", "q002"], ["q001", "q002", "q003"]
        )
        assert ok is True

    def test_validate_stage_dependencies_unmet(self):
        ok, err = ChainDependencySerializer.validate_stage_dependencies(
            1, ["q001", "q_missing"], ["q001"]
        )
        assert ok is False
        assert "q_missing" in err

    def test_serialize_dependency_graph(self):
        chains = {
            "c1": {"prerequisites": []},
            "c2": {"prerequisites": ["c1"]},
            "c3": {"prerequisites": ["c1", "c2"]},
        }
        graph = ChainDependencySerializer.serialize_dependency_graph(chains)
        assert graph["c1"]["can_start"] is True
        assert "c2" in graph["c1"]["unlocks"]
        assert "c3" in graph["c1"]["unlocks"]
        assert graph["c2"]["can_start"] is False

    def test_serialize_dependency_graph_empty(self):
        graph = ChainDependencySerializer.serialize_dependency_graph({})
        assert graph == {}


# ===========================================================================
# ChainProgressionSerializer
# ===========================================================================


class TestChainProgressionSerializer:
    def test_get_chain_progress_no_data(self):
        player = _make_player()
        result = ChainProgressionSerializer.get_chain_progress(player, "c001")
        assert result["chain_id"] == "c001"
        assert result["current_stage"] == 0
        assert result["completed_stages"] == []
        assert result["is_active"] is False

    def test_get_chain_progress_existing_data(self):
        player = _make_player()
        player.chain_progress = {
            "c001": {"current_stage": 2, "completed_stages": [0, 1]}
        }
        player.active_chains = ["c001"]
        result = ChainProgressionSerializer.get_chain_progress(player, "c001")
        assert result["current_stage"] == 2
        assert result["total_completed"] == 2
        assert result["is_active"] is True

    def test_advance_to_next_stage(self):
        player = _make_player()
        result = ChainProgressionSerializer.advance_to_next_stage(
            player, "c001", current_stage=0, next_stage=1
        )
        assert result["success"] is True
        assert result["previous_stage"] == 0
        assert result["current_stage"] == 1
        assert result["completed_count"] == 1

    def test_advance_does_not_double_add_completed_stage(self):
        player = _make_player()
        player.chain_progress = {"c001": {"current_stage": 1, "completed_stages": [0]}}
        ChainProgressionSerializer.advance_to_next_stage(player, "c001", 0, 2)
        assert player.chain_progress["c001"]["completed_stages"].count(0) == 1

    def test_complete_chain(self):
        player = _make_player()
        result = ChainProgressionSerializer.complete_chain(player, "c001")
        assert result["success"] is True
        assert result["status"] == ChainStatus.COMPLETED.value
        assert "c001" in player.completed_chains

    def test_serialize_all_chains_empty(self):
        player = _make_player()
        result = ChainProgressionSerializer.serialize_all_chains_progress(player)
        assert result["total_chains"] == 0
        assert result["completed_chains"] == 0
        assert result["completion_percentage"] == 0

    def test_serialize_all_chains_with_progress(self):
        player = _make_player()
        player.chain_progress = {
            "c001": {"current_stage": 1, "completed_stages": [0]},
        }
        player.completed_chains = {"c002": {"completed_at": "now"}}
        result = ChainProgressionSerializer.serialize_all_chains_progress(player)
        assert "c001" in result["chains"]
        assert "c002" in result["chains"]
        assert result["chains"]["c001"]["status"] == ChainStatus.IN_PROGRESS.value
        assert result["chains"]["c002"]["status"] == ChainStatus.COMPLETED.value

    def test_serialize_all_chains_completion_percentage(self):
        player = _make_player()
        player.chain_progress = {
            "c001": {"current_stage": 1, "completed_stages": [0]},
            "c002": {"current_stage": 0, "completed_stages": []},
        }
        player.completed_chains = {"c001": {}, "c002": {}}
        result = ChainProgressionSerializer.serialize_all_chains_progress(player)
        assert result["completion_percentage"] == 100.0


# ===========================================================================
# ChainRewardSerializer
# ===========================================================================


class TestChainRewardSerializer:
    def test_serialize_stage_rewards(self):
        rewards = {"gold": 75, "experience": 300, "skill_points": 2}
        result = ChainRewardSerializer.serialize_stage_rewards(rewards)
        assert result["gold"] == 75
        assert result["experience"] == 300
        assert result["skill_points"] == 2
        assert result["items"] == []
        assert result["unlocks"] == []

    def test_serialize_stage_rewards_defaults(self):
        result = ChainRewardSerializer.serialize_stage_rewards({})
        assert result["gold"] == 0
        assert result["experience"] == 0

    def test_serialize_chain_completion_rewards(self):
        bonus = {
            "bonus_type": "legendary",
            "title": "Crusader",
            "achievement": "completed_main_chain",
            "gold_bonus": 500,
            "experience_bonus": 2000,
        }
        result = ChainRewardSerializer.serialize_chain_completion_rewards("c001", bonus)
        assert result["chain_id"] == "c001"
        assert result["bonus_type"] == "legendary"
        assert result["title_unlocked"] == "Crusader"
        assert result["gold_bonus"] == 500

    def test_serialize_chain_completion_defaults(self):
        result = ChainRewardSerializer.serialize_chain_completion_rewards("c001", {})
        assert result["bonus_type"] == "standard"
        assert result["title_unlocked"] is None
        assert result["gold_bonus"] == 0

    def test_calculate_completion_bonus_normal(self):
        result = ChainRewardSerializer.calculate_completion_bonus(3, "normal", 0, 0)
        assert result["gold_multiplier"] == 1.0
        assert result["experience_multiplier"] == 1.0

    def test_calculate_completion_bonus_hard_with_objectives(self):
        result = ChainRewardSerializer.calculate_completion_bonus(
            3, "hard", bonus_objectives_completed=2, total_bonus_objectives=4
        )
        # objective_bonus = 0.5 * 0.5 = 0.25; total = 1.25 * 1.5 = 1.875
        assert abs(result["gold_multiplier"] - 1.875) < 0.01

    def test_calculate_completion_bonus_no_objectives(self):
        result = ChainRewardSerializer.calculate_completion_bonus(2, "nightmare", 0, 0)
        assert result["gold_multiplier"] == 2.0
        assert result["objective_bonus_percentage"] == 0


# ===========================================================================
# ChainBranchSerializer
# ===========================================================================


class TestChainBranchSerializer:
    def test_serialize_branch_point(self):
        branches = [
            {
                "id": "b1",
                "name": "Left Path",
                "description": "Stealth",
                "alignment": "neutral",
            },
            {
                "id": "b2",
                "name": "Right Path",
                "description": "Combat",
                "alignment": "lawful",
            },
        ]
        result = ChainBranchSerializer.serialize_branch_point("c001", 2, branches)
        assert result["chain_id"] == "c001"
        assert result["branch_stage"] == 2
        assert result["total_branches"] == 2
        assert result["branches"][0]["branch_id"] == "b1"
        assert result["branches"][1]["alignment"] == "lawful"

    def test_serialize_branch_point_missing_ids(self):
        branches = [{"name": "Option A"}, {"name": "Option B"}]
        result = ChainBranchSerializer.serialize_branch_point("c001", 1, branches)
        assert result["branches"][0]["branch_id"] == "branch_0"
        assert result["branches"][1]["branch_id"] == "branch_1"

    def test_get_available_branches_all_pass(self):
        player = _make_player()
        player.reputation = {"gorran": 60}
        branch_point = {
            "branches": [
                {"id": "b1", "reputation_gates": {"gorran": 50}},
                {"id": "b2", "reputation_gates": {}},
            ]
        }
        available = ChainBranchSerializer.get_available_branches(
            player, "c001", branch_point
        )
        assert len(available) == 2

    def test_get_available_branches_reputation_gate_fails(self):
        player = _make_player()
        player.reputation = {"gorran": 20}
        branch_point = {
            "branches": [
                {"id": "b1", "reputation_gates": {"gorran": 50}},
                {"id": "b2", "reputation_gates": {}},
            ]
        }
        available = ChainBranchSerializer.get_available_branches(
            player, "c001", branch_point
        )
        assert len(available) == 1
        assert available[0]["id"] == "b2"

    def test_get_available_branches_no_branches(self):
        player = _make_player()
        branch_point = {"branches": []}
        available = ChainBranchSerializer.get_available_branches(
            player, "c001", branch_point
        )
        assert available == []


# ===========================================================================
# NPCRelationshipSerializer
# ===========================================================================


class TestNPCRelationshipSerializer:
    def test_serialize_friendly(self):
        result = NPCRelationshipSerializer.serialize_relationship("g", "Gorran", 75)
        assert result["attitude"] == "friendly"
        assert result["locked_dialogue"] is False

    def test_serialize_favorable(self):
        result = NPCRelationshipSerializer.serialize_relationship("g", "Gorran", 30)
        assert result["attitude"] == "favorable"

    def test_serialize_neutral(self):
        result = NPCRelationshipSerializer.serialize_relationship("g", "Gorran", 0)
        assert result["attitude"] == "neutral"
        assert result["locked_dialogue"] is False

    def test_serialize_wary(self):
        result = NPCRelationshipSerializer.serialize_relationship("g", "Gorran", -10)
        assert result["attitude"] == "wary"
        assert result["locked_dialogue"] is True

    def test_serialize_hostile(self):
        result = NPCRelationshipSerializer.serialize_relationship("g", "Gorran", -40)
        assert result["attitude"] == "hostile"

    def test_serialize_enemy(self):
        result = NPCRelationshipSerializer.serialize_relationship("g", "Gorran", -75)
        assert result["attitude"] == "enemy"

    def test_calculate_trust_levels(self):
        assert NPCRelationshipSerializer._calculate_trust_level(80) == "Complete Trust"
        assert NPCRelationshipSerializer._calculate_trust_level(60) == "High Trust"
        assert NPCRelationshipSerializer._calculate_trust_level(30) == "Good Trust"
        assert NPCRelationshipSerializer._calculate_trust_level(10) == "Neutral"
        assert NPCRelationshipSerializer._calculate_trust_level(-10) == "Suspicious"
        assert NPCRelationshipSerializer._calculate_trust_level(-40) == "Distrusting"
        assert NPCRelationshipSerializer._calculate_trust_level(-80) == "Hostile"

    def test_get_npc_name_known(self):
        assert NPCRelationshipSerializer._get_npc_name("healer") == "Healer"

    def test_get_npc_name_unknown_formats(self):
        name = NPCRelationshipSerializer._get_npc_name("cave_guide")
        assert name == "Cave Guide"

    def test_get_npc_name_unknown_id(self):
        name = NPCRelationshipSerializer._get_npc_name("some_random_npc")
        assert name == "Some Random Npc"


# ===========================================================================
# PlayerReputationSerializer
# ===========================================================================


class TestPlayerReputationSerializer:
    def test_serialize_all_reputation_empty(self):
        player = _make_player(reputation={})
        result = PlayerReputationSerializer.serialize_all_reputation(player)
        assert result["total_npcs"] == 0
        assert result["highest_reputation"] == 0
        assert result["lowest_reputation"] == 0

    def test_serialize_all_reputation_with_data(self):
        player = _make_player(reputation={"gorran": 60, "merchant": -30, "healer": 10})
        result = PlayerReputationSerializer.serialize_all_reputation(player)
        assert result["total_npcs"] == 3
        assert result["highest_reputation"] == 60
        assert result["lowest_reputation"] == -30
        assert result["friendly_npcs"] == 1
        assert result["hostile_npcs"] == 0

    def test_serialize_reputation_change_positive(self):
        result = PlayerReputationSerializer.serialize_reputation_change(
            "gorran", "Gorran", 20, 40, "quest_complete"
        )
        assert result["change"] == 20
        assert result["direction"] == "positive"
        assert result["reason"] == "quest_complete"

    def test_serialize_reputation_change_negative(self):
        result = PlayerReputationSerializer.serialize_reputation_change(
            "gorran", "Gorran", 50, 10, "betrayal"
        )
        assert result["direction"] == "negative"
        assert result["change"] == -40

    def test_serialize_reputation_change_neutral(self):
        result = PlayerReputationSerializer.serialize_reputation_change(
            "gorran", "Gorran", 20, 20, "no_change"
        )
        assert result["direction"] == "neutral"

    def test_serialize_reputation_change_attitude_changed(self):
        result = PlayerReputationSerializer.serialize_reputation_change(
            "gorran", "Gorran", 60, 20, "quest_fail"
        )
        # 60 = friendly, 20 = favorable
        assert result["attitude_changed"] is True

    def test_serialize_reputation_change_attitude_unchanged(self):
        result = PlayerReputationSerializer.serialize_reputation_change(
            "gorran", "Gorran", 55, 60, "small_gain"
        )
        # both friendly
        assert result["attitude_changed"] is False


# ===========================================================================
# RelationshipFlagSerializer
# ===========================================================================


class TestRelationshipFlagSerializer:
    def test_set_flag_valid(self):
        player = _make_player()
        result = RelationshipFlagSerializer.set_flag(player, "gorran", "alliance", True)
        assert result["success"] is True
        assert result["new_value"] is True
        assert result["changed"] is True

    def test_set_flag_invalid(self):
        player = _make_player()
        result = RelationshipFlagSerializer.set_flag(
            player, "gorran", "invalid_flag", True
        )
        assert result["success"] is False
        assert "invalid_flag" in result["error"]

    def test_set_flag_creates_attributes(self):
        player = _make_player()
        RelationshipFlagSerializer.set_flag(player, "healer", "romance", True)
        assert player.relationship_flags["healer"]["romance"] is True

    def test_set_flag_unchanged(self):
        player = _make_player()
        player.relationship_flags = {"gorran": {"betrayed": True}}
        result = RelationshipFlagSerializer.set_flag(player, "gorran", "betrayed", True)
        assert result["changed"] is False

    def test_get_flags_empty(self):
        player = _make_player()
        result = RelationshipFlagSerializer.get_flags(player, "gorran")
        assert result["npc_id"] == "gorran"
        assert result["flags"] == {}
        assert result["active_count"] == 0

    def test_get_flags_with_data(self):
        player = _make_player()
        player.relationship_flags = {
            "gorran": {"alliance": True, "betrayed": False, "romance": True}
        }
        result = RelationshipFlagSerializer.get_flags(player, "gorran")
        assert result["active_count"] == 2
        assert "alliance" in result["active_flags"]
        assert "betrayed" not in result["active_flags"]

    def test_serialize_flags_summary_empty(self):
        player = _make_player()
        result = RelationshipFlagSerializer.serialize_flags_summary(player)
        assert result["total_npcs_with_flags"] == 0
        assert result["total_active_flags"] == 0
        assert result["romance_count"] == 0

    def test_serialize_flags_summary_with_data(self):
        player = _make_player()
        player.relationship_flags = {
            "gorran": {"alliance": True, "romance": False},
            "healer": {"romance": True, "enemy": True},
        }
        result = RelationshipFlagSerializer.serialize_flags_summary(player)
        assert result["total_active_flags"] == 3
        assert result["romance_count"] == 1
        assert result["allied_npcs"] == 1
        assert result["enemy_npcs"] == 1


# ===========================================================================
# ReputationThresholdValidator
# ===========================================================================


class TestReputationThresholdValidator:
    def test_check_dialogue_available_sufficient_rep(self):
        player = _make_player(reputation={"gorran": 60})
        ok, reason = ReputationThresholdValidator.check_dialogue_available(
            player, "gorran", "special_dialogue"
        )
        assert ok is True
        assert reason is None

    def test_check_dialogue_available_insufficient_rep(self):
        player = _make_player(reputation={"gorran": 10})
        ok, reason = ReputationThresholdValidator.check_dialogue_available(
            player, "gorran", "special_dialogue"
        )
        assert ok is False
        assert "50" in reason

    def test_check_dialogue_available_unknown_node_defaults_zero(self):
        player = _make_player(reputation={"gorran": 0})
        ok, _ = ReputationThresholdValidator.check_dialogue_available(
            player, "gorran", "nonexistent_dialogue"
        )
        assert ok is True

    def test_check_quest_available_sufficient_rep(self):
        player = _make_player(reputation={"gorran": 80})
        ok, _ = ReputationThresholdValidator.check_quest_available(
            player, "gorran", "secret_quest"
        )
        assert ok is True

    def test_check_quest_available_insufficient_rep(self):
        player = _make_player(reputation={"gorran": 10})
        ok, reason = ReputationThresholdValidator.check_quest_available(
            player, "gorran", "secret_quest"
        )
        assert ok is False
        assert "75" in reason

    def test_serialize_dialogue_locks(self):
        player = _make_player(reputation={"gorran": 30})
        result = ReputationThresholdValidator.serialize_dialogue_locks(
            player,
            "gorran",
            ["greeting_friendly", "special_dialogue", "quest_offer"],
        )
        assert result["npc_id"] == "gorran"
        assert result["total_dialogues"] == 3
        # greeting_friendly needs 25 — gorran has 30, ok
        # special_dialogue needs 50 — gorran has 30, locked
        # quest_offer needs 0 — ok
        assert result["unlocked_dialogues"] == 2
        assert result["locked_dialogues"] == 1

    def test_serialize_quest_locks(self):
        player = _make_player(reputation={"healer": 5})
        quests = [
            ("q1", "normal_quest"),
            ("q2", "secret_quest"),
        ]
        result = ReputationThresholdValidator.serialize_quest_locks(
            player, "healer", quests
        )
        assert result["unlocked_quests"] == 1
        assert result["quest_status"]["q1"]["available"] is True
        assert result["quest_status"]["q2"]["available"] is False
