from __future__ import annotations
import random
import time
import states
from neotermcolor import colored, cprint

import functions as functions
from player import Player
from tiles import MapTile
from events import Event # noqa; This is used in type hints
from items import Item # noqa; This is used in type hints

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
        else:
            return None


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

    def __init__(self, player, tile, params=None, position: bool=False):
        description = "A small depression in the wall. You may be able to PRESS on it."
        super().__init__(name="Wall Depression", description=description,
                         idle_message="There's a small depression in the wall.",
                         discovery_message="a small depression in the wall!", player=player, tile=tile)
        self.position: bool = position  # False is unpressed, True is pressed
        self.event_on = None
        self.event_off = None
        self.keywords.append('press')
        self.keywords.append('touch')
        self.keywords.append('push')

        if params:
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

    def push(self):
        self.press()

    def touch(self):
        self.press()


class WallInscription(Object):
    """
    An inscription (typically visible) that can be looked at.
    """

    def __init__(self, player: Player, tile: MapTile,
                 description: str="Words scratched into the wall."
                                  " Unfortunately, the inscription is too worn to be decipherable.",
                 text: str=None):
        super().__init__(name="Inscription", description=description, hidden=False, hide_factor=0,
                         idle_message="There appears to be some words inscribed in the wall.",
                         discovery_message="some words etched into the wall!", player=player, tile=tile)
        self.events = []
        self.keywords.append('read')
        self.text = text


    def read(self):
        if self.text:
            cprint(f"{self.player.name} begins reading...", color="cyan")
            functions.print_slow(self.description, speed="fast")
            functions.await_input()
        else:
            print(self.description)


class Container(Object):
    """
    A generic container that may contain items. Superclass
    NOTE: If you ever make it so items can be added to an existing container post-spawn, run the stack_items method
    """

    # Class constants for better performance and memory usage
    _POSSIBLE_STATES = ("closed", "opened")
    _DEFAULT_KEYWORDS = ['open', 'unlock', 'loot', 'check', 'view', 'examine', 'inspect', 'peruse']

    @property
    def start_open(self) -> bool:
        """Indicates whether the container should start opened.
        Setting this property updates the container's public state and locked flag so
        that when a Container instance is later created from serialized data (where
        start_open may be written as an attribute after __init__), the container's
        state correctly reflects that attribute.
        """
        return getattr(self, '_start_open', False)

    @start_open.setter
    def start_open(self, value: bool):
        self._start_open = bool(value)
        # Ensure state matches the boolean flag
        self.state = self._POSSIBLE_STATES[1] if self._start_open else self._POSSIBLE_STATES[0]
        # If a container starts open, it cannot be locked
        if self._start_open:
            try:
                # Only override locked if attribute exists or when starting open
                self.locked = False
            except Exception:
                # ignore attribute issues during early init
                pass

    def __init__(self, name: str="Container", description: str="A container. There may be something inside.",
                 hidden: bool=False, hide_factor: int=0, start_open: bool=False,
                 idle_message: str="A container is sitting here.",
                 discovery_message: str=" a container!", player: Player=None, tile: MapTile=None,
                 nickname: str="container", locked: bool=False, inventory: list['Item']=None, events: list['Event']=None,
                 merchant: object="", items: list['Item']=None, allowed_subtypes: list[type[Item]] = None, stock_count: int=10):
        """Accept both 'items' (legacy/tests) and 'inventory'. Normalize merchant to a name when possible.
        Also accept 'allowed_subtypes' and expose as allowed_item_types (list of types).
        """
        # Normalize inventory parameter: accept items alias for tests/tools
        inv = inventory if inventory is not None else (items if items is not None else [])
        self.nickname = nickname
        self.possible_states = self._POSSIBLE_STATES
        # Set default revealed flag
        self.revealed = False
        # Assign initial locked state (may be overridden by start_open semantics)
        self.locked = locked
        # Set start_open via property so that later attribute assignment also keeps state consistent
        self._start_open = False
        self.start_open = start_open
        # Normalize merchant to name if an object is provided (avoid circular import of Merchant)
        try:
            self.merchant = merchant.name if hasattr(merchant, 'name') else merchant
        except Exception:
            self.merchant = merchant
        # allowed_subtypes may be provided as tuple/list of types; default to Item if falsy
        self.allowed_item_types = list(allowed_subtypes) if allowed_subtypes else [Item]
        self.stock_count = stock_count  # Maximum number of items the container should hold (for shop logic)
        self.inventory = inv if inv else []

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
            cprint(f"Jean uses {matching_key.name} to unlock the {self.name}.", "green")
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
        """
        Allows the player to loot the container. If the container is closed, it opens it first.
        If the container is opened, launches the ContainerLootInterface for item selection and transfer.
        """
        if self.state == "closed":
            self.open()

        if self.state != "opened":
            return

        # Import the interface class
        from interface import ContainerLootInterface

        # Create and run the loot interface
        loot_interface = ContainerLootInterface(self, self.player)
        loot_interface.run()

    def check(self):
        self.loot()

    def view(self):
        self.loot()

    def examine(self):
        self.loot()

    def inspect(self):
        self.loot()

    def peruse(self):
        self.loot()

    def process_events(self):
        """Optimized process_events method with early return and cleaner iteration"""
        if not self.events:
            return

        # Process events more efficiently by avoiding modification during iteration
        events_to_process = self.events[:]  # Create a copy
        self.events.clear()  # Clear the original list

        for event in events_to_process:
            #TODO: Test this and make sure events process properly
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
                if (
                        hasattr(duplicate_item, "count") and
                        master_item.__class__ == duplicate_item.__class__
                ):
                    master_item.count += duplicate_item.count # noqa; attribute guaranteed in conditional
                    items_to_remove.append(j)

            # Update grammar if needed
            if hasattr(master_item, "stack_grammar"):
                master_item.stack_grammar()

        # Remove duplicates in reverse order to maintain indices
        for idx in sorted(items_to_remove, reverse=True):
            self.inventory.pop(idx)

