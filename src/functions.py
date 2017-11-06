import string, textwrap, os
import sys, time, random, pickle, datetime
import npc, tiles, moves
from player import Player
from termcolor import colored, cprint
from os import listdir
from os.path import isfile, join

### This module contains general functions to use throughout the game

def print_slow(str):
    wrap = textwrap.fill(str, 80)
    for letter in wrap:
        print(letter, end='',flush=True),
        time.sleep(.05)

def screen_clear():
    print("\n" * 100)

def check_for_npcs(room):  # Check to see what NPCs are in the room.
    # Does not evaluate combat aggro - that's a different function
    if len(room.npcs_here) > 0:  # Evaluate the room's NPCs.
        for npc in room.npcs_here:
            if npc.hidden == False:
                print(npc.name + npc.idle_message)
        print("\n")

def check_for_items(room):
    if len(room.items_here) > 0:
        for item in room.items_here:
            if item.hidden == False:
                print(item.announce)
        print("\n")

def check_for_objects(room): # Check to see what objects are in the room.
    if len(room.objects_here) > 0:
        for obj in room.objects_here:
            if obj.hidden == False:
                print(obj.idle_message)
        print("\n")


def check_for_combat(player): # returns a list of angry enemies who are ready to fight
    enemy_combat_list = []
    if len(player.current_room.npcs_here) > 0:  # Evaluate the room's enemies. Check if they are aggro and
        # notice the player.
        finesse_check = player.finesse + random.randint((-1 * (player.finesse * 0.2)), (player.finesse * 0.2))
        for e in player.current_room.npcs_here:  # Now go through all of the jerks in the room and do a finesse check
            if finesse_check <= e.awareness and e.aggro == True:  # finesse check fails, break and rescan the list,
                # adding all aggro enemies
                print(e.name + " " + e.alert_message)  # player's been spotted
                enemy_combat_list.append(e)
                for aggro_enemy in player.current_room.npcs_here:  # the jerk's friends join in the fun
                    if aggro_enemy.aggro == True and aggro_enemy != e:
                        print(aggro_enemy.name + aggro_enemy.alert_message)
                        enemy_combat_list.append(aggro_enemy)
                break  # we don't need to scan any more since the alarm has been raised
    return enemy_combat_list

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
    target.resistance = target.resistance_base
    if hasattr(target, 'weight_tolerance'):
        target.weight_tolerance = target.weight_tolerance_base


def load_select():
    if saves_list() != []:
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
    while save_complete == False:
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
            while overwrite_complete == False:
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