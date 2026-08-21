"""End-to-end lifecycle tests for the PhoenixRevive enchantment and state.

Every test here drives the **real** engine objects: a real ``src.player.Player``,
the real ``OfThePhoenix`` enchantment, and the real
``Player.equip_item``/``unequip_item`` → ``Item.on_equip``/``on_unequip`` →
``apply_equip_states``/``remove_equip_states``/``recharge_equip_states`` chain,
plus ``Combatant.check_revive``.

This file previously defined its own copies of ``apply_equip_states`` and
``recharge_equip_states`` inside its fixtures and asserted against those copies,
so the engine could have deleted the real methods outright without a single test
turning red (CLAUDE.md: "a mock cannot catch a mock agreeing with itself").
Do not reintroduce a hand-written stand-in for the unit under test — patch a
single method on a real object instead if a state is otherwise unreachable.

Covers: equip applies the state, a lethal hit revives at 50% HP and consumes it,
a second lethal hit in the same fight does not re-trigger, victory recharges it,
unequip removes it (unless another equipped item still grants it), and neither
equip nor recharge ever stacks a duplicate.
"""

import pytest
from unittest.mock import patch

import src.items as items
from src.enchant_tables import OfThePhoenix
from src.states import PhoenixRevive

PHOENIX = "Phoenix Revive"


def enchant_phoenix(item_cls):
    """Return a real item of ``item_cls`` carrying a real ``OfThePhoenix``.

    Mirrors what ``functions.add_random_enchantments`` does at spawn time:
    construct the enchantment, run ``modify()`` (which renames/reprices the
    item), and hand its ``equip_states`` to the item.
    """
    item = item_cls()
    enchantment = OfThePhoenix(item)
    enchantment.modify()
    item.equip_states = enchantment.equip_states
    return item


def phoenix_states(player):
    return [s for s in player.states if s.name == PHOENIX]


@pytest.fixture
def player(make_player):
    """A real ``Player`` at full health with no states applied yet."""
    return make_player(hp=100, maxhp=100)


@pytest.fixture
def boots(player):
    """Phoenix-enchanted boots sitting in the real player's inventory.

    Boots are used rather than a weapon because ``OfThePhoenix.requirements()``
    only admits Armor/Helm/Gloves/Boots/Accessory, and because the default
    loadout leaves the Boots slot free (Armor, Helm and Ring are taken).
    """
    item = enchant_phoenix(items.LeatherBoots)
    player.inventory.append(item)
    return item


@pytest.fixture
def gloves(player):
    """A second, independent Phoenix source for the multi-item cases."""
    item = enchant_phoenix(items.LeatherGloves)
    player.inventory.append(item)
    return item


class TestPhoenixReviveState:
    """The state object's own contract and ``try_revive`` mechanics."""

    def test_revive_state_initialization(self, player):
        state = PhoenixRevive(player)

        assert state.name == PHOENIX
        assert state.target is player
        assert state.chance == 0.25
        assert state.persistent is True
        assert state.combat is True
        assert state.world is False
        assert state.beats_max == 0
        assert state.statustype == "revive"

    def test_revive_on_lethal_damage_success(self, player):
        """A winning roll heals to 50% maxhp and consumes the state."""
        state = PhoenixRevive(player)
        player.states = [state]
        player.hp = 0

        with patch("random.random", return_value=0.2):  # < 0.25 → triggers
            result = state.try_revive(player)

        assert result is True
        assert player.hp == 50
        assert state not in player.states

    def test_revive_roll_boundary_is_exclusive(self, player):
        """A roll exactly at ``chance`` must NOT revive (``random() < chance``)."""
        state = PhoenixRevive(player)
        player.states = [state]
        player.hp = 0

        with patch("random.random", return_value=0.25):
            assert state.try_revive(player) is False

        assert player.hp == 0
        assert state in player.states

    def test_revive_on_lethal_damage_miss(self, player):
        state = PhoenixRevive(player)
        player.states = [state]
        player.hp = 0

        with patch("random.random", return_value=0.3):  # > 0.25 → no trigger
            result = state.try_revive(player)

        assert result is False
        assert player.hp == 0
        assert state in player.states

    def test_revive_does_not_trigger_without_lethal_damage(self, player):
        """A guaranteed roll is still wasted-proof while the player is alive."""
        state = PhoenixRevive(player)
        player.states = [state]
        player.hp = 1

        with patch("random.random", return_value=0.0):
            result = state.try_revive(player)

        assert result is False
        assert player.hp == 1
        assert state in player.states

    @pytest.mark.parametrize("maxhp, expected_hp", [(200, 100), (100, 50), (75, 37)])
    def test_revive_heals_to_half_maxhp(self, player, maxhp, expected_hp):
        """``int(maxhp * 0.5)`` — including the truncation on an odd maxhp."""
        state = PhoenixRevive(player)
        player.states = [state]
        player.maxhp = maxhp
        player.hp = 0

        with patch("random.random", return_value=0.0):
            state.try_revive(player)

        assert player.hp == expected_hp


