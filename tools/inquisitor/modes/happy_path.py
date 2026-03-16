"""Happy-path mode: Claude plays through the story chapter by chapter."""

from pathlib import Path

_PROMPT_FILE = Path(__file__).resolve().parent.parent / "prompts" / "happy_path.txt"


class HappyPathMode:
    """Configuration for the happy-path testing mode."""

    name = "happy_path"
    display_name = "Happy Path"

    def __init__(self, chapter_filter: str = None):
        self.chapter_filter = chapter_filter  # e.g. "ch01" to run only that chapter

    def system_prompt(self) -> str:
        base = _PROMPT_FILE.read_text(encoding="utf-8")
        if self.chapter_filter:
            base += (
                f"\n\nCHAPTER FILTER\n==============\n"
                f"Only complete chapter {self.chapter_filter!r}.  "
                f"Call done() immediately after that chapter is marked complete.\n"
            )
        return base
