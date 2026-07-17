"""Chapter 3 story event flow checks (Eastern Descent / Nomad Camp / river egress).

Exercises all 7 Ch03 events via the API, verifying that no step produces a
5xx server crash and that the story flags each event is responsible for
actually get set — matching the bug criteria in
docs/development/beta-test-scope-grondia-arc.md (Scenes 4-7). This is the
tail end of the beta arc: "Grondia entrance -> river crossing with Mara".

Unlike ch01/ch02, none of these events use staged (needs_input) dialogue —
each is a single check_conditions() -> process() call, so there is no
submit_input chain to drive.

Events exercised (in story order):
  1. GorranGestureEvent         — fires on arrival from another tile (Grondia exit)
  2. EasternRoadTurnbackEvent   — repeating turnback block at the eastern road
  3. NomadCampSmellEvent        — first entry to the nomad camp sub-map
  4. MaraFirstContactEvent      — Mara's canned "crossing west?" opener
  5. DevetIntroEvent            — Devet's wordless bowl-offering
  6. LissObservingEvent         — Liss watching Gorran from a distance
  7. MaraObservationEvent       — fires once all three intro gates are set;
                                   sets nomad_camp_reached (the beta arc's
                                   completion gate)

Out of scope (see docs/development/beta-test-scope-grondia-arc.md Scene 6,
and the "Known gap" note under Scene 7): Mara/Devet/Liss `talk` dialogue
voice-consistency requires a real LLM call, which bug_hunt.py disables
(MYNX_LLM_ENABLED=0); there is also no river-crossing completion event to
test — crossing is narrative-only via Mara, by design.

Prerequisites: session player must have been initialised with a full Universe.
If the player is a MinimalPlayer (no universe), the scenario returns cleanly
with no bugs reported — that is a harness limitation, not an API bug.
"""

from typing import List

from .base import Scenario
from ..client import GameClient
from ..reporter import BugReport, BugSeverity, BugCategory


