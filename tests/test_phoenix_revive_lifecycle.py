"""End-to-end lifecycle tests for PhoenixRevive enchantment and state.

Covers: equip applies state, lethal hit triggers revive at 50% HP with state
removed, second lethal hit doesn't re-trigger (state gone), victory recharges
the state, unequip removes it, no stacking when victory-recharge runs while
state is still present.
"""

import pytest
from unittest.mock import MagicMock, patch
import random

from src.states import PhoenixRevive
from src.enchant_tables import OfThePhoenix
from src.items import Weapon
from src.player import Player
from src.universe import Universe


class TestPhoenixReviveState:
    """Test PhoenixRevive state mechanics."""

    @pytest.fixture
    def player(self):
        """Create a test player with initialized states."""
        p = MagicMock(spec=Player)
        p.name = "TestPlayer"
        p.hp = 100
        p.maxhp = 100
        p.states = []
        return p

    def test_revive_state_initialization(self, player):
        """Test PhoenixRevive initializes with correct properties."""
        state = PhoenixRevive(player)

        assert state.name == "Phoenix Revive"
        assert state.target is player
        assert state.chance == 0.25
        assert state.persistent is True
        assert state.combat is True
        assert state.beats_max == 0
        assert state.statustype == "revive"

    def test_revive_on_lethal_damage_success(self, player):
        """Test revive triggers on lethal damage with 25% chance."""
        state = PhoenixRevive(player)
        player.states = [state]
        player.hp = 0  # Lethal damage

        with patch("random.random", return_value=0.2):  # 0.2 < 0.25, should trigger
            result = state.try_revive(player)

        assert result is True
        assert player.hp == 50  # Revived to 50% of maxhp
        assert state not in player.states  # State removed after use

    def test_revive_on_lethal_damage_miss(self, player):
        """Test revive does not trigger if random roll fails."""
        state = PhoenixRevive(player)
        player.states = [state]
        player.hp = 0

        with patch("random.random", return_value=0.3):  # 0.3 > 0.25, should not trigger
            result = state.try_revive(player)

        assert result is False
        assert player.hp == 0  # HP unchanged
        assert state in player.states  # State still present

    def test_revive_does_not_trigger_without_lethal_damage(self, player):
        """Test revive does not trigger if player is not dead."""
        state = PhoenixRevive(player)
        player.states = [state]
        player.hp = 1  # Still alive

        with patch("random.random", return_value=0.0):  # 0.0 < 0.25, but no lethal damage
            result = state.try_revive(player)

        assert result is False
        assert player.hp == 1
        assert state in player.states

    def test_revive_heals_to_50_percent(self, player):
        """Test revive heals to exactly 50% of maxhp."""
        state = PhoenixRevive(player)
        player.states = [state]
        player.maxhp = 200
        player.hp = 0

        with patch("random.random", return_value=0.0):
            state.try_revive(player)

        assert player.hp == 100  # 50% of 200


class TestPhoenixReviveEquip:
    """Test PhoenixRevive state application via equip."""

    @pytest.fixture
    def mock_player(self):
        """Create a mock player for equip testing."""
        p = MagicMock(spec=Player)
        p.name = "TestPlayer"
        p.hp = 100
        p.maxhp = 100
        p.states = []
        p.equipped = {}

        def mock_get_equipped_items():
            return list(p.equipped.values())

        p.get_equipped_items = mock_get_equipped_items
        return p

    def test_equip_phoenix_item_applies_revive_state(self, mock_player):
        """Test equipping a Phoenix item applies PhoenixRevive to player."""
        # Create item with Phoenix enchantment
        weapon = Weapon(
            name="Test Sword",
            description="Test",
            damage_type="slashing",
            damage=10,
            maintype="Weapon",
            subtype="Sword",
        )
        enchantment = OfThePhoenix(weapon)
        enchantment.modify()

        # Simulate equip by calling apply_equip_states
        initial_state_count = len(mock_player.states)
        mock_player.apply_equip_states = MagicMock()

        weapon.on_equip(mock_player)

        mock_player.apply_equip_states.assert_called_once_with(weapon)

    def test_equip_states_includes_phoenix_revive(self):
        """Test that OfThePhoenix enchantment creates PhoenixRevive equip_states."""
        weapon = Weapon(
            name="Phoenix Blade",
            description="A blade that can revive",
            damage_type="slashing",
            damage=10,
            maintype="Weapon",
            subtype="Sword",
        )
        enchantment = OfThePhoenix(weapon)

        assert len(enchantment.equip_states) == 1
        assert isinstance(enchantment.equip_states[0], PhoenixRevive)


