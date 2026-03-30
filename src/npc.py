import random
import genericng  # type: ignore
import moves  # type: ignore
import functions  # type: ignore
import loot_tables  # type: ignore
from items import (
    Item,
    Shortsword,
    Gold,
    Restorative,
    Draught,
    Antidote,
    Rock,
    Spear,
    Consumable,
)  # type: ignore
from neotermcolor import colored, cprint
from combatant import Combatant
from npc_shop_mixin import MerchantShopMixin  # type: ignore
from npc_mynx_mixin import MynxLLMMixin  # type: ignore

loot = loot_tables.Loot()  # initialize a loot object to access the loot table


class NPC(Combatant):
    alert_message = "appears!"

    def __init__(
        self,
        name,
        description,
        damage,
        aggro,
        exp_award,
        inventory: list[Item] = None,
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
        idle_message=" is shuffling about.",
        alert_message="glares sharply at Jean!",
        discovery_message="something interesting.",
        target=None,
        friend=False,
    ):
        self.name = name
        self.description = description
        self.current_room = None
        # Preserve provided inventory instead of always clobbering it
        self.inventory: list[Item] = inventory if inventory is not None else []
        self.idle_message = idle_message
        self.alert_message = alert_message
        self.maxhp = maxhp
        self.maxhp_base = maxhp
        self.hp = maxhp
        self.damage = damage
        self.damage_base = damage
        self.protection = protection
        self.protection_base = protection
        self.speed = speed
        self.speed_base = speed
        self.finesse = finesse
        self.finesse_base = finesse
        # Resistance dicts are defined canonically in Combatant (combatant.py).
        self._init_resistances()
        self.awareness = awareness  # used when a player enters the room to see if npc spots the player
        self.aggro = aggro
        self.exp_award = exp_award
        self.exp_award_base = exp_award
        self.maxfatigue = maxfatigue
        self.maxfatigue_base = maxfatigue
        self.endurance = endurance
        self.endurance_base = endurance
        self.strength = strength
        self.strength_base = strength
        self.charisma = charisma
        self.charisma_base = charisma
        self.intelligence = intelligence
        self.intelligence_base = intelligence
        self.faith = faith
        self.faith_base = faith
        self.fatigue = self.maxfatigue
        self.target = target
        self.known_moves = [moves.NpcRest(self)]
        self.current_move = None
        self.states = []
        self.in_combat = False
        self.combat_proximity = (
            {}
        )  # dict for unit proximity: {unit: distance}; Range for most melee weapons is 5,
        # ranged is 20. Distance is in feet (for reference)
        self.combat_position = None  # CombatPosition object; None outside combat. Source of truth for positioning
        self.default_proximity = 20
        self.hidden = hidden
        self.hide_factor = hide_factor
        self.discovery_message = discovery_message
        self.friend = friend  # Is this a friendly NPC? Default is False (enemy). Friends will help Jean in combat.
        self.combat_delay = (
            0  # initial delay for combat actions. Typically randomized on unit spawn
        )
        self.combat_range = combat_range  # similar to weapon range, but is an attribute to the NPC since
        # NPCs don't equip items
        self.loot = loot.lev0
        self.keywords = (
            []
        )  # action keywords to hook up an arbitrary command like "talk" for a friendly NPC
        self.pronouns = {
            "personal": "it",
            "possessive": "its",
            "reflexive": "itself",
            "intensive": "itself",
        }
        self.player_ref = (
            None  # Will be set during combat initialization for config access
        )
        self.ai_config = None  # Initialized during combat

    def die(self):
        really_die = self.before_death()
        if really_die:
            print(colored(self.name, "magenta") + " exploded into fragments of light!")

    def select_move(self):
        available_moves = self.refresh_moves()

        # Initialize AI config if we have a player reference (combat started)
        if (
            (not hasattr(self, "ai_config") or self.ai_config is None)
            and hasattr(self, "player_ref")
            and self.player_ref
        ):
            try:
                from npc_ai_config import NPCAIConfig

                self.ai_config = NPCAIConfig(self.player_ref)
            except ImportError:
                pass

        #  simple random selection; if you want something more complex, overwrite this for the specific NPC
        weighted_moves = []
        for move in available_moves:
            # Calculate tactical weight modifications
            weight = move.weight
            if hasattr(self, "ai_config") and self.ai_config:
                weight += self.ai_config.get_weighted_move_bonus(self, move.name)

            # Ensure at least 1 weight for viable moves
            weight = max(1, weight)

            for _ in range(weight):
                weighted_moves.append(move)

        if not weighted_moves:
            # Fallback if no moves generated
            return

        # If no offensive move is both affordable and viable, rest to recover fatigue.
        # This prevents the NPC from idling forever when the preferred attack costs more
        # fatigue than is currently available (e.g. after 2+ attacks drain the pool).
        # Use available_moves (deduplicated) rather than weighted_moves to avoid calling
        # viable() multiple times on the same object due to weight expansion.
        # Use getattr in case a move was created via __new__ without calling Move.__init__.
        can_attack = any(
            getattr(m, "category", "") == "Offensive"
            and m.fatigue_cost <= self.fatigue
            and m.viable()
            for m in available_moves
        )
        if not can_attack and self.fatigue < self.maxfatigue:
            # Only force-rest when advancing is not an option.  If a viable Advance move
            # exists the NPC should close distance rather than stand still and recover.
            can_advance = any(
                getattr(m, "name", "") == "Advance" for m in available_moves
            )
            if not can_advance:
                self.current_move = moves.NpcRest(self)
                return

        num_choices = len(weighted_moves) - 1
        max_attempts = 20  # Prevent infinite loops
        attempts = 0
        choice = 0

        while self.current_move is None and attempts < max_attempts:
            attempts += 1
            choice = random.randint(0, num_choices)
            if (weighted_moves[choice].fatigue_cost <= self.fatigue) and weighted_moves[
                choice
            ].viable():
                self.current_move = weighted_moves[choice]

        # Hard fallback: if all 20 random attempts failed, rest rather than doing nothing.
        if self.current_move is None:
            self.current_move = moves.NpcRest(self)
            return

        # Log NPC decision if debug tracing is enabled
        if hasattr(self, "player_ref") and self.player_ref:
            player = self.player_ref
            if hasattr(player, "combat_debug_manager") and player.combat_debug_manager:
                if player.combat_debug_manager.should_debug_ai_decisions():
                    flank_bonus = 0
                    retreat_prio = 0
                    if hasattr(self, "ai_config") and self.ai_config:
                        flank_bonus = self.ai_config.get_weighted_move_bonus(
                            self, self.current_move.name
                        )
                        retreat_prio = self.ai_config.calculate_retreat_priority(
                            self, []
                        )
                    player.combat_debug_manager.display_ai_debug_info(
                        self,
                        f"Selected {self.current_move.name}",
                        {
                            "fatigue_cost": self.current_move.fatigue_cost,
                            "original_weight": weighted_moves[choice].weight,
                            "ai_bonus": flank_bonus,
                            "retreat_priority": retreat_prio,
                        },
                    )

    def add_move(self, move, weight=1):
        """Adds a move to the NPC's known move list. Weight is the number of times to add."""
        self.known_moves.append(move)
        move.weight = weight

    def drop_inventory(self):
        if len(self.inventory) > 0:
            for item in self.inventory:
                quantity = 1
                if hasattr(item, "count"):
                    quantity = item.count
                loopcount = quantity
                while loopcount > 0:
                    if random.random() > 0.6:
                        quantity -= 1
                    loopcount -= 1
                if quantity > 0:
                    self.current_room.spawn_item(
                        item.__class__.__name__,
                        amt=quantity,
                        hidden=1,
                        hfactor=random.randint(20, 60),
                    )
                    # In API combat mode, record drops for victory summary
                    if (
                        hasattr(self, "player_ref")
                        and self.player_ref
                        and hasattr(self.player_ref, "_combat_adapter")
                    ):
                        if not hasattr(self.player_ref, "combat_drops"):
                            self.player_ref.combat_drops = []
                        item_name = getattr(item, "name", item.__class__.__name__)
                        self.player_ref.combat_drops.append(
                            {
                                "name": item_name,
                                "quantity": int(quantity),
                                "source": getattr(self, "name", "Unknown"),
                                "kind": "inventory",
                            }
                        )
            self.inventory = []

    def before_death(
        self,
    ):  # Overwrite for each NPC if they are supposed to do something special before dying
        if self.loot:
            self.roll_loot()  # checks to see if an item will drop
        self.drop_inventory()
        return True

    def reset_combat_moves(self):
        """
        Resets all move states to stage 0 with 0 beats remaining.
        This ensures moves progress correctly when the NPC joins combat mid-fight.
        Called by combat_engage() and when allies join mid-combat.
        """
        for move in self.known_moves:
            move.current_stage = 0
            move.beats_left = 0

    def combat_engage(self, player):
        """
        Adds NPC to the proper combat lists and initializes.
        Resets all move states to ensure moves progress correctly from the start.
        """
        player.combat_list.append(self)
        player.combat_proximity[self] = int(
            self.default_proximity * random.uniform(0.75, 1.25)
        )
        if len(player.combat_list_allies) > 0:
            for ally in player.combat_list_allies:
                ally.combat_proximity[self] = int(
                    self.default_proximity * random.uniform(0.75, 1.25)
                )
        self.in_combat = True
        self.reset_combat_moves()

    def roll_loot(
        self,
    ):  # when the NPC dies, do a roll to see if any loot drops
        if self.current_room is None:
            print("### ERR: Current room for {} ({}) is None".format(self.name, self))
            return
        # Shuffle the dict keys to create random access
        keys = list(self.loot.keys())
        random.shuffle(keys)
        for item in keys:
            roll = random.randint(0, 100)
            if self.loot[item]["chance"] >= roll:  # success!
                dropcount = functions.randomize_amount(self.loot[item]["qty"])
                if (
                    "Equipment" in item
                ):  # ex Equipment_1_0 will yield an item at level 1 with no enchantments;
                    # Equipment_0_2 will yield an item at level 0 with 2 enchantment points
                    params = item.split("_")
                    item = loot.random_equipment(
                        self.current_room, params[1], params[2]
                    )
                    drop = item
                else:
                    drop = self.current_room.spawn_item(item, dropcount)
                cprint(
                    "{} dropped {} x {}!".format(self.name, drop.name, dropcount),
                    "cyan",
                    attrs=["bold"],
                )
                # In API combat mode, record drops for victory summary
                if (
                    hasattr(self, "player_ref")
                    and self.player_ref
                    and hasattr(self.player_ref, "_combat_adapter")
                ):
                    if not hasattr(self.player_ref, "combat_drops"):
                        self.player_ref.combat_drops = []
                    drop_name = getattr(drop, "name", str(drop))
                    self.player_ref.combat_drops.append(
                        {
                            "name": drop_name,
                            "quantity": int(dropcount),
                            "source": getattr(self, "name", "Unknown"),
                            "kind": "loot",
                        }
                    )
                break  # only one item in the loot table will drop


