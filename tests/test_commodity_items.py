import sys
import os
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)
if os.path.join(repo_root, 'src') not in sys.path:
    sys.path.insert(0, os.path.join(repo_root, 'src'))

from src.items import Commodity, Crystals, Special
from src.player import Player


class TestCommodityClass:
    """Test suite for the Commodity class (intermediate class between Special and commodity items)."""

    def test_commodity_inherits_from_special(self):
        """Commodity should inherit from Special class."""
        commodity = Commodity(
            name="Test Commodity",
            description="A test commodity item",
            value=50,
            weight=1.0,
            maintype="Special",
            subtype="Commodity"
        )
        assert isinstance(commodity, Special)
        assert isinstance(commodity, Commodity)

    def test_commodity_initialization_defaults(self):
        """Test that Commodity initializes with correct default values."""
        commodity = Commodity(
            name="Test Commodity",
            description="A test commodity item",
            value=50,
            weight=1.0,
            maintype="Special",
            subtype="Commodity"
        )
        assert commodity.name == "Test Commodity"
        assert commodity.description == "A test commodity item"
        assert commodity.value == 50
        assert commodity.weight == 1.0
        assert commodity.maintype == "Special"
        assert commodity.subtype == "Commodity"
        assert commodity.count == 1  # default count
        assert commodity.stack_key == "Test Commodity"
        assert commodity.interactions == ["drop"]
        assert commodity.merchandise is False  # default

    def test_commodity_with_custom_count(self):
        """Test Commodity initialization with custom count."""
        commodity = Commodity(
            name="Test Commodity",
            description="A test commodity item",
            value=50,
            weight=1.0,
            maintype="Special",
            subtype="Commodity",
            count=5
        )
        assert commodity.count == 5

    def test_commodity_with_merchandise_flag(self):
        """Test Commodity initialization with merchandise flag set."""
        commodity = Commodity(
            name="Test Commodity",
            description="A test commodity item",
            value=50,
            weight=1.0,
            maintype="Special",
            subtype="Commodity",
            merchandise=True
        )
        assert commodity.merchandise is True

    def test_commodity_stack_key_matches_name(self):
        """Test that stack_key is set to the item name for stacking logic."""
        commodity = Commodity(
            name="Unique Stack Key",
            description="Test",
            value=10,
            weight=0.5,
            maintype="Special",
            subtype="Commodity"
        )
        assert commodity.stack_key == "Unique Stack Key"

    def test_commodity_stack_grammar_method_exists(self):
        """Test that stack_grammar method exists and is callable."""
        commodity = Commodity(
            name="Test",
            description="Test",
            value=10,
            weight=0.5,
            maintype="Special",
            subtype="Commodity"
        )
        # Should not raise an error
        commodity.stack_grammar()

    def test_commodity_str_single_item(self):
        """Test __str__ method with a single item (count=1)."""
        commodity = Commodity(
            name="Test Commodity",
            description="A test commodity item",
            value=50,
            weight=1.0,
            maintype="Special",
            subtype="Commodity",
            count=1
        )
        result = str(commodity)
        assert "Test Commodity" in result
        assert "A test commodity item" in result
        assert "Count: 1" in result
        assert "Value: 50 gold each, 50 gold total" in result
        assert "Weight: 1.0 lbs each, 1.0 lbs total" in result

    def test_commodity_str_multiple_items(self):
        """Test __str__ method with multiple items in stack."""
        commodity = Commodity(
            name="Test Commodity",
            description="A test commodity item",
            value=50,
            weight=1.0,
            maintype="Special",
            subtype="Commodity",
            count=10
        )
        result = str(commodity)
        assert "Count: 10" in result
        assert "Value: 50 gold each, 500 gold total" in result
        assert "Weight: 1.0 lbs each, 10.0 lbs total" in result

    def test_commodity_drop_interaction_exists(self):
        """Test that 'drop' interaction is available."""
        commodity = Commodity(
            name="Test",
            description="Test",
            value=10,
            weight=0.5,
            maintype="Special",
            subtype="Commodity"
        )
        assert "drop" in commodity.interactions


