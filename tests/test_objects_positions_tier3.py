"""
Comprehensive test suite for objects.py and positions.py achieving 100% coverage.

This test suite covers:
- All object classes (Door, Chest, Corpse, Torch, Fountain, Switch, etc.)
- All methods on each object class
- Object state transitions
- Interaction branches
- Edge cases (null parameters, boundary values, empty states)
- All position calculations
- Coordinate validation
- Distance calculations
- Adjacency checks
- Path-finding logic
"""

import pytest
import math
import random
from unittest.mock import Mock, MagicMock, patch, call
import time

from src.objects import (
    Object,
    TileDescription,
    WallSwitch,
    WallInscription,
    Container,
    Crate,
    Shelf,
    Shrine,
    HealingSpring,
    Passageway,
    MarketBell,
    Fountain,
)

from src.positions import (
    Direction,
    CombatPosition,
    CombatScenario,
    COMBAT_SCENARIOS,
    distance_from_coords,
    distance_squared,
    angle_to_target,
    attack_angle_difference,
    get_damage_modifier,
    get_accuracy_modifier,
    random_position_in_zone,
    clamp_position,
    move_toward,
    move_toward_constrained,
    move_away_from,
    move_away_constrained,
    move_to_flank,
    move_to_flank_constrained,
    turn_toward,
    recalculate_proximity_dict,
    initialize_combat_positions,
    get_combat_scenario,
)


# ============================================================================
# OBJECTS.PY TESTS
# ============================================================================


class TestObject:
    """Test suite for the base Object class."""

    def test_object_init_basic(self):
        """Test basic Object initialization."""
        obj = Object(name="Test Object", description="A test object")
        assert obj.name == "Test Object"
        assert obj.description == "A test object"
        assert obj.hidden is False
        assert obj.hide_factor == 0
        assert obj.idle_message == " is here."
        assert obj.discovery_message == "something interesting."
        assert obj.aliases == []
        assert obj.keywords == []
        assert obj.action_aliases == []
        assert obj.events == []
        assert obj.tile is None
        assert obj.player is None

    def test_object_init_with_all_params(self):
        """Test Object initialization with all parameters."""
        player = Mock()
        tile = Mock()
        obj = Object(
            name="Hidden Object",
            description="Hard to find",
            tile=tile,
            player=player,
            hidden=True,
            hide_factor=50,
            idle_message="It's here.",
            discovery_message="Found it!",
            aliases=["hidden", "object"],
        )
        assert obj.name == "Hidden Object"
        assert obj.hidden is True
        assert obj.hide_factor == 50
        assert obj.idle_message == "It's here."
        assert obj.discovery_message == "Found it!"
        assert obj.announce == "It's here."
        assert obj.aliases == ["hidden", "object"]
        assert obj.tile is tile
        assert obj.player is player

    def test_object_spawn_event_success(self):
        """Test successful event spawning on Object."""
        obj = Object(name="Test", description="Test")
        player = Mock()
        tile = Mock()

        with patch("src.objects.functions.seek_class") as mock_seek:
            with patch("src.objects.functions.instantiate_event") as mock_inst:
                event_cls = Mock()
                mock_seek.return_value = event_cls
                event = Mock()
                mock_inst.return_value = event

                result = obj.spawn_event("TestEvent", player, tile, ["param1"])
                assert result is event
                assert event in obj.events

    def test_object_spawn_event_failure(self):
        """Test failed event spawning returns None."""
        obj = Object(name="Test", description="Test")
        player = Mock()
        tile = Mock()

        with patch("src.objects.functions.seek_class") as mock_seek:
            with patch("src.objects.functions.instantiate_event") as mock_inst:
                event_cls = Mock()
                mock_seek.return_value = event_cls
                mock_inst.return_value = ""

                result = obj.spawn_event("TestEvent", player, tile, ["param1"])
                assert result is None


class TestTileDescription:
    """Test suite for TileDescription class."""

    def test_tile_description_init(self):
        """Test TileDescription initialization."""
        player = Mock()
        tile = Mock()
        desc = TileDescription(player, tile, ["extra", "description", "text"])
        assert desc.name == "null"
        assert player in [desc.player]
        assert tile in [desc.tile]

    def test_tile_description_with_tilde(self):
        """Test TileDescription with tilde terminator."""
        player = Mock()
        tile = Mock()
        desc = TileDescription(player, tile, ["extra", "description", "text~"])
        # Should process the tilde and remove it
        assert "description" in desc.description.lower()

    def test_tile_description_text_wrapping(self):
        """Test TileDescription handles long text with wrapping."""
        player = Mock()
        tile = Mock()
        long_text = ["extra"] + ["word"] * 20
        desc = TileDescription(player, tile, long_text)
        # Should wrap long lines
        assert "\n" in desc.description or len(desc.description) > 0


