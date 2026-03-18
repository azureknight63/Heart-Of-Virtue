import pytest
import sys
from pathlib import Path

# Ensure the project's src directory is on sys.path
ROOT = Path(__file__).resolve().parent.parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Mock neotermcolor if not available
try:
    import neotermcolor
except ImportError:
    import mock
    sys.modules['neotermcolor'] = mock.Mock()

from src.universe import Universe
from src.player import Player
from src.api.services.game_service import GameService

class TestChestRumblerBattleIntegration:
    """Integration test for the complete Chest Rumbler battle narrative sequence."""

    def setup_method(self):
        """Set up the game state in Dark Grotto at the chest location."""
        self.player = Player()
        self.universe = Universe(self.player)
        self.universe.build(self.player)
        
        # Load Dark Grotto map
        dg_map = next((m for m in self.universe.maps if m.get('name') == 'dark-grotto'), None)
        assert dg_map is not None, "dark-grotto map not found"
        
        self.player.map = dg_map
        self.player.universe = self.universe
        
        # Tile (7, 1) is where the Wooden Chest is located
        self.target_tile = self.universe.get_tile(7, 1)
        assert self.target_tile is not None, "Tile (7, 1) not found"
        
        self.player.location_x = 7
        self.player.location_y = 1
        self.player.current_room = self.target_tile
        
        self.service = GameService()
        self.session_data = {}

    def test_complete_chest_rumbler_sequence(self):
        """
        Test the complete interaction sequence:
        1. Open chest
        2. Take all items (triggering the event when chest becomes empty)
        3. Verify narrative pause with user input required
        4. Submit user input to continue
        5. Verify combat starts with Rock Rumbler
        """
        # Step 1: Find and open the Wooden Chest
        chest = next((obj for obj in self.target_tile.objects_here if obj.name == 'Wooden Chest'), None)
        assert chest is not None, "Wooden Chest not found on tile (7, 1)"
        
        # Open the chest if closed
        if chest.state == "closed":
            result = self.service.interact_with_target(
                self.player,
                str(id(chest)),
                "open",
                session_data=self.session_data
            )
            assert result["success"] is True, "Failed to open chest"
        
        # Verify chest has items
        initial_item_count = len(chest.inventory)
        assert initial_item_count > 0, "Chest should have items initially"
        print(f"Chest contains {initial_item_count} items")
        
        # Step 2: Take all items from the chest one by one
        items_taken = []
        while len(chest.inventory) > 0:
            item = chest.inventory[0]
            item_name = item.name
            
            result = self.service.interact_with_target(
                self.player,
                str(id(item)),
                "take",
                session_data=self.session_data
            )
            
            assert result["success"] is True, f"Failed to take {item_name}"
            items_taken.append(item_name)
            print(f"Took: {item_name}")
        
        print(f"Total items taken: {len(items_taken)}")
        assert len(chest.inventory) == 0, "Chest should be empty after taking all items"
        
        # Step 3: The last 'take' action should have triggered the event
        # Check if there are any pending events in the session
        pending_events = self.session_data.get("pending_events", {})
        print(f"Pending events after looting: {len(pending_events)}")
        
        # Find the chest rumbler battle event in pending events
        battle_event = None
        event_id = None
        for eid, event_info in pending_events.items():
            event_data = event_info.get("event_data", {})
            if "Ch01_Chest_Rumbler_Battle" in event_data.get("name", ""):
                battle_event = event_data
                event_id = eid
                break
        
        # If not in pending events, check the last result's events_triggered
        if battle_event is None and result.get("events_triggered"):
            for event in result.get("events_triggered", []):
                if "Ch01_Chest_Rumbler_Battle" in event.get("name", ""):
                    battle_event = event
                    event_id = event.get("event_id")
                    break
        
        assert battle_event is not None, "Ch01ChestRumblerBattle event should have been triggered"
        assert event_id is not None, "Event should have an ID"
        print(f"Battle event found: {battle_event['name']}")
        
        # Step 4: Verify the event requires user input (narrative pause)
        assert battle_event.get("needs_input") is True, "Event should require user input"
        assert battle_event.get("input_type") == "choice", "Input type should be 'choice'"
        assert battle_event.get("input_prompt") == "What's that noise!?", "Unexpected input prompt"
        
        # Verify the narrative text is present
        output_text = battle_event.get("output_text", "")
        assert "rusty iron mace" in output_text.lower(), "Narrative should mention the mace"
        assert "rumbling noise" in output_text.lower(), "Narrative should mention rumbling"
        print(f"Narrative text verified: {len(output_text)} characters")
        
        # Verify input options
        input_options = battle_event.get("input_options", [])
        assert len(input_options) == 1, "Should have exactly one option"
        assert input_options[0]["value"] == "continue", "Option value should be 'continue'"
        assert input_options[0]["label"] == "Continue", "Option label should be 'Continue'"
        
        # Step 5: Submit user input to continue the narrative
        event_id = battle_event["event_id"]
        result = self.service.process_event_input(
            self.player,
            event_id,
            "continue",
            session_data=self.session_data
        )
        
        assert result["success"] is True, "Event input processing should succeed"
        print("User input processed successfully")
        
        # Step 6: Verify combat has started
        assert result.get("combat_started") is True, "Combat should have started after continuing"
        
        # Verify the output mentions the Rock Rumbler appearing
        output_text = result.get("output_text", "")
        assert "rock-like creature" in output_text.lower() or "rumbler" in output_text.lower(), \
            "Output should mention the Rock Rumbler appearing"
        
        # Step 7: Verify combat state
        combat_state = result.get("combat_state")
        assert combat_state is not None, "Combat state should be present"
        
        # Verify enemies list contains Rock Rumbler
        enemies = combat_state.get("enemies", [])
        assert len(enemies) > 0, "Should have at least one enemy"
        
        rumbler_found = any("rumbler" in enemy.get("name", "").lower() for enemy in enemies)
        assert rumbler_found, "Rock Rumbler should be in the enemies list"
        
        print(f"Combat started with {len(enemies)} enemy(ies)")
        
        # Step 8: Verify player has the Rusted Iron Mace equipped
        player_inventory = [item.name for item in self.player.inventory]
        assert "Rusted Iron Mace" in player_inventory, "Player should have the Rusted Iron Mace"
        
        # Check if it's equipped
        if hasattr(self.player, 'eq_weapon') and self.player.eq_weapon:
            assert self.player.eq_weapon.name == "Rusted Iron Mace", \
                "Rusted Iron Mace should be equipped as weapon"
        
        print("[OK] Complete sequence verified: Loot chest -> Narrative pause -> User continue -> Combat start")

    def test_event_does_not_retrigger(self):
        """
        Verify that the event doesn't retrigger after being activated once.
        This tests the 'triggered' flag functionality.
        """
        # Empty the chest
        chest = next((obj for obj in self.target_tile.objects_here if obj.name == 'Wooden Chest'), None)
        assert chest is not None
        
        if chest.state == "closed":
            chest.open()
        
        chest.inventory = []  # Empty it directly
        
        # Trigger events the first time
        events_first = self.service.trigger_tile_events(
            self.player,
            self.target_tile,
            self.session_data
        )
        
        battle_event_first = next(
            (e for e in events_first if "Ch01_Chest_Rumbler_Battle" in e.get("name", "")),
            None
        )
        assert battle_event_first is not None, "Event should trigger the first time"
        first_event_id = battle_event_first.get("event_id")
        
        # Verify it's in pending_events
        assert first_event_id in self.session_data.get("pending_events", {}), \
            "Event should be in pending_events"
        
        # Trigger events again (simulating another game loop)
        # The event should still be in pending_events but NOT trigger a new event
        events_second = self.service.trigger_tile_events(
            self.player,
            self.target_tile,
            self.session_data
        )
        
        # Count how many times the battle event appears in the second trigger
        battle_events_count = sum(
            1 for e in events_second 
            if "Ch01_Chest_Rumbler_Battle" in e.get("name", "")
        )
        
        # The event should appear exactly once (the existing pending event)
        # because the triggered flag prevents re-processing
        assert battle_events_count == 1, \
            f"Event should appear exactly once in second trigger, got {battle_events_count}"
        
        # Verify the event is still in pending_events (not removed)
        assert first_event_id in self.session_data.get("pending_events", {}), \
            "Event should still be in pending_events after second check"
        
        print("[OK] Event correctly does not retrigger")

    def test_event_cleanup_after_completion(self):
        """
        Verify that the event is properly removed from the tile after completion.
        """
        # Empty the chest and trigger the event
        chest = next((obj for obj in self.target_tile.objects_here if obj.name == 'Wooden Chest'), None)
        if chest.state == "closed":
            chest.open()
        chest.inventory = []
        
        # Trigger and get event
        events = self.service.trigger_tile_events(self.player, self.target_tile, self.session_data)
        battle_event = next(
            (e for e in events if "Ch01_Chest_Rumbler_Battle" in e.get("name", "")),
            None
        )
        assert battle_event is not None
        
        # Process the event to completion
        event_id = battle_event["event_id"]
        result = self.service.process_event_input(
            self.player,
            event_id,
            "continue",
            self.session_data
        )
        
        assert result["success"] is True
        
        # Verify the event is no longer in pending_events
        pending_events = self.session_data.get("pending_events", {})
        assert event_id not in pending_events, "Event should be removed from pending_events after completion"
        
        # Verify the event is removed from the tile
        event_still_on_tile = any(
            hasattr(e, 'name') and e.name == 'Ch01_Chest_Rumbler_Battle'
            for e in self.target_tile.events_here
        )
        assert not event_still_on_tile, "Event should be removed from tile after completion"
        
        print("[OK] Event properly cleaned up after completion")
