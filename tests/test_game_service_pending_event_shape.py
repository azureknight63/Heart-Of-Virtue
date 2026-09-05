"""One authority for the staged keys, one builder for the pending entry (#524).

Three structural findings in ``game_service.py``, all the same failure mode: a
rule that lives in one place and a copy of it that does not know the rule
exists, so the next fix lands on one of N paths by construction.

1. ``_STAGED_PAYLOAD_KEYS`` was declared as the authority for
   ``output_text``/``segments``/``conversation`` and then not consulted by
   anything: ``_apply_staged_payload`` spelled the three names out, and
   ``trigger_combat_events`` spelled them out a THIRD time inline — a verbatim
   re-implementation the helper never saw and the binding test could not reach.
2. The ``session_data["pending_events"]`` entry shape had four writers. Only
   ``_store_pending_event`` knows the dedupe-by-name rule and the
   ``_carry_staged_payload`` invariant from #515, so that fix protected one of
   the four paths and nothing said so.
3. ``process_event_input`` wrote ``result["event"]`` back into the store under
   an id that every path out of the method then popped.

The behavioural tests here re-point ``_STAGED_PAYLOAD_KEYS`` at other names and
watch where the payload lands: a copy that spells the real names cannot follow,
so the tuple's authority is proven rather than asserted. The structural tests
walk the AST for a re-inlined copy, because a fresh copy that agrees with the
helper on the day it lands is exactly the state this issue is about.
"""

import ast
import inspect
import textwrap
import types

import pytest

from src.api.services.game_service import GameService
from src.events import Event
from src.narration import narrate


