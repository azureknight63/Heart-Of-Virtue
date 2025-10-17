from __future__ import annotations
import random
import time
from neotermcolor import colored, cprint
import functions
from typing import Any, Dict, List, Optional, Tuple, Union, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - for type checking only
    from player import Player  # noqa

item_types: Dict[str, Dict[str, Any]] = {
    'weapons': {
        'subtypes': [
            "Dagger",
            "Sword",
            "Axe",
            "Pick",
            "Scythe",
            "Spear",
            "Halberd",
            "Bludgeon",
            "Hammer",
            "Bow",
            "Arrow",  # distinct from Bow because Bow is considered a blunt attack at close range
            "Crossbow",
            "Polearm",
            "Stars",
            "Staff",
            "Ethereal"
        ],
        'base_damage_types': {  # not to be confused with subtypes or archetypes, base damage is what a
            # standard attack evaluates as for a weapon or skill,
            # which can be combined with other base types or elemental types of damage
            "piercing": ["Dagger", "Pick", "Spear", "Arrow"],
            "slashing": ["Sword", "Axe", "Scythe", "Halberd", "Stars"],
            "crushing": ["Bludgeon", "Hammer", "Bow", "Crossbow", "Polearm", "Staff"],
            "spiritual": ["Ethereal"],
            "pure": ["Pure"]
        },
        'archetypes': {
            "Blade": ["Dagger", "Sword", "Axe", "Pick", "Scythe", "Spear", "Halberd"],
            "Blunt": ["Bludgeon", "Hammer", "Polearm", "Staff"],
            "Archery": ["Bow", "Crossbow"],
            "Ranged": ["Bow", "Crossbow", "Stars"],
            "Melee": ["Dagger", "Sword", "Axe", "Pick", "Scythe", "Spear", "Halberd", "Bludgeon", "Hammer", "Polearm",
                      "Staff"],
            "Twohand": ["Scythe", "Bow", "Crossbow", "Polearm"]
        }
    }
}


def get_all_subtypes() -> None:
    collection: List[str] = []
    for group in item_types.keys():
        for subtype in item_types[group]:  # type: ignore[index]
            collection.append(subtype)  # pragma: no cover - logic preserved as-is
        item_types[group]['archetypes']['All'] = collection  # type: ignore[index]


def get_base_damage_type(item: Any) -> str:
    damagetype: str = "pure"  # default
    # If an item explicitly defines a base_damage_type (set by an enchantment), respect it.
    override = getattr(item, 'base_damage_type', None)
    if isinstance(override, str) and override:
        return override
    for basetype, weapontypes in item_types['weapons']['base_damage_types'].items():  # type: ignore[index]
        if getattr(item, 'subtype', None) in weapontypes:
            damagetype = basetype
    return damagetype


class Item:
    """The base class for all items"""
    name: str
    description: str
    value: Union[int, float]
    type: str
    subtype: str
    hidden: bool
    hide_factor: Union[int, float]
    merchandise: bool
    discovery_message: str
    announce: str
    interactions: List[str]
    skills: Optional[Dict[Any, int]]
    owner: Optional[Any]
    equip_states: List[Any]
    add_resistance: Dict[str, float]
    add_status_resistance: Dict[str, float]
    gives_exp: bool

    def __init__(self, name: str, description: str, value: Union[int, float], maintype: str, subtype: str,
                 discovery_message: str, hidden: bool = False, hide_factor: Union[int, float] = 0,
                 skills: Optional[Dict[Any, int]] = None, merchandise: bool = False, enchantment_level: int = 0) -> None:
        self.name = name
        self.description = description
        self.value = value
        self.type = maintype
        self.subtype = subtype
        self.hidden = hidden
        self.hide_factor = hide_factor
        self.merchandise = merchandise
        self.discovery_message = discovery_message
        self.announce = "There's a {} here.".format(self.name)
        self.interactions = ["drop"]  # things to do with the item from the inventory menu
        self.skills = skills  # skills that can be learned from using the item (acquiring exp)
        self.owner = None  # used to tie an item to an owner for special interactions
        self.equip_states = []  # items can cause states to be applied to the player when the item is equipped
        self.add_resistance = {}
        self.add_status_resistance = {}
        self.gives_exp = False  # checked before opening an exp category for this item
        if hasattr(self, "isequipped"):
            if getattr(self, "isequipped"):
                self.interactions.append("unequip")
            else:
                self.interactions.append("equip")
        if enchantment_level > 0:
            functions.add_random_enchantments(self, enchantment_level)

    def __str__(self) -> str:
        return "{}\n=====\n{}\nValue: {}\n".format(self.name, self.description, self.value)

    def on_equip(self, player: 'Player') -> None:
        # Prevent equipping merchandise items until purchased
        if getattr(self, 'merchandise', False):
            cprint("You must purchase {} before using or equipping it.".format(self.name), "red")
            # Ensure the item is not marked as equipped on the player
            try:
                if hasattr(self, 'isequipped'):
                    self.isequipped = False  # type: ignore[assignment]
                    # If it is a weapon, ensure the player's eq_weapon falls back to fists
                    if issubclass(self.__class__, Weapon):
                        player.eq_weapon = getattr(player, 'fists', player.eq_weapon)
                # restore interactions to allow equip later
                if "unequip" in self.interactions:
                    try:
                        self.interactions.remove("unequip")
                    except ValueError:
                        pass
                if "equip" not in self.interactions:
                    self.interactions.append("equip")
                functions.refresh_stat_bonuses(player)
                player.refresh_protection_rating()
            except Exception:
                # If anything goes wrong here, fail gracefully without breaking the equip flow
                pass
            return
        # Normal equip behavior: apply any equip states
        if len(self.equip_states) > 0:
            for state in self.equip_states:
                player.apply_state(state)
        return

    def on_unequip(self, player: 'Player') -> None:
        pass

    def drop(self, player: 'Player') -> None:
        if hasattr(self, "count"):
            if getattr(self, "count") > 1:
                while True:
                    drop_count = input("How many would you like to drop? (Carrying {}) ".format(getattr(self, "count")))
                    if functions.is_input_integer(drop_count):
                        if 0 <= int(drop_count) <= getattr(self, "count"):
                            if int(drop_count) > 0:
                                cprint("Jean dropped {} x {}.".format(self.name, drop_count), "cyan")
                                for _ in range(int(drop_count)):
                                    self.count -= 1  # type: ignore[attr-defined]
                                    itemtype = self.__class__.__name__
                                    player.current_room.spawn_item(item_type=itemtype)
                                player.current_room.stack_duplicate_items()
                            else:
                                print("Jean changed his mind.")
                            break
                        else:
                            cprint("Invalid amount!", "red")
                    else:
                        cprint("Invalid amount!", "red")
            else:
                cprint("Jean dropped {}.".format(self.name), "cyan")
                player.current_room.items_here.append(self)
                player.inventory.remove(self)
        else:
            cprint("Jean dropped {}.".format(self.name), "cyan")
            player.current_room.items_here.append(self)
            player.inventory.remove(self)
            if hasattr(self, "isequipped"):
                if getattr(self, "isequipped"):
                    self.isequipped = False  # type: ignore[assignment]
                    self.on_unequip(player)
                    self.interactions.remove("unequip")
                    self.interactions.append("equip")
                    if issubclass(self.__class__, Weapon):
                        player.eq_weapon = player.fists
        functions.refresh_stat_bonuses(player)
        player.refresh_protection_rating()

    def equip(self, player: 'Player') -> None:
        player.equip_item(phrase="{}".format(self.name))

    def unequip(self, player: 'Player') -> None:
        if hasattr(self, "isequipped"):
            self.isequipped = False  # type: ignore[assignment]
            if issubclass(self.__class__, Weapon):  # if the player is now unarmed, "equip" fists
                player.eq_weapon = player.fists
            cprint("Jean put {} back into his bag.".format(self.name), "cyan")
            self.on_unequip(player)
            self.interactions.remove("unequip")
            self.interactions.append("equip")
            functions.refresh_stat_bonuses(player)
            player.refresh_protection_rating()


class Gold(Item):
    amt: int

    def __init__(self, amt: int = 1) -> None:
        self.amt = functions.randomize_amount(amt)
        self.maintype = "Gold"
        super().__init__(name="Gold", description="A small pouch containing {} gold pieces.".format(str(self.amt)),
                         value=self.amt, maintype="Currency", subtype="Gold",
                         discovery_message="a small pouch of gold.")
        self.announce = "There's a small pouch of gold on the ground."
        self.interactions = []
        self.count = self.amt  # allow gold to stack in inventory

    def drop(self, player: 'Player') -> None:
        pass  # cannot drop gold

    def stack_grammar(self):
        pass  # gold does not need special grammar handling


