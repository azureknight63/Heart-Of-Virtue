"""Content-Security-Policy delivery for the Flask app (issue #492).

Why a response header and not a ``<meta>`` tag
----------------------------------------------
A ``<meta http-equiv="Content-Security-Policy-Report-Only">`` element is
**ignored by browsers** — the CSP spec allows only the enforcing header name in
markup, and Chrome/Firefox additionally log a console error when a report-only
policy arrives that way. Since the rollout starts in report-only mode (no
player-visible breakage while we learn what the real policy needs), a meta tag
is not an option today; the policy has to be a response header.

Where the header actually lands
-------------------------------
Three surfaces serve bytes to a browser, and each needs the header from its own
server:

* **The Flask API** — this module. Covers every ``/api/*`` response and any HTML
  Werkzeug renders (error pages), and is the home the policy moves to wholesale
  if Flask ever serves the SPA itself.
* **The Vite dev server** — ``frontend/vite.config.js`` (``server.headers`` /
  ``preview.headers``). This is what carries the policy on the *document* during
  development and QA runs, which is where violations are actually observed.
* **Production static hosting** — the built SPA is untarred into the web
  server's document root by ``deploy.ps1``; that server is not configured from
  this repo. ``docs/development/csp-rollout.md`` carries the snippet to add
  there.

All three read the same directive data from ``src/resources/csp-policy.json`` so
the dev and production policies cannot silently diverge.

Why only ``report-uri``, and not the newer ``report-to``
-------------------------------------------------------
The obvious move is to advertise both transports, since ``report-uri`` is
deprecated and browser support is split. Measured in headless Chromium against
this app, that combination delivers **nothing**: ``report-to`` takes precedence
over ``report-uri`` whenever both are present, and Chromium's Reporting API then
queues the report rather than POSTing it (delivery is batched, and a plain-HTTP
origin is not an eligible endpoint at all). A three-way A/B over one forced
violation — ``report-uri`` alone, ``report-to`` alone, both — produced 1, 0 and 0
report POSTs respectively.

A report-only rollout whose reports never arrive is worse than no rollout: it
reads as "zero violations" and nothing is learned. So the policy ships
``report-uri`` alone, which is also the only transport Firefox and Safari
implement. Re-adding ``report-to`` is a follow-up in
docs/development/csp-rollout.md, gated on re-running that A/B over HTTPS.
"""

import json
import os
from pathlib import Path

# Directive data shared with frontend/vite.config.js. Loaded once at import.
POLICY_PATH = (
    Path(__file__).resolve().parent.parent / "resources" / "csp-policy.json"
)

ENFORCING_HEADER = "Content-Security-Policy"
REPORT_ONLY_HEADER = "Content-Security-Policy-Report-Only"


def load_policy(path=None):
    """Read the shared directive data.

    Returns a ``{"base": {...}, "dev_additions": {...}}`` mapping. Keys starting
    with an underscore (the in-file rationale comment) are dropped.
    """
    with open(path or POLICY_PATH, "r", encoding="utf-8") as handle:
        raw = json.load(handle)
    return {k: v for k, v in raw.items() if not k.startswith("_")}


def build_csp(dev=False, report_uri=None, policy=None):
    """Compose the policy string.

    Args:
        dev: Apply the development relaxations (the Vite dev server injects an
            inline React-Refresh preamble that no build step can hash). Never
            true for the production policy.
        report_uri: Where violations are POSTed, as a ``report-uri`` directive.
            Deliberately not paired with ``report-to`` — see the module
            docstring for the measurement that ruled that out.
        policy: Pre-loaded directive data, for tests. Defaults to the shared
            JSON file.

    Returns:
        The policy as a single ``;``-joined header value.
    """
    data = policy if policy is not None else load_policy()
    directives = {name: list(values) for name, values in data["base"].items()}

    if dev:
        for name, extra in data.get("dev_additions", {}).items():
            merged = directives.setdefault(name, [])
            # Preserve source order and skip anything the base already allows;
            # a duplicated source is legal CSP but noise in a header humans read.
            merged.extend(value for value in extra if value not in merged)

    parts = [f"{name} {' '.join(values)}" for name, values in directives.items()]

    if report_uri:
        parts.append(f"report-uri {report_uri}")

    return "; ".join(parts)


def _flag(app, key, default):
    """Read a boolean switch from Flask config, then environment, then default."""
    value = app.config.get(key, os.environ.get(key))
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in ("0", "false", "no", "")


def register_security_headers(app):
    """Attach the CSP response header to every response this app serves.

    Report-only by default: ``CSP_REPORT_ONLY=false`` (config or environment)
    flips it to enforcing. See docs/development/csp-rollout.md for the checklist
    that gates that flip.
    """
    if not _flag(app, "CSP_ENABLED", True):
        return False

    report_only = _flag(app, "CSP_REPORT_ONLY", True)
    dev = _flag(app, "CSP_DEV_RELAXATIONS", bool(app.config.get("TESTING")))
    report_uri = app.config.get(
        "CSP_REPORT_URI", os.environ.get("CSP_REPORT_URI", "/api/logs/csp-report")
    )
    header_name = REPORT_ONLY_HEADER if report_only else ENFORCING_HEADER
    header_value = build_csp(dev=dev, report_uri=report_uri)

    @app.after_request
    def _set_csp(response):
        # Don't clobber a policy a nearer layer already chose (e.g. a route that
        # deliberately relaxes it) — set only when absent.
        if ENFORCING_HEADER not in response.headers:
            if REPORT_ONLY_HEADER not in response.headers:
                response.headers[header_name] = header_value
        return response

    return True
