"""Inquisitor agent: Claude tool-use loop that drives game testing.

Uses claude-opus-4-6 with adaptive thinking.  Tool results are fed back as
user messages per the Anthropic multi-turn tool-use pattern.
"""

import json
import logging
import os
from typing import Any, Dict, Optional

import anthropic

from tools.inquisitor.reporter import (
    AgentFinding, BugSeverity, BugCategory, findings_to_bug_reports
)
from tools.inquisitor.game_tools import ToolResult, INTERNAL_TOOLS

logger = logging.getLogger("inquisitor.agent")

# Anthropic model — Opus 4.6 per project claude-api skill docs.
_MODEL = "claude-opus-4-6"
_MAX_OUTPUT_TOKENS = 4096

# ------------------------------------------------------------------
# Inquisitor
# ------------------------------------------------------------------


class Inquisitor:
    """Runs an AI-driven game testing session.

    Parameters
    ----------
    mode:
        A HappyPathMode or BugHuntMode instance.
    layer:
        An ApiLayer or BrowserLayer instance (already initialised).
    max_turns:
        Maximum number of Claude API round-trips before stopping.
    chapter_filter:
        Only relevant to happy_path; passed through for reporting.
    """

    def __init__(self, mode, layer, max_turns: int = 100, chapter_filter: Optional[str] = None):
        api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            raise EnvironmentError(
                "ANTHROPIC_API_KEY environment variable is not set.\n"
                "Export it before running the Inquisitor:\n"
                "  export ANTHROPIC_API_KEY=sk-ant-..."
            )

        self._client = anthropic.Anthropic(api_key=api_key)
        self.mode = mode
        self.layer = layer
        self.max_turns = max_turns
        self.chapter_filter = chapter_filter

        self.findings: list[AgentFinding] = []
        self._step = 0
        self._done = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> list:
        """Execute the full agent loop.  Returns list[AgentFinding]."""
        system = self.mode.system_prompt()
        tools = self.layer.tool_specs()

        initial_state = self.layer.get_initial_state()
        messages = [
            {
                "role": "user",
                "content": (
                    f"Game state at session start:\n\n{initial_state}\n\n"
                    f"Begin your {self.mode.display_name} testing session."
                ),
            }
        ]

        for turn in range(self.max_turns):
            if self._done:
                break

            try:
                response = self._client.messages.create(
                    model=_MODEL,
                    max_tokens=_MAX_OUTPUT_TOKENS,
                    thinking={"type": "adaptive"},
                    system=system,
                    tools=tools,
                    messages=messages,
                )
            except anthropic.APIError as exc:
                logger.error("Anthropic API error on turn %d: %s", turn, exc)
                # Record as a finding so the caller knows what happened.
                self.findings.append(AgentFinding(
                    mode=self.mode.name,
                    layer=self._layer_name(),
                    type="observation",
                    title=f"Anthropic API error on turn {turn}",
                    description=str(exc),
                    severity="medium",
                    chapter=self.chapter_filter,
                    step_number=self._step,
                    tool_call="(api)",
                    tool_input={},
                    tool_result={},
                ))
                break

            # Append the assistant response to the conversation.
            # Must use response.content (not just text) to preserve tool_use blocks
            # and any compaction blocks the API may inject.
            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn":
                break

            # Collect tool calls from this response.
            tool_results = []
            for block in response.content:
                if not hasattr(block, "type") or block.type != "tool_use":
                    continue

                self._step += 1
                result = self.layer.execute(block.name, block.input)

                # Implicit bug detection (5xx from any game call).
                if result.implicit_bug:
                    self._add_finding(
                        type_="bug",
                        title=result.implicit_bug_title,
                        description=f"Tool {block.name!r} returned a server error.",
                        severity="critical",
                        tool_name=block.name,
                        tool_input=dict(block.input),
                        tool_result=result.to_dict(),
                    )

                # Explicit agent reports / milestones.
                if block.name == "report_bug":
                    self._handle_report_bug(block.input, result)
                elif block.name == "mark_chapter_complete":
                    self._handle_chapter_complete(block.input)
                elif block.name == "mark_stuck":
                    self._handle_stuck(block.input)
                    self._done = True
                elif block.name == "done":
                    self._handle_done(block.input)
                    self._done = True

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result.to_content(),
                })

            if tool_results:
                messages.append({"role": "user", "content": tool_results})
            elif response.stop_reason == "tool_use":
                # stop_reason was tool_use but no tool_use blocks found (e.g. all
                # thinking blocks).  Break to avoid an infinite empty loop.
                break

        return self.findings

    # ------------------------------------------------------------------
    # Finding recorders
    # ------------------------------------------------------------------

    def _handle_report_bug(self, inputs: dict, result: ToolResult):
        self._add_finding(
            type_="bug",
            title=inputs.get("title", "(no title)"),
            description=inputs.get("description", ""),
            severity=inputs.get("severity", "medium"),
            tool_name="report_bug",
            tool_input=inputs,
            tool_result=result.to_dict(),
            extra={"evidence": inputs.get("evidence", "")},
        )

    def _handle_chapter_complete(self, inputs: dict):
        chapter = inputs.get("chapter", "unknown")
        self.findings.append(AgentFinding(
            mode=self.mode.name,
            layer=self._layer_name(),
            type="chapter_complete",
            title=f"Chapter {chapter} completed",
            description=inputs.get("notes", ""),
            severity=None,
            chapter=chapter,
            step_number=self._step,
            tool_call="mark_chapter_complete",
            tool_input=inputs,
            tool_result={},
        ))

    def _handle_stuck(self, inputs: dict):
        self._add_finding(
            type_="stuck",
            title="Agent stuck — cannot progress",
            description=inputs.get("reason", "(no reason given)"),
            severity="medium",
            tool_name="mark_stuck",
            tool_input=inputs,
            tool_result={},
        )

    def _handle_done(self, inputs: dict):
        self.findings.append(AgentFinding(
            mode=self.mode.name,
            layer=self._layer_name(),
            type="done",
            title="Session complete",
            description=inputs.get("summary", ""),
            severity=None,
            chapter=self.chapter_filter,
            step_number=self._step,
            tool_call="done",
            tool_input=inputs,
            tool_result={},
        ))

    def _add_finding(
        self,
        type_: str,
        title: str,
        description: str,
        severity: Optional[str],
        tool_name: str,
        tool_input: dict,
        tool_result: dict,
        extra: Optional[dict] = None,
    ):
        finding = AgentFinding(
            mode=self.mode.name,
            layer=self._layer_name(),
            type=type_,
            title=title,
            description=description,
            severity=severity,
            chapter=self.chapter_filter,
            step_number=self._step,
            tool_call=tool_name,
            tool_input=tool_input,
            tool_result=tool_result,
        )
        self.findings.append(finding)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _layer_name(self) -> str:
        return "browser" if hasattr(self.layer, "_browser") else "api"

    def bug_count(self) -> Dict[str, int]:
        bugs = findings_to_bug_reports(self.findings)
        return {
            "total": len(bugs),
            "critical": sum(1 for b in bugs if b.severity == BugSeverity.CRITICAL),
            "high": sum(1 for b in bugs if b.severity == BugSeverity.HIGH),
        }