class Weapon(Item):
    damage: Union[int, float]
    str_req: int
    fin_req: int
    str_mod: Union[int, float]
    fin_mod: Union[int, float]
    weight: Union[int, float]
    isequipped: bool
    maintype: str
    subtype: str
    wpnrange: Tuple[int, int]
    twohand: bool

    def __init__(self, name: str, description: str, value: Union[int, float], damage: Union[int, float],
                 isequipped: bool, str_req: int, fin_req: int, str_mod: Union[int, float], fin_mod: Union[int, float],
                 weight: Union[int, float], maintype: str, subtype: str, wpnrange: Tuple[int, int] = (0, 5),
                 discovery_message: str = 'a kind of weapon.', twohand: bool = False,
                 skills: Optional[Dict[Any, int]] = None, merchandise: bool = False, enchantment_level: int = 0) -> None:
        self.damage = damage
        self.str_req = str_req
        self.fin_req = fin_req
        self.str_mod = str_mod
        self.fin_mod = fin_mod
        self.weight = weight
        self.isequipped = isequipped
        self.maintype = maintype
        self.subtype = subtype
        self.wpnrange = wpnrange  # tuple containing the min and max range for the weapon
        super().__init__(name, description, value, maintype, subtype,
                         discovery_message, skills=skills, merchandise=merchandise,
                         enchantment_level=enchantment_level)
        self.announce = "There's a {} here.".format(self.name)
        self.twohand = twohand
        self.gives_exp = True

    def __str__(self) -> str:  # pragma: no cover - display logic
        if self.isequipped:
            return "{} (EQUIPPED)\n=====\n{}\nValue: {}\nDamage: {}\nWeight: {}\nRange: {}".format(self.name,
                                                                                                   self.description,
                                                                                                   self.value,
                                                                                                   self.damage,
                                                                                                   self.weight,
                                                                                                   self.wpnrange)
        else:
            return "{}\n=====\n{}\nValue: {}\nDamage: {}\nWeight: {}\nRange: {}".format(self.name, self.description,
                                                                                        self.value, self.damage,
                                                                                        self.weight, self.wpnrange)


class Armor(Item):
    protection: Union[int, float]
    str_req: int
    str_mod: Union[int, float]
    weight: Union[int, float]
    isequipped: bool
    maintype: str
    subtype: str

    def __init__(self, name: str, description: str, value: Union[int, float], protection: Union[int, float],
                 isequipped: bool, str_req: int, str_mod: Union[int, float], weight: Union[int, float],
                 maintype: str, subtype: str, discovery_message: str = 'a piece of armor.',
                 merchandise: bool = False, enchantment_level: int = 0) -> None:
        self.protection = protection
        self.str_req = str_req
        self.str_mod = str_mod
        self.weight = weight
        self.isequipped = isequipped
        self.maintype = maintype
        self.subtype = subtype
        super().__init__(name, description, value, maintype, subtype,
                         discovery_message, merchandise=merchandise, enchantment_level=enchantment_level)

    def __str__(self) -> str:  # pragma: no cover - display logic
        if self.isequipped:
            return "{} (EQUIPPED)\n=====\n{}\nValue: {}\nProtection: {}\nWeight: {}".format(
                self.name, self.description, self.value, self.protection, self.weight)
        else:
            return "{}\n=====\n{}\nValue: {}\nProtection: {}\nWeight: {}".format(
                self.name, self.description, self.value, self.protection, self.weight)


class Boots(Item):
    protection: Union[int, float]
    str_req: int
    str_mod: Union[int, float]
    weight: Union[int, float]
    isequipped: bool
    maintype: str
    subtype: str

    def __init__(self, name: str, description: str, value: Union[int, float], protection: Union[int, float],
                 isequipped: bool, str_req: int, str_mod: Union[int, float], weight: Union[int, float],
                 maintype: str, subtype: str, discovery_message: str = 'a pair of footgear.',
                 merchandise: bool = False, enchantment_level: int = 0) -> None:
        self.protection = protection
        self.str_req = str_req
        self.str_mod = str_mod
        self.weight = weight
        self.isequipped = isequipped
        self.maintype = maintype
        self.subtype = subtype
        super().__init__(name, description, value, maintype, subtype,
                         discovery_message, merchandise=merchandise, enchantment_level=enchantment_level)

    def __str__(self) -> str:  # pragma: no cover - display logic
        if self.isequipped:
            return "{} (EQUIPPED)\n=====\n{}\nValue: {}\nProtection: {}\nWeight: {}".format(
                    self.name, self.description, self.value, self.protection, self.weight)
        else:
            return "{}\n=====\n{}\nValue: {}\nProtection: {}\nWeight: {}".format(
                self.name, self.description, self.value, self.protection, self.weight)


class ClothBoots(Boots):
    """Very light cloth boots. Minimal protection and very low weight."""
    level: int = 0

    def __init__(self, merchandise: bool = False, enchantment_level: int=0) -> None:
        super().__init__(name="Cloth Boots",
                         description="Simple stitched cloth boots. Keeps feet warm but offers almost no protection.",
                         isequipped=False, value=3,
                         protection=1, str_req=1, str_mod=0.03, weight=0.6, maintype="Boots",
                         subtype="Light Boots", merchandise=merchandise, enchantment_level=enchantment_level)
        # slight finesse benefit for light footwear
        self.add_fin: int = 1


class PaddedBoots(Boots):
    """Padded boots with modest cushioning for comfort and minor protection."""
    level: int = 0

    def __init__(self, merchandise: bool = False, enchantment_level: int=0) -> None:
        super().__init__(name="Padded Boots",
                         description="Boots lined with padding to absorb small impacts and protect the feet.",
                         isequipped=False, value=12,
                         protection=2, str_req=1, str_mod=0.08, weight=1.0, maintype="Boots", subtype="Light Boots",
                         merchandise=merchandise, enchantment_level=enchantment_level)
        self.add_fin: int = 1


class LeatherBoots(Boots):
    """Treated leather boots that balance protection and mobility."""
    level: int = 1

    def __init__(self, merchandise: bool = False, enchantment_level: int = 0) -> None:
        super().__init__(name="Leather Boots",
                         description="Durable leather boots treated to resist wear and offer solid protection without much bulk.",
                         isequipped=False, value=45,
                         protection=3, str_req=3, str_mod=0.15, weight=1.8, maintype="Boots", subtype="Light Boots",
                         merchandise=merchandise, enchantment_level=enchantment_level)
        self.add_fin: int = 1


class StuddedBoots(Boots):
    """Leather boots reinforced with metal studs; tougher while still usable for skirmishers."""
    level: int = 2

    def __init__(self, merchandise: bool = False, enchantment_level: int = 0) -> None:
        super().__init__(name="Studded Boots",
                         description="Leather boots reinforced with small metal studs. Good protection without excessive weight.",
                         isequipped=False, value=110,
                         protection=5, str_req=6, str_mod=0.3, weight=2.6, maintype="Boots", subtype="Medium Boots",
                         merchandise=merchandise, enchantment_level=enchantment_level)


class ChainSabaton(Boots):
    """Chain sabatons (mail footwear) providing solid protection with flexible rings."""
    level: int = 3

    def __init__(self, merchandise: bool = False, enchantment_level: int = 0) -> None:
        super().__init__(name="Chain Sabatons",
                         description="Footwear woven of small interlinked rings. Offers good protection for skirmishers and infantry.",
                         isequipped=False, value=230,
                         protection=8, str_req=9, str_mod=0.5, weight=5.0, maintype="Boots", subtype="Medium Boots",
                         merchandise=merchandise, enchantment_level=enchantment_level)


class IronGreaves(Boots):
    """Heavy iron greaves/boots. Bulky and protective for frontline combatants."""
    level: int = 4

    def __init__(self, merchandise: bool = False, enchantment_level: int = 0) -> None:
        super().__init__(name="Iron Greaves",
                         description="Heavy iron footwear that provides strong protection but reduces nimbleness.",
                         isequipped=False, value=420,
                         protection=12, str_req=13, str_mod=0.9, weight=8.0, maintype="Boots", subtype="Heavy Boots",
                         merchandise=merchandise, enchantment_level=enchantment_level)
        # heavy boots do not grant finesse bonus


class Helm(Item):
    protection: Union[int, float]
    str_req: int
    str_mod: Union[int, float]
    weight: Union[int, float]
    isequipped: bool
    maintype: str
    subtype: str

    def __init__(self, name: str, description: str, value: Union[int, float], protection: Union[int, float],
                 isequipped: bool, str_req: int, str_mod: Union[int, float], weight: Union[int, float],
                 maintype: str, subtype: str, discovery_message: str = 'a kind of head covering.',
                 merchandise: bool = False, enchantment_level: int = 0) -> None:
        self.protection = protection
        self.str_req = str_req
        self.str_mod = str_mod
        self.weight = weight
        self.isequipped = isequipped
        self.maintype = maintype
        self.subtype = subtype
        super().__init__(name, description, value, maintype, subtype,
                         discovery_message, merchandise=merchandise, enchantment_level=enchantment_level)

    def __str__(self) -> str:  # pragma: no cover - display logic
        if self.isequipped:
            return "{} (EQUIPPED)\n=====\n{}\nValue: {}\nProtection: {}\nWeight: {}".format(
                self.name, self.description, self.value, self.protection, self.weight)
        else:
            return "{}\n=====\n{}\nValue: {}\nProtection: {}\nWeight: {}".format(
                self.name, self.description, self.value, self.protection, self.weight)


