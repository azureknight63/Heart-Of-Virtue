import math
import os
import inspect
import re
import random
import importlib
import pkgutil

from typing import Any
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # only for type hints; avoids runtime circular imports
    from src.items import Item
    from src.player import Player

from src.narration import colored, cprint, narrate
from os import listdir
from os.path import isfile, join

"""
This module contains general functions to use throughout the game
"""

# Primary stats whose *_base counterpart drives reset_stats() and which must
# never go negative after bonus summation in refresh_stat_bonuses(). Pools
# (maxhp, maxfatigue) are intentionally excluded -- they aren't floor-clamped.
PRIMARY_STAT_FIELDS = (
    "strength",
    "finesse",
    "speed",
    "endurance",
    "charisma",
    "intelligence",
    "faith",
)


def print_slow(text, speed="slow"):
    """Emit narrative text as a single message.

    The terminal typewriter effect has been retired with terminal mode; the web
    frontend is responsible for any progressive-reveal animation. ``speed`` is
    accepted for signature compatibility and ignored.
    """
    narrate(text)


def execute_arbitrary_method(method, player):
    """
    Checks the number of parameters required by a method and executes accordingly
    """
    number_of_params = len(inspect.signature(method).parameters)
    if number_of_params == 0:
        method()
    else:
        method(player)


def screen_clear():
    """No-op retained for compatibility.

    Clearing the terminal is meaningless in the web client, which manages its own
    display surface. Kept so existing callers don't need to change.
    """
    return None


def _print_visible_lines(seq, attr_getter):
    if not seq:
        return
    lines = []
    for obj in seq:
        if not getattr(obj, "hidden", False):
            try:
                lines.append(attr_getter(obj))
            except Exception:
                lines.append(str(obj))
    if lines:
        narrate("\n".join(lines))
        narrate()


def print_npcs_in_room(room):
    _print_visible_lines(
        getattr(room, "npcs_here", []),
        lambda o: f"{getattr(o, 'name', '')}{getattr(o, 'idle_message', '')}",
    )


def print_items_in_room(room):
    _print_visible_lines(
        getattr(room, "items_here", []), lambda o: getattr(o, "announce", "")
    )


def print_objects_in_room(room):
    _print_visible_lines(
        getattr(room, "objects_here", []),
        lambda o: getattr(o, "idle_message", ""),
    )


def check_for_combat(
    player,
):  # returns a list of angry enemies who are ready to fight
    enemy_combat_list = []
    npcs = getattr(getattr(player, "current_room", None), "npcs_here", []) or []
    if not npcs:
        return enemy_combat_list

    # Safe finesse roll
    try:
        base = float(getattr(player, "finesse", 0))
        low = int(base * 0.6)
        high = int(base * 1.4)
        if low > high:
            low, high = high, low
        finesse_check = random.randint(low, high)
    except Exception:
        finesse_check = random.randint(0, 10)

    # Quiet Movement bonus
    if any(
        getattr(m, "name", "") == "Quiet Movement"
        for m in getattr(player, "known_moves", [])
    ):
        finesse_check = int(finesse_check * 1.2)

    for e in npcs:
        if getattr(e, "friend", False):
            continue
        if not getattr(e, "aggro", False):
            continue
        awareness = getattr(e, "awareness", float("inf"))
        if finesse_check <= awareness:
            # Don't print here - combat adapter will handle alert messages
            enemy_combat_list.append(e)
            e.in_combat = True
            # Nearby aggro allies join
            for aggro_enemy in npcs:
                if aggro_enemy is e:
                    continue
                if getattr(aggro_enemy, "aggro", False) and not getattr(
                    aggro_enemy, "friend", False
                ):
                    # Don't print here - combat adapter will handle alert messages
                    enemy_combat_list.append(aggro_enemy)
                    aggro_enemy.in_combat = True
            break  # stop scanning after alarm is raised
    return enemy_combat_list


