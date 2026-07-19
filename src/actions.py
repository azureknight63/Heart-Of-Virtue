from src.player import Player


class Action:
    def __init__(self, method, name, hotkey, debug=False, **kwargs):
        self.method = method
        self.hotkey = []
        self.name = name
        self.debug = debug  # Optional flag for debug commands
        self.kwargs = kwargs
        for key in hotkey:
            self.hotkey.append(key)

    def __str__(self):
        return "{}: {}".format(self.hotkey, self.name)


class Search(Action):
    def __init__(self):
        super().__init__(
            method=Player.search,
            name="Search",
            hotkey=("search", "seek", "snoop"),
        )


class Menu(Action):
    def __init__(self):
        super().__init__(
            method=Player.menu, name="Menu", hotkey=("menu", "exit", "quit")
        )


class Save(Action):
    def __init__(self):
        super().__init__(method=Player.save, name="Save", hotkey=("sav", "save"))


class ViewMap(Action):
    def __init__(self):
        super().__init__(
            method=Player.view_map,
            name="View Map",
            hotkey=("m", "map", "cartography"),
        )


# DEBUG / CHEATS


class Teleport(Action):
    def __init__(self):
        super().__init__(
            method=Player.teleport,
            name="Teleport",
            hotkey=("tele", "teleport"),
            debug=True,
            color="silver",
        )


class Alter(Action):  # change a switch/variable
    def __init__(self):
        super().__init__(
            method=Player.alter,
            name="Alter",
            hotkey=("alt", "alter"),
            debug=True,
            color="silver",
        )


class Showvar(Action):  # list all switches/vars
    def __init__(self):
        super().__init__(
            method=Player.print_story_vars,
            name="Showvar",
            hotkey=("sv", "showvar"),
            debug=True,
            color="silver",
        )


class Supersaiyan(Action):
    def __init__(self):
        super().__init__(
            method=Player.supersaiyan,
            name="Supersaiyan",
            hotkey=("ss", "supersaiyan"),
            debug=True,
            color="silver",
        )


class TestEvent(Action):
    def __init__(self):
        super().__init__(
            method=Player.testevent,
            name="TestEvent",
            hotkey=("te", "test", "testevent"),
            debug=True,
            color="silver",
        )


class SpawnObj(Action):
    def __init__(self):
        super().__init__(
            method=Player.spawnobject,
            name="SpawnObj",
            hotkey=("so", "spawn", "spawnobject"),
            debug=True,
            color="silver",
        )


class RefreshMerchants(Action):  # debug utility to refresh all merchant inventories
    def __init__(self):
        super().__init__(
            method=Player.refresh_merchants,
            name="Refresh Merchants",
            hotkey=(
                "rm",
                "refreshmerchants",
                "merchrefresh",
                "updatemerchants",
            ),
            debug=True,
            color="silver",
        )
