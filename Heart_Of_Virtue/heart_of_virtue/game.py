"""
My take on Phillip Johnson's text adventure tutorial
"""
__author__ = 'Alex Egbert'
import universe, functions, intro_scene, moves, combat, npc
from player import Player
from universe import Universe
from termcolor import colored, cprint
import time, sys

print_slow = functions.print_slow
screen_clear = functions.screen_clear
def play():
    game = True
    while game == True:
        cprint(r"""
        _
       (_)
       |=|              __  __
       |=|              ||  ||  ____  ___     ____    __||__
   /|__|_|__|\          ||__||  ||    ||\\    || ))   --||--
  (    ( )    )         ||__||  ||-   ||_\\   || \\     ||
   \|\/\"/\/|/          ||  ||  ||__  ||  \\  ||  \\    ||
     |  Y  |            ||  ||
     |  |  |           '--''--'              OF
     |  |  |
    _|  |  |                     __           __
 __/ |  |  |\                    \ \         / /
/  \ |  |  |  \                   \ \       / / ___     __       ____   ____
   __|  |  |   |                   \ \     / /  ||\\    ||      //  \\  || ))
/\/  |  |  |   |\                   \ \   / /   ||_\\   ||____  ||  ||  || \\
 <   +\ |  |\ />  \                  \ \_/ /    ||  \\  \|----  \\__//  ||  \\
  >   + \  | LJ    |                  \___/
        + \|+  \  < \
  (O)      +    |    )                        By Alexander Egbert
   |             \  /\
 ( | )   (o)      \/  )
_\\|//__( | )______)_/
        \\|//

            """, "cyan")
        newgame = True
        if functions.saves_list() != []:
            save_exists = True
        else:
            save_exists = False

        menu = ['NEW GAME', 'QUIT TO DESKTOP']
        if save_exists:
            menu.insert(0, 'LOAD GAME')
        for i, option in enumerate(menu):
            print('{}'.format(i) + colored(': {}'.format(option), 'red'))
        choice = input('Selection: ')
        while not functions.is_input_integer(choice):
            cprint("You must enter a valid number to select an option.", "red")
            choice = input('Selection: ')
        choice = int(choice)
        if menu[choice] == 'NEW GAME':
            pass  # proceed as new game
        elif menu[choice] == 'LOAD GAME':
            newgame = False
        elif menu[choice] == 'QUIT TO DESKTOP':
            game = False
            continue

        if newgame == False:
            try:
                player = functions.load_select()
                if player == SyntaxError:  # if something's broken, go back to main menu
                    continue
            except:  # if something's broken, go back to main menu
                continue

        else:
            player = Player()
            universe = Universe()
            player.universe = universe

        if newgame:
            # intro_scene.intro()  # Comment this out to disable the intro sequence
            player.universe.build(player)
            player.map = player.universe.starting_map
            player.location_x, player.location_y = (player.universe.starting_position)
        room = player.universe.tile_exists(player.map, player.location_x, player.location_y)

        if newgame:
            for item in player.inventory:
                if item.name == "Rock":
                    player.eq_weapon = item
                    item.isequipped = True
                if item.name == "Tattered Cloth" or item.name == "Cloth Hood":
                    item.isequipped = True
        print(room.intro_text())
        player.main_menu = False
        check_time = time.time()
        auto_save_timer = check_time
        mark_health = player.hp
        while player.is_alive() and not player.victory and not player.main_menu:
            player.time_elapsed += (time.time() - check_time)
            auto_save_timer += (time.time() - check_time)
            if auto_save_timer > 300:  # autosave timer
                functions.autosave(player)
                auto_save_timer = 0
            check_time = time.time()
            room = player.universe.tile_exists(player.map, player.location_x, player.location_y)
            player.current_room = room
            room.evaluate_events()
            room.modify_player(player)
            if mark_health != player.hp:
                player.show_bars(True,False)  # show just the health bar if the player's current HP has changed
                mark_health = player.hp
            player.refresh_moves()
            functions.check_for_npcs(room)
            functions.check_for_items(room)
            functions.check_for_objects(room)
            combat_list = functions.check_for_combat(player)
            if len(combat_list) > 0:  # Check the state of the room to see if there are any enemies
                print(colored("Jean readies himself for battle!","red"))
                combat.combat(player, combat_list)

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
                arbitrary_action = True
                if len(count_args) == 1:
                    for action in available_actions:
                        if action_input in action.hotkey:
                            arbitrary_action = False
                            player.do_action(action, **action.kwargs)
                elif len(count_args) > 1:
                    for action in available_actions:
                        if count_args[0] in action.hotkey:
                            join_args = ' '.join(count_args[1:])
                            player.do_action(action, join_args)
                            arbitrary_action = False
                            break
                    if arbitrary_action:
                        lower_phrase = count_args[1].lower()
                        for i, object in enumerate(room.objects_here):
                            search_item = object.name.lower() + ' ' + object.idle_message.lower()
                            if lower_phrase in search_item and not object.hidden:
                                for keyword in object.keywords:
                                    if count_args[0] == keyword:
                                        object.__getattribute__(keyword)()
                                break

                else:
                    cprint("Jean isn't sure exactly what he's trying to do.", 'red')
            time.sleep(0.5)

if __name__ == "__main__":
    play()