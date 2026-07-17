"""Chapter 2 story event flow checks (Grondia / King Slime / Votha Krr arc).

Exercises all 9 Ch02 events via the API, verifying that no step produces a
5xx server crash and that the story flags each event is responsible for
actually get set — matching the bug criteria in
docs/development/beta-test-scope-grondia-arc.md (Scenes 0-3).

Events exercised (in story order):
  1.  AfterDefeatingLurker      — no-op event (beta: continuation disabled)
  2.  BetaTesterBriefing        — 3-stage briefing (tile 1,2 in the real game)
  3.  Ch02GuideToCitadel        — 8-stage guided walk + quest offer choice
  4.  Ch02ArenaEntrance         — requires a live KingSlime on the tile
  5.  AfterDefeatingKingSlime   — fires once KingSlime is gone; spawns
                                   MineralFragment + queues the memory flash
  6.  Ch02FragmentReminder      — evaluate_for_map_entry() only, not reachable
                                   via check_conditions; called directly
  7.  Ch02KingSlimeMemoryFlash  — fires once the fragment is in inventory
  8.  AfterKingSlimeReturn      — 7-stage fragment handoff to Votha Krr
  9.  Ch02GorranAtPools         — spawns Gorran onto the pools atrium tile

Prerequisites: session player must have been initialised with a full Universe
(the harness creates one via SessionManager._create_player_for_session).
If the player is a MinimalPlayer (no universe), the scenario returns cleanly
with no bugs reported — that is a harness limitation, not an API bug.

Out of scope (see docs/development/beta-test-scope-grondia-arc.md Scene 1, 5, 6):
Grondia navigation / NPCSpawnerEvent population and the Conclave Elder
placeholder are generic engine behavior, not Ch02-specific event classes.
Mara/Devet/Liss dialogue voice-consistency requires a real LLM call, which
bug_hunt.py disables (MYNX_LLM_ENABLED=0) — that's an Inquisitor/browser job.
"""

from typing import List

from .base import Scenario
from ..client import GameClient
from ..reporter import BugReport, BugSeverity, BugCategory


