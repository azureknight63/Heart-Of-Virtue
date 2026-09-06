"""Canonical doubles and factories for the ``ai/llm_client.py`` test suite.

Why this module exists
----------------------
Five files grew their own copies of the same four things, and the copies had
drifted into shapes that could not be swapped for one another:

* ``_Resp`` existed three times with three attribute sets — one carried
  ``headers``, one carried ``json()``, one carried neither — so a test moved
  between files silently changed what the transport under test could read.
* ``_HeaderResp`` existed twice with **incompatible positional constructors**:
  ``_HeaderResp(429)`` meant a status in one file and ``_HeaderResp({...})``
  meant a headers dict in the other. Copying a line across files produced a
  passing test that recorded the wrong thing. :class:`Resp` ends that by having
  one signature, status first, with ``headers`` keyword-only in practice.
* Thirteen ``NpcChatLLMAdapter.__new__`` stand-in builders shared two names
  (``_adapter``/``_adapter_returning``) across three files under five distinct
  signatures. :func:`make_chat_adapter` is the one factory.
* The provider-credential blank list was spelled in five places with five
  different subsets, while ``ai.llm_client._OPENAI_COMPATIBLE_PROVIDERS`` is
  the actual source of truth. Adding a fourth provider and missing one site
  lets a unit test dial a live endpoint — the exact hazard ``tests/conftest.py``
  says its blanking exists to prevent. :data:`PROVIDER_KEY_ENVS` is derived, so
  a new provider is covered everywhere the moment it is registered.

This is a plain module, not a ``conftest.py``, so nothing here is auto-injected;
:func:`isolate_llm_class_state` is a fixture a module opts into by name (see its
docstring). Sibling harness for the NPC/chat mixin: ``tests/_npc_fixtures.py``.
"""

import ast
import re
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Tuple, Type, TypeVar

from ai.llm_client import (
    _OPENAI_COMPATIBLE_PROVIDERS,
    GenericLLMClient,
    NpcChatLLMAdapter,
)

import pytest

import ai.llm_client as llm

__all__ = [
    "PROVIDER_KEY_ENVS",
    "PROVIDER_MODEL_ENVS",
    "CREDENTIAL_ENVS",
    "OUTBOUND_CREDENTIAL_ENVS",
    "LOCAL_ONLY_SECRET_ENVS",
    "NON_SECRET_ENVS",
    "declared_env_names",
    "env_names_read_under",
    "classify_env_name",
    "LLM_GATE_SUFFIXES",
    "LLM_SETTING_ENVS",
    "llm_gate_envs",
    "HARNESS_ENV_PINS",
    "blank_outbound_env",
    "Resp",
    "make_chat_adapter",
    "make_generic_client",
    "isolate_llm_class_state",
    "child_env",
]


#: Every provider credential the fallback chain reads, derived from the
#: registry rather than transcribed. ``_provider_chain`` treats a *present* key
#: as dialable, so any test process that must not reach the network has to blank
#: all of these — see :func:`child_env` and ``tests/conftest.py``.
PROVIDER_KEY_ENVS = tuple(
    sorted(cfg["key_env"] for cfg in _OPENAI_COMPATIBLE_PROVIDERS.values())
)

#: The per-provider model pin, derived from the same registry. ``openrouter``
#: has no ``model_env`` (it rotates models itself), so this is shorter than
#: :data:`PROVIDER_KEY_ENVS` by construction rather than by omission. Blanking
#: one is safe: the read site is
#: ``os.getenv(model_env, "").strip() or cfg["default_model"]``, so an empty
#: value restores the registry default instead of emptying the model id.
PROVIDER_MODEL_ENVS = tuple(
    sorted(
        cfg["model_env"]
        for cfg in _OPENAI_COMPATIBLE_PROVIDERS.values()
        if cfg.get("model_env")
    )
)

#: Secrets that authenticate to something OUTSIDE this machine. Blanked.
#:
#: This list used to be ``PROVIDER_KEY_ENVS + ("GITHUB_TOKEN",)`` with a
#: comment calling GITHUB_TOKEN "the non-LLM credential that also rides in on
#: ``.env``". There were four, and the omissions cost real money and real
#: noise: the harness filed 20 real GitHub issues, then wrote real rows to the
#: production database, then spent real provider credit -- three incidents,
#: one shape, each closed by adding one more name by hand.
#:
#: ``TURSO_*`` were transcribed as literals in ``tests/conftest.py`` AND
#: ``tools/bug_hunt.py``, which is the duplication this module exists to end,
#: so they live here now and both call sites read them.
OUTBOUND_CREDENTIAL_ENVS = PROVIDER_KEY_ENVS + (
    "GITHUB_TOKEN",
    "TURSO_DATABASE_URL",
    "TURSO_AUTH_TOKEN",
    "HOV_ANALYTICS_WEBHOOK_URL",
    "NEXUS_PASS",
    # Documented in .env.example but absent from _OPENAI_COMPATIBLE_PROVIDERS,
    # so PROVIDER_KEY_ENVS does not derive them. Found by the guard below on
    # its first run -- which is the guard earning its keep, and the reason it
    # reads the env files rather than trusting this tuple.
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    # tools/inquisitor/email_reporter.py mails the findings report through a
    # real SMTP server. These four were read by that module and DECLARED
    # NOWHERE, so no scan that starts from the env files could ever have seen
    # them; test_every_env_name_the_code_reads_is_declared found them by
    # starting from the code instead. REPORT_EMAIL is the gate (unset =>
    # send_report returns before touching SMTP), FROM_EMAIL/HOST address
    # something off this box, and PASSWORD/USER authenticate to it.
    "INQUISITOR_FROM_EMAIL",
    "INQUISITOR_REPORT_EMAIL",
    "INQUISITOR_SMTP_HOST",
    "INQUISITOR_SMTP_PASSWORD",
    "INQUISITOR_SMTP_USER",
)

