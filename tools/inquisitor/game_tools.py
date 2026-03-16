"""Tool specs (Claude API format) and ToolResult used by both layers."""

import json
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


# ---------------------------------------------------------------------------
# ToolResult — returned by layer.execute()
# ---------------------------------------------------------------------------

@dataclass
class ToolResult:
    """Wraps the outcome of a single agent tool call."""

    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    error: str = ""
    http_status: int = 200
    # If True the layer detected an implicit bug (e.g. 5xx response).
    implicit_bug: bool = False
    implicit_bug_title: str = ""

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "data": self.data,
            "error": self.error,
            "http_status": self.http_status,
        }

    def to_content(self) -> str:
        """Return JSON string suitable for Anthropic tool_result content."""
        return json.dumps(self.to_dict())

    @classmethod
    def ok(cls, data: dict) -> "ToolResult":
        return cls(success=True, data=data)

    @classmethod
    def err(cls, error: str, http_status: int = 400) -> "ToolResult":
        return cls(success=False, error=error, http_status=http_status)

    @classmethod
    def server_error(cls, error: str, title: str = "") -> "ToolResult":
        return cls(
            success=False,
            error=error,
            http_status=500,
            implicit_bug=True,
            implicit_bug_title=title or f"Server error: {error[:80]}",
        )


# ---------------------------------------------------------------------------
# Internal no-op result (report_bug, mark_*, done)
# ---------------------------------------------------------------------------

INTERNAL_TOOLS = frozenset({"report_bug", "mark_chapter_complete", "mark_stuck", "done"})

INTERNAL_ACK = ToolResult.ok({"recorded": True})


# ---------------------------------------------------------------------------
# Tool spec helpers
# ---------------------------------------------------------------------------

def _tool(name: str, description: str, props: dict, required: list) -> dict:
    return {
        "name": name,
        "description": description,
        "input_schema": {
            "type": "object",
            "properties": props,
            "required": required,
        },
    }


# ---------------------------------------------------------------------------
# Core game tools (available in both layers)
# ---------------------------------------------------------------------------

