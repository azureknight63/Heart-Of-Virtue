"""Movement mixin for Player — map navigation, teleport, flee, and party recall."""

import random
import time

import functions  # type: ignore
from universe import tile_exists as tile_exists
from neotermcolor import colored, cprint


class PlayerMovementMixin:
    """Map navigation and positioning for the Player."""

    def move(self, dx, dy):
        """Move player by (dx, dy), printing intro text on success or an error on failure."""
        self.universe.game_tick += 1
        # Store previous position before moving
        self.prev_location_x = self.location_x
        self.prev_location_y = self.location_y
        self.location_x += dx
        self.location_y += dy
        tile = tile_exists(self.map, self.location_x, self.location_y)
        if tile is None:
            self.location_x -= dx
            self.location_y -= dy
            # Restore previous position if move failed
            self.prev_location_x = self.location_x
            self.prev_location_y = self.location_y
            cprint("{} cannot go that way.".format(self.name), "red")
            time.sleep(1)
        else:
            print(tile.intro_text())
            functions.print_items_in_room(tile)
            functions.print_objects_in_room(tile)
            functions.advise_player_actions(self, tile)

    def move_north(self):
        self.move(dx=0, dy=-1)

    def move_south(self):
        self.move(dx=0, dy=1)

    def move_east(self):
        self.move(dx=1, dy=0)

    def move_west(self):
        self.move(dx=-1, dy=0)

    def move_northeast(self):
        self.move(dx=1, dy=-1)

    def move_northwest(self):
        self.move(dx=-1, dy=-1)

    def move_southeast(self):
        self.move(dx=1, dy=1)

    def move_southwest(self):
        self.move(dx=-1, dy=1)

    def do_action(self, action, phrase=""):
        """Dispatch a room Action to the corresponding player method."""
        action_method = getattr(self, action.method.__name__)
        if phrase == "":
            if action_method:
                action_method()
        else:
            if action_method:
                action_method(phrase)

    def flee(self, tile):
        """Moves the player randomly to an adjacent tile."""
        available_moves = tile.adjacent_moves()
        if not available_moves:
            cprint("There's nowhere for Jean to run!", "red")
            return
        r = random.randint(0, len(available_moves) - 1)
        self.do_action(available_moves[r])

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
                    print(tile.intro_text())
                    return
                else:
                    print(f"### INVALID TELEPORT LOCATION: {target_map} | {x},{y} ###")
                    return
        print(f"### INVALID TELEPORT LOCATION: {target_map} | {x},{y} ###")

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
            print(
                colored(self.combat_list_allies[1].name, "cyan")
                + colored(" follows Jean.", "green")
            )
        elif party_size == 2:
            print(
                colored(self.combat_list_allies[1].name, "cyan")
                + colored(" and ", "green")
                + colored(self.combat_list_allies[2].name, "cyan")
                + colored("follow Jean.", "green")
            )
        elif party_size >= 3:
            output = ""
            for friend in range(party_size - 1):
                output += colored(
                    self.combat_list_allies[friend + 1].name, "cyan"
                ) + colored(", ", "green")
            output += (
                colored(", and ", "green")
                + colored(self.combat_list_allies[party_size].name, "cyan")
                + colored(" follow Jean.", "green")
            )
            print(output)
