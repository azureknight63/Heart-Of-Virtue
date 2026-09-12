"""Guards against cp1252-mis-decoded UTF-8 punctuation ("mojibake") surviving
in authored content (issue #578).

Em dashes in ``eastern-descent-nomad-camp.json`` were stored as
``U+00E2 U+20AC U+201D`` instead of a single ``U+2014`` -- the byte sequence
you get by taking the UTF-8 bytes of a real em dash (``E2 80 94``) and
reinterpreting each one as its own windows-1252 code point instead of
decoding all three as one UTF-8 character. The JSON source stores the result
as three separate ``\\uXXXX`` escapes, so a raw-text grep for the mojibake
*characters* finds nothing -- ``json.load`` has to run first to turn the
escapes into the code points this guard looks for. That trap is why earlier
passes over that map were waved through as "clean".

Everything the scan looks for is derived from code points by
``_build_mojibake_sequences`` -- never from a literal typed into this file --
because a module about mis-decoded punctuation is not where an editor's or
terminal's encoding assumptions should get a chance to re-mangle the
characters under test. The parametrize rows of
``test_mis_decode_reproduces_known_corruptions`` are fixed, byte-verified
corruptions, written as escapes like everything else here, that pin the
derivation itself.

The scan walks every JSON file under ``src/resources/`` and ``ai/`` (skipping
hidden paths), decodes each one, and checks every string -- keys and values,
never the raw file text -- for the mis-decode of any character in the two
Unicode blocks authored prose in this repo actually uses: the printable half
of Latin-1 Supplement (accented letters, the non-breaking space) and General
Punctuation (dashes, curly quotes, the ellipsis, bullets, and their
neighbours). It also walks every ``src/**/*.py`` file twice: as text lines,
and as the *values* of its string literals, because a literal spelled
``"\\u00e2\\u20ac\\u201d"`` is plain ASCII on the page and carries the
corruption only once evaluated -- the same trap the JSON escapes set.
"""

import ast
import functools
import json
import pathlib
import re
import unicodedata
from collections import Counter
from typing import NamedTuple

import pytest

from tests._source_scan import MAP_DIR, ROOT, SRC_ROOT, py_files

#: The two roots the issue asked this guard to cover: shipped map/content
#: JSON and the AI personality/config JSON. Hidden paths (any dot-prefixed
#: file or directory) are excluded from the walk: ``ai/.model_cache.json`` is
#: a gitignored runtime cache written from a remote provider's catalogue, not
#: authored content.
_CONTENT_JSON_ROOTS = (
    SRC_ROOT / "resources",
    ROOT / "ai",
)


class Violation(NamedTuple):
    """One report row: which file, where in it, which pattern, what context."""

    file: str
    where: str
    pattern: str
    snippet: str


#: ``where`` for a whole-file problem, and the one ``pattern`` label per kind
#: of failure -- the same label from both scanners.
_FILE_LEVEL = "file"
_NOT_READABLE = "NOT READABLE"
_NOT_UTF8 = "NOT VALID UTF-8"
_NOT_PARSEABLE = "NOT PARSEABLE"


def _line_where(line_no):
    """``where`` for a hit the text scan found on ``line_no``."""
    return f"line {line_no}"


def _literal_where(line_no):
    """``where`` for a hit the evaluated-literal scan found on ``line_no``."""
    return f"literal at line {line_no}"


def _cp1252_char(byte):
    """One byte decoded the way real windows-1252 decoders decode it.

    Python's strict ``cp1252`` codec raises on the byte values (0x81, 0x8D,
    0x8F, 0x90, 0x9D) the official table leaves undefined. Browsers, the
    WHATWG windows-1252 decoder and Windows' ``MultiByteToWideChar`` pass
    those through as the identically numbered code point instead, which is
    what an actual mis-decode in the wild produces. Decoding one byte at a
    time keeps that rule here, rather than in a codecs error handler that
    would have to be registered for the whole process.
    """
    try:
        return bytes([byte]).decode("cp1252")
    except UnicodeDecodeError:
        return chr(byte)


