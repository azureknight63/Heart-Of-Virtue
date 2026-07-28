"""Shared inventory helpers for API routes and serializers."""


def get_inventory_list(player):
    """Return the player's inventory list, tolerating both attribute names.

    The engine ``Player`` exposes its items as ``inventory``; some call sites
    reference an ``inventory_list`` alias. Prefer ``inventory_list`` when it is
    a real (non-``None``) list, otherwise fall back to ``inventory``.

    Uses an explicit ``is None`` check rather than the old ``a or b`` idiom to
    avoid the falsy-empty-list trap: a legitimately empty ``inventory_list``
    would silently fall through to ``inventory`` with ``or``.

    Args:
        player: Player object

    Returns:
        The player's inventory list (possibly empty).
    """
    inventory_list = getattr(player, "inventory_list", None)
    if inventory_list is None:
        inventory_list = getattr(player, "inventory", [])
    return inventory_list
