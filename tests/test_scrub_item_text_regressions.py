"""Two scrub findings on item text (#611/#624 review).

* Taking part of a stack out of a container narrated "Jean takes Dried
  Crystal Sap." -- before #624 the name the stack baked in carried the count,
  and removing the bake removed it from this one sentence, the only "Jean
  takes ..." line that did not go through ``stack_sentence_label``.
* ``Book.text`` opened its authored path relative to the process's working
  directory, so #611's forward-slash fix only worked when the server started
  at the repo root; and a failed load narrated the path and the OS error to
  the player.
"""

import pytest

from src.combatant import wire_handle
from src.items import Book, DriedCrystalSap
from src.narration import capture_narration
from src.objects import Container
from tests._gs_fixtures import live_world

_SHIPPED_BOOK = "src/resources/books/jambos-book-of-business-wisdom.txt"


@pytest.fixture
def game_service():
    from src.api.services.game_service import GameService

    return GameService()


def test_taking_part_of_a_stack_from_a_container_says_how_many(game_service):
    player, game_map = live_world()
    tile = game_map[(0, 0)]
    sap = DriedCrystalSap()
    sap.count = 3
    crate = Container(name="Crate", description="A crate.", player=player, tile=tile)
    crate.inventory = [sap]
    crate.state = "opened"
    tile.objects_here = [crate]

    result = game_service.interact_with_target(
        player, wire_handle(sap), "take", quantity=2, session_data={}
    )

    assert result["success"] is True, result
    assert result["message"] == "Jean takes 2× Dried Crystal Sap.", result


def test_a_book_reads_from_any_working_directory(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    book = Book(text_file_path=_SHIPPED_BOOK)

    assert book.text != "This book is mysteriously blank."


def test_a_missing_book_tells_the_player_nothing_about_the_filesystem():
    book = Book(text_file_path="src/resources/books/does-not-exist.txt")

    with capture_narration() as messages:
        text = book.text

    assert text == "This book is mysteriously blank."
    leaked = [m["text"] for m in messages if "does-not-exist" in m["text"]]
    assert leaked == [], leaked