# --- Merchants ---


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


# --- Friends ---


class Friend(NPC):
    def __init__(
        self,
        name,
        description,
        damage,
        aggro,
        exp_award,
        inventory=None,
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
        alert_message="gets ready for a fight!",
        discovery_message="someone here.",
        target=None,
        friend=True,
    ):
        self.keywords = ["talk"]
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
            friend=friend,
        )

    def talk(self, player):
        print(self.name + " has nothing to say.")


# Mynx: a friendly, non-combatant monkey-cat hybrid NPC with LLM-driven interaction hooks.
class Mynx(MynxLLMMixin, Friend):
    """A small, nimble forest creature (mynx) that is friendly to the player and cannot fight.

    Behavior and interaction methods are provided as stubs so an LLM can be integrated later.
    """

    def __init__(self, name: str = None, description: str | None = None):
        if name is None:
            name = "Mynx " + genericng.generate(1, 3)
        if description is None:
            description = (
                "A small, nimble creature with spotted fur, a prehensile tufted tail, and bright curious eyes. "
                "It chirrs and chatters but cannot speak human words."
            )
        # Damage is zero and aggro False; exp_award 0 since it's non-combatant
        super().__init__(
            name=name,
            description=description,
            damage=0,
            aggro=False,
            exp_award=0,
            inventory=None,
            maxhp=30,
            protection=1,
            speed=18,
            finesse=16,
            awareness=20,
            maxfatigue=50,
            endurance=8,
            strength=4,
            charisma=14,
            intelligence=12,
            faith=6,
            hidden=False,
            hide_factor=0,
            combat_range=(0, 0),
            idle_message=" flicks its tail.",
            alert_message="startles and chatters!",
            discovery_message="a curious mynx.",
        )

        # Mynx-specific traits
        self.pronouns = {
            "personal": "it",
            "possessive": "its",
            "reflexive": "itself",
            "intensive": "itself",
        }
        self.keywords = ["talk", "pet", "play"]

        # Ensure the mynx never enters combat
        self.in_combat = False
        self._combat_disabled = True

        # Minimal move set (no attacks)
        try:
            self.known_moves = [moves.NpcIdle(self)]
        except Exception:
            self.known_moves = []

        # Basic state useful for LLM-driven behavior
        self._llm_last_response = None
        # Lazy-initialized LLM adapter
        self._llm_adapter = None
        # Cached player (Jean) advisor data
        self._jean_advisor = None
        # Short LLM interaction history: list of {'prompt': str, 'response': str}, most recent last
        self._llm_history: list[dict] = []

    def combat_engage(self, player):
        """Override to prevent the mynx from entering combat.
        This intentionally does nothing; mynx can never be attacked or enter combat by design.
        """
        # Keep flags consistent but do not add to player's combat lists
        self.in_combat = False
        return

    def can_enter_combat(self) -> bool:
        return False

    # Override talk to use the interaction framework
    def talk(self, player, prompt: str | None = None, structured: bool = False):
        try:
            return self.interact_with_player(
                player, prompt=prompt, structured=structured
            )
        except Exception:
            print(f"{self.name} tilts its head and makes a confused chitter.")
            return None

    def pet(self, player=None, structured: bool = False):
        return self.interact_with_player(player, prompt="pet", structured=structured)

    def play(self, player=None, item=None, structured: bool = False):
        prompt = "play"
        if item:
            prompt = f"play with {str(item)}"
        return self.interact_with_player(player, prompt=prompt, structured=structured)


