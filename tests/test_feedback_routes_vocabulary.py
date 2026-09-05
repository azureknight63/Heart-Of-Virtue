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

import re
from unittest.mock import MagicMock, patch

import pytest

from src.api.routes import feedback as feedback_module
from src.api.routes.feedback import (
    FEEDBACK_TYPES,
    MAX_USERNAME_LABEL_LENGTH,
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
