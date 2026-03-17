"""Self-drive runner: executes the Inquisitor bug-hunt probe sequence.

Runs the eight probe categories from bug_hunt.txt as a deterministic script
and returns structured findings the calling agent can act on.

Usage (from within Python):
    layer = BrowserLayer(headless=True)
    runner = SelfDriveRunner(layer)
    findings = runner.run()
    layer.teardown()

CLI (via tools/inquisitor.py):
    python tools/inquisitor.py [--no-browser] [--headless] [--output FILE]
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List

from tools.inquisitor.game_tools import ToolResult
from tools.inquisitor.reporter import AgentFinding, BugSeverity, BugCategory


# ---------------------------------------------------------------------------
# Probe record
# ---------------------------------------------------------------------------

@dataclass
class ProbeResult:
    """Outcome of a single adversarial probe."""

    name: str
    tool: str
    inputs: Dict[str, Any]
    result: ToolResult
    category: str

    @property
    def is_bug(self) -> bool:
        return self.result.implicit_bug

    def to_finding(self, layer: str = "api") -> AgentFinding:
        return AgentFinding(
            mode="bug_hunt",
            layer=layer,
            type="bug",
            title=self.result.implicit_bug_title or f"5xx on {self.tool}",
            description=(
                f"Probe '{self.name}' triggered a server error.\n"
                f"Tool: {self.tool}\n"
                f"Inputs: {json.dumps(self.inputs)}\n"
                f"Response ({self.result.http_status}): {self.result.error}"
            ),
            severity="critical",
            chapter=None,
            step_number=0,
            tool_call=self.tool,
            tool_input=self.inputs,
            tool_result=self.result.to_dict(),
        )


# ---------------------------------------------------------------------------
# Self-drive runner
# ---------------------------------------------------------------------------

class SelfDriveRunner:
    """Runs the eight bug-hunt probe categories deterministically.

    The probe sequence mirrors the categories in tools/inquisitor/prompts/bug_hunt.txt
    so self-drive and AI-drive sessions exercise the same surface area.

    Parameters
    ----------
    layer:
        An initialised ApiLayer or BrowserLayer.
    verbose:
        If True, print a line per probe as it executes.
    """

    def __init__(self, layer, verbose: bool = True):
        self._layer = layer
        self._verbose = verbose
        self._probes: List[ProbeResult] = []
        self._extra_findings: List[AgentFinding] = []
        self._browser_mode = hasattr(layer, "_page")  # BrowserLayer has _page

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> List[AgentFinding]:
        """Run all probe categories and return a list of AgentFinding."""
        self._log("Starting self-drive bug-hunt session")
        self._log(f"Layer: {'browser' if self._browser_mode else 'api'}")

        # Fetch initial state
        initial_raw = self._layer.get_initial_state()
        initial = json.loads(initial_raw)
        self._log(f"Initial state — HP: {initial.get('stats', {}).get('hp')} | "
                  f"gold: {initial.get('status', {}).get('gold')}")

        self._run_navigation()
        self._run_combat()
        self._run_inventory()
        self._run_events()
        self._run_saves()
        self._run_interactions()
        self._run_malformed_inputs()
        self._run_state_integrity()

        if self._browser_mode:
            self._run_browser_specific()

        return self._collect_findings()

    # ------------------------------------------------------------------
    # Category 1: Navigation
    # ------------------------------------------------------------------

    def _run_navigation(self):
        self._section("1. NAVIGATION")
        self._probe("move: non-existent direction (north)", "move_player",
                    direction="north", category="navigation")
        self._probe("move: gibberish direction", "move_player",
                    direction="xyzzy_invalid_direction", category="navigation")
        self._probe("move: empty direction string", "move_player",
                    direction="", category="navigation")
        self._probe("move: numeric direction", "move_player",
                    direction="42", category="navigation")

    # ------------------------------------------------------------------
    # Category 2: Combat
    # ------------------------------------------------------------------

    def _run_combat(self):
        self._section("2. COMBAT")
        self._probe("start combat: fake enemy_id", "start_combat",
                    enemy_id="fake_enemy_001", category="combat")
        self._probe("combat status: no active combat", "get_combat_status",
                    category="combat")
        self._probe("execute move: no active combat", "execute_combat_move",
                    move_id="attack", target_id="goblin_001", category="combat")
        self._probe("execute move: empty move_id", "execute_combat_move",
                    move_id="", target_id="", category="combat")
        self._probe("execute move: missing both fields", "execute_combat_move",
                    move_id="nonexistent_move_999", target_id="nonexistent_target",
                    category="combat")

    # ------------------------------------------------------------------
    # Category 3: Inventory
    # ------------------------------------------------------------------

    def _run_inventory(self):
        self._section("3. INVENTORY")
        self._probe("use item: nonexistent item_id", "use_item",
                    item_id="fake_item_999", category="inventory")
        self._probe("use item: empty item_id", "use_item",
                    item_id="", category="inventory")
        self._probe("equip item: nonexistent item_id", "equip_item",
                    item_id="fake_item_999", category="inventory")
        self._probe("equip item: empty item_id", "equip_item",
                    item_id="", category="inventory")

    # ------------------------------------------------------------------
    # Category 4: Events
    # ------------------------------------------------------------------

    def _run_events(self):
        self._section("4. EVENTS")
        self._probe("submit event input: fake event_id", "submit_event_input",
                    event_id="00000000-dead-beef-0000-000000000000",
                    user_input="a", category="events")
        self._probe("submit event input: empty user_input", "submit_event_input",
                    event_id="00000000-dead-beef-0000-000000000000",
                    user_input="", category="events")
        self._probe("get pending events", "get_pending_events",
                    category="events")
        # Rapid-fire room event trigger
        for i in range(1, 4):
            self._probe(f"trigger room events: call #{i}", "trigger_room_events",
                        category="events")

    # ------------------------------------------------------------------
    # Category 5: Saves
    # ------------------------------------------------------------------

    def _run_saves(self):
        self._section("5. SAVES")
        self._probe("save game: first save", "save_game", category="saves")
        self._probe("save game: rapid second save", "save_game", category="saves")

    # ------------------------------------------------------------------
    # Category 6: Interactions
    # ------------------------------------------------------------------

    def _run_interactions(self):
        self._section("6. INTERACTIONS")
        self._probe("interact: nonexistent target_id", "interact",
                    target_id="fake_npc_999", category="interaction")
        self._probe("interact: empty target_id", "interact",
                    target_id="", category="interaction")

    # ------------------------------------------------------------------
    # Category 7: Malformed / empty inputs
    # ------------------------------------------------------------------

    def _run_malformed_inputs(self):
        self._section("7. MALFORMED INPUTS")
        # Numeric values where strings expected
        self._probe("move: numeric value for direction", "move_player",
                    direction="0", category="malformed")
        self._probe("use item: numeric item_id", "use_item",
                    item_id="0", category="malformed")
        self._probe("start combat: empty enemy_id", "start_combat",
                    enemy_id="", category="malformed")

    # ------------------------------------------------------------------
    # Category 8: State integrity
    # ------------------------------------------------------------------

    def _run_state_integrity(self):
        self._section("8. STATE INTEGRITY")
        # State should still be valid after all the bad input above
        r = self._probe("get_game_state after probes", "get_game_state",
                        category="state_integrity")
        if not r.result.success:
            self._log("  WARNING: get_game_state failed after probe sequence — "
                      "possible state corruption")

        # Interleaved abuse: try to move while in a bad state
        self._probe("move after bad inputs", "move_player",
                    direction="south", category="state_integrity")

        # Verify state is still coherent
        r2 = self._probe("get_game_state final check", "get_game_state",
                         category="state_integrity")
        if r2.result.success:
            stats = r2.result.data.get("stats", {})
            hp = stats.get("hp")
            self._log(f"  Final state — HP: {hp} (should be non-negative integer)")
            if hp is not None and (not isinstance(hp, (int, float)) or hp < 0):
                self._log(f"  ANOMALY: unexpected HP value: {hp!r}")

    # ------------------------------------------------------------------
    # Browser-specific probes (BrowserLayer only)
    # ------------------------------------------------------------------

    def _run_browser_specific(self):
        self._section("BROWSER-SPECIFIC")

        # Screenshot of current state
        self._layer.execute("take_screenshot", {"label": "self_drive_final_state"})
        self._log("  Screenshot taken")

        # Visible text sanity check
        vis = self._layer.execute("get_visible_text", {})
        text = vis.data.get("text", "")
        self._log(f"  Visible text ({len(text)} chars): {text[:100]!r}...")

        # Page errors — split into significant vs noise
        err_r = self._layer.execute("get_page_errors", {})
        sig_console = err_r.data.get("console_errors", [])
        sig_net = err_r.data.get("network_failures", [])
        noise = err_r.data.get("known_noise", {})
        self._log(f"  Significant JS errors: {len(sig_console)}, "
                  f"network failures: {len(sig_net)}")
        self._log(f"  Known noise filtered: "
                  f"{len(noise.get('console', []))} console, "
                  f"{len(noise.get('network', []))} network")

        for e in sig_console[:5]:
            self._log(f"    [JS {e.get('type')}] {str(e.get('text', ''))[:100]}")
        for f in sig_net[:3]:
            self._log(f"    [NET] {f.get('method')} {f.get('url', '')[:80]}")

        # Record significant browser errors as findings
        if sig_console:
            self._manual_finding(
                title=f"{len(sig_console)} significant JS console error(s)",
                description="\n".join(
                    f"[{e.get('type')}] {e.get('text', '')[:200]}"
                    for e in sig_console[:5]
                ),
                severity=BugSeverity.HIGH,
                category=BugCategory.UI,
            )
        if sig_net:
            self._manual_finding(
                title=f"{len(sig_net)} significant network failure(s)",
                description="\n".join(
                    f"{f.get('method')} {f.get('url', '')[:120]} — {f.get('failure', '')}"
                    for f in sig_net[:3]
                ),
                severity=BugSeverity.MEDIUM,
                category=BugCategory.UI,
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _probe(self, name: str, tool: str, category: str, **inputs) -> ProbeResult:
        result = self._layer.execute(tool, inputs)
        pr = ProbeResult(name=name, tool=tool, inputs=inputs, result=result,
                         category=category)
        self._probes.append(pr)

        if self._verbose:
            tag = "BUG(5xx)" if pr.is_bug else ("ok" if result.success else f"err-{result.http_status}")
            msg = result.implicit_bug_title or result.error or "success"
            self._log(f"  [{tag}] {name}: {msg[:100]}")

        return pr

    def _manual_finding(self, title: str, description: str,
                        severity: BugSeverity, category: BugCategory):
        """Add a finding that didn't come from a ToolResult implicit_bug."""
        # Build the AgentFinding directly rather than routing through ProbeResult
        # so we can set the correct severity (not always "critical").
        sev_str = severity.value if hasattr(severity, "value") else str(severity)
        self._extra_findings.append(AgentFinding(
            mode="bug_hunt",
            layer="browser",
            type="bug",
            title=title,
            description=description,
            severity=sev_str,
            chapter=None,
            step_number=0,
            tool_call="_browser",
            tool_input={},
            tool_result={},
        ))

    def _collect_findings(self) -> List[AgentFinding]:
        layer = "browser" if self._browser_mode else "api"
        bugs = [p.to_finding(layer) for p in self._probes if p.is_bug]
        bugs.extend(self._extra_findings)
        total = len(self._probes)
        bug_count = len(bugs)
        self._log(f"\nProbes run: {total}  |  Bugs flagged: {bug_count}")
        return bugs

    def _section(self, label: str):
        if self._verbose:
            print(f"\n=== {label} ===")

    def _log(self, msg: str):
        if self._verbose:
            print(msg)
