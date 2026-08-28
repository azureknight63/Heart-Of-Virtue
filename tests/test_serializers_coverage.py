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

    def test_serialize_active_move_uses_the_real_moves_stage_beat(self):
        """A real `Move` carries its own `stage_beat` table, so `total_beats`
        must index it — the old mock supplied a hand-written list, which meant
        an off-by-one index would still have matched."""
        import src.moves as moves

        combatant = _combatant()
        move = moves.PowerStrike(combatant)
        assert move.stage_beat == [5, 4, 8, 9]
        move.current_stage = 1
        move.beats_left = 2
        combatant.current_move = move

        result = self.CombatantSerializer._serialize_active_move(combatant)

        assert result["name"] == "Power Strike"
        assert result["display_name"] == "Power Strike"
        assert result["category"] == move.category == "Offensive"
        assert result["current_stage"] == 1
        assert result["beats_left"] == 2
        assert result["total_beats"] == move.stage_beat[1] == 4

    def test_serialize_active_move_without_stage_beat(self):
        """Every engine Move defines `stage_beat`; the 0 fallback exists for
        degraded/legacy move objects, so it is proven with a namespace rather
        than a mock that would auto-vivify the attribute."""
        from types import SimpleNamespace

        combatant = _combatant()
        # A namespace, not a MagicMock: a mock auto-vivifies `stage_beat`, so
        # the fallback under test would never be reached. The range/falloff/
        # resolve callables are the rest of the Move API the serializer now
        # invokes unguarded — supplied explicitly so this stays a test about the
        # missing `stage_beat`, and so a *new* unguarded call shows up here as a
        # clear AttributeError rather than being silently absorbed.
        combatant.current_move = SimpleNamespace(
            name="Slash",
            category="Attack",
            description="Slash",
            current_stage=0,
            beats_left=1,
            # Signatures mirror the real Move API: both range helpers take the
            # acting user, beats_until_resolve takes none.
            get_effective_range_max=lambda user: None,
            get_accuracy_falloff=lambda user: None,
            beats_until_resolve=lambda: None,
        )
        result = self.CombatantSerializer._serialize_active_move(combatant)
        assert result["total_beats"] == 0
        assert result["beats_left"] == 1

    def test_serialize_active_move_none(self):
        combatant = _combatant()
        combatant.current_move = None
        combatant.known_moves = []
        result = self.CombatantSerializer._serialize_active_move(combatant)
        assert result is None

    @pytest.mark.parametrize("stage", [2, 3])  # RECOIL, COOLDOWN
    def test_serialize_active_move_reports_a_detached_cooldown_move(self, stage):
        """`move_in_progress` also surfaces a move that has been detached from
        `current_move` while it recoils or cools down."""
        import src.moves as moves

        combatant = _combatant(name="Goblin", is_player=False)
        move = moves.NpcAttack(combatant)
        move.current_stage = stage
        move.beats_left = 2
        combatant.current_move = None
        combatant.known_moves = [move]

        result = self.CombatantSerializer._serialize_active_move(combatant)

        assert result["name"] == move.name
        assert result["current_stage"] == stage
        assert result["total_beats"] == move.stage_beat[stage]

    def test_an_idle_known_move_is_not_reported_as_active(self):
        import src.moves as moves

        combatant = _combatant(name="Goblin", is_player=False)
        move = moves.NpcAttack(combatant)
        move.current_stage = 0
        combatant.current_move = None
        combatant.known_moves = [move]

        assert self.CombatantSerializer._serialize_active_move(combatant) is None

    def test_serialize_position_from_a_real_combat_position(self):
        from src.positions import CombatPosition, Direction

        combatant = _combatant()
        combatant.combat_position = CombatPosition(3, 5, Direction.S)

        result = self.CombatantSerializer._serialize_position(combatant)
        assert result == {"x": 3, "y": 5, "facing": "S"}

    def test_serialize_position_defaults_facing_when_absent(self):
        from types import SimpleNamespace

        combatant = _combatant()
        combatant.combat_position = SimpleNamespace(x=1, y=2)

        result = self.CombatantSerializer._serialize_position(combatant)
        assert result == {"x": 1, "y": 2, "facing": "N"}

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
        # HIT_CHANCE_BASE (85) + finesse*0.7 + intelligence*0.3
        assert stats["accuracy"] == 102
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
        assert stats["accuracy"] == 95
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
    """`NPCSerializer` against **real** `src.npc` classes.

    Issue #432: the serializer used to read a nonexistent `is_hostile` flag.
    Every test here therefore builds a genuine NPC, so `level`, `max_hp`,
    `loquacity_*` and `is_hostile` are absent exactly as they are in play and
    the `getattr(..., default)` fallbacks are the branches under test.
    """

    def setup_method(self):
        from src.api.serializers.npc_serializer import NPCSerializer

        self.NPCSerializer = NPCSerializer

    @staticmethod
    def _slime():
        from src.npc._enemies import Slime

        return Slime()

    @staticmethod
    def _mara():
        from src.npc._friends import Mara

        return Mara()

    def test_serialize_none_npc(self):
        assert self.NPCSerializer.serialize(None) == {}

    def test_serialize_real_enemy(self):
        slime = self._slime()
        result = self.NPCSerializer.serialize(slime)

        assert result["id"] == str(id(slime))
        assert result["name"] == slime.name
        assert result["type"] == "Slime"
        assert result["description"] == slime.description
        # Real NPCs expose `hp`/`maxhp` — never `current_hp`/`max_hp`.
        assert not hasattr(slime, "current_hp")
        assert result["health"] == slime.hp
        assert result["max_health"] == slime.maxhp
        assert result["idle_message"] == slime.idle_message
        assert result["alert_message"] == slime.alert_message

    def test_enemies_have_no_level_so_the_default_is_what_ships(self):
        slime = self._slime()
        assert not hasattr(slime, "level")

        assert self.NPCSerializer.serialize(slime)["level"] == 1

    def test_hostile_enemy_gains_the_attack_keyword(self):
        slime = self._slime()
        assert slime.aggro is True and slime.friend is False
        assert slime.keywords == []

        result = self.NPCSerializer.serialize(slime)
        assert result["is_hostile"] is True
        assert result["keywords"] == ["attack"]

    def test_friendly_npc_keeps_its_own_keywords_and_is_not_attackable(self):
        mara = self._mara()
        assert mara.friend is True and mara.aggro is False

        result = self.NPCSerializer.serialize(mara)
        assert result["is_hostile"] is False
        assert result["keywords"] == mara.keywords
        assert "attack" not in result["keywords"]

    def test_an_aggro_ally_is_still_not_hostile_to_jean(self):
        """`friend` overrides `aggro`: an ally that attacks on sight attacks
        Jean's enemies, not Jean."""
        slime = self._slime()
        slime.friend = True

        result = self.NPCSerializer.serialize(slime)
        assert result["is_hostile"] is False
        assert "keywords" not in result

    def test_passive_enemy_is_not_hostile(self):
        slime = self._slime()
        slime.aggro = False

        result = self.NPCSerializer.serialize(slime)
        assert result["is_hostile"] is False
        assert "keywords" not in result

    def test_fabricated_is_hostile_is_ignored(self):
        """#432: a hand-set `is_hostile` must not grant the attack keyword."""
        slime = self._slime()
        slime.aggro = False
        slime.is_hostile = True

        result = self.NPCSerializer.serialize(slime)
        assert result["is_hostile"] is False
        assert "keywords" not in result

    def test_max_hp_fallback_for_an_object_without_maxhp(self):
        """No real NPC lacks `maxhp`; the `max_hp` branch exists for degraded
        or legacy-unpickled objects, so it is exercised with a plain namespace
        rather than a mock that would satisfy both branches at once."""
        from types import SimpleNamespace

        stand_in = SimpleNamespace(
            name="Echo", description="A memory", hp=30, max_hp=90
        )
        result = self.NPCSerializer.serialize(stand_in)

        assert result["health"] == 30
        assert result["max_health"] == 90

    def test_object_with_no_hp_attributes_omits_the_health_block(self):
        from types import SimpleNamespace

        result = self.NPCSerializer.serialize(
            SimpleNamespace(name="Ghost", description="Spooky")
        )

        assert result["name"] == "Ghost"
        assert "health" not in result
        assert "max_health" not in result
        assert "is_hostile" not in result

    def test_enemies_have_no_chat_mixin_so_loquacity_is_unavailable(self):
        slime = self._slime()
        assert not hasattr(slime, "_init_chat_attrs")

        result = self.NPCSerializer.serialize(slime)
        assert result["llm_chat_enabled"] is False
        assert result["loquacity_available"] is False

    @pytest.mark.parametrize(
        "current,threshold,maximum,expected",
        [
            (3, 2, 3, True),    # rested enough to talk
            (0, 2, 3, False),   # talked out, below the threshold
            (2, 2, 3, True),    # exactly at the threshold
            (0, 5, 0, True),    # loquacity_max 0 -> the cap doesn't apply
        ],
    )
    def test_loquacity_availability_on_a_real_conversational_npc(
        self, current, threshold, maximum, expected
    ):
        mara = self._mara()
        mara.loquacity_current = current
        mara.loquacity_threshold = threshold
        mara.loquacity_max = maximum

        result = self.NPCSerializer.serialize(mara)
        assert result["loquacity_available"] is expected

    @pytest.mark.parametrize(
        "env_value,expected", [("1", True), ("true", True), ("0", False),
                               ("no", False)]
    )
    def test_llm_chat_flag_follows_the_environment(
        self, monkeypatch, env_value, expected
    ):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", env_value)
        result = self.NPCSerializer.serialize(self._mara())
        assert result["llm_chat_enabled"] is expected

    def test_llm_chat_stays_off_for_an_npc_without_the_mixin(self, monkeypatch):
        monkeypatch.setenv("NPC_CHAT_LLM_ENABLED", "1")
        assert self.NPCSerializer.serialize(self._slime())["llm_chat_enabled"] is False

    def test_serialize_list(self):
        slime, mara = self._slime(), self._mara()
        result = self.NPCSerializer.serialize_list([slime, mara])

        assert [r["name"] for r in result] == [slime.name, mara.name]
        assert [r["is_hostile"] for r in result] == [True, False]
        assert self.NPCSerializer.serialize_list([]) == []
        assert self.NPCSerializer.serialize_list(None) == []


