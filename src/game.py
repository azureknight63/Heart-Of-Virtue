"""
My take on Phillip Johnson's text adventure tutorial
Not much is left of the original code.

REMINDERS:

"""
__author__ = 'Alex Egbert'

import time

from neotermcolor import colored, cprint
from intro_scene import intro

import combat
import functions
import items
from player import Player
from universe import Universe

print_slow = functions.print_slow
screen_clear = functions.screen_clear

testing_mode = True
"""
testing_mode has several effects if set to True. They are:
- The starting map is changed to testing.txt
- The intro sequence is skipped

Setting testing_mode to False makes start_area.txt the starting map
"""


def validate_numerical_input(prompt, min_value, max_value):
    while True:
        choice = input(prompt)
        if functions.is_input_integer(choice):
            choice = int(choice)
            if min_value <= choice < max_value:
                return choice
        print(colored("You must enter a valid number within the given range.", "red"))


def play():
    game = True
    while game:
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
/  \ |  |  |  \                   \ \       / / __  ____    __||__  __  __ ____
   __|  |  |   |                   \ \     / /  ||  || ))   --||--  ||  || ||
/\/  |  |  |   |\                   \ \   / /   ||  || \\     ||    ||  || ||-
 <   +\ |  |\ />  \                  \ \_/ /    ||  ||  \\    ||    ||==|| ||__
  >   + \  | LJ    |                  \___/
        + \|+  \  < \
  (O)      +    |    )                        By Alex Egbert
   |             \  /\
 ( | )   (o)      \/  )
