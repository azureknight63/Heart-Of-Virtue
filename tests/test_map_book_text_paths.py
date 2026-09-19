"""Every ``text_file_path`` a shipped map authors actually loads.

``Book.text`` (``src/items.py``) opens ``self.text_file_path`` **raw** -- no
``os.path.normpath``, no ``pathlib`` round-trip -- and swallows the failure,
handing the player "This book is mysteriously blank." instead. So a map
authored on Windows with ``src\\resources\\books\\...`` loads fine for its
author and ships silently blank to production, where the only evidence is a
red line in a server log nobody reads. That is exactly how Jambo's book came
to read blank at Grondia's Tent Lounge.

**This guard must not normalise, and that is the whole point.** Checking
``os.path.exists(raw.replace("\\", "/"))`` would have passed on the bug this
exists to catch: by normalised existence the tree read "2 of 3 paths resolve";
by the open the engine actually performs it read "1 of 3 resolves on Linux".
So the check goes through a real ``Book`` and asserts the player does not get
the blank-book fallback -- the engine's own open, on the authored string, as
authored.

The authored paths are relative, so they resolve against the process CWD. The
game and the API both run from the repo root; the test pins that with
``chdir`` rather than inheriting whatever directory pytest was invoked from.
"""

from typing import Any, Iterator, List, NamedTuple

import pytest

from src.items import Book
from tests import _map_scan
from tests._source_scan import ROOT

#: What ``Book.text`` returns when the open fails -- and also what a book
#: authored with neither text nor a path returns. Any authored
#: ``text_file_path`` reaching it means the file did not load.
BLANK_BOOK = "This book is mysteriously blank."

#: Authored paths whose target file is not written yet. Exempt entries are
#: SUBTRACTED from the offenders rather than asserted to BE offenders: issue
#: #631 is writing ``tattered-journal.txt``, and an equality-asserted
#: allow-list would start failing the moment that lands. A newly dangling path
#: is still a failure -- only these exact authored strings are excused, so
#: re-authoring one with Windows separators would not slip through either.
KNOWN_UNWRITTEN = {
    # #631 -- the Dark Grotto's tattered journal has a placement but no text
    # file behind it yet; being written separately.
    "src/resources/books/tattered-journal.txt",
}

#: Positive-control floor. Three ``text_file_path`` references ship today; if
#: the walk below ever matches fewer, the key was renamed or the authored
#: shape moved and this guard has quietly retired -- a scan that matches
#: nothing approves of everything.
MINIMUM_AUTHORED_BOOK_PATHS = 3


class BookPath(NamedTuple):
    """One authored ``text_file_path``, and where in the tree it was written."""

    map_name: str
    json_path: str
    raw: str

    def __str__(self) -> str:
        return f"{self.map_name}{self.json_path} -> {self.raw!r}"


def _walk(node: Any, map_name: str, json_path: str) -> Iterator[BookPath]:
    """Every ``text_file_path`` anywhere in one decoded map.

    Recursive rather than ``_map_scan.object_placements()`` on purpose: the
    references in the tree sit in more than one shape -- a tile ``items``
    entry, and one nested inside a container's ``inventory`` -- and the shared
    placement walk deliberately does not descend into a payload's props.
    Population completeness is what matters here; this guard never needs the
    class resolution that walk provides.
    """
    if isinstance(node, dict):
        value = node.get("text_file_path")
        if isinstance(value, str):
            yield BookPath(map_name, json_path, value)
        for key, child in node.items():
            yield from _walk(child, map_name, f"{json_path}.{key}")
    elif isinstance(node, list):
        for index, child in enumerate(node):
            yield from _walk(child, map_name, f"{json_path}[{index}]")


def _authored_book_paths() -> List[BookPath]:
    """Every authored ``text_file_path`` in the shipped maps.

    Built on ``_map_scan.map_data()`` rather than a private ``json.loads``:
    that parse is the shared, per-worker-cached one the map guards agree on,
    and "which files are the maps" is derived in exactly one place. The
    decoded dicts are shared, so this walk only ever reads them.
    """
    found: List[BookPath] = []
    for map_file, decoded in _map_scan.map_data():
        found.extend(_walk(decoded, map_file.name, ""))
    return found


@pytest.fixture
def at_repo_root(monkeypatch):
    """Run from the repo root, as the API and the game loop do."""
    monkeypatch.chdir(ROOT)


def test_walk_finds_the_authored_book_paths():
    """Positive control: the scan still matches the references that ship."""
    found = _authored_book_paths()
    assert len(found) >= MINIMUM_AUTHORED_BOOK_PATHS, (
        f"the text_file_path walk matched {len(found)} references; it should "
        f"match at least {MINIMUM_AUTHORED_BOOK_PATHS}. The key was probably "
        "renamed -- a scan that matches nothing approves of everything."
    )


def test_guard_does_not_normalise_separators(at_repo_root, tmp_path):
    """Control for the check itself: it must read paths the way the engine does.

    A real, readable file named with backslash separators -- the shape the
    Grondia map authored -- still has to come back blank here. If it did not,
    this guard would be measuring ``os.path.exists`` on a normalised copy and
    would have passed on the defect it was written for.

    ``at_repo_root`` is not decoration: backslashing an absolute POSIX path
    yields ``\\tmp\\...``, which is *relative*, so what it resolves against is
    the CWD. Pinning that keeps the assertion from depending on where pytest
    happened to be invoked.
    """
    book_file = tmp_path / "control.txt"
    book_file.write_text("readable", encoding="utf-8")
    backslashed = str(book_file).replace("/", "\\")

    assert Book(text_file_path=str(book_file)).text == "readable"
    assert Book(text_file_path=backslashed).text == BLANK_BOOK


def test_authored_book_paths_are_readable(at_repo_root):
    """The engine's own open, on each authored string, exactly as authored."""
    offenders = [
        authored
        for authored in _authored_book_paths()
        if authored.raw not in KNOWN_UNWRITTEN
        and Book(name="guard", text_file_path=authored.raw).text == BLANK_BOOK
    ]

    assert not offenders, (
        "authored book paths that hand the player "
        f"{BLANK_BOOK!r}:\n  "
        + "\n  ".join(str(offender) for offender in offenders)
        + "\nBook.text opens the authored string raw, so Windows separators "
        "resolve for their author and fail on Linux. Author map paths with "
        "forward slashes."
    )
