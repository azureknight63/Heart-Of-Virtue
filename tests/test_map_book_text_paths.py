"""Every ``text_file_path`` a shipped map authors actually loads.

``Book.text`` (``src/items.py``) swallows a failed open and hands the player
"This book is mysteriously blank." instead, so the only evidence of a broken
authored path is a line in a server log nobody reads. That is how Jambo's book
came to read blank at Grondia's Tent Lounge: the map authored
``src\\resources\\books\\...``, which opened for its Windows author and not on
Linux.

**This guard must not normalise, and that is the whole point.** Checking
``os.path.exists(raw.replace("\\", "/"))`` would have passed on the bug this
exists to catch: by normalised existence the tree read "2 of 3 paths resolve";
by the open the engine actually performed it read "1 of 3 resolves on Linux".
So the check goes through a real ``Book`` and asserts the player does not get
the blank-book fallback -- the engine's own open, on the authored string, as
authored.

**Issue #648 moved the normalisation into the engine, deliberately.**
``Book._resolve_text_path`` now reads a backslash as a separator, so the
Windows spelling resolves at runtime rather than being caught here at test
time. This guard still does no normalising of its own: it agrees with the new
behaviour because it asks the engine, and the separator control below was
rewritten on purpose to pin that agreement rather than left to flip silently.
The authoring convention -- forward slashes only -- is still enforced, by
``tests/test_map_authored_file_paths.py``.

#648 also found a second, silent blank-book mechanism the raw-``Book`` check
could not see: an authored ``"text": ""`` arrives as a post-construction
``setattr`` through the legacy loader and, under the old ``_text is None``
gate, suppressed the file entirely. The placement test at the bottom therefore
also builds each book from its **full authored prop set** through
``Universe._deserialize_saved_instance``, the loader the shipped maps use.

The authored paths are relative; ``Book.text`` anchors them at the repo root.
The test still pins the CWD with ``chdir`` so nothing depends on where pytest
was invoked.
"""

import os
from typing import Any, Iterator, List, NamedTuple, Set

import pytest

from src.items import Book
from src.universe import Universe
from tests import _map_scan
from tests._source_scan import ROOT

#: What ``Book.text`` returns when the open fails -- and also what a book
#: authored with neither text nor a path returns. Any authored
#: ``text_file_path`` reaching it means the file did not load.
BLANK_BOOK = "This book is mysteriously blank."

#: Authored paths whose target file is not written yet. Exempt entries are
#: SUBTRACTED from the offenders rather than asserted to BE offenders, so an
#: entry can be retired in the commit that writes its file instead of failing
#: alongside it. A newly dangling path is still a failure -- only these exact
#: authored strings are excused, so re-authoring one with Windows separators
#: would not slip through either.
#:
#: **Empty is the healthy state, and it is the state today.** An exemption is
#: a hole in this guard for that one path: while it sits here, deleting or
#: renaming the file behind it keeps this test green. Add one only while a
#: book is genuinely mid-write, and delete it in the commit that lands the
#: file -- issue #631's ``tattered-journal.txt`` entry outlived its own change
#: set exactly that way.
KNOWN_UNWRITTEN: Set[str] = set()

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


class BookPlacement(NamedTuple):
    """One authored book placement: its path, and the payload that carries it."""

    map_name: str
    json_path: str
    raw: str
    payload: dict

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


def _walk_placements(node: Any, map_name: str, json_path: str) -> Iterator[BookPlacement]:
    """Every whole placement payload whose props author a ``text_file_path``.

    The payload, not just the path: ``_walk`` above sees the one key, and so
    cannot see a sibling prop (an authored ``"text": ""``) that stops the
    engine from ever opening it.
    """
    if isinstance(node, dict):
        for key in ("props", "params"):
            props = node.get(key)
            if isinstance(props, dict) and isinstance(props.get("text_file_path"), str):
                yield BookPlacement(map_name, json_path, props["text_file_path"], node)
        for key, child in node.items():
            yield from _walk_placements(child, map_name, f"{json_path}.{key}")
    elif isinstance(node, list):
        for index, child in enumerate(node):
            yield from _walk_placements(child, map_name, f"{json_path}[{index}]")


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


def test_guard_reads_through_a_real_book_open(books_dir_in_tmp):
    """Control for the check itself: ``BLANK_BOOK`` has to be discriminating.

    A readable file must come back as its contents, and an authored path with
    nothing behind it must come back blank. Without this pair, the offender
    test below could be comparing against a constant that never matches -- or
    one that always does. Both paths here are absolute and natively spelled,
    so unlike the separator control this holds on every platform.
    """
    book_file = books_dir_in_tmp / "control.txt"
    book_file.write_text("readable", encoding="utf-8")

    assert Book(text_file_path=str(book_file)).text == "readable"
    assert Book(text_file_path=str(books_dir_in_tmp / "absent.txt")).text == BLANK_BOOK


@pytest.mark.skipif(
    os.name == "nt",
    reason=(
        "Windows resolves '\\' and '/' interchangeably, so the backslashed "
        "spelling below opens there with or without the engine's help and no "
        "control can tell the two apart. The defect -- authored on Windows, "
        "blank on Linux -- is POSIX-only, and CI runs on Linux."
    ),
)
def test_guard_reads_separators_the_way_the_engine_does(at_repo_root, books_dir_in_tmp):
    """Control for the check itself: it must read paths the way the engine does.

    Before #648 this asserted a backslashed path came back **blank**, because
    that is what the engine did. #648 changed the engine, so the assertion was
    inverted deliberately: a real, readable file named with backslash
    separators -- the shape the Grondia map authored -- now reads. The guard
    still performs no normalisation itself; it passes because ``Book`` does.

    ``at_repo_root`` is not decoration: backslashing an absolute POSIX path
    yields ``\\tmp\\...``, which is *relative*, so the engine anchors it at the
    repo root -- where it resolves to nothing. The spelling used here is
    therefore made relative to the repo root first, as a map would author it.
    """
    book_file = books_dir_in_tmp / "control.txt"
    book_file.write_text("readable", encoding="utf-8")
    relative = os.path.relpath(book_file, ROOT)
    backslashed = relative.replace("/", "\\")
    assert "\\" in backslashed

    assert Book(text_file_path=relative).text == "readable"
    assert Book(text_file_path=backslashed).text == "readable"


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


def test_authored_book_placements_load_through_the_map_loader(at_repo_root):
    """Each book built from its full authored prop set, as the game builds it.

    Issue #648: a raw ``Book(text_file_path=...)`` cannot see a sibling prop
    that suppresses the open -- an authored ``"text": ""`` did exactly that,
    silently. So every placement goes through the real loader, and the
    placement count must match the path count: a placement the walk misses
    would otherwise approve itself by absence.
    """
    placements = [
        placement
        for map_file, decoded in _map_scan.map_data()
        for placement in _walk_placements(decoded, map_file.name, "")
    ]
    assert len(placements) == len(_authored_book_paths()), (
        "the placement walk and the path walk disagree on how many books are "
        "authored; a book whose payload is not reached is not checked here"
    )

    universe = Universe()
    offenders = []
    for placement in placements:
        if placement.raw in KNOWN_UNWRITTEN:
            continue
        book = universe._deserialize_saved_instance(placement.payload)
        if not isinstance(book, Book) or book.text == BLANK_BOOK:
            offenders.append(placement)

    assert not offenders, (
        "authored book placements that hand the player "
        f"{BLANK_BOOK!r} once loaded through the map loader:\n  "
        + "\n  ".join(str(offender) for offender in offenders)
    )
