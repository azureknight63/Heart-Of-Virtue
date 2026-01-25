from src.tiles import *


class TestChestRoom(MapTile):
    def __init__(self, universe, current_map, x, y, description: str=None):
        super().__init__(universe, current_map, x, y, description="""
        A test room with a wooden chest. This is for testing the chest rumbler battle narrative.
        """)
        self.symbol = '#'

    def modify_player(self, the_player):
        # Room has no action on player
        pass