def _mis_decode(char):
    """The mojibake a "declared the wrong charset" pipeline produces for ``char``.

    Encodes as UTF-8 and decodes those bytes as windows-1252, one code point
    per byte -- reproducing, rather than hand-transcribing, the exact
    corruption #578 reported: U+2014 became U+00E2 U+20AC U+201D.
    """
    return "".join(_cp1252_char(byte) for byte in char.encode("utf-8"))


#: The printable half of Latin-1 Supplement (U+00A0-U+00FF; the C1 controls
#: U+0080-U+009F are not prose) and all of General Punctuation
#: (U+2000-U+206F). Building the watch list from the blocks rather than from
#: "the ones issue #578 happened to name" is what makes the guard durable: a
#: mis-decoded guillemet or per-mille sign trips it exactly as an em dash
#: does, without anyone having thought to list either.
_WATCHED_CODE_POINTS = tuple(range(0x00A0, 0x0100)) + tuple(range(0x2000, 0x2070))


def _pattern_name(code_point):
    """``U+2014 (EM DASH)`` -- the label a violation is reported under."""
    return f"U+{code_point:04X} ({unicodedata.name(chr(code_point), 'UNNAMED')})"


def _build_mojibake_sequences():
    """``{pattern name: mis-decoded sequence}`` for every watched code point.

    Every watched character is at least two UTF-8 bytes, so every mis-decode
    is at least two characters and never the character itself; a derivation
    that produced anything else is broken, and says so here rather than
    quietly shrinking the watch set.
    """
    sequences = {}
    for code_point in _WATCHED_CODE_POINTS:
        char = chr(code_point)
        mis_decoded = _mis_decode(char)
        assert len(mis_decoded) > 1 and mis_decoded != char, (
            f"mis-decode derivation broke for U+{code_point:04X}: {mis_decoded!r}"
        )
        sequences[_pattern_name(code_point)] = mis_decoded
    return sequences


_MOJIBAKE_SEQUENCES = _build_mojibake_sequences()
_SEQUENCE_TO_NAME = {seq: name for name, seq in _MOJIBAKE_SEQUENCES.items()}

#: One compiled alternation over every derived sequence: a single C-level
#: pass per string or line instead of one ``str.find`` per sequence. No
#: sequence is a prefix of another today (two-character hits start with
#: U+00C2/U+00C3, three-character ones with U+00E2); longest-first ordering
#: keeps the match right if a future block ever changes that.
_MOJIBAKE_RE = re.compile(
    "|".join(
        re.escape(seq)
        for seq in sorted(_MOJIBAKE_SEQUENCES.values(), key=len, reverse=True)
    )
)


def _as_unicode_escapes(text):
    """``text`` spelled as ``\\uXXXX`` escapes -- ASCII on the page."""
    return "".join(f"\\u{ord(char):04x}" for char in text)


#: The code points the positive controls exercise -- the one #578 reported
#: mangled, and a Latin-1 letter for the shorter two-character shape -- with
#: the mis-decode and report label each is expected under.
_EM_DASH = 0x2014
_EM_DASH_MOJIBAKE = _mis_decode(chr(_EM_DASH))
_EM_DASH_ESCAPED = _as_unicode_escapes(_EM_DASH_MOJIBAKE)
_EM_DASH_PATTERN = _pattern_name(_EM_DASH)
_E_ACUTE = 0x00E9
_E_ACUTE_MOJIBAKE = _mis_decode(chr(_E_ACUTE))
_E_ACUTE_PATTERN = _pattern_name(_E_ACUTE)

#: Where the corruption goes in an f-string control: each control body is
#: written as the f-string it will be, with these standing in for the text
#: form and the escape form until ``.replace`` fills them in. ASCII with no
#: braces, so they need no escaping anywhere.
_TEXT_SLOT = "@TEXT@"
_ESCAPE_SLOT = "@ESCAPED@"

#: What a line carrying the corruption both as characters and as escapes
#: reports: the text form from the line scan, the escape form from the
#: literal scan.
_BOTH_FORMS_ON_LINE_1 = [
    (_line_where(1), _EM_DASH_PATTERN),
    (_literal_where(1), _EM_DASH_PATTERN),
]

#: Joins an f-string's literal parts into one text, sitting between each two
#: consecutive parts: ASCII, so no derived sequence can match across a join.
_FIELD_MARK = "{}"


def _snippet(text, start, end, radius=25):
    """``radius`` characters of context either side of the hit."""
    return text[max(0, start - radius):end + radius]