class Gorran(Friend):  # The "rock-man" that helps Jean at the beginning of the game.
    def __init__(self):
        description = """
A massive creature that somewhat resembles a man,
except he is covered head-to-toe in rock-like armor. He seems a bit clumsy and his
speech is painfully slow and deep. He seems to prefer gestures over actual speech,
though this makes his intent a bit difficult to interpret. At any rate, he seems
friendly enough to Jean.
"""
        super().__init__(
            name="Rock-Man",
            description=description,
            maxhp=200,
            damage=55,
            awareness=20,
            speed=5,
            aggro=True,
            exp_award=0,
            combat_range=(0, 7),
            idle_message=" is bumbling about.",
            alert_message=" lets out a deep and angry rumble!",
        )
        self.add_move(moves.NpcAttack(self), 4)
        self.add_move(moves.Advance(self), 4)
        self.add_move(moves.GorranClub(self), 3)
        self.add_move(moves.NpcIdle(self))
        self.add_move(moves.Parry(self), 2)
        self.keywords = ["talk"]
        self.pronouns = {
            "personal": "he",
            "possessive": "his",
            "reflexive": "himself",
            "intensive": "himself",
        }

    def before_death(self):
        print(
            colored(self.name, "yellow", attrs=["bold"]) + " quaffs one of his potions!"
        )
        self.fatigue /= 2
        self.hp = self.maxhp
        return False

    def talk(self, player):
        if self.current_room.universe.story["gorran_first"] == "0":
            self.current_room.events_here.append(
                functions.seek_class("AfterGorranIntro", "story")(
                    player, self.current_room, None, False
                )
            )
            self.current_room.universe.story["gorran_first"] = "1"
        else:
            print(self.name + " has nothing to say.")


class Slime(NPC):
    def __init__(self):
        description = "Goop that moves. Gross."
        super().__init__(
            name="Slime " + genericng.generate(4, 5),
            description=description,
            maxhp=10,
            damage=20,
            awareness=12,
            aggro=True,
            exp_award=1,
            idle_message=" is glopping about.",
            alert_message="burbles angrily at Jean!",
        )
        self.add_move(moves.NpcAttack(self), 5)
        self.add_move(moves.Advance(self), 4)
        self.add_move(moves.NpcIdle(self))
        self.add_move(moves.Dodge(self))


class Testexp(NPC):
    def __init__(self):
        description = "Goop that moves. Gross."
        super().__init__(
            name="Slime " + genericng.generate(4, 5),
            description=description,
            maxhp=200,
            damage=2,
            awareness=12,
            aggro=True,
            exp_award=500,
            idle_message=" is glopping about.",
            alert_message="burbles angrily at Jean!",
        )
        self.add_move(moves.NpcAttack(self), 5)
        self.add_move(moves.Advance(self), 4)
        self.add_move(moves.NpcIdle(self))
        self.add_move(moves.Dodge(self))


