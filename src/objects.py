from __future__ import annotations
import random
import time
import src.states as states
from src.narration import colored, cprint, narrate

import src.functions as functions
from src.player import Player
from src.tiles import MapTile
from src.events import Event  # noqa; This is used in type hints
from src.items import Item  # noqa; This is used in type hints

#####
# These are objects that exist on tiles as opposed to items carried by the player
#####


class Object:
    def __init__(
        self,
        name,
        description,
        tile=None,
        player=None,
        hidden=False,
        hide_factor=0,
        idle_message=" is here.",
        discovery_message="something interesting.",
        aliases=None,
    ):
        self.name = name
        self.description = description
        self.idle_message = idle_message
        self.hidden = hidden
        self.hide_factor = hide_factor
        self.discovery_message = discovery_message
        self.announce = self.idle_message
        self.aliases = aliases or []
        self.keywords = (
            []
        )  # action keywords to hook up an arbitrary command like "press" for a switch
        self.action_aliases = []  # Keywords that are aliases for other primary actions
        self.events = (
            []
        )  # a list of events that occur when the player interacts with the object.
        # Events with "repeat" will persist.
        self.tile = tile
        self.player = player

    def spawn_event(self, event_type, player, tile, params, repeat=False):
        event_cls = functions.seek_class(event_type, "story")
        event = functions.instantiate_event(
            event_cls, player, tile, params=params, repeat=repeat
        )
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

    def __init__(self, player, tile, params=None, description=None):
        if description is not None:
            # Programmatic construction: description passed directly as a string.
            desc_text = description
            end_mark = ""
        else:
            # Legacy construction from map-file params list.
            if params is None:
                raise ValueError("TileDescription requires either description or params")
            param_list = params[2:]
            last_param = param_list[-1]
            if (
                last_param[-1] == "~"
            ):  # Tilde is used to replace the end period when parsing the object from the map
                param_list[-1] = last_param[:-1]  # Remove the tilde
                end_mark = "."
            else:
                end_mark = ""
            desc_text = ".".join(param_list)
        word_list = desc_text.split(" ")
        last_word = word_list[-1]
        word_list[-1] = (
            last_word + end_mark
        )  # adds the last bit of punctuation if it's a period
        lines = []
        temp_line = word_list[0]
        for word in word_list[1:]:
            if len(temp_line) < (104 - len(word)):
                temp_line += " " + word
            else:
                lines.append(temp_line)
                temp_line = word
        lines.append(temp_line)
        for i, v in enumerate(lines):
            lines[i] = "        " + v + "\n"
        description = colored("".join(lines), "cyan")
        idle_message = description
        super().__init__(
            name="null",
            description=description,
            hidden=False,
            hide_factor=0,
            idle_message=idle_message,
            discovery_message="",
            player=player,
            tile=tile,
        )


class WallSwitch(Object):
    """
    A wall switch that does something when pressed.
    """

    def __init__(self, player, tile, params=None, position: bool = False):
        description = "A small depression in the wall. You may be able to PRESS on it."
        super().__init__(
            name="Wall Depression",
            description=description,
            idle_message="There's a small depression in the wall.",
            discovery_message="a small depression in the wall!",
            player=player,
            tile=tile,
            aliases=["depression", "small depression"],
        )
        self.position: bool = position  # False is unpressed, True is pressed
        self.event_on = None
        self.event_off = None
        self.keywords.append("press")
        self.action_aliases.extend(["touch", "push"])
        self.keywords.extend(self.action_aliases)

        if params:
            for thing in params:
                # account for the events associated with this switch. Max of 2 events.
                # The first event, in order of index, is tied to toggling the switch ON.
                # The second is tied to an OFF toggle.
                if thing[0] == "!":
                    param = thing.replace("!", "")
                    p_list = param.split(":")
                    repeat = False
                    event_type = p_list.pop(0)
                    for setting in p_list:
                        if setting == "r":
                            repeat = True
                            p_list.remove(setting)
                            continue
                    # use adapter for backward compatible signature handling
                    event_cls = functions.seek_class(event_type, "story")
                    event = functions.instantiate_event(
                        event_cls,
                        player,
                        tile,
                        params=(p_list if p_list else None),
                        repeat=repeat,
                    )
                    if self.event_on is None:
                        self.event_on = event
                    else:
                        self.event_off = event

    def press(self):
        narrate("Jean hears a faint 'click.'")
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

    def __init__(
        self,
        player: Player,
        tile: MapTile,
        description: str = "Words scratched into the wall."
        " Unfortunately, the inscription is too worn to be decipherable.",
        text: str = None,
    ):
        super().__init__(
            name="Inscription",
            description=description,
            hidden=False,
            hide_factor=0,
            idle_message="There appears to be some words inscribed in the wall.",
            discovery_message="some words etched into the wall!",
            player=player,
            tile=tile,
            aliases=["words inscribed", "inscription", "words etched"],
        )
        self.events = []
        # Ensure keywords are always properly set
        self.keywords = ["read", "examine"]
        self.text = text

    def read(self):
        if self.text:
            if self.player and hasattr(self.player, 'name'):
                cprint(f"{self.player.name} begins reading...", color="cyan")
            else:
                cprint("You begin reading...", color="cyan")
            functions.print_slow(self.text, speed="fast")
            functions.await_input()
        else:
            narrate(self.description)

    def examine(self):
        # Alias of read
        self.read()


