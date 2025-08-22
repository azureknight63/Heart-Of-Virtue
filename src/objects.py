import random
import time
import functions
import states
from neotermcolor import colored, cprint
from src.player import Player
from src.tiles import MapTile
from src.events import Event
from src.items import Item


#####
# These are objects that exist on tiles as opposed to items carried by the player
#####


class Object:
    def __init__(self, name, description, tile=None, player=None, hidden=False, hide_factor=0,
                 idle_message=' is here.',
                 discovery_message='something interesting.'):
        self.name = name
        self.description = description
        self.idle_message = idle_message
        self.hidden = hidden
        self.hide_factor = hide_factor
        self.discovery_message = discovery_message
        self.announce = self.idle_message
        self.keywords = []  # action keywords to hook up an arbitrary command like "press" for a switch
        self.events = []  # a list of events that occur when the player interacts with the object.
        # Events with "repeat" will persist.
        self.tile = tile
        self.player = player

    def spawn_event(self, event_type, player, tile, params, repeat=False):
        event_cls = functions.seek_class(event_type, "story")
        event = functions.instantiate_event(event_cls, player, tile, params=params, repeat=repeat)
        if event != "":
            self.events.append(event)
            return event


class TileDescription(Object):
    """
    Adds to the description of the tile. Has no other function. The existence of this object allows tile descriptions
    to be dynamically changed.
    """

    def __init__(self, player, tile, params):
        param_list = params[2:]
        last_param = param_list[-1]
        if last_param[-1] == '~':  # Tilde is used to replace the end period when parsing the object from the map
            param_list[-1] = last_param[:-1]  # Remove the tilde
            end_mark = '.'
        else:
            end_mark = ''
        description = '.'.join(param_list)
        word_list = description.split(' ')
        last_word = word_list[-1]
        word_list[-1] = last_word + end_mark  # adds the last bit of punctuation if it's a period
        lines = []
        temp_line = word_list[0]
        for word in word_list[1:]:
            if len(temp_line) < (104 - len(word)):
                temp_line += (' ' + word)
            else:
                lines.append(temp_line)
                temp_line = word
        lines.append(temp_line)
        for i, v in enumerate(lines):
            lines[i] = '        ' + v + '\n'
            # if i != len(lines)-1:
            #     lines[i] = '        ' + v + '\n'
            # else:
            #     lines[i] = '        ' + v + '.\n'
        description = colored(''.join(lines), 'cyan')
        idle_message = description
        super().__init__(name="null", description=description, hidden=False, hide_factor=0,
                         idle_message=idle_message,
                         discovery_message="", player=player, tile=tile)


class WallSwitch(Object):
    """
    A wall switch that does something when pressed.
    """

    def __init__(self, player, tile, params=None):
        description = "A small depression in the wall. You may be able to PRESS on it."
        super().__init__(name="Wall Depression", description=description,
                         idle_message="There's a small depression in the wall.",
                         discovery_message="a small depression in the wall!", player=player, tile=tile)
        self.position = False
        self.event_on = None
        self.event_off = None
        self.keywords.append('press')

        for thing in params:
            # account for the events associated with this switch. Max of 2 events.
            # The first event, in order of index, is tied to toggling the switch ON.
            # The second is tied to an OFF toggle.
            if thing[0] == '!':
                param = thing.replace('!', '')
                p_list = param.split(':')
                repeat = False
                event_type = p_list.pop(0)
                for setting in p_list:
                    if setting == 'r':
                        repeat = True
                        p_list.remove(setting)
                        continue
                # use adapter for backward compatible signature handling
                event_cls = functions.seek_class(event_type, "story")
                event = functions.instantiate_event(event_cls, player, tile, params=(p_list if p_list else None), repeat=repeat)
                if self.event_on is None:
                    self.event_on = event
                else:
                    self.event_off = event

    def press(self):
        print("Jean hears a faint 'click.'")
        time.sleep(0.5)
        if not self.position:
            self.position = True
            if self.event_on is not None:
                self.event_on.process()
        else:
            self.position = False
            if self.event_off is not None:
                self.event_off.process()


