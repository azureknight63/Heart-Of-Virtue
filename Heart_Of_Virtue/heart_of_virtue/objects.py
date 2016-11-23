import random, time
import functions

class Object:
    def __init__(self, name, description, hidden = False, hide_factor = 0,
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


class Hidden_Wall_Switch(Object):
    '''
    A hidden wall switch that does something when pressed.
    '''
    def __init__(self, params):
        description = "A small depression in the wall. You may be able to PRESS on it."
        super().__init__(name="Wall Depression", description=description, hidden=True, hide_factor=0,
                         idle_message="There's a small depression in the wall.",
                         discovery_message="a small depression in the wall!")
        self.position = False
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
    def __init__(self, params):
        description = "Words scratched into the wall. Unfortunately, the inscription is too worn to be decipherable."
        super().__init__(name="Inscription", description=description, hidden=False, hide_factor=0,
                         idle_message="There appears to be some words inscribed in the wall.",
                         discovery_message="some words etched into the wall!")

        if 'v0' in params:  # if there is a version declaration, change the description, else keep it generic
            self.description = "The inscription reads: 'EZ 41:1, LK 11:9-10, JL 2:7'"

class Wooden_Chest(Object):
    '''
    A wooden chest that may contain items.
    '''
    def __init__(self, params):
        description = "A wooden chest which may or may not have things inside. You can try to OPEN it."
        super().__init__(name="Wooden Chest", description=description, hidden=False, hide_factor=0,
                         idle_message="There's a wooden chest here.",
                         discovery_message=" a wooden chest!")
        self.position = False
        self.event = None
        if 'locked:' in params: #todo make key objects
            self.locked = True
        else:
            self.locked = False
        self.contents = []
        for thing in params: # put items in the chest based on what's declared in params
            if '#' in thing:
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
            if '!' in thing:
                param = thing.replace('!', '')
                p_list = param.split(':')
                item_type = p_list[0] #todo finish this up - adding events to chests


        self.keywords.append('open')
        self.keywords.append('unlock')

    def open(self):
        if self.locked == True:
            print("Jean pulls on the lid of the chest to no avail. It's locked.")
        else:
            print("The chest creaks eerily.")
            time.sleep(0.5)
            print("The lid lifts back on the hinge, revealing the contents inside.")
            if self.position == False:
                self.position = True
            else:
                self.position = False