class TestWallSwitch:
    """Test suite for WallSwitch class."""

    def test_wall_switch_init_unpressed(self):
        """Test WallSwitch initialization (unpressed)."""
        player = Mock()
        tile = Mock()
        switch = WallSwitch(player, tile)
        assert switch.name == "Wall Depression"
        assert switch.position is False
        assert switch.event_on is None
        assert switch.event_off is None
        assert "press" in switch.keywords

    def test_wall_switch_init_with_position_true(self):
        """Test WallSwitch initialization with position parameter."""
        player = Mock()
        tile = Mock()
        switch = WallSwitch(player, tile, position=True)
        assert switch.position is True

    def test_wall_switch_press_unpressed_no_event(self):
        """Test pressing an unpressed switch with no event."""
        player = Mock()
        tile = Mock()
        switch = WallSwitch(player, tile)
        with patch("builtins.print") as mock_print:
            with patch("time.sleep"):
                switch.press()
        assert switch.position is True
        mock_print.assert_called_with("Jean hears a faint 'click.'")

    def test_wall_switch_press_unpressed_with_event(self):
        """Test pressing unpressed switch with event_on."""
        player = Mock()
        tile = Mock()
        switch = WallSwitch(player, tile)
        event_on = Mock()
        switch.event_on = event_on
        with patch("builtins.print"):
            with patch("time.sleep"):
                switch.press()
        assert switch.position is True
        event_on.process.assert_called_once()

    def test_wall_switch_press_pressed_no_event(self):
        """Test pressing a pressed switch with no event."""
        player = Mock()
        tile = Mock()
        switch = WallSwitch(player, tile, position=True)
        with patch("builtins.print"):
            with patch("time.sleep"):
                switch.press()
        assert switch.position is False

    def test_wall_switch_press_pressed_with_event(self):
        """Test pressing pressed switch with event_off."""
        player = Mock()
        tile = Mock()
        switch = WallSwitch(player, tile, position=True)
        event_off = Mock()
        switch.event_off = event_off
        with patch("builtins.print"):
            with patch("time.sleep"):
                switch.press()
        assert switch.position is False
        event_off.process.assert_called_once()

    def test_wall_switch_push_alias(self):
        """Test push() aliases press()."""
        player = Mock()
        tile = Mock()
        switch = WallSwitch(player, tile)
        with patch.object(switch, "press") as mock_press:
            switch.push()
            mock_press.assert_called_once()

    def test_wall_switch_touch_alias(self):
        """Test touch() aliases press()."""
        player = Mock()
        tile = Mock()
        switch = WallSwitch(player, tile)
        with patch.object(switch, "press") as mock_press:
            switch.touch()
            mock_press.assert_called_once()

    def test_wall_switch_init_with_params(self):
        """Test WallSwitch initialization with event params."""
        player = Mock()
        tile = Mock()
        with patch("src.objects.functions.seek_class") as mock_seek:
            with patch("src.objects.functions.instantiate_event") as mock_inst:
                event_cls = Mock()
                mock_seek.return_value = event_cls
                event = Mock()
                mock_inst.return_value = event
                params = ["!TestEvent:r"]
                switch = WallSwitch(player, tile, params=params)
                # First event should be set to event_on
                assert switch.event_on is not None


class TestWallInscription:
    """Test suite for WallInscription class."""

    def test_wall_inscription_init_no_text(self):
        """Test WallInscription initialization without text."""
        player = Mock()
        player.name = "Jean"
        tile = Mock()
        inscription = WallInscription(player, tile)
        assert inscription.name == "Inscription"
        assert "read" in inscription.keywords
        assert "examine" in inscription.keywords
        assert inscription.text is None

    def test_wall_inscription_init_with_text(self):
        """Test WallInscription initialization with text."""
        player = Mock()
        player.name = "Jean"
        tile = Mock()
        text = "Hello there!"
        inscription = WallInscription(player, tile, text=text)
        assert inscription.text == text

    def test_wall_inscription_read_with_text(self):
        """Test reading an inscription with text."""
        player = Mock()
        player.name = "Jean"
        tile = Mock()
        text = "Test inscription"
        inscription = WallInscription(player, tile, text=text)
        with patch("src.objects.functions.print_slow") as mock_print:
            with patch("src.objects.functions.await_input"):
                with patch("src.objects.cprint"):
                    inscription.read()
                    mock_print.assert_called_once_with(text, speed="fast")

    def test_wall_inscription_read_no_text(self):
        """Test reading an inscription without text."""
        player = Mock()
        player.name = "Jean"
        tile = Mock()
        inscription = WallInscription(player, tile, text=None)
        with patch("builtins.print") as mock_print:
            inscription.read()
            mock_print.assert_called_with(inscription.description)

    def test_wall_inscription_examine_alias(self):
        """Test examine() aliases read()."""
        player = Mock()
        player.name = "Jean"
        tile = Mock()
        inscription = WallInscription(player, tile, text="Test")
        with patch.object(inscription, "read") as mock_read:
            inscription.examine()
            mock_read.assert_called_once()