# --- Annotation normalization patch ---
# Ensure that the 'allowed_subtypes' annotation on Container.__init__ is an evaluated type
# instead of a postponed string (due to from __future__ import annotations) so that
# inspect.get_origin returns 'list' as expected by tests and runtime reflection.
try:
    _ann = Container.__init__.__annotations__.get('allowed_subtypes')  # type: ignore[attr-defined]
    if isinstance(_ann, str):
        # Rebind with concrete evaluated type
        from items import Item as _Item  # local import to avoid re-export side effects
        Container.__init__.__annotations__['allowed_subtypes'] = list[type[_Item]]  # type: ignore[index]
except Exception:
    pass


class Crate(Container):
    """
    This is meant to be a merchant crate with all merchandise and a stock count.
    The purpose of this object is to be a convenient, predefined container for rapid map creation.
    """
    def __init__(self, player, tile, events: list['Event']=None,
                 merchant: object="", allowed_subtypes: list[type[Item]] = None, stock_count: int=20):
        description = "A large wooden crate containing merchandise."
        super().__init__(name="Crate", description=description,
                         idle_message="A large wooden crate is here.", events=events,
                         merchant=merchant, allowed_subtypes=allowed_subtypes,
                         discovery_message=" a large wooden crate!", player=player, tile=tile,
                         nickname="crate", locked=False, start_open=True, stock_count=stock_count)
        self.keywords.remove("open")
        self.keywords.remove("unlock")


