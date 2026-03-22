"""Exploration mixin for Player — look, view, search, and map display."""

import random
import time

import functions  # type: ignore
from neotermcolor import colored, cprint


class PlayerExplorationMixin:
    """Room exploration and map display for the Player."""

    def look(self, target=None):
        """Describe the current room, or delegate to view() if a target is given."""
        if target is not None:
            self.view(target)
        else:
            print(self.current_room.intro_text())
            print()
            functions.print_items_in_room(self.current_room)
            functions.print_objects_in_room(self.current_room)
            functions.advise_player_actions(self)

    def view(self, phrase=""):
        """Describe a specific entity in the current room by name phrase or interactive menu."""
        # print(phrase)
        if phrase == "":
            stuff_here = {}
            for i, thing in enumerate(
                self.current_room.npcs_here
                + self.current_room.items_here
                + self.current_room.objects_here
            ):
                if not thing.hidden and thing.name != "null":
                    stuff_here[str(i)] = thing
            if len(stuff_here) > 0:
                print("What would you like to view?\n\n")
                for k, v in stuff_here.items():
                    print(k, ": ", v.name)
                choice = input("Selection: ")
                if choice in stuff_here:
                    print(stuff_here[choice].description)
                    functions.await_input()
                else:
                    print("Invalid selection.")
            else:
                print("Jean doesn't see anything remarkable here to look at.\n")
        else:
            lower_phrase = phrase.lower()
            for i, thing in enumerate(
                self.current_room.npcs_here
                + self.current_room.items_here
                + self.current_room.objects_here
            ):
                if not thing.hidden and thing.name != "null":
                    announce = ""
                    idle = ""
                    if hasattr(thing, "announce"):
                        announce = thing.announce
                    if hasattr(thing, "idle_message"):
                        idle = thing.idle_message
                    search_item = (
                        thing.name.lower() + " " + announce.lower() + " " + idle.lower()
                    )
                    if lower_phrase in search_item:
                        print(thing.description)
                        functions.await_input()
                        break

    def search(self):
        """
        Searches the current room for hidden NPCs, items, and objects.
        Reveals any hidden entities if the player's search ability exceeds their hide factor.
        Prints discovery messages for found entities, or a message if nothing is found.
        """
        print("Jean searches around the area...")
        search_ability = int(
            ((self.finesse * 2) + (self.intelligence * 3) + self.faith)
            * random.uniform(0.5, 1.5)
        )
        time.sleep(5)
        something_found = False
        for hidden in self.current_room.npcs_here:
            if hidden.hidden:
                if search_ability > hidden.hide_factor:
                    print("Jean uncovered " + hidden.discovery_message)
                    something_found = True
                    hidden.hidden = False
        for hidden in self.current_room.items_here:
            if hidden.hidden:
                if search_ability > hidden.hide_factor:
                    print("Jean found " + hidden.discovery_message)
                    something_found = True
                    hidden.hidden = False
        for hidden in self.current_room.objects_here:
            if hidden.hidden:
                if search_ability > hidden.hide_factor:
                    print("Jean found " + hidden.discovery_message)
                    something_found = True
                    hidden.hidden = False
        if not something_found:
            print("...but he couldn't find anything of interest.")

    def view_map(self):
        """Display a map of discovered tiles with player position marked.

        Iterates discovered tiles to draw a grid where 'X' marks current position,
        tile symbols show visited areas, and '?' indicates discovered but unvisited tiles.
        """
        # Collect discovered tiles and determine grid bounds
        discovered = []
        min_x = min_y = float("inf")
        max_x = max_y = float("-inf")

        for coord, tile in self.map.items():
            if coord == "name":
                continue
            if not getattr(tile, "discovered", False):
                continue
            x, y = coord
            discovered.append((x, y, tile))
            if x > max_x:
                max_x = x
            if x < min_x:
                min_x = x
            if y > max_y:
                max_y = y
            if y < min_y:
                min_y = y

        if not discovered:
            cprint("Jean hasn't explored enough to draw a map yet.", "yellow")
            functions.await_input()
            return

        # Build map grid
        grid = {}
        for x, y, tile in discovered:
            if tile == self.current_room:
                grid[(x, y)] = "X"
            elif getattr(tile, "last_entered", 0) > 0:
                symbol = getattr(tile, "symbol", "●")
                # Handle empty string symbols - use default if `symbol is empty
                grid[(x, y)] = symbol if symbol else "●"
            else:
                grid[(x, y)] = "?"

        # Ensure current position is always marked, even if object reference doesn't match
        if (self.location_x, self.location_y) in grid and grid[
            (self.location_x, self.location_y)
        ] != "X":
            grid[(self.location_x, self.location_y)] = "X"

        # Calculate direction from previous to current position
        prev_direction = None
        if (self.prev_location_x, self.prev_location_y) != (
            self.location_x,
            self.location_y,
        ):
            dx = self.location_x - self.prev_location_x
            dy = self.location_y - self.prev_location_y
            # Determine connector symbol based on direction
            if dx > 0 and dy == 0:  # moved east
                prev_direction = ("horizontal", self.prev_location_x, self.location_y)
            elif dx < 0 and dy == 0:  # moved west
                prev_direction = ("horizontal", self.location_x, self.location_y)
            elif dy > 0 and dx == 0:  # moved south
                prev_direction = ("vertical", self.location_x, self.prev_location_y)
            elif dy < 0 and dx == 0:  # moved north
                prev_direction = ("vertical", self.location_x, self.location_y)
            elif dx != 0 and dy != 0:  # diagonal
                prev_direction = (
                    "diagonal",
                    dx,
                    dy,
                    self.prev_location_x,
                    self.prev_location_y,
                )

        # Render map lines with enlarged display
        print()  # Blank line before map
        for y in range(min_y, max_y + 1):
            # Build line with spacing between characters for better visibility
            chars = [grid.get((x, y), "·") for x in range(min_x, max_x + 1)]

            # Build the line with connectors
            line_parts = []
            for i, ch in enumerate(chars):
                x = min_x + i
                # Color the character
                colored_ch = (
                    colored(ch, "red", attrs=["bold"])
                    if ch == "X"
                    else (
                        colored(ch, "green")
                        if ch == "●" or (ch != "?" and ch != "·" and ch != "'")
                        else (
                            colored(ch, "yellow")
                            if ch == "?"
                            else colored(ch, "white", attrs=["dark"])
                        )
                    )
                )
                line_parts.append(colored_ch)

                # Add connector between this and next character
                if i < len(chars) - 1:
                    next_x = x + 1
                    # Check if we should draw a horizontal connector
                    if prev_direction and prev_direction[0] == "horizontal":
                        if prev_direction[2] == y and prev_direction[1] == x:
                            line_parts.append(colored("-", "white", attrs=["dark"]))
                        else:
                            line_parts.append(" ")
                    else:
                        line_parts.append(" ")

            print(" " + "".join(line_parts))

            # Add vertical connector line if needed
            if y < max_y:
                vertical_parts = []
                for i, ch in enumerate(chars):
                    x = min_x + i

                    # Check if we should draw a vertical connector (in the tile position)
                    if prev_direction and prev_direction[0] == "vertical":
                        if prev_direction[1] == x and prev_direction[2] == y:
                            vertical_parts.append(colored("|", "white", attrs=["dark"]))
                        else:
                            vertical_parts.append(" ")
                    else:
                        vertical_parts.append(" ")

                    # Add space or diagonal connector between columns
                    if i < len(chars) - 1:
                        next_x = x + 1
                        connector_added = False

                        # Check for diagonal connectors (in the space between tiles)
                        if prev_direction and prev_direction[0] == "diagonal":
                            dx_dir = prev_direction[1]
                            dy_dir = prev_direction[2]
                            prev_x = prev_direction[3]
                            prev_y = prev_direction[4]

                            # Diagonal connectors appear in the space between tiles
                            # SE movement (dx=1, dy=1): \ appears between (prev_x, prev_y) and (prev_x+1, prev_y+1)
                            # SW movement (dx=-1, dy=1): / appears between (prev_x, prev_y) and (prev_x-1, prev_y+1)
                            # NE movement (dx=1, dy=-1): / appears between (prev_x, prev_y) and (prev_x+1, prev_y-1)
                            # NW movement (dx=-1, dy=-1): \ appears between (prev_x, prev_y) and (prev_x-1, prev_y-1)

                            if (
                                dy_dir > 0 and dx_dir > 0
                            ):  # SE: \ between prev and current
                                if x == prev_x and y == prev_y:
                                    vertical_parts.append(
                                        colored("\\", "white", attrs=["dark"])
                                    )
                                    connector_added = True
                            elif (
                                dy_dir > 0 and dx_dir < 0
                            ):  # SW: / between prev and current
                                if x == self.location_x and y == prev_y:
                                    vertical_parts.append(
                                        colored("/", "white", attrs=["dark"])
                                    )
                                    connector_added = True
                            elif (
                                dy_dir < 0 and dx_dir > 0
                            ):  # NE: / between prev and current
                                if x == prev_x and y == self.location_y:
                                    vertical_parts.append(
                                        colored("/", "white", attrs=["dark"])
                                    )
                                    connector_added = True
                            elif (
                                dy_dir < 0 and dx_dir < 0
                            ):  # NW: \ between prev and current
                                if x == self.location_x and y == self.location_y:
                                    vertical_parts.append(
                                        colored("\\", "white", attrs=["dark"])
                                    )
                                    connector_added = True

                        if not connector_added:
                            vertical_parts.append(" ")

                print(" " + "".join(vertical_parts))

        functions.await_input()
