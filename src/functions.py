import textwrap
import os
import inspect
import re
import random
import pickle
import datetime
import importlib
import time
import pkgutil

from typing import Any
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # only for type hints; avoids runtime circular imports
    from src.items import Item

from neotermcolor import colored, cprint
from os import listdir
from os.path import isfile, join

"""
This module contains general functions to use throughout the game
"""


def print_slow(text, speed="slow"):
    speeds = {"slow": 1, "medium": 2, "fast": 4}
    printspeed = speeds.get(speed, 1) if not isinstance(speed, int) else speed
    rate = 0.1 / printspeed
    wrap = textwrap.fill(text, 80)
    for letter in wrap:
        print(letter, end='', flush=True)
        time.sleep(rate)


def execute_arbitrary_method(method, player):
    """
    Checks the number of parameters required by a method and executes accordingly
    """
    number_of_params = len(inspect.signature(method).parameters)
    if number_of_params == 0:
        method()
    else:
        method(player)


def confirm(thing, action, player, args_list):
    """Prompt the user to confirm an action on `thing`.

    Parameters:
      thing: target object to act upon
      action: string name of the method/interaction to call on `thing` if confirmed
      player: the player instance (passed to the action when executed)
      args_list: full argument list from the original command (used for display)
    """
    # Use the first token of the original args for a friendly prompt if available
    prompt_verb = args_list[0].title() if args_list else ''
    check = input(colored(f"{prompt_verb} {thing.name}? (y/n)", "cyan"))
    if check.lower() in ("y", "yes"):
        execute_arbitrary_method(thing.__getattribute__(action), player)
        return True
    return False


def enumerate_for_interactions(subjects, player, args_list, action_input):
    """Resolve and execute an interaction on one of several candidate subjects.

    This function unifies the logic for handling both single-verb inputs (e.g. "look")
    and verb + target inputs (e.g. "take apple"). It searches a provided iterable of
    candidate objects (items, NPCs, room objects, inventory objects) for those that
    expose the requested interaction.

    Resolution rules:
      1. Parse the action verb from args_list[0]. If additional tokens exist, treat
         args_list[1] as a target fragment used to filter candidates by fuzzy
         substring matching over object name / description style fields.
      2. A subject is considered to support the action if:
           - it declares an 'interactions' list containing the verb (case-insensitive), OR
           - it has an attribute/method named after the verb (fallback), OR
           - (single-token mode only) the raw action input exactly matches one of its 'keywords'.
      3. If zero candidates are found -> return False (not handled).
         If exactly one candidate -> execute its method immediately.
         If multiple candidates -> display a menu (similar to RoomTakeInterface) allowing
         the player to choose one; selection 0 or 'x' cancels.

    Parameters
    ----------
    subjects : iterable
        Collection of game entities to inspect.
    player : object
        Player instance passed to interaction methods when needed.
    args_list : list[str]
        Tokenized user command (first element: verb; second (optional): target fragment).
    action_input : str
        The raw (possibly original-cased) action input used for keyword matches in single-token mode.

    Returns
    -------
    bool
        True if an interaction was executed; False otherwise or if user cancelled.
    """
    if not args_list:
        return False

    action_attr = args_list[0]
    verb = action_attr.lower()
    multi_token = len(args_list) > 1
    target_fragment = args_list[1].lower() if multi_token and isinstance(args_list[1], str) else None
    raw_input_lower = action_input.lower() if isinstance(action_input, str) else ''

    candidates = []  # list of (thing, resolved_method_name)

    for thing in subjects:
        if getattr(thing, 'hidden', False):
            continue
        # Exclude Gold
        if verb == 'drop' and getattr(thing, 'name', '').lower() == 'gold':
            continue

        # Build search corpus once for potential target filtering
        search_corpus = ' '.join(filter(None, [
            getattr(thing, 'name', ''),
            getattr(thing, 'idle_message', ''),
            getattr(thing, 'description', ''),
            getattr(thing, 'announce', '')
        ])).lower()

        if multi_token:
            # Require fuzzy target match
            if target_fragment and target_fragment not in search_corpus:
                continue
            # Action support: interactions OR method OR (keywords only used in single-token mode)
            supported = False
            inters = getattr(thing, 'interactions', None)
            if inters and any(isinstance(i, str) and i.lower() == verb for i in inters):
                supported = True
            elif hasattr(thing, action_attr):
                supported = True
            if supported:
                candidates.append((thing, action_attr))
        else:
            # Single-token mode: allow keyword exact matches or interactions or attr fallback
            kws = getattr(thing, 'keywords', None)
            if kws and any(isinstance(k, str) and raw_input_lower == k.lower() for k in kws):
                candidates.append((thing, action_attr))
                continue
            inters = getattr(thing, 'interactions', None)
            if inters and any(isinstance(i, str) and raw_input_lower == i.lower() for i in inters):
                candidates.append((thing, action_attr))
                continue
            # Fallback: method presence (only if no keywords/interactions matched)
            if hasattr(thing, action_attr):
                candidates.append((thing, action_attr))

    if not candidates:
        return False

    # Single candidate: execute immediately
    if len(candidates) == 1:
        thing, method_name = candidates[0]
        execute_arbitrary_method(getattr(thing, method_name), player)
        return True

    # Multiple candidates: show selection menu
    print(colored(f"Multiple targets match '{verb}' command:" + (f" '{target_fragment}'" if target_fragment else ''), 'cyan'))
    for idx, (thing, _m) in enumerate(candidates, start=1):
        display_name = getattr(thing, 'name', str(thing))
        print(colored(f"{idx}: {display_name}", 'yellow'))
    print(colored("X: Cancel", 'red'))

    selection = input(colored("Selection: ", 'cyan')).strip().lower()
    if selection in ('0', 'x', 'X', 'cancel'):
        print(colored("Jean decides against it for now.", 'yellow'))
        return False
    if selection.isdigit():
        choice = int(selection)
        if 1 <= choice <= len(candidates):
            thing, method_name = candidates[choice - 1]
            execute_arbitrary_method(getattr(thing, method_name), player)
            return True

    print(colored("Invalid selection. Nothing happens.", 'red'))
    return False


