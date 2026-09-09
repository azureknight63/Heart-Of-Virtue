"""A doc block must sit on the thing it documents.

Six times on one branch (#567) a JSDoc block was silently re-parented onto
whatever declaration got inserted above the function it described, and each
occurrence was found by a human reader — twice by the reviewer who had just
watched the previous one get fixed. The mechanism is that `/** */` and Python
``#:`` blocks bind by ADJACENCY alone: nothing type-checks a comment, so the
edit that breaks one produces no signal at all, and inserting a constant is
the highest-risk edit there is.

The instances, so the shape is on record:

* ``LiveAnnouncer.jsx`` — the component's block on ``const VISUALLY_HIDDEN``.
* ``CombatLog.jsx`` — ``LogAnnouncer``'s block, ``@param props.entries`` and
  all, on ``const LOG_FADE_GROUND = '#030303'``.
* ``CooldownTray.jsx`` — ``cooldownLabel``'s block on ``const beatUnit``.
* ``RoomContents.jsx`` — the component's block on ``hostileMarkerFor``.
* ``AbortMoveControl.jsx`` — the component's block on ``export const HOLD_MS``.
* ``combat_adapter.py`` — two ``#:`` blocks fused, so the one describing
  ``_WEAPON_NOUN_PHRASES`` documented a single string instead.

This file is the guard. It is deliberately two narrow rules rather than one
clever one: a comment's *subject* is not decidable in general, so it checks
only the two shapes that actually recurred, and it is calibrated to zero
findings on a tree the reviewers have been over. On its first run it found two
MORE instances nobody had reported (``InteractPanel.jsx`` and
``useCombatCoordinator.js``), which is the whole argument for not relying on
vigilance here.
"""

import io
import pathlib
import re
import sys

import pytest

_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _frontend_sources():
    """Every non-test module under `frontend/src`."""
    base = _ROOT / "frontend" / "src"
    return sorted(
        path
        for path in base.rglob("*.js*")
        if ".test." not in path.name and "node_modules" not in str(path)
    )


#: What a `@param`/`@returns` block may legitimately sit on. Anything callable,
#: including the hook wrappers (`useCallback`, `useMemo`) and the two React
#: HOCs this codebase uses, plus object-literal members — `npcChat.js` documents
#: each endpoint of an exported object that way, which is fine.
_CALLABLE_SUBJECT = re.compile(
    r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?"
    r"(?:"
    r"function\b"
    r"|class\b"
    r"|(?:const|let|var)\s+\w+\s*=\s*(?:async\s*)?(?:\([^)]*\)|\w+)\s*=>"
    r"|(?:const|let|var)\s+\w+\s*=\s*(?:async\s+)?function\b"
    r"|(?:const|let|var)\s+\w+\s*=\s*(?:React\.)?(?:memo|forwardRef)\s*\("
    r"|(?:const|let|var)\s+\w+\s*=\s*use(?:Callback|Memo)\s*\("
    r"|\w+\s*:\s*(?:async\s*)?(?:\([^)]*\)|\w+)\s*=>"
    r"|\w+\s*\([^)]*\)\s*\{"
    r")"
)

_DECLARED = re.compile(
    r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?"
    r"(?:function\s+(\w+)|(?:const|let|var)\s+(\w+))",
    flags=re.M,
)


def _doc_blocks(lines):
    """Yield `(start, subject_line, gapped)` for each `/** */` block.

    `subject_line` is the next non-blank line after the block; `gapped` says
    whether a blank line separated them, which is itself a severance (an
    editor's hover-doc and every doc tool bind on adjacency).
    """
    index = 0
    while index < len(lines):
        if lines[index].strip().startswith("/**"):
            end = index
            while end < len(lines) and "*/" not in lines[end]:
                end += 1
            after = end + 1
            while after < len(lines) and not lines[after].strip():
                after += 1
            yield (
                index,
                "\n".join(lines[index:end + 1]),
                lines[after] if after < len(lines) else "",
                after > end + 1,
            )
            index = end + 1
        else:
            index += 1


def _named_subject(line):
    match = _DECLARED.match(line)
    return (match.group(1) or match.group(2)) if match else None


@pytest.mark.parametrize(
    "path", _frontend_sources(), ids=lambda p: p.name
)
def test_a_param_block_sits_on_something_callable(path):
    """`@param`/`@returns` describes a call signature, so its subject is one.

    This is the `CombatLog.jsx` and `AbortMoveControl.jsx` shape: a block with
    a full parameter list attached to a string or a number, while the function
    it describes sits below with no doc at all.
    """
    lines = io.open(path, encoding="utf-8").read().split("\n")
    offenders = [
        (start + 1, subject.strip()[:70])
        for start, block, subject, _gapped in _doc_blocks(lines)
        if ("@param" in block or "@returns" in block)
        and not _CALLABLE_SUBJECT.match(subject)
    ]
    assert not offenders, (
        f"{path.name}: a doc block with @param/@returns is not attached to "
        f"anything callable — {offenders}. A declaration was almost certainly "
        "inserted between the block and the function it describes; move the "
        "block back down. If the subject IS callable in a shape this guard "
        "does not know, widen _CALLABLE_SUBJECT rather than deleting the check."
    )


@pytest.mark.parametrize(
    "path", _frontend_sources(), ids=lambda p: p.name
)
def test_a_block_naming_a_declaration_sits_on_that_declaration(path):
    """A block opening with `Foo - …` must be attached to `Foo`.

    This is the `LiveAnnouncer.jsx` / `RoomContents.jsx` / `InteractPanel.jsx`
    shape: the component's own doc block, which names itself in its first
    line, left sitting on a constant or a helper that got inserted above it.
    Only fires when the named identifier is genuinely declared in the same
    file, so a block that merely opens with a capitalised English word is not
    flagged.
    """
    text = io.open(path, encoding="utf-8").read()
    lines = text.split("\n")
    declared = {
        name
        for pair in _DECLARED.findall(text)
        for name in pair
        if name
    }

    offenders = []
    for start, _block, subject, _gapped in _doc_blocks(lines):
        first = lines[start + 1] if start + 1 < len(lines) else ""
        match = re.match(r"\s*\*\s*([A-Z][A-Za-z0-9_]{2,})\b", first)
        if not match or match.group(1) not in declared:
            continue
        if _named_subject(subject) != match.group(1):
            offenders.append((start + 1, match.group(1), _named_subject(subject)))

    assert not offenders, (
        f"{path.name}: a doc block names one declaration and sits on another "
        f"— {offenders} as (line, named, actually_attached_to). Move the block "
        "onto the thing it names."
    )
