"""Guards against cp1252-mis-decoded UTF-8 punctuation ("mojibake") surviving
in authored content (issue #578).

Three em dashes in ``eastern-descent-nomad-camp.json`` were stored as
``U+00E2 U+20AC U+201D`` instead of a single ``U+2014`` -- the byte sequence
you get by taking the UTF-8 bytes of a real em dash (``E2 80 94``) and
reinterpreting each one as its own windows-1252 code point instead of
decoding all three as one UTF-8 character. The JSON source stores the result
as three separate ``\\uXXXX`` escapes, so a raw-text grep for the mojibake
*characters* finds nothing -- ``json.load`` has to run first to turn the
escapes into the code points this guard looks for. That trap is why two
earlier passes over this file were waved through as "clean".

(The runtime scan below is driven entirely by code points -- ``_mis_decode``
derives every watched sequence from ``chr()``, never from a literal typed
into this file, for exactly that reason: a file about mis-decoded punctuation
is not where you want an editor's or terminal's own encoding assumptions to
quietly re-mangle the characters under test. The handful of literal
em-dash/curly-quote characters that DO appear below, in
``test_mis_decode_reproduces_known_corruptions``, are a fixed, small,
byte-verified set precisely so a corruption in one of them cannot hide behind
this module's own derivation.)

The scan below walks every JSON file under ``src/resources/`` and ``ai/``,
decodes each one, and checks every string *value* (never the raw file text)
for the mis-decode of any character in the two Unicode blocks authored prose
in this repo actually uses: Latin-1 Supplement (accented letters, the
non-breaking space) and General Punctuation (dashes, curly quotes, the
ellipsis, bullets, and their neighbours). It also walks every ``src/**/*.py``
file as text, since a Python string literal can carry the same corruption
without ever passing through ``json.load``.

The 208 watched sequences are derived from the two Unicode blocks, not
hand-copied character by character -- so the set can never disagree with the
corruption it exists to catch, and a mis-decoded guillemet or per-mille sign
(neither one anyone would think to type into a hand-written list) trips this
exactly as an em dash does.
"""

import json
import pathlib
import unicodedata

import pytest

_ROOT = pathlib.Path(__file__).resolve().parent.parent

#: The two roots the issue asked this guard to cover: shipped map/content
#: JSON and the AI personality/config JSON.
_CONTENT_JSON_ROOTS = (
    _ROOT / "src" / "resources",
    _ROOT / "ai",
)
_PY_ROOT = _ROOT / "src"

#: A directory the JSON scan must actually reach -- proves the glob below is
#: walking the real tree and not an empty or wrong one.
_KNOWN_MAP_DIR = _ROOT / "src" / "resources" / "maps"


def _mis_decode(char):
    """The mojibake a real "declared the wrong charset" pipeline produces.

    Encodes ``char`` as UTF-8 and decodes those bytes as windows-1252, one
    code point per byte -- reproducing (rather than hand-transcribing) the
    exact corruption #578 reported: the correct single U+2014 em dash became
    the three code points U+00E2 U+20AC U+201D.

    Python's ``cp1252`` codec raises on five byte values (0x81, 0x8D, 0x8F,
    0x90, 0x9D) the official windows-1252 table leaves undefined. Real
    decoders -- browsers, the WHATWG windows-1252 decoder, Windows'
    ``MultiByteToWideChar`` -- do not raise; they pass those bytes through as
    the identically-numbered C1 control code point, which is what an actual
    mis-decode in the wild produces. That fallback is applied byte-by-byte,
    only where the strict codec refuses, so it never masks a real mapping
    with a guess.
    """
    data = char.encode("utf-8")
    out = []
    chunk_start = 0
    for i, byte in enumerate(data):
        try:
            bytes([byte]).decode("cp1252")
        except UnicodeDecodeError:
            out.append(data[chunk_start:i].decode("cp1252"))
            out.append(chr(byte))
            chunk_start = i + 1
    out.append(data[chunk_start:].decode("cp1252"))
    return "".join(out)


#: Latin-1 Supplement (accented letters and punctuation like the
#: non-breaking space) and General Punctuation (dashes, curly quotes, the
#: ellipsis, bullets) -- the two blocks that show up in this repo's English
#: prose and placeholder-schema text. Building the watch list from the
#: blocks, rather than from "the ones issue #578 happened to name", is what
#: makes the guard durable: a future mojibake report for a different
#: character in either block is already covered.
_WATCHED_CODE_POINTS = list(range(0x00A0, 0x0100)) + list(range(0x2000, 0x2070))


def _build_mojibake_sequences():
    sequences = {}
    for code_point in _WATCHED_CODE_POINTS:
        char = chr(code_point)
        mis_decoded = _mis_decode(char)
        if mis_decoded == char or len(mis_decoded) <= 1:
            # Never happens for a multi-byte UTF-8 source character (a
            # single-byte mis-decode target would mean the codec produced a
            # 1:1 byte-to-char mapping for a >=2-byte encoding), but skipped
            # explicitly rather than assumed impossible.
            continue
        try:
            name = unicodedata.name(char)
        except ValueError:
            name = "UNNAMED"
        sequences["U+%04X (%s)" % (code_point, name)] = mis_decoded
    return sequences


#: pattern name -> the literal mis-decoded sequence to search for.
MOJIBAKE_SEQUENCES = _build_mojibake_sequences()


