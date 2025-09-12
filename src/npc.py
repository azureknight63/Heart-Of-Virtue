import random
import time
import genericng
import moves
import functions
from neotermcolor import colored, cprint
import loot_tables
from items import Item, Shortsword, Gold, Restorative, Rock, Spear
import items as items_module  # added for unique item registry management
from objects import Container
from interface import ShopInterface as Shop
from shop_conditions import ValueModifierCondition, RestockWeightBoostCondition, UniqueItemInjectionCondition

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
        self.inventory: list[Item] = inventory
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
        self.inventory = []
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
                 specialties: list[Item]=None, enchantment_rate: float=1.0,
                 always_stock: list[Item]=None,
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
            "{merchant} deftly relieves Jean of the {item} and adds it to the display.",
            "With a practiced motion {merchant} places the {item} among the wares.",
            "'{item}? Fine taste,' {merchant} says, arranging it for sale.",
            "{merchant} chuckles softly and logs the {item} into a battered ledger.",
            "'{player}, I'll catalog that {item} for you first,' {merchant} murmurs." ,
            "The {item} is whisked from Jean's hands and rotated under the light before joining the stock." ,
            "{merchant} nods knowingly— the {item} now sits center shelf." ,
            "'Curious about the {item}? Let's price it properly,' says {merchant}."
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
                    item=getattr(it, 'name', 'item'),
                    player=getattr(player, 'name', 'Jean')
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
        self.shop = Shop(merchant=self, player=None, shop_name=f"{self.name}'s Shop")

    def talk(self, player):
        print(self.name + " has nothing to say.")

    def trade(self, player):
        """
        This method is called when the player wants to trade with the merchant.
        It should handle the trading logic, such as buying and selling items.
        """
        print(f"{self.name} is ready to trade with you.")
        # First, absorb any merchandise Jean carried over so it appears in the Buy list.
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
        if self.current_room and hasattr(self.current_room, 'map'):
            for room in self.current_room.map:
                for obj in getattr(room, "objects", []):
                    if ((hasattr(obj, "inventory") and hasattr(obj, "merchant")) and
                            getattr(obj, "merchant", None) == self.name):
                        total += len(obj.inventory)
        return total

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
        if self.current_room and getattr(self.current_room, 'map', None):
            for room in self.current_room.map.values():
                for obj in getattr(room, "objects", []):
                    if ((hasattr(obj, "inventory") and hasattr(obj, "merchant")) and
                            getattr(obj, "merchant", None) == self.name):
                        # Scan container inventory for unique items prior to clearing
                        for it in getattr(obj, 'inventory', []) or []:
                            if getattr(it, 'unique', False):
                                removed_unique.add(it.__class__.__name__)
        # Now clear merchant inventory
        self.inventory = []
        # And clear container inventories while recording them
        if not self.current_room or not getattr(self.current_room, 'map', None):
            # Deregister unique items (safe even if set not present)
            for cls_name in removed_unique:
                items_module.unique_items_spawned.discard(cls_name)
            return containers
        for room in self.current_room.map.values():
            if isinstance(room, str):
                continue
            for obj in room.objects_here:
                if ((hasattr(obj, "inventory") and hasattr(obj, "merchant")) and
                            getattr(obj, "merchant", None) == self.name):
                    obj.inventory = []
                    containers.append(obj)
            for item in room.items_here[:]:
                if getattr(item, 'merchandise', None) and item.merchandise:
                    room.items_here.remove(item)
        # Finally, release unique item class names so they can be spawned again later
        for cls_name in removed_unique:
            items_module.unique_items_spawned.discard(cls_name)
        return containers

    def _create_always_stock_item(self, item_spec) -> Item | None:
        """Instantiate an item from an always_stock entry.
        Supports either an Item subclass or an Item instance (used as a template).
        Preserves count when provided on a template instance.
        """
        # Determine desired count (if template instance supplies it and >1)
        desired_count = 0
        template_instance = None
        if isinstance(item_spec, Item):
            template_instance = item_spec
            if hasattr(item_spec, 'count') and getattr(item_spec, 'count', 0) > 1:
                desired_count = item_spec.count
            item_class_name = item_spec.__class__.__name__
        else:
            # Assume it's a class / type; fall back gracefully
            if hasattr(item_spec, '__name__'):
                item_class_name = item_spec.__name__
            else:
                return None
            if hasattr(item_spec, 'count') and getattr(item_spec, 'count', 0) > 1:
                desired_count = item_spec.count
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
        for _nm, obj in inspect.getmembers(items_module, inspect.isclass):
            try:
                if obj is Item:
                    continue
                if not issubclass(obj, Item):
                    continue
                if obj in unique_factories:
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
            if not hasattr(spawned, 'base_value'):
                try:
                    setattr(spawned, 'base_value', spawned.value)
                except Exception:
                    pass
            self._maybe_enchant(spawned)
            placed = False
            #todo seems to be failing to place anything here

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
                self.current_room.items_here.remove(spawned)
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
        if self.current_room and getattr(self.current_room, 'map', None):
            for room in self.current_room.map:
                for obj in getattr(room, "objects", []):
                    if ((hasattr(obj, "inventory") and hasattr(obj, "merchant")) and
                            getattr(obj, "merchant", None) == self.name):
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
            stock_count=50
        )
        self.shop.exit_message = ("Milo nods as you leave his shop, "
                                  "already looking for new curiosities to add to his collection.")
    def talk(self, player):  # noqa
        print("Milo grins: 'Looking for something rare, friend? I've got just the thing!'")
    def trade(self, player):
        print("Milo opens his patchwork coat, revealing a dazzling array of curiosities.")
        # Collect merchandise items first (in case Jean picked something up on Milo's floor)
        self._collect_player_merchandise(player)
        shop = Shop(merchant=self, player=player, shop_name="The Wandering Curiosities Shop")
        shop.run()


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


class Gorran(Friend):  # The "rock-man" that helps Jean at the beginning of the game.
    # His name is initially unknown. Species name is Grondite.
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
        self.pronouns = {
            "personal": "he", "possessive": "his", "reflexive": "himself", "intensive": "himself"
        }

    def before_death(self):  # this essentially makes Gorran invulnerable, though he will likely have to rest
        print(colored(self.name, "yellow", attrs="bold") + " quaffs one of his potions!")
        self.fatigue /= 2
        self.hp = self.maxhp
        return False

    def talk(self, player):
        if self.current_room.universe.story["gorran_first"] == "0":
            self.current_room.events_here.append(
                functions.seek_class("AfterGorranIntro", "story")(player,
                                                                  self.current_room, None, False))
            self.current_room.universe.story["gorran_first"] = "1"

        else:
            print(self.name + " has nothing to say.")


class Slime(NPC):  # target practice
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


class Testexp(NPC):  # target practice
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
        description = "A burly creature covered in a rock-like carapace somewhat resembling a stout crocodile." \
                      "Highly resistant to most weapons. You'd probably be better off avoiding combat with this" \
                      "one."
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
        description = "A grisly demon of the dark. Its body is vaguely humanoid in shape. Long, thin arms end" \
                      "in sharp, poisonous claws. It prefers to hide in the dark, making it difficult to surprise."
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
