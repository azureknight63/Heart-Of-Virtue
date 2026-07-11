"""
Coverage-gap tests for API serializers.

Targets:
- src/api/serializers/combat.py  (73% -> ~95%)
- src/api/serializers/npc_serializer.py  (82% -> ~98%)
- src/api/serializers/item_serializer.py  (75% -> ~98%)
- src/api/serializers/inventory.py  (69% -> ~95%)
- src/api/serializers/event_serializer.py  (95% -> ~100%)
- src/api/serializers/object_serializer.py  (94% -> ~100%)
"""

import pytest
from unittest.mock import MagicMock, patch
from types import SimpleNamespace

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_combatant(
    name="Jean",
    hp=80,
    maxhp=100,
    level=3,
    is_player=True,
    fatigue=10,
    maxfatigue=100,
    heat=1.2,
    speed=8,
    damage=15,
    armor=5,
    accuracy=85,
    evasion=10,
    defense=5,
    attack_power=20,
    strength=12,
    finesse=9,
    endurance=10,
    intelligence=7,
    charisma=6,
    friend=False,
    resistances=None,
):
    c = MagicMock()
    if is_player:
        # Serializers isinstance-check the real Player class; assigning it to
        # __class__ makes the mock pass that check.
        from src.player import Player

        c.__class__ = Player
    else:
        c.__class__ = type("NPC", (), {})
    c.name = name
    c.hp = hp
    c.maxhp = maxhp
    c.level = level
    c.fatigue = fatigue
    c.maxfatigue = maxfatigue
    c.heat = heat
    c.speed = speed
    c.damage = damage
    c.armor = armor
    c.accuracy = accuracy
    c.evasion = evasion
    c.defense = defense
    c.attack_power = attack_power
    c.strength = strength
    c.finesse = finesse
    c.endurance = endurance
    c.intelligence = intelligence
    c.charisma = charisma
    c.friend = friend
    c.battle_symbol = "@" if is_player else "E"
    c.combat_proximity = 0
    c.combat_position = None
    c.states = []
    c.known_moves = []
    c.inventory = []
    c.current_move = None
    c.suggested_moves = []
    c.suggestions_loading = False
    c.last_move_summary = ""
    c.last_move_name = None
    c.last_move_target_id = None
    if resistances is not None:
        c.resistances = resistances
    else:
        del c.resistances
    return c


def _mock_move(
    name="Slash",
    description="A basic slash",
    move_type="physical",
    category="Attack",
    base_damage=10,
    damage_type="slashing",
    mp_cost=0,
    stamina_cost=5,
    range_val="melee",
    cooldown_max=0,
    cooldown=0,
    accuracy=100,
    passive=False,
    applies_state=None,
):
    m = MagicMock()
    m.name = name
    m.description = description
    m.move_type = move_type
    m.category = category
    m.base_damage = base_damage
    m.damage_type = damage_type
    m.mp_cost = mp_cost
    m.stamina_cost = stamina_cost
    m.range = range_val
    m.cooldown_max = cooldown_max
    m.cooldown = cooldown
    m.accuracy = accuracy
    m.passive = passive
    m.applies_state = applies_state
    return m


def _mock_state(name="Poisoned", state_type="debuff", damage_per_turn=3, beats_left=2):
    s = MagicMock()
    s.name = name
    s.state_type = state_type
    s.description = "Taking poison damage."
    s.damage_per_turn = damage_per_turn
    s.healing_per_turn = 0
    s.resistable = True
    s.beats_left = beats_left
    return s


# ===========================================================================
# CombatStateSerializer
# ===========================================================================


class TestCombatStateSerializer:
    """Tests for CombatStateSerializer covering uncovered branches."""

    def setup_method(self):
        from src.api.serializers.combat import CombatStateSerializer

        self.CombatStateSerializer = CombatStateSerializer

    def test_serialize_combat_state_basic(self):
        player = _mock_combatant()
        enemy = _mock_combatant(name="Goblin", is_player=False, hp=40, maxhp=60)
        result = self.CombatStateSerializer.serialize_combat_state(
            player, [enemy], current_turn_index=0, round_number=2
        )
        assert result["status"] == "active"
        assert result["round"] == 2
        assert result["current_turn_index"] == 0
        assert "player" in result
        assert len(result["enemies"]) == 1
        assert result["allies"] == []

    def test_serialize_combat_state_with_allies(self):
        player = _mock_combatant()
        ally = _mock_combatant(name="Ally", is_player=False, friend=True)
        enemy = _mock_combatant(name="Troll", is_player=False)
        result = self.CombatStateSerializer.serialize_combat_state(
            player, [enemy], allies=[ally]
        )
        assert len(result["allies"]) == 1
        assert len(result["enemies"]) == 1
        assert len(result["combatants"]) == 3

    def test_serialize_turn_data_player(self):
        player = _mock_combatant()
        result = self.CombatStateSerializer.serialize_turn_data(player)
        assert result["name"] == "Jean"
        assert result["type"] == "player"
        assert "available_actions" in result

    def test_serialize_turn_data_enemy(self):
        enemy = _mock_combatant(name="Orc", is_player=False)
        result = self.CombatStateSerializer.serialize_turn_data(enemy)
        assert result["type"] == "enemy"

    def test_serialize_battle_summary_victory(self):
        player = _mock_combatant()
        enemy = _mock_combatant(name="Goblin", is_player=False, hp=0, maxhp=40)
        enemy.hp = 0
        enemy.exp_reward = 50
        result = self.CombatStateSerializer.serialize_battle_summary(
            player, [enemy], victory=True
        )
        assert result["status"] == "victory"
        assert result["enemies_defeated"] == 1
        assert result["experience_gained"] == 50

    def test_serialize_battle_summary_defeat(self):
        player = _mock_combatant()
        enemy = _mock_combatant(name="Dragon", is_player=False, hp=200, maxhp=200)
        result = self.CombatStateSerializer.serialize_battle_summary(
            player, [enemy], victory=False
        )
        assert result["status"] == "defeat"
        assert result["experience_gained"] == 0
        assert result["items_dropped"] == []

    def test_get_turn_order(self):
        player = _mock_combatant()
        enemy = _mock_combatant(name="Goblin", is_player=False)
        order = self.CombatStateSerializer._get_turn_order(player, [enemy])
        assert order[0] == "player"
        assert "enemy_0" in order

    def test_get_available_actions_with_inventory(self):
        combatant = _mock_combatant()
        actions = self.CombatStateSerializer._get_available_actions(combatant)
        assert "attack" in actions
        assert "use_item" in actions

    def test_calculate_experience_with_level_fallback(self):
        enemy = MagicMock()
        del enemy.exp_reward
        enemy.level = 5
        total = self.CombatStateSerializer._calculate_experience([enemy])
        assert total == 50

    def test_calculate_experience_with_exp_reward(self):
        enemy = MagicMock()
        enemy.exp_reward = 100
        total = self.CombatStateSerializer._calculate_experience([enemy])
        assert total == 100

    def test_get_drops_with_inventory(self):
        enemy = _mock_combatant(name="Boss", is_player=False)
        item = MagicMock()
        item.name = "Gold Sword"
        item.count = 1
        item.subtype = "weapon"
        item.weight = 3.5
        item.value = 200
        item._enchantment_count = 2
        item.description = "A golden sword."
        enemy.inventory = [item]
        drops = self.CombatStateSerializer._get_drops([enemy])
        assert len(drops) == 1
        assert drops[0]["name"] == "Gold Sword"
        assert drops[0]["enchantment_count"] == 2

    def test_get_drops_uses_enchantment_count_fallback(self):
        enemy = _mock_combatant(name="Boss", is_player=False)
        item = MagicMock(
            spec=[
                "name",
                "count",
                "subtype",
                "weight",
                "value",
                "description",
                "enchantment_count",
            ]
        )
        item.name = "Plain Sword"
        item.count = 1
        item.subtype = "weapon"
        item.weight = 2.0
        item.value = 50
        item.enchantment_count = 1
        item.description = "A plain sword."
        enemy.inventory = [item]
        drops = self.CombatStateSerializer._get_drops([enemy])
        assert drops[0]["enchantment_count"] == 1

    def test_get_consumables_with_inventory(self):
        player = _mock_combatant()
        item = MagicMock()
        item.name = "Health Potion"
        item.count = 2
        item.value = 50
        item.description = "Restores HP."
        player.inventory = [item]
        consumables = self.CombatStateSerializer._get_consumables(player)
        assert len(consumables) == 1
        assert consumables[0]["name"] == "Health Potion"
        assert consumables[0]["qty"] == 2

    def test_get_consumables_no_inventory(self):
        player = MagicMock(spec=[])
        consumables = self.CombatStateSerializer._get_consumables(player)
        assert consumables == []


