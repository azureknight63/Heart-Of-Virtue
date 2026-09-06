"""Event-type strings the React client compares against, pinned to the engine.

THE HOLE THIS CLOSES. `frontend/src/utils/eventIds.js` declares

    PASSAGEWAY_TRANSITION_EVENT_TYPE = 'PassagewayTransitionEvent'

and `useWorldInteract.js` uses it to decide whether a passageway confirmation is
in flight — a decision that, got wrong, leaves the player in an unrecoverable
soft-lock. The string is the Python class name, serialized into
`events_triggered[].type` by `EventSerializer.serialize_with_input`.

Nothing checked it. All three frontend consumers import the same JS constant, so
every fixture agreed with the code BY CONSTRUCTION — rename the Python class and
the whole suite stays green while the feature silently stops working. That is
the "a mock cannot catch a mock agreeing with itself" failure
`tests/test_wire_field_contract.py`'s own header was written about, and the
constant was extracted into `eventIds.js` precisely so a rename would reach
every call site. It reaches every JS call site. It does not reach the engine.

WHY THIS PINS THE SERIALIZER AND NOT THE CLASS NAME. `type(event).__name__` is
what the serializer happens to use today, so asserting the class is named
`PassagewayTransitionEvent` would pass even if the serializer started emitting a
`kind` field, or a snake_case name, or a registry id. The wire is the contract;
this drives the real serializer over a real event instance and reads the field
the client actually compares.
"""

import io
import re
from pathlib import Path

import pytest

from src.api.serializers.event_serializer import EventSerializer
from src.events import PassagewayTransitionEvent

_EVENT_IDS_JS = Path("frontend/src/utils/eventIds.js")


class _StubTile:
    """The least tile the event constructor and serializer will accept."""

    x = 0
    y = 0
    events_here: list = []


def _js_constant(name):
    """The value of a `export const NAME = '...'` in eventIds.js.

    Parsed rather than duplicated: a copy here would be one more spelling to
    drift, which is the defect this module exists to stop.
    """
    source = io.open(_EVENT_IDS_JS, encoding="utf-8").read()
    match = re.search(
        r"export\s+const\s+" + re.escape(name) + r"\s*=\s*['\"]([^'\"]+)['\"]",
        source,
    )
    assert match, (
        "%s declares no `export const %s = '...'` — if it was renamed, the "
        "frontend consumers and this pin both need repointing" % (_EVENT_IDS_JS, name)
    )
    return match.group(1)


class TestThePassagewayTransitionTypeIsTheOneTheEngineSends:
    def test_the_js_file_is_parseable_and_declares_the_constant(self):
        """Non-vacuity. A parse that finds nothing agrees with any engine."""
        value = _js_constant("PASSAGEWAY_TRANSITION_EVENT_TYPE")
        assert value and len(value) > 3, value

    def test_the_serializer_emits_exactly_that_string(self):
        event = PassagewayTransitionEvent(
            name="Passage_Test",
            player=None,
            tile=_StubTile(),
            passageway=None,
        )
        emitted = EventSerializer.serialize_with_input(event).get("type")
        expected = _js_constant("PASSAGEWAY_TRANSITION_EVENT_TYPE")
        assert emitted == expected, (
            "the engine puts %r in events_triggered[].type, but "
            "frontend/src/utils/eventIds.js compares against %r.\n\n"
            "useWorldInteract.js uses that comparison to decide whether a "
            "passageway confirmation is in flight; a mismatch leaves the player "
            "in an unrecoverable soft-lock, and no frontend test can see it "
            "because every fixture imports the same JS constant."
            % (emitted, expected)
        )

    def test_the_type_field_is_the_one_the_client_reads(self):
        """Guards the shape, not just the value.

        If the serializer moved the discriminator to another key, the assertion
        above would compare `None` to the constant and fail with a confusing
        message. This says plainly which field the contract is about.
        """
        event = PassagewayTransitionEvent(
            name="Passage_Test",
            player=None,
            tile=_StubTile(),
            passageway=None,
        )
        payload = EventSerializer.serialize_with_input(event)
        assert "type" in payload, sorted(payload)


class TestCombatInitIsDeliberatelyClientMinted:
    """The other constant in that file, and why it is NOT pinned here.

    `COMBAT_INIT_EVENT_ID = 'combat_init'` has no Python source: the client
    mints it, which `eventIds.js` says in as many words. Asserting it against
    the engine would fail for the right value, so what is asserted instead is
    the PREMISE — that the engine really does not emit it. If that changes, this
    fails and somebody has to decide which side owns the string.
    """

    def test_the_engine_does_not_emit_combat_init_as_an_event_type(self):
        value = _js_constant("COMBAT_INIT_EVENT_ID")
        hits = []
        for path in Path("src").rglob("*.py"):
            text = io.open(path, encoding="utf-8", errors="replace").read()
            if "'%s'" % value in text or '"%s"' % value in text:
                hits.append(str(path))
        assert hits == [], (
            "%r now appears in the engine (%s), so it may no longer be "
            "client-minted. Decide which side owns it and pin it accordingly."
            % (value, ", ".join(hits))
        )


@pytest.mark.parametrize(
    "constant", ["PASSAGEWAY_TRANSITION_EVENT_TYPE", "COMBAT_INIT_EVENT_ID"]
)
def test_every_exported_event_constant_is_accounted_for(constant):
    """Both directions: a THIRD constant added to eventIds.js fails here.

    Without this the file could grow a new cross-language string and neither
    class above would notice — the floor on the increment that every guard in
    this repo has had to learn to carry.
    """
    source = io.open(_EVENT_IDS_JS, encoding="utf-8").read()
    exported = set(re.findall(r"export\s+const\s+(\w+)\s*=\s*['\"]", source))
    assert constant in exported
    unaccounted = exported - {
        "PASSAGEWAY_TRANSITION_EVENT_TYPE",
        "COMBAT_INIT_EVENT_ID",
    }
    assert unaccounted == set(), (
        "eventIds.js exports %s, which no test in this module accounts for. "
        "Either pin it against the engine or record why it is client-minted."
        % ", ".join(sorted(unaccounted))
    )
