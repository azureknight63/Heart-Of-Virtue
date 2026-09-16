"""Serializer contract tests built on **real engine objects**, not mocks.

Issues #411/#412/#430/#431/#432 all shipped the same way: a serializer read an
attribute name that no real `Player`/`NPC`/`State`/`Item` defines, the
`getattr(..., default)` fallback hid it, and the only tests were mocks whose
attributes had been hand-set to the fabricated names — so they passed.

Every test here therefore constructs a genuine engine object (`src.player`,
`src.npc`, `src.states`, `src.items`) and asserts the serialized payload
carries real values. If an engine attribute is ever renamed, these fail instead
of silently reporting defaults.
"""

import pytest

from src.api.serializers.combat import CombatantSerializer, StateEffectSerializer
from src.api.serializers.inventory import ItemComparisonSerializer
from src.api.serializers.npc_serializer import NPCSerializer


@pytest.fixture
def slime():
    from src.npc._enemies import Slime

    return Slime()


# ---------------------------------------------------------------------------
# Issue #430 — CombatantSerializer stats / equipment
# ---------------------------------------------------------------------------


class TestCombatStatsFromRealObjects:
    """`_serialize_combat_stats` / `_serialize_combat_equipment` (#430)."""

    def test_player_stats_are_not_all_defaults(self, player):
        stats = CombatantSerializer._serialize_combat_stats(player)

        # The bug's signature: armor/defense/evasion == 0 and accuracy == 80
        # for every combatant that ever existed.
        assert stats["defense"] == round(player.protection)
        assert stats["defense"] > 0
        assert stats["evasion"] == round(player.finesse)
        assert stats["evasion"] > 0
        assert stats["accuracy"] != 80
        assert stats["speed"] == player.speed

    def test_player_damage_and_power_come_from_equipped_weapon(self, player):
        stats = CombatantSerializer._serialize_combat_stats(player)
        weapon = player.eq_weapon

        # Player has no `damage` attribute at all; it lives on the weapon.
        assert not hasattr(player, "damage")
        assert stats["damage"] == round(weapon.damage)
        expected_power = (
            weapon.damage
            + player.strength * weapon.str_mod
            + player.finesse * weapon.fin_mod
        )
        assert stats["attack_power"] == round(expected_power)
        assert stats["attack_power"] > 0

    def test_stronger_weapon_raises_attack_power(self, player):
        from src.items import Longsword

        before = CombatantSerializer._serialize_combat_stats(player)["attack_power"]
        player.eq_weapon = Longsword()
        after = CombatantSerializer._serialize_combat_stats(player)["attack_power"]

        assert after > before

    def test_npc_stats_use_flat_damage_and_protection(self, slime):
        stats = CombatantSerializer._serialize_combat_stats(slime)

        assert not hasattr(slime, "eq_weapon")
        assert stats["damage"] == round(slime.damage)
        assert stats["attack_power"] == round(slime.damage)
        assert stats["defense"] == round(slime.protection)
        assert stats["evasion"] == round(slime.finesse)

    def test_player_equipment_reports_starting_gear(self, player):
        equipment = CombatantSerializer._serialize_combat_equipment(player)

        # Jean starts with fists equipped plus Tattered Cloth in the body slot.
        assert not hasattr(player, "equipped")
        assert equipment["weapon"] is not None
        assert equipment["weapon"]["name"] == player.eq_weapon.name
        assert equipment["armor"] is not None
        assert equipment["armor"]["name"] == "Tattered Cloth"
        assert equipment["armor"]["protection"] >= 0

    def test_player_equipment_reports_real_resistance_dict(self, player):
        equipment = CombatantSerializer._serialize_combat_equipment(player)

        # The real attribute is singular `resistance`.
        assert not hasattr(player, "resistances")
        assert equipment["resistances"] == player.resistance
        assert equipment["resistances"]

    def test_equipping_better_armor_shows_in_the_body_slot(self, player):
        from src.items import IronCuirass

        for item in player.inventory:
            if getattr(item, "maintype", None) == "Armor":
                item.isequipped = False
        cuirass = IronCuirass()
        cuirass.isequipped = True
        player.inventory.append(cuirass)

        equipment = CombatantSerializer._serialize_combat_equipment(player)

        assert equipment["armor"]["name"] == cuirass.name
        assert equipment["armor"]["protection"] == round(cuirass.protection)

    def test_npc_equipment_is_empty_but_resistances_are_real(self, slime):
        equipment = CombatantSerializer._serialize_combat_equipment(slime)

        # NPCs equip nothing — they fight with `damage`/`combat_range`.
        assert equipment["weapon"] is None
        assert equipment["armor"] is None
        assert equipment["resistances"] == slime.resistance

    def test_serialize_combatant_payload_is_populated(self, player, slime):
        payload = CombatantSerializer.serialize_combatant(slime, reference=player)

        assert payload["name"] == slime.name
        assert payload["hp"] == slime.hp
        assert payload["stats"]["damage"] == round(slime.damage)
        assert payload["equipment"]["resistances"]

    def test_degraded_inventory_only_costs_the_equipment_block(self, slime):
        """A non-iterable inventory must not blank the whole combatant."""
        slime.inventory = object()

        payload = CombatantSerializer.serialize_combatant(slime)

        assert payload["name"] == slime.name
        assert payload["equipment"]["weapon"] is None