def _rel(path):
    """``path`` relative to the repo root for the report; a file outside the
    tree (the positive controls write to ``tmp_path``) keeps its own name."""
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return path.name


def _hit_row(text, match):
    """``(pattern name, snippet)`` for one regex match in ``text``."""
    return _SEQUENCE_TO_NAME[match.group()], _snippet(text, match.start(), match.end())


def _sequence_hits(text):
    """Yield ``(pattern name, snippet)`` for every mis-decode in ``text``.

    Every occurrence, not just the first per sequence: the failure message
    lists each one so a fix pass needs no second run to find the rest.
    """
    for match in _MOJIBAKE_RE.finditer(text):
        yield _hit_row(text, match)


def _is_hidden(path, root):
    """True when any component of ``path`` below ``root`` is dot-prefixed."""
    return any(part.startswith(".") for part in path.relative_to(root).parts)


def _content_json_files(roots):
    """Every non-hidden JSON file under ``roots``, from the filesystem.

    A hand-written list of maps/config files silently stops covering the
    next map or NPC file that ships; globbing the real tree is the only way
    "every file" keeps meaning that after this test is written. The roots
    are resolved before they key the cache, so two spellings of the same
    roots share one walk; the hidden-path rule has a control of its own over
    ``tmp_path``.
    """
    return _content_json_walk(tuple(pathlib.Path(root).resolve() for root in roots))


@functools.lru_cache(maxsize=None)
def _content_json_walk(roots):
    files = []
    for root in roots:
        files.extend(
            path for path in sorted(root.rglob("*.json")) if not _is_hidden(path, root)
        )
    return tuple(files)


def _walk_json_strings(value, path=""):
    """Yield ``(json_path, string)`` for every string in a decoded document.

    Keys as well as values: most keys are schema names like
    ``"description"``, but a mis-decoded key would otherwise be the one
    string the guard never looked at. ``json_path`` mirrors how a map's own
    coordinate/prop structure reads (``/(0, 2)/description``), so a failure
    message can be pasted straight back into the authored file.
    """
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, sub in value.items():
            key_path = f"{path}/{key}"
            yield f"{key_path} (key)", key
            yield from _walk_json_strings(sub, key_path)
    elif isinstance(value, list):
        for index, sub in enumerate(value):
            yield from _walk_json_strings(sub, f"{path}[{index}]")


def _file_violation(rel_path, label, error):
    """The report row for a whole file that failed as ``label``."""
    return Violation(rel_path, _FILE_LEVEL, label, str(error))


def _read_utf8(path):
    """``(text, None)``, or ``(None, violation)`` when ``path`` cannot be
    read or is not UTF-8 -- one reader, so both scanners label a failure the
    same way."""
    try:
        return path.read_text(encoding="utf-8"), None
    except UnicodeDecodeError as error:
        return None, _file_violation(_rel(path), _NOT_UTF8, error)
    except OSError as error:
        return None, _file_violation(_rel(path), _NOT_READABLE, error)


def _find_json_violations(files):
    """Every mis-decode in the content JSON, one ``Violation`` per occurrence.

    Checked per file, per JSON string, so every report row names exactly
    which string is broken. A file that cannot be read, decoded or parsed is
    itself a violation row rather than an abort: the scan still names it, and
    still finishes the other files.
    """
    violations = []
    for path in files:
        raw, unreadable = _read_utf8(path)
        if unreadable:
            violations.append(unreadable)
            continue
        rel_path = _rel(path)
        try:
            data = json.loads(raw)
        except (ValueError, RecursionError) as error:
            # json.JSONDecodeError is a ValueError.
            violations.append(_file_violation(rel_path, _NOT_PARSEABLE, error))
            continue
        for json_path, string in _walk_json_strings(data):
            violations.extend(
                Violation(rel_path, json_path, *hit) for hit in _sequence_hits(string)
            )
    return violations


def _line_hits(raw):
    """``(where, pattern, snippet)`` for every mis-decode visible in the text.

    ``split("\\n")``, not ``splitlines()``: the latter also breaks on form
    feeds and U+2028/2029, which the parser does not, and the line numbers
    here must agree with the literal scan's ``lineno``.
    """
    for line_no, line in enumerate(raw.split("\n"), start=1):
        for pattern, snippet in _sequence_hits(line):
            yield _line_where(line_no), pattern, snippet