def screen_clear():
    try:
        # Prefer native terminal clear; fallback to printing newlines
        if os.name == "nt":
            os.system("cls")
        else:
            os.system("clear")
    except Exception:
        print("\n" * 100)


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
        print("\n".join(lines))
        print()


def print_npcs_in_room(room):
    _print_visible_lines(getattr(room, "npcs_here", []), lambda o: f"{getattr(o, 'name', '')}{getattr(o, 'idle_message', '')}")


def print_items_in_room(room):
    _print_visible_lines(getattr(room, "items_here", []), lambda o: getattr(o, "announce", ""))


def print_objects_in_room(room):
    _print_visible_lines(getattr(room, "objects_here", []), lambda o: getattr(o, "idle_message", ""))


def check_for_combat(player):  # returns a list of angry enemies who are ready to fight
    enemy_combat_list = []
    npcs = getattr(getattr(player, 'current_room', None), 'npcs_here', []) or []
    if not npcs:
        return enemy_combat_list

    # Safe finesse roll
    try:
        base = float(getattr(player, 'finesse', 0))
        low = int(base * 0.6)
        high = int(base * 1.4)
        if low > high:
            low, high = high, low
        finesse_check = random.randint(low, high)
    except Exception:
        finesse_check = random.randint(0, 10)

    # Quiet Movement bonus
    if any(getattr(m, 'name', '') == "Quiet Movement" for m in getattr(player, 'known_moves', [])):
        finesse_check = int(finesse_check * 1.2)

    for e in npcs:
        if getattr(e, 'friend', False):
            continue
        if not getattr(e, 'aggro', False):
            continue
        awareness = getattr(e, 'awareness', float('inf'))
        if finesse_check <= awareness:
            print(f"{getattr(e, 'name', '')} {getattr(e, 'alert_message', '')}")
            enemy_combat_list.append(e)
            e.in_combat = True
            # Nearby aggro allies join
            for aggro_enemy in npcs:
                if aggro_enemy is e:
                    continue
                if getattr(aggro_enemy, 'aggro', False) and not getattr(aggro_enemy, 'friend', False):
                    print(f"{getattr(aggro_enemy, 'name', '')}{getattr(aggro_enemy, 'alert_message', '')}")
                    enemy_combat_list.append(aggro_enemy)
                    aggro_enemy.in_combat = True
            break  # stop scanning after alarm is raised
    return enemy_combat_list