# ===========================================================================
# CombatantSerializer
# ===========================================================================


class TestCombatantSerializer:
    """Tests for CombatantSerializer covering uncovered branches."""

    def setup_method(self):
        from src.api.serializers.combat import CombatantSerializer

        self.CombatantSerializer = CombatantSerializer

    def test_serialize_combatant_player(self):
        player = _mock_combatant()
        result = self.CombatantSerializer.serialize_combatant(player)
        assert result["id"] == "player"
        assert result["type"] == "player"
        assert result["health"]["current"] == 80

    def test_serialize_combatant_enemy(self):
        enemy = _mock_combatant(name="Goblin", is_player=False)
        result = self.CombatantSerializer.serialize_combatant(enemy)
        assert result["id"].startswith("enemy_")
        assert result["type"] == "npc"

    def test_serialize_combatant_ally(self):
        ally = _mock_combatant(name="Friend", is_player=False, friend=True)
        result = self.CombatantSerializer.serialize_combatant(ally)
        assert result["id"].startswith("ally_")

    def test_serialize_combatant_with_reference_in_range(self):
        player = _mock_combatant()
        enemy = _mock_combatant(name="Goblin", is_player=False)
        enemy.combat_proximity = 2
        result = self.CombatantSerializer.serialize_combatant(enemy, reference=player)
        assert result["in_range"] is True

    def test_serialize_combatant_with_reference_out_of_range(self):
        from src.api.constants import ITEM_USE_RANGE

        player = _mock_combatant()
        enemy = _mock_combatant(name="Archer", is_player=False)
        enemy.combat_proximity = ITEM_USE_RANGE + 5
        result = self.CombatantSerializer.serialize_combatant(enemy, reference=player)
        assert result["in_range"] is False

    def test_serialize_combatant_with_dict_proximity(self):
        player = _mock_combatant()
        enemy = _mock_combatant(name="Bandit", is_player=False)
        enemy.combat_proximity = {player: 3}
        result = self.CombatantSerializer.serialize_combatant(enemy, reference=player)
        assert result["distance"] == 3

    def test_serialize_combatant_with_dict_proximity_no_key(self):
        player = _mock_combatant()
        enemy = _mock_combatant(name="Bandit", is_player=False)
        other_player = MagicMock()
        enemy.combat_proximity = {other_player: 3}
        result = self.CombatantSerializer.serialize_combatant(enemy, reference=player)
        assert result["distance"] == 0

    def test_serialize_active_move_with_stage_beat(self):
        combatant = _mock_combatant()
        move = MagicMock()
        move.name = "Charge"
        move.category = "Attack"
        move.description = "A charging attack"
        move.current_stage = 1
        move.beats_left = 2
        move.stage_beat = [0, 3, 0, 0]
        combatant.current_move = move
        result = self.CombatantSerializer._serialize_active_move(combatant)
        assert result is not None
        assert result["name"] == "Charge"
        assert result["total_beats"] == 3

    def test_serialize_active_move_without_stage_beat(self):
        combatant = _mock_combatant()
        move = MagicMock(
            spec=["name", "category", "description", "current_stage", "beats_left"]
        )
        move.name = "Slash"
        move.category = "Attack"
        move.description = "Slash"
        move.current_stage = 0
        move.beats_left = 1
        combatant.current_move = move
        result = self.CombatantSerializer._serialize_active_move(combatant)
        assert result["total_beats"] == 0

    def test_serialize_active_move_none(self):
        combatant = _mock_combatant()
        combatant.current_move = None
        result = self.CombatantSerializer._serialize_active_move(combatant)
        assert result is None

    def test_serialize_position_with_facing(self):
        combatant = _mock_combatant()
        pos = MagicMock()
        pos.x = 3
        pos.y = 5
        pos.facing = MagicMock()
        pos.facing.name = "N"
        combatant.combat_position = pos
        result = self.CombatantSerializer._serialize_position(combatant)
        assert result is not None
        assert result["x"] == 3
        assert result["y"] == 5
        assert result["facing"] == "N"

    def test_serialize_position_none(self):
        combatant = _mock_combatant()
        combatant.combat_position = None
        result = self.CombatantSerializer._serialize_position(combatant)
        assert result is None

    def test_serialize_position_no_attribute(self):
        combatant = MagicMock(spec=[])
        result = self.CombatantSerializer._serialize_position(combatant)
        assert result is None

    def test_serialize_combatant_list(self):
        p = _mock_combatant()
        e = _mock_combatant(name="Orc", is_player=False)
        result = self.CombatantSerializer.serialize_combatant_list([p, e])
        assert len(result) == 2

    def test_serialize_health_bar_healthy(self):
        combatant = MagicMock()
        combatant.health = 90
        combatant.max_health = 100
        result = self.CombatantSerializer.serialize_health_bar(combatant)
        assert result["status"] == "healthy"
        assert result["percent"] == 90.0

    def test_serialize_health_bar_injured(self):
        combatant = MagicMock()
        combatant.health = 65
        combatant.max_health = 100
        result = self.CombatantSerializer.serialize_health_bar(combatant)
        assert result["status"] == "injured"

    def test_serialize_health_bar_wounded(self):
        combatant = MagicMock()
        combatant.health = 40
        combatant.max_health = 100
        result = self.CombatantSerializer.serialize_health_bar(combatant)
        assert result["status"] == "wounded"

    def test_serialize_health_bar_critical(self):
        combatant = MagicMock()
        combatant.health = 20
        combatant.max_health = 100
        result = self.CombatantSerializer.serialize_health_bar(combatant)
        assert result["status"] == "critical"

    def test_serialize_health_bar_zero_max(self):
        combatant = MagicMock()
        combatant.health = 0
        combatant.max_health = 0
        result = self.CombatantSerializer.serialize_health_bar(combatant)
        assert result["percent"] == 0

    def test_serialize_passives(self):
        combatant = _mock_combatant()
        passive_move = _mock_move(name="Shield Wall", passive=True)
        combatant.known_moves = [passive_move]
        result = self.CombatantSerializer._serialize_passives(combatant)
        assert len(result) == 1
        assert result[0]["name"] == "Shield Wall"
        assert result[0]["type"] == "passive"

    def test_serialize_passives_skips_active_moves(self):
        combatant = _mock_combatant()
        active_move = _mock_move(name="Slash", passive=False)
        combatant.known_moves = [active_move]
        result = self.CombatantSerializer._serialize_passives(combatant)
        assert result == []

    def test_serialize_status_effects(self):
        combatant = _mock_combatant()
        state = _mock_state()
        combatant.states = [state]
        result = self.CombatantSerializer._serialize_status_effects(combatant)
        assert len(result) == 1
        assert result[0]["name"] == "Poisoned"

    def test_serialize_combat_equipment_with_weapon_and_armor(self):
        combatant = _mock_combatant()
        weapon = MagicMock()
        weapon.name = "Iron Sword"
        weapon.damage_type = "slashing"
        body = MagicMock()
        body.name = "Leather Armor"
        body.defense = 8
        combatant.equipped = {"weapon": weapon, "body": body}
        result = self.CombatantSerializer._serialize_combat_equipment(combatant)
        assert result["weapon"]["name"] == "Iron Sword"
        assert result["armor"]["name"] == "Leather Armor"

    def test_serialize_combat_equipment_with_resistances(self):
        combatant = _mock_combatant(resistances={"fire": 0.5})
        combatant.equipped = {}
        result = self.CombatantSerializer._serialize_combat_equipment(combatant)
        assert result["resistances"]["fire"] == 0.5

    def test_serialize_combat_equipment_empty(self):
        combatant = MagicMock(spec=[])
        result = self.CombatantSerializer._serialize_combat_equipment(combatant)
        assert result["weapon"] is None
        assert result["armor"] is None


