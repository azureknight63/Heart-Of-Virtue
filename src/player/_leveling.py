"""Leveling mixin for Player — gain_exp, level_up, and skill learning."""

import random
import time

import functions  # type: ignore
from neotermcolor import colored, cprint


class PlayerLevelingMixin:
    """Experience gain, leveling-up, and skill-tree learning for the Player."""

    def gain_exp(self, amt, exp_type="Basic"):
        """
        Give the player amt exp, then check to see if he gained a level and act accordingly
        Also adds exp to the designated skill tree subtype. All abilities under that subtype gain the exp and are
        learned if possible.
        EXP is always added to the "Basic" subtype regardless of the subtype declared.
        """

        if exp_type not in self.skill_exp:
            self.skill_exp[exp_type] = 0
        self.skill_exp[exp_type] += amt

        # Check through the players skill tree and announce if any skills may be learned
        announce = False
        for category, d in self.skilltree.subtypes.items():
            if category == exp_type:
                for skill, req in d.items():
                    if self.skill_exp[exp_type] >= req:
                        skill_is_already_learned = False
                        for known_skill in self.known_moves:
                            if skill.name == known_skill.name:
                                skill_is_already_learned = True
                                break
                        if not skill_is_already_learned:
                            announce = True
                    else:
                        continue
                if announce:
                    cprint(f"Jean may spend some of his earned exp to learn a new {exp_type} skill. "
                           f"Type SKILL to open the skill menu for details.", "magenta")
                break

        if self.level < 100:
            self.exp += amt

        # In API mode (frontend), do not prompt for input during level-up.
        if hasattr(self, '_combat_adapter'):
            events = []
            while self.exp >= self.exp_to_level:
                events.append(self._level_up_api())
            return events

        while self.exp >= self.exp_to_level:
            self.level_up()

        return None

    def _level_up_api(self):
        """API-safe level up that mirrors terminal behavior without blocking for input.

        Returns a dict describing the level-up event for frontend display.
        """
        old_level = int(getattr(self, 'level', 1) or 1)

        # Level up bookkeeping (match terminal behavior)
        self.level += 1
        self.exp -= self.exp_to_level
        self.exp_to_level = self.level * (150 - self.intelligence)

        # Apply random bonus increases to base stats
        bonuses = {}
        attributes = [
            ("strength_base", "Strength"),
            ("finesse_base", "Finesse"),
            ("speed_base", "Speed"),
            ("endurance_base", "Endurance"),
            ("charisma_base", "Charisma"),
            ("intelligence_base", "Intelligence"),
        ]

        for attr, _label in attributes:
            bonus = random.randint(0, 2)
            if bonus:
                setattr(self, attr, getattr(self, attr) + bonus)
                bonuses[attr] = bonus

        # Award attribute points to distribute (same range as terminal mode)
        points = random.randint(6, 9)
        if not hasattr(self, 'pending_attribute_points'):
            self.pending_attribute_points = 0
        self.pending_attribute_points += points

        return {
            "level_up": True,
            "old_level": old_level,
            "new_level": int(self.level),
            "points_awarded": int(points),
            "bonuses": bonuses,
        }

    def learn_skill(self, skill):
        """Add skill to known_moves if not already known. Returns the skill."""
        success = True
        for move in self.known_moves:
            if move.name == skill.name:
                success = False
                break
        if success:
            cprint("Jean learned {}!".format(skill.name), "magenta")
            self.known_moves.append(skill)
        return skill
        # if not success, Jean already knows the skill so no need to do anything!

    def level_up(self):
        """Terminal-mode level up: prints ASCII art, awards random stat increases, prompts for attribute allocation."""
        cprint(r"""
                         .'  '.____.' '.           ..
        '''';;;,~~~,,~~''   /  *    ,\  ''~~,,,..''  '.,_
                           / ,    *   \
                          /*    * .  * \
                         /  . *     ,   \
                        / *     ,  *   , \
                       /  .  *       *  . \
        """, "yellow")
        cprint("Jean has reached a new level!", "cyan")
        self.level += 1
        print(colored("He is now level {}".format(self.level)))
        self.exp -= self.exp_to_level
        self.exp_to_level = self.level * (150 - self.intelligence)
        cprint("{} exp needed for the next level.".format(self.exp_to_level - self.exp), "yellow")

        attributes = [
            ("strength_base", colored("Strength", "magenta"), 1),
            ("finesse_base", colored("Finesse", "magenta"), 2),
            ("speed_base", colored("Speed", "magenta"), 3),
            ("endurance_base", colored("Endurance", "magenta"), 4),
            ("charisma_base", colored("Charisma", "magenta"), 5),
            ("intelligence_base", colored("Intelligence", "magenta"), 6)
        ]

        for attr, attr_name, i in attributes:
            bonus = random.randint(0, 2)
            if bonus != 0:
                current_value = getattr(self, attr)
                setattr(self, attr, current_value + bonus)
                print(f"{attr_name} went up by {colored(str(bonus), 'yellow')}.")
                time.sleep(2)

        points = random.randint(6, 9)

        while points > 0:
            print(f'You have {colored(str(points), "yellow")} additional attribute points to distribute. '
                  f'Please select an attribute to increase:\n')
            for attr, attr_name, i in attributes:
                print(f'({i}) {attr_name} - {getattr(self, attr)}')

            selection = input("Selection: ")
            if not selection.isdigit() or (1 > int(selection) > 6):
                cprint("Invalid selection. You must enter a choice between 1 and 6.", "red")
                continue

            selection = int(selection)
            set_attr = ""
            set_attr_name = ""
            for attr, attr_name, i in attributes:
                if selection == i:
                    set_attr, set_attr_name = attr, attr_name
                    break

            amt = input(f"How many points would you like to allocate? ({points} available, 0 to cancel) ")
            if not amt.isdigit() or not (0 <= int(amt) <= points):
                cprint(f"Invalid selection. You must enter an amount between 0 and {points}.", "red")
                continue

            amt = int(amt)
            if amt > 0:
                setattr(self, set_attr, getattr(self, set_attr) + amt)
                points -= amt
                cprint(f"{set_attr_name} increased by {amt}!", "green")
