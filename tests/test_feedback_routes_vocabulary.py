"""The feedback type vocabulary is closed, and its tables cannot fail open.

``feedback.py`` spelled "bug"/"feature"/"general" four times — the label map,
the field-type table, the route's ``not in (...)`` test and its ``if/elif``
dispatch — and read one of those tables with
``_STRING_FIELD_KEYS_BY_TYPE.get(feedback_type, ())``. A type present in the
membership test but missing from that table therefore validated *nothing* and
went straight to a body builder, while the ``if/elif`` chain's ``else``
rendered it as general feedback. Two silent defaults on the one function whose
job is to fail closed.

"Fail-open table" has been flagged in five consecutive review rounds across
this repo, so the fix here is the shape rather than the instance:
:data:`~src.api.routes.feedback.FeedbackType` is the single declaration, and
the shared ``assert_closed_over`` fixture (``tests/conftest.py``) pins every
table against it. Adding a member without a row in all three now fails here,
which is the only place it *can* fail — a route-level test only ever exercises
the members that exist.

Also covered: the two label scrubs that were asymmetric with each other. The
issue *title* got ``_CONTROL_CHARS`` but not ``_LABEL_WHITESPACE``, so a
newline in a title survived into the tracker; and the username got both scrubs
but no length bound at all.
"""

import ast
import re
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.api.routes import feedback as feedback_module
from src.api.routes.feedback import (
    FEEDBACK_TYPES,
    MAX_USERNAME_LABEL_LENGTH,
    _BODY_BUILDERS,
    _MAPPING_FIELD_KEYS_BY_TYPE,
    _STRING_FIELD_KEYS_BY_TYPE,
    _validate_fields_for_type,
)

_AUTH = {"Authorization": "Bearer sid_fb"}


@pytest.fixture
def client(make_route_app, make_stub_session, make_stub_session_manager):
    """``feedback_bp`` on the shared route harness, with a captured GitHub call.

    ``_create_github_issue`` has no TESTING guard by design — it files a real
    issue whenever ``GITHUB_TOKEN`` is set — so every test here patches
    ``requests.post`` and reads the payload out of the call rather than letting
    anything reach the network. (``tests/conftest.py`` blanks the token as
    well; this is the second layer, not the first.)
    """

    def _client(username="jean_claire"):
        from src.api.routes.feedback import _feedback_limiter, feedback_bp

        if _feedback_limiter is not None:
            _feedback_limiter.clear_all()
        session = make_stub_session(session_id="sid_fb", username=username)
        sm = make_stub_session_manager(session, MagicMock())
        # The blueprint carries no prefix of its own, so the route is
        # "/issue" here rather than the "/api/feedback/issue" create_app mounts.
        return make_route_app(feedback_bp, session=session, session_manager=sm)

    return _client


def _post(app, body):
    """Submit ``body`` with a stubbed GitHub, returning the issue payload."""
    created = MagicMock()
    created.status_code = 201
    created.json.return_value = {"html_url": "https://example.invalid/1"}
    with patch.dict("os.environ", {"GITHUB_TOKEN": "not-a-real-token"}):
        with patch(
            "src.api.routes.feedback.requests.post", return_value=created
        ) as post:
            with app.test_client() as c:
                response = c.post("/issue", json=body, headers=_AUTH)
    return response, (post.call_args.kwargs["json"] if post.called else None)


class TestTheVocabularyIsDeclaredOnce:
    def test_every_table_is_keyed_over_the_literal(self, assert_closed_over):
        """The guard the whole module reorganisation exists for. Add a member
        to ``FeedbackType`` without giving it a label list, a field row and a
        body builder and this is what says so."""
        assert_closed_over(
            feedback_module,
            "FeedbackType",
            "LABEL_MAP",
            "_STRING_FIELD_KEYS_BY_TYPE",
            "_MAPPING_FIELD_KEYS_BY_TYPE",
            "_BODY_BUILDERS",
        )

    def test_the_members_are_the_ones_the_frontend_sends(self):
        """A control on the guard above, which would pass just as happily over
        a vocabulary someone had quietly renamed."""
        assert set(FEEDBACK_TYPES) == {"bug", "feature", "general"}

    def test_the_route_asks_the_vocabulary_rather_than_a_literal_tuple(self):
        """The membership test was the fourth copy of the three strings. It is
        checked by source because the behaviour is identical either way — that
        is precisely why the copy survived four rounds of review."""
        source = feedback_module.__file__
        with open(source, encoding="utf-8") as handle:
            text = handle.read()
        assert 'not in FEEDBACK_TYPES' in text
        assert 'not in ("bug", "feature", "general")' not in text


