import random, time
import functions, states
from neotermcolor import colored, cprint


#####
# These are objects that exist on tiles as opposed to items carried by the player
#####


class Object:
    def __init__(self, name, description, tile=None, player=None, hidden=False, hide_factor=0,
                 idle_message=' is here.',
                 discovery_message='something interesting.', target=None):
        self.name = name
        self.description = description
        self.idle_message = idle_message
        self.hidden = hidden
        self.hide_factor = hide_factor
        self.discovery_message = discovery_message
        self.announce = self.idle_message
        self.keywords = []  # action keywords to hook up an arbitrary command like "press" for a switch
        self.events = []  # a list of events that occur when the player interacts with the object. Events with "repeat" will persist.
        self.tile = tile
        self.player = player

    def spawn_event(self, event_type, player, tile, params, repeat=False):
        event = functions.seek_class(event_type, "story")(player, tile, params, repeat)
        if event != "":
            self.events.append(event)
            return event


class TileDescription(Object):
    '''
    Adds to the description of the tile. Has no other function. The existence of this object allows tile descriptions
    to be dynamically changed.
    '''

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
    '''
    A wall switch that does something when pressed.
    '''

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
                event = functions.seek_class(event_type, "story")(player, tile, params, repeat)
                if self.event_on is None:
                    self.event_on = event
                else:
                    self.event_off = event

    def press(self, player):
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
    '''
    An inscription (typically visible) that can be looked at.
    '''

    def __init__(self, player, tile, params=None):
        description = "Words scratched into the wall. Unfortunately, the inscription is too worn to be decipherable."
        super().__init__(name="Inscription", description=description, hidden=False, hide_factor=0,
                         idle_message="There appears to be some words inscribed in the wall.",
                         discovery_message="some words etched into the wall!", player=player, tile=tile)
        self.events = []

        if 'v0' in params:  # if there is a version declaration, change the description, else keep it generic
            self.description = "The inscription reads: 'EZ 41:1, LK 11:9-10, JL 2:7'"


class Container(Object):
    '''
    A generic container that may contain items. Superclass
    NOTE: If you ever make it so items can be added to an existing container post-spawn, run the stack_items method
    '''

    def __init__(self, name, description, hidden, hide_factor, idle_message, discovery_message, player, tile, nickname,
                 params=None):
        self.nickname = nickname

        super().__init__(name=name, description=description, hidden=hidden, hide_factor=hide_factor,
                         idle_message=idle_message,
                         discovery_message=discovery_message, player=player, tile=tile)
        self.possible_states = ("closed", "opened")
        self.state = self.possible_states[0]  # start closed
        self.contents = []
        self.revealed = False
        if '%locked' in params:
            self.locked = True
            alias = "unknown"
            for thing in params:
                if '^' in thing:
                    alias = thing[1:]
                    break
            self.player.universe.locked_chests.append((self, alias))
        else:
            self.locked = False
        for thing in params:  # put items in the chest or attach events based on what's declared in params
            if thing[0] == '#':
                param = thing.replace('#', '')
                p_list = param.split(':')
                item_type = p_list[0]
                amt = functions.randomize_amount(p_list[1])  # only randomizes if amt is in the form "r##-##"
                gold_amt = 0
                if p_list[0] == 'Gold':
                    gold_amt = amt
                    amt = 1
                for i in range(0, amt):
                    if item_type == 'Gold':
                        item = getattr(__import__('items'), item_type)(gold_amt)
                    else:
                        item = getattr(__import__('items'), item_type)()
                    self.contents.append(item)
            if thing[0] == '!':
                param = thing.replace('!', '')
                p_list = param.split(':')
                repeat = False
                #trigger = 'auto'
                event_type = p_list.pop(0)
                for setting in p_list:
                    if setting == 'r':
                        repeat = True
                        p_list.remove(setting)
                        continue
                event = self.spawn_event(event_type, player, tile, p_list, repeat)
                self.events.append(event)

        self.keywords.append('open')
        self.keywords.append('unlock')
        self.keywords.append('loot')
        self.process_events()  # process initial events (triggers labeled "auto")
        self.stack_items()

    def refresh_description(self):
        if self.state == "closed":
            self.description = "A " + self.nickname + " which may or may not have things inside. You can try to UNLOCK (if locked), OPEN, or LOOT it."
        else:
            if len(self.contents) > 0:
                self.description = "A " + self.nickname + ". Inside are the following things: \n\n"
                for item in self.contents:
                    self.description += (colored(item.description, 'yellow') + '\n')
            else:
                self.description = "A " + self.nickname + ". It's empty. Very sorry."

    def unlock(self, player):
        if not self.state == "closed":
            print("Jean can't unlock something that's already open!")
        else:
            #  search the player's inventory for a corresponding key
            for key in self.player.inventory:
                if hasattr(key, "lock"):
                    if key.lock == self:
                        self.locked = False
                        cprint("Jean uses " + key.name + " to unlock the " + self.name + ".", "green")
            if self.locked:
                cprint("Jean couldn't find a matching key.", "red")

    def open(self, player):
        if self.locked:
            print("Jean pulls on the lid of the " + self.nickname + " to no avail. It's locked.")
        else:
            if self.state == "closed":
                print("The " + self.nickname + " creaks eerily.")

                time.sleep(0.5)
                print("The lid lifts back on the hinge, revealing the contents inside.")
                self.revealed = True
                self.state = "opened"
                self.refresh_description()
                self.process_events()
            else:
                print("The " + self.nickname + " is already open. You should VIEW or LOOT it to see what's inside.")

    def loot(self, player):
        if self.state == "closed":
            self.open(player)
        if self.state == "opened":  # keep this as a separate branch so self.open() gets evaluated
            if len(self.contents) > 0:
                print(
                    "Jean rifles through the contents of the " + self.nickname + ".\n\n Choose which items to take.\n\n")
                acceptable_responses = ['all', 'x']
                for i, item in enumerate(self.contents):
                    cprint('{}: {} - {}'.format(i, item.name, item.description), 'yellow')
                    acceptable_responses.append(str(i))
                cprint('all: Take all items.\nx: Cancel', 'yellow')
                choice = 'zzz'
                while choice not in acceptable_responses:
                    choice = input('Selection: ')
                if choice == 'all':
                    while len(self.contents) > 0:
                        item_taken = self.contents.pop()
                        print('Jean takes {}.'.format(item_taken.name))
                        self.player.inventory.append(item_taken)
                        self.refresh_description()
                elif choice == 'x':
                    pass
                else:
                    for i, item in enumerate(self.contents):
                        if choice == str(i):
                            item_taken = self.contents.pop(i)
                            print('Jean takes {}.'.format(item_taken.name))
                            self.player.inventory.append(item_taken)
                            self.refresh_description()
                            break
                self.process_events()
            else:
                print("It's empty. Very sorry.")

    def process_events(self):  # process all events currently tied to the object
        if len(self.events) > 0:
            for event in self.events:
                event.params.append(self)
                self.tile.events_here.append(event)
                self.events.remove(event)
        self.tile.evaluate_events()

    def stack_items(self):
        for master_item in self.contents:  # traverse the inventory for stackable items, then stack them
            if hasattr(master_item, "count"):
                remove_duplicates = []
                for duplicate_item in self.contents:
                    if duplicate_item != master_item and master_item.__class__ == duplicate_item.__class__:
                        master_item.count += duplicate_item.count
                        remove_duplicates.append(duplicate_item)
                if hasattr(master_item, "stack_grammar"):
                    master_item.stack_grammar()
                for duplicate in remove_duplicates:
                    self.contents.remove(duplicate)


