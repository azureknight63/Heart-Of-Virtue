# Book Pagination Feature

## Overview

The `Book` item now supports automatic pagination for long text content. When a player reads a book with text longer than 600 characters, the content is automatically broken into pages with navigation controls.

**Note:** `Book` is now an item (subclass of `Special`) that can be carried in inventory, rather than a tile object.

## Features

### Automatic Pagination
- Books with text longer than 600 characters are automatically paginated
- Shorter texts display normally without pagination
- Smart page breaks at sentence boundaries when possible
- Handles edge cases like very long sentences or text without punctuation

### Navigation Controls
Players can navigate through book pages using simple commands:
- **N** or **Next**: Go to the next page (if available)
- **P** or **Previous** or **Prev**: Go to the previous page (if available)
- **C** or **Close** or **X** or **Exit**: Close the book

### Page Display
Each page shows:
- Book name and current page number in header
- Content wrapped to 80 characters for readability
- Page number footer
- Available navigation options

## Usage

### Basic Usage
```python
from src.items import Book

# Short book (no pagination)
short_book = Book(
    name="Small Note",
    text="A brief inscription.",
    description="A small note."
)

# Long book (with pagination, default 800 chars per page)
long_book = Book(
    name="Ancient Tome",
    text="<very long text here>",
    description="An ancient tome."
)
```

### Custom Page Size
You can customize the characters per page:
```python
# Smaller pages for denser content
detailed_book = Book(
    name="Detailed Manuscript",
    text=long_text,
    description="A detailed manuscript.",
    chars_per_page=500  # Custom page size
)
```

### With Events
Books can still have events that trigger after reading:
```python
from src.events import Event

book_with_event = Book(
    player=player,
    tile=tile,
    text=long_text,
    description="A mysterious grimoire.",
    event=some_event  # Event triggers after reading (and closing)
)
```

## Implementation Details

### Pagination Logic
1. Text is split at sentence boundaries (periods, exclamation marks, question marks)
2. Sentences are grouped into pages up to `chars_per_page` characters
3. If a single sentence exceeds `chars_per_page`, it's force-split at character boundaries
4. Empty pages are automatically filtered out

### Thresholds
- **Pagination threshold**: 600 characters (hardcoded in `read()` method)
- **Default page size**: 800 characters (can be customized via `chars_per_page` parameter)
- **Display width**: 80 characters per line

### Screen Management
- Uses `functions.screen_clear()` to clear the screen between pages
- Pages are wrapped using Python's `textwrap.fill()` for consistent formatting
- Color-coded navigation prompts for better user experience

## Testing

A comprehensive test suite is available in `tests/test_book_pagination.py` covering:
- Short text (no pagination)
- Long text (with pagination)
- Forward/backward navigation
- Invalid input handling
- Boundary conditions
- Sentence preservation
- Event triggering
- Custom page sizes

Run tests with:
```bash
pytest tests/test_book_pagination.py -v
```

## Demo

An interactive demonstration is available in `demo_book_pagination.py`:
```bash
# Run all demos
python demo_book_pagination.py

# Run specific demo
python demo_book_pagination.py 1  # Short book
python demo_book_pagination.py 2  # Long book
python demo_book_pagination.py 3  # Custom page size
```

## Backward Compatibility

The pagination feature is fully backward compatible:
- Existing books with short text work exactly as before
- Books without text continue to display descriptions
- All existing book parameters remain unchanged
- New optional `chars_per_page` parameter defaults to 800

## Future Enhancements

Possible future improvements:
- Bookmarks to remember last page read
- Search functionality within book text
- Multiple text sections/chapters
- Page numbers in save/load system
- Illustration support on certain pages