class Container(Object):
    """
    A generic container that may contain items. Superclass
    NOTE: If you ever make it so items can be added to an existing container post-spawn, run the stack_items method
    """

    # Class constants for better performance and memory usage
    _POSSIBLE_STATES = ("closed", "opened")
    _DEFAULT_KEYWORDS = [
        "open",
        "unlock",
        "loot",
        "check",
        "view",
        "examine",
        "inspect",
        "peruse",
    ]

    @property
    def start_open(self) -> bool:
        """Indicates whether the container should start opened.
        Setting this property updates the container's public state and locked flag so
        that when a Container instance is later created from serialized data (where
        start_open may be written as an attribute after __init__), the container's
        state correctly reflects that attribute.
        """
        return getattr(self, "_start_open", False)

    @start_open.setter
    def start_open(self, value: bool):
        self._start_open = bool(value)
        # Ensure state matches the boolean flag
        self.state = (
            self._POSSIBLE_STATES[1] if self._start_open else self._POSSIBLE_STATES[0]
        )
        # If a container starts open, it cannot be locked
        if self._start_open:
            try:
                # Only override locked if attribute exists or when starting open
                self.locked = False
            except Exception:
                # ignore attribute issues during early init
                pass

    def __init__(
        self,
        name: str = "Container",
        description: str = "A container. There may be something inside.",
        hidden: bool = False,
        hide_factor: int = 0,
        start_open: bool = False,
        idle_message: str = "A container is sitting here.",
        discovery_message: str = " a container!",
        player: Player = None,
        tile: MapTile = None,
        nickname: str = "container",
        locked: bool = False,
        inventory: list["Item"] = None,
        events: list["Event"] = None,
        merchant: object = "",
        items: list["Item"] = None,
        allowed_subtypes: list[type[Item]] = None,
        stock_count: int = 10,
    ):
        """Accept both 'items' (legacy/tests) and 'inventory'. Normalize merchant to a name when possible.
        Also accept 'allowed_subtypes' and expose as allowed_item_types (list of types).
        """
        # Normalize inventory parameter: accept items alias for tests/tools
        inv = (
            inventory if inventory is not None else (items if items is not None else [])
        )
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
            self.merchant = merchant.name if hasattr(merchant, "name") else merchant
        except Exception:
            self.merchant = merchant
        # allowed_subtypes may be provided as tuple/list of types; default to Item if falsy
        self.allowed_item_types = list(allowed_subtypes) if allowed_subtypes else [Item]
        self.stock_count = stock_count  # Maximum number of items the container should hold (for shop logic)
        self.inventory = inv if inv else []

        aliases = [nickname, name.lower()]
        super().__init__(
            name=name,
            description=description,
            hidden=hidden,
            hide_factor=hide_factor,
            idle_message=idle_message,
            discovery_message=discovery_message,
            player=player,
            tile=tile,
            aliases=aliases,
        )

        # Extend events list efficiently if events provided
        if events:
            self.events.extend(events)

        # Add keywords efficiently
        self.keywords.extend(["loot", "take_all"])

        # Add conditional keywords based on state
        if self.locked:
            if "unlock" not in self.keywords:
                self.keywords.append("unlock")
        elif self.state == "closed":
            if "open" not in self.keywords:
                self.keywords.append("open")

        self.action_aliases.extend(["check", "view", "examine", "inspect", "peruse"])
        self.keywords.extend(self.action_aliases)

        self.process_events()  # process initial events (triggers labeled "auto")
        self.stack_items()

    def refresh_description(self):
        """Optimized description refresh using f-strings and join for better performance"""
        if self.state == "closed":
            self.description = f"A {self.nickname} which may or may not have things inside. You can try to UNLOCK (if locked), OPEN, or LOOT it."
        elif self.inventory:
            item_descriptions = []
            for item in self.inventory:
                if isinstance(item, dict):
                    # Improperly deserialized item — use dict values as fallback
                    desc = item.get("description", item.get("name", "unknown item"))
                else:
                    desc = getattr(item, "description", str(item))
                item_descriptions.append(desc)
            self.description = (
                f"A {self.nickname}. Inside are the following things: \n\n"
                + "\n".join(item_descriptions)
            )
        else:
            self.description = f"A {self.nickname}. It's empty. Very sorry."

    def unlock(self):
        """Optimized unlock method with early return and f-string formatting. Supports both direct object reference and nickname-based key matching."""
        if self.state != "closed":
            narrate("Jean can't unlock something that's already open!")
            return

        # Search for a matching key (either by direct object reference or by nickname)
        matching_key = next(
            (
                key
                for key in self.player.inventory
                if hasattr(key, "lock")
                and (
                    key.lock == self
                    or (
                        hasattr(key, "lock_nickname")
                        and hasattr(self, "nickname")
                        and key.lock_nickname == self.nickname
                    )
                )
            ),
            None,
        )

        if matching_key:
            self.locked = False
            if "unlock" in self.keywords:
                self.keywords.remove("unlock")
            if "open" not in self.keywords and self.state == "closed":
                self.keywords.append("open")
            cprint(
                f"Jean uses {matching_key.name} to unlock the {self.name}.",
                "green",
            )
        else:
            cprint("Jean couldn't find a matching key.", "red")

    def open(self):
        """Optimized open method with f-string formatting"""
        if self.locked:
            narrate(
                f"Jean pulls on the lid of the {self.nickname} to no avail. It's locked."
            )
            return

        if self.state == "closed":
            narrate(f"The {self.nickname} creaks eerily.")
            time.sleep(0.5)
            narrate("The lid lifts back on the hinge, revealing the contents inside.")
            self.revealed = True
            self.state = "opened"
            if "open" in self.keywords:
                self.keywords.remove("open")
            self.refresh_description()
            self.process_events()
        else:
            narrate(
                f"The {self.nickname} is already open. You should VIEW or LOOT it to see what's inside."
            )

    def take_all(self, player):
        """
        Transfer all items from container to player.
        """
        if self.state == "closed":
            self.open()

        if self.state != "opened":
            narrate(f"The {self.nickname} must be opened before you can take items from it.")
            return

        from src.inventory_utils import transfer_item

        if not self.inventory:
            narrate(f"The {self.nickname} is already empty.")
            return

        # Snapshot inventory since transfer_item modifies it
        snapshot = self.inventory[:]
        taken_labels = []
        for item in snapshot:
            qty = getattr(item, "count", 1)
            transfer_item(self, player, item, qty)
            label = f"{qty}× {item.name}" if qty > 1 else item.name
            taken_labels.append(label)

        if taken_labels:
            narrate(f"Jean takes {', '.join(taken_labels)}.")
        self.refresh_description()
        self.process_events()

    def loot(self):
        """
        Open the container so its contents are revealed.

        Item selection and transfer are driven by the structured
        ``events.LootEvent`` (created by
        ``GameService.interact_with_target``) for the web client. This method
        only ensures the container is open; it no longer launches a terminal
        interface.
        """
        if self.state == "closed":
            self.open()

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
            # TODO: Test this and make sure events process properly
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
            if (
                not hasattr(master_item, "count")
                or master_item.__class__ in processed_classes
            ):
                continue

            processed_classes.add(master_item.__class__)

            # Find all duplicates of this item type in one pass
            for j in range(i + 1, len(self.inventory)):
                duplicate_item = self.inventory[j]
                if (
                    hasattr(duplicate_item, "count")
                    and master_item.__class__ == duplicate_item.__class__
                ):
                    master_item.count += (
                        duplicate_item.count
                    )  # noqa; attribute guaranteed in conditional
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
    _ann = Container.__init__.__annotations__.get("allowed_subtypes")  # type: ignore[attr-defined]
    if isinstance(_ann, str):
        # Rebind with concrete evaluated type
        from src.items import (
            Item as _Item,
        )  # local import to avoid re-export side effects

        Container.__init__.__annotations__["allowed_subtypes"] = list[type[_Item]]  # type: ignore[index]
