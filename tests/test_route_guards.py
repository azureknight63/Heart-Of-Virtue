"""DRY guard: every route reaches ``game_service`` through the shared helper.

``require_game_service()`` in ``src/api/middleware/auth.py`` replaced fifteen
verbatim copies of the same eight-line 500 block -- including the literal error
string -- spread across ``world.py`` and ``player.py``. A fix or a rewording had
fifteen places to reach, which is fourteen chances to miss one.

Deleting the copies is only half the job; the other half is making the
sixteenth impossible to add quietly, which is what this module is. Two scans,
both structural:

* No route module may spell the error message itself. That is the DRY check
  proper -- the message belongs to the helper.
* No route module may read ``current_app.game_service`` directly. That is the
  anti-evasion check: hand-rolling the guard starts by fetching the service,
  and a module that fetches it without the helper is either re-implementing
  the check or (worse) skipping it and trusting the attribute to exist.

Scoped to ``src/api/routes/`` on purpose. ``src/api/middleware/auth.py`` is
where the one legitimate read and the one legitimate copy of the string live,
and a scan that could not tell the helper from its callers would have nothing
left to say.
"""

import ast
import pathlib

import pytest

from src.api.middleware.auth import require_game_service


#: The message ``require_game_service`` owns. Compared whitespace-insensitively
#: and case-insensitively, so a reflowed or re-capitalised copy is still a copy.
GUARD_MESSAGE = "Game service not initialized"


def _routes_dir():
    return pathlib.Path(__file__).resolve().parent.parent / "src/api/routes"


def _route_modules():
    return sorted(_routes_dir().glob("*.py"))


def _normalise(text: str) -> str:
    """Collapse whitespace and case, so formatting is not a hiding place."""
    return " ".join(str(text).split()).lower()


def _docstring_nodes(tree: ast.AST):
    """Every string node that is a docstring rather than a value.

    Prose *describing* the contract ("returns 500 with 'Game service not
    initialized'") is documentation, not a second copy of it, so the message
    scan skips docstrings the way the rate-limiter guards skip comments.
    """
    docstrings = set()
    for node in ast.walk(tree):
        if not isinstance(
            node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            continue
        body = getattr(node, "body", None)
        if not body:
            continue
        first = body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
            if isinstance(first.value.value, str):
                docstrings.add(id(first.value))
    return docstrings


def _folded_strings(tree: ast.AST):
    """Every string literal in ``tree``, with ``+`` concatenations folded.

    The parser already folds implicit concatenation (``"a" "b"``) into one
    Constant and exposes an f-string's literal parts as Constants inside a
    JoinedStr, so walking Constants covers both. Explicit ``"a" + "b"`` is the
    one spelling it does not fold, and folding it here is what stops the guard
    being defeated by a plus sign.
    """
    folded = {}

    def fold(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left, right = fold(node.left), fold(node.right)
            if left is not None and right is not None:
                return left + right
        return None

    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp):
            value = fold(node)
            if value is not None:
                folded[id(node)] = (node.lineno, value)

    return folded


def message_copies(source: str):
    """Line numbers where ``source`` spells the guard's error message itself.

    Parsed rather than grepped: a substring search over the file text would
    fire on the comment in this docstring, on a comment explaining why the
    message moved, and on any prose mentioning it -- a guard that cries wolf
    gets an ``# noqa`` and stops guarding.
    """
    tree = ast.parse(source)
    docstrings = _docstring_nodes(tree)
    target = _normalise(GUARD_MESSAGE)
    found = []

    for _node_id, (lineno, value) in _folded_strings(tree).items():
        if target in _normalise(value):
            found.append(lineno)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        if id(node) in docstrings:
            continue
        if target in _normalise(node.value):
            found.append(node.lineno)

    return sorted(set(found))


def direct_service_reads(source: str):
    """Line numbers where ``source`` reads ``current_app.game_service`` itself.

    Catches the attribute access however it is reached (bare ``current_app`` or
    ``flask.current_app``) and the ``getattr`` spelling, which is the form the
    helper itself uses and therefore the most plausible way someone would
    reproduce it in a route.
    """
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Attribute) and node.attr == "game_service":
            if _base_name(node.value) == "current_app":
                found.append(node.lineno)
        elif isinstance(node, ast.Call) and _base_name(node.func) == "getattr":
            args = node.args
            if (
                len(args) >= 2
                and _base_name(args[0]) == "current_app"
                and isinstance(args[1], ast.Constant)
                and args[1].value == "game_service"
            ):
                found.append(node.lineno)
    return sorted(set(found))


