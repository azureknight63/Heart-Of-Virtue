"""Shared setup for tests of ``GameService.collect_combat_loot``.

Writes only what a real won fight leaves on the player, so it works on a real
``Player`` and on a ``Mock`` alike.
"""

import uuid

from src.combatant import wire_handle


def offer_victory_drops(player, *names, tile=None):
    """Leave ``player`` as a won, unresolved fight does: ``combat_drops``
    offering one of each name (the engine's ``{"name", "quantity", "handles"}``
    shape) and a victory end-of-combat summary, which is what makes it an
    offer.

    Each name is bound to an object of that name lying on ``tile`` — the
    player's current room unless one is given — exactly as a dying enemy binds
    its record to the objects it spawned (issue #621). The offer is an
    identity, so a test that merely names a drop is not describing one. A name
    with nothing of its kind on the floor gets a handle that answers to
    nothing: the fight dropped it and it has since gone.
    """
    if tile is None:
        tile = getattr(player, "current_room", None)
    floor = getattr(tile, "items_here", None)
    unclaimed = list(floor) if isinstance(floor, list) else []

    player.combat_drops = []
    for name in names:
        # Newest first, and one object per name, the way the drops themselves
        # were recorded: two offers of a name must not name one object twice.
        match = next(
            (i for i in reversed(unclaimed) if getattr(i, "name", None) == name),
            None,
        )
        if match is not None:
            unclaimed.remove(match)
        player.combat_drops.append(
            {
                "name": name,
                "quantity": 1,
                "handles": [
                    wire_handle(match) if match is not None else uuid.uuid4().hex
                ],
            }
        )
    player.combat_end_summary = {"status": "victory"}
