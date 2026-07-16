"""Fuzz test for the REST API request surface (issue #292).

Drives tools/api_fuzzer.py, which auto-enumerates every ``/api`` route from the
real app's URL map (built via ``create_app(TestingConfig)`` + the ``/api/test/
session`` bypass) and hammers each with malformed bodies, hostile path segments,
and forged/absent auth tokens. The security invariant — asserted zero here — is
that no route returns a 5xx or leaks a traceback on bad input, and auth holds
under garbage tokens. A structured 4xx (or 401/403) is the correct outcome.

Lives under tests/api/ (excluded from the default run) because it constructs a
real session/universe, which mutates module-level registries — see CLAUDE.md.
The fuzzer module is loaded by file path, matching tests/test_save_fuzz.py.
"""

import importlib.util
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]


def _load_fuzzer():
    path = _ROOT / "tools" / "api_fuzzer.py"
    spec = importlib.util.spec_from_file_location("_api_fuzzer", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


fuzzer = _load_fuzzer()


@pytest.mark.parametrize("seed", [1, 42, 1337, 20240101])
def test_api_fuzz_no_5xx_or_leak(seed):
    findings = fuzzer.run_fuzz(iterations=400, seed=seed)
    security = fuzzer.security_findings(findings)
    assert not security, "\n".join(str(f) for f in security)


def test_malformed_bodies_are_4xx_not_5xx():
    """A handful of previously-crashing shapes now return a structured 4xx."""
    from src.api.app import create_app
    from src.api.config import TestingConfig

    app, _ = create_app(TestingConfig)
    client = app.test_client()
    sid = (client.post("/api/test/session", json={"username": "t"})
           .get_json())["session_id"]
    auth = {"Authorization": f"Bearer {sid}"}

    # Non-dict JSON bodies that used to raise "argument of type X is not
    # iterable" / "X has no attribute get".
    for path, body in [
        ("/api/combat/move", True),
        ("/api/combat/start", 5),
        ("/api/world/move", 7),
        ("/api/world/events/input", "oops"),
        ("/api/skills/learn", [1, 2]),
    ]:
        r = client.post(path, json=body, headers=auth)
        assert r.status_code < 500, f"{path} 5xx'd on {body!r}"

    # Hostile log filenames must not 500 (path traversal / over-long / dir).
    for seg in ["%2e%2e", "x" * 900, ".."]:
        r = client.get(f"/api/logs/browser/files/{seg}")
        assert r.status_code < 500