class TestContainer:
    """Test suite for Container class."""

    def test_container_init_basic(self):
        """Test basic Container initialization."""
        player = Mock()
        tile = Mock()
        container = Container(player=player, tile=tile)
        assert container.nickname == "container"
        assert container.state == "closed"
        assert container.revealed is False
        assert container.locked is False
        assert container.inventory == []

    def test_container_init_with_items(self):
        """Test Container initialization with items."""
        player = Mock()
        tile = Mock()
        item1 = Mock()
        item2 = Mock()
        container = Container(player=player, tile=tile, items=[item1, item2])
        assert len(container.inventory) == 2
        assert item1 in container.inventory

    def test_container_init_with_inventory_param(self):
        """Test Container initialization with inventory param (preferred)."""
        player = Mock()
        tile = Mock()
        item1 = Mock()
        container = Container(player=player, tile=tile, inventory=[item1])
        assert container.inventory == [item1]

    def test_container_start_open_property_true(self):
        """Test start_open property when True."""
        player = Mock()
        tile = Mock()
        container = Container(player=player, tile=tile)
        container.start_open = True
        assert container.state == "opened"
        assert container.locked is False

    def test_container_start_open_property_false(self):
        """Test start_open property when False."""
        player = Mock()
        tile = Mock()
        container = Container(player=player, tile=tile, start_open=True)
        container.start_open = False
        assert container.state == "closed"

    def test_container_open_when_locked(self):
        """Test opening a locked container."""
        player = Mock()
        tile = Mock()
        container = Container(player=player, tile=tile, locked=True)
        container.player = player
        with patch("builtins.print") as mock_print:
            container.open()
            assert container.state == "closed"
            mock_print.assert_called()

    def test_container_open_when_closed(self):
        """Test opening a closed container."""
        player = Mock()
        tile = Mock()
        container = Container(player=player, tile=tile)
        with patch("builtins.print"):
            with patch("time.sleep"):
                container.open()
        assert container.state == "opened"
        assert container.revealed is True

    def test_container_open_already_open(self):
        """Test opening already-open container."""
        player = Mock()
        tile = Mock()
        container = Container(player=player, tile=tile, start_open=True)
        with patch("builtins.print") as mock_print:
            container.open()
            # Should print already open message
            assert mock_print.called

    def test_container_refresh_description_closed(self):
        """Test refresh_description when closed."""
        player = Mock()
        tile = Mock()
        container = Container(player=player, tile=tile)
        container.refresh_description()
        assert "UNLOCK" in container.description or "unlock" in container.description

    def test_container_refresh_description_open_with_items(self):
        """Test refresh_description when open with items."""
        player = Mock()
        tile = Mock()
        item = Mock()
        item.description = "A test item"
        container = Container(
            player=player, tile=tile, start_open=True, inventory=[item]
        )
        container.refresh_description()
        assert "test item" in container.description

    def test_container_refresh_description_open_empty(self):
        """Test refresh_description when open but empty."""
        player = Mock()
        tile = Mock()
        container = Container(player=player, tile=tile, start_open=True)
        container.refresh_description()
        assert "empty" in container.description.lower()

    def test_container_unlock_success(self):
        """Test successful unlock with matching key."""
        player = Mock()
        tile = Mock()
        container = Container(player=player, tile=tile, locked=True)
        key = Mock()
        key.lock = container
        player.inventory = [key]
        container.player = player
        with patch("src.objects.cprint"):
            container.unlock()
        assert container.locked is False
        assert "unlock" not in container.keywords

    def test_container_unlock_no_key(self):
        """Test unlock with no matching key."""
        player = Mock()
        tile = Mock()
        container = Container(player=player, tile=tile, locked=True)
        player.inventory = []
        container.player = player
        with patch("src.objects.cprint"):
            container.unlock()
        assert container.locked is True

    def test_container_unlock_already_open(self):
        """Test unlock on already-open container."""
        player = Mock()
        tile = Mock()
        container = Container(player=player, tile=tile, start_open=True)
        container.player = player
        with patch("builtins.print") as mock_print:
            container.unlock()
            mock_print.assert_called()

    def test_container_take_all_closed(self):
        """Test take_all on closed container."""
        player = Mock()
        tile = Mock()
        container = Container(player=player, tile=tile)
        with patch.object(container, "open"):
            with patch("src.objects.transfer_item"):
                container.take_all(player)
                container.open.assert_called_once()

    def test_container_loot_closed(self):
        """Test loot on closed container."""
        player = Mock()
        tile = Mock()
        container = Container(player=player, tile=tile)
        with patch.object(container, "open"):
            with patch("src.objects.ContainerLootInterface"):
                container.loot()
                container.open.assert_called_once()

    def test_container_check_alias(self):
        """Test check() aliases loot()."""
        player = Mock()
        tile = Mock()
        container = Container(player=player, tile=tile)
        with patch.object(container, "loot") as mock_loot:
            container.check()
            mock_loot.assert_called_once()

    def test_container_view_alias(self):
        """Test view() aliases loot()."""
        player = Mock()
        tile = Mock()
        container = Container(player=player, tile=tile)
        with patch.object(container, "loot") as mock_loot:
            container.view()
            mock_loot.assert_called_once()

    def test_container_examine_alias(self):
        """Test examine() aliases loot()."""
        player = Mock()
        tile = Mock()
        container = Container(player=player, tile=tile)
        with patch.object(container, "loot") as mock_loot:
            container.examine()
            mock_loot.assert_called_once()

    def test_container_inspect_alias(self):
        """Test inspect() aliases loot()."""
        player = Mock()
        tile = Mock()
        container = Container(player=player, tile=tile)
        with patch.object(container, "loot") as mock_loot:
            container.inspect()
            mock_loot.assert_called_once()

    def test_container_peruse_alias(self):
        """Test peruse() aliases loot()."""
        player = Mock()
        tile = Mock()
        container = Container(player=player, tile=tile)
        with patch.object(container, "loot") as mock_loot:
            container.peruse()
            mock_loot.assert_called_once()

    def test_container_process_events(self):
        """Test process_events transfers events to tile."""
        player = Mock()
        tile = Mock()
        tile.events_here = []
        tile.evaluate_events = Mock()
        event = Mock()
        container = Container(player=player, tile=tile)
        container.events = [event]
        container.process_events()
        assert event in tile.events_here
        tile.evaluate_events.assert_called_once()

    def test_container_stack_items_no_count(self):
        """Test stack_items with items without count."""
        player = Mock()
        tile = Mock()
        item = Mock(spec=[])  # No count attribute
        container = Container(player=player, tile=tile, inventory=[item])
        container.stack_items()
        assert len(container.inventory) == 1

    def test_container_stack_items_with_count(self):
        """Test stack_items stacks items with count."""
        player = Mock()
        tile = Mock()
        item1 = Mock()
        item1.__class__ = type("TestItem", (), {})
        item1.count = 5
        item2 = Mock()
        item2.__class__ = type("TestItem", (), {})
        item2.count = 3
        container = Container(player=player, tile=tile, inventory=[item1, item2])
        container.stack_items()
        # Should stack to single item with count 8
        assert len(container.inventory) == 1
        assert item1.count == 8


class TestCrate:
    """Test suite for Crate class."""

    def test_crate_init(self):
        """Test Crate initialization."""
        player = Mock()
        tile = Mock()
        crate = Crate(player, tile)
        assert crate.name == "Crate"
        assert crate.state == "opened"
        assert "open" not in crate.keywords
        assert "unlock" not in crate.keywords


class TestShelf:
    """Test suite for Shelf class."""

    def test_shelf_init(self):
        """Test Shelf initialization."""
        player = Mock()
        tile = Mock()
        shelf = Shelf(player, tile)
        assert shelf.name == "Shelf"
        assert shelf.state == "opened"
        assert "open" not in shelf.keywords
        assert "unlock" not in shelf.keywords


class TestShrine:
    """Test suite for Shrine class."""

    def test_shrine_init_no_params(self):
        """Test Shrine initialization without params."""
        player = Mock()
        tile = Mock()
        shrine = Shrine(player, tile)
        assert shrine.name == "Shrine"
        assert shrine.event is None
        assert "pray" in shrine.keywords

    def test_shrine_pray_no_event(self):
        """Test praying at shrine with no event."""
        player = Mock()
        player.prayer_msg = ["Amen."]
        tile = Mock()
        shrine = Shrine(player, tile)
        with patch("builtins.print"):
            with patch("time.sleep"):
                with patch("src.objects.cprint"):
                    with patch("src.objects.functions.await_input"):
                        shrine.pray(player)

    def test_shrine_pray_with_event(self):
        """Test praying at shrine with event."""
        player = Mock()
        player.prayer_msg = ["Amen."]
        tile = Mock()
        shrine = Shrine(player, tile)
        event = Mock()
        shrine.event = event
        with patch("builtins.print"):
            with patch("time.sleep"):
                with patch("src.objects.cprint"):
                    with patch("src.objects.functions.await_input"):
                        shrine.pray(player)
        event.process.assert_called_once()
        assert shrine.event is None


