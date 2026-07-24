"""
Merchant NPC classes — shop-keeping NPCs.

Merchant is a base class that combines NPC with MerchantShopMixin and adds
the buy/sell/trade verbs.  MiloCurioDealer and JamboHealsU are concrete
merchant subclasses with their own inventories and shop personalities.
"""

from pathlib import Path

import src.functions as functions  # type: ignore
from src.items import (  # type: ignore
    Item,
    Shortsword,
    Gold,
    Restorative,
    Draught,
    Antidote,
    Rock,
    Spear,
    Consumable,
    Dagger,
    Weapon,
    Armor,
    PaddedJerkin,
    LeatherArmor,
    StuddedLeather,
)

from ._base import NPC
from ._shop import MerchantShopMixin
from ._chat_llm import ConversationalNPCMixin
from src.narration import narrate

_HUMAN_NPC_DIR = Path(__file__).resolve().parent.parent.parent / "ai" / "npc" / "human"


class Merchant(NPC, MerchantShopMixin):
    def __init__(
        self,
        name: str,
        description: str,
        damage: int,
        aggro: bool,
        exp_award: int,
        stock_count: int,
        inventory: list[Item] = None,
        specialties: list[type[Item]] = None,
        enchantment_rate: float = 1.0,
        always_stock: list[Item] = None,
        base_gold: int = 300,
        maxhp=100,
        protection=0,
        speed=10,
        finesse=10,
        awareness=10,
        maxfatigue=100,
        endurance=10,
        strength=10,
        charisma=10,
        intelligence=10,
        faith=10,
        hidden=False,
        hide_factor=0,
        combat_range=(0, 5),
        idle_message=" is here.",
        alert_message="glares sharply at Jean!",
        discovery_message="someone interesting.",
        target=None,
    ):
        super().__init__(
            name=name,
            description=description,
            damage=damage,
            aggro=aggro,
            exp_award=exp_award,
            inventory=inventory,
            maxhp=maxhp,
            protection=protection,
            speed=speed,
            finesse=finesse,
            awareness=awareness,
            maxfatigue=maxfatigue,
            endurance=endurance,
            strength=strength,
            charisma=charisma,
            intelligence=intelligence,
            faith=faith,
            hidden=hidden,
            hide_factor=hide_factor,
            combat_range=combat_range,
            idle_message=idle_message,
            alert_message=alert_message,
            discovery_message=discovery_message,
            target=target,
        )
        self.keywords = ["buy", "sell", "trade", "talk"]
        self.specialties = (
            specialties  # List of item classes the merchant specializes in
        )
        if self.specialties is None:
            self.specialties = []
        self.enchantment_rate = enchantment_rate  # 0 to 10.0 with 0 being none and 10 being 10x the normal rate
        self.stock_count = (
            stock_count  # Number of items to keep in stock after each refresh
        )
        self.always_stock = (
            always_stock  # List of item classes the merchant always keeps in stock
        )
        self.base_gold = (
            base_gold  # Amount of gold the merchant has to buy items from the player
        )
        self.shop_conditions = {"value": [], "availability": [], "unique": []}
        self.initialize_shop()

    def talk(self, player):
        narrate(self.name + " has nothing to say.")

    def trade(self, player):
        """
        Called when the player trades with the merchant. The web client drives
        buying/selling through the /shop/* routes; this engine verb only absorbs
        any merchandise Jean carried over so it surfaces in the Buy list.
        """
        narrate(f"{self.name} is ready to trade with you.")
        self._collect_player_merchandise(player)

    def buy(self, player):
        self.trade(player)

    def sell(self, player):
        self.trade(player)