def _content_json_files():
    """Every JSON file under the content roots, derived from the filesystem.

    A hand-written list of maps/config files silently stops covering the
    next map or NPC file that ships; globbing the real tree is the only way
    "every file" keeps meaning that after this test is written.
    """
    files = []
    for root in _CONTENT_JSON_ROOTS:
        if root.is_dir():
            files.extend(sorted(root.rglob("*.json")))
    return files


def _content_py_files():
    """Every Python module under ``src/``, derived the same way."""
    return sorted(_PY_ROOT.rglob("*.py"))


def _walk_json_strings(value, path=""):
    """Yield ``(json_path, string_value)`` for every string leaf.

    ``json_path`` mirrors how a map's own coordinate/prop structure reads
    (``/(0, 2)/description``), so a failure message can be pasted straight
    back into the authored file to find the spot.
    """
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, sub in value.items():
            yield from _walk_json_strings(sub, f"{path}/{key}" if path else f"/{key}")
    elif isinstance(value, list):
        for index, sub in enumerate(value):
            yield from _walk_json_strings(sub, f"{path}[{index}]")


def _snippet(value, index, sequence_len, radius=25):
    start = max(0, index - radius)
    end = index + sequence_len + radius
    return value[start:end]


def _find_json_violations(files):
    """``(file, json_path, pattern_name, snippet)`` for every mis-decode.

    Checked per file, per JSON string value: a hit in one file's one string
    cannot satisfy the assertion for any other file or value, and the
    message always names exactly which value is broken -- never just that
    *something* in the repo matched somewhere.
    """
    violations = []
    for path in files:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        rel_path = str(path.relative_to(_ROOT))
        for json_path, string_value in _walk_json_strings(data):
            for pattern_name, sequence in MOJIBAKE_SEQUENCES.items():
                index = string_value.find(sequence)
                if index != -1:
                    violations.append(
                        (
                            rel_path,
                            json_path,
                            pattern_name,
                            _snippet(string_value, index, len(sequence)),
                        )
                    )
    return violations


def _find_py_violations(files):
    """``(file, "line N", pattern_name, snippet)`` for every mis-decode.

    Line-scoped rather than whole-file, for the same per-unit reason as the
    JSON walk: one matching line in one file must not be able to stand in
    for a different file or line in the failure message.
    """
    violations = []
    for path in files:
        try:
            raw = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # A source file that is not even valid UTF-8 has a different,
            # worse problem than mojibake; out of scope for this guard.
            continue
        rel_path = str(path.relative_to(_ROOT))
        for line_no, line in enumerate(raw.splitlines(), start=1):
            for pattern_name, sequence in MOJIBAKE_SEQUENCES.items():
                index = line.find(sequence)
                if index != -1:
                    violations.append(
                        (
                            rel_path,
                            f"line {line_no}",
                            pattern_name,
                            _snippet(line, index, len(sequence)),
                        )
                    )
    return violations


def _format_violations(violations):
    return "\n".join(
        "%s :: %s :: %s :: %r" % (file, where, pattern_name, snippet)
        for file, where, pattern_name, snippet in violations
    )


class TestScanPopulationIsReal:
    """A scan that matches no files approves of everything it never looked
    at, so the population itself is asserted before any content claim runs
    against it."""

    def test_json_population_is_non_empty(self):
        files = _content_json_files()
        assert len(files) > 0
        assert any(f.parent == _KNOWN_MAP_DIR for f in files), (
            "the known map directory (src/resources/maps) was not reached "
            "by the content JSON scan -- the glob is walking the wrong tree"
        )

    def test_py_population_is_non_empty(self):
        assert len(_content_py_files()) > 0

    def test_the_watched_sequence_set_is_non_trivial(self):
        # Not a round number: it is whatever the two Unicode blocks above
        # actually contain once undecoded/self-identical entries are
        # skipped, so this pins "the derivation ran and produced many
        # sequences", not a specific count that would go stale.
        assert len(MOJIBAKE_SEQUENCES) > 100


class TestNoMojibakeSurvivesInContentJson:
    def test_no_cp1252_mis_decode_in_any_content_json_string(self):
        violations = _find_json_violations(_content_json_files())
        assert violations == [], (
            "cp1252-mis-decoded punctuation found in shipped content JSON "
            "(file :: json_path :: pattern :: snippet):\n"
            + _format_violations(violations)
        )


class TestNoMojibakeSurvivesInPythonSource:
    def test_no_cp1252_mis_decode_in_any_src_py_file(self):
        violations = _find_py_violations(_content_py_files())
        assert violations == [], (
            "cp1252-mis-decoded punctuation found in src/**/*.py "
            "(file :: line :: pattern :: snippet):\n"
            + _format_violations(violations)
        )


@pytest.mark.parametrize(
    "char,expected",
    [
        # U+2014 em dash -> U+00E2 U+20AC U+201D: the exact #578 corruption.
        ("—", "â€”"),
        # U+2019 right single quote / apostrophe -> the common mis-decoded
        # apostrophe seen in text pasted from word processors.
        ("’", "â€™"),
    ],
)
def test_mis_decode_reproduces_known_corruptions(char, expected):
    """Pins the derivation against the two corruptions this issue is about,
    so a change to ``_mis_decode`` that broke the derivation would fail here
    even if every shipped file were already clean."""
    assert _mis_decode(char) == expected