class RockRumbler(NPC):
    def __init__(self):
        description = (
            "A burly creature covered in a rock-like carapace somewhat resembling a stout crocodile."
            "Highly resistant to most weapons. You'd probably be better off avoiding combat with this"
            "one."
        )
        super().__init__(
            name="Rock Rumbler " + genericng.generate(2, 4),
            description=description,
            maxhp=30,
            damage=22,
            protection=30,
            awareness=25,
            aggro=True,
            exp_award=100,
        )
        self.resistance_base["earth"] = 0.5
        self.resistance_base["fire"] = 0.5
        self.resistance_base["crushing"] = 1.5
        self.resistance_base["piercing"] = 0.5
        self.resistance_base["slashing"] = 0.5
        self.add_move(moves.NpcAttack(self), 5)
        self.add_move(moves.Advance(self), 4)
        self.add_move(moves.Withdraw(self))
        self.add_move(moves.NpcIdle(self))
        self.add_move(moves.Dodge(self))


class Lurker(NPC):
    def __init__(self):
        description = (
            "A grisly demon of the dark. Its body is vaguely humanoid in shape. Long, thin arms end"
            "in sharp, poisonous claws. It prefers to hide in the dark, making it difficult to surprise."
        )
        super().__init__(
            name="Lurker " + genericng.generate(2, 4),
            description=description,
            maxhp=250,
            damage=25,
            protection=0,
            awareness=60,
            endurance=20,
            aggro=True,
            exp_award=800,
        )
        self.loot = loot.lev1
        self.resistance_base["dark"] = 0.5
        self.resistance_base["fire"] = -0.5
        self.resistance_base["light"] = -2
        self.status_resistance_base["death"] = 1
        self.status_resistance_base["doom"] = 1
        self.add_move(moves.NpcAttack(self), 5)
        self.add_move(moves.VenomClaw(self), 5)
        self.add_move(moves.Advance(self), 4)
        self.add_move(moves.Withdraw(self))
        self.add_move(moves.NpcIdle(self))
        self.add_move(moves.Dodge(self), 2)


class GiantSpider(NPC):
    def __init__(self):
        description = (
            "A humongous spider, covered in black, wiry hairs. It skitters about, looking for its next "
            "victim to devour It flexes its sharp, poisonous mandibles in eager anticipation, "
            "spilling toxic drool that leaves a glowing green "
            "trail in its wake. Be careful that you don't fall victim to its bite!"
        )
        super().__init__(
            name="Giant Spider " + genericng.generate(1),
            description=description,
            maxhp=110,
            damage=22,
            protection=0,
            awareness=30,
            endurance=10,
            aggro=True,
            exp_award=120,
        )
        self.resistance_base["fire"] = -0.5
        self.status_resistance_base["poison"] = 1
        self.add_move(moves.NpcAttack(self), 3)
        self.add_move(moves.SpiderBite(self), 6)
        self.add_move(moves.Advance(self), 4)
        self.add_move(moves.Withdraw(self))
        self.add_move(moves.NpcIdle(self))
        self.add_move(moves.Dodge(self), 2)


class CaveBat(NPC):
    def __init__(self):
        description = (
            "A small, leathery-winged mammal that nests in caverns and ambushes from above. "
            "Fragile alone but dangerous in numbers; some variants nibble at blood and drain a little life."
        )
        super().__init__(
            name="Cave Bat " + genericng.generate(2, 4),
            description=description,
            maxhp=8,
            damage=18,
            protection=0,
            awareness=14,
            speed=40,
            aggro=True,
            exp_award=4,
            idle_message=" is hanging from the ceiling.",
            alert_message="screeches and dives!",
        )
        # Flavor resistances: bats are more vulnerable to light, indifferent to earth
        self.resistance_base["light"] = 0.8
        self.resistance_base["earth"] = 1.1
        # Some variants may have a small life-drain implemented elsewhere; leave hooks in status_resistance
        self.status_resistance_base["poison"] = 1.0
        # Movement and combat style
        self.add_move(moves.NpcAttack(self), 5)
        self.add_move(moves.BatBite(self), 5)
        self.add_move(moves.Advance(self), 4)
        self.add_move(moves.Withdraw(self))
        self.add_move(moves.NpcIdle(self))
        self.add_move(moves.Dodge(self), 2)


class ElderSlime(NPC):
    """
    Mid-tier threat in the Grondelith Mineral Pools. Larger and slower than a Slime,
    but capable of a devastating telegraphed directional surge (SlimeVolley).
    Players who learn to read the charge can Dodge and avoid the worst of it.
    """

    def __init__(self):
        description = (
            "A vastly larger cousin of the common slime — slow, deliberate, and heavy. "
            "It watches Jean with something that might be intelligence."
        )
        super().__init__(
            name="Elder Slime " + genericng.generate(2, 4),
            description=description,
            maxhp=70,
            damage=28,
            protection=12,
            awareness=20,
            speed=8,
            aggro=True,
            exp_award=45,
            idle_message=" shifts slowly in the muck.",
            alert_message=" fixes Jean with a cold, deliberate focus!",
        )
        self.resistance_base["slashing"] = 0.65
        self.resistance_base["piercing"] = 0.65
        self.resistance_base["crushing"] = 1.25
        self.resistance_base["fire"] = 1.4
        self.resistance_base["earth"] = 0.85
        self.status_resistance_base["poison"] = 1.0
        self.status_resistance_base["slimed"] = 1.0
        self.add_move(moves.NpcAttack(self), 3)
        self.add_move(moves.SlimeVolley(self), 4)
        self.add_move(moves.Advance(self), 3)
        self.add_move(moves.NpcIdle(self), 2)


class KingSlime(NPC):
    """
    Chapter 1 boss. The final corruption of the Grondelith Mineral Pools.
    Uses the same telegraphed surge mechanic as ElderSlime (TidalSurge) but at
    boss scale — the player has learned the tell from two prior encounters.
    """

    def __init__(self):
        description = (
            "A colossal mass of pulsating green slime, its body studded with mineral fragments "
            "it has consumed over centuries. It moves with a slow, terrible certainty."
        )
        super().__init__(
            name="King Slime",
            description=description,
            maxhp=200,
            damage=50,
            protection=15,
            awareness=30,
            speed=6,
            aggro=True,
            exp_award=500,
            idle_message=" pulses at the centre of the pool.",
            alert_message=" rears upward with a deep, resonant churn!",
        )
        self.resistance_base["slashing"] = 0.65
        self.resistance_base["piercing"] = 0.65
        self.resistance_base["crushing"] = 1.2
        self.resistance_base["fire"] = 1.5
        self.resistance_base["earth"] = 0.9
        self.status_resistance_base["poison"] = 1.0
        self.status_resistance_base["slimed"] = 1.0
        self.loot = loot.lev1
        self.add_move(moves.NpcAttack(self), 5)
        self.add_move(moves.TidalSurge(self), 3)
        self.add_move(moves.Advance(self), 4)
        self.add_move(moves.NpcIdle(self), 1)


