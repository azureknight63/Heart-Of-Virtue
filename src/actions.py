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


class MoveNorthEast(Action):
    def __init__(self):
        super().__init__(method=Player.move_northeast, name='Move northeast', hotkey=('ne', 'northeast'))


class MoveNorthWest(Action):
    def __init__(self):
        super().__init__(method=Player.move_northwest, name='Move northwest', hotkey=('nw', 'northwest'))


class MoveSouthEast(Action):
    def __init__(self):
        super().__init__(method=Player.move_southeast, name='Move southeast', hotkey=('se', 'southeast'))


class MoveSouthWest(Action):
    def __init__(self):
        super().__init__(method=Player.move_southwest, name='Move southwest', hotkey=('sw', 'southwest'))


class ViewInventory(Action):
    def __init__(self):
        super().__init__(method=Player.print_inventory, name='View inventory', hotkey=('i', 'inv', 'inventory'))


class ViewStatus(Action):
    def __init__(self):
        super().__init__(method=Player.print_status, name='View status', hotkey=('st', 'stat', 'status', 'char', 'character'))


class SkillMenu(Action):
    def __init__(self):
        super().__init__(method=Player.skillmenu, name='View skill menu', hotkey=('k', 'skill', 'skillmenu'))

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


class Attack(Action):
    def __init__(self):
        super().__init__(method=Player.attack, name="Attack", hotkey=('a', 'at', 'atk', 'attack'))

### DEBUG / CHEATS ###


class Teleport(Action):
    def __init__(self):
        super().__init__(method=Player.teleport, name="Teleport", hotkey=('tele', 'teleport'))


class Alter(Action):  # change a switch/variable
    def __init__(self):
        super().__init__(method=Player.alter, name="Alter", hotkey=('alt', 'alter'))


class Showvar(Action):  # list all switches/vars
    def __init__(self):
        super().__init__(method=Player.vars, name="Showvar", hotkey=('sv', 'showvar'))


class Supersaiyan(Action):
    def __init__(self):
        super().__init__(method=Player.supersaiyan, name="Supersaiyan", hotkey=('ss', 'supersaiyan'))


class TestEvent(Action):
    def __init__(self):
        super().__init__(method=Player.testevent, name="TestEvent", hotkey=('te', 'test', 'testevent'))


class SpawnObj(Action):
    def __init__(self):
        super().__init__(method=Player.spawnobject, name="SpawnObj", hotkey=('so', 'spawn', 'spawnobject'))

class RefreshMerchants(Action):  # debug utility to refresh all merchant inventories
    def __init__(self):
        super().__init__(method=Player.refresh_merchants, name="Refresh Merchants", hotkey=(
            'rm', 'refreshmerchants', 'merchrefresh', 'updatemerchants'))