"""Reading frontend constants from Python, for the cross-language guards.

Several guards hold a JS constant to the Python value it mirrors, and each grew
its own reader -- ``test_combat_beat_schema.py``, ``test_event_type_contract.py``,
``test_combat_glossary_contract.py``, ``test_move_categories_ui_contract.py``
and ``test_move_web_animations.py`` all read an exported constant by hand. A
new guard should take ``js_literal`` from here instead; the older ones still
spell their own, and migrating them belongs to whoever next touches those
files. ``test_narration_emotions.py``'s reader is NOT among them: it matches a
bare ``<binding> = [...]`` because one of its call sites is ``emotionState``
in ``tools/portrait_splitter.html``, which exports nothing.

What it covers is one shape: a FLAT literal. The scan closes on the first
bracket matching the one it opened with, so a literal nested in the SAME
bracket type (``[[1], 2]``) truncates and raises; the other bracket type
happens to survive the scan and is untested territory, not support. A bare
string or number must sit on one line; a bracketed literal may span lines, as
``WAIT_DURATION_PROMPT`` does -- see ``js_literal``. Reading something else
out of JS still means writing it: ``test_wire_field_contract.py``'s
``_js_builder_keys`` takes the KEY SET of a builder's object literal, and
stayed there because it has one consumer and a different job.

No assertion about a POPULATION lives here (see ``tests/_map_scan.py`` for
why): a caller proves its own. A constant this cannot find or read does raise,
naming it.
"""

import ast
import pathlib
from typing import Any

from tests._source_scan import ROOT

#: Where the frontend's modules live -- the one spelling of that layout for
#: guards reaching across the boundary, built on ``_source_scan``'s ``ROOT``
#: rather than re-deriving it.
FRONTEND_SRC = ROOT / "frontend" / "src"


def js_literal(path: pathlib.Path, name: str) -> Any:
    """The value of ``export const <name> = <literal>`` in ``path``.

    Deliberately narrow. The literal is read from the ``=`` to the first
    ``]``/``}`` -- or to the end of the line for a bare string or number --
    and evaluated with ``ast.literal_eval``, so:

    * it must be FLAT: a literal nested in the same bracket type truncates,
      because the scan closes on the first matching bracket;
    * it must be a literal Python also understands, which covers both JS quote
      styles but not ``true``/``false``/``null``.

    A trailing ``;`` is stripped, so a semicolon-terminated module reads too.

    Either way it raises here, naming the constant, rather than quietly
    comparing as something else.
    """
    source = path.read_text(encoding="utf-8")
    # Exactly this spelling: one space either side of the ``=``, and the
    # literal beginning on the same line. Said in the failure message too,
    # because "exports no const named X" otherwise names the wrong cause for a
    # constant written ``export const X =`` with the value on the next line.
    marker = f"export const {name} = "
    try:
        start = source.index(marker) + len(marker)
    except ValueError:
        raise AssertionError(
            f"{path.name} exports no const named {name} as "
            f"`export const {name} = <literal>`"
        ) from None
    try:
        # Every lookup is inside the try: an unclosed literal, a bare scalar
        # on a final line with no trailing newline, and a file ending at the
        # marker each raise here, and a bare "substring not found" or
        # "string index out of range" names nothing.
        closer = {"[": "]", "{": "}"}.get(source[start])
        end = source.index(closer, start) + 1 if closer else source.index("\n", start)
        return ast.literal_eval(source[start:end].strip().rstrip(";"))
    except (IndexError, ValueError, SyntaxError) as exc:
        raise AssertionError(
            f"{name} in {path.name} is not a flat literal Python can read: {exc}"
        ) from None