except Exception:
    pass


class Crate(Container):
    """
    This is meant to be a merchant crate with all merchandise and a stock count.
    The purpose of this object is to be a convenient, predefined container for rapid map creation.
    """

    def __init__(
        self,
        player,
        tile,
        events: list["Event"] = None,
        merchant: object = "",
        allowed_subtypes: list[type[Item]] = None,
        stock_count: int = 20,
    ):
        description = "A large wooden crate containing merchandise."
        super().__init__(
            name="Crate",
            description=description,
            idle_message="A large wooden crate is here.",
            events=events,
            merchant=merchant,
            allowed_subtypes=allowed_subtypes,
            discovery_message=" a large wooden crate!",
            player=player,
            tile=tile,
            nickname="crate",
            locked=False,
            start_open=True,
            stock_count=stock_count,
        )
        if "open" in self.keywords:
            self.keywords.remove("open")
        if "unlock" in self.keywords:
            self.keywords.remove("unlock")


class Shelf(Container):
    """
    This is meant to be a merchant shelf with all merchandise and a stock count.
    The purpose of this object is to be a convenient, predefined container for rapid map creation.
    """

    def __init__(
        self,
        player,
        tile,
        events: list["Event"] = None,
        merchant: object = "",
        allowed_subtypes: list[type[Item]] = None,
        stock_count: int = 10,
    ):
        description = "A practical wooden shelf displaying merchandise."
        super().__init__(
            name="Shelf",
            description=description,
            idle_message="A shelf displaying merchandise is here.",
            events=events,
            merchant=merchant,
            allowed_subtypes=allowed_subtypes,
            discovery_message=" a wooden shelf!",
            player=player,
            tile=tile,
            nickname="shelf",
            locked=False,
            start_open=True,
            stock_count=stock_count,
        )
        if "open" in self.keywords:
            self.keywords.remove("open")
        if "unlock" in self.keywords:
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

    def __init__(self, player=None, tile=None, params=None):
        description = "A beautiful shrine depicting a variety of saints praying to God."
        super().__init__(
            name="Shrine",
            description=description,
            idle_message="There is an ornate shrine here.",
            discovery_message=" a shrine!",
            player=player,
            tile=tile,
        )
        self.event = None
        self.keywords.append("pray")

        if params:
            for thing in params:
                # account for the events associated with this object. Max of 1 event.
                # Triggers after interacting with the shrine.
                if thing[0] == "!":
                    param = thing.replace("!", "")
                    p_list = param.split(":")
                    repeat = False
                    event_type = p_list.pop(0)
                    for setting in p_list:
                        if setting == "r":
                            repeat = True
                            p_list.remove(setting)
                            continue
                    event_cls = functions.seek_class(event_type, "story")
                    self.event = functions.instantiate_event(
                        event_cls,
                        player,
                        tile,
                        params=(p_list if p_list else None),
                        repeat=repeat,
                    )

    def pray(self, player):
        narrate("Jean kneels down and begins to pray for intercession.")
        time.sleep(random.randint(3, 10))

        # Robustly handle missing prayer_msg
        prayer_messages = getattr(player, "prayer_msg", ["Jean prays silently."])
        selection = random.randint(0, len(prayer_messages) - 1)
        narrate(prayer_messages[selection])
        if getattr(self, "event", None) is not None:
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
        super().__init__(
            name="HealingSpring",
            description=description,
            idle_message="There is a small spring bubbling here.",
            discovery_message=" a healing spring!",
            player=player,
            tile=tile,
        )
        self.event = None
        self.keywords.append("drink")
        self.keywords.append("clean")
        self.keywords.append("wash")

        if params:
            for thing in params:
                # account for the events associated with this object. Max of 1 event.
                # Triggers after interacting with the object.
                if thing[0] == "!":
                    param = thing.replace("!", "")
                    p_list = param.split(":")
                    repeat = False
                    event_type = p_list.pop(0)
                    for setting in p_list:
                        if setting == "r":
                            repeat = True
                            p_list.remove(setting)
                            continue
                    event_cls = functions.seek_class(event_type, "story")
                    self.event = functions.instantiate_event(
                        event_cls,
                        player,
                        tile,
                        params=(p_list if p_list else None),
                        repeat=repeat,
                    )

    def drink(self, player):
        narrate(
            "Jean bends down to the water and, cupping it in his hands, begins to sip eagerly."
        )
        time.sleep(2)
        narrate("The water is cool and refreshing as it goes down his throat.")
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
        narrate("Jean summarily begins washing himself in the cool water of the spring.")
        time.sleep(2)
        narrate(
            "Jean closes his eyes for a moment, enjoying the feeling of simple cleanliness."
        )
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

    def __init__(
        self,
        player: Player,
        tile: MapTile,
        events_before: list["Event"] = None,
        events_after: list["Event"] = None,
        teleport_map: str = None,
        teleport_tile: tuple = None,
        persist: bool = True,
        hidden: bool = False,
        hide_factor: int = 0,
        is_shop_exit: bool = False,
        passthrough: bool = False,
        name: str = "Passageway",
        description: str = "A passageway leading elsewhere is here.",
        idle_message: str = "There is a passageway here.",
        discovery_message: str = " a passageway!",
    ):
        aliases = [name.lower(), "passage"]
        super().__init__(
            name=name,
            description=description,
            idle_message=idle_message,
            hidden=hidden,
            hide_factor=hide_factor,
            discovery_message=discovery_message,
            player=player,
            tile=tile,
            aliases=aliases,
        )
        self.keywords.append("enter")
        self.action_aliases.extend(["go", "leave", "exit"])
        self.keywords.extend(self.action_aliases)
        _name_words = name.lower().replace("'s", "").replace("'", "").split()
        for _word in _name_words:
            if len(_word) > 3 and _word.isalpha() and not hasattr(self, _word):
                setattr(self, _word, self.enter)
                self.action_aliases.append(_word)
                self.keywords.append(_word)
        self.events_before = events_before if events_before is not None else []
        self.events_after = events_after if events_after is not None else []
        self.teleport_map = teleport_map if teleport_map is not None else ""
        self.teleport_tile = teleport_tile if teleport_tile is not None else ""
        self.persist = persist  # if True, the passageway will remain after use, else
        # it will be removed from the tile after use
        # If True, the frontend skips the Interactions panel and directly executes
        # the first action (enter) when the player clicks this object.
        self.passthrough = passthrough

    def enter(self, player):
        # Drop any merchandise items immediately upon attempting to enter/teleport
        if hasattr(player, "drop_merchandise_items"):
            player.drop_merchandise_items()
        if self.events_before:
            for event in self.events_before:
                event.process()
        if self.teleport_map and self.teleport_tile:
            self._commit_teleport(player)
        else:
            narrate(
                "The passageway is not properly configured. Please contact the developer."
            )
        functions.await_input()

    def _commit_teleport(self, player):
        """Perform the actual teleport.  Called directly by CLI enter()
        or via PassagewayTransitionEvent.process() in API mode."""
        player.teleport(self.teleport_map, self.teleport_tile)
        if self.events_after:
            for event in self.events_after:
                event.process()
        if not self.persist:
            self.tile.objects_here.remove(self)

    @staticmethod
    def build_article_phrase(name):
        """Build a natural article phrase for a passageway name.

        Possessives (Jambo's Tent) are proper nouns — no article.
        Names starting with "The" strip the duplicate and preserve rest.
        Generic noun phrases (Archive Door, Tent Flap) get "the " prepended.
        """
        if "'" in name:
            return name
        if name.lower().startswith("the "):
            return f"the {name[4:]}"
        return f"the {name.lower()}"

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

    def __init__(self, player: Player, tile: MapTile, event: Event = None):
        description = "A small metal bell hangs from a short iron hook; it looks like it can be RUNG to draw attention."
        super().__init__(
            name="Market Bell",
            description=description,
            idle_message="A small bell hangs here, waiting to be rung.",
            discovery_message="a small bell mounted by a stall!",
            player=player,
            tile=tile,
        )
        self.keywords.append("ring")
        self.keywords.append("use")
        self.event = event

    def ring(self):
        """Player rings the bell. If an event is attached, process it. Otherwise provide a simple cue."""
        cprint("Jean reaches up and rings the bell.", color="cyan")
        time.sleep(0.4)
        narrate(
            "A clear, bright tone rings through the arcade, briefly carrying above the market din."
        )
        if self.event is not None:
            # process and clear non-repeat events; instantiate_event handles repeat flag behavior
            time.sleep(0.6)
            self.event.process()
            # if the event was non-repeat it will typically be consumed; mirror Shrine behavior by clearing
            try:
                if not getattr(self.event, "repeat", False):
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

    def __init__(self, player: Player, tile: MapTile, event: Event = None):
        description = (
            "A low circular fountain murmurs softly; clear water bubbles up and spills over carved stone."
            " You could probably DRINK from it or just LISTEN to the water."
        )  # noqa: E501
        super().__init__(
            name="Fountain",
            description=description,
            idle_message="A small stone fountain murmurs here.",
            discovery_message="a murmuring fountain!",
            player=player,
            tile=tile,
        )
        self.keywords.extend(["drink", "listen", "admire", "use"])
        self.event = event

    def drink(self):
        cprint(
            "Jean cups some water from the fountain and takes a cool sip.",
            "cyan",
        )
        time.sleep(0.5)
        if self.event:
            time.sleep(0.5)
            self.event.process()
            if not getattr(self.event, "repeat", False):
                self.event = None
        functions.await_input()

    def listen(self):
        narrate("Jean closes his eyes a moment, listening to the gentle splash of water.")
        functions.await_input()

    def admire(self):
        narrate("The craftsmanship of the fountain is simple but pleasant.")
        functions.await_input()

    def use(self):  # alias
        self.drink()