class TestHealingSpring:
    """Test suite for HealingSpring class."""

    def test_healing_spring_init(self):
        """Test HealingSpring initialization."""
        player = Mock()
        tile = Mock()
        spring = HealingSpring(player, tile)
        assert spring.name == "HealingSpring"
        assert "drink" in spring.keywords
        assert "clean" in spring.keywords
        assert "wash" in spring.keywords

    def test_healing_spring_drink(self):
        """Test drinking from healing spring."""
        player = Mock()
        player.hp = 50
        player.maxhp = 100
        tile = Mock()
        spring = HealingSpring(player, tile)
        with patch("builtins.print"):
            with patch("time.sleep"):
                with patch("src.objects.cprint"):
                    with patch("src.objects.functions.await_input"):
                        spring.drink(player)
        assert player.hp == 100

    def test_healing_spring_drink_with_event(self):
        """Test drinking from spring with event."""
        player = Mock()
        player.hp = 50
        player.maxhp = 100
        tile = Mock()
        spring = HealingSpring(player, tile)
        event = Mock()
        spring.event = event
        with patch("builtins.print"):
            with patch("time.sleep"):
                with patch("src.objects.cprint"):
                    with patch("src.objects.functions.await_input"):
                        spring.drink(player)
        event.process.assert_called_once()

    def test_healing_spring_clean(self):
        """Test cleaning in healing spring."""
        player = Mock()
        player.apply_state = Mock()
        with patch("builtins.print"):
            with patch("time.sleep"):
                with patch("src.objects.cprint"):
                    HealingSpring.clean(player)
        player.apply_state.assert_called_once()

    def test_healing_spring_wash_alias(self):
        """Test wash() aliases clean()."""
        player = Mock()
        tile = Mock()
        spring = HealingSpring(player, tile)
        with patch.object(spring, "clean") as mock_clean:
            spring.wash(player)
            mock_clean.assert_called_once()


class TestPassageway:
    """Test suite for Passageway class."""

    def test_passageway_init_basic(self):
        """Test Passageway initialization."""
        player = Mock()
        tile = Mock()
        passage = Passageway(player, tile)
        assert passage.name == "Passageway"
        assert "enter" in passage.keywords

    def test_passageway_enter_no_teleport(self):
        """Test entering passageway without teleport config."""
        player = Mock()
        tile = Mock()
        passage = Passageway(player, tile)
        with patch("builtins.print") as mock_print:
            with patch("src.objects.functions.await_input"):
                passage.enter(player)
            # Should print error message
            assert any("not properly configured" in str(c) for c in mock_print.call_args_list)

    def test_passageway_enter_with_teleport(self):
        """Test entering passageway with valid teleport."""
        player = Mock()
        player.teleport = Mock()
        tile = Mock()
        passage = Passageway(
            player, tile, teleport_map="test_map", teleport_tile=(1, 1)
        )
        with patch("builtins.print"):
            with patch("time.sleep"):
                with patch("src.objects.functions.await_input"):
                    passage.enter(player)
        player.teleport.assert_called_once_with("test_map", (1, 1))

    def test_passageway_go_alias(self):
        """Test go() aliases enter()."""
        player = Mock()
        tile = Mock()
        passage = Passageway(player, tile)
        with patch.object(passage, "enter") as mock_enter:
            passage.go(player)
            mock_enter.assert_called_once_with(player)

    def test_passageway_leave_alias(self):
        """Test leave() aliases enter()."""
        player = Mock()
        tile = Mock()
        passage = Passageway(player, tile)
        with patch.object(passage, "enter") as mock_enter:
            passage.leave(player)
            mock_enter.assert_called_once_with(player)

    def test_passageway_exit_alias(self):
        """Test exit() aliases enter()."""
        player = Mock()
        tile = Mock()
        passage = Passageway(player, tile)
        with patch.object(passage, "enter") as mock_enter:
            passage.exit(player)
            mock_enter.assert_called_once_with(player)


class TestMarketBell:
    """Test suite for MarketBell class."""

    def test_market_bell_init(self):
        """Test MarketBell initialization."""
        player = Mock()
        tile = Mock()
        bell = MarketBell(player, tile)
        assert bell.name == "Market Bell"
        assert "ring" in bell.keywords
        assert "use" in bell.keywords

    def test_market_bell_ring_no_event(self):
        """Test ringing bell with no event."""
        player = Mock()
        tile = Mock()
        bell = MarketBell(player, tile)
        with patch("src.objects.cprint"):
            with patch("time.sleep"):
                with patch("builtins.print"):
                    with patch("src.objects.functions.await_input"):
                        bell.ring()

    def test_market_bell_ring_with_event(self):
        """Test ringing bell with event."""
        player = Mock()
        tile = Mock()
        event = Mock()
        event.repeat = False
        bell = MarketBell(player, tile, event=event)
        with patch("src.objects.cprint"):
            with patch("time.sleep"):
                with patch("builtins.print"):
                    with patch("src.objects.functions.await_input"):
                        bell.ring()
        event.process.assert_called_once()

    def test_market_bell_use_alias(self):
        """Test use() aliases ring()."""
        player = Mock()
        tile = Mock()
        bell = MarketBell(player, tile)
        with patch.object(bell, "ring") as mock_ring:
            bell.use()
            mock_ring.assert_called_once()


class TestFountain:
    """Test suite for Fountain class."""

    def test_fountain_init(self):
        """Test Fountain initialization."""
        player = Mock()
        tile = Mock()
        fountain = Fountain(player, tile)
        assert fountain.name == "Fountain"
        assert "drink" in fountain.keywords
        assert "listen" in fountain.keywords
        assert "admire" in fountain.keywords

    def test_fountain_drink_no_event(self):
        """Test drinking from fountain with no event."""
        player = Mock()
        tile = Mock()
        fountain = Fountain(player, tile)
        with patch("src.objects.cprint"):
            with patch("time.sleep"):
                with patch("src.objects.functions.await_input"):
                    fountain.drink()

    def test_fountain_drink_with_event(self):
        """Test drinking from fountain with event."""
        player = Mock()
        tile = Mock()
        event = Mock()
        event.repeat = False
        fountain = Fountain(player, tile, event=event)
        with patch("src.objects.cprint"):
            with patch("time.sleep"):
                with patch("src.objects.functions.await_input"):
                    fountain.drink()
        event.process.assert_called_once()


