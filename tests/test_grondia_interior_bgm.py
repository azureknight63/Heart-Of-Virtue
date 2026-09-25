"""Grondia building interiors no longer author the Mineral Pools BGM (#692).

``grondia-conclave-archive``, ``grondia-fabricarium-forge``,
``grondia-guesthold`` and ``grondia-vacated-dwelling`` used to author
``metadata.bgm: "mineral_pools"``, so stepping into them from Grondia played
the wrong dungeon's theme. Grondia itself authors no ``bgm`` and falls back to
the name-based match in ``GameService._resolve_bgm``
(``src/api/services/game_service.py``) -- since none of these map names
contain "mineral", removing the authored key lets that fallback resolve them
to ``"grondia"`` like the city they are part of.

A cheap guard so a future grondia-* interior can't reintroduce this by
accident: authoring "mineral_pools" only makes sense for the actual Mineral
Pools map, whose name contains "mineral".
"""

import json
import pathlib

MAPS_DIR = pathlib.Path(__file__).resolve().parent.parent / "src" / "resources" / "maps"


#: The four interiors #692 named, plus a name-shaped guard: any future
#: grondia-* interior whose name has no other bgm-triggering substring
#: (mineral/nomad/jambos/eastern/verdette -- see _resolve_bgm) is expected to
#: fall back to "grondia", same as these four.
_KNOWN_OFFENDERS = {
    "grondia-conclave-archive",
    "grondia-fabricarium-forge",
    "grondia-guesthold",
    "grondia-vacated-dwelling",
}
_OTHER_BGM_HINTS = ("mineral", "nomad", "jambos", "eastern", "verdette")


def _grondia_interior_maps():
    return sorted(
        p
        for p in MAPS_DIR.glob("grondia-*.json")
        if p.stem in _KNOWN_OFFENDERS
        or not any(hint in p.stem for hint in _OTHER_BGM_HINTS)
    )


def test_no_grondia_interior_authors_mineral_pools():
    offenders = []
    for path in _grondia_interior_maps():
        metadata = json.loads(path.read_text(encoding="utf-8")).get("metadata", {})
        if metadata.get("bgm") == "mineral_pools":
            offenders.append(path.stem)
    assert offenders == [], (
        f"{offenders} author metadata.bgm='mineral_pools' but their names "
        "don't say 'mineral' -- that plays the wrong dungeon's theme. See #692."
    )


def test_grondia_interiors_fall_back_to_the_grondia_bgm():
    from src.api.services.game_service import GameService

    service = GameService()
    player = type("P", (), {})()
    for path in _grondia_interior_maps():
        player.map = {"name": path.stem, "metadata": {}}
        tile = type("T", (), {})()  # no tile-level bgm attribute
        assert service._resolve_bgm(tile, player) == "grondia", path.stem