# ---------------------------------------------------------------------------
# Issue #431 — StateEffectSerializer statustype mapping
# ---------------------------------------------------------------------------


class TestStateEffectsFromRealStates:
    """Real `State` objects expose `statustype`, never `state_type` (#431)."""

    @pytest.mark.parametrize(
        "state_name,expected_type,expected_severity",
        [
            ("Poisoned", "ailment", "severe"),
            ("Enflamed", "ailment", "severe"),
            ("Slimed", "ailment", "severe"),
            ("Disoriented", "debuff", "moderate"),
            ("Petrified", "debuff", "moderate"),
            ("Hollowed", "debuff", "moderate"),
            ("Staggered", "debuff", "moderate"),
            ("Fervent", "buff", "light"),
            ("Clean", "buff", "light"),
            ("Dodging", "buff", "light"),
        ],
    )
    def test_real_states_map_to_frontend_vocabulary(
        self, player, state_name, expected_type, expected_severity
    ):
        import src.states as states

        state = getattr(states, state_name)(player)
        result = StateEffectSerializer.serialize_state(state)

        assert not hasattr(state, "state_type")
        assert result["name"] == state.name
        assert result["type"] == expected_type, (
            f"{state_name} (statustype={state.statustype}) mis-categorized"
        )
        assert result["severity"] == expected_severity

    def test_not_every_state_is_a_buff(self, player):
        """The bug's signature: `type` was "buff" for every effect, so poison
        rendered with the green buff colour in StatusEffectsIconPanel."""
        import src.states as states

        types = {
            StateEffectSerializer.serialize_state(cls(player))["type"]
            for cls in (states.Poisoned, states.Disoriented, states.Fervent)
        }
        assert types == {"ailment", "debuff", "buff"}

    def test_generic_statustype_polarity_comes_from_modifiers(self, player):
        """`generic` is the State default and is used by both polarities:
        Quarried strips protection, StoneBulwarkState grants it."""
        import src.states as states

        player.protection = 20
        quarried = states.Quarried(player)
        bulwark = states.StoneBulwarkState(player, 5)

        assert quarried.statustype == "generic"
        assert bulwark.statustype == "generic"
        assert StateEffectSerializer.serialize_state(quarried)["type"] == "debuff"
        assert StateEffectSerializer.serialize_state(bulwark)["type"] == "buff"

    def test_serialized_state_has_no_fabricated_damage_fields(self, player):
        import src.states as states

        state = states.Poisoned(player)
        result = StateEffectSerializer.serialize_state(state)

        # Real States compute damage inline per subclass — there is no generic
        # damage_per_turn/healing_per_turn/resistable attribute to report.
        assert "damage_per_turn" not in result
        assert "healing_per_turn" not in result
        assert "resistable" not in result
        assert result["beats_left"] == state.beats_left


# ---------------------------------------------------------------------------
# Issue #432 — NPCSerializer HP / hostility
# ---------------------------------------------------------------------------


class TestNPCSerializerFromRealNPCs:
    """`serialize()` must read `hp` and derive hostility (#432)."""

    def test_current_hp_is_reported(self, slime):
        slime.hp = 7
        result = NPCSerializer.serialize(slime)

        assert not hasattr(slime, "current_hp")
        assert result["health"] == 7
        assert result["max_health"] == slime.maxhp

    def test_hostility_derived_from_aggro(self, slime):
        result = NPCSerializer.serialize(slime)

        assert not hasattr(slime, "is_hostile")
        assert result["is_hostile"] is bool(slime.aggro)
        assert "attack" in result["keywords"]

    def test_friendly_npc_is_never_hostile(self):
        from src.npc._base import Friend

        ally = Friend(name="Ally", description="A friend", damage=5, aggro=True,
                      exp_award=0)
        result = NPCSerializer.serialize(ally)

        assert ally.friend is True
        assert result["is_hostile"] is False
        assert "attack" not in result.get("keywords", [])


# ---------------------------------------------------------------------------
# Issue #412 — ItemComparisonSerializer recommendation
# ---------------------------------------------------------------------------


