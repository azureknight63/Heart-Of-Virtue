'''
All of the loot tables for NPCs can be found here. These are called from the npc module.
'''

import inspect, random
import items


class Loot:
    def __init__(self):
        self.lev0 = {
            "Gold": {
                "chance": 50,
                "qty": "r25-50"
            },
            "Restorative": {
                "chance": 25,
                "qty": 1
            },
            "Draught": {
                "chance": 25,
                "qty": 1
            },
            "Equipment_0_0": {
                "chance": 100,  # todo: reset to 10 for production
                "qty": 1
            }
        }

        self.lev1 = {
            "Gold": {
                "chance": 50,
                "qty": "r50-100"
            },
            "Restorative": {
                "chance": 25,
                "qty": "r1-3"
            },
            "Draught": {
                "chance": 25,
                "qty": "r1-3"
            },
            "Equipment_0_0": {
                "chance": 40,
                "qty": 1
            },  # todo: add random enchantments for drops
            "Equipment_1_0": {
                "chance": 10,
                "qty": 1
            }
        }

    @staticmethod
    def random_equipment(tile, level, enchantment):
        candidates = []
        eq_level = int(level)
        for name, obj in inspect.getmembers(items):
            if inspect.isclass(obj):
                if hasattr(obj, "level"):
                    if eq_level == obj.level:
                        candidates.append(name)
        select = random.randint(0, len(candidates)-1)
        drop = tile.spawn_item(candidates[select], amt=1, hidden=False, hfactor=0)
        try:
            enchantment = int(enchantment)
        except:
            print("###ERR: Enchantment couldn't be turned into an int! {}".format(enchantment))
            enchantment = 0
        while enchantment > 0:
            # todo: add an enchantment
            enchantment -= 1
        return drop

