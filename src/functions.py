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
import types

from typing import Any

from src import moves
from src import enchant_tables
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


def confirm(thing, action, context):
    player = context[0]
    args_list = context[1]
    check = input(colored("{} {}? (y/n)".format(args_list[0].title(), thing.name), "cyan"))
    if check.lower() == ('y' or 'yes'):
        execute_arbitrary_method(thing.__getattribute__(action), player)
        return True
    else:
        return False


def enumerate_for_interactions(subjects, context):
    player = context[0]
    args_list = context[1]
    action_input = context[2]
    if len(args_list) == 1:
        candidates = []
        for thing in subjects:
            if hasattr(thing, "keywords"):
                if not thing.hidden:
                    for keyword in thing.keywords:
                        if action_input == keyword:
                            candidates.append(thing)
            elif hasattr(thing, "interactions"):
                for interaction in thing.interactions:
                    if action_input == interaction:
                        candidates.append(thing)
        if len(candidates) == 1:  # if there is only one possibility, skip the confirmation step
            execute_arbitrary_method(candidates[0].__getattribute__(args_list[0]), player)
            return True
        elif candidates:  # otherwise, if there is more than one possibility, ask the player to confirm
            for candidate in candidates:
                if confirm(candidate, action_input, context):
                    return True
    elif len(args_list) > 1:
        candidates = []
        for i, thing in enumerate(subjects):
            if hasattr(thing, "keywords"):
                search_item = thing.name.lower() + ' ' + thing.idle_message.lower()
                if args_list[1] in search_item and not thing.hidden:
                    for keyword in thing.keywords:
                        if args_list[0] == keyword:
                            candidates.append(thing)
            elif hasattr(thing, "interactions"):
                search_item = thing.name.lower() + ' ' + thing.description.lower() + ' ' + thing.announce.lower()
                if args_list[1] in search_item and not thing.hidden:
                    for interaction in thing.interactions:
                        if args_list[0] == interaction:
                            candidates.append(thing)
        if len(candidates) == 1:  # if there is only one possibility, skip the confirmation step
            execute_arbitrary_method(candidates[0].__getattribute__(args_list[0]), player)
            return True
        elif candidates:  # otherwise, if there is more than one possibility, ask the player to confirm
            for candidate in candidates:
                if confirm(candidate, args_list[0], context):
                    return True
    return False


def screen_clear():
    print("\n" * 100)


def print_npcs_in_room(room):
    # Does not evaluate combat aggro - that's a different function
    if len(room.npcs_here) > 0:  # Evaluate the room's NPCs.
        for npc in room.npcs_here:
            if not npc.hidden:
                print(npc.name + npc.idle_message)
        print("\n")


def print_items_in_room(room):
    if len(room.items_here) > 0:
        for item in room.items_here:
            if not item.hidden:
                print(item.announce)
        print("\n")


def print_objects_in_room(room):
    if len(room.objects_here) > 0:
        for obj in room.objects_here:
            if not obj.hidden:
                print(obj.idle_message)
        print("\n")


def check_for_combat(player):  # returns a list of angry enemies who are ready to fight
    enemy_combat_list = []
    if len(player.current_room.npcs_here) > 0:  # Evaluate the room's enemies. Check if they are aggro
        # and notice the player.
        finesse_check = random.randint(int(player.finesse * 0.6), int(player.finesse * 1.4))
        for move in player.known_moves:
            if move.name == "Quiet Movement":
                finesse_check *= 1.2
                break
        for e in player.current_room.npcs_here:  # Now go through all of the jerks in the room and do a finesse check
            if not e.friend:
                if (finesse_check <= e.awareness) and e.aggro:  # finesse check fails, break and rescan the list,
                    # adding all aggro enemies
                    print(e.name + " " + e.alert_message)  # player's been spotted
                    enemy_combat_list.append(e)
                    e.in_combat = True
                    for aggro_enemy in player.current_room.npcs_here:  # the jerk's friends join in the fun
                        if aggro_enemy.aggro and aggro_enemy != e and not aggro_enemy.friend:
                            print(aggro_enemy.name + aggro_enemy.alert_message)
                            enemy_combat_list.append(aggro_enemy)
                            aggro_enemy.in_combat = True
                    break  # we don't need to scan any more since the alarm has been raised
    return enemy_combat_list


