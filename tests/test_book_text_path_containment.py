"""Issue #674 item 11: ``Book.text`` reads only from the books directory.

``text_file_path`` arrives from map JSON and from saves, both untrusted
inputs, and ``_resolve_text_path`` used to accept an absolute path or a
``..`` walk out of the repo -- so a crafted book read any file the server
could open and handed it to the player as page text. The path is now
resolved and must lie under ``src/resources/books``; anything else reads as a
missing file (blank book) and is logged.
"""

import logging

import pytest

import src.items as items
from src.items import Book

BLANK_BOOK = "This book is mysteriously blank."
SHIPPED = "src/resources/books/jambos-book-of-business-wisdom.txt"


@pytest.fixture
def secret(tmp_path):
    """A readable file outside the books directory."""
    path = tmp_path / "secret.txt"
    path.write_text("TOP SECRET", encoding="utf-8")
    return path


def test_the_books_directory_is_the_shipped_one():
    assert items.BOOKS_DIR == items._REPO_ROOT / "src" / "resources" / "books"
    assert (items.BOOKS_DIR / "jambos-book-of-business-wisdom.txt").is_file()


def test_absolute_path_outside_the_books_dir_reads_blank(secret, caplog):
    with caplog.at_level(logging.WARNING, logger="src.items"):
        text = Book(text_file_path=str(secret)).text

    assert text == BLANK_BOOK
    assert "TOP SECRET" not in text
    assert any("outside" in r.getMessage() for r in caplog.records)


@pytest.mark.parametrize("spelling", [
    "src/resources/books/../../../{rel}",
    "src\\resources\\books\\..\\..\\..\\{rel}",
    "../{rel}",
])
def test_dot_dot_walks_out_of_the_books_dir_read_blank(spelling, tmp_path):
    """A repo-relative path that climbs out reads nothing, however spelled."""
    target = items._REPO_ROOT / "setup_probe_674.txt"
    target.write_text("REPO FILE", encoding="utf-8")
    try:
        rel = target.name
        text = Book(text_file_path=spelling.format(rel=rel)).text
    finally:
        target.unlink()
    assert text == BLANK_BOOK


def test_a_repo_file_outside_the_books_dir_reads_blank():
    """Inside the repo is not enough: CLAUDE.md is not a book."""
    assert Book(text_file_path="CLAUDE.md").text == BLANK_BOOK


def test_a_symlink_inside_the_books_dir_cannot_escape(secret, tmp_path, monkeypatch):
    books = tmp_path / "books"
    books.mkdir()
    link = books / "innocent.txt"
    try:
        link.symlink_to(secret)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable on this platform")
    monkeypatch.setattr(items, "BOOKS_DIR", books)

    assert Book(text_file_path=str(link)).text == BLANK_BOOK


def test_the_shipped_spellings_still_read():
    expected = (items._REPO_ROOT / SHIPPED).read_text(encoding="utf-8")
    assert Book(text_file_path=SHIPPED).text == expected
    assert Book(text_file_path=SHIPPED.replace("/", "\\")).text == expected
    absolute = str(items._REPO_ROOT / SHIPPED)
    assert Book(text_file_path=absolute).text == expected