def add_enemies_to_combat(player, new_enemies, announcement: str = None):
    """Add new enemies to an ongoing combat and reinitialize positions.

    This function is designed for mid-combat enemy spawning (e.g., reinforcements,
    ambushes, or event-triggered spawns). It properly integrates new enemies into
    the combat system by:

    1. Adding them to the player's combat_list
    2. Setting up bidirectional combat list references
    3. Reinitializing battlefield positions for ALL combatants
    4. Updating combat_proximity dicts for backward compatibility

    Args:
        player: The Player instance
        new_enemies: List of NPC instances to add to combat

    Example:
        # In an event that spawns reinforcements:
        new_enemies = [tile.spawn_npc("Goblin") for _ in range(3)]
        add_enemies_to_combat(player, new_enemies)
    """
    from src.coordinate_config import CoordinateSystemConfig
    import src.positions as positions

    # Announce the new enemies
    if announcement:
        cprint(announcement, "red", attrs=["bold"])

    # Add enemies to combat list
    for enemy in new_enemies:
        if enemy not in player.combat_list:
            player.combat_list.append(enemy)
            enemy.in_combat = True

            # Provide back-reference for API drop/loot tracking when available
            try:
                enemy.player_ref = player
            except Exception:
                pass

            # Reset move states for newly added enemies
            if hasattr(enemy, "reset_combat_moves"):
                enemy.reset_combat_moves()
            else:
                for move in getattr(enemy, "known_moves", []):
                    move.current_stage = 0
                    move.beats_left = 0

            # Set up combat lists for the enemy
            # Enemies target allies (player's team)
            enemy.combat_list = player.combat_list_allies
            # Enemies are allied with other enemies
            enemy.combat_list_allies = player.combat_list

    # Reinitialize positions for ALL combatants to include new enemies
    try:
        coord_config = CoordinateSystemConfig(player)
        total_combatants = len(player.combat_list_allies) + len(player.combat_list)
        grid_w, grid_h = coord_config.get_dynamic_grid_size(total_combatants)

        # Determine scenario type based on combat composition
        scenario_type = "standard"
        if len(player.combat_list) > 1 and len(player.combat_list_allies) < len(
            player.combat_list
        ):
            scenario_type = "pincer"
        elif len(player.combat_list_allies) == 1 and len(player.combat_list) == 1:
            scenario_type = "boss_arena"

        positions.initialize_combat_positions(
            allies=player.combat_list_allies,
            enemies=player.combat_list,
            scenario_type=scenario_type,
            grid_width=grid_w,
            grid_height=grid_h,
        )
    except Exception:
        # Fallback to legacy proximity system if position initialization fails
        for enemy in new_enemies:
            default_proximity = getattr(enemy, "default_proximity", 20)
            player.combat_proximity[enemy] = int(
                default_proximity * random.uniform(0.75, 1.25)
            )

            if len(player.combat_list_allies) > 0:
                for ally in player.combat_list_allies:
                    distance = int(default_proximity * random.uniform(0.75, 1.25))
                    ally.combat_proximity[enemy] = distance
                    enemy.combat_proximity[ally] = distance

    # Reinitialize API combat adapter state if present (mid-combat reinforcements)
    if hasattr(player, "_combat_adapter"):
        try:
            player._combat_adapter.initialize_combat(new_enemies, reinit=True)
        except Exception:
            pass


