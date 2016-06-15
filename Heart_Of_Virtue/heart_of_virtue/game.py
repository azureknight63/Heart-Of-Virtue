"""
A simple text adventure designed as a learning experience for new programmers.
"""
__author__ = 'Phillip Johnson'
import world, functions, intro_scene
from player import Player
print_slow = functions.print_slow
screen_clear = functions.screen_clear
def play():
    world.load_tiles()
    world.place_enemies()
    player = Player()
    room = world.tile_exists(player.location_x, player.location_y)
    # intro_scene.intro() # Comment this out to disable the intro sequence
    print(room.intro_text())
    while player.is_alive() and not player.victory:
        room = world.tile_exists(player.location_x, player.location_y)
        room.modify_player(player)
        functions.check_for_enemies(room)
        # combat_list = list(functions.check_for_enemies(room, player))
        # if combat_list != []:
        #     pass # begin combat, not yet implemented



        # Check again since the room could have changed the player's state
        if player.is_alive() and not player.victory:
            # Check the state of the room to see if there are any enemies

            print("Choose an action:\n")
            available_actions = room.adjacent_moves()
            print('| ',end='')
            for action in available_actions:
                print(action, end=' | ')
            print("\n\nFor a list of additional commands, enter 'c'.\n")
            action_input = input('Action: ')
            available_actions = room.available_actions()
            for action in available_actions:
                if action_input == action.hotkey:
                    player.do_action(action, **action.kwargs)
                    break


if __name__ == "__main__":
    play()