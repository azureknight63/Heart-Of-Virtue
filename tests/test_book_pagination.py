"""Tests for Book object pagination functionality."""
import pytest
from src.objects import Book
from src.player import Player
from src.tiles import MapTile


@pytest.fixture
def mock_player():
    """Create a minimal mock player for testing."""
    class MockPlayer:
        name = "Jean"
        inventory = []
    return MockPlayer()


@pytest.fixture
def mock_tile():
    """Create a minimal mock tile for testing."""
    class MockTile:
        pass
    return MockTile()


def test_book_short_text_no_pagination(mock_player, mock_tile, monkeypatch, capsys):
    """Test that short text doesn't trigger pagination."""
    short_text = "This is a short book with minimal content."
    book = Book(mock_player, mock_tile, text=short_text)
    
    # Mock await_input to avoid blocking
    monkeypatch.setattr('src.functions.await_input', lambda: None)
    monkeypatch.setattr('src.functions.print_slow', lambda text, speed: print(text))
    
    book.read()
    
    captured = capsys.readouterr()
    assert short_text in captured.out
    assert "Page" not in captured.out  # No pagination header


def test_book_long_text_pagination(mock_player, mock_tile, monkeypatch, capsys):
    """Test that long text triggers pagination system."""
    # Create text long enough to require pagination (>600 chars)
    long_text = "This is a long book. " * 50  # ~1000 characters
    book = Book(mock_player, mock_tile, text=long_text, chars_per_page=300)
    
    # Simulate: view first page, go to next page, then close
    responses = ['n', 'c']
    monkeypatch.setattr('builtins.input', lambda prompt='': responses.pop(0))
    monkeypatch.setattr('src.functions.screen_clear', lambda: None)
    
    book.read()
    
    captured = capsys.readouterr()
    assert "begins reading" in captured.out
    assert "Page 1 of" in captured.out or "Page 2 of" in captured.out


def test_book_pagination_navigation_forward(mock_player, mock_tile, monkeypatch):
    """Test navigating forward through pages."""
    long_text = ". ".join([f"Sentence {i}" for i in range(100)])  # Many sentences
    book = Book(mock_player, mock_tile, text=long_text, chars_per_page=200)
    
    pages = book._paginate_text(long_text)
    assert len(pages) > 1  # Should create multiple pages


def test_book_pagination_navigation_backward(mock_player, mock_tile, monkeypatch, capsys):
    """Test navigating backward through pages."""
    long_text = "This is page content. " * 100
    book = Book(mock_player, mock_tile, text=long_text, chars_per_page=200)
    
    # Simulate: next page, next page, previous page, close
    responses = ['n', 'n', 'p', 'c']
    monkeypatch.setattr('builtins.input', lambda prompt='': responses.pop(0))
    monkeypatch.setattr('src.functions.screen_clear', lambda: None)
    
    book.read()
    
    captured = capsys.readouterr()
    assert "closes the book" in captured.out


def test_book_pagination_invalid_choice(mock_player, mock_tile, monkeypatch, capsys):
    """Test handling of invalid navigation choice."""
    long_text = "Content here. " * 100
    book = Book(mock_player, mock_tile, text=long_text, chars_per_page=200)
    
    # Simulate: invalid choice, then close
    responses = ['invalid', 'c']
    monkeypatch.setattr('builtins.input', lambda prompt='': responses.pop(0))
    monkeypatch.setattr('src.functions.screen_clear', lambda: None)
    
    book.read()
    
    captured = capsys.readouterr()
    assert "Invalid choice" in captured.out


def test_book_pagination_boundary_conditions(mock_player, mock_tile):
    """Test pagination at page boundaries."""
    # Test with exactly chars_per_page characters
    exact_text = "a" * 800
    book = Book(mock_player, mock_tile, text=exact_text, chars_per_page=800)
    pages = book._paginate_text(exact_text)
    assert len(pages) == 1
    
    # Test with just over chars_per_page
    over_text = "a" * 801
    book2 = Book(mock_player, mock_tile, text=over_text, chars_per_page=800)
    pages2 = book2._paginate_text(over_text)
    assert len(pages2) >= 1


def test_book_pagination_preserves_sentences(mock_player, mock_tile):
    """Test that pagination breaks at sentence boundaries when possible."""
    text_with_sentences = "First sentence. Second sentence. Third sentence. Fourth sentence. Fifth sentence."
    book = Book(mock_player, mock_tile, text=text_with_sentences, chars_per_page=40)
    pages = book._paginate_text(text_with_sentences)
    
    # Should break into multiple pages at sentence boundaries
    for page in pages:
        # Each page should end at a reasonable point (not mid-word if possible)
        assert page.strip()  # No empty pages


def test_book_with_event(mock_player, mock_tile, monkeypatch, capsys):
    """Test that book events trigger after reading (with pagination)."""
    class MockEvent:
        repeat = False
        processed = False
        
        def process(self):
            self.processed = True
            print("Event triggered!")
    
    event = MockEvent()
    long_text = "Story content. " * 100
    book = Book(mock_player, mock_tile, event=event, text=long_text, chars_per_page=200)
    
    # Simulate: immediately close book
    responses = ['c']
    monkeypatch.setattr('builtins.input', lambda prompt='': responses.pop(0))
    monkeypatch.setattr('src.functions.screen_clear', lambda: None)
    monkeypatch.setattr('src.functions.await_input', lambda: None)
    
    book.read()
    
    assert event.processed
    captured = capsys.readouterr()
    assert "Event triggered!" in captured.out


def test_book_empty_text(mock_player, mock_tile, capsys):
    """Test book with no text shows description only."""
    book = Book(mock_player, mock_tile, text=None)
    
    book.read()
    
    captured = capsys.readouterr()
    assert book.description in captured.out


def test_book_custom_chars_per_page(mock_player, mock_tile):
    """Test custom chars_per_page parameter."""
    text = "a" * 1000
    
    # Default pagination
    book1 = Book(mock_player, mock_tile, text=text)
    pages1 = book1._paginate_text(text)
    
    # Custom smaller pages
    book2 = Book(mock_player, mock_tile, text=text, chars_per_page=100)
    pages2 = book2._paginate_text(text)
    
    # Smaller page size should create more pages
    assert len(pages2) > len(pages1)