class MiloCurioDealer(Merchant):
    def __init__(self):
        # Enchanted Weapon
        enchanted_sword = Shortsword(merchandise=True)
        functions.add_random_enchantments(enchanted_sword, 5)
        # Gold
        gold_pouch = Gold(amt=100)
        # Milo's inventory
        self.inventory = [
            Restorative(count=100, merchandise=True),
            Rock(merchandise=True),
            Spear(merchandise=True),
            enchanted_sword,
            gold_pouch,
        ]
        self.base_gold = 5000
        super().__init__(
            name="Milo the Traveling Curio Dealer",
            description="A spry, eccentric merchant with a patchwork coat and a twinkle in his eye. "
            "Milo claims to have traveled the world, collecting rare oddities and useful adventuring gear.",
            damage=2,
            aggro=False,
            exp_award=0,
            inventory=self.inventory,
            maxhp=50,
            protection=2,
            speed=12,
            finesse=14,
            charisma=18,
            intelligence=16,
            stock_count=30,
            base_gold=self.base_gold,
        )
        self.shop_name = "The Wandering Curiosities Shop"

    def talk(self, player):  # noqa
        narrate(
            "Milo grins: 'Looking for something rare, friend? I've got just the thing!'"
        )

    def trade(self, player):
        narrate(
            "Milo opens his patchwork coat, revealing a dazzling array of curiosities."
        )
        # Collect merchandise items first (in case Jean picked something up on Milo's floor)
        self._collect_player_merchandise(player)


class JamboHealsU(Merchant):
    """Apothecary-style merchant who always keeps core potions in stock

    Always-stock is limited to common consumable potions; only a few
    spare/random slots are filled on restock (small stock_count).
    """

    def __init__(self):
        # Starter inventory so shop works before first restock
        always_stock = [
            Restorative(count=5, merchandise=True),
            Draught(count=4, merchandise=True),
            Antidote(count=3, merchandise=True),
        ]
        specialties = [Consumable]
        self.inventory = []
        super().__init__(
            name="Jambo",
            description="A wiry, dark-skinned merchant always wearing an oversized turban and a massive grin.",
            damage=1,
            aggro=False,
            exp_award=0,
            stock_count=6,  # only a few spare slots for random stock
            inventory=self.inventory,
            specialties=specialties,
            enchantment_rate=0.0,  # potions are not enchanted
            always_stock=always_stock,
            base_gold=800,
            maxhp=35,
            protection=1,
            speed=10,
            finesse=12,
            charisma=14,
            intelligence=14,
        )
        self.shop_name = "Jambo Heals U"

    def talk(self, player):  # pragma: no cover - simple flavor
        on_nomad_camp = (
            getattr(player, "map", None) is not None
            and player.map.get("name") == "eastern-descent-nomad-camp"
        )
        gorran_in_party = any(
            getattr(a, "name", "") == "Gorran"
            for a in getattr(player, "combat_list_allies", [])
        )

        lines = [
            # always available
            (
                "\"The road west is long,\" Jambo says, not unkindly. \"Jambo has been west. "
                "The west does not care if Jean is prepared. Jambo cares. "
                "This is the difference. Come, let us fix this.\""
            ),
            (
                "Jambo studies Jean for a moment with his merchant's eye. "
                "\"Jean looks like someone who has been sleeping somewhere cold "
                "and eating somewhere worse. A Restorative. Maybe two. "
                "Jambo recommends this strongly.\""
            ),
            (
                "\"River crossings — Jambo has always said this — very good for business. "
                "People come from the mountains. People go to the plains. "
                "Everybody needs something in the middle. "
                "Jambo is always in the middle. This is not an accident.\""
            ),
        ]

        if on_nomad_camp:
            lines.append(
                "Jambo gestures at the river with evident satisfaction. "
                "\"Good crossing, this. Steady traffic. Everybody tired, everybody needs "
                "something. Jambo has timed this very well.\""
            )

        if gorran_in_party:
            lines.append(
                "Jambo glances at Gorran with the look of a man mentally cataloguing "
                "a new market segment. \"Jambo has sold to many interesting customers. "
                "The stone one — does he need potions? Jambo thinks not. "
                "Jambo asks anyway. This is good business practice.\""
            )

        narrate(random.choice(lines))

    def trade(self, player):
        # Collect any merchandise Jean brought in so it appears in the Buy list.
        self._collect_player_merchandise(player)


