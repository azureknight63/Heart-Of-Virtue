from player import Player



class Action():
    def __init__(self, method, name, hotkey, **kwargs):
        self.method = method
        self.hotkey = []
        self.name = name
        self.kwargs = kwargs
        for key in hotkey:
            self.hotkey.append(key)

    def __str__(self):
        return "{}: {}".format(self.hotkey, self.name)

class MoveNorth(Action):
    def __init__(self):
        super().__init__(method=Player.move_north, name='Move north', hotkey=('n', 'north'))

class MoveSouth(Action):
    def __init__(self):
        super().__init__(method=Player.move_south, name='Move south', hotkey=('s', 'south'))

class MoveEast(Action):
    def __init__(self):
        super().__init__(method=Player.move_east, name='Move east', hotkey=('e', 'east'))

class MoveWest(Action):
    def __init__(self):
        super().__init__(method=Player.move_west, name='Move west', hotkey=('w', 'west'))

class ViewInventory(Action):
    """Prints the player's inventory"""

    def __init__(self):
        super().__init__(method=Player.print_inventory, name='View inventory', hotkey=('i', 'inv', 'inventory'))

# class Attack(Action):
#     def __init__(self, enemy):
#         super().__init__(method=Player.attack, name="Attack", hotkey='a', enemy=enemy)
#
# class Flee(Action):
#     def __init__(self, tile):
#         super().__init__(method=Player.flee, name="Flee", hotkey='flee', tile=tile)

class Look(Action):
    def __init__(self):
        super().__init__(method=Player.look, name="Look", hotkey=('l', 'look'))

class ListCommands(Action):
    def __init__(self):
        super().__init__(method=Player.commands, name="List Commands", hotkey=('c', 'com', 'commands', 'man', 'help',
                                                                               '?'))

class View(Action):
    def __init__(self):
        super().__init__(method=Player.view, name="View", hotkey=('v', 'view'))

class Equip(Action):
    def __init__(self):
        super().__init__(method=Player.equip_item, name="Change Equipment", hotkey=('q', 'equip'))

class Use(Action):
    def __init__(self):
        super().__init__(method=Player.use_item, name="Use Item", hotkey=('u','use'))

class Search(Action):
    def __init__(self):
        super().__init__(method=Player.search, name="Search", hotkey=('search', 'seek', 'snoop'))

class Menu(Action):
    def __init__(self):
        super().__init__(method=Player.menu, name="Menu", hotkey=('menu', 'exit', 'quit'))

class Save(Action):
    def __init__(self):
        super().__init__(method=Player.save, name="Save", hotkey=('sav', 'save'))

class Take(Action):
    def __init__(self):
        super().__init__(method=Player.take, name="Take Item", hotkey=('t','take'))

class ViewMap(Action):
    def __init__(self):
        super().__init__(method=Player.view_map, name="View Map", hotkey=('m', 'map', 'cartography'))

# def commands(self):
#     print("l: Look around\n"
#           "v: View details on a person, creature, or object\n"
#           "i: Inspect your inventory\n"
#           "q: Equip or unequip an item from your inventory\n"
#           "u: Use an item from your inventory\n"