class StreetLantern(Object):
    """A wrought iron street lantern that can be LIGHTed or DOUSEd. Optional events may trigger on state change."""

    def __init__(
        self,
        player: Player,
        tile: MapTile,
        event_when_lighting: Event = None,
        event_when_dousing: Event = None,
        lit: bool = False,
    ):
        description = (
            "An iron street lantern stands here, its glass panes slightly clouded."
            + (
                " It is currently lit, casting a warm glow in all directions."
                if lit
                else " It is dark; maybe you could LIGHT it."
            )
        )
        super().__init__(
            name="Street Lantern",
            description=description,
            idle_message="A wrought iron street lantern stands here.",
            discovery_message="a street lantern!",
            player=player,
            tile=tile,
        )
        self.keywords.extend(["light", "douse", "extinguish", "inspect"])
        self.lit = lit
        self.event_on = event_when_lighting
        self.event_off = event_when_dousing
        self._update_description()

    def _update_description(self):
        state_text = "lit" if self.lit else "dark"
        self.description = f"An iron street lantern stands here. It is {state_text}."

    def light(self):
        if self.lit:
            narrate("The lantern is already lit.")
            return
        narrate("Jean strikes a spark and coaxes the lantern to life.")
        self.lit = True
        self._update_description()
        if self.event_on:
            self.event_on.process()
            if not getattr(self.event_on, "repeat", False):
                self.event_on = None
        functions.await_input()

    def douse(self):
        if not self.lit:
            narrate("The lantern is already dark.")
            return
        narrate("Jean shields the flame and pinches it out.")
        self.lit = False
        self._update_description()
        if self.event_off:
            self.event_off.process()
            if not getattr(self.event_off, "repeat", False):
                self.event_off = None
        functions.await_input()

    def extinguish(self):
        self.douse()

    def inspect(self):
        narrate(self.description)
        functions.await_input()


