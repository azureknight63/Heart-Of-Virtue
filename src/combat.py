from neotermcolor import colored, cprint
import time
import random

from src.functions import refresh_stat_bonuses, is_input_integer, await_input


def combat(player):
    """
    :param player:
    :attr player.combat_list: A list of enemies to engage in this combat loop.
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
                if (npc.current_move is not None and hasattr(npc.current_move, "cast") and
                        callable(getattr(npc.current_move, "cast"))):
                    npc.current_move.cast()
        get_moves = npc.known_moves[:]
        if (npc.current_move is not None) and (npc.current_move not in get_moves):  # this will handle dynamically
            # added moves (as a result from a state or low fatigue)
            get_moves.append(npc.current_move)
        for each_move in get_moves:
            each_move.advance(npc)

    def synchronize_distances():
        """
        Loops over all enemies in the combat list and updates their distances. If the enemy isn't in a proximity list,
        then it gets added.
        """
        for each_ally in player.combat_list_allies:
            remove_these = []
            for each_enemy in each_ally.combat_proximity:  # Remove any dead enemies
                if not each_enemy.is_alive:
                    remove_these.append(each_enemy)
            for each_enemy in remove_these:
                del each_ally.combat_proximity[each_enemy]
            for each_enemy in player.combat_list:
                remove_these = []
                for each_ally_in_prox in each_enemy.combat_proximity:  # Remove any dead allies from combat proximity;
                    # this will only work for allies who can die, excluding Jean
                    if not each_ally.is_alive:
                        remove_these.append(each_ally_in_prox)
                for each_ally_that_died in remove_these:
                    del each_enemy.combat_proximity[each_ally_that_died]
                if each_enemy in each_ally.combat_proximity:
                    each_enemy.combat_proximity[each_ally] = each_ally.combat_proximity[each_enemy]
                else:  # The enemy is not in the list, probably because it was added via an event mid-combat;
                    # so, let's add it!
                    each_distance = int(each_enemy.default_proximity * random.uniform(0.75, 1.25))
                    each_ally.combat_proximity[each_enemy] = each_enemy.combat_proximity[each_ally] = each_distance

        for each_enemy in player.combat_list:
            remove_these = []
            for each_ally in each_enemy.combat_proximity:
                if not each_ally.is_alive():
                    remove_these.append(each_ally)
            for each_ally in remove_these:
                del each_enemy.combat_proximity[each_ally]
            for each_ally in player.combat_list_allies:
                if each_ally not in each_enemy.combat_proximity:
                    each_distance = int(each_enemy.default_proximity * random.uniform(0.75, 1.25))
                    each_ally.combat_proximity[each_enemy] = each_enemy.combat_proximity[each_ally] = each_distance

    def check_for_dead_enemy(this_enemy, skip_enemy_actions=False):
        if not this_enemy.is_alive():
            this_enemy.die()
        if not this_enemy.is_alive():  # check again in case some pre-death sequence saved the NPC
            player.current_room.npcs_here.remove(this_enemy)
            player.combat_list.remove(this_enemy)
            for each_ally in player.combat_list_allies:
                if this_enemy in each_ally.combat_proximity:
                    del each_ally.combat_proximity[this_enemy]
        elif not skip_enemy_actions:
            process_npc(this_enemy)

    beat = 0  # initialize the beat variable. Beats are "combat" turns but more granular - moves can take multiple
    # beats and can be interrupted before completion
    player.heat = 1.0  # initialize the heat multiplier. This increases the damage of moves. The more the player
    # can combo moves together without being hit, the higher this multiplier grows.
    player.in_combat = True

    for enemy in player.combat_list:
        check_for_dead_enemy(enemy, True)

    # Reset all moves for all combatants
    for ally in player.combat_list_allies:
        ally.in_combat = True
        for move in ally.known_moves:
            move.current_stage = 0
            move.beats_left = 0
    for enemy in player.combat_list:
        for move in enemy.known_moves:
            move.current_stage = 0
            move.beats_left = 0

    while True:  # combat will loop until there are no aggro enemies or the player is dead
        #  Check for combat events and execute them once, if possible
        synchronize_distances()
        if len(player.combat_events) > 0:  # first check combat events. This is higher in case, for example,
            # an event is to fire upon player or enemy death
            for event in player.combat_events:
                event.check_combat_conditions()

        if not player.is_alive():
            player.death()
            break

        if len(player.combat_list) == 0:
            print("Victory!")
            player.fatigue = player.maxfatigue
            gained_exp = ''
            for subtype, value in player.combat_exp.items():
                gained_exp += "{0:<10}:{1:>6}\n".format(subtype, int(value))
            print("Jean gained exp in the following: \n\n{}".format(gained_exp))
            for subtype, value in player.combat_exp.items():
                player.gain_exp(int(value), exp_type=subtype)
                player.combat_exp[subtype] = 0
            break

        #  at this point, the player is alive and at least one enemy remains
        for friendly in player.combat_list_allies:
            refresh_stat_bonuses(friendly)
        for enemy in player.combat_list:
            refresh_stat_bonuses(enemy)

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

        while player.current_move is None:  # the player must choose to do something
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
                                                                     "Available in {} beats\n".format(
                            move.beats_left + 1))
                    else:
                        move_str = (str(i) + ": " + str(move.name) + " ||| "
                                                                     "Available next beat\n")
                    move_str = colored(move_str, "red")
                available_moves += move_str
            print(available_moves)
            selected_move = input("Selection: ")
            while not is_input_integer(selected_move):  # only allow integers here
                cprint("Invalid selection.", "red", attrs=['bold'])
                selected_move = input("Selection: ")
            try:
                selected_move = int(selected_move)
            except SyntaxError:
                cprint("Invalid selection.", "red", attrs=['bold'])
            for i, move in enumerate(viable_moves):
                if i == selected_move:
                    if player.fatigue >= move.fatigue_cost and move.current_stage == 0:
                        player.current_move = move
                        player.current_move.user = player
                        if player.current_move.targeted:
                            target = None
                            acceptable_targets = []
                            range_min, range_max = player.current_move.mvrange
                            if player.current_move.name == "Shoot Bow":  # if the player is shooting his bow,
                                # overwrite max to include decaying range
                                range_max = player.eq_weapon.range_base + (100 / player.eq_weapon.range_decay)
                            for enemy, distance in player.combat_proximity.items():
                                if enemy.is_alive:
                                    if range_min <= distance <= range_max:
                                        acceptable_targets.append((enemy, distance))
                                else:
                                    del player.combat_proximity[enemy]
                            if not player.current_move.verbose_targeting:
                                if len(acceptable_targets) > 1:
                                    acceptable_targets.sort(key=lambda tup: tup[1])  # sort acceptable_targets
                                    # by distance
                                    while target is None:
                                        print("Select a target: \n")
                                        for index, enemy in enumerate(acceptable_targets):
                                            print(colored(str(index), "magenta") + ": " +
                                                  colored(enemy[0].name + " (" + str(enemy[1]) + "ft)", "magenta"))
                                        cprint("x: Cancel", "magenta")
                                        choice = input("Target: ")
                                        if choice.lower() == "x":
                                            player.current_move = None
                                            break
                                        if not is_input_integer(choice):
                                            cprint("Invalid selection!", "red")
                                            continue
                                        choice = int(choice)
                                        if choice > len(acceptable_targets):
                                            cprint("Invalid selection!", "red")
                                            continue
                                        for index, enemy in enumerate(acceptable_targets):
                                            if choice == index:
                                                target = enemy[0]
                                else:
                                    target = acceptable_targets[0][0]
                                if player.current_move:
                                    player.current_move.target = target
                            else:  # verbose targeting is enabled for this move
                                acceptable_targets.sort(key=lambda tup: tup[1])  # sort acceptable_targets by distance
                                while target is None:
                                    print("Select a target: \n")
                                    for index, enemy in enumerate(acceptable_targets):
                                        print(colored(str(index), "magenta") + ": " +
                                              colored("{} ({}ft; {}%)".format(enemy[0].name, str(enemy[1]),
                                                                              player.current_move.calculate_hit_chance(
                                                                                  enemy[0])), "cyan"))
                                    choice = input("Target: ")
                                    if not is_input_integer(choice):
                                        cprint("Invalid selection!", "red")
                                        continue
                                    choice = int(choice)
                                    if choice > len(acceptable_targets):
                                        cprint("Invalid selection!", "red")
                                        continue
                                    for index, enemy in enumerate(acceptable_targets):
                                        if choice == index:
                                            target = enemy[0]
                                if player.current_move:
                                    player.current_move.target = target
                        else:
                            player.current_move.target = player
                        player.current_move.cast()
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
                    ally.die()
                if not ally.is_alive():  # check again in case some pre-death sequence saved the NPC
                    print(colored(ally.name, "yellow", attrs="bold") + " has fallen in battle!")
                    # not sure yet if I want to change this
                    player.current_room.npcs_here.remove(ally)
                    player.combat_list_allies.remove(ally)
                else:
                    process_npc(ally)

        for enemy in player.combat_list:
            check_for_dead_enemy(enemy)  # will process the enemy's actions if it's alive

        player.combat_idle()

        player.cycle_states()

        time.sleep(0.5)
        beat += 1
        # print("### CURRENT BEAT: "+str(beat))

    #  AFTER COMBAT LOOP (VICTORY, ESCAPE, OR DEFEAT)
    for status in player.states:
        if not status.persistent:
            player.states.remove(status)
    await_input()
    player.in_combat = False
    player.current_move = None
    player.current_room.evaluate_events()
