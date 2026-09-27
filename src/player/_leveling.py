"""Leveling mixin for Player — gain_exp, level_up, and skill learning."""

import random

from src import functions
from src.combatant import exp_needed_for_level  # type: ignore
from src.narration import cprint


#: The attributes a level-up distributes points across, and their display
#: labels. THE ENGINE OWNS THIS.
#:
#: It was written out three times: here inside ``_level_up_api``, and twice
#: more in ``GameService.allocate_level_up_points`` -- once as the set of keys
#: the route will accept and once as the list it randomises over. Adding an
#: eighth attribute to the engine therefore left the API silently refusing it
#: with "Invalid attribute", which is the architecture rule (the engine is the
#: source of truth; the API adapts) failing in the direction that is hardest to
#: notice, because nothing errors.
LEVEL_UP_ATTRIBUTES = (
    ("strength_base", "Strength"),
    ("finesse_base", "Finesse"),
    ("speed_base", "Speed"),
    ("endurance_base", "Endurance"),
    ("charisma_base", "Charisma"),
    ("intelligence_base", "Intelligence"),
    ("faith_base", "Faith"),
)

#: Just the attribute names, for callers that do not want the labels.
LEVEL_UP_ATTRIBUTE_NAMES = tuple(name for name, _label in LEVEL_UP_ATTRIBUTES)

#: Highest level ``gain_exp`` will climb to; ``apply_starting_level`` honours it.
LEVEL_CAP = 100


def _even_allocation(points, names):
    """Split ``points`` round-robin across ``names`` in the engine's order.

    Every attribute gets ``points // len(names)``; the remainder goes one
    point each to the FIRST attributes in ``LEVEL_UP_ATTRIBUTES`` order, so
    the outcome is reproducible for a given point total.
    """
    share, extra = divmod(points, len(names))
    return {
        name: share + (1 if index < extra else 0)
        for index, name in enumerate(names)
    }


def _player_allocation(points, names):
    """Spend nothing: every point stays pending for the player's LEVEL UP
    dialog, which the client opens once no story event is on screen (beta 2)."""
    return {}


#: Named policies for spending a starting level's points (issue #581). Each
#: maps ``(points, attribute_names) -> {name: amount}`` with the amounts
#: summing to at most ``points``; whatever a policy leaves unspent stays
#: pending for the player to spend in the LEVEL UP dialog. Add a
#: "combat-heavy" entry here and ``config_manager`` accepts it the same day --
#: the config validates against this registry, not a list of its own.
STARTING_LEVEL_ALLOCATION_POLICIES = {
    "even": _even_allocation,
    "player": _player_allocation,
}

#: The policy names ``starting_level_allocation`` may take.
STARTING_LEVEL_ALLOCATIONS = tuple(STARTING_LEVEL_ALLOCATION_POLICIES)


