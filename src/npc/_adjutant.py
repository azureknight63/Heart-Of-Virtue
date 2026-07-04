"""
TheAdjutant — combat-testing arena NPC.

Intended for use with the combat testing arena only (not in the production
game world).  Provides debug operations for setting Jean's stats at runtime and
managing the NPC roster on each arena tile.

These operations are exposed to the web client through the test-only debug
blueprint (src/api/routes/debug.py); the legacy terminal input() menu has been
removed.  Every operation is a parametrized method that returns a JSON-safe
result dict — no input()/print().

The _add_combatant logic uses globals().get(cls_name) to dynamically
instantiate NPC classes by name.  All concrete NPC classes are imported into
this module's namespace so that lookup works correctly.
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

from src.narration import narrate


# Arena tile coordinates (map-tile coordinates, not combat-grid).
ARENA_TILES = {
    "Fodder Pit": (1, 0),
    "The Crucible": (2, 0),
    "Ally Courtyard": (0, 1),
    "Status Chamber": (1, 1),
}

# Player attributes editable via the debug interface.
PLAYER_ATTRS = (
    "strength",
    "finesse",
    "speed",
    "endurance",
    "charisma",
    "intelligence",
    "faith",
)

# NPC stats editable via the debug interface.
NPC_EDITABLE_STATS = (
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
)


class TheAdjutant(Friend):
    """Dream-space combat preparation NPC.

    Intended for use in the combat testing arena only. Harmless — cannot enter
    combat. Talking points the player at the debug interface; the actual stat /
    roster operations are parametrized methods driven by the debug blueprint.
    """

    _ARENA_TILES = ARENA_TILES

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
    # Keyword dispatch — flavor only; configuration happens via the debug API.
    # ------------------------------------------------------------------

    def talk(self, player):
        narrate(
            "The Adjutant inclines its head. 'Speak your needs through the "
            "preparation interface, and I will shape you for the trial ahead.'"
        )

    set = talk
    adjust = talk
    configure = talk
    help = talk

    # ------------------------------------------------------------------
    # Player stat operations
    # ------------------------------------------------------------------

    def player_state(self, player):
        """Return Jean's current debug-relevant stats as a dict."""
        return {
            "hp": player.hp,
            "maxhp": player.maxhp,
            "heat": player.heat,
            "fatigue": player.fatigue,
            "maxfatigue": player.maxfatigue,
            "level": player.level,
            "exp": player.exp,
            "exp_to_level": player.exp_to_level,
            "attributes": {attr: getattr(player, attr) for attr in PLAYER_ATTRS},
        }

    def set_hp(self, player, hp, maxhp):
        """Set Jean's HP and max HP (clamped to >= 1; hp <= maxhp)."""
        maxhp = int(maxhp)
        hp = int(hp)
        player.maxhp = max(1, maxhp)
        player.hp = max(1, min(hp, player.maxhp))
        return {"success": True, "hp": player.hp, "maxhp": player.maxhp}

    def set_level(self, player, level, exp):
        """Set Jean's level (1-100) and EXP (>= 0)."""
        player.level = max(1, min(100, int(level)))
        player.exp = max(0, int(exp))
        return {"success": True, "level": player.level, "exp": player.exp}

    def set_attributes(self, player, attrs):
        """Set one or more of Jean's base attributes from a {name: value} dict.

        Accepts either the bare stat name ("speed") or the "_base" suffixed
        form ("speed_base") — both are common conventions elsewhere in the
        API (e.g. level-up allocation), so both must resolve here or callers
        silently no-op (the value is dropped but the call still reports
        success).
        """
        updated = {}
        for attr, value in (attrs or {}).items():
            base_attr = attr[:-5] if attr.endswith("_base") else attr
            if base_attr not in PLAYER_ATTRS:
                continue
            v = int(value)
            setattr(player, base_attr, v)
            setattr(player, base_attr + "_base", v)
            updated[base_attr] = v
        return {"success": True, "updated": updated}

    def set_heat(self, player, heat):
        """Set Jean's combat heat (clamped to 0.5-10.0)."""
        player.heat = max(0.5, min(10.0, float(heat)))
        return {"success": True, "heat": player.heat}

    def restore(self, player):
        """Restore Jean's HP and fatigue to full."""
        player.hp = player.maxhp
        player.fatigue = player.maxfatigue
        return {"success": True, "hp": player.hp, "fatigue": player.fatigue}

    def learn_all_skills(self, player):
        """Learn every skill in the skill tree."""
        functions.learn_all_skills_from_skilltree(player)
        return {
            "success": True,
            "known_moves": len(getattr(player, "known_moves", [])),
        }

    def list_skills(self, player):
        """Return the names of Jean's currently known moves."""
        return [
            getattr(m, "name", repr(m))
            for m in getattr(player, "known_moves", [])
        ]

    # ------------------------------------------------------------------
    # Party ally progression (see npc/_progression.py)
    # ------------------------------------------------------------------

    def _find_party_ally(self, player, name):
        """Return the party ally matching an instance name or class name."""
        for ally in getattr(player, "combat_list_allies", [])[1:]:
            if getattr(ally, "name", None) == name or type(ally).__name__ == name:
                return ally
        return None

    def ally_state(self, player):
        """Return progression state for every party ally (excludes Jean)."""
        allies = []
        for ally in getattr(player, "combat_list_allies", [])[1:]:
            allies.append(
                {
                    "name": getattr(ally, "name", "?"),
                    "class": type(ally).__name__,
                    "progression_enabled": bool(getattr(ally, "growth_profile", None)),
                    "level": int(getattr(ally, "level", 1) or 1),
                    "exp": int(getattr(ally, "exp", 0) or 0),
                    "exp_to_level": int(getattr(ally, "exp_to_level", 0) or 0),
                    "hp": int(getattr(ally, "hp", 0) or 0),
                    "maxhp": int(getattr(ally, "maxhp", 0) or 0),
                    "damage": int(getattr(ally, "damage", 0) or 0),
                    "protection": int(getattr(ally, "protection", 0) or 0),
                    "known_moves": [
                        {
                            "name": getattr(m, "name", "?"),
                            "weight": int(getattr(m, "weight", 1) or 1),
                        }
                        for m in getattr(ally, "known_moves", [])
                    ],
                }
            )
        return {"success": True, "allies": allies}

    def set_ally_progression(self, player, name, level=None, exp=None):
        """Set a party ally's level and/or banked exp.

        Level moves upward only (via sync_level — deterministic growth can't
        be unwound; respawn the ally to reset).  Exp is set verbatim, which
        lets tests prime an ally just below a level threshold.
        """
        ally = self._find_party_ally(player, name)
        if ally is None:
            return {"success": False, "error": f"No party ally named '{name}'."}
        if level is not None:
            if not hasattr(ally, "sync_level"):
                return {
                    "success": False,
                    "error": f"'{name}' does not support progression.",
                }
            ally.sync_level(int(level))
        if exp is not None:
            ally.exp = max(0, int(exp))
        return {
            "success": True,
            "name": getattr(ally, "name", "?"),
            "level": int(getattr(ally, "level", 1) or 1),
            "exp": int(getattr(ally, "exp", 0) or 0),
        }

    # ------------------------------------------------------------------
    # Arena combatant management
    # ------------------------------------------------------------------

    def _get_arena_tile(self, player, coords):
        """Return the MapTile at coords from the current map, or None."""
        tile_map = getattr(player, "map", None)
        if tile_map is None:
            current_room = getattr(self, "current_room", None)
            tile_map = getattr(current_room, "map", None)
        if tile_map is None:
            return None
        return tile_map.get(coords) if hasattr(tile_map, "get") else None

    def _resolve_arena(self, arena):
        """Map an arena name (or coords tuple) to coordinates, or None."""
        if isinstance(arena, (tuple, list)) and len(arena) == 2:
            return tuple(arena)
        return ARENA_TILES.get(arena)

    def arena_rosters(self, player):
        """Return the per-tile NPC roster for every arena tile."""
        rosters = {}
        for name, coords in ARENA_TILES.items():
            tile = self._get_arena_tile(player, coords)
            if tile is None:
                rosters[name] = {"coords": list(coords), "loaded": False, "npcs": []}
                continue
            npcs = getattr(tile, "npcs_here", [])
            rosters[name] = {
                "coords": list(coords),
                "loaded": True,
                "npcs": [
                    {
                        "name": getattr(n, "name", "?"),
                        "friend": bool(getattr(n, "friend", False)),
                    }
                    for n in npcs
                ],
            }
        return rosters

    def add_combatant(self, player, arena, cls_name):
        """Instantiate an NPC class by name and place it on an arena tile."""
        coords = self._resolve_arena(arena)
        if coords is None:
            return {"success": False, "error": f"Unknown arena '{arena}'."}
        tile = self._get_arena_tile(player, coords)
        if tile is None:
            return {"success": False, "error": f"Tile {coords} not loaded."}

        cls = globals().get(cls_name)
        if cls is None or not isinstance(cls, type):
            return {"success": False, "error": f"Class '{cls_name}' not found."}

        try:
            instance = cls()
        except Exception as e:  # pragma: no cover - defensive
            return {"success": False, "error": f"Could not instantiate {cls_name}: {e}"}
        instance.current_room = tile
        getattr(tile, "npcs_here", []).append(instance)
        return {"success": True, "added": cls_name, "arena": arena}

    def remove_combatant(self, player, arena, index):
        """Remove the NPC at `index` from an arena tile's roster."""
        coords = self._resolve_arena(arena)
        if coords is None:
            return {"success": False, "error": f"Unknown arena '{arena}'."}
        tile = self._get_arena_tile(player, coords)
        if tile is None:
            return {"success": False, "error": f"Tile {coords} not loaded."}
        npcs = getattr(tile, "npcs_here", [])
        if not (0 <= int(index) < len(npcs)):
            return {"success": False, "error": "Invalid combatant index."}
        removed = npcs.pop(int(index))
        return {"success": True, "removed": getattr(removed, "name", "?")}

    def clear_room(self, player, arena):
        """Remove every NPC from an arena tile."""
        coords = self._resolve_arena(arena)
        if coords is None:
            return {"success": False, "error": f"Unknown arena '{arena}'."}
        tile = self._get_arena_tile(player, coords)
        if tile is None:
            return {"success": False, "error": f"Tile {coords} not loaded."}
        npcs = getattr(tile, "npcs_here", [])
        count = len(npcs)
        npcs.clear()
        return {"success": True, "cleared": count}

    def set_combatant_stats(self, player, arena, index, stats):
        """Edit stats on an NPC already present in an arena tile."""
        coords = self._resolve_arena(arena)
        if coords is None:
            return {"success": False, "error": f"Unknown arena '{arena}'."}
        tile = self._get_arena_tile(player, coords)
        if tile is None:
            return {"success": False, "error": f"Tile {coords} not loaded."}
        npcs = getattr(tile, "npcs_here", [])
        if not (0 <= int(index) < len(npcs)):
            return {"success": False, "error": "Invalid combatant index."}

        target = npcs[int(index)]
        updated = {}
        for stat, value in (stats or {}).items():
            if stat not in NPC_EDITABLE_STATS:
                continue
            if stat in ("aggro", "friend"):
                bool_val = value if isinstance(value, bool) else (
                    str(value).lower() in ("true", "1", "yes")
                )
                setattr(target, stat, bool_val)
                updated[stat] = bool_val
                continue
            int_val = int(value)
            setattr(target, stat, int_val)
            if stat == "maxhp":
                target.hp = min(getattr(target, "hp", int_val), int_val)
            updated[stat] = int_val
        return {"success": True, "name": getattr(target, "name", "?"), "updated": updated}