def refresh_stat_bonuses(
    target,
):  # searches all items and states for stat bonuses, then applies them
    """Refresh dynamic stat bonuses on a target (player or NPC).

    Behavior (preserved):
      1. All primary stats + resistances are reset to base via reset_stats.
      2. Equipped items (those with isequipped True) and active states that expose at least
         one recognized bonus attribute are collected.
      3. Supported bonus attributes:
           add_str, add_fin, add_maxhp, add_maxfatigue, add_speed, add_endurance,
           add_charisma, add_intelligence, add_faith, add_weight_tolerance, add_protection,
           add_resistance (dict), add_status_resistance (dict)
      4. Resistance & status resistance bonuses merge only for keys present in the target's
         base dictionaries. Status resistance cannot drop below 0.
      5. Jean-specific logic:
           - Recomputes weight_tolerance deterministically from base + (STR+END)/2 (rounded 2dp).
           - Adjusts maxfatigue: +25% if carrying <50% capacity; subtracts 10 * overweight pounds otherwise (floor at 0).
      6. Function is idempotent: repeated calls without changes to inventory/states yield identical results.

    Optimization changes:
      - Single pass to gather items & states (no repeated per-bonus scans while collecting).
      - Pre-compute present bonus attributes per adder to avoid redundant hasattr checks in inner loops.
      - Streamlined resistance merging (loop only actual keys present in adder dict & target dict).
      - Clearer, documented flow for easier maintenance & future extension.
    """
    reset_stats(target)

    # Mapping of bonus attribute -> target attribute (dict entries handled specially)
    bonuses_map = {
        "add_str": "strength",
        "add_fin": "finesse",
        "add_maxhp": "maxhp",
        "add_maxfatigue": "maxfatigue",
        "add_speed": "speed",
        "add_endurance": "endurance",
        "add_charisma": "charisma",
        "add_intelligence": "intelligence",
        "add_faith": "faith",
        "add_weight_tolerance": "weight_tolerance",
        "add_protection": "protection",
        "add_resistance": "_resistance_dict",  # sentinel: dict merge
        "add_status_resistance": "_status_resistance_dict",  # sentinel: dict merge
    }

    # Dynamically mirror current base resistance categories (these can evolve elsewhere)
    resistance_keys = list(target.resistance_base.keys())
    status_resistance_keys = list(target.status_resistance_base.keys())

    # Collect candidate adders (equipped items + states with at least one bonus attr)
    adder_group = []
    get_attr = getattr

    # Equipped items
    inv = get_attr(target, "inventory", [])
    if isinstance(inv, list):
        for item in inv:
            if get_attr(item, "isequipped", False):
                for bonus_attr in bonuses_map.keys():
                    if hasattr(item, bonus_attr):
                        adder_group.append(item)
                        break

    # States
    for state in get_attr(target, "states", []):
        for bonus_attr in bonuses_map.keys():
            if hasattr(state, bonus_attr):
                adder_group.append(state)
                break

    # Apply bonuses. add_protection is deferred to its own pass below: Player's
    # refresh_protection_rating() (called after this loop) recomputes protection
    # from strength/finesse via equipped str_mod/fin_mod, so it must run only
    # after those stats have been fully bonused -- otherwise it would read their
    # pre-bonus values.
    for adder in adder_group:
        # Precompute which bonus attributes this adder actually supplies
        present = [b for b in bonuses_map if b != "add_protection" and hasattr(adder, b)]
        for bonus_attr in present:
            target_field = bonuses_map[bonus_attr]
            bonus_value = get_attr(adder, bonus_attr)
            if target_field == "_resistance_dict" and isinstance(bonus_value, dict):
                # Merge only known resistance keys
                for k in resistance_keys:
                    if k in bonus_value:
                        try:
                            target.resistance[k] += float(bonus_value[k])
                        except Exception:
                            continue
            elif target_field == "_status_resistance_dict" and isinstance(
                bonus_value, dict
            ):
                for k in status_resistance_keys:
                    if k in bonus_value:
                        try:
                            target.status_resistance[k] += float(bonus_value[k])
                        except Exception:
                            continue
            else:
                try:
                    setattr(
                        target,
                        target_field,
                        get_attr(target, target_field) + bonus_value,
                    )
                except Exception:
                    # Fail-safe: skip malformed bonus
                    continue

    # Clamp negative status resistances to 0
    for k, v in list(target.status_resistance.items()):
        if v < 0:
            target.status_resistance[k] = 0

    # Clamp negative primary stats to 0 (stacked debuffs should never invert sign,
    # which would otherwise inflate downstream calculations like hit_chance)
    for stat_field in PRIMARY_STAT_FIELDS:
        stat_value = get_attr(target, stat_field, None)
        if isinstance(stat_value, (int, float)) and stat_value < 0:
            setattr(target, stat_field, 0)

    # Attribute-derived stat bumps (applied after item/state bonuses, before weight adjustments)
    # Strength adds a small amount of max HP: +2 per point above base 10
    try:
        if hasattr(target, "maxhp") and isinstance(getattr(target, "strength", None), (int, float)):
            str_bonus = max(0, target.strength - 10)
            target.maxhp = int(target.maxhp + str_bonus * 2)
    except Exception:
        pass
    # Endurance adds a small amount of max fatigue: +2 per point above base 10
    try:
        if hasattr(target, "maxfatigue") and isinstance(getattr(target, "endurance", None), (int, float)):
            end_bonus = max(0, target.endurance - 10)
            target.maxfatigue = int(target.maxfatigue + end_bonus * 2)
    except Exception:
        pass

    # Faith-based status resistance scaling for mental/debilitating effects
    try:
        faith = getattr(target, 'faith', 0)
        if faith and isinstance(faith, (int, float)) and hasattr(target, 'status_resistance') and hasattr(target, 'status_resistance_base'):
            faith_keys = ("apathy", "hollowed", "fear")
            for key in faith_keys:
                if key in target.status_resistance_base:
                    target.status_resistance[key] = min(1.0, target.status_resistance.get(key, 0) + faith * 0.005)
    except Exception:
        pass

    # Jean-specific post-processing
    if get_attr(target, "name", None) == "Jean":
        # weight_tolerance recalculation is deterministic (assignment, not +=)
        if (
            hasattr(target, "weight_tolerance_base")
            and hasattr(target, "strength")
            and hasattr(target, "endurance")
        ):
            target.weight_tolerance = target.weight_tolerance_base + round(
                (target.strength + target.endurance) / 2, 2
            )
        # Refresh weight & adjust fatigue
        if hasattr(target, "refresh_weight"):
            try:
                target.refresh_weight()
            except Exception:
                pass
        if hasattr(target, "weight_tolerance") and hasattr(target, "weight_current"):
            try:
                check_weight = target.weight_tolerance - target.weight_current
                if check_weight > (target.weight_tolerance / 2):
                    target.maxfatigue = int(math.ceil(target.maxfatigue * 1.25))
                elif check_weight < 0:
                    # Overweight penalty
                    penalty = (-check_weight) * 10
                    target.maxfatigue = int(math.ceil(target.maxfatigue - penalty))
                    if target.maxfatigue < 0:
                        target.maxfatigue = 0
            except Exception:
                pass

    # Recompute Player's gear-based protection now that strength/finesse/endurance
    # bonuses above are fully applied (str_mod/fin_mod on equipped armor read the
    # current, post-bonus values). NPCs already had protection reset to
    # protection_base in reset_stats and need no further recompute here.
    if hasattr(target, "refresh_protection_rating"):
        try:
            target.refresh_protection_rating()
        except Exception:
            pass

    # Sum declarative add_protection bonuses (states/items) on top of the
    # freshly-established base.
    for adder in adder_group:
        if hasattr(adder, "add_protection"):
            try:
                target.protection = target.protection + get_attr(adder, "add_protection")
            except Exception:
                continue

    # Ensure all fatigue values are rounded up to the nearest integer and clamped
    if hasattr(target, "fatigue") and hasattr(target, "maxfatigue"):
        target.maxfatigue = int(math.ceil(target.maxfatigue))
        target.fatigue = int(math.ceil(target.fatigue))
        if target.fatigue > target.maxfatigue:
            target.fatigue = target.maxfatigue


