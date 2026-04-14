"""
NPCLootMixin — death, loot table rolls, and inventory drops.

Mixed into NPC (_base.py).  Contains the four methods that handle what
happens when an NPC dies: the death hook, inventory scattering, and the
loot-table roll.

Also exports the module-level `loot` object so that _base.py and
_enemies.py can reference loot table tiers (loot.lev0, loot.lev1, etc.)
without creating multiple Loot instances.

Attributes expected on the host class (provided by NPC.__init__):
    self.name           str
    self.loot           dict | None     (loot table tier)
    self.inventory      list[Item]
    self.current_room   Room | None
    self.player_ref     Player | None
"""

import random

import functions  # type: ignore
import loot_tables  # type: ignore
from neotermcolor import colored, cprint  # type: ignore

# Single Loot instance shared across the package via import
loot = loot_tables.Loot()


class NPCLootMixin:
    """Death sequencing and loot distribution for NPC."""

    def die(self):
        really_die = self.before_death()
        if really_die:
            print(colored(self.name, "magenta") + " exploded into fragments of light!")

    def before_death(
        self,
    ):  # Overwrite for each NPC if they are supposed to do something special before dying
        if self.loot:
            self.roll_loot()  # checks to see if an item will drop
        self.drop_inventory()
        return True

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
