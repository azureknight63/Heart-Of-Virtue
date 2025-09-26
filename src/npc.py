import random
import time
import genericng as genericng
import moves as moves
import functions as functions
from neotermcolor import colored, cprint
import loot_tables as loot_tables
from items import (Item, Shortsword, Gold, Restorative, Draught, Antidote, Rock, Spear, Fists, Key, Special, Consumable, Accessory,
                       Gloves, Helm, Boots, Armor, Weapon, Arrow)
import items as items_module  # added for unique item registry management
from objects import Container
from shop_conditions import ValueModifierCondition, RestockWeightBoostCondition, UniqueItemInjectionCondition
from pathlib import Path
import os
import importlib.util
import re

loot = loot_tables.Loot()  # initialize a loot object to access the loot table


class NPC:
    def __init__(self, name, description, damage, aggro, exp_award,
                 inventory: list[Item]=None, maxhp=100, protection=0, speed=10, finesse=10,
                 awareness=10, maxfatigue=100, endurance=10, strength=10, charisma=10, intelligence=10,
                 faith=10, hidden=False, hide_factor=0, combat_range=(0, 5),
                 idle_message=' is shuffling about.', alert_message='glares sharply at Jean!',
                 discovery_message='something interesting.', target=None, friend=False):
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
        # A note about resistances: 1.0 means "no effect." 0.5 means "damage/chance reduced by half."
        # 2.0 means "double damage/change."
        # Negative values mean the damage is absorbed (heals instead of damages.) Status resistances cannot be negative.
        self.resistance = {
            "fire": 1.0,
            "ice": 1.0,
            "shock": 1.0,
            "earth": 1.0,
            "light": 1.0,
            "dark": 1.0,
            "piercing": 1.0,
            "slashing": 1.0,
            "crushing": 1.0,
            "spiritual": 1.0,
            "pure": 1.0
        }
        self.resistance_base = {
            "fire": 1.0,
            "ice": 1.0,
            "shock": 1.0,
            "earth": 1.0,
            "light": 1.0,
            "dark": 1.0,
            "piercing": 1.0,
            "slashing": 1.0,
            "crushing": 1.0,
            "spiritual": 1.0,
            "pure": 1.0
        }
        self.status_resistance = {
            "generic": 1.0,  # Default status type for all states
            "stun": 1.0,  # Unable to move; typically short duration
            "poison": 1.0,  # Drains Health every combat turn/game tick; persists
            "enflamed": 1.0,
            "sloth": 1.0,  # Drains Fatigue every combat turn
            "apathy": 1.0,  # Drains HEAT every combat turn
            "blind": 1.0,  # Miss physical attacks more frequently; persists
            "incoherence": 1.0,  # Miracles fail more frequently; persists
            "mute": 1.0,  # Cannot use Miracles; persists
            "enraged": 1.0,  # Double physical damage given and taken
            "enchanted": 1.0,  # Double magical damage given and taken
            "ethereal": 1.0,  # Immune to physical damage but take 3x magical damage; persists
            "berserk": 1.0,  # Auto attack, 1.5x physical damage
            "slow": 1.0,  # All move times are doubled
            "sleep": 1.0,  # Unable to move; removed upon physical damage
            "confusion": 1.0,  # Uses random moves on random targets; removed upon physical damage
            "cursed": 1.0,  # Makes luck 1, chance of using a random move with a random target; persists
            "stop": 1.0,  # Unable to move; not removed with damage
            "stone": 1.0,  # Unable to move; immune to damage; permanent death if allowed to persist after battle
            "frozen": 1.0,  # Unable to move; removed with Fire magic; permanent death if allowed
            # to persist after battle
            "doom": 1.0,  # Death after n turns/ticks; persists; lifted with purification magic ONLY
            "death": 1.0
        }
        self.status_resistance_base = {
            "generic": 1.0,
            "stun": 1.0,
            "poison": 1.0,
            "enflamed": 1.0,
            "sloth": 1.0,
            "apathy": 1.0,
            "blind": 1.0,
            "incoherence": 1.0,
            "mute": 1.0,
            "enraged": 1.0,
            "enchanted": 1.0,
            "ethereal": 1.0,
            "berserk": 1.0,
            "slow": 1.0,
            "sleep": 1.0,
            "confusion": 1.0,
            "cursed": 1.0,
            "stop": 1.0,
            "stone": 1.0,
            "frozen": 1.0,
            "doom": 1.0,
            "death": 1.0
        }
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
        self.combat_proximity = {}  # dict for unit proximity: {unit: distance}; Range for most melee weapons is 5,
        # ranged is 20. Distance is in feet (for reference)
        self.default_proximity = 20
        self.hidden = hidden
        self.hide_factor = hide_factor
        self.discovery_message = discovery_message
        self.friend = friend  # Is this a friendly NPC? Default is False (enemy). Friends will help Jean in combat.
        self.combat_delay = 0  # initial delay for combat actions. Typically randomized on unit spawn
        self.combat_range = combat_range  # similar to weapon range, but is an attribute to the NPC since
        # NPCs don't equip items
        self.loot = loot.lev0
        self.keywords = []  # action keywords to hook up an arbitrary command like "talk" for a friendly NPC
        self.pronouns = {
            "personal": "it", "possessive": "its", "reflexive": "itself", "intensive": "itself"
        }

    def is_alive(self):
        return self.hp > 0

    def die(self):
        really_die = self.before_death()
        if really_die:
            print(colored(self.name, "magenta") + " exploded into fragments of light!")

    def cycle_states(self):
        """
        Loop through all the states on the NPC and process the effects of each one
        """
        for state in self.states:
            state.process(self)

    def refresh_moves(self):
        available_moves = self.known_moves[:]
        moves_to_remove = []
        for move in available_moves:
            if not move.viable():
                moves_to_remove.append(move)
        output = [x for x in available_moves if x not in moves_to_remove]
        return output

    def select_move(self):
        available_moves = self.refresh_moves()
        #  simple random selection; if you want something more complex, overwrite this for the specific NPC
        weighted_moves = []
        for move in available_moves:
            for weight in range(move.weight):
                weighted_moves.append(move)

        #  add additional rest moves if fatigue is low to make it a more likely choice
        if (self.fatigue / self.maxfatigue) < 0.25:
            for i in range(0, 5):
                weighted_moves.append(moves.NpcRest(self))

        num_choices = len(weighted_moves) - 1
        while self.current_move is None:
            choice = random.randint(0, num_choices)
            if (weighted_moves[choice].fatigue_cost <= self.fatigue) and weighted_moves[choice].viable():
                self.current_move = weighted_moves[choice]

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
                    self.current_room.spawn_item(item.__class__.__name__, amt=quantity, hidden=1,
                                                 hfactor=random.randint(20, 60))
            self.inventory = []

    def before_death(self):  # Overwrite for each NPC if they are supposed to do something special before dying
        if self.loot:
            self.roll_loot()  # checks to see if an item will drop
        self.drop_inventory()
        return True

    def combat_engage(self, player):
        """
        Adds NPC to the proper combat lists and initializes
        """
        player.combat_list.append(self)
        player.combat_proximity[self] = int(self.default_proximity * random.uniform(0.75, 1.25))
        if len(player.combat_list_allies) > 0:
            for ally in player.combat_list_allies:
                ally.combat_proximity[self] = int(self.default_proximity * random.uniform(0.75, 1.25))
        self.in_combat = True

    def roll_loot(self):  # when the NPC dies, do a roll to see if any loot drops
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
                if "Equipment" in item:  # ex Equipment_1_0 will yield an item at level 1 with no enchantments;
                    # Equipment_0_2 will yield an item at level 0 with 2 enchantment points
                    params = item.split("_")
                    item = loot.random_equipment(self.current_room, params[1], params[2])
                    drop = item
                else:
                    drop = self.current_room.spawn_item(item, dropcount)
                cprint("{} dropped {} x {}!".format(self.name, drop.name, dropcount), 'cyan', attrs=['bold'])
                break  # only one item in the loot table will drop

    def get_equipped_items(self):
        """
        Returns a list of all items in the npc's inventory that are currently equipped.
        """
        equipped_items = []
        for item in self.inventory:
            if hasattr(item, "isequipped") and item.isequipped:
                equipped_items.append(item)
        return equipped_items

""" Merchants """

