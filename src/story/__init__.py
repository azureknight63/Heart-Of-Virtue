"""The story chapters (``chNN.py``) and the pieces they share."""

import logging
from importlib import import_module

logger = logging.getLogger(__name__)


#: Each entry is ``("<module>", "<function>")``: one save repair, named rather
#: than imported, so this module can be imported without loading a chapter and
#: so a chapter that fails to import is skipped like any other failing repair.
#: Each function takes the player and returns a count of what it repaired.
SAVE_REPAIRS = (
    ("src.story.ch02", "fold_legacy_cleansed_descriptions"),
    ("src.story.ch03", "wire_ferry_landing_completers"),
)


def repair_loaded_save(player):
    """Bring a player restored from a save up to date with the story code;
    returns how much the repairs changed, summed over them.

    The one hook the load path calls after unpickling, so a new save repair
    joins ``SAVE_REPAIRS`` rather than becoming another import in the API. A
    repair only tidies what an older build left behind, so one that raises is
    logged and skipped and never costs the player the load.
    """
    repaired = 0
    for module_name, repair_name in SAVE_REPAIRS:
        try:
            repair = getattr(import_module(module_name), repair_name)
            repaired += repair(player)
        except Exception:
            logger.warning("Save repair %s skipped", repair_name, exc_info=True)
    return repaired
