"""Chapter 1 PostRumbler3 wrong choice paths (b and c) - regression test.

Verifies that wrong choices in Ch01PostRumbler3 don't cause server crashes (500 errors).
The fix for GitHub issue #38 restructured the defeat narrative into stages to prevent
displaying the entire sequence at once in the frontend.

This scenario exercises the wrong choice paths to ensure no regressions were introduced.
"""

from typing import List

from .base import Scenario
from ..client import GameClient
from ..reporter import BugReport, BugSeverity, BugCategory


class Ch01WrongChoiceScenario(Scenario):
    name = "ch01_wrong_choice"
    description = (
        "Test Ch01PostRumbler3 wrong choice paths (b and c) regression test "
        "for issue #38 (staged defeat narrative)."
    )

    def run(self, client: GameClient) -> List[BugReport]:
        bugs = []

        # ------------------------------------------------------------------
        # Setup
        # ------------------------------------------------------------------
        sm = client._session_manager
        player = sm.get_player(client.session_id)
        session = sm.get_session(client.session_id)

        if player is None or session is None:
            return []

        universe = getattr(player, "universe", None)
        if universe is None:
            return []

        tile = universe.get_tile(player.location_x, player.location_y)
        if tile is None:
            return []

        player.current_room = tile

        # Combat setup
        player.in_combat = True
        player.combat_list = []
        if not hasattr(player, "combat_list_allies") or not player.combat_list_allies:
            player.combat_list_allies = [player]
        if not hasattr(player, "combat_events"):
            player.combat_events = []

        # ------------------------------------------------------------------
        # Imports
        # ------------------------------------------------------------------
        try:
            from src.story.ch01 import Ch01PostRumbler3
            from src.api.serializers.event_serializer import EventSerializer
        except Exception as exc:
            bugs.append(self._bug(
                title=f"ch01_wrong_choice: failed to import: {exc}",
                severity=BugSeverity.HIGH,
                category=BugCategory.CRASH,
                endpoint="import",
                method="IMPORT",
                expected="Clean import",
                actual=str(exc),
            ))
            return bugs

        # ------------------------------------------------------------------
        # Helpers
        # ------------------------------------------------------------------
        def submit_input(event_id, user_input):
            return client.post(
                "/api/world/events/input",
                json={"event_id": event_id, "user_input": user_input},
            )

        def queue_event(event):
            import uuid
            eid = str(uuid.uuid4())
            edata = EventSerializer.serialize_with_input(event)
            edata["event_id"] = eid
            session.data.setdefault("pending_events", {})[eid] = {
                "event": event,
                "event_data": edata,
            }
            return eid

        def next_stage_id(resp):
            data = client.parse(resp)
            evt = data.get("event", {})
            if evt.get("event_id"):
                return evt["event_id"]
            return None

        def check(resp, label, endpoint="/api/world/events/input", method="POST"):
            return self._check_no_crash(resp, endpoint, method, label)

        # ==================================================================
        # Test wrong choice 'b' (Make a break for it)
        # ==================================================================
        event = Ch01PostRumbler3(player=player, tile=tile, repeat=False)
        eid = queue_event(event)

        # Reset player HP for this test
        player.hp = player.maxhp // 2

        # Stage 1: Show prompt
        resp = submit_input(eid, "")
        bug = check(resp, "Ch01PostRumbler3 wrong_choice: prompt stage")
        if bug:
            bugs.append(bug)
            return bugs

        eid = next_stage_id(resp) or eid

        # Stage 2: Submit choice 'b' (cowardly escape)
        resp = submit_input(eid, "b")
        bug = check(resp, "Ch01PostRumbler3 wrong_choice 'b': choice submission")
        if bug:
            bugs.append(bug)
            return bugs

        eid = next_stage_id(resp)

        # Continue through remaining stages (should not crash)
        stage_count = 0
        while eid and stage_count < 10:  # Allow many stages to complete
            resp = submit_input(eid, "")
            bug = check(resp, f"Ch01PostRumbler3 'b' choice: stage {stage_count + 3}")
            if bug:
                bugs.append(bug)
                break

            # Check if we're done
            data = client.parse(resp)
            if not data.get("event", {}).get("event_id"):
                break

            eid = next_stage_id(resp)
            stage_count += 1

        # ==================================================================
        # Test wrong choice 'c' (Consider alternatives / indecision)
        # ==================================================================
        event = Ch01PostRumbler3(player=player, tile=tile, repeat=False)
        eid = queue_event(event)

        # Reset for this path
        player.hp = player.maxhp // 2

        # Stage 1: Show prompt
        resp = submit_input(eid, "")
        bug = check(resp, "Ch01PostRumbler3 wrong_choice 'c': prompt stage")
        if bug:
            bugs.append(bug)
            return bugs

        eid = next_stage_id(resp) or eid

        # Stage 2: Submit choice 'c' (paralyzed by indecision)
        resp = submit_input(eid, "c")
        bug = check(resp, "Ch01PostRumbler3 wrong_choice 'c': choice submission")
        if bug:
            bugs.append(bug)
            return bugs

        eid = next_stage_id(resp)

        # Continue through remaining stages
        stage_count = 0
        while eid and stage_count < 10:
            resp = submit_input(eid, "")
            bug = check(resp, f"Ch01PostRumbler3 'c' choice: stage {stage_count + 3}")
            if bug:
                bugs.append(bug)
                break

            data = client.parse(resp)
            if not data.get("event", {}).get("event_id"):
                break

            eid = next_stage_id(resp)
            stage_count += 1

        return bugs