def _fstring_parts(joined):
    """Every part of an f-string, in source order: its literal parts and its
    braced fields, each field followed by its format spec -- a ``JoinedStr``
    of its own -- and then that spec's parts. The one place that knows a
    format spec is a nested f-string."""
    for part in joined.values:
        yield part
        if isinstance(part, ast.FormattedValue) and isinstance(part.format_spec, ast.JoinedStr):
            yield part.format_spec
            yield from _fstring_parts(part.format_spec)


def _fstring_literal_parts(joined):
    """Every literal part of an f-string, its format specs' parts included,
    in source order."""
    return [
        part for part in _fstring_parts(joined)
        if isinstance(part, ast.Constant) and isinstance(part.value, str)
    ]


def _fstring_expressions(joined):
    """Every braced expression of an f-string, its format specs' included."""
    return [part.value for part in _fstring_parts(joined) if isinstance(part, ast.FormattedValue)]


def _string_literals(tree):
    """``(node, evaluated text)`` for every string literal unit in ``tree``.

    A plain string constant is one unit. An f-string is one unit too, whose
    text is its literal parts -- format specs' included -- joined at
    ``_FIELD_MARK``. On Python 3.11 every literal part of an f-string, and
    every format spec, reports the whole f-string's source span, so parts
    cannot be counted against their own source: a text-form hit in one part
    would discount an escape-form hit in another. Expressions inside the
    braces are ordinary nodes, walked on their own.

    Two passes, so the result does not depend on the order ``ast.walk``
    visits an f-string and its parts in.
    """
    nodes = list(ast.walk(tree))
    inside_an_fstring = set()
    for node in nodes:
        if isinstance(node, ast.JoinedStr):
            # Its literal parts and its format specs; not its braced fields.
            inside_an_fstring.update(
                id(part) for part in _fstring_parts(node)
                if not isinstance(part, ast.FormattedValue)
            )
    for node in nodes:
        if id(node) in inside_an_fstring:
            continue
        if isinstance(node, ast.JoinedStr):
            yield node, _FIELD_MARK.join(part.value for part in _fstring_literal_parts(node))
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            yield node, node.value


def _text_form_counts(raw, node):
    """How often each sequence appears as CHARACTERS in ``node``'s source.

    For an f-string, the text of every braced expression -- in its format
    specs too -- is subtracted: it belongs to the nodes inside the braces,
    which are counted on their own.
    """
    def count(segment_node):
        segment = ast.get_source_segment(raw, segment_node) or ""
        return Counter(m.group() for m in _MOJIBAKE_RE.finditer(segment))

    counts = count(node)
    if isinstance(node, ast.JoinedStr):
        for expression in _fstring_expressions(node):
            counts.subtract(count(expression))
    return counts


def _escaped_literal_hits(raw, tree):
    """``(where, pattern, snippet)`` for mis-decodes hiding in escapes, over
    ``tree`` -- the parse of ``raw``.

    The line scan sees the source text; a literal written as
    ``"\\u00e2\\u20ac\\u201d"`` is pure ASCII there and carries the corruption
    only in its evaluated value. Each occurrence the line scan already
    reported -- one per time the sequence appears as characters in the
    literal's own source -- is discounted here, so a defect is reported once
    and a literal carrying the same sequence both ways reports both.
    """
    hits = []
    for node, text in _string_literals(tree):
        matches = list(_MOJIBAKE_RE.finditer(text))
        if not matches:
            continue
        # Only a hit pays for the source lookup: ``get_source_segment``
        # re-splits the whole file per call, and almost every string constant
        # in the engine never matches.
        reported_by_line_scan = _text_form_counts(raw, node)
        for match in matches:
            if reported_by_line_scan[match.group()] > 0:
                reported_by_line_scan[match.group()] -= 1
                continue
            pattern, snippet = _hit_row(text, match)
            hits.append((_literal_where(node.lineno), pattern, snippet))
    return hits