class Gloves(Item):
    protection: Union[int, float]
    str_req: int
    str_mod: Union[int, float]
    weight: Union[int, float]
    isequipped: bool
    maintype: str
    subtype: str

    def __init__(self, name: str, description: str, value: Union[int, float], protection: Union[int, float],
                 isequipped: bool, str_req: int, str_mod: Union[int, float], weight: Union[int, float],
                 maintype: str, subtype: str, discovery_message: str = 'a pair of gloves.',
                 merchandise: bool = False, enchantment_level: int = 0) -> None:
        self.protection = protection
        self.str_req = str_req
        self.str_mod = str_mod
        self.weight = weight
        self.isequipped = isequipped
        self.maintype = maintype
        self.subtype = subtype
        super().__init__(name, description, value, maintype, subtype,
                         discovery_message, merchandise=merchandise, enchantment_level=enchantment_level)

    def __str__(self) -> str:  # pragma: no cover - display logic
        if self.isequipped:
            return "{} (EQUIPPED)\n=====\n{}\nValue: {}\nProtection: {}\nWeight: {}".format(
                    self.name, self.description, self.value, self.protection, self.weight)
        else:
            return "{}\n=====\n{}\nValue: {}\nProtection: {}\nWeight: {}".format(
                self.name, self.description, self.value, self.protection, self.weight)


# New gloves subclasses (low -> medium value)
class ClothMitts(Gloves):
    """Very light cloth mitts. Minimal protection but do not hinder dexterity."""
    level: int = 0

    def __init__(self, merchandise: bool = False, enchantment_level: int = 0) -> None:
        super().__init__(name="Cloth Mitts",
                         description="Simple cloth mitts stitched from scraps. They keep hands warm but offer almost no protection.",
                         isequipped=False, value=2,
                         protection=0, str_req=1, str_mod=0.02, weight=0.2, maintype="Gloves", subtype="Light Gloves",
                         merchandise=merchandise, enchantment_level=enchantment_level)
        # tiny finesse bonus
        self.add_fin: int = 1


class PaddedGloves(Gloves):
    """Padded gloves with modest cushioning for the hands."""
    level: int = 0

    def __init__(self, merchandise: bool = False, enchantment_level: int = 0) -> None:
        super().__init__(name="Padded Gloves",
                         description="Gloves stuffed with quilted padding. Comfortable and inexpensive protection for hands.",
                         isequipped=False, value=8,
                         protection=1, str_req=1, str_mod=0.05, weight=0.5, maintype="Gloves", subtype="Light Gloves",
                         merchandise=merchandise, enchantment_level=enchantment_level)
        self.add_fin: int = 1


class LeatherGloves(Gloves):
    """Hardened leather gloves providing a good balance of protection and dexterity."""
    level: int = 1

    def __init__(self, merchandise: bool = False, enchantment_level: int = 0) -> None:
        super().__init__(name="Leather Gloves",
                         description="Treated leather gloves that protect the hands without overly restricting movement.",
                         isequipped=False, value=35,
                         protection=2, str_req=3, str_mod=0.15, weight=0.8, maintype="Gloves", subtype="Light Gloves",
                         merchandise=merchandise, enchantment_level=enchantment_level)
        self.add_fin: int = 1


class StuddedGloves(Gloves):
    """Leather gloves reinforced with studs for added protection."""
    level: int = 2

    def __init__(self, merchandise: bool = False, enchantment_level: int = 0) -> None:
        super().__init__(name="Studded Gloves",
                         description="Gloves of leather with small metal studs riveted into the surface. Tough and practical.",
                         isequipped=False, value=90,
                         protection=3, str_req=6, str_mod=0.3, weight=1.4, maintype="Gloves", subtype="Medium Gloves",
                         merchandise=merchandise, enchantment_level=enchantment_level)


class ChainGauntlets(Gloves):
    """Interlinked ring gauntlets offering solid protection with reasonable flexibility."""
    level: int = 3

    def __init__(self, merchandise: bool = False, enchantment_level: int = 0) -> None:
        super().__init__(name="Chain Gauntlets",
                         description="Gauntlets woven from small metal rings. Good protection with moderate weight.",
                         isequipped=False, value=180,
                         protection=5, str_req=9, str_mod=0.5, weight=2.5, maintype="Gloves", subtype="Medium Gloves",
                         merchandise=merchandise, enchantment_level=enchantment_level)


class IronGauntlets(Gloves):
    """Solid iron gauntlets. Heavy but protective for frontline fighters."""
    level: int = 4

    def __init__(self, merchandise: bool = False, enchantment_level: int = 0) -> None:
        super().__init__(name="Iron Gauntlets",
                         description="Heavy iron gauntlets that provide strong protection at the cost of dexterity.",
                         isequipped=False, value=360,
                         protection=7, str_req=14, str_mod=0.85, weight=4.0, maintype="Gloves", subtype="Heavy Gloves",
                         merchandise=merchandise, enchantment_level=enchantment_level)
        # heavy gloves do not grant finesse bonus


class Accessory(Item):
    protection: Union[int, float]
    str_mod: Union[int, float]
    fin_mod: Union[int, float]
    weight: Union[int, float]
    isequipped: bool
    maintype: str
    subtype: str

    def __init__(self, name: str, description: str, value: Union[int, float], protection: Union[int, float],
                 isequipped: bool, str_mod: Union[int, float], fin_mod: Union[int, float], weight: Union[int, float],
                 maintype: str, subtype: str, discovery_message: str = 'a small trinket.',
                 merchandise: bool = False, enchantment_level: int = 0) -> None:
        self.protection = protection
        self.str_mod = str_mod
        self.fin_mod = fin_mod
        self.weight = weight
        self.isequipped = isequipped
        self.maintype = maintype
        self.subtype = subtype
        super().__init__(name, description, value, maintype, subtype, discovery_message, merchandise=merchandise,
                         enchantment_level=enchantment_level)

    def __str__(self) -> str:  # pragma: no cover - display logic
        if self.isequipped:
            return "{} (EQUIPPED)\n=====\n{}\nValue: {}\nProtection: {}\nWeight: {}".format(
                self.name, self.description, self.value, self.protection, self.weight)
        else:
            return "{}\n=====\n{}\nValue: {}\nProtection: {}\nWeight: {}".format(
                self.name, self.description, self.value, self.protection, self.weight)


class Consumable(Item):
    weight: Union[int, float]
    maintype: str
    subtype: str
    count: int

    def __init__(self, name: str, description: str, value: Union[int, float], weight: Union[int, float],
                 maintype: str, subtype: str, discovery_message: str = 'a useful item.', count: int = 1,
                 merchandise: bool = False, enchantment_level: int = 0) -> None:
        self.weight = weight
        self.maintype = maintype
        self.subtype = subtype
        self.count = count
        self.interactions = ["use", "drop"]
        self.stack_key = name
        super().__init__(name, description, value, maintype, subtype,
                         discovery_message, merchandise=merchandise, enchantment_level=enchantment_level)

    def stack_grammar(self) -> None:
        """Checks the stack count for the item and changes the verbiage accordingly"""
        pass

    def __str__(self) -> str:  # pragma: no cover - display logic
        return "{}\n=====\n{}\n" \
               "Count: {}\n" \
               "Value: {} gold each, {} gold total\n" \
               "Weight: {} lbs each, {} lbs total".format(self.name, self.description, self.count, self.value,
                                                          self.value * self.count, self.weight,
                                                          self.weight * self.count)


class Special(Item):
    weight: Union[int, float]
    maintype: str
    subtype: str
    count: int

    def __init__(self, name: str, description: str, value: Union[int, float], weight: Union[int, float],
                 maintype: str, subtype: str, discovery_message: str = 'a strange object.',
                 merchandise: bool = False) -> None:
        self.weight = weight
        self.maintype = maintype
        self.subtype = subtype
        self.count = 1
        self.interactions = ["drop"]
        super().__init__(name, description, value, maintype, subtype,
                         discovery_message, merchandise=merchandise)

    def __str__(self) -> str:  # pragma: no cover - display logic
        return "{}\n=====\n{}\nValue: {}\nWeight: {}".format(
            self.name, self.description, self.value, self.weight)


class Commodity(Special):
    """Intermediate class for commodity-type items (creature loot with no practical purpose other than selling).
    
    Commodities stack like consumables and are primarily meant to be sold to merchants for gold.
    """
    stack_key: str

    def __init__(self, name: str, description: str, value: Union[int, float], weight: Union[int, float],
                 maintype: str, subtype: str, discovery_message: str = 'a commodity item.',
                 count: int = 1, merchandise: bool = False) -> None:
        super().__init__(name, description, value, weight, maintype, subtype,
                         discovery_message, merchandise=merchandise)
        self.count = count
        self.stack_key = name
        self.interactions = ["drop"]

    def stack_grammar(self) -> None:
        """Checks the stack count for the item and changes the verbiage accordingly"""
        pass

    def __str__(self) -> str:  # pragma: no cover - display logic
        return "{}\n=====\n{}\n" \
               "Count: {}\n" \
               "Value: {} gold each, {} gold total\n" \
               "Weight: {} lbs each, {} lbs total".format(self.name, self.description, self.count, self.value,
                                                          self.value * self.count, self.weight,
                                                          self.weight * self.count)


class Key(Special):
    lock: Optional[Any]

    def __init__(self, lock: Optional[Any] = None, merchandise: bool = False) -> None:
        """
        Keys just sort of sit in inventory. They are "used" when the player uses 'unlock' on their paired lock
        :param lock: Any object that has an 'unlock' method
        """

        super().__init__(name="Key",
                         description="A small, dull, metal key.",
                         value=0, weight=0, maintype="Special", subtype="Key", merchandise=merchandise)

        self.lock = lock  # Any object that has an 'unlock' method
        self.interactions = ["drop"]