# ===========================================================================
# MoveSerializer
# ===========================================================================


class TestMoveSerializer:
    """Tests for MoveSerializer covering uncovered branches."""

    def setup_method(self):
        from src.api.serializers.combat import MoveSerializer

        self.MoveSerializer = MoveSerializer

    def test_serialize_move_basic(self):
        move = _mock_move()
        result = self.MoveSerializer.serialize_move(move)
        assert result["name"] == "Slash"
        assert result["type"] == "physical"
        assert result["damage"]["base"] == 10
        assert result["cost"]["stamina"] == 5

    def test_serialize_move_list(self):
        moves = [_mock_move("Slash"), _mock_move("Stab", base_damage=12)]
        result = self.MoveSerializer.serialize_move_list(moves)
        assert len(result) == 2
        assert result[1]["name"] == "Stab"

    def test_serialize_move_with_cooldown(self):
        move = _mock_move()
        result = self.MoveSerializer.serialize_move_with_cooldown(
            move, cooldown_remaining=3
        )
        assert result["cooldown"]["remaining"] == 3
        assert result["available"] is False

    def test_serialize_move_with_cooldown_zero(self):
        move = _mock_move()
        result = self.MoveSerializer.serialize_move_with_cooldown(
            move, cooldown_remaining=0
        )
        assert result["available"] is True

    def test_serialize_move_effects_with_state(self):
        state = _mock_state(damage_per_turn=8)
        move = _mock_move(applies_state=state)
        effects = self.MoveSerializer._serialize_move_effects(move)
        assert len(effects) == 1
        assert effects[0]["type"] == "Poisoned"
        assert effects[0]["severity"] == "severe"

    def test_serialize_move_effects_no_state(self):
        move = _mock_move(applies_state=None)
        move.applies_state = None
        effects = self.MoveSerializer._serialize_move_effects(move)
        assert effects == []


# ===========================================================================
# StateEffectSerializer
# ===========================================================================


class TestStateEffectSerializer:
    """Tests for StateEffectSerializer covering uncovered branches."""

    def setup_method(self):
        from src.api.serializers.combat import StateEffectSerializer

        self.StateEffectSerializer = StateEffectSerializer

    def test_serialize_state_basic(self):
        state = _mock_state()
        result = self.StateEffectSerializer.serialize_state(state)
        assert result["name"] == "Poisoned"
        assert result["type"] == "debuff"
        assert result["severity"] == "moderate"

    def test_serialize_state_list(self):
        states = [_mock_state("Poisoned"), _mock_state("Burned", damage_per_turn=7)]
        result = self.StateEffectSerializer.serialize_state_list(states)
        assert len(result) == 2

    def test_serialize_state_with_duration(self):
        state = _mock_state()
        result = self.StateEffectSerializer.serialize_state_with_duration(
            state, duration_remaining=3
        )
        assert result["duration_remaining"] == 3
        assert result["active"] is True

    def test_serialize_state_with_duration_inactive(self):
        state = _mock_state()
        result = self.StateEffectSerializer.serialize_state_with_duration(
            state, duration_remaining=0
        )
        assert result["active"] is False

    def test_get_severity_light(self):
        state = _mock_state(damage_per_turn=0)
        result = self.StateEffectSerializer._get_severity(state)
        assert result == "light"

    def test_get_severity_moderate(self):
        state = _mock_state(damage_per_turn=4)
        result = self.StateEffectSerializer._get_severity(state)
        assert result == "moderate"

    def test_get_severity_severe(self):
        state = _mock_state(damage_per_turn=10)
        result = self.StateEffectSerializer._get_severity(state)
        assert result == "severe"


# ===========================================================================
# NPCSerializer
# ===========================================================================


class TestNPCSerializer:
    """Tests for NPCSerializer covering uncovered branches."""

    def setup_method(self):
        from src.api.serializers.npc_serializer import NPCSerializer

        self.NPCSerializer = NPCSerializer

    def _make_npc(self, name="Goblin", is_hostile=False, aggro=False, friend=False):
        npc = MagicMock()
        npc.name = name
        npc.description = "A generic NPC"
        npc.level = 2
        npc.is_hostile = is_hostile
        npc.aggro = aggro
        npc.friend = friend
        npc.keywords = ["talk"]
        npc.idle_message = "..."
        npc.alert_message = "!!!"
        npc.current_hp = 60
        npc.maxhp = 80
        npc._init_chat_attrs = True
        npc.loquacity_max = 3
        npc.loquacity_current = 3
        npc.loquacity_threshold = 2
        return npc

    def test_serialize_none_npc(self):
        result = self.NPCSerializer.serialize(None)
        assert result == {}

    def test_serialize_basic_npc(self):
        npc = self._make_npc()
        result = self.NPCSerializer.serialize(npc)
        assert result["name"] == "Goblin"
        assert "health" in result

    def test_serialize_npc_with_max_hp_fallback(self):
        npc = self._make_npc()
        del npc.maxhp
        npc.max_hp = 90
        result = self.NPCSerializer.serialize(npc)
        assert result["max_health"] == 90

    def test_serialize_npc_no_hp_attrs(self):
        npc = MagicMock(spec=["name", "description", "level"])
        npc.name = "Ghost"
        npc.description = "Spooky"
        npc.level = 1
        result = self.NPCSerializer.serialize(npc)
        assert "health" not in result
        assert "max_health" not in result

    def test_serialize_hostile_npc_gets_attack_keyword(self):
        npc = self._make_npc(is_hostile=True)
        npc.keywords = []
        result = self.NPCSerializer.serialize(npc)
        assert "attack" in result["keywords"]

    def test_serialize_aggressive_npc_gets_attack_keyword(self):
        npc = self._make_npc(aggro=True)
        npc.keywords = []
        result = self.NPCSerializer.serialize(npc)
        assert "attack" in result["keywords"]

    def test_serialize_friendly_hostile_no_attack_keyword(self):
        npc = self._make_npc(is_hostile=True, friend=True)
        npc.keywords = []
        result = self.NPCSerializer.serialize(npc)
        assert "attack" not in result.get("keywords", [])

    def test_serialize_loquacity_available_below_threshold(self):
        npc = self._make_npc()
        npc.loquacity_current = 0
        npc.loquacity_threshold = 2
        npc.loquacity_max = 3
        result = self.NPCSerializer.serialize(npc)
        assert result["loquacity_available"] is False

    def test_serialize_loquacity_max_zero(self):
        npc = self._make_npc()
        npc.loquacity_max = 0
        result = self.NPCSerializer.serialize(npc)
        assert result["loquacity_available"] is True

    def test_serialize_with_stats(self):
        npc = self._make_npc()
        npc.strength = 15
        npc.speed = 6
        npc.add_resistance = {"fire": 0.5}
        npc.add_status_resistance = {"poison": 0.3}
        npc.equipped = {"weapon": MagicMock()}
        result = self.NPCSerializer.serialize_with_stats(npc)
        assert "stats" in result
        assert result["stats"]["strength"] == 15
        assert "resistances" in result
        assert "status_resistances" in result
        assert "equipped" in result

    def test_serialize_with_stats_empty(self):
        npc = MagicMock(spec=["name", "description", "level"])
        npc.name = "Empty"
        npc.description = ""
        npc.level = 1
        result = self.NPCSerializer.serialize_with_stats(npc)
        assert "stats" not in result

    def test_serialize_merchant_with_inventory(self):
        from src.api.serializers.npc_serializer import NPCSerializer

        npc = self._make_npc("Merchant")
        item = MagicMock()
        item.name = "Potion"
        item.description = "Heals"
        item.value = 50
        item.weight = 0.5
        item.aliases = []
        item.action_aliases = []
        item.interactions = []
        item.keywords = ["take", "buy"]
        npc.inventory = [item]
        result = NPCSerializer.serialize_merchant(npc)
        assert result["is_merchant"] is True
        assert len(result["shop_items"]) == 1

    def test_serialize_merchant_empty_inventory(self):
        npc = self._make_npc("Merchant")
        del npc.inventory
        result = self.NPCSerializer.serialize_merchant(npc)
        assert result["shop_items"] == []

    def test_serialize_with_inventory(self):
        npc = self._make_npc()
        item = MagicMock()
        item.name = "Dagger"
        item.description = ""
        item.value = 30
        item.weight = 0.3
        item.aliases = []
        item.action_aliases = []
        item.interactions = []
        item.keywords = ["take"]
        npc.inventory = [item]
        result = self.NPCSerializer.serialize_with_inventory(npc)
        assert "inventory" in result
        assert result["inventory_count"] == 1

    def test_serialize_with_inventory_missing(self):
        npc = MagicMock(spec=["name", "description", "level"])
        npc.name = "Ghost"
        npc.description = ""
        npc.level = 1
        result = self.NPCSerializer.serialize_with_inventory(npc)
        assert result["inventory"] == []
        assert result["inventory_count"] == 0

    def test_serialize_for_combat(self):
        npc = self._make_npc()
        npc.combat_list = [MagicMock()]
        npc.status_effects = ["Poisoned"]
        result = self.NPCSerializer.serialize_for_combat(npc)
        assert result["in_combat"] is True
        assert result["status_effects"] == ["Poisoned"]


