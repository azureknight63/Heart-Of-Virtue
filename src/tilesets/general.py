from src.tiles import *


class Boundary(MapTile):
    def __init__(self, universe, current_map, x, y):
        super().__init__(universe, current_map, x, y, description="""
        You should not be here.
        """)
        self.symbol = "'"

    def modify_player(self, the_player):
        # Room has no action on player
        pass


class BlankTile(MapTile):
    def __init__(self, universe, current_map, x, y):
        super().__init__(universe, current_map, x, y, description='')
        self.symbol = '#'

    def modify_player(self, the_player):
        # Room has no action on player
        pass