class TestCrystalsClass:
    """Test suite for the Crystals class (first commodity-type item)."""

    def test_crystals_inherits_from_commodity(self):
        """Crystals should inherit from Commodity class."""
        crystals = Crystals()
        assert isinstance(crystals, Commodity)
        assert isinstance(crystals, Special)

    def test_crystals_initialization_defaults(self):
        """Test that Crystals initializes with correct default values."""
        crystals = Crystals()
        assert crystals.name == "Crystals"
        assert "scintillating purple and aquamarine crystals" in crystals.description
        assert crystals.value == 10
        assert crystals.weight == 0.1
        assert crystals.maintype == "Special"
        assert crystals.subtype == "Commodity"
        assert crystals.count == 1  # default count
        assert crystals.merchandise is False  # default

    def test_crystals_with_custom_count(self):
        """Test Crystals initialization with custom count."""
        crystals = Crystals(count=5)
        assert crystals.count == 5

    def test_crystals_with_merchandise_flag(self):
        """Test Crystals initialization with merchandise flag."""
        crystals = Crystals(merchandise=True)
        assert crystals.merchandise is True

    def test_crystals_announce_single(self):
        """Test that single crystal has appropriate announcement."""
        crystals = Crystals(count=1)
        assert crystals.announce == "Jean notices some crystals on the ground."

    def test_crystals_stack_grammar_single(self):
        """Test stack_grammar for a single crystal."""
        crystals = Crystals(count=1)
        crystals.stack_grammar()
        assert crystals.announce == "Jean notices some crystals on the ground."
        assert "scintillating purple and aquamarine crystals" in crystals.description

    def test_crystals_stack_grammar_multiple(self):
        """Test stack_grammar for multiple crystals."""
        crystals = Crystals(count=5)
        crystals.stack_grammar()
        assert crystals.announce == "Jean notices a pile of crystals on the ground."
        assert "scintillating purple and aquamarine crystals" in crystals.description

    def test_crystals_stack_grammar_changes_based_on_count(self):
        """Test that stack_grammar correctly updates based on count changes."""
        crystals = Crystals(count=1)
        # Initially single
        crystals.stack_grammar()
        assert "some crystals" in crystals.announce
        
        # Change to multiple
        crystals.count = 10
        crystals.stack_grammar()
        assert "pile of crystals" in crystals.announce
        
        # Change back to single
        crystals.count = 1
        crystals.stack_grammar()
        assert "some crystals" in crystals.announce

    def test_crystals_str_single(self):
        """Test __str__ method with a single crystal."""
        crystals = Crystals(count=1)
        result = str(crystals)
        assert "Crystals" in result
        assert "Count: 1" in result
        assert "Value: 10 gold each, 10 gold total" in result
        assert "Weight: 0.1 lbs each, 0.1 lbs total" in result

    def test_crystals_str_multiple(self):
        """Test __str__ method with multiple crystals."""
        crystals = Crystals(count=20)
        result = str(crystals)
        assert "Count: 20" in result
        assert "Value: 10 gold each, 200 gold total" in result
        assert "Weight: 0.1 lbs each, 2.0 lbs total" in result

    def test_crystals_discovery_message(self):
        """Test that Crystals has an appropriate discovery message."""
        crystals = Crystals()
        assert crystals.discovery_message == "some shimmering crystals."

    def test_crystals_drop_interaction(self):
        """Test that Crystals can be dropped."""
        crystals = Crystals()
        assert "drop" in crystals.interactions
        # Ensure 'use' and 'drink' are NOT in interactions (unlike consumables)
        assert "use" not in crystals.interactions
        assert "drink" not in crystals.interactions

    def test_crystals_lore_description(self):
        """Test that Crystals includes lore about Rock Rumblers and Grondites."""
        crystals = Crystals()
        assert "Rock Rumblers" in crystals.description
        assert "Grondites" in crystals.description
        assert "food source" in crystals.description

    def test_crystals_stack_key(self):
        """Test that Crystals has correct stack_key for inventory stacking."""
        crystals = Crystals()
        assert crystals.stack_key == "Crystals"


