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
# Helpers — real engine objects wherever affordable
#
# Issues #411/#412/#430/#431/#432 all shipped the same way: a serializer read
# an attribute name no engine class defines, the `getattr(obj, name, default)`
# fallback swallowed the miss, and the only tests were bare `MagicMock()`s
# whose attributes had been hand-set to the fabricated name. A bare MagicMock
# materialises *whatever* attribute is asked of it, so those tests could not
# fail — "a mock cannot catch a mock agreeing with itself" (CLAUDE.md).
#
# The factories below therefore return **real** `Player` / `NPC` / `State` /
# `Item` instances (all cheap: ~0.6 ms for a Player, ~0.05 ms for an NPC), and
# `_set()` refuses to invent an attribute the real class does not already
# define. A serializer that reads a renamed attribute now takes the genuine
# AttributeError path and falls back to its default, which the assertions
# below catch.
# ---------------------------------------------------------------------------


def _set(obj, **overrides):
    """Assign attributes to a real engine object, refusing to invent new ones.

    The guard is the whole point: a test that could fabricate
    `combatant.attack_power` would re-open issue #430.
    """
    for key, value in overrides.items():
        if not hasattr(obj, key):
            raise AttributeError(
                f"{type(obj).__name__} has no attribute {key!r} — do not "
                f"fabricate engine attributes in tests (see issue #430)."
            )
        setattr(obj, key, value)
    return obj


def _weapon(cls=None, **overrides):
    """A real engine weapon from `src.items` (default: Shortsword, 25 dmg)."""
    from src import items

    return _set((cls or items.Shortsword)(), **overrides)


def _player(**overrides):
    """A real `src.player.Player`, with a real Shortsword equipped.

    Jean's own starting kit (Tattered Cloth / Cloth Hood / Wedding Band) is
    left in place so equipment serialization sees a realistic inventory.
    """
    from src.player import Player

    player = Player()
    player.eq_weapon = _weapon()
    return _set(player, **overrides)


def _npc(name="Goblin", **overrides):
    """A real `src.npc.NPC`.

    Deliberately built from the base class rather than a mock so the absence
    of `level`, `heat`, `battle_symbol` and `eq_weapon` on real NPCs is
    faithfully reproduced.
    """
    from src.npc import NPC

    npc = NPC(
        name=name,
        description="A generic foe",
        damage=15,
        aggro=True,
        exp_award=50,
        maxhp=100,
        protection=5,
        speed=8,
        finesse=9,
        endurance=10,
        strength=12,
        charisma=6,
        intelligence=7,
    )
    npc.hp = 80
    return _set(npc, **overrides)


def _combatant(name="Jean", is_player=True, **overrides):
    """Real Player or real NPC, whichever the test needs."""
    if is_player:
        return _player(name=name, **overrides)
    return _npc(name=name, **overrides)


def _state(name="Poisoned", statustype="poison", beats_left=2, target=None):
    """A real `src.states.State` (never a mock).

    Real States expose `statustype` (e.g. "poison", "stun") — never
    `state_type` — and have no damage_per_turn/healing_per_turn/resistable
    attributes; constructing the genuine class is what keeps that honest.
    """
    from src.states import State

    state = State(
        name=name,
        target=target,
        description="Taking poison damage.",
        statustype=statustype,
    )
    state.beats_left = beats_left
    return state


def _move(cls=None, **overrides):
    """A real `src.moves` Move instance bound to a real Player."""
    import src.moves as moves

    user = overrides.pop("user", None) or _player()
    move = (cls or moves.PowerStrike)(user)
    return _set(move, **overrides)


# ===========================================================================
# CombatStateSerializer
# ===========================================================================