class Merchant(NPC):
    def __init__(self, name: str, description: str, damage: int, aggro: bool, exp_award: int,
                 stock_count: int, inventory:list[Item]=None,
                 specialties: list[type[Item]]=None, enchantment_rate: float=1.0,
                 always_stock: list[Item]=None, base_gold: int=300,
                 maxhp=100, protection=0, speed=10, finesse=10,
                 awareness=10, maxfatigue=100, endurance=10, strength=10, charisma=10, intelligence=10,
                 faith=10, hidden=False, hide_factor=0, combat_range=(0, 5),
                 idle_message=' is here.', alert_message='glares sharply at Jean!',
                 discovery_message='someone interesting.', target=None):
        super().__init__(name=name, description=description, damage=damage, aggro=aggro, exp_award=exp_award,
                         inventory=inventory, maxhp=maxhp, protection=protection, speed=speed, finesse=finesse,
                         awareness=awareness, maxfatigue=maxfatigue, endurance=endurance, strength=strength,
                         charisma=charisma, intelligence=intelligence, faith=faith, hidden=hidden,
                         hide_factor=hide_factor, combat_range=combat_range,
                         idle_message=idle_message,
                         alert_message=alert_message,
                         discovery_message=discovery_message,
                         target=target)
        self.keywords = ["buy", "sell", "trade", "talk"]
        self.specialties = specialties  # List of item classes the merchant specializes in
        if self.specialties is None:
            self.specialties = []
        self.enchantment_rate = enchantment_rate  # 0 to 10.0 with 0 being none and 10 being 10x the normal rate
        self.stock_count = stock_count  # Number of items to keep in stock after each refresh
        self.always_stock = always_stock  # List of item classes the merchant always keeps in stock
        self.base_gold = base_gold  # Amount of gold the merchant has to buy items from the player
        self.shop_conditions = {
            "value": [],
            "availability": [],
            "unique": []
        }
        self.shop = None
        self.initialize_shop()



    def _collect_player_merchandise(self, player):
        """Pull any merchandise items the player is carrying into the merchant's stock with flavor text.

        Rationale: If Jean brings unpaid shop goods to the merchant, presume intent to purchase and
        surface them in the Buy menu. Similar pacing & flavor to player.drop_merchandise_items().
        """
        if not player or not hasattr(player, 'inventory'):
            return
        phrases = [
            "{merchant} arches a brow: 'Ahh, eyeing the {item}, are we? I'll just set that out proper.'",
            "{merchant} deftly takes the {item} and adds it to the display.",
            "With a practiced motion {merchant} places the {item} among the wares.",
            "'{item}? Fine taste,' {merchant} says, arranging it for sale.",
            "{merchant} chuckles softly and logs the {item} into a battered ledger.",
            "'I'll catalog that {item} for you first,' {merchant} murmurs.",
            "The {item} is swept into a polished tray and set beneath a lamp by {merchant}.",
            "{merchant} nods knowingly; the {item} now sits at the center of the shelf.",
            "'Curious about the {item}? Let's price it properly,' says {merchant}.",
            "{merchant} rubs the {item} with a cloth, revealing a faint maker's mark.",
            "{merchant} inspects the {item} closely, humming as if counting its merits.",
            "A small tag is tied to the {item} and {merchant} sets it upright for viewing.",
            "{merchant} smiles: 'This {item} will fetch a good coin or two on market day.'",
            "{merchant} sets the {item} beneath glass and adjusts its angle for the light.",
            "'A rare find,' {merchant} whispers, handling the {item} with care.",
            "{merchant} dips a finger in a small pot and brushes away dust from the {item}.",
            "The {item} is rotated slowly as {merchant} asks a passing customer if they fancy it.",
            "{merchant} murmurs to themselves while weighing the {item}'s qualities.",
            "A tiny charcoal sketch of the {item} is scribbled into a ledger by {merchant}.",
            "'Keep an eye on that one,' {merchant} says, pointing to the {item} as he cocks a smile.",
            "{merchant} wraps the {item} in cloth and tucks it among the curios for safekeeping.",
            "{merchant} hums an old tune while polishing the {item}'s edges.",
            "The {item} is placed upon a velvet cushion and presented as if it were a trinket of kings.",
            "{merchant} traces a worn seam on the {item} and nods appreciatively.",
            "'I'll put a modest price to start,' {merchant} decides, fastening a tag to the {item}.",
            "{merchant} tests the {item}'s weight with a practiced hand before shelving it.",
            "A faint smile crosses {merchant}'s face as he tucks the {item} into the display case.",
            "{merchant} murmurs, 'There's history in this piece,' as the {item} is set out.",
            "The {item} receives a final dusting before being propped among the wares by {merchant}.",
            "{merchant} whispers, 'Keep this quiet — it's a curious thing,' and gives the {item} a place of honor.",
            "{merchant} consults a small book of prices, then scribbles a number next to the {item}.",
            "{merchant} cradles the {item} for a moment, then places it where passersby may admire it.",
            "A thin ribbon is looped about the {item} and tied by {merchant} with a flourish.",
            "'Handled gently,' {merchant} notes, placing the {item} where only careful hands may reach.",
            "{merchant} leans in, as if to tell a story about the {item}, "
            "but decides against it and places it on display."
        ]
        took_any = False
        for it in player.inventory[:]:
            if getattr(it, 'merchandise', False):
                # Remove from player
                try:
                    player.inventory.remove(it)
                except ValueError:
                    continue
                # Add to merchant stock
                if self.inventory is None:
                    self.inventory = []
                self.inventory.append(it)
                msg = random.choice(phrases).format(
                    merchant=self.name.split(' ')[0],
                    item=getattr(it, 'name', 'item')
                )
                print(msg)
                time.sleep(0.15)
                took_any = True
        if took_any:
            time.sleep(0.25)

    def initialize_shop(self):
        """
        This method can be used to initialize the merchant's shop with items.
        It can be called when the merchant is created or when the game starts.
        Override this method to customize the shop's inventory and other properties.
        """
        if self.inventory is None:
            self.inventory = []
        # Local import to avoid circular import with interface -> npc
        try:
            from interface import ShopInterface as Shop
        except Exception:
            Shop = None
        if Shop:
            self.shop = Shop(merchant=self, player=None, shop_name=f"{self.name}'s Shop")
        else:
            self.shop = None

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

    def count_stock(self):
        """
        This method returns the number of items currently in stock. This includes items in the merchant's
        inventory as well as items in any containers associated with the merchant.
        :return int: The total number of items in stock.
        """
        total = len(self.inventory)
        # Support room.universe.map for test harnesses when room.map is missing
        rooms_source = None
        if self.current_room:
            rooms_source = getattr(self.current_room, 'map', None)
            if rooms_source is None:
                uni = getattr(self.current_room, 'universe', None)
                if uni is not None:
                    rooms_source = getattr(uni, 'map', None)
        if rooms_source:
            rooms = rooms_source.values() if hasattr(rooms_source, 'values') else rooms_source
            for room in rooms:
                for obj in getattr(room, "objects", []):
                    if hasattr(obj, "inventory") and hasattr(obj, "merchant"):
                        owner = getattr(obj, "merchant", None)
                        if owner == self or owner == self.name:
                            total += len(getattr(obj, 'inventory', []))
        return total

    def _remove_placed_item_from_room(self, item: Item):
        room_items = getattr(self.current_room, 'items_here', None)
        if room_items is None:
            room_items = getattr(self.current_room, 'items', None)
        if room_items is None:
            room_items = getattr(self.current_room, 'spawned', None)
        if room_items and item in room_items:
            try:
                room_items.remove(item)
            except Exception:
                pass

    def update_goods(self):
        """Refresh or update the merchant's inventory.
        High-level orchestration that (1) resets current stock, (2) spawns always-stock items,
        (3) applies enchantments when appropriate, (4) places items into eligible containers, and
        (5) fills remaining stock for the merchant and associated containers up to stock_count.
        """
        containers = self._reset_stock_state()
        # Spawn & place always-stock items
        if self.always_stock:
            for item_spec in self.always_stock:
                item = self._create_always_stock_item(item_spec)
                if not item:
                    continue
                self._maybe_enchant(item)
                placed = self._place_item(item, containers)
                if not placed:
                    self.inventory.append(item)
                self._remove_placed_item_from_room(item)
        # Update shop conditions
        self._update_shop_conditions()
        # Fill remainder
        self._fill_remaining_stock(containers)
        # Apply value conditions to all items in stock
        self._apply_value_conditions()
        # Add any unique items from unique item injection conditions, if applicable
        for condition in self.shop_conditions.get("unique", []):
            if isinstance(condition, UniqueItemInjectionCondition):
                # Rely on condition to inject & place items; avoid double placement of returned items
                condition.inject_unique_items(self)
        gold_random_modifier = random.uniform(0.75, 1.25)
        self.inventory.append(Gold(int(self.base_gold * gold_random_modifier)))


    # ----------------- Helper Methods (Modularized) -----------------
    def _reset_stock_state(self) -> list[Container]:
        """Clear merchant inventory and any associated container inventories.
        Returns list of containers tied to this merchant.
        Also releases any unique items about to be removed back into the global
        unique item registry so they may respawn elsewhere in future restocks.
        """
        # Collect unique item class names BEFORE clearing inventories
        removed_unique: set[str] = set()
        # Merchant's direct inventory
        for it in getattr(self, 'inventory', []) or []:
            if getattr(it, 'unique', False):  # unique flag placed on special one-off items
                removed_unique.add(it.__class__.__name__)
        containers: list[Container] = []
        # Support both real Room.map and fake test harness where room.universe.map is provided
        rooms_source = None
        if self.current_room:
            rooms_source = getattr(self.current_room, 'map', None)
            if rooms_source is None:
                uni = getattr(self.current_room, 'universe', None)
                if uni is not None:
                    rooms_source = getattr(uni, 'map', None)
        if rooms_source:
            rooms = rooms_source.values() if hasattr(rooms_source, 'values') else rooms_source
            for room in rooms:
                for obj in getattr(room, "objects", []):
                    if hasattr(obj, "inventory") and hasattr(obj, "merchant"):
                        owner = getattr(obj, "merchant", None)
                        if owner == self or owner == self.name:
                            # Scan container inventory for unique items prior to clearing
                            for it in getattr(obj, 'inventory', []) or []:
                                if getattr(it, 'unique', False):
                                    removed_unique.add(it.__class__.__name__)
        # Now clear merchant inventory
        self.inventory = []
        # And clear container inventories while recording them
        if not self.current_room:
            # Deregister unique items (safe even if set not present)
            for cls_name in removed_unique:
                items_module.unique_items_spawned.discard(cls_name)
            return containers
        # Recompute rooms_source defensively in case current_room.map was missing earlier
        rooms_source = getattr(self.current_room, 'map', None)
        if rooms_source is None:
            uni = getattr(self.current_room, 'universe', None)
            if uni is not None:
                rooms_source = getattr(uni, 'map', None)
        if not rooms_source:
            # Nothing to iterate; deregister uniques and return
            for cls_name in removed_unique:
                items_module.unique_items_spawned.discard(cls_name)
            return containers
        for room in (rooms_source.values() if hasattr(rooms_source, 'values') else rooms_source):
            if isinstance(room, str):
                continue
            # support both objects_here and objects attribute on fake rooms
            for obj in getattr(room, 'objects_here', getattr(room, 'objects', [])):
                if hasattr(obj, "inventory") and hasattr(obj, "merchant"):
                    owner = getattr(obj, "merchant", None)
                    if owner == self or owner == self.name:
                        obj.inventory = []
                        containers.append(obj)
            # support both items_here and items/spawned lists
            room_items = getattr(room, 'items_here', None)
            if room_items is None:
                room_items = getattr(room, 'items', None)
            if room_items is None:
                room_items = getattr(room, 'spawned', None)
            if room_items:
                for item in list(room_items):
                    if getattr(item, 'merchandise', None) and item.merchandise:
                        try:
                            room_items.remove(item)
                        except Exception:
                            pass
        # Finally, release unique item class names so they can be spawned again later
        for cls_name in removed_unique:
            items_module.unique_items_spawned.discard(cls_name)
        return containers

    def _create_always_stock_item(self, item_spec) -> Item | None:
        """Instantiate an item from an always_stock entry.
        Supports either an Item subclass or an Item instance (used as a template).
        Preserves count when provided on a template instance.
        """
        # Ensure defaults
        desired_count = 0
        # Accept both class objects (e.g. Restorative) and template instances (possibly from a different module)
        if hasattr(item_spec, '__class__') and not isinstance(item_spec, type):
            # It's an instance; preserve count if present and derive class name from its class
            desired_count = getattr(item_spec, 'count', 0) or 0
            item_class_name = item_spec.__class__.__name__
        else:
            # Assume it's a class / type; fall back gracefully
            if hasattr(item_spec, '__name__'):
                item_class_name = item_spec.__name__
            else:
                return None
            if getattr(item_spec, 'count', 0) > 1:
                desired_count = getattr(item_spec, 'count', 0)
        if not self.current_room:
            return None
        spawned = self.current_room.spawn_item(item_class_name, merchandise=True)
        if spawned and desired_count > 0 and hasattr(spawned, 'count'):
            spawned.count = desired_count
        return spawned

    def _maybe_enchant(self, item: Item):
        """Apply random enchantments to equippable items based on enchantment_rate.
        Mirrors original probability curve while isolating logic.
        """
        if not hasattr(item, 'isequipped') or self.enchantment_rate <= 0:
            return
        base_roll = random.random()
        # Original scaling logic retained; safeguard division by zero already handled above.
        no_enchant_threshold = 0.6 / self.enchantment_rate
        enchantment_points = 0
        if base_roll > no_enchant_threshold:
            # Compute cumulative bands (scaled as previously) in ascending order.
            band = base_roll - no_enchant_threshold
            scale = 1 / self.enchantment_rate
            if band <= 0.2 * scale:
                enchantment_points = 1
            elif band <= 0.3 * scale:
                enchantment_points = 3
            elif band <= 0.35 * scale:
                enchantment_points = 5
            elif band <= 0.38 * scale:
                enchantment_points = 7
            else:
                enchantment_points = 10
        enchantment_points = int(enchantment_points)
        if enchantment_points > 0:
            functions.add_random_enchantments(item, enchantment_points)

    def _place_item(self, item: Item, containers: list[Container]) -> bool:
        """Attempt to place an item into one of the merchant's containers.
        Chooses randomly among containers whose allowed_item_types accept the item.
        Returns True if placed into a container, else False.
        """
        acceptable = []
        for container in containers:
            allowed_types = getattr(container, 'allowed_item_types', None)
            if not allowed_types:
                continue
            for allowed_type in allowed_types:
                if isinstance(item, allowed_type):  # isinstance covers subclass relationship
                    acceptable.append(container)
                    break
        if acceptable:
            chosen = random.choice(acceptable)
            chosen.inventory.append(item)
            return True
        return False

    def _fill_remaining_stock(self, containers: list[Container]):
        """Populate merchant + associated containers up to their individual stock caps.

        Rules:
        - Merchant inventory target: self.stock_count
        - Each container may define its own stock_count (ignored if missing / 0)
        - Weighted random selection of Item subclasses (excluding unique factories)
          * Base weight = 1
          * If class is (subclass of) a specialty -> *3 weight
          * Availability conditions (RestockWeightBoostCondition) further multiply weights
        - Avoid spawning unique items (those provided via unique_item_factories)
        - Apply enchantments via _maybe_enchant
        - Stop when all capacities filled or no candidates remain / safety limit reached
        """
        if not self.current_room:
            return

        # Remaining slot helpers
        def merchant_slots_remaining() -> int:
            return max(0, self.stock_count - len(self.inventory))
        def container_slots_remaining(ct: Container) -> int:
            cap = getattr(ct, 'stock_count', 0)
            if cap <= 0:
                return 0
            return max(0, cap - len(getattr(ct, 'inventory', [])))
        def all_full() -> bool:
            if merchant_slots_remaining() > 0:
                return False
            for ct in containers:
                if container_slots_remaining(ct) > 0:
                    return False
            return True
        if all_full():
            return

        import inspect
        # Build candidate classes (exclude Item itself & unique factories)
        try:
            unique_factories = set(items_module.unique_item_factories)  # type: ignore[attr-defined]
        except Exception:
            unique_factories = set()
        candidates: list[type[Item]] = []
        disallowed_classes = {Gold, Rock, Fists, Key, Special, Consumable, Accessory,
                              Gloves, Helm, Boots, Armor, Weapon, Arrow}
        for _nm, obj in inspect.getmembers(items_module, inspect.isclass):
            try:
                if obj is Item:
                    continue
                if not issubclass(obj, Item):
                    continue
                if obj in unique_factories:
                    continue
                if obj in disallowed_classes:
                    continue
                candidates.append(obj)
            except Exception:
                continue
        if not candidates:
            return

        # Specialties normalization
        specialty_classes: list[type[Item]] = []
        for spec in self.specialties or []:
            try:
                if isinstance(spec, Item):
                    specialty_classes.append(spec.__class__)
                elif isinstance(spec, type) and issubclass(spec, Item):
                    specialty_classes.append(spec)
            except Exception:
                continue

        # Weight map
        weight_map: dict[type[Item], float] = {}
        for cls in candidates:
            w = 1.0
            if any(issubclass(cls, s) for s in specialty_classes):
                w *= 3.0
            weight_map[cls] = w

        # Availability conditions adjust weights
        for cond in self.shop_conditions.get("availability", []):
            try:
                cond.adjust_restock_weights(weight_map)
            except Exception:
                continue
        weight_map = {cls: w for cls, w in weight_map.items() if w > 0}
        if not weight_map:
            return

        def weighted_choice() -> type[Item] | None:
            total = sum(weight_map.values())
            if total <= 0:
                return None
            r = random.uniform(0, total)
            acc = 0.0
            for cls, w in weight_map.items():
                acc += w
                if r <= acc:
                    return cls
            return None

        def eligible_containers_for(item: Item) -> list[Container]:
            elig: list[Container] = []
            for ct in containers:
                if container_slots_remaining(ct) <= 0:
                    continue
                allowed = getattr(ct, 'allowed_item_types', None)
                if not allowed:
                    continue
                try:
                    for t in allowed:
                        debug_item_class = item.__class__
                        if isinstance(item, t):
                            elig.append(ct)
                            break
                except Exception:
                    continue
            return elig

        safety = 0
        max_iterations = 1000
        while not all_full() and safety < max_iterations:
            safety += 1
            cls = weighted_choice()
            if cls is None:
                break
            try:
                spawned = self.current_room.spawn_item(cls.__name__, merchandise=True)
            except Exception:
                spawned = None
            if not spawned:
                continue
            self._maybe_enchant(spawned)
            if not hasattr(spawned, 'base_value'):
                try:
                    setattr(spawned, 'base_value', spawned.value)
                except Exception:
                    pass
            placed = False

            elig = eligible_containers_for(spawned)
            if elig:
                random.choice(elig).inventory.append(spawned)
                placed = True
            elif merchant_slots_remaining() > 0:
                self.inventory.append(spawned)
                placed = True
            if not placed:
                continue
            if placed:
                # Successfully placed, so we don't need it to appear in the room
                self._remove_placed_item_from_room(spawned)
        return

    def _update_shop_conditions(self):
        """Updates the merchant's shop conditions. These modify prices and availability on goods."""
        # First, clear any existing conditions by resetting the dict
        self.shop_conditions = {
            "value": [],
            "availability": [],
            "unique": []
        }
        # Value conditions
        # Up to three random value conditions can be applied. Each one has a 25% chance of being applied.
        for i in range(3):
            if random.random() < 0.25:
                # Set the amount to modify the value to a random value between 50% and 150%, with a 10% step.
                amount = random.randrange(50, 151, 10) / 100
                condition = ValueModifierCondition(amount)
                self.shop_conditions["value"].append(condition)

        # Availability conditions
        # Up to two random availability conditions can be applied. Each one has a 40% chance of being applied.
        for i in range(2):
            if random.random() < 0.4:
                # Set the weight boost to a random value between 0.25 and 3.0.
                weight_boost = round(random.uniform(0.25, 3.0), 2)
                condition = RestockWeightBoostCondition(weight_boost)
                self.shop_conditions["availability"].append(condition)

        # Unique item injection condition
        if random.random() < 0.05:  # 5% chance of being applied
            condition = UniqueItemInjectionCondition()
            self.shop_conditions["unique"].append(condition)

    def _apply_value_conditions(self):
        """Applies all value modifier conditions to the merchant's inventory items."""
        if not self.shop_conditions.get("value"):
            return
        for item in self.inventory:
            base_value = getattr(item, 'base_value', None)
            if base_value is None:
                continue
            modified_value = base_value
            for condition in self.shop_conditions["value"]:
                # Corrected: pass both item and current modified_value to condition
                try:
                    modified_value = condition.apply_to_price(item, modified_value)
                except TypeError:
                    # Fallback for legacy signature (condition.apply_to_price(base_price))
                    modified_value = condition.apply_to_price(modified_value)  # type: ignore[arg-type]
            item.value = max(1, int(modified_value))
        # Also apply to items in containers
        rooms_source = None
        if self.current_room:
            rooms_source = getattr(self.current_room, 'map', None)
            if rooms_source is None:
                uni = getattr(self.current_room, 'universe', None)
                if uni is not None:
                    rooms_source = getattr(uni, 'map', None)
        if rooms_source:
            rooms_iter = rooms_source.values() if hasattr(rooms_source, 'values') else rooms_source
            for room in rooms_iter:
                for obj in getattr(room, "objects", []):
                    if ((hasattr(obj, "inventory") and hasattr(obj, "merchant")) and
                            getattr(obj, "merchant", None) in (self, self.name)):
                        for item in obj.inventory:
                            base_value = getattr(item, 'base_value', None)
                            if base_value is None:
                                continue
                            modified_value = base_value
                            for condition in self.shop_conditions["value"]:
                                try:
                                    modified_value = condition.apply_to_price(item, modified_value)
                                except TypeError:
                                    modified_value = condition.apply_to_price(modified_value)  # type: ignore[arg-type]
                            item.value = max(1, int(modified_value))