_\\|//__( | )______)_/
        \\|//

            """, "cyan")
        newgame = True
        save_exists = bool(functions.saves_list())
        menu = {'NEW GAME':
                {
                    'Enabled': True,
                    'Index': 1
                },
                'LOAD GAME':
                {
                    'Enabled': not newgame and save_exists,
                    'Index': 2
                },
                'QUIT TO DESKTOP':
                {
                    'Enabled': True,
                    'Index': 3
                }
                }

        choice = 0
        while choice == 0:
            for i, option in enumerate(menu):
                if menu[option]['Enabled']:
                    print(f"{menu[option]['Index']}: {colored(option, 'red')}")
            choice = validate_numerical_input('Selection: ', 1, len(menu)+1)
            if choice == menu['NEW GAME']['Index']:
                pass  # Proceed as new game
            elif choice == menu['LOAD GAME']['Index']:
                newgame = False
            elif choice == menu['QUIT TO DESKTOP']['Index']:
                break  # Exit the loop and quit
        player = functions.load_select() if not newgame else Player()
        universe = Universe()
        player.universe = universe
        player.universe.build(player)
        player.map = player.universe.starting_map if not testing_mode else (
            next((map_item for map_item in player.universe.maps if map_item.get('name') == 'testing'), None))
        # player.map = player.universe.starting_map
        player.location_x, player.location_y = player.universe.starting_position
        room = player.universe.tile_exists(player.map, player.location_x, player.location_y)

        """
        begin post-menu game loop
        """
        if newgame:
            for item in player.inventory:
                # if item.name == "Rock":
                #     player.eq_weapon = item
                #     item.isequipped = True
                if item.name == "Tattered Cloth" or item.name == "Cloth Hood":
                    item.isequipped = True
                    item.interactions.append("unequip")
                    item.interactions.remove("equip")
        if not testing_mode:
            intro()
        print(room.intro_text())
        player.main_menu = False
        check_time = time.time()
        auto_save_timer = check_time
        mark_health = player.hp
        items.get_all_subtypes()  # creates the 'All' archetypes for each item group; used for states/item effects/etc.

        while player.is_alive() and not player.victory and not player.main_menu:
            elapsed_time = time.time() - check_time
            player.time_elapsed += elapsed_time
            auto_save_timer += elapsed_time
            if auto_save_timer > 3000:  # autosave timer
                functions.autosave(player)
                auto_save_timer = 0
            check_time = time.time()

            for item in player.inventory:
                item.owner = player  # enforce player ownership of all inventory items; used for special interactions
            if not player.eq_weapon:  # if the player is unarmed, "equip" fists
                player.eq_weapon = player.fists

            player.current_room = player.universe.tile_exists(player.map, player.location_x, player.location_y)
            if player.universe.game_tick > 0:
                player.current_room.last_entered = player.universe.game_tick
            else:
                player.current_room.last_entered = 1
            player.recall_friends()  # bring any party members along
            for actor in player.combat_list_allies:
                actor.cycle_states()
            player.current_room.evaluate_events()
            player.current_room.modify_player(player)
            if mark_health != player.hp:
                player.show_bars(True, False)  # show just the health bar if the player's current HP has changed
                mark_health = player.hp
            functions.print_npcs_in_room(player.current_room)
            player.current_room.stack_duplicate_items()
            functions.print_items_in_room(player.current_room)
            functions.print_objects_in_room(player.current_room)
            player.combat_list = functions.check_for_combat(player)
            if len(player.combat_list) > 0:  # Check the state of the room to see if there are any enemies
                print(colored("Jean readies himself for battle!", "red"))
                combat.combat(player)
            # check to make sure entering the most recent tile hasn't ended the game
            if not player.is_alive():
                player.death()
            elif player.is_alive() and not player.victory:
                player.stack_inv_items()
                player.stack_gold()
                print("\nChoose an action:\n")
                available_actions = player.current_room.adjacent_moves()
                move_separator = colored(' | ', "cyan")
                available_moves = move_separator.join(colored(str(action), "green") for action in available_actions)
                while available_moves.count('|') > 4:  # Break the list of moves over multiple lines
                    cutoff = functions.findnth(available_moves, "|", 4)
                    print(available_moves[:cutoff + 1])
                    available_moves = available_moves[cutoff:]
                    if ":" not in available_moves:  # if there aren't any moves left, erase the tail
                        available_moves = ""
                if len(available_moves) > 0:
                    print(available_moves)
                print("\nFor a list of additional commands, enter 'c'.\n")
                action_input = input('Action: ')
                raw_args = action_input.split(' ')
                lc_exceptions = ("te", "test",
                                 "testevent")  # exceptions to lowering case
                # (better precision, worse searching, may break some actions)
                if raw_args[0] not in lc_exceptions:
                    action_input = action_input.lower()
                available_actions = player.current_room.available_actions()
                count_args = action_input.split(' ')
                arbitrary_action = True  # this will be set to False if the action is a default one that the player
                #                          normally has access to
                if len(count_args) == 1:  # if the player entered only one word (ex 'look'), do this stuff
                    for action in available_actions:
                        for key in action.hotkey:
                            if action_input == key:
                                arbitrary_action = False
                                player.do_action(action, **action.kwargs)
                elif len(count_args) > 1:  # if the player entered more than one word (ex 'view restorative'), do this
                    for action in available_actions:
                        for key in action.hotkey:
                            if count_args[0] == key:
                                join_args = ' '.join(count_args[1:])
                                player.do_action(action, join_args)
                                arbitrary_action = False
                                break
                if arbitrary_action:  # if the command the player used could not be found in the list of default
                    #                   actions, check to see if objects in the room have an associated command.
                    #                   In arbitrary one-word commands, ALL objects that associate the command
                    #                   will evaluate their respective functions
                    #                   The syntax for multiple words is '<command> <target object>';
                    #                   additional words are ignored
                    interaction_scopes = [
                        player.current_room.objects_here + player.current_room.npcs_here,
                        player.inventory
                        ]
                    success = False
                    for scope in interaction_scopes:
                        if functions.enumerate_for_interactions(scope, (player, count_args, action_input)):
                            success = True  # Check each scope separately and, if an interaction is found,
                            # don't check the remaining scope(s)
                            break
                    if not success:  # Nothing was found matching the arbitrary input, so Jean is mightily confused
                        cprint("Jean isn't sure exactly what he's trying to do.", 'red')
            time.sleep(0.5)


if __name__ == "__main__":
    play()