#: Secrets that are local-only, and why each is safe to leave alone.
#:
#: Not blanked, because blanking them breaks the thing under test rather than
#: protecting anything: neither authenticates to anything off this machine.
#: They are listed rather than merely omitted so that
#: :func:`classify_env_name` has somewhere to put them -- an unclassified
#: secret must fail, and "we thought about this one" has to be expressible.
LOCAL_ONLY_SECRET_ENVS = (
    # Signs session cookies. TestingConfig mints a random one per run.
    "SECRET_KEY",
    # Encrypts saved games at rest, in this process, on this disk.
    "ENCRYPTION_KEY",
)

#: Backwards-compatible alias. Both conftests and ``tools/bug_hunt.py`` blank
#: this set.
CREDENTIAL_ENVS = OUTBOUND_CREDENTIAL_ENVS


#: What a variable name can look like, and the ONLY filter
#: :func:`declared_env_names` applies. Deliberately the POSIX shell identifier
#: shape rather than anything about capitalisation or wording: ``sh`` and
#: ``python-dotenv`` both accept lowercase names, and so do the libraries that
#: read them (see the docstring below on ``https_proxy``). Its whole job is to
#: tell a declaration from a sentence that happens to contain an "=".
_ENV_NAME_SHAPE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def declared_env_names(*paths):
    """Every variable name declared in the given env files. No filtering.

    Reads the NAMES only -- never a value -- so this is safe to call on a real
    ``.env``. Commented-out declarations count: ``.env.example`` ships most of
    its entries commented, and a variable is no less a credential for being
    optional.

    This used to filter to "secret-shaped" names through a regex of
    credential-ish word stems (``KEY``, ``TOKEN``, ``SECRET``, ``PASS``,
    ``WEBHOOK``, ...). That regex is gone, and its removal is the point. It was
    the same hand-maintained list as the ones that caused three incidents,
    written one level up: a credential named ``*_DSN``, ``*_BASE_URL``,
    ``*_ENDPOINT`` or ``*_HOOK`` did not match it, so it was never *shown* to
    the classifier and passed as silently as if the classifier had approved it.
    ``OLLAMA_BASE_URL`` -- the one variable in this file that can put a unit
    test on the network by itself -- matched none of those stems and was
    covered only because somebody had hand-listed it elsewhere.

    Removing it left a smaller filter of the same kind behind, which is worth
    naming rather than glossing: the shape test below also required
    ``name.isupper()``. Convention is not a rule -- ``requests`` resolves
    proxies through ``urllib.request.getproxies()``, which reads the LOWERCASE
    ``https_proxy``/``http_proxy``/``all_proxy``, so a declared
    ``https_proxy=http://user:pass@corp/`` is a credential-bearing URL that
    routes ``feedback.py``'s GitHub POST and every LLM call through a third
    party -- and it was dropped here, before the classifier ever saw it. The
    case requirement is gone with the stems.

    What remains is a shape test that decides nothing about *what a credential
    is called*: it only asks whether the text left of the ``=`` is a variable
    name at all, so that prose in a comment ("...see notes.md, where x=y") does
    not arrive as a declaration. Every name that survives it must be
    classified, and the non-credentials are the ones that need a written reason
    (:data:`NON_SECRET_ENVS`).
    """
    names = set()
    for path in paths:
        try:
            text = Path(path).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            stripped = line.lstrip("# ").strip()
            name, sep, _value = stripped.partition("=")
            if not sep:
                continue
            name = name.strip()
            if not _ENV_NAME_SHAPE.match(name):
                continue
            names.add(name)
    return names


def _env_name_argument(node):
    """The AST node naming the variable, if ``node`` is a direct env read.

    Covers the four spellings this repo actually uses: ``os.environ[X]``,
    ``os.environ.get/pop/setdefault(X, ...)`` and ``os.getenv(X, ...)``.
    """
    if (
        isinstance(node, ast.Subscript)
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "environ"
    ):
        return node.slice
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.args
    ):
        if node.func.attr == "getenv":
            return node.args[0]
        if (
            node.func.attr in ("get", "pop", "setdefault")
            and isinstance(node.func.value, ast.Attribute)
            and node.func.value.attr == "environ"
        ):
            return node.args[0]
    return None