class Ch02EventsScenario(Scenario):
    name = "ch02_events"
    description = (
        "Exercise all 9 Chapter 2 (Grondia/King Slime/Votha Krr) story events "
        "via the API and verify none produce a 5xx server crash."
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
        original_map = player.map
        player.in_combat = False
        player.combat_list = []
        if not hasattr(player, "combat_list_allies") or not player.combat_list_allies:
            player.combat_list_allies = [player]
        story = universe.story

        # ------------------------------------------------------------------
        # Lazy imports — src modules are shimmed by bug_hunt.py bootstrap
        # ------------------------------------------------------------------
        try:
            from src.story.ch02 import (
                AfterDefeatingLurker,
                BetaTesterBriefing,
                Ch02GuideToCitadel,
                AfterDefeatingKingSlime,
                Ch02GorranAtPools,
                Ch02ArenaEntrance,
                Ch02FragmentReminder,
                Ch02KingSlimeMemoryFlash,  # noqa: F401 (queued dynamically by AfterDefeatingKingSlime)
                AfterKingSlimeReturn,
            )
        except Exception as exc:
            bugs.append(self._bug(
                title=f"ch02_events: failed to import story modules: {exc}",
                severity=BugSeverity.HIGH,
                category=BugCategory.CRASH,
                endpoint="import",
                method="IMPORT",
                expected="Clean import of src.story.ch02",
                actual=str(exc),
            ))
            return bugs

        # ------------------------------------------------------------------
        # Local helpers (mirrors tools/harness/scenarios/ch01_events.py)
        # ------------------------------------------------------------------

        def trigger_events():
            return client.post("/api/world/events")

        def submit_input(event_id, user_input):
            return client.post(
                "/api/world/events/input",
                json={"event_id": event_id, "user_input": user_input},
            )

        def first_input_event(resp):
            data = client.parse(resp)
            for evt in data.get("events", []):
                if evt.get("needs_input") and evt.get("event_id"):
                    return evt["event_id"], evt
            return None, None

        def next_stage_id(resp):
            data = client.parse(resp)
            evt = data.get("event", {})
            if data.get("needs_input") and evt.get("event_id"):
                return evt["event_id"]
            return None

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

        def run_staged(event, stage_labels, submits, trigger_label):
            """Trigger `event`, then submit each value in `submits` in order.

            Returns True if a crash was found (caller should stop the chain).
            """
            tile.events_here = [event]
            resp = trigger_events()
            bug = check(resp, trigger_label)
            if bug:
                bugs.append(bug)
                return True
            eid, _ = first_input_event(resp)
            if eid is None:
                return False
            for label, value in zip(stage_labels, submits):
                resp = submit_input(eid, value)
                bug = check(resp, label, "/api/world/events/input")
                if bug:
                    bugs.append(bug)
                    return True
                new_eid = next_stage_id(resp)
                if new_eid:
                    eid = new_eid
            return False

        # ==================================================================
        # 1. AfterDefeatingLurker (no-op — beta continuation is disabled)
        # ==================================================================
        tile.objects_here = []
        tile.npcs_here = []
        tile.events_here = [AfterDefeatingLurker(player, tile, repeat=False)]

        resp = trigger_events()
        bug = check(resp, "AfterDefeatingLurker trigger")
        if bug:
            bugs.append(bug)

        # ==================================================================
        # 2. BetaTesterBriefing (3 stages)
        # ==================================================================
        crashed = run_staged(
            BetaTesterBriefing(player, tile, repeat=False),
            ["BetaTesterBriefing stage-2 (beta notice)",
             "BetaTesterBriefing stage-3 (complete)"],
            ["continue", "begin"],
            "BetaTesterBriefing trigger (stage-1 recap)",
        )

        # Revisit check — the beta doc's Scene 0 bug criteria explicitly
        # calls out "the event repeating on revisit" as a bug. The real
        # no-repeat guard is structural: a completed one-shot event removes
        # itself from tile.events_here (see Event.pass_conditions_to_process
        # and BetaTesterBriefing's own stage-3 cleanup) — a fresh instance
        # would always "fire" regardless of that guard, so the only honest
        # check is that the completed instance actually removed itself.
        if not crashed and tile.events_here:
            bugs.append(self._bug(
                title="BetaTesterBriefing did not remove itself from tile.events_here on completion",
                severity=BugSeverity.HIGH,
                category=BugCategory.WRONG_RESPONSE,
                endpoint="/api/world/events",
                method="POST",
                expected="tile.events_here no longer contains the completed briefing",
                actual=f"tile.events_here = {[type(e).__name__ for e in tile.events_here]}",
            ))

        # ==================================================================
        # 3. Ch02GuideToCitadel (8 stages, choice at stage 5->6)
        # ==================================================================
        player.combat_list = []
        run_staged(
            Ch02GuideToCitadel(player, tile, params=None, repeat=False),
            [
                "Ch02GuideToCitadel stage-2 (archway/Citadel sight)",
                "Ch02GuideToCitadel stage-3 (Grondites greet)",
                "Ch02GuideToCitadel stage-4 (elders chamber/Votha intro)",
                "Ch02GuideToCitadel stage-5 (quest offer)",
                "Ch02GuideToCitadel stage-6 (choice 'a' response)",
                "Ch02GuideToCitadel stage-7 (loot/farewell)",
                "Ch02GuideToCitadel stage-8 (teleport/cleanup)",
            ],
            ["continue", "continue", "continue", "continue", "a", "continue", "done"],
            "Ch02GuideToCitadel trigger (stage-1 approach)",
        )

        # Stage 8 calls player.teleport("grondia", (10, 5)), which reassigns
        # player.map to the Grondia map dict and player.location_x/y to (10, 5)
        # (teleport() does not touch player.current_room directly). Every event
        # from here on is attached to `tile`, and get_current_tile_object()/
        # trigger_tile_events() resolve the "current" tile from player.map +
        # location_x/y, so leaving player.map pointed at Grondia would silently
        # misdirect every remaining event onto whatever tile happens to sit at
        # (10, 5) on that map instead of our synthetic test tile.
        player.map = original_map
        player.current_room = tile
        player.location_x, player.location_y = tile.x, tile.y

        # ==================================================================
        # 4. Ch02ArenaEntrance (requires a live KingSlime on the tile)
        # ==================================================================
        tile.npcs_here = []
        tile.spawn_npc("KingSlime")
        tile.events_here = [Ch02ArenaEntrance(player, tile, repeat=False)]

        resp = trigger_events()
        bug = check(resp, "Ch02ArenaEntrance trigger")
        if bug:
            bugs.append(bug)
        check_flag("arena_entered", "Ch02ArenaEntrance")

        # Simulate the King Slime being defeated in combat.
        tile.npcs_here = [
            n for n in tile.npcs_here if n.__class__.__name__ != "KingSlime"
        ]

        # ==================================================================
        # 5. AfterDefeatingKingSlime (spawns fragment + queues memory flash)
        # ==================================================================
        tile.events_here = [AfterDefeatingKingSlime(player, tile, repeat=False)]

        resp = trigger_events()
        bug = check(resp, "AfterDefeatingKingSlime trigger")
        if bug:
            bugs.append(bug)
        check_flag("king_slime_defeated", "AfterDefeatingKingSlime")

        fragment = next(
            (i for i in tile.items_here if i.__class__.__name__ == "MineralFragment"),
            None,
        )
        if fragment is None:
            bugs.append(self._bug(
                title="AfterDefeatingKingSlime did not spawn a MineralFragment",
                severity=BugSeverity.MEDIUM,
                category=BugCategory.WRONG_RESPONSE,
                endpoint="/api/world/events",
                method="POST",
                expected="A MineralFragment item is present on the arena tile",
                actual=f"tile.items_here = {[type(i).__name__ for i in tile.items_here]}",
            ))

        # ==================================================================
        # 6. Ch02FragmentReminder (evaluate_for_map_entry only — direct call)
        # Only meaningful while the fragment is still on the tile (not yet
        # picked up) and the player has left — matches its own precondition.
        # ==================================================================
        reminder = Ch02FragmentReminder(player, tile, repeat=True)
        original_room = player.current_room
        original_tick = story.get("fragment_reminder_tick")
        try:
            player.current_room = None  # simulate having left the arena
            reminder.evaluate_for_map_entry(player)
        except Exception as exc:
            bugs.append(self._bug(
                title=f"Ch02FragmentReminder.evaluate_for_map_entry() raised: {type(exc).__name__}: {exc}",
                severity=BugSeverity.HIGH,
                category=BugCategory.CRASH,
                endpoint="Ch02FragmentReminder.evaluate_for_map_entry()",
                method="DIRECT",
                expected="No exception",
                actual=f"{type(exc).__name__}: {exc}",
            ))
        finally:
            player.current_room = original_room
            if original_tick is None:
                story.pop("fragment_reminder_tick", None)

        # ==================================================================
        # 7. Ch02KingSlimeMemoryFlash (fires once fragment is in inventory)
        # Simulate pickup: move the fragment from the tile onto the player.
        # ==================================================================
        if fragment is not None:
            if fragment in tile.items_here:
                tile.items_here.remove(fragment)
            player.inventory.append(fragment)

            resp = trigger_events()
            bug = check(resp, "Ch02KingSlimeMemoryFlash trigger (fragment pickup)")
            if bug:
                bugs.append(bug)
            else:
                eid, _ = first_input_event(resp)
                if eid:
                    resp2 = submit_input(eid, "continue")
                    bug = check(resp2, "Ch02KingSlimeMemoryFlash acknowledge",
                                "/api/world/events/input")
                    if bug:
                        bugs.append(bug)

        # ==================================================================
        # 8. AfterKingSlimeReturn (7 stages, 3-way choice at stage 1->2)
        # ==================================================================
        run_staged(
            AfterKingSlimeReturn(player, tile, repeat=False),
            [
                "AfterKingSlimeReturn stage-2 (handover narration)",
                "AfterKingSlimeReturn stage-3 (Votha consumes fragment)",
                "AfterKingSlimeReturn stage-4 (acknowledgment)",
                "AfterKingSlimeReturn stage-5 (philosophical directive)",
                "AfterKingSlimeReturn stage-6 (farewell gesture)",
                "AfterKingSlimeReturn stage-7 (cleanup)",
            ],
            ["a", "continue", "continue", "continue", "continue", "continue"],
            "AfterKingSlimeReturn trigger (stage-1 greeting/choice)",
        )
        check_flag("votha_krr_response_given", "AfterKingSlimeReturn")

        has_fragment_after = any(
            i.__class__.__name__ == "MineralFragment" for i in player.inventory
        )
        if has_fragment_after:
            bugs.append(self._bug(
                title="MineralFragment still in inventory after AfterKingSlimeReturn",
                severity=BugSeverity.LOW,
                category=BugCategory.WRONG_RESPONSE,
                endpoint="/api/world/events",
                method="POST",
                expected="MineralFragment removed from inventory once handed to Votha Krr",
                actual="MineralFragment present in player.inventory",
            ))

        # ==================================================================
        # 9. Ch02GorranAtPools (spawns Gorran onto the pools atrium tile)
        # ==================================================================
        tile.events_here = [Ch02GorranAtPools(player, tile, repeat=False)]

        resp = trigger_events()
        bug = check(resp, "Ch02GorranAtPools trigger")
        if bug:
            bugs.append(bug)
        check_flag("gorran_at_pools", "Ch02GorranAtPools")

        return bugs