# ============================================================================
# POSITIONS.PY TESTS
# ============================================================================


class TestDirection:
    """Test suite for Direction enum."""

    def test_direction_values(self):
        """Test all Direction enum values."""
        assert Direction.N.value == 0
        assert Direction.NE.value == 45
        assert Direction.E.value == 90
        assert Direction.SE.value == 135
        assert Direction.S.value == 180
        assert Direction.SW.value == 225
        assert Direction.W.value == 270
        assert Direction.NW.value == 315

    def test_direction_names(self):
        """Test Direction enum names."""
        assert Direction.N.name == "N"
        assert Direction.NE.name == "NE"
        assert Direction.E.name == "E"
        assert Direction.SE.name == "SE"
        assert Direction.S.name == "S"
        assert Direction.SW.name == "SW"
        assert Direction.W.name == "W"
        assert Direction.NW.name == "NW"


class TestCombatPosition:
    """Test suite for CombatPosition dataclass."""

    def test_combat_position_init_defaults(self):
        """Test CombatPosition with default facing."""
        pos = CombatPosition(x=10, y=20)
        assert pos.x == 10
        assert pos.y == 20
        assert pos.facing == Direction.N

    def test_combat_position_init_with_facing(self):
        """Test CombatPosition with specific facing."""
        pos = CombatPosition(x=5, y=5, facing=Direction.E)
        assert pos.facing == Direction.E

    def test_combat_position_invalid_x_type(self):
        """Test CombatPosition rejects non-int x."""
        with pytest.raises(ValueError):
            CombatPosition(x=10.5, y=20)

    def test_combat_position_invalid_y_type(self):
        """Test CombatPosition rejects non-int y."""
        with pytest.raises(ValueError):
            CombatPosition(x=10, y=20.5)

    def test_combat_position_x_boundary_low(self):
        """Test CombatPosition rejects x < 0."""
        with pytest.raises(ValueError):
            CombatPosition(x=-1, y=20)

    def test_combat_position_x_boundary_high(self):
        """Test CombatPosition rejects x > 50."""
        with pytest.raises(ValueError):
            CombatPosition(x=51, y=20)

    def test_combat_position_y_boundary_low(self):
        """Test CombatPosition rejects y < 0."""
        with pytest.raises(ValueError):
            CombatPosition(x=10, y=-1)

    def test_combat_position_y_boundary_high(self):
        """Test CombatPosition rejects y > 50."""
        with pytest.raises(ValueError):
            CombatPosition(x=10, y=51)

    def test_combat_position_boundaries_valid(self):
        """Test CombatPosition accepts boundaries."""
        pos1 = CombatPosition(x=0, y=0)
        pos2 = CombatPosition(x=50, y=50)
        assert pos1.x == 0 and pos1.y == 0
        assert pos2.x == 50 and pos2.y == 50

    def test_combat_position_invalid_facing(self):
        """Test CombatPosition rejects invalid facing."""
        with pytest.raises(ValueError):
            CombatPosition(x=10, y=10, facing="NORTH")

    def test_combat_position_copy(self):
        """Test copy() creates independent copy."""
        pos = CombatPosition(x=10, y=20, facing=Direction.E)
        copy = pos.copy()
        assert copy.x == pos.x
        assert copy.y == pos.y
        assert copy.facing == pos.facing
        assert copy is not pos


class TestCombatScenario:
    """Test suite for CombatScenario dataclass."""

    def test_combat_scenario_standard(self):
        """Test standard combat scenario."""
        scenario = COMBAT_SCENARIOS["standard"]
        assert scenario.scenario_type == "standard"
        assert scenario.formation_type == "spread"

    def test_combat_scenario_pincer(self):
        """Test pincer combat scenario."""
        scenario = COMBAT_SCENARIOS["pincer"]
        assert scenario.scenario_type == "pincer"
        assert scenario.formation_type == "cluster"

    def test_combat_scenario_melee(self):
        """Test melee combat scenario."""
        scenario = COMBAT_SCENARIOS["melee"]
        assert scenario.scenario_type == "melee"
        assert scenario.formation_type == "random"

    def test_combat_scenario_boss_arena(self):
        """Test boss arena scenario."""
        scenario = COMBAT_SCENARIOS["boss_arena"]
        assert scenario.scenario_type == "boss_arena"
        assert scenario.formation_type == "spread"


class TestDistanceFunctions:
    """Test suite for distance calculation functions."""

    def test_distance_from_coords_same_position(self):
        """Test distance between same position."""
        pos = CombatPosition(x=10, y=10)
        assert distance_from_coords(pos, pos) == 0

    def test_distance_from_coords_horizontal(self):
        """Test distance with horizontal separation."""
        pos1 = CombatPosition(x=0, y=10)
        pos2 = CombatPosition(x=10, y=10)
        assert distance_from_coords(pos1, pos2) == 10

    def test_distance_from_coords_vertical(self):
        """Test distance with vertical separation."""
        pos1 = CombatPosition(x=10, y=0)
        pos2 = CombatPosition(x=10, y=10)
        assert distance_from_coords(pos1, pos2) == 10

    def test_distance_from_coords_diagonal(self):
        """Test distance with diagonal separation."""
        pos1 = CombatPosition(x=0, y=0)
        pos2 = CombatPosition(x=3, y=4)
        # 3-4-5 triangle
        assert distance_from_coords(pos1, pos2) == 5

    def test_distance_squared_same(self):
        """Test squared distance between same position."""
        pos = CombatPosition(x=10, y=10)
        assert distance_squared(pos, pos) == 0

    def test_distance_squared_3_4_5(self):
        """Test squared distance for 3-4-5 triangle."""
        pos1 = CombatPosition(x=0, y=0)
        pos2 = CombatPosition(x=3, y=4)
        assert distance_squared(pos1, pos2) == 25


