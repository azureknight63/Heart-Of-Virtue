"""Content-Security-Policy composition and delivery (issue #492).

The policy is report-only during the rollout, so nothing here asserts that a
browser blocked anything — what these tests pin is the *shape* of the policy and
the fact that it actually reaches a response, plus the two properties that would
silently ruin the rollout if they regressed: production must never carry
``'unsafe-inline'`` in ``script-src``, and the dev/production policies must both
be built from the one shared JSON file rather than a hand-copied list.
"""

import json
import types

import pytest
from flask import Flask

from src.api import security_headers
from src.api.config import DevelopmentConfig, ProductionConfig, TestingConfig
from src.api.security_headers import (
    ENFORCING_HEADER,
    REPORT_ONLY_HEADER,
    build_csp,
    load_policy,
    register_security_headers,
)


def _directives(policy_string):
    """Parse a policy string back into {directive: [sources]}."""
    parsed = {}
    for part in policy_string.split(";"):
        tokens = part.split()
        if tokens:
            parsed[tokens[0]] = tokens[1:]
    return parsed


def _app(config_class, **overrides):
    """A bare Flask app with the CSP hook installed and one route."""
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.config.update(overrides)
    register_security_headers(app)

    @app.route("/ping")
    def ping():
        return "pong"

    return app


# --------------------------------------------------------------------------
# Policy composition
# --------------------------------------------------------------------------


def test_shared_policy_file_is_readable_and_has_both_sections():
    policy = load_policy()
    assert set(policy) == {"base", "dev_additions"}
    assert policy["base"]["default-src"] == ["'self'"]


def test_load_policy_drops_the_in_file_rationale_comment():
    """The JSON carries a `_comment` array for humans; consumers must not see it."""
    raw = json.loads(security_headers.POLICY_PATH.read_text(encoding="utf-8"))
    assert "_comment" in raw, "the rationale comment is part of the file's contract"
    assert "_comment" not in load_policy()


def test_production_policy_locks_down_script_src():
    directives = _directives(build_csp(dev=False))
    assert directives["script-src"] == ["'self'"]
    assert "'unsafe-eval'" not in directives["script-src"]


def test_production_policy_never_relaxes_scripts_even_via_dev_additions():
    """The whole point of the dev flag: prod must not inherit its relaxations."""
    prod = build_csp(dev=False)
    assert "'unsafe-inline'" not in _directives(prod)["script-src"]
    assert "ws:" not in prod


def test_dev_policy_allows_the_vite_react_refresh_preamble():
    directives = _directives(build_csp(dev=True))
    assert "'unsafe-inline'" in directives["script-src"]
    assert "ws:" in directives["connect-src"]
    # Base sources survive the merge rather than being replaced by it.
    assert "'self'" in directives["connect-src"]


def test_dev_additions_do_not_duplicate_a_source_the_base_already_allows():
    policy = {
        "base": {"connect-src": ["'self'"]},
        "dev_additions": {"connect-src": ["'self'", "ws:"]},
    }
    assert _directives(build_csp(dev=True, policy=policy))["connect-src"] == [
        "'self'",
        "ws:",
    ]


def test_style_src_keeps_unsafe_inline_for_react_inline_style_props():
    """Documented, accepted exception — see docs/development/csp-rollout.md."""
    assert "'unsafe-inline'" in _directives(build_csp())["style-src"]


def test_report_directives_are_emitted_only_when_a_uri_is_configured():
    with_uri = build_csp(report_uri="/api/logs/csp-report")
    assert "report-uri /api/logs/csp-report" in with_uri

    without = build_csp(report_uri=None)
    assert "report-uri" not in without


def test_report_to_is_never_advertised_alongside_report_uri():
    """Advertising both transports delivers nothing in Chromium.

    ``report-to`` takes precedence over ``report-uri`` whenever both are
    present, and Chromium then queues the report through the Reporting API
    instead of POSTing it — a plain-HTTP origin is not even an eligible
    endpoint. Measured over one forced violation: ``report-uri`` alone → 1 POST,
    ``report-to`` alone → 0, both → 0. A report-only rollout that silently
    reports nothing reads as "clean", which is the worst possible outcome, so
    this is pinned rather than left to a future tidy-up. See the module
    docstring in src/api/security_headers.py.
    """
    assert "report-to" not in build_csp(report_uri="/api/logs/csp-report")


