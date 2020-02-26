import string, textwrap, os, inspect
import sys, time, random, pickle, datetime, importlib, decimal
import npc, tiles, moves, enchant_tables
from player import Player
from termcolor import colored, cprint
from os import listdir
from os.path import isfile, join

### This module contains general functions to use throughout the game

def print_slow(text, speed=1):
    if not is_input_integer(speed):
        printspeed = 1
    else:
        printspeed = speed
    rate = 0.1 / printspeed
    wrap = textwrap.fill(text, 80)
    for letter in wrap:
        print(letter, end='',flush=True),
        time.sleep(rate)


def screen_clear():
    print("\n" * 100)


def check_for_npcs(room):  # Check to see what NPCs are in the room.
    # Does not evaluate combat aggro - that's a different function
    if len(room.npcs_here) > 0:  # Evaluate the room's NPCs.
        for npc in room.npcs_here:
            if not npc.hidden:
                print(npc.name + npc.idle_message)
        print("\n")


def check_for_items(room):
    if len(room.items_here) > 0:
        for item in room.items_here:
            if not item.hidden:
                print(item.announce)
        print("\n")


def check_for_objects(room):  # Check to see what objects are in the room.
    if len(room.objects_here) > 0:
        for obj in room.objects_here:
            if not obj.hidden:
                print(obj.idle_message)
        print("\n")


def check_for_combat(player):  # returns a list of angry enemies who are ready to fight
    enemy_combat_list = []
    if len(player.current_room.npcs_here) > 0:  # Evaluate the room's enemies. Check if they are aggro and notice the player.
        finesse_check = random.randint(int(player.finesse * 0.8), int(player.finesse * 1.2))
        for e in player.current_room.npcs_here:  # Now go through all of the jerks in the room and do a finesse check
            if not e.friend:
                if (finesse_check <= e.awareness) and e.aggro:  # finesse check fails, break and rescan the list,
                    # adding all aggro enemies
                    print(e.name + " " + e.alert_message)  # player's been spotted
                    enemy_combat_list.append(e)
                    e.in_combat = True
                    for aggro_enemy in player.current_room.npcs_here:  # the jerk's friends join in the fun
                        if aggro_enemy.aggro and aggro_enemy != e:
                            print(aggro_enemy.name + aggro_enemy.alert_message)
                            enemy_combat_list.append(aggro_enemy)
                            aggro_enemy.in_combat = True
                    break  # we don't need to scan any more since the alarm has been raised
    return enemy_combat_list


def refresh_stat_bonuses(target):  # searches all items and states for stat bonuses, then applies them
    reset_stats(target)
    bonuses = {
        "add_str":"strength",
        "add_fin":"finesse",
        "add_maxhp":"maxhp",
        "add_maxfatigue":"maxfatigue",
        "add_speed":"speed",
        "add_endurance":"endurance",
        "add_charisma":"charisma",
        "add_intelligence":"intelligence",
        "add_faith":"faith",
        "add_weight_tolerance":"weight_tolerance"
    }
    for category, value in target.resistance_base.items():
        bonuses["add_resistance[" + category + "]"] = value
    for category, value in target.status_resistance_base.items():
        bonuses["add_status_resistance[" + category + "]"] = value
    adder_group = []
    if hasattr(target, "inventory"):
        for item in target.inventory:
            if hasattr(item, "is_equipped"):
                if item.is_equipped:
                    for bonus, attr in bonuses.items():
                        if hasattr(item, bonus):
                            adder_group.append(item)
                            break
    for state in target.states:
        for bonus, attr in bonuses.items():
            if hasattr(state, bonus):
                adder_group.append(state)
                break
    for adder in adder_group:
        for bonus, attr in bonuses.items():
            if hasattr(adder, bonus):
                setattr(target, attr, getattr(target, attr) + getattr(adder, bonus))  # adds the value of each bonus to each attribute

    ### Process other things which may affect stats, such as weight ###
    if target.name == "Jean":
        target.refresh_weight()
        target.weight_tolerance += decimal.Decimal((target.strength + target.endurance) / 2)
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
    player.known_moves = [moves.Rest(), moves.PlayerAttack()]
    # add other moves based on logic and stuff