def _find_py_violations(files):
    """Every mis-decode in the engine source, one ``Violation`` per occurrence.

    Reported per line and per literal, so every row names exactly where the
    corruption sits. A source file that cannot be read, is not UTF-8, or does
    not parse is a violation row rather than a skip: skipping would drop from
    the scan exactly the file most likely to carry an encoding defect, and a
    scan that silently narrows its population approves of whatever it
    stopped reading.
    """
    violations = []
    for path in files:
        raw, unreadable = _read_utf8(path)
        if unreadable:
            violations.append(unreadable)
            continue
        rel_path = _rel(path)
        violations.extend(Violation(rel_path, *hit) for hit in _line_hits(raw))
        try:
            tree = ast.parse(raw)
        except (SyntaxError, ValueError, RecursionError) as error:
            # ast.parse raises ValueError (not SyntaxError) for a NUL byte
            # on this project's interpreter.
            violations.append(_file_violation(rel_path, _NOT_PARSEABLE, error))
            continue
        violations.extend(Violation(rel_path, *hit) for hit in _escaped_literal_hits(raw, tree))
    return violations


def _format_report(violations, where_label):
    """A header naming the columns, then one line per violation.

    Header and rows are both built from ``Violation``'s own fields, so they
    cannot disagree about which columns there are or their order.
    """
    def cell(field, value):
        return repr(value) if field == "snippet" else value

    header = " :: ".join(
        where_label if field == "where" else field for field in Violation._fields
    )
    rows = (
        " :: ".join(cell(field, value) for field, value in zip(Violation._fields, v))
        for v in violations
    )
    return "\n".join((header, *rows))


def _assert_clean(violations, population, where_label):
    """Fail with the whole report when ``population`` holds any violation."""
    assert violations == [], (
        f"cp1252-mis-decoded punctuation found in {population}:\n"
        + _format_report(violations, where_label)
    )


def _shapes(violations):
    """The ``(where, pattern)`` pairs of a report, for the positive controls."""
    return [(v.where, v.pattern) for v in violations]


def _write_control(tmp_path, name, content):
    """Write ``content`` (text, or raw bytes) to ``tmp_path / name`` and
    return the path."""
    path = tmp_path / name
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")
    return path


def _scan_json(tmp_path, content):
    """Scan one JSON control file holding ``content``."""
    return _find_json_violations([_write_control(tmp_path, "control.json", content)])


def _scan_py(tmp_path, content):
    """Scan one Python control file holding ``content``."""
    return _find_py_violations([_write_control(tmp_path, "control.py", content)])


class TestScanPopulationIsReal:
    """A scan that matches no files approves of everything it never looked
    at, so each population the content tests scan has tests of its own. A
    content test passing over an empty population therefore cannot pass the
    module unnoticed, whichever order the tests run in."""

    def test_every_json_root_exists_and_contributes_files(self):
        files = _content_json_files(_CONTENT_JSON_ROOTS)
        assert files
        for root in _CONTENT_JSON_ROOTS:
            assert root.is_dir(), f"content root {root} is missing -- renamed?"
            assert any(root.resolve() in path.parents for path in files), (
                f"content root {root} contributed no JSON file to the scan"
            )
        assert any(path.parent == MAP_DIR.resolve() for path in files), (
            "the known map directory (src/resources/maps) was not reached "
            "by the content JSON scan -- the glob is walking the wrong tree"
        )

    def test_the_json_walk_skips_hidden_paths_and_nothing_else(self, tmp_path):
        # A control of its own rather than a check against the real roots:
        # the hidden file there is gitignored, so on a clean checkout the
        # real-tree version of this assertion would pass over an empty set.
        (tmp_path / "authored.json").write_text("{}", encoding="utf-8")
        (tmp_path / ".cache.json").write_text("{}", encoding="utf-8")
        (tmp_path / ".hidden").mkdir()
        (tmp_path / ".hidden" / "nested.json").write_text("{}", encoding="utf-8")
        (tmp_path / "shown").mkdir()
        (tmp_path / "shown" / "nested.json").write_text("{}", encoding="utf-8")

        root = tmp_path.resolve()
        assert _content_json_files((tmp_path,)) == (
            root / "authored.json",
            root / "shown" / "nested.json",
        )

    def test_py_population_is_non_empty(self):
        assert py_files(SRC_ROOT)


