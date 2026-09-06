"""A handled failure must not become an unhandled one.

``print`` is not exception-free. It raises ``UnicodeEncodeError`` on a cp1252
Windows console -- this repo has been bitten by exactly that, from the terminal
engine's ``cprint`` -- and ``ValueError: I/O operation on closed file`` when a
WSGI server has closed stdout. Inside an ``except`` block, whose entire job is
to swallow, either one escapes the handler and turns a diagnostic into the
fault it was describing.

``traceback.print_exc`` is worse again: it writes straight to stderr, so the
traceback -- the part most likely to carry a path, a connection string or an
interpolated secret -- is the one thing bypassing ``_RedactSecretsFilter``
(``src/api/app.py``). ``handlers/error_handler.py`` was moved off it for that
reason, and thirty sibling sites were left behind in four other modules.

THIS IS THE INCREMENT FLOOR. The same defect was found and fixed in
``routes/logs.py``, with a guard scoped to that one file -- so the thirty
elsewhere stayed invisible to it. Scoped to a file, a guard can only ever
protect the file somebody already looked at.
"""

import ast
from pathlib import Path

#: Where the rule applies. ``tools/`` is deliberately out: those are operator
#: scripts run at a terminal, where printing IS the interface and a crash is
#: seen by the person who ran it.
_ROOTS = ("src", "ai")

#: Modules allowed to call ``print`` inside a handler, with the reason. An
#: entry here has to be argued for, so there is exactly one.
#:
#: A "not imported anywhere" rule was considered and rejected: it would have
#: exempted ``src/api/migrations.py`` too, and that one is API code an operator
#: happens to be able to run, not a CLI -- a distinction a reference count
#: cannot draw. Judgement, written down, beats a derivation that is subtly
#: wrong about the thing it is deriving.
_EXEMPT = {
    "validate_mynx.py": (
        "a standalone operator CLI (a __main__ guard and sys.exit(2) two lines "
        "on) that nothing imports: printing is its interface, and a crash is "
        "seen by the person who ran it -- the same reason tools/ is out of "
        "scope entirely"
    ),
}


def _diagnostic_calls(node):
    """``print(...)`` and ``*.print_exc(...)`` anywhere under ``node``."""
    found = []
    for inner in ast.walk(node):
        if not isinstance(inner, ast.Call):
            continue
        func = inner.func
        if isinstance(func, ast.Name) and func.id == "print":
            found.append(("print", inner.lineno))
        elif isinstance(func, ast.Attribute) and func.attr == "print_exc":
            found.append(("traceback.print_exc", inner.lineno))
    return found


def offenders_in(source: str):
    """Every diagnostic call that runs inside an ``except`` block."""
    found = []
    for handler in ast.walk(ast.parse(source)):
        if isinstance(handler, ast.ExceptHandler):
            found += _diagnostic_calls(handler)
    return found


def _modules():
    seen, out = set(), []
    for root in _ROOTS:
        for path in sorted(Path(root).rglob("*.py")):
            key = path.as_posix()
            if key in seen:
                continue
            seen.add(key)
            out.append(path)
    return out


class TestNoDiagnosticInsideAHandlerCanRaise:
    def test_the_scan_reads_a_real_corpus(self):
        """Non-vacuity. A scan over nothing bans nothing, which is how the
        file-scoped version of this guard managed to be green while thirty
        sites stood."""
        assert len(_modules()) > 100, len(_modules())

    def test_no_module_prints_from_inside_an_except(self):
        problems = []
        for path in _modules():
            if path.name in _EXEMPT:
                continue
            try:
                found = offenders_in(path.read_text(encoding="utf-8"))
            except SyntaxError:  # pragma: no cover - not ours to fix
                continue
            problems += [
                "%s:%d (%s)" % (path.as_posix(), lineno, kind)
                for kind, lineno in found
            ]
        assert problems == [], (
            "these run inside an except block and can themselves raise, which "
            "escapes the handler: %s\n\n"
            "Use a logger call wrapped so it cannot throw (see `_warn` / "
            "`_fault` in src/api/services/session_manager.py). For a "
            "traceback, `logger.exception` routes it through "
            "_RedactSecretsFilter; traceback.print_exc does not."
            % ", ".join(problems)
        )

    def test_every_exemption_carries_a_reason_and_a_real_file(self):
        thin = sorted(n for n, r in _EXEMPT.items() if len(r.split()) < 8)
        assert thin == [], thin
        names = {p.name for p in _modules()}
        stale = sorted(set(_EXEMPT) - names)
        assert stale == [], stale

    def test_the_scan_finds_both_spellings(self):
        """Guard-the-guard, in the two forms actually found in this repo."""
        for source in (
            "try:\n    pass\nexcept Exception as e:\n    print(f'boom {e}')\n",
            "import traceback\ntry:\n    pass\nexcept Exception:\n"
            "    traceback.print_exc()\n",
        ):
            assert offenders_in(source), source

    def test_the_scan_leaves_an_ordinary_print_alone(self):
        """The control. A print in normal flow is stdout noise, not a fault --
        banning those would make the rule unusable and someone would delete
        it."""
        source = "print('starting up')\ntry:\n    pass\nexcept Exception:\n    pass\n"
        assert offenders_in(source) == []

    def test_the_scan_leaves_a_logger_call_alone(self):
        source = (
            "try:\n    pass\nexcept Exception:\n"
            "    logger.exception('failed')\n"
        )
        assert offenders_in(source) == []