# ===========================================================================
# ItemSerializer
# ===========================================================================


class TestItemSerializer:
    """`ItemSerializer`, exercised against **real** `src.items` objects.

    The previous version built a bare `MagicMock()` and hand-set `keywords`,
    `equip_states`, `count`, `power` and `hide_factor` on it. Every one of the
    serializer's `hasattr(item, ...)` guards therefore reported True, so the
    tests could not distinguish a live branch from a dead one — and three of
    them are dead on real items (no engine item defines `keywords`, and real
    gear ships with an empty `equip_states`).
    """

    def setup_method(self):
        from src.api.serializers.item_serializer import ItemSerializer

        self.ItemSerializer = ItemSerializer

    def test_serialize_none_item(self):
        result = self.ItemSerializer.serialize(None)
        assert result == {}

    def test_serialize_real_weapon(self):
        from src.items import Longsword

        sword = Longsword()
        result = self.ItemSerializer.serialize(sword)

        assert result["name"] == "Longsword"
        assert result["type"] == "Longsword"
        assert result["description"] == sword.description
        assert result["value"] == sword.value
        assert result["weight"] == sword.weight
        assert result["subtype"] == "Sword"
        assert result["aliases"] == []
        assert result["action_aliases"] == []
        assert result["announce"] == sword.announce
        assert result["merchandise"] is False
        assert result["hidden"] is False

    def test_real_items_have_no_keywords_so_interactions_is_the_live_path(self):
        """`keywords` is checked first but no engine item defines it, so the
        `interactions` fallback is the only branch real play ever takes."""
        from src.items import Longsword

        sword = Longsword()
        assert not hasattr(sword, "keywords")
        assert sword.interactions == ["drop", "equip"]

        result = self.ItemSerializer.serialize(sword)
        # "drop" is inventory-only and filtered; "take" is always appended.
        assert result["keywords"] == ["equip", "take"]

    def test_keywords_attribute_wins_when_something_does_define_it(self):
        from src.items import Longsword

        sword = Longsword()
        sword.keywords = ["take", "drop", "unequip", "inspect"]

        result = self.ItemSerializer.serialize(sword)
        assert result["keywords"] == ["take", "inspect"]

    def test_take_is_added_to_an_item_with_no_interactions(self):
        from src.items import Gold

        coins = Gold(75)
        assert coins.interactions == []

        result = self.ItemSerializer.serialize(coins)
        assert result["keywords"] == ["take"]
        assert result["count"] == 75  # Gold's count is the coin amount

    def test_count_defaults_to_one_for_unstackable_gear(self):
        """No weapon or armour defines `count`; `quantity` is never read."""
        from src.items import Longsword

        sword = Longsword()
        assert not hasattr(sword, "count")
        sword.quantity = 20  # the fabricated name from issue #412

        result = self.ItemSerializer.serialize(sword)
        assert result["count"] == 1

    def test_count_reflects_a_real_stack(self):
        from src.items import WoodenArrow

        arrows = WoodenArrow()
        arrows.count = 15

        result = self.ItemSerializer.serialize(arrows)
        assert result["count"] == 15

    def test_empty_equip_states_are_omitted_for_plain_gear(self):
        from src.items import IronCuirass

        armor = IronCuirass()
        assert armor.equip_states == []

        result = self.ItemSerializer.serialize(armor)
        assert "equip_states" not in result

    def test_populated_equip_states_survive_the_json_safe_boundary(self):
        """Enchantments merge `State` objects into `item.equip_states`
        (functions.enchant_item). States are not JSON-primitives, so the
        `_safe.json_safe` boundary must stringify them rather than let
        `jsonify` choke on the room payload."""
        import json
        from src.items import IronCuirass
        from src.states import Poisoned

        armor = IronCuirass()
        armor.equip_states.append(Poisoned(None))

        result = self.ItemSerializer.serialize(armor)
        assert len(result["equip_states"]) == 1
        assert all(isinstance(s, str) for s in result["equip_states"])
        json.dumps(result)  # would raise if a State leaked through

    def test_real_status_resistance_item(self):
        from src.items import HardenedEarPlug

        plug = HardenedEarPlug()
        result = self.ItemSerializer.serialize(plug)

        assert result["status_resistances"] == {"stun": 0.5}
        # add_resistance exists but is empty, so the key is omitted.
        assert plug.add_resistance == {}
        assert "resistances" not in result

    def test_real_damage_resistance_from_an_enchantment(self):
        from src.items import IronCuirass
        from src.enchant_tables import Dousing

        armor = IronCuirass()
        Dousing(armor).modify()

        result = self.ItemSerializer.serialize(armor)
        assert result["resistances"] == armor.add_resistance
        assert result["resistances"]["fire"] > 0

    def test_power_is_reported_for_a_real_consumable(self):
        from src.items import Restorative

        potion = Restorative()
        result = self.ItemSerializer.serialize(potion)

        assert result["power"] == potion.power == 60
        assert result["aliases"] == potion.aliases
        assert "vial" in result["aliases"]

    def test_power_is_absent_for_gear_that_has_none(self):
        from src.items import Longsword

        sword = Longsword()
        assert not hasattr(sword, "power")
        assert "power" not in self.ItemSerializer.serialize(sword)

    def test_hidden_item_reports_its_hide_factor(self):
        from src.items import Longsword

        sword = Longsword()
        sword.hidden = True
        sword.hide_factor = 3

        result = self.ItemSerializer.serialize(sword)
        assert result["hidden"] is True
        assert result["hide_factor"] == 3

    def test_merchandise_flag_round_trips(self):
        from src.items import Restorative

        stock = Restorative(merchandise=True)
        assert stock.merchandise is True
        assert self.ItemSerializer.serialize(stock)["merchandise"] is True

    def test_serialize_list_empty(self):
        assert self.ItemSerializer.serialize_list([]) == []
        assert self.ItemSerializer.serialize_list(None) == []

    def test_serialize_list_preserves_order_and_identity(self):
        from src.items import Longsword, IronCuirass

        sword, armor = Longsword(), IronCuirass()
        result = self.ItemSerializer.serialize_list([sword, armor])

        assert [r["name"] for r in result] == ["Longsword", "Iron Cuirass"]
        assert result[0]["id"] == str(id(sword))
        assert result[1]["id"] == str(id(armor))


