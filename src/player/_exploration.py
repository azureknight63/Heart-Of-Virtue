"""Exploration mixin for Player.

The terminal exploration surface (``search`` and ``view_map``) was removed
with the terminal-mode teardown. The web API owns these now:
``GameService.search`` handles searching, and the frontend renders the map
from the ``/world/explored`` route. This mixin is retained as a placeholder
so the ``Player`` MRO is unchanged.
"""


class PlayerExplorationMixin:
    """Room exploration for the Player (terminal methods removed)."""

    pass