class TestCombatStateSerializer:
    """Tests for CombatStateSerializer covering uncovered branches."""

    def setup_method(self):
        from src.api.serializers.combat import CombatStateSerializer

        self.CombatStateSerializer = CombatStateSerializer

    def test_serialize_combat_state_basic(self):
        player = _combatant()
        enemy = _combatant(name="Goblin", is_player=False, hp=40, maxhp=60)
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
        player = _combatant()
        ally = _combatant(name="Ally", is_player=False, friend=True)
        enemy = _combatant(name="Troll", is_player=False)
        result = self.CombatStateSerializer.serialize_combat_state(
            player, [enemy], allies=[ally]
        )
        assert len(result["allies"]) == 1
        assert len(result["enemies"]) == 1
        assert len(result["combatants"]) == 3

    def test_serialize_turn_data_player(self):
        player = _combatant()
        result = self.CombatStateSerializer.serialize_turn_data(player)
        assert result["name"] == "Jean"
        assert result["type"] == "player"
        assert "available_actions" in result

    def test_serialize_turn_data_enemy(self):
        enemy = _combatant(name="Orc", is_player=False)
        result = self.CombatStateSerializer.serialize_turn_data(enemy)
        assert result["type"] == "enemy"

    def test_serialize_battle_summary_victory(self):
        player = _combatant()
        enemy = _combatant(name="Goblin", is_player=False, hp=0, maxhp=40)
        enemy.hp = 0
        enemy.exp_reward = 50
        result = self.CombatStateSerializer.serialize_battle_summary(
            player, [enemy], victory=True
        )
        assert result["status"] == "victory"
        assert result["enemies_defeated"] == 1
        assert result["experience_gained"] == 50

    def test_serialize_battle_summary_defeat(self):
        player = _combatant()
        enemy = _combatant(name="Dragon", is_player=False, hp=200, maxhp=200)
        result = self.CombatStateSerializer.serialize_battle_summary(
            player, [enemy], victory=False
        )
        assert result["status"] == "defeat"
        assert result["experience_gained"] == 0
        assert result["items_dropped"] == []

    def test_get_turn_order(self):
        player = _combatant()
        enemy = _combatant(name="Goblin", is_player=False)
        order = self.CombatStateSerializer._get_turn_order(player, [enemy])
        assert order[0] == "player"
        assert "enemy_0" in order

    def test_get_available_actions_with_inventory(self):
        combatant = _combatant()
        actions = self.CombatStateSerializer._get_available_actions(combatant)
        assert actions[:3] == ["attack", "defend", "flee"]
        assert "use_item" in actions  # real Player has an `inventory`

    def test_get_available_actions_omits_moves_because_it_reads_a_dead_name(self):
        """KNOWN WIRE-FIELD DEFECT — src/api/serializers/combat.py:212.

        `_get_available_actions` extends the action list from
        `combatant.moves`. No engine class defines `moves`; the real
        attribute is `known_moves` (src/combatant.py). Fed a real Player with
        twelve castable moves, the helper therefore reports none of them.

        The previous test used a bare `MagicMock()`, which materialised
        `.moves` on demand and so could never see this. Asserting on a real
        Player is the proof. If the serializer is corrected to read
        `known_moves`, this test fails — update it then.
        """
        combatant = _combatant()
        assert combatant.known_moves, "real Player starts with castable moves"
        assert not hasattr(combatant, "moves")

        actions = self.CombatStateSerializer._get_available_actions(combatant)

        assert actions == ["attack", "defend", "flee", "use_item"]
        assert not any(
            m.name in actions for m in combatant.known_moves
        )

    def test_calculate_experience_reads_a_dead_name_on_real_npcs(self):
        """KNOWN WIRE-FIELD DEFECT — src/api/serializers/combat.py:227-231.

        `_calculate_experience` sums `enemy.exp_reward`, falling back to
        `enemy.level * 10`. Real NPCs define **neither**: the engine attribute
        is `exp_award` (see `NPC.__init__`) and NPCs carry no `level` at all.
        Every real battle summary therefore awards 0 experience.

        The two tests this replaces set `exp_reward`/`level` on a bare
        MagicMock and asserted the number back — the mock agreeing with
        itself. Real NPCs are the only way to see the drift.
        """
        slime, goblin = _npc(name="Slime"), _npc(name="Goblin")
        for enemy in (slime, goblin):
            assert enemy.exp_award == 50
            assert not hasattr(enemy, "exp_reward")
            assert not hasattr(enemy, "level")

        assert self.CombatStateSerializer._calculate_experience([slime, goblin]) == 0

    @pytest.mark.parametrize(
        "attrs, expected",
        [
            ({"exp_reward": 100}, 100),
            ({"exp_reward": 30}, 30),
            ({"level": 5}, 50),
            ({}, 0),
        ],
        ids=["exp_reward", "exp_reward_small", "level_fallback", "neither"],
    )
    def test_calculate_experience_arithmetic(self, attrs, expected):
        """The summing arithmetic itself, on spec-locked stand-ins.

        `spec=list(attrs)` is what makes this meaningful: the stand-in exposes
        *only* the listed attributes, so the `hasattr` branch under test is
        genuinely taken (or not) instead of being satisfied by MagicMock's
        auto-attribute.
        """
        enemy = MagicMock(spec=list(attrs))
        for key, value in attrs.items():
            setattr(enemy, key, value)
        assert self.CombatStateSerializer._calculate_experience([enemy]) == expected

    def test_get_drops_with_inventory(self):
        """Drops mirror a real `src.items` weapon field-for-field."""
        from src import items

        enemy = _combatant(name="Boss", is_player=False)
        sword = _weapon(items.Longsword)
        sword._enchantment_count = 2
        enemy.inventory = [sword]

        drops = self.CombatStateSerializer._get_drops([enemy])

        assert len(drops) == 1
        assert drops[0] == {
            "name": sword.name,
            # A real weapon carries no `count`; the serializer defaults it to 1.
            "quantity": 1,
            "type": "Longsword",
            "subtype": sword.subtype,
            "weight": sword.weight,
            "value": sword.value,
            "enchantment_count": 2,
            "description": sword.description,
        }
        # Real weights/values are non-trivial: a silently defaulted payload
        # (the #430 signature) would show 0/None here.
        assert drops[0]["weight"] > 0
        assert drops[0]["subtype"] == "Sword"

    def test_get_drops_reports_nothing_for_an_enemy_without_inventory(self):
        enemy = MagicMock(spec=[])
        assert self.CombatStateSerializer._get_drops([enemy]) == []

    def test_get_drops_uses_enchantment_count_fallback(self):
        enemy = _combatant(name="Boss", is_player=False)
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
        """Consumables mirror a real `src.items` consumable field-for-field."""
        from src import items

        player = _combatant()
        potion = items.Restorative()
        potion.count = 2
        player.inventory = [potion]

        consumables = self.CombatStateSerializer._get_consumables(player)

        assert consumables == [
            {
                "name": potion.name,
                "qty": 2,
                "value": potion.value,
                "description": potion.description,
            }
        ]
        assert consumables[0]["value"] > 0
        assert consumables[0]["description"]

    def test_get_consumables_lists_jeans_whole_starting_inventory(self):
        """The helper deliberately lists *everything*, not just consumables.

        Pinning that against Jean's real starting kit documents the current
        contract (the LLM strategist filters, the serializer does not) and
        catches an accidental narrowing.
        """
        player = _combatant()
        names = [c["name"] for c in self.CombatStateSerializer._get_consumables(player)]
        assert names == [item.name for item in player.inventory]
        assert "Tattered Cloth" in names  # armour, not a consumable

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
        player = _combatant(hp=80)
        result = self.CombatantSerializer.serialize_combatant(player)
        assert result["id"] == "player"
        assert result["type"] == "player"
        assert result["health"]["current"] == 80
        assert result["health"]["max"] == player.maxhp
        # Aliases must agree with the nested block — the client reads both.
        assert result["hp"] == 80
        assert result["max_hp"] == player.maxhp
        assert result["max_fatigue"] == result["maxfatigue"] == player.maxfatigue
        assert result["name"] == player.name == "Jean"
        assert result["level"] == player.level
        assert result["heat"] == player.heat

    def test_serialize_combatant_enemy(self):
        enemy = _combatant(name="Goblin", is_player=False)
        result = self.CombatantSerializer.serialize_combatant(enemy)
        assert result["id"].startswith("enemy_")
        assert result["type"] == "npc"

    def test_serialize_combatant_ally(self):
        ally = _combatant(name="Friend", is_player=False, friend=True)
        result = self.CombatantSerializer.serialize_combatant(ally)
        assert result["id"].startswith("ally_")

    def test_serialize_combatant_with_reference_in_range(self):
        player = _combatant()
        enemy = _combatant(name="Goblin", is_player=False)
        enemy.combat_proximity = 2
        result = self.CombatantSerializer.serialize_combatant(enemy, reference=player)
        assert result["in_range"] is True

    def test_serialize_combatant_with_reference_out_of_range(self):
        from src.api.constants import ITEM_USE_RANGE

        player = _combatant()
        enemy = _combatant(name="Archer", is_player=False)
        enemy.combat_proximity = ITEM_USE_RANGE + 5
        result = self.CombatantSerializer.serialize_combatant(enemy, reference=player)
        assert result["in_range"] is False

    def test_serialize_combatant_with_dict_proximity(self):
        player = _combatant()
        enemy = _combatant(name="Bandit", is_player=False)
        enemy.combat_proximity = {player: 3}
        result = self.CombatantSerializer.serialize_combatant(enemy, reference=player)
        assert result["distance"] == 3

    def test_serialize_combatant_with_dict_proximity_no_key(self):
        player = _combatant()
        enemy = _combatant(name="Bandit", is_player=False)
        other_player = MagicMock()
        enemy.combat_proximity = {other_player: 3}
        result = self.CombatantSerializer.serialize_combatant(enemy, reference=player)
        assert result["distance"] == 0

    def test_serialize_active_move_with_stage_beat(self):
        combatant = _combatant()
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
        combatant = _combatant()
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
        combatant = _combatant()
        combatant.current_move = None
        result = self.CombatantSerializer._serialize_active_move(combatant)
        assert result is None

    def test_serialize_active_move_reports_cooldown_move(self):
        combatant = _combatant(name="Goblin", is_player=False)
        cooldown_move = MagicMock()
        cooldown_move.name = "NPC_Attack"
        cooldown_move.category = "Offensive"
        cooldown_move.description = ""
        cooldown_move.current_stage = 3
        cooldown_move.beats_left = 2
        cooldown_move.stage_beat = [0, 1, 0, 4]
        combatant.current_move = None
        combatant.known_moves = [cooldown_move]

        result = self.CombatantSerializer._serialize_active_move(combatant)

        assert result["name"] == "NPC_Attack"
        assert result["current_stage"] == 3

    def test_serialize_position_with_facing(self):
        combatant = _combatant()
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
        combatant = _combatant()
        combatant.combat_position = None
        result = self.CombatantSerializer._serialize_position(combatant)
        assert result is None

    def test_serialize_position_no_attribute(self):
        combatant = MagicMock(spec=[])
        result = self.CombatantSerializer._serialize_position(combatant)
        assert result is None

    def test_serialize_combatant_list(self):
        p = _combatant()
        e = _combatant(name="Orc", is_player=False)
        result = self.CombatantSerializer.serialize_combatant_list([p, e])
        assert len(result) == 2

    @pytest.mark.parametrize(
        "current, maximum, percent, status",
        [
            (90, 100, 90.0, "healthy"),
            (76, 100, 76.0, "healthy"),   # just above the injured boundary
            (75, 100, 75.0, "injured"),   # boundary is inclusive
            (65, 100, 65.0, "injured"),
            (50, 100, 50.0, "wounded"),
            (40, 100, 40.0, "wounded"),
            (25, 100, 25.0, "critical"),
            (20, 100, 20.0, "critical"),
            (0, 0, 0, "critical"),        # zero max must not divide by zero
        ],
    )
    def test_serialize_health_bar_bucket_boundaries(
        self, current, maximum, percent, status
    ):
        """Bucket arithmetic, including every inclusive boundary.

        `spec=[...]` locks the stand-in to exactly the two attributes the
        helper reads, so nothing else can leak in.
        """
        combatant = MagicMock(spec=["health", "max_health"])
        combatant.health = current
        combatant.max_health = maximum

        result = self.CombatantSerializer.serialize_health_bar(combatant)

        assert result["percent"] == percent
        assert result["status"] == status
        assert result["current"] == current
        assert result["max"] == maximum

    def test_serialize_health_bar_reads_dead_names_on_real_combatants(self):
        """KNOWN WIRE-FIELD DEFECT — src/api/serializers/combat.py:411-412.

        `serialize_health_bar` reads `health` / `max_health`. CLAUDE.md is
        explicit that neither exists: HP is `hp` / `maxhp`. Fed a real
        full-health Player it reports 0% and "critical".

        The five tests this consolidates each built a bare `MagicMock()` and
        set `.health` on it, so they only ever proved MagicMock works.
        """
        player = _combatant()
        assert player.hp == player.maxhp == 100
        assert not hasattr(player, "health")
        assert not hasattr(player, "max_health")

        result = self.CombatantSerializer.serialize_health_bar(player)

        assert result["current"] == 0
        assert result["percent"] == 0.0
        assert result["status"] == "critical"

    def test_serialize_passives(self):
        """A real PassiveMove (`passive is True`) is reported as a passive."""
        import src.moves as moves

        combatant = _combatant()
        passive_move = _move(moves.IronFist, user=combatant)
        combatant.known_moves = [passive_move]
        result = self.CombatantSerializer._serialize_passives(combatant)
        assert len(result) == 1
        assert result[0]["name"] == passive_move.name == "Iron Fist"
        assert result[0]["type"] == "passive"
        assert result[0]["category"] == passive_move.category == "Passive"
        assert result[0]["description"] == passive_move.description

    def test_serialize_passives_skips_active_moves(self):
        """A real castable Move (`passive is False`) must not be listed."""
        import src.moves as moves

        combatant = _combatant()
        active_move = _move(moves.PowerStrike, user=combatant)
        assert active_move.passive is False
        combatant.known_moves = [active_move]
        result = self.CombatantSerializer._serialize_passives(combatant)
        assert result == []

    def test_serialize_passives_partitions_a_real_move_list(self):
        """Jean's genuine starting move list splits into passive/castable.

        Built from `Player().known_moves` rather than a hand-made list, so a
        move whose `passive` flag is dropped in the engine trips this test.
        """
        import src.moves as moves

        combatant = _combatant()
        castable = list(combatant.known_moves)
        assert castable, "Jean should start with a non-empty move list"
        assert not any(m.passive for m in castable), (
            "fixture assumption: Jean's starting moves are all castable"
        )
        combatant.known_moves = castable + [_move(moves.IronFist, user=combatant)]

        result = self.CombatantSerializer._serialize_passives(combatant)

        assert {r["name"] for r in result} == {"Iron Fist"}
        assert all(r["type"] == "passive" for r in result)

    def test_serialize_status_effects(self):
        combatant = _combatant()
        state = _state()
        combatant.states = [state]
        result = self.CombatantSerializer._serialize_status_effects(combatant)
        assert len(result) == 1
        assert result[0]["name"] == "Poisoned"

    def test_serialize_combat_equipment_with_weapon_and_armor(self):
        """Equipment is derived from `eq_weapon` + inventory `isequipped`.

        There is no `combatant.equipped` dict on any engine class (#430).
        """
        combatant = _combatant()
        combatant.eq_weapon = _weapon(name="Iron Sword", damage=12, subtype="Sword")
        body = SimpleNamespace(
            name="Leather Armor", maintype="Armor", isequipped=True, protection=8
        )
        combatant.inventory = [body]
        result = self.CombatantSerializer._serialize_combat_equipment(combatant)
        assert result["weapon"]["name"] == "Iron Sword"
        assert result["weapon"]["damage"] == 12
        assert result["weapon"]["damage_type"] == "slashing"
        assert result["armor"]["name"] == "Leather Armor"
        assert result["armor"]["protection"] == 8

    def test_serialize_combat_equipment_ignores_stale_equipped_dict(self):
        """A fabricated `equipped` dict must not be read — real combatants
        have no such attribute, so honouring it would resurrect #430."""
        combatant = _combatant(is_player=False)
        combatant.inventory = []
        combatant.equipped = {
            "weapon": SimpleNamespace(name="Phantom Blade"),
            "body": SimpleNamespace(name="Phantom Mail", defense=99),
        }
        result = self.CombatantSerializer._serialize_combat_equipment(combatant)
        assert result["weapon"] is None
        assert result["armor"] is None

    def test_serialize_combat_equipment_reads_singular_resistance(self):
        """The real attribute is `resistance`, not `resistances` (#430)."""
        combatant = _combatant(resistance={"fire": 0.5})
        combatant.inventory = []
        result = self.CombatantSerializer._serialize_combat_equipment(combatant)
        assert result["resistances"]["fire"] == 0.5

    def test_serialize_combat_equipment_ignores_plural_resistances(self):
        combatant = _combatant(is_player=False, resistance={})
        combatant.resistances = {"fire": 0.25}
        combatant.inventory = []
        result = self.CombatantSerializer._serialize_combat_equipment(combatant)
        assert result["resistances"] == {}

    def test_serialize_combat_equipment_empty(self):
        combatant = MagicMock(spec=[])
        result = self.CombatantSerializer._serialize_combat_equipment(combatant)
        assert result["weapon"] is None
        assert result["armor"] is None
        assert result["resistances"] == {}

    def test_serialize_combat_stats_derived_from_real_attributes(self):
        """`armor`/`defense`/`evasion`/`accuracy`/`attack_power` don't exist on
        any engine class; the serializer derives them (#430)."""
        combatant = _combatant(
            protection=7, finesse=20, intelligence=10, strength=12, speed=8
        )
        combatant.eq_weapon = _weapon(
            name="Steel Sword", damage=20, str_mod=0.5, fin_mod=0.25
        )
        stats = self.CombatantSerializer._serialize_combat_stats(combatant)
        assert stats["defense"] == 7  # protection, the real mitigation stat
        assert stats["evasion"] == 20  # finesse, subtracted from attacker accuracy
        # 98 + finesse*0.7 + intelligence*0.3
        assert stats["accuracy"] == 115
        assert stats["damage"] == 20  # weapon base damage
        # weapon damage + strength*str_mod + finesse*fin_mod
        assert stats["attack_power"] == 31

    def test_serialize_combat_stats_ignores_fabricated_attributes(self):
        """Hand-set `armor`/`defense`/`evasion`/`accuracy`/`attack_power` must
        be ignored — no engine class defines them, so honouring them would
        make the mock-only tests that shipped #430 pass again."""
        combatant = _combatant(protection=3, finesse=12, intelligence=8)
        combatant.armor = 99
        combatant.defense = 99
        combatant.evasion = 99
        combatant.accuracy = 42
        combatant.attack_power = 99
        stats = self.CombatantSerializer._serialize_combat_stats(combatant)
        assert stats["defense"] == 3
        assert stats["evasion"] == 12
        assert stats["accuracy"] == 108
        assert stats["attack_power"] != 99
        assert "armor" not in stats

    def test_serialize_combat_stats_npc_uses_flat_damage(self):
        """NPCs equip nothing — their flat `damage` is their attack power."""
        npc = _combatant(is_player=False, damage=26, protection=4)
        stats = self.CombatantSerializer._serialize_combat_stats(npc)
        assert stats["damage"] == 26
        assert stats["attack_power"] == 26
        assert stats["defense"] == 4


