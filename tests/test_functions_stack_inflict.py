"""Unit tests for functions.py — stack_items_list, stack_inv_items, inflict, add_preference.

Coverage targets (all in src/functions.py):
  - stack_items_list: empty/short list, stackable merging, stack_key path, merchandise key,
    stack_grammar callback, non-stackable items, duplicate id removal
  - stack_inv_items: delegates correctly, no inventory attr
  - inflict: resistance immunity, failed roll, existing state compound, replace in-place,
    new state append, on_application variants, force=True bypass
  - add_preference: arrow toggle, arrow change, other preftype
"""

import pathlib
import sys
import random
from unittest.mock import MagicMock, patch

_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import src.functions as functions
import src.states as states


# ---------------------------------------------------------------------------
# stack_items_list
# ---------------------------------------------------------------------------


class _Stackable:
    """Minimal stackable item (has a count attribute)."""

    def __init__(self, name="Rock", count=1, description="A rock"):
        self.name = name
        self.count = count
        self.description = description

    def __repr__(self):
        return f"<{self.name} x{self.count}>"


class _NonStackable:
    """Item without a count attribute."""

    def __init__(self, name="Sword"):
        self.name = name


class TestStackItemsList:
    def test_empty_list_does_nothing(self):
        lst = []
        functions.stack_items_list(lst)
        assert lst == []

    def test_single_item_does_nothing(self):
        item = _Stackable(count=3)
        lst = [item]
        functions.stack_items_list(lst)
        assert len(lst) == 1
        assert lst[0].count == 3

    def test_non_list_does_nothing(self):
        # Must be a list, not a tuple or set
        not_a_list = (_Stackable(), _Stackable())
        # Should not raise
        functions.stack_items_list(not_a_list)

    def test_merges_two_identical_stackable_items(self):
        a = _Stackable(name="Rock", count=3)
        b = _Stackable(name="Rock", count=2)
        lst = [a, b]
        functions.stack_items_list(lst)
        assert len(lst) == 1
        assert lst[0].count == 5

    def test_merges_three_identical_items(self):
        items = [_Stackable(count=1), _Stackable(count=2), _Stackable(count=4)]
        functions.stack_items_list(items)
        assert len(items) == 1
        assert items[0].count == 7

    def test_different_names_not_merged(self):
        a = _Stackable(name="Rock", count=1)
        b = _Stackable(name="Arrow", count=3)
        lst = [a, b]
        functions.stack_items_list(lst)
        assert len(lst) == 2

    def test_non_stackable_items_preserved(self):
        stackable = _Stackable(count=2)
        non_stackable = _NonStackable()
        lst = [stackable, non_stackable]
        functions.stack_items_list(lst)
        # Non-stackable preserved as-is; stackable alone so no merging
        assert len(lst) == 2

    def test_mixed_stackable_and_non_stackable(self):
        rock1 = _Stackable(name="Rock", count=1)
        rock2 = _Stackable(name="Rock", count=3)
        sword = _NonStackable(name="Sword")
        lst = [rock1, rock2, sword]
        functions.stack_items_list(lst)
        assert len(lst) == 2  # 1 merged rock + sword
        rocks = [i for i in lst if isinstance(i, _Stackable)]
        assert rocks[0].count == 4

    def test_stack_grammar_called_after_merge(self):
        a = _Stackable(count=1)
        b = _Stackable(count=2)
        a.stack_grammar = MagicMock()
        b.stack_grammar = MagicMock()
        lst = [a, b]
        functions.stack_items_list(lst)
        # stack_grammar should be called on the master (a)
        a.stack_grammar.assert_called_once()

    def test_stack_key_method_used_when_available(self):
        """Items providing stack_key() are grouped by it, not by class+name."""

        class KeyedItem:
            count = 5
            name = "Potion"
            description = "Heals"

            def stack_key(self):
                return "healing_potion_key"

        a = KeyedItem()
        b = KeyedItem()
        lst = [a, b]
        functions.stack_items_list(lst)
        assert len(lst) == 1
        assert lst[0].count == 10

    def test_merchandise_items_keyed_separately(self):
        """Merchandise and non-merchandise items should NOT merge with each other."""

        class MerchItem(_Stackable):
            merchandise = True

        a = _Stackable(name="Rock", count=1)
        b = MerchItem(name="Rock", count=1)
        lst = [a, b]
        functions.stack_items_list(lst)
        # Different keys → no merge
        assert len(lst) == 2

    def test_identical_merchandise_items_do_merge(self):
        """Two merchandise items of the same class/name should merge."""

        class MerchItem(_Stackable):
            merchandise = True

        a = MerchItem(name="Herb", count=2)
        b = MerchItem(name="Herb", count=3)
        lst = [a, b]
        functions.stack_items_list(lst)
        assert len(lst) == 1
        assert lst[0].count == 5

    def test_stack_key_as_attribute_not_callable(self):
        """stack_key as a plain attribute (not method) should still work."""

        class AttrKeyedItem:
            count = 3
            name = "Gem"
            description = ""
            stack_key = "gem_type_A"

        a = AttrKeyedItem()
        b = AttrKeyedItem()
        lst = [a, b]
        functions.stack_items_list(lst)
        assert len(lst) == 1
        assert lst[0].count == 6

    def test_master_preserves_identity_first_item(self):
        """The first item in the list should be the master after stacking."""
        a = _Stackable(count=1)
        b = _Stackable(count=9)
        lst = [a, b]
        functions.stack_items_list(lst)
        assert lst[0] is a
        assert a.count == 10