def check_parry(target):
    states = getattr(target, "states", []) or []
    for s in states:
        name = s if isinstance(s, str) else getattr(s, "name", None)
        if isinstance(name, str) and name.lower() == "parrying":
            return True
    return False


def refresh_moves(player):
    """Populate player's known_moves with default move instances (tolerant to import/instantiate errors)."""
    try:
        import src.moves as _moves
    except Exception:
        _moves = None

    # Ensure known_moves exists and start fresh
    if not hasattr(player, "known_moves") or player.known_moves is None:
        player.known_moves = []
    else:
        player.known_moves.clear()

    default_moves = (
        "Check",
        "Wait",
        "Rest",
        "Turn",
        "UseItem",
        "Advance",
        "Withdraw",
        "Attack",
        "Dodge",
        "Parry",
    )
    for move_name in default_moves:
        if _moves is None or not hasattr(_moves, move_name):
            continue
        move_class = getattr(_moves, move_name)
        try:
            move_instance = move_class(player)
        except Exception:
            # Skip moves that fail to instantiate
            continue
        player.known_moves.append(move_instance)
    # add other moves based on logic and stuff


def is_input_integer(
    input_to_check,
):  # useful for checking to see if the player's input can be converted to int
    try:
        int(input_to_check)
        return True
    except ValueError:
        return False


def reset_stats(target):  # resets all stats to base level
    # Map target attrs to their corresponding base attrs to avoid repetitive code
    stat_pairs = tuple((f, f"{f}_base") for f in PRIMARY_STAT_FIELDS) + (
        ("maxhp", "maxhp_base"),
        ("maxfatigue", "maxfatigue_base"),
    )

    for attr, base_attr in stat_pairs:
        if hasattr(target, base_attr):
            try:
                setattr(target, attr, getattr(target, base_attr))
            except Exception:
                # Fail-safe: skip malformed attributes
                pass

    # Reset resistance dictionaries in a safe, efficient way
    try:
        if hasattr(target, "resistance") and hasattr(target, "resistance_base"):
            target.resistance.clear()
            target.resistance.update(
                {k: v for k, v in getattr(target, "resistance_base", {}).items()}
            )
    except Exception:
        pass

    try:
        if hasattr(target, "status_resistance") and hasattr(
            target, "status_resistance_base"
        ):
            target.status_resistance.clear()
            target.status_resistance.update(
                {k: v for k, v in getattr(target, "status_resistance_base", {}).items()}
            )
    except Exception:
        pass

    # Preserve compatibility for weight_tolerance if present
    if hasattr(target, "weight_tolerance") and hasattr(target, "weight_tolerance_base"):
        try:
            target.weight_tolerance = getattr(target, "weight_tolerance_base")
        except Exception:
            pass

    # Reset protection to its true base before add_protection bonuses (from states/
    # items) are summed on top. NPCs fall back to the fixed value captured at
    # construction. Player's protection is recomputed dynamically from gear via
    # refresh_protection_rating(), but that depends on strength/finesse, which
    # haven't been re-bonused yet at this point -- so for Player that recompute
    # happens later in refresh_stat_bonuses, after those bonuses are summed.
    if hasattr(target, "protection_base"):
        try:
            target.protection = target.protection_base
        except Exception:
            pass


class _MissingLegacyPlaceholder:
    """Generic benign placeholder for legacy objects whose classes can't be imported anymore."""

    def __init__(self, module_name: str, class_name: str):
        self._legacy_module = module_name
        self._legacy_class = class_name

    def __repr__(self):
        return f"<LegacyMissing {self._legacy_module}.{self._legacy_class}>"

    # Provide no-op methods sometimes expected
    def process(self, *a, **k):
        return None

    def check_conditions(self, *a, **k):
        return None


# Save deserialization (allow-list, strict mode, size cap, event logging) lives
# in src.secure_pickle. These names are re-exported for backward compatibility:
# universe.py / tiles.py resolve legacy module paths via
# ``functions.canonical_module_name``, and existing tests reference
# ``functions.SafeUnpickler`` / ``functions.LEGACY_BARE_MODULES`` directly.
from src.secure_pickle import (  # noqa: E402,F401  (public re-exports)
    LEGACY_BARE_MODULES,
    canonical_module_name,
    SafeUnpickler,
    RestrictedUnpicklingError,
    SaveTooLargeError,
    SaveIntegrityError,
    safe_pickle_load,
    serialize_for_save,
    DEFAULT_MAX_SAVE_BYTES,
)