def refresh_stat_bonuses(target):  # searches all items and states for stat bonuses, then applies them
    """Refresh dynamic stat bonuses on a target (player or NPC).

    Behavior (preserved):
      1. All primary stats + resistances are reset to base via reset_stats.
      2. Equipped items (those with isequipped True) and active states that expose at least
         one recognized bonus attribute are collected.
      3. Supported bonus attributes:
           add_str, add_fin, add_maxhp, add_maxfatigue, add_speed, add_endurance,
           add_charisma, add_intelligence, add_faith, add_weight_tolerance,
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
        "add_resistance": "_resistance_dict",          # sentinel: dict merge
        "add_status_resistance": "_status_resistance_dict"  # sentinel: dict merge
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

    # Apply bonuses
    for adder in adder_group:
        # Precompute which bonus attributes this adder actually supplies
        present = [b for b in bonuses_map if hasattr(adder, b)]
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
            elif target_field == "_status_resistance_dict" and isinstance(bonus_value, dict):
                for k in status_resistance_keys:
                    if k in bonus_value:
                        try:
                            target.status_resistance[k] += float(bonus_value[k])
                        except Exception:
                            continue
            else:
                try:
                    setattr(target, target_field, get_attr(target, target_field) + bonus_value)
                except Exception:
                    # Fail-safe: skip malformed bonus
                    continue

    # Clamp negative status resistances to 0
    for k, v in list(target.status_resistance.items()):
        if v < 0:
            target.status_resistance[k] = 0

    # Jean-specific post-processing
    if get_attr(target, "name", None) == "Jean":
        # weight_tolerance recalculation is deterministic (assignment, not +=)
        if hasattr(target, "weight_tolerance_base") and hasattr(target, "strength") and hasattr(target, "endurance"):
            target.weight_tolerance = target.weight_tolerance_base + round((target.strength + target.endurance) / 2, 2)
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
                    target.maxfatigue += (target.maxfatigue / 4)
                elif check_weight < 0:
                    # Overweight penalty
                    penalty = (-check_weight) * 10
                    target.maxfatigue -= penalty
                    if target.maxfatigue < 0:
                        target.maxfatigue = 0
            except Exception:
                pass


def check_parry(target):
    states = getattr(target, "states", []) or []
    for s in states:
        name = s if isinstance(s, str) else getattr(s, "name", None)
        if isinstance(name, str) and name.lower() == "parrying":
            return True
    return False


def spawn_npc(npc_name, tile):
    tile.npcs_here.append(npc_name)


def spawn_item(item_name, tile):
    tile.items_here.append(item_name)


def refresh_moves(player):
    """Populate player's known_moves with default move instances (tolerant to import/instantiate errors)."""
    try:
        from src import moves as _moves
    except Exception:
        _moves = None

    # Ensure known_moves exists and start fresh
    if not hasattr(player, "known_moves") or player.known_moves is None:
        player.known_moves = []
    else:
        player.known_moves.clear()

    default_moves = ("Rest", "PlayerAttack")
    for move_name in default_moves:
        if _moves is None or not hasattr(_moves, move_name):
            continue
        move_class = getattr(_moves, move_name)
        try:
            move_instance = move_class()
        except Exception:
            # Skip moves that fail to instantiate
            continue
        player.known_moves.append(move_instance)
    # add other moves based on logic and stuff