# ===========================================================================
# ItemSerializer
# ===========================================================================


class TestItemSerializer:
    """Tests for ItemSerializer covering uncovered branches."""

    def setup_method(self):
        from src.api.serializers.item_serializer import ItemSerializer

        self.ItemSerializer = ItemSerializer

    def _make_item(self, name="Sword", item_type="Weapon"):
        item = MagicMock()
        item.__class__ = MagicMock()
        item.__class__.__name__ = item_type
        item.name = name
        item.description = "A basic sword"
        item.aliases = ["blade"]
        item.action_aliases = []
        item.value = 100
        item.weight = 2.5
        item.keywords = ["take", "equip"]
        item.isequipped = False
        item.equip_states = ["equipped"]
        item.interactions = ["take", "equip", "drop", "unequip"]
        return item

    def test_serialize_none_item(self):
        result = self.ItemSerializer.serialize(None)
        assert result == {}

    def test_serialize_basic_item(self):
        item = self._make_item()
        result = self.ItemSerializer.serialize(item)
        assert result["name"] == "Sword"
        assert "take" in result["keywords"]

    def test_serialize_item_with_quantity(self):
        item = self._make_item("Arrow", "Ammo")
        item.quantity = 20
        result = self.ItemSerializer.serialize(item)
        assert result["count"] == 20

    def test_serialize_item_with_count_attr(self):
        item = self._make_item("Arrow", "Ammo")
        del item.quantity
        item.count = 15
        result = self.ItemSerializer.serialize(item)
        assert result["count"] == 15

    def test_serialize_item_subtype(self):
        item = self._make_item()
        item.subtype = "longsword"
        result = self.ItemSerializer.serialize(item)
        assert result["subtype"] == "longsword"

    def test_serialize_item_equip_states(self):
        item = self._make_item()
        result = self.ItemSerializer.serialize(item)
        assert "equip_states" in result

    def test_serialize_item_status_resistance(self):
        item = self._make_item()
        item.add_status_resistance = {"poison": 0.5}
        result = self.ItemSerializer.serialize(item)
        assert "status_resistances" in result

    def test_serialize_item_damage_resistance(self):
        item = self._make_item()
        item.add_resistance = {"fire": 0.3}
        result = self.ItemSerializer.serialize(item)
        assert "resistances" in result

    def test_serialize_item_power(self):
        item = self._make_item()
        item.power = 15
        result = self.ItemSerializer.serialize(item)
        assert result["power"] == 15

    def test_serialize_item_hidden(self):
        item = self._make_item()
        item.hidden = True
        item.hide_factor = 3
        result = self.ItemSerializer.serialize(item)
        assert result["hidden"] is True
        assert result["hide_factor"] == 3

    def test_serialize_item_merchandise(self):
        item = self._make_item()
        item.merchandise = True
        result = self.ItemSerializer.serialize(item)
        assert result["merchandise"] is True

    def test_serialize_item_announce(self):
        item = self._make_item()
        item.announce = "A gleaming sword lies here."
        result = self.ItemSerializer.serialize(item)
        assert result["announce"] == "A gleaming sword lies here."

    def test_serialize_item_interactions_fallback(self):
        item = self._make_item()
        del item.keywords
        item.interactions = ["take", "use", "drop"]
        result = self.ItemSerializer.serialize(item)
        assert "take" in result["keywords"]

    def test_serialize_item_inventory_only_filtered(self):
        item = self._make_item()
        item.keywords = ["take", "drop", "unequip"]
        result = self.ItemSerializer.serialize(item)
        assert "drop" not in result["keywords"]
        assert "unequip" not in result["keywords"]

    def test_serialize_item_equip_keyword_added(self):
        item = self._make_item()
        item.keywords = ["take"]
        result = self.ItemSerializer.serialize(item)
        assert "equip" in result["keywords"]

    def test_serialize_list_empty(self):
        result = self.ItemSerializer.serialize_list([])
        assert result == []

    def test_serialize_list_multiple(self):
        items = [self._make_item("Sword"), self._make_item("Shield", "Armor")]
        result = self.ItemSerializer.serialize_list(items)
        assert len(result) == 2

    def test_serialize_with_effects_skills_and_effects(self):
        item = self._make_item()
        item.skills = ["Power Strike"]
        item.effects = [{"type": "heal", "amount": 50}]
        item.discovery_message = "You found a sword!"
        item.announce = "A sword gleams."
        result = self.ItemSerializer.serialize_with_effects(item)
        assert "skills" in result
        assert "effects" in result
        assert "discovery_message" in result

    def test_serialize_inventory_no_effects(self):
        item = self._make_item()
        result = self.ItemSerializer.serialize_inventory([item], include_effects=False)
        assert "items" in result
        assert result["count"] == 1
        assert "total_weight" in result

    def test_serialize_inventory_with_effects(self):
        item = self._make_item()
        item.skills = []
        item.effects = []
        result = self.ItemSerializer.serialize_inventory([item], include_effects=True)
        assert result["count"] == 1

    def test_serialize_container(self):
        items = [self._make_item("Gold Coin", "Currency")]
        result = self.ItemSerializer.serialize_container(items)
        assert result["count"] == 1
        assert "items" in result


# ===========================================================================
# InventorySerializer
# ===========================================================================


