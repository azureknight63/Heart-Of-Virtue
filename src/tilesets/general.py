from src.tiles import MapTile


class Boundary(MapTile):
    def __init__(self, universe, current_map, x, y):
        super().__init__(
            universe,
            current_map,
            x,
            y,
            description="""
        You should not be here.
        """,
        )
        self.symbol = "'"


class BlankTile(MapTile):
    def __init__(self, universe, current_map, x, y):
        super().__init__(universe, current_map, x, y, description="")
        self.symbol = "#"