# ----------------- Legacy / Integrity Helpers -----------------

_PLAYER_REQUIRED_DEFAULTS = {
    "inventory": list,
    "known_moves": list,
    "states": list,
    "combat_list": list,
    "combat_list_allies": list,
    "combat_events": list,
    "preferences": lambda: {"arrow": "Wooden Arrow"},
    "resistance": dict,
    "status_resistance": dict,
    "combat_log": list,
}


def _patch_player_integrity(obj: Any):
    """Patch legacy Player instances to ensure required attributes exist.
    This is deliberately conservative: only add missing attrs / lists.
    """
    try:
        from src.player import (
            Player,
        )  # local import to avoid circulars at module load
    except Exception:
        return obj
    if not isinstance(obj, Player):
        return obj
    for attr, factory in _PLAYER_REQUIRED_DEFAULTS.items():
        if not hasattr(obj, attr) or getattr(obj, attr) is None:
            try:
                setattr(obj, attr, factory() if callable(factory) else factory())
            except Exception:
                # fallback simple types
                if factory in (list, dict):
                    setattr(obj, attr, factory())
    # Ensure Jean has fists weapon for older saves
    if not getattr(obj, "fists", None):
        try:
            import src.items as _items

            obj.fists = _items.Fists()
        except Exception:
            pass
    if not getattr(obj, "eq_weapon", None):
        obj.eq_weapon = getattr(obj, "fists", None)
    # Sanity on resistance/status_resistance contents
    base_res_keys = {
        "fire",
        "ice",
        "shock",
        "earth",
        "light",
        "dark",
        "piercing",
        "slashing",
        "crushing",
        "spiritual",
        "pure",
    }
    if hasattr(obj, "resistance"):
        for k in base_res_keys:
            obj.resistance.setdefault(k, 1.0)
    base_status_keys = {
        "generic",
        "stun",
        "poison",
        "enflamed",
        "sloth",
        "apathy",
        "blind",
        "incoherence",
        "mute",
        "enraged",
        "enchanted",
        "ethereal",
        "berserk",
        "slow",
        "sleep",
        "confusion",
        "cursed",
        "stop",
        "stone",
        "frozen",
        "doom",
        "death",
    }
    if hasattr(obj, "status_resistance"):
        for k in base_status_keys:
            obj.status_resistance.setdefault(k, 1.0)
    return obj


def _safe_pickle_load(fp):
    try:
        # safe_pickle_load enforces the size cap and applies the allow-list /
        # strict-mode gating from src.secure_pickle before unpickling.
        data = safe_pickle_load(fp)

        # Attempt recursive patch for Player objects nested in simple containers
        def _walk(o):
            if isinstance(o, (list, tuple, set)):
                return type(o)(_walk(i) for i in o)
            if isinstance(o, dict):
                return {k: _walk(v) for k, v in o.items()}
            return _patch_player_integrity(o)

        return _walk(data)
    except Exception:
        return None


def load(filename):
    """Load a saved game file. Returns deserialized object or raises if completely unreadable.
    Legacy compatibility: missing modules/classes replaced with benign placeholders.
    """
    try:
        with open(filename, "rb") as f:
            data = _safe_pickle_load(f)
            if data is None:
                raise RuntimeError(f"Failed to load save: {filename}")
            _maybe_convert_to_v2(data, filename)
            return data
    except FileNotFoundError:
        raise
    except Exception as e:
        # Re-raise with context so caller can decide to skip
        raise RuntimeError(f"Corrupt or incompatible save '{filename}': {e}") from e


def _maybe_convert_to_v2(data, filename):
    """One-shot migration: write a data-only v2 sidecar after a pickle load.

    Feature-flagged via HOV_SAVE_V2 (off by default). Best-effort and never
    fatal to the load -- a Player loaded from the trusted pickle is converted to
    the safe JSON format alongside the original .sav (issue #13, Phase 3).
    """
    try:
        from src.save_format import save_v2_enabled, convert_pickle_save_to_v2
        from src.player import Player

        if not save_v2_enabled() or not isinstance(data, Player):
            return
        sidecar = re.sub(r"\.sav$", "", filename) + ".v2.json"
        convert_pickle_save_to_v2(data, sidecar)
    except Exception:
        # Migration is opportunistic; a failure must not break loading.
        pass


def save(player, filename):  # player is the player object
    # TODO(security, issue #13): saves are written as pickle (now wrapped in an
    # integrity header for tamper detection). Loading a pickle executes
    # arbitrary code by design, so these files are only safe as trusted local
    # artifacts (see SECURITY.md). Phase 3's data-only (JSON) format
    # (src.save_format) is the eventual replacement; pickle becomes legacy-import
    # only. serialize_for_save() prepends the HOVS magic/version/sha256 header;
    # the loader validates it and still accepts old headerless saves.
    if not filename.endswith(".sav"):
        filename = "{}.sav".format(filename)
    with open(filename, "wb") as f:
        f.write(serialize_for_save(player))


