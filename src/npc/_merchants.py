"""
Merchant NPC classes — shop-keeping NPCs.

Merchant is a base class that combines NPC with MerchantShopMixin and adds
the buy/sell/trade verbs.  MiloCurioDealer and JamboHealsU are concrete
merchant subclasses with their own inventories and shop personalities.
"""

import functions  # type: ignore
from items import (  # type: ignore
    Item,
    Shortsword,
    Gold,
    Restorative,
    Draught,
    Antidote,
    Rock,
    Spear,
    Consumable,
)

from ._base import NPC
from ._shop import MerchantShopMixin


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
        self.shop = None
        self.initialize_shop()

    def talk(self, player):
        print(self.name + " has nothing to say.")

    def trade(self, player):
        """
        This method is called when the player wants to trade with the merchant.
        It should handle the trading logic, such as buying and selling items.
        """
        print(f"{self.name} is ready to trade with you.")
        # First, absorb any merchandise Jean carried over so it appears in the Buy menu.
        self._collect_player_merchandise(player)
        if self.shop:
            self.shop.player = player
            self.shop.run()

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
        if self.shop:
            self.shop.exit_message = (
                "Milo nods as you leave his shop, "
                "already looking for new curiosities to add to his collection."
            )

    def talk(self, player):  # noqa
        print(
            "Milo grins: 'Looking for something rare, friend? I've got just the thing!'"
        )

    def trade(self, player):
        print(
            "Milo opens his patchwork coat, revealing a dazzling array of curiosities."
        )
        # Collect merchandise items first (in case Jean picked something up on Milo's floor)
        self._collect_player_merchandise(player)
        # Local import to avoid circular import at module load
        from interface import ShopInterface as Shop

        shop = Shop(
            merchant=self,
            player=player,
            shop_name="The Wandering Curiosities Shop",
        )
        shop.run()


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

    def talk(self, player):  # pragma: no cover - simple flavor
        print(
            "Jambo chuckles: 'Feeling a bit under the weather, friend? Well no worry; Jambo Heals U! "
            "Come and see my selection of potions and draughts!'"
        )

    def trade(self, player):
        # Collect any merchandise Jean brought in so it appears in the Buy list.
        self._collect_player_merchandise(player)
        # Local import to avoid circular import at module load
        from interface import ShopInterface as Shop

        self.shop = Shop(merchant=self, player=player, shop_name="Jambo Heals U")
        self.shop.exit_message = (
            "Jambo waves enthusiastically and loudly calls out, "
            "'Jambo wishes you well on your travels "
            "and don't forget: When you blue, Jambo Heals U!'"
        )
        self.shop.player = player
        self.shop.run()