class MiloCurioDealer(Merchant):
    def __init__(self):
        # Enchanted Weapon
        enchanted_sword = Shortsword(merchandise=True)
        functions.add_random_enchantments(enchanted_sword, 5)
        # Gold
        gold_pouch = Gold(amt=100)
        # Milo's inventory
        self.inventory = [Restorative(count=100, merchandise=True),
                          Rock(merchandise=True),
                          Spear(merchandise=True),
                          enchanted_sword,
                          gold_pouch]
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
            base_gold=self.base_gold
        )
        self.shop.exit_message = ("Milo nods as you leave his shop, "
                                  "already looking for new curiosities to add to his collection.")
    def talk(self, player):  # noqa
        print("Milo grins: 'Looking for something rare, friend? I've got just the thing!'")
    def trade(self, player):
        print("Milo opens his patchwork coat, revealing a dazzling array of curiosities.")
        # Collect merchandise items first (in case Jean picked something up on Milo's floor)
        self._collect_player_merchandise(player)
        # Local import to avoid circular import at module load
        from interface import ShopInterface as Shop
        shop = Shop(merchant=self, player=player, shop_name="The Wandering Curiosities Shop")
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
            stock_count=6,               # only a few spare slots for random stock
            inventory=self.inventory,
            specialties=specialties,
            enchantment_rate=0.0,        # potions are not enchanted
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
        print("Jambo chuckles: 'Feeling a bit under the weather, friend? Well no worry; Jambo Heals U! "
              "Come and see my selection of potions and draughts!'")

    def trade(self, player):
        # Collect any merchandise Jean brought in so it appears in the Buy list.
        self._collect_player_merchandise(player)
        # Local import to avoid circular import at module load
        from interface import ShopInterface as Shop
        self.shop = Shop(merchant=self, player=player, shop_name="Jambo Heals U")
        self.shop.exit_message = ("Jambo waves enthusiastically and loudly calls out, "
                                  "'Jambo wishes you well on your travels "
                                  "and don't forget: When you blue, Jambo Heals U!'")
        self.shop.player = player
        self.shop.run()


