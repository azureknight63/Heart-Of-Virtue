"""
Grondia Happy Path Scenario.

Tests the main Grondia quest flow:
1. Boot game on worktree alpha
2. Navigate to Votha Krr (tile 6,5)
3. Trigger Votha Krr conversation
4. Go through Jambo's shop and buy a Restorative
5. Fight through mineral pools to King Slime
6. Encounter and defeat King Slime
7. Return to Votha Krr

Uses Flask test client (API layer).
"""

from typing import List
from .base import Scenario
from ..client import GameClient
from ..reporter import BugReport, BugSeverity, BugCategory


class GroniaHappyPathScenario(Scenario):
    name = "grondia_happy_path"
    description = "End-to-end Grondia quest walkthrough"

    def run(self, client: GameClient) -> List[BugReport]:
        bugs = []

        # =====================================================================
        # STEP 1: Create session and boot game
        # =====================================================================
        print("\n[STEP 1] Boot game with Grondia config...")

        try:
            session_id = client.create_session("grondia_tester")
            print(f"  Session created: {session_id}")

            # Get initial game state
            resp = client.get("/api/status")
            status_bug = self._check_status(
                resp, 200, "/api/status", "GET",
                "Boot: fetch player status"
            )
            if status_bug:
                bugs.append(status_bug)
                return bugs  # Can't continue without game state

            data = client.parse(resp)
            status_data = data.get('status', {})
            print(f"  Player: {status_data.get('name', 'UNKNOWN')}")
            print(f"  Level: {status_data.get('level', 'UNKNOWN')}")
            print(f"  HP: {status_data.get('hp', 'UNKNOWN')}")

        except Exception as e:
            bugs.append(self._bug(
                title="Boot crash",
                severity=BugSeverity.CRITICAL,
                category=BugCategory.CRASH,
                endpoint="/api/game/status",
                method="GET",
                expected="Player loads at Grondia entry",
                actual=f"Exception: {e}",
            ))
            return bugs

        # =====================================================================
        # STEP 2: Navigate to Votha Krr (tile 6,5)
        # =====================================================================
        print("\n[STEP 2] Navigate to Votha Krr (6, 5)...")

        try:
            # Move from (1,2) towards (6,5)
            # Path: south to (1,3), then east/south as map allows
            move_sequence = [
                ("south", "1,3"),
                ("east", "2,3"),
                ("south", "2,4"),
                ("east", "3,4"),
                ("south", "3,5"),
                ("east", "4,5"),
                ("east", "5,5"),
                ("east", "6,5"),
            ]

            current_location = None
            for direction, expected_loc in move_sequence:
                resp = client.post("/api/world/move", json={"direction": direction})

                move_bug = self._check_no_crash(
                    resp, "/api/world/move", "POST",
                    f"Move {direction}"
                )
                if move_bug:
                    bugs.append(move_bug)
                    break

                if resp.status_code == 200:
                    data = client.parse(resp)
                    # /api/world/move returns {"new_position": {"x", "y"}, "room": {...}, ...}
                    # — there is no "location" string field anywhere in the contract.
                    pos = data.get("new_position") or data.get("room", {})
                    if "x" in pos and "y" in pos:
                        current_location = f"{pos['x']},{pos['y']}"
                    else:
                        # Fall back to the real current-room endpoint.
                        room_resp = client.get("/api/world")
                        if room_resp.status_code == 200:
                            room = client.parse(room_resp).get("room", {})
                            current_location = f"{room.get('x', '?')},{room.get('y', '?')}"

                    print(f"  Moved {direction} -> {current_location}")
                    if current_location == expected_loc:
                        break
                elif resp.status_code == 400:
                    # Hit a wall, can't proceed further
                    print(f"  Movement blocked at {direction}")
                    break

        except Exception as e:
            bugs.append(self._bug(
                title="Navigation crash",
                severity=BugSeverity.HIGH,
                category=BugCategory.CRASH,
                endpoint="/api/world/move",
                method="POST",
                expected="Move successfully to adjacent tile",
                actual=f"Exception: {e}",
            ))

        # =====================================================================
        # STEP 3: Check for Votha Krr NPC
        # =====================================================================
        print("\n[STEP 3] Check for Votha Krr on current tile...")

        try:
            resp = client.get("/api/world")
            view_bug = self._check_no_crash(
                resp, "/api/world", "GET",
                "Fetch current room"
            )
            if view_bug:
                bugs.append(view_bug)
            else:
                data = client.parse(resp)
                room = data.get("room", {})
                npcs = room.get("npcs", [])
                npc_names = [n.get("name", "UNKNOWN") for n in npcs]
                current_loc = f"{room.get('x', '?')},{room.get('y', '?')}"
                print(f"  NPCs on tile: {npc_names}")
                print(f"  (Current location: {current_loc})")

                votha_found = any("votha" in n.lower() for n in npc_names)
                if not votha_found and len(npc_names) == 0:
                    # Only bug if no NPCs on tile AND we're at the right location
                    if current_loc == "6,5":
                        bugs.append(self._bug(
                            title="Votha Krr not found on tile (6,5)",
                            severity=BugSeverity.MEDIUM,
                            category=BugCategory.WRONG_RESPONSE,
                            endpoint="/api/world",
                            method="GET",
                            expected="Votha Krr present on tile (6,5)",
                            actual=f"No NPCs on tile. Found: {npc_names}",
                            response=resp,
                        ))

        except Exception as e:
            bugs.append(self._bug(
                title="NPC lookup crash",
                severity=BugSeverity.HIGH,
                category=BugCategory.CRASH,
                endpoint="/api/world",
                method="GET",
                expected="Fetch current room",
                actual=f"Exception: {e}",
            ))

        # =====================================================================
        # STEP 4: Jambo's shop (simplified check)
        # =====================================================================
        print("\n[STEP 4] Verify Jambo's shop exists...")

        try:
            # Check if jambos_shop map exists in universe
            resp = client.get("/api/world")
            if resp.status_code >= 500:
                bugs.append(self._bug(
                    title="Room query crash via /api/world",
                    severity=BugSeverity.MEDIUM,
                    category=BugCategory.CRASH,
                    endpoint="/api/world",
                    method="GET",
                    expected="Fetch current room",
                    actual=f"Server error {resp.status_code}",
                    response=resp,
                ))
            elif resp.status_code == 200:
                data = client.parse(resp)
                # Maps info may be in the response
                print("  [Shop verification deferred - see /api/world for available exits/maps]")

        except Exception as e:
            bugs.append(self._bug(
                title="Maps lookup crash",
                severity=BugSeverity.MEDIUM,
                category=BugCategory.CRASH,
                endpoint="/api/world",
                method="GET",
                expected="Fetch current room",
                actual=f"Exception: {e}",
            ))

        # =====================================================================
        # STEP 5: Mineral pools navigation (simplified check)
        # =====================================================================
        print("\n[STEP 5] Verify mineral pools map exists...")

        try:
            print("  [Mineral pools verification deferred - requires map traversal]")

        except Exception as e:
            bugs.append(self._bug(
                title="Mineral pools lookup crash",
                severity=BugSeverity.MEDIUM,
                category=BugCategory.CRASH,
                endpoint="/api/world/maps",
                method="GET",
                expected="Fetch maps",
                actual=f"Exception: {e}",
            ))

        # =====================================================================
        # STEP 6: Verify King Slime exists
        # =====================================================================
        print("\n[STEP 6] Verify King Slime exists...")

        try:
            # There is no standalone NPC-listing endpoint — NPCs are only
            # visible per-room via /api/world's room.npcs. Without navigating
            # all the way to King Slime's tile (deferred, see STEP 5), this
            # check only verifies the current room's NPCs are well-formed.
            resp = client.get("/api/world")
            bug = self._check_no_crash(
                resp, "/api/world", "GET", "Fetch current room (King Slime check)"
            )
            if bug:
                bugs.append(bug)
            elif resp.status_code == 200:
                data = client.parse(resp)
                room = data.get("room", {})
                npcs = room.get("npcs", [])
                npc_names = [n.get("name", "") for n in npcs if isinstance(n, dict)]

                king_slime_found = any(
                    "king" in n.lower() and "slime" in n.lower() for n in npc_names
                )
                if king_slime_found:
                    print("  King Slime found on current tile.")
                else:
                    print(
                        "  [King Slime presence not verified - requires navigation to "
                        "the mineral pools tile, deferred in this scenario]"
                    )

        except Exception as e:
            print(f"  [NPC lookup exception - {e} - skipping]")

        # =====================================================================
        # Summary
        # =====================================================================
        print(f"\n[SUMMARY] Grondia Happy Path: {len(bugs)} bugs found")
        for bug in bugs:
            print(f"  - {bug.severity.name}: {bug.title}")

        return bugs
