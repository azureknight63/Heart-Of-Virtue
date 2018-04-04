import random, time
import functions
from termcolor import colored, cprint

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
        self.tile = tile
        self.player = player

class Tile_Description(Object):
    '''
    Adds to the description of the tile. Has no other function. The existence of this object allows tile descriptions
    to be dynamically changed.
    '''
    def __init__(self, params, player, tile):
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
            if len(temp_line) < (104-len(word)):
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

class Wall_Switch(Object):
    '''
    A wall switch that does something when pressed.
    '''
    def __init__(self, params, player, tile):
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
                parallel = False
                event_type = p_list.pop(0)
                for setting in p_list:
                    if setting == 'r':
                        repeat = True
                        p_list.remove(setting)
                        continue
                    elif setting == 'p':
                        parallel = True
                        p_list.remove(setting)
                        continue
                event = getattr(__import__('events'), event_type)(player, tile, repeat, parallel, p_list)
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


class Wall_Inscription(Object):
    '''
    An inscription (typically visible) that can be looked at.
    '''
    def __init__(self, params, player, tile):
        description = "Words scratched into the wall. Unfortunately, the inscription is too worn to be decipherable."
        super().__init__(name="Inscription", description=description, hidden=False, hide_factor=0,
                         idle_message="There appears to be some words inscribed in the wall.",
                         discovery_message="some words etched into the wall!", player=player, tile=tile)
        self.events = []

        if 'v0' in params:  # if there is a version declaration, change the description, else keep it generic
            self.description = "The inscription reads: 'EZ 41:1, LK 11:9-10, JL 2:7'"

class Wooden_Chest(Object):  #todo auto-stack duplicates inside the chest
    '''
    A wooden chest that may contain items.
    '''
    def __init__(self, params, player, tile):
        description = "A wooden chest which may or may not have things inside. You can try to OPEN or LOOT it."
        super().__init__(name="Wooden Chest", description=description, hidden=False, hide_factor=0,
                         idle_message="There's a wooden chest here.",
                         discovery_message=" a wooden chest!", player=player, tile=tile)
        self.position = False
        self.events = []  # a list of events that occur when the player interacts with the chest. Events with "repeat" will persist.
        self.possible_states = ("closed", "opened", "looted")
        self.state = self.possible_states[0]  # start closed
        self.contents = []
        self.revealed = False
        if 'locked:' in params: #todo make key objects
            self.locked = True
        else:
            self.locked = False
        for thing in params: # put items in the chest or attach events based on what's declared in params
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
                parallel = False
                trigger = 'auto'
                event_type = p_list.pop(0)
                for setting in p_list:
                    if setting == 'r':
                        repeat = True
                        p_list.remove(setting)
                        continue
                    elif setting == 'p':
                        parallel = True
                        p_list.remove(setting)
                        continue
                    elif setting in self.possible_states:  # event trigger
                        trigger = setting
                        p_list.remove(setting)

                event = getattr(__import__('events'), event_type)(player, tile, repeat, parallel, p_list)
                self.events.append((event,trigger))


        self.keywords.append('open')
        self.keywords.append('unlock')
        self.keywords.append('loot')
        self.process_events()  # process initial events (triggers labeled "auto")

    def refresh_description(self):
        if self.position == False:
            self.description = "A wooden chest which may or may not have things inside. You can try to OPEN or LOOT it."
        else:
            if len(self.contents) > 0:
                self.description = "A wooden chest. Inside are the following things: \n\n"
                for item in self.contents:
                    self.description += (colored(item.description, 'yellow') + '\n')
            else:
                self.description = "A wooden chest. It's empty. Very sorry."

    def open(self):
        if self.locked == True:
            print("Jean pulls on the lid of the chest to no avail. It's locked.")
        else:
            if self.position == False:
                print("The chest creaks eerily.")

                time.sleep(0.5)
                print("The lid lifts back on the hinge, revealing the contents inside.")
                self.revealed = True
                self.position = True
                self.state = "opened"
                self.refresh_description()
                self.process_events()
            else:
                print("The chest is already open. You should VIEW or LOOT it to see what's inside.")

    def loot(self):
        if self.position == False:
            self.open()
        if self.position == True:  # keep this as a separate branch so self.open() gets evaluated
            if len(self.contents) > 0:
                print("Jean rifles through the contents of the chest.\n\n Choose which items to take.\n\n")
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
                    self.state = "looted"
                elif choice == 'x':
                    pass
                else:
                    for i, item in enumerate(self.contents):
                        if choice == str(i):
                            item_taken = self.contents.pop(i)
                            print('Jean takes {}.'.format(item_taken.name))
                            self.player.inventory.append(item_taken)
                            self.refresh_description()
                            self.state = "looted"
                            break
                self.process_events()
            else:
                print("It's empty. Very sorry.")

    def process_events(self): # process all events currently tied to the object
        for event in self.events:
            event_object = event[0]
            event_trigger = event[1]
            if event_trigger == "auto" or event_trigger == self.state:
                self.tile.events_here.append(event_object)
                self.events.remove(event)
        self.tile.evaluate_events()