""" Friends """


class Friend(NPC):
    def __init__(self, name, description, damage, aggro, exp_award,
                 inventory=None, maxhp=100, protection=0, speed=10, finesse=10,
                 awareness=10, maxfatigue=100, endurance=10, strength=10, charisma=10, intelligence=10,
                 faith=10, hidden=False, hide_factor=0, combat_range=(0, 5),
                 idle_message=' is here.', alert_message='gets ready for a fight!',
                 discovery_message='someone here.', target=None, friend=True):
        self.keywords = ["talk"]
        super().__init__(name=name, description=description, damage=damage, aggro=aggro, exp_award=exp_award,
                         inventory=inventory, maxhp=maxhp, protection=protection, speed=speed, finesse=finesse,
                         awareness=awareness, maxfatigue=maxfatigue, endurance=endurance, strength=strength,
                         charisma=charisma, intelligence=intelligence, faith=faith, hidden=hidden,
                         hide_factor=hide_factor, combat_range=combat_range, idle_message=idle_message,
                         alert_message=alert_message, discovery_message=discovery_message, target=target, friend=friend)

    def talk(self, player):
        print(self.name + " has nothing to say.")


# Mynx: a friendly, non-combatant monkey-cat hybrid NPC with LLM-driven interaction hooks.
class Mynx(Friend):
    """A small, nimble forest creature (mynx) that is friendly to the player and cannot fight.

    Behavior and interaction methods are provided as stubs so an LLM can be integrated later.
    """

    def __init__(self, name: str = "Mynx", description: str | None = None):
        if description is None:
            description = (
                "A small, nimble creature with spotted fur, a prehensile tufted tail, and bright curious eyes. "
                "It chirrs and chatters but cannot speak human words."
            )
        # Damage is zero and aggro False; exp_award 0 since it's non-combatant
        super().__init__(name=name, description=description, damage=0, aggro=False, exp_award=0,
                         inventory=None, maxhp=30, protection=1, speed=18, finesse=16,
                         awareness=20, maxfatigue=50, endurance=8, strength=4, charisma=14,
                         intelligence=12, faith=6, hidden=False, hide_factor=0, combat_range=(0, 0),
                         idle_message=" flicks its tail.", alert_message="startles and chatters!",
                         discovery_message="a curious mynx.")

        # Mynx-specific traits
        self.pronouns = {"personal": "it", "possessive": "its", "reflexive": "itself", "intensive": "itself"}
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

    # Precompiled regex patterns (avoid recompiling each call)
    _re_whitespace = re.compile(r"\s+")
    _re_sentence_split = re.compile(r"[.!?]")
    _re_capitalized_token = re.compile(r"^[A-Z][A-Za-z\-']+$")
    _re_disallowed_name_token = re.compile(r"\b([A-Z][A-Za-z\-]+)('s)?\b")
    _re_self_actions = re.compile(r"\b(batting|pawing|swatting|tapping) at (?:{name}|{pronoun})\b", re.IGNORECASE)
    _re_duplicate_pronoun_template = r"\b({p})\s+\1\b"
    _gendered_pronouns = re.compile(r"\b(he|him|his|she|her|hers)\b", re.IGNORECASE)

    def _append_llm_history(self, prompt: str, response: str):
        """Append a short normalized prompt/response pair to the in-memory history (keep last 3).
        This is intentionally lightweight (whitespace normalized, truncated) to avoid long prompts.
        """
        try:
            if not isinstance(prompt, str):
                prompt = str(prompt or "")
            if not isinstance(response, str):
                response = str(response or "")
            p = re.sub(r"\s+", " ", prompt).strip()[:200]
            r = re.sub(r"\s+", " ", response).strip()[:300]
            if not p and not r:
                return
            self._llm_history.append({"prompt": p, "response": r})
            # keep only last 3
            if len(self._llm_history) > 3:
                self._llm_history = self._llm_history[-3:]
        except Exception:
            # non-fatal; history is advisory only
            return

    def _load_player_advisor(self):
        """Lazy load Jean's advisor JSON (ai/player/jean.json). Returns dict or minimal fallback."""
        if self._jean_advisor is not None:
            return self._jean_advisor
        try:
            root = Path(__file__).resolve().parent.parent  # project root
            jean_path = root / 'ai' / 'player' / 'jean.json'
            if jean_path.exists():
                import json as _json
                with open(jean_path, 'r', encoding='utf-8') as f:
                    self._jean_advisor = _json.load(f)
            else:
                self._jean_advisor = {
                    'character_name': 'Jean',
                    'pronouns': {'subject': 'he', 'object': 'him', 'possessive_adjective': 'his'},
                    'system_prompt_snippet': 'Jean is the human player (he/him). Keep references to him concise and third-person.'
                }
        except Exception:
            self._jean_advisor = {
                'character_name': 'Jean',
                'pronouns': {'subject': 'he', 'object': 'him', 'possessive_adjective': 'his'},
                'system_prompt_snippet': 'Jean is the human player (he/him). Keep references concise.'
            }
        return self._jean_advisor

    # Prevent joining combat lists
    def combat_engage(self, player):
        """Override to prevent the mynx from entering combat.
        This intentionally does nothing; mynx can never be attacked or enter combat by design.
        """
        # Keep flags consistent but do not add to player's combat lists
        self.in_combat = False
        return

    def can_enter_combat(self) -> bool:
        return False

    # Helper: lazy-load local LLM adapter when enabled
    def _get_llm_adapter(self):
        if self._llm_adapter is not None:
            return self._llm_adapter
        if os.getenv("MYNX_LLM_ENABLED", "0") not in ("1", "true", "True"):
            self._llm_adapter = None
            if os.getenv("MYNX_LLM_DEBUG", "0") in ("1", "true", "True"):
                print("[MYNX_LLM_DEBUG] Adapter disabled: set MYNX_LLM_ENABLED=1 to enable.")
            return None
        try:
            root = Path(__file__).resolve().parent.parent  # project root
            adapter_path = root / "ai" / "llm_client.py"
            if not adapter_path.exists():
                self._llm_adapter = None
                if os.getenv("MYNX_LLM_DEBUG", "0") in ("1", "true", "True"):
                    print(f"[MYNX_LLM_DEBUG] llm_client.py not found at {adapter_path}.")
                return None
            spec = importlib.util.spec_from_file_location("ai.llm_client", str(adapter_path))
            if spec and spec.loader:
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                Adapter = getattr(mod, "MynxLLMAdapter", None)
                if Adapter is None:
                    self._llm_adapter = None
                    if os.getenv("MYNX_LLM_DEBUG", "0") in ("1", "true", "True"):
                        print("[MYNX_LLM_DEBUG] MynxLLMAdapter class not found in llm_client module.")
                    return None
                inst = Adapter()
                # only keep if available
                try:
                    avail = getattr(inst, "available")()
                except Exception as e:
                    avail = False
                    if os.getenv("MYNX_LLM_DEBUG", "0") in ("1", "true", "True"):
                        print(f"[MYNX_LLM_DEBUG] Exception checking availability: {e}")
                if avail is True:
                    self._llm_adapter = inst
                    if os.getenv("MYNX_LLM_DEBUG", "0") in ("1", "true", "True"):
                        # If debug_status exists, show it
                        if hasattr(inst, "debug_status"):
                            print(f"[MYNX_LLM_DEBUG] Adapter available: {inst.debug_status()}")
                        else:
                            print("[MYNX_LLM_DEBUG] Adapter available.")
                else:
                    if hasattr(inst, "debug_status") and os.getenv("MYNX_LLM_DEBUG", "0") in ("1", "true", "True"):
                        try:
                            print(f"[MYNX_LLM_DEBUG] Adapter unavailable: {inst.debug_status()}")
                        except Exception:
                            pass
                    self._llm_adapter = None
            else:
                self._llm_adapter = None
                if os.getenv("MYNX_LLM_DEBUG", "0") in ("1", "true", "True"):
                    print("[MYNX_LLM_DEBUG] Failed to create module spec for llm_client.")
        except Exception as e:
            self._llm_adapter = None
            if os.getenv("MYNX_LLM_DEBUG", "0") in ("1", "true", "True"):
                print(f"[MYNX_LLM_DEBUG] Exception loading adapter: {e}")
        return self._llm_adapter

    def _sanitize_mynx_llm_text(self, text: str, allowed_names) -> str:
        """Post-process LLM text to reduce self-referential confusion.
        Rules:
          - Keep only the first occurrence of any allowed proper noun (other than Jean) for the mynx itself; later occurrences -> pronoun.
          - Remove self-targeting phrases like 'batting at <name/pronoun>'.
          - Strip OR replace with pronoun any capitalized tokens not in allowed_names + {'Jean'}.
          - Preserve possessive forms (Jean's, Snookums's) of allowed names; for disallowed names in possessive form, use the possessive adjective pronoun (its, his, her) instead of pronoun + apostrophe.
        allowed_names: iterable of permitted entity names (case sensitive as provided) including the mynx's name.
        """
        try:
            import re
            if not text:
                return text
            allowed = set(allowed_names or [])
            allowed.add(self.name)
            allowed.add('Jean')
            # Pre-compute possessive variants for quick membership test
            allowed_possessives = {f"{n}'s" for n in allowed}
            pronoun = self.pronouns.get("personal", "it") if hasattr(self, "pronouns") else "it"
            poss_adj = None
            if hasattr(self, "pronouns"):
                poss_adj = self.pronouns.get("possessive_adjective") or ("its" if pronoun == "it" else f"{pronoun}'s")
            else:
                poss_adj = "its" if pronoun == "it" else f"{pronoun}'s"
            name = self.name

            # Normalize whitespace
            text = re.sub(r"\s+", " ", text).strip()

            # Replace subsequent occurrences of mynx's own name with pronoun
            count = 0
            def repl_self(m):
                nonlocal count
                count += 1
                return name if count == 1 else pronoun
            pattern_self = re.compile(re.escape(name), re.IGNORECASE)
            text = pattern_self.sub(repl_self, text)

            # Remove self-targeting action patterns
            text = re.sub(rf"\b(batting|pawing|swatting|tapping) at (?:{re.escape(name)}|{pronoun})\b",
                          r"\1 playfully", text, flags=re.IGNORECASE)

            # Token pass to remove invented capitalized single words while preserving allowed possessives
            tokens = text.split(" ")
            cleaned = []
            for t in tokens:
                if re.match(r"^[A-Z][A-Za-z\-']+$", t):
                    if t in allowed or t in allowed_possessives:
                        cleaned.append(t)
                        continue
                    # Handle possessive form of an allowed name (e.g., Jean's) that might differ by case
                    if t.endswith("'s"):
                        base = t[:-2]
                        if base in allowed:
                            cleaned.append(t)  # allowed possessive
                            continue
                        # Disallowed possessive -> use possessive adjective pronoun
                        cleaned.append(poss_adj)
                        continue
                    # Disallowed capitalized token (non-possessive)
                    cleaned.append(pronoun)
                else:
                    cleaned.append(t)
            text = " ".join(cleaned)
            # Collapse duplicate pronouns (case-insensitive)
            text = re.sub(rf"\b({pronoun})\s+\1\b", pronoun, text, flags=re.IGNORECASE)
            text = re.sub(r"\s+", " ", text).strip()
            return text
        except Exception:
            return text

    # Strict pronoun & invented-name enforcement (post-sanitize)
    def _enforce_pronouns_and_names(self, text: str, roster_set: set[str]) -> str:
        try:
            if not text:
                return text
            pron_mynx = self.pronouns.get('personal', 'it') if hasattr(self, 'pronouns') else 'it'
            poss_mynx = (self.pronouns.get('possessive_adjective') or self.pronouns.get('possessive') or 'its') if hasattr(self, 'pronouns') else 'its'
            allowed = set(roster_set) | {self.name, 'Jean'}

            # First, replace invented capitalized tokens not in allowed with pronoun
            def repl_name(m):
                base = m.group(1)
                possessive = m.group(2)
                if base in allowed:
                    return m.group(0)
                # Invented name -> neutral replacement: prefer generic pronoun
                replacement = pron_mynx
                return replacement + ("'s" if possessive else '')
            text = self._re_disallowed_name_token.sub(repl_name, text)

            # Now perform sentence-aware gendered-pronoun replacement.
            # If a sentence contains 'Jean' we map gendered pronouns to Jean's configured pronouns.
            # If a sentence contains the mynx's name, prefer mynx pronouns. Otherwise prefer neutral they/their to avoid misassignment.
            jean_adv = self._load_player_advisor() or {}
            jean_pronouns = jean_adv.get('pronouns', {}) or {}
            jean_subj = jean_pronouns.get('subject', 'he')
            jean_obj = jean_pronouns.get('object', 'him')
            jean_poss = jean_pronouns.get('possessive_adjective') or jean_pronouns.get('possessive') or 'his'

            # helper to map gendered token to replacement based on target ('jean'|'mynx'|'neutral')
            def map_token(token, target):
                t = token.lower()
                if target == 'jean':
                    if t in ('he', 'she'):
                        return jean_subj
                    if t in ('him', 'her'):
                        return jean_obj
                    if t in ('his', 'hers'):
                        return jean_poss
                    return jean_subj
                if target == 'mynx':
                    if t in ('he', 'she'):
                        return pron_mynx
                    if t in ('him', 'her'):
                        return pron_mynx
                    if t in ('his', 'hers'):
                        return poss_mynx
                    return pron_mynx
                # neutral
                if t in ('he', 'she'):
                    return 'they'
                if t in ('him', 'her'):
                    return 'them'
                if t in ('his', 'hers'):
                    return 'their'
                return 'they'

            # split into sentences and replace gendered pronouns per-sentence
            parts = []
            last_end = 0
            for sep in re.finditer(r'[.!?]+', text):
                end = sep.end()
                sentence = text[last_end:end]
                last_end = end
                parts.append(sentence)
            # tail
            if last_end < len(text):
                parts.append(text[last_end:])

            processed = []
            for sent in parts:
                s = sent
                # determine who is the likely antecedent
                lowered = s.lower()
                target = None
                if 'jean' in lowered:
                    target = 'jean'
                elif self.name.lower() in lowered:
                    target = 'mynx'
                else:
                    # look for any other roster names; if a roster name (other NPC) appears, prefer neutral
                    found_other = False
                    for nm in roster_set:
                        if nm.lower() != self.name.lower() and nm.lower() in lowered:
                            found_other = True
                            break
                    target = 'neutral' if found_other else 'neutral'

                # replace gendered pronouns in this sentence according to target
                def repl_gendered_local(m):
                    token = m.group(1)
                    return map_token(token, target)

                s = self._gendered_pronouns.sub(repl_gendered_local, s)
                processed.append(s)

            text = ''.join(processed)

            # Collapse duplicate pronouns
            dup_re = re.compile(self._re_duplicate_pronoun_template.format(p=re.escape(pron_mynx)), re.IGNORECASE)
            text = dup_re.sub(pron_mynx, text)
            return self._normalize_ws(text)
        except Exception:
            return text

    def _gather_environment_lists(self):
        nearby_items = []
        nearby_objects = []
        other_npcs = []
        room = getattr(self, 'current_room', None)
        if not room:
            return '', set()
        try:
            room_items = getattr(room, 'items_here', None) or getattr(room, 'items', None) or getattr(room, 'spawned', None) or []
            for itm in room_items or []:
                nm = getattr(itm, 'name', None) or getattr(itm, 'title', None)
                desc = getattr(itm, 'description', None) or getattr(itm, 'short_description', None)
                if isinstance(nm, str) and nm.strip():
                    name = self._normalize_ws(nm)[:60]
                    if isinstance(desc, str) and desc.strip():
                        d = self._normalize_ws(desc)[:140]
                        nearby_items.append(f"{name} — {d}")
                    else:
                        nearby_items.append(f"{name} — (no description)")
            room_objs = getattr(room, 'objects_here', None) or getattr(room, 'objects', None) or []
            for obj in room_objs or []:
                onm = getattr(obj, 'name', None)
                odesc = getattr(obj, 'description', None) or getattr(obj, 'summary', None)
                if isinstance(onm, str) and onm.strip():
                    name = self._normalize_ws(onm)[:60]
                    if isinstance(odesc, str) and odesc.strip():
                        s = self._normalize_ws(odesc).split('.')[0][:140]
                        nearby_objects.append(f"{name} — {s}")
                    else:
                        nearby_objects.append(f"{name} — (no description)")
            for npc_inst in getattr(room, 'npcs_here', []) or []:
                nm = getattr(npc_inst, 'name', None)
                if isinstance(nm, str) and nm.strip() and nm != self.name:
                    ndesc = getattr(npc_inst, 'description', None) or getattr(npc_inst, 'discovery_message', None)
                    name = self._normalize_ws(nm)[:60]
                    if isinstance(ndesc, str) and ndesc.strip():
                        nd = self._normalize_ws(ndesc)[:140]
                        other_npcs.append(f"{name} — {nd}")
                    else:
                        other_npcs.append(f"{name} — (no description)")
        except Exception:
            pass
        def prep(lst):
            try:
                return '; '.join(list(dict.fromkeys(lst))[:5])
            except Exception:
                return ''
        ni = prep(nearby_items)
        no = prep(nearby_objects)
        nn = prep(other_npcs)
        env_parts = []
        if ni: env_parts.append(f"Nearby items (name — description): {ni}.")
        if no: env_parts.append(f"Nearby objects (name — description): {no}.")
        if nn: env_parts.append(f"Other nearby NPCs (name — description): {nn}.")
        return (' ' + ' '.join(env_parts) if env_parts else ''), set()

    def _build_history_block(self):
        history_lines = []
        try:
            for h in (self._llm_history or [])[-3:]:
                ph = h.get('prompt', '')
                rh = h.get('response', '')
                phs = self._normalize_ws(str(ph))[:120]
                rhs = self._normalize_ws(str(rh))[:180]
                if phs or rhs:
                    history_lines.append(f"Prompt: '{phs}' -> Resp: '{rhs}'")
        except Exception:
            pass
        if history_lines:
            return " Conversation history (most recent last): " + " | ".join(history_lines) + "."
        return ''

    def _build_pronoun_guidance(self, jean_pronoun_line: str, jean_snippet: str):
        mynx_personal = self.pronouns.get('personal', 'it') if hasattr(self, 'pronouns') else 'it'
        mynx_possessive = (self.pronouns.get('possessive_adjective') or self.pronouns.get('possessive') or 'its') if hasattr(self, 'pronouns') else 'its'
        try:
            pg = []
            if jean_pronoun_line:
                pg.append(f"For Jean use: {jean_pronoun_line.strip()}")
            pg.append(f"For the mynx use: {mynx_personal}/{mynx_possessive}.")
            pg.append("For any other nearby NPCs, prefer using their NAME; if a pronoun is needed, use they/them/their.")
            return ' '.join(pg) + f" {jean_snippet}" if jean_snippet else ' '.join(pg)
        except Exception:
            return "Use Jean and Mynx pronouns consistently; prefer names for others or they/them."

    def _build_llm_context(self, roster_set: set[str], prompt: str, jean_pronoun_line: str, jean_snippet: str):
        room_desc_raw = getattr(self.current_room, 'description', '') if getattr(self, 'current_room', None) else ''
        room_desc_raw = self._normalize_ws(room_desc_raw)
        room_desc = f" You are in {room_desc_raw}." if room_desc_raw else '.'
        env_lists, _ = self._gather_environment_lists()
        history_block = self._build_history_block()
        pronoun_guidance = self._build_pronoun_guidance(jean_pronoun_line, jean_snippet)
        allowed_names = ', '.join(sorted(roster_set | {'Jean'}))
        # Assemble with list join to reduce concatenation overhead
        parts = [
            "You describe only what the mynx does in one immediate, nonverbal action.",
            f"The mynx's proper name is {self.name}.",
            f"{self.name} is the ACTOR, never its own target.",
            f"Allowed entity names you may reference (no others): {allowed_names}.",
            "Do not invent other creature names. If the player is referenced use 'Jean'.",
            pronoun_guidance,
            "Keep it present-tense, concise (<=2 short sentences), no speech.",
            f"Player action/intent: '{prompt or 'interact'}'.",
            room_desc + env_lists,
            "Respond in a way that's appropriate for the environment.",
            history_block,
            "Try not to repeat recent actions or descriptions; be novel relative to the above history."
        ]
        ctx = ' '.join(filter(None, parts))
        if os.getenv('MYNX_LLM_DEBUG', '0') in ('1', 'true', 'True'):
            try:
                print(f"[MYNX_LLM_DEBUG] Built context ({len(ctx)} chars): {ctx[:4000]}")
            except Exception:
                pass
        return ctx

    def interact_with_player(self, player, prompt: str | None = None, structured: bool = False):
        # Minimal prompt normalization
        p = (prompt or '').strip().lower()
        action_print = None
        if p in ("pet", "stroke", "scritch"):
            action_print = "Jean reaches out to pet the mynx."
        elif p in ("feed", "offer food", "give food"):
            action_print = "Jean offers a morsel of food to the mynx."
        elif p.startswith("play with ") or p in ("play", "toy", "tease"):
            item_name = p[len("play with "):].strip() if p.startswith("play with ") else None
            action_print = f"Jean plays with the mynx using {item_name}." if item_name else "Jean tries to play with the mynx."
        elif p:
            action_print = f"Jean {p}."
        else:
            action_print = "Jean interacts with the mynx."
        try:
            print(action_print)
        except Exception:
            pass
        adapter = self._get_llm_adapter()
        roster = []
        if getattr(self, 'current_room', None) is not None:
            try:
                for npc_inst in getattr(self.current_room, 'npcs_here', []) or []:
                    nm = getattr(npc_inst, 'name', None)
                    if isinstance(nm, str):
                        roster.append(nm)
            except Exception:
                pass
        if self.name not in roster:
            roster.append(self.name)
        roster_set = set(roster)
        if adapter is not None:
            jean_adv = self._load_player_advisor() or {}
            jean_pronouns = jean_adv.get('pronouns', {})
            jean_snippet = jean_adv.get('system_prompt_snippet', '')[:300]
            jean_pronoun_line = ''
            if jean_pronouns:
                subj = jean_pronouns.get('subject', 'he')
                obj = jean_pronouns.get('object', 'him')
                poss = jean_pronouns.get('possessive_adjective', 'his')
                jean_pronoun_line = f"{subj}/{obj}/{poss}."
            context = self._build_llm_context(roster_set, p, jean_pronoun_line, jean_snippet)
            responded = False
            try:
                if structured:
                    obj = adapter.generate_structured(context=context)
                    if isinstance(obj, dict) and isinstance(obj.get('description'), str):
                        if os.getenv('MYNX_LLM_DEBUG', '0') in ('1', 'true', 'True'):
                            try: print(f"[MYNX_LLM_DEBUG] Raw structured description: {obj.get('description')}")
                            except Exception: pass
                        desc = self._sanitize_mynx_llm_text(obj['description'], roster_set)
                        desc = self._enforce_pronouns_and_names(desc, roster_set)
                        desc_checked = self._check_and_correct_mynx_text(desc, p, roster)
                        if desc_checked is None:
                            obj = None
                        else:
                            obj['description'] = desc_checked
                            self._llm_last_response = obj
                            try: self._append_llm_history(p, desc_checked)
                            except Exception: pass
                            responded = True
                            return obj
                else:
                    text_resp = adapter.generate_plain(context=context)
                    if isinstance(text_resp, str) and text_resp:
                        if os.getenv('MYNX_LLM_DEBUG', '0') in ('1', 'true', 'True'):
                            try: print(f"[MYNX_LLM_DEBUG] Raw plain text: {text_resp}")
                            except Exception: pass
                        sanitized = self._sanitize_mynx_llm_text(text_resp, roster_set)
                        sanitized = self._enforce_pronouns_and_names(sanitized, roster_set)
                        checked = self._check_and_correct_mynx_text(sanitized, p, roster)
                        if checked is not None:
                            self._llm_last_response = {
                                'action': 'narrate', 'intensity': 'low', 'description': checked,
                                'duration_seconds': 2, 'audible': 'soft chitter'
                            }
                            try: self._append_llm_history(p, checked)
                            except Exception: pass
                            print(checked)
                            responded = True
                            return checked
            except Exception as e:
                if os.getenv('MYNX_LLM_DEBUG', '0') in ('1', 'true', 'True'):
                    print(f"[MYNX_LLM_DEBUG] Generation/validation error, falling back: {e}")
        # Deterministic stub fallback responses (legacy behavior for tests / offline mode)
        if p in ("pet", "stroke", "scritch"):
            text = f"{self.name} leans into the hand, purring a soft chitter and nudging the wrist with its head."
            structured_obj = {
                "action": "groom",
                "intensity": "gentle",
                "description": text,
                "duration_seconds": 2,
                "audible": "soft purr/chitter"
            }
            # record fallback in history
            try:
                self._append_llm_history(p, text)
            except Exception:
                pass
        elif p in ("feed", "offer food", "give food"):
            text = f"{self.name} eyes the offered morsel, snatches it with a quick paw, and tucks it into its tail-fur triumphantly."
            structured_obj = {
                "action": "take_food",  # legacy test expectation; synonym of 'steal_food'
                "intensity": "medium",
                "description": text,
                "duration_seconds": 3,
                "audible": "happy chitter"
            }
            try:
                self._append_llm_history(p, text)
            except Exception:
                pass
        elif p in ("play", "toy", "tease"):
            text = f"{self.name} bats the object with nimble paws, then darts back and forth in a brief, jubilant display."
            structured_obj = {
                "action": "play",  # legacy test expectation; synonym of 'playful_tussle'
                "intensity": "high",
                "description": text,
                "duration_seconds": 4,
                "audible": "rapid chitters"
            }
            try:
                self._append_llm_history(p, text)
            except Exception:
                pass
        else:
            text = f"{self.name} pads forward on silent paws, head cocked, whiskers twitching as it studies you."
            structured_obj = {
                "action": "investigate",  # legacy test expectation; synonym of 'investigate_object'
                "intensity": "low",
                "description": text,
                "duration_seconds": 3,
                "audible": "soft chitter"
            }
            try:
                self._append_llm_history(p, text)
            except Exception:
                pass
        self._llm_last_response = structured_obj
        if structured:
            return structured_obj
        print(text)
        # configurable delay (default legacy 1.5s) to avoid slowing tests/game unnecessarily
        try:
            delay = float(os.getenv("MYNX_FALLBACK_DELAY", "1.5"))
        except Exception:
            delay = 1.5
        try:
            if delay > 0:
                time.sleep(delay)
        except Exception:
            pass
        return text

    # Override talk to use the interaction framework
    def talk(self, player, prompt: str | None = None, structured: bool = False):
        try:
            return self.interact_with_player(player, prompt=prompt, structured=structured)
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

    def _normalize_ws(self, text: str) -> str:
        try:
            return self._re_whitespace.sub(" ", text).strip()
        except Exception:
            return text.strip() if isinstance(text, str) else str(text)

    def _check_and_correct_mynx_text(self, text: str, prompt: str, roster) -> str | None:
        """Validate and lightly correct LLM output. Return corrected text or None if unacceptable.
        Heuristics:
          - <= 2 sentences (split on . ! ?) with non-empty content.
          - No disallowed proper nouns (capitalized tokens) outside roster + Jean + mynx name.
          - Present-tense preference: avoid majority past-tense tokens ending with 'ed'.
          - Length 5..200 chars.
          - Reject speech / quoted dialogue.
        Correction attempts:
          - Trim to first 2 sentences.
          - Replace disallowed capitalized tokens (and possessives) with mynx pronouns / possessive adjective.
          - Ensure terminal period.
        """
        try:
            import re as _re
            if not isinstance(text, str):
                return None
            raw = text.strip()
            if not raw:
                return None
            if '"' in raw or ("'" in raw and (' says ' in raw or raw.count('"') >= 2)):
                return None
            sentences = [s.strip() for s in _re.split(r"[.!?]", raw) if s.strip()]
            if not sentences:
                return None
            if len(sentences) > 2:
                sentences = sentences[:2]
            candidate = '. '.join(sentences)
            allowed = set(roster or []) | {self.name, 'Jean'}
            pronoun = self.pronouns.get('personal', 'it') if hasattr(self, 'pronouns') else 'it'
            poss_adj = (self.pronouns.get('possessive_adjective') or self.pronouns.get('possessive') or 'its') if hasattr(self, 'pronouns') else 'its'
            pattern = _re.compile(r"\b([A-Z][A-Za-z\-]+)('s)?\b")
            def fix_token(m):
                base = m.group(1)
                possessive = m.group(2)
                if base in allowed:
                    return base + (possessive or '')
                if possessive:
                    return poss_adj
                return pronoun
            candidate = pattern.sub(fix_token, candidate)
            ed_tokens = [t for t in candidate.split() if t.lower().endswith('ed')]
            if len(ed_tokens) > 3 and len(ed_tokens) >= len(candidate.split()) * 0.4:
                return None
            candidate = candidate.strip()
            if not (5 <= len(candidate) <= 200):
                return None
            if not candidate.endswith('.'):
                candidate += '.'
            return candidate
        except Exception:
            return None

