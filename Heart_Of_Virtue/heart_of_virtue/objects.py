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

class Hidden_Wall_Switch(Object):
    '''
    A hidden wall switch that does something when pressed.
    '''
    def __init__(self):
        description = "A small depression in the wall."
        super().__init__(name="Wall Switch", description=description, hidden=True, hide_factor=0,
                         idle_message="There's a small depression in the wall.",
                         discovery_message=" a small depression in the wall!")
        self.position = False

    def use(self):
        print("Jean hears a faint 'click.'")
        time.sleep(0.5)
        if self.position == False:
            self.position = True
        else:
            self.position = False