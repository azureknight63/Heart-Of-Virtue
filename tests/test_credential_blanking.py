"""Every secret this repo declares is classified, and the outbound ones are blank.

THREE INCIDENTS, ONE SHAPE. The test harness has, on separate occasions, filed
20 real GitHub issues, written real rows to the production Turso database, and
spent real LLM provider credit while shipping harness-authored dialogue
off-box. Each was closed by adding one more name to a hand-maintained list, and
each time the next omission was exactly as invisible as the last had been.

The list was ``PROVIDER_KEY_ENVS + ("GITHUB_TOKEN",)``, with a comment calling
that "the non-LLM credential that also rides in on ``.env``". At the time it
was written there were at least four, and by the time this file was added there
were ten.

So the question is asked the other way round -- twice, because the first
inversion did not go far enough.

The first version read the NAMES declared in ``.env`` and ``.env.example`` and
required every *secret-shaped* one to be classified as outbound (blanked) or
local-only (deliberately not). On its first run it found ``ANTHROPIC_API_KEY``
and ``OPENAI_API_KEY`` sitting unblanked in ``.env.example`` -- documented as
supported, absent from the provider registry that ``PROVIDER_KEY_ENVS`` derives
from, and invisible to every list that had come before it.

But "secret-shaped" was itself a hand-maintained list: a regex of credential
word stems (KEY, TOKEN, SECRET, PASS, WEBHOOK, ...). A credential named
``*_DSN``, ``*_BASE_URL``, ``*_ENDPOINT`` or ``*_HOOK`` never reached the
classifier at all, so it passed exactly as silently as an unclassified one
would have. ``OLLAMA_BASE_URL`` is the proof: it matched no stem, and was
covered only because somebody had hand-listed it somewhere else.

So the filter is gone. EVERY declared name must be classified now -- as
outbound, local-only, an LLM setting (both of those classes are derived, not
listed), or as a non-credential with a written reason in ``NON_SECRET_ENVS``.
The list of things to think about is no longer chosen by a pattern that can be
wrong about what a credential looks like.

THEN A THIRD TIME, because even that only asked half the question. Both
inversions above start from the ENV FILES, so both share one blind spot: a
credential the code reads and nobody ever wrote down is invisible to them, and
so is a process that loads ``.env`` without sweeping. Two more questions,
asked from the code:

* :class:`TestEveryNameTheCodeReadsIsDeclared` -- is every environment name
  ``src/`` and ``tools/`` READ declared in ``.env.example``? On its first run
  it found seven, including ``INQUISITOR_SMTP_PASSWORD``: an SMTP credential
  read by ``tools/inquisitor/email_reporter.py``, declared nowhere, therefore
  classified by nothing and blanked by nothing.
* :class:`TestEveryToolThatLoadsDotenvSweeps` -- is every ``tools/`` entry
  point whose imports reach a module that loads ``.env`` actually blanking the
  shared vocabulary? Six of the eight were not. ``tools/bug_hunt.py`` was the
  one that had been fixed, three incidents in; the other five were the same
  hazard with nobody watching, and ``tools/api_fuzzer.py`` POSTs to
  ``/api/feedback`` and ``/api/auth/register`` -- the exact two routes whose
  missing guards caused incidents one and two.

That test runs each tool for real rather than reading it for a magic line: it
executes the module body in a subprocess with fake credentials set, and checks
they come back blank. A guard that greps for the name of a function is
satisfied by a file that imports it and never calls it.
"""

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.llm_doubles import (
    LLM_SETTING_ENVS,
    LOCAL_ONLY_SECRET_ENVS,
    NON_SECRET_ENVS,
    OUTBOUND_CREDENTIAL_ENVS,
    classify_env_name,
    declared_env_names,
    env_names_read_under,
)

#: The committed inventory, plus the developer's real file when it exists.
#: ``.env`` is gitignored, so CI sees only the example -- which is why the
#: example is the one that must stay complete.
ENV_FILES = (".env", ".env.example")


def _declared():
    return declared_env_names(*ENV_FILES)