class NoticeBoard(Object):
    """A public notice board. Jean can READ posted notes. Optional single event
    triggers on first READ.
    """

    def __init__(
        self,
        player: Player,
        tile: MapTile,
        event: Event = None,
        notes: list[str] = None,
    ):
        description = "A wooden notice board stands here with a scattering of parchment scraps pinned to it."
        super().__init__(
            name="Notice Board",
            description=description,
            idle_message="A wooden notice board is here.",
            discovery_message="a notice board!",
            player=player,
            tile=tile,
        )
        self.keywords.extend(["read", "use"])
        self.notes: list[str] = (
            notes
            if notes
            else [
                "Lost: One black cat with a white spot on its chest. Answers to 'Midnight'. Reward offered.",
                "For Sale: Handmade pottery bowls, vases, and mugs. All proceeds support the local orphanage.",
                "Help Wanted: Looking for an assistant to help with daily chores and errands. Inquire within.",
                "Event: The annual Ecumerium Festival will take place next week! Music, food, and games for all ages.",
                "Notice: Please keep the market area clean. Trash bins are provided throughout the arcade.",
            ]
        )
        self.event = event
        self._read_once = False

    def read(self):
        narrate("Jean scans the various notes:")
        for note in self.notes:
            narrate(f"  - {note}")
        if self.event and (not self._read_once or getattr(self.event, "repeat", False)):
            time.sleep(0.3)
            self.event.process()
            if not getattr(self.event, "repeat", False):
                self._read_once = True
        functions.await_input()

    def use(self):
        self.read()


class PrayerCandleRack(Object):
    """A rack of small votive candles. Jean can LIGHT a candle (increments count) or PRAY. Optional single event on PRAY."""

    def __init__(
        self,
        player: Player,
        tile: MapTile,
        lit_candles: int = 0,
        event: Event = None,
    ):
        description = "A wrought rack of small votive candles. A few flicker; many are unlit."  # noqa: E501
        super().__init__(
            name="Candle Rack",
            description=description,
            idle_message="A rack of votive candles stands here.",
            discovery_message="a rack of small candles!",
            player=player,
            tile=tile,
        )
        self.keywords.extend(["light", "pray", "use"])
        self.lit_candles = lit_candles
        self.event = event

    def light(self):
        if self.lit_candles >= 20:
            narrate("All the candles are already lit.")
            functions.await_input()
            return
        self.lit_candles += 1
        narrate(f"Jean lights a small candle. ({self.lit_candles} now flicker.)")
        functions.await_input()

    def pray(self):
        narrate("Jean bows his head silently before the little flames.")
        time.sleep(5)
        narrate(
            "A strange feeling fills his chest, as if there's a tune he can't quite remember."
        )
        time.sleep(0.5)
        if getattr(self, "event", None):
            self.event.process()
            if not getattr(self.event, "repeat", False):
                self.event = None
        functions.await_input()

    def use(self):
        self.pray()


class MarketGong(Object):
    """A larger bronze gong used to signal openings or special sales. Jean can STRIKE/HIT it; optional event triggers."""

    def __init__(self, player: Player, tile: MapTile, event: Event = None):
        description = "A wide bronze gong is suspended from a stout frame. A padded mallet invites someone to STRIKE it."  # noqa: E501
        super().__init__(
            name="Market Gong",
            description=description,
            idle_message="A bronze gong hangs here, silent.",
            discovery_message="a large bronze gong!",
            player=player,
            tile=tile,
        )
        self.keywords.extend(["strike", "hit", "bang", "use"])
        self.event = event

    def strike(self):
        cprint(
            "Jean swings the mallet into the gong with a resonant BOOOONG...",
            "cyan",
        )
        time.sleep(0.7)
        narrate("The deep tone rolls outward and slowly fades.")
        time.sleep(1)
        narrate(
            "Some nearby shoppers glance over, momentarily distracted. More than a few wear a confused expression."
        )
        if self.event:
            time.sleep(0.4)
            self.event.process()
            if not getattr(self.event, "repeat", False):
                self.event = None
        functions.await_input()

    def hit(self):
        self.strike()

    def bang(self):
        self.strike()

    def use(self):
        self.strike()