class TestAnUnknownTypeCannotSkipValidation:
    def test_validation_raises_rather_than_returning_none(self):
        """``.get(type, ())`` returned "no fields to check" for an unknown
        type, which reads exactly like "all fields are fine"."""
        with pytest.raises(KeyError):
            _validate_fields_for_type("harness_unknown_type", {"steps": 123})

    def test_the_route_never_reaches_it_with_an_unknown_type(self, client):
        response, payload = _post(
            client(), {"type": "harness_unknown_type", "title": "T"}
        )
        assert response.status_code == 400
        assert payload is None

    @pytest.mark.parametrize(
        "body, expected",
        [
            (
                {"type": "bug", "title": "T", "fields": {"steps": 123}},
                "fields.steps must be a string",
            ),
            (
                {
                    "type": "general",
                    "title": "T",
                    "fields": {"ratings": "not-a-dict"},
                },
                "fields.ratings must be an object",
            ),
        ],
    )
    def test_a_wrong_typed_field_is_still_a_400(self, client, body, expected):
        """The control: the tables are indexed harder, and they still do the
        job they were indexed for."""
        response, payload = _post(client(), body)
        assert response.status_code == 400
        assert response.get_json()["error"] == expected
        assert payload is None

    @pytest.mark.parametrize("feedback_type", FEEDBACK_TYPES)
    def test_every_declared_type_still_files_an_issue(
        self, client, feedback_type
    ):
        response, payload = _post(
            client(), {"type": feedback_type, "title": "A real report"}
        )
        assert response.status_code == 201
        assert payload["labels"] == feedback_module.LABEL_MAP[feedback_type]


class TestTheTitleIsALabel:
    @pytest.mark.parametrize("whitespace", ["\n", "\r", "\t", "\r\n"])
    def test_line_breaks_never_reach_the_issue_title(self, client, whitespace):
        """``_CONTROL_CHARS`` deliberately spares \\n, \\t and \\r because a
        report *body* is prose. A title is not prose — it is one line — and
        those three were the only control characters still getting through."""
        response, payload = _post(
            client(), {"type": "bug", "title": "before%safter" % whitespace}
        )
        assert response.status_code == 201
        assert payload["title"] == "before after"

    def test_the_title_is_not_emptied_by_the_scrub(self, client):
        """The control: collapsing whitespace must not become deleting it."""
        response, payload = _post(
            client(), {"type": "bug", "title": "Combat crash on   the bridge"}
        )
        assert response.status_code == 201
        assert payload["title"] == "Combat crash on the bridge"


def _attribution_label(body):
    """The name the issue body attributes the report to."""
    match = re.search(r"Submitted in-game by: \*\*(.*?)\*\*", body)
    assert match, body
    return match.group(1)


class TestTheUsernameLabelIsBounded:
    def test_a_long_username_is_truncated(self, client):
        long_name = "j" * (MAX_USERNAME_LABEL_LENGTH * 4)
        response, payload = _post(
            client(username=long_name), {"type": "bug", "title": "T"}
        )
        assert response.status_code == 201
        assert (
            _attribution_label(payload["body"])
            == "j" * MAX_USERNAME_LABEL_LENGTH
        )

    def test_an_ordinary_username_is_untouched(self, client):
        """"Untouched" by the *bound*, that is. ``_MARKDOWN_UNSAFE`` still
        drops the underscore, as it did before and for its own reasons."""
        response, payload = _post(
            client(username="jean_claire"), {"type": "bug", "title": "T"}
        )
        assert _attribution_label(payload["body"]) == "jeanclaire"

    def test_a_blank_username_still_renders_a_label(self, client):
        """Unchanged behaviour, re-pinned because the truncation sits directly
        above the ``or "Unknown Player"`` fallback that produces it."""
        response, payload = _post(
            client(username="  "), {"type": "bug", "title": "T"}
        )
        assert _attribution_label(payload["body"]) == "Unknown Player"