class Crystals(Commodity):
    def __init__(self, count: int = 1, merchandise: bool = False) -> None:
        """
        Crystals are commodity drops from certain creatures like Rock Rumblers.
        They can also be found growing naturally in some caves and mountain areas.
        They can be sold to merchants. Gollem merchants will pay an increased rate for them since
        they are a source of food.
        """
        super().__init__(name="Crystals",
                         description="A beautiful collection of scintillating purple and aquamarine crystals. "
                                     "Interesting baubles to most, but a valuable"
                                     " food source to Rock Rumblers and their gentler cousins, the Grondites.",
                         value=10, weight=0.1, maintype="Special", subtype="Commodity",
                         discovery_message="some shimmering crystals.", count=count, merchandise=merchandise)
        self.announce = "Jean notices some crystals on the ground."

    def stack_grammar(self) -> None:
        if self.count > 1:
            self.announce = "Jean notices a pile of crystals on the ground."
            self.description = "A beautiful collection of scintillating purple and aquamarine crystals. " \
                             "Interesting baubles to most, but a valuable " \
                             "food source to Rock Rumblers and their gentler cousins, the Grondites."
        else:
            self.announce = "Jean notices some crystals on the ground."
            self.description = "A beautiful collection of scintillating purple and aquamarine crystals. " \
                             "Interesting baubles to most, but a valuable " \
                             "food source to Rock Rumblers and their gentler cousins, the Grondites."


# ---------------------------------------------------------------------------
# Weapons
# ---------------------------------------------------------------------------
class Fists(Weapon):  # equipped automatically when Jean has no other weapon equipped
    def __init__(self, merchandise: bool = False) -> None:
        super().__init__(name="fists",
                         description="",
                         isequipped=True, value=0,
                         damage=1, str_req=1, fin_req=1, str_mod=1, fin_mod=1, weight=0.0,
                         maintype="Weapon", subtype="Unarmed", merchandise=merchandise)
        self.interactions = []


class Rock(Weapon):
    def __init__(self, merchandise: bool = False, enchantment_level: int = 0) -> None:
        super().__init__(name="Rock",
                         description="A fist-sized rock, suitable for bludgeoning.",
                         isequipped=False, value=0,
                         damage=1, str_req=1, fin_req=1, str_mod=3.00, fin_mod=0.50, weight=2.0,
                         maintype="Weapon", subtype="Bludgeon", merchandise=merchandise,
                         enchantment_level=enchantment_level)


class RustedIronMace(Weapon):
    level: int = 0
    def __init__(self, merchandise: bool = False, enchantment_level: int = 0) -> None:
        super().__init__(name="Rusted Iron Mace",
                         description="A small mace with some rust around the spikes. Heavy and slow, "
                                     "but packs a decent punch.",
                         isequipped=False, value=10,
                         damage=15, str_req=10, fin_req=5, str_mod=2.25, fin_mod=0.5, weight=5.0, maintype="Weapon",
                         subtype="Bludgeon", merchandise=merchandise, enchantment_level=enchantment_level)


class Mace(Weapon):
    level: int = 1
    def __init__(self, merchandise: bool = False, enchantment_level: int = 0) -> None:
        super().__init__(name="Mace",
                         description="A small mace. Heavy and slow, but packs a decent punch.",
                         isequipped=False, value=100,
                         damage=25, str_req=10, fin_req=5, str_mod=2, fin_mod=0.5, weight=5.0, maintype="Weapon",
                         subtype="Bludgeon", merchandise=merchandise, enchantment_level=enchantment_level)


class RustedDagger(Weapon):
    level: int = 0
    def __init__(self, merchandise: bool = False, enchantment_level: int = 0) -> None:
        super().__init__(name="Rusted Dagger",
                         description="A small dagger with some rust. Somewhat more dangerous than a rock.",
                         isequipped=False, value=10,
                         damage=10, str_req=1, fin_req=12, str_mod=0.25, fin_mod=3, weight=1, maintype="Weapon",
                         subtype="Dagger", wpnrange=(0, 3), merchandise=merchandise, enchantment_level=enchantment_level)


class Dagger(Weapon):
    level: int = 1
    def __init__(self, merchandise: bool = False, enchantment_level: int = 0) -> None:
        super().__init__(name="Dagger",
                         description="A rogue's best friend.",
                         isequipped=False, value=100,
                         damage=12, str_req=1, fin_req=12, str_mod=0.25, fin_mod=3, weight=1, maintype="Weapon",
                         subtype="Dagger", wpnrange=(0, 3), merchandise=merchandise, enchantment_level=enchantment_level)


class Baselard(Weapon):
    level: int = 1
    def __init__(self, merchandise: bool = False, enchantment_level: int = 0) -> None:
        super().__init__(name="Baselard",
                         description="A small, sharp dagger with an 'H'-shaped hilt.",
                         isequipped=False, value=100,
                         damage=18, str_req=1, fin_req=12, str_mod=0.2, fin_mod=2.8, weight=1.2, maintype="Weapon",
                         subtype="Dagger", wpnrange=(0, 3), merchandise=merchandise, enchantment_level=enchantment_level)


class Shortsword(Weapon):
    level: int = 1

    def __init__(self, merchandise: bool = False, enchantment_level: int = 0) -> None:
        super().__init__(name="Shortsword",
                         description="A double-edged shortsword. A reliable companion in any fight.",
                         isequipped=False, value=100,
                         damage=25, str_req=5, fin_req=10, str_mod=0.75, fin_mod=1.25, weight=2, maintype="Weapon",
                         subtype="Sword", wpnrange=(0, 4), merchandise=merchandise, enchantment_level=enchantment_level)


class Epee(Weapon):
    level: int = 1

    def __init__(self, merchandise: bool = False, enchantment_level: int = 0) -> None:
        super().__init__(name="Epee",
                         description="A short dueling sword. Frequently used ceremonially, "
                                     "it is nonetheless effective in combat if wielded properly.\n"
                                     " While the long, thin blade does have a cutting edge, "
                                     "it is most effective with thrusting attacks or to parry an opponent.",
                         isequipped=False, value=100,
                         damage=25, str_req=5, fin_req=20, str_mod=0.5, fin_mod=2, weight=3, maintype="Weapon",
                         subtype="Sword", wpnrange=(0, 5), merchandise=merchandise, enchantment_level=enchantment_level)


class Battleaxe(Weapon):
    level: int = 1

    def __init__(self, merchandise: bool = False, enchantment_level: int = 0) -> None:
        super().__init__(name="Battleaxe",
                         description="A crescent blade affixed to a reinforced wooden haft. "
                                     "It is light and easy to swing.",
                         isequipped=False, value=100,
                         damage=25, str_req=5, fin_req=5, str_mod=1, fin_mod=0.5, weight=2, maintype="Weapon",
                         subtype="Axe", wpnrange=(0, 5), merchandise=merchandise, enchantment_level=enchantment_level)


class Pickaxe(Weapon):
    level: int = 1

    def __init__(self, merchandise: bool = False, enchantment_level: int = 0) -> None:
        super().__init__(name="Pickaxe",
                         description="A hardy weapon that can also be used to mine for rare metals, "
                                     "if the user is so-inclined. \n"
                                     "Difficult to wield at very close range.",
                         isequipped=False, value=100,
                         damage=25, str_req=10, fin_req=1, str_mod=2.5, fin_mod=0.1, weight=3, maintype="Weapon",
                         subtype="Pick", wpnrange=(1, 5), merchandise=merchandise, enchantment_level=enchantment_level)


class Scythe(Weapon):
    level: int = 1

    def __init__(self, merchandise: bool = False, enchantment_level: int = 0) -> None:
        super().__init__(name="Scythe",
                         description="An unusual weapon that, despite its intimidating appearance, "
                                     "is particularly difficult to wield. Requires two hands.",
                         isequipped=False, value=100,
                         damage=5, str_req=1, fin_req=1, str_mod=2, fin_mod=2, weight=7, maintype="Weapon",
                         subtype="Scythe", wpnrange=(1, 5), twohand=True,
                         merchandise=merchandise, enchantment_level=enchantment_level)


class Spear(Weapon):
    level: int = 1

    def __init__(self, merchandise: bool = False, enchantment_level: int = 0) -> None:
        super().__init__(name="Spear",
                         description="A weapon of simple design and great effectiveness. \n"
                                     "Has a longer reach than most melee weapons but is not great at close range.",
                         isequipped=False, value=100,
                         damage=25, str_req=10, fin_req=1, str_mod=2, fin_mod=0.5, weight=3, maintype="Weapon",
                         subtype="Spear", wpnrange=(3, 8), merchandise=merchandise, enchantment_level=enchantment_level)


class Halberd(Weapon):
    level: int = 1

    def __init__(self, merchandise: bool = False, enchantment_level: int = 0) -> None:
        super().__init__(name="Halberd",
                         description="Essentially an axe mounted on top of a large pole. \n"
                                     "Has a longer reach than most melee weapons but is not great at close range.",
                         isequipped=False, value=100,
                         damage=25, str_req=10, fin_req=1, str_mod=1.75, fin_mod=1, weight=4, maintype="Weapon",
                         subtype="Spear", wpnrange=(3, 8), merchandise=merchandise, enchantment_level=enchantment_level)


