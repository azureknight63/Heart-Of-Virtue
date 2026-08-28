""".env.example documents every environment variable ``src/api/`` reads.

The hole this closes: ``REGISTER_RATE_LIMIT_PER_HOUR`` shipped as a live,
operator-tunable throttle with no entry in ``.env.example`` -- the only one of
the five rate-limit knobs without one -- and nothing noticed, because nothing
was looking. ``NPC_CHAT_LLM_ENABLED`` had been undocumented for longer. An
undocumented knob is a knob nobody sets, which makes its default the only value
it ever has, which makes it a constant wearing a variable's costume.

Two things make this check worth more than a grep:

* The reader inventory is **derived, not transcribed**. A variable read through
  a helper (``limiter_from_env("X", ...)``) or through a module constant
  (``_LOG_LEVEL_ENV = "LOG_LEVEL"``) is still a variable an operator must be
  told about, and both indirections exist in this tree today. The helpers are
  themselves discovered -- any function that forwards its own first parameter
  into an env read is one, transitively, so ``limiter_from_env`` is found even
  though only ``_parse_env_limit`` touches ``os.environ`` -- and adding a sixth
  wrapper does not silently shrink the scan.
* :data:`INTERNAL_ONLY` is an explicit, reasoned exemption list rather than a
  skip. Exempting a variable means writing down why, next to its name, in the
  file that fails; and :class:`TestTheExemptionListStaysHonest` retires the
  entry the moment the reason expires.
"""

import ast
import pathlib
import re

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
API_DIR = REPO_ROOT / "src" / "api"
ENV_EXAMPLE = REPO_ROOT / ".env.example"

#: Variables read by ``src/api/`` that an operator is deliberately not offered.
#:
#: Map each name to the reason it is not a knob. Empty today, and that is the
#: intended steady state: every variable this package reads is currently
#: something an operator may legitimately want to set. Add an entry only for a
#: variable that is genuinely internal -- a test-harness signal, a value
#: injected by the platform -- never to quiet a failure for a knob that simply
#: has not been written up yet. The fix for that one is a paragraph in
#: ``.env.example``.
INTERNAL_ONLY: dict = {}

#: ``os.environ.get(...)`` / ``os.getenv(...)`` -- the direct reads.
_DIRECT_READERS = frozenset({"getenv", "get"})


def _module_level_strings(tree):
    """``NAME -> value`` for module-level ``NAME = "literal"`` assignments.

    Without this the scan has a blind spot exactly where a refactor puts one:
    hoisting ``"LOG_LEVEL"`` into ``_LOG_LEVEL_ENV`` (which ``app.py`` does, so
    that two reads 700 lines apart cannot drift) would otherwise erase the
    variable from the inventory.
    """
    constants = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        value = node.value
        if not (isinstance(value, ast.Constant) and isinstance(value.value, str)):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                constants[target.id] = value.value
    return constants


def _is_direct_env_read(func):
    """True for ``os.getenv`` / ``os.environ.get`` attribute expressions."""
    if not isinstance(func, ast.Attribute) or func.attr not in _DIRECT_READERS:
        return False
    if func.attr == "getenv":
        return True
    return isinstance(func.value, ast.Attribute) and func.value.attr == "environ"


def _is_env_subscript(node):
    """True for ``os.environ[...]``."""
    return isinstance(node.value, ast.Attribute) and node.value.attr == "environ"


def _first_param(func_node):
    """The name of ``func_node``'s first positional parameter, or ``None``."""
    params = func_node.args.posonlyargs + func_node.args.args
    return params[0].arg if params else None


def _passes_first_param_to(func_node, known_helpers):
    """True when ``func_node`` forwards its first param as an env-var name.

    Either straight into ``os.environ``/``os.getenv``, or into a function
    already known to take one. The second arm is what finds
    ``limiter_from_env``, which never touches ``os.environ`` itself -- it hands
    ``var`` to ``_parse_env_limit``. Chase only the direct read and the public
    entry point disappears from the scan while its four call sites stay
    invisible.
    """
    first = _first_param(func_node)
    if first is None:
        return False

    def forwards(node_args):
        arg = node_args[0] if node_args else None
        return isinstance(arg, ast.Name) and arg.id == first

    for node in ast.walk(func_node):
        if isinstance(node, ast.Call):
            called = node.func
            named = (
                called.id
                if isinstance(called, ast.Name)
                else called.attr if isinstance(called, ast.Attribute) else None
            )
            if _is_direct_env_read(called) or named in known_helpers:
                if forwards(node.args):
                    return True
        if isinstance(node, ast.Subscript) and _is_env_subscript(node):
            if isinstance(node.slice, ast.Name) and node.slice.id == first:
                return True
    return False


def _parsed_sources(package_dir):
    for path in sorted(package_dir.rglob("*.py")):
        yield path, ast.parse(path.read_text(encoding="utf-8"), str(path))