class GeminateGeode(Object):
    """
    Puzzle object in the Luminous Grotto. Accepts three mineral fragments in the
    correct sequence (Azure Crystal → Amber Stone → Pale Grey Fragment) and rewards
    the EnchantedGolemitePauldron. One-use; removes itself after success.
    """

    # Each entry is (ClassName, display_name) — kept together so they can't drift apart
    _INGREDIENT_DEFS = (
        ("AzuriteGem", "Azure Crystal"),
        ("AmberStone", "Amber Stone"),
        ("PaleGreyFragment", "Pale Grey Fragment"),
    )

    def __init__(self, player: Player, tile: MapTile, params=None):
        super().__init__(
            name="Geode",
            description=(
                "A large hollow geode resting on a natural stone pedestal. "
                "Three shallow depressions are carved into its rim, each shaped to receive "
                "a single fragment. The vein colours above the depressions match the ritual "
                "sequence from the Atrium etching: blue, amber, grey."
            ),
            idle_message="A hollow geode rests on a stone pedestal here, waiting.",
            discovery_message=" a hollow geode resting on a stone pedestal!",
            player=player,
            tile=tile,
            aliases=["geode", "hollow geode", "pedestal", "stone pedestal"],
        )
        self.keywords.extend(["place", "insert", "solve", "use", "examine"])
        self.action_aliases.extend(["examine", "use"])

    def _has_ingredient(self, cls_name: str) -> bool:
        return any(
            item.__class__.__name__ == cls_name for item in self.player.inventory
        )

    def _remove_ingredient(self, cls_name: str) -> None:
        for item in list(self.player.inventory):
            if item.__class__.__name__ == cls_name:
                self.player.inventory.remove(item)
                return

    def place(self, player=None):
        """Attempt to solve the puzzle by placing the three mineral fragments."""
        if player is not None:
            self.player = player
        missing = [
            name for cls, name in self._INGREDIENT_DEFS if not self._has_ingredient(cls)
        ]
        if missing:
            narrate(f"The depressions wait. Jean is missing: {', '.join(missing)}.")
            narrate("The ritual carving in the Atrium showed the sequence clearly.")
            return
        # All three fragments present — solve the puzzle
        narrate(
            "\nJean places the blue crystal in the first depression. The vein above it pulses."
        )
        time.sleep(1)
        narrate(
            "The amber stone settles into the second. A harmonic hum begins, low and resonant."
        )
        time.sleep(1)
        narrate("The pale grey fragment locks into the third.")
        time.sleep(0.5)
        narrate("\nA sound like a struck bell fills the chamber — the geode cracks open.")
        time.sleep(1)
        narrate(
            "Inside: a stone pauldron, inlaid with the same tricolor veins as the walls. "
            "Still luminous."
        )
        time.sleep(1)
        for cls, _name in self._INGREDIENT_DEFS:
            self._remove_ingredient(cls)
        if self.tile:
            self.tile.spawn_item("EnchantedGolemitePauldron")
        if self.tile and self in self.tile.objects_here:
            self.tile.objects_here.remove(self)
        functions.await_input()

    def insert(self, player=None):
        self.place(player)

    def solve(self, player=None):
        self.place(player)

    def use(self, player=None):
        self.place(player)

    def examine(self):
        narrate(self.description)


# ═════════════════════════════════════════════════════════════════════════════
# Camp objects — eastern-descent nomad camp interactables
    # ═════════════════════════════════════════════════════════════════════════════


class Campfire(Object):
    """A campfire at the nomad camp. Can be LIT, used to WARM oneself, STOKEd, or SAT beside for a narrative moment.
    """

    def __init__(self, player=None, tile=None, lit: bool = True):
        description = (
            "A ring of stones encircling a bed of glowing embers. A thin curl of smoke "
            "rises into the evening air. You could WARM yourself, STOKE it, or just SIT "
            "and rest a while."
            if lit
            else "A ring of stones encircling a bed of cold ash. Dry kindling is stacked "
            "beside it, ready to be LIT."
        )
        super().__init__(
            name="Campfire",
            description=description,
            idle_message="A campfire burns softly here."
            if lit
            else "A cold fire ring sits here.",
            discovery_message="a campfire!",
            player=player,
            tile=tile,
            aliases=["fire", "fire ring", "campfire"],
        )
        self.lit = lit
        self.keywords.extend(["light", "warm", "stoke", "sit", "examine", "use"])
        self.action_aliases.extend([])

    def light(self):
        if self.lit:
            narrate("The fire is already burning.")
            return
        narrate("Jean kneels and strikes flint against steel. After a few sparks, the "
                "kindling catches and a small flame curls upward.")
        self.lit = True
        self.description = (
            "A ring of stones encircling a bed of glowing embers. A thin curl of smoke "
            "rises into the evening air. You could WARM yourself, STOKE it, or just SIT "
            "and rest a while."
        )
        self.idle_message = "A campfire burns softly here."
        functions.await_input()

    def warm(self):
        if not self.lit:
            narrate("The fire is cold. Jean would need to LIGHT it first.")
            return
        narrate("Jean holds his hands over the flames, letting the warmth seep "
                "into his fingers. The heat presses against his face, and for a "
                "moment the road feels farther away than it is.")
        functions.await_input()

    def stoke(self):
        if not self.lit:
            narrate("The fire is cold. Jean would need to LIGHT it first.")
            return
        narrate("Jean nudges a fresh log into the embers. Sparks swirl upward and the "
                "flames brighten with a low, satisfied crackle.")
        functions.await_input()

    def sit(self):
        if not self.lit:
            narrate("Jean sits on one of the stones ringing the cold fire pit. The air "
                    "is still; the river murmurs somewhere beyond the camp. It's not "
                    "unpleasant, exactly. Just quiet.")
            return
        narrate("Jean settles onto a smooth stone near the fire. The heat presses "
                "against his face. Beyond the ring of light, the camp continues its "
                "quiet rhythms — someone mending a strap, someone stirring a pot, "
                "the river running below it all.")
        functions.await_input()

    def examine(self):
        narrate(self.description)

    def use(self):
        if self.lit:
            self.warm()
        else:
            self.light()


class WaterBarrel(Object):
    """A wooden barrel of fresh river water at the camp. Jean can DRINK to
    restore a small amount of HP. Unlimited uses.
    """

    def __init__(self, player=None, tile=None):
        description = (
            "A sturdy wooden barrel, half-sunk into the ground near the fire ring. "
            "A dipper hangs from its rim. The water inside is cool and clear — drawn "
            "from the river upstream and left to settle. You could DRINK from it."
        )
        super().__init__(
            name="Water Barrel",
            description=description,
            idle_message="A barrel of fresh water stands near the fire ring.",
            discovery_message="a barrel of fresh water!",
            player=player,
            tile=tile,
            aliases=["barrel", "water", "water barrel"],
        )
        self.keywords.extend(["drink", "examine", "use"])
        self.action_aliases.extend([])

    def drink(self):
        if self.player is None:
            narrate("Jean dips the ladle and drinks. The water is cool and clean.")
            return
        hp_restored = min(10, self.player.maxhp - self.player.hp)
        if hp_restored <= 0:
            narrate("Jean drinks deeply from the dipper. The water is cool and "
                    "refreshing, but he doesn't need any more right now.")
            return
        self.player.hp += hp_restored
        cprint(f"Jean drinks from the water barrel. (+{hp_restored} HP)", "green")
        functions.await_input()


    def examine(self):
        narrate(self.description)

    def use(self):
        self.drink()