class Hammer(Weapon):
    level: int = 0

    def __init__(self, merchandise: bool = False, enchantment_level: int = 0) -> None:
        super().__init__(name="Hammer",
                         description="Great for smashing more heavily-armored foes.",
                         isequipped=False, value=100,
                         damage=25, str_req=10, fin_req=1, str_mod=2.5, fin_mod=0.1, weight=3, maintype="Weapon",
                         subtype="Bludgeon", merchandise=merchandise, enchantment_level=enchantment_level)


class Shortbow(Weapon):
    level: int = 0

    def __init__(self, merchandise: bool = False, enchantment_level: int = 0) -> None:
        super().__init__(name="Shortbow",
                         description="A reliable missile weapon. Useful as a weak bludgeon at close range.\n"
                                     "Requires two hands.",
                         isequipped=False, value=50,
                         damage=8, str_req=5, fin_req=5, str_mod=1, fin_mod=1, weight=1.5, maintype="Weapon",
                         subtype="Bow", merchandise=merchandise, enchantment_level=enchantment_level)
        self.range_base: Union[int, float] = 20
        self.range_decay: Union[int, float] = 0.05


class Longbow(Weapon):
    level: int = 0

    def __init__(self, merchandise: bool = False, enchantment_level: int = 0) -> None:
        super().__init__(name="Longbow",
                         description="Specialized bow for shooting long distances. Useful as a weak bludgeon at "
                                     "close range.\n"
                                     "Requires two hands.",
                         isequipped=False, value=100,
                         damage=8, str_req=5, fin_req=5, str_mod=1, fin_mod=1, weight=2, maintype="Weapon",
                         subtype="Bow", merchandise=merchandise, enchantment_level=enchantment_level)
        self.range_base: Union[int, float] = 25
        self.range_decay: Union[int, float] = 0.04


class Crossbow(Weapon):
    level: int = 0

    def __init__(self, merchandise: bool = False, enchantment_level: int = 0) -> None:
        super().__init__(name="Crossbow",
                         description="Heavier than a standard bow but able to fire more rapidly. "
                                     "It fires bolts instead of arrows.\n"
                                     "Requires two hands.",
                         isequipped=False, value=100,
                         damage=20, str_req=5, fin_req=5, str_mod=1.5, fin_mod=1, weight=4, maintype="Weapon",
                         subtype="Crossbow", merchandise=merchandise, enchantment_level=enchantment_level)
        self.range_base: Union[int, float] = 15
        self.range_decay: Union[int, float] = 0.06


class Pole(Weapon):
    level: int = 1

    def __init__(self, merchandise: bool = False, enchantment_level: int = 0) -> None:
        super().__init__(name="Pole",
                         description="A large pole, great for delivering blows from a distance. \n"
                                     "Has a longer reach than most melee weapons but is not great at close range.",
                         isequipped=False, value=100,
                         damage=25, str_req=5, fin_req=5, str_mod=1.25, fin_mod=1.25, weight=2, maintype="Weapon",
                         subtype="Polearm", wpnrange=(2, 7), merchandise=merchandise, enchantment_level=enchantment_level)


# ---------------------------------------------------------------------------
# Armor
# ---------------------------------------------------------------------------
class TatteredCloth(Armor):
    level: int = 0

    def __init__(self, merchandise: bool = False, enchantment_level: int = 0) -> None:
        super().__init__(name="Tattered Cloth",
                         description="Shamefully tattered cloth wrappings. \n"
                                     "Lightweight, but offering little in protection.",
                         isequipped=False, value=0,
                         protection=1, str_req=1, str_mod=0.1, weight=0.5, maintype="Armor", subtype="Light Armor",
                         merchandise=merchandise, enchantment_level=enchantment_level)


class PaddedJerkin(Armor):
    """Very light, padded jerkin. Comfortable and cheap; minimal protection."""
    level: int = 0

    def __init__(self, merchandise: bool = False, enchantment_level: int = 0) -> None:
        super().__init__(name="Padded Jerkin",
                         description="A jerkin sewn from layers of fabric and padding. Lightweight and inexpensive.",
                         isequipped=False, value=10,
                         protection=2, str_req=1, str_mod=0.1, weight=1.0, maintype="Armor", subtype="Light Armor",
                         merchandise=merchandise, enchantment_level=enchantment_level)
        self.add_fin: int = 1


class QuiltedVest(Armor):
    """Quilted vest offering a balance of comfort and light protection."""
    level: int = 1

    def __init__(self, merchandise: bool = False, enchantment_level: int = 0) -> None:
        super().__init__(name="Quilted Vest",
                         description="A vest sewn with quilted padding. Good for scouts and caravan guards.",
                         isequipped=False, value=35,
                         protection=3, str_req=3, str_mod=0.15, weight=1.8, maintype="Armor", subtype="Light Armor",
                         merchandise=merchandise, enchantment_level=enchantment_level)
        self.add_fin: int = 1


class LeatherArmor(Armor):
    """Hardened leather armor. A reliable light armor choice for early adventurers."""
    level: int = 1

    def __init__(self, merchandise: bool = False, enchantment_level: int = 0) -> None:
        super().__init__(name="Leather Armor",
                         description="Thick leather treated to resist wear and improve protection.",
                         isequipped=False, value=50,
                         protection=4, str_req=4, str_mod=0.2, weight=2.5, maintype="Armor", subtype="Light Armor",
                         merchandise=merchandise, enchantment_level=enchantment_level)
        self.add_fin: int = 1


class StuddedLeather(Armor):
    """Leather armor reinforced with metal studs. Good protection for modest weight."""
    level: int = 2

    def __init__(self, merchandise: bool = False, enchantment_level: int = 0) -> None:
        super().__init__(name="Studded Leather",
                         description="A leather cuirass reinforced with small metal studs. Popular with rangers and skirmishers.",
                         isequipped=False, value=120,
                         protection=6, str_req=6, str_mod=0.3, weight=3.0, maintype="Armor", subtype="Medium Armor",
                         merchandise=merchandise, enchantment_level=enchantment_level)


class ChainmailShirt(Armor):
    """A short chain shirt providing solid protection without the bulk of full mail."""
    level: int = 3

    def __init__(self, merchandise: bool = False, enchantment_level: int = 0) -> None:
        super().__init__(name="Chainmail Shirt",
                         description="A shirt of interlocking metal rings. Good defense against slashes.",
                         isequipped=False, value=250,
                         protection=9, str_req=10, str_mod=0.5, weight=7.0, maintype="Armor", subtype="Medium Armor",
                         merchandise=merchandise, enchantment_level=enchantment_level)


class IronCuirass(Armor):
    """A heavy iron cuirass offering dependable mid-tier protection."""
    level: int = 4

    def __init__(self, merchandise: bool = False, enchantment_level: int = 0) -> None:
        super().__init__(name="Iron Cuirass",
                         description="A solid iron breastplate. Heavy, but provides strong protection for front-line fighters.",
                         isequipped=False, value=500,
                         protection=14, str_req=14, str_mod=0.9, weight=12.0, maintype="Armor", subtype="Heavy Armor",
                         merchandise=merchandise, enchantment_level=enchantment_level)


# ---------------------------------------------------------------------------
# Helms
# ---------------------------------------------------------------------------
class ClothHood(Helm):
    level: int = 0

    def __init__(self, merchandise: bool = False, enchantment_level: int = 0) -> None:
        super().__init__(name="Cloth Hood",
                         description="Stained cloth hood. "
                                     "Enough to conceal your face, but that's about it.",
                         isequipped=False, value=0,
                         protection=0, str_req=1, str_mod=0.1, weight=0.5, maintype="Helm", subtype="Light Helm",
                         merchandise=merchandise, enchantment_level=enchantment_level)
        self.add_fin: int = 1


class LeatherCap(Helm):
    """A simple, practical helmet made of hardened leather. Provides light protection
    while remaining comfortable and lightweight.
    """
    level: int = 1

    def __init__(self, merchandise: bool = False, enchantment_level: int = 0) -> None:
        super().__init__(name="Leather Cap",
                         description="A simple leather cap offering modest protection without much weight.",
                         isequipped=False, value=20,
                         protection=2, str_req=3, str_mod=0.2, weight=0.8, maintype="Helm", subtype="Light Helm",
                         merchandise=merchandise, enchantment_level=enchantment_level)
        # Small finesse bonus for better handling
        self.add_fin: int = 1


class PaddedCap(Helm):
    """Very light padded headgear. Cheap and comfortable, minimal protection."""
    level: int = 0

    def __init__(self, merchandise: bool = False, enchantment_level: int = 0) -> None:
        super().__init__(name="Padded Cap",
                         description="A cheap cap stuffed with padding. Comfortable but offers only trivial protection.",
                         isequipped=False, value=5,
                         protection=1, str_req=1, str_mod=0.05, weight=0.6, maintype="Helm", subtype="Light Helm",
                         merchandise=merchandise, enchantment_level=enchantment_level)
        self.add_fin: int = 1


class HunterHood(Helm):
    """A hood favored by scouts and hunters. Lightweight with small bonuses to finesse."""
    level: int = 1

    def __init__(self, merchandise: bool = False, enchantment_level: int = 0) -> None:
        super().__init__(name="Hunter's Hood",
                         description="A muted hood designed to muffle sound and blend into foliage. Lightweight and practical.",
                         isequipped=False, value=15,
                         protection=1, str_req=2, str_mod=0.1, weight=0.5, maintype="Helm", subtype="Light Helm",
                         merchandise=merchandise, enchantment_level=enchantment_level)
        self.add_fin: int = 2