class WallInscription(Object):
    """
    An inscription (typically visible) that can be looked at.
    """

    def __init__(self, player, tile, params=None):
        description = "Words scratched into the wall. Unfortunately, the inscription is too worn to be decipherable."
        super().__init__(name="Inscription", description=description, hidden=False, hide_factor=0,
                         idle_message="There appears to be some words inscribed in the wall.",
                         discovery_message="some words etched into the wall!", player=player, tile=tile)
        self.events = []
        self.keywords.append('read')
        if 'v0' in params:  # if there is a version declaration, change the description, else keep it generic
            self.description = "The inscription reads: 'EZ 41:1, LK 11:9-10, JL 2:7'"

    def read(self):
        cprint(f"{self.player.name} begins reading...", color="cyan")
        functions.print_slow(self.description, speed="fast")
        functions.await_input()


class Container(Object):
    """
    A generic container that may contain items. Superclass
    NOTE: If you ever make it so items can be added to an existing container post-spawn, run the stack_items method
    """

    # Class constants for better performance and memory usage
    _POSSIBLE_STATES = ("closed", "opened")
    _DEFAULT_KEYWORDS = ['open', 'unlock', 'loot']

    def __init__(self, name: str="Container", description: str="A container. There may be something inside.",
                 hidden: bool=False, hide_factor: int=0, idle_message: str="A container is sitting here.",
                 discovery_message: str=" a container!", player: Player=None, tile: MapTile=None,
                 nickname: str="container", locked: bool=False, items: list['Item']=None, events: list['Event']=None):
        self.nickname = nickname
        self.possible_states = self._POSSIBLE_STATES
        self.state = self._POSSIBLE_STATES[0]  # start closed
        self.revealed = False
        self.locked = locked

        # Initialize inventory with items if provided, using list comprehension for efficiency
        self.inventory = list(items) if items else []

        super().__init__(name=name, description=description, hidden=hidden, hide_factor=hide_factor,
                         idle_message=idle_message,
                         discovery_message=discovery_message, player=player, tile=tile)

        # Extend events list efficiently if events provided
        if events:
            self.events.extend(events)

        # Add keywords efficiently
        self.keywords.extend(self._DEFAULT_KEYWORDS)

        self.process_events()  # process initial events (triggers labeled "auto")
        self.stack_items()

    def refresh_description(self):
        """Optimized description refresh using f-strings and join for better performance"""
        if self.state == "closed":
            self.description = f"A {self.nickname} which may or may not have things inside. You can try to UNLOCK (if locked), OPEN, or LOOT it."
        elif self.inventory:
            # Use join for efficient string building instead of concatenation
            item_descriptions = [colored(item.description, 'yellow') for item in self.inventory]
            self.description = f"A {self.nickname}. Inside are the following things: \n\n" + '\n'.join(item_descriptions)
        else:
            self.description = f"A {self.nickname}. It's empty. Very sorry."

    def unlock(self):
        """Optimized unlock method with early return and f-string formatting"""
        if self.state != "closed":
            print("Jean can't unlock something that's already open!")
            return

        # Use any() for more efficient key search
        matching_key = next((key for key in self.player.inventory
                           if hasattr(key, "lock") and key.lock == self), None)

        if matching_key:
            self.locked = False
            cprint(f"Jean uses {matching_key.name} to unlock the {self.nickname}.", "green")
        else:
            cprint("Jean couldn't find a matching key.", "red")

    def open(self):
        """Optimized open method with f-string formatting"""
        if self.locked:
            print(f"Jean pulls on the lid of the {self.nickname} to no avail. It's locked.")
            return

        if self.state == "closed":
            print(f"The {self.nickname} creaks eerily.")
            time.sleep(0.5)
            print("The lid lifts back on the hinge, revealing the contents inside.")
            self.revealed = True
            self.state = "opened"
            self.refresh_description()
            self.process_events()
        else:
            print(f"The {self.nickname} is already open. You should VIEW or LOOT it to see what's inside.")

    def loot(self):
        """Optimized loot method with better memory management and f-strings"""
        if self.state == "closed":
            self.open()

        if self.state != "opened":
            return

        if not self.inventory:
            print("It's empty. Very sorry.")
            return

        print(f"Jean rifles through the contents of the {self.nickname}.\n\n Choose which items to take.\n\n")

        # Pre-build acceptable responses for efficiency
        acceptable_responses = ['all', 'x'] + [str(i) for i in range(len(self.inventory))]

        # Display items using f-strings
        for i, item in enumerate(self.inventory):
            cprint(f'{i}: {item.name} - {item.description}', 'yellow')
        cprint('all: Take all items.\nx: Cancel', 'yellow')

        choice = None
        while choice not in acceptable_responses:
            choice = input('Selection: ')

        if choice == 'all':
            # More efficient: transfer all items at once and clear inventory
            taken_items = self.inventory.copy()
            self.inventory.clear()
            self.player.inventory.extend(taken_items)
            for item in taken_items:
                print(f'Jean takes {item.name}.')
            self.refresh_description()
        elif choice != 'x':
            # Convert choice to int and take specific item
            choice_idx = int(choice)
            if 0 <= choice_idx < len(self.inventory):
                item_taken = self.inventory.pop(choice_idx)
                print(f'Jean takes {item_taken.name}.')
                self.player.inventory.append(item_taken)
                self.refresh_description()

        # Only process events if items were actually taken
        if choice != 'x':
            self.process_events()

    def process_events(self):
        """Optimized process_events method with early return and cleaner iteration"""
        if not self.events:
            return

        # Process events more efficiently by avoiding modification during iteration
        events_to_process = self.events[:]  # Create a copy
        self.events.clear()  # Clear the original list

        for event in events_to_process:
            event.params.append(self)
            self.tile.events_here.append(event)

        self.tile.evaluate_events()

    def stack_items(self):
        """Optimized stack_items method with better algorithm and reduced iterations"""
        if not self.inventory:
            return

        # Use a more efficient algorithm that processes each item type only once
        processed_classes = set()
        items_to_remove = []

        for i, master_item in enumerate(self.inventory):
            if not hasattr(master_item, "count") or master_item.__class__ in processed_classes:
                continue

            processed_classes.add(master_item.__class__)

            # Find all duplicates of this item type in one pass
            for j in range(i + 1, len(self.inventory)):
                duplicate_item = self.inventory[j]
                if (hasattr(duplicate_item, "count") and
                    master_item.__class__ == duplicate_item.__class__):
                    master_item.count += duplicate_item.count
                    items_to_remove.append(j)

            # Update grammar if needed
            if hasattr(master_item, "stack_grammar"):
                master_item.stack_grammar()

        # Remove duplicates in reverse order to maintain indices
        for idx in sorted(items_to_remove, reverse=True):
            self.inventory.pop(idx)


