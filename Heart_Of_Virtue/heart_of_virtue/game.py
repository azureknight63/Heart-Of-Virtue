"""
My take on Phillip Johnson's text adventure tutorial
"""
__author__ = 'Alex Egbert'
import universe, functions, intro_scene, moves, combat, npc
from player import Player
from universe import Universe
from termcolor import colored, cprint
import time

print_slow = functions.print_slow
screen_clear = functions.screen_clear
def play():  #todo set up a way to save/load from player-selected files, as well as autosave
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
        try:
            test = functions.load()
            save_exists = True
        except:
            save_exists = False

        menu = ['NEW GAME', 'QUIT TO DESKTOP']
        if save_exists:
            menu.insert(0, 'CONTINUE')
        for i, option in enumerate(menu):
            print('{}'.format(i) + colored(': {}'.format(option), 'red'))
        choice = input('Selection: ')
        while not functions.is_input_integer(choice):
            cprint("You must enter a valid number to select an option.", "red")
            choice = input('Selection: ')
        choice = int(choice)
        if menu[choice] == 'NEW GAME':
            pass  # proceed as new game
        elif menu[choice] == 'CONTINUE':
            newgame = False
        elif menu[choice] == 'QUIT TO DESKTOP':
            game = False
            continue

        if newgame == False:
            try:
                player = functions.load()
            except:  # if something's broken, proceed as if it were a new game
                player = Player()
                universe = Universe()
                player.universe = universe
                newgame = True
        else:
            player = Player()
            universe = Universe()
            player.universe = universe

        if newgame == True:
            intro_scene.intro()  # Comment this out to disable the intro sequence
            player.universe.build(player)
            player.map = player.universe.starting_map
            player.location_x, player.location_y = (player.universe.starting_position)
        room = player.universe.tile_exists(player.map, player.location_x, player.location_y)

        if newgame == True:
            for item in player.inventory:
                if item.name == "Rock":
                    player.eq_weapon = item
                    item.isequipped = True
                if item.name == "Tattered Cloth" or item.name == "Cloth Hood":
                    item.isequipped = True
        print(room.intro_text())
        while player.is_alive() and not player.victory:
            functions.save(player)
            room = player.universe.tile_exists(player.map, player.location_x, player.location_y)
            player.current_room = room
            room.modify_player(player)
            player.show_bars(True,False)  # show just the health bar
            player.refresh_moves()
            # room.spawn_npc('Slime')
            functions.check_for_npcs(room)
            functions.check_for_items(room)
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
                    cprint("Jean isn't sure exactly what he's trying to do.", 'red')
            time.sleep(0.5)



if __name__ == "__main__":
    play()