def _keys_each_builder_reads():
    """The field keys the body builders actually read, taken from their source.

    Derived from the BUILDERS, not from ``_STRING_FIELD_KEYS_BY_TYPE``, and the
    difference is the whole point. Those tables are what the *validator*
    consults, so a guard built on them could only confirm that the validator
    agrees with itself. The builders are the independent authority here: they
    are the code that dereferences the value, so they are the code that decides
    which keys can crash.

    It also gives the floor a direction the tables cannot. Add a
    ``fields.get("foo", "")`` to a builder and forget its table row, and
    ``test_every_key_a_builder_reads_is_declared`` fails. The reverse -- a
    table row with no builder -- is what ``assert_closed_over`` covers above.
    """
    source = Path(feedback_module.__file__).read_text(encoding="utf-8")
    by_function = {}
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.FunctionDef):
            continue
        keys = []
        for call in ast.walk(node):
            if not isinstance(call, ast.Call):
                continue
            target = call.func
            if not isinstance(target, ast.Attribute) or target.attr != "get":
                continue
            # ``fields.get(...)`` only. ``_build_general_body`` also does
            # ``ratings.get(key)``, but that reads an already-extracted
            # sub-mapping rather than the request payload.
            if not isinstance(target.value, ast.Name):
                continue
            if target.value.id != "fields":
                continue
            if call.args and isinstance(call.args[0], ast.Constant):
                if isinstance(call.args[0].value, str):
                    keys.append(call.args[0].value)
        if keys:
            by_function[node.name] = keys
    return {
        feedback_type: tuple(by_function.get(builder.__name__, ()))
        for feedback_type, builder in _BODY_BUILDERS.items()
    }


_BUILDER_READS = _keys_each_builder_reads()

#: Every (type, key) pair a builder dereferences -- the population an explicit
#: ``null`` can be sent for.
_NULLABLE = [
    (feedback_type, key)
    for feedback_type, keys in sorted(_BUILDER_READS.items())
    for key in keys
]