class TestEverySecretIsClassified:
    def test_the_scan_finds_something(self):
        """Non-vacuity. A scan that reads nothing agrees with any claim.

        The env files could move or the parser could break on a format change,
        and every assertion below would pass silently. That is the failure this
        whole file exists to prevent, so it would be absurd to leave the door
        open here. The floor is set against ``.env.example`` alone (the file CI
        sees), which declares more than fifty.
        """
        assert len(_declared()) >= 40, sorted(_declared())

    def test_no_declared_name_is_unclassified(self):
        unclassified = sorted(n for n in _declared() if classify_env_name(n) is None)
        assert unclassified == [], (
            "these variables are declared in %s and classified as nothing: "
            "%s\n\n"
            "Every declared name needs an answer, not just the ones that look "
            "like credentials -- looking like one was the filter that let "
            "*_BASE_URL through. Put each in:\n"
            "  OUTBOUND_CREDENTIAL_ENVS  if it authenticates to, or addresses, "
            "anything off this machine (blanked in tests and in "
            "tools/bug_hunt.py)\n"
            "  LOCAL_ONLY_SECRET_ENVS    if it is a secret that never leaves "
            "this box, with a one-line reason\n"
            "  NON_SECRET_ENVS           if it is not a credential at all, "
            "with a one-line reason\n"
            "Do not delete it from the scan. A name picked up from a prose "
            "comment in your own .env still needs an answer; if that is what "
            "this is, the answer is usually NON_SECRET_ENVS."
            % (", ".join(ENV_FILES), ", ".join(unclassified))
        )

    def test_the_classes_do_not_overlap(self):
        classes = {
            "OUTBOUND_CREDENTIAL_ENVS": set(OUTBOUND_CREDENTIAL_ENVS),
            "LOCAL_ONLY_SECRET_ENVS": set(LOCAL_ONLY_SECRET_ENVS),
            "NON_SECRET_ENVS": set(NON_SECRET_ENVS),
        }
        names = sorted(classes)
        for i, left in enumerate(names):
            for right in names[i + 1 :]:
                both = classes[left] & classes[right]
                assert both == set(), "%s and %s both claim %s" % (
                    left,
                    right,
                    sorted(both),
                )

    def test_every_non_secret_carries_a_reason(self):
        """The allow-list is only worth more than the regex if each entry was
        actually decided. An empty or one-word reason is a name somebody waved
        through, which is the failure mode this class replaced."""
        thin = sorted(
            name
            for name, reason in NON_SECRET_ENVS.items()
            if len(reason.split()) < 5
        )
        assert thin == [], (
            "these NON_SECRET_ENVS entries have no real reason written: %s"
            % ", ".join(thin)
        )

    def test_a_credential_the_old_regex_missed_would_now_fail(self, tmp_path):
        """The regression this inversion exists for, run against the parser.

        ``ACME_BASE_URL`` / ``ACME_DSN`` / ``ACME_ENDPOINT`` / ``ACME_HOOK``
        matched none of the retired pattern's stems, so the old scan never
        showed them to the classifier. They must now come back unclassified.
        """
        env = tmp_path / ".env.fake"
        env.write_text(
            "ACME_BASE_URL=https://acme.test\n"
            "ACME_DSN=postgres://u:p@acme.test/db\n"
            "# ACME_ENDPOINT=https://acme.test/v1\n"
            "ACME_HOOK=https://acme.test/hook/abc\n",
            encoding="utf-8",
        )
        declared = declared_env_names(str(env))
        assert declared == {
            "ACME_BASE_URL",
            "ACME_DSN",
            "ACME_ENDPOINT",
            "ACME_HOOK",
        }
        assert all(classify_env_name(n) is None for n in declared)

    def test_a_lowercase_credential_url_would_now_fail(self, tmp_path):
        """The filter that SURVIVED the first inversion, and its regression.

        Dropping the word-stem regex left a second shape test behind:
        ``name.isupper()``. Convention is not a rule. ``requests`` resolves
        proxies through ``urllib.request.getproxies()``, which reads the
        LOWERCASE ``https_proxy`` / ``http_proxy`` / ``all_proxy``, so a
        declared ``https_proxy=http://user:pass@corp/`` is a credential-bearing
        URL that routes ``feedback.py``'s GitHub POST and every LLM call
        through a third party. The scan dropped it before the classifier could
        object -- the same silence the word stems produced, one level down.
        """
        env = tmp_path / ".env.fake"
        env.write_text(
            "https_proxy=http://user:pass@corp.example/\n"
            "# all_proxy=socks5://user:pass@corp.example:1080\n"
            "no_proxy=localhost\n",
            encoding="utf-8",
        )
        declared = declared_env_names(str(env))
        assert declared == {"https_proxy", "all_proxy", "no_proxy"}
        assert all(classify_env_name(n) is None for n in declared)

    def test_prose_containing_an_equals_sign_is_not_a_declaration(self, tmp_path):
        """The control for the test above.

        Dropping the case requirement is only safe if what remains still tells
        a declaration from a sentence. Otherwise the fix trades a blind spot
        for a permanent false alarm, and the next person widens the filter
        again to shut it up -- which is how the first one got there.
        """
        env = tmp_path / ".env.fake"
        env.write_text(
            "# see docs/tuning.md, where temperature=0.65 is argued\n"
            "# NOTE: this file uses a=b style pairs\n"
            "REAL_NAME=1\n",
            encoding="utf-8",
        )
        assert declared_env_names(str(env)) == {"REAL_NAME"}


