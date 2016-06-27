from termcolor import colored
from termcolor import cprint

def combat(player, enemy_list):
    """

    :param player:
    :param enemy_list: A list of enemies to engage in this combat loop.
    :return: Nothing is returned - this is simply a branch from the main game loop to handle combat.
    """
    beat = 0 # initialize the beat variable. Beats are "combat" turns but more granular - moves can take multiple beats and can be interrupted before completion
    heat = 1.0 # initialize the heat multiplier. This increases the damage of moves. The more the player can combo moves together without being hit, the higher this multiplier grows.
    while len(enemy_list) > 0 or player.hp > 0: #combat will loop until there are no aggro enemies or the player is dead
        cprint("BEAT " + str(beat), "yellow", "on_grey", "bold") #declare current Beat
        cprint("HEAT: " + (str(heat * 100)) + "%", "red", "on_grey", "bold") #declare current Heat
        cprint("FATIGUE: " + str(player.fatigue), "green", "on_grey", "bold") #declare current fatigue level
        while player.current_move == None: #the player must choose to do something
            print("What will you do?")
            for i, move in enumerate(player.known_moves):
                print(str(i) + ": " + move.name + " ||| F: " + move.fatigue_cost + ", CD: " + move.cooldown_left)
            selected_move = input("Selection ")
            for i, move in enumerate(player.known_moves):
                if i == selected_move:
                    if player.fatigue >= move.fatigue_cost & move.cooldown_left == 0:
                        player.current_move = move
                    elif player.fatigue < move.fatigue_cost:
                        cprint("You'll need to rest a bit before you can do that.", "red")
                    elif move.cooldown_left > 0:
                        cprint("You're not yet ready to do that again.", "red")
