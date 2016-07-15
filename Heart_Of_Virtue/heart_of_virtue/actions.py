from player import Player



class Action():
    def __init__(self, method, name, hotkey, **kwargs):
        self.method = method
        self.hotkey = hotkey
        self.name = name
        self.kwargs = kwargs

    def __str__(self):
        return "{}: {}".format(self.hotkey, self.name)

class MoveNorth(Action):
    def __init__(self):
        super().__init__(method=Player.move_north, name='Move north', hotkey='n')

class MoveSouth(Action):
    def __init__(self):
        super().__init__(method=Player.move_south, name='Move south', hotkey='s')

class MoveEast(Action):
    def __init__(self):
        super().__init__(method=Player.move_east, name='Move east', hotkey='e')

class MoveWest(Action):
    def __init__(self):
        super().__init__(method=Player.move_west, name='Move west', hotkey='w')

class ViewInventory(Action):
    """Prints the player's inventory"""

    def __init__(self):
        super().__init__(method=Player.print_inventory, name='View inventory', hotkey='i')

class Attack(Action):
    def __init__(self, enemy):
        super().__init__(method=Player.attack, name="Attack", hotkey='a', enemy=enemy)

class Flee(Action):
    def __init__(self, tile):
        super().__init__(method=Player.flee, name="Flee", hotkey='flee', tile=tile)

class Look(Action):
    def __init__(self):
        super().__init__(method=Player.look, name="Look", hotkey='l')

class ListCommands(Action):
    def __init__(self):
        super().__init__(method=Player.commands, name="List Commands", hotkey='c')

class View(Action):
    def __init__(self):
        super().__init__(method=Player.view, name="View", hotkey='v')

class Equip(Action):
    def __init__(self):
        super().__init__(method=Player.equip_item, name="Change Equipment", hotkey='q')

class Use(Action):
    def __init__(self):
        super().__init__(method=Player.use_item, name="Use Item", hotkey='use')

class Take(Action):
    def __init__(self):
        super().__init__(method=Player.take, name="Take Item", hotkey='take')

# def commands(self):
#     print("l: Look around\n"
#           "v: View details on a person, creature, or object\n"
#           "i: Inspect your inventory\n"
#           "q: Equip or unequip an item from your inventory\n"
#           "u: Use an item from your inventory\n"