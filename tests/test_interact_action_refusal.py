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
from src.items import Book  # noqa: E402
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


def test_the_refusal_does_not_reflect_an_unbounded_verb(game_service, world):
    """`action` is client input, and /world/interact sets no max_length on it.

    The refusal quotes the verb back, so without a cap a caller could have any
    amount of its own text reflected into the response body.
    """
    player, _tile, handle = _place(
        world,
        Container(name="Cold Hearth", nickname="cold hearth"),
    )

    result = game_service.interact_with_target(player, handle, "z" * 5000)

    assert result["success"] is False
    assert len(result["message"]) < 200, len(result["message"])


def _place_floor_item(world, item):
    """Put ``item`` on the starting tile's floor (``items_here``), authored-style.

    Mirrors what the map loader does for a placement's ``props``: construct
    the object, then ``setattr`` the authored fields straight onto the
    instance -- so an authored ``interactions`` list can differ from whatever
    ``__init__`` produced, exactly as a map JSON's ``props.interactions``
    does.
    """
    player, game_map = world
    tile = game_map[(0, 0)]
    tile.items_here = [item]
    return player, tile, wire_handle(item)


def test_issue_665_floor_book_read_is_honored_not_refused(game_service, world):
    """Issue #665: the interaction panel offers READ on a floor book, but the
    server refuses it in fiction anyway.

    ``src/resources/maps/eastern-descent-jambos-tent.json`` authors Jambo's
    book with ``"interactions": ["drop", "read"]`` and no ``keywords`` --
    ``Item``/``Book`` (``src/items.py``) never set a ``.keywords`` attribute
    at all. ``ItemSerializer.serialize`` computes the wire ``keywords`` field
    FROM ``.interactions`` when ``.keywords`` is absent, which is why the
    frontend panel renders a READ button in the first place. But the
    server-side authorization gate, ``GameService._verb_refusal`` ->
    ``src.objects.advertised_keywords``, reads ONLY ``.keywords`` and falls
    back to a small allow-list that does not include "read" -- so the
    advertised verb was always rejected with the generic
    "There's no way for Jean to read the ..." fallback
    (``_unsupported_action_message``), instead of delivering the book's text
    via ``Book.KEYWORD_METHOD_ALIASES = {"read": "use"}``.

    Pre-fix, this fails with that fallback message. Post-fix, the gate must
    also honor an authored ``.interactions`` verb, and the read must succeed.
    """
    book = Book(name="Jambo's Little Book of Big Deals", text="Buy low. Sell high.")
    # What the map JSON actually authors on this placement (props are set
    # directly on the instance by the map loader, replacing whatever
    # Book.__init__ produced).
    book.interactions = ["drop", "read"]
    assert not hasattr(book, "keywords"), (
        "Item/Book must not carry a .keywords attribute for this repro to "
        "exercise the real drift between the serializer and the gate"
    )
    player, _tile, handle = _place_floor_item(world, book)

    result = game_service.interact_with_target(player, handle, "read")

    assert result["success"] is True, result
    assert "Buy low. Sell high." in result["message"], result


def test_advertised_keywords_ignores_interactions_on_a_non_item_target():
    """The #665 ``.interactions`` merge in ``advertised_keywords`` is Item-only.

    No ``Object`` subclass (``Container``, ``Passageway``, ``WallInscription``,
    ...) ever sets ``.interactions`` in practice, so nothing today exercises
    the boundary -- a later refactor that loosened the guard from
    ``isinstance(target, Item)`` to ``hasattr(target, "interactions")`` would
    pass every other test in this suite while quietly authorizing verbs an
    Object's own ``.keywords`` deliberately left off (e.g. a crafted save, or
    a future authored field collision). This pins the boundary directly.
    """
    from src.objects import Container, advertised_keywords

    container = Container(name="Cold Hearth", nickname="cold hearth")
    container.interactions = ["hack"]  # never a real Container attribute

    assert "hack" not in advertised_keywords(container)


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