class Kaelen(ConversationalNPCMixin, Merchant):
    """Weaponsmith and co-proprietor of Iron & Oath arms & armor stall.
    Passionate about metallurgy and weapon balance, deeply loyal to Vespera.
    """

    def __init__(self):
        always_stock = [
            Shortsword(merchandise=True),
            Spear(merchandise=True),
            Dagger(merchandise=True),
        ]
        specialties = [Weapon]
        inventory = []
        super().__init__(
            name="Kaelen",
            description=(
                "A broad-shouldered weaponsmith with a full, rugged beard singed pale in spots "
                "from forge sparks. He stands at the Iron & Oath counter, filing a pommel with "
                "the focused efficiency of a master craftsman."
            ),
            damage=2,
            aggro=False,
            exp_award=0,
            stock_count=12,
            inventory=inventory,
            specialties=specialties,
            enchantment_rate=0.0,
            always_stock=always_stock,
            base_gold=1200,
            maxhp=110,
            protection=4,
            speed=10,
            finesse=12,
            charisma=14,
            intelligence=15,
            strength=16,
            idle_message=" is examining the balance of a shortsword.",
            alert_message=" looks up, hand resting on an anvil hammer.",
            discovery_message="a rugged weaponsmith at the Iron & Oath stall.",
        )
        self.shop_name = "Iron & Oath"
        self._chat_config_path = str(_HUMAN_NPC_DIR / "kaelen.json")
        self._init_chat_attrs()

    def talk(self, player):
        lines = [
            "Kaelen holds up a blade to the light, checking the edge. 'Feel the balance where the guard "
            "meets the tang, Jean. That's three hours of hammer work right there.'",
            "Kaelen nods toward Vespera with a quiet grin. 'Listen to her on the armor fittings. "
            "I make the steel hold an edge, but Vespera makes sure you live to swing it.'",
            "Kaelen turns a spear in his hands. 'The road west is hard on iron. If you need a nick "
            "filed out before crossing, set it on the block.'",
            "Kaelen's eyes track to Gorran's stone shoulder. 'That's natural granite weave... "
            "Fascinating structure. You couldn't forge plates like that if you had a bellows the size of a barn.'",
        ]
        narrate(random.choice(lines))


class Vespera(ConversationalNPCMixin, Merchant):
    """Armor specialist and commercial co-proprietor of Iron & Oath.
    Sharp, commercial, protective of travelers, deeply loyal to Kaelen.
    """

    def __init__(self):
        always_stock = [
            PaddedJerkin(merchandise=True),
            LeatherArmor(merchandise=True),
            StuddedLeather(merchandise=True),
        ]
        specialties = [Armor]
        inventory = []
        super().__init__(
            name="Vespera",
            description=(
                "A sharp, poised armorer with dark hair bound in a braid threaded with brass wire. "
                "Her dark leather harness holds awls and calipers, and a leather-bound merchant's "
                "ledger rests on the Iron & Oath counter beside her."
            ),
            damage=1,
            aggro=False,
            exp_award=0,
            stock_count=12,
            inventory=inventory,
            specialties=specialties,
            enchantment_rate=0.0,
            always_stock=always_stock,
            base_gold=1200,
            maxhp=95,
            protection=5,
            speed=11,
            finesse=14,
            charisma=16,
            intelligence=16,
            idle_message=" is inspecting the strap alignment on a leather doublet.",
            alert_message=" looks up, ledger in hand.",
            discovery_message="a sharp-eyed armorer at the Iron & Oath stall.",
        )
        self.shop_name = "Iron & Oath"
        self._chat_config_path = str(_HUMAN_NPC_DIR / "vespera.json")
        self._init_chat_attrs()

    def talk(self, player):
        lines = [
            "Vespera runs a finger along the seam of a doublet. 'A good sword gets all the glory, Jean, "
            "but two inches of boiled leather over the ribs keeps your heart inside where it belongs.'",
            "Vespera glances at Kaelen with a fond, quiet smile. 'Don't mind his lecture on coal temperature. "
            "He forged the steel, but I set the price and guarantee the fit.'",
            "Vespera says, 'Take your time looking through the racks. We buy fair, we sell honest, and we "
            "don't sell garbage to people heading into the Badlands.'",
            "Vespera checks a strap buckle. 'The river damp gets into iron faster than you think. Keep your "
            "harness oiled before crossing.'",
        ]
        narrate(random.choice(lines))

