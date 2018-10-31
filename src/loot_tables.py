'''
All of the loot tables for NPCs can be found here. These are called from the npc module.
'''

import inspect, random
import items, enchant_tables


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
            "Equipment_0_1": {
                "chance": 10,
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
            ench_pool = int(enchantment)
        except:
            print("###ERR: Enchantment couldn't be turned into an int! {}".format(enchantment))
            ench_pool = 0
        enchantment_level = [0, 0]
        enchantments = [None, None]
        while ench_pool > 0:
            # todo: add an enchantment
            group = random.randint(0,1)  # 0 = "Prefix", 1 = "Suffix"
            enchantment_level[group] += 1
            candidates = []
            for name, obj in inspect.getmembers(enchant_tables):
                if inspect.isclass(obj):
                    if hasattr(obj, "tier"):
                        if obj.tier == enchantment_level[group]:
                            ench = getattr(enchant_tables, name)(drop)
                            candidates.append(ench)
            rarity = random.randint(0, 100)
            if not candidates:  # skip ahead if there are no available enchantments
                ench_pool -= 1
                continue
            for candidate in candidates:
                if not candidate.requirements() or (rarity < candidate.rarity):
                    candidates.remove(candidate)
            select = random.randint(0, len(candidates) - 1)
            enchantments[group] = candidates[select]
            ench_pool -= 1
        if enchantments[0]:
            enchantments[0].modify()
        if enchantments[1]:
            enchantments[1].modify()
        return drop
