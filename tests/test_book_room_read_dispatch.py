"""Regression test for issue #598 (bug 1): room-placed Book "read" dispatch.

``GameService._dispatch_interaction`` resolves a room object's interaction verb
through ``src.objects.resolve_interaction``, which reads ``KEYWORD_METHOD_ALIASES``
off the target's class MRO and falls back to a bare ``getattr(target, action)``
when the class declares no alias. ``Book`` (``src/items.py``) declared no such
alias, so a room-placed book's authored "read" keyword resolved straight to
``Book.read()`` -- the terminal-era method that paginates long text and wraps
every page in ``--- Title (Page N of M) ---`` markers for a pagination prompt
the web client no longer drives -- instead of ``Book.use()``, the clean
single-block method ``/inventory/use`` and the frontend's own
``BookReaderDialog`` pagination are built around.
``BookReaderDialog.stripBookWrapper`` (``frontend/src/components/BookReaderDialog.jsx``)
only strips one leading/trailing line, so any book long enough to paginate
(over ~600 characters, like "Jambo's Little Book of Big Deals" at 3853 chars)
displayed with leftover page-marker lines baked into the middle of the text in
the Read panel.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import src.items as items  # noqa: E402
from src.objects import resolve_interaction  # noqa: E402
from src.narration import capture_narration  # noqa: E402
from src.api.services.game_service import _call_interaction_handler  # noqa: E402


def _long_book(name="Jambo's Little Book of Big Deals"):
    """A Book whose text is long enough (> 600 chars) to hit the pagination
    branch of ``Book.read()``."""
    sentence = "Deal number one is always better than the last one. "
    text = (sentence * 20).strip()
    assert len(text) > 600
    return items.Book(name=name, text=text, merchandise=False)


def test_resolve_interaction_routes_book_read_to_use():
    """resolve_interaction(book, "read") must hand back Book.use, not Book.read."""
    book = _long_book()

    handler = resolve_interaction(book, "read")

    assert handler is not None, "'read' must resolve to something callable"
    assert handler.__func__ is items.Book.use, (
        "room-based 'read' on a Book resolved to "
        f"{getattr(handler, '__func__', handler)!r} -- it must dispatch through "
        "Book.use(), not the terminal-era Book.read() (issue #598)"
    )


def test_room_book_read_output_has_no_pagination_markers():
    """The narration a room 'read' interaction produces must match use()'s
    clean single-block output, not read()'s paginated
    '--- Title (Page N of M) ---' wrapped pages.

    Dispatches through the same helper ``GameService._dispatch_interaction``
    uses (``_call_interaction_handler``) so this exercises the real calling
    convention rather than assuming a signature.
    """
    book = _long_book()
    handler = resolve_interaction(book, "read")

    with capture_narration() as messages:
        _call_interaction_handler(handler, None, None)

    text = "\n".join(m["text"] for m in messages)
    assert "Page 1 of" not in text, (
        "room-based read still emits Book.read()'s pagination header:\n" + text
    )
    assert f"--- {book.name} ---" in text, (
        "expected Book.use()'s clean '--- Title ---' wrapper, got:\n" + text
    )