# ===========================================================================
# InventorySerializer
# ===========================================================================


class TestInventorySerializer:
    """`inventory.py` serializers, exercised against **real** engine objects.

    Everything here used to run on bare `MagicMock()` items and players. That
    hid two whole families of bug:

    * A mock materialises `count`, `rarity`, `add_str`, `carrying_capacity`,
      `inventory_list` on demand, so every `getattr(obj, name, default)`
      fallback in the serializer looked like it was reading a real attribute.
      No real `Weapon` has `count`/`rarity`/`add_str`; no real `Player` has
      `inventory_list` or `carrying_capacity`.
    * `InventorySerializer` reads `weight_tolerance` first and only then
      `carrying_capacity`. On a `MagicMock` player *both* resolve, so the
      test could not tell which one the code actually used — which is exactly
      how `weight_limit` shipped at 5x the real cap (#411).
    """

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

    @staticmethod
    def _player_carrying(*inventory):
        """A real `Player` whose inventory is exactly `inventory`."""
        from src.player import Player

        player = Player()
        player.inventory = list(inventory)
        return player

    # -- InventoryItemSerializer -------------------------------------------

    def test_serialize_real_weapon_reports_engine_values_not_defaults(self):
        from src.items import Longsword

        sword = Longsword()
        result = self.InventoryItemSerializer.serialize(sword, 0)

        assert result["type"] == "Longsword"
        assert result["maintype"] == "Weapon"
        assert result["subtype"] == sword.subtype == "Sword"
        assert result["damage"] == round(sword.damage) == 30
        assert result["str_mod"] == sword.str_mod
        assert result["fin_mod"] == sword.fin_mod
        assert result["damage_type"] == "slashing"
        assert result["weight"] == sword.weight
        assert result["value"] == sword.value
        assert result["can_equip"] is True
        assert result["can_use"] is False
        assert result["can_drop"] is True
        assert result["is_equipped"] is False
        assert result["index"] == 0

    def test_weapon_quantity_and_rarity_come_from_absent_attribute_defaults(self):
        """No engine weapon defines `count` or `rarity` — pin the fallbacks.

        The old mock set both by hand, so a serializer typo (`counts`,
        `rarity_tier`) would still have produced 1/"uncommon" and passed.
        """
        from src.items import Longsword

        sword = Longsword()
        assert not hasattr(sword, "count")
        assert not hasattr(sword, "rarity")

        result = self.InventoryItemSerializer.serialize(sword, 0)
        assert result["quantity"] == 1
        assert result["rarity"] == "common"

    def test_stackable_consumable_reports_its_real_count(self):
        from src.items import Restorative

        potion = Restorative()
        potion.count = 4
        result = self.InventoryItemSerializer.serialize(potion, 0)

        assert result["quantity"] == 4

    @pytest.mark.parametrize(
        "cls_name,expected_slot_type",
        [
            ("IronCuirass", "Armor"),
            ("IronGreaves", "Boots"),
            ("IronHelm", "Helm"),
            ("IronGauntlets", "Gloves"),
            ("DullMedallion", "Accessory"),
        ],
    )
    def test_real_protective_gear_reports_engine_protection(
        self, cls_name, expected_slot_type
    ):
        from src import items

        gear = getattr(items, cls_name)()
        result = self.InventoryItemSerializer.serialize(gear, 1)

        assert result["maintype"] == expected_slot_type
        assert result["protection"] == round(gear.protection)
        assert result["str_mod"] == gear.str_mod
        assert result["can_equip"] is True
        # Protection is not a weapon stat, so no damage block is emitted.
        assert "damage" not in result

    def test_real_consumable_effects_block_is_populated(self):
        from src.items import Restorative

        result = self.InventoryItemSerializer.serialize(Restorative(), 0)

        assert result["can_use"] is True
        assert result["effects"] == [
            {"type": "heal", "stat": "hp", "power": 60, "range": [48, 72]}
        ]

    @pytest.mark.parametrize(
        "cls_name",
        ["Restorative", "Draught", "Antidote", "IronRation", "Bitterroot",
         "DriedCrystalSap"],
    )
    def test_declared_consumable_power_matches_the_real_item(self, cls_name):
        """`_CONSUMABLE_EFFECTS` is hand-maintained; its own docstring calls it
        a SYNC RISK. Nothing checked it until now, and `DriedCrystalSap`
        had drifted (declared 20, the item heals 25).

        The declared `power` is what the frontend chip renders, so a mismatch
        lies to the player about how much an item heals.
        """
        from src import items
        from src.api.serializers.inventory import _CONSUMABLE_EFFECTS

        item = getattr(items, cls_name)()
        declared = _CONSUMABLE_EFFECTS[cls_name]
        heal = next(e for e in declared if e["type"] == "heal")

        assert heal["power"] == item.power, (
            f"{cls_name}: serializer declares power={heal['power']} but the "
            f"engine item heals for {item.power}"
        )
        low, high = heal["range"]
        assert low <= item.power <= high

    def test_consumable_without_an_effects_entry_reports_no_effects(self):
        """`Respite` is usable but is not in `_CONSUMABLE_EFFECTS`."""
        from src.items import Respite
        from src.api.serializers.inventory import _CONSUMABLE_EFFECTS

        assert "Respite" not in _CONSUMABLE_EFFECTS
        result = self.InventoryItemSerializer.serialize(Respite(), 0)

        assert result["can_use"] is True
        assert result["effects"] == []

    def test_enchantment_overrides_the_subtype_damage_type(self):
        """`Flaming` is a real enchantment that writes `base_damage_type`."""
        from src.items import Longsword
        from src.enchant_tables import Flaming

        sword = Longsword()
        assert not hasattr(sword, "base_damage_type")
        Flaming(sword).modify()

        result = self.InventoryItemSerializer.serialize(sword, 0)
        assert result["damage_type"] == "fire"

    def test_real_enchantment_bonuses_reach_the_payload(self):
        """`OfVigor` creates the `add_str` attribute the serializer reads."""
        from src.items import Longsword
        from src.enchant_tables import OfVigor

        sword = Longsword()
        assert not hasattr(sword, "add_str")
        OfVigor(sword).modify()

        result = self.InventoryItemSerializer.serialize(sword, 0)
        assert sword.add_str >= 1
        assert result["bonuses"] == {"strength": sword.add_str}

    def test_unenchanted_item_omits_the_bonuses_key(self):
        from src.items import Longsword

        result = self.InventoryItemSerializer.serialize(Longsword(), 0)
        assert "bonuses" not in result

    def test_real_resistance_enchantment_reaches_the_payload(self):
        """`Dousing` is a real enchantment that fills `add_resistance`."""
        from src.items import IronCuirass
        from src.enchant_tables import Dousing

        armor = IronCuirass()
        Dousing(armor).modify()

        result = self.InventoryItemSerializer.serialize(armor, 0)
        assert result["resistances"] == armor.add_resistance
        assert result["resistances"]["fire"] > 0
        # Nothing set a status resistance, so that key stays absent.
        assert "status_resistances" not in result

    def test_real_status_resistance_gear_reaches_the_payload(self):
        """`HardenedEarPlug` ships with `add_status_resistance={"stun": 0.5}`."""
        from src.items import HardenedEarPlug

        plug = HardenedEarPlug()
        result = self.InventoryItemSerializer.serialize(plug, 0)

        assert result["status_resistances"] == {"stun": 0.5}
        assert result["status_resistances"] == plug.add_status_resistance
        assert "resistances" not in result

    def test_plain_gear_omits_the_resistance_keys(self):
        from src.items import IronCuirass

        armor = IronCuirass()
        assert armor.add_resistance == {} and armor.add_status_resistance == {}

        result = self.InventoryItemSerializer.serialize(armor, 0)
        assert "resistances" not in result
        assert "status_resistances" not in result

    # -- comparison block ---------------------------------------------------

    def test_comparison_against_the_really_equipped_counterpart(self):
        from src.items import Shortsword, Longsword
        from src.enchant_tables import OfVigor

        equipped = Shortsword()
        equipped.isequipped = True
        candidate = Longsword()
        OfVigor(candidate).modify()
        player = self._player_carrying(equipped, candidate)

        result = self.InventoryItemSerializer.serialize(candidate, 1, player)
        comparison = result["comparison"]

        assert comparison["comparison_type"] == "item_to_item"
        assert comparison["current"]["name"] == equipped.name
        assert comparison["differences"]["damage_diff"] == (
            candidate.damage - equipped.damage
        )
        assert comparison["differences"]["damage_diff"] > 0
        assert comparison["differences"]["bonus_diffs"] == {
            "strength": candidate.add_str
        }
        assert comparison["recommendation"] == "upgrade"

    def test_comparison_is_empty_to_item_when_the_slot_is_free(self):
        from src.items import Longsword

        candidate = Longsword()
        # Jean's starting kit equips body/head/accessory but never a weapon
        # from the inventory (`Fists` live on `player.eq_weapon`).
        player = self._player_carrying(candidate)

        result = self.InventoryItemSerializer.serialize(candidate, 0, player)
        assert result["comparison"]["comparison_type"] == "empty_to_item"
        assert result["comparison"]["current"] is None

    def test_item_without_a_maintype_skips_comparison(self):
        from src.items import Longsword

        candidate = Longsword()
        candidate.maintype = None
        player = self._player_carrying(candidate)

        result = self.InventoryItemSerializer.serialize(candidate, 0, player)
        assert "comparison" not in result

    @pytest.mark.parametrize("cls_name", ["GoldRing", "GoldBracelet"])
    def test_multi_equip_accessories_skip_comparison(self, cls_name):
        from src import items
        from src.api.serializers.inventory import (
            _MULTI_EQUIP_ACCESSORY_SUBTYPES,
        )

        candidate = getattr(items, cls_name)()
        assert candidate.subtype in _MULTI_EQUIP_ACCESSORY_SUBTYPES
        player = self._player_carrying(candidate)

        result = self.InventoryItemSerializer.serialize(candidate, 0, player)
        assert "comparison" not in result

    def test_already_equipped_item_skips_comparison(self):
        from src.items import Longsword

        sword = Longsword()
        sword.isequipped = True
        player = self._player_carrying(sword)

        result = self.InventoryItemSerializer.serialize(sword, 0, player)
        assert result["is_equipped"] is True
        assert "comparison" not in result

    def test_equip_slot_status_ignores_a_different_maintype(self):
        from src.api.serializers.inventory import _get_equip_slot_status
        from src.items import IronHelm, Longsword

        helm = IronHelm()
        helm.isequipped = True
        candidate = Longsword()
        player = self._player_carrying(helm, candidate)

        comparable, counterpart = _get_equip_slot_status(player, candidate)
        assert comparable is True
        assert counterpart is None

    def test_equip_slot_status_ignores_a_different_accessory_subtype(self):
        from src.api.serializers.inventory import _get_equip_slot_status
        from src.items import DullMedallion, HardenedEarPlug

        necklace = DullMedallion()
        necklace.isequipped = True
        candidate = HardenedEarPlug()
        assert necklace.subtype != candidate.subtype
        player = self._player_carrying(necklace, candidate)

        comparable, counterpart = _get_equip_slot_status(player, candidate)
        assert comparable is True
        assert counterpart is None

    def test_equip_slot_status_matches_the_same_accessory_subtype(self):
        from src.api.serializers.inventory import _get_equip_slot_status
        from src.items import DullMedallion, GoldChain

        worn = DullMedallion()
        worn.isequipped = True
        candidate = GoldChain()
        assert worn.subtype == candidate.subtype == "Necklace"
        player = self._player_carrying(worn, candidate)

        comparable, counterpart = _get_equip_slot_status(player, candidate)
        assert comparable is True
        assert counterpart is worn

    def test_diff_resistance_dicts_with_real_enchantment_deltas(self):
        from src.api.serializers.inventory import _diff_resistance_dicts
        from src.items import IronCuirass
        from src.enchant_tables import Dousing, Bulwark

        current = IronCuirass()
        Dousing(current).modify()
        candidate = IronCuirass()
        Bulwark(candidate).modify()

        diffs = _diff_resistance_dicts(current, candidate, "add_resistance")
        assert set(diffs) == {"fire", "crushing"}
        assert diffs["fire"] == pytest.approx(-current.add_resistance["fire"])
        assert diffs["crushing"] == pytest.approx(
            candidate.add_resistance["crushing"]
        )

    # -- InventorySerializer -----------------------------------------------

    def test_inventory_weight_limit_is_the_real_weight_tolerance(self):
        """#411: `carrying_capacity` does not exist, so `weight_limit` was
        always the 100.0 default — five times Jean's real 20-30 lb cap."""
        from src.items import Longsword

        player = self._player_carrying(Longsword())
        assert not hasattr(player, "carrying_capacity")
        assert not hasattr(player, "inventory_slots")

        result = self.InventorySerializer.serialize(player)

        assert result["weight_limit"] == player.weight_tolerance
        assert result["weight_limit"] != 100.0
        assert result["item_count"] == 1
        assert result["total_weight"] == pytest.approx(3.0)
        assert result["weight_percentage"] == pytest.approx(
            round(3.0 / player.weight_tolerance * 100, 1)
        )
        assert result["slots_total"] == 20
        assert result["items"][0]["name"] == "Longsword"

    def test_inventory_totals_sum_every_real_item_weight(self):
        from src.items import Longsword, IronCuirass, Restorative

        carried = [Longsword(), IronCuirass(), Restorative()]
        player = self._player_carrying(*carried)

        result = self.InventorySerializer.serialize(player)

        assert result["item_count"] == 3
        assert result["slots_used"] == 3
        assert result["total_weight"] == pytest.approx(
            round(sum(i.weight for i in carried), 2)
        )

    def test_inventory_serializer_falls_back_to_inventory_for_minimal_player(self):
        """`MinimalPlayer` has `inventory` but no `inventory_list`, and no
        `weight_tolerance` — so it is the one object that legitimately takes
        the 100.0 capacity default."""
        from src.api.services.session_manager import MinimalPlayer

        player = MinimalPlayer("tester")
        assert not hasattr(player, "inventory_list")
        assert not hasattr(player, "weight_tolerance")

        result = self.InventorySerializer.serialize(player)

        assert result["item_count"] == len(player.inventory)
        assert result["item_count"] > 0
        assert result["weight_limit"] == 100.0

    def test_inventory_serializer_empty(self):
        player = self._player_carrying()
        result = self.InventorySerializer.serialize(player)

        assert result["item_count"] == 0
        assert result["items"] == []
        assert result["total_weight"] == 0.0
        assert result["weight_percentage"] == 0.0

    def test_zero_capacity_does_not_divide_by_zero(self):
        player = self._player_carrying()
        player.weight_tolerance = 0

        result = self.InventorySerializer.serialize(player)
        assert result["weight_percentage"] == 0.0

    # -- EquipmentSlotSerializer / EquipmentSerializer -----------------------

    def test_equipment_slot_serializer_empty_slot(self):
        result = self.EquipmentSlotSerializer.serialize("head", None)
        assert result["equipped"] is False
        assert result["slot"] == "head"
        # Real gear exposes `protection`; there is no `.armor` attribute (#411).
        assert result["protection"] == 0
        assert result["item_name"] is None
        assert result["stat_bonuses"] == {}

    def test_equipment_slot_serializer_with_a_real_helm(self):
        from src.items import IronHelm

        helm = IronHelm()
        result = self.EquipmentSlotSerializer.serialize("head", helm)

        assert result["equipped"] is True
        assert result["item_name"] == "Iron Helm"
        assert result["item_type"] == "IronHelm"
        assert result["protection"] == round(helm.protection) == 7
        assert result["damage"] == 0  # helms have no `damage` attribute
        assert result["weight"] == helm.weight
        assert result["value"] == helm.value
        assert result["rarity"] == "common"  # no engine item defines `rarity`
        assert result["stat_bonuses"] == {}
        assert result["resistance_bonuses"] == {}

    def test_equipment_slot_serializer_reports_enchantment_bonuses(self):
        from src.items import IronHelm
        from src.enchant_tables import OfHealth, Dousing

        helm = IronHelm()
        OfHealth(helm).modify()
        Dousing(helm).modify()

        result = self.EquipmentSlotSerializer.serialize("head", helm)
        assert result["stat_bonuses"] == {"maxhp": helm.add_maxhp}
        assert result["resistance_bonuses"] == helm.add_resistance

    def test_equipment_serializer_derives_slots_from_the_real_inventory(self):
        """#411: the real Player has no `equipped`/`equipment` dict and no
        per-slot attributes — slots are derived from inventory `isequipped`
        plus `maintype`, with `eq_weapon` filling the weapon slot."""
        from src.player import Player

        player = Player()  # Jean's starting kit: cloth, hood, wedding band
        assert not hasattr(player, "equipped")

        result = self.EquipmentSerializer.serialize(player)
        equipped = result["equipped"]

        assert equipped["body"]["item_name"] == "Tattered Cloth"
        assert equipped["head"]["item_name"] == "Cloth Hood"
        assert equipped["accessory_1"]["item_name"] == "Wedding Band"
        # Fists are held on the player, not in the inventory.
        assert equipped["weapon"]["item_name"] == player.eq_weapon.name
        assert result["equipment_value"] == sum(
            getattr(i, "value", 0)
            for i in (
                player.eq_weapon,
                *[i for i in player.inventory if getattr(i, "isequipped", False)],
            )
        )

    def test_equipment_serializer_sums_enchantment_bonuses_across_slots(self):
        from src.items import IronHelm, IronCuirass
        from src.enchant_tables import OfVigor

        helm, cuirass = IronHelm(), IronCuirass()
        for gear in (helm, cuirass):
            OfVigor(gear).modify()
            gear.isequipped = True
        player = self._player_carrying(helm, cuirass)

        result = self.EquipmentSerializer.serialize(player)

        assert result["total_stat_bonuses"]["strength"] == (
            helm.add_str + cuirass.add_str
        )
        assert set(result["equipped"]) == {"head", "body", "weapon"}

    def test_equipment_serializer_counts_only_unequipped_equippables(self):
        """`hasattr(item, "equip")` is True for every item (it lives on the
        base `Item`), so the old check counted potions and gold (#411).
        `is_equippable` keys off `isequipped` instead."""
        from src.items import Longsword, IronHelm, Restorative, Gold

        worn = IronHelm()
        worn.isequipped = True
        potion, coins = Restorative(), Gold(25)
        assert not hasattr(potion, "isequipped")
        assert not hasattr(coins, "isequipped")
        player = self._player_carrying(Longsword(), worn, potion, coins)

        result = self.EquipmentSerializer.serialize(player)
        assert result["unequipped_equippable_count"] == 1

    def test_equipment_serializer_with_no_weapon_at_all(self):
        player = self._player_carrying()
        player.eq_weapon = None

        result = self.EquipmentSerializer.serialize(player)
        assert result["equipped"] == {}
        assert result["total_stat_bonuses"] == {}
        assert result["equipment_value"] == 0

    # -- ItemDetailSerializer ----------------------------------------------

    def test_item_detail_serializer_on_a_real_weapon(self):
        from src.items import Longsword

        sword = Longsword()
        result = self.ItemDetailSerializer.serialize(
            sword, equipped=True, inventory_index=2
        )

        assert result["name"] == "Longsword"
        assert result["type"] == "Longsword"
        assert result["equipped"] is True
        assert result["inventory_index"] == 2
        assert result["quantity"] == 1
        assert result["rarity"] == "common"
        assert result["weight"] == sword.weight
        assert result["value"] == sword.value
        assert result["can_equip"] is True
        assert result["stats"]["damage"] == round(sword.damage)
        assert result["stats"]["protection"] == 0
        assert result["bonuses"] == {"stat_bonuses": {}, "resistance_bonuses": {}}
        assert result["flags"] == {
            "merchandise": False,
            "hidden": False,
            "special": False,
        }

    def test_item_detail_serializer_marks_special_items(self):
        from src.items import AncientRelic, Special

        relic = AncientRelic()
        assert isinstance(relic, Special)

        result = self.ItemDetailSerializer.serialize(relic)
        assert result["flags"]["special"] is True
        assert result["can_equip"] is False
        assert result["inventory_index"] is None

    def test_item_detail_serializer_does_not_offer_equip_on_a_potion(self):
        """Every `Item` has an `equip` method, so the old `hasattr` check
        offered an Equip button on consumables (#411)."""
        from src.items import Restorative

        potion = Restorative()
        assert hasattr(potion, "equip")

        result = self.ItemDetailSerializer.serialize(potion)
        assert result["can_equip"] is False
        assert result["can_use"] is True
        assert result["quantity"] == potion.count

    # -- ItemComparisonSerializer ------------------------------------------

    def test_item_comparison_empty_to_item(self):
        from src.items import Longsword

        candidate = Longsword()
        result = self.ItemComparisonSerializer.serialize(None, candidate)

        assert result["comparison_type"] == "empty_to_item"
        assert result["current"] is None
        assert result["candidate"]["name"] == "Longsword"
        assert result["recommendation"] == "upgrade"
        assert result["reason"] == "No item currently equipped"

    def test_item_comparison_upgrade_between_real_weapons(self):
        from src.items import Shortsword, Longsword

        current, candidate = Shortsword(), Longsword()
        result = self.ItemComparisonSerializer.serialize(current, candidate)
        diffs = result["differences"]

        assert result["comparison_type"] == "item_to_item"
        assert result["recommendation"] == "upgrade"
        assert diffs["damage_diff"] == candidate.damage - current.damage == 5
        assert diffs["protection_diff"] == 0
        assert diffs["weight_diff"] == candidate.weight - current.weight
        assert diffs["value_diff"] == candidate.value - current.value
        assert "Damage +5" in result["reason"]

    def test_item_comparison_downgrade_between_real_weapons(self):
        from src.items import Longsword, RustedDagger

        current, candidate = Longsword(), RustedDagger()
        result = self.ItemComparisonSerializer.serialize(current, candidate)

        assert result["recommendation"] == "downgrade"
        assert result["differences"]["damage_diff"] < 0
        assert result["current"]["equipped"] is True
        assert result["candidate"]["equipped"] is False

    def test_item_comparison_armor_upgrade_uses_protection(self):
        from src.items import TatteredCloth, IronCuirass

        result = self.ItemComparisonSerializer.serialize(
            TatteredCloth(), IronCuirass()
        )

        assert result["recommendation"] == "upgrade"
        assert result["differences"]["damage_diff"] == 0
        assert result["differences"]["protection_diff"] > 0
        assert "Protection +" in result["reason"]

    def test_item_comparison_sidegrade_trades_damage_for_protection(self):
        """A sidegrade needs one stat up and the other down. No real pair does
        that (weapons carry no protection), so this builds the mixed case from
        two real items by moving the candidate's protection up."""
        from src.items import Longsword, Shortsword

        current = Longsword()  # damage 30
        candidate = Shortsword()  # damage 25
        candidate.protection = 5

        result = self.ItemComparisonSerializer.serialize(current, candidate)

        assert result["differences"]["damage_diff"] == -5
        assert result["differences"]["protection_diff"] == 5
        assert result["recommendation"] == "sidegrade"


