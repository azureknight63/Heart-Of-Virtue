"""Shared setup for tests of ``GameService.collect_combat_loot``.

No engine imports: it only writes the two attributes a real won fight leaves on
the player, so it works on a real ``Player`` and on a ``Mock`` alike.
"""


def offer_victory_drops(player, *names):
    """Leave ``player`` as a won, unresolved fight does: ``combat_drops``
    offering one of each name (the engine's ``{"name", "quantity"}`` shape)
    and a victory end-of-combat summary, which is what makes it an offer."""
    player.combat_drops = [{"name": name, "quantity": 1} for name in names]
    player.combat_end_summary = {"status": "victory"}