class TestOutboundCredentialsAreBlankInThisProcess:
    """conftest blanks these at import; this proves it, per name.

    Asserted individually rather than as a set so a failure names the variable
    that is live rather than reporting that some unspecified one is.
    """

    @pytest.mark.parametrize("name", sorted(OUTBOUND_CREDENTIAL_ENVS))
    def test_it_is_blank(self, name):
        value = os.environ.get(name, "")
        assert value == "", (
            "%s is set in this pytest process. tests/conftest.py blanks every "
            "name in OUTBOUND_CREDENTIAL_ENVS before the first src.api import; "
            "if this fails, either the blanking ran too late or something "
            "re-set it afterwards." % name
        )


# ---------------------------------------------------------------------------
# The third inversion, part one: start from the code, not from the env files.
# ---------------------------------------------------------------------------

#: The roots whose environment reads must be documented. ``ai/`` is deliberately
#: out: everything it reads goes through ``GenericLLMClient._first_env`` on a
#: tuple its callers build, which is a computed name and not something a literal
#: scan can see. That half is covered from the other direction, by
#: ``LLM_GATE_SUFFIXES`` and by the declared-name tests above.
CODE_ROOTS = ("src", "tools")


class TestEveryNameTheCodeReadsIsDeclared:
    """``.env.example`` is the inventory. An undeclared read is a blind spot.

    Every scan above starts from the env files, so a variable the code reads
    but nobody wrote down cannot fail any of them -- it is not merely
    unclassified, it is unseen. ``INQUISITOR_SMTP_PASSWORD`` was exactly that,
    and it is a password for a real mail server, read by a module a full
    Inquisitor run calls at the end of every session.
    """

    def test_the_scan_finds_something(self):
        """Non-vacuity, and for THIS scan a live risk rather than a formality:
        it resolves indirection through a DERIVED helper set, so a refactor
        that changed how those helpers take their argument would quietly drop
        names rather than error. Thirty-five are found today."""
        read = env_names_read_under(*CODE_ROOTS)
        assert len(read) >= 25, sorted(read)

    def test_every_env_name_the_code_reads_is_declared(self):
        read = env_names_read_under(*CODE_ROOTS)
        declared = declared_env_names(".env.example")
        missing = sorted(n for n in read if n not in declared)
        assert missing == [], (
            "these variables are READ under %s and declared in .env.example "
            "nowhere:\n%s\n\n"
            "An undeclared name is worse than an unclassified one: every other "
            "test in this file scans the env files, so nothing can see it at "
            "all. Declare it in .env.example (commented out is fine -- that is "
            "how most of that file ships), which then forces "
            "test_no_declared_name_is_unclassified to make you say what it is."
            % (
                "/".join(CODE_ROOTS),
                "\n".join(
                    "  %s  <- %s" % (n, ", ".join(sorted(read[n]))) for n in missing
                ),
            )
        )

    def test_the_scan_sees_through_a_helper_and_a_constant(self, tmp_path):
        """The two indirections this repo actually uses, as a regression.

        ``limiter_from_env("FEEDBACK_RATE_LIMIT_PER_HOUR", ...)`` never touches
        ``os.environ`` in its own body -- it forwards to a function that does --
        and ``os.getenv(SAVE_V2_ENV_VAR)`` names its variable through a module
        constant. A scan of literal ``os.environ[...]`` arguments alone sees
        neither, and would report a clean sweep while missing the reads that
        matter. ``PLAINLY_READ`` is the control: if the helper machinery breaks
        outright, that one still has to come back.
        """
        (tmp_path / "mod.py").write_text(
            "import os\n"
            "CONST_NAME = 'VIA_A_CONSTANT'\n"
            "def _leaf(name, default=''):\n"
            "    return os.environ.get(name, default)\n"
            "def _branch(name):\n"
            "    return _leaf(name, '0')\n"
            "def go():\n"
            "    return (\n"
            "        os.environ['PLAINLY_READ'],\n"
            "        os.getenv(CONST_NAME),\n"
            "        _branch('VIA_TWO_HELPERS'),\n"
            "    )\n",
            encoding="utf-8",
        )
        read = env_names_read_under(str(tmp_path))
        assert set(read) == {"PLAINLY_READ", "VIA_A_CONSTANT", "VIA_TWO_HELPERS"}