def saves_list():
    path = os.path.dirname(os.path.abspath(__file__))
    savefiles = [
        f for f in listdir(path) if isfile(join(path, f)) and f.endswith(".sav")
    ]
    savefiles.sort(key=lambda x: os.stat(os.path.join(path, x)).st_mtime, reverse=True)
    return savefiles


def autosave(player):
    # Rotate existing autosaves (skip corrupt ones silently)
    for i in range(4, 0, -1):
        old_name = f"autosave{i}.sav"
        new_name = f"autosave{i+1}.sav"
        try:
            if old_name in saves_list():
                try:
                    loaded = load(old_name)
                except Exception:
                    continue  # skip corrupt legacy file
                if loaded:
                    try:
                        save(loaded, new_name)
                    except Exception:
                        continue
        except Exception:
            # Skip problematic legacy/corrupt file
            continue
    # Finally write newest autosave1
    save(player, "autosave1.sav")


def findnth(haystack, needle, n):
    parts = haystack.split(needle, n + 1)
    if len(parts) <= n + 1:
        return -1
    return len(haystack) - len(parts[-1]) - len(needle)


def checkrange(user):
    """Checks the min & max range constraints for the user; returns a tuple of (min, max)"""
    if user.name == "Jean":
        return user.eq_weapon.range[0], user.eq_weapon.range[1]

    return user.combat_range[0], user.combat_range[1]


def randomize_amount(param):
    param = str(param)
    if "r" in param:
        ramt = param[1:]
        ramt = ramt.split("-")
        rmin = int(ramt[0])
        rmax = int(ramt[1])
        return random.randint(rmin, rmax)
    else:
        return int(param)


def seek_class(classname, package="all", allow_other_modules=True):
    """
    Searches through the requested package(s) and returns the matching class object
    :param str classname: the classname of the desired object as a string
    :param str package: optionally provide the desired package to search, leave default to search all packages
    :param bool allow_other_modules: when False, restricts the search strictly to the named package.
        The default (True) uses __import__ which resolves dotted names to the top-level package,
        so "src.tilesets" walks all of src/; set to False when callers must avoid class-name collisions
        with unrelated modules in the same root package.
    :return object or None:
    """
    packages = ["story", "tilesets"]
    module_paths: set[str] = set()

    def add_modules_for(base_pkg):
        try:
            # importlib returns the exact subpackage; __import__ returns only the top-level package
            root_pkg = __import__(base_pkg) if allow_other_modules else importlib.import_module(base_pkg)
            # Walk the package tree recursively to include nested modules (effects, ch01, etc.)
            for modinfo in pkgutil.walk_packages(root_pkg.__path__, prefix=root_pkg.__name__ + "."):  # type: ignore
                module_paths.add(modinfo.name)
        except Exception:
            pass

    if package == "all":
        for package_n in packages:
            add_modules_for(f"src.{package_n}")
    elif package in packages:
        add_modules_for(f"src.{package}")
    else:
        raise ValueError(f"Cannot find class '{classname}' after searching '{package}'")

    for module_path in sorted(module_paths):
        try:
            module = importlib.import_module(module_path)
            if hasattr(module, classname):
                return getattr(module, classname)
        except (AttributeError, ImportError):
            continue
    raise ValueError(f"Cannot find class '{classname}' after searching '{package}'")


def await_input():
    """No-op retained for compatibility.

    There is no blocking "press Enter" pause in the web client; pacing between
    narrative beats is handled by the frontend.
    """
    return None


def inflict(state, target, chance=1.0, force=False):
    """
    Attempt to inflict a state on a target player or NPC.

    Args:
        state: A new instance of a State (or subclass) to be inflicted.
        target: The entity that may receive the state (must have `states` and `status_resistance`).
        chance (float): Base chance of success; modified by target resistance. (1.0 = 100%).
        force (bool): If True, bypasses resistance & chance rolls and always applies/compounds.

    Returns:
        The active state object (either the newly applied instance or the pre-existing compounded one)
        on success, otherwise False when the state fails to apply (e.g., resistance immunity or failed roll).

    Notes:
        Previous implementation sometimes returned None on success and called on_application without the
        target param in one branch. This version standardizes behavior, improves clarity & micro-performance,
        and guards against missing resistance keys.
    """
    # Fast-fail path unless forcing
    if not force:
        resistance = target.status_resistance.get(getattr(state, "statustype", ""), 0.0)
        effective_chance = chance * (1 - resistance)
        if effective_chance <= 0:
            return False  # Immune
        if effective_chance < 1.0:
            # Only roll RNG if we aren't guaranteed success
            if random.random() > effective_chance:
                return False  # Failed application
    # At this point we are applying / compounding
    states_list = target.states
    new_cls = state.__class__
    for idx, existing in enumerate(states_list):
        if isinstance(existing, new_cls):
            # Existing matching state found
            if getattr(existing, "compounding", False) and hasattr(
                existing, "compound"
            ):
                existing.compound(target)
                return existing
            # Replace in-place (cheaper & preserves ordering index)
            states_list[idx] = state
            # Ensure on_application always receives target
            if hasattr(state, "on_application"):
                try:
                    state.on_application(target)
                except TypeError:
                    # Backwards compatibility for states with signature ()
                    state.on_application()  # type: ignore
            return state
    # No existing matching state; append
    states_list.append(state)
    if hasattr(state, "on_application"):
        try:
            state.on_application(target)
        except TypeError:
            state.on_application()  # type: ignore
    return state


