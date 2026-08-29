""".env.example documents every environment variable this engine reads.

The hole this closes: ``REGISTER_RATE_LIMIT_PER_HOUR`` shipped as a live,
operator-tunable throttle with no entry in ``.env.example`` -- the only one of
the five rate-limit knobs without one -- and nothing noticed, because nothing
was looking. ``NPC_CHAT_LLM_ENABLED`` had been undocumented for longer. An
undocumented knob is a knob nobody sets, which makes its default the only value
it ever has, which makes it a constant wearing a variable's costume.

:data:`SCANNED_ROOTS` is what the check covers. It was ``src/api/`` alone at
first, which is the package with the *fewest* knobs: the LLM configuration
surface -- provider, model, gate and five sampling temperatures per feature --
lives in ``ai/`` and ``src/npc/``, and nineteen live knobs were undocumented
the day the roots were widened.

Three things make this check worth more than a grep:

* The reader inventory is **derived, not transcribed**. A variable read through
  a helper (``limiter_from_env("X", ...)``) or through a module constant
  (``_LOG_LEVEL_ENV = "LOG_LEVEL"``) is still a variable an operator must be
  told about, and both indirections exist in this tree today. The helpers are
  themselves discovered -- any function that forwards its own first parameter
  into an env read is one, transitively, so ``limiter_from_env`` is found even
  though only ``_parse_env_limit`` touches ``os.environ`` -- and adding a sixth
  wrapper does not silently shrink the scan.
* **Declared name lists** are resolved the same way. ``GenericLLMClient``
  subclasses configure themselves by naming their variables in a class
  attribute (``_ENABLED_ENV_VARS = ("COMBAT_LLM_ENABLED", "MYNX_LLM_ENABLED")``)
  which the *base class* hands to ``_first_env``. Neither the sequence helper
  nor the class attribute is named here: the helper is found by the shape of
  what it does with its first parameter, and the attribute by being passed to
  it. That indirection hid all six of combat's and NPC chat's provider/model
  knobs from the literal-only scan.
* :data:`INTERNAL_ONLY` is an explicit, reasoned exemption list rather than a
  skip. Exempting a variable means writing down why, next to its name, in the
  file that fails; and :class:`TestTheExemptionListStaysHonest` retires the
  entry the moment the reason expires.
"""

import ast
import functools
import pathlib
import re
from typing import Dict

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
API_DIR = REPO_ROOT / "src" / "api"
ENV_EXAMPLE = REPO_ROOT / ".env.example"

#: The packages whose environment reads must be documented.
#:
#: ``src`` subsumes the two packages named before it. They are still listed
#: because they are where the operator-facing knobs actually cluster, and
#: because the guard tests below assert against ``src/api`` by name; a reader
#: who sees only ``src`` cannot tell whether the API layer was ever considered.
#: Scanning a directory twice costs a re-parse and changes no result -- the
#: per-root findings are unioned.
#:
#: ``tools/`` is deliberately absent. Its variables (``HOST``, ``PORT``) belong
#: to the development launcher rather than to the deployed application, and are
#: documented in ``.env.example`` anyway.
SCANNED_ROOTS = (
    API_DIR,
    REPO_ROOT / "ai",
    REPO_ROOT / "src" / "npc",
    REPO_ROOT / "src",
)

#: Variables read by :data:`SCANNED_ROOTS` that an operator is deliberately not
#: offered.
#:
#: Map each name to the reason it is not a knob. Empty today, and that is the
#: intended steady state: every variable these packages read is currently
#: something an operator may legitimately want to set. Add an entry only for a
#: variable that is genuinely internal -- a test-harness signal, a value
#: injected by the platform -- never to quiet a failure for a knob that simply
#: has not been written up yet. The fix for that one is a paragraph in
#: ``.env.example``.
INTERNAL_ONLY: Dict[str, str] = {}

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


def _label_for(path):
    """``src/api/db.py`` for a repo file; the bare name for a scratch tree."""
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:  # a scratch tree in the guard-the-guard tests
        return path.name