class TheAdjutant(Friend):
    """Dream-space combat preparation NPC. Interacts to set Jean's stats at runtime.

    Intended for use in the combat testing arena only. Harmless — cannot enter combat.
    Keywords: talk, set, adjust, configure, help.
    """

    def __init__(self):
        description = (
            "A translucent figure robed in pale light. Its face is calm and purposeful — "
            "a construct of the dream, here to prepare you for what lies ahead."
        )
        super().__init__(
            name="The Adjutant",
            description=description,
            damage=0,
            aggro=False,
            exp_award=0,
            maxhp=9999,
            protection=999,
            speed=1,
            idle_message=" waits silently.",
            alert_message=" makes no move to fight.",
            discovery_message="a robed, luminous figure.",
        )
        self.keywords = ["talk", "set", "adjust", "configure", "help"]
        self.pronouns = {
            "personal": "it",
            "possessive": "its",
            "reflexive": "itself",
            "intensive": "itself",
        }
        try:
            self.known_moves = [moves.NpcIdle(self)]
        except Exception:
            self.known_moves = []

    # ------------------------------------------------------------------
    # Keyword dispatch
    # ------------------------------------------------------------------

    def talk(self, player):
        self._adjutant_menu(player)

    def set(self, player):
        self._adjutant_menu(player)

    def adjust(self, player):
        self._adjutant_menu(player)

    def configure(self, player):
        self._adjutant_menu(player)

    def help(self, player):
        self._adjutant_menu(player)

    # ------------------------------------------------------------------
    # Interactive menu
    # ------------------------------------------------------------------

    # Arena tile coordinates (map-tile coordinates, not combat-grid)
    _ARENA_TILES = {
        "Fodder Pit": (1, 0),
        "The Crucible": (2, 0),
        "Ally Courtyard": (0, 1),
        "Status Chamber": (1, 1),
    }

    def _adjutant_menu(self, player):
        """Terminal menu for runtime stat configuration."""
        print("\n" + "=" * 56)
        print("  THE ADJUTANT — Combat Preparation Interface")
        print("=" * 56)
        while True:
            print(
                f"\n  HP: {player.hp}/{player.maxhp}  "
                f"Heat: {player.heat:.1f}  "
                f"Fatigue: {player.fatigue}/{player.maxfatigue}"
            )
            print(
                f"  Level: {player.level}  EXP: {player.exp}  "
                f"EXP-to-next: {player.exp_to_level}"
            )
            print(
                f"  STR:{player.strength}  FIN:{player.finesse}  "
                f"SPD:{player.speed}  END:{player.endurance}  "
                f"CHA:{player.charisma}  INT:{player.intelligence}  "
                f"FAI:{player.faith}"
            )
            print("\n  [1] Set HP / Max HP")
            print("  [2] Set Level & EXP")
            print("  [3] Set Attributes")
            print("  [4] Set Heat")
            print("  [5] Restore HP and Fatigue to full")
            print("  [6] Learn all skills")
            print("  [7] List known skills/moves")
            print("  [8] Manage arena combatants")
            print("  [0] Exit")
            choice = input("\n  Choice: ").strip()

            if choice == "1":
                try:
                    hp_val = int(
                        input(f"  New HP (current max {player.maxhp}): ").strip()
                    )
                    maxhp_val = int(input("  New Max HP: ").strip())
                    player.maxhp = max(1, maxhp_val)
                    player.hp = max(1, min(hp_val, player.maxhp))
                    print(f"  HP set to {player.hp}/{player.maxhp}.")
                except ValueError:
                    print("  Invalid value — enter whole numbers.")

            elif choice == "2":
                try:
                    lvl = int(input("  New Level (1–100): ").strip())
                    exp_val = int(input("  New EXP: ").strip())
                    player.level = max(1, min(100, lvl))
                    player.exp = max(0, exp_val)
                    print(f"  Level → {player.level}, EXP → {player.exp}.")
                except ValueError:
                    print("  Invalid value — enter whole numbers.")

            elif choice == "3":
                attrs = [
                    "strength",
                    "finesse",
                    "speed",
                    "endurance",
                    "charisma",
                    "intelligence",
                    "faith",
                ]
                for attr in attrs:
                    raw = input(
                        f"  {attr.capitalize()} (current {getattr(player, attr)}, blank to skip): "
                    ).strip()
                    if raw:
                        try:
                            v = int(raw)
                            setattr(player, attr, v)
                            setattr(player, attr + "_base", v)
                        except ValueError:
                            print(f"  Skipping {attr} — invalid value.")
                print("  Attributes updated.")

            elif choice == "4":
                try:
                    heat_val = float(input("  New Heat (0.5–10.0): ").strip())
                    player.heat = max(0.5, min(10.0, heat_val))
                    print(f"  Heat set to {player.heat:.2f}.")
                except ValueError:
                    print("  Invalid value — enter a decimal number.")

            elif choice == "5":
                player.hp = player.maxhp
                player.fatigue = player.maxfatigue
                print("  HP and Fatigue fully restored.")

            elif choice == "6":
                try:
                    functions.learn_all_skills_from_skilltree(player)
                    print(
                        f"  All skills learned. "
                        f"Jean now knows {len(getattr(player, 'known_moves', []))} moves."
                    )
                except Exception as e:
                    print(f"  Could not load skill tree: {e}")

            elif choice == "7":
                moves_list = getattr(player, "known_moves", [])
                if moves_list:
                    print(f"  Known moves ({len(moves_list)}):")
                    for m in moves_list:
                        print(f"    - {getattr(m, 'name', repr(m))}")
                else:
                    print("  No moves known yet.")

            elif choice == "8":
                self._combatant_menu(player)

            elif choice == "0":
                print("\n  The Adjutant nods. 'You are prepared.'\n")
                break
            else:
                print("  Unknown option.")

    # ------------------------------------------------------------------
    # Arena combatant management
    # ------------------------------------------------------------------

    def _get_arena_tile(self, player, coords):
        """Return the MapTile at coords from the current map, or None."""
        tile_map = getattr(player, "map", None)
        if tile_map is None:
            # Fallback: resolve via current_room's map reference
            current_room = getattr(self, "current_room", None)
            tile_map = getattr(current_room, "map", None)
        if tile_map is None:
            return None
        return tile_map.get(coords) if hasattr(tile_map, "get") else None

    def _combatant_menu(self, player):
        """Sub-menu for inspecting and editing NPC rosters on each arena tile."""
        print("\n  --- ARENA COMBATANT MANAGER ---")
        while True:
            # Print current roster for every arena tile
            for name, coords in self._ARENA_TILES.items():
                tile = self._get_arena_tile(player, coords)
                if tile is None:
                    print(f"  {name} {coords}: (tile not loaded)")
                    continue
                npcs = getattr(tile, "npcs_here", [])
                npc_summary = (
                    ", ".join(
                        f"{getattr(n, 'name', '?')} ({'ally' if getattr(n, 'friend', False) else 'enemy'})"
                        for n in npcs
                    )
                    or "(empty)"
                )
                print(f"  {name} {coords}: {npc_summary}")

            print("\n  [1] Add combatant to a room")
            print("  [2] Remove combatant from a room")
            print("  [3] Clear all combatants from a room")
            print("  [4] Set a combatant's stats")
            print("  [0] Back")
            sub = input("\n  Choice: ").strip()

            if sub == "1":
                self._add_combatant(player)
            elif sub == "2":
                self._remove_combatant(player)
            elif sub == "3":
                self._clear_room(player)
            elif sub == "4":
                self._set_combatant_stats(player)
            elif sub == "0":
                break
            else:
                print("  Unknown option.")

    def _pick_arena(self, prompt="  Arena: "):
        """Prompt the user to pick an arena tile. Returns (name, coords) or (None, None)."""
        arenas = list(self._ARENA_TILES.items())
        for i, (name, coords) in enumerate(arenas, 1):
            print(f"  [{i}] {name} {coords}")
        print("  [0] Cancel")
        raw = input(prompt).strip()
        if raw == "0":
            return None, None
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(arenas):
                return arenas[idx]
        except ValueError:
            pass
        print("  Invalid selection.")
        return None, None

    def _add_combatant(self, player):
        """Instantiate an NPC class by name and place it in a chosen arena tile."""
        name, coords = self._pick_arena("  Add to which arena? ")
        if coords is None:
            return
        tile = self._get_arena_tile(player, coords)
        if tile is None:
            print(f"  Tile {coords} not loaded — cannot modify.")
            return

        cls_name = input("  NPC class name (e.g. Slime, Lurker, KingSlime): ").strip()
        if not cls_name:
            return

        # All NPC classes are in this module's globals — no import needed.
        cls = globals().get(cls_name)
        if cls is None or not isinstance(cls, type):
            print(f"  Class '{cls_name}' not found in npc module.")
            return

        try:
            instance = cls()
            instance.current_room = tile
            getattr(tile, "npcs_here", []).append(instance)
            print(f"  {cls_name} added to {name}.")
        except Exception as e:
            print(f"  Could not instantiate {cls_name}: {e}")

    def _remove_combatant(self, player):
        """Remove a specific NPC from a chosen arena tile by index."""
        name, coords = self._pick_arena("  Remove from which arena? ")
        if coords is None:
            return
        tile = self._get_arena_tile(player, coords)
        if tile is None:
            print(f"  Tile {coords} not loaded.")
            return
        npcs = getattr(tile, "npcs_here", [])
        if not npcs:
            print(f"  {name} is already empty.")
            return
        for i, npc in enumerate(npcs, 1):
            tag = "ally" if getattr(npc, "friend", False) else "enemy"
            print(f"  [{i}] {getattr(npc, 'name', '?')} ({tag})")
        print("  [0] Cancel")
        raw = input("  Remove which? ").strip()
        if raw == "0":
            return
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(npcs):
                removed = npcs.pop(idx)
                print(f"  Removed {getattr(removed, 'name', '?')} from {name}.")
                return
        except ValueError:
            pass
        print("  Invalid selection.")

    def _clear_room(self, player):
        """Remove every NPC from a chosen arena tile."""
        name, coords = self._pick_arena("  Clear which arena? ")
        if coords is None:
            return
        tile = self._get_arena_tile(player, coords)
        if tile is None:
            print(f"  Tile {coords} not loaded.")
            return
        npcs = getattr(tile, "npcs_here", [])
        count = len(npcs)
        npcs.clear()
        print(f"  Cleared {count} combatant(s) from {name}.")

    def _set_combatant_stats(self, player):
        """Edit base stats on an NPC already present in an arena tile."""
        name, coords = self._pick_arena("  Edit combatant in which arena? ")
        if coords is None:
            return
        tile = self._get_arena_tile(player, coords)
        if tile is None:
            print(f"  Tile {coords} not loaded.")
            return
        npcs = getattr(tile, "npcs_here", [])
        if not npcs:
            print(f"  {name} has no combatants.")
            return
        for i, npc in enumerate(npcs, 1):
            print(f"  [{i}] {getattr(npc, 'name', '?')}")
        print("  [0] Cancel")
        raw = input("  Edit which? ").strip()
        if raw == "0":
            return
        try:
            idx = int(raw) - 1
            if not (0 <= idx < len(npcs)):
                print("  Invalid selection.")
                return
        except ValueError:
            print("  Invalid selection.")
            return

        target = npcs[idx]
        npc_name = getattr(target, "name", "?")
        editable = [
            "hp",
            "maxhp",
            "damage",
            "protection",
            "speed",
            "finesse",
            "awareness",
            "endurance",
            "strength",
            "charisma",
            "intelligence",
            "faith",
            "aggro",
            "friend",
        ]
        print(f"\n  Editing: {npc_name}")
        for stat in editable:
            current = getattr(target, stat, "—")
            raw_val = input(f"  {stat} (current {current}, blank to skip): ").strip()
            if not raw_val:
                continue
            # Boolean stats
            if stat in ("aggro", "friend"):
                if raw_val.lower() in ("true", "1", "yes"):
                    setattr(target, stat, True)
                elif raw_val.lower() in ("false", "0", "no"):
                    setattr(target, stat, False)
                else:
                    print(f"  Skipping {stat} — use true/false.")
                continue
            try:
                int_val = int(raw_val)
                setattr(target, stat, int_val)
                # Keep hp clamped to new maxhp
                if stat == "maxhp":
                    target.hp = min(getattr(target, "hp", int_val), int_val)
            except ValueError:
                print(f"  Skipping {stat} — invalid value.")
        print(f"  {npc_name} stats updated.")