def env_name_helpers(package_dir):
    """Names of functions in ``package_dir`` whose first argument is a var name.

    Iterated to a fixed point, because these wrappers delegate: discovering
    ``_parse_env_limit`` on the first pass is what makes ``limiter_from_env``
    discoverable on the second.
    """
    functions = [
        node
        for _path, tree in _parsed_sources(package_dir)
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    helpers = set()
    while True:
        grown = {
            node.name
            for node in functions
            if node.name not in helpers and _passes_first_param_to(node, helpers)
        }
        if not grown:
            return helpers
        helpers |= grown


def env_names_read(package_dir):
    """``VAR -> {source files}`` for every env var ``package_dir`` reads."""
    helpers = env_name_helpers(package_dir)
    found = {}

    for path, tree in _parsed_sources(package_dir):
        constants = _module_level_strings(tree)
        try:
            label = path.relative_to(REPO_ROOT).as_posix()
        except ValueError:  # a scratch tree in the guard-the-guard tests
            label = path.name

        def literal(expr, _constants=constants):
            if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
                return expr.value
            if isinstance(expr, ast.Name):
                return _constants.get(expr.id)
            return None

        for node in ast.walk(tree):
            name = None
            if isinstance(node, ast.Call):
                called = node.func
                is_helper = (
                    isinstance(called, ast.Name) and called.id in helpers
                ) or (isinstance(called, ast.Attribute) and called.attr in helpers)
                if node.args and (_is_direct_env_read(called) or is_helper):
                    name = literal(node.args[0])
            elif isinstance(node, ast.Subscript) and _is_env_subscript(node):
                name = literal(node.slice)
            if name:
                found.setdefault(name, set()).add(label)

    return found


def documented_in_env_example(name, text=None):
    """True when ``.env.example`` carries a ``NAME=`` line, live or commented.

    Optional knobs are documented commented-out, so ``# NAME=default`` counts.
    A bare mention inside prose deliberately does not: the point is a line an
    operator can uncomment.
    """
    if text is None:
        text = ENV_EXAMPLE.read_text(encoding="utf-8")
    pattern = r"^[ \t]*#?[ \t]*%s[ \t]*=" % re.escape(name)
    return re.search(pattern, text, re.M) is not None


# ---------------------------------------------------------------------------
# The check itself
# ---------------------------------------------------------------------------


class TestEveryApiEnvVarIsDocumented:
    def test_env_example_exists(self):
        assert ENV_EXAMPLE.is_file(), "the file this suite checks against is missing"

    def test_the_scan_found_the_variables_we_know_are_there(self):
        """A scan that silently returned nothing would make the real check
        below pass forever. These four are read through four *different*
        mechanisms -- a bare literal, a module constant, a limiter helper and a
        flag helper -- so their presence proves each arm of the scan is live.
        """
        names = env_names_read(API_DIR)
        for expected in (
            "TURSO_DATABASE_URL",  # os.environ.get("...") literal
            "LOG_LEVEL",  # os.environ.get(_LOG_LEVEL_ENV) module constant
            "REGISTER_RATE_LIMIT_PER_HOUR",  # limiter_from_env("...", ...)
            "COMBAT_SOCKET_STREAMING",  # _env_flag("...", default=False)
        ):
            assert expected in names, "%s not found by the scan" % expected

    def test_every_variable_read_under_src_api_is_documented(self):
        undocumented = {
            name: sorted(files)
            for name, files in sorted(env_names_read(API_DIR).items())
            if name not in INTERNAL_ONLY and not documented_in_env_example(name)
        }
        assert not undocumented, (
            "these environment variables are read by src/api/ but have no "
            "entry in .env.example, so nobody deploying this knows they "
            "exist: %r. Add a commented `# NAME=default` line in the style of "
            "its neighbours, or -- only if the variable is genuinely not an "
            "operator's business -- add it to INTERNAL_ONLY with the reason."
            % undocumented
        )


class TestTheExemptionListStaysHonest:
    """An allow-list nobody prunes becomes a list of things nobody checks."""

    def test_every_exemption_has_a_written_reason(self):
        unexplained = [
            name for name, reason in INTERNAL_ONLY.items() if not str(reason).strip()
        ]
        assert not unexplained, (
            "INTERNAL_ONLY entries with no reason: %r. The reason is the whole "
            "mechanism -- without it this is a skip list." % unexplained
        )

    def test_no_exemption_is_for_a_variable_nothing_reads_any_more(self):
        names = env_names_read(API_DIR)
        stale = sorted(name for name in INTERNAL_ONLY if name not in names)
        assert not stale, (
            "INTERNAL_ONLY exempts variables src/api/ no longer reads: %r" % stale
        )

    def test_no_exemption_is_for_a_variable_that_is_documented_anyway(self):
        both = sorted(n for n in INTERNAL_ONLY if documented_in_env_example(n))
        assert not both, (
            "these are exempted *and* documented, so the exemption is dead "
            "weight hiding a real entry: %r" % both
        )


# ---------------------------------------------------------------------------
# Guard the guard
# ---------------------------------------------------------------------------


class TestTheScannerHasTeeth:
    """Every assertion above is worth exactly what the scan is worth. A scanner
    that quietly missed a read shape would turn the real check into a green
    light for the next undocumented knob -- which is the failure it was written
    to stop, one level up.
    """

    #: Every read shape ``src/api/`` actually uses, reproduced in one scratch
    #: module. Self-contained on purpose: the scan is directory-scoped, so a
    #: helper imported from elsewhere is legitimately invisible to it, and a
    #: probe that imported one would be testing the fixture, not the scanner.
    _SOURCE = '''
import os

_NAME_IN_A_CONSTANT = "HOV_PROBE_VIA_CONSTANT"


def _env_flag(name, default=False):
    """Reads os.environ directly -- found on the first pass."""
    return os.environ.get(name)


def _parse_env_limit(var, default):
    """The inner half of the delegating pair below."""
    return os.environ.get(var, "")


def limiter_from_env(var, default, window_seconds):
    """Never touches os.environ itself; only reachable transitively."""
    return _parse_env_limit(var, default)


VIA_GETENV = os.getenv("HOV_PROBE_VIA_GETENV")
VIA_ENVIRON_GET = os.environ.get("HOV_PROBE_VIA_ENVIRON_GET", "x")
VIA_SUBSCRIPT = os.environ["HOV_PROBE_VIA_SUBSCRIPT"]
VIA_CONSTANT = os.environ.get(_NAME_IN_A_CONSTANT)
VIA_HELPER = _env_flag("HOV_PROBE_VIA_HELPER")
VIA_DELEGATING_HELPER = limiter_from_env("HOV_PROBE_VIA_LIMITER", 1, 60)
DYNAMIC = os.environ.get("HOV_PROBE_" + "COMPUTED")
'''

    @pytest.fixture
    def scanned(self, tmp_path):
        (tmp_path / "probe.py").write_text(self._SOURCE, encoding="utf-8")
        return env_names_read(tmp_path)

    @pytest.mark.parametrize(
        "name",
        [
            "HOV_PROBE_VIA_GETENV",
            "HOV_PROBE_VIA_ENVIRON_GET",
            "HOV_PROBE_VIA_SUBSCRIPT",
            "HOV_PROBE_VIA_CONSTANT",
            "HOV_PROBE_VIA_HELPER",
            "HOV_PROBE_VIA_LIMITER",
        ],
    )
    def test_it_finds_every_read_shape_this_repo_uses(self, scanned, name):
        assert name in scanned

    def test_it_follows_a_helper_that_only_delegates(self, tmp_path):
        """``limiter_from_env`` hands ``var`` to ``_parse_env_limit`` and never
        reads ``os.environ`` itself. A single-pass discovery finds only the
        inner function, and the public entry point every route actually calls
        drops out of the scan with all four of its variables."""
        (tmp_path / "probe.py").write_text(self._SOURCE, encoding="utf-8")
        helpers = env_name_helpers(tmp_path)
        assert "_parse_env_limit" in helpers, "the direct reader should be found"
        assert "limiter_from_env" in helpers, "the delegating wrapper was missed"

    def test_a_computed_name_is_not_invented(self, scanned):
        """The scan reports names it can prove, not names it guesses. A
        concatenated key is unknowable statically, and reporting a wrong one
        would fail the real check over a variable that does not exist."""
        assert "HOV_PROBE_COMPUTED" not in scanned
        assert not any("COMPUTED" in name for name in scanned)

    def test_an_undocumented_variable_actually_fails_the_check(self, scanned):
        """The end-to-end proof: an undocumented read reaches the failing set.
        Without it, every assertion in this file could be satisfied by a scan
        that found things and a check that ignored them."""
        undocumented = [
            name
            for name in scanned
            if name not in INTERNAL_ONLY and not documented_in_env_example(name)
        ]
        assert "HOV_PROBE_VIA_GETENV" in undocumented

    def test_the_documentation_check_reads_commented_and_live_lines(self):
        text = "# OPTIONAL_KNOB=10\nLIVE_KNOB=1\nMENTIONED_IN_PROSE is nice\n"
        assert documented_in_env_example("OPTIONAL_KNOB", text)
        assert documented_in_env_example("LIVE_KNOB", text)
        assert not documented_in_env_example("MENTIONED_IN_PROSE", text)
        assert not documented_in_env_example("ABSENT_KNOB", text)

    def test_the_documentation_check_does_not_match_a_longer_name(self):
        """``LOGIN_RATE_LIMIT_PER_15_MIN=10`` must not count as documenting
        ``RATE_LIMIT_PER_15_MIN``, or a substring collision would silently
        exempt a real variable."""
        text = "# LOGIN_RATE_LIMIT_PER_15_MIN=10\n"
        assert not documented_in_env_example("RATE_LIMIT_PER_15_MIN", text)

    def test_the_helper_discovery_finds_this_repos_wrappers(self):
        """Named here only as evidence the derivation works -- the scan itself
        never hard-codes them."""
        helpers = env_name_helpers(API_DIR)
        assert {"limiter_from_env", "_env_flag"} <= helpers
