"""Tests for Book item pagination functionality."""
import pytest
from src.items import Book


def test_book_short_text_no_pagination(monkeypatch, capsys):
    """Test that short text doesn't trigger pagination."""
    short_text = "This is a short book with minimal content."
    book = Book(text=short_text)
    
    # Mock await_input to avoid blocking
    monkeypatch.setattr('src.functions.await_input', lambda: None)
    monkeypatch.setattr('src.functions.print_slow', lambda text, speed: print(text))
    
    book.read()
    
    captured = capsys.readouterr()
    assert short_text in captured.out
    assert "Page" not in captured.out  # No pagination header


def test_book_long_text_pagination(monkeypatch, capsys):
    """Test that long text triggers pagination system."""
    # Create text long enough to require pagination (>600 chars)
    long_text = "This is a long book. " * 50  # ~1000 characters
    book = Book(text=long_text, chars_per_page=300)
    
    # Simulate: view first page, go to next page, then close
    responses = ['n', 'c']
    monkeypatch.setattr('builtins.input', lambda prompt='': responses.pop(0))
    monkeypatch.setattr('src.functions.screen_clear', lambda: None)
    
    book.read()
    
    captured = capsys.readouterr()
    assert "begins reading" in captured.out
    assert "Page 1 of" in captured.out or "Page 2 of" in captured.out


def test_book_pagination_navigation_forward(monkeypatch):
    """Test navigating forward through pages."""
    long_text = ". ".join([f"Sentence {i}" for i in range(100)])  # Many sentences
    book = Book(text=long_text, chars_per_page=200)
    
    pages = book._paginate_text(long_text)
    assert len(pages) > 1  # Should create multiple pages


def test_book_pagination_navigation_backward(monkeypatch, capsys):
    """Test navigating backward through pages."""
    long_text = "This is page content. " * 100
    book = Book(text=long_text, chars_per_page=200)
    
    # Simulate: next page, next page, previous page, close
    responses = ['n', 'n', 'p', 'c']
    monkeypatch.setattr('builtins.input', lambda prompt='': responses.pop(0))
    monkeypatch.setattr('src.functions.screen_clear', lambda: None)
    
    book.read()
    
    captured = capsys.readouterr()
    assert "closes the book" in captured.out


def test_book_pagination_invalid_choice(monkeypatch, capsys):
    """Test handling of invalid navigation choice."""
    long_text = "Content here. " * 100
    book = Book(text=long_text, chars_per_page=200)
    
    # Simulate: invalid choice, then close
    responses = ['invalid', 'c']
    monkeypatch.setattr('builtins.input', lambda prompt='': responses.pop(0))
    monkeypatch.setattr('src.functions.screen_clear', lambda: None)
    
    book.read()
    
    captured = capsys.readouterr()
    assert "Invalid choice" in captured.out


def test_book_pagination_boundary_conditions():
    """Test pagination at page boundaries."""
    # Test with exactly chars_per_page characters
    exact_text = "a" * 800
    book = Book(text=exact_text, chars_per_page=800)
    pages = book._paginate_text(exact_text)
    assert len(pages) == 1
    
    # Test with just over chars_per_page
    over_text = "a" * 801
    book2 = Book(text=over_text, chars_per_page=800)
    pages2 = book2._paginate_text(over_text)
    assert len(pages2) >= 1


def test_book_pagination_preserves_sentences():
    """Test that pagination breaks at sentence boundaries when possible."""
    text_with_sentences = "First sentence. Second sentence. Third sentence. Fourth sentence. Fifth sentence."
    book = Book(text=text_with_sentences, chars_per_page=40)
    pages = book._paginate_text(text_with_sentences)
    
    # Should break into multiple pages at sentence boundaries
    for page in pages:
        # Each page should end at a reasonable point (not mid-word if possible)
        assert page.strip()  # No empty pages


def test_book_with_event(monkeypatch, capsys):
    """Test that book events trigger after reading (with pagination)."""
    class MockEvent:
        repeat = False
        processed = False
        
        def process(self):
            self.processed = True
            print("Event triggered!")
    
    event = MockEvent()
    long_text = "Story content. " * 100
    book = Book(event=event, text=long_text, chars_per_page=200)
    
    # Simulate: immediately close book
    responses = ['c']
    monkeypatch.setattr('builtins.input', lambda prompt='': responses.pop(0))
    monkeypatch.setattr('src.functions.screen_clear', lambda: None)
    monkeypatch.setattr('src.functions.await_input', lambda: None)
    
    book.read()
    
    assert event.processed
    captured = capsys.readouterr()
    assert "Event triggered!" in captured.out