class StuddedSkullcap(Helm):
    """A skullcap reinforced with small metal studs for added protection while remaining compact."""
    level: int = 2

    def __init__(self, merchandise: bool = False, enchantment_level: int = 0) -> None:
        super().__init__(name="Studded Skullcap",
                         description="A close-fitting cap reinforced with metal studs. Offers respectable protection for its size.",
                         isequipped=False, value=60,
                         protection=3, str_req=5, str_mod=0.25, weight=1.4, maintype="Helm", subtype="Light Helm",
                         merchandise=merchandise, enchantment_level=enchantment_level)
        # Slight balance to handling
        self.add_fin: int = 1


class ChainCoif(Helm):
    """Mail coif that protects the head and neck. Heavier, but provides solid defense."""
    level: int = 3

    def __init__(self, merchandise: bool = False, enchantment_level: int = 0) -> None:
        super().__init__(name="Chain Coif",
                         description="A hood of interlinked metal rings. Offers good protection against slashes at modest weight.",
                         isequipped=False, value=120,
                         protection=5, str_req=8, str_mod=0.5, weight=2.5, maintype="Helm", subtype="Medium Helm",
                         merchandise=merchandise, enchantment_level=enchantment_level)
        # Heavier headgear; small strength tradeoff handled by str_mod


class IronHelm(Helm):
    """A simple iron helm. Bulky and sturdy; suitable as dependable mid-tier protection."""
    level: int = 4

    def __init__(self, merchandise: bool = False, enchantment_level: int = 0) -> None:
        super().__init__(name="Iron Helm",
                         description="A solid iron helm. Heavy, but provides dependable protection to the wearer.",
                         isequipped=False, value=220,
                         protection=7, str_req=12, str_mod=0.8, weight=4.0, maintype="Helm", subtype="Heavy Helm",
                         merchandise=merchandise, enchantment_level=enchantment_level)
        # Heavy helms may reduce finesse slightly; provide no finesse bonus

# ---------------------------------------------------------------------------
# Accessories
# ---------------------------------------------------------------------------
class DullMedallion(Accessory):
    def __init__(self, merchandise: bool = False) -> None:
        super().__init__(name="Dull Medallion",
                         description="A rather unremarkable medallion. \n"
                                     "It's face is dull, and seems to swallow any light unlucky enough to "
                                     "land upon it. \n"
                                     "It may have been a family heirloom or a memento of a lost love.",
                         isequipped=False, value=25,
                         protection=0, str_mod=0, fin_mod=0, weight=0.5, maintype="Accessory", subtype="Necklace",
                         merchandise=merchandise)

    def on_equip(self, player: 'Player') -> None:
        cprint("Jean feels a slight chill as the medallion's chain settles on his neck.", "green")
        player.combat_idle_msg.append("Jean feels the soft caress of a stranger's hand on his cheek.")
        player.combat_idle_msg.append("A faint whisper of unknown origin passes quickly through Jean's mind.")
        player.combat_idle_msg.append("For an instant, Jean thought he saw the face of an unknown woman.")
        player.combat_idle_msg.append("A sharp feeling of grief suddenly grips Jean's chest.")
        player.combat_idle_msg.append("Jean suddenly imagined his wife coughing up blood.")
        player.combat_idle_msg.append("A sense of urgency and desperation suddenly fills Jean.")
        player.combat_idle_msg.append("The words, 'Cherub Root,' flash across Jean's mind.")

    def on_unequip(self, player: 'Player') -> None:
        cprint("Removing the medallion gives Jean a strange sense of relief, but also inexplicable sadness.", "green")
        player.combat_idle_msg.remove("Jean feels the soft caress of a stranger's hand on his cheek.")
        player.combat_idle_msg.remove("A faint whisper of unknown origin passes quickly through Jean's mind.")
        player.combat_idle_msg.remove("For an instant, Jean thought he saw the face of an unknown woman.")
        player.combat_idle_msg.remove("A sharp feeling of grief suddenly grips Jean's chest.")
        player.combat_idle_msg.remove("Jean suddenly imagined his wife coughing up blood.")
        player.combat_idle_msg.remove("A sense of urgency and desperation suddenly fills Jean.")
        player.combat_idle_msg.remove("The words, 'Cherub Root,' flash across Jean's mind.")


class GoldRing(Accessory):
    level: int = 1

    def __init__(self, merchandise: bool = False, enchantment_level: int = 0) -> None:
        super().__init__(name="Gold Ring",
                         description="A shiny gold ring. \n"
                                     "Typically a sign of marital vows, though it may also be worn to exhibit wealth.",
                         isequipped=False, value=200,
                         protection=0, str_mod=0, fin_mod=0, weight=0.1, maintype="Accessory", subtype="Ring",
                         merchandise=merchandise, enchantment_level=enchantment_level)


class JeanWeddingBand(Accessory):
    level: int = 99
    add_faith: int = 1
    add_endurance: int = 1
    add_charisma: int = -1

    def __init__(self, merchandise: bool = False) -> None:
        super().__init__(name="Wedding Band",
                         description="A shiny gold ring with some intricate patterns carved into it. \n"
                                     "The faded inscription on the inner wall of the ring reads, 'AMELIA.' \n"
                                     "This is an item of special interest to Jean. "
                                     "Some things are too difficult to let go.",
                         isequipped=True, value=900,
                         protection=0, str_mod=0, fin_mod=0, weight=0.1, maintype="Accessory", subtype="Ring", merchandise=merchandise)
        self.interactions.remove("drop")

    def on_equip(self, player: 'Player') -> None:
        if len(self.equip_states) > 0:
            for state in self.equip_states:
                player.apply_state(state)
        print(
            "As he slides on the band, Jean's face appears placid. "
            "His heart, however, is filled with sadness, and a coldness grips his stomach.")

    def on_unequip(self, player: 'Player') -> None:
        print("Jean's frown twitches slightly as his finger is released from the weight of the band. "
              "He glances briefly at the faded inscription on the ring's inner wall "
              "before stuffing the small baubel into his bag.")


class SilverRing(Accessory):
    level: int = 0

    def __init__(self, merchandise: bool = False, enchantment_level: int = 0) -> None:
        super().__init__(name="Silver Ring",
                         description="A shiny silver ring. \n"
                                     "A small bauble favored by people of typically lower class.",
                         isequipped=False, value=50,
                         protection=0, str_mod=0, fin_mod=0, weight=0.1, maintype="Accessory", subtype="Ring",
                         merchandise=merchandise, enchantment_level=enchantment_level)


class GoldChain(Accessory):
    level: int = 2

    def __init__(self, merchandise: bool = False, enchantment_level: int = 0) -> None:
        super().__init__(name="Gold Chain",
                         description="A shiny gold chain. \n"
                                     "Worn to impress. An excellent gift for a lady.",
                         isequipped=False, value=300,
                         protection=0, str_mod=0, fin_mod=0, weight=0.1, maintype="Accessory", subtype="Necklace",
                         merchandise=merchandise, enchantment_level=enchantment_level)


class SilverChain(Accessory):
    level: int = 1

    def __init__(self, merchandise: bool = False, enchantment_level: int = 0) -> None:
        super().__init__(name="Silver Chain",
                         description="A shiny silver chain. \n"
                                     "An excellent gift for a lady who has simple tastes.",
                         isequipped=False, value=100,
                         protection=0, str_mod=0, fin_mod=0, weight=0.1, maintype="Accessory", subtype="Necklace",
                         merchandise=merchandise, enchantment_level=enchantment_level)


class GoldBracelet(Accessory):
    level: int = 2

    def __init__(self, merchandise: bool = False, enchantment_level: int = 0) -> None:
        super().__init__(name="Gold Bracelet",
                         description="A shiny gold bracelet. \n"
                                     "Everyone knows that you need to accessorize in order to make an impression.",
                         isequipped=False, value=300,
                         protection=0, str_mod=0, fin_mod=0, weight=0.1, maintype="Accessory", subtype="Bracelet",
                         merchandise=merchandise, enchantment_level=enchantment_level)


class SilverBracelet(Accessory):
    level: int = 0

    def __init__(self, merchandise: bool = False, enchantment_level: int = 0) -> None:
        super().__init__(name="Silver Bracelet",
                         description="A shiny silver bracelet. \n"
                                     "More of an eccentricity than anything else.",
                         isequipped=False, value=100,
                         protection=0, str_mod=0, fin_mod=0, weight=0.1, maintype="Accessory", subtype="Bracelet",
                         merchandise=merchandise, enchantment_level=enchantment_level)