def _game_service_functions():
    """Every ``def`` in :class:`GameService`, by name."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(GameService)))
    return {
        node.name: node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
    }


def _literal_key_writers(keys):
    """Functions containing a ``something["<key>"] = ...`` for any of ``keys``."""
    writers = set()
    for name, node in _game_service_functions().items():
        for assign in ast.walk(node):
            if not isinstance(assign, ast.Assign):
                continue
            for target in assign.targets:
                if (
                    isinstance(target, ast.Subscript)
                    and isinstance(target.slice, ast.Constant)
                    and target.slice.value in keys
                ):
                    writers.add(name)
    return writers


def _callers_of(method_name):
    """Functions containing a ``self.<method_name>(...)`` / ``cls.<...>`` call."""
    callers = set()
    for name, node in _game_service_functions().items():
        for call in ast.walk(node):
            if (
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Attribute)
                and call.func.attr == method_name
            ):
                callers.add(name)
    return callers


def make_room(name="TestRoom"):
    return types.SimpleNamespace(
        events_here=[],
        npcs_here=[],
        items_here=[],
        objects_here=[],
        x=3,
        y=4,
        map={"name": name},
    )


class NarratingCombatEvent(Event):
    """A ``combat_effect`` event that narrates once and completes.

    A real ``Event``: ``trigger_combat_events`` serializes it and calls
    ``check_combat_conditions`` on it, so a stub would exercise a different
    branch than the story events the staged payload exists for.
    """

    def __init__(self, player=None, tile=None):
        super().__init__(
            name="Narrating",
            player=player,
            tile=tile if tile is not None else make_room(),
            combat_effect=True,
        )
        self.fired = False

    def check_combat_conditions(self):
        if not self.fired:
            self.fired = True
            self.pass_conditions_to_process()

    def process(self, user_input=None):
        narrate("The chamber answers with a low, wet echo.")
        self.needs_input = False
        self.completed = True


@pytest.fixture
def service():
    return GameService()


# ── Finding 1: _STAGED_PAYLOAD_KEYS is the authority, and it is READ ────────


class TestTheStagedKeysTupleIsActuallyRead:
    def test_the_helper_writes_whatever_the_tuple_says(self, service, monkeypatch):
        """Re-point the tuple; the payload must follow it.

        This is the whole claim of ``_STAGED_PAYLOAD_KEYS``. The previous
        implementation spelled the three names out and would keep writing
        ``output_text`` here — the tuple was documentation, not an authority.
        """
        monkeypatch.setattr(
            GameService, "_STAGED_PAYLOAD_KEYS", ("alpha", "beta", "gamma")
        )
        target = {}

        service._apply_staged_payload(target, "prose", [{"text": "s"}], {"c": 1})

        assert target == {
            "alpha": "prose",
            "beta": [{"text": "s"}],
            "gamma": {"c": 1},
        }

    def test_empty_parts_are_still_skipped(self, service):
        """The shape of an unstaged event's payload must not change."""
        target = {}

        service._apply_staged_payload(target, "prose", [], None)

        assert target == {"output_text": "prose"}

    def test_the_carry_helper_reads_the_same_tuple(self, service, monkeypatch):
        monkeypatch.setattr(GameService, "_STAGED_PAYLOAD_KEYS", ("alpha",))
        event = Event(name="E")
        previous = {"event": event, "event_data": {"alpha": "kept", "beta": "not"}}
        event_data = {}

        GameService._carry_staged_payload(previous, event, event_data)

        assert event_data == {"alpha": "kept"}

    def test_no_one_spells_a_staged_key_by_hand(self):
        """The third inline copy, and any successor, fails here.

        ``trigger_combat_events`` re-implemented ``_apply_staged_payload``
        verbatim — three ``event_data["<key>"] = ...`` assignments that neither
        helper nor the binding test could reach. Both helpers now index by a
        variable read from the tuple, so a literal staged key anywhere in
        ``GameService`` is by definition a copy.
        """
        writers = _literal_key_writers(GameService._STAGED_PAYLOAD_KEYS)
        assert writers == set(), (
            f"{sorted(writers)} write a staged payload key by name instead of "
            "going through _apply_staged_payload; that is the copy issue #524 "
            "removed"
        )

    def test_the_literal_key_detector_can_actually_find_one(self):
        """Positive control — an empty result must not be able to mean 'no scan'."""
        assert _literal_key_writers({"event_id"}), (
            "the AST scan finds no literal 'event_id' write, so its empty "
            "result above proves nothing"
        )

    def test_combat_events_stage_their_prose_through_the_helper(
        self, service, monkeypatch
    ):
        """End-to-end: re-point the tuple and watch ``trigger_combat_events``.

        The inline copy would put the narration under ``output_text`` no matter
        what the tuple said. Driving the real method rather than asserting the
        helper was called keeps this honest about the routing actually being
        wired up.
        """
        monkeypatch.setattr(
            GameService, "_STAGED_PAYLOAD_KEYS", ("alpha", "beta", "gamma")
        )
        room = make_room()
        player = types.SimpleNamespace(
            combat_events=[],
            current_room=room,
            location_x=room.x,
            location_y=room.y,
            universe=types.SimpleNamespace(get_tile=lambda x, y: room),
        )
        event = NarratingCombatEvent(player=player, tile=room)
        player.combat_events.append(event)

        triggered = service.trigger_combat_events(
            player, session_data={"pending_events": {}}
        )

        assert len(triggered) == 1
        assert "The chamber answers" in triggered[0]["alpha"], (
            "trigger_combat_events still spells the staged keys itself"
        )
        assert "output_text" not in triggered[0]

    def test_a_silent_event_that_wants_input_is_still_reported(self, service):
        """``triggered`` must keep both of its reasons after the rewrite.

        It was ``if clean_output: triggered = True`` plus ``if needs_input:
        triggered = True``. Collapsing that to the prose test alone would drop
        every input-only event out of the response.
        """
        room = make_room()
        player = types.SimpleNamespace(
            combat_events=[],
            current_room=room,
            location_x=room.x,
            location_y=room.y,
            universe=types.SimpleNamespace(get_tile=lambda x, y: room),
        )

        class SilentPrompt(NarratingCombatEvent):
            def process(self, user_input=None):
                self.needs_input = True
                self.input_prompt = "Well?"

        event = SilentPrompt(player=player, tile=room)
        player.combat_events.append(event)

        triggered = service.trigger_combat_events(
            player, session_data={"pending_events": {}}
        )

        assert [e["name"] for e in triggered] == ["Narrating"]


# ── Finding 2: one builder for the pending-event entry ─────────────────────