def is_input_integer(input): #useful for checking to see if the player's input can be converted to int
    try:
        int(input)
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
                check_playtime = load(file)
                playtime = str(datetime.timedelta(seconds=check_playtime.time_elapsed))
                playtime = playtime[:-7]
                print('{}: {} (last modified {}) (play time: {})'.format(i, file, timestamp, playtime))
            print('x: Cancel')
            choice = input("Selection: ")
            if choice == 'x':
                print('Load operation cancelled.')
                return SyntaxError
            if is_input_integer(choice):
                try:
                    return load(saves_list()[int(choice)])
                except:
                    cprint("Invalid selection.", "red")
    else:
        cprint("No save files detected.", "red")
        return SyntaxError


def load(filename):
    with open(filename, 'rb') as f:
        data = pickle.load(f)
    return data


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
                except:
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
    for i in range(4,0,-1):
        for file in saves_list():  # cascade the autosaves, trimming off number 5
            if file == 'autosave{}.sav'.format(i):
                save(load('autosave{}.sav'.format(i)), 'autosave{}.sav'.format(i+1))
                break
    save(player, 'autosave1.sav')


def findnth(haystack, needle, n):
    parts = haystack.split(needle, n+1)
    if len(parts) <= n+1:
        return -1
    return len(haystack)-len(parts[-1])-len(needle)


def checkrange(user):
    '''Checks the min & max range constraints for the user; returns a tuple of (min, max)'''
    minr=0
    maxr=0
    if user.name == "Jean":
        minr += user.eq_weapon.range[0]
        minr += user.eq_weapon.range[1]
    else:
        minr += user.combat_range[0]
        minr += user.combat_range[1]
    return minr, maxr


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


def seek_class(classname, player, tile, repeat, params):  # searches through the story folder for the matching module and returns an instance
    class_obj = ""
    try:
        class_obj = getattr(importlib.import_module('src.events'), classname)(player, tile, repeat, params)
    except:
    # except BaseException as e:
        # print("#####ERR: {}".format(e))
        try:
            class_obj = getattr(importlib.import_module('src.story.general'), classname)(player, tile, repeat, params)
        except:
        # except BaseException as e:
            # print("#####ERR: {}".format(e))
            try:
                class_obj = getattr(importlib.import_module('src.story.ch01'), classname)(player, tile, repeat, params)
            except:
            # except BaseException as e:
                # print("#####ERR: {}".format(e))
                print("#####ERR: Cannot find event " + classname)
    return class_obj


def await_input():
    input(colored("\n(Press Enter)", "yellow"))


def inflict(state, target, chance=1.0, force=False):
    '''
    attempt to inflict a state on a target player or NPC.
    :param state: new instance of the state object to be inflicted
    :param target: target to receive the state
    :param chance: base chance of success; further altered by resistances
    :param force: if true, inflicting will never fail regardless of resistance
    :return: returns the state object that was inflicted/compounded or False if it failed
    '''

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
            roll = random.uniform(0,1)
            if chance >= roll:  # success! Status gets inflicted!
                success(target, state)
            else:
                return False  # state failed to apply
    else:
        success(target, state)


def add_random_enchantments(item, count):
    ench_pool = count
    enchantment_level = [0, 0]
    enchantments = [None, None]
    while ench_pool > 0:
        group = random.randint(0, 1)  # 0 = "Prefix", 1 = "Suffix"
        enchantment_level[group] += 1
        candidates = []
        rarity = random.randint(0, 100)
        for name, obj in inspect.getmembers(enchant_tables):
            if inspect.isclass(obj):
                if hasattr(obj, "tier"):
                    if obj.tier == enchantment_level[group]:
                        ench = getattr(enchant_tables, name)(item)
                        if ench.requirements() and (rarity >= ench.rarity):
                            candidates.append(ench)
        if not candidates:  # skip ahead if there are no available enchantments
            ench_pool -= 1
            continue
        # for candidate in candidates:
        #     print(candidate.name + " req? " + str(candidate.requirements()))
        #     if not candidate.requirements() or (rarity < candidate.rarity):
        #         candidates.remove(candidate)
        # print("Candidates: " + str(candidates))
        select = random.randint(0, len(candidates) - 1)
        enchantments[group] = candidates[select]
        ench_pool -= 1
    if enchantments[0]:
        enchantments[0].modify()
    if enchantments[1]:
        enchantments[1].modify()
