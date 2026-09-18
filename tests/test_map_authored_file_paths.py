"""Structural guard: file paths authored into the shipped map JSON.

Issue #611 reported a book in Jambo's tent that could not be read. Two separate
faults produced that symptom, and this module guards the second of them:
``grondia-jambos_shop.json`` authored its book as
``"src\\resources\\books\\..."`` -- Windows separators -- while the same file is
referenced with forward slashes elsewhere. ``open()`` resolves the backslash
form on Windows only. On Linux and in CI the path does not resolve,
``Book.text``'s ``except`` fires, and the book reads "This book is mysteriously
blank." The failure is silent, platform-dependent, and invisible to anyone
authoring on Windows -- which is the whole reason it needs a guard rather than
a careful author.

**The population is derived, not hand-kept.** Every string value in every
shipped map that looks like a path to a file is collected by walking the
decoded JSON, so a new authored path is covered the day it lands, under
whatever key name it is given. A scan that stops matching approves of
everything forever (``tests/_map_scan.py`` says the same thing at more
length), so ``test_the_scan_finds_the_authored_paths_at_all`` asserts the
population is non-empty and still contains the book paths we know are there.

The one hand-kept list here is ``UNWRITTEN_BOOKS``, and it is asserted by
*exact equality* rather than as an exclusion: a new dangling path fails, and
so does writing one of the missing files, which forces the entry out of the
list instead of letting it rot.
"""

import pathlib
from typing import Any, Iterator, List, NamedTuple, Tuple

from tests._map_scan import map_data
from tests._source_scan import ROOT

#: A value is treated as a file path when it carries a separator and ends in a
#: short extension. Deliberately loose: over-matching costs a prose string that
#: happens to look like a path (which would then have to survive the same
#: separator rule, no hardship), while under-matching costs the guard.
_EXTENSION_LENGTHS = range(2, 6)

#: Authored book paths that have no file behind them yet -- a content gap, not
#: a separator fault. The Tattered Journal in the Dark Grotto (tile (6, 3),
#: "the merchant's final thoughts") authors a path whose text was never
#: written, so it reads as blank exactly like the #611 book did. Writing it is
#: narrative work, not a path fix. Asserted by equality below, so the entry
#: cannot outlive the gap.
UNWRITTEN_BOOKS = frozenset({"src/resources/books/tattered-journal.txt"})


class AuthoredPath(NamedTuple):
    """One path-looking string value found in a shipped map."""

    map_name: str
    key: str
    value: str

    def describe(self) -> str:
        return f"{self.map_name}: {self.key} = {self.value!r}"


def _looks_like_a_path(value: str) -> bool:
    if "/" not in value and "\\" not in value:
        return False
    tail = value.strip().rsplit(".", 1)
    if len(tail) != 2:
        return False
    return len(tail[1]) in _EXTENSION_LENGTHS and tail[1].isalnum()


def _walk(node: Any, map_name: str) -> Iterator[AuthoredPath]:
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(value, str) and _looks_like_a_path(value):
                yield AuthoredPath(map_name, str(key), value.strip())
            else:
                yield from _walk(value, map_name)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value, map_name)


def authored_paths() -> Tuple[AuthoredPath, ...]:
    """Every path-looking string value across every shipped map."""
    found: List[AuthoredPath] = []
    for path, decoded in map_data():
        found.extend(_walk(decoded, path.name))
    return tuple(found)


def test_the_scan_finds_the_authored_paths_at_all():
    """Positive control: an empty scan would approve of every map forever."""
    found = authored_paths()
    assert found, "no authored file paths found in any shipped map -- scan is broken"
    keys = {entry.key for entry in found}
    assert "text_file_path" in keys, (
        "the scan stopped seeing book paths, which are the authored paths this "
        f"guard exists for; it matched these keys instead: {sorted(keys)}"
    )
    books = [e for e in found if e.key == "text_file_path"]
    assert len(books) >= 3, (
        f"expected at least the three shipped book placements, found {len(books)}: "
        f"{[e.describe() for e in books]}"
    )


def test_no_map_authors_a_windows_path_separator():
    """Regression test for issue #611 (a book in Jambo's tent that cannot be read).

    A backslash-separated path resolves on Windows and nowhere else, so the
    book it points at loads for the author and is blank for everyone running
    Linux or CI.
    """
    offenders = [entry for entry in authored_paths() if "\\" in entry.value]
    assert offenders == [], (
        "authored map paths must use forward slashes -- a backslash path only "
        "resolves on Windows: " + "; ".join(e.describe() for e in offenders)
    )


def test_authored_paths_are_repo_relative_and_resolve():
    """Every authored path must point at a file that exists, bar the known gaps.

    ``UNWRITTEN_BOOKS`` is compared by equality, not subtracted: adding a new
    dangling path fails here, and so does writing one of the missing files,
    which is what stops the list going stale.
    """
    missing = {
        entry.value
        for entry in authored_paths()
        if not (ROOT / pathlib.PurePosixPath(entry.value)).is_file()
    }
    assert missing == set(UNWRITTEN_BOOKS), (
        "authored map paths must resolve from the repo root. Unexpectedly "
        f"missing: {sorted(missing - set(UNWRITTEN_BOOKS))}. Now present, so "
        f"remove from UNWRITTEN_BOOKS: {sorted(set(UNWRITTEN_BOOKS) - missing)}"
    )