class TestTheMisDecodeDerivation:
    """The derivation every pattern the scan looks for comes from."""

    def test_every_watched_code_point_yields_one_distinct_sequence(self):
        # Derived from the same authority as the watch list, so it cannot go
        # stale: one sequence per watched code point, all distinct, so the
        # reverse map used in failure messages loses nothing.
        assert len(_SEQUENCE_TO_NAME) == len(_MOJIBAKE_SEQUENCES) == len(_WATCHED_CODE_POINTS)

    @pytest.mark.parametrize(
        "char,expected",
        [
            # U+2014 em dash -> U+00E2 U+20AC U+201D: the exact #578 corruption.
            ("\u2014", "\u00e2\u20ac\u201d"),
            # U+2019 right single quote / apostrophe -> the common mis-decoded
            # apostrophe seen in text pasted from word processors.
            ("\u2019", "\u00e2\u20ac\u2122"),
        ],
        ids=["em dash", "apostrophe"],
    )
    def test_mis_decode_reproduces_known_corruptions(self, char, expected):
        """Pins the derivation against the em dash #578 reported, and the
        common mis-decoded apostrophe, so a change to ``_mis_decode`` that
        broke the derivation would fail here even if every shipped file were
        already clean."""
        assert _mis_decode(char) == expected

    def test_undefined_cp1252_bytes_pass_through_as_c1_controls(self):
        """U+2041 encodes to E2 81 81; 0x81 is undefined in windows-1252, and
        a real decoder yields U+0081 for it rather than raising or dropping it."""
        assert _mis_decode(chr(0x2041)) == chr(0xE2) + chr(0x81) * 2

    def test_every_byte_the_strict_codec_rejects_passes_through_unchanged(self):
        """The bytes Python's cp1252 table leaves undefined all sit in the C1
        range and each comes back as its own code point, while a defined byte
        in that range still maps through the table."""
        rejected = []
        for byte in range(256):
            try:
                bytes([byte]).decode("cp1252")
            except UnicodeDecodeError:
                rejected.append(byte)
        assert rejected, "cp1252 rejects no byte -- the passthrough covers nothing"
        assert all(0x80 <= byte < 0xA0 for byte in rejected), rejected
        assert [_cp1252_char(byte) for byte in rejected] == [chr(byte) for byte in rejected]
        assert _cp1252_char(0x80) == "\u20ac"