class StatusDummy(NPC):
    """A status-effect testing target.

    All status resistances stripped to 0.0 so every effect lands cleanly.
    High HP, minimal damage, very slow — designed to survive extended tests.
    Intended for use in the combat testing arena only.
    """

    def __init__(self):
        description = (
            "A featureless shape woven from the dream itself. "
            "It holds no malice — only the purpose you give it."
        )
        super().__init__(
            name="Pell",
            description=description,
            maxhp=500,
            damage=3,
            protection=0,
            awareness=100,
            speed=2,
            aggro=True,
            exp_award=0,
            idle_message=" stands inert, awaiting the test.",
            alert_message=" shifts to face Jean, passive and ready.",
        )
        # Strip all status resistances so effects land reliably
        for key in self.status_resistance_base:
            self.status_resistance_base[key] = 0.0
        # Strip all damage resistances to neutral
        for key in self.resistance_base:
            self.resistance_base[key] = 1.0
        self.add_move(moves.NpcIdle(self), 5)
        self.add_move(moves.NpcAttack(self), 1)





# ─────────────────────────────────────────────────────────────────────────────
# Grondite citizens — Grondia city map population
# Regular Grondite folk do not speak human language.
# All talk() implementations narrate gesture and sound only.
# ─────────────────────────────────────────────────────────────────────────────