class PlayerLevelingMixin:
    """Experience gain, leveling-up, and skill-tree learning for the Player."""

    #: True while a starting level's points wait for the player to spend them;
    #: ``complete_starting_allocation`` acts on it once. Class-level so a
    #: player restored from an older save reads False.
    starting_allocation_pending = False

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

        if self.level < LEVEL_CAP:
            self.exp += amt

        # Web-only: always level up via the non-blocking API path (the terminal
        # stat-allocation prompt has been removed). `api_mode` is retained for
        # caller compatibility.
        events = []
        while self.level < LEVEL_CAP and self.exp >= self.exp_to_level:
            events.append(self._level_up_api())
        return events

    def recompute_exp_to_level(self):
        """Re-derive ``exp_to_level`` from the current level and intelligence.

        For stats written after construction (a config's ``[player]`` block):
        ``__init__`` fixes the first threshold at the default intelligence (#710).
        """
        self.exp_to_level = exp_needed_for_level(self.level, self.intelligence)

    def _level_up_api(self):
        """API-safe level up that mirrors terminal behavior without blocking for input.

        Returns a dict describing the level-up event for frontend display.
        """
        old_level = int(getattr(self, "level", 1) or 1)

        # Level up bookkeeping (match terminal behavior)
        self.level += 1
        self.exp -= self.exp_to_level
        self.recompute_exp_to_level()

        # Apply random bonus increases to base stats
        bonuses = {}

        for attr, _label in LEVEL_UP_ATTRIBUTES:
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

    def apply_starting_level(self, target_level, allocation="even"):
        """Climb to ``target_level`` and spend its attribute points by policy.

        The config-driven counterpart of ``starting_exp`` for a level-N start
        (issue #581). ``starting_exp`` cannot open a session at a higher level
        cleanly: each crossed boundary leaves 6-9 ``pending_attribute_points``
        and the client blocks on a LEVEL UP modal until they are spent. This
        path climbs through the same ``_level_up_api`` loop -- so the random
        per-level stat bonuses land exactly as they would in play -- then
        spends the points with the named ``allocation`` policy (see
        ``STARTING_LEVEL_ALLOCATION_POLICIES``), recomputes derived stats the
        way a manual allocation would, and starts Jean at full health and
        fatigue.

        A policy that spends every point (``even``) clears any pending
        level-up records, so no modal opens. One that leaves points (``player``)
        hands them to that modal on purpose: the climb's level-ups become
        ``pending_level_ups`` for it to list, and spending the last point
        restores health and fatigue (``complete_starting_allocation``).

        Progress toward the next level (``exp``) is preserved rather than
        debited, so a ``starting_exp`` below the first boundary still counts.
        Skill-tree exp is untouched: learnable skills are ``starting_exp``'s
        job. A target at or below the current level, or one that is not a
        positive integer, is a no-op that returns ``[]``.

        Returns the list of level-up event dicts, as ``gain_exp`` does.
        """
        policy_name = str(allocation or "").strip().lower()
        policy = STARTING_LEVEL_ALLOCATION_POLICIES.get(policy_name)
        if policy is None:
            raise ValueError(
                f"Unknown starting_level_allocation {allocation!r}; "
                f"expected one of {STARTING_LEVEL_ALLOCATIONS}"
            )
        try:
            target = int(target_level)
        except (TypeError, ValueError):
            return []
        target = min(target, LEVEL_CAP)

        exp_before = int(getattr(self, "exp", 0) or 0)
        events = []
        while int(getattr(self, "level", 1) or 1) < target:
            events.append(self._level_up_api())
        if not events:
            return []
        # _level_up_api debits exp_to_level per level; nothing was earned
        # here, so restore the pool rather than leave it negative.
        self.exp = exp_before

        self._spend_pending_attribute_points(policy)
        if self.pending_attribute_points:
            self.pending_level_ups = list(events)
            self.starting_allocation_pending = True
        elif getattr(self, "pending_level_ups", None):
            self.pending_level_ups = []

        functions.refresh_stat_bonuses(self)
        self.hp = self.maxhp
        self.fatigue = self.maxfatigue
        return events

    def complete_starting_allocation(self):
        """Restore health and fatigue once a starting level's points are spent.

        Strength raises max HP and endurance max fatigue, so the points
        ``apply_starting_level`` left to the player would otherwise open the
        game below full. Acts once, and only for those points: an in-play
        level-up heals nothing. The caller spends the last point and refreshes
        stat bonuses first, so the maxima are current.
        """
        if not self.starting_allocation_pending:
            return
        self.starting_allocation_pending = False
        self.hp = self.maxhp
        self.fatigue = self.maxfatigue

    def _spend_pending_attribute_points(self, policy):
        """Spend pending points via ``policy`` (see the registry above).

        Mirrors the explicit branch of ``GameService.allocate_level_up_points``
        -- the ``*_base`` attribute is raised and the pending pool debited --
        without the per-request validation. Points the policy leaves stay
        pending. The caller refreshes stat bonuses. Returns
        ``{attribute: amount}`` for what was spent.
        """
        points = int(getattr(self, "pending_attribute_points", 0) or 0)
        if points <= 0:
            return {}
        shares = policy(points, LEVEL_UP_ATTRIBUTE_NAMES)
        spent = {}
        for name, amount in shares.items():
            amount = int(amount)
            if amount <= 0:
                continue
            setattr(self, name, int(getattr(self, name, 0) or 0) + amount)
            spent[name] = amount
        self.pending_attribute_points = points - sum(spent.values())
        return spent

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