def refresh_stat_bonuses(target):  # searches all items and states for stat bonuses, then applies them
    reset_stats(target)
    bonuses = {
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
        "add_resistance": {},
        "add_status_resistance": {}
    }

    for category in target.resistance_base:  # roll up all of the resistances and status resistances into the
        # bonuses list
        bonuses["add_resistance"][category] = category       # doing this here will allow changes on the
        # target's class to be reflected
    for category in target.status_resistance_base:
        bonuses["add_status_resistance"][category] = category
    adder_group = []
    if hasattr(target, "inventory"):
        for item in target.inventory:
            if hasattr(item, "isequipped"):
                if item.isequipped:
                    for bonus, attr in bonuses.items():
                        if hasattr(item, bonus):
                            adder_group.append(item)
                            break
    for state in target.states:  # loop through all of the target's states and, if each state has an "adder"
        # attribute like bonus hp, include that
        for bonus, attr in bonuses.items():
            if hasattr(state, bonus):
                adder_group.append(state)
                break  # the state has at least one bonus; we don't have to look for more to include it
    for adder in adder_group:  # here, "adder" is the item or state containing the bonus or bonuses
        for bonus, attr in bonuses.items():
            if hasattr(adder, bonus):  # the item or state has one of the recognized bonuses
                if bonus == "add_resistance":  # since resistances are dicts,
                    # we have to handle them a little differently
                    for v in attr.values():
                        if hasattr(adder, bonus):
                            if v in adder.add_resistance:
                                target.resistance[v] += float(adder.add_resistance[v])
                elif bonus == "add_status_resistance":
                    for v in attr.values():
                        if hasattr(adder, bonus):
                            if v in adder.add_status_resistance:
                                target.status_resistance[v] += float(adder.add_status_resistance[v])
                else:
                    setattr(target, attr, getattr(target, attr) + getattr(adder, bonus))  # adds the value of each
                    # bonus to each attribute
    for i, v in target.status_resistance.items():
        if v < 0:
            target.status_resistance[i] = 0  # prevent status resistances from being negative

    # Process other things which may affect stats, such as weight
    if target.name == "Jean":
        target.refresh_weight()
        target.weight_tolerance += round((target.strength + target.endurance) / 2, 2)
        check_weight = target.weight_tolerance - target.weight_current
        if check_weight > (
                target.weight_tolerance / 2):  # if the player's carrying less than 50% capacity, add 25% to
            target.maxfatigue += (target.maxfatigue / 4)  # max fatigue as a bonus
        elif check_weight < 0:  # if the player is over capacity, reduce max fatigue by excess lbs * 10
            check_weight *= -1
            target.maxfatigue -= (check_weight * 10)
            if target.maxfatigue < 0:
                target.maxfatigue = 0


def check_parry(target):
    parry = False
    for state in target.states:
        if state.name == "Parrying":
            parry = True
            break
    return parry


def spawn_npc(npc_name, tile):
    tile.npcs_here.append(npc_name)


def spawn_item(item_name, tile):
    tile.items_here.append(item_name)


def refresh_moves(player):
    player.known_moves = []
    default_moves = ["Rest", "PlayerAttack"]
    for move_name in default_moves:
        move_class = getattr(moves, move_name)
        move_instance = move_class()
        player.known_moves.append(move_instance)
    # add other moves based on logic and stuff


def is_input_integer(input_to_check):  # useful for checking to see if the player's input can be converted to int
    try:
        int(input_to_check)
        return True
    except ValueError:
        return False


def reset_stats(target):  # resets all stats to base level
    target.strength = target.strength_base
    target.finesse = target.finesse_base
    target.maxhp = target.maxhp_base
    target.maxfatigue = target.maxfatigue_base
    target.speed = target.speed_base
    target.endurance = target.endurance_base
    target.charisma = target.charisma_base
    target.intelligence = target.intelligence_base
    target.faith = target.faith_base
    target.resistance.clear()
    target.status_resistance.clear()
    for element, resist in target.resistance_base.items():
        target.resistance[element] = resist
    for element, resist in target.status_resistance_base.items():
        target.status_resistance[element] = resist
    if hasattr(target, 'weight_tolerance'):
        target.weight_tolerance = target.weight_tolerance_base


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


def add_random_enchantments(item: Item, count: int) -> None:
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

    # Cache enchantment classes by tier to avoid repeated reflection/lookup
    class_by_tier: dict[int, list[type]] = {}
    for _, cls in inspect.getmembers(enchant_tables, inspect.isclass):
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
                requirements_ok = req() if callable(req) else bool(req) if req is not None else True
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
            key = (item.__class__, "stack_key", item.stack_key)
        else:
            # Fallback: use class + name + description where available
            key = (item.__class__, getattr(item, "name", None), getattr(item, "description", None))
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