class TestPhoenixEnchantment:
    """What ``OfThePhoenix`` puts on the item before anyone equips it."""

    def test_enchantment_supplies_one_untargeted_revive_state(self):
        item = items.LeatherBoots()
        enchantment = OfThePhoenix(item)

        assert len(enchantment.equip_states) == 1
        state = enchantment.equip_states[0]
        assert isinstance(state, PhoenixRevive)
        # Not bound to anyone yet — apply_equip_states is what re-targets it.
        assert state.target is None

    def test_modify_renames_and_reprices_the_item(self):
        item = items.LeatherBoots()
        base_value = item.value
        base_name = item.name

        OfThePhoenix(item).modify()

        assert item.name == base_name + " of the Phoenix"
        assert item.value == base_value * 2
        assert "radiating warmth" in item.announce

    @pytest.mark.parametrize(
        "item_cls, allowed",
        [
            (items.LeatherBoots, True),
            (items.LeatherGloves, True),
            (items.TatteredCloth, True),
            (items.ClothHood, True),
            (items.GoldRing, True),
            (items.Longsword, False),  # Weapons are not a legal Phoenix host
        ],
    )
    def test_requirements_admit_only_worn_gear(self, item_cls, allowed):
        assert OfThePhoenix(item_cls()).requirements() is allowed


class TestPhoenixReviveEquip:
    """The real equip path: ``equip_item`` → ``on_equip`` → ``apply_equip_states``."""

    def test_equipping_phoenix_gear_applies_and_retargets_the_state(
        self, player, boots
    ):
        assert phoenix_states(player) == []

        player.equip_item(item_object=boots)

        applied = phoenix_states(player)
        assert len(applied) == 1
        # The very object the item carries, now bound to this player.
        assert applied[0] is boots.equip_states[0]
        assert applied[0].target is player
        assert boots.isequipped is True

    def test_equipping_plain_gear_applies_nothing(self, player):
        plain = items.LeatherBoots()
        player.inventory.append(plain)

        player.equip_item(item_object=plain)

        assert plain.isequipped is True
        assert player.states == []

    def test_two_phoenix_items_do_not_stack_the_state(self, player, boots, gloves):
        player.equip_item(item_object=boots)
        player.equip_item(item_object=gloves)

        assert len(phoenix_states(player)) == 1

    def test_reapplying_the_same_item_does_not_stack(self, player, boots):
        player.apply_equip_states(boots)
        player.apply_equip_states(boots)

        assert len(phoenix_states(player)) == 1

    def test_apply_skips_a_same_named_state_from_another_source(self, player, boots):
        """The stacking guard is by *name*, not by object identity."""
        pre_existing = PhoenixRevive(player)
        player.states = [pre_existing]

        player.apply_equip_states(boots)

        assert phoenix_states(player) == [pre_existing]
        assert boots.equip_states[0] not in player.states


class TestPhoenixReviveUnequip:
    """The real unequip path: ``unequip_item`` → ``on_unequip`` → ``remove_equip_states``."""

    def test_unequip_removes_the_state(self, player, boots):
        player.equip_item(item_object=boots)
        assert phoenix_states(player)

        player.unequip_item(boots)

        assert phoenix_states(player) == []
        assert boots.isequipped is False

    def test_unequip_keeps_the_state_when_another_item_still_grants_it(
        self, player, boots, gloves
    ):
        """``remove_equip_states`` strips then reapplies from the remaining gear."""
        player.equip_item(item_object=boots)
        player.equip_item(item_object=gloves)

        player.unequip_item(boots)

        surviving = phoenix_states(player)
        assert len(surviving) == 1
        # Re-sourced from the gloves, since the boots' own state was stripped.
        assert surviving[0] is gloves.equip_states[0]
        assert surviving[0].target is player

        player.unequip_item(gloves)
        assert phoenix_states(player) == []

    def test_unequip_leaves_unrelated_states_alone(self, player, boots):
        from src.states import Poisoned

        player.equip_item(item_object=boots)
        unrelated = Poisoned(player)
        player.states.append(unrelated)

        player.unequip_item(boots)

        assert phoenix_states(player) == []
        assert unrelated in player.states


