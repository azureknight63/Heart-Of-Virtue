"""Regression coverage for GitHub issue #545 — "Anvil not listed in INTERACT
at the Tradepost".

Every existing Anvil test (``tests/test_eastern_descent.py``) constructs
``Anvil()`` directly, which bypasses the entire pipeline the bug report is
actually about: map JSON -> ``Universe._load_single_json_map`` ->
``Universe._deserialize_saved_instance`` -> ``tile.npcs_here`` ->
``NPCSerializer`` -> ``GameService.get_current_room`` (the service method
behind ``GET /world``). No test asserted that round trip actually reproduces
Anvil with his authored ``keywords`` at the Tradepost tile ``(4, 3)`` in
``src/resources/maps/eastern-descent-nomad-camp.json``. This module is that
missing coverage, following the same "load the real shipped map JSON through
the real engine loader" pattern as ``tests/test_location_bgm.py`` and
``tests/test_jambo_tent_navigation.py``.
"""

from pathlib import Path

from src.api.services.game_service import GameService
from src.player import Player
from src.universe import Universe


_ROOT = Path(__file__).resolve().parent.parent
_MAPS = _ROOT / "src" / "resources" / "maps"


def _load_tradepost():
    """Load the real nomad-camp map through the real engine loader and
    return (player, tile) positioned at the Tradepost, (4, 3)."""
    player = Player()
    universe = Universe(player=player)
    universe._load_single_json_map(player, _MAPS / "eastern-descent-nomad-camp.json")
    game_map = universe.maps[-1]
    player.universe = universe
    player.map = game_map

    coordinate = (4, 3)
    tile = game_map[coordinate]
    player.location_x, player.location_y = coordinate
    player.current_room = tile
    return player, tile


def test_anvil_is_present_on_the_deserialized_tradepost_tile():
    """Beneath the API layer: Anvil must land in ``tile.npcs_here`` after a
    real deserialization pass, not just when ``Anvil()`` is constructed by
    hand. Also pins the ``hidden``/``keywords`` values the JSON authors
    (verified in the source map: ``hidden: false``, ``keywords: ["talk",
    "pet"]``), so a future change to either is caught here independent of
    serialization.
    """
    _, tile = _load_tradepost()

    names = [getattr(npc, "name", None) for npc in tile.npcs_here]
    assert "Anvil" in names, (
        f"Anvil did not deserialize onto the Tradepost tile; npcs_here "
        f"contained: {names}"
    )

    anvil = next(npc for npc in tile.npcs_here if npc.name == "Anvil")
    assert getattr(anvil, "hidden", False) is False
    assert list(getattr(anvil, "keywords", [])) == ["talk", "pet"]


def test_anvil_appears_in_get_current_room_at_the_tradepost():
    """``GameService.get_current_room`` — the service method backing
    ``GET /world`` — must list Anvil among the Tradepost's npcs, carrying his
    authored ``keywords``. This is the actual symptom reported in issue #545:
    Anvil missing from the INTERACT panel, which reads off this response's
    ``npcs[*].keywords``.
    """
    player, _ = _load_tradepost()

    room = GameService().get_current_room(player)

    assert room.get("name") == "Tradepost", room
    npc_names = [npc.get("name") for npc in room["npcs"]]
    assert "Anvil" in npc_names, (
        "Anvil did not appear in GET /world's npcs list for the Tradepost "
        f"tile (4, 3); npcs returned were: {npc_names}"
    )

    anvil = next(npc for npc in room["npcs"] if npc.get("name") == "Anvil")
    assert anvil.get("keywords") == ["talk", "pet"], anvil
