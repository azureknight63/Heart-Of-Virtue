"""Issue #648: ``Book.text`` must load an authored file however it arrived.

Two independent mechanisms handed the player "This book is mysteriously
blank." for a book whose file exists:

1. **Windows separators.** A map authored on Windows as
   ``src\\resources\\books\\x.txt`` resolved for its author and failed on
   Linux, because ``Book.text`` opened the raw string. The engine now reads a
   backslash in an authored path as a separator.
2. **An authored ``"text": ""``.** ``MAP_AUTHORED_ATTR_ALIASES`` maps ``text``
   to ``_text``, and the legacy map loader applies every prop as a
   post-construction ``setattr`` -- so ``_text`` became ``""`` *after*
   ``__init__`` had deferred to the file. The load gate was ``_text is None``;
   ``""`` is not ``None``, so no open was ever attempted and nothing logged.

The fixture file below lives inside the repo so the relative spelling is a
real repo-relative path, exactly the shape a map authors.
"""

import pytest

from src.items import Book
from src.universe import Universe
import src.items as items

BLANK_BOOK = items.BLANK_BOOK_TEXT
#: A shipped book file: the repo-relative spelling the maps author.
SHIPPED = "src/resources/books/jambos-book-of-business-wisdom.txt"


@pytest.fixture
def shipped_text():
    from tests._source_scan import ROOT

    return (ROOT / SHIPPED).read_text(encoding="utf-8")


def _legacy_payload(**props):
    """A legacy full-dump book placement, the shape every shipped map uses."""
    return {"__class__": "Book", "__module__": "items", "props": props}


def test_windows_separators_in_an_authored_path_resolve(shipped_text, tmp_path, monkeypatch):
    """The Grondia map's original spelling reads the book, from any CWD."""
    monkeypatch.chdir(tmp_path)
    windows_spelling = SHIPPED.replace("/", "\\")

    assert Book(text_file_path=windows_spelling).text == shipped_text


def test_authored_empty_text_does_not_suppress_the_file(shipped_text):
    """``_text = ""`` set after construction still loads the authored file."""
    book = Book(text_file_path=SHIPPED)
    book._text = ""

    assert book.text == shipped_text


def test_legacy_map_payload_with_empty_text_loads_the_file(shipped_text):
    """Through the real loader: the post-construction setattr sweep included."""
    book = Universe()._deserialize_saved_instance(
        _legacy_payload(name="Ledger", text="", text_file_path=SHIPPED)
    )

    assert isinstance(book, Book)
    assert book.text == shipped_text


def test_legacy_map_payload_with_windows_path_loads_the_file(shipped_text):
    book = Universe()._deserialize_saved_instance(
        _legacy_payload(name="Ledger", text_file_path=SHIPPED.replace("/", "\\"))
    )

    assert book.text == shipped_text


def test_explicit_text_without_a_path_is_kept():
    """Unchanged: authored prose with no file is the book's text."""
    assert Book(text="Inline prose.").text == "Inline prose."


def test_missing_file_still_reads_blank(tmp_path):
    """Unchanged: a path with nothing behind it is the blank fallback."""
    assert Book(text_file_path=str(tmp_path / "absent.txt")).text == BLANK_BOOK