class TestInventorySerializer:
    """Tests for inventory.py serializers covering uncovered branches."""

    def setup_method(self):
        from src.api.serializers.inventory import (
            InventoryItemSerializer,
            InventorySerializer,
            EquipmentSlotSerializer,
            EquipmentSerializer,
            ItemDetailSerializer,
            ItemComparisonSerializer,
        )

        self.InventoryItemSerializer = InventoryItemSerializer
        self.InventorySerializer = InventorySerializer
        self.EquipmentSlotSerializer = EquipmentSlotSerializer
        self.EquipmentSerializer = EquipmentSerializer
        self.ItemDetailSerializer = ItemDetailSerializer
        self.ItemComparisonSerializer = ItemComparisonSerializer

    def _make_item(self, item_type="Weapon", maintype="Weapon", interactions=None):
        item = MagicMock()
        item.__class__ = MagicMock()
        item.__class__.__name__ = item_type
        item.maintype = maintype
        item.subtype = "longsword"
        item.name = "Iron Sword"
        item.description = "A solid sword"
        item.count = 1
        item.rarity = "uncommon"
        item.weight = 2.5
        item.value = 120
        item.isequipped = False
        item.merchandise = False
        item.interactions = interactions or ["take", "equip", "unequip", "drop"]
        item.damage = 15.0
        item.str_mod = 1
        item.fin_mod = 0
        item.protection = 0
        item.add_str = 0
        item.add_fin = 0
        item.add_maxhp = 0
        item.add_maxfatigue = 0
        item.add_speed = 0
        item.add_endurance = 0
        item.add_charisma = 0
        item.add_intelligence = 0
        item.add_faith = 0
        item.add_weight_tolerance = 0
        item.add_resistance = {}
        item.add_status_resistance = {}
        return item

    def test_serialize_weapon_item(self):
        item = self._make_item()
        result = self.InventoryItemSerializer.serialize(item, 0)
        assert result["type"] == "Weapon"
        assert "damage" in result
        assert result["can_equip"] is True

    def test_serialize_armor_item(self):
        item = self._make_item(item_type="Armor", maintype="Armor")
        item.protection = 8.0
        result = self.InventoryItemSerializer.serialize(item, 1)
        assert "protection" in result

    def test_serialize_boots_item(self):
        item = self._make_item(item_type="Boots", maintype="Boots")
        item.protection = 3.0
        result = self.InventoryItemSerializer.serialize(item, 2)
        assert "protection" in result

    def test_serialize_helm_item(self):
        item = self._make_item(item_type="Helm", maintype="Helm")
        item.protection = 4.0
        result = self.InventoryItemSerializer.serialize(item, 3)
        assert "protection" in result

    def test_serialize_gloves_item(self):
        item = self._make_item(item_type="Gloves", maintype="Gloves")
        item.protection = 2.0
        result = self.InventoryItemSerializer.serialize(item, 4)
        assert "protection" in result

    def test_serialize_accessory_item(self):
        item = self._make_item(item_type="Accessory", maintype="Accessory")
        item.protection = 1.0
        result = self.InventoryItemSerializer.serialize(item, 5)
        assert "protection" in result

    def test_serialize_consumable_item_with_effects(self):
        item = self._make_item(item_type="Restorative", maintype="Consumable")
        item.interactions = ["use", "drop"]
        result = self.InventoryItemSerializer.serialize(item, 0)
        assert result["can_use"] is True
        assert "effects" in result
        assert len(result["effects"]) > 0

    def test_serialize_consumable_unknown_type(self):
        item = self._make_item(item_type="UnknownPotion", maintype="Consumable")
        item.interactions = ["use", "drop"]
        result = self.InventoryItemSerializer.serialize(item, 0)
        assert result["effects"] == []

    def test_serialize_weapon_damage_type(self):
        item = self._make_item()
        item.subtype = "Sword"
        result = self.InventoryItemSerializer.serialize(item, 0)
        assert result["damage_type"] == "slashing"

    def test_serialize_weapon_damage_type_enchanted_override(self):
        item = self._make_item()
        item.subtype = "Sword"
        item.base_damage_type = "fire"
        result = self.InventoryItemSerializer.serialize(item, 0)
        assert result["damage_type"] == "fire"

    def test_serialize_item_with_stat_bonuses(self):
        item = self._make_item()
        item.add_str = 2
        item.add_speed = 3
        result = self.InventoryItemSerializer.serialize(item, 0)
        assert result["bonuses"] == {"strength": 2, "speed": 3}

    def test_serialize_item_without_bonuses_omits_key(self):
        item = self._make_item()
        result = self.InventoryItemSerializer.serialize(item, 0)
        assert "bonuses" not in result

    def test_serialize_item_with_resistances(self):
        item = self._make_item()
        item.add_resistance = {"fire": 0.2}
        item.add_status_resistance = {"poison": 0.5}
        result = self.InventoryItemSerializer.serialize(item, 0)
        assert result["resistances"] == {"fire": 0.2}
        assert result["status_resistances"] == {"poison": 0.5}

    def test_serialize_item_without_resistances_omits_keys(self):
        item = self._make_item()
        result = self.InventoryItemSerializer.serialize(item, 0)
        assert "resistances" not in result
        assert "status_resistances" not in result

    def test_serialize_item_comparison_with_real_counterpart(self):
        equipped = self._make_item()
        equipped.isequipped = True
        equipped.damage = 10.0
        equipped.add_str = 1

        candidate = self._make_item()
        candidate.isequipped = False
        candidate.damage = 18.0
        candidate.add_str = 3

        player = MagicMock()
        player.inventory_list = [equipped, candidate]

        result = self.InventoryItemSerializer.serialize(candidate, 1, player)
        comparison = result["comparison"]
        assert comparison["comparison_type"] == "item_to_item"
        assert comparison["differences"]["damage_diff"] == 8.0
        assert comparison["differences"]["bonus_diffs"] == {"strength": 2}

    def test_serialize_item_comparison_empty_slot(self):
        candidate = self._make_item()
        candidate.isequipped = False

        player = MagicMock()
        player.inventory_list = [candidate]

        result = self.InventoryItemSerializer.serialize(candidate, 0, player)
        assert result["comparison"]["comparison_type"] == "empty_to_item"

    def test_serialize_item_no_maintype_skips_comparison(self):
        candidate = self._make_item(maintype=None)
        candidate.isequipped = False

        player = MagicMock()
        player.inventory_list = [candidate]

        result = self.InventoryItemSerializer.serialize(candidate, 0, player)
        assert "comparison" not in result

    def test_serialize_item_multi_equip_accessory_skips_comparison(self):
        candidate = self._make_item(item_type="Accessory", maintype="Accessory")
        candidate.subtype = "Ring"
        candidate.isequipped = False

        player = MagicMock()
        player.inventory_list = [candidate]

        result = self.InventoryItemSerializer.serialize(candidate, 0, player)
        assert "comparison" not in result

    def test_serialize_item_equipped_skips_comparison(self):
        item = self._make_item()
        item.isequipped = True

        player = MagicMock()
        player.inventory_list = [item]

        result = self.InventoryItemSerializer.serialize(item, 0, player)
        assert "comparison" not in result

    def test_get_equip_slot_status_skips_other_maintypes(self):
        from src.api.serializers.inventory import _get_equip_slot_status

        unrelated = self._make_item(item_type="Helm", maintype="Helm")
        unrelated.isequipped = True
        candidate = self._make_item()  # maintype="Weapon"

        player = MagicMock()
        player.inventory_list = [unrelated, candidate]

        comparable, counterpart = _get_equip_slot_status(player, candidate)
        assert comparable is True
        assert counterpart is None

    def test_get_equip_slot_status_skips_mismatched_accessory_subtype(self):
        from src.api.serializers.inventory import _get_equip_slot_status

        equipped_necklace = self._make_item(item_type="Accessory", maintype="Accessory")
        equipped_necklace.subtype = "Necklace"
        equipped_necklace.isequipped = True

        candidate = self._make_item(item_type="Accessory", maintype="Accessory")
        candidate.subtype = "Circlet"

        player = MagicMock()
        player.inventory_list = [equipped_necklace, candidate]

        comparable, counterpart = _get_equip_slot_status(player, candidate)
        assert comparable is True
        assert counterpart is None

    def test_diff_resistance_dicts_with_real_deltas(self):
        from src.api.serializers.inventory import _diff_resistance_dicts

        current = self._make_item()
        current.add_resistance = {"fire": 0.1, "ice": 0.3}
        candidate = self._make_item()
        candidate.add_resistance = {"fire": 0.4, "earth": 0.2}

        diffs = _diff_resistance_dicts(current, candidate, "add_resistance")
        assert diffs == {"fire": pytest.approx(0.3), "ice": -0.3, "earth": 0.2}

    def test_inventory_serializer_with_inventory_list(self):
        player = MagicMock()
        item = self._make_item()
        player.inventory_list = [item]
        player.carrying_capacity = 100.0
        player.inventory_slots = 20
        result = self.InventorySerializer.serialize(player)
        assert result["item_count"] == 1
        assert "total_weight" in result

    def test_inventory_serializer_fallback_to_inventory(self):
        player = MagicMock(spec=["inventory", "carrying_capacity", "inventory_slots"])
        item = self._make_item()
        player.inventory = [item]
        player.carrying_capacity = 50.0
        player.inventory_slots = 10
        result = self.InventorySerializer.serialize(player)
        assert result["item_count"] == 1

    def test_inventory_serializer_empty(self):
        player = MagicMock()
        player.inventory_list = []
        player.carrying_capacity = 100.0
        player.inventory_slots = 20
        result = self.InventorySerializer.serialize(player)
        assert result["item_count"] == 0
        assert result["total_weight"] == 0.0

    def test_equipment_slot_serializer_empty_slot(self):
        result = self.EquipmentSlotSerializer.serialize("head", None)
        assert result["equipped"] is False
        assert result["slot"] == "head"
        assert result["armor"] == 0

    def test_equipment_slot_serializer_with_item(self):
        item = MagicMock()
        item.__class__.__name__ = "Helm"
        item.name = "Iron Helm"
        item.armor = 5.0
        item.damage = 0.0
        item.weight = 1.5
        item.value = 80
        item.stat_bonuses = {}
        item.resistance_bonuses = {}
        item.rarity = "common"
        result = self.EquipmentSlotSerializer.serialize("head", item)
        assert result["equipped"] is True
        assert result["item_name"] == "Iron Helm"
        assert result["armor"] == 5

    def test_equipment_serializer_with_equipped_dict(self):
        player = MagicMock()
        weapon = MagicMock()
        weapon.name = "Sword"
        weapon.__class__.__name__ = "Weapon"
        weapon.armor = 0.0
        weapon.damage = 10.0
        weapon.weight = 2.0
        weapon.value = 100
        weapon.stat_bonuses = {"attack": 5}
        weapon.resistance_bonuses = {}
        weapon.rarity = "uncommon"
        player.equipped = {"weapon": weapon}
        player.inventory_list = []
        result = self.EquipmentSerializer.serialize(player)
        assert "weapon" in result["equipped"]
        assert result["total_stat_bonuses"]["attack"] == 5

    def test_equipment_serializer_empty_equipment_fallback(self):
        player = MagicMock()
        player.equipped = {}
        player.equipment = {}
        weapon = MagicMock()
        weapon.isequipped = True
        weapon.__class__.__name__ = "Weapon"
        weapon.name = "Dagger"
        weapon.armor = 0.0
        weapon.damage = 5.0
        weapon.weight = 0.5
        weapon.value = 30
        weapon.stat_bonuses = {}
        weapon.resistance_bonuses = {}
        weapon.rarity = "common"
        player.eq_weapon = weapon
        player.shield = None
        player.head = None
        player.body = None
        player.legs = None
        player.feet = None
        player.hands = None
        player.accessory_1 = None
        player.accessory_2 = None
        player.inventory_list = []
        result = self.EquipmentSerializer.serialize(player)
        assert "weapon" in result["equipped"]

    def test_equipment_serializer_unequipped_count(self):
        player = MagicMock()
        player.equipped = {}
        player.equipment = {}
        player.eq_weapon = None
        player.shield = None
        player.head = None
        player.body = None
        player.legs = None
        player.feet = None
        player.hands = None
        player.accessory_1 = None
        player.accessory_2 = None
        equippable = MagicMock()
        equippable.equip = MagicMock()
        equippable.equipped_state = False
        player.inventory_list = [equippable]
        result = self.EquipmentSerializer.serialize(player)
        assert result["unequipped_equippable_count"] == 1

    def test_item_detail_serializer_basic(self):
        item = MagicMock()
        item.__class__.__name__ = "Weapon"
        item.name = "Blade"
        item.description = "Sharp"
        item.count = 1
        item.rarity = "rare"
        item.weight = 1.5
        item.value = 250
        item.armor = 0.0
        item.protection = 0.0
        item.damage = 20.0
        item.magic_attack = 0
        item.magic_defense = 0
        item.accuracy = 0
        item.evasion = 0
        item.stat_bonuses = {}
        item.resistance_bonuses = {}
        item.merchandise = False
        item.hidden = False
        result = self.ItemDetailSerializer.serialize(
            item, equipped=True, inventory_index=2
        )
        assert result["name"] == "Blade"
        assert result["equipped"] is True
        assert result["inventory_index"] == 2

    def test_item_comparison_empty_to_item(self):
        candidate = MagicMock()
        candidate.__class__.__name__ = "Weapon"
        candidate.name = "New Sword"
        candidate.description = ""
        candidate.count = 1
        candidate.rarity = "common"
        candidate.weight = 2.0
        candidate.value = 100
        candidate.armor = 0.0
        candidate.protection = 0.0
        candidate.damage = 12.0
        candidate.magic_attack = 0
        candidate.magic_defense = 0
        candidate.accuracy = 0
        candidate.evasion = 0
        candidate.stat_bonuses = {}
        candidate.resistance_bonuses = {}
        candidate.merchandise = False
        candidate.hidden = False
        result = self.ItemComparisonSerializer.serialize(None, candidate)
        assert result["comparison_type"] == "empty_to_item"
        assert result["recommendation"] == "upgrade"

    def test_item_comparison_upgrade(self):
        current = MagicMock()
        current.__class__.__name__ = "Weapon"
        current.name = "Old Sword"
        current.description = ""
        current.count = 1
        current.rarity = "common"
        current.weight = 2.0
        current.value = 50
        current.armor = 0.0
        current.protection = 0.0
        current.damage = 8.0
        current.magic_attack = 0
        current.magic_defense = 0
        current.accuracy = 0
        current.evasion = 0
        current.stat_bonuses = {}
        current.resistance_bonuses = {}
        current.merchandise = False
        current.hidden = False

        candidate = MagicMock()
        candidate.__class__.__name__ = "Weapon"
        candidate.name = "New Sword"
        candidate.description = ""
        candidate.count = 1
        candidate.rarity = "uncommon"
        candidate.weight = 2.0
        candidate.value = 150
        candidate.armor = 0.0
        candidate.protection = 0.0
        candidate.damage = 20.0
        candidate.magic_attack = 0
        candidate.magic_defense = 0
        candidate.accuracy = 0
        candidate.evasion = 0
        candidate.stat_bonuses = {}
        candidate.resistance_bonuses = {}
        candidate.merchandise = False
        candidate.hidden = False
        result = self.ItemComparisonSerializer.serialize(current, candidate)
        assert result["comparison_type"] == "item_to_item"
        assert result["recommendation"] == "upgrade"

    def test_item_comparison_downgrade(self):
        current = MagicMock()
        current.__class__.__name__ = "Weapon"
        current.name = "Good Sword"
        current.description = ""
        current.count = 1
        current.rarity = "rare"
        current.weight = 2.0
        current.value = 300
        current.armor = 10.0
        current.protection = 10.0
        current.damage = 25.0
        current.magic_attack = 0
        current.magic_defense = 0
        current.accuracy = 0
        current.evasion = 0
        current.stat_bonuses = {}
        current.resistance_bonuses = {}
        current.merchandise = False
        current.hidden = False

        candidate = MagicMock()
        candidate.__class__.__name__ = "Weapon"
        candidate.name = "Weak Sword"
        candidate.description = ""
        candidate.count = 1
        candidate.rarity = "common"
        candidate.weight = 1.0
        candidate.value = 30
        candidate.armor = 0.0
        candidate.protection = 0.0
        candidate.damage = 5.0
        candidate.magic_attack = 0
        candidate.magic_defense = 0
        candidate.accuracy = 0
        candidate.evasion = 0
        candidate.stat_bonuses = {}
        candidate.resistance_bonuses = {}
        candidate.merchandise = False
        candidate.hidden = False
        result = self.ItemComparisonSerializer.serialize(current, candidate)
        assert result["recommendation"] == "downgrade"

    def test_item_comparison_sidegrade(self):
        current = MagicMock()
        current.__class__.__name__ = "Weapon"
        current.name = "Sword A"
        current.description = ""
        current.count = 1
        current.rarity = "common"
        current.weight = 2.0
        current.value = 100
        current.armor = 5.0
        current.protection = 5.0
        current.damage = 15.0
        current.magic_attack = 0
        current.magic_defense = 0
        current.accuracy = 0
        current.evasion = 0
        current.stat_bonuses = {}
        current.resistance_bonuses = {}
        current.merchandise = False
        current.hidden = False

        candidate = MagicMock()
        candidate.__class__.__name__ = "Weapon"
        candidate.name = "Sword B"
        candidate.description = ""
        candidate.count = 1
        candidate.rarity = "common"
        candidate.weight = 2.0
        candidate.value = 100
        candidate.armor = 8.0
        candidate.protection = 8.0
        candidate.damage = 10.0
        candidate.magic_attack = 0
        candidate.magic_defense = 0
        candidate.accuracy = 0
        candidate.evasion = 0
        candidate.stat_bonuses = {}
        candidate.resistance_bonuses = {}
        candidate.merchandise = False
        candidate.hidden = False
        result = self.ItemComparisonSerializer.serialize(current, candidate)
        assert result["recommendation"] == "sidegrade"