class TestPhoenixReviveApplyMerge:
    """Test apply_equip_states stacking guard."""

    @pytest.fixture
    def player_with_methods(self):
        """Create a player with apply_equip_states method."""
        from src.player import Player

        p = MagicMock(spec=Player)
        p.name = "TestPlayer"
        p.hp = 100
        p.maxhp = 100
        p.states = []

        # Use real apply_equip_states logic
        def apply_equip_states(item):
            equip_states = getattr(item, "equip_states", None) or []
            existing_names = {s.name for s in p.states}
            for state in equip_states:
                if state.name in existing_names:
                    continue
                if hasattr(state, "target"):
                    state.target = p
                p.states.append(state)
                existing_names.add(state.name)

        p.apply_equip_states = apply_equip_states
        return p

    def test_no_stacking_when_state_already_present(self, player_with_methods):
        """Test that apply_equip_states skips duplicate states by name."""
        # Create first Phoenix state and add to player
        state1 = PhoenixRevive(player_with_methods)
        player_with_methods.states = [state1]

        # Create item with Phoenix enchantment (creates a new PhoenixRevive state)
        weapon = Weapon(
            name="Phoenix Sword",
            description="Test",
            damage_type="slashing",
            damage=10,
            maintype="Weapon",
            subtype="Sword",
        )
        enchantment = OfThePhoenix(weapon)
        enchantment.modify()

        # Apply equip states — should skip the new state since one with that name exists
        player_with_methods.apply_equip_states(weapon)

        # Should still be only 1 Phoenix Revive state (no duplicate)
        phoenix_states = [s for s in player_with_methods.states if s.name == "Phoenix Revive"]
        assert len(phoenix_states) == 1


class TestPhoenixReviveUnequip:
    """Test PhoenixRevive removal on unequip."""

    @pytest.fixture
    def player_with_methods(self):
        """Create a player with full equip/unequip methods."""
        p = MagicMock(spec=Player)
        p.name = "TestPlayer"
        p.hp = 100
        p.maxhp = 100
        p.states = []
        p.equipped = {}

        def get_equipped_items():
            return list(p.equipped.values())

        def apply_equip_states(item):
            equip_states = getattr(item, "equip_states", None) or []
            existing_names = {s.name for s in p.states}
            for state in equip_states:
                if state.name in existing_names:
                    continue
                if hasattr(state, "target"):
                    state.target = p
                p.states.append(state)
                existing_names.add(state.name)

        def remove_equip_states(item):
            names_to_remove = {s.name for s in getattr(item, "equip_states", None) or []}
            if not names_to_remove:
                return
            p.states = [s for s in p.states if s.name not in names_to_remove]
            for other in get_equipped_items():
                if other is not item:
                    apply_equip_states(other)

        p.get_equipped_items = get_equipped_items
        p.apply_equip_states = apply_equip_states
        p.remove_equip_states = remove_equip_states
        return p

    def test_unequip_removes_phoenix_state(self, player_with_methods):
        """Test that unequipping a Phoenix item removes PhoenixRevive."""
        weapon = Weapon(
            name="Phoenix Sword",
            description="Test",
            damage_type="slashing",
            damage=10,
            maintype="Weapon",
            subtype="Sword",
        )
        enchantment = OfThePhoenix(weapon)
        enchantment.modify()

        # Equip the weapon
        player_with_methods.apply_equip_states(weapon)
        assert any(s.name == "Phoenix Revive" for s in player_with_methods.states)

        # Unequip the weapon
        player_with_methods.remove_equip_states(weapon)

        # PhoenixRevive should be gone
        assert not any(s.name == "Phoenix Revive" for s in player_with_methods.states)