# ---------------------------------------------------------------------------
# stack_inv_items
# ---------------------------------------------------------------------------


class TestStackInvItems:
    def test_no_inventory_attr_does_nothing(self):
        target = object()  # has no 'inventory' attribute
        # Should not raise
        functions.stack_inv_items(target)

    def test_delegates_to_stack_items_list(self):
        target = MagicMock()
        rock1 = _Stackable(count=2)
        rock2 = _Stackable(count=3)
        target.inventory = [rock1, rock2]
        functions.stack_inv_items(target)
        # Should have merged the two rocks
        assert len(target.inventory) == 1
        assert target.inventory[0].count == 5

    def test_empty_inventory_does_nothing(self):
        target = MagicMock()
        target.inventory = []
        functions.stack_inv_items(target)
        assert target.inventory == []


# ---------------------------------------------------------------------------
# inflict
# ---------------------------------------------------------------------------


def _make_target_with_states(**status_resistance):
    """Return a minimal object suitable as an inflict target."""
    tgt = MagicMock()
    tgt.states = []
    tgt.status_resistance = {"poison": 1.0, "stun": 1.0, "generic": 1.0}
    tgt.status_resistance.update(status_resistance)
    return tgt


class TestInflict:
    def test_immune_target_returns_false(self):
        tgt = _make_target_with_states(poison=1.0)
        state = states.Poisoned(tgt)
        result = functions.inflict(state, tgt, chance=1.0)
        assert result is False

    def test_partial_resistance_can_fail(self, monkeypatch):
        tgt = _make_target_with_states(poison=0.5)
        state = states.Poisoned(tgt)
        # Make random.random return high value → fails roll
        monkeypatch.setattr(random, "random", lambda: 0.9)
        result = functions.inflict(state, tgt, chance=1.0)
        assert result is False

    def test_partial_resistance_can_succeed(self, monkeypatch):
        tgt = _make_target_with_states(poison=0.0)
        tgt.states = []
        state = states.Poisoned(tgt)
        monkeypatch.setattr(random, "random", lambda: 0.0)
        result = functions.inflict(state, tgt, chance=1.0)
        assert result is not False

    def test_force_bypasses_resistance(self):
        """force=True should apply even to a fully immune target."""
        tgt = _make_target_with_states(poison=1.0)
        tgt.states = []
        state = states.Poisoned(tgt)
        result = functions.inflict(state, tgt, chance=1.0, force=True)
        assert result is not False
        assert state in tgt.states

    def test_new_state_appended(self):
        tgt = _make_target_with_states(poison=0.0)
        tgt.states = []
        state = states.Poisoned(tgt)
        result = functions.inflict(state, tgt, chance=1.0)
        assert state in tgt.states
        assert result is state

    def test_existing_matching_state_replaced(self):
        """Non-compounding states should be replaced in-place."""
        tgt = _make_target_with_states()
        tgt.states = []

        # Create a non-compounding state type
        class SimpleState:
            statustype = "stun"
            compounding = False

            def on_application(self, target=None):
                pass

        old = SimpleState()
        tgt.states = [old]
        new_state = SimpleState()
        result = functions.inflict(new_state, tgt, chance=1.0, force=True)
        assert old not in tgt.states
        assert new_state in tgt.states
        assert result is new_state

    def test_compounding_state_calls_compound(self):
        tgt = _make_target_with_states()
        tgt.states = []

        class CompoundingState:
            statustype = "generic"
            compounding = True

            def compound(self, target):
                self._compounded = True

            def on_application(self, target=None):
                pass

        existing = CompoundingState()
        tgt.states = [existing]
        new_instance = CompoundingState()
        result = functions.inflict(new_instance, tgt, chance=1.0, force=True)
        assert result is existing
        assert getattr(existing, "_compounded", False) is True

    def test_no_existing_state_appends_new(self):
        tgt = _make_target_with_states()
        tgt.states = []
        state = states.Parrying(tgt)
        result = functions.inflict(state, tgt, chance=1.0, force=True)
        assert state in tgt.states
        assert result is state

    def test_guaranteed_application_no_roll_needed(self, monkeypatch):
        """With zero resistance and chance=1.0, no roll should be made."""
        tgt = _make_target_with_states(poison=0.0)
        tgt.states = []
        state = states.Poisoned(tgt)
        roll_count = []

        def counting_random():
            roll_count.append(1)
            return 0.0

        monkeypatch.setattr(random, "random", counting_random)
        functions.inflict(state, tgt, chance=1.0)
        # effective_chance = 1.0 * (1-0.0) = 1.0 → no roll needed
        assert len(roll_count) == 0


