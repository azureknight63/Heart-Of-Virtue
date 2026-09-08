"""Issue #553: an authored keyword must never hand the player an exception.

Reported symptom, at grondia (8,4) -> INTERACT -> Carved Lintel -> `touch`:

    Error executing action: 'WallInscription' object has no attribute 'touch'

Two separate defects produced that one string, and this file guards both:

1. ``interact_with_target`` dispatched authored keywords with a bare
   ``getattr(target, action)``, with nothing checking that the class actually
   implements the verb the map authored.
2. The broad ``except Exception`` around the dispatch interpolated ``str(e)``
   into the message handed back to the client, so *any* internal failure —
   this one included — was rendered as engine internals in the game's prose
   panel.

The keyword-resolution half is covered exhaustively, against every shipped map,
in ``tests/test_object_action_dispatch_contract.py``. This file covers the
player-facing surface: what the response actually says.
"""

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.api.services.game_service import GameService  # noqa: E402
from src.combatant import wire_handle  # noqa: E402
from src.objects import Container, WallInscription  # noqa: E402
from tests._gs_fixtures import live_world  # noqa: E402

#: Substrings that mean engine internals reached the prose panel.
_INTERNALS = (
    "Traceback",
    "AttributeError",
    "object has no attribute",
    "Error executing action",
)


@pytest.fixture
def game_service():
    return GameService()


@pytest.fixture
def world():
    return live_world()


def _place(world, obj):
    player, game_map = world
    tile = game_map[(0, 0)]
    obj.tile = tile
    obj.player = player
    tile.objects_here = [obj]
    return player, tile, wire_handle(obj)


def _lintel(world):
    """The reported object: a WallInscription authored with `touch`."""
    player, game_map = world
    lintel = WallInscription(
        player=player,
        tile=game_map[(0, 0)],
        description="A carved lintel over the doorway.",
        text="Names, cut deep and worn shallow again.",
    )
    lintel.name = "Carved Lintel"
    # What grondia.json authors on this placement. The loader setattrs props
    # straight onto the instance, replacing the class's ["read", "examine"].
    lintel.keywords = ["read", "examine", "inspect", "touch"]
    return _place(world, lintel)


def test_the_reported_repro_no_longer_leaks_the_exception(game_service, world):
    player, _tile, handle = _lintel(world)

    result = game_service.interact_with_target(player, handle, "touch")

    blob = repr(result)
    for marker in _INTERNALS:
        assert marker not in blob, (
            f"engine internals ({marker!r}) reached the player: {result}"
        )


def test_the_reported_repro_delivers_the_inscription(game_service, world):
    """`touch` on a carving is a synonym for reading it, not a dead button.

    Every verb authored on a WallInscription was put there to deliver
    ``self.text`` — the object has no second behaviour it could mean.
    """
    player, _tile, handle = _lintel(world)

    result = game_service.interact_with_target(player, handle, "touch")

    assert result["success"] is True
    assert "worn shallow" in result["message"], result


@pytest.mark.parametrize("keyword", ["inspect", "view", "check", "look", "touch"])
def test_wall_inscription_read_synonyms_all_deliver_the_text(
    game_service, world, keyword
):
    player, _tile, handle = _lintel(world)
    # Authored keywords vary per placement across the maps; the class must
    # answer all of them.
    player.current_room.objects_here[0].keywords = [keyword]

    result = game_service.interact_with_target(player, handle, keyword)

    assert result["success"] is True, result
    assert "worn shallow" in result["message"], result


@pytest.mark.parametrize("keyword", ["search", "look", "lift"])
def test_container_look_inside_synonyms_open_the_container(
    game_service, world, keyword
):
    """grondia authors search/look/lift on hearths, troughs and floor grates."""
    player, tile, handle = _place(
        world,
        Container(name="Cold Hearth", nickname="cold hearth"),
    )
    container = tile.objects_here[0]
    container.keywords = [keyword]

    result = game_service.interact_with_target(
        player, handle, keyword, session_data={}
    )

    assert result["success"] is True, result
    assert container.state == "opened", result


def test_an_unimplemented_verb_is_refused_in_fiction(game_service, world):
    """A verb on the interaction allow-list that the class cannot do.

    ``equip`` passes ``_ALLOWED_INTERACTION_VERBS`` even though no Container
    implements it, so this reached the same bare ``getattr`` the reported bug
    did — without any map having to author it.
    """
    player, _tile, handle = _place(
        world,
        Container(name="Cold Hearth", nickname="cold hearth"),
    )

    result = game_service.interact_with_target(player, handle, "equip")

    assert result["success"] is False
    blob = repr(result)
    for marker in _INTERNALS:
        assert marker not in blob, f"{marker!r} reached the player: {result}"
    assert "Cold Hearth" in result["message"], result


def test_an_internal_failure_is_not_reported_as_its_exception_text(
    game_service, world, monkeypatch
):
    """The broad except must stop interpolating ``str(e)`` into the message."""
    player, tile, handle = _place(
        world,
        Container(name="Cold Hearth", nickname="cold hearth"),
    )

    def boom(*_a, **_k):
        raise RuntimeError("SECRET-INTERNAL-DETAIL")

    monkeypatch.setattr(tile.objects_here[0], "open", boom)

    result = game_service.interact_with_target(
        player, handle, "loot", session_data={}
    )

    assert result["success"] is False
    assert "SECRET-INTERNAL-DETAIL" not in repr(result), result
    for marker in _INTERNALS:
        assert marker not in repr(result), f"{marker!r} reached the player: {result}"
    assert result["message"].strip(), "the refusal said nothing at all"