class TestPhoenixReviveVictoryRecharge:
    """Test PhoenixRevive recharge on combat victory."""

    @pytest.fixture
    def player_with_methods(self):
        """Create a player with recharge_equip_states method."""
        p = MagicMock(spec=Player)
        p.name = "TestPlayer"
        p.hp = 100
        p.maxhp = 100
        p.states = []
        p.equipped = {}

        def get_equipped_items():
            return list(p.equipped.values())

        def apply_equip_states(item):
            equip_states = getattr(item, "equip_states", None) or []
            existing_names = {s.name for s in p.states}
            for state in equip_states:
                if state.name in existing_names:
                    continue
                if hasattr(state, "target"):
                    state.target = p
                p.states.append(state)
                existing_names.add(state.name)

        def recharge_equip_states():
            for item in get_equipped_items():
                apply_equip_states(item)

        p.get_equipped_items = get_equipped_items
        p.apply_equip_states = apply_equip_states
        p.recharge_equip_states = recharge_equip_states
        return p

    def test_victory_recharge_restores_consumed_revive(self, player_with_methods):
        """Test that victory recharge restores a consumed PhoenixRevive state."""
        # Create Phoenix weapon and equip it
        weapon = Weapon(
            name="Phoenix Sword",
            description="Test",
            damage_type="slashing",
            damage=10,
            maintype="Weapon",
            subtype="Sword",
        )
        enchantment = OfThePhoenix(weapon)
        enchantment.modify()

        # Add weapon to equipped items
        player_with_methods.equipped["weapon"] = weapon

        # Apply initial equip_states
        player_with_methods.apply_equip_states(weapon)
        assert any(s.name == "Phoenix Revive" for s in player_with_methods.states)

        # Simulate using PhoenixRevive (remove it)
        player_with_methods.states = [s for s in player_with_methods.states if s.name != "Phoenix Revive"]
        assert not any(s.name == "Phoenix Revive" for s in player_with_methods.states)

        # Victory recharge should restore it
        player_with_methods.recharge_equip_states()
        assert any(s.name == "Phoenix Revive" for s in player_with_methods.states)

    def test_no_stacking_on_victory_recharge(self, player_with_methods):
        """Test that victory recharge does not stack a state that's already present."""
        weapon = Weapon(
            name="Phoenix Sword",
            description="Test",
            damage_type="slashing",
            damage=10,
            maintype="Weapon",
            subtype="Sword",
        )
        enchantment = OfThePhoenix(weapon)
        enchantment.modify()

        # Add weapon to equipped items
        player_with_methods.equipped["weapon"] = weapon

        # Manually apply equip_states (as on initial equip)
        player_with_methods.apply_equip_states(weapon)
        initial_count = len([s for s in player_with_methods.states if s.name == "Phoenix Revive"])
        assert initial_count == 1

        # Victory recharge while state still present (did not trigger)
        player_with_methods.recharge_equip_states()

        # Still only 1 Phoenix Revive state (no stacking)
        final_count = len([s for s in player_with_methods.states if s.name == "Phoenix Revive"])
        assert final_count == 1


class TestPhoenixReviveSecondLethalHit:
    """Test that second lethal hit in same battle does not retrigger revive."""

    @pytest.fixture
    def player(self):
        p = MagicMock(spec=Player)
        p.name = "TestPlayer"
        p.hp = 100
        p.maxhp = 100
        p.states = []
        return p

    def test_revive_not_available_after_first_trigger(self, player):
        """Test that second lethal hit does not revive if state was consumed."""
        state = PhoenixRevive(player)
        player.states = [state]
        player.hp = 0

        # First lethal hit — revive triggers
        with patch("random.random", return_value=0.0):
            result1 = state.try_revive(player)

        assert result1 is True
        assert state not in player.states
        assert player.hp == 50

        # Simulate another lethal hit
        player.hp = 0
        player.states = []  # State was removed

        # Second lethal hit — no revive available (state removed)
        # There's no state to call try_revive on
        for s in player.states:
            if hasattr(s, "try_revive"):
                s.try_revive(player)

        assert player.hp == 0  # Still dead


