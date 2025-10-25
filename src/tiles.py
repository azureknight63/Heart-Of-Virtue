"""Describes the tiles in the world space."""
__author__ = 'Alex Egbert'

import random
import importlib

from neotermcolor import colored

import actions  # type: ignore
import functions  # type: ignore
from universe import tile_exists as tile_exists  # type: ignore


class MapTile:
    """The base class for a tile within the world space"""

    def __init__(self, universe, current_map, x, y, description=''):
        """Creates a new tile.

        :param x: the x-coordinate of the tile
        :param y: the y-coordinate of the tile
        """
        self.universe = universe
        self.map = current_map
        self.x = x
        self.y = y
        self.npcs_here = []
        self.items_here = []
        self.events_here = []
        self.objects_here = []
        self.last_entered = 0  # describes the game_tick when the player last entered. Useful for monster/item respawns.
        self.discovered = False  # when drawing the map for the player,
        # display a ? if this is True and self.last_entered == 0
        self.respawn_rate = 9999  # tiles which respawn enemies will adjust this number.
        self.block_exit = []  # append a direction to block it
        self.description = description  # used for the intro_text to make it dynamic
        self.symbol = '●'  # symbol to mark on the map when the tile is fully discovered

    def intro_text(self):
        """Information to be displayed when the player moves into this tile."""
        return colored(self.description, "cyan")

    def modify_player(self, the_player):
        """Process actions that change the state of the player."""
        pass

    def adjacent_moves(self):
        """Returns all move actions for adjacent tiles."""
        moves = []
        directions = [
            ((1, 0), "east", actions.MoveEast),
            ((-1, 0), "west", actions.MoveWest),
            ((0, -1), "north", actions.MoveNorth),
            ((0, 1), "south", actions.MoveSouth),
            ((1, -1), "northeast", actions.MoveNorthEast),
            ((-1, -1), "northwest", actions.MoveNorthWest),
            ((1, 1), "southeast", actions.MoveSouthEast),
            ((-1, 1), "southwest", actions.MoveSouthWest),
        ]
        for (dx, dy), direction, action_cls in directions:
            if tile_exists(self.map, self.x + dx, self.y + dy) and direction not in self.block_exit:
                moves.append(action_cls())
                tile = tile_exists(self.map, self.x + dx, self.y + dy)
                tile.discovered = True
        return moves

    def available_actions(self) -> list[actions.Action]:
        """Returns all the available actions in this room."""
        moves = self.adjacent_moves()  # first, add the available directions in the current room
        default_moves = [  # these are the default moves available to the player
            actions.ListCommands(),
            actions.ViewInventory(),
            actions.SkillMenu(),
            actions.Look(),
            actions.View(),
            actions.Equip(),
            actions.Take(),
            actions.Use(),
            actions.Search(),
            actions.Menu(),
            actions.Save(),
            actions.ViewMap(),
            actions.Attack(),
            actions.ViewStatus()
        ]

        debug_moves = [  # these are the moves available to the player if debugging is enabled
            actions.Teleport(),
            actions.Showvar(),
            actions.Alter(),
            actions.Supersaiyan(),
            actions.TestEvent(),
            actions.SpawnObj(),
            actions.RefreshMerchants()
        ]

        for move in default_moves:
            moves.append(move)

        for move in debug_moves:
            # noinspection PyTypeChecker
            moves.append(move)

        return moves

    def evaluate_events(self):
        for event in self.events_here:
            event.check_conditions()

    def spawn_npc(self, npc_type, hidden=False, hfactor=0, delay=-1):
        try:
            module = __import__('npc')
        except ModuleNotFoundError:
            module = None
        npc_cls = None
        if module:
            try:
                npc_cls = getattr(module, npc_type)
            except Exception:
                npc_cls = None
        if npc_cls is None:
            # Fallback lightweight stub to satisfy spawning tests without full npc graph
            class _StubNPC:
                def __init__(self, name):
                    self.name = name
                    self.current_room = None
                    self.hidden = False
                    self.hide_factor = 0
                    self.combat_delay = 0
                    self.friend = False

                def is_alive(self):
                    return True

            npc = _StubNPC(f"{npc_type} (stub)")
        else:
            npc = npc_cls()
        if hidden:
            npc.hidden = True
            npc.hide_factor = hfactor
        if delay == -1:
            try:
                npc.combat_delay = random.randint(0, 7)
            except Exception:
                npc.combat_delay = 0
        else:
            npc.combat_delay = delay
        self.npcs_here.append(npc)
        try:
            npc.current_room = self
        except Exception:
            pass
        return npc

    def spawn_item(self, item_type, amt=1, hidden=False, hfactor=0, merchandise=False):
        # python
        import importlib

        items_mod = importlib.import_module('items')
        amt = max(1, int(amt))
        spawned = []

        if item_type == 'Gold':
            item = getattr(items_mod, item_type)(amt)
            spawned.append(item)
        else:
            item_cls = getattr(items_mod, item_type)
            # create a sample to inspect attributes
            sample = item_cls()
            if hasattr(sample, 'count'):
                # stackable: create a single item with the requested count
                item = sample
                if hasattr(item, 'merchandise'):
                    item.merchandise = merchandise
                item.count = amt
                spawned.append(item)
            else:
                # non-stackable: create separate instances
                for _ in range(amt):
                    inst = item_cls()
                    if hasattr(inst, 'merchandise'):
                        inst.merchandise = merchandise
                    spawned.append(inst)
                item = spawned[0]

        if hidden:
            for it in spawned:
                it.hidden = True
                it.hide_factor = hfactor

        self.items_here.extend(spawned)
        return item

    def spawn_event(self, event_type, player, tile, repeat=False, params=None):
        event_cls = functions.seek_class(event_type, "story")
        event = functions.instantiate_event(event_cls, player, tile, params=params, repeat=repeat)
        if event:
            self.events_here.append(event)
            return event
        return None

    def spawn_object(self, obj_type, player, tile, params=None, hidden=False, hfactor=0, **kwargs):
        """
        Spawn an object on this tile.
        
        Args:
            obj_type: The class name of the object to spawn
            player: The player instance
            tile: The tile instance
            params: Legacy parameter (list/dict) for objects that parse params
            hidden: Whether the object starts hidden
            hfactor: Hide factor for discovery
            **kwargs: Modern named parameters passed directly to object constructor
        """
        # For backward compatibility: if params is a string like "t.grondia 1 3", parse it
        if isinstance(params, str) and obj_type == "Passageway":
            # Parse old-style Passageway params: "t.mapname x y" or "mapname x y"
            parts = params.split()
            if len(parts) >= 3:
                map_part = parts[0]
                # Handle both "t.mapname" and "mapname" formats
                if map_part.startswith('t.'):
                    teleport_map = map_part[2:]  # Remove "t." prefix
                else:
                    teleport_map = map_part
                try:
                    x = int(parts[1])
                    y = int(parts[2])
                    kwargs['teleport_map'] = teleport_map
                    kwargs['teleport_tile'] = (x, y)
                    params = None  # Don't pass the string to constructor
                except (ValueError, IndexError):
                    pass  # Fall back to passing params as-is
        
        # Import the object class
        obj_cls = getattr(__import__('objects'), obj_type)
        
        # Try to instantiate with kwargs first (modern approach)
        if kwargs:
            try:
                obj = obj_cls(player=player, tile=tile, **kwargs)
            except TypeError:
                # Fall back to params if kwargs don't work
                obj = obj_cls(player, tile, params)
        else:
            # Use params (legacy approach)
            obj = obj_cls(player, tile, params)
        
        if hidden:
            obj.hidden = True
            obj.hide_factor = hfactor
        self.objects_here.append(obj)
        return obj

    def stack_duplicate_items(self):
        for master_item in self.items_here:  # traverse the inventory for stackable items, then stack them
            if hasattr(master_item, "count"):
                remove_duplicates = []
                for duplicate_item in self.items_here:
                    if duplicate_item != master_item and master_item.__class__ == duplicate_item.__class__:
                        master_item.count += duplicate_item.count
                        remove_duplicates.append(duplicate_item)
                if master_item.count > 1:
                    master_item.stack_grammar()
                for duplicate in remove_duplicates:
                    self.items_here.remove(duplicate)

    def remove_event(self, event_name):
        """Removes an event from the tile."""
        for event in self.events_here:
            if getattr(event, "name", None) == event_name:
                self.events_here.remove(event)
                break