# ===========================================================================
# EventSerializer
# ===========================================================================


class TestEventSerializer:
    """Tests for EventSerializer covering remaining uncovered branches."""

    def setup_method(self):
        from src.api.serializers.event_serializer import EventSerializer

        self.EventSerializer = EventSerializer

    def _make_event(self, name="TestEvent"):
        event = MagicMock()
        event.description = "A test event"
        event.name = name
        event.repeat = False
        event.one_time_only = True
        event.triggered = False
        event.completed = False
        event.event_type = "generic"
        event.hidden = False
        event.hide_factor = 0
        event.delay_mode = None
        return event

    def test_serialize_none_event(self):
        result = self.EventSerializer.serialize(None)
        assert result == {}

    def test_serialize_basic_event(self):
        event = self._make_event()
        result = self.EventSerializer.serialize(event)
        assert result["name"] == "TestEvent"
        assert result["triggered"] is False

    def test_serialize_event_with_delay_mode(self):
        event = self._make_event()
        event.delay_mode = "fade"
        event.delay_duration = 2000
        result = self.EventSerializer.serialize(event)
        assert result["delay_mode"] == "fade"
        assert result["delay_duration"] == 2000

    def test_serialize_with_conditions_has_check(self):
        event = self._make_event()
        event.check_conditions = MagicMock()
        event.required_item = "sword"
        event.required_level = 5
        event.required_flag = "quest_started"
        event.params = {"key": "val"}
        result = self.EventSerializer.serialize_with_conditions(event)
        assert result["has_conditions_check"] is True
        assert result["required_item"] == "sword"
        assert result["required_level"] == 5
        assert result["required_flag"] == "quest_started"
        assert result["params"] is not None

    def test_serialize_with_conditions_no_params(self):
        event = self._make_event()
        event.check_conditions = MagicMock()
        event.params = None
        result = self.EventSerializer.serialize_with_conditions(event)
        assert result["params"] is None

    def test_serialize_with_consequences_string(self):
        event = self._make_event()
        event.consequence = "Quest completed"
        event.experience_reward = 100
        event.gold_reward = 50
        event.item_rewards = ["sword"]
        event.item_reward = "shield"
        event.story_flag = "act1_complete"
        event.chapter = 1
        event.section = "prologue"
        result = self.EventSerializer.serialize_with_consequences(event)
        assert result["consequence"] == "Quest completed"
        assert result["experience_reward"] == 100

    def test_serialize_with_consequences_complex_object(self):
        event = self._make_event()
        event.consequence = object()
        result = self.EventSerializer.serialize_with_consequences(event)
        assert isinstance(result["consequence"], str)

    def test_serialize_story_event(self):
        event = self._make_event()
        event.story_name = "The Beginning"
        event.narrative_text = "Long ago..."
        event.dialogue = ["Hello", "World"]
        event.choices = ["Option A", "Option B"]
        event.enemy_spawned = True
        event.encounter_type = "ambush"
        event.consequence = "story progresses"
        result = self.EventSerializer.serialize_story_event(event)
        assert result["is_story_event"] is True
        assert result["story_name"] == "The Beginning"
        assert result["choice_count"] == 2
        assert result["enemy_spawned"] is True

    def test_serialize_combat_event(self):
        event = self._make_event()
        event.trigger_on = "enter"
        event.trigger_condition = "hp_low"
        event.enemy_type = "Goblin"
        event.enemy_level = 3
        event.enemy_count = 2
        event.victory_message = "You won!"
        event.defeat_message = "You lost."
        result = self.EventSerializer.serialize_combat_event(event)
        assert result["is_combat_event"] is True
        assert result["enemy_type"] == "Goblin"

    def test_serialize_conditional_event(self):
        event = self._make_event()
        event.conditions = ["cond1", "cond2"]
        event.success_consequence = "win"
        event.failure_consequence = "lose"
        event.trigger_on_enter = True
        event.trigger_on_exit = False
        event.trigger_in_combat = False
        event.consequence = "something"
        result = self.EventSerializer.serialize_conditional_event(event)
        assert result["is_conditional"] is True
        assert result["condition_count"] == 2

    def test_serialize_with_input_needs_input(self):
        event = self._make_event()
        event.needs_input = True
        event.api_event_id = "evt_123"
        event.input_type = "choice"
        event.input_prompt = "What do you do?"
        event.input_options = ["Attack", "Flee"]
        result = self.EventSerializer.serialize_with_input(event)
        assert result["needs_input"] is True
        assert result["event_id"] == "evt_123"
        assert result["input_type"] == "choice"
        assert result["input_options"] == ["Attack", "Flee"]

    def test_serialize_with_input_number_type(self):
        event = self._make_event()
        event.needs_input = True
        event.api_event_id = None
        event.input_type = "number"
        event.input_prompt = "Enter amount:"
        event.input_min = 1
        event.input_max = 100
        result = self.EventSerializer.serialize_with_input(event)
        assert result["input_type"] == "number"
        assert result["input_min"] == 1
        assert result["input_max"] == 100

    def test_serialize_with_input_text_type(self):
        event = self._make_event()
        event.needs_input = True
        event.api_event_id = None
        event.input_type = "text"
        event.input_prompt = "Your name?"
        event.input_max_length = 100
        result = self.EventSerializer.serialize_with_input(event)
        assert result["input_type"] == "text"
        assert result["input_max_length"] == 100

    def test_serialize_with_input_text_default_max_length(self):
        event = self._make_event()
        event.needs_input = True
        event.api_event_id = None
        event.input_type = "text"
        event.input_prompt = "Name?"
        del event.input_max_length
        result = self.EventSerializer.serialize_with_input(event)
        assert result["input_max_length"] == 500

    def test_serialize_with_input_no_input_needed(self):
        event = self._make_event()
        event.needs_input = False
        event.api_event_id = None
        del event.requires_input
        result = self.EventSerializer.serialize_with_input(event)
        assert result["needs_input"] is False

    def test_detect_input_by_class_name(self):
        event = MagicMock()
        event.__class__.__name__ = "WhisperingStatue"
        event.needs_input = False
        del event.requires_input
        result = self.EventSerializer._detect_input_requirement(event)
        assert result is True

    def test_detect_input_requires_input_method(self):
        event = MagicMock()
        event.needs_input = False
        event.requires_input = MagicMock(return_value=True)
        result = self.EventSerializer._detect_input_requirement(event)
        assert result is True

    def test_infer_input_type_choice_from_choices(self):
        event = MagicMock()
        event.choices = ["A", "B"]
        del event.input_options
        del event.get_input_options
        result = self.EventSerializer._infer_input_type(event)
        assert result == "choice"

    def test_infer_input_type_number(self):
        event = MagicMock(spec=["input_min", "input_max"])
        event.input_min = 1
        event.input_max = 10
        result = self.EventSerializer._infer_input_type(event)
        assert result == "number"

    def test_infer_input_type_default(self):
        event = MagicMock(spec=[])
        result = self.EventSerializer._infer_input_type(event)
        assert result == "choice"


