import string, textwrap, os
import sys, time, random
import npc, tiles, moves
from player import Player
from termcolor import colored

### This module contains general functions to use throughout the game

def print_slow(str):
    wrap = textwrap.fill(str, 80)
    for letter in wrap:
        print(letter, end='',flush=True),
        time.sleep(.05)

def screen_clear():
    print("\n" * 100)

def check_for_npcs(room): # Check to see what NPCs are in the room. Does not evaluate combat aggro - that's a different function
    if len(room.npcs_here) > 0:  # Evaluate the room's NPCs.
        for npc in room.npcs_here:
            if npc.hidden == False:
                print(npc.name + npc.idle_message)
        print("\n")

def check_for_combat(player): # returns a list of angry enemies who are ready to fight
    enemy_combat_list = []
    if len(player.current_room.npcs_here) > 0:  # Evaluate the room's enemies. Check if they are aggro and notice the player.
        finesse_check = player.finesse + random.randint((-1 * (player.finesse * 0.2)), (player.finesse * 0.2))
        for e in player.current_room.npcs_here:  # Now go through all of the jerks in the room and do a finesse check
            if finesse_check <= e.awareness and e.aggro == True:  # finesse check fails, break and rescan the list, adding all aggro enemies
                print(e.name + e.alert_message)  # player's been spotted
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

def check_for_items(room):
    if len(room.items_here) > 0:
        for item in room.items_here:
            print(item.announce)
        print("\n")

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