# ===========================================================================
# MoveSerializer
# ===========================================================================


# ===========================================================================
# StateEffectSerializer
# ===========================================================================


class TestStateEffectSerializer:
    """Tests for StateEffectSerializer covering uncovered branches."""

    def setup_method(self):
        from src.api.serializers.combat import StateEffectSerializer

        self.StateEffectSerializer = StateEffectSerializer

    def test_serialize_state_basic(self):
        state = _state()
        result = self.StateEffectSerializer.serialize_state(state)
        assert result["name"] == "Poisoned"
        assert result["type"] == "ailment"
        assert result["severity"] == "severe"

    def test_serialize_state_list(self):
        states = [_state("Poisoned"), _state("Burned", statustype="enflamed")]
        result = self.StateEffectSerializer.serialize_state_list(states)
        assert len(result) == 2

    def test_serialize_state_with_duration(self):
        state = _state()
        result = self.StateEffectSerializer.serialize_state_with_duration(
            state, duration_remaining=3
        )
        assert result["duration_remaining"] == 3
        assert result["active"] is True

    def test_serialize_state_with_duration_inactive(self):
        state = _state()
        result = self.StateEffectSerializer.serialize_state_with_duration(
            state, duration_remaining=0
        )
        assert result["active"] is False

    def test_get_severity_light(self):
        state = _state(statustype="revive")
        result = self.StateEffectSerializer._get_severity(state)
        assert result == "light"

    def test_get_severity_moderate(self):
        state = _state(statustype="disoriented")
        result = self.StateEffectSerializer._get_severity(state)
        assert result == "moderate"

    def test_get_severity_severe(self):
        state = _state(statustype="poison")
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

    def _make_npc(self, name="Goblin", aggro=False, friend=False):
        """Mock an engine NPC (src/npc/_base.py).

        There is no `is_hostile` attribute on the real class (#432) — the mock
        omits it so tests can't pass by fabricating it.
        """
        npc = MagicMock()
        npc.name = name
        npc.description = "A generic NPC"
        npc.level = 2
        del npc.is_hostile
        npc.aggro = aggro
        npc.friend = friend
        npc.keywords = ["talk"]
        npc.idle_message = "..."
        npc.alert_message = "!!!"
        npc.hp = 60
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

    def test_serialize_aggressive_npc_gets_attack_keyword(self):
        npc = self._make_npc(aggro=True)
        npc.keywords = []
        result = self.NPCSerializer.serialize(npc)
        assert "attack" in result["keywords"]

    def test_serialize_passive_npc_gets_no_attack_keyword(self):
        npc = self._make_npc(aggro=False)
        npc.keywords = []
        result = self.NPCSerializer.serialize(npc)
        assert "attack" not in result.get("keywords", [])

    def test_serialize_friendly_aggro_no_attack_keyword(self):
        npc = self._make_npc(aggro=True, friend=True)
        npc.keywords = []
        result = self.NPCSerializer.serialize(npc)
        assert "attack" not in result.get("keywords", [])

    def test_serialize_ignores_fabricated_is_hostile(self):
        """A hand-set `is_hostile` must not grant the attack keyword — the real
        NPC class never defines it (#432)."""
        npc = self._make_npc(aggro=False)
        npc.is_hostile = True
        npc.keywords = []
        result = self.NPCSerializer.serialize(npc)
        assert "attack" not in result.get("keywords", [])
        assert result["is_hostile"] is False

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

    def test_serialize_health_reads_hp_not_current_hp(self):
        """Real NPCs expose `hp`, never `current_hp` -- see src/npc/_base.py."""
        npc = self._make_npc()
        npc.hp = 45
        result = self.NPCSerializer.serialize(npc)
        assert result["health"] == 45

    def test_serialize_is_hostile_derived_from_aggro_and_friend(self):
        """`is_hostile` isn't a real NPC attribute; it's derived from aggro/friend."""
        npc = self._make_npc(aggro=True, friend=False)
        result = self.NPCSerializer.serialize(npc)
        assert result["is_hostile"] is True

    def test_serialize_is_hostile_false_for_friendly_aggro_npc(self):
        npc = self._make_npc(aggro=True, friend=True)
        result = self.NPCSerializer.serialize(npc)
        assert result["is_hostile"] is False


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

    def test_serialize_item_quantity_attr_is_ignored(self):
        """Real Item objects (src/items.py) always use `count`; `quantity` is
        never set on a real item, so the serializer must not read it."""
        item = self._make_item("Arrow", "Ammo")
        del item.count
        item.quantity = 20
        result = self.ItemSerializer.serialize(item)
        assert result["count"] == 1  # falls back to the default, ignoring quantity

    def test_serialize_item_with_count_attr(self):
        item = self._make_item("Arrow", "Ammo")
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
        # Real gear exposes `protection`; there is no `.armor` attribute (#411).
        assert result["protection"] == 0

    def test_equipment_slot_serializer_with_item(self):
        item = MagicMock()
        item.__class__.__name__ = "Helm"
        item.name = "Iron Helm"
        item.protection = 5.0
        item.damage = 0.0
        item.weight = 1.5
        item.value = 80
        item.resistance_bonuses = {}
        item.rarity = "common"
        result = self.EquipmentSlotSerializer.serialize("head", item)
        assert result["equipped"] is True
        assert result["item_name"] == "Iron Helm"
        assert result["protection"] == 5

    def test_equipment_serializer_derives_slots_from_inventory(self):
        """Equipment comes from inventory `isequipped` + `maintype` (#411).

        The real Player has no `equipped`/`equipment` dict and no per-slot
        attributes, and stat bonuses are scalar `add_*` fields, not a
        `stat_bonuses` mapping.
        """
        player = MagicMock()
        weapon = MagicMock()
        weapon.name = "Sword"
        weapon.__class__.__name__ = "Weapon"
        weapon.maintype = "Weapon"
        weapon.isequipped = True
        weapon.protection = 0.0
        weapon.damage = 10.0
        weapon.weight = 2.0
        weapon.value = 100
        weapon.add_str = 5
        weapon.resistance_bonuses = {}
        weapon.rarity = "uncommon"
        player.inventory_list = [weapon]
        result = self.EquipmentSerializer.serialize(player)
        assert "weapon" in result["equipped"]
        assert result["total_stat_bonuses"]["strength"] == 5

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
        # Equippability is `hasattr(item, "isequipped")` — `equip` lives on base
        # Item, so it counted potions and gold before (#411). A non-equippable
        # item alongside the real one proves the filter works.
        equippable = MagicMock(spec=["isequipped", "name", "maintype"])
        equippable.isequipped = False
        equippable.maintype = "Helm"
        potion = MagicMock(spec=["name", "use"])
        player.inventory_list = [equippable, potion]
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
        # Real Event classes don't define awaits_input unless they opt in to the
        # resolve-on-first-call structural signal; a bare MagicMock would otherwise
        # auto-vivify it to a truthy value.
        event.awaits_input = False
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
            from src.objects import Container as C
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