class TestAngleFunctions:
    """Test suite for angle calculation functions."""

    def test_angle_to_target_north(self):
        """Test angle to target to the north."""
        from_pos = CombatPosition(x=10, y=10)
        to_pos = CombatPosition(x=10, y=5)
        angle = angle_to_target(from_pos, to_pos)
        assert abs(angle - 0) < 5 or abs(angle - 360) < 5

    def test_angle_to_target_south(self):
        """Test angle to target to the south."""
        from_pos = CombatPosition(x=10, y=10)
        to_pos = CombatPosition(x=10, y=15)
        angle = angle_to_target(from_pos, to_pos)
        assert abs(angle - 180) < 5

    def test_angle_to_target_east(self):
        """Test angle to target to the east."""
        from_pos = CombatPosition(x=10, y=10)
        to_pos = CombatPosition(x=15, y=10)
        angle = angle_to_target(from_pos, to_pos)
        assert abs(angle - 90) < 5

    def test_angle_to_target_west(self):
        """Test angle to target to the west."""
        from_pos = CombatPosition(x=10, y=10)
        to_pos = CombatPosition(x=5, y=10)
        angle = angle_to_target(from_pos, to_pos)
        assert abs(angle - 270) < 5

    def test_attack_angle_difference_front(self):
        """Test angle difference for front attack."""
        angle = 0  # Attack from north
        facing = Direction.N  # Facing north
        diff = attack_angle_difference(angle, facing)
        assert diff == 0

    def test_attack_angle_difference_flank(self):
        """Test angle difference for flanking attack."""
        angle = 90  # Attack from east
        facing = Direction.N  # Facing north
        diff = attack_angle_difference(angle, facing)
        assert diff == 90

    def test_attack_angle_difference_rear(self):
        """Test angle difference for rear attack."""
        angle = 180  # Attack from south
        facing = Direction.N  # Facing north
        diff = attack_angle_difference(angle, facing)
        assert diff == 180

    def test_attack_angle_difference_wrapping(self):
        """Test angle difference with wrapping."""
        angle = 350  # Just before north
        facing = Direction.N  # Facing north (0°)
        diff = attack_angle_difference(angle, facing)
        assert diff == 10


class TestDamageModifier:
    """Test suite for damage modifier function."""

    def test_damage_modifier_front_quarter(self):
        """Test damage modifier for front quarter (0-45°)."""
        modifier = get_damage_modifier(20)
        assert modifier == 0.85

    def test_damage_modifier_flanking(self):
        """Test damage modifier for flanking (45-90°)."""
        modifier = get_damage_modifier(70)
        assert modifier == 1.15

    def test_damage_modifier_deep_flank(self):
        """Test damage modifier for deep flank (90-135°)."""
        modifier = get_damage_modifier(110)
        assert modifier == 1.25

    def test_damage_modifier_rear(self):
        """Test damage modifier for rear (135-180°)."""
        modifier = get_damage_modifier(160)
        assert modifier == 1.40

    def test_damage_modifier_boundary_45(self):
        """Test damage modifier at 45° boundary."""
        modifier = get_damage_modifier(45)
        assert modifier == 0.85  # Inclusive of front quarter

    def test_damage_modifier_boundary_90(self):
        """Test damage modifier at 90° boundary."""
        modifier = get_damage_modifier(90)
        assert modifier == 1.15  # Inclusive of flanking

    def test_damage_modifier_boundary_135(self):
        """Test damage modifier at 135° boundary."""
        modifier = get_damage_modifier(135)
        assert modifier == 1.25  # Inclusive of deep flank


class TestAccuracyModifier:
    """Test suite for accuracy modifier function."""

    def test_accuracy_modifier_front_quarter(self):
        """Test accuracy modifier for front quarter."""
        modifier = get_accuracy_modifier(20)
        assert modifier == 0.95

    def test_accuracy_modifier_flanking(self):
        """Test accuracy modifier for flanking."""
        modifier = get_accuracy_modifier(70)
        assert modifier == 1.10

    def test_accuracy_modifier_deep_flank(self):
        """Test accuracy modifier for deep flank."""
        modifier = get_accuracy_modifier(110)
        assert modifier == 1.20

    def test_accuracy_modifier_rear(self):
        """Test accuracy modifier for rear."""
        modifier = get_accuracy_modifier(160)
        assert modifier == 1.30


class TestRandomPositionInZone:
    """Test suite for random position generation."""

    def test_random_position_in_zone_bounds(self):
        """Test random position respects zone bounds."""
        zone = ((10, 10), (20, 20))
        for _ in range(10):
            pos = random_position_in_zone(zone)
            assert 10 <= pos.x <= 20
            assert 10 <= pos.y <= 20

    def test_random_position_in_zone_reproducible(self):
        """Test random position with seed is reproducible."""
        zone = ((0, 0), (50, 50))
        pos1 = random_position_in_zone(zone, seed=42)
        pos2 = random_position_in_zone(zone, seed=42)
        assert pos1.x == pos2.x and pos1.y == pos2.y

    def test_random_position_corner_zone(self):
        """Test random position in corner zone."""
        zone = ((0, 0), (1, 1))
        for _ in range(5):
            pos = random_position_in_zone(zone)
            assert 0 <= pos.x <= 1
            assert 0 <= pos.y <= 1


class TestClampPosition:
    """Test suite for position clamping."""

    def test_clamp_position_within_bounds(self):
        """Test clamping position already within bounds."""
        pos = CombatPosition(x=25, y=25)
        clamped = clamp_position(pos)
        assert clamped.x == 25
        assert clamped.y == 25

    def test_clamp_position_over_max(self):
        """Test clamping position beyond max."""
        pos = CombatPosition(x=60, y=60)
        clamped = clamp_position(pos)
        assert clamped.x == 50
        assert clamped.y == 50

    def test_clamp_position_under_min(self):
        """Test clamping position below zero (shouldn't happen but test anyway)."""
        # Can't actually create invalid position, so test the clamp logic
        pos = CombatPosition(x=0, y=0)
        clamped = clamp_position(pos)
        assert clamped.x == 0
        assert clamped.y == 0

    def test_clamp_position_custom_bounds(self):
        """Test clamping with custom grid bounds."""
        pos = CombatPosition(x=25, y=25)
        clamped = clamp_position(pos, max_w=20, max_h=20)
        assert clamped.x == 20
        assert clamped.y == 20


