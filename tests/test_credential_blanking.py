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
"""

import os

import pytest

from tests.llm_doubles import (
    LOCAL_ONLY_SECRET_ENVS,
    NON_SECRET_ENVS,
    OUTBOUND_CREDENTIAL_ENVS,
    classify_env_name,
    declared_env_names,
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


class TestTheHarnessBlanksTheSameSet:
    """``tools/bug_hunt.py`` must read the shared vocabulary, not restate it.

    The Turso pair used to be spelled as a literal tuple in that file AND in
    ``tests/conftest.py`` -- the duplication ``llm_doubles`` exists to end,
    reintroduced by the fix for the second incident.
    """

    def test_bug_hunt_imports_the_shared_vocabulary(self):
        from pathlib import Path

        source = Path("tools/bug_hunt.py").read_text(encoding="utf-8")
        assert "CREDENTIAL_ENVS" in source, (
            "tools/bug_hunt.py should blank the shared credential set rather "
            "than a list of its own"
        )

    def test_bug_hunt_does_not_hand_list_credentials(self):
        """A literal credential name in that file is a list starting again."""
        from pathlib import Path

        source = Path("tools/bug_hunt.py").read_text(encoding="utf-8")
        code = "\n".join(
            line for line in source.splitlines() if not line.strip().startswith("#")
        )
        restated = sorted(
            name
            for name in OUTBOUND_CREDENTIAL_ENVS
            if '"%s"' % name in code or "'%s'" % name in code
        )
        assert restated == [], (
            "tools/bug_hunt.py spells these credential names literally: %s. "
            "They are already in OUTBOUND_CREDENTIAL_ENVS, which that file "
            "sweeps -- a second spelling is how TURSO_* came to be maintained "
            "in two places." % ", ".join(restated)
        )