def _imported_names(source: str):
    """Every name ``source`` binds with an ``import`` statement."""
    names = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".")[0])
    return names


def _base_name(node):
    """The trailing name of a possibly-dotted expression, else ``None``."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


class TestEveryRouteUsesTheSharedGameServiceGuard:
    """The two scans, run over the real tree."""

    def test_no_route_module_spells_the_error_message(self):
        offenders = {
            path.name: message_copies(path.read_text(encoding="utf-8"))
            for path in _route_modules()
        }
        offenders = {name: lines for name, lines in offenders.items() if lines}
        assert offenders == {}, (
            "the 'Game service not initialized' message belongs to "
            "require_game_service() alone -- a route spelling it again is a "
            f"copy of the guard that a reword will not reach: {offenders}"
        )

    def test_no_route_module_reads_the_service_directly(self):
        offenders = {
            path.name: direct_service_reads(path.read_text(encoding="utf-8"))
            for path in _route_modules()
        }
        offenders = {name: lines for name, lines in offenders.items() if lines}
        assert offenders == {}, (
            "routes must reach the game service through require_game_service(), "
            "which is what makes the missing-service case a clean 500 instead "
            f"of an AttributeError: {offenders}"
        )

    def test_the_routes_that_need_the_service_actually_import_the_helper(self):
        """The scans above are also satisfied by a module that stopped touching
        the service at all, so this pins the positive half: the modules that do
        use it import the helper. Read from the import statement rather than
        from the file text, so a mention in a comment does not count."""
        importers = {
            path.name
            for path in _route_modules()
            if "require_game_service"
            in _imported_names(path.read_text(encoding="utf-8"))
        }
        assert importers >= {
            "combat.py",
            "inventory.py",
            "npc_chat.py",
            "player.py",
            "saves.py",
            "shop.py",
            "world.py",
        }, importers

    def test_the_helper_still_returns_the_documented_shape(self):
        """The scans are worth nothing if the helper's contract drifts: every
        converted route does ``value, error = require_game_service()``."""
        from flask import Flask

        app = Flask(__name__)
        with app.test_request_context("/"):
            service, error = require_game_service()
            assert service is None
            response, status = error
            assert status == 500
            payload = response.get_json()
            assert payload["success"] is False
            assert payload["error"] == GUARD_MESSAGE

            app.game_service = object()
            service, error = require_game_service()
            assert error is None
            assert service is app.game_service


class TestTheMessageScanSeesThroughFormatting:
    """Guard-the-guard. An AST scan that a rewrap or a plus sign walks past
    reads as coverage without being it -- and would report every module clean
    forever after.
    """

    @pytest.mark.parametrize(
        "snippet",
        [
            'x = "Game service not initialized"',
            "x = 'Game service not initialized'",
            # black splits long lines into implicit concatenation
            'x = (\n    "Game service "\n    "not initialized"\n)',
            # explicit concatenation -- the one the parser does not fold
            'x = "Game service not " + "initialized"',
            # f-string with a placeholder: literal parts live inside a JoinedStr
            'x = f"Game service not initialized ({code})"',
            # reflowed across lines inside one literal
            'x = """Game service\nnot initialized"""',
            # re-capitalised
            'x = "game service NOT initialized"',
            # buried in the dict a hand-rolled guard would actually build
            'return jsonify({"success": False, '
            '"error": "Game service not initialized"}), 500',
        ],
    )
    def test_it_finds_the_message_however_it_is_written(self, snippet):
        assert message_copies(snippet), snippet

    def test_it_ignores_prose_in_a_docstring(self):
        """Documenting the contract is not duplicating it."""
        source = (
            'def f():\n'
            '    """Returns 500 Game service not initialized."""\n'
            '    return 1\n'
        )
        assert message_copies(source) == []

    def test_it_ignores_a_comment(self):
        assert message_copies("# Game service not initialized\nx = 1\n") == []

    def test_it_does_not_fire_on_a_different_message(self):
        """``resolve_session`` has its own 'Session manager not initialized'
        and must not be swept up by a scan that matched too loosely."""
        assert message_copies('x = "Session manager not initialized"') == []
        assert message_copies('x = "Game service"') == []

    def test_a_docstring_exemption_does_not_leak_to_ordinary_strings(self):
        """The docstring skip is positional: only the *first* statement of a
        module/class/function is exempt, not every string in it."""
        source = (
            'def f():\n'
            '    """Doc."""\n'
            '    return "Game service not initialized"\n'
        )
        assert message_copies(source) == [3]


class TestTheServiceReadScanSeesThroughFormatting:
    """Guard-the-guard for the second scan."""

    @pytest.mark.parametrize(
        "snippet",
        [
            "x = current_app.game_service",
            "x = current_app.game_service.do_thing(player)",
            "x = flask.current_app.game_service",
            'x = getattr(current_app, "game_service", None)',
            'x = getattr(current_app, "game_service")',
            "x = (\n    current_app\n    .game_service\n)",
        ],
    )
    def test_it_finds_the_read_however_it_is_written(self, snippet):
        assert direct_service_reads(snippet), snippet

    @pytest.mark.parametrize(
        "snippet",
        [
            # the sanctioned route: the helper, called by name
            "game_service, gs_error = require_game_service()",
            # a different attribute on the same object
            "x = current_app.session_manager",
            # the same attribute on a different object
            "x = session.game_service",
            'x = getattr(session, "game_service", None)',
            # prose only
            "# current_app.game_service\nx = 1",
        ],
    )
    def test_it_does_not_fire_on_the_sanctioned_or_the_unrelated(self, snippet):
        assert direct_service_reads(snippet) == [], snippet

    def test_the_helper_itself_would_trip_the_scan(self):
        """Proof the scan has teeth rather than passing vacuously: the one
        legitimate read in the codebase *is* caught by it, which is exactly why
        the scan is scoped to ``src/api/routes/`` and the helper lives in
        ``src/api/middleware/``.
        """
        auth = (
            pathlib.Path(__file__).resolve().parent.parent
            / "src/api/middleware/auth.py"
        )
        source = auth.read_text(encoding="utf-8")
        assert direct_service_reads(source), "the helper no longer reads the service"
        assert message_copies(source), "the helper no longer owns the message"


#: Exception types whose message a route may put in a response body.
#:
#: The rule is that "safe to echo" rides on the TYPE, never on the wording
#: surviving a filter. A five-substring deny-list over free-form exception
#: text is what returned
#: ``could not connect to postgres://svc:<password>@db.internal:5432/hov``
#: from an anonymous ``POST /api/auth/register``; the same shape then turned
#: up untouched one route over in ``saves.py``, because the first fix was
#: applied to the site rather than to the class and its guard was scoped to a
#: single function.
_ECHOABLE_EXCEPTIONS = frozenset(
    {
        "RegistrationValidationError",
        "SaveLimitReached",
    }
)

#: Modules exempt, with the reason. ``debug.py`` is registered only under
#: ``app.config["TESTING"]`` (``_register_test_routes`` in ``src/api/app.py``),
#: so it is unreachable in a deployed app and its echoes are a debugging
#: convenience rather than a disclosure.
_ECHO_EXEMPT_MODULES = {
    "debug.py": (
        "registered only when TESTING is set, so it is not reachable in a "
        "deployed app -- see _register_test_routes in src/api/app.py"
    ),
}


def _caught_type_names(handler):
    """The exception names an ``except`` clause catches."""
    caught = handler.type
    if caught is None:
        return {"<bare except>"}
    parts = caught.elts if isinstance(caught, ast.Tuple) else [caught]
    names = set()
    for part in parts:
        if isinstance(part, ast.Name):
            names.add(part.id)
        elif isinstance(part, ast.Attribute):
            names.add(part.attr)
    return names


def _puts_alias_in(node, alias):
    """True if ``alias`` reaches ``node`` as text -- ``str(e)`` or ``f"{e}"``."""
    for inner in ast.walk(node):
        if isinstance(inner, ast.Call) and isinstance(inner.func, ast.Name):
            if inner.func.id == "str" and any(
                isinstance(a, ast.Name) and a.id == alias for a in inner.args
            ):
                return True
        if isinstance(inner, ast.FormattedValue):
            for sub in ast.walk(inner.value):
                if isinstance(sub, ast.Name) and sub.id == alias:
                    return True
    return False


def exception_text_echoes(source: str):
    """Every ``except ... as e`` whose ``e`` reaches a ``jsonify`` body."""
    found = []
    for handler in ast.walk(ast.parse(source)):
        if not isinstance(handler, ast.ExceptHandler) or not handler.name:
            continue
        bodies = [
            node
            for node in ast.walk(handler)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "jsonify"
        ]
        if any(_puts_alias_in(body, handler.name) for body in bodies):
            found.append((handler.lineno, frozenset(_caught_type_names(handler))))
    return found


class TestNoRouteEchoesAnUndeclaredExceptionToTheClient:
    """A route may echo an exception's text only for a type declared safe.

    THE INCIDENT. ``register`` decided what to disclose by scanning the message
    for five substrings and echoing anything that matched none of them. A
    ``ValueError`` reading ``could not connect to
    postgres://svc:<password>@db.internal:5432/hov`` matched none, and went
    back verbatim to an anonymous caller.

    THE REASON IT NEEDED A SECOND FIX. That was closed by allow-listing
    ``RegistrationValidationError`` in ``routes/auth.py`` -- and the guard
    written to hold it scanned ``AuthService.create_user`` alone. ``saves.py``
    had the identical ``except ValueError as ve: str(ve)`` around a call that
    reaches ``db.get_client()``'s ``ValueError("TURSO_DATABASE_URL is not
    set")``, and no guard could see it. The message even tripped two of the
    markers the discarded deny-list used, so the mechanism that was replaced
    would have caught this one.

    So the scan is over every route module, and the exemptions are declared
    with reasons rather than implied by scope.
    """

    def test_the_scan_reads_every_route_module(self):
        """Non-vacuity: a scan over no modules permits anything."""
        modules = _route_modules()
        assert len(modules) >= 8, [m.name for m in modules]

    def test_no_route_echoes_an_undeclared_exception(self):
        offenders = []
        for path in _route_modules():
            if path.name in _ECHO_EXEMPT_MODULES:
                continue
            source = path.read_text(encoding="utf-8")
            for lineno, caught in exception_text_echoes(source):
                if caught & _ECHOABLE_EXCEPTIONS:
                    continue
                offenders.append(
                    "%s:%d (catches %s)"
                    % (path.name, lineno, ", ".join(sorted(caught)))
                )
        assert offenders == [], (
            "these handlers put an exception's text into a response body for a "
            "type not declared safe to echo: %s\n\n"
            "The exception may carry infrastructure detail -- a connection "
            "string, an env-var name, an internal path. If the message really "
            "is player-facing advice, give it a declared type (beside "
            "RegistrationValidationError) and add it to _ECHOABLE_EXCEPTIONS. "
            "Otherwise log it and answer a fixed string."
            % ", ".join(offenders)
        )

    def test_every_declared_echoable_type_exists(self):
        """An allow-list entry for a type nobody raises is a licence lying
        around waiting to excuse something."""
        import src.api.services.auth_service as auth_service

        missing = sorted(
            name
            for name in _ECHOABLE_EXCEPTIONS
            if not isinstance(getattr(auth_service, name, None), type)
        )
        assert missing == [], missing

    def test_every_exemption_carries_a_reason(self):
        thin = sorted(
            name
            for name, reason in _ECHO_EXEMPT_MODULES.items()
            if len(reason.split()) < 8
        )
        assert thin == [], thin

    def test_every_exempt_module_still_exists(self):
        """An exemption for a deleted module is dead weight that makes the
        next reader trust the list less."""
        names = {p.name for p in _route_modules()}
        stale = sorted(set(_ECHO_EXEMPT_MODULES) - names)
        assert stale == [], stale

    def test_the_scan_recognises_both_spellings(self):
        """Guard-the-guard, in the two forms the codebase has actually used:
        ``str(e)`` (auth, saves) and an f-string (shop)."""
        for source in (
            "try:\n    pass\nexcept ValueError as e:\n"
            "    return jsonify({'error': str(e)}), 400\n",
            "try:\n    pass\nexcept ValueError as e:\n"
            "    return jsonify({'error': f'Invalid input: {e}'}), 400\n",
        ):
            assert exception_text_echoes(source), source

    def test_the_scan_leaves_a_logged_exception_alone(self):
        """The control. Logging the text is correct and must not be flagged,
        or the rule is unusable and someone will delete it."""
        source = (
            "try:\n    pass\nexcept ValueError as e:\n"
            "    logger.exception('failed: %s', e)\n"
            "    return jsonify({'error': 'An internal error occurred'}), 500\n"
        )
        assert exception_text_echoes(source) == []
