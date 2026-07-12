"""Movement mixin for Player — map navigation, teleport, and party recall."""

from src.universe import tile_exists as tile_exists
from src.narration import colored, narrate


class PlayerMovementMixin:
    """Map navigation and positioning for the Player."""

    def teleport(self, target_map: str, target_coordinates: tuple):
        """
        Teleports the player to a specified area and coordinates.

        Args:
            target_map (str): The name of the area to teleport to.
            target_coordinates (tuple): The (x, y) coordinates to teleport to.

        Behavior:
            - If the area and coordinates are valid, moves the player there and prints the tile's intro text.
            - If invalid, prints an error message.
        """
        # Before teleporting, drop any merchandise items at the origin
        self.drop_merchandise_items()
        x = target_coordinates[0]
        y = target_coordinates[1]
        for area in self.universe.maps:
            if area.get("name") == target_map and x is not None and y is not None:
                tile = tile_exists(area, x, y)
                if tile:
                    self.map = area
                    self.universe.game_tick += 1
                    self.location_x = x
                    self.location_y = y
                    narrate(tile.intro_text())
                    return
                else:
                    narrate(f"### INVALID TELEPORT LOCATION: {target_map} | {x},{y} ###")
                    return
        narrate(f"### INVALID TELEPORT LOCATION: {target_map} | {x},{y} ###")

    def recall_friends(self):
        """Move all allied NPCs to the player's current room."""
        party_size = len(self.combat_list_allies) - 1
        for friend in self.combat_list_allies:
            if friend.current_room != self.current_room:
                try:
                    friend.current_room.npcs_here.remove(friend)
                except ValueError:
                    pass
                friend.current_room = self.current_room
                friend.current_room.npcs_here.append(friend)
        if party_size == 1:
            narrate(
                colored(self.combat_list_allies[1].name, "cyan")
                + colored(" follows Jean.", "green")
            )
        elif party_size == 2:
            narrate(
                colored(self.combat_list_allies[1].name, "cyan")
                + colored(" and ", "green")
                + colored(self.combat_list_allies[2].name, "cyan")
                + colored(" follow Jean.", "green")
            )
        elif party_size >= 3:
            output = ""
            for friend in range(party_size - 1):
                output += colored(
                    self.combat_list_allies[friend + 1].name, "cyan"
                ) + colored(", ", "green")
            output += (
                colored("and ", "green")
                + colored(self.combat_list_allies[party_size].name, "cyan")
                + colored(" follow Jean.", "green")
            )
            narrate(output)