CORE_TOOLS: list = [
    _tool(
        "get_game_state",
        (
            "Get the current game state: player status, location with exits, "
            "inventory, and any pending events awaiting input."
        ),
        {},
        [],
    ),
    _tool(
        "move_player",
        "Move the player one step in a compass direction.",
        {
            "direction": {
                "type": "string",
                "description": "One of: north, south, east, west, up, down",
            }
        },
        ["direction"],
    ),
    _tool(
        "start_combat",
        "Start a combat encounter with the specified enemy.",
        {
            "enemy_id": {
                "type": "string",
                "description": "ID of the enemy to fight (from room NPC list)",
            }
        },
        ["enemy_id"],
    ),
    _tool(
        "get_combat_status",
        "Fetch current combat state: combatant HP, turn order, and suggested moves.",
        {},
        [],
    ),
    _tool(
        "execute_combat_move",
        "Execute a combat ability or attack.",
        {
            "move_id": {
                "type": "string",
                "description": "ID of the move to execute (from suggested_moves)",
            },
            "target_id": {
                "type": "string",
                "description": "ID of the combatant to target",
            },
        },
        ["move_id", "target_id"],
    ),
    _tool(
        "use_item",
        "Use a consumable item from the player's inventory.",
        {
            "item_id": {
                "type": "string",
                "description": "ID of the item (from inventory list)",
            }
        },
        ["item_id"],
    ),
    _tool(
        "equip_item",
        "Equip an item from inventory to the appropriate equipment slot.",
        {
            "item_id": {
                "type": "string",
                "description": "ID of the item to equip",
            }
        },
        ["item_id"],
    ),
    _tool(
        "interact",
        "Interact with an NPC or object in the current room.",
        {
            "target_id": {
                "type": "string",
                "description": "ID of the NPC or object (from room data)",
            }
        },
        ["target_id"],
    ),
    _tool(
        "trigger_room_events",
        "Trigger any events attached to the current room (e.g. on-entry spawners).",
        {},
        [],
    ),
    _tool(
        "submit_event_input",
        (
            "Respond to a pending story event.  Call get_pending_events first to "
            "discover the event_id, then supply user_input such as 'a', 'b', 'c', "
            "or 'continue'."
        ),
        {
            "event_id": {
                "type": "string",
                "description": "UUID of the pending event",
            },
            "user_input": {
                "type": "string",
                "description": (
                    "The player's response: 'a'/'b'/'c' for branching choices, "
                    "'continue' for narrative events"
                ),
            },
        },
        ["event_id", "user_input"],
    ),
    _tool(
        "get_pending_events",
        "Check whether any story events are waiting for player input.",
        {},
        [],
    ),
    _tool(
        "save_game",
        "Save the current game state to the cloud.",
        {},
        [],
    ),
    _tool(
        "report_bug",
        (
            "Report a bug discovered during testing.  Call this whenever you observe "
            "unexpected behaviour, crashes, wrong data, or broken game state."
        ),
        {
            "title": {
                "type": "string",
                "description": "Short descriptive title for the bug",
            },
            "severity": {
                "type": "string",
                "enum": ["critical", "high", "medium", "low"],
                "description": (
                    "critical=crash/data-loss, high=major feature broken, "
                    "medium=wrong but playable, low=cosmetic"
                ),
            },
            "description": {
                "type": "string",
                "description": "Detailed description of what went wrong",
            },
            "evidence": {
                "type": "string",
                "description": "What you did, what you expected, and what actually happened",
            },
        },
        ["title", "severity", "description", "evidence"],
    ),
    _tool(
        "done",
        "Signal that this testing session is complete.",
        {
            "summary": {
                "type": "string",
                "description": "Brief summary of what was tested and what was found",
            }
        },
        ["summary"],
    ),
]

# Happy-path-only tools
HAPPY_PATH_EXTRA_TOOLS: list = [
    _tool(
        "mark_chapter_complete",
        (
            "Mark a chapter as successfully completed.  Call this once the key story "
            "milestone for the chapter has been reached."
        ),
        {
            "chapter": {
                "type": "string",
                "description": "Chapter identifier, e.g. 'ch01' or 'ch02'",
            },
            "notes": {
                "type": "string",
                "description": "Notes on how the chapter ended and any observations",
            },
        },
        ["chapter", "notes"],
    ),
    _tool(
        "mark_stuck",
        (
            "Signal that you cannot make further progress.  Only call this after "
            "trying at least five different approaches."
        ),
        {
            "reason": {
                "type": "string",
                "description": "Detailed explanation of what you tried and why you are stuck",
            }
        },
        ["reason"],
    ),
]

# Browser-only tools
BROWSER_ONLY_TOOLS: list = [
    _tool(
        "take_screenshot",
        "Capture a screenshot of the current browser state.",
        {
            "label": {
                "type": "string",
                "description": "Descriptive label used as the filename",
            }
        },
        ["label"],
    ),
    _tool(
        "get_page_errors",
        (
            "Return JavaScript console errors and failed network requests "
            "collected since the session started."
        ),
        {},
        [],
    ),
    _tool(
        "click_element",
        "Click a UI element identified by a CSS selector.",
        {
            "selector": {
                "type": "string",
                "description": "CSS selector for the element to click",
            }
        },
        ["selector"],
    ),
    _tool(
        "get_visible_text",
        "Extract all visible text from the current page.",
        {},
        [],
    ),
]


def build_tool_list(mode_name: str, use_browser: bool) -> list:
    """Return the full tool list for the given mode and layer."""
    tools = list(CORE_TOOLS)
    if mode_name == "happy_path":
        tools.extend(HAPPY_PATH_EXTRA_TOOLS)
    if use_browser:
        tools.extend(BROWSER_ONLY_TOOLS)
    return tools
