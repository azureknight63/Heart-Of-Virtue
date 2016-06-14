"""
A simple text adventure designed as a learning experience for new programmers.
"""
__author__ = 'Phillip Johnson'
import world, time, random
import sys
import functions, genericng
from player import Player
print_slow = functions.print_slow
screen_clear = functions.screen_clear
def play():
    world.load_tiles()
    world.place_enemies()
    player = Player()
    room = world.tile_exists(player.location_x, player.location_y)
    #UNCOMMENT TO ENABLE THE INTRO
    # print_slow("Darkness. Silence. You are surrounded by these. They seem to hang around you like a thick fog,"
    #       " suffocating your senses, your consciousness. You try to cry out into the void, but you can't feel"
    #       " your mouth moving. You can't feel anything. You'd panic but that all seems so pointless now, here"
    #       " in this thick soup of nullity. Not even the sound of your own heart beating or your breath"
    #       " escaping your lungs seems to penetrate the blackness and the quiet.\n")
    # time.sleep(10)
    # screen_clear()
    # print_slow("Gradually, a noise begins to rise out of the void. Indistinct and quiet at first, like a whisper, "
    #       "but slowly coming into focus.\n\n\n")
    # time.sleep(5)
    # screen_clear()
    # print_slow("'The body of Christ...'\n\n")
    # time.sleep(5)
    # screen_clear()
    # print_slow("'The body of Christ...'\n\n")
    # time.sleep(5)
    # screen_clear()
    # print_slow("Slowly, light and sound begin to pour back into your awareness. After what seems like an "
    #            "eternity, you open your eyes...\n\n")
    # time.sleep(10)
    # screen_clear()
    print(room.intro_text())
    while player.is_alive() and not player.victory:
        room = world.tile_exists(player.location_x, player.location_y)
        room.modify_player(player)
        combat_list = list(functions.check_for_enemies(room, player))
        if combat_list != []:
            pass # begin combat, not yet implemented



        # Check again since the room could have changed the player's state
        if player.is_alive() and not player.victory:
            # Check the state of the room to see if there are any enemies

            print("Choose an action:\n")
            available_actions = room.available_actions()
            for action in available_actions:
                print(action)
            print("Other common actions: equip, unequip, look, peer (direction)\n")
            action_input = input('Action: ')
            for action in available_actions:
                if action_input == action.hotkey:
                    player.do_action(action, **action.kwargs)
                    break


if __name__ == "__main__":
    play()