# ---------------------------------------------------------------------------
# The third inversion, part two: is every process that loads .env covered?
# ---------------------------------------------------------------------------

#: Tools that are SUPPOSED to run with live credentials, and why.
#:
#: An allow-list, not an exception list: a tool is here because using the real
#: environment is the point of it, and each entry has to say so. Anything not
#: named here that reaches a ``.env`` loader must sweep.
TOOLS_ALLOWED_LIVE_CREDENTIALS = {
    "run_api.py": (
        "This one IS the server. It runs the real app against the real "
        "configuration -- that is its entire job, and blanking the "
        "credentials would leave a developer debugging a database that "
        "will not connect. It also never runs under pytest."
    ),
}


def _module_path(module):
    """The file backing a dotted local module name, or ``None``.

    Package before module, which is what Python does -- and it matters here:
    ``tools/inquisitor.py`` and ``tools/inquisitor/`` both exist, so the name
    ``tools.inquisitor`` resolves to the PACKAGE and the script is reachable
    only by path. (That collision is not this file's problem, but a reach
    analysis that got it backwards would silently analyse the wrong file.)
    """
    base = Path(module.replace(".", "/"))
    for candidate in (base / "__init__.py", base.with_suffix(".py")):
        if candidate.is_file():
            return candidate
    return None


def _parse(path):
    try:
        return ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError):
        return None


def _local_imports(tree):
    """Every local module this file imports, at ANY nesting depth.

    Function-body imports count. ``create_app`` imports ``src.api.db`` inside
    itself, and that import is what loads ``.env`` for ``tools/api_fuzzer.py``
    -- a graph over module-level imports alone reports that file as clean.
    """
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            out.add(node.module)
            out.update("%s.%s" % (node.module, a.name) for a in node.names)
    return {m for m in out if m.split(".")[0] in ("src", "ai", "tools")}


def _loads_dotenv_on_import(tree):
    """Does importing this module load ``.env``?

    DERIVED from the call, not from a list of the three modules that happen to
    do it today: a statement at module scope calling ``load_project_env`` or
    ``load_dotenv``. Bodies of functions and classes are not module scope and
    are skipped, which is the difference between ``src/api/db.py`` (loads on
    import) and ``src/env_bootstrap.py`` (merely defines the loader).
    """
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        for inner in ast.walk(node):
            if isinstance(inner, ast.Call):
                name = getattr(inner.func, "id", None) or getattr(
                    inner.func, "attr", None
                )
                if name in ("load_project_env", "load_dotenv"):
                    return True
    return False


def _tools_that_load_dotenv():
    """``{filename: {loader module, ...}}`` for every ``tools/*.py`` script."""
    reached = {}
    for tool in sorted(Path("tools").glob("*.py")):
        tree = _parse(tool)
        if tree is None:
            continue
        seen, stack, loaders = set(), list(_local_imports(tree)), set()
        while stack:
            module = stack.pop()
            if module in seen:
                continue
            seen.add(module)
            path = _module_path(module)
            if path is None:
                continue
            subtree = _parse(path)
            if subtree is None:
                continue
            if _loads_dotenv_on_import(subtree):
                loaders.add(module)
            stack.extend(m for m in _local_imports(subtree) if m not in seen)
        if loaders:
            reached[tool.name] = loaders
    return reached


