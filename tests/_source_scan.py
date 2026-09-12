"""Engine-source discovery for the repo-wide structural scans.

A structural guard that walks ``src/**/*.py`` should take the walk from here
rather than spelling its own ``rglob``, the way they each used to (a few
older ones still do). The walk is the population such a guard asserts over
(``tests/_map_scan.py`` explains why one derivation matters), so it lives
here. ``py_files`` leaves reading to the caller, because the guards
disagree, correctly, about what an undecodable file means; ``src_trees`` is
the strict variant for guards that need syntax trees and treat an engine
file that will not parse as a failure.

``ROOT``, ``SRC_ROOT`` and ``MAP_DIR`` are the one spelling of the repo
layout the other shared scan modules build on. ``MAP_DIR`` lives here rather
than in ``tests/_map_scan.py`` so a pure-text guard can name the maps
directory without importing the engine.

No assertions live here; each caller proves non-emptiness itself.
"""

import ast
import functools
import pathlib
from typing import NamedTuple, Tuple

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC_ROOT = ROOT / "src"
MAP_DIR = SRC_ROOT / "resources" / "maps"


class SourceFile(NamedTuple):
    """One parsed engine module: its repo-relative posix name, its path, and
    its syntax tree.

    The path rides along because both consumers wanted it and each rebuilt it
    from the string differently -- one re-joining ``ROOT``, one stripping the
    ``src/`` prefix back off.
    """

    rel_posix: str
    path: pathlib.Path
    tree: ast.Module


def py_files(root: pathlib.Path) -> Tuple[pathlib.Path, ...]:
    """Every ``.py`` under ``root``, sorted, as a tuple -- walked once per tree.

    ``root`` is resolved before it keys the cache, so every spelling of one
    directory shares one walk. A relative ``root`` resolves against the
    current working directory, not the repo, so pass an absolute root such
    as ``SRC_ROOT``.
    """
    return _py_files(pathlib.Path(root).resolve())


@functools.lru_cache(maxsize=None)
def _py_files(root: pathlib.Path) -> Tuple[pathlib.Path, ...]:
    return tuple(sorted(root.rglob("*.py")))


@functools.lru_cache(maxsize=1)
def src_trees() -> Tuple[SourceFile, ...]:
    """A ``SourceFile`` for every ``src/**/*.py``, parsed once per worker.
    ``rel_posix`` is a forward-slash string (``"src/story/ch03.py"``) on every
    OS, so reports and comparisons built on it read the same everywhere.

    Strict: a file that does not decode or parse raises here. An engine file
    the interpreter cannot import is a failure, not something a structural
    guard should step over.
    """
    return tuple(
        SourceFile(
            path.relative_to(ROOT).as_posix(),
            path,
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path)),
        )
        for path in py_files(SRC_ROOT)
    )