# ---------------------------------------------------------------------------
# Consumables
# ---------------------------------------------------------------------------
class Restorative(Consumable):
    power: int

    def __init__(self, count: int = 1, merchandise: bool = False) -> None:
        super().__init__(name="Restorative",
                         description="A strange pink fluid of questionable chemistry.\n"
                                     "Drinking it seems to cause your wounds to immediately mend "
                                     "themselves.",
                         value=100, weight=0.25, maintype="Consumable", subtype="Potion", count=count, merchandise=merchandise)
        self.power = 60
        self.count = count
        self.interactions = ["use", "drink", "drop"]
        self.announce = "Jean notices a small glass vial on the ground with an odd pink fluid inside and a label " \
                        "reading, 'Restorative.'"

    def stack_grammar(self) -> None:
        if self.count > 1:
            self.description = "A box filled with vials of a strange pink fluid.\n" \
                               "Drinking one would seem to cause your wounds to immediately mend themselves.\n" \
                               "There appear to be {} vials in the box.\n".format(self.count)
            self.announce = "There is a box of small glass vials here."
        else:
            self.description = "A strange pink fluid of questionable chemistry.\n" \
                               "Drinking it seems to cause your wounds to immediately mend " \
                               "themselves."
            self.announce = "Jean notices a small glass vial on the ground with an odd pink fluid inside and a label " \
                            "reading, 'Restorative.'"

    def drink(self, player: 'Player') -> None:
        self.use(player)

    def use(self, player: 'Player') -> None:
        # Prevent using merchandise items until purchased
        if getattr(self, 'merchandise', False):
            cprint("You must purchase {} before using or equipping it.".format(self.name), "red")
            return
        if player.hp < player.maxhp:
            print(
               "Jean quaffs down the Restorative. The liquid burns slightly in his throat for a moment, before the \n"
               "sensation is replaced with a period of numbness. He feels his limbs getting a bit lighter, his \n"
               "muscles relaxing, and the myriad of scratches and cuts closing up.\n")
            amount: int = int((self.power * random.uniform(0.8, 1.2)))
            missing_hp: int = player.maxhp - player.hp
            if amount > missing_hp:
                amount = missing_hp
            player.hp += amount
            time.sleep(2)
            cprint("Jean recovered {} HP!".format(amount), "green")
            self.count -= 1
            self.stack_grammar()
            if self.count <= 0:
                player.inventory.remove(self)
        else:
            print("Jean is already at full health. He places the Restorative back into his bag.")


class Draught(Consumable):
    power: int

    def __init__(self, count: int = 1, merchandise: bool = False) -> None:
        super().__init__(name="Draught",
                         description="A green fluid giving off a warm, pleasant glow.\n"
                                     "Invigorating for any tired adventurer.",
                         value=75, weight=0.25, maintype="Consumable", subtype="Potion", count=count, merchandise=merchandise)
        self.power = 100
        self.count = count
        self.interactions = ["use", "drink", "drop"]
        self.announce = ("Jean notices a small glass bottle of glowing green fluid on the ground. "
                         "Its label reads, simply, 'Draught.'")

    def stack_grammar(self) -> None:
        if self.count > 1:
            self.description = "A box filled with bottles of a green fluid giving off a warm, pleasant glow.\n" \
                               "Invigorating for any tired adventurer.\n" \
                               "There appear to be {} bottles in the box.\n".format(self.count)
            self.announce = "There is a box of small glass bottles containing glowing green fluid here."
        else:
            self.description = "A green fluid giving off a warm, pleasant glow.\n" \
                               "Invigorating for any tired adventurer."
            self.announce = ("Jean notices a small glass bottle of glowing green fluid on the ground. "
                             "Its label reads, simply, 'Draught.'")

    def drink(self, player: 'Player') -> None:
        self.use(player)

    def use(self, player: 'Player') -> None:
        if getattr(self, 'merchandise', False):
            cprint("You must purchase {} before using or equipping it.".format(self.name), "red")
            return
        if player.hp < player.maxhp:
            print("Jean gulps down the {}. It's surprisingly sweet and warm. The burden of fatigue seems \n"
                  "to have lifted off of his shoulders for the time being.".format(self.name))
            amount: int = int((self.power * random.uniform(0.8, 1.2)))
            missing_fatigue: int = player.maxfatigue - player.fatigue
            if amount > missing_fatigue:
                amount = missing_fatigue
            player.fatigue += amount
            time.sleep(2)
            cprint("Jean recovered {} fatigue!".format(amount), "green")
            self.count -= 1
            self.stack_grammar()
            if self.count <= 0:
                player.inventory.remove(self)
        else:
            print("Jean is already fully rested. He places the {} back into his bag.".format(self.name))


class Antidote(Consumable):
    power: int

    def __init__(self, count: int = 1, merchandise: bool = False) -> None:
        super().__init__(name="Antidote",
                         description="A murky green fluid of questionable chemistry.\n"
                                     "Drinking it restores a small amount of health and \n"
                                     "neutralizes harmful toxins in the bloodstream.",
                         value=175, weight=0.25, maintype="Consumable", subtype="Potion", count=count, merchandise=merchandise)
        self.power = 15
        self.count = count
        self.interactions = ["use", "drink", "drop"]
        self.announce = "Jean notices a small glass bottle on the ground with a murky green fluid inside and a label " \
                        "reading, 'Antidote.'"

    def stack_grammar(self) -> None:
        if self.count > 1:
            self.description = "A box filled with bottles of a murky green fluid.\n" \
                               "Drinking one restores a small amount of health and \n" \
                               "neutralizes harmful toxins in the bloodstream. \n" \
                               "There appear to be {} vials in the box.\n".format(self.count)
            self.announce = "There is a box of small glass bottles containing a murky green fluid here."
        else:
            self.description = "A murky green fluid of questionable chemistry.\n" \
                               "Drinking it restores a small amount of health and \n" \
                               "neutralizes harmful toxins in the bloodstream."
            self.announce = ("Jean notices a small glass bottle on the ground with a murky green "
                             "fluid inside and a label reading, 'Antidote.'")

    def drink(self, player: 'Player') -> None:
        self.use(player)

    def use(self, player: 'Player') -> None:
        if getattr(self, 'merchandise', False):
            cprint("You must purchase {} before using or equipping it.".format(self.name), "red")
            return
        poisons: List[Any] = []
        for state in player.states:
            if hasattr(state, "statustype"):
                if getattr(state, 'statustype') == "poison":
                    poisons.append(state)

        if poisons:
            print("Jean sips gingerly at the Antidote. The liquid feels very cool as it slides thickly down \n"
                  "his throat. He shudders uncontrollably for a moment as the medicine flows into his \n"
                  "bloodstream, doing its work on whatever toxic agent made its home there.\n")
            amount: int = int((self.power * random.uniform(0.8, 1.2)))
            missing_hp: int = player.maxhp - player.hp
            if missing_hp > 0:
                if amount > missing_hp:
                    amount = missing_hp
                player.hp += amount
                time.sleep(2)
                cprint("Jean recovered {} HP!".format(amount), "green")
            for poison in poisons:
                poison.on_removal(poison.target)
                player.states.remove(poison)
            self.count -= 1
            self.stack_grammar()
            if self.count <= 0:
                player.inventory.remove(self)
            return
        else:
            print("Jean is not beset by poison. He places the Antidote back into his bag.")

# ---------------------------------------------------------------------------
# Arrows
# ---------------------------------------------------------------------------
class Arrow(Consumable):  # master class for arrows.
    power: Union[int, float]
    range_base_modifier: Union[int, float]
    range_decay_modifier: Union[int, float]
    sturdiness: Union[int, float]
    helptext: str
    effects: Optional[List[Any]]

    def __init__(self, name: str, description: str, value: Union[int, float], weight: Union[int, float], power: Union[int, float], range_base_modifier: Union[int, float], range_decay_modifier: Union[int, float], sturdiness: Union[int, float],
                 helptext: str, effects: Optional[List[Any]], count: int = 1, merchandise: bool = False,
                 enchantment_level: int = 0) -> None:
        super().__init__(name=name, description=description, value=value, weight=weight, maintype="Consumable",
                         subtype="Arrow", count=count, merchandise=merchandise, enchantment_level=enchantment_level)
        self.power = power
        self.count = count
        self.interactions = ["drop", "prefer"]
        self.announce = "Jean notices an arrow on the ground."
        self.range_base_modifier = range_base_modifier
        self.range_decay_modifier = range_decay_modifier
        self.sturdiness = sturdiness
        self.helptext = helptext
        self.effects = effects

    def stack_grammar(self) -> None:
        if self.count > 1:
            self.description = "A quiver of {}s.\n" \
                               "There appear to be {} arrows in the quiver.\n".format(self.name.lower(), self.count)
            self.announce = "There is a quiver of arrows here."
        else:
            self.description = "A standard arrow, to be fired with a bow."
            self.announce = "Jean notices an arrow on the ground."

    def prefer(self, player: 'Player') -> None:
        functions.add_preference(player, "arrow", self.name)


class WoodenArrow(Arrow):
    def __init__(self, count: int = 1, merchandise: bool = False, enchantment_level: int = 0) -> None:
        super().__init__(name="Wooden Arrow",
                         description="A useful device composed of a sharp tip, a shaft of sorts, and fletching. \n"
                                     "This one is made of wood. Wooden arrows are lightweight, "
                                     "so they generally improve accuracy at the cost of impact force. "
                                     "\nThey tend to break frequently.",
                         value=1, weight=0.05, power=20, range_base_modifier=1.2, range_decay_modifier=0.8,
                         sturdiness=0.4,
                         helptext=colored("+range, -decay, ", "green") + colored("-damage, -sturdiness", "red"),
                         effects=None, count=count, merchandise=merchandise, enchantment_level=enchantment_level)


class IronArrow(Arrow):
    def __init__(self, count: int = 1, merchandise: bool = False, enchantment_level: int = 0) -> None:
        super().__init__(name="Iron Arrow", description="A useful device composed of a sharp tip, "
                                                        "a shaft of sorts, and fletching. \
        This one is made of iron. Iron arrows are heavy and can be devastating up close. "
                                                        "They suffer, however, when it comes to range and "
                                                        "accuracy over long \
        distances. \nLike all metal arrows, they are considerably sturdier than other types of arrows.",
                         value=5, weight=0.25, power=30, range_base_modifier=0.7, range_decay_modifier=1.4,
                         sturdiness=0.6,
                         helptext=colored("+damage, +sturdiness, ", "green") + colored("-range, ++decay", "red"),
                         effects=None, count=count, merchandise=merchandise, enchantment_level=enchantment_level)


