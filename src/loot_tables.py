'''
All of the loot tables for NPCs can be found here. These are called from the npc module.
'''


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
            }
        }