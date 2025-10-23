from src.tiles import *


class StartingRoom(MapTile):
    def __init__(self, universe, current_map, x, y, description: str=None):
        super().__init__(universe, current_map, x, y, description="""
        Jean finds himself in a gloomy cavern. Cold grey stone surrounds him. In the center of the room is a large
        rock resembling a table. A silver beam of light falls through a small hole in the ceiling - the only source
        of light in the room. Jean can make out a few beds of moss and mushrooms littering the cavern floor. The
        darkness seems to extend endlessly in all directions.
        """)
        self.symbol = '#'

    def modify_player(self, the_player):
        # Room has no action on player
        pass


class EmptyCave(MapTile):
    def __init__(self, universe=None, current_map=None, x=None, y=None, description=None):
        if description is None:
            description = """
        The darkness here is as oppressive as the silence. The best Jean can do is feel his way around. Each step
        seems to get him no further than the last. The air here is quite cold, sending shivers through Jean's body.
        """
        super().__init__(universe, current_map, x, y, description=description)
        self.symbol = '#'

    def modify_player(self, the_player):
        # Room has no action on player
        pass
