"""Bug-hunt mode: Claude adversarially probes the game for bugs."""

from pathlib import Path

_PROMPT_FILE = Path(__file__).resolve().parent.parent / "prompts" / "bug_hunt.txt"


class BugHuntMode:
    """Configuration for the adversarial bug-hunt testing mode."""

    name = "bug_hunt"
    display_name = "Bug Hunt"

    def system_prompt(self) -> str:
        return _PROMPT_FILE.read_text(encoding="utf-8")