#: Executes one tool's module body, then forces ``.env`` to load, then reports
#: which of the given names still hold a value. Forcing the load AFTERWARDS is
#: the part that matters: ``load_dotenv(override=False)`` skips keys that are
#: present and REFILLS ones that are absent, so a tool that popped its
#: credentials instead of assigning "" passes a naive check and fails this one.
_PROBE = """
import importlib.util, json, os, sys

spec = importlib.util.spec_from_file_location("_probe_tool", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
sys.modules["_probe_tool"] = mod
err = None
try:
    spec.loader.exec_module(mod)
except BaseException as exc:
    err = "%s: %s" % (type(exc).__name__, exc)

try:
    from src.env_bootstrap import load_project_env
    load_project_env()
    reloaded = True
except BaseException as exc:
    reloaded = "%s: %s" % (type(exc).__name__, exc)

live = sorted(n for n in json.loads(sys.argv[2]) if os.environ.get(n, ""))
print("PROBE_RESULT " + json.dumps(
    {"live": live, "error": err, "reloaded": reloaded,
     "npc_chat": os.environ.get("NPC_CHAT_LLM_ENABLED", "")}))
"""

#: Fake values, so this test says the same thing on a machine with no ``.env``
#: as on a developer's. Every host is unroutable and every token is nonsense:
#: the child executes module bodies only, but a probe for a credential leak
#: should not be able to cause one.
_FAKE_CREDENTIALS = {
    "GITHUB_TOKEN": "probe-not-a-real-token",
    "TURSO_DATABASE_URL": "libsql://127.0.0.1:1",
    "TURSO_AUTH_TOKEN": "probe-not-a-real-token",
    "OPENROUTER_API_KEY": "probe-not-a-real-key",
    "GROQ_API_KEY": "probe-not-a-real-key",
    "CEREBRAS_API_KEY": "probe-not-a-real-key",
    "ANTHROPIC_API_KEY": "probe-not-a-real-key",
    "OPENAI_API_KEY": "probe-not-a-real-key",
    "OLLAMA_BASE_URL": "http://127.0.0.1:1",
    "INQUISITOR_SMTP_HOST": "127.0.0.1",
    "INQUISITOR_SMTP_PASSWORD": "probe-not-a-real-password",
    "INQUISITOR_REPORT_EMAIL": "probe@example.invalid",
    "HOV_ANALYTICS_WEBHOOK_URL": "http://127.0.0.1:1/hook",
    "NEXUS_PASS": "probe-not-a-real-password",
    "NPC_CHAT_LLM_ENABLED": "1",
}

_MUST_BE_BLANK = sorted(set(OUTBOUND_CREDENTIAL_ENVS) | set(LLM_SETTING_ENVS))


def _run_probe(tool_name):
    env = dict(os.environ)
    env.update(_FAKE_CREDENTIALS)
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            _PROBE,
            "tools/" + tool_name,
            json.dumps(_MUST_BE_BLANK),
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=300,
    )
    for line in completed.stdout.splitlines():
        if line.startswith("PROBE_RESULT "):
            return json.loads(line[len("PROBE_RESULT ") :])
    raise AssertionError(
        "the probe produced no result for tools/%s\nstdout:\n%s\nstderr:\n%s"
        % (tool_name, completed.stdout[-4000:], completed.stderr[-4000:])
    )


_LOADER_TOOLS = _tools_that_load_dotenv()
_TOOLS_THAT_MUST_SWEEP = sorted(
    name for name in _LOADER_TOOLS if name not in TOOLS_ALLOWED_LIVE_CREDENTIALS
)