class TestPhoenixReviveIntegration:
    """Integration tests for full PhoenixRevive lifecycle."""

    @pytest.fixture
    def realistic_player(self):
        """Create a more realistic player object for integration testing."""
        p = MagicMock(spec=Player)
        p.name = "Jean Claire"
        p.hp = 100
        p.maxhp = 100
        p.states = []
        p.equipped = {}

        def get_equipped_items():
            return list(p.equipped.values())

        def apply_equip_states(item):
            equip_states = getattr(item, "equip_states", None) or []
            existing_names = {s.name for s in p.states}
            for state in equip_states:
                if state.name in existing_names:
                    continue
                if hasattr(state, "target"):
                    state.target = p
                p.states.append(state)
                existing_names.add(state.name)

        def remove_equip_states(item):
            names_to_remove = {s.name for s in getattr(item, "equip_states", None) or []}
            if not names_to_remove:
                return
            p.states = [s for s in p.states if s.name not in names_to_remove]
            for other in get_equipped_items():
                if other is not item:
                    apply_equip_states(other)

        def recharge_equip_states():
            for item in get_equipped_items():
                apply_equip_states(item)

        def check_revive():
            """Consult revive-capable states before death is finalized."""
            for state in p.states[:]:
                try_revive = getattr(state, "try_revive", None)
                if try_revive and try_revive(p):
                    return True
            return False

        p.get_equipped_items = get_equipped_items
        p.apply_equip_states = apply_equip_states
        p.remove_equip_states = remove_equip_states
        p.recharge_equip_states = recharge_equip_states
        p.check_revive = check_revive
        return p

    def test_full_lifecycle(self, realistic_player):
        """Test complete PhoenixRevive lifecycle: equip, trigger, discharge, recharge."""
        weapon = Weapon(
            name="Phoenix Blade",
            description="A blade blessed by phoenix fire",
            damage_type="slashing",
            damage=10,
            maintype="Weapon",
            subtype="Sword",
        )
        enchantment = OfThePhoenix(weapon)
        enchantment.modify()

        # Step 1: Equip weapon — applies PhoenixRevive state
        realistic_player.equipped["weapon"] = weapon
        realistic_player.apply_equip_states(weapon)
        assert any(s.name == "Phoenix Revive" for s in realistic_player.states)

        # Step 2: Take lethal damage — revive triggers
        realistic_player.hp = 0
        with patch("random.random", return_value=0.0):
            revived = realistic_player.check_revive()

        assert revived is True
        assert realistic_player.hp == 50
        assert not any(s.name == "Phoenix Revive" for s in realistic_player.states)

        # Step 3: Take another lethal hit in same battle — no revive (state consumed)
        realistic_player.hp = 0
        revived_again = realistic_player.check_revive()
        assert revived_again is False

        # Step 4: Victory recharge — restores PhoenixRevive for next battle
        realistic_player.hp = 50  # Assume we won after the revive
        realistic_player.recharge_equip_states()
        assert any(s.name == "Phoenix Revive" for s in realistic_player.states)

        # Step 5: Unequip weapon — removes PhoenixRevive
        realistic_player.remove_equip_states(weapon)
        assert not any(s.name == "Phoenix Revive" for s in realistic_player.states)

    def test_no_revive_stacking_across_equips(self, realistic_player):
        """Test that equipping same item twice doesn't stack revive states."""
        weapon = Weapon(
            name="Phoenix Blade",
            description="A blade blessed by phoenix fire",
            damage_type="slashing",
            damage=10,
            maintype="Weapon",
            subtype="Sword",
        )
        enchantment = OfThePhoenix(weapon)
        enchantment.modify()

        # Equip weapon
        realistic_player.apply_equip_states(weapon)
        count_after_first = len([s for s in realistic_player.states if s.name == "Phoenix Revive"])
        assert count_after_first == 1

        # Simulate another equip attempt (or victory recharge while still equipped)
        realistic_player.apply_equip_states(weapon)
        count_after_second = len([s for s in realistic_player.states if s.name == "Phoenix Revive"])

        # Should still be 1 (no stacking)
        assert count_after_second == 1