### World objects ###

class WoodenChest(Container):
    '''
    A wooden chest that may contain items.
    '''

    def __init__(self, player, tile, params=None):
        description = "A wooden chest which may or may not have things inside. You can try to OPEN or LOOT it."
        super().__init__(name="Wooden Chest", description=description, hidden=False, hide_factor=0,
                         idle_message="There's a wooden chest here.",
                         discovery_message=" a wooden chest!", player=player, tile=tile, nickname="chest",
                         params=params)


class Skeleton(Container):
    def __init__(self, player, tile, params=None):
        description = "The skeletal remains of a poor soul who just couldn't make it. It may carry some LOOT."
        super().__init__(name="Skeletal Remains", description=description, hidden=False, hide_factor=0,
                         idle_message="There are some skeletal remains on the ground.",
                         discovery_message=" skeletal remains!", player=player, tile=tile, nickname="skeleton",
                         params=params)
        self.state = "opened"
        self.keywords.remove("open")
        self.keywords.remove("unlock")


class Shrine(Object):
    '''
    A shrine that can bestow a variety of items, effects, and sometimes challenges to the player
    All shrines should be tied to an event to have an effect. Prayer is always effective, but for these, game effects should only happen once.
    '''

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
                event = functions.seek_class(event_type, "story")(player, tile, params, repeat)
                self.event = event

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
    '''
    A spring that restores Jean's health when he drinks from it. He can also WASH or CLEAN himself in it, which provides a small, temporary boost to charisma
    and max fatigue.
    '''

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
                event = functions.seek_class(event_type, "story")(player, tile, params, repeat)
                self.event = event

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

    def clean(self, player):
        print("Jean summarily begins washing himself in the cool water of the spring.")
        time.sleep(2)
        print("Jean closes his eyes for a moment, enjoying the feeling of simple cleanliness.")
        time.sleep(1)
        cprint("Jean now has Clean status!", "green")
        player.apply_state(states.Clean())

    def wash(self, player):
        self.clean(player)  # this is an alias for clean


class Passageway(Object):
    '''
    A passageway that takes Jean to a different location. This can either be a location in the same map or a different map entirely.
    '''

    def __init__(self, player, tile, params=None):
        description = "A burbling spring with fresh smelling water. It is clean and very inviting."
        super().__init__(name="HealingSpring", description=description,
                         idle_message="There is a small spring bubbling here.",
                         discovery_message=" a healing spring!", player=player, tile=tile)
        self.event = None
        self.keywords.append('enter')

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
                event = functions.seek_class(event_type, "story")(player, tile, params, repeat)
                self.event = event

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
