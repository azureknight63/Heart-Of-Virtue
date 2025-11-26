import json
import os

file_path = r"c:\Users\azure\PycharmProjects\Heart-Of-Virtue\src\resources\maps\testing-map.json"

new_items_json = """
[
    {
        "__class__": "Gold",
        "__module__": "items",
        "props": {
            "amt": 50000,
            "maintype": "Gold",
            "name": "Gold",
            "description": "A small pouch containing 50000 gold pieces.",
            "value": 50000,
            "type": "Currency",
            "subtype": "Gold",
            "hidden": false,
            "hide_factor": 0,
            "merchandise": false,
            "discovery_message": "a small pouch of gold.",
            "announce": "There's a small pouch of gold on the ground.",
            "interactions": [],
            "skills": null,
            "owner": null,
            "equip_states": [],
            "add_resistance": {},
            "add_status_resistance": {},
            "gives_exp": false
        }
    },
    {
        "__class__": "Antidote",
        "__module__": "items",
        "props": {
            "weight": 0.25,
            "maintype": "Consumable",
            "subtype": "Potion",
            "count": 10,
            "interactions": [
                "use",
                "drink",
                "drop"
            ],
            "stack_key": "Antidote",
            "name": "Antidote",
            "description": "A murky green fluid of questionable chemistry.\\nDrinking it restores a small amount of health and \\nneutralizes harmful toxins in the bloodstream.",
            "value": 175,
            "type": "Consumable",
            "hidden": false,
            "hide_factor": 0,
            "merchandise": false,
            "discovery_message": "a useful item.",
            "announce": "Jean notices a small glass bottle on the ground with a murky green fluid inside and a label reading, 'Antidote.'",
            "skills": null,
            "owner": null,
            "equip_states": [],
            "add_resistance": {},
            "add_status_resistance": {},
            "gives_exp": false,
            "power": 15
        }
    },
    {
        "__class__": "Restorative",
        "__module__": "items",
        "props": {
            "weight": 0.25,
            "maintype": "Consumable",
            "subtype": "Potion",
            "count": 10,
            "interactions": [
                "use",
                "drink",
                "drop"
            ],
            "stack_key": "Restorative",
            "name": "Restorative",
            "description": "A strange pink fluid of questionable chemistry.\\nDrinking it seems to cause your wounds to immediately mend themselves.",
            "value": 100,
            "type": "Consumable",
            "hidden": false,
            "hide_factor": 0,
            "merchandise": false,
            "discovery_message": "a useful item.",
            "announce": "Jean notices a small glass vial on the ground with an odd pink fluid inside and a label reading, 'Restorative.'",
            "skills": null,
            "owner": null,
            "equip_states": [],
            "add_resistance": {},
            "add_status_resistance": {},
            "gives_exp": false,
            "power": 60
        }
    },
    {
        "__class__": "Spear",
        "__module__": "items",
        "props": {
            "damage": 25,
            "str_req": 10,
            "fin_req": 1,
            "str_mod": 2,
            "fin_mod": 0.5,
            "weight": 3,
            "isequipped": false,
            "maintype": "Weapon",
            "subtype": "Spear",
            "wpnrange": [
                3,
                8
            ],
            "name": "Spear",
            "description": "A weapon of simple design and great effectiveness. \\nHas a longer reach than most melee weapons but is not great at close range.",
            "value": 100,
            "type": "Weapon",
            "hidden": false,
            "hide_factor": 0,
            "merchandise": false,
            "discovery_message": "a kind of weapon.",
            "announce": "There's a Spear here.",
            "interactions": [
                "drop",
                "equip"
            ],
            "skills": null,
            "owner": null,
            "equip_states": [],
            "add_resistance": {},
            "add_status_resistance": {},
            "gives_exp": true,
            "twohand": false
        }
    },
    {
        "__class__": "Scythe",
        "__module__": "items",
        "props": {
            "damage": 5,
            "str_req": 1,
            "fin_req": 1,
            "str_mod": 2,
            "fin_mod": 2,
            "weight": 7,
            "isequipped": false,
            "maintype": "Weapon",
            "subtype": "Scythe",
            "wpnrange": [
                1,
                5
            ],
            "name": "Scythe",
            "description": "An unusual weapon that, despite its intimidating appearance, is particularly difficult to wield. Requires two hands.",
            "value": 100,
            "type": "Weapon",
            "hidden": false,
            "hide_factor": 0,
            "merchandise": false,
            "discovery_message": "a kind of weapon.",
            "announce": "There's a Scythe here.",
            "interactions": [
                "drop",
                "equip"
            ],
            "skills": null,
            "owner": null,
            "equip_states": [],
            "add_resistance": {},
            "add_status_resistance": {},
            "gives_exp": true,
            "twohand": true
        }
    },
    {
        "__class__": "Pickaxe",
        "__module__": "items",
        "props": {
            "damage": 25,
            "str_req": 10,
            "fin_req": 1,
            "str_mod": 2.5,
            "fin_mod": 0.1,
            "weight": 3,
            "isequipped": false,
            "maintype": "Weapon",
            "subtype": "Pick",
            "wpnrange": [
                1,
                5
            ],
            "name": "Pickaxe",
            "description": "A hardy weapon that can also be used to mine for rare metals, if the user is so-inclined. \\nDifficult to wield at very close range.",
            "value": 100,
            "type": "Weapon",
            "hidden": false,
            "hide_factor": 0,
            "merchandise": false,
            "discovery_message": "a kind of weapon.",
            "announce": "There's a Pickaxe here.",
            "interactions": [
                "drop",
                "equip"
            ],
            "skills": null,
            "owner": null,
            "equip_states": [],
            "add_resistance": {},
            "add_status_resistance": {},
            "gives_exp": true,
            "twohand": false
        }
    },
    {
        "__class__": "Battleaxe",
        "__module__": "items",
        "props": {
            "damage": 25,
            "str_req": 5,
            "fin_req": 5,
            "str_mod": 1,
            "fin_mod": 0.5,
            "weight": 2,
            "isequipped": false,
            "maintype": "Weapon",
            "subtype": "Axe",
            "wpnrange": [
                0,
                5
            ],
            "name": "Battleaxe",
            "description": "A crescent blade affixed to a reinforced wooden haft. It is light and easy to swing.",
            "value": 100,
            "type": "Weapon",
            "hidden": false,
            "hide_factor": 0,
            "merchandise": false,
            "discovery_message": "a kind of weapon.",
            "announce": "There's a Battleaxe here.",
            "interactions": [
                "drop",
                "equip"
            ],
            "skills": null,
            "owner": null,
            "equip_states": [],
            "add_resistance": {},
            "add_status_resistance": {},
            "gives_exp": true,
            "twohand": false
        }
    },
    {
        "__class__": "Shortsword",
        "__module__": "items",
        "props": {
            "damage": 15,
            "str_req": 1,
            "fin_req": 1,
            "str_mod": 1,
            "fin_mod": 1,
            "weight": 2,
            "isequipped": false,
            "maintype": "Weapon",
            "subtype": "Sword",
            "wpnrange": [0, 1],
            "name": "Shortsword",
            "description": "A simple shortsword.",
            "value": 50,
            "type": "Weapon",
            "hidden": false,
            "hide_factor": 0,
            "merchandise": false,
            "discovery_message": "a weapon.",
            "announce": "There is a Shortsword here.",
            "interactions": ["drop", "equip"],
            "skills": null,
            "owner": null,
            "equip_states": [],
            "add_resistance": {},
            "add_status_resistance": {},
            "gives_exp": true,
            "twohand": false
        }
    },
    {
        "__class__": "LeatherArmor",
        "__module__": "items",
        "props": {
            "protection": 2,
            "weight": 5,
            "isequipped": false,
            "maintype": "Armor",
            "subtype": "Light",
            "type_s": "Armor",
            "name": "Leather Armor",
            "description": "Basic leather armor.",
            "value": 50,
            "type": "Armor",
            "hidden": false,
            "hide_factor": 0,
            "merchandise": false,
            "discovery_message": "some armor.",
            "announce": "There is Leather Armor here.",
            "interactions": ["drop", "equip"],
            "skills": null,
            "owner": null,
            "equip_states": [],
            "add_resistance": {},
            "add_status_resistance": {},
            "gives_exp": true
        }
    },
    {
        "__class__": "IronHelm",
        "__module__": "items",
        "props": {
            "protection": 3,
            "weight": 4,
            "isequipped": false,
            "maintype": "Helm",
            "subtype": "Heavy",
            "type_s": "Helm",
            "name": "Iron Helm",
            "description": "A sturdy iron helmet.",
            "value": 75,
            "type": "Helm",
            "hidden": false,
            "hide_factor": 0,
            "merchandise": false,
            "discovery_message": "a helm.",
            "announce": "There is an Iron Helm here.",
            "interactions": ["drop", "equip"],
            "skills": null,
            "owner": null,
            "equip_states": [],
            "add_resistance": {},
            "add_status_resistance": {},
            "gives_exp": true
        }
    }
]
"""

new_items = json.loads(new_items_json)

with open(file_path, 'r') as f:
    data = json.load(f)

# Tile (2, 2)
tile = data["(2, 2)"]
items = tile["items"]

# Check if items already exist to avoid duplicates
existing_names = {item["props"]["name"] for item in items}
for item in new_items:
    if item["props"]["name"] not in existing_names:
        items.append(item)

with open(file_path, 'w') as f:
    json.dump(data, f, indent=4)

print("Items added successfully.")