class TestThePendingEntryHasOneBuilder:
    def test_only_the_builder_constructs_the_entry(self):
        builders = set()
        for name, node in _game_service_functions().items():
            for dict_node in ast.walk(node):
                if not isinstance(dict_node, ast.Dict):
                    continue
                literal_keys = {
                    k.value for k in dict_node.keys if isinstance(k, ast.Constant)
                }
                if {"event", "event_data"} <= literal_keys:
                    builders.add(name)
        assert builders == {"_pending_payload"}, (
            f"{sorted(builders)} build a pending-events entry by hand; the "
            "shape has one builder so a new required field cannot be added to "
            "three of four writers"
        )

    def test_the_dedupe_owner_is_the_only_writer_that_mints_ids(self):
        """The loot and passageway sites route through ``_store_pending_event``.

        They minted their own UUIDs, so ``_store_pending_event``'s
        dedupe-by-name rule and the ``_carry_staged_payload`` invariant from
        #515 simply did not apply to them. Their names are per-target
        (``Looting <container>``, ``Passage_<passageway>``), so a name collision
        IS the same dialog re-opened and deduping is the right rule for both.
        """
        assert "interact_with_target" in _callers_of("_store_pending_event")
        assert "interact_with_target" not in _callers_of("_pending_payload")

    def test_the_stage_rekey_shares_the_shape_but_not_the_dedupe(self):
        """A fresh UUID is the entire point of that branch.

        Routing it through ``_store_pending_event`` would rehome the new stage
        onto an existing id and reintroduce the frontend dedupe suppression the
        re-key exists to defeat — so this site takes the builder and not the
        rule. Checked, not assumed: "route everything through one function" is
        the wrong fix here.
        """
        assert "process_event_input" in _callers_of("_pending_payload")
        assert "process_event_input" not in _callers_of("_store_pending_event")

    def test_the_builder_carries_tile_coordinates(self, service):
        tile = make_room()
        event = Event(name="E")
        session_data = {}

        service._store_pending_event(event, {"name": "E"}, session_data, tile=tile)

        stored = session_data["pending_events"][event.api_event_id]
        assert stored["tile_x"] == tile.x
        assert stored["tile_y"] == tile.y
        assert stored["event"] is event

    def test_the_builder_omits_coordinates_it_was_not_given(self, service):
        event = Event(name="E")
        session_data = {}

        service._store_pending_event(event, {"name": "E"}, session_data)

        stored = session_data["pending_events"][event.api_event_id]
        assert "tile_x" not in stored and "tile_y" not in stored

    def test_a_rerouted_writer_now_dedupes_by_name(self, service):
        """What routing the loot/passageway sites through the owner buys.

        Two entries for one dialog is not cosmetic: the first stays pending
        forever and every later request sees a blocking event the player has no
        way to answer.
        """
        session_data = {}
        first = Event(name="Looting Chest")
        service._store_pending_event(first, {"name": "Looting Chest"}, session_data)
        second = Event(name="Looting Chest")

        result = service._store_pending_event(
            second, {"name": "Looting Chest"}, session_data
        )

        assert len(session_data["pending_events"]) == 1
        assert result["event_id"] == first.api_event_id


# ── Finding 3: the dead assignment ─────────────────────────────────────────


def test_process_event_input_writes_the_store_exactly_once():
    """The mid-``try`` write went to an id every exit from the method drops.

    It read as the update that keeps the store current. It never was one: the
    tail either re-keys the entry to a fresh UUID (popping this id) or pops it
    outright, on every path including the ``except``. Counted structurally
    because deleting dead code has no behaviour to observe — the risk is
    someone restoring it while reading the tail as conditional.
    """
    node = _game_service_functions()["process_event_input"]
    writes = [
        ast.unparse(target)
        for assign in ast.walk(node)
        if isinstance(assign, ast.Assign)
        for target in assign.targets
        if isinstance(target, ast.Subscript) and "pending_events" in ast.unparse(target)
    ]
    assert writes == ["session_data['pending_events'][new_event_id]"], (
        f"process_event_input writes the pending store at {writes}; the only "
        "live write is the fresh-UUID re-key -- anything stored under the "
        "incoming event_id is popped before the method returns"
    )


def test_a_multistage_event_leaves_nothing_behind_under_its_old_id(monkeypatch):
    """The property the deleted write pretended to maintain, held by the tail.

    NEGATIVE CONTROL for the deletion -- it passed before it too, which is what
    made the write dead. It is here so the re-key tail cannot quietly stop
    doing the job while the structural test above still passes.
    """
    room = make_room()

    class TwoStage(Event):
        def __init__(self):
            super().__init__(name="TwoStage", player=None, tile=room)
            self.stage = 1

        def process(self, user_input=None):
            if self.stage == 1:
                self.stage = 2
                self.needs_input = True
                self.input_prompt = "Go on?"
                return
            self.needs_input = False
            self.completed = True

    event = TwoStage()
    player = types.SimpleNamespace(
        current_room=room,
        location_x=room.x,
        location_y=room.y,
        universe=types.SimpleNamespace(get_tile=lambda x, y: room),
        in_combat=False,
    )
    event.player = player
    session_data = {
        "pending_events": {
            "old-id": {
                "event": event,
                "event_data": {"needs_input": True},
                "tile_x": room.x,
                "tile_y": room.y,
            }
        }
    }

    GameService().process_event_input(player, "old-id", "continue", session_data)

    assert "old-id" not in session_data["pending_events"]
    assert len(session_data["pending_events"]) == 1
    (stored,) = session_data["pending_events"].values()
    assert stored["event"] is event
    # The coordinates must ride across the re-key or the next stage resolves
    # event.tile from player.current_room, which is usually None in the API.
    assert (stored["tile_x"], stored["tile_y"]) == (room.x, room.y)