class GronditePasserby(Friend):
    """A generic Grondite citizen moving through the city.

    Non-hostile, non-speaking. Used in arcology concourses, market, and
    residential lanes. TALK produces narrated gesture/sound — never words.
    """

    _TALK_LINES = [
        "The Grondite meets your gaze. A low subsonic vibration moves through the floor "
        "beneath your feet. It turns away and continues.",
        "The Grondite stops and looks at you — really looks, tilting its head slowly. "
        "Then it makes a sound like two stones sliding together and moves on.",
        "The Grondite produces three short, percussive sounds from somewhere in its chest. "
        "It does not wait for a response.",
        "The Grondite gestures — a single, deliberate downward press of one hand. "
        "Jean isn't sure what it means. The Grondite continues walking.",
        "The Grondite makes no sound. It places a fist briefly against its own sternum, "
        "then turns away.",
        "A low grinding tone rises from the Grondite's chest — short, even, and then "
        "gone. It does not slow its pace.",
        "The Grondite regards Jean with an unhurried stillness, then tilts its head toward "
        "the path ahead and moves on.",
    ]

    def __init__(self):
        super().__init__(
            name="Grondite",
            description=(
                "A broad, heavily-built figure of living stone, unhurried and deliberate. "
                "Its surface is a mosaic of grey and ochre rock, worn smooth at the joints "
                "from centuries of movement. It acknowledges Jean with a slow lateral turn "
                "of its head — enough to register, not enough to invite."
            ),
            damage=0,
            aggro=False,
            exp_award=0,
            maxhp=80,
            protection=10,
            speed=4,
            finesse=8,
            awareness=14,
            idle_message=" moves past with measured, heavy steps.",
            alert_message=" shifts its weight and watches.",
            discovery_message="a broad, stone-skinned Grondite.",
        )
        self.keywords = ["talk"]
        self.pronouns = {
            "personal": "it",
            "possessive": "its",
            "reflexive": "itself",
            "intensive": "itself",
        }
        try:
            self.known_moves = [moves.NpcIdle(self)]
        except Exception:
            self.known_moves = []

    def talk(self, player):
        print(random.choice(self._TALK_LINES))


class GronditeWorker(Friend):
    """A Grondite artisan, found near the Fabricarium and workshop areas.

    Non-hostile, non-speaking. TALK produces narrated gesture/sound only.
    """

    _TALK_LINES = [
        "The worker pauses its task and straightens. It makes a low, measured sound — "
        "not unfriendly — and returns to what it was doing.",
        "The Grondite does not look up but raises one finger briefly, as if asking Jean "
        "to wait. Then the sound it's working out of the rock fills the silence again.",
        "It looks at Jean with an expression that is — possibly — patience. It holds up "
        "whatever it is working on. Jean doesn't know what he is supposed to understand from this.",
        "The worker turns its head toward Jean without stopping its motion. A low percussive "
        "sound. Then it looks back at the work.",
        "The Grondite sets its tool down deliberately, regards Jean for a moment, makes a "
        "single short vowel sound, and picks the tool back up.",
    ]

    def __init__(self):
        super().__init__(
            name="Grondite Worker",
            description=(
                "A Grondite whose stone-skin is darkened at the hands and forearms — "
                "mineral dust worked into the grain over long practice. "
                "It moves with the focused economy of someone partway through a task."
            ),
            damage=0,
            aggro=False,
            exp_award=0,
            maxhp=80,
            protection=8,
            speed=4,
            finesse=10,
            awareness=12,
            idle_message=" is occupied with something near the floor.",
            alert_message=" pauses its work and watches.",
            discovery_message="a Grondite working at something.",
        )
        self.keywords = ["talk"]
        self.pronouns = {
            "personal": "it",
            "possessive": "its",
            "reflexive": "itself",
            "intensive": "itself",
        }
        try:
            self.known_moves = [moves.NpcIdle(self)]
        except Exception:
            self.known_moves = []

    def talk(self, player):
        print(random.choice(self._TALK_LINES))