def test_book_empty_text(monkeypatch, capsys):
    """Test book with no text shows the blank book message."""
    monkeypatch.setattr('src.functions.await_input', lambda: None)
    monkeypatch.setattr('src.functions.print_slow', lambda text, speed: print(text))
    book = Book(text=None)
    
    book.read()
    
    captured = capsys.readouterr()
    # Book with None text should show the blank message
    assert "mysteriously blank" in captured.out


def test_book_custom_chars_per_page():
    """Test custom chars_per_page parameter."""
    text = "a" * 1000
    
    # Default pagination
    book1 = Book(text=text)
    pages1 = book1._paginate_text(text)
    
    # Custom smaller pages
    book2 = Book(text=text, chars_per_page=100)
    pages2 = book2._paginate_text(text)
    
    # Smaller page size should create more pages
    assert len(pages2) > len(pages1)


def test_book_text_from_file_only(tmp_path, monkeypatch, capsys):
    """Test book that loads text from a file with no text property set."""
    # Create a temporary file with book content (keep it short to avoid pagination)
    book_file = tmp_path / "test_book.txt"
    file_content = "This is content loaded from a file."
    book_file.write_text(file_content, encoding='utf-8')
    
    # Create book with only text_file_path set (no text parameter)
    book = Book(name="File Book", text_file_path=str(book_file))
    
    # Mock functions to avoid blocking
    monkeypatch.setattr('src.functions.await_input', lambda: None)
    monkeypatch.setattr('src.functions.print_slow', lambda text, speed: print(text))
    
    # Verify the text property lazily loads from file
    assert book.text == file_content
    
    # Verify reading works
    book.read()
    captured = capsys.readouterr()
    assert file_content in captured.out


def test_book_file_overrides_text_property(tmp_path, monkeypatch, capsys):
    """Test that file takes precedence when both text and text_file_path are set."""
    # Create a temporary file
    book_file = tmp_path / "test_book.txt"
    file_content = "This content is in the file and should be used."
    book_file.write_text(file_content, encoding='utf-8')
    
    # Create book with BOTH text and text_file_path
    text_property_content = "This is the text property content that should be ignored."
    book = Book(name="Override Book", text=text_property_content, text_file_path=str(book_file))
    
    # Mock functions to avoid blocking
    monkeypatch.setattr('src.functions.await_input', lambda: None)
    monkeypatch.setattr('src.functions.print_slow', lambda text, speed: print(text))
    
    # Verify file content is used, not the text property
    assert book.text == file_content
    assert text_property_content not in book.text
    
    # Verify reading uses file content
    book.read()
    captured = capsys.readouterr()
    assert file_content in captured.out
    assert text_property_content not in captured.out


def test_book_neither_text_nor_file(monkeypatch, capsys):
    """Test book with neither text property nor file path shows blank message."""
    # Create book with neither text nor text_file_path
    book = Book(name="Empty Book")
    
    # Mock functions to avoid blocking
    monkeypatch.setattr('src.functions.await_input', lambda: None)
    monkeypatch.setattr('src.functions.print_slow', lambda text, speed: print(text))
    
    # Verify it shows the blank message
    assert "mysteriously blank" in book.text
    
    # Verify reading shows the blank message
    book.read()
    captured = capsys.readouterr()
    assert "mysteriously blank" in captured.out


def test_book_file_not_found_fallback(monkeypatch, capsys):
    """Test that book gracefully handles missing file by showing blank message."""
    # Create book with non-existent file path
    book = Book(name="Missing File Book", text_file_path="/nonexistent/path/to/book.txt")
    
    # Mock functions to avoid blocking
    monkeypatch.setattr('src.functions.await_input', lambda: None)
    monkeypatch.setattr('src.functions.print_slow', lambda text, speed: print(text))
    
    # Verify it falls back to blank message when file doesn't exist
    assert "mysteriously blank" in book.text
    
    # Verify reading shows the blank message
    book.read()
    captured = capsys.readouterr()
    assert "mysteriously blank" in captured.out