# ===========================================================================
# EventSerializer
# ===========================================================================


class TestEventSerializer:
    """`EventSerializer` against **real** `src.events` / `src.story` events.

    The previous version hand-set `description`, `one_time_only`, `triggered`,
    `event_type`, `hidden` and `hide_factor` on a `MagicMock`. No real `Event`
    defines any of those, so every one of the serializer's `hasattr` guards
    reported True in the tests and False in production — the tests could not
    tell a live branch from a dead one.
    """

    def setup_method(self):
        from src.api.serializers.event_serializer import EventSerializer

        self.EventSerializer = EventSerializer

    @staticmethod
    def _event(name="TestEvent", **kwargs):
        from src.events import Event

        return Event(name=name, **kwargs)

    def test_serialize_none_event(self):
        assert self.EventSerializer.serialize(None) == {}
        assert self.EventSerializer.serialize_list([]) == []
        assert self.EventSerializer.serialize_list(None) == []

    def test_serialize_a_real_base_event(self):
        event = self._event()
        result = self.EventSerializer.serialize(event)

        assert result["id"] == str(id(event))
        assert result["type"] == "Event"
        assert result["name"] == "TestEvent"
        assert result["repeat"] is False
        assert result["completed"] is False
        # `delay_mode` defaults to "combat" on every Event, so the delay block
        # is always emitted in real play.
        assert result["delay_mode"] == "combat"
        assert result["delay_duration"] == 3000

    def test_base_events_define_none_of_the_optional_metadata(self):
        """Pins which serializer branches are actually dead on a real Event."""
        event = self._event()
        for attr in (
            "description",
            "one_time_only",
            "triggered",
            "event_type",
            "hidden",
            "hide_factor",
            "presentation",
        ):
            assert not hasattr(event, attr), attr

        result = self.EventSerializer.serialize(event)
        assert result["description"] == ""
        for key in (
            "one_time_only",
            "triggered",
            "event_type",
            "hidden",
            "hide_factor",
            "presentation",
        ):
            assert key not in result

    def test_optional_metadata_is_emitted_when_an_event_carries_it(self):
        event = self._event()
        event.description = "A cold wind rises."
        event.one_time_only = True
        event.triggered = True
        event.event_type = "ambush"
        event.hidden = True
        event.hide_factor = 4

        result = self.EventSerializer.serialize(event)
        assert result["description"] == "A cold wind rises."
        assert result["one_time_only"] is True
        assert result["triggered"] is True
        assert result["event_type"] == "ambush"
        assert result["hidden"] is True
        assert result["hide_factor"] == 4

    def test_falsy_delay_mode_suppresses_the_delay_block(self):
        event = self._event(delay_mode=None)

        result = self.EventSerializer.serialize(event)
        assert "delay_mode" not in result
        assert "delay_duration" not in result

    def test_custom_delay_duration_round_trips(self):
        event = self._event(delay_mode="fade", delay_duration=2000)

        result = self.EventSerializer.serialize(event)
        assert result["delay_mode"] == "fade"
        assert result["delay_duration"] == 2000

    def test_memory_flash_presentation_hint_reaches_the_client(self, player):
        """`MemoryFlash` is the one real event that sets `presentation`; the
        client keys its Memory Flash flair off this exact string."""
        from src.story.effects import MemoryFlash

        flash = MemoryFlash(player=player, tile=None, memory_lines=["a line"])
        assert flash.presentation == "memory_flash"

        result = self.EventSerializer.serialize(flash)
        assert result["presentation"] == "memory_flash"
        assert result["type"] == "MemoryFlash"

    def test_serialize_list_preserves_order(self):
        first, second = self._event("First"), self._event("Second")

        result = self.EventSerializer.serialize_list([first, second])
        assert [r["name"] for r in result] == ["First", "Second"]

    # -- serialize_with_input ----------------------------------------------

    def test_combat_event_is_input_needing_out_of_the_box(self):
        """A real `CombatEvent` ships `needs_input=True` and
        `input_type="choice"` — no test scaffolding required."""
        from src.events import CombatEvent

        event = CombatEvent(name="Ambush")
        assert event.needs_input is True

        result = self.EventSerializer.serialize_with_input(event)
        assert result["needs_input"] is True
        assert result["input_type"] == "choice"
        assert result["input_prompt"] == event.input_prompt == "Prepare for combat!"
        assert result["input_options"] == event.input_options
        # api_event_id is None until the API assigns one, so no event_id key.
        assert "event_id" not in result

    def test_input_prompt_falls_back_to_the_generic_string(self):
        event = self._event()
        event.needs_input = True
        assert not hasattr(event, "input_prompt")
        assert not hasattr(event, "get_input_prompt")

        result = self.EventSerializer.serialize_with_input(event)
        assert result["input_prompt"] == "Please make your choice:"
        assert result["input_options"] == []

    def test_api_event_id_is_preserved_for_multi_stage_events(self):
        from src.events import CombatEvent

        event = CombatEvent(name="Ambush")
        event.api_event_id = "evt_123"
        event.input_prompt = "What do you do?"
        event.input_options = ["Attack", "Flee"]

        result = self.EventSerializer.serialize_with_input(event)
        assert result["event_id"] == "evt_123"
        assert result["input_prompt"] == "What do you do?"
        assert result["input_options"] == ["Attack", "Flee"]

    def test_get_input_options_callable_is_used_when_present(self):
        event = self._event()
        event.needs_input = True
        event.get_input_options = lambda: ["Left", "Right"]
        event.get_input_prompt = lambda: "Which way?"

        result = self.EventSerializer.serialize_with_input(event)
        assert result["input_type"] == "choice"
        assert result["input_prompt"] == "Which way?"
        assert result["input_options"] == ["Left", "Right"]

    def test_number_input_carries_its_bounds(self):
        event = self._event()
        event.needs_input = True
        event.input_type = "number"
        event.input_prompt = "How many?"
        event.input_min = 1
        event.input_max = 100

        result = self.EventSerializer.serialize_with_input(event)
        assert result["input_type"] == "number"
        assert result["input_min"] == 1
        assert result["input_max"] == 100
        assert "input_options" not in result

    @pytest.mark.parametrize(
        "max_length,expected", [(100, 100), (None, 500)]
    )
    def test_text_input_max_length_and_its_default(self, max_length, expected):
        event = self._event()
        event.needs_input = True
        event.input_type = "text"
        event.input_prompt = "Your name?"
        if max_length is not None:
            event.input_max_length = max_length

        result = self.EventSerializer.serialize_with_input(event)
        assert result["input_type"] == "text"
        assert result["input_max_length"] == expected

    def test_a_plain_event_needs_no_input(self):
        event = self._event()
        assert event.needs_input is False

        result = self.EventSerializer.serialize_with_input(event)
        assert result["needs_input"] is False
        assert "input_type" not in result
        assert "input_prompt" not in result

    # -- _detect_input_requirement -----------------------------------------

    def test_every_name_in_the_legacy_fallback_list_is_a_real_class(self):
        """The list previously named four classes that exist nowhere in the
        repo, so the fallback silently matched nothing. Resolve each name
        against the modules that own them."""
        import inspect
        import src.events as events
        import src.story.effects as effects
        from src.api.serializers.event_serializer import EventSerializer

        source = inspect.getsource(EventSerializer._detect_input_requirement)
        listed = [
            line.strip().strip('",')
            for line in source.splitlines()
            if line.strip().startswith('"') and line.strip().endswith('",')
        ]
        assert listed, "could not extract the fallback list"
        for name in listed:
            assert hasattr(events, name) or hasattr(effects, name), (
                f"{name} is in the input-requiring fallback list but is not a "
                "real Event class"
            )

    def test_whispering_statue_is_detected_by_name(self, player):
        """A resolve-on-first-call story event with no `needs_input` flag."""
        from src.story.effects import WhisperingStatue

        statue = WhisperingStatue(player=player, tile=None)
        assert not getattr(statue, "needs_input", False)
        assert not hasattr(statue, "awaits_input")

        assert self.EventSerializer._detect_input_requirement(statue) is True

    def test_awaits_input_opt_in_is_honoured(self):
        event = self._event()
        assert self.EventSerializer._detect_input_requirement(event) is False

        event.awaits_input = True
        assert self.EventSerializer._detect_input_requirement(event) is True

    def test_requires_input_method_is_called(self):
        calls = []
        event = self._event()
        event.requires_input = lambda: (calls.append(1), True)[1]

        assert self.EventSerializer._detect_input_requirement(event) is True
        assert calls == [1]

    def test_a_raising_requires_input_falls_through_instead_of_crashing(self):
        def boom():
            raise RuntimeError("event is mid-teardown")

        event = self._event()
        event.requires_input = boom

        assert self.EventSerializer._detect_input_requirement(event) is False

    def test_npc_spawner_is_deliberately_not_input_requiring(self):
        """It spawns silently; treating it as interactive soft-locked the
        client waiting for a prompt that never came."""
        import inspect
        from src.api.serializers.event_serializer import EventSerializer

        source = inspect.getsource(EventSerializer._detect_input_requirement)
        assert '"NPCSpawnerEvent"' not in source

    # -- _infer_input_type --------------------------------------------------

    def test_infer_choice_from_a_choices_attribute(self):
        event = self._event()
        event.choices = ["A", "B"]

        assert self.EventSerializer._infer_input_type(event) == "choice"

    def test_infer_number_from_bounds(self):
        event = self._event()
        event.input_min = 1
        event.input_max = 10

        assert self.EventSerializer._infer_input_type(event) == "number"

    def test_infer_defaults_to_choice(self):
        event = self._event()

        assert self.EventSerializer._infer_input_type(event) == "choice"