def add_random_enchantments(item: "Item", count: int) -> None:
    """
    Add up to `count` random enchantments to `item`.

    The function:
      - Caches enchantment classes from `enchant_tables` by their `tier` attribute.
      - Performs `count` enchantment rolls, choosing between prefix (0) and suffix (1)
        groups and incrementing that group's tier each time it is selected.
      - Instantiates candidate enchantments for the computed tier and filters them
        by their `requirements()` and `rarity` attributes.
      - Applies the chosen enchantments by calling `modify()` and merging any
        `equip_states` into `item.equip_states`.

    Args:
        item: Target item object that enchantment classes accept as their constructor arg.
        count: Number of enchantment rolls to attempt (int-like).

    Notes:
        This function is intentionally tolerant of instantiation/modify errors and
        will skip failing enchantments rather than raise.
    """
    ench_pool = int(count)
    enchantment_level: list[int] = [0, 0]
    enchantments: list[Any] = [None, None]

    # Local import (deferred) to reduce initial import cost & circular risks
    import src.enchant_tables as _enchant_tables

    # Cache enchantment classes by tier to avoid repeated reflection/lookup
    class_by_tier: dict[int, list[type]] = {}
    for _, cls in inspect.getmembers(_enchant_tables, inspect.isclass):
        if hasattr(cls, "tier"):
            class_by_tier.setdefault(int(cls.tier), []).append(cls)

    while ench_pool > 0:
        group = random.randrange(2)  # 0 = "Prefix", 1 = "Suffix"
        enchantment_level[group] += 1
        tier = enchantment_level[group]

        rarity = random.randint(0, 100)
        candidates: list[Any] = []
        for cls in class_by_tier.get(tier, ()):
            try:
                ench = cls(item)
                req = getattr(ench, "requirements", None)
                # Normalize the optional `requirements` attribute. It may be:
                # - a callable returning bool
                # - a truthy/falsey value (e.g., bool)
                # - None (meaning 'no requirement' -> allowed)
                requirements_ok = (
                    req() if callable(req) else (bool(req) if req is not None else True)
                )
                if requirements_ok and rarity >= int(getattr(ench, "rarity", 0)):
                    candidates.append(ench)
            except Exception:
                # Skip classes that fail instantiation or checks
                continue

        if not candidates:
            ench_pool -= 1
            continue

        enchant = random.choice(candidates)
        enchantments[group] = enchant
        ench_pool -= 1

    item._enchantment_count = sum(1 for e in enchantments if e)

    for ench in enchantments:
        if ench:
            try:
                ench.modify()
            except Exception:
                pass
            equip_states = getattr(ench, "equip_states", None)
            if equip_states:
                if not hasattr(item, "equip_states") or item.equip_states is None:
                    try:
                        item.equip_states = []
                    except Exception:
                        # If item doesn't support assignment, skip merging
                        continue
                try:
                    item.equip_states += equip_states
                except Exception:
                    # Fallback to extend if necessary
                    try:
                        item.equip_states.extend(equip_states)
                    except Exception:
                        pass


def add_preference(player, preftype, setting):
    if preftype == "arrow":
        if player.preferences[preftype] != setting:
            player.preferences[preftype] = setting
            narrate("Jean made " + colored(setting, color="magenta") + " his preference.")
        else:
            player.preferences[preftype] = "None"
            narrate("Jean stopped preferring a specific {}.".format(preftype))
    else:
        player.preferences[preftype] = setting
        narrate("Jean made " + colored(setting, "purple") + " his preference.")


def escape_ansi(line):
    ansi_escape = re.compile(r"(?:\x1B[@-_]|[\x80-\x9F])[0-?]*[ -/]*[@-~]")
    return ansi_escape.sub("", line)


def list_module_names(package_name):
    package = __import__(package_name)
    module_names = []

    for importer, modname, ispkg in pkgutil.iter_modules(package.__path__):
        module_names.append(modname)

    return module_names


def clean_string(input_string):
    # Remove non-printable characters
    cleaned_string = re.sub(r"[\[\d]+m|[^\x20-\x7E]", "", input_string)
    return cleaned_string


