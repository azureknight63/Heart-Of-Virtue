"""Chapter 1 story event flow checks.

Exercises all 10 Ch01 events via the API, verifying that no step produces
a 5xx server crash.

Events exercised (in story order):
  1.  Ch01_Memory_Amelia      — MemoryFlash: tile trigger + "continue" input
  2.  Ch01StartOpenWall        — tile event, auto-triggers on WallSwitch press
  3.  Ch01BridgeWall           — tile event, same trigger pattern
  4.  Ch01ChestRumblerBattle   — tile event + "continue" input → combat start
  5.  Ch01PostRumbler          — staged combat event (3 API calls)
  6.  Ch01PostRumblerRep       — repeating combat announcement (2 API calls)
  7.  Ch01PostRumbler2         — low-HP Gorran-entrance event (direct call)
  8.  Ch01PostRumbler3         — branching choice, input "a" (help Gorran)
  9.  AfterTheRumblerFight     — post-combat tile event
  10. AfterGorranIntro         — tile event, teleports player to caverns

Prerequisites: session player must have been initialised with a full Universe
(the harness creates one via SessionManager._create_player_for_session).
If the player is a MinimalPlayer (no universe), the scenario returns cleanly
with no bugs reported — that is a harness limitation, not an API bug.
"""

from typing import List

from .base import Scenario
from ..client import GameClient
from ..reporter import BugReport, BugSeverity, BugCategory


