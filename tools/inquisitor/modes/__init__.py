from tools.inquisitor.modes.happy_path import HappyPathMode
from tools.inquisitor.modes.bug_hunt import BugHuntMode

__all__ = ["HappyPathMode", "BugHuntMode"]


def get_mode(name: str, chapter_filter: str = None):
    """Return a mode instance by name ('happy-path' or 'bug-hunt')."""
    if name in ("happy-path", "happy_path"):
        return HappyPathMode(chapter_filter=chapter_filter)
    if name in ("bug-hunt", "bug_hunt"):
        return BugHuntMode()
    raise ValueError(f"Unknown mode: {name!r}. Choose 'happy-path' or 'bug-hunt'.")