class GronditeElder(Friend):
    """An older, senior Grondite. Found in or near the Conclave and Citadel.

    Notably still; inspects Jean with deliberate attention.
    Non-hostile, non-speaking. TALK produces narrated gesture/sound only.
    """

    _TALK_LINES = [
        "The Elder turns. It looks at Jean the way a geologist looks at a particular "
        "stratum — with genuine, slow interest. Then it makes a single sound, deep and "
        "resonant, and returns its gaze to the middle distance.",
        "The Elder does not speak. It places a hand on Jean's shoulder — briefly, a weight, "
        "an anchor — and removes it. Then it is still again.",
        "The Elder considers Jean for a long moment. It produces a subsonic resonance Jean "
        "feels in his sternum before he hears it. Then it gestures toward the Conclave and "
        "turns away.",
        "Two sounds: one short, one long, with a pause between them. The Elder makes them "
        "without looking at Jean, then waits — as if for a response Jean doesn't know how "
        "to give.",
        "The Elder's attention is unhurried and complete. It takes Jean in from boots to "
        "face, then makes a low grinding sound that rises and resolves. Then it is still.",
    ]

    def __init__(self):
        super().__init__(
            name="Grondite Elder",
            description=(
                "This Grondite is older — its stone-skin more cracked and mineral-threaded, "
                "grey and iron-veined. It moves slowly, not from frailty, but from the "
                "unhurried certainty of something that has been exactly where it is "
                "for a very long time."
            ),
            damage=0,
            aggro=False,
            exp_award=0,
            maxhp=120,
            protection=15,
            speed=2,
            finesse=6,
            awareness=20,
            idle_message=" stands in quiet contemplation.",
            alert_message=" turns slowly to watch.",
            discovery_message="a weathered, ancient-looking Grondite.",
        )
        self.keywords = ["talk"]
        self.pronouns = {
            "personal": "it",
            "possessive": "its",
            "reflexive": "itself",
            "intensive": "itself",
        }
        try:
            self.known_moves = [moves.NpcIdle(self)]
        except Exception:
            self.known_moves = []

    def talk(self, player):
        print(random.choice(self._TALK_LINES))


class GronditeConclaveElder(Friend):
    """The Elder in the Conclave side chamber at (9,3). A stubbed side-quest giver.

    In the future, this NPC will initiate a formal side quest retrieving a
    lost clan token. For now, talk() presents the opening stub interaction and
    a placeholder acknowledgment that the quest is not yet available.
    """

    _INTRO_RUN_KEY = "conclave_elder_intro"

    def __init__(self):
        super().__init__(
            name="Conclave Elder",
            description=(
                "An Elder Grondite who stands each day at the center of this chamber, "
                "facing the plinth. Its stone-skin has the deep cracking and vivid mineral "
                "banding of great age. Unlike the other Elders you have seen, it does not "
                "merely tolerate your presence — it seems to have been expecting someone."
            ),
            damage=0,
            aggro=False,
            exp_award=0,
            maxhp=150,
            protection=20,
            speed=2,
            finesse=6,
            awareness=25,
            idle_message=" stands before the plinth, still as carved stone.",
            alert_message=" slowly turns its gaze toward you.",
            discovery_message="a Grondite Elder standing before the plinth.",
        )
        self.keywords = ["talk"]
        self.pronouns = {
            "personal": "it",
            "possessive": "its",
            "reflexive": "itself",
            "intensive": "itself",
        }
        try:
            self.known_moves = [moves.NpcIdle(self)]
        except Exception:
            self.known_moves = []

    def talk(self, player):
        import time
        # Check if intro has already fired this session
        story = getattr(getattr(player, "universe", None), "story", {})
        first_time = story.get(self._INTRO_RUN_KEY, "0") == "0"

        if first_time:
            print(
                "\nThe Elder turns before Jean says anything. It had already turned — "
                "waiting — before he reached the plinth."
            )
            time.sleep(1.5)
            print(
                "It studies him. Then it reaches into the folds of its stone-mantle and "
                "produces something: a small disc, cracked cleanly in half, one piece "
                "missing. It holds it out toward Jean."
            )
            time.sleep(1.5)
            print(
                "It makes a sound: low, deliberate, with a rising inflection at the end. "
                "The sound of a question."
            )
            time.sleep(1)
            print(
                "Jean doesn't know what it is asking. But the broken disc is clearly "
                "meant to show him."
            )
            time.sleep(1)
            print(
                "\n[A side quest would begin here — the Elder is looking for a missing "
                "clan token. This quest is not yet available.]"
            )
            time.sleep(0.5)
            print(
                "\nThe Elder lowers the broken disc. It makes one short sound — patient, "
                "not disappointed — and turns back to the plinth."
            )
            universe_story = getattr(getattr(player, "universe", None), "story", None)
            if universe_story is not None:
                universe_story[self._INTRO_RUN_KEY] = "1"
        else:
            lines = [
                "The Elder turns and regards Jean for a moment. Then it produces the broken "
                "disc again and holds it in the space between them.",
                "The Elder makes the same rising sound as before. The question hasn't changed.",
                "The Elder looks at Jean. Looks at the plinth. Looks at Jean again.",
            ]
            print(random.choice(lines))