class TestEveryToolThatLoadsDotenvSweeps:
    """One sweep, asserted in every process that needs it.

    The inventory used to be enforced in exactly one place -- this file, over
    the pytest process -- plus one hand-written check that ``tools/bug_hunt.py``
    mentioned ``CREDENTIAL_ENVS``. Every other harness entry point ran with the
    developer's real ``.env`` and nothing watching. Six of the eight tools that
    load it were leaking when this class was written.
    """

    def test_the_reach_analysis_is_not_vacuous(self):
        """A bug in the graph walk would empty the parametrised tests below
        into a green nothing. These are known-good anchors from opposite ends:
        bug_hunt.py is the tool that must sweep, run_api.py the one that must
        not, and both have to be SEEN."""
        assert "bug_hunt.py" in _LOADER_TOOLS, sorted(_LOADER_TOOLS)
        assert "run_api.py" in _LOADER_TOOLS, sorted(_LOADER_TOOLS)
        assert len(_TOOLS_THAT_MUST_SWEEP) >= 5, _TOOLS_THAT_MUST_SWEEP

    def test_the_allow_list_names_real_tools_with_real_reasons(self):
        for name, reason in TOOLS_ALLOWED_LIVE_CREDENTIALS.items():
            assert Path("tools", name).is_file(), (
                "%s is allow-listed to run with live credentials but does not "
                "exist. A stale entry here is a hole that looks like a "
                "decision." % name
            )
            assert len(reason.split()) >= 10, (
                "%s is allow-listed with no real reason written. Running with "
                "production credentials is the one thing in this file that "
                "needs an argument, not a shrug." % name
            )

    @pytest.mark.parametrize("tool_name", _TOOLS_THAT_MUST_SWEEP)
    def test_the_tool_blanks_outbound_credentials(self, tool_name):
        """Run it for real. Do not grep it for the name of the sweep.

        A textual check is satisfied by a file that imports
        ``blank_outbound_env`` and never calls it, or calls it after the import
        that spends the money. This executes the module body with fake
        credentials in the environment and asks what survived.
        """
        result = _run_probe(tool_name)
        assert result["live"] == [], (
            "tools/%s leaves these live after its module body runs: %s\n\n"
            "It reaches a module that loads .env (%s), so a developer's real "
            "credentials are in os.environ by the time anything in it runs. "
            "Add, above its first src./ai. import:\n\n"
            "    from tests.llm_doubles import blank_outbound_env\n\n"
            "    blank_outbound_env()\n\n"
            "If this tool is genuinely meant to run against live services, "
            "put it in TOOLS_ALLOWED_LIVE_CREDENTIALS with a reason instead."
            % (
                tool_name,
                ", ".join(result["live"]),
                ", ".join(sorted(_LOADER_TOOLS[tool_name])),
            )
        )
        assert result["npc_chat"] in ("", "0"), (
            "tools/%s leaves NPC_CHAT_LLM_ENABLED=%r. That gate alone is what "
            "shipped harness-authored dialogue to a paid provider; pinning "
            "MYNX_* never touched it." % (tool_name, result["npc_chat"])
        )
        assert result["reloaded"] is True, (
            "the probe could not re-load .env after tools/%s, so it never "
            "tested the half that matters -- that the values were ASSIGNED "
            "blank rather than popped. Reason: %s"
            % (tool_name, result["reloaded"])
        )

    @pytest.mark.parametrize("tool_name", _TOOLS_THAT_MUST_SWEEP)
    def test_the_tool_does_not_hand_list_credentials(self, tool_name):
        """A literal credential name in an entry point is a list starting again.

        The Turso pair was once spelled in ``tools/bug_hunt.py`` AND
        ``tests/conftest.py``; ``tools/measure_llm_tokens.py`` later grew a
        third derivation that silently omitted five names. Comments are
        stripped: naming a variable in prose is how the reasoning gets written
        down, and that is wanted.
        """
        source = Path("tools", tool_name).read_text(encoding="utf-8")
        code = "\n".join(
            line for line in source.splitlines() if not line.strip().startswith("#")
        )
        restated = sorted(
            name
            for name in OUTBOUND_CREDENTIAL_ENVS
            if '"%s"' % name in code or "'%s'" % name in code
        )
        assert restated == [], (
            "tools/%s spells these credential names literally: %s. They are "
            "already in OUTBOUND_CREDENTIAL_ENVS, which blank_outbound_env "
            "sweeps -- a second spelling is how TURSO_* came to be maintained "
            "in two places at once." % (tool_name, ", ".join(restated))
        )