class Shelf(Container):
    """
    This is meant to be a merchant shelf with all merchandise and a stock count.
    The purpose of this object is to be a convenient, predefined container for rapid map creation.
    """
    def __init__(self, player, tile, events: list['Event']=None,
                 merchant: object="", allowed_subtypes: list[type[Item]] = None, stock_count: int=10):
        description = "A practical wooden shelf displaying merchandise."
        super().__init__(name="Shelf", description=description,
                         idle_message="A shelf displaying merchandise is here.", events=events,
                         merchant=merchant, allowed_subtypes=allowed_subtypes,
                         discovery_message=" a wooden shelf!", player=player, tile=tile,
                         nickname="shelf", locked=False, start_open=True, stock_count=stock_count)
        self.keywords.remove("open")
        self.keywords.remove("unlock")

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

        if params:
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

        if params:
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

    def __init__(self, player: Player, tile: MapTile,
                 events_before: list['Event']=None, events_after: list['Event']=None,
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
        # Drop any merchandise items immediately upon attempting to enter/teleport
        if hasattr(player, 'drop_merchandise_items'):
            player.drop_merchandise_items()
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


class MarketBell(Object):
    """
        Represents a bell mounted near a stall or booth in the Ecumerium. Players can RING it to summon attention or
        trigger a configured event. The bell provides feedback when rung and can optionally process an attached event.
    """
    def __init__(self, player: Player, tile: MapTile, event: Event=None):
        description = "A small metal bell hangs from a short iron hook; it looks like it can be RUNG to draw attention."
        super().__init__(name="Market Bell", description=description,
                         idle_message="A small bell hangs here, waiting to be rung.",
                         discovery_message="a small bell mounted by a stall!", player=player, tile=tile)
        self.keywords.append('ring')
        self.keywords.append('use')
        self.event = event

    def ring(self):
        """Player rings the bell. If an event is attached, process it. Otherwise provide a simple cue."""
        cprint("Jean reaches up and rings the bell.", color='cyan')
        time.sleep(0.4)
        print("A clear, bright tone rings through the arcade, briefly carrying above the market din.")
        if self.event is not None:
            # process and clear non-repeat events; instantiate_event handles repeat flag behavior
            time.sleep(0.6)
            self.event.process()
            # if the event was non-repeat it will typically be consumed; mirror Shrine behavior by clearing
            try:
                if not getattr(self.event, 'repeat', False):
                    self.event = None
            except Exception:
                self.event = None
        functions.await_input()

    def use(self):
        self.ring()


class Fountain(Object):
    """A decorative stone fountain providing simple ambiance. Jean can DRINK (minor refresh) or LISTEN/ADMIRE it.
    Optionally an event may be attached which triggers the first time it is drunk from.
    """
    def __init__(self, player: Player, tile: MapTile, event: Event=None):
        description = "A low circular fountain murmurs softly; clear water bubbles up and spills over carved stone."\
                      " You could probably DRINK from it or just LISTEN to the water."  # noqa: E501
        super().__init__(name="Fountain", description=description,
                         idle_message="A small stone fountain murmurs here.",
                         discovery_message="a murmuring fountain!", player=player, tile=tile)
        self.keywords.extend(['drink', 'listen', 'admire', 'use'])
        self.event = event

    def drink(self):
        cprint("Jean cups some water from the fountain and takes a cool sip.", 'cyan')
        time.sleep(0.5)
        if self.event:
            time.sleep(0.5)
            self.event.process()
            if not getattr(self.event, 'repeat', False):
                self.event = None
        functions.await_input()

    def listen(self):
        print("Jean closes his eyes a moment, listening to the gentle splash of water.")
        functions.await_input()

    def admire(self):
        print("The craftsmanship of the fountain is simple but pleasant.")
        functions.await_input()

    def use(self):  # alias
        self.drink()


class StreetLantern(Object):
    """A wrought iron street lantern that can be LIGHTed or DOUSEd. Optional events may trigger on state change.
    """
    def __init__(self, player: Player, tile: MapTile, event_when_lighting: Event=None, event_when_dousing: Event=None,
                 lit: bool=False):
        description = "An iron street lantern stands here, its glass panes slightly clouded." + \
                      (" It is currently lit, casting a warm glow in all directions." if lit
                       else " It is dark; maybe you could LIGHT it.")
        super().__init__(name="Street Lantern", description=description,
                         idle_message="A wrought iron street lantern stands here.",
                         discovery_message="a street lantern!", player=player, tile=tile)
        self.keywords.extend(['light', 'douse', 'extinguish', 'inspect'])
        self.lit = lit
        self.event_on = event_when_lighting
        self.event_off = event_when_dousing
        self._update_description()

    def _update_description(self):
        state_text = "lit" if self.lit else "dark"
        self.description = f"An iron street lantern stands here. It is {state_text}."

    def light(self):
        if self.lit:
            print("The lantern is already lit.")
            return
        print("Jean strikes a spark and coaxes the lantern to life.")
        self.lit = True
        self._update_description()
        if self.event_on:
            self.event_on.process()
            if not getattr(self.event_on, 'repeat', False):
                self.event_on = None
        functions.await_input()

    def douse(self):
        if not self.lit:
            print("The lantern is already dark.")
            return
        print("Jean shields the flame and pinches it out.")
        self.lit = False
        self._update_description()
        if self.event_off:
            self.event_off.process()
            if not getattr(self.event_off, 'repeat', False):
                self.event_off = None
        functions.await_input()

    def extinguish(self):
        self.douse()

    def inspect(self):
        print(self.description)
        functions.await_input()


class NoticeBoard(Object):
    """A public notice board. Jean can READ posted notes. Optional single event
    triggers on first READ.
    """
    def __init__(self, player: Player, tile: MapTile, event: Event=None, notes: list[str]=None):
        description = "A wooden notice board stands here with a scattering of parchment scraps pinned to it."
        super().__init__(name="Notice Board", description=description,
                         idle_message="A wooden notice board is here.",
                         discovery_message="a notice board!", player=player, tile=tile)
        self.keywords.extend(['read', 'use'])
        self.notes: list[str] = notes if notes else [
            "Lost: One black cat with a white spot on its chest. Answers to 'Midnight'. Reward offered.",
            "For Sale: Handmade pottery bowls, vases, and mugs. All proceeds support the local orphanage.",
            "Help Wanted: Looking for an assistant to help with daily chores and errands. Inquire within.",
            "Event: The annual Ecumerium Festival will take place next week! Music, food, and games for all ages.",
            "Notice: Please keep the market area clean. Trash bins are provided throughout the arcade."
        ]
        self.event = event
        self._read_once = False

    def read(self):
        print("Jean scans the various notes:")
        for note in self.notes:
            print(f"  - {note}")
        if self.event and (not self._read_once or getattr(self.event, 'repeat', False)):
            time.sleep(0.3)
            self.event.process()
            if not getattr(self.event, 'repeat', False):
                self._read_once = True
        functions.await_input()

    def use(self):
        self.read()


class PrayerCandleRack(Object):
    """A rack of small votive candles. Jean can LIGHT a candle (increments count) or PRAY. Optional single event on PRAY.
    """
    def __init__(self, player: Player, tile: MapTile, lit_candles: int=0, event: Event=None):
        description = "A wrought rack of small votive candles. A few flicker; many are unlit."  # noqa: E501
        super().__init__(name="Candle Rack", description=description,
                         idle_message="A rack of votive candles stands here.",
                         discovery_message="a rack of small candles!", player=player, tile=tile)
        self.keywords.extend(['light', 'pray', 'use'])
        self.lit_candles = lit_candles
        self.event = event

    def light(self):
        if self.lit_candles >= 20:
            print("All the candles are already lit.")
            functions.await_input()
            return
        self.lit_candles += 1
        print(f"Jean lights a small candle. ({self.lit_candles} now flicker.)")
        functions.await_input()

    def pray(self):
        print("Jean bows his head silently before the little flames.")
        time.sleep(5)
        print("A strange feeling fills his chest, as if there's a tune he can't quite remember.")
        time.sleep(0.5)
        if self.event:
            self.event.process()
            if not getattr(self.event, 'repeat', False):
                self.event = None
        functions.await_input()

    def use(self):
        self.pray()


class MarketGong(Object):
    """A larger bronze gong used to signal openings or special sales. Jean can STRIKE/HIT it; optional event triggers.
    """
    def __init__(self, player: Player, tile: MapTile, event: Event=None):
        description = "A wide bronze gong is suspended from a stout frame. A padded mallet invites someone to STRIKE it."  # noqa: E501
        super().__init__(name="Market Gong", description=description,
                         idle_message="A bronze gong hangs here, silent.",
                         discovery_message="a large bronze gong!", player=player, tile=tile)
        self.keywords.extend(['strike', 'hit', 'bang', 'use'])
        self.event = event

    def strike(self):
        cprint("Jean swings the mallet into the gong with a resonant BOOOONG...", 'cyan')
        time.sleep(0.7)
        print("The deep tone rolls outward and slowly fades.")
        time.sleep(1)
        print("Some nearby shoppers glance over, momentarily distracted. More than a few wear a confused expression.")
        if self.event:
            time.sleep(0.4)
            self.event.process()
            if not getattr(self.event, 'repeat', False):
                self.event = None
        functions.await_input()

    def hit(self):
        self.strike()

    def bang(self):
        self.strike()

    def use(self):
        self.strike()


class Book(Object):
    """
    A book. Jean can READ it. Optionally, an event may be tied to reading the book.
    """

    def __init__(self, player: Player, tile: MapTile, event: Event=None,
                 description: str="A dusty old book, full of mysteries and sentiments.",
                 text: str=None, text_file_path: str=None, chars_per_page: int=800):
        super().__init__(name="Book", description=description, hidden=False, hide_factor=0,
                         idle_message="There's a book here.",
                         discovery_message="a book!", player=player, tile=tile)
        self.event = event
        self.keywords.append('read')
        self.text_file_path = text_file_path
        self._text = None  # Cache for loaded text
        
        # Only set _text if text_file_path is not provided
        if not text_file_path:
            if text:
                self._text = text
            else:
                self._text = "This book is mysteriously blank."
        # If text_file_path is provided, text will be loaded lazily via property
        
        self.chars_per_page = chars_per_page  # characters per page for pagination

    @property
    def text(self):
        """Lazy load text from file if needed."""
        if self._text is None and self.text_file_path:
            try:
                with open(self.text_file_path, 'r', encoding='utf-8') as f:
                    self._text = f.read()
            except Exception as e:
                cprint(f"Error loading book text from {self.text_file_path}: {e}", "red")
                self._text = "This book is mysteriously blank."
        return self._text if self._text else "This book is mysteriously blank."
    
    @text.setter
    def text(self, value):
        """Allow direct setting of text (for deserialization)."""
        self._text = value

    def _paginate_text(self, text: str) -> list[str]:
        """Break text into pages of approximately chars_per_page characters, breaking at sentence boundaries."""
        if not text or len(text) <= self.chars_per_page:
            return [text] if text else []
        
        pages = []
        current_page = ""
        
        # Split by sentences (basic sentence detection)
        sentences = text.replace('! ', '!|').replace('? ', '?|').replace('. ', '.|').split('|')
        
        for sentence in sentences:
            # If a single sentence is longer than chars_per_page, we need to force-split it
            if len(sentence) > self.chars_per_page:
                # If current_page has content, save it first
                if current_page.strip():
                    pages.append(current_page.strip())
                    current_page = ""
                
                # Split the long sentence into chunks
                while len(sentence) > self.chars_per_page:
                    pages.append(sentence[:self.chars_per_page].strip())
                    sentence = sentence[self.chars_per_page:]
                
                # Add remaining part to current page
                if sentence.strip():
                    current_page = sentence
                continue
            
            # If adding this sentence would exceed page limit and we have content, start new page
            if len(current_page) + len(sentence) > self.chars_per_page and current_page:
                pages.append(current_page.strip())
                current_page = sentence
            else:
                current_page += sentence
        
        # Add the last page if there's remaining content
        if current_page.strip():
            pages.append(current_page.strip())
        
        return pages if pages else [text]

    def _display_page(self, page_text: str, page_num: int, total_pages: int):
        """Display a single page with header and footer."""
        functions.screen_clear()
        cprint(f"--- {self.name} (Page {page_num} of {total_pages}) ---", "cyan")
        print()
        # Wrap text to 80 characters for readability
        import textwrap
        wrapped = textwrap.fill(page_text, width=80)
        print(wrapped)
        print()
        cprint(f"--- Page {page_num} of {total_pages} ---", "cyan")

    def _show_page_navigation(self, current_page: int, total_pages: int) -> str:
        """Display navigation options and get user input."""
        print()
        options = []
        if current_page > 1:
            options.append(colored("P: Previous Page", "yellow"))
        if current_page < total_pages:
            options.append(colored("N: Next Page", "yellow"))
        options.append(colored("C: Close Book", "red"))
        
        print(" | ".join(options))
        
        choice = input(colored("Selection: ", "cyan")).strip().lower()
        return choice

    def read(self):
        if self.text:
            cprint(f"{self.player.name} begins reading...", color="cyan")
            time.sleep(0.5)
            
            # Check if text is long enough to paginate (threshold: ~600 chars)
            if len(self.text) > 600:
                pages = self._paginate_text(self.text)
                current_page = 1
                
                while True:
                    self._display_page(pages[current_page - 1], current_page, len(pages))
                    choice = self._show_page_navigation(current_page, len(pages))
                    
                    if choice in ('p', 'prev', 'previous') and current_page > 1:
                        current_page -= 1
                    elif choice in ('n', 'next') and current_page < len(pages):
                        current_page += 1
                    elif choice in ('c', 'close', 'x', 'exit'):
                        cprint(f"{self.player.name} closes the book.", "cyan")
                        break
                    else:
                        cprint("Invalid choice. Please try again.", "red")
                        time.sleep(1)
            else:
                # Short text - just print it normally
                functions.print_slow(self.text, speed="fast")
                functions.await_input()
        else:
            print(self.description)

        if self.event:
            time.sleep(0.5)
            self.event.process()
            if not getattr(self.event, 'repeat', False):
                self.event = None
            functions.await_input()