class TestCommodityPlayerInteractions:
    """Test commodity items interacting with player inventory."""

    def test_commodity_in_player_inventory(self):
        """Test that commodity items can be added to player inventory."""
        player = Player()
        commodity = Commodity(
            name="Test Commodity",
            description="Test",
            value=50,
            weight=1.0,
            maintype="Special",
            subtype="Commodity",
            count=3
        )
        player.inventory.append(commodity)
        assert commodity in player.inventory

    def test_crystals_in_player_inventory(self):
        """Test that Crystals can be added to player inventory."""
        player = Player()
        crystals = Crystals(count=5)
        player.inventory.append(crystals)
        assert crystals in player.inventory
        assert any(isinstance(item, Crystals) for item in player.inventory)

    def test_multiple_crystal_stacks_can_exist(self):
        """Test that multiple instances of Crystals can exist (though stacking logic should merge them)."""
        player = Player()
        crystals1 = Crystals(count=3)
        crystals2 = Crystals(count=5)
        player.inventory.append(crystals1)
        player.inventory.append(crystals2)
        
        crystal_items = [item for item in player.inventory if isinstance(item, Crystals)]
        assert len(crystal_items) == 2
        total_count = sum(item.count for item in crystal_items)
        assert total_count == 8

    def test_commodity_weight_calculation(self):
        """Test that commodity weight scales with count."""
        commodity = Commodity(
            name="Heavy Commodity",
            description="Test",
            value=10,
            weight=2.5,
            maintype="Special",
            subtype="Commodity",
            count=4
        )
        # Total weight should be 2.5 * 4 = 10.0
        expected_total_weight = 2.5 * 4
        # The __str__ method shows this calculation
        result = str(commodity)
        assert f"Weight: 2.5 lbs each, {expected_total_weight} lbs total" in result

    def test_commodity_value_calculation(self):
        """Test that commodity total value scales with count."""
        commodity = Commodity(
            name="Valuable Commodity",
            description="Test",
            value=100,
            weight=0.5,
            maintype="Special",
            subtype="Commodity",
            count=7
        )
        # Total value should be 100 * 7 = 700
        expected_total_value = 100 * 7
        result = str(commodity)
        assert f"Value: 100 gold each, {expected_total_value} gold total" in result


class TestCommodityEdgeCases:
    """Test edge cases and boundary conditions for Commodity items."""

    def test_commodity_zero_count(self):
        """Test commodity with zero count (edge case)."""
        commodity = Commodity(
            name="Test",
            description="Test",
            value=10,
            weight=0.5,
            maintype="Special",
            subtype="Commodity",
            count=0
        )
        assert commodity.count == 0
        result = str(commodity)
        assert "Count: 0" in result

    def test_commodity_negative_count(self):
        """Test commodity with negative count (edge case - should be handled by game logic)."""
        commodity = Commodity(
            name="Test",
            description="Test",
            value=10,
            weight=0.5,
            maintype="Special",
            subtype="Commodity",
            count=-1
        )
        assert commodity.count == -1

    def test_commodity_fractional_weight(self):
        """Test commodity with fractional weight."""
        commodity = Commodity(
            name="Light Commodity",
            description="Test",
            value=5,
            weight=0.05,
            maintype="Special",
            subtype="Commodity",
            count=3
        )
        assert commodity.weight == 0.05
        result = str(commodity)
        assert "0.05 lbs each" in result
        # Use approximate comparison for floating point
        total_weight = 0.05 * 3
        assert f"{total_weight} lbs total" in result or "0.15" in result

    def test_crystals_large_stack(self):
        """Test Crystals with a very large stack count."""
        crystals = Crystals(count=999)
        assert crystals.count == 999
        result = str(crystals)
        assert "Count: 999" in result
        assert "Value: 10 gold each, 9990 gold total" in result
        assert "Weight: 0.1 lbs each, 99.9 lbs total" in result

    def test_commodity_zero_value(self):
        """Test commodity with zero value."""
        commodity = Commodity(
            name="Worthless Commodity",
            description="Test",
            value=0,
            weight=1.0,
            maintype="Special",
            subtype="Commodity"
        )
        assert commodity.value == 0
        result = str(commodity)
        assert "Value: 0 gold each, 0 gold total" in result

    def test_commodity_zero_weight(self):
        """Test commodity with zero weight."""
        commodity = Commodity(
            name="Weightless Commodity",
            description="Test",
            value=10,
            weight=0,
            maintype="Special",
            subtype="Commodity"
        )
        assert commodity.weight == 0
        result = str(commodity)
        assert "Weight: 0 lbs each, 0 lbs total" in result
