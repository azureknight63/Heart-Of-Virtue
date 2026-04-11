"""
TheAdjutant — combat-testing arena NPC.

Intended for use with the combat testing arena only (not in the production
game world).  Provides a terminal menu for setting Jean's stats at runtime
and managing the NPC roster on each arena tile.

The _add_combatant() method uses globals().get(cls_name) to dynamically
instantiate NPC classes by name.  All concrete NPC classes are imported
into this module's namespace so that lookup works correctly.
"""

import functions  # type: ignore
import moves  # type: ignore

from ._base import NPC, Friend  # noqa: F401
from ._enemies import (  # noqa: F401
    CaveBat,
    ElderSlime,
    GiantSpider,
    KingSlime,
    Lurker,
    RockRumbler,
    Slime,
    StatusDummy,
    Testexp,
)
from ._friends import (  # noqa: F401
    Gorran,
    GronditeConclaveElder,
    GronditeElder,
    GronditePasserby,
    GronditeWorker,
    Mynx,
)
from ._merchants import JamboHealsU, MiloCurioDealer, Merchant  # noqa: F401


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

        # All NPC classes are imported into this module's globals — no extra lookup needed.
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