class WashingBasin(Object):
    """A simple basin of water for washing. Jean can WASH or CLEAN himself,
    applying the Clean status effect. Unlimited uses.
    """

    def __init__(self, player=None, tile=None):
        description = (
            "A wide, shallow basin carved from a hollowed log, filled with water "
            "that catches the firelight. A scrap of rough soap rests on the rim and "
            "a cloth hangs from a peg beside it. You could WASH or CLEAN up here."
        )
        super().__init__(
            name="Washing Basin",
            description=description,
            idle_message="A washing basin sits near the edge of the camp.",
            discovery_message="a washing basin!",
            player=player,
            tile=tile,
            aliases=["basin", "wash basin", "washing basin"],
        )
        self.keywords.extend(["wash", "clean", "examine", "use"])
        self.action_aliases.extend([])

    def wash(self):
        if self.player is None:
            narrate("Jean splashes water on his face. The cold cuts through the "
                    "grime of the road.")
            return
        narrate("Jean scrubs the road dust from his hands and face. The water "
                "darkens with silt. When he's done, he feels lighter — not clean "
                "in the way a bathhouse makes you clean, but clean enough.")
        self.player.apply_state(states.Clean(self.player))
        cprint("Jean now has Clean status!", "green")
        functions.await_input()

    def clean(self):
        self.wash()

    def examine(self):
        narrate(self.description)

    def use(self):
        self.wash()


class DryingRack(Object):
    """A wooden rack where nomads dry herbs, fish, and strips of meat. Jean can
    CHECK what's drying or TAKE a small consumable item. Refills every 50 game ticks.
    """

    # What might be found drying on the rack
    _DRIED_GOODS = [
        ("Dried Fish", "A strip of river fish, salted and dried to a leathery "
         "chew. Not delicious, but it keeps."),
        ("Dried Meat", "A strip of cured meat, dark and firm. Traveler's fare."),
        ("Dried Herbs", "A bundle of aromatic herbs tied with twine. They smell "
         "of the foothills — sage, maybe, and something sharper."),
        ("Dried Berries", "A small pouch of shriveled berries. Chewy and tart "
         "enough to make your jaw tighten."),
    ]

    def __init__(self, player=None, tile=None):
        description = (
            "A wooden frame strung with lengths of twine, draped with strips "
            "of something dark and fragrant drying slowly above the fire's reach. "
            "You could CHECK what's there, or TAKE something if it's ready."
        )
        super().__init__(
            name="Drying Rack",
            description=description,
            idle_message="A drying rack stands near the fire, laden with provisions.",
            discovery_message="a drying rack laden with goods!",
            player=player,
            tile=tile,
            aliases=["rack", "drying rack"],
        )
        self.keywords.extend(["check", "take", "loot", "examine", "use"])
        self.action_aliases.extend(["loot"])
        self._last_take_tick = -50  # Start ready
        self._current_item = None

    def _get_tick(self):
        """Get current game tick, or 0 if unavailable."""
        try:
            return getattr(getattr(self.player, "universe", None), "game_tick", 0) or 0
        except Exception:
            return 0

    def _refill_if_needed(self):
        tick = self._get_tick()
        if tick - self._last_take_tick >= 50:
            self._current_item = random.choice(self._DRIED_GOODS)
        return self._current_item is not None

    def check(self):
        item = self._refill_if_needed()
        if item is None:
            narrate("The drying rack is bare. Give it some time.")
            return
        name, desc = item
        narrate(f"Jean checks the drying rack. There's {name} here — {desc}")

    def take(self):
        if self.player is None:
            narrate("Jean takes something from the drying rack.")
            return
        item = self._refill_if_needed()
        if item is None:
            narrate("The drying rack is bare. Nothing ready to take yet.")
            return
        name, desc = item
        # Spawn the item on the tile for the player to pick up
        narrate(f"Jean takes {name} from the drying rack. {desc}")
        if self.tile:
            self.tile.spawn_item("Restorative")
        self._last_take_tick = self._get_tick()
        self._current_item = None
        functions.await_input()

    def loot(self):
        self.take()

    def examine(self):
        self.check()

    def use(self):
        self.take()


class SupplyTent(Container):
    """A small canvas tent where the nomads keep shared camp supplies. Locked;
    can be opened with a key held by Devet or Mara. Contains basic provisions.
    """

    def __init__(self, player=None, tile=None):
        description = (
            "A low canvas tent staked at the camp's edge, its flap tied shut with "
            "a length of hemp cord. A faded mark on the canvas suggests it holds "
            "shared supplies — bandages, rations, the kind of things a camp keeps "
            "for when they're needed."
        )
        super().__init__(
            name="Supply Tent",
            description=description,
            idle_message="A small supply tent is staked at the camp's edge.",
            discovery_message="a small supply tent!",
            player=player,
            tile=tile,
            nickname="supply tent",
            locked=True,
            start_open=False,
        )
        self.aliases.extend(["tent", "supply tent"])

    def open(self):
        if self.locked:
            narrate("Jean tugs at the tent flap. The hemp cord holds fast — "
                    "it's tied from the inside. Someone with access to the camp "
                    "would have the key.")
            return
        super().open()


