#!/usr/bin/env python
"""Manual Inquisitor driver — same bootstrap as inquisitor.py but no Anthropic API.

Usage:
    python tools/manual_inquisitor.py <tool_name> [key=value ...]

Examples:
    python tools/manual_inquisitor.py get_game_state
    python tools/manual_inquisitor.py move_player direction=north
    python tools/manual_inquisitor.py start_combat enemy_id=fake_enemy_001
    python tools/manual_inquisitor.py execute_combat_move move_id=basic_attack target_id=goblin_1
    python tools/manual_inquisitor.py submit_event_input event_id=abc user_input=a
    python tools/manual_inquisitor.py get_pending_events
    python tools/manual_inquisitor.py trigger_room_events
    python tools/manual_inquisitor.py use_item item_id=fake_item_999
    python tools/manual_inquisitor.py equip_item item_id=fake_item_999
    python tools/manual_inquisitor.py interact target_id=fake_npc
    python tools/manual_inquisitor.py save_game
    python tools/manual_inquisitor.py get_combat_status
"""

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(1, str(SRC_DIR))

os.environ.setdefault("MYNX_LLM_ENABLED", "0")
os.environ.setdefault("MYNX_FALLBACK_DELAY", "0")
os.environ.setdefault("MYNX_LLM_PROVIDER", "none")

# tkinter stub for headless
if "tkinter" not in sys.modules:
    import types as _types
    _tk = _types.ModuleType("tkinter")
    _tk.Tk = type("Tk", (), {k: (lambda s, *a, **kw: None) for k in
                              ["__init__", "title", "geometry", "resizable",
                               "configure", "after", "destroy", "mainloop"]})
    _tk.Canvas = type("Canvas", (), {k: (lambda s, *a, **kw: None) for k in
                                      ["__init__", "pack", "delete",
                                       "create_text", "create_rectangle"]})
    _tk.font = _types.ModuleType("tkinter.font")
    _tk.font.Font = type("Font", (), {"__init__": lambda s, *a, **kw: None,
                                       "measure": lambda s, *a: 8})
    _tk.END = "end"
    sys.modules["tkinter"] = _tk
    sys.modules["tkinter.font"] = _tk.font

try:
    import src.functions as _f
    sys.modules["functions"] = _f
except Exception:
    pass

for _n in ["animations", "genericng", "items", "states", "enchant_tables",
           "objects", "loot_tables", "actions", "tiles", "universe", "positions",
           "moves", "combatant", "npc", "skilltree", "switch", "player"]:
    if _n not in sys.modules:
        try:
            _m = __import__(f"src.{_n}", fromlist=["*"])
            sys.modules[_n] = _m
        except Exception:
            pass

for _n in ("combat", "events", "shop_conditions"):
    if _n not in sys.modules:
        try:
            sys.modules[_n] = __import__(f"src.{_n}", fromlist=["*"])
        except Exception:
            pass

from src.api.app import create_app
from src.api.config import TestingConfig
from tools.inquisitor.api_layer import ApiLayer

app, _ = create_app(TestingConfig)
layer = ApiLayer(app=app, mode_name="bug_hunt")

# Parse args: tool_name key=value ...
if len(sys.argv) < 2:
    print(__doc__)
    sys.exit(1)

tool_name = sys.argv[1]
inputs = {}
for arg in sys.argv[2:]:
    if "=" in arg:
        k, v = arg.split("=", 1)
        inputs[k] = v
    else:
        print(f"[manual_inquisitor] Bad argument (expected key=value): {arg}", file=sys.stderr)
        sys.exit(1)

result = layer.execute(tool_name, inputs)
print(json.dumps({
    "tool": tool_name,
    "inputs": inputs,
    "success": result.success,
    "http_status": result.http_status,
    "data": result.data,
    "error": result.error,
    "implicit_bug": result.implicit_bug,
    "implicit_bug_title": result.implicit_bug_title,
}, indent=2))

layer.teardown()