@functools.lru_cache(maxsize=None)
def _parsed_sources(*roots):
    """``((path, tree), ...)`` for every ``.py`` file under ``roots``.

    Cached, and returning a tuple rather than yielding, because each scan below
    walks the same trees again and ``src/`` alone is ~120 files. Duplicate
    paths are collapsed, so naming an inner root alongside its parent (which
    :data:`SCANNED_ROOTS` does, deliberately) costs one directory listing and
    changes nothing else.
    """
    seen = {}
    for root in roots:
        for path in sorted(pathlib.Path(root).rglob("*.py")):
            if path not in seen:
                seen[path] = ast.parse(path.read_text(encoding="utf-8"), str(path))
    return tuple(seen.items())


def _functions_in(roots):
    return [
        node
        for _path, tree in _parsed_sources(*roots)
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]


def env_name_helpers(*roots):
    """Names of functions under ``roots`` whose first argument is a var name.

    Iterated to a fixed point, because these wrappers delegate: discovering
    ``_parse_env_limit`` on the first pass is what makes ``limiter_from_env``
    discoverable on the second.
    """
    functions = _functions_in(roots)
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


def _iterates_first_param_as_env_names(func_node, name_helpers):
    """True when ``func_node`` loops over its first param reading each element.

    The shape ``ai/llm_client.py``'s ``_first_env`` uses::

        def _first_env(names):
            for name in names:
                value = os.getenv(name, "").strip()

    Recognised by what it does with its parameter rather than by its name, for
    the same reason :func:`env_name_helpers` is: a second one written tomorrow
    is found without editing this file.
    """
    first = _first_param(func_node)
    if first is None:
        return False
    for loop in ast.walk(func_node):
        if not isinstance(loop, ast.For):
            continue
        if not (isinstance(loop.iter, ast.Name) and loop.iter.id == first):
            continue
        if not isinstance(loop.target, ast.Name):
            continue
        element = loop.target.id
        for node in ast.walk(loop):
            if isinstance(node, ast.Call):
                called = node.func
                named = (
                    called.id
                    if isinstance(called, ast.Name)
                    else called.attr if isinstance(called, ast.Attribute) else None
                )
                arg = node.args[0] if node.args else None
                if (_is_direct_env_read(called) or named in name_helpers) and (
                    isinstance(arg, ast.Name) and arg.id == element
                ):
                    return True
            if isinstance(node, ast.Subscript) and _is_env_subscript(node):
                if isinstance(node.slice, ast.Name) and node.slice.id == element:
                    return True
    return False


def env_sequence_helpers(*roots):
    """Functions taking a *sequence* of variable names as their first argument.

    Kept separate from :func:`env_name_helpers` because the two consume their
    first parameter differently: one is handed a name, the other a list of
    them. Collapsing the two sets would let a wrapper that forwards a whole
    list be mistaken for one that forwards a single name, and the argument
    would then be reported as a variable literally called
    ``_ENABLED_ENV_VARS``.
    """
    name_helpers = env_name_helpers(*roots)
    return {
        node.name
        for node in _functions_in(roots)
        if _iterates_first_param_as_env_names(node, name_helpers)
    }