class RiverCrossingMarker(Object):
    """A weathered wooden post marking the river ford. Jean can READ the
    carved directions or EXAMINE it more closely. Pure lore object.
    """

    _MARKER_TEXT = [
        "The post is old but the carving is deep: CROSS AT DAWN WHEN CURRENT "
        "IS LOW. Below it, in a different hand: Mara knows the timing. Ask her.",
        "Carved into the wood: STAY ON THE MARKED LINE. CURRENT SHIFTS PAST "
        "MIDDAY. Below: If the rope is gone, wait. Devet will restring it.",
        "The marker reads: WEST BANK IS UNSTABLE AFTER RAIN. TEST THE GROUND "
        "BEFORE STEPPING OFF. Someone has added in charcoal: Especially in spring.",
        "Weathered letters spell out: FIVE SECONDS BETWEEN WAVES MEANS CROSS. "
        "THREE MEANS WAIT. Beneath it: Gorran counts the seconds. He's never wrong.",
    ]

    def __init__(self, player=None, tile=None):
        description = (
            "A weathered wooden post driven deep into the riverbank, its surface "
            "cross-hatched with carved directions and years of weather. You could "
            "READ the markings or EXAMINE the post."
        )
        super().__init__(
            name="River Crossing Marker",
            description=description,
            idle_message="A weathered marker post stands at the river's edge.",
            discovery_message="a weathered marker post!",
            player=player,
            tile=tile,
            aliases=["marker", "post", "river marker", "crossing marker"],
        )
        self.keywords.extend(["read", "examine", "use"])
        self.action_aliases.extend([])

    def read(self):
        narrate(random.choice(self._MARKER_TEXT))
        functions.await_input()

    def examine(self):
        self.read()

    def use(self):
        self.read()


class CampBanner(Object):
    """A cloth banner hanging from a pole at the nomad camp, bearing the
    markings of the group that travels these routes. Jean can EXAMINE or READ
    the markings. Pure lore object.
    """

    _BANNER_LINES = [
        "The banner is a long strip of undyed wool, its edges frayed by wind. "
        "Three symbols are stitched across it in dark thread: a river, a rising "
        "sun, and what might be an open hand. The stitching is uneven — many "
        "different hands have worked on it over the years.",
        "The cloth is faded but the design is clear: a series of concentric "
        "circles, each one stitched in a different color of thread, all of them "
        "bleached by sun until the differences are almost gone. At the center, "
        "a single knot of undyed wool. The meaning isn't obvious, but the care "
        "taken is.",
        "Jean studies the banner. It bears the mark of the eastern routes — "
        "a stylized river forking into three paths, with a small stitched star "
        "at the end of each one. Some of the stars have names embroidered beside "
        "them in tiny, careful letters. Most are too worn to read.",
        "The banner is newer than the post it hangs from. The cloth is still "
        "supple, the dyes still holding. It shows a caravan silhouette against "
        "a rising sun, and below it, a single word in a script Jean doesn't "
        "recognize. The stitching is recent — someone in this camp made this.",
    ]

    def __init__(self, player=None, tile=None):
        description = (
            "A long strip of cloth hangs from a weathered pole at the camp's "
            "center, stirring faintly in the river breeze. Its markings are "
            "visible but faded. You could EXAMINE the banner or READ its markings."
        )
        super().__init__(
            name="Camp Banner",
            description=description,
            idle_message="A cloth banner hangs from a pole at the camp's center.",
            discovery_message="a cloth banner stirring in the breeze!",
            player=player,
            tile=tile,
            aliases=["banner", "camp banner", "cloth", "flag"],
        )
        self.keywords.extend(["examine", "read", "look", "use"])
        self.action_aliases.extend(["read", "look"])

    def examine(self):
        narrate(random.choice(self._BANNER_LINES))
        functions.await_input()

    def read(self):
        self.examine()

    def look(self):
        self.examine()

    def use(self):
        self.examine()


class TravelersLogbook(Object):
    """A worn leather-bound book where travelers record their crossings. Jean
    can READ entries from past travelers. Pure lore, flavor text.
    """

    _ENTRIES = [
        "The ink is faded but legible: 'Crossed at dawn. River lower than "
        "expected. The camp on the east side had good water and a fire going. "
        "Didn't catch the name of the woman who pointed out the ford. She knew "
        "the river like a road.' Signed with a symbol, not a name.",
        "A cramped, hurried hand: 'Three of us crossed today. Current was "
        "strong — lost a pack at the bend. Devet gave us dried fish and didn't "
        "ask for anything. Good man. The Badlands start to feel real after this.'",
        "Someone has written in careful, deliberate letters: 'I have crossed "
        "this river four times now. Each time I tell myself it's the last. Each "
        "time the road brings me back. The water doesn't remember you, but you "
        "remember the water.' No signature.",
        "A single line, pressed hard into the page: 'Going west. Not coming "
        "back. Tell Mara thanks for the fuel.' The rest of the page is blank.",
        "An entry in a looping, unhurried script: 'The girl at the camp — Liss — "
        "asked me if I'd seen the stone one. I told her yes. She asked what he "
        "eats. I said I didn't know. She seemed disappointed but not surprised. "
        "Children on the road are different.'",
        "A page that's been written on, crossed out, and written on again. The "
        "final version reads: 'Crossed. Alive. Moving on.' Below it, someone "
        "else has added in different ink: 'That's the spirit.'",
        "Several names are listed in a column, each with a date and a destination "
        "— some east, some west. The list goes back months. Near the bottom, a "
        "line reads: 'If you're reading this and you're afraid, you're paying "
        "attention. Cross anyway.' No name.",
        "A child's drawing in the margin: a stick figure with what might be a "
        "sword, and beside it a larger figure made of circles. Underneath, an "
        "adult has written: 'He wanted to draw the Golemite. I told him to use "
        "the margin.'",
    ]

    def __init__(self, player=None, tile=None):
        description = (
            "A worn leather-bound book resting on a flat stone near the fire ring, "
            "its pages swollen with river damp and years of handling. A stub of "
            "charcoal lies beside it. You could READ the travelers' entries."
        )
        super().__init__(
            name="Traveler's Logbook",
            description=description,
            idle_message="A worn logbook rests on a flat stone near the fire.",
            discovery_message="a traveler's logbook!",
            player=player,
            tile=tile,
            aliases=["logbook", "book", "ledger", "traveler's logbook"],
        )
        self.keywords.extend(["read", "examine", "use"])
        self.action_aliases.extend([])

    def read(self):
        narrate(random.choice(self._ENTRIES))
        functions.await_input()

    def examine(self):
        self.read()

    def use(self):
        self.read()
