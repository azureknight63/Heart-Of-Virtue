"""Leveling mixin for Player — gain_exp, level_up, and skill learning."""

import random

from narration import cprint


class PlayerLevelingMixin:
    """Experience gain, leveling-up, and skill-tree learning for the Player."""

    def gain_exp(self, amt, exp_type="Basic", api_mode=False):
        """
        Give the player amt exp, then check to see if he gained a level and act accordingly
        Also adds exp to the designated skill tree subtype. All abilities under that subtype gain the exp and are
        learned if possible.
        EXP is always added to the "Basic" subtype regardless of the subtype declared.
        Pass api_mode=True from any non-combat API caller to use the non-blocking level-up path.
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
                        if not skill_is_already_learned and (
                            not hasattr(skill, "learnable_when") or skill.learnable_when(self)
                        ):
                            announce = True
                    else:
                        continue
                if announce:
                    cprint(
                        f"Jean may spend some of his earned exp to learn a new {exp_type} skill. "
                        f"Type SKILL to open the skill menu for details.",
                        "magenta",
                    )
                break

        if self.level < 100:
            self.exp += amt

        # Web-only: always level up via the non-blocking API path (the terminal
        # stat-allocation prompt has been removed). `api_mode` is retained for
        # caller compatibility.
        events = []
        while self.exp >= self.exp_to_level:
            events.append(self._level_up_api())
        return events

    def _level_up_api(self):
        """API-safe level up that mirrors terminal behavior without blocking for input.

        Returns a dict describing the level-up event for frontend display.
        """
        old_level = int(getattr(self, "level", 1) or 1)

        # Level up bookkeeping (match terminal behavior)
        self.level += 1
        self.exp -= self.exp_to_level
        self.exp_to_level = self.level * (165 - self.intelligence)

        # Apply random bonus increases to base stats
        bonuses = {}
        attributes = [
            ("strength_base", "Strength"),
            ("finesse_base", "Finesse"),
            ("speed_base", "Speed"),
            ("endurance_base", "Endurance"),
            ("charisma_base", "Charisma"),
            ("intelligence_base", "Intelligence"),
            ("faith_base", "Faith"),
        ]

        for attr, _label in attributes:
            bonus = random.randint(0, 2)
            if bonus:
                setattr(self, attr, getattr(self, attr) + bonus)
                bonuses[attr] = bonus

        # Award attribute points to distribute (same range as terminal mode)
        points = random.randint(6, 9)
        if not hasattr(self, "pending_attribute_points"):
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