"""
World objects 
"""

class Shrine(Object):
    """
    A shrine that can bestow a variety of items, effects, and sometimes challenges to the player
    All shrines should be tied to an event to have an effect. Prayer is always effective, but for these,
    game effects should only happen once.
    """

    def __init__(self, player, tile, params=None):
        description = "A beautiful shrine depicting a variety of saints praying to God."
        super().__init__(name="Shrine", description=description,
                         idle_message="There is an ornate shrine here.",
                         discovery_message=" a shrine!", player=player, tile=tile)
        self.event = None
        self.keywords.append('pray')

        for thing in params:
            # account for the events associated with this object. Max of 1 event.
            # Triggers after interacting with the shrine.
            if thing[0] == '!':
                param = thing.replace('!', '')
                p_list = param.split(':')
                repeat = False
                event_type = p_list.pop(0)
                for setting in p_list:
                    if setting == 'r':
                        repeat = True
                        p_list.remove(setting)
                        continue
                event_cls = functions.seek_class(event_type, "story")
                self.event = functions.instantiate_event(event_cls, player, tile, params=(p_list if p_list else None), repeat=repeat)

    def pray(self, player):
        print("Jean kneels down and begins to pray for intercession.")
        time.sleep(random.randint(3, 10))
        selection = random.randint(0, len(player.prayer_msg) - 1)
        print(player.prayer_msg[selection])
        if self.event is not None:
            time.sleep(random.randint(3, 10))
            self.event.process()
            self.event = None
        functions.await_input()