def test_a_directive_only_present_in_dev_additions_is_still_emitted():
    policy = {"base": {"default-src": ["'self'"]}, "dev_additions": {"worker-src": ["blob:"]}}
    assert "worker-src blob:" in build_csp(dev=True, policy=policy)


# --------------------------------------------------------------------------
# Delivery
# --------------------------------------------------------------------------


def test_report_only_header_is_set_on_responses():
    app = _app(TestingConfig)
    response = app.test_client().get("/ping")
    assert REPORT_ONLY_HEADER in response.headers
    assert ENFORCING_HEADER not in response.headers


def test_no_reporting_endpoints_header_is_sent():
    """The companion of ``report-to``; both are omitted for the same reason."""
    headers = _app(TestingConfig).test_client().get("/ping").headers
    assert "Reporting-Endpoints" not in headers


def test_report_only_false_switches_to_the_enforcing_header():
    app = _app(TestingConfig, CSP_REPORT_ONLY=False)
    response = app.test_client().get("/ping")
    assert ENFORCING_HEADER in response.headers
    assert REPORT_ONLY_HEADER not in response.headers


def test_csp_can_be_disabled_entirely():
    app = _app(TestingConfig, CSP_ENABLED=False)
    response = app.test_client().get("/ping")
    assert REPORT_ONLY_HEADER not in response.headers
    assert ENFORCING_HEADER not in response.headers


def test_register_reports_whether_it_installed_the_hook():
    assert register_security_headers(_app(TestingConfig)) is True
    disabled = Flask(__name__)
    disabled.config["CSP_ENABLED"] = False
    assert register_security_headers(disabled) is False


def test_a_policy_already_set_by_a_nearer_layer_is_not_clobbered():
    app = _app(TestingConfig)

    @app.route("/own-policy")
    def own_policy():
        from flask import make_response

        response = make_response("ok")
        response.headers[ENFORCING_HEADER] = "default-src 'none'"
        return response

    response = app.test_client().get("/own-policy")
    assert response.headers[ENFORCING_HEADER] == "default-src 'none'"
    assert REPORT_ONLY_HEADER not in response.headers


def test_development_config_serves_the_dev_relaxations():
    header = _app(DevelopmentConfig).test_client().get("/ping").headers[
        REPORT_ONLY_HEADER
    ]
    assert "'unsafe-inline'" in _directives(header)["script-src"]


def test_production_config_serves_the_locked_down_policy():
    header = _app(ProductionConfig).test_client().get("/ping").headers[
        REPORT_ONLY_HEADER
    ]
    assert _directives(header)["script-src"] == ["'self'"]


@pytest.mark.parametrize(
    "raw,expected_relaxed",
    [("0", False), ("false", False), ("no", False), ("", False), ("1", True), ("true", True)],
)
def test_string_flags_from_the_environment_are_coerced(raw, expected_relaxed):
    app = _app(TestingConfig, CSP_DEV_RELAXATIONS=raw)
    header = app.test_client().get("/ping").headers[REPORT_ONLY_HEADER]
    assert ("'unsafe-inline'" in _directives(header)["script-src"]) is expected_relaxed


def test_missing_config_key_falls_back_to_the_environment(monkeypatch):
    monkeypatch.setenv("CSP_REPORT_ONLY", "false")
    app = Flask(__name__)
    app.config["TESTING"] = True
    register_security_headers(app)

    @app.route("/ping")
    def ping():
        return "pong"

    assert ENFORCING_HEADER in app.test_client().get("/ping").headers


def test_flask_config_wins_over_a_conflicting_environment_variable(monkeypatch):
    monkeypatch.setenv("CSP_REPORT_ONLY", "false")
    app = _app(TestingConfig, CSP_REPORT_ONLY=True)
    assert REPORT_ONLY_HEADER in app.test_client().get("/ping").headers