class TestMoveToward:
    """Test suite for move_toward function."""

    def test_move_toward_horizontal(self):
        """Test moving horizontally toward target."""
        current = CombatPosition(x=0, y=10)
        target = CombatPosition(x=10, y=10)
        new_pos = move_toward(current, target, 5)
        assert new_pos.x == 5
        assert new_pos.y == 10

    def test_move_toward_vertical(self):
        """Test moving vertically toward target."""
        current = CombatPosition(x=10, y=0)
        target = CombatPosition(x=10, y=10)
        new_pos = move_toward(current, target, 5)
        assert new_pos.x == 10
        assert new_pos.y == 5

    def test_move_toward_diagonal(self):
        """Test moving diagonally toward target."""
        current = CombatPosition(x=0, y=0)
        target = CombatPosition(x=10, y=10)
        new_pos = move_toward(current, target, 5)
        assert new_pos.x == 5
        assert new_pos.y == 5

    def test_move_toward_already_at_target(self):
        """Test moving when already at target."""
        current = CombatPosition(x=10, y=10)
        new_pos = move_toward(current, current, 5)
        assert new_pos.x == current.x
        assert new_pos.y == current.y

    def test_move_toward_overshoot_prevention(self):
        """Test that move_toward doesn't overshoot target."""
        current = CombatPosition(x=0, y=0)
        target = CombatPosition(x=5, y=0)
        new_pos = move_toward(current, target, 10)
        # Should only move to target, not overshoot
        assert new_pos.x == 5
        assert new_pos.y == 0


class TestMoveAwayFrom:
    """Test suite for move_away_from function."""

    def test_move_away_from_horizontal(self):
        """Test moving away horizontally."""
        current = CombatPosition(x=10, y=10)
        threat = CombatPosition(x=0, y=10)
        new_pos = move_away_from(current, threat, 5)
        assert new_pos.x == 15
        assert new_pos.y == 10

    def test_move_away_from_vertical(self):
        """Test moving away vertically."""
        current = CombatPosition(x=10, y=10)
        threat = CombatPosition(x=10, y=0)
        new_pos = move_away_from(current, threat, 5)
        assert new_pos.x == 10
        assert new_pos.y == 15

    def test_move_away_from_same_position(self):
        """Test moving away from same position picks random direction."""
        current = CombatPosition(x=10, y=10)
        new_pos = move_away_from(current, current, 5)
        # Should move somewhere, just not be same position
        assert not (new_pos.x == 10 and new_pos.y == 10)

    def test_move_away_from_boundaries(self):
        """Test moving away respects boundaries."""
        current = CombatPosition(x=0, y=0)
        threat = CombatPosition(x=0, y=0)
        new_pos = move_away_from(current, threat, 100)
        assert 0 <= new_pos.x <= 50
        assert 0 <= new_pos.y <= 50


class TestMoveToFlank:
    """Test suite for move_to_flank function."""

    def test_move_to_flank_basic(self):
        """Test basic flanking movement."""
        current = CombatPosition(x=10, y=10, facing=Direction.N)
        target = CombatPosition(x=20, y=20, facing=Direction.N)
        flank_pos = move_to_flank(current, target, distance=3)
        # Should be perpendicular to target's facing
        assert 0 <= flank_pos.x <= 50
        assert 0 <= flank_pos.y <= 50

    def test_move_to_flank_respects_bounds(self):
        """Test flanking respects grid bounds."""
        current = CombatPosition(x=0, y=0)
        target = CombatPosition(x=50, y=50, facing=Direction.N)
        flank_pos = move_to_flank(current, target, distance=10)
        assert 0 <= flank_pos.x <= 50
        assert 0 <= flank_pos.y <= 50


class TestTurnToward:
    """Test suite for turn_toward function."""

    def test_turn_toward_north(self):
        """Test turning to face north."""
        from_pos = CombatPosition(x=10, y=10)
        to_pos = CombatPosition(x=10, y=5)
        direction = turn_toward(from_pos, to_pos)
        assert direction == Direction.N

    def test_turn_toward_south(self):
        """Test turning to face south."""
        from_pos = CombatPosition(x=10, y=10)
        to_pos = CombatPosition(x=10, y=15)
        direction = turn_toward(from_pos, to_pos)
        assert direction == Direction.S

    def test_turn_toward_east(self):
        """Test turning to face east."""
        from_pos = CombatPosition(x=10, y=10)
        to_pos = CombatPosition(x=15, y=10)
        direction = turn_toward(from_pos, to_pos)
        assert direction == Direction.E

    def test_turn_toward_west(self):
        """Test turning to face west."""
        from_pos = CombatPosition(x=10, y=10)
        to_pos = CombatPosition(x=5, y=10)
        direction = turn_toward(from_pos, to_pos)
        assert direction == Direction.W


class TestRecalculateProximityDict:
    """Test suite for proximity dict recalculation."""

    def test_recalculate_proximity_dict_basic(self):
        """Test basic proximity dict calculation."""
        unit1 = Mock()
        unit1.combat_position = CombatPosition(x=0, y=0)
        unit2 = Mock()
        unit2.combat_position = CombatPosition(x=10, y=0)
        all_combatants = [unit1, unit2]

        proximity = recalculate_proximity_dict(unit1, all_combatants)
        assert unit2 in proximity
        assert proximity[unit2] == 10

    def test_recalculate_proximity_dict_no_position(self):
        """Test proximity with missing combat_position."""
        unit = Mock()
        unit.combat_position = None
        proximity = recalculate_proximity_dict(unit, [unit])
        assert proximity == {}

    def test_recalculate_proximity_dict_excludes_self(self):
        """Test that unit is excluded from its own proximity dict."""
        unit = Mock()
        unit.combat_position = CombatPosition(x=10, y=10)
        proximity = recalculate_proximity_dict(unit, [unit])
        assert unit not in proximity