class Gorran(Friend):  # The "rock-man" that helps Jean at the beginning of the game.
    def __init__(self):
        description = """
A massive creature that somewhat resembles a man,
except he is covered head-to-toe in rock-like armor. He seems a bit clumsy and his
speech is painfully slow and deep. He seems to prefer gestures over actual speech,
though this makes his intent a bit difficult to interpret. At any rate, he seems
friendly enough to Jean.
"""
        super().__init__(name="Rock-Man", description=description, maxhp=200,
                         damage=55, awareness=20, speed=5, aggro=True, exp_award=0,
                         combat_range=(0, 7),
                         idle_message=" is bumbling about.",
                         alert_message=" lets out a deep and angry rumble!")
        self.add_move(moves.NpcAttack(self), 4)
        self.add_move(moves.Advance(self), 4)
        self.add_move(moves.GorranClub(self), 3)
        self.add_move(moves.NpcIdle(self))
        self.add_move(moves.Parry(self), 2)
        self.keywords = ["talk"]
        self.pronouns = {"personal": "he", "possessive": "his", "reflexive": "himself", "intensive": "himself"}

    def before_death(self):
        print(colored(self.name, "yellow", attrs="bold") + " quaffs one of his potions!")
        self.fatigue /= 2
        self.hp = self.maxhp
        return False

    def talk(self, player):
        if self.current_room.universe.story["gorran_first"] == "0":
            self.current_room.events_here.append(
                functions.seek_class("AfterGorranIntro", "story")(player, self.current_room, None, False))
            self.current_room.universe.story["gorran_first"] = "1"
        else:
            print(self.name + " has nothing to say.")

