"""Content guard for Aldric's Tattered Journal in the Dark Grotto (issue #631).

The journal is one of the first readable objects in Jean's opening cave. It is
authored as a file-backed ``Book`` inside the "Remains" container, and two
independent mistakes can silently make the player read
"This book is mysteriously blank." instead of the prose:

* the ``text_file_path`` pointing at a file that does not exist, and
* an authored ``"text": ""`` prop, which the map loader ``setattr``s through
  ``Book.text``'s setter *after* construction. That leaves ``_text == ""``,
  which is not ``None``, so ``Book.text``'s lazy file read never fires at all
  and the dangling path is never even noticed.

Neither failure raises or logs, so this guard asserts on what the player
actually reads, built through the real map loader.
"""

import json
from pathlib import Path

from src.items import Book
from src.universe import Universe

REPO_ROOT = Path(__file__).resolve().parents[1]
DARK_GROTTO = REPO_ROOT / "src" / "resources" / "maps" / "dark-grotto.json"
BLANK = "This book is mysteriously blank."

# The shipped journal is ~1500 characters of prose. A floor of 400 is far below
# that but far above anything a truncated file, a stub, or the blank-book
# fallback (32 characters) could clear.
MIN_PROSE_CHARS = 400


def _iter_payloads(node):
    """Yield every ``{__class__, __module__, props}`` payload in a map subtree."""
    if isinstance(node, dict):
        if "__class__" in node and "__module__" in node:
            yield node
        for value in node.values():
            yield from _iter_payloads(value)
    elif isinstance(node, list):
        for value in node:
            yield from _iter_payloads(value)


def _journal_placements():
    """Every authored Tattered Journal payload, with its tile coordinate key."""
    raw = json.loads(DARK_GROTTO.read_text(encoding="utf-8"))
    found = []
    for coord, tile in raw.items():
        if coord == "metadata":
            continue
        for payload in _iter_payloads(tile):
            props = payload.get("props") or {}
            if (
                payload.get("__class__") == "Book"
                and props.get("name") == "Tattered Journal"
            ):
                found.append((coord, payload))
    return found


def test_tattered_journal_placement_population_is_non_empty():
    """Guard the guard: if the placement is renamed or removed, the content
    assertions below would pass by matching nothing."""
    assert _journal_placements(), (
        "No Book named 'Tattered Journal' found in dark-grotto.json -- the "
        "content guard would pass vacuously."
    )


def test_tattered_journal_renders_real_prose(monkeypatch):
    """The player must read Aldric's journal, not the blank-book fallback."""
    placements = _journal_placements()
    assert placements, "No Tattered Journal placement to exercise."

    # ``Book.text_file_path`` is authored relative to the repo root, which is
    # the working directory the game and API are launched from.
    monkeypatch.chdir(REPO_ROOT)

    for coord, payload in placements:
        # ``Book`` takes neither ``tile`` nor ``player``, so the loader's tile
        # injection is irrelevant here and the payload deserializes exactly as
        # it does when the map is loaded for a real session.
        book = Universe(player=None)._deserialize_saved_instance(payload)
        assert isinstance(book, Book), f"{coord}: journal failed to deserialize"

        text = book.text
        assert text != BLANK, (
            f"{coord}: the Tattered Journal renders the blank-book fallback. "
            f"text_file_path={book.text_file_path!r}"
        )
        assert len(text.strip()) > MIN_PROSE_CHARS, (
            f"{coord}: journal prose is too short ({len(text.strip())} chars): "
            f"{text!r}"
        )
        assert "Aldric" in text, f"{coord}: journal is not signed by Aldric"

        # It is a dated diary, and the Day 18 entry is the one the torn page at
        # (2, 3) already quotes to the player.
        assert "DAY 18" in text.upper(), f"{coord}: journal has no Day 18 entry"

        # The clue the chest puzzle depends on: the chest, and the key hidden
        # under the loose stones at the altar.
        lowered = text.lower()
        assert "chest" in lowered, f"{coord}: journal never mentions the chest"
        assert "key" in lowered, f"{coord}: journal never mentions the key"

        # The prose is longer than one page at the authored pagination width,
        # so the player gets a genuine multi-page read. A single page would
        # mean the file had shrunk to a stub.
        assert len(text) > book.chars_per_page
        pages = book._paginate_text(text)
        assert len(pages) >= 2, f"{coord}: journal paginated to {len(pages)} page(s)"


def test_tattered_journal_is_not_blanked_by_an_authored_empty_text_prop():
    """Regression for the trap in #631: writing the file is not enough.

    An authored ``text`` of ``""`` is applied through ``Book.text``'s setter by
    the loader and short-circuits the lazy file read, so the player still sees
    the blank-book string even though the file exists. This asserts on the
    authored JSON directly so the failure names the cause rather than only the
    symptom.
    """
    placements = _journal_placements()
    assert placements, "No Tattered Journal placement to exercise."
    for coord, payload in placements:
        authored = (payload.get("props") or {}).get("text")
        assert not isinstance(authored, str) or authored.strip(), (
            f'{coord}: authored "text" prop is empty -- this suppresses the '
            f"text_file_path load entirely. Omit the prop (as the shipped "
            f"Jambo book does) or author it as null."
        )