def declared_name_sequences(*roots):
    """``IDENTIFIER -> {(variable name, declaring file), ...}``.

    Walks whole trees rather than module level only, because in this repo these
    declarations are *class attributes* -- that is the point of them: the
    subclass names its variables and the base class reads them. They are also
    pooled across every scanned file for the same reason. The class declaring
    ``COMBAT_LLM_ENABLED`` (``ai/combat_strategist.py``) and the ``_first_env``
    call that reads it (``ai/llm_client.py``) sit in different modules, so a
    per-file table resolves neither.

    Attribution is to the *declaring* file. An operator asking where
    ``COMBAT_LLM_MODEL`` comes from is better served by the class that names it
    than by the base-class loop that happens to read it.
    """
    declared = {}
    for path, tree in _parsed_sources(*roots):
        label = _label_for(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                targets = node.targets
            elif isinstance(node, ast.AnnAssign):
                targets = [node.target]
            else:
                continue
            if not isinstance(node.value, (ast.Tuple, ast.List)):
                continue
            elements = node.value.elts
            values = [
                element.value
                for element in elements
                if isinstance(element, ast.Constant) and isinstance(element.value, str)
            ]
            # All-or-nothing: a mixed tuple is not a declared name list, and
            # half of one is a guess.
            if not values or len(values) != len(elements):
                continue
            for target in targets:
                if isinstance(target, ast.Name):
                    declared.setdefault(target.id, set()).update(
                        (value, label) for value in values
                    )
    return declared


def _sequence_argument_identifier(expr):
    """The identifier a sequence argument names, or ``None`` for a literal.

    Unwraps subscripts so ``self._PROVIDER_ENV_VARS[:1]`` -- the "only the
    first entry counts as an explicit choice" read in ``_resolve_provider`` --
    resolves to the same declaration as the unsliced form. Reporting the whole
    tuple for a sliced read is the safe direction: every name in it is one this
    code can read.
    """
    while isinstance(expr, ast.Subscript):
        expr = expr.value
    if isinstance(expr, ast.Name):
        return expr.id
    if isinstance(expr, ast.Attribute):
        return expr.attr
    return None


def env_names_read(*roots):
    """``VAR -> {source files}`` for every env var ``roots`` read.

    Two arms, because this tree reads variables two ways. The first resolves a
    name at the point it is read -- a literal, a module constant, or either of
    those handed to a discovered wrapper. The second resolves a *declared list*
    of names handed to a discovered sequence helper; see
    :func:`declared_name_sequences` for why that one has to be pooled across
    files while the first stays file-local.
    """
    helpers = env_name_helpers(*roots)
    sequence_helpers = env_sequence_helpers(*roots)
    declared = declared_name_sequences(*roots)
    found = {}

    def record(name, label):
        found.setdefault(name, set()).add(label)

    for path, tree in _parsed_sources(*roots):
        constants = _module_level_strings(tree)
        label = _label_for(path)

        def literal(expr, _constants=constants):
            if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
                return expr.value
            if isinstance(expr, ast.Name):
                return _constants.get(expr.id)
            return None

        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                called = node.func
                called_name = (
                    called.id
                    if isinstance(called, ast.Name)
                    else called.attr if isinstance(called, ast.Attribute) else None
                )
                if not node.args:
                    continue
                if _is_direct_env_read(called) or called_name in helpers:
                    name = literal(node.args[0])
                    if name:
                        record(name, label)
                elif called_name in sequence_helpers:
                    for name in _sequence_literal(node.args[0]):
                        record(name, label)
                    identifier = _sequence_argument_identifier(node.args[0])
                    for name, declared_in in declared.get(identifier, ()):
                        record(name, declared_in)
            elif isinstance(node, ast.Subscript) and _is_env_subscript(node):
                name = literal(node.slice)
                if name:
                    record(name, label)

    return found


def _sequence_literal(expr):
    """The strings in a ``("A", "B")`` argument written out at the call site."""
    if not isinstance(expr, (ast.Tuple, ast.List)):
        return []
    return [
        element.value
        for element in expr.elts
        if isinstance(element, ast.Constant) and isinstance(element.value, str)
    ]


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


class TestEveryEnvVarIsDocumented:
    def test_env_example_exists(self):
        assert ENV_EXAMPLE.is_file(), "the file this suite checks against is missing"

    def test_the_scan_found_the_variables_we_know_are_there(self):
        """A scan that silently returned nothing would make the real check
        below pass forever. These five are read through five *different*
        mechanisms -- a bare literal, a module constant, a limiter helper, a
        flag helper and a class-declared name list -- so their presence proves
        each arm of the scan is live.
        """
        names = env_names_read(*SCANNED_ROOTS)
        for expected in (
            "TURSO_DATABASE_URL",  # os.environ.get("...") literal
            "LOG_LEVEL",  # os.environ.get(_LOG_LEVEL_ENV) module constant
            "REGISTER_RATE_LIMIT_PER_HOUR",  # limiter_from_env("...", ...)
            "COMBAT_SOCKET_STREAMING",  # _env_flag("...", default=False)
            "COMBAT_LLM_ENABLED",  # _first_env(self._ENABLED_ENV_VARS)
        ):
            assert expected in names, "%s not found by the scan" % expected

    def test_each_scanned_root_contributes_something(self):
        """``SCANNED_ROOTS`` names four packages; a typo in one of them would
        silently narrow the check back towards the ``src/api``-only scan that
        left nineteen live knobs undocumented, and every other test here would
        still pass.
        """
        empty = [
            root.as_posix()
            for root in SCANNED_ROOTS
            if not env_names_read(root)
        ]
        assert not empty, "these roots contributed no variables at all: %r" % empty

    def test_every_variable_read_is_documented(self):
        undocumented = {
            name: sorted(files)
            for name, files in sorted(env_names_read(*SCANNED_ROOTS).items())
            if name not in INTERNAL_ONLY and not documented_in_env_example(name)
        }
        assert not undocumented, (
            "these environment variables are read by this engine but have no "
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
        names = env_names_read(*SCANNED_ROOTS)
        stale = sorted(name for name in INTERNAL_ONLY if name not in names)
        assert not stale, (
            "INTERNAL_ONLY exempts variables nothing reads any more: %r" % stale
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


def _first_env(names):
    """Takes a sequence of names, not one name -- the GenericLLMClient shape."""
    for name in names:
        value = os.getenv(name, "")
        if value:
            return value
    return ""


class Feature:
    """Declares its variables; the read happens in the base class below."""

    _NAMES = ("HOV_PROBE_VIA_DECLARED_LIST", "HOV_PROBE_VIA_DECLARED_FALLBACK")
    _MIXED = ("HOV_PROBE_NOT_ALL_LITERAL", DYNAMIC)

    def resolve(self):
        return _first_env(self._NAMES)

    def resolve_first_only(self):
        return _first_env(self._NAMES[:1])


VIA_SEQUENCE_LITERAL = _first_env(("HOV_PROBE_VIA_SEQUENCE_LITERAL",))
VIA_MIXED_SEQUENCE = _first_env(Feature._MIXED)
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
            "HOV_PROBE_VIA_SEQUENCE_LITERAL",
            "HOV_PROBE_VIA_DECLARED_LIST",
            "HOV_PROBE_VIA_DECLARED_FALLBACK",
        ],
    )
    def test_it_finds_every_read_shape_this_repo_uses(self, scanned, name):
        assert name in scanned

    def test_a_sliced_declared_list_still_reports_the_whole_list(self, scanned):
        """``_resolve_provider`` reads ``self._PROVIDER_ENV_VARS[:1]`` as well
        as the whole tuple. Both entries are names this code can read, and the
        slice is the narrower read, so reporting the full declaration is the
        direction that cannot hide a knob."""
        assert "HOV_PROBE_VIA_DECLARED_FALLBACK" in scanned

    def test_a_partly_computed_declared_list_is_not_half_read(self, scanned):
        """A tuple whose entries are not all string literals is not a declared
        name list. Reporting the literal half would demand documentation for a
        name while silently dropping its neighbour -- worse than reporting
        neither, because it looks complete."""
        assert "HOV_PROBE_NOT_ALL_LITERAL" not in scanned

    def test_it_finds_a_sequence_helper_by_shape(self, tmp_path):
        """``_first_env`` never appears in this file by name. It is found
        because it loops over its first parameter and reads each element, which
        is what makes a second one written tomorrow findable too."""
        (tmp_path / "probe.py").write_text(self._SOURCE, encoding="utf-8")
        assert "_first_env" in env_sequence_helpers(tmp_path)
        assert "_first_env" not in env_name_helpers(tmp_path), (
            "a sequence helper misfiled as a name helper would report its "
            "argument identifier as if it were a variable name"
        )

    def test_a_declaration_in_another_module_is_still_resolved(self, tmp_path):
        """The real shape: ``ai/combat_strategist.py`` names
        ``COMBAT_LLM_ENABLED`` and ``ai/llm_client.py`` reads it. A per-file
        constant table resolves neither half."""
        (tmp_path / "base.py").write_text(
            "import os\n"
            "def _first_env(names):\n"
            "    for name in names:\n"
            "        if os.getenv(name, ''):\n"
            "            return name\n"
            "    return ''\n"
            "class Base:\n"
            "    def go(self):\n"
            "        return _first_env(self._NAMES)\n",
            encoding="utf-8",
        )
        (tmp_path / "feature.py").write_text(
            'class Feature:\n    _NAMES = ("HOV_PROBE_CROSS_MODULE",)\n',
            encoding="utf-8",
        )
        scanned = env_names_read(tmp_path)
        assert "HOV_PROBE_CROSS_MODULE" in scanned
        assert scanned["HOV_PROBE_CROSS_MODULE"] == {"feature.py"}, (
            "a declared variable is attributed to the module that names it, "
            "not to the base-class loop that reads it"
        )

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
        assert "_NAMES" not in scanned, (
            "the identifier holding a declared list is not itself a variable"
        )

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
        assert {"limiter_from_env", "_env_flag"} <= env_name_helpers(API_DIR)
        assert "_first_env" in env_sequence_helpers(*SCANNED_ROOTS)