class TestItemComparisonFromRealItems:
    """A strictly-worse item must never report "sidegrade" (#412)."""

    def test_real_weapons_have_no_protection_attribute(self):
        from src.items import Dagger

        assert not hasattr(Dagger(), "protection")

    def test_real_armor_has_no_damage_attribute(self):
        from src.items import LeatherArmor

        assert not hasattr(LeatherArmor(), "damage")

    # Dagger (piercing) vs Longsword (slashing) was the original pair here;
    # since #571 cross-type weapons are not ranked, so the #412 check uses
    # two piercing daggers — same category, same type, different damage.
    def test_weaker_weapon_is_a_downgrade(self):
        from src.items import Dagger, RustedDagger

        result = ItemComparisonSerializer.serialize(Dagger(), RustedDagger())

        assert result["differences"]["damage_diff"] < 0
        assert result["differences"]["protection_diff"] == 0
        assert result["recommendation"] == "downgrade"

    def test_stronger_weapon_is_an_upgrade(self):
        from src.items import Dagger, RustedDagger

        result = ItemComparisonSerializer.serialize(RustedDagger(), Dagger())

        assert result["recommendation"] == "upgrade"

    def test_weaker_armor_is_a_downgrade(self):
        from src.items import IronCuirass, LeatherArmor

        result = ItemComparisonSerializer.serialize(IronCuirass(), LeatherArmor())

        assert result["differences"]["protection_diff"] < 0
        assert result["differences"]["damage_diff"] == 0
        assert result["recommendation"] == "downgrade"

    def test_stronger_armor_is_an_upgrade(self):
        from src.items import IronCuirass, LeatherArmor

        result = ItemComparisonSerializer.serialize(LeatherArmor(), IronCuirass())

        assert result["recommendation"] == "upgrade"

    def test_equal_damage_weapons_of_the_same_type_are_a_sidegrade(self):
        """Same base damage type, same damage: the ladder still applies and
        the verdict is "sidegrade" (#412). Longsword/Shortsword are both
        slashing, so the only trade-off is weight."""
        from src.items import Longsword, Shortsword

        current, candidate = Longsword(), Shortsword()
        candidate.damage = current.damage  # equalize; keep both slashing

        result = ItemComparisonSerializer.serialize(current, candidate)

        assert result["recommendation"] == "sidegrade"

    def test_equal_damage_weapons_of_different_types_are_not_ranked(self):
        """Mace (crushing) vs Shortsword (slashing) used to be "sidegrade"
        purely because their damage numbers matched. That was a coincidence,
        not a verdict: the two weapons hit different resistance tables, so
        the serializer must not rank them at all (#571) — the same reason the
        beta loadout's Rusted Iron Mace must not read "DOWNGRADE"."""
        from src.items import Mace, Shortsword

        # Both deal 25 damage; the trade-off is damage type, not power.
        assert Mace().damage == Shortsword().damage
        result = ItemComparisonSerializer.serialize(Mace(), Shortsword())

        assert result["recommendation"] == "different_type"

    # -- Issue #571 — cross-damage-type weapons are not ranked ------------

    def test_beta_loadout_mace_vs_shortsword_is_different_type(self):
        """config_grondia_beta.ini starts Jean with a slashing Shortsword and
        a crushing Rusted Iron Mace. Every enemy on that route resists
        slashing and is weak to crushing, so "DOWNGRADE" on the mace (damage
        15 < 25) contradicts the engine. Cross-type weapons get a neutral
        verdict; the reason line names both types so the player can decide."""
        from src.items import RustedIronMace, Shortsword

        current, candidate = Shortsword(), RustedIronMace()
        result = ItemComparisonSerializer.serialize(current, candidate)

        assert result["recommendation"] == "different_type"
        reason = result["reason"].lower()
        assert "slashing" in reason
        assert "crushing" in reason
        # Raw numbers are still reported — the diff is a fact, the ranking
        # was the lie.
        assert result["differences"]["damage_diff"] == -10
        assert "Damage -10" in result["reason"]

    def test_beta_loadout_is_symmetric(self):
        """The verdict does not depend on which weapon is equipped."""
        from src.items import RustedIronMace, Shortsword

        result = ItemComparisonSerializer.serialize(RustedIronMace(), Shortsword())

        assert result["recommendation"] == "different_type"
        assert result["differences"]["damage_diff"] == 10

    def test_comparison_sides_carry_damage_type_and_subtype(self):
        """`comparison.current`/`comparison.candidate` come from
        ItemDetailSerializer, which omitted the weapon's type — the inventory
        row had it, the comparison did not, so the client had nothing to
        explain the verdict with."""
        from src.items import RustedIronMace, Shortsword

        result = ItemComparisonSerializer.serialize(Shortsword(), RustedIronMace())

        assert result["current"]["damage_type"] == "slashing"
        assert result["current"]["subtype"] == "Sword"
        assert result["candidate"]["damage_type"] == "crushing"
        assert result["candidate"]["subtype"] == "Bludgeon"

    def test_same_type_weapons_are_still_ranked(self):
        """Longsword vs Shortsword are both slashing: #571 must not silence
        the upgrade/downgrade verdict where it is legitimate."""
        from src.items import Longsword, Shortsword

        assert ItemComparisonSerializer.serialize(
            Shortsword(), Longsword()
        )["recommendation"] == "upgrade"
        assert ItemComparisonSerializer.serialize(
            Longsword(), Shortsword()
        )["recommendation"] == "downgrade"

    def test_armor_is_never_different_type(self):
        """Armor has no damage type; the cross-type branch is weapons-only."""
        from src.items import IronCuirass, LeatherArmor

        result = ItemComparisonSerializer.serialize(LeatherArmor(), IronCuirass())

        assert result["recommendation"] == "upgrade"
        assert "damage_type" not in result["candidate"]
