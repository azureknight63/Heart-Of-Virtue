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
population is non-empty and still contains the book path #611 fixed.

The one hand-kept list here is ``UNWRITTEN_BOOKS``, and it is asserted by
*exact equality* rather than as an exclusion: a new dangling path fails, and
so does writing one of the missing files, which forces the entry out of the
list instead of letting it rot.
"""

import functools
import pathlib
from typing import NamedTuple, Tuple

from tests._map_scan import map_data
from tests._source_scan import JSON_KEY_SUFFIX, ROOT, walk_json_strings

#: A value is treated as a file path when it carries a separator and ends in a
#: short extension. Deliberately loose: under-matching costs the guard, while
#: over-matching costs a prose string that happens to look like a path -- it
#: would then have to use forward slashes AND resolve to a real file, and the
#: fix is to tighten this rule rather than to bend the prose.
_EXTENSION_LENGTHS = range(2, 6)

#: Authored book paths that have no file behind them yet -- a content gap, not
#: a separator fault. Empty today, and asserted by equality below so an entry
#: cannot outlive its gap: the Dark Grotto's Tattered Journal sat here until
#: issue #631 wrote the text, and this guard is what reported that the entry
#: had gone stale. A new dangling path fails until it is either written or
#: named here with the reason.
UNWRITTEN_BOOKS: frozenset[str] = frozenset()

#: The path #611 fixed. The positive control names it rather than counting
#: books, so it fails if the scan stops reaching the very placement it exists
#: for.
JAMBO_BOOK = "src/resources/books/jambos-book-of-business-wisdom.txt"


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


@functools.lru_cache(maxsize=1)
def authored_paths() -> Tuple[AuthoredPath, ...]:
    """Every path-looking string value across every shipped map.

    Walked with the shared ``walk_json_strings``, so strings sitting directly
    in a list are seen too; keys are skipped, since a key is never a path.
    """
    return tuple(
        AuthoredPath(path.name, json_path.rsplit("/", 1)[-1], value.strip())
        for path, decoded in map_data()
        for json_path, value in walk_json_strings(decoded)
        if not json_path.endswith(JSON_KEY_SUFFIX) and _looks_like_a_path(value)
    )


def test_the_scan_finds_the_authored_paths_at_all():
    """Positive control: an empty scan would approve of every map forever."""
    found = authored_paths()
    assert found, "no authored file paths found in any shipped map -- scan is broken"
    keys = {entry.key for entry in found}
    assert "text_file_path" in keys, (
        "the scan stopped seeing book paths, which are the authored paths this "
        f"guard exists for; it matched these keys instead: {sorted(keys)}"
    )
    values = {entry.value for entry in found}
    assert JAMBO_BOOK in values, (
        f"the scan no longer reaches the book #611 fixed ({JAMBO_BOOK}); it "
        f"found: {sorted(values)}"
    )


def test_no_map_authors_a_windows_path_separator():
    """Regression test for issue #611 (a book in Jambo's tent that cannot be read).

    A backslash-separated path resolves on Windows and nowhere else, so the
    book it points at loads for the author and is blank for everyone running
    Linux or CI.

    Issue #648 taught ``Book.text`` to read a backslash as a separator, so a
    book no longer reads blank for this. The convention is kept anyway: this
    scan covers every authored path, not only books, and the resolution test
    below checks them as POSIX paths -- nothing else that reads an authored
    path has been taught the same tolerance.
    """
    offenders = [entry for entry in authored_paths() if "\\" in entry.value]
    assert offenders == [], (
        "authored map paths must use forward slashes -- a backslash path only "
        "resolves on Windows: " + "; ".join(e.describe() for e in offenders)
    )


def test_authored_paths_stay_inside_the_repo():
    """``Book.text`` opens what the map says. An absolute path or a ``..``
    segment reaches outside the repo, and the resolution test below cannot
    see it: ``ROOT / "/etc/passwd"`` discards ``ROOT`` entirely."""
    escaping = [
        entry
        for entry in authored_paths()
        if pathlib.PurePosixPath(entry.value).is_absolute()
        or pathlib.PureWindowsPath(entry.value).is_absolute()
        or ".." in pathlib.PurePosixPath(entry.value.replace("\\", "/")).parts
    ]
    assert escaping == [], (
        "authored map paths must be repo-relative with no '..': "
        + "; ".join(e.describe() for e in escaping)
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
    assert missing == UNWRITTEN_BOOKS, (
        "authored map paths must resolve from the repo root. Unexpectedly "
        f"missing: {sorted(missing - UNWRITTEN_BOOKS)}. Now present, so "
        f"remove from UNWRITTEN_BOOKS: {sorted(UNWRITTEN_BOOKS - missing)}"
    )