class TestAnExplicitNullIsNotAServerError:
    """A field sent as JSON ``null`` answered 500.

    ``_validate_fields_for_type`` tests ``value is not None and not
    isinstance(value, str)``, exempting ``None`` because an omitted field is
    fine. The builders then reach for their defaults with
    ``fields.get(key, default)``, which supplies the default only when the key
    is ABSENT -- so a key present with a null value passed validation and hit
    ``None.strip()`` one frame later. The ``except Exception`` wrapped around
    the handler turned that AttributeError into "An internal error occurred".

    The review that found it named ``steps``. It was all eight declared fields
    across all three types, which is why the fix is one normalisation at the
    boundary rather than eight defensive ``or ""`` edits -- and why this guard
    derives its population instead of listing what was reported.
    """

    def test_the_scan_found_the_builders(self):
        """Non-vacuity. An AST scan that matches nothing parametrises nothing,
        and the two parametrised tests below would pass with no cases."""
        assert set(_BUILDER_READS) == set(FEEDBACK_TYPES)
        empty = sorted(t for t, keys in _BUILDER_READS.items() if not keys)
        assert empty == [], (
            "no fields.get(...) reads found in the builders for %s -- the scan "
            "has stopped matching the source it derives from"
            % ", ".join(empty)
        )

    @pytest.mark.parametrize("feedback_type, key", _NULLABLE)
    def test_a_null_field_renders_exactly_as_an_omitted_one(
        self, client, feedback_type, key
    ):
        """The chosen semantic, asserted as an equivalence rather than against
        a hand-copied ``_Not provided_`` literal: whatever a builder renders
        for a missing field, a null one must render identically."""
        with_null, null_payload = _post(
            client(),
            {"type": feedback_type, "title": "T", "fields": {key: None}},
        )
        without, omitted_payload = _post(
            client(), {"type": feedback_type, "title": "T", "fields": {}}
        )
        assert without.status_code == 201, without.get_json()
        assert with_null.status_code == 201, with_null.get_json()
        assert null_payload["body"] == omitted_payload["body"]

    #: The one field whose builder is deliberately total, and why.
    #:
    #: ``severity`` is a CLOSED vocabulary: closing it against a forged
    #: attribution footer (see TestPlayerProseCannotForgeTheAttribution) meant
    #: coercing anything unrecognised to the default, which necessarily made
    #: ``None`` unrecognised rather than fatal. Every other field is prose and
    #: stays strict, so the boundary normalisation is still what carries them.
    _TOTAL_BY_DESIGN = {("bug", "severity")}

    @pytest.mark.parametrize("feedback_type, key", _NULLABLE)
    def test_the_builders_are_still_strict_about_none(self, feedback_type, key):
        """What makes the test above non-vacuous.

        It would pass just as happily if the builders had been made tolerant,
        and then it would be pinning nothing about the route. The fix is
        deliberately at the boundary -- one place, ahead of both the validator
        and every builder -- so the builders stay strict, and this records
        that they do.
        """
        if (feedback_type, key) in self._TOTAL_BY_DESIGN:
            # Tolerant on purpose; assert THAT rather than skipping, so the
            # exception cannot quietly become the rule.
            assert _BODY_BUILDERS[feedback_type]({key: None}, "attribution")
            return
        with pytest.raises(AttributeError):
            _BODY_BUILDERS[feedback_type]({key: None}, "attribution")

    def test_the_total_by_design_list_is_not_a_licence(self):
        """An entry here has to be a field the builder really does accept, or
        it is just an excuse someone wrote down."""
        for feedback_type, key in self._TOTAL_BY_DESIGN:
            assert (feedback_type, key) in _NULLABLE, (feedback_type, key)
            assert _BODY_BUILDERS[feedback_type]({key: None}, "attribution")

    def test_every_key_a_builder_reads_is_declared(self):
        """Floor on the increment.

        A builder that reads a key no table declares is a field the validator
        never type-checks -- the fail-open hole ``assert_closed_over`` closes
        for TYPES, closed here for KEYS.
        """
        undeclared = []
        for feedback_type, keys in sorted(_BUILDER_READS.items()):
            declared = set(_STRING_FIELD_KEYS_BY_TYPE[feedback_type]) | set(
                _MAPPING_FIELD_KEYS_BY_TYPE[feedback_type]
            )
            undeclared += [
                "%s.%s" % (feedback_type, key)
                for key in keys
                if key not in declared
            ]
        assert undeclared == [], (
            "these keys are read by a body builder but declared in neither "
            "_STRING_FIELD_KEYS_BY_TYPE nor _MAPPING_FIELD_KEYS_BY_TYPE, so "
            "_validate_fields_for_type never type-checks them and a "
            "wrong-typed value reaches the builder as a 500: %s"
            % ", ".join(undeclared)
        )


#: The two lines every body builder ends with. Taken from the builders' own
#: output rather than retyped: `_footer_lines` below renders a real body and
#: reads them off it, so a change to the footer cannot leave this stale.
def _footer_lines():
    body = feedback_module._build_bug_body({}, "Submitted anonymously")
    lines = body.split("\n")
    rule = next(i for i, ln in enumerate(lines) if ln.startswith("---"))
    return lines[rule], lines[rule + 1]


