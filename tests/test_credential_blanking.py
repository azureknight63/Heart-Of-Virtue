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

So the question is asked the other way round. Rather than maintaining a list of
secrets to blank, this reads the NAMES declared in ``.env`` and
``.env.example`` and requires every secret-shaped one to be classified as
either outbound (blanked) or local-only (deliberately not). A new credential
fails until somebody decides which it is. That is the property no version of
the hand-maintained list ever had.

On its first run this guard found ``ANTHROPIC_API_KEY`` and ``OPENAI_API_KEY``
sitting unblanked in ``.env.example`` -- documented as supported, absent from
the provider registry that ``PROVIDER_KEY_ENVS`` derives from, and therefore
invisible to every list that had come before it.
"""

import os

import pytest

from tests.llm_doubles import (
    LOCAL_ONLY_SECRET_ENVS,
    OUTBOUND_CREDENTIAL_ENVS,
    secret_shaped_env_names,
)

#: The committed inventory, plus the developer's real file when it exists.
#: ``.env`` is gitignored, so CI sees only the example -- which is why the
#: example is the one that must stay complete.
ENV_FILES = (".env", ".env.example")


def _declared():
    return secret_shaped_env_names(*ENV_FILES)


class TestEverySecretIsClassified:
    def test_the_scan_finds_something(self):
        """Non-vacuity. A scan that reads nothing agrees with any claim.

        The env files could move, the parser could break on a format change, or
        the pattern could stop matching -- and every assertion below would pass
        silently. That is the failure this whole file exists to prevent, so it
        would be absurd to leave the door open here.
        """
        assert len(_declared()) >= 8, sorted(_declared())

    def test_no_declared_secret_is_unclassified(self):
        classified = set(OUTBOUND_CREDENTIAL_ENVS) | set(LOCAL_ONLY_SECRET_ENVS)
        unclassified = sorted(_declared() - classified)
        assert unclassified == [], (
            "these secret-shaped variables are declared in %s but classified "
            "as neither outbound nor local-only: %s\n\n"
            "Add each to OUTBOUND_CREDENTIAL_ENVS (blanked in tests and in "
            "tools/bug_hunt.py) if it authenticates to anything off this "
            "machine, or to LOCAL_ONLY_SECRET_ENVS with a one-line reason if "
            "it does not. Do not delete it from the scan."
            % (", ".join(ENV_FILES), ", ".join(unclassified))
        )

    def test_the_two_classes_do_not_overlap(self):
        both = set(OUTBOUND_CREDENTIAL_ENVS) & set(LOCAL_ONLY_SECRET_ENVS)
        assert both == set(), sorted(both)


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
