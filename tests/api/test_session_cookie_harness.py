from src.api.session_cookie import DEFAULT_COOKIE_NAME


"""The cookie surfaces the QA harnesses depend on (issue #493).

These live in ``tests/api/`` deliberately. They drive the real ``create_app``
and ``POST /api/test/session``, which builds a real Player and Universe and
mutates the module-level item/merchant registries — in the default suite that
pollutes downstream shop and spawn tests, which is exactly why CLAUDE.md
reserves this directory for full-app tests. The rest of the session-cookie
suite stays in ``tests/test_session_cookie.py`` on stubbed session managers.
"""


def _cookie_header(response):
    """The Set-Cookie line for our auth cookie, or "" if none was sent."""
    for value in response.headers.getlist("Set-Cookie"):
        if value.startswith(f"{DEFAULT_COOKIE_NAME}="):
            return value
    return ""


class TestHarnessSurfaces:
    def test_the_test_session_endpoint_sets_the_cookie(self, make_api_app):
        """A browser-driven QA run must authenticate the way a player does."""
        client = make_api_app().test_client()
        response = client.post("/api/test/session")
        assert response.status_code == 201
        assert "HttpOnly" in _cookie_header(response)

    def test_the_test_session_endpoint_still_returns_the_id(self, make_api_app):
        """In-process harnesses replay it as a Bearer header."""
        response = make_api_app().test_client().post("/api/test/session")
        assert response.get_json()["session_id"]

    def test_the_test_session_endpoint_tolerates_a_bodyless_post(self, make_api_app):
        """Harnesses POST it with no JSON content type; 415 would break them."""
        response = make_api_app().test_client().post("/api/test/session")
        assert response.status_code == 201
        assert response.get_json()["username"] == "inquisitor_test"

    def test_the_cookie_from_test_session_authenticates_a_later_request(
        self, make_api_app
    ):
        """End to end: no Authorization header is ever sent."""
        app = make_api_app()
        client = app.test_client()
        client.post("/api/test/session")  # test client keeps the cookie
        assert client.get("/api/auth/validate").get_json()["valid"] is True
