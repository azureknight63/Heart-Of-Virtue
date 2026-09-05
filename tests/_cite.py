"""Derived cross-file citations, so a comment cannot cite a line that moved.

Hand-written ``File.jsx:123`` references are the dominant defect class in this
repo's review history. They are wrong on arrival or wrong a round later, and
nothing catches either: the number is prose, and prose is not executed. Five
separate reviewers reached the same conclusion independently -- one of them
after watching a *correct* docstring fix break the count on the line above it,
and another after finding ``InteractPanel:768`` written by hand two files away
from a scanner that derives the same fact properly.

The cure is not a better-maintained number. It is not writing the number.

:class:`Read` names a file and an *anchor* -- a literal string the citing code
claims is there. The line numbers are computed at failure time, so they are
always current, and the anchor is asserted to exist, which catches the drift a
line number silently hides. An entry with no literal anchor says so out loud
via ``note=``, and :func:`unverifiable` makes that set countable, so "we could
not check this one" is a number a test can hold rather than a gap nobody sees.

Usage::

    CONTRACT = {
        "targeted": Read("CombatMovePanel.jsx", "move.targeted"),
        "position": Read("BattlefieldGrid.jsx", note="destructured in getPos"),
    }

    # in the failure message
    Read("CombatMovePanel.jsx", "move.targeted").describe()
    # -> "CombatMovePanel.jsx:80,142 move.targeted"
"""

from __future__ import annotations

import io
import os
from typing import Dict, List, NamedTuple, Optional, Sequence

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Directories a citation may name a file in. Kept narrow on purpose: a
#: citation that resolves into ``node_modules`` is a citation of somebody
#: else's code, which this repo has no business pinning.
_SEARCH_ROOTS = ("frontend/src", "src", "ai", "tools", "tests")

_SKIP_DIRS = {"node_modules", "__pycache__", ".git", "dist", "build", "coverage"}

_index_cache: Optional[Dict[str, List[str]]] = None


def _index() -> Dict[str, List[str]]:
    """basename -> every path carrying it, built once per process."""
    global _index_cache
    if _index_cache is None:
        found: Dict[str, List[str]] = {}
        for root in _SEARCH_ROOTS:
            base = os.path.join(_REPO_ROOT, root)
            for dirpath, dirnames, filenames in os.walk(base):
                dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
                for filename in filenames:
                    found.setdefault(filename, []).append(
                        os.path.join(dirpath, filename)
                    )
        _index_cache = found
    return _index_cache


class CitationError(AssertionError):
    """A citation names a file that cannot be resolved to exactly one path."""


class Read(NamedTuple):
    """One consumer of a wire field, cited by anchor rather than by line.

    ``file`` is a basename (``"CombatMovePanel.jsx"``) or a repo-relative path
    when the basename is ambiguous. ``anchor`` is a literal substring of that
    file -- normally the member expression the consumer actually evaluates.
    ``note`` replaces the anchor for the cases where no single literal exists
    (a destructured prop, a value threaded through a rename); such an entry is
    honest about being unverifiable instead of pretending to a line number.
    """

    file: str
    anchor: Optional[str] = None
    note: Optional[str] = None

    # -- resolution ------------------------------------------------------

    def path(self) -> str:
        """The one file this citation names, or raise."""
        direct = os.path.join(_REPO_ROOT, self.file.replace("/", os.sep))
        if os.path.isfile(direct):
            return direct
        candidates = _index().get(os.path.basename(self.file), [])
        if self.file != os.path.basename(self.file):
            wanted = self.file.replace("/", os.sep)
            candidates = [p for p in candidates if p.endswith(wanted)]
        if len(candidates) == 1:
            return candidates[0]
        if not candidates:
            raise CitationError(
                "citation names %r, which does not exist under %s"
                % (self.file, ", ".join(_SEARCH_ROOTS))
            )
        rel = sorted(os.path.relpath(p, _REPO_ROOT) for p in candidates)
        raise CitationError(
            "citation names %r, which is ambiguous between %s -- cite a "
            "repo-relative path instead of a bare basename"
            % (self.file, ", ".join(rel))
        )

    def lines(self) -> Sequence[int]:
        """1-based lines where ``anchor`` appears. Empty when it does not."""
        if not self.anchor:
            return ()
        with io.open(self.path(), encoding="utf-8", errors="replace") as handle:
            return tuple(
                n for n, text in enumerate(handle, 1) if self.anchor in text
            )

    # -- reporting -------------------------------------------------------

    def describe(self) -> str:
        """``File.jsx:80,142 move.targeted`` -- computed, never stored.

        Degrades honestly: a missing anchor reports the note, and an anchor
        that has gone missing says so rather than printing a stale number.
        """
        if not self.anchor:
            return "%s (%s)" % (self.file, self.note or "no anchor recorded")
        hits = self.lines()
        if not hits:
            return "%s ANCHOR NOT FOUND: %s" % (self.file, self.anchor)
        return "%s:%s %s" % (
            self.file,
            ",".join(str(n) for n in hits[:4]) + ("..." if len(hits) > 4 else ""),
            self.anchor,
        )

    def __str__(self) -> str:  # so an f-string in a failure message just works
        return self.describe()


def verify(reads) -> List[str]:
    """Every anchored citation that no longer finds its anchor.

    This is the half a line number cannot give you. A stale ``:123`` still
    renders as a plausible reference; a stale anchor is a test failure.
    """
    broken = []
    for read in reads:
        if read.anchor and not read.lines():
            broken.append(
                "%s: anchor %r not found in that file" % (read.file, read.anchor)
            )
    return broken


def unverifiable(reads) -> List["Read"]:
    """Citations carrying a note instead of an anchor.

    Exposed so a suite can assert the size of its own blind spot. An unchecked
    citation is acceptable; an unchecked citation nobody counts is how the
    class this module exists to close got started.
    """
    return [r for r in reads if not r.anchor]