# ---------------------------------------------------------------------------
# add_preference
# ---------------------------------------------------------------------------


class TestAddPreference:
    def _make_player(self, arrow_pref="None"):
        player = MagicMock()
        player.preferences = {"arrow": arrow_pref, "weapon": "None"}
        return player

    def test_arrow_preference_set_to_new_value(self):
        player = self._make_player(arrow_pref="None")
        with patch("src.functions.colored", side_effect=lambda t, *a, **k: t), \
             patch("builtins.print"):
            functions.add_preference(player, "arrow", "WoodenArrow")
        assert player.preferences["arrow"] == "WoodenArrow"

    def test_arrow_preference_toggled_off_when_same(self):
        player = self._make_player(arrow_pref="WoodenArrow")
        with patch("src.functions.colored", side_effect=lambda t, *a, **k: t), \
             patch("builtins.print"):
            functions.add_preference(player, "arrow", "WoodenArrow")
        assert player.preferences["arrow"] == "None"

    def test_other_preftype_sets_directly(self):
        player = self._make_player()
        with patch("src.functions.colored", side_effect=lambda t, *a, **k: t), \
             patch("builtins.print"):
            functions.add_preference(player, "weapon", "Dagger")
        assert player.preferences["weapon"] == "Dagger"

    def test_arrow_print_called(self):
        player = self._make_player(arrow_pref="None")
        with patch("src.functions.colored", side_effect=lambda t, *a, **k: t), \
             patch("builtins.print") as mock_print:
            functions.add_preference(player, "arrow", "WoodenArrow")
        mock_print.assert_called_once()

    def test_non_arrow_print_called(self):
        player = self._make_player()
        with patch("src.functions.colored", side_effect=lambda t, *a, **k: t), \
             patch("builtins.print") as mock_print:
            functions.add_preference(player, "weapon", "Spear")
        mock_print.assert_called_once()
