__author__ = 'Alex Egbert'

import time

from neotermcolor import colored, cprint

from functions import refresh_stat_bonuses
from intro_scene import intro

from combat import combat
import functions as functions
import items as items
from player import Player
from universe import Universe, tile_exists
import sys
from config_manager import ConfigManager


print_slow = functions.print_slow
screen_clear = functions.screen_clear


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
                    'Enabled': save_exists,
                    'Index': 2
                },
                'QUIT TO DESKTOP':
                {
                    'Enabled': True,
                    'Index': 3
                }
                }

        choice = None
        enabled_options = {menu[option]['Index']: option for option in menu if menu[option]['Enabled']}
        while choice not in enabled_options:
            for option, data in menu.items():
                if data['Enabled']:
                    print(f"{data['Index']}: {colored(option, 'red')}")
                else:
                    print(f"X: {colored(option, 'yellow', attrs=['dark'])}")
            choice = validate_numerical_input('Selection: ', 1, len(menu) + 1)
            selected_option = enabled_options.get(choice)
            if selected_option == 'NEW GAME':
                pass  # Proceed as new game
            elif selected_option == 'LOAD GAME':
                newgame = False
            elif selected_option == 'QUIT TO DESKTOP':
                sys.exit()
        # Acquire player (either new or loaded). If load cancelled, restart menu loop.
        if newgame:
            player = Player()
        else:
            loaded = functions.load_select()
            if loaded is None:
                # User cancelled or no saves; restart main menu loop
                continue
            player = loaded
        player.universe = Universe(player)
        player.universe.build(player)
        starting_map_name = "default"
        
        # Load configuration using ConfigManager
        config_mgr = ConfigManager('config_dev.ini')
        config = config_mgr.load()
        
        testing_mode = config.testmode
        skip_dialog = config.skipdialog
        if skip_dialog:
            player.skip_dialog = True
        starting_map_name = config.startmap
        startposition = config.startposition
        
        # Apply configuration to player and universe
        player.use_colour = config.use_colour
        player.enable_animations = config.enable_animations
        player.animation_speed = config.animation_speed
        player.testing_mode = testing_mode
        player.game_config = config
        player.universe.testing_mode = testing_mode
        player.universe.game_config = config
        
        starting_map = next((map_item for map_item in player.universe.maps if
                            map_item.get('name') == starting_map_name), player.universe.starting_map_default)

        if testing_mode:
            print(f"\n\n###\nTest Mode: {testing_mode}")
            print(f"Start Map: {starting_map_name}")
            print(f"Start Position: {startposition}\n###\n\n")
            player.skill_exp['Basic'] = 9999
            player.skill_exp['Unarmed'] = 9999

        player.map = starting_map
        player.location_x, player.location_y = startposition
        room = tile_exists(player.map, player.location_x, player.location_y)

        """
        begin post-menu game loop
        """
        if newgame:
            for item in player.inventory:
                if item.name == "Tattered Cloth" or item.name == "Cloth Hood":
                    item.isequipped = True
                    item.interactions.append("unequip")
                    item.interactions.remove("equip")
        if not testing_mode:
            intro()
        player.refresh_merchants()
        player.current_room = room
        room.discovered = True  # Mark starting room as discovered
        print(room.intro_text())
        functions.print_items_in_room(player.current_room)
        functions.print_objects_in_room(player.current_room)
        functions.advise_player_actions(player)
        player.main_menu = False
        check_time = time.time()
        auto_save_timer = check_time
        mark_health = player.hp
        items.get_all_subtypes()  # creates the 'All' archetypes for each item group; used for states/item effects/etc.

        while player.is_alive() and not player.victory and not player.main_menu:
            player.refresh_weight()
            refresh_stat_bonuses(player)
            now = time.time()
            elapsed_time = now - check_time
            player.time_elapsed += elapsed_time
            auto_save_timer += elapsed_time
            if auto_save_timer > 3000:  # autosave timer
                functions.autosave(player)
                auto_save_timer = 0
            check_time = now
            player.universe.game_tick_events()

            for item in player.inventory:
                if item.owner is not player:
                    item.owner = player  # enforce player ownership of all inventory items; used for special interactions
            if not player.eq_weapon:  # if the player is unarmed, "equip" fists
                player.eq_weapon = player.fists

            player.current_room = tile_exists(player.map, player.location_x, player.location_y)
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
            player.combat_list = functions.check_for_combat(player)
            if len(player.combat_list) > 0:  # Check the state of the room to see if there are any enemies
                print(colored("Jean readies himself for battle!", "red"))
                combat(player)
            # check to make sure entering the most recent tile hasn't ended the game
            if not player.is_alive():
                player.death()
            elif player.is_alive() and not player.victory:
                player.stack_inv_items()
                player.stack_gold()
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
                        if action_input in action.hotkey:
                            arbitrary_action = False
                            player.do_action(action, **action.kwargs)
                elif len(count_args) > 1:
                    for action in available_actions:
                        if count_args[0] in action.hotkey:
                            join_args = ' '.join(count_args[1:])
                            player.do_action(action, join_args)
                            arbitrary_action = False
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
                        if functions.enumerate_for_interactions(scope, player, count_args, action_input):
                            success = True  # Check each scope separately and, if an interaction is found,
                            # don't check the remaining scope(s)
                            break
                    if not success:  # Nothing was found matching the arbitrary input, so Jean is mightily confused
                        cprint("Jean isn't sure exactly what he's trying to do.", 'red')
            player.universe.game_tick += 1
            time.sleep(0.5)





if __name__ == "__main__":
    play()
