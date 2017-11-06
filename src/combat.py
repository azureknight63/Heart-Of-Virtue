from termcolor import colored, cprint
import time

def combat(player):
    """

    :param player:
    :param player.combat_list: A list of enemies to engage in this combat loop.
    :return: Nothing is returned - this is simply a branch from the main game loop to handle combat.
    """
    beat = 0  # initialize the beat variable. Beats are "combat" turns but more granular - moves can take multiple beats and can be interrupted before completion
    player.heat = 1.0  # initialize the heat multiplier. This increases the damage of moves. The more the player can combo moves together without being hit, the higher this multiplier grows.
    player.in_combat = True
    for enemy in player.combat_list:
        enemy.in_combat = True
    while True:  # combat will loop until there are no aggro enemies or the player is dead
        #  Check for combat events and execute them once, if possible
        if len(player.combat_events) > 0:  # first check combat events. This is higher in case, for example, an event is to fire upon player or enemy death
            for event in player.combat_events:
                event.check_combat_conditions(beat)

        if not player.is_alive():
            player.death()
            break

        if len(player.combat_list) == 0:
            print("Victory!")
            player.fatigue = player.maxfatigue
            print("Jean gained {} exp!".format(player.combat_exp))
            player.gain_exp(player.combat_exp)
            player.combat_exp = 0
            break

        #  at this point, the player is alive and at least one enemy remains

        player.refresh_stat_bonuses()
        for enemy in player.combat_list:
            enemy.refresh_stat_bonuses()

        while player.current_move == None: #the player must choose to do something
            beat_str = colored("BEAT: ", "blue") + colored(str(beat), "blue")
            heat_display = int(player.heat * 100)
            heat_str = colored("HEAT: ", "red") + colored(str(heat_display), "red") + colored("%", "red")
            print("\n" + beat_str + "                  " + heat_str)
            player.show_bars()
            print("\nWhat will you do?\n")
            available_moves = "\n"
            for i, move in enumerate(player.known_moves):
                if not move.current_stage == 3:
                    if move.fatigue_cost > player.fatigue:
                        move_str = (str(i) + ": " + str(move.name) + " ||| F: " + str(move.fatigue_cost) + "\n")
                        move_str = colored(move_str, "red")
                    else:
                        move_str = (str(i) + ": " + str(move.name) + " ||| F: " + str(move.fatigue_cost) + "\n")
                else:
                    if move.beats_left > 0:
                        move_str = (str(i) + ": " + str(move.name) + " ||| "
                                                                     "Available after {} beats\n".format(move.beats_left))
                    else:
                        move_str = (str(i) + ": " + str(move.name) + " ||| "
                                                                     "Available next beat\n")
                    move_str = colored(move_str, "red")
                available_moves += move_str
            print(available_moves)
            selected_move = int(input("Selection: "))
            for i, move in enumerate(player.known_moves):
                if i == selected_move:
                    if player.fatigue >= move.fatigue_cost and move.current_stage == 0:
                        player.current_move = move
                        player.current_move.user = player
                        if player.current_move.targeted:
                            target = None
                            if len(player.combat_list) > 1:
                                while target == None:
                                    print("Select a target: \n")
                                    for i, enemy in enumerate(player.combat_list):
                                        print(colored(str(i), "magenta") + ": " + colored(enemy.name, "magenta"))
                                    choice = int(input("Target: "))
                                    for i, enemy in enumerate(player.combat_list):
                                        if choice == i:
                                            target = enemy
                            else:
                                target = player.combat_list[0]
                            player.current_move.target = target
                        else:
                            player.current_move.target = player
                        player.current_move.cast(player)
                    elif player.fatigue < move.fatigue_cost:
                        cprint("Jean will need to rest a bit before he can do that.", "red")
                    elif move.current_stage == 3:
                        cprint("Jean's not yet ready to do that again.", "red")

        for move in player.known_moves: #advances moves one beat along the path toward cooldown zero.
            move.advance(player)

        for i, enemy in enumerate(player.combat_list):
            if not enemy.is_alive():
                print(colored(enemy.name, "magenta") + " exploded into fragments of light!")
                player.current_room.npcs_here.remove(enemy)
                player.combat_list.remove(enemy)
            else:
                if enemy.current_move == None:
                    enemy.target = player
                    enemy.select_move()
                    enemy.current_move.target = player
                    enemy.current_move.cast(enemy)

                for move in enemy.known_moves:
                    move.advance(enemy)

                enemy.cycle_states()

        player.combat_idle()

        player.cycle_states()

        time.sleep(0.5)
        beat += 1
    player.in_combat = False
    player.current_move = None