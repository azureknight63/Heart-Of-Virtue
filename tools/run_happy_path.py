#!/usr/bin/env python
"""Manual happy-path runner for Heart of Virtue.

Drives the same API endpoints the Inquisitor would use, without requiring
Anthropic API credits.  Follows the chapter goals in happy_path.txt:
  - Ch01: Verdette Caverns / Dark Grotto — defeat Rock Rumbler, choose option "a"
  - Ch02: Grondia — speak to Elder Votha Krr, receive quest
"""

import json
import os
import sys
import types
from pathlib import Path

# --------------------------------------------------------------------------
# Bootstrap (mirrors inquisitor.py)
# --------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
for p in (str(ROOT), str(SRC_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

os.environ.setdefault("MYNX_LLM_ENABLED", "0")
os.environ.setdefault("MYNX_FALLBACK_DELAY", "0")
os.environ.setdefault("MYNX_LLM_PROVIDER", "none")

# Tkinter stub
if "tkinter" not in sys.modules:
    _tk = types.ModuleType("tkinter")
    _stub_noop = lambda s, *a, **k: None
    _tk.Tk = type("Tk", (), {name: _stub_noop for name in
                             ("__init__", "title", "geometry", "resizable",
                              "configure", "after", "destroy", "mainloop")})
    _tk.Canvas = type("Canvas", (), {name: _stub_noop for name in
                                     ("__init__", "pack", "delete",
                                      "create_text", "create_rectangle")})
    _tk.font = types.ModuleType("tkinter.font")
    _tk.font.Font = type("Font", (), {"__init__": _stub_noop,
                                       "measure": lambda s, *a: 8})
    _tk.END = "end"
    sys.modules["tkinter"] = _tk
    sys.modules["tkinter.font"] = _tk.font

try:
    import src.functions as _fn
    sys.modules["functions"] = _fn
except Exception as e:
    print(f"[runner] WARNING: could not shim 'functions': {e}")

for _name in ("animations", "genericng", "items", "states", "enchant_tables",
              "objects", "loot_tables", "actions", "tiles", "universe",
              "positions", "moves", "combatant", "npc", "skilltree",
              "switch", "player"):
    if _name not in sys.modules:
        try:
            _mod = __import__(f"src.{_name}", fromlist=["*"])
            sys.modules[_name] = _mod
            sys.modules[f"src.{_name}"] = _mod
        except Exception:
            pass

for _name in ("combat", "events", "shop_conditions"):
    if _name not in sys.modules:
        try:
            sys.modules[_name] = __import__(f"src.{_name}", fromlist=["*"])
        except Exception:
            pass

from src.api.app import create_app
from src.api.config import TestingConfig
from tools.harness.client import GameClient

# --------------------------------------------------------------------------
# Bug tracker
# --------------------------------------------------------------------------

bugs = []


def _bug(severity, title, description, evidence=""):
    bugs.append({
        "severity": severity, "title": title,
        "description": description, "evidence": evidence,
    })
    print(f"  *** BUG [{severity.upper()}]: {title}")
    print(f"      {description}")
    if evidence:
        print(f"      Evidence: {evidence[:300]}")


def _get(client, path):
    resp = client.get(path)
    data = _parse(client, resp)
    if resp.status_code >= 500:
        _bug("critical", f"5xx on GET {path}",
             f"HTTP {resp.status_code}", str(data)[:300])
    return resp, data


def _post(client, path, body=None):
    resp = client.post(path, json=body or {})
    data = _parse(client, resp)
    if resp.status_code >= 500:
        _bug("critical", f"5xx on POST {path}",
             f"HTTP {resp.status_code}", str(data)[:300])
    return resp, data


def _parse(client, resp):
    return client.parse(resp)


# --------------------------------------------------------------------------
# Main happy-path walk
# --------------------------------------------------------------------------

def run():
    print("=== Heart of Virtue — Manual Happy-Path Runner ===\n")

    app, _ = create_app(TestingConfig)
    client = GameClient(app)
    client.create_session("happy_path_runner")
    print("Session created OK\n")

    # ---- 1. Player status ----
    print("--- Step 1: Player status ---")
    resp, status_data = _get(client, "/api/status")
    if resp.status_code == 200:
        s = status_data.get("status", {})
        print(f"  Name: {s.get('name','?')}  HP: {s.get('hp','?')}/{s.get('max_hp','?')}  Level: {s.get('level','?')}")
    else:
        _bug("critical", "/api/status failed at start",
             f"HTTP {resp.status_code}", str(status_data)[:300])

    # ---- 2. World/location ----
    print("\n--- Step 2: World location ---")
    resp, world_data = _get(client, "/api/world")
    if resp.status_code == 200:
        room = world_data.get("room", world_data)
        print(f"  Location: {room.get('name', room.get('map_id','?'))}")
        print(f"  Exits: {list(room.get('exits', {}).keys())}")
        npcs = room.get("npcs", [])
        print(f"  NPCs: {[(n.get('id','?'), n.get('name','?')) for n in npcs]}")
        items_here = room.get("items", [])
        print(f"  Items here: {[(i.get('id','?'), i.get('name','?')) for i in items_here]}")
    elif resp.status_code == 404 and "Invalid player position" in str(world_data):
        _bug("critical",
             "Player has no valid starting map — all world endpoints fail",
             "GET /api/world → 404 'Invalid player position'. "
             "Universe.starting_map_default is None and no map named 'default' exists. "
             "The session manager silently falls back to player.map = None because "
             "config_dev.ini is missing and there is no startmap configured for test sessions.",
             str(world_data)[:300])
        print("  CRITICAL: world init failed — see bug report above.")
        # Still run non-world checks before returning
        _check_inventory(client)
        _check_saves(client)
        _print_summary()
        return bugs
    else:
        _bug("high", "/api/world failed unexpectedly",
             f"HTTP {resp.status_code}", str(world_data)[:300])

    # ---- 3. Pending events ----
    print("\n--- Step 3: Pending events ---")
    resp, ev_data = _get(client, "/api/world/events/pending")
    if resp.status_code == 200:
        pending = ev_data.get("events", [])
        print(f"  Pending: {len(pending)}")
        _drain_events(client, max_rounds=10, default_choice="continue")
    else:
        _bug("high", "pending events endpoint error",
             f"HTTP {resp.status_code}", str(ev_data)[:300])

    # ---- 4. Trigger room events ----
    print("\n--- Step 4: Trigger room events ---")
    resp, evr = _post(client, "/api/world/events")
    print(f"  HTTP {resp.status_code}  {str(evr)[:120]}")
    _drain_events(client, max_rounds=10, default_choice="continue")

    # ---- 5. Find & fight Rock Rumbler ----
    print("\n--- Step 5: Explore and find Rock Rumbler ---")
    rock_rumbler_id = _find_npc_by_keyword(client, "rumbler", max_moves=20)
    if rock_rumbler_id:
        print(f"\n--- Step 6: Combat with Rock Rumbler ({rock_rumbler_id}) ---")
        resp_c, cdata = _post(client, "/api/combat/start",
                              {"enemy_id": rock_rumbler_id})
        if resp_c.status_code == 200:
            print(f"  Combat started.")
            _run_combat(client, max_rounds=40)
        else:
            _bug("high", "combat/start rejected",
                 f"HTTP {resp_c.status_code}", str(cdata)[:300])
    else:
        print("  Rock Rumbler not found — map exploration exhausted")
        _bug("high",
             "Rock Rumbler not found on dark-grotto map during exploration",
             "Walked all accessible tiles; no NPC with 'rumbler' in id/name found. "
             "Either the NPC is not placed on the map or exploration failed.")

    # ---- 7. Post-combat events — choose 'a' for Gorran ----
    print("\n--- Step 7: Post-combat events (choose 'a' for Gorran) ---")
    _drain_events(client, max_rounds=15, default_choice="a")

    # ---- 8. Verify story state ----
    print("\n--- Step 8: Story flags after ch01 milestone ---")
    resp, state = _get(client, "/api/world")
    if resp.status_code == 200:
        room2 = state.get("room", state)
        print(f"  Location: {room2.get('name', room2.get('map_id','?'))}")
        print(f"  Exits: {list(room2.get('exits', {}).keys())}")

    # ---- 9. Inventory ----
    print("\n--- Step 9: Inventory ---")
    _check_inventory(client)

    # ---- 10. Quests ----
    print("\n--- Step 10: Quest progression ---")
    resp, qdata = _get(client, "/api/quests/progression")
    if resp.status_code == 200:
        print(f"  Quest progression: {json.dumps(qdata)[:300]}")
    else:
        print(f"  /api/quests/progression HTTP {resp.status_code}: {str(qdata)[:120]}")
        # Try active quests via npc route
        resp2, qdata2 = _get(client, "/api/npc/quests/active")
        if resp2.status_code == 200:
            print(f"  NPC active quests: {json.dumps(qdata2)[:300]}")
        else:
            print(f"  /api/npc/quests/active HTTP {resp2.status_code}: {str(qdata2)[:120]}")

    # ---- 11. Save ----
    print("\n--- Step 11: Save game ---")
    _check_saves(client)

    client.destroy_session()
    _print_summary()
    return bugs


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _find_npc_by_keyword(client, keyword, max_moves=20):
    """Explore the map and return first NPC id whose id or name contains keyword."""
    visited = set()
    current_pos = _current_pos(client)
    if current_pos:
        visited.add(current_pos)

    for _ in range(max_moves + 1):
        resp, world = _get(client, "/api/world")
        if resp.status_code != 200:
            break
        room = world.get("room", world)
        npcs = room.get("npcs", [])
        for n in npcs:
            nid = n.get("id", "")
            nname = n.get("name", "")
            if keyword.lower() in nid.lower() or keyword.lower() in nname.lower():
                return nid

        exits = room.get("exits", {})
        moved = False
        for direction in exits:
            dest = exits[direction]
            dest_key = f"{dest.get('x',0)},{dest.get('y',0)}" if isinstance(dest, dict) else str(dest)
            if dest_key not in visited:
                resp_m, _ = _post(client, "/api/world/move", {"direction": direction})
                if resp_m.status_code == 200:
                    pos = _current_pos(client)
                    if pos:
                        visited.add(pos)
                    _drain_events(client, max_rounds=3)
                    moved = True
                    break
        if not moved:
            # revisit
            for direction in exits:
                resp_m, mv = _post(client, "/api/world/move", {"direction": direction})
                if resp_m.status_code == 200:
                    _drain_events(client, max_rounds=3)
                    break
            else:
                break
    return None


def _current_pos(client):
    resp, world = _get(client, "/api/world")
    if resp.status_code == 200:
        room = world.get("room", world)
        x = room.get("x")
        y = room.get("y")
        if x is not None and y is not None:
            return f"{x},{y}"
    return None


def _drain_events(client, max_rounds=10, default_choice="continue"):
    """Submit all pending events."""
    for _ in range(max_rounds):
        resp, ev_data = _get(client, "/api/world/events/pending")
        if resp.status_code != 200:
            break
        events = ev_data.get("events", [])
        if not events:
            break
        for ev in events:
            eid = ev.get("event_id") or ev.get("id", "")
            choices = ev.get("choices") or []
            inp = default_choice if (not choices or default_choice in choices) else choices[0]
            print(f"  [event] {ev.get('name','?')} (id={eid}) → '{inp}'")
            resp2, res2 = _post(client, "/api/world/events/input",
                                {"event_id": eid, "user_input": inp})
            if resp2.status_code >= 400 and resp2.status_code < 500:
                print(f"    [warn] {resp2.status_code}: {str(res2)[:120]}")
            elif resp2.status_code >= 500:
                _bug("critical", "event input 5xx",
                     f"POST /api/world/events/input returned {resp2.status_code}",
                     str(res2)[:300])


def _run_combat(client, max_rounds=40):
    """Execute combat loop until no longer active or max_rounds."""
    for rnd in range(max_rounds):
        resp, status = _get(client, "/api/combat/status")
        if resp.status_code != 200:
            _bug("critical", "combat/status failed mid-combat",
                 f"HTTP {resp.status_code}", str(status)[:300])
            return

        in_combat = status.get("active", status.get("in_combat", False))
        if not in_combat:
            print(f"  Combat ended at round {rnd}.")
            _drain_events(client, max_rounds=5, default_choice="a")
            return

        moves = status.get("suggested_moves") or status.get("available_moves") or []
        if not moves:
            _bug("high", "no moves available mid-combat",
                 "suggested_moves empty", str(status)[:300])
            return

        move = moves[0]
        move_id = move.get("id") or move.get("move_id", "")
        combatants = status.get("combatants", [])
        target_id = next(
            (c.get("id", "") for c in combatants
             if not c.get("is_player", True) and c.get("hp", 1) > 0),
            "",
        )
        if not target_id:
            print(f"  Round {rnd + 1}: no enemy target — combat probably over")
            _drain_events(client, max_rounds=5, default_choice="a")
            return

        print(f"  Round {rnd + 1}: {move_id} → {target_id}")
        resp_m, mv = _post(client, "/api/combat/move",
                           {"move_id": move_id, "target_id": target_id})
        if resp_m.status_code >= 400:
            _bug("high", "combat move failed",
                 f"move {move_id!r} returned {resp_m.status_code}",
                 str(mv)[:300])
            return
        _drain_events(client, max_rounds=3, default_choice="a")

    _bug("high", "combat did not end within max_rounds",
         f"Still active after {max_rounds} rounds")


def _check_inventory(client):
    resp, inv = _get(client, "/api/inventory")
    if resp.status_code == 200:
        items = inv.get("items", [])
        print(f"  Items ({len(items)}): {[(i.get('name','?'), i.get('id','?')) for i in items[:5]]}")
    else:
        print(f"  /api/inventory HTTP {resp.status_code}: {str(inv)[:120]}")


def _check_saves(client):
    resp, sv = _post(client, "/api/saves", {"name": "happy_path_test"})
    if resp.status_code not in (200, 201):
        if resp.status_code == 401:
            print(f"  Save → 401 (no cloud account in test env — expected)")
        else:
            _bug("high", "save game failed",
                 f"HTTP {resp.status_code}", str(sv)[:300])
    else:
        print(f"  Save OK: {json.dumps(sv)[:120]}")


def _print_summary():
    print("\n" + "=" * 60)
    print("HAPPY PATH SUMMARY")
    print("=" * 60)
    if not bugs:
        print("No bugs found.")
    else:
        print(f"{len(bugs)} bug(s) found:\n")
        for i, b in enumerate(bugs, 1):
            print(f"  {i}. [{b['severity'].upper()}] {b['title']}")
            print(f"     {b['description']}")
            if b.get("evidence"):
                print(f"     Evidence: {b['evidence'][:250]}")
            print()


if __name__ == "__main__":
    result = run()
    sys.exit(1 if any(b["severity"] in ("critical", "high") for b in result) else 0)
