"""
All the loot tables for NPCs can be found here. These are called from the npc module.
"""

import inspect
import logging
import random
import src.items as items
import src.functions as functions
from src.narration import narrate

_log = logging.getLogger(__name__)


class Loot:
    def __init__(self):
        self.lev0 = {
            "Gold": {"chance": 50, "qty": "r25-50"},
            "Restorative": {"chance": 25, "qty": 1},
            "Draught": {"chance": 25, "qty": 1},
            "Equipment_0_1": {"chance": 10, "qty": 1},
        }

        self.lev1 = {
            "Gold": {"chance": 50, "qty": "r50-100"},
            "Restorative": {"chance": 25, "qty": "r1-3"},
            "Draught": {"chance": 25, "qty": "r1-3"},
            "Equipment_0_0": {"chance": 40, "qty": 1},
            "Equipment_1_0": {"chance": 10, "qty": 1},
        }

    @staticmethod
    def random_equipment(tile, level, enchantment):
        """Spawn one random equipment item of ``level`` on ``tile`` and return
        it, or None (spawning nothing) when no class qualifies."""
        candidates = []
        eq_level = int(level)
        for name, obj in inspect.getmembers(items, inspect.isclass):
            # Issue #647: the shared registry policy first. The level match
            # alone kept story items out only because they happen to have no
            # level; the policy keeps them out on purpose.
            if not items.is_randomly_selectable(obj):
                continue
            if getattr(obj, "level", None) == eq_level:
                candidates.append(name)
        if not candidates:
            # A level with no selectable equipment is no drop, not a
            # randint(0, -1) crash in the middle of a death (#674).
            _log.warning(
                "random_equipment: no selectable equipment at level %s", eq_level
            )
            return None
        select = random.randint(0, len(candidates) - 1)
        drop = tile.spawn_item(candidates[select], amt=1, hidden=False, hfactor=0)
        try:
            ench_pool = int(enchantment)
        except Exception:
            narrate(
                "###ERR: Enchantment couldn't be turned into an int! {}".format(
                    enchantment
                )
            )
            ench_pool = 0
        functions.add_random_enchantments(drop, ench_pool)
        return drop