def test_report_uri_omitted_leaves_the_report_directive_off():
    app = _app(TestingConfig, CSP_REPORT_URI="")
    headers = app.test_client().get("/ping").headers
    assert "report-uri" not in headers[REPORT_ONLY_HEADER]


def test_policy_is_read_once_at_registration_not_per_request(monkeypatch):
    """A per-response file read would put disk I/O on every API call."""
    calls = []
    real = security_headers.load_policy

    def counting(*args, **kwargs):
        calls.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(security_headers, "load_policy", counting)
    app = _app(TestingConfig)
    before = len(calls)
    client = app.test_client()
    client.get("/ping")
    client.get("/ping")
    assert len(calls) == before


def test_load_policy_accepts_an_explicit_path(tmp_path):
    path = tmp_path / "policy.json"
    path.write_text(json.dumps({"base": {"default-src": ["'none'"]}}), encoding="utf-8")
    assert load_policy(path) == {"base": {"default-src": ["'none'"]}}


def test_bool_config_values_pass_through_unchanged():
    """`_flag` must not stringify a real bool into an always-true value."""
    app = types.SimpleNamespace(config={"CSP_ENABLED": False})
    assert security_headers._flag(app, "CSP_ENABLED", True) is False


# --------------------------------------------------------------------------
# Cross-server drift
#
# The Vite dev/preview server composes the same policy in JavaScript. Nothing
# at runtime can catch the two implementations disagreeing — a dev server whose
# policy has quietly diverged from the API's simply reports the wrong
# violations, which is worse than reporting none. These pin the properties that
# keep them in step by construction.
# --------------------------------------------------------------------------

VITE_CONFIG = (
    security_headers.POLICY_PATH.parent.parent.parent
    / "frontend"
    / "vite.config.js"
)


def _vite_config_source(strip_comments=False):
    source = VITE_CONFIG.read_text(encoding="utf-8")
    if strip_comments:
        # Directive names are discussed in the file's comments; only *code*
        # that names one would be an inlined copy.
        source = "\n".join(
            line for line in source.splitlines() if not line.lstrip().startswith(("//", "*", "/*"))
        )
    return source


def test_vite_config_reads_the_shared_policy_file():
    assert "csp-policy.json" in _vite_config_source()


@pytest.mark.parametrize("directive", sorted(load_policy()["base"]))
def test_vite_config_does_not_inline_a_copy_of_any_directive(directive):
    """A hand-copied directive list is exactly how the two policies drift."""
    assert directive not in _vite_config_source(strip_comments=True)


def test_vite_config_does_not_advertise_report_to_either():
    """Same measured reason as the Flask side — the two must not diverge."""
    source = _vite_config_source(strip_comments=True)
    assert "report-to" not in source
    assert "Reporting-Endpoints" not in source


def test_vite_preview_serves_the_production_policy():
    """`vite preview` serves the built bundle, so it must not relax script-src.

    Step 3 of docs/development/csp-rollout.md leans on this: preview is the only
    local surface that exercises the production ``script-src``.
    """
    source = _vite_config_source()
    assert "cspHeaders({ dev: true })" in source, "dev server keeps its relaxations"
    assert "cspHeaders({ dev: false })" in source, "preview must not"


def test_the_vite_report_uri_matches_the_production_report_uri():
    """Both resolve to the deployed subpath; a mismatch loses reports silently."""
    assert ProductionConfig.CSP_REPORT_URI in _vite_config_source().replace(
        "${BASE}api", "/games/HeartOfVirtue/api"
    )


def test_the_real_app_factory_serves_the_policy(make_api_app):
    """Every other delivery test builds a bare Flask app and registers the hook
    by hand, so deleting ``register_security_headers(app)`` from the factory
    left this whole file green. This is the only test that would catch that.

    ``/health`` is deliberate: it needs no session, so this cannot drag a real
    Universe into the default suite.
    """
    response = make_api_app().test_client().get("/health")
    assert REPORT_ONLY_HEADER in response.headers


def test_the_report_uri_resolves_to_a_real_route(make_api_app):
    """A re-prefixed blueprint would send every violation into a 404."""
    app = make_api_app()
    report_path = app.config["CSP_REPORT_URI"]
    assert any(str(rule) == report_path for rule in app.url_map.iter_rules())