def is_input_integer(input_to_check):  # useful for checking to see if the player's input can be converted to int
    try:
        int(input_to_check)
        return True
    except ValueError:
        return False


def reset_stats(target):  # resets all stats to base level
    # Map target attrs to their corresponding base attrs to avoid repetitive code
    stat_pairs = (
        ("strength", "strength_base"),
        ("finesse", "finesse_base"),
        ("maxhp", "maxhp_base"),
        ("maxfatigue", "maxfatigue_base"),
        ("speed", "speed_base"),
        ("endurance", "endurance_base"),
        ("charisma", "charisma_base"),
        ("intelligence", "intelligence_base"),
        ("faith", "faith_base"),
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
            target.resistance.update({k: v for k, v in getattr(target, "resistance_base", {}).items()})
    except Exception:
        pass

    try:
        if hasattr(target, "status_resistance") and hasattr(target, "status_resistance_base"):
            target.status_resistance.clear()
            target.status_resistance.update({k: v for k, v in getattr(target, "status_resistance_base", {}).items()})
    except Exception:
        pass

    # Preserve compatibility for weight_tolerance if present
    if hasattr(target, "weight_tolerance") and hasattr(target, "weight_tolerance_base"):
        try:
            target.weight_tolerance = getattr(target, "weight_tolerance_base")
        except Exception:
            pass


def load_select():
    if saves_list():
        while True:
            print("Select the file you wish to load.")
            for i, file in enumerate(saves_list()):
                timestamp = str(datetime.datetime.fromtimestamp(os.path.getmtime(file)))
                timestamp = timestamp[:-7]
                try:
                    check_playtime = load(file)
                    playtime = str(datetime.timedelta(seconds=getattr(check_playtime, 'time_elapsed', 0)))
                    playtime = playtime[:-7]
                    descriptor = f"play time: {playtime}" if playtime else "play time: 0"
                except Exception as e:
                    descriptor = colored('UNREADABLE (legacy/incompatible)', 'red')
                print(f'{i}: {file} (last modified {timestamp}) ({descriptor})')
            print('x: Cancel')
            choice = input("Selection: ")
            if choice == 'x':
                print('Load operation cancelled.')
                return SyntaxError
            if is_input_integer(choice):
                try:
                    candidate = saves_list()[int(choice)]
                    return load(candidate)
                except TypeError:
                    cprint("Invalid selection.", "red")
                except Exception as e:
                    cprint(f"Unable to load selected file: {e}", 'red')
    else:
        cprint("No save files detected.", "red")
        return SyntaxError


class _MissingLegacyPlaceholder:
    """Generic benign placeholder for legacy objects whose classes can't be imported anymore."""
    def __init__(self, module_name:str, class_name:str):
        self._legacy_module = module_name
        self._legacy_class = class_name
    def __repr__(self):
        return f"<LegacyMissing {self._legacy_module}.{self._legacy_class}>"
    # Provide no-op methods sometimes expected
    def process(self, *a, **k):
        return None
    def check_conditions(self, *a, **k):
        return None

class SafeUnpickler(pickle.Unpickler):
    """Unpickler resilient to missing legacy modules/classes.
    Strategy:
      1. Try normal resolution.
      2. If fails, attempt module path rewrites (e.g., add 'src.' prefix).
      3. If still fails, create a benign placeholder class.
    """
    MODULE_REWRITES = [
        (lambda m: m.startswith('story.'), lambda m: 'src.' + m),
        (lambda m: m.startswith('tilesets.'), lambda m: 'src.' + m),
    ]
    def find_class(self, module, name):
        try:
            return super().find_class(module, name)
        except (ModuleNotFoundError, AttributeError):
            pass
        # Attempt rewrites
        for predicate, rewrite in self.MODULE_REWRITES:
            try:
                if predicate(module):
                    new_mod = rewrite(module)
                    try:
                        mod = importlib.import_module(new_mod)
                        if hasattr(mod, name):
                            return getattr(mod, name)
                    except Exception:
                        pass
            except Exception:
                pass
        # As a last resort, synthesize a dummy module + class placeholder
        placeholder_class_name = f"LegacyMissing_{module.replace('.', '_')}_{name}"
        # Create a dynamic class so isinstance checks won't explode (but still benign)
        placeholder_cls = type(placeholder_class_name, (object,), {
            '__doc__': f'Placeholder for missing legacy class {module}.{name}',
            '__init__': lambda self, *a, **k: None,
            '__repr__': lambda self: f"<LegacyMissing {module}.{name}>",
            # Commonly accessed attributes in game logic
            'name': name,
            'hidden': True,
            'announce': '',
            'idle_message': '',
            'description': '',
            'keywords': [],
            'interactions': [],
            # Benign no-op methods
            'process': lambda self, *a, **k: None,
            'check_conditions': lambda self, *a, **k: None,
        })
        return placeholder_cls

# ----------------- Legacy / Integrity Helpers -----------------

_PLAYER_REQUIRED_DEFAULTS = {
    'inventory': list,
    'known_moves': list,
    'states': list,
    'combat_list': list,
    'combat_list_allies': list,
    'combat_events': list,
    'preferences': lambda: {"arrow": "Wooden Arrow"},
    'resistance': dict,
    'status_resistance': dict,
}

def _patch_player_integrity(obj: Any):
    """Patch legacy Player instances to ensure required attributes exist.
    This is deliberately conservative: only add missing attrs / lists.
    """
    try:
        from player import Player  # local import to avoid circulars at module load
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
    if not getattr(obj, 'fists', None):
        try:
            import items as _items
            obj.fists = _items.Fists()
        except Exception:
            pass
    if not getattr(obj, 'eq_weapon', None):
        obj.eq_weapon = getattr(obj, 'fists', None)
    # Sanity on resistance/status_resistance contents
    base_res_keys = {"fire","ice","shock","earth","light","dark","piercing","slashing","crushing","spiritual","pure"}
    if hasattr(obj, 'resistance'):
        for k in base_res_keys:
            obj.resistance.setdefault(k, 1.0)
    base_status_keys = {"generic","stun","poison","enflamed","sloth","apathy","blind","incoherence","mute","enraged","enchanted","ethereal","berserk","slow","sleep","confusion","cursed","stop","stone","frozen","doom","death"}
    if hasattr(obj, 'status_resistance'):
        for k in base_status_keys:
            obj.status_resistance.setdefault(k, 1.0)
    return obj


def _safe_pickle_load(fp):
    try:
        data = SafeUnpickler(fp).load()
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
        with open(filename, 'rb') as f:
            data = _safe_pickle_load(f)
            if data is None:
                raise RuntimeError(f"Failed to load save: {filename}")
            return data
    except FileNotFoundError:
        raise
    except Exception as e:
        # Re-raise with context so caller can decide to skip
        raise RuntimeError(f"Corrupt or incompatible save '{filename}': {e}") from e


def save_select(player):
    save_complete = False
    while not save_complete:
        print("Save as a new file or overwrite existing?\nn: New file\no: Overwrite existing\nx: Cancel")
        choice = input("Selection: ")
        if choice == 'n':
            while True:
                filename = input("Enter a name for your save: ")
                try:
                    save(player, filename)
                    save_complete = True
                    break
                except SyntaxError:
                    cprint("Invalid file name. Please enter a valid file name (no spaces or special characters): ")
        elif choice == 'o':
            overwrite_complete = False
            while not overwrite_complete:
                print("Select a file to overwrite.\n")
                for i, filename in enumerate(saves_list()):
                    if 'autosave' not in filename:
                        timestamp = str(datetime.datetime.fromtimestamp(os.path.getmtime(filename)))
                        timestamp = timestamp[:-7]
                        print('{}: {} (last modified {})'.format(i, filename, timestamp))
                print('x: Cancel')
                choice = input("Selection: ")
                if is_input_integer(choice):
                    for i, filename in enumerate(saves_list()):
                        if int(choice) == i:
                            save(player, filename)
                            overwrite_complete = True
                            save_complete = True
                            break
                elif choice == 'x':
                    overwrite_complete = True
        elif choice == 'x':
            save_complete = True


def save(player, filename):  # player is the player object
    if filename.endswith('.sav'):
        with open('{}'.format(filename), 'wb') as f:
            pickle.dump(player, f, pickle.HIGHEST_PROTOCOL)
    else:
        with open('{}.sav'.format(filename), 'wb') as f:
            pickle.dump(player, f, pickle.HIGHEST_PROTOCOL)


def saves_list():
    path = os.path.dirname(os.path.abspath(__file__))
    savefiles = [f for f in listdir(path) if isfile(join(path, f)) and f.endswith('.sav')]
    savefiles.sort(key=lambda x: os.stat(os.path.join(path, x)).st_mtime, reverse=True)
    return savefiles


def autosave(player):
    # Rotate existing autosaves (skip corrupt ones silently)
    for i in range(4, 0, -1):
        old_name = f'autosave{i}.sav'
        new_name = f'autosave{i+1}.sav'
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
    save(player, 'autosave1.sav')


def findnth(haystack, needle, n):
    parts = haystack.split(needle, n+1)
    if len(parts) <= n+1:
        return -1
    return len(haystack)-len(parts[-1])-len(needle)


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


def seek_class(classname, package='all'):
    """
    Searches through the requested package(s) and returns the matching class object
    :param str classname: the classname of the desired object as a string
    :param str package: optionally provide the desired package to search, leave default to search all packages
    :return object or None:
    """
    packages = ['story', 'tilesets']
    module_paths: set[str] = set()

    def add_modules_for(base_pkg):
        try:
            root_pkg = __import__(base_pkg)
            # Walk the package tree recursively to include nested modules (effects, ch01, etc.)
            for modinfo in pkgutil.walk_packages(root_pkg.__path__, prefix=root_pkg.__name__ + '.'):  # type: ignore
                module_paths.add(modinfo.name)
        except Exception:
            pass

    if package == 'all':
        for package_n in packages:
            add_modules_for(package_n)
            add_modules_for(f"src.{package_n}")
    elif package in packages:
        add_modules_for(package)
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
    input(colored("\n(Press Enter)", "yellow"))


def inflict(state, target, chance=1.0, force=False):
    """
    attempt to inflict a state on a target player or NPC.
    :param state: new instance of the state object to be inflicted
    :param target: target to receive the state
    :param chance: base chance of success; further altered by resistances
    :param force: if true, inflicting will never fail regardless of resistance
    :return: returns the state object that was inflicted/compounded or False if it failed
    """

    def success(victim, status):
        for existing_state in victim.states:
            if isinstance(existing_state, status.__class__):
                if existing_state.compounding:
                    # if the state already exists on the target and it's a compounding state, execute the compounding
                    # effect and return the existing state
                    existing_state.compound(victim)
                    return existing_state
                else:
                    # the state already exists and is non-compounding, so replace it with the new state
                    victim.states.remove(existing_state)
                    victim.states.append(status)
                    status.on_application()
                    return status
        # the state does not yet exist on the target
        target.states.append(status)
        status.on_application(target)
        return status

    if not force:
        chance *= (1 - target.status_resistance[state.statustype])
        if chance <= 0:
            return False  # target is immune
        else:
            roll = random.uniform(0, 1)
            if chance >= roll:  # success! Status gets inflicted!
                success(target, state)
            else:
                return False  # state failed to apply
    else:
        success(target, state)


def add_random_enchantments(item: 'Item', count: int) -> None:
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
    from src import enchant_tables as _enchant_tables
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
                requirements_ok = req() if callable(req) else (bool(req) if req is not None else True)
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
            print("Jean made " + colored(setting, "magenta") + " his preference.")
        else:
            player.preferences[preftype] = "None"
            print("Jean stopped preferring a specific {}.".format(preftype))
    else:
        player.preferences[preftype] = setting
        print("Jean made " + colored(setting, "purple") + " his preference.")


def escape_ansi(line):
    ansi_escape = re.compile(r'(?:\x1B[@-_]|[\x80-\x9F])[0-?]*[ -/]*[@-~]')
    return ansi_escape.sub('', line)


def list_module_names(package_name):
    package = __import__(package_name)
    module_names = []

    for importer, modname, ispkg in pkgutil.iter_modules(package.__path__):
        module_names.append(modname)

    return module_names


def clean_string(input_string):
    # Remove non-printable characters
    cleaned_string = re.sub(r'[\[\d]+m|[^\x20-\x7E]', '', input_string)
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
        params_list = [p for p in sig.parameters.values() if p.name != 'self']
        kwargs = {}
        # Map by parameter names if present
        names = [p.name for p in params_list]
        if {'player','tile'}.issubset(names):
            kwargs['player'] = player
            kwargs['tile'] = tile
            if 'params' in names:
                kwargs['params'] = params
            if 'repeat' in names:
                kwargs['repeat'] = repeat
            if 'name' in names and name is not None:
                kwargs['name'] = name
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


def stack_inv_items(target):
    """
    Collapse stackable items in `target.inventory` by summing their `count`
    and removing duplicate instances.

    Behavior:
      - Operates only if `target.inventory` exists and is a list with 2+ items.
      - Only items with a `count` attribute are considered stackable.
      - Items are grouped by a best-effort stacking key:
          1. If an item provides `stack_key()` or `stackable_key()`, that is used.
          2. Otherwise a tuple of (class, name, description) is used.
      - For each group, the first instance is kept as the master; other instances'
        counts are added to the master and the duplicates are removed from the
        inventory.
      - If an item has `stack_grammar()`, it is called on the master after stacking.
    """
    if not hasattr(target, "inventory"):
        return
    inventory = target.inventory
    if not isinstance(inventory, list):
        return
    if len(inventory) < 2:
        return

    # Build groups of stackable items without modifying the inventory in-place
    groups: dict[tuple, list] = {}
    for item in list(inventory):
        if not hasattr(item, "count"):
            # leave non-stackable items alone
            continue
        # Prefer explicit stack key methods if provided by the item
        if hasattr(item, "stack_key"):
            # Invoke if callable (previously the bound method object itself was used as part of the key
            # which caused each instance to appear unique and blocked stacking). Falling back to the
            # attribute value preserves legacy behavior for non-callable attributes.
            key_component = item.stack_key if not callable(getattr(item, "stack_key")) else item.stack_key()
            key = (item.__class__, "stack_key", key_component)
        else:
            # Fallback: use class + name + description where available
            key = (item.__class__, getattr(item, "name", None), getattr(item, "description", None))
        if hasattr(item, "merchandise") and item.merchandise is True:
            # Differentiate merchandise items by their merchant status
            key += ("merchandise",)
        groups.setdefault(key, []).append(item)

    # Merge each group into a single master item and remove duplicates
    for items in groups.values():
        master = items[0]
        # Sum counts from duplicates into master
        for dup in items[1:]:
            if dup is master:
                continue
            try:
                master.count += getattr(dup, "count", 0)
            except Exception:
                # Fail-safe: skip problematic duplicates
                continue
        # Allow item to update any derived text/grammar after counts changed
        if hasattr(master, "stack_grammar") and callable(getattr(master, "stack_grammar")):
            try:
                master.stack_grammar()
            except Exception:
                pass
        # Remove duplicate instances from the inventory
        for dup in items[1:]:
            try:
                if dup in inventory:
                    inventory.remove(dup)
            except ValueError:
                pass