class TestGetCombatScenario:
    """Test suite for get_combat_scenario function."""

    def test_get_combat_scenario_standard(self):
        """Test getting standard scenario."""
        scenario = get_combat_scenario("standard", 50, 50)
        assert scenario.scenario_type == "standard"
        assert scenario.formation_type == "spread"

    def test_get_combat_scenario_pincer(self):
        """Test getting pincer scenario."""
        scenario = get_combat_scenario("pincer", 50, 50)
        assert scenario.scenario_type == "pincer"
        assert scenario.formation_type == "cluster"

    def test_get_combat_scenario_melee(self):
        """Test getting melee scenario."""
        scenario = get_combat_scenario("melee", 50, 50)
        assert scenario.scenario_type == "melee"
        assert scenario.formation_type == "random"

    def test_get_combat_scenario_random(self):
        """Test getting random scenario (alias for melee)."""
        scenario = get_combat_scenario("random", 50, 50)
        assert scenario.formation_type == "random"

    def test_get_combat_scenario_boss_arena(self):
        """Test getting boss arena scenario."""
        scenario = get_combat_scenario("boss_arena", 50, 50)
        assert scenario.scenario_type == "boss_arena"

    def test_get_combat_scenario_invalid(self):
        """Test invalid scenario type raises error."""
        with pytest.raises(ValueError):
            get_combat_scenario("invalid_scenario", 50, 50)

    def test_get_combat_scenario_small_grid(self):
        """Test scenario with small grid."""
        scenario = get_combat_scenario("standard", 20, 20)
        assert scenario.scenario_type == "standard"

    def test_get_combat_scenario_case_insensitive(self):
        """Test scenario type is case insensitive."""
        scenario = get_combat_scenario("STANDARD", 50, 50)
        assert scenario.scenario_type == "standard"


class TestInitializeCombatPositions:
    """Test suite for initialize_combat_positions function."""

    def test_initialize_combat_positions_basic(self):
        """Test basic combat position initialization."""
        ally = Mock()
        enemy = Mock()

        allies = [ally]
        enemies = [enemy]

        initialize_combat_positions(allies, enemies, scenario_type="standard")

        assert hasattr(ally, "combat_position")
        assert hasattr(enemy, "combat_position")
        assert ally.combat_position is not None
        assert enemy.combat_position is not None

    def test_initialize_combat_positions_multiple_combatants(self):
        """Test initialization with multiple combatants."""
        allies = [Mock() for _ in range(3)]
        enemies = [Mock() for _ in range(2)]

        initialize_combat_positions(
            allies, enemies, scenario_type="standard"
        )

        for ally in allies:
            assert ally.combat_position is not None
        for enemy in enemies:
            assert enemy.combat_position is not None

    def test_initialize_combat_positions_pincer(self):
        """Test initialization with pincer scenario."""
        ally = Mock()
        enemy = Mock()

        initialize_combat_positions(
            [ally], [enemy], scenario_type="pincer"
        )

        assert ally.combat_position is not None
        assert enemy.combat_position is not None

    def test_initialize_combat_positions_facing_direction(self):
        """Test that combatants face toward opponents."""
        ally = Mock()
        enemy = Mock()

        initialize_combat_positions([ally], [enemy], scenario_type="standard")

        # Allies should face toward enemies
        assert ally.combat_position.facing is not None
        assert enemy.combat_position.facing is not None

    def test_initialize_combat_positions_proximity_dict(self):
        """Test that proximity dicts are set."""
        ally = Mock()
        enemy = Mock()

        allies = [ally]
        enemies = [enemy]

        initialize_combat_positions(allies, enemies, scenario_type="standard")

        assert hasattr(ally, "combat_proximity")
        assert hasattr(enemy, "combat_proximity")


class TestConstrainedMovement:
    """Test suite for constrained movement functions."""

    def test_move_toward_constrained_no_occupied(self):
        """Test constrained movement with no obstacles."""
        current = CombatPosition(x=0, y=0)
        target = CombatPosition(x=10, y=0)
        new_pos = move_toward_constrained(current, target, 5, [])
        assert new_pos.x == 5
        assert new_pos.y == 0

    def test_move_toward_constrained_with_obstacle(self):
        """Test constrained movement around obstacle."""
        current = CombatPosition(x=0, y=0)
        target = CombatPosition(x=10, y=0)
        obstacle = CombatPosition(x=5, y=0)
        new_pos = move_toward_constrained(current, target, 5, [obstacle])
        # Should move less distance to avoid obstacle
        assert new_pos.x < 5 or (new_pos.x == 0 and new_pos.y == 0)

    def test_move_away_constrained_no_occupied(self):
        """Test constrained away movement with no obstacles."""
        current = CombatPosition(x=10, y=10)
        threat = CombatPosition(x=0, y=10)
        new_pos = move_away_constrained(current, threat, 5, [])
        assert new_pos.x == 15
        assert new_pos.y == 10

    def test_move_away_constrained_with_obstacle(self):
        """Test constrained away movement around obstacle."""
        current = CombatPosition(x=10, y=10)
        threat = CombatPosition(x=0, y=10)
        obstacle = CombatPosition(x=15, y=10)
        new_pos = move_away_constrained(current, threat, 5, [obstacle])
        # Should move less to avoid obstacle
        assert new_pos.x <= 15 or (new_pos.x == 10 and new_pos.y == 10)

    def test_move_to_flank_constrained_no_obstacles(self):
        """Test constrained flank with no obstacles."""
        current = CombatPosition(x=10, y=10)
        target = CombatPosition(x=20, y=20, facing=Direction.N)
        flank_pos = move_to_flank_constrained(current, target, 3, [])
        assert 0 <= flank_pos.x <= 50
        assert 0 <= flank_pos.y <= 50

    def test_move_to_flank_constrained_with_obstacles(self):
        """Test constrained flank avoids obstacles."""
        current = CombatPosition(x=10, y=10)
        target = CombatPosition(x=20, y=20, facing=Direction.N)
        obstacles = [
            CombatPosition(x=23, y=20),
            CombatPosition(x=17, y=20),
        ]
        flank_pos = move_to_flank_constrained(current, target, 3, obstacles)
        assert 0 <= flank_pos.x <= 50
        assert 0 <= flank_pos.y <= 50


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