class TestPhoenixReviveVictoryRecharge:
    """``recharge_equip_states`` — the post-victory / session-load restore."""

    def test_recharge_restores_a_consumed_revive(self, player, boots):
        player.equip_item(item_object=boots)
        player.states = [s for s in player.states if s.name != PHOENIX]
        assert phoenix_states(player) == []

        player.recharge_equip_states()

        assert len(phoenix_states(player)) == 1

    def test_recharge_does_not_stack_a_still_charged_revive(self, player, boots):
        player.equip_item(item_object=boots)
        assert len(phoenix_states(player)) == 1

        player.recharge_equip_states()

        assert len(phoenix_states(player)) == 1

    def test_recharge_ignores_unequipped_phoenix_gear(self, player, boots):
        """Carrying the boots in the bag must not grant the revive."""
        assert boots.isequipped is False

        player.recharge_equip_states()

        assert phoenix_states(player) == []


class TestPhoenixReviveInCombatantDeathCheck:
    """``Combatant.check_revive`` — what the combat adapter actually calls."""

    def test_check_revive_consumes_the_state_and_reports_true(self, player, boots):
        player.equip_item(item_object=boots)
        player.hp = 0

        with patch("random.random", return_value=0.0):
            assert player.check_revive() is True

        assert player.hp == 50
        assert player.is_alive() is True
        assert phoenix_states(player) == []

    def test_second_lethal_hit_in_the_same_fight_does_not_revive(self, player, boots):
        player.equip_item(item_object=boots)
        player.hp = 0

        with patch("random.random", return_value=0.0):
            assert player.check_revive() is True

        player.hp = 0
        # No patch needed: the state is gone, so no roll can happen at all.
        assert player.check_revive() is False
        assert player.hp == 0
        assert player.is_alive() is False

    def test_check_revive_is_false_with_no_revive_states(self, player):
        player.hp = 0

        with patch("random.random", return_value=0.0):
            assert player.check_revive() is False

        assert player.hp == 0

    def test_check_revive_tolerates_states_without_try_revive(self, player, boots):
        """A mixed state list must not break the revive scan."""
        from src.states import Poisoned

        player.equip_item(item_object=boots)
        player.states.insert(0, Poisoned(player))
        player.hp = 0

        with patch("random.random", return_value=0.0):
            assert player.check_revive() is True

        assert player.hp == 50


class TestPhoenixReviveIntegration:
    """The whole arc on one real player: equip → die → revive → win → unequip."""

    def test_full_lifecycle(self, player, boots):
        # 1. Equip — the state is granted and bound to Jean.
        player.equip_item(item_object=boots)
        assert len(phoenix_states(player)) == 1
        assert phoenix_states(player)[0].target is player

        # 2. Lethal damage — the revive fires and is consumed.
        player.hp = 0
        with patch("random.random", return_value=0.0):
            assert player.check_revive() is True
        assert player.hp == 50
        assert phoenix_states(player) == []

        # 3. A second lethal hit in the same fight finds nothing left.
        player.hp = 0
        assert player.check_revive() is False

        # 4. Victory — recharge restores it for the next fight.
        player.hp = 50
        player.recharge_equip_states()
        assert len(phoenix_states(player)) == 1

        # 5. Unequip — the state goes away with the gear.
        player.unequip_item(boots)
        assert phoenix_states(player) == []

    def test_recharge_after_unequip_does_not_resurrect_the_state(self, player, boots):
        """The bug this guards: recharge reading the bag instead of worn gear."""
        player.equip_item(item_object=boots)
        player.unequip_item(boots)

        player.recharge_equip_states()

        assert phoenix_states(player) == []
        assert boots in player.inventory