class HealingSpring(Object):
    """
    A spring that restores Jean's health when he drinks from it. He can also WASH or CLEAN himself in it,
    which provides a small, temporary boost to charisma and max fatigue.
    """

    def __init__(self, player, tile, params=None):
        description = "A burbling spring with fresh smelling water. It is clean and very inviting."
        super().__init__(name="HealingSpring", description=description,
                         idle_message="There is a small spring bubbling here.",
                         discovery_message=" a healing spring!", player=player, tile=tile)
        self.event = None
        self.keywords.append('drink')
        self.keywords.append('clean')
        self.keywords.append('wash')

        for thing in params:
            # account for the events associated with this object. Max of 1 event.
            # Triggers after interacting with the object.
            if thing[0] == '!':
                param = thing.replace('!', '')
                p_list = param.split(':')
                repeat = False
                event_type = p_list.pop(0)
                for setting in p_list:
                    if setting == 'r':
                        repeat = True
                        p_list.remove(setting)
                        continue
                event_cls = functions.seek_class(event_type, "story")
                self.event = functions.instantiate_event(event_cls, player, tile, params=(p_list if p_list else None), repeat=repeat)

    def drink(self, player):
        print("Jean bends down to the water and, cupping it in his hands, begins to sip eagerly.")
        time.sleep(2)
        print("The water is cool and refreshing as it goes down his throat.")
        time.sleep(1)
        cprint("HP restored!", "green")
        player.hp = player.maxhp
        if self.event is not None:
            time.sleep(2)
            self.event.process()
            self.event = None
        functions.await_input()

    @staticmethod
    def clean(player):
        print("Jean summarily begins washing himself in the cool water of the spring.")
        time.sleep(2)
        print("Jean closes his eyes for a moment, enjoying the feeling of simple cleanliness.")
        time.sleep(1)
        cprint("Jean now has Clean status!", "green")
        player.apply_state(states.Clean(player))

    def wash(self, player):
        self.clean(player)  # this is an alias for clean


class Passageway(Object):
    """
    A passageway that takes Jean to a different location. This can either be a location in the same map or a
    different map entirely.
    """

    def __init__(self, player: Player, tile: MapTile, events_before: list['Event']=None, events_after: list['Event']=None,
                 teleport_map: str=None, teleport_tile: tuple=None, persist: bool=True,
                 hidden: bool=False, hide_factor: int=0,
                 is_shop_exit: bool=False,
                 name: str="Passageway",
                 description: str="A passageway leading elsewhere is here.",
                 idle_message: str="There is a passageway here.",
                 discovery_message: str =" a passageway!"):
        super().__init__(name=name, description=description,
                         idle_message=idle_message,
                         hidden=hidden, hide_factor=hide_factor,
                         discovery_message=discovery_message, player=player, tile=tile)
        self.keywords.extend(['enter', 'go', 'leave', 'exit'])
        self.events_before = events_before if events_before is not None else []
        self.events_after = events_after if events_after is not None else []
        self.teleport_map = teleport_map if teleport_map is not None else ""
        self.teleport_tile = teleport_tile if teleport_tile is not None else ""
        self.persist = persist  # if True, the passageway will remain after use, else
        # it will be removed from the tile after use
    def enter(self, player):
        # If this is a shop exit, force player to drop all merchandise items before events
        if getattr(self, 'is_shop_exit', False):
            dropped_items = []
            # Copy inventory to avoid modifying while iterating
            for item in player.inventory[:]:
                if getattr(item, 'merchandise', False):
                    player.inventory.remove(item)
                    player.tile.items_here.append(item)
                    dropped_items.append(item.name if hasattr(item, 'name') else str(item))
            if dropped_items:
                print(f"Jean placed the following merchandise neatly on the ground: {', '.join(dropped_items)}.")
                time.sleep(1)
        if self.events_before:
            for event in self.events_before:
                event.process()
        if self.teleport_map and self.teleport_tile:
            print(f"Jean steps through the {self.name.lower()}...")
            time.sleep(0.5)
            player.teleport(self.teleport_map, self.teleport_tile)
            if self.events_after:
                for event in self.events_after:
                    event.process()
            if not self.persist:
                self.tile.objects.remove(self)
        else:
            print("The passageway is not properly configured. Please contact the developer.")
        functions.await_input()

    def go(self, player):
            self.enter(player)

    def leave(self, player):
        self.enter(player)

    def exit(self, player):
        self.enter(player)
