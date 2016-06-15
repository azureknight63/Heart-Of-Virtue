import string, textwrap, os
import sys, time, random
import enemies, tiles
from player import Player

### This module contains general functions to use throughout the game

def print_slow(str):
    wrap = textwrap.fill(str, 80)
    for letter in wrap:
        print(letter, end='',flush=True),
        time.sleep(.05)

def screen_clear():
    print("\n" * 100)

def check_for_enemies(room): # Check to see what NPCs are in the room. Does not evaluate combat aggro - that's a different function
    if len(room.enemies_here) > 0:  # Evaluate the room's NPCs.
        print("You notice something moving.\n")
        for npc in room.enemies_here:
            print(npc.name + npc.idle_message)

def spawn_enemy(enemy_name, tile):
    tile.enemies_here.append(enemy_name)
#
# if len(room.enemies_here) > 0:  # Evaluate the room's enemies. Check if they are aggro and notice the player.
#     finesse_check = player.finesse + random.randint((-1 * (player.finesse * 0.2)), (player.finesse * 0.2))
#     for npc in room.enemies_here:  # First tell the player about peaceful characters in the room
#         if npc.aggro == False:
#             print(npc.name + npc.idle_message)
#     for e in room.enemies_here:  # Now go through all of the jerks in the room and do a finesse check
#         if finesse_check > (e.awareness) and e.aggro == True:  # finesse check succeeds
#             print(e.name + e.idle_message)  # player went unnoticed
#         elif player.finesse <= e.awareness and e.aggro == True:  # finesse check fails, break and rescan the list, adding all aggro enemies
#             print(e.name + e.alert_message)  # player's been spotted
#             enemy_combat_list.append(e)
#             for aggro_enemy in room.enemies_here:  # the jerk's friends join in the fun
#                 if aggro_enemy.aggro == True and aggro_enemy != e:
#                     print(aggro_enemy.name + aggro_enemy.alert_message)
#                     enemy_combat_list.append(aggro_enemy)
#             break  # we don't need to scan any more since the alarm has been raised
# return enemy_combat_list


def check_for_items(room):
    if len(room.items_here) > 0:
        return room.items_here
    else:
        return None