# ===========================================================================
# ObjectSerializer
# ===========================================================================


class TestObjectSerializer:
    """Tests for ObjectSerializer covering remaining uncovered branches."""

    def setup_method(self):
        from src.api.serializers.object_serializer import ObjectSerializer

        self.ObjectSerializer = ObjectSerializer

    def _make_obj(self, name="Chest"):
        obj = MagicMock()
        obj.name = name
        obj.description = "A sturdy chest"
        obj.aliases = []
        obj.action_aliases = []
        obj.keywords = ["open", "examine"]
        obj.hidden = False
        obj.hide_factor = 0
        obj.locked = False
        obj.state = "closed"
        obj.opened = False
        obj.is_passable = False
        obj.open_message = "The chest opens."
        obj.idle_message = None
        return obj

    def test_serialize_none_obj(self):
        result = self.ObjectSerializer.serialize(None)
        assert result == {}

    def test_serialize_basic_obj(self):
        obj = self._make_obj()
        result = self.ObjectSerializer.serialize(obj)
        assert result["name"] == "Chest"

    def test_serialize_dict_obj(self):
        obj = {
            "id": "door_1",
            "name": "Iron Door",
            "type": "Door",
            "description": "A heavy iron door.",
            "aliases": [],
            "action_aliases": [],
        }
        result = self.ObjectSerializer._serialize_base(obj)
        assert result["name"] == "Iron Door"
        assert result["type"] == "Door"

    def test_serialize_obj_with_locked_state(self):
        obj = self._make_obj()
        obj.locked = True
        obj.state = "closed"
        obj.opened = False
        result = self.ObjectSerializer._serialize_base(obj)
        assert result["locked"] is True
        assert "unlock" in result["keywords"]

    def test_serialize_obj_unlocked_closed(self):
        obj = self._make_obj()
        obj.locked = False
        obj.state = "closed"
        obj.opened = False
        result = self.ObjectSerializer._serialize_base(obj)
        assert "open" in result["keywords"]

    def test_serialize_container_with_inventory(self):
        obj = self._make_obj()
        item = MagicMock()
        item.name = "Gold"
        item.description = ""
        item.value = 10
        item.weight = 0.1
        item.aliases = []
        item.action_aliases = []
        item.interactions = ["take"]
        item.keywords = ["take"]
        obj.inventory = [item]

        try:
            from objects import Container as C
        except ImportError:
            from src.objects import Container as C

        obj.__class__ = C

        with patch.object(
            self.ObjectSerializer,
            "serialize_container",
            wraps=self.ObjectSerializer.serialize_container,
        ):
            result = self.ObjectSerializer.serialize(obj)
        assert result.get("is_container") is True

    def test_serialize_container_dispatch(self):
        from src.objects import Container

        obj = MagicMock()
        obj.__class__ = Container
        obj.name = "Barrel"
        obj.description = "A wooden barrel"
        obj.aliases = []
        obj.action_aliases = []
        obj.keywords = []
        obj.is_passable = False
        obj.inventory = []
        with patch(
            "src.api.serializers.object_serializer.ObjectSerializer.serialize_container"
        ) as mock_sc:
            mock_sc.return_value = {"is_container": True, "name": "Barrel"}
            result = self.ObjectSerializer.serialize(obj)
        assert result["is_container"] is True

    def test_serialize_container_with_contents_attr(self):
        obj = self._make_obj("Box")
        obj.__class__.__name__ = "NotContainer"
        item = MagicMock()
        item.name = "Gem"
        item.description = ""
        item.value = 500
        item.weight = 0.05
        item.aliases = []
        item.action_aliases = []
        item.keywords = ["take"]
        item.interactions = ["take"]
        del obj.inventory
        obj.contents = [item]
        obj.items_here = None
        result = self.ObjectSerializer.serialize_container(obj)
        assert result["is_container"] is True
        assert result["item_count"] == 1

    def test_serialize_container_with_items_here(self):
        obj = self._make_obj("Room")
        obj.__class__.__name__ = "NotContainer"
        item = MagicMock()
        item.name = "Potion"
        item.description = ""
        item.value = 25
        item.weight = 0.3
        item.aliases = []
        item.action_aliases = []
        item.keywords = ["take"]
        item.interactions = ["take"]
        del obj.inventory
        del obj.contents
        obj.items_here = [item]
        result = self.ObjectSerializer.serialize_container(obj)
        assert result["item_count"] == 1

    def test_serialize_container_empty(self):
        obj = self._make_obj("Empty Box")
        del obj.inventory
        del obj.contents
        del obj.items_here
        result = self.ObjectSerializer.serialize_container(obj)
        assert result["contents"] == []
        assert result["item_count"] == 0

    def test_serialize_container_with_capacity(self):
        obj = self._make_obj()
        obj.capacity = 10
        del obj.inventory
        del obj.contents
        del obj.items_here
        result = self.ObjectSerializer.serialize_container(obj)
        assert result["capacity"] == 10

    def test_serialize_interactive(self):
        obj = self._make_obj()
        obj.events = [MagicMock(), MagicMock()]
        obj.consequence_text = "Something happens."
        obj.use_message = "You use it."
        obj.examine_message = "You examine it."
        obj.one_time_only = True
        result = self.ObjectSerializer.serialize_interactive(obj)
        assert result["has_events"] is True
        assert result["events"] == 2
        assert result["consequence"] == "Something happens."

    def test_serialize_interactive_no_events(self):
        obj = self._make_obj()
        del obj.events
        result = self.ObjectSerializer.serialize_interactive(obj)
        assert result["has_events"] is False

    def test_serialize_door(self):
        obj = self._make_obj("Oak Door")
        obj.opened = False
        obj.locked = True
        obj.open_message = "The door creaks open."
        obj.locked_message = "The door is locked."
        obj.leads_to = "dungeon_entrance"
        result = self.ObjectSerializer.serialize_door(obj)
        assert result["is_door"] is True
        assert result["locked"] is True
        assert result["leads_to"] == "dungeon_entrance"

    def test_serialize_shrine(self):
        obj = self._make_obj("Altar")
        obj.blessing_text = "You feel blessed."
        obj.blessing_effect = {"hp": 20}
        obj.last_blessed_at = "2026-01-01"
        result = self.ObjectSerializer.serialize_shrine(obj)
        assert result["is_shrine"] is True
        assert result["blessing"] == "You feel blessed."
        assert result["last_blessed_at"] == "2026-01-01"