class GlassArrow(Arrow):
    def __init__(self, count: int = 1, merchandise: bool = False, enchantment_level: int = 0) -> None:
        super().__init__(name="Glass Arrow", description="A useful device composed of a sharp tip, "
                                                         "a shaft of sorts, and fletching. \
        This one is made of glass. It is of moderate weight and extremely sharp. \nAs you might expect, "
                                                         "arrows like this rarely survive the first shot.",
                         value=10, weight=0.1, power=40, range_base_modifier=1.1, range_decay_modifier=1,
                         sturdiness=0.1,
                         helptext=colored("+range, +damage, ", "green") + colored("~decay, ", "yellow") + colored(
                             "---sturdiness", "red"), effects=None, count=count, merchandise=merchandise,
                         enchantment_level=enchantment_level)


class FlareArrow(Arrow):
    def __init__(self, count: int = 1, merchandise: bool = False) -> None:
        super().__init__(name="Flare Arrow", description="A useful device composed of a sharp tip, a shaft of sorts, "
                                                         "and fletching. \
        This one is made of wood and bursts into flames upon impact."
                                                         "\nObviously, don't expect to get it back after firing.",
                         value=10, weight=0.05, power=25, range_base_modifier=1.2, range_decay_modifier=0.8,
                         sturdiness=0.0,
                         helptext=colored("+range, +damage, -decay, ", "green") + colored("----sturdiness", "red"),
                         effects=None, count=count, merchandise=merchandise)
        # todo add fire effect on impact

# ---------------------------------------------------------------------------
# Unique items
# ---------------------------------------------------------------------------
class AncientRelic(Special):
    """A rare relic. Serves as a very high value unique item.

    Marked by appearing in the predefined unique item list. Additional flavor
    attributes can be added later (e.g., lore hooks, quest flags).
    """
    def __init__(self, merchandise: bool = True) -> None:
        super().__init__(name="Ancient Relic",
                         description="A mysterious relic radiating latent, unknowable power. Its surface is etched "
                                     "with patterns that seem to shift when unobserved.",
                         value=10000, weight=1.0, maintype="Relic", subtype="Relic", merchandise=merchandise)
        # Flag baseline uniqueness (the condition will still overwrite / reinforce)
        setattr(self, 'unique', True)


class DragonHeartGem(Special):
    """Crystallized residue of a dragon's heart flame."""
    def __init__(self, merchandise: bool = True) -> None:
        super().__init__(name="Dragon Heart Gem",
                         description="A pulsing crimson gem that's warm to the touch. It hums faintly with residual "
                                     "draconic vitality.",
                         value=15000, weight=0.3, maintype="Relic", subtype="Gem", merchandise=merchandise)
        setattr(self, 'unique', True)
        self.add_resistance = {'fire': 0.30}  # example bonus for future systems


class CrystalTear(Special):
    """Prismatic tear-like crystal said to form where realities brush together."""
    def __init__(self, merchandise: bool = True) -> None:
        super().__init__(name="Crystal Tear",
                         description="A prismatic, tear-shaped crystal that refracts light into impossible spectrums."
                                     " It evokes a sense of distant memories.",
                         value=12000, weight=0.2, maintype="Relic", subtype="Crystal", merchandise=merchandise)
        setattr(self, 'unique', True)
        self.add_resistance = {'spiritual': 0.25}

# List of factories (callables returning new instances) used by UniqueItemInjectionCondition
unique_item_factories = [AncientRelic, DragonHeartGem, CrystalTear]
# Registry to track which unique item classes have been spawned in the universe
unique_items_spawned: set[str] = set()


class Book(Special):
    """
    A book that Jean can READ. Books are now items that can be carried in inventory.
    Optionally, an event may be tied to reading the book.
    """

    def __init__(self, name: str = "Book",
                 description: str = "A dusty old book, full of mysteries and sentiments.",
                 value: Union[int, float] = 5,
                 weight: Union[int, float] = 2.0,
                 event: Optional[Any] = None,
                 text: Optional[str] = None,
                 text_file_path: Optional[str] = None,
                 chars_per_page: int = 800,
                 merchandise: bool = False,
                 discovery_message: str = "a book!") -> None:
        super().__init__(name=name, description=description, value=value, weight=weight,
                         maintype="Book", subtype="Book", discovery_message=discovery_message,
                         merchandise=merchandise)
        self.event = event
        self.interactions.append('read')
        self.text_file_path = text_file_path
        self._text: Optional[str] = None  # Cache for loaded text
        
        # Priority: file path > explicit text parameter > blank message
        if text_file_path:
            # If file path is provided, text will be loaded lazily via property (even if text is also set)
            pass  # _text remains None for lazy loading
        elif text is not None:
            # If no file path but text is explicitly provided, use it
            self._text = text
        else:
            # No file path and no text means blank book
            self._text = "This book is mysteriously blank."
        
        self.chars_per_page = chars_per_page  # characters per page for pagination

    @property
    def text(self) -> str:
        """Lazy load text from file if needed."""
        if self._text is None and self.text_file_path:
            try:
                with open(self.text_file_path, 'r', encoding='utf-8') as f:
                    self._text = f.read()
            except Exception as e:
                cprint(f"Error loading book text from {self.text_file_path}: {e}", "red")
                self._text = "This book is mysteriously blank."
        return self._text if self._text else "This book is mysteriously blank."
    
    @text.setter
    def text(self, value: Optional[str]) -> None:
        """Allow direct setting of text (for deserialization)."""
        self._text = value

    def _paginate_text(self, text: str) -> list[str]:
        """Break text into pages of approximately chars_per_page characters, breaking at sentence boundaries."""
        if not text or len(text) <= self.chars_per_page:
            return [text] if text else []
        
        pages: list[str] = []
        current_page = ""
        
        # Split by sentences (basic sentence detection)
        sentences = text.replace('! ', '!|').replace('? ', '?|').replace('. ', '.|').split('|')
        
        for sentence in sentences:
            # If a single sentence is longer than chars_per_page, we need to force-split it
            if len(sentence) > self.chars_per_page:
                # If current_page has content, save it first
                if current_page.strip():
                    pages.append(current_page.strip())
                    current_page = ""
                
                # Split the long sentence into chunks
                while len(sentence) > self.chars_per_page:
                    pages.append(sentence[:self.chars_per_page].strip())
                    sentence = sentence[self.chars_per_page:]
                
                # Add remaining part to current page
                if sentence.strip():
                    current_page = sentence
                continue
            
            # If adding this sentence would exceed page limit and we have content, start new page
            if len(current_page) + len(sentence) > self.chars_per_page and current_page:
                pages.append(current_page.strip())
                current_page = sentence
            else:
                current_page += sentence
        
        # Add the last page if there's remaining content
        if current_page.strip():
            pages.append(current_page.strip())
        
        return pages if pages else [text]

    def _display_page(self, page_text: str, page_num: int, total_pages: int) -> None:
        """Display a single page with header and footer."""
        functions.screen_clear()
        cprint(f"--- {self.name} (Page {page_num} of {total_pages}) ---", "cyan")
        print()
        # Wrap text to 80 characters for readability
        import textwrap
        wrapped = textwrap.fill(page_text, width=80)
        print(wrapped)
        print()
        cprint(f"--- Page {page_num} of {total_pages} ---", "cyan")

    def _show_page_navigation(self, current_page: int, total_pages: int) -> str:
        """Display navigation options and get user input."""
        print()
        options: list[str] = []
        if current_page > 1:
            options.append(colored("P: Previous Page", "yellow"))
        if current_page < total_pages:
            options.append(colored("N: Next Page", "yellow"))
        options.append(colored("C: Close Book", "red"))
        
        print(" | ".join(options))
        
        choice = input(colored("Selection: ", "cyan")).strip().lower()
        return choice

    def read(self) -> None:
        """Read the book, with pagination for long texts."""
        if self.text:
            cprint("Jean begins reading...", color="cyan")
            time.sleep(0.5)
            
            # Check if text is long enough to paginate (threshold: ~600 chars)
            if len(self.text) > 600:
                pages = self._paginate_text(self.text)
                current_page = 1
                
                while True:
                    self._display_page(pages[current_page - 1], current_page, len(pages))
                    choice = self._show_page_navigation(current_page, len(pages))
                    
                    if choice in ('p', 'prev', 'previous') and current_page > 1:
                        current_page -= 1
                    elif choice in ('n', 'next') and current_page < len(pages):
                        current_page += 1
                    elif choice in ('c', 'close', 'x', 'exit'):
                        cprint("Jean closes the book.", "cyan")
                        break
                    else:
                        cprint("Invalid choice. Please try again.", "red")
                        time.sleep(1)
            else:
                # Short text - just print it normally
                functions.print_slow(self.text, speed="fast")
                functions.await_input()
        else:
            print(self.description)

        if self.event:
            time.sleep(0.5)
            self.event.process()
            if not getattr(self.event, 'repeat', False):
                self.event = None
            functions.await_input()