class Slime(NPC):
    def __init__(self):
        description = "Goop that moves. Gross."
        super().__init__(name="Slime " + genericng.generate(4, 5), description=description, maxhp=10,
                         damage=20, awareness=12, aggro=True, exp_award=1,
                         idle_message=" is glopping about.",
                         alert_message="burbles angrily at Jean!")
        self.add_move(moves.NpcAttack(self), 5)
        self.add_move(moves.Advance(self), 4)
        self.add_move(moves.NpcIdle(self))
        self.add_move(moves.Dodge(self))

class Testexp(NPC):
    def __init__(self):
        description = "Goop that moves. Gross."
        super().__init__(name="Slime " + genericng.generate(4, 5), description=description, maxhp=200,
                         damage=2, awareness=12, aggro=True, exp_award=500,
                         idle_message=" is glopping about.",
                         alert_message="burbles angrily at Jean!")
        self.add_move(moves.NpcAttack(self), 5)
        self.add_move(moves.Advance(self), 4)
        self.add_move(moves.NpcIdle(self))
        self.add_move(moves.Dodge(self))

class RockRumbler(NPC):
    def __init__(self):
        description = ("A burly creature covered in a rock-like carapace somewhat resembling a stout crocodile."
                      "Highly resistant to most weapons. You'd probably be better off avoiding combat with this"
                      "one.")
        super().__init__(name="Rock Rumbler " + genericng.generate(2, 4), description=description, maxhp=30,
                         damage=22, protection=30, awareness=25, aggro=True, exp_award=100)
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
        description = ("A grisly demon of the dark. Its body is vaguely humanoid in shape. Long, thin arms end"
                      "in sharp, poisonous claws. It prefers to hide in the dark, making it difficult to surprise.")
        super().__init__(name="Lurker " + genericng.generate(2, 4), description=description, maxhp=250,
                         damage=25, protection=0, awareness=60, endurance=20, aggro=True, exp_award=800)
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
        description = ("A humongous spider, covered in black, wiry hairs. It skitters about, looking for its next "
                       "victim to devour It flexes its sharp, poisonous mandibles in eager anticipation, "
                       "spilling toxic drool that leaves a glowing green "
                       "trail in its wake. Be careful that you don't fall victim to its bite!")
        super().__init__(name="Giant Spider " + genericng.generate(1), description=description, maxhp=110,
                         damage=22, protection=0, awareness=30, endurance=10, aggro=True, exp_award=120)
        self.resistance_base["fire"] = -0.5
        self.status_resistance_base["poison"] = 1
        self.add_move(moves.NpcAttack(self), 3)
        self.add_move(moves.SpiderBite(self), 6)
        self.add_move(moves.Advance(self), 4)
        self.add_move(moves.Withdraw(self))
        self.add_move(moves.NpcIdle(self))
        self.add_move(moves.Dodge(self), 2)

# Agent Support: This is the end of the file npc.py