class TestTheScannersCatchWhatTheyClaimTo:
    """Positive controls: each scanner run against a file that IS broken.

    The content assertions below prove the shipped files are clean; these
    prove the scanners would have said otherwise, which a clean tree alone
    cannot show.
    """

    def test_a_json_value_with_the_reported_corruption_is_flagged(self, tmp_path):
        violations = _scan_json(
            tmp_path, json.dumps({"tile": {"description": f"cold {_EM_DASH_MOJIBAKE} wet"}})
        )
        assert _shapes(violations) == [("/tile/description", _EM_DASH_PATTERN)], violations

    def test_a_json_key_with_a_mis_decode_is_flagged(self, tmp_path):
        key = f"caf{_E_ACUTE_MOJIBAKE}"
        violations = _scan_json(tmp_path, json.dumps({key: "clean"}))
        assert _shapes(violations) == [(f"/{key} (key)", _E_ACUTE_PATTERN)], violations

    def test_an_unparseable_json_file_is_a_violation_not_an_abort(self, tmp_path):
        violations = _scan_json(tmp_path, "{not json")
        assert _shapes(violations) == [(_FILE_LEVEL, _NOT_PARSEABLE)], violations
        assert violations[0].file == "control.json"

    def test_a_non_utf8_json_file_is_a_violation_not_an_abort(self, tmp_path):
        violations = _scan_json(tmp_path, b'{"k": "caf\xe9"}')
        assert _shapes(violations) == [(_FILE_LEVEL, _NOT_UTF8)], violations

    def test_an_unreadable_json_file_is_a_violation_not_an_abort(self, tmp_path):
        violations = _find_json_violations([tmp_path / "missing.json"])
        assert _shapes(violations) == [(_FILE_LEVEL, _NOT_READABLE)], violations

    def test_a_python_line_with_the_corruption_is_flagged_once(self, tmp_path):
        violations = _scan_py(tmp_path, f'LINE = "cold {_EM_DASH_MOJIBAKE} wet"\n')
        # Once, from the line scan; the literal scan sees the same sequence
        # in the source segment and stays quiet.
        assert _shapes(violations) == [(_line_where(1), _EM_DASH_PATTERN)], violations

    def test_an_escape_form_python_literal_is_flagged(self, tmp_path):
        source = f'LINE = "cold {_EM_DASH_ESCAPED} wet"\n'
        assert not _MOJIBAKE_RE.search(source), (
            "positive control is wrong: the escaped literal should be invisible to a text scan"
        )
        violations = _scan_py(tmp_path, source)
        assert _shapes(violations) == [(_literal_where(1), _EM_DASH_PATTERN)], violations

    def test_a_literal_carrying_the_corruption_both_ways_reports_both(self, tmp_path):
        violations = _scan_py(
            tmp_path, f'LINE = "{_EM_DASH_MOJIBAKE} and {_EM_DASH_ESCAPED}"\n'
        )
        assert _shapes(violations) == _BOTH_FORMS_ON_LINE_1, violations

    @pytest.mark.parametrize(
        "body",
        [
            "@TEXT@ {x} and @ESCAPED@",
            "{'@TEXT@'} and @ESCAPED@",
            "{x:@TEXT@} and @ESCAPED@",
            "{x:{'@TEXT@'}} and @ESCAPED@",
        ],
        ids=[
            "in a literal part",
            "inside a braced expression",
            "in a format spec's literal text",
            "inside a format spec's braced expression",
        ],
    )
    def test_an_fstring_carrying_the_corruption_both_ways_reports_both(self, tmp_path, body):
        """The text form and the escape form in DIFFERENT parts of one
        f-string: each is reported once, wherever in the f-string the text
        form sits."""
        assert _TEXT_SLOT in body and _ESCAPE_SLOT in body, body
        fstring = body.replace(_TEXT_SLOT, _EM_DASH_MOJIBAKE).replace(_ESCAPE_SLOT, _EM_DASH_ESCAPED)
        violations = _scan_py(tmp_path, 'LINE = f"' + fstring + '"\n')
        assert _shapes(violations) == _BOTH_FORMS_ON_LINE_1, violations

    def test_an_fstring_is_one_unit_and_a_string_in_its_braces_is_another(self):
        """An f-string's literal parts -- its format spec's included -- never
        surface as units of their own, whatever span the parser gives them;
        a string written inside the braces is an ordinary literal and does."""
        tree = ast.parse("LINE = f\"a{x:>{'w'}}b{'c'}\"\n")
        units = sorted((type(node).__name__, text) for node, text in _string_literals(tree))
        # Literal parts in order: "a", the spec's ">", "b" -- joined at _FIELD_MARK.
        assert units == [("Constant", "c"), ("Constant", "w"), ("JoinedStr", "a{}>{}b")]

    def test_a_non_utf8_python_file_is_a_violation_not_a_skip(self, tmp_path):
        violations = _scan_py(tmp_path, b"# caf\xe9\nX = 1\n")
        assert _shapes(violations) == [(_FILE_LEVEL, _NOT_UTF8)], violations

    def test_an_unreadable_python_file_is_a_violation_not_a_skip(self, tmp_path):
        violations = _find_py_violations([tmp_path / "missing.py"])
        assert _shapes(violations) == [(_FILE_LEVEL, _NOT_READABLE)], violations

    def test_an_unparseable_python_file_is_a_violation_not_an_abort(self, tmp_path):
        violations = _scan_py(tmp_path, "def (:\n")
        assert _shapes(violations) == [(_FILE_LEVEL, _NOT_PARSEABLE)], violations


class TestNoMojibakeSurvivesInContentJson:
    """The shipped content JSON, every string of every file."""

    def test_no_cp1252_mis_decode_in_any_content_json_string(self):
        _assert_clean(
            _find_json_violations(_content_json_files(_CONTENT_JSON_ROOTS)),
            "shipped content JSON",
            "json_path",
        )


class TestNoMojibakeSurvivesInPythonSource:
    """The engine source, every line and every string literal of every file."""

    def test_no_cp1252_mis_decode_in_any_src_py_file(self):
        _assert_clean(_find_py_violations(py_files(SRC_ROOT)), "src/**/*.py", "where")
