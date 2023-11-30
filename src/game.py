"""
My take on Phillip Johnson's text adventure tutorial
Not much is left of the original code.

REMINDERS:

"""
__author__ = 'BasharTeg'
import functions, intro_scene, moves, combat, npc, items
from player import Player
from universe import Universe
from termcolor import colored, cprint
import time, sys

print_slow = functions.print_slow
screen_clear = functions.screen_clear


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
  (O)      +    |    )                        By BasharTeg
   |             \  /\
 ( | )   (o)      \/  )
_\\|//__( | )______)_/
        \\|//

            """, "cyan")
        newgame = True
        if functions.saves_list():
            save_exists = True
        else:
            save_exists = False

        menu = ['NEW GAME', 'QUIT TO DESKTOP']
        if save_exists:
            menu.insert(0, 'LOAD GAME')
        for i, option in enumerate(menu):
            print('{}'.format(i) + colored(': {}'.format(option), 'red'))
        choice = input('Selection: ')
        while True:
            if functions.is_input_integer(choice):
                if 0 <= int(choice) < len(menu):
                    break
            cprint("You must enter a valid number to select an option.", "red")
            choice = input('Selection: ')

        choice = int(choice)
        if menu[choice] == 'NEW GAME':
            pass  # proceed as new game
        elif menu[choice] == 'LOAD GAME':
            newgame = False
        elif menu[choice] == 'QUIT TO DESKTOP':
            game = False
            continue # todo fix the sneak system; it's too easy to evade npcs with only a little investment into finesse - maybe make it a skill

        if not newgame:
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
            player.location_x, player.location_y = player.universe.starting_position

        room = player.universe.tile_exists(player.map, player.location_x, player.location_y)

        ### prepare to enter the post-menu game loop ###
        if newgame:
            for item in player.inventory:
                # if item.name == "Rock":
                #     player.eq_weapon = item
                #     item.isequipped = True
                if item.name == "Tattered Cloth" or item.name == "Cloth Hood":
                    item.isequipped = True
                    item.interactions.append("unequip")
                    item.interactions.remove("equip")
        print(room.intro_text())
        player.main_menu = False
        check_time = time.time()
        auto_save_timer = check_time
        mark_health = player.hp
        items.get_all_subtypes()  # creates the 'All' archetypes for each item group; used for states/item effects/etc.
        ### enter post-menu game loop ###
        while player.is_alive() and not player.victory and not player.main_menu:
            for item in player.inventory:
                item.owner = player  # enforce player ownership of all inventory items; used for special interactions
            if not player.eq_weapon:  # if the player is unarmed, "equip" fists
                player.eq_weapon = player.fists
            player.time_elapsed += (time.time() - check_time)
            auto_save_timer += (time.time() - check_time)
            if auto_save_timer > 3000:  # autosave timer
                functions.autosave(player)
                auto_save_timer = 0
            check_time = time.time()
            room = player.universe.tile_exists(player.map, player.location_x, player.location_y)
            player.current_room = room
            if player.universe.game_tick > 0:
                player.current_room.last_entered = player.universe.game_tick
            else:
                player.current_room.last_entered = 1
            player.recall_friends()  # bring any party members along
            for actor in player.combat_list_allies:
                actor.cycle_states()
            room.evaluate_events()
            room.modify_player(player)
            if mark_health != player.hp:
                player.show_bars(True,False)  # show just the health bar if the player's current HP has changed
                mark_health = player.hp
            functions.check_for_npcs(room)
            room.stack_duplicate_items()
            functions.check_for_items(room)
            functions.check_for_objects(room)
            player.combat_list = functions.check_for_combat(player)
            if len(player.combat_list) > 0:  # Check the state of the room to see if there are any enemies
                print(colored("Jean readies himself for battle!","red"))
                combat.combat(player)
            ### check to make sure entering the most recent tile hasn't ended the game ###
            if not player.is_alive():
                player.death()
            if player.is_alive() and not player.victory:
                player.stack_inv_items()
                player.stack_gold()
                print("\nChoose an action:\n")
                available_actions = room.adjacent_moves()
                available_moves = colored('| ', "cyan")
                for action in available_actions:
                    available_moves += (colored(str(action), "green")) + colored(' | ', "cyan")
                while available_moves.count('|') > 4:  # Break the list of moves over multiple lines
                    cutoff = functions.findnth(available_moves, "|", 4)
                    print(available_moves[:cutoff+1])
                    available_moves = available_moves[cutoff:]
                    if ":" not in available_moves:  # if there aren't any moves left, erase the tail
                        available_moves = ""
                if len(available_moves) > 0:
                    print(available_moves)
                print("\n\nFor a list of additional commands, enter 'c'.\n")
                action_input = input('Action: ')
                raw_args = action_input.split(' ')
                lc_exceptions = ("te", "test", "testevent")  # exceptions to lowering case (better precision, worse searching, may break some actions)
                if raw_args[0] not in lc_exceptions:
                    action_input = action_input.lower()
                available_actions = room.available_actions()
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
                    #                   NOTE: in arbitrary one-word commands, ALL objects that associate the command
                    #                   will evaluate their respective functions
                    #                   NOTE: syntax for multiple words is '<command> <target object>';
                    #                   additional words are ignored
                    success = False
                    
                    def enumerate_for_interactions(subjects):

                        def confirm(thing, action):
                            check = input(colored("{} {}? (y/n)".format(count_args[0].title(), thing.name), "cyan"))
                            if check.lower() == ('y' or 'yes'):
                                thing.__getattribute__(action)(player)
                                return True
                            else:
                                return False

                        if len(count_args) == 1:
                            candidates = []
                            for thing in subjects:
                                if hasattr(thing, "keywords"):
                                    if not thing.hidden:
                                        for keyword in thing.keywords:
                                            if action_input == keyword:
                                                candidates.append(thing)
                                            # if action_input == keyword and confirm(thing, keyword):
                                            #     return True
                                elif hasattr(thing, "interactions"):
                                    for interaction in thing.interactions:
                                        if action_input == interaction:
                                            candidates.append(thing)
                                        #if action_input == interaction and confirm(thing, interaction):
                                        #    return True
                            if len(candidates) == 1:  #if there is only one possibility, skip the confirmation step
                                candidates[0].__getattribute__(action_input)(player)
                                return True
                            elif candidates:  #otherwise, if there is more than one possibility, ask the player to confirm
                                for candidate in candidates:
                                    if confirm(candidate, action_input):
                                        return True
                        elif len(count_args) > 1:
                            candidates = []
                            for i, thing in enumerate(subjects):
                                if hasattr(thing, "keywords"):
                                    search_item = thing.name.lower() + ' ' + thing.idle_message.lower()
                                    if count_args[1] in search_item and not thing.hidden:
                                        for keyword in thing.keywords:
                                            if count_args[0] == keyword:
                                                candidates.append(thing)
                                            #if count_args[0] == keyword and confirm(thing, keyword):
                                            #    return True
                                elif hasattr(thing, "interactions"):
                                    search_item = thing.name.lower() + ' ' + thing.description.lower() + ' ' + thing.announce.lower()
                                    if count_args[1] in search_item and not thing.hidden:
                                        for interaction in thing.interactions:
                                            if count_args[0] == interaction:
                                                candidates.append(thing)
                                            #if count_args[0] == interaction and confirm(thing, interaction):
                                            #    return True
                            if len(candidates) == 1:  #if there is only one possibility, skip the confirmation step
                                candidates[0].__getattribute__(count_args[0])(player)
                                return True
                            elif candidates:  #otherwise, if there is more than one possibility, ask the player to confirm
                                for candidate in candidates:
                                    if confirm(candidate, count_args[0]):
                                        return True
                        return False

                    subjects = room.objects_here + room.npcs_here
                    success = enumerate_for_interactions(subjects)
                    if not success:  # Now check items in the player's inventory
                        subjects = player.inventory
                        success = enumerate_for_interactions(subjects)

                    if not success:  # Nothing was found matching the arbitrary input, so Jean is mightily confused
                        cprint("Jean isn't sure exactly what he's trying to do.", 'red')

            time.sleep(0.5)


if __name__ == "__main__":
    play()