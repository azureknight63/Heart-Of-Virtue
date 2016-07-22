"""
My take on Phillip Johnson's text adventure tutorial
"""
__author__ = 'Alex Egbert'
import world, functions, intro_scene, moves, combat
from player import Player
from termcolor import colored, cprint
import time

print_slow = functions.print_slow
screen_clear = functions.screen_clear
def play():
    world.load_tiles()
    world.place_enemies() #loads the default enemies into world tiles
    world.place_items() #same thing for items
    player = Player()
    room = world.tile_exists(player.location_x, player.location_y)
    # intro_scene.intro() # Comment this out to disable the intro sequence
    for item in player.inventory:
        if item.name == "Rock":
            player.eq_weapon = item
            item.isequipped = True
        if item.name == "Tattered Cloth" or item.name == "Cloth Hood":
            item.isequipped = True
    print(room.intro_text())
    while player.is_alive() and not player.victory:
        room = world.tile_exists(player.location_x, player.location_y)
        player.current_room = room
        room.modify_player(player)
        player.show_bars(True,False)
        player.refresh_moves()
        functions.check_for_enemies(room)
        functions.check_for_items(room)
        combat_list = functions.check_for_combat(player)
        if len(combat_list) > 0: # Check the state of the room to see if there are any enemies
            print(colored("You ready yourself for battle!","red"))
            combat.combat(player, combat_list)
        # Check again since the room could have changed the player's state
        if player.is_alive() and not player.victory:
            player.stack_inv_items()
            print("\nChoose an action:\n")
            available_actions = room.adjacent_moves()
            available_moves = colored('| ', "cyan")
            for action in available_actions:
                available_moves += (colored(action, "green")) + colored(' | ',"cyan")
            print(available_moves)
            print("\n\nFor a list of additional commands, enter 'c'.\n")
            action_input = input('Action: ')
            available_actions = room.available_actions()
            count_args = action_input.split(' ')
            if len(count_args) == 1:
                for action in available_actions:
                    if action_input == action.hotkey:
                        player.do_action(action, **action.kwargs)
                        break
            elif len(count_args) > 1:
                for action in available_actions:
                    if count_args[0] == action.hotkey:
                        join_args = ' '.join(count_args[1:])
                        player.do_action(action, join_args)
                        break
            else:
                cprint("You aren't sure exactly what you're trying to do.", 'red')
        time.sleep(0.5)



if __name__ == "__main__":
    play()