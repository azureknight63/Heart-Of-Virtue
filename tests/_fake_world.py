"""Engine-free helpers for test doubles that stand in for a built world.

Imports nothing from ``src``, so any test file can use it without building a
universe.
"""


def bind_rooms_to_shared_map(rooms):
    """Give every fake room the one coordinate-keyed map they share, as ``room.map``.

    A real ``Universe`` has no ``map`` attribute (issue #739): each ``MapTile``
    carries the dict of its own map as ``room.map``, and that is what the shop
    code walks. The rooms are placed along row 0 in list order.

    String entries are kept in the map but not bound: some tests put a bare
    string among the rooms to exercise the engine's skip of non-tile entries,
    and a string cannot take an attribute. Returns the shared map.
    """
    game_map = {(index, 0): room for index, room in enumerate(rooms)}
    for room in rooms:
        if not isinstance(room, str):
            room.map = game_map
    return game_map