def _env_reader_functions(trees):
    """``{function name: {argument index that names a variable}}``.

    DERIVED from what the functions do, not from a list of helper names. A
    function qualifies if one of its own parameters reaches an environment read
    -- directly, or through another function that already qualifies. The loop
    runs to a fixed point because the indirection is layered in this repo:
    ``limiter_from_env`` never touches ``os.environ`` itself, it forwards to
    ``_parse_env_limit``, which does.

    Without this, a scan of literal ``os.environ[...]`` arguments alone reports
    that ``FEEDBACK_RATE_LIMIT_PER_HOUR`` is never read, and misses
    ``INQUISITOR_SMTP_PASSWORD`` entirely -- both of which reach the
    environment through exactly one such helper.
    """
    functions = [
        node
        for tree in trees
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    readers = {}
    changed = True
    while changed:
        changed = False
        for fn in functions:
            params = [
                a.arg
                for a in fn.args.posonlyargs + fn.args.args + fn.args.kwonlyargs
            ]
            found = set()
            for node in ast.walk(fn):
                arg = _env_name_argument(node)
                if arg is None and isinstance(node, ast.Call):
                    called = (
                        node.func.attr
                        if isinstance(node.func, ast.Attribute)
                        else getattr(node.func, "id", None)
                    )
                    for index in readers.get(called, ()):
                        if index < len(node.args):
                            arg = node.args[index]
                            break
                if isinstance(arg, ast.Name) and arg.id in params:
                    found.add(params.index(arg.id))
            if found - readers.get(fn.name, set()):
                readers.setdefault(fn.name, set()).update(found)
                changed = True
    return readers


def _module_level_string_constants(tree):
    """``{NAME: "value"}`` for module-level ``NAME = "literal"`` assignments.

    ``src/save_format.py`` reads ``os.environ.get(SAVE_V2_ENV_VAR, ...)``. One
    hop of constant folding is the difference between seeing ``HOV_SAVE_V2``
    and seeing nothing.
    """
    out = {}
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    out[target.id] = node.value.value
    return out


def env_names_read_under(*roots):
    """``{variable name: {file, ...}}`` for every env name the code READS.

    The mirror of :func:`declared_env_names`, and the direction that catches
    what an env-file scan structurally cannot: a variable the code reads but
    nobody wrote down is invisible to every list, every classifier and every
    blanking sweep in this repo, because all of them start from the files.
    ``INQUISITOR_SMTP_PASSWORD`` was exactly that.

    Resolves one hop of constant indirection (``os.getenv(SAVE_V2_ENV_VAR)``)
    and the derived helper closure from :func:`_env_reader_functions`.

    NOT resolved, deliberately: a name that is computed rather than written
    (``os.getenv(prefix + suffix)``) or read through a helper whose argument
    comes from a variable. Those exist -- ``GenericLLMClient._first_env`` takes
    a tuple built by its callers -- and the answer for them is the OTHER
    direction: they are swept by suffix (:func:`llm_gate_envs`) and asserted
    from the env files by ``tests/test_credential_blanking.py``. Neither scan
    is complete alone; between them a name has to be missing from BOTH the
    files and every literal read site to stay unclassified.
    """
    paths = [
        path
        for root in roots
        for path in sorted(Path(root).rglob("*.py"))
        if "__pycache__" not in path.parts
    ]
    trees = {}
    for path in paths:
        try:
            trees[path] = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except (OSError, SyntaxError):
            continue
    readers = _env_reader_functions(trees.values())

    found = {}
    for path, tree in trees.items():
        constants = _module_level_string_constants(tree)

        def literal(node):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                return node.value
            if isinstance(node, ast.Name):
                return constants.get(node.id)
            return None

        for node in ast.walk(tree):
            arg = _env_name_argument(node)
            if arg is None and isinstance(node, ast.Call):
                called = (
                    node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else getattr(node.func, "id", None)
                )
                for index in readers.get(called, ()):
                    if index < len(node.args):
                        arg = node.args[index]
                        break
            name = literal(arg) if arg is not None else None
            if name and _ENV_NAME_SHAPE.match(name):
                found.setdefault(name, set()).add(path.as_posix())
    return found


# ---------------------------------------------------------------------------
# The LLM environment vocabulary, owned here so both conftests derive from it
# ---------------------------------------------------------------------------
# tests/conftest.py BLANKS this set process-wide; tests/integration/conftest.py
# RESTORES it for the opt-in live suite. Those two halves have to describe the
# same set of names or the live suite runs a feature adapter that the default
# suite disabled and nobody re-enabled -- which is precisely how
# test_tactical_advisor_live.py came to skip all 21 of its tests while
# reporting success. Neither conftest can import the other (no
# ``tests/__init__.py``, so pytest imports the root conftest under the bare
# name ``conftest``), so the vocabulary lives in this plain module, which both
# already import.

#: The naming convention every feature LLM adapter's gate trio obeys:
#: ``<FEATURE>_LLM_ENABLED`` / ``_PROVIDER`` / ``_MODEL``, resolved by
#: ``GenericLLMClient._first_env`` with "first non-empty wins". Swept by suffix
#: rather than from a list of adapter classes so an adapter added tomorrow --
#: or one whose module is mid-refactor and does not currently import -- is
#: covered without anyone remembering to add it.
LLM_GATE_SUFFIXES = ("_LLM_ENABLED", "_LLM_PROVIDER", "_LLM_MODEL")


def llm_gate_envs(names: Iterable[str]) -> Tuple[str, ...]:
    """The gate-trio variables among ``names``, sorted and de-duplicated.

    ``names`` is normally ``os.environ`` (what is actually set in this process)
    or the keys of ``dotenv_values()`` (what ``.env`` can contribute). Both
    conftests call this rather than spelling a tuple, so the blanked set and
    the restored set cannot drift apart.
    """
    return tuple(sorted({n for n in names if n.endswith(LLM_GATE_SUFFIXES)}))


#: The LLM settings that do NOT follow the gate-trio convention, so nothing
#: derives them. Each is here because leaving it live changes what the default
#: suite tests:
#:
#: * ``OLLAMA_BASE_URL`` -- the one that actually reaches the network.
#:   ``_provider_chain`` appends ollama whenever it is set and
#:   ``_provider_available("ollama")`` reads nothing else, so a developer with
#:   a local Ollama gets unit tests dialling it. This is the "host" the
#:   blanking comment in tests/conftest.py always claimed to cover.
#: * ``NPC_CHAT_LLM_TIMEOUT`` -- feeds ``_turn_deadline``. A large ``.env``
#:   value spends the whole per-round budget on attempt 1, so the QC retry and
#:   the state-guard revision call never run and their tests pass for the
#:   wrong reason. Blanking is safe: ``_round_timeout`` wraps the ``float()``
#:   in ``except (TypeError, ValueError)``.
#: * ``NPC_CHAT_LLM_FALLBACK`` -- three-state. ``_remote_fallback_setting``
#:   reads a blank as "unset", which is the default this suite wants.
#: * ``LLM_LOG_RAW_BODIES`` -- transcribes whole provider bodies to the log.
#: * ``OPENROUTER_SITE`` / ``_SITE_TITLE`` -- ranking headers; both read as
#:   ``os.getenv(...).strip() or None``, so blank is exactly absent.
#: * :data:`PROVIDER_MODEL_ENVS` -- the "model" half of the same claim.
#:
#: Deliberately ABSENT: the five ``NPC_CHAT_TEMP_*`` overrides. They are read
#: as a bare ``float(os.getenv("NPC_CHAT_TEMP_NPC", "0.65"))`` with no
#: ``try``/``except`` (ai/llm_client.py, five call sites), and ``float("")``
#: raises -- so blanking them would turn a developer's ``.env`` override into a
#: crash rather than neutralising it, and pinning them to their defaults here
#: would be a sixth copy of five constants that live in the engine. They also
#: cannot reach the network on their own: they only set ``temperature`` on a
#: call the blanked chain never dials. Fix the read sites (give them
#: ``_round_timeout``'s ``except``) before adding them here.
LLM_SETTING_ENVS = (
    "LLM_LOG_RAW_BODIES",
    "NPC_CHAT_LLM_FALLBACK",
    "NPC_CHAT_LLM_TIMEOUT",
    "OLLAMA_BASE_URL",
    "OPENROUTER_SITE",
    "OPENROUTER_SITE_TITLE",
) + PROVIDER_MODEL_ENVS


#: Applied AFTER :func:`blank_outbound_env`'s sweep, because the sweep would
#: otherwise blank them. Blank is not the same as off for these two:
#:
#: * ``MYNX_LLM_PROVIDER`` — "none" is ``PROVIDER_DISABLED``. Empty falls
#:   through to ``DEFAULT_PROVIDER`` ("ollama"), leaving a local Ollama to be
#:   probed.
#: * ``MYNX_FALLBACK_DELAY`` — read through ``float()`` with a default, so
#:   pinning 0 is what removes the sleep rather than merely neutralising it.
#:
#: The two ``*_ENABLED`` pins are belt to the sweep's braces: the sweep already
#: blanks every ``_LLM_ENABLED`` it finds set, and an unset one reads as off.
HARNESS_ENV_PINS = {
    "MYNX_LLM_ENABLED": "0",
    "MYNX_LLM_PROVIDER": "none",
    "NPC_CHAT_LLM_ENABLED": "0",
    "MYNX_FALLBACK_DELAY": "0",
}


def blank_outbound_env(**pins):
    """Make this process unable to reach a provider, a database or a mailbox.

    THE one sweep. Every ``tools/`` entry point whose import graph reaches a
    module that loads ``.env`` calls this before it imports the engine, and
    ``tests/test_credential_blanking.py`` proves that per tool, by running the
    import with fake credentials set and checking they come back blank.

    It is three parts because the vocabulary is three shapes, and each part is
    DERIVED:

    * :data:`CREDENTIAL_ENVS` — everything that authenticates to, or addresses,
      something off this machine.
    * :func:`llm_gate_envs` over the LIVE ``os.environ`` — the
      ``<FEATURE>_LLM_ENABLED/_PROVIDER/_MODEL`` trio, swept by suffix so an
      adapter added tomorrow is covered without anyone editing a list.
    * :data:`LLM_SETTING_ENVS` — the LLM settings that do not follow that
      convention, ``OLLAMA_BASE_URL`` chief among them.

    Any one of the three alone has been enough to spend real money: the
    harness has filed 20 real GitHub issues, written real rows to the
    production Turso database, and shipped harness-authored dialogue to a paid
    provider, each on a different one of these parts being the one that was
    missing.

    ASSIGNED "", never ``del``/``.pop()``. ``load_project_env`` runs
    ``load_dotenv(override=False)``, which skips keys already *present*
    regardless of value but refills ones that are *absent* — so a deleted key
    comes straight back from ``.env`` at the next import that loads it. This is
    also why calling this AFTER ``.env`` has been read is fine, and why every
    caller can simply put it at the top of the file.

    ``pins`` override :data:`HARNESS_ENV_PINS` for the rare caller that needs a
    different value; passing ``None`` for a key drops that pin entirely.
    Returns the sorted names it blanked.
    """
    import os

    blanked = tuple(
        sorted(set(CREDENTIAL_ENVS + llm_gate_envs(os.environ) + LLM_SETTING_ENVS))
    )
    for name in blanked:
        os.environ[name] = ""
    merged = dict(HARNESS_ENV_PINS)
    merged.update(pins)
    for name, value in merged.items():
        if value is not None:
            os.environ[name] = value
    return blanked


#: Declared variables that are NOT credentials, and why each one is not.
#:
#: The third and largest class, and the one that makes the inversion in
#: :func:`declared_env_names` work. With no "does this look like a secret?"
#: filter in front of the classifier, every declared name arrives here, and a
#: name nobody has thought about fails the suite instead of passing it.
#:
#: Grouped by shared reason rather than repeated per name: five sampling
#: temperatures do not have five different justifications, and writing the same
#: sentence five times is how a family drifts into four justifications and one
#: stale one. A name whose reason is genuinely its own gets its own group.
#:
#: What does NOT belong here: anything that could authenticate to, or address,
#: something off this machine. Those go in :data:`OUTBOUND_CREDENTIAL_ENVS`
#: even when they are not obviously a credential -- ``HOV_ANALYTICS_WEBHOOK_URL``
#: is a URL whose *path* is the credential, and a hostname alone is enough to
#: put a test on the network.
_NON_SECRET_GROUPS = (
    (
        "Where the process listens. A bind target, not a credential.",
        ("HOST", "PORT"),
    ),
    (
        "Selects a config class. wsgi.py refuses to boot on anything but "
        "'production', so this cannot quietly weaken a deployment.",
        ("FLASK_ENV",),
    ),
    (
        "Path to a gameplay .ini. Every conftest already overrides it so a "
        "developer's manual-QA config cannot change what the suite tests.",
        ("CONFIG_FILE",),
    ),
    (
        "Opt-in switch for binding the dev server off localhost. Security "
        "relevant, but a boolean rather than a secret -- and blanking it is "
        "the safe direction anyway.",
        ("ALLOW_REMOTE_DEV_SERVER",),
    ),
    (
        "How many X-Forwarded-For hops rate_limiter.client_ip() trusts. An "
        "integer describing this deployment's proxy depth.",
        ("TRUSTED_PROXY_COUNT",),
    ),
    (
        "Logging destination and verbosity. What lands IN the log file can be "
        "sensitive -- which is why app.py installs _RedactSecretsFilter and "
        "confines the path to logs/ -- but neither name nor value is.",
        ("LOG_FILE", "LOG_LEVEL"),
    ),
    (
        "Feature flags. Booleans selecting which code path runs.",
        ("COMBAT_SOCKET_STREAMING", "HOV_SAVE_V2", "HOV_STRICT_UNPICKLE"),
    ),
    (
        "Gates the /api/test/session login-bypass route, so it is a door "
        "rather than a key -- and one this suite has to leave open, since the "
        "TestingConfig every API test builds sets it. Blanking it here would "
        "disable the harness, not protect anything; what keeps it shut in "
        "production is that ProductionConfig never sets it.",
        ("TESTING",),
    ),
    (
        "Throttle thresholds, read as integers by limiter_from_env. Worth "
        "leaving live: a test that needs a different ceiling sets it itself, "
        "and blanking them would exercise the fallback rather than the "
        "configured path.",
        (
            "BROWSER_LOG_RATE_LIMIT_PER_MINUTE",
            "FEEDBACK_RATE_LIMIT_PER_HOUR",
            "LOGIN_IP_RATE_LIMIT_PER_15_MIN",
            "LOGIN_RATE_LIMIT_PER_15_MIN",
            "NPC_CHAT_IP_RATE_LIMIT_PER_MINUTE",
            "NPC_CHAT_RATE_LIMIT_PER_MINUTE",
            "REGISTER_RATE_LIMIT_PER_HOUR",
        ),
    ),
    (
        "Schedule and content of the analytics digest. The sink it posts to "
        "is HOV_ANALYTICS_WEBHOOK_URL, which is outbound and blanked; without "
        "that, these describe a report nothing sends.",
        (
            "HOV_ANALYTICS_ALERT_INTERVAL_HOURS",
            "HOV_ANALYTICS_ALERT_THRESHOLD",
            "HOV_ANALYTICS_INTERVAL_HOURS",
            "HOV_ANALYTICS_SECTIONS",
        ),
    ),
    (
        "Numeric tuning for the provider digest and the Mynx fallback.",
        ("LLM_SATURATION_CUTOFF", "MYNX_FALLBACK_DELAY"),
    ),
    (
        "Extra logging for the Mynx adapter. A verbosity switch; the payload "
        "bound it does not control lives in LLM_LOG_RAW_BODIES, which is in "
        "LLM_SETTING_ENVS and blanked.",
        ("MYNX_LLM_DEBUG",),
    ),
    (
        "The half of the Inquisitor's SMTP settings that cannot reach anything "
        "on their own. A port with no host addresses nothing, and the TLS "
        "switch is read as `!= \"0\"`, so a blank keeps STARTTLS on -- the "
        "safe direction. Blanking the port would be actively worse: it is read "
        "through int(), which raises on an empty string. The four that DO "
        "reach out are in OUTBOUND_CREDENTIAL_ENVS.",
        ("INQUISITOR_SMTP_PORT", "INQUISITOR_SMTP_TLS"),
    ),
    (
        "Sampling temperatures. Deliberately NOT blanked -- read as a bare "
        "float(os.getenv(...)) with no except, so a blank value raises rather "
        "than neutralising. See the note at the foot of LLM_SETTING_ENVS.",
        (
            "NPC_CHAT_TEMP_GUARD",
            "NPC_CHAT_TEMP_NPC",
            "NPC_CHAT_TEMP_OPTIONS",
            "NPC_CHAT_TEMP_PERSONALITY",
            "NPC_CHAT_TEMP_TURN",
        ),
    ),
)

#: ``{name: reason}``, flattened from :data:`_NON_SECRET_GROUPS`.
NON_SECRET_ENVS = {
    name: reason for reason, names in _NON_SECRET_GROUPS for name in names
}


def classify_env_name(name):
    """Which class ``name`` falls in, or ``None`` if nobody has said.

    Three of the four answers are derived rather than listed, which is the
    whole point: a fifth provider registered in ``_OPENAI_COMPATIBLE_PROVIDERS``
    or a sixth feature adapter following the ``<FEATURE>_LLM_*`` convention is
    classified the moment it exists, without anyone editing this file.
    """
    if name in OUTBOUND_CREDENTIAL_ENVS:
        return "outbound"
    if name in LOCAL_ONLY_SECRET_ENVS:
        return "local-only"
    if name in LLM_SETTING_ENVS or name.endswith(LLM_GATE_SUFFIXES):
        return "llm-setting"
    if name in NON_SECRET_ENVS:
        return "non-secret"
    return None


class Resp:
    """A ``requests``-shaped response double for the chat transports.

    One class rather than the previous ``_Resp``/``_HeaderResp`` pair: the
    split bought nothing (``headers`` defaults to empty, which is what the
    header-less call sites wanted anyway) and cost a positional-argument
    collision between two files. ``status`` stays first because that is the
    ordering the larger set of call sites already used.
    """

    def __init__(
        self,
        status: int = 200,
        payload: Optional[Dict[str, Any]] = None,
        text: str = "",
        headers: Optional[Dict[str, str]] = None,
        json_error: Optional[BaseException] = None,
    ) -> None:
        self.status_code = status
        self._payload = payload or {
            "choices": [{"message": {"content": '{"npc_text": "Fine."}'}}]
        }
        self.text = text
        self.headers = headers or {}
        self._json_error = json_error

    def json(self) -> Dict[str, Any]:
        """The decoded body, or ``json_error`` raised.

        A real ``requests`` response raises out of ``.json()`` whenever the
        body is not JSON -- an HTML error page from a proxy, a truncated
        stream, an empty 200. Two production branches exist for exactly that
        and neither was reachable from this class until ``json_error`` was
        added: ``_ollama_chat``'s ``except Exception: data = None``, which then
        falls back to ``r.text``, and ``NpcChatLLMAdapter._call_llm``'s chain
        safety net, which must move to the next provider rather than let one
        malformed body abort the round. Both were covered only by ad-hoc
        ``MagicMock(json=Mock(side_effect=...))`` in a single file.

        Pass any exception instance: ``Resp(json_error=ValueError("no json"))``.
        ``requests`` raises its own ``JSONDecodeError`` in real life, but both
        call sites catch bare ``Exception``, so the type is not part of the
        contract under test and pinning it here would only couple the double to
        the ``requests`` version.
        """
        if self._json_error is not None:
            raise self._json_error
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError("HTTP %s" % self.status_code)


#: Any ``GenericLLMClient`` subclass, so :func:`_build` returns the class it
#: was handed rather than the base class -- which is the whole reason the two
#: public factories below have distinct return types.
_ClientT = TypeVar("_ClientT", bound=GenericLLMClient)


def _build(
    cls: Type[_ClientT],
    provider: Optional[str],
    model: Optional[str],
    api_key: Optional[str],
    overrides: Mapping[str, Any],
) -> _ClientT:
    obj = cls.__new__(cls)
    obj.enabled = True
    if provider is not None:
        obj.provider = provider
        obj.model = model
    if api_key is not None:
        obj._openrouter_api_key = api_key
        obj._openrouter_site = ""
        obj._openrouter_site_title = ""
    for key, value in overrides.items():
        setattr(obj, key, value)
    return obj


def make_chat_adapter(
    provider: Optional[str] = "openrouter",
    model: Optional[str] = "m",
    api_key: Optional[str] = "or-key",
    **overrides: Any,
) -> NpcChatLLMAdapter:
    """An ``NpcChatLLMAdapter`` built without running ``__init__``.

    ``__init__`` reads the environment and can start provider discovery, so
    every test that wants to drive one method in isolation goes through
    ``__new__`` and sets attributes by hand. This is that, once.

    Args:
        provider: value for ``.provider``. ``None`` leaves ``.provider`` and
            ``.model`` unset entirely — the shape used by tests that replace
            ``_call_llm`` outright and never reach provider selection.
        model: value for ``.model``; ignored when ``provider`` is ``None``.
        api_key: value for ``._openrouter_api_key``, which is also what arms
            the OpenRouter leg of the fallback chain. Pass ``None`` to leave the
            three OpenRouter attributes unset, which is what a test asserting on
            an *unconfigured* chain needs.
        **overrides: any further attribute — ``base_url`` for ollama,
            ``_call_llm`` for a scripted transport, ``_available``, and so on.
    """
    return _build(NpcChatLLMAdapter, provider, model, api_key, overrides)


def make_generic_client(
    provider: Optional[str] = "openrouter",
    model: Optional[str] = "m",
    api_key: Optional[str] = "k",
    **overrides: Any,
) -> GenericLLMClient:
    """:func:`make_chat_adapter` for the ``GenericLLMClient`` base class.

    Separate from the adapter factory because the two classes are tested for
    different things: the base class owns the transports, the subclass owns the
    chat payload. A single factory returning either would make every call site
    state which one it meant anyway.
    """
    return _build(GenericLLMClient, provider, model, api_key, overrides)


def _refuse_to_dial(*args, **kwargs):
    """Stand-in for ``requests.post``/``get`` while a unit test is running.

    THE HOLE THIS CLOSES. ``tests/conftest.py`` and
    :func:`isolate_llm_class_state` blank every credential in the
    ENVIRONMENT. But :func:`_build` constructs its clients with ``__new__``
    and assigns ``obj._openrouter_api_key = "or-key"`` straight onto the
    instance, where no environment control can reach it. So a test that drives
    ``_try_http``, ``_openrouter_attempt`` or ``_openrouter_chat_single``
    without patching the transport makes a REAL HTTPS POST to openrouter.ai,
    carrying the fixture's prompt text in the body.

    Every test in the suite currently does patch. That is precisely the
    problem: "the author remembered" is the only control, and
    ``tests/conftest.py`` names that as unacceptable in its own docstring --
    having watched it fail four times over, with 20 real GitHub issues filed,
    real rows written to the production Turso database, real provider credit
    spent, and an SMTP password reachable from ``tools/inquisitor.py``.

    Installed with ``monkeypatch.setattr`` onto the real ``requests`` module,
    which is deliberate and is what makes it compatible rather than
    obstructive: a test doing ``patch("requests.post", ...)`` or
    ``patch.object(llm.requests, "post", ...)`` replaces this for its own
    duration, exactly as before. Only an UNPATCHED call reaches here.
    """
    raise AssertionError(
        "a unit test tried to make a real HTTP request from ai.llm_client. "
        "Patch the transport in this test (`patch(\"requests.post\", ...)` "
        "is the idiom used elsewhere in this suite). The fixture credentials "
        "are fake, but the URL is not: unpatched, this dials a live provider "
        "with the prompt text in the request body."
    )


@pytest.fixture(autouse=True)
def isolate_llm_class_state(monkeypatch, tmp_path):
    """Reset the process-wide LLM class state around every test in a module.

    ``GenericLLMClient`` keeps discovery results, benched models, provider usage
    counters and the usage window on the *class*, so one test's failed model or
    spent quota is visible to every test that runs after it — including in
    another file, since the class outlives the module.

    Opt a module in with a module-level alias::

        from tests.llm_doubles import isolate_llm_class_state  # noqa: F401

    The alias makes the fixture module-scoped in effect (autouse applies only
    where the name is visible), which is why this is not in ``conftest.py``:
    the whole suite does not need a ``reset_class_state`` per test.

    This replaced four spellings of the same idea — two near-identical
    ``_reset_llm_class_state`` copies, one ``_isolate_class_state``, and ten
    hand-rolled ``setup_method``/``teardown_method`` pairs. The pairs are the
    worse form for exactly the reason seen in ``test_llm_provider_digest.py``:
    a class that adds one more piece of state to reset updates its own pair and
    nobody else's, so the classes drift apart silently. A fixture cannot drift,
    because there is only one.

    The disk model cache is redirected into ``tmp_path`` for the same reason —
    it is real, shared, and survives the process. The environment is pinned to a
    clean, provider-less baseline that individual tests override as needed; the
    credential names come from :data:`PROVIDER_KEY_ENVS`, so a newly registered
    provider is neutralised here without anyone remembering to add it.

    Those names are SET EMPTY rather than deleted, which is not a style choice.
    ``load_dotenv`` runs with ``override=False``, so it refills a key that is
    *absent* and leaves an assigned empty one alone — and ``load_project_env()``
    runs again at import of several ``src.api`` modules. A ``delenv`` here
    therefore held only until the test under it imported something from the API,
    at which point the repo's real ``GROQ_API_KEY``/``CEREBRAS_API_KEY``/
    ``OPENROUTER_API_KEY`` came straight back from ``.env`` and armed the
    fallback chain inside a unit test. Empty is what every consumer reads as
    unset anyway: ``_first_env()`` strips and skips it, ``_provider_chain``
    tests ``os.getenv(key_env, "").strip()``, and the enabled gate compares
    against ``("1", "true", "True")``. Same trap as the GITHUB_TOKEN incident,
    and the same fix as :func:`child_env` and ``tests/conftest.py``.
    """
    GenericLLMClient.reset_class_state()
    GenericLLMClient._nightly_refresh_started = False
    monkeypatch.setattr(llm, "_MODEL_CACHE_FILE", str(tmp_path / ".model_cache.json"))
    monkeypatch.setenv("MYNX_LLM_ENABLED", "0")
    monkeypatch.setenv("MYNX_LLM_PROVIDER", "none")
    for key in PROVIDER_KEY_ENVS + (
        "MYNX_LLM_MODEL",
        "NPC_CHAT_LLM_ENABLED",
        "NPC_CHAT_LLM_PROVIDER",
        "NPC_CHAT_LLM_MODEL",
    ):
        monkeypatch.setenv(key, "")
    # The STRUCTURAL half of the same job. Blanking the environment cannot
    # reach a credential written straight onto an instance by `_build`, so the
    # transport refuses instead. See :func:`_refuse_to_dial` -- a test's own
    # patch still wins, because this is set on the real module.
    if llm.requests is not None:
        for verb in ("post", "get", "put", "delete", "head", "request"):
            if hasattr(llm.requests, verb):
                monkeypatch.setattr(llm.requests, verb, _refuse_to_dial)
    yield
    GenericLLMClient.reset_class_state()
    GenericLLMClient._nightly_refresh_started = False


def child_env(**overrides: str) -> Dict[str, str]:
    """A subprocess environment that inherits PATH etc. but no live credentials.

    ``os.environ.copy()`` alone hands the child everything ``python-dotenv``
    loaded from the repo's real ``.env`` — live provider API keys included —
    and none of ``tests/conftest.py``'s blanking, so a child that imports the
    API can make real paid LLM calls.

    The blanked keys are ASSIGNED an empty string rather than popped: dotenv
    runs with ``override=False``, which only skips keys already *present*, so a
    popped key is silently refilled from ``.env`` the moment the child imports
    anything that calls ``load_dotenv()``. (Same trap as the GITHUB_TOKEN
    incident.)
    """
    import os

    env = os.environ.copy()
    for key in CREDENTIAL_ENVS:
        env[key] = ""
    env["NPC_CHAT_LLM_ENABLED"] = "0"
    env["LOG_LEVEL"] = "WARNING"
    env.update(overrides)
    return env
