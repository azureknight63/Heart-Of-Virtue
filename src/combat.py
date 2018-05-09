from termcolor import colored, cprint
import time, random, functions


def combat(player):
    """
    :param player:
    :param player.combat_list: A list of enemies to engage in this combat loop.
    :return: Nothing is returned - this is simply a branch from the main game loop to handle combat.
    """
    def process_npc(npc):  # when an NPC's turn comes up, perform these actions
        npc.cycle_states()
        if npc.combat_delay > 0:
            npc.combat_delay -= 1
        else:
            if npc.current_move is None:
                if not npc.friend:
                    npc.target = player.combat_list_allies[
                        random.randint(0, len(
                            player.combat_list_allies) - 1)]  # select a random target from the player's party
                else:
                    npc.target = player.combat_list[
                        random.randint(0, len(
                            player.combat_list) - 1)]  # select a random target from the enemy's party
                npc.select_move()
                npc.current_move.target = npc.target
                npc.current_move.cast(npc)
        get_moves = npc.known_moves[:]
        for move in get_moves:
            move.advance(npc)

    def synchronize_distances():
        '''
        Loops over all enemies in the combat list and updates their distances. If the enemy isn't in a proximity list, then it gets added.
        :return:
        '''
        for ally in player.combat_list_allies:
            remove_these = []
            for enemy in ally.combat_proximity:  # Remove any dead enemies
                if not enemy.is_alive:
                    remove_these.append(enemy)
            for enemy in remove_these:
                del ally.combat_proximity[enemy]
            for enemy in player.combat_list:
                remove_these = []
                for ally in enemy.combat_proximity:  # Remove any dead allies from combat proximity; this will only work for allies who can die, excluding Jean
                    if not ally.is_alive:
                        remove_these.append(ally)
                for ally in remove_these:
                    del enemy.combat_proximity[ally]
                if enemy in ally.combat_proximity:
                    enemy.combat_proximity[ally] = ally.combat_proximity[enemy]
                else:  # The enemy is not in the list, probably because it was added via an event mid-combat; so, let's add it!
                    distance = int(enemy.default_proximity * random.uniform(0.75, 1.25))
                    ally.combat_proximity[enemy] = enemy.combat_proximity[ally] = distance

        for enemy in player.combat_list:
            remove_these = []
            for ally in enemy.combat_proximity:
                if not ally.is_alive():
                    remove_these.append(ally)
            for ally in remove_these:
                del enemy.combat_proximity[ally]
            for ally in player.combat_list_allies:
                if ally not in enemy.combat_proximity:
                    distance = int(enemy.default_proximity * random.uniform(0.75, 1.25))
                    ally.combat_proximity[enemy] = enemy.combat_proximity[ally] = distance

    beat = 0  # initialize the beat variable. Beats are "combat" turns but more granular - moves can take multiple beats and can be interrupted before completion
    player.heat = 1.0  # initialize the heat multiplier. This increases the damage of moves. The more the player can combo moves together without being hit, the higher this multiplier grows.
    player.in_combat = True
    for ally in player.combat_list_allies:
        ally.in_combat = True
    while True:  # combat will loop until there are no aggro enemies or the player is dead
        #  Check for combat events and execute them once, if possible
        synchronize_distances()
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

        for friendly in player.combat_list_allies:
            functions.refresh_stat_bonuses(friendly)
        for enemy in player.combat_list:
            functions.refresh_stat_bonuses(enemy)

        #  Recovery / Entropy for HEAT
        if player.heat < 1:  # recovery
            amt = (1 - player.heat) / 20
            if amt < 0.001:
                amt = 0.001
            player.heat += amt
        elif player.heat > 1:  # entropy
            amt = (player.heat - 1) / 20
            if amt < 0.001:
                amt = 0.001
            player.heat -= amt

        while player.current_move is None: # the player must choose to do something
            beat_str = colored("BEAT: ", "blue") + colored(str(beat), "blue")
            heat_display = int(player.heat * 100)
            heat_str = colored("HEAT: ", "red") + colored(str(heat_display), "red") + colored("%", "red")
            print("\n" + beat_str + "                  " + heat_str)
            if beat == 0:
                player.fatigue = player.maxfatigue
            player.show_bars()
            print("\nWhat will you do?\n")
            available_moves = "\n"
            viable_moves = player.refresh_moves()
            for i, move in enumerate(viable_moves):
                if not move.current_stage == 3:
                    if move.fatigue_cost > 0:
                        if move.fatigue_cost > player.fatigue:
                            move_str = (str(i) + ": " + str(move.name) + " ||| F: " + str(move.fatigue_cost) + "\n")
                            move_str = colored(move_str, "red")
                        else:
                            move_str = (str(i) + ": " + str(move.name) + " ||| F: " + str(move.fatigue_cost) + "\n")
                    else:
                        move_str = (str(i) + ": " + str(move.name) + "\n")
                else:
                    if move.beats_left > 0:
                        move_str = (str(i) + ": " + str(move.name) + " ||| "
                                                                     "Available in {} beats\n".format(move.beats_left + 1))
                    else:
                        move_str = (str(i) + ": " + str(move.name) + " ||| "
                                                                     "Available next beat\n")
                    move_str = colored(move_str, "red")
                available_moves += move_str
            print(available_moves)
            selected_move = input("Selection: ")
            while not functions.is_input_integer(selected_move):  # only allow integers here
                cprint("Invalid selection.", "red", attrs=['bold'])
                selected_move = input("Selection: ")
            try:
                selected_move = int(selected_move)
            except:
                cprint("Invalid selection.", "red", attrs=['bold'])
            for i, move in enumerate(viable_moves):
                if i == selected_move:
                    if player.fatigue >= move.fatigue_cost and move.current_stage == 0:
                        player.current_move = move
                        player.current_move.user = player
                        if player.current_move.targeted:
                            target = None
                            acceptable_targets = []
                            min, max = player.current_move.mvrange
                            for enemy, distance in player.combat_proximity.items():
                                if enemy.is_alive:
                                    if min < distance < max:
                                        acceptable_targets.append((enemy, distance))
                                else:
                                    del player.combat_proximity[enemy]
                            if len(acceptable_targets) > 1:
                                acceptable_targets.sort(key=lambda tup: tup[1])  # sort acceptable_targets by distance
                                while target is None:
                                    print("Select a target: \n")
                                    for i, enemy in enumerate(acceptable_targets):
                                        print(colored(str(i), "magenta") + ": " +
                                              colored(enemy[0].name + " (" + str(enemy[1]) + "ft)", "magenta"))
                                    choice = input("Target: ")  # todo: clean this up >.<
                                    while not functions.is_input_integer(choice):
                                        cprint("Invalid selection!", "red")
                                        choice = input("Target: ")
                                    targeting_done = False
                                    while not targeting_done:
                                        for i, enemy in enumerate(acceptable_targets):
                                            if choice == i:
                                                target = enemy[0]
                                                targeting_done = True
                                                break
                                        if not targeting_done:
                                            choice = input("Target: ")
                                            while not functions.is_input_integer(choice):
                                                cprint("Invalid selection!", "red")
                                                choice = input("Target: ")
                            else:
                                target = acceptable_targets[0][0]
                            player.current_move.target = target
                        else:
                            player.current_move.target = player
                        player.current_move.cast(player)
                    elif player.fatigue < move.fatigue_cost:
                        cprint("Jean will need to rest a bit before he can do that.", "red")
                    elif move.current_stage == 3:
                        cprint("Jean's not yet ready to do that again.", "red")
            if hasattr(player.current_move, 'instant'):
                while player.current_move.instant:
                    player.current_move.advance(player)
                    if player.current_move is None:
                        break

        for move in player.known_moves:  # advances moves one beat along the path toward cooldown zero.
            move.advance(player)

        for i, ally in enumerate(player.combat_list_allies):
            if not ally == player:  # make sure you don't select Jean!
                if not ally.is_alive():
                    ally.before_death()  # if there is anything to process before death happens, do it now
                if not ally.is_alive():  # in case the npc got healed as part of before_death(), check again
                    print(colored(ally.name, "yellow", attrs="bold") + " has fallen in battle!")  # not sure yet if I want to change this
                    player.current_room.npcs_here.remove(ally)
                    player.combat_list_allies.remove(ally)
                else:
                    process_npc(ally)

        for i, enemy in enumerate(player.combat_list):
            if not enemy.is_alive():
                enemy.before_death()  # if there is anything to process before death happens, do it now
            if not enemy.is_alive():
                print(colored(enemy.name, "magenta") + " exploded into fragments of light!")
                player.current_room.npcs_here.remove(enemy)
                player.combat_list.remove(enemy)
                for ally in player.combat_list_allies:
                    if enemy in ally.combat_proximity:
                        del ally.combat_proximity[enemy]
            else:
                process_npc(enemy)

        player.combat_idle()

        player.cycle_states()

        time.sleep(0.5)
        beat += 1
        # print("### CURRENT BEAT: "+str(beat))

    #  AFTER COMBAT LOOP (VICTORY, ESCAPE, OR DEFEAT)
    player.in_combat = False
    player.current_move = None
    player.current_room.evaluate_events()