def instantiate_event(event_cls, player, tile, params=None, repeat=False, name=None):
    """Instantiate an Event subclass with backward-compatible argument ordering.
    Supports legacy signature: (player, tile, params, repeat=False, name='X')
    and transitional signature: (player, tile, repeat, params)
    and new unified signature: (player, tile, params=None, repeat=False, name='X').
    Falls back to best-effort positional mapping using parameter names.
    """
    try:
        sig = inspect.signature(event_cls.__init__)
        # Exclude self
        params_list = [p for p in sig.parameters.values() if p.name != "self"]
        kwargs = {}
        # Map by parameter names if present
        names = [p.name for p in params_list]
        if {"player", "tile"}.issubset(names):
            kwargs["player"] = player
            kwargs["tile"] = tile
            if "params" in names:
                kwargs["params"] = params
            if "repeat" in names:
                kwargs["repeat"] = repeat
            if "name" in names and name is not None:
                kwargs["name"] = name
            return event_cls(**kwargs)
        # Fallback positional (legacy variants)
        # Try (player, tile, params, repeat)
        try:
            return event_cls(player, tile, params, repeat)
        except Exception:
            pass
        # Try (player, tile, repeat, params)
        try:
            return event_cls(player, tile, repeat, params)
        except Exception:
            pass
        # Final attempt with minimal args
        return event_cls(player, tile)
    except Exception:
        # As a last resort attempt bare construction
        try:
            return event_cls(player, tile)
        except Exception:
            return event_cls


def stack_items_list(items_list):
    """
    Collapse stackable items in a list by summing their `count`
    and removing duplicate instances.

    Args:
        items_list: A list of items to stack (e.g., tile.items_here, player.inventory)

    Behavior:
      - Operates only if items_list is a list with 2+ items.
      - Only items with a `count` attribute are considered stackable.
      - Items are grouped by a best-effort stacking key:
          1. If an item provides `stack_key()`, that is used.
          2. Otherwise a tuple of (class, name, description) is used.
      - For each group, the first instance is kept as the master; other instances'
        counts are added to the master and the duplicates are removed.
      - If an item has `stack_grammar()`, it is called on the master after stacking.
    """
    if not isinstance(items_list, list) or len(items_list) < 2:
        return

    # Build groups of stackable items without modifying the list in-place
    groups: dict[tuple, list] = {}
    for item in list(items_list):
        if not hasattr(item, "count"):
            # leave non-stackable items alone
            continue
        # Prefer explicit stack key methods if provided by the item
        if hasattr(item, "stack_key"):
            key_component = (
                item.stack_key
                if not callable(getattr(item, "stack_key"))
                else item.stack_key()
            )
            key = (item.__class__, "stack_key", key_component)
        else:
            # Fallback: use class + name + description where available
            key = (
                item.__class__,
                getattr(item, "name", None),
                getattr(item, "description", None),
            )
        if hasattr(item, "merchandise") and item.merchandise is True:
            # Differentiate merchandise items by their merchant status
            key += ("merchandise",)
        groups.setdefault(key, []).append(item)

    # Merge each group into a single master item and remove duplicates
    to_remove = set()
    for items in groups.values():
        master = items[0]
        # Sum counts from duplicates into master
        for dup in items[1:]:
            if dup is master:
                continue
            try:
                master.count += getattr(dup, "count", 0)
                to_remove.add(id(dup))
            except Exception:
                # Fail-safe: skip problematic duplicates
                continue
        # Allow item to update any derived text/grammar after counts changed
        if hasattr(master, "stack_grammar") and callable(
            getattr(master, "stack_grammar")
        ):
            try:
                master.stack_grammar()
            except Exception:
                pass
    # Remove duplicate instances in O(n) instead of O(n²)
    items_list[:] = [item for item in items_list if id(item) not in to_remove]


def stack_inv_items(target):
    """
    Collapse stackable items in `target.inventory` by summing their `count`
    and removing duplicate instances.

    Delegates to stack_items_list() for the actual stacking logic.
    """
    if not hasattr(target, "inventory"):
        return
    stack_items_list(target.inventory)


def learn_all_skills_from_skilltree(player: "Player"):
    """
    Learn all skills from the skill tree for the player.
    This is useful for testing and development when learn_all_skills config is enabled.
    """
    from src.skilltree import Skilltree  # type: ignore

    skilltree = Skilltree(player)
    learned_count = 0

    # Iterate through all skill categories
    for category, skills_dict in skilltree.subtypes.items():
        for skill_move in skills_dict.keys():
            # skill_move is already an instantiated move object from skilltree
            # Check if player already knows a move with this name
            already_known = False
            for known_move in player.known_moves:
                if known_move.name == skill_move.name:
                    already_known = True
                    break

            # Add the skill if not already known
            if not already_known:
                player.known_moves.append(skill_move)
                learned_count += 1

    if learned_count > 0:
        cprint(f"[Config] Learned {learned_count} skills from skill tree.", "cyan")

    return learned_count
