"""NPC chat (LLM conversation) endpoint checks (npc_chat_bp).

MYNX_LLM_ENABLED=0 is set by bug_hunt.py's bootstrap, so any conversation
that actually opens will run through the LLM-disabled fallback path rather
than making real network calls. This scenario mostly hunts for crashes on
bad/missing input; if a human NPC happens to be on the current tile it also
exercises a real open/respond/end/history round-trip.
"""

from typing import List, Optional

from .base import Scenario
from ..client import GameClient
from ..reporter import BugReport

_BAD_NPC = "harness_nonexistent_npc"


class NpcChatScenario(Scenario):
    name = "npc_chat"
    description = (
        "Verify NPC chat open/respond/end/history endpoints reject bad "
        "input gracefully (no 5xx)."
    )

    def run(self, client: GameClient) -> List[BugReport]:
        bugs = []

        # POST /api/npc/chat/open — missing npc_id ---------------------------
        resp = client.post("/api/npc/chat/open", json={})
        bug = self._check_rejected(
            resp, "/api/npc/chat/open", "POST",
            "NPC chat open without npc_id not rejected",
            "HTTP 400 when npc_id is absent",
        )
        if bug:
            bugs.append(bug)

        # POST /api/npc/chat/open — unknown npc_id, must not 500 -------------
        body = {"npc_id": _BAD_NPC}
        resp = client.post("/api/npc/chat/open", json=body)
        bug = self._check_no_crash(
            resp, "/api/npc/chat/open", "POST",
            f"Open chat with unknown npc '{_BAD_NPC}'", request_body=body,
        )
        if bug:
            bugs.append(bug)

        # POST /api/npc/chat/respond — missing npc_key/jean_text -------------
        resp = client.post("/api/npc/chat/respond", json={})
        bug = self._check_rejected(
            resp, "/api/npc/chat/respond", "POST",
            "NPC chat respond without npc_key/jean_text not rejected",
            "HTTP 400 when npc_key/jean_text is absent",
        )
        if bug:
            bugs.append(bug)

        # POST /api/npc/chat/respond — no open conversation, must not 500 ---
        body = {"npc_key": _BAD_NPC, "jean_text": "Hello there.", "jean_tone": "direct"}
        resp = client.post("/api/npc/chat/respond", json=body)
        bug = self._check_no_crash(
            resp, "/api/npc/chat/respond", "POST",
            "Respond with no open conversation", request_body=body,
        )
        if bug:
            bugs.append(bug)

        # POST /api/npc/chat/end — missing npc_key ---------------------------
        resp = client.post("/api/npc/chat/end", json={})
        bug = self._check_rejected(
            resp, "/api/npc/chat/end", "POST",
            "NPC chat end without npc_key not rejected",
            "HTTP 400 when npc_key is absent",
        )
        if bug:
            bugs.append(bug)

        # POST /api/npc/chat/end — no open conversation, must not 500 -------
        body = {"npc_key": _BAD_NPC}
        resp = client.post("/api/npc/chat/end", json=body)
        bug = self._check_no_crash(
            resp, "/api/npc/chat/end", "POST",
            "End a conversation that was never opened", request_body=body,
        )
        if bug:
            bugs.append(bug)

        # GET /api/npc/chat/history/<npc_key> — never-chatted npc ------------
        resp = client.get(f"/api/npc/chat/history/{_BAD_NPC}")
        bug = self._check_no_crash(
            resp, f"/api/npc/chat/history/{_BAD_NPC}", "GET",
            "History for an npc never chatted with",
        )
        if bug:
            bugs.append(bug)

        # Bonus: if a human/chattable NPC is present on the current tile,
        # exercise a real open -> respond -> end -> history round trip.
        real_npc_id = self._find_chattable_npc(client)
        if real_npc_id:
            resp = client.post("/api/npc/chat/open", json={"npc_id": real_npc_id})
            bug = self._check_no_crash(
                resp, "/api/npc/chat/open", "POST",
                f"Open chat with real npc '{real_npc_id}'",
                request_body={"npc_id": real_npc_id},
            )
            if bug:
                bugs.append(bug)
            elif resp.status_code == 200 and client.parse(resp).get("success"):
                body = {
                    "npc_key": real_npc_id,
                    "jean_text": "Hello there.",
                    "jean_tone": "direct",
                }
                resp = client.post("/api/npc/chat/respond", json=body)
                bug = self._check_no_crash(
                    resp, "/api/npc/chat/respond", "POST",
                    "Respond in a real open conversation", request_body=body,
                )
                if bug:
                    bugs.append(bug)

                resp = client.post(
                    "/api/npc/chat/end", json={"npc_key": real_npc_id}
                )
                bug = self._check_no_crash(
                    resp, "/api/npc/chat/end", "POST",
                    "End a real conversation",
                    request_body={"npc_key": real_npc_id},
                )
                if bug:
                    bugs.append(bug)

                resp = client.get(f"/api/npc/chat/history/{real_npc_id}")
                bug = self._check_no_crash(
                    resp, f"/api/npc/chat/history/{real_npc_id}", "GET",
                    "History for a real conversation",
                )
                if bug:
                    bugs.append(bug)

        return bugs

    def _find_chattable_npc(self, client: GameClient) -> Optional[str]:
        """Return the id of a friendly (non-hostile) NPC on the current tile.

        NPCSerializer.serialize() (used for room.npcs) never emits `friend`/
        `is_ally` — those flags only exist on the underlying NPC object, not
        in the JSON payload — so `is_hostile is False` is the only reliable
        signal actually present here.
        """
        resp = client.get("/api/world")
        if resp.status_code != 200:
            return None
        data = client.parse(resp)
        for npc in data.get("room", {}).get("npcs", []):
            if isinstance(npc, dict) and not npc.get("is_hostile", True):
                return npc.get("id") or npc.get("npc_id")
        return None
