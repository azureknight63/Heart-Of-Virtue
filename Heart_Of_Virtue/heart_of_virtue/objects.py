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


class Hidden_Wall_Switch(Object):
    '''
    A hidden wall switch that does something when pressed.
    '''
    def __init__(self, params, player, tile):
        description = "A small depression in the wall. You may be able to PRESS on it."
        super().__init__(name="Wall Depression", description=description, hidden=True, hide_factor=0,
                         idle_message="There's a small depression in the wall.",
                         discovery_message="a small depression in the wall!", player=player, tile=tile)
        self.position = False
        self.events = []
        self.keywords.append('press')

    def press(self):
        print("Jean hears a faint 'click.'")
        time.sleep(0.5)
        if self.position == False:
            self.position = True
        else:
            self.position = False


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

class Wooden_Chest(Object):
    '''
    A wooden chest that may contain items.
    '''
    def __init__(self, params, player, tile):
        description = "A wooden chest which may or may not have things inside. You can try to OPEN it."
        super().__init__(name="Wooden Chest", description=description, hidden=False, hide_factor=0,
                         idle_message="There's a wooden chest here.",
                         discovery_message=" a wooden chest!", player=player, tile=tile)
        self.position = False
        self.events = []  # a list of events that occur when the chest is opened. Events with "repeat" will persist.
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
                amt = int(p_list[1])
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
                    params.append(setting)
                event = getattr(__import__('events'), event_type)(player, tile, repeat, parallel, params)
                self.events.append(event)

        self.keywords.append('open')
        self.keywords.append('unlock')
        self.keywords.append('loot')

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
                if len(self.contents) > 0:
                    self.description = "A wooden chest. Inside are the following things: \n\n"
                    for item in self.contents:
                        self.description += (colored(item.description, 'yellow') + '\n')
                else:
                    self.description = "A wooden chest. It's empty. Very sorry."
            else:
                print("The chest is already open. You should VIEW or LOOT it to see what's inside.")


    def loot(self):
        if self.position == False:
            self.open()
        if self.position == True:  # keep this as a separate branch so self.open() gets evaluated
            if len(self.contents) > 0:
                print("Jean rifles through the contents of the chest.\n\n Choose which items to take.\n\n")
                acceptable_responses = ['all', 'ALL', 'a']
                for i, item in enumerate(self.contents):
                    cprint('{}: {} - {}\n'.format(i, item.name, item.description, 'yellow'))
                    acceptable_responses.append(str(i))
                cprint('all: Take all items.', 'yellow')
                choice = input('Selection: ')  #todo finish this