class TestPlayerProseCannotForgeTheAttribution:
    """Every body ends with a horizontal rule and an italicised attribution.

    Nothing stopped a player putting that same pair inside a field. An
    ANONYMOUS report whose ``steps`` ended with::

        \\n---\\n*Submitted in-game by: **someone_else***

    rendered a second, identical-looking footer naming whoever the player
    liked -- and the genuine one below it reads as part of the same block, the
    rule having already been drawn.

    Player prose is now blockquoted, so it cannot begin a line at column zero
    and therefore cannot open a rule, a heading or a footer. The population is
    derived from ``_STRING_FIELD_KEYS_BY_TYPE`` rather than listed, so a
    seventh field is covered on the day it is added.
    """

    def test_the_footer_is_where_this_test_thinks_it_is(self):
        """Non-vacuity. If the footer shape changed, every probe below would
        be asserting the absence of something that never appears anyway."""
        rule, attribution = _footer_lines()
        assert rule == "---"
        assert attribution.startswith("*") and attribution.endswith("*")

    @pytest.mark.parametrize("feedback_type, key", _NULLABLE)
    def test_no_field_can_open_a_line_at_column_zero(
        self, feedback_type, key
    ):
        rule, attribution = _footer_lines()
        forgery = "harmless.\n%s\n%s" % (rule, attribution)
        # A mapping field is not prose: the forgery has to be attempted through
        # a VALUE, which is where it would have to travel. (It cannot -- the
        # rating rows go through int() -- and asserting that is the point,
        # rather than skipping the field and assuming.)
        if key in _MAPPING_FIELD_KEYS_BY_TYPE[feedback_type]:
            payload = {"story": forgery, "combat": 5}
        else:
            payload = forgery
        builder = feedback_module._BODY_BUILDERS[feedback_type]
        body = builder({key: payload}, "Submitted anonymously")

        # The route's own footer is the LAST two lines. Anything matching it
        # earlier is a forgery.
        lines = body.split("\n")
        forged = [
            i
            for i, ln in enumerate(lines[:-2])
            if ln == rule or ln.startswith("*Submitted")
        ]
        assert forged == [], (
            "field %s.%s produced a footer-shaped line at %s, before the "
            "route's own: %r" % (feedback_type, key, forged, lines)
        )

    def test_the_player_text_still_reaches_the_issue(self):
        """The control. Dropping the field entirely would satisfy the
        assertion above and lose the bug report."""
        body = feedback_module._build_bug_body(
            {"steps": "the ferry crashed at dawn"}, "Submitted anonymously"
        )
        assert "the ferry crashed at dawn" in body

    def test_multi_line_player_text_survives_as_multiple_lines(self):
        """And the other control: quoting must not collapse the prose into
        one line, which would make a numbered repro unreadable."""
        body = feedback_module._build_bug_body(
            {"steps": "one\ntwo\nthree"}, "Submitted anonymously"
        )
        assert "> one" in body and "> two" in body and "> three" in body


class TestTheControlClassIsNotAsciiOnly:
    """``_CONTROL_CHARS`` is documented for terminal safety and was ASCII-only.

    Two families survived it, and both are the thing it exists to stop:

    * C1 (U+0080-U+009F). U+009B is CSI -- the single-character form of the
      ``ESC [`` the ASCII half already strips -- so a player could reach a
      terminal with exactly the sequence this class was written to prevent.
    * The bidirectional overrides. These reorder rendered text, so an issue can
      display in an order its bytes do not have. GitHub renders them.
    """

    def test_every_cc_character_except_the_three_kept_is_stripped(self):
        """Derived from ``unicodedata``, not from the pattern. Newline, tab and
        carriage return are kept deliberately -- a report body is prose."""
        import unicodedata

        kept = {"\n", "\t", "\r"}
        survivors = [
            hex(cp)
            for cp in range(0x00, 0x0100)
            if unicodedata.category(chr(cp)) == "Cc"
            and chr(cp) not in kept
            and feedback_module._CONTROL_CHARS.sub("", chr(cp)) != ""
        ]
        assert survivors == [], survivors

    def test_the_three_prose_characters_survive(self):
        """The control, in the other direction: stripping these would run a
        bug report's steps together into one line."""
        for ch in ("\n", "\t", "\r"):
            assert feedback_module._CONTROL_CHARS.sub("", ch) == ch

    @pytest.mark.parametrize(
        "name, ch",
        [
            ("CSI", ""),
            ("LRM", "‎"),
            ("RLM", "‏"),
            ("LRE", "‪"),
            ("RLO", "‮"),
            ("LRI", "⁦"),
            ("PDI", "⁩"),
            ("LINE SEPARATOR", " "),
            ("PARAGRAPH SEPARATOR", " "),
        ],
    )
    def test_the_named_reordering_characters_are_stripped(self, name, ch):
        assert feedback_module._CONTROL_CHARS.sub("", ch) == "", name

    def test_ordinary_text_is_untouched(self):
        """The broadest control. A class that ate real text would pass every
        assertion above and destroy every bug report."""
        prose = "The ferry runs at dawn — mind the current. Café, naïve, 日本語."
        assert feedback_module._CONTROL_CHARS.sub("", prose) == prose
