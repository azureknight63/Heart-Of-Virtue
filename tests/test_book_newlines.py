"""Test that book pagination preserves newlines in text."""
import re

import pytest
from src.items import Book


def test_book_preserves_double_newlines_in_pagination():
    """Test that double newlines (paragraph breaks) are preserved during pagination."""
    text_with_paragraphs = """First paragraph with some content here.

Second paragraph has different content.

Third paragraph appears at the end."""

    book = Book(text=text_with_paragraphs, chars_per_page=200)
    pages = book._paginate_text(text_with_paragraphs)

    # Should preserve the double newlines
    assert '\n\n' in pages[0], "Double newlines (paragraph breaks) should be preserved"


def test_book_preserves_multiple_paragraphs():
    """Test that multiple paragraphs with blank lines between them are preserved."""
    text = """Paragraph one.

Paragraph two.

Paragraph three.

Paragraph four."""

    book = Book(text=text, chars_per_page=500)
    pages = book._paginate_text(text)

    # Count double newlines - should have at least 3 (between 4 paragraphs)
    page_content = pages[0]
    double_newline_count = page_content.count('\n\n')
    assert double_newline_count >= 3, f"Expected at least 3 paragraph breaks, got {double_newline_count}"


def test_book_display_preserves_paragraph_formatting(monkeypatch, capsys):
    """Test that the _display_page method preserves paragraph breaks when displaying."""
    text = """First paragraph with content.

Second paragraph with more content."""

    book = Book(text=text, chars_per_page=200)
    monkeypatch.setattr('src.functions.screen_clear', lambda: None)

    # Display the first page
    pages = book._paginate_text(text)
    book._display_page(pages[0], 1, len(pages))

    captured = capsys.readouterr()
    # Check that there's a blank line in the output (two consecutive newlines)
    assert '\n\n' in captured.out, "Display should preserve paragraph breaks with blank lines"


def test_book_single_newlines_preserved():
    """Test that single newlines within content are also preserved."""
    text = """Line one
Line two
Line three

New paragraph."""

    book = Book(text=text, chars_per_page=200)
    pages = book._paginate_text(text)

    # Should preserve both single newlines and double newlines
    assert '\n' in pages[0], "Single newlines should be preserved"
    assert '\n\n' in pages[0], "Double newlines should be preserved"


def test_book_from_file_preserves_newlines(tmp_path, monkeypatch, capsys):
    """Test that newlines are preserved when loading from a file."""
    # Create a file with paragraphs
    book_file = tmp_path / "test_book_newlines.txt"
    file_content = """TITLE

This is the first paragraph.

This is the second paragraph.

This is the third paragraph."""
    book_file.write_text(file_content, encoding='utf-8')

    # Create book from file
    book = Book(name="Test Book", text_file_path=str(book_file), chars_per_page=300)

    # Check that text preserves newlines
    assert '\n\n' in book.text, "Text loaded from file should preserve double newlines"

    # Check pagination preserves newlines
    pages = book._paginate_text(book.text)
    assert '\n\n' in pages[0], "Pagination should preserve double newlines from file"


def test_book_long_text_paginates_without_losing_or_duplicating_text():
    """Pagination must be lossless: every page respects the size limit and the
    pages, concatenated, hold exactly the original characters.

    The old assertion here was ``if '\n' in page: assert page.count('\n') > 0``
    -- literally ``if X: assert X``. It could not fail, which meant a paginator
    that silently dropped a page (or repeated one) passed.
    """
    paragraphs = [
        f"This is paragraph number {i}. It has some content to make it "
        f"reasonably long so we can test pagination properly. Let's add "
        f"more text here."
        for i in range(10)
    ]
    text = "\n\n".join(paragraphs)

    book = Book(text=text, chars_per_page=300)
    pages = book._paginate_text(text)

    assert len(pages) > 1, "Long text should create multiple pages"
    assert all(len(page) <= 300 for page in pages), [len(p) for p in pages]
    # rstrip()/page-boundary whitespace is the only thing pagination may alter.
    squash = lambda s: re.sub(r"\s+", "", s)          # noqa: E731
    assert squash("".join(pages)) == squash(text)
    # Every paragraph must still be findable somewhere in the paginated output.
    for i in range(10):
        assert f"paragraph number {i}" in "".join(pages)


def test_book_paginates_a_sentence_longer_than_a_whole_page():
    """A single over-long sentence is force-split rather than dropped."""
    sentence = "word " * 200                      # ~1000 chars, no '. '
    book = Book(text=sentence, chars_per_page=100)
    pages = book._paginate_text(sentence)

    assert len(pages) > 1
    assert all(len(page) <= 100 for page in pages)
    squash = lambda s: re.sub(r"\s+", "", s)          # noqa: E731
    assert squash("".join(pages)) == squash(sentence)


def test_short_text_is_a_single_page_and_empty_text_is_no_pages():
    assert Book(text="Short.", chars_per_page=100)._paginate_text("Short.") == ["Short."]
    assert Book(text="", chars_per_page=100)._paginate_text("") == []


def test_book_edge_case_only_newlines():
    """Test edge case where text is mostly newlines."""
    text = "\n\n\n\nSome text\n\n\n\n"

    book = Book(text=text, chars_per_page=100)
    pages = book._paginate_text(text)

    # Should handle gracefully and preserve structure
    assert len(pages) >= 1
    # The content should have the text
    combined = ''.join(pages)
    assert 'Some text' in combined


def test_book_mixed_sentence_endings_with_newlines():
    """Test that sentence endings and newlines work together correctly."""
    text = """First sentence. Second sentence.

New paragraph! This is exciting.

Final paragraph? Maybe so."""

    book = Book(text=text, chars_per_page=200)
    pages = book._paginate_text(text)

    # Should preserve paragraph breaks
    assert '\n\n' in pages[0]
    # Should still break on sentences if needed
    assert 'First sentence' in pages[0]
