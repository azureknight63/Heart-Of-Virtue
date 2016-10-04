import random, time
import functions

class Object:
    def __init__(self, name, description, hidden = False, hide_factor = 0,
                 idle_message = ' is here.',
                 discovery_message = 'something interesting.', target = None):
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
    def __init__(self):
        description = "A small depression in the wall. You may be able to PRESS on it."
        super().__init__(name="Wall Depression", description=description, hidden=True, hide_factor=0,
                         idle_message="There's a small depression in the wall.",
                         discovery_message=" a small depression in the wall!")
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
    An inscription (typically visible) that can be READ.
    '''
    def __init__(self):
        description = "Words scratched into the wall. You think you may be able to READ them."
        super().__init__(name="Inscription", description=description, hidden=False, hide_factor=0,
                         idle_message="There appears to be some words inscribed in the wall.",
                         discovery_message=" some words etched into the wall!")
        self.words = 'Unfortunately, the inscription is too worn to be decipherable.'
        self.keywords.append('read')

    def read(self):
        print("Jean leans ") #todo
        time.sleep(0.5)
