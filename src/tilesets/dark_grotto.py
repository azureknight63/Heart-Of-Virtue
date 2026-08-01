from src.tiles import MapTile


class EmptyCave(MapTile):
    def __init__(
        self, universe=None, current_map=None, x=None, y=None, description=None
    ):
        if description is None:
            description = """
        The darkness here is as oppressive as the silence. The best Jean can do is feel his way around. Each step
        seems to get him no further than the last. The air here is quite cold, sending shivers through Jean's body.
        """
        super().__init__(universe, current_map, x, y, description=description)
        self.symbol = "#"
