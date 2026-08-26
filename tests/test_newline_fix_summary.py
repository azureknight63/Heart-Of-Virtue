"""Book pagination must preserve paragraph structure and sentence spacing.

Regression cover for the newline-preservation fix in ``Book._paginate_text`` /
``Book._display_page``: sentence splitting used to drop ``\\n`` characters, and
``textwrap.fill`` used to collapse blank lines, so a multi-section book came
back as one run-on paragraph.

Every assertion here is exact. The previous version of this file spelled its
checks as ``'x. y' in text or 'x.  y' in text`` and
``'heading\\n\\n' in text or 'heading\\n' in text`` — pairs that accept both the
fixed and the broken output, so the "paragraph breaks are preserved" claim
would have passed against single-newline output, and the "sentences have
proper spacing" claim against doubled spaces. It also joined the pages with
``''.join(pages)``, which drops the separator that pagination legitimately
consumes at a page boundary, and then asserted on the result.
"""

import pytest

from src.items import Book
from src.narration import capture_narration

_MULTI_SECTION_TEXT = (
    "TITLE OF BOOK\n"
    "\n"
    "This is the first paragraph. It contains multiple sentences. Each "
    "sentence should be separated by spaces.\n"
    "\n"
    "SECTION HEADING\n"
    "\n"
    "This is the second paragraph in a new section. It also has several "
    "sentences. They should flow naturally.\n"
    "\n"
    "This is a third paragraph. More content here. And even more.\n"
    "\n"
    "FINAL SECTION\n"
    "\n"
    "The final paragraph wraps everything up. It should maintain proper "
    "spacing. And preserve paragraph breaks."
)


@pytest.fixture(scope="module")
def single_page_book():
    """chars_per_page above the text length, so pagination is a pass-through
    and every structural assertion is about the text itself, not page breaks."""
    return Book(
        name="Test Book",
        text=_MULTI_SECTION_TEXT,
        chars_per_page=len(_MULTI_SECTION_TEXT) + 1,
    )


def test_text_short_enough_for_one_page_is_returned_verbatim(single_page_book):
    """The whole point of the fix: nothing is rewritten on the way through."""
    pages = single_page_book._paginate_text(_MULTI_SECTION_TEXT)

    assert pages == [_MULTI_SECTION_TEXT]


def test_paragraph_breaks_survive_pagination(single_page_book):
    page = single_page_book._paginate_text(_MULTI_SECTION_TEXT)[0]

    # Exactly a blank line, not a single newline, after every section heading.
    assert "TITLE OF BOOK\n\nThis is the first paragraph." in page
    assert "SECTION HEADING\n\nThis is the second paragraph" in page
    assert "FINAL SECTION\n\nThe final paragraph" in page
    assert page.count("\n\n") == 6


def test_sentences_are_separated_by_exactly_one_space(single_page_book):
    page = single_page_book._paginate_text(_MULTI_SECTION_TEXT)[0]

    assert "sentences. Each sentence" in page
    assert "sentences.  Each" not in page  # the split must not double the space
    assert "sentences.Each" not in page  # ...nor swallow it


def test_pagination_splits_at_a_sentence_boundary_without_losing_text():
    """Two pages, each within budget, and together they reproduce the source
    once the separator consumed at the boundary is put back."""
    book = Book(name="Test Book", text=_MULTI_SECTION_TEXT, chars_per_page=400)

    pages = book._paginate_text(_MULTI_SECTION_TEXT)

    assert len(pages) == 2
    assert all(0 < len(page) <= 400 for page in pages)
    assert pages[0].endswith("It should maintain proper spacing.")
    assert pages[1] == "And preserve paragraph breaks."
    assert " ".join(pages) == _MULTI_SECTION_TEXT


def test_display_page_wraps_without_collapsing_blank_lines(single_page_book):
    """_display_page runs each paragraph through textwrap separately, so the
    blank lines between them survive (textwrap.fill over the whole page would
    have eaten them, which was half the original defect)."""
    with capture_narration() as messages:
        single_page_book._display_page(_MULTI_SECTION_TEXT, 1, 1)

    texts = [m["text"] for m in messages]
    assert texts[0] == "--- Test Book (Page 1 of 1) ---"
    assert texts[-1] == "--- Page 1 of 1 ---"

    body = next(t for t in texts if "SECTION HEADING" in t)
    assert "SECTION HEADING\n\nThis is the second paragraph" in body
    assert body.count("\n\n") == 6
    assert all(len(line) <= 80 for line in body.splitlines())


def test_read_emits_every_page_in_order(single_page_book):
    with capture_narration() as messages:
        single_page_book.read()

    texts = [m["text"] for m in messages]
    assert texts[0] == "Jean begins reading..."
    assert _MULTI_SECTION_TEXT in texts


def test_book_loaded_from_a_file_keeps_its_paragraph_breaks(tmp_path):
    realistic_content = (
        "MERCHANT'S GUIDE\n"
        "(A Short Manual)\n"
        "\n"
        "LESSON ONE: Be Honest\n"
        "Honesty is the best policy. Customers appreciate it. They will return.\n"
        "\n"
        "LESSON TWO: Know Your Products\n"
        "You must understand what you sell. This builds trust.\n"
        "\n"
        "CONCLUSION\n"
        "\n"
        "Follow these lessons for success. Good luck!"
    )
    book_file = tmp_path / "realistic_book.txt"
    book_file.write_text(realistic_content, encoding="utf-8")

    book = Book(
        name="Merchant's Guide",
        text_file_path=str(book_file),
        chars_per_page=len(realistic_content) + 1,
    )

    assert book.text == realistic_content
    assert book._paginate_text(book.text) == [realistic_content]
    # Single newlines inside a paragraph are kept too, not upgraded or dropped.
    assert "LESSON ONE: Be Honest\nHonesty is the best policy." in book.text