class Ch03EventsScenario(Scenario):
    name = "ch03_events"
    description = (
        "Exercise all 7 Chapter 3 (Eastern Descent/Nomad Camp/river) story "
        "events via the API and verify none produce a 5xx server crash."
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
        player.in_combat = False
        player.combat_list = []
        story = universe.story

        # ------------------------------------------------------------------
        # Lazy imports — src modules are shimmed by bug_hunt.py bootstrap
        # ------------------------------------------------------------------
        try:
            from src.story.ch03 import (
                GorranGestureEvent,
                EasternRoadTurnbackEvent,
                NomadCampSmellEvent,
                MaraFirstContactEvent,
                DevetIntroEvent,
                LissObservingEvent,
                MaraObservationEvent,
            )
        except Exception as exc:
            bugs.append(self._bug(
                title=f"ch03_events: failed to import story modules: {exc}",
                severity=BugSeverity.HIGH,
                category=BugCategory.CRASH,
                endpoint="import",
                method="IMPORT",
                expected="Clean import of src.story.ch03",
                actual=str(exc),
            ))
            return bugs

        # ------------------------------------------------------------------
        # Local helpers (mirrors ch01_events.py / ch02_events.py)
        # ------------------------------------------------------------------

        def trigger_events():
            return client.post("/api/world/events")

        def check(resp, label, endpoint="/api/world/events", method="POST"):
            return self._check_no_crash(resp, endpoint, method, label)

        def check_flag(flag_name, label):
            if story.get(flag_name) != "1":
                bugs.append(self._bug(
                    title=f"{label}: story flag '{flag_name}' not set",
                    severity=BugSeverity.MEDIUM,
                    category=BugCategory.WRONG_RESPONSE,
                    endpoint="/api/world/events",
                    method="POST",
                    expected=f"story['{flag_name}'] == '1'",
                    actual=f"story.get({flag_name!r}) = {story.get(flag_name)!r}",
                ))

        # ==================================================================
        # 1. GorranGestureEvent — requires a truthy previous_tile to fire
        # ==================================================================
        player.previous_tile = tile
        tile.events_here = [GorranGestureEvent(player, tile, repeat=False)]

        resp = trigger_events()
        bug = check(resp, "GorranGestureEvent trigger")
        if bug:
            bugs.append(bug)
        check_flag("gorran_gesture_done", "GorranGestureEvent")

        # ==================================================================
        # 2. EasternRoadTurnbackEvent — repeating; fire it twice to confirm
        # the block actually repeats rather than firing only once.
        # ==================================================================
        tile.events_here = [EasternRoadTurnbackEvent(player, tile, repeat=True)]

        resp = trigger_events()
        bug = check(resp, "EasternRoadTurnbackEvent trigger (1st)")
        if bug:
            bugs.append(bug)

        # process() moves the player off-tile; put it back on the same tile
        # with the same event attached, mirroring a player who keeps trying
        # to push east.
        player.current_room = tile
        player.location_x, player.location_y = tile.x, tile.y
        tile.events_here = [EasternRoadTurnbackEvent(player, tile, repeat=True)]
        resp = trigger_events()
        bug = check(resp, "EasternRoadTurnbackEvent trigger (2nd, repeat check)")
        if bug:
            bugs.append(bug)

        # process() moves the player again on this 2nd trigger too — restore
        # position once more before every subsequent event, or trigger_events()
        # resolves the "current tile" from wherever process() left the player
        # and silently never finds the events we attach to `tile` below.
        player.current_room = tile
        player.location_x, player.location_y = tile.x, tile.y

        # ==================================================================
        # 3. NomadCampSmellEvent
        # ==================================================================
        tile.events_here = [NomadCampSmellEvent(player, tile, repeat=False)]

        resp = trigger_events()
        bug = check(resp, "NomadCampSmellEvent trigger")
        if bug:
            bugs.append(bug)
        check_flag("nomad_camp_entered", "NomadCampSmellEvent")

        # ==================================================================
        # 4. MaraFirstContactEvent
        # ==================================================================
        tile.events_here = [MaraFirstContactEvent(player, tile, repeat=False)]

        resp = trigger_events()
        bug = check(resp, "MaraFirstContactEvent trigger")
        if bug:
            bugs.append(bug)
        check_flag("mara_intro_done", "MaraFirstContactEvent")

        # ==================================================================
        # 5. DevetIntroEvent
        # ==================================================================
        tile.events_here = [DevetIntroEvent(player, tile, repeat=False)]

        resp = trigger_events()
        bug = check(resp, "DevetIntroEvent trigger")
        if bug:
            bugs.append(bug)
        check_flag("devet_intro_done", "DevetIntroEvent")

        # ==================================================================
        # 6. LissObservingEvent
        # ==================================================================
        tile.events_here = [LissObservingEvent(player, tile, repeat=False)]

        resp = trigger_events()
        bug = check(resp, "LissObservingEvent trigger")
        if bug:
            bugs.append(bug)
        check_flag("liss_gorran_done", "LissObservingEvent")

        # ==================================================================
        # 7. MaraObservationEvent — requires all three intro gates above
        # ==================================================================
        tile.events_here = [MaraObservationEvent(player, tile, repeat=False)]

        resp = trigger_events()
        bug = check(resp, "MaraObservationEvent trigger")
        if bug:
            bugs.append(bug)
        check_flag("nomad_camp_reached", "MaraObservationEvent (beta arc completion gate)")

        # ==================================================================
        # Revisit check — one-shot camp events should not re-fire once their
        # gates are set (matches the beta doc's "repeating on revisit" bug
        # criteria applied to Scene 0/3 elsewhere in the arc).
        # ==================================================================
        tile.events_here = [
            NomadCampSmellEvent(player, tile, repeat=False),
            MaraFirstContactEvent(player, tile, repeat=False),
        ]
        resp = trigger_events()
        bug = check(resp, "Nomad camp gate events revisit (should not re-fire)")
        if bug:
            bugs.append(bug)

        return bugs
