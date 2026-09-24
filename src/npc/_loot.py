"""
NPCLootMixin — death, loot table rolls, and inventory drops.

Mixed into NPC (_base.py). Handles what happens when an NPC dies: the death
hook, the loot-table roll, inventory scattering and embedded arrows, the
stacking of that death's own drops, and the bookkeeping that records what
landed for the victory's loot offer (``player.combat_drops``, #621).

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

import src.functions as functions  # type: ignore
import src.loot_tables as loot_tables  # type: ignore
from src.combatant import wire_handle  # type: ignore
from src.narration import colored, cprint, narrate  # type: ignore
# Single Loot instance shared across the package via import
loot = loot_tables.Loot()


def _floor_of(room):
    """``room.items_here`` when it is a real list, else None -- a tile double
    or a room built without a floor has nothing to diff or restack."""
    floor = getattr(room, "items_here", None)
    return floor if isinstance(floor, list) else None


class NPCLootMixin:
    """Death sequencing and loot distribution for NPC."""

    def die(self):
        if self.check_revive():
            return
        really_die = self.before_death()
        if really_die:
            narrate(colored(self.name, color="magenta") + " exploded into fragments of light!")

    def before_death(self):
        """Put this NPC's loot on the floor as it dies; True means really die.

        Roll the loot table, scatter the inventory, spill embedded arrows,
        then stack what THIS death dropped (never what was already lying
        there -- #621). Subclasses override it to do something special first.
        """
        dropped = []
        if self.loot:
            dropped += self.roll_loot() or []  # checks to see if an item will drop
        dropped += self.drop_inventory() or []
        dropped += self.drop_embedded_arrows() or []
        self._stack_own_drops(dropped)
        return True

    def _spawn_drop(self, spawn):
        """Run ``spawn`` and return ``(what it returned, everything it added)``.

        ``MapTile.spawn_item`` returns ``spawned[0]`` only: a non-stackable of
        ``amt`` 2 creates two objects and hands back the first, and
        ``Loot.random_equipment`` spawns inside itself. Diffing ``items_here``
        around the call recovers the whole set without changing a return value
        the rest of the engine reads as "the item".

        Compared by ``id``: ``Item`` defines no ``__eq__`` today, so a
        membership test would work, but it would start conflating twins the
        day one is defined — and identity is the entire point here (#621).
        """
        room = self.current_room
        floor = _floor_of(room)
        if floor is None:
            # No real floor to diff — a tile double in a test, or a room built
            # without one. Take the spawn at its word rather than raising in
            # the middle of a death.
            result = spawn()
            return result, [result] if result is not None else []
        before = {id(item) for item in floor}
        result = spawn()
        return result, [i for i in floor if id(i) not in before]

    def _record_combat_drop(self, name, quantity, kind, objects):
        """Record what this death put on the floor, for the victory loot offer.

        API combat mode only: ``player.combat_drops`` is read by the victory
        summary and by ``GameService.collect_combat_loot``, and nothing writes
        it outside a fight, which is what keeps the offer scoped to one fight.

        ``handles`` is the offer's identity. The collect resolves those wire
        handles against the fight's tile, so no same-named object the fight did
        not drop — an older twin, a pile that was already lying there, a hidden
        one the player never found — can stand in for a drop (#621). Recording
        every spawned object, not just the one ``spawn_item`` returned, is what
        makes that resolution complete for a multi-object drop.
        """
        player = getattr(self, "player_ref", None)
        if not player or not hasattr(player, "_combat_adapter"):
            return
        if not hasattr(player, "combat_drops"):
            player.combat_drops = []
        player.combat_drops.append(
            {
                "name": name,
                "quantity": int(quantity),
                "source": getattr(self, "name", "Unknown"),
                "kind": kind,
                "handles": [wire_handle(obj) for obj in objects],
            }
        )

    def _stack_own_drops(self, dropped):
        """Merge this death's own drops into one pile per kind and visibility.

        This is the narrowed descendant of a whole-floor
        ``functions.stack_items_list(items_here)`` call, whose comment said
        "prevent duplicates". The commit that added it says what that meant
        (2d0f625, "items dropped by enemies now stack immediately after NPC
        death via stack_items_list() — previously items didn't stack until
        next world beat, creating visual clutter"): one death's several drops
        of a kind were arriving as several piles. That intent is kept here.

        What is dropped is the collateral. Stacking the whole floor merged a
        drop into the FIRST pile of its kind — oldest wins, ``hidden``
        ignored — which handed that pile's pre-existing units to the loot
        collect along with the drop, and could drag a hidden stash out of
        concealment with them (#621). Only objects this death spawned are
        merged now, and never across the visible/hidden line: a scattered
        inventory pile is hidden and a loot-table roll is not, and merging
        those two either conceals a drop the player was shown or reveals a
        cache they had not found.
        """
        room = self.current_room
        if _floor_of(room) is None:
            return
        merged_away = []
        for concealed in (False, True):
            group = [d for d in dropped if bool(getattr(d, "hidden", False)) is concealed]
            survivors = list(group)
            # ``functions.stack_items_list``'s grouping rules (stack_key,
            # class/name/description, merchandise) -- the pack's, not the
            # floor pass's, which groups by class alone.
            functions.stack_items_list(survivors)
            kept = {id(s) for s in survivors}
            merged_away += [g for g in group if id(g) not in kept]
        if not merged_away:
            return
        gone = {id(m) for m in merged_away}
        room.items_here[:] = [i for i in room.items_here if id(i) not in gone]
        self._forget_drop_handles({wire_handle(m) for m in merged_away})

    def _forget_drop_handles(self, handles):
        """Drop merged-away objects from the loot offer.

        Offer hygiene: their units live on in the pile they were merged into,
        which is itself one of this death's recorded drops, so the offer keeps
        only handles that still name an object. (A dead handle would not cost
        the player anything today -- ``_take_offered_drops`` reports
        ``not_found`` only when none of a name's handles resolve -- but the
        #621 floor freeze reads these handles to find the fight's tile.)

        Only handles minted for *this* death's objects are passed in, so an
        earlier kill's entries in the same fight cannot be touched.
        """
        drops = getattr(getattr(self, "player_ref", None), "combat_drops", None)
        if not isinstance(drops, list):
            return
        for entry in drops:
            if isinstance(entry, dict) and isinstance(entry.get("handles"), list):
                entry["handles"] = [h for h in entry["handles"] if h not in handles]

    def drop_embedded_arrows(self):
        """Arrows that hit and stuck in this NPC are 100% recoverable from the
        corpse (issue #418) — unlike drop_inventory()'s randomized survival
        chance, every embedded arrow spawns. Visible immediately (not hidden),
        since an arrow sticking out of a corpse isn't concealed the way
        scattered inventory contents are.

        Returns the objects it spawned, for ``before_death``'s stacking pass.
        """
        embedded = getattr(self, "embedded_arrows", None)
        if not embedded or self.current_room is None:
            return []
        spawned = []
        for arrow_class_name in embedded:
            _, landed = self._spawn_drop(
                lambda name=arrow_class_name: self.current_room.spawn_item(name)
            )
            spawned += landed
        self.embedded_arrows = []
        return spawned

    def drop_inventory(self):
        """Scatter what this NPC was carrying, and return what landed."""
        if len(self.inventory) > 0 and self.current_room is None:
            narrate("### ERR: Current room for {} ({}) is None".format(self.name, self))
            return []
        spawned = []
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
                    _, landed = self._spawn_drop(
                        lambda item=item, quantity=quantity: self.current_room.spawn_item(
                            item.__class__.__name__,
                            amt=quantity,
                            hidden=1,
                            hfactor=random.randint(20, 60),
                        )
                    )
                    spawned += landed
                    item_name = getattr(item, "name", item.__class__.__name__)
                    self._record_combat_drop(item_name, quantity, "inventory", landed)
            self.inventory = []
        return spawned

    def roll_loot(
        self,
    ):  # when the NPC dies, do a roll to see if any loot drops
        """Roll this NPC's loot table; return the objects that landed."""
        if self.current_room is None:
            narrate("### ERR: Current room for {} ({}) is None".format(self.name, self))
            return []
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
                    drop, landed = self._spawn_drop(
                        lambda p=params: loot.random_equipment(
                            self.current_room, p[1], p[2]
                        )
                    )
                    if drop is None:
                        continue  # no equipment at that level: skip this entry
                else:
                    drop, landed = self._spawn_drop(
                        lambda name=item, amt=dropcount: self.current_room.spawn_item(
                            name, amt
                        )
                    )
                cprint(
                    "{} dropped {} x {}!".format(self.name, drop.name, dropcount),
                    "cyan",
                    attrs=["bold"],
                )
                self._record_combat_drop(drop.name, dropcount, "loot", landed)
                return landed  # only one item in the loot table will drop
        return []