class Ch01EventsScenario(Scenario):
    name = "ch01_events"
    description = (
        "Exercise all 10 Chapter 1 story events via the API and verify "
        "none produce a 5xx server crash."
    )

    def run(self, client: GameClient) -> List[BugReport]:
        bugs = []

        # ------------------------------------------------------------------
        # Setup: resolve player, tile, session
        # ------------------------------------------------------------------
        sm = client._session_manager
        player = sm.get_player(client.session_id)
        session = sm.get_session(client.session_id)

        if player is None or session is None:
            return []

        universe = getattr(player, "universe", None)
        if universe is None:
            # MinimalPlayer fallback — story events require a full universe.
            return []

        tile = universe.get_tile(player.location_x, player.location_y)
        if tile is None:
            return []

        player.current_room = tile

        # Ensure combat-related attributes are present
        player.in_combat = False
        player.combat_list = []
        if not hasattr(player, "combat_list_allies") or not player.combat_list_allies:
            player.combat_list_allies = [player]
        if not hasattr(player, "combat_events"):
            player.combat_events = []

        # ------------------------------------------------------------------
        # Lazy imports — src modules are shimmed by bug_hunt.py bootstrap
        # ------------------------------------------------------------------
        try:
            from src.story.ch01 import (
                Ch01_Memory_Amelia,
                Ch01StartOpenWall,
                Ch01BridgeWall,
                Ch01ChestRumblerBattle,
                Ch01PostRumbler,
                Ch01PostRumblerRep,
                Ch01PostRumbler2,
                Ch01PostRumbler3,
                AfterTheRumblerFight,
                AfterGorranIntro,
            )
            from src.objects import WallSwitch, Container
            from src.npc import NPC
        except Exception as exc:
            bugs.append(self._bug(
                title=f"ch01_events: failed to import story modules: {exc}",
                severity=BugSeverity.HIGH,
                category=BugCategory.CRASH,
                endpoint="import",
                method="IMPORT",
                expected="Clean import of src.story.ch01 and src.objects",
                actual=str(exc),
            ))
            return bugs

        # ------------------------------------------------------------------
        # Local helpers
        # ------------------------------------------------------------------

        def trigger_events():
            """POST /api/world/events — fires tile events for current room."""
            return client.post("/api/world/events")

        def submit_input(event_id, user_input):
            """POST /api/world/events/input — advance a pending event."""
            return client.post(
                "/api/world/events/input",
                json={"event_id": event_id, "user_input": user_input},
            )

        def queue_event(event):
            """Manually add an event to session pending_events; return its ID."""
            import uuid
            from src.api.serializers.event_serializer import EventSerializer

            eid = str(uuid.uuid4())
            edata = EventSerializer.serialize_with_input(event)
            edata["event_id"] = eid
            session.data.setdefault("pending_events", {})[eid] = {
                "event": event,
                "event_data": edata,
            }
            return eid

        def first_input_event(resp):
            """Return (event_id, event_dict) for the first event needing input."""
            data = client.parse(resp)
            for evt in data.get("events", []):
                if evt.get("needs_input") and evt.get("event_id"):
                    return evt["event_id"], evt
            return None, None

        def next_stage_id(resp):
            """After submitting input, extract the new event_id if still pending."""
            data = client.parse(resp)
            evt = data.get("event", {})
            if data.get("needs_input") and evt.get("event_id"):
                return evt["event_id"]
            return None

        def check(resp, label, endpoint="/api/world/events", method="POST"):
            return self._check_no_crash(resp, endpoint, method, label)

        # ==================================================================
        # 1. Ch01_Memory_Amelia
        # ==================================================================
        tile.objects_here = []
        tile.events_here = [Ch01_Memory_Amelia(player, tile, repeat=False)]

        resp = trigger_events()
        bug = check(resp, "Ch01_Memory_Amelia trigger")
        if bug:
            bugs.append(bug)
        else:
            eid, _ = first_input_event(resp)
            if eid:
                resp2 = submit_input(eid, "continue")
                bug = check(resp2, "Ch01_Memory_Amelia acknowledge",
                            "/api/world/events/input")
                if bug:
                    bugs.append(bug)

        # ==================================================================
        # 2. Ch01StartOpenWall
        # ==================================================================
        tile.block_exit = ["east"]
        tile.objects_here = [WallSwitch(player=player, tile=tile, position=True)]
        tile.events_here = [Ch01StartOpenWall(player, tile, repeat=True)]

        resp = trigger_events()
        bug = check(resp, "Ch01StartOpenWall trigger")
        if bug:
            bugs.append(bug)

        # ==================================================================
        # 3. Ch01BridgeWall
        # ==================================================================
        tile.block_exit = ["east"]
        tile.objects_here = [WallSwitch(player=player, tile=tile, position=True)]
        tile.events_here = [Ch01BridgeWall(player, tile, repeat=True)]

        resp = trigger_events()
        bug = check(resp, "Ch01BridgeWall trigger")
        if bug:
            bugs.append(bug)

        # ==================================================================
        # 4. Ch01ChestRumblerBattle
        # ==================================================================
        chest = Container(name="Wooden Chest", inventory=[])
        chest.tile = tile
        chest.player = player
        tile.objects_here = [chest]
        tile.events_here = [Ch01ChestRumblerBattle(player, tile, repeat=True)]

        resp = trigger_events()
        bug = check(resp, "Ch01ChestRumblerBattle trigger")
        if bug:
            bugs.append(bug)
        else:
            eid, _ = first_input_event(resp)
            if eid:
                resp2 = submit_input(eid, "continue")
                bug = check(resp2, "Ch01ChestRumblerBattle acknowledge",
                            "/api/world/events/input")
                if bug:
                    bugs.append(bug)

        # Switch to in-combat state for the remaining combat events
        player.in_combat = True
        player.combat_list = []

        # ==================================================================
        # 5. Ch01PostRumbler  (3 stages — event_id rotates each stage)
        # ==================================================================
        event = Ch01PostRumbler(player=player, tile=tile, repeat=False)
        eid = queue_event(event)

        stage_labels = [
            "Ch01PostRumbler stage-1 (memory)",
            "Ch01PostRumbler stage-2 (spawn enemies)",
            "Ch01PostRumbler stage-3 (complete)",
        ]
        crashed = False
        for label in stage_labels:
            resp = submit_input(eid, "continue")
            bug = check(resp, label, "/api/world/events/input")
            if bug:
                bugs.append(bug)
                crashed = True
                break
            new_eid = next_stage_id(resp)
            if new_eid:
                eid = new_eid

        # ==================================================================
        # 6. Ch01PostRumblerRep  (2 stages)
        # ==================================================================
        if not crashed:
            player.combat_list = []  # empty list satisfies check_combat_conditions
            event = Ch01PostRumblerRep(player=player, tile=tile, repeat=False)
            eid = queue_event(event)

            resp = submit_input(eid, "continue")
            bug = check(resp, "Ch01PostRumblerRep stage-1 (spawn+announce)",
                        "/api/world/events/input")
            if bug:
                bugs.append(bug)
            else:
                new_eid = next_stage_id(resp)
                if new_eid:
                    resp2 = submit_input(new_eid, "continue")
                    bug = check(resp2, "Ch01PostRumblerRep stage-2 (acknowledge)",
                                "/api/world/events/input")
                    if bug:
                        bugs.append(bug)

        # ==================================================================
        # 7. Ch01PostRumbler2  (no API input needed — call process directly)
        # Gorran bursts in, heals Jean, and adds Ch01PostRumbler3 to
        # combat_events.  We trigger it directly because there is no HTTP
        # endpoint that dispatches combat events on demand.
        # ==================================================================
        player.hp = max(1, int(player.maxhp * 0.2))
        player.combat_list = []       # avoid index errors inside process()
        player.combat_list_allies = [player]
        tile.events_here = []
        tile.npcs_here = []

        event2 = Ch01PostRumbler2(player=player, tile=tile, repeat=False)
        try:
            # process() calls cprint/time.sleep — no blocking calls, safe here.
            event2.process()
        except Exception as exc:
            bugs.append(self._bug(
                title=f"Ch01PostRumbler2.process() raised: {type(exc).__name__}: {exc}",
                severity=BugSeverity.HIGH,
                category=BugCategory.CRASH,
                endpoint="Ch01PostRumbler2.process()",
                method="DIRECT",
                expected="No exception",
                actual=f"{type(exc).__name__}: {exc}",
            ))

        # ==================================================================
        # 8. Ch01PostRumbler3  (branching choice, path 'a' = help Gorran)
        # ==================================================================
        tile.events_here = []   # reset — Ch01PostRumbler2 may have appended
        player.combat_list = []
        player.combat_list_allies = [player]

        event = Ch01PostRumbler3(player=player, tile=tile, repeat=False)
        eid = queue_event(event)

        # First call: display prompt (user_input is falsy triggers prompt path)
        # We pass an empty string so process() takes the needs_input branch.
        resp = submit_input(eid, "")
        bug = check(resp, "Ch01PostRumbler3 prompt display",
                    "/api/world/events/input")
        if bug:
            bugs.append(bug)
        else:
            new_eid = next_stage_id(resp) or eid
            # Second call: commit choice 'a' (help Gorran — the virtuous path)
            resp2 = submit_input(new_eid, "a")
            bug = check(resp2, "Ch01PostRumbler3 choice 'a' (help Gorran)",
                        "/api/world/events/input")
            if bug:
                bugs.append(bug)

        # ==================================================================
        # 9. AfterTheRumblerFight
        # ==================================================================
        player.in_combat = False
        player.combat_list = []
        tile.npcs_here = [
            NPC(name="Rock-Man", description="Rock ally",
                damage=1, aggro=False, exp_award=0)
        ]
        tile.events_here = [AfterTheRumblerFight(player, tile)]

        resp = trigger_events()
        bug = check(resp, "AfterTheRumblerFight trigger")
        if bug:
            bugs.append(bug)

        # ==================================================================
        # 10. AfterGorranIntro
        # ==================================================================
        tile.events_here = [AfterGorranIntro(player, tile)]

        resp = trigger_events()
        bug = check(resp, "AfterGorranIntro trigger")
        if bug:
            bugs.append(bug)

        return bugs