# ===========================================================================
# ObjectSerializer
# ===========================================================================


class TestObjectSerializer:
    """`ObjectSerializer` against **real** `src.objects` world objects.

    The old version mocked every attribute the serializer probes, including
    `contents`, `items_here`, `capacity`, `opened`, `is_passable` and
    `open_message` — none of which any real object defines. It also patched
    `serialize_container` out and then asserted the patch's own return value,
    so the container dispatch was never actually exercised.
    """

    def setup_method(self):
        from src.api.serializers.object_serializer import ObjectSerializer

        self.ObjectSerializer = ObjectSerializer

    @staticmethod
    def _container(**kwargs):
        from src.objects import Container

        return Container(**kwargs)

    def test_serialize_none_obj(self):
        assert self.ObjectSerializer.serialize(None) == {}
        assert self.ObjectSerializer.serialize_list([]) == []
        assert self.ObjectSerializer.serialize_list(None) == []

    def test_serialize_a_real_passageway(self):
        from src.objects import Passageway

        passage = Passageway(player=None, tile=None)
        result = self.ObjectSerializer.serialize(passage)

        assert result["id"] == str(id(passage))
        assert result["name"] == "Passageway"
        assert result["type"] == "Passageway"
        assert result["description"] == passage.description
        assert result["keywords"] == passage.keywords
        assert result["hidden"] is False
        assert result["hide_factor"] == 0
        assert result["passthrough"] is False
        assert result["idle_message"] == passage.idle_message
        # Passageways carry no lock/open state, so those keys stay absent.
        assert "locked" not in result
        assert "state" not in result
        assert "opened" not in result

    def test_serialize_dict_shaped_object(self):
        """Map JSON hands the serializer plain dicts for some objects."""
        obj = {
            "id": "door_1",
            "name": "Iron Door",
            "type": "Door",
            "description": "A heavy iron door.",
            "aliases": ["door"],
            "action_aliases": [],
            "locked": True,
            "keywords": ["examine", "open"],
        }
        result = self.ObjectSerializer._serialize_base(obj)

        assert result["id"] == "door_1"
        assert result["name"] == "Iron Door"
        assert result["type"] == "Door"
        assert result["aliases"] == ["door"]
        assert result["locked"] is True
        # Locked objects offer unlock and never open.
        assert result["keywords"] == ["examine", "unlock"]

    def test_dict_without_a_type_is_labelled_dict(self):
        result = self.ObjectSerializer._serialize_base({"name": "Thing"})

        assert result["type"] == "dict"
        assert result["description"] == ""
        assert result["aliases"] == []

    def test_locked_container_offers_unlock_not_open(self):
        chest = self._container(name="Chest", locked=True)
        assert chest.state == "closed"

        result = self.ObjectSerializer.serialize(chest)
        assert result["locked"] is True
        assert result["state"] == "closed"
        assert result["opened"] is False
        assert "unlock" in result["keywords"]
        assert "open" not in result["keywords"]

    def test_closed_unlocked_container_offers_open(self):
        chest = self._container(name="Chest")

        result = self.ObjectSerializer.serialize(chest)
        assert result["locked"] is False
        assert result["opened"] is False
        assert "open" in result["keywords"]
        assert "unlock" not in result["keywords"]

    def test_open_container_offers_neither_open_nor_unlock(self):
        chest = self._container(name="Chest", start_open=True)
        assert chest.state == "opened"

        result = self.ObjectSerializer.serialize(chest)
        assert result["state"] == "opened"
        assert result["opened"] is True
        assert "open" not in result["keywords"]
        assert "unlock" not in result["keywords"]
        # Its own non-state keywords survive the rewrite.
        assert "loot" in result["keywords"]

    def test_serialize_dispatches_a_real_container_to_serialize_container(self):
        """`isinstance(obj, Container)` is the dispatch — no patching, so a
        broken dispatch actually fails this test."""
        from src.items import Longsword
        from src.objects import Container

        chest = self._container(name="Chest", inventory=[Longsword()])
        assert isinstance(chest, Container)

        result = self.ObjectSerializer.serialize(chest)
        assert result["is_container"] is True
        assert result["item_count"] == 1
        assert result["contents"][0]["name"] == "Longsword"

    def test_non_container_object_gets_no_container_block(self):
        from src.objects import Passageway

        result = self.ObjectSerializer.serialize(Passageway(player=None, tile=None))
        assert "is_container" not in result
        assert "contents" not in result

    def test_container_contents_are_fully_serialized_items(self):
        from src.items import Longsword, Restorative

        chest = self._container(
            name="Chest", inventory=[Longsword(), Restorative()]
        )
        result = self.ObjectSerializer.serialize_container(chest)

        assert result["item_count"] == 2
        names = [c["name"] for c in result["contents"]]
        assert names == ["Longsword", "Restorative"]
        assert result["contents"][0]["value"] == 150
        assert "take" in result["contents"][0]["keywords"]

    def test_empty_container_reports_zero_items(self):
        chest = self._container(name="Empty Box", inventory=[])
        assert chest.inventory == []

        result = self.ObjectSerializer.serialize_container(chest)
        assert result["contents"] == []
        assert result["item_count"] == 0

    @pytest.mark.parametrize("attr", ["contents", "items_here"])
    def test_legacy_contents_attribute_names_are_still_read(self, attr):
        """No engine object uses these names any more; the branches exist for
        legacy/unpickled objects, so they are exercised with a plain namespace
        rather than a mock that would satisfy all three at once."""
        from types import SimpleNamespace
        from src.items import Longsword

        obj = SimpleNamespace(name="Box", description="An old box")
        setattr(obj, attr, [Longsword()])

        result = self.ObjectSerializer.serialize_container(obj)
        assert result["is_container"] is True
        assert result["item_count"] == 1
        assert result["contents"][0]["name"] == "Longsword"

    def test_inventory_wins_over_the_legacy_names(self):
        from types import SimpleNamespace
        from src.items import Longsword, Restorative

        obj = SimpleNamespace(
            name="Box",
            description="",
            inventory=[Longsword()],
            contents=[Restorative(), Restorative()],
        )

        result = self.ObjectSerializer.serialize_container(obj)
        assert result["item_count"] == 1
        assert result["contents"][0]["name"] == "Longsword"

    def test_capacity_is_reported_when_the_object_declares_one(self):
        from types import SimpleNamespace

        obj = SimpleNamespace(name="Crate", description="", capacity=10)

        result = self.ObjectSerializer.serialize_container(obj)
        assert result["capacity"] == 10

    def test_real_containers_declare_no_capacity(self):
        chest = self._container(name="Chest")
        assert not hasattr(chest, "capacity")

        assert "capacity" not in self.ObjectSerializer.serialize_container(chest)

    def test_serialize_list_mixes_containers_and_plain_objects(self):
        from src.items import Longsword
        from src.objects import Passageway

        chest = self._container(name="Chest", inventory=[Longsword()])
        passage = Passageway(player=None, tile=None)

        result = self.ObjectSerializer.serialize_list([chest, passage])
        assert [r["name"] for r in result] == ["Chest", "Passageway"]
        assert result[0]["is_container"] is True
        assert "is_container" not in result[1]

