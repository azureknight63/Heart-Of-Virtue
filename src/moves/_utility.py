"""Universal utility moves: Check, Wait, Rest, UseItem, Attack, Disrupt,
StrategicInsight, MasterTactician."""

from src.narration import colored, cprint, narrate  # noqa: F401
import random  # noqa: F401
import math  # noqa: F401
import src.states as states  # noqa: F401
import src.functions as functions  # noqa: F401
import src.items as items  # noqa: F401
import src.positions as positions  # noqa: F401
from src.animations import animate_to_main_screen as animate  # noqa: F401
from src.combatant import MOVE_STAGE_PREP, move_in_progress
from ._base import (
    Move,
    PassiveMove,
    default_animations,
    _apply_carry_fatigue,
    _apply_blade_mastery_discount,
    _apply_to_hit_modifiers,
    apply_facing_damage,
    to_hit_chance,
    display_name_of,
)  # noqa: F401


class StrategicInsight(PassiveMove):
    """Passive move that enhances decision-making in combat.

    This is a passive move affecting the TacticalAdvisor feature.
    It cannot be selected during combat.
    """
    display_name = 'Strategic Insight'

    def __init__(self, user):
        description = (
            "Enhanced tactical awareness and strategic insight into enemy movements."
        )
        super().__init__(user, name="Strategic Insight", description=description)


class MasterTactician(PassiveMove):
    """Passive move representing mastery of tactical combat.

    This is a passive move affecting the TacticalAdvisor feature.
    It cannot be selected during combat.
    """
    display_name = 'Master Tactician'

    def __init__(self, user):
        description = "Mastery of tactical positioning, timing, and combat strategy."
        super().__init__(user, name="Master Tactician", description=description)


class Check(Move):  # player checks the battlefield (shows enemies, allies, distances)
    display_name = 'Check'
    web_animation = "pulse"

    def __init__(self, player):
        description = "Check your surroundings."
        prep = 0
        execute = 0
        recoil = 0
        cooldown = 0
        fatigue_cost = 0
        super().__init__(
            name="Check",
            description=description,
            xp_gain=0,
            current_stage=0,
            targeted=False,
            stage_beat=[prep, execute, recoil, cooldown],
            stage_announce=["Jean checks his surroundings.", "", "", ""],
            fatigue_cost=fatigue_cost,
            beats_left=execute,
            target=player,
            user=player,
            instant=True,
            category="Utility",
        )

    def prep(self, user):
        # In API mode, generate structured combatant data
        if hasattr(user, "_combat_adapter"):
            self._generate_api_check_data(user)

        # Check coordinate-based positioning if available
        if hasattr(user, "combat_position") and user.combat_position is not None:
            self._display_coordinate_info(user)
        else:
            # Fallback to legacy distance display
            self._display_legacy_info(user)

        # Don't block for input in API mode - info is captured in combat log
        if not hasattr(user, "_combat_adapter"):
            functions.await_input()

    def _generate_api_check_data(self, user):
        """Generate structured combatant data for API mode."""
        import src.positions as positions

        combatants_data = []

        # Collect all combatants (enemies and allies)
        all_combatants = []

        # Add enemies
        for enemy in user.combat_list:
            if not enemy.is_alive():
                continue
            all_combatants.append(
                {
                    "combatant": enemy,
                    "is_ally": False,
                    "distance": user.combat_proximity.get(enemy, 0),
                }
            )

        # Add allies (excluding the player)
        for ally in user.combat_list_allies:
            if ally != user:
                all_combatants.append(
                    {
                        "combatant": ally,
                        "is_ally": True,
                        "distance": user.combat_proximity.get(ally, 0),
                    }
                )

        # Sort by distance (closest first)
        all_combatants.sort(key=lambda x: x["distance"])

        # Generate data for each combatant
        for item in all_combatants:
            combatant = item["combatant"]
            distance = item["distance"]
            is_ally = item["is_ally"]

            combatant_info = {
                "name": combatant.name,
                "is_ally": is_ally,
                "distance": int(distance),
                "facing": None,
                "direction_from_player": None,
                "current_move": None,
            }

            # Get facing direction if available
            if (
                hasattr(combatant, "combat_position")
                and combatant.combat_position is not None
            ):
                combatant_info["facing"] = combatant.combat_position.facing.name

                # Calculate direction relative to player
                if (
                    hasattr(user, "combat_position")
                    and user.combat_position is not None
                ):
                    # Calculate angle from player to combatant
                    angle = positions.angle_to_target(
                        user.combat_position, combatant.combat_position
                    )

                    # Convert angle to cardinal direction
                    if 337.5 <= angle or angle < 22.5:
                        direction = "North"
                    elif 22.5 <= angle < 67.5:
                        direction = "Northeast"
                    elif 67.5 <= angle < 112.5:
                        direction = "East"
                    elif 112.5 <= angle < 157.5:
                        direction = "Southeast"
                    elif 157.5 <= angle < 202.5:
                        direction = "South"
                    elif 202.5 <= angle < 247.5:
                        direction = "Southwest"
                    elif 247.5 <= angle < 292.5:
                        direction = "West"
                    else:  # 292.5 <= angle < 337.5
                        direction = "Northwest"

                    combatant_info["direction_from_player"] = direction

            # Include every stage of the move in progress, including stage 0
            # (preparation), so the UI can distinguish preparing from idle.
            move = move_in_progress(combatant)
            if move is not None:
                combatant_info["current_move"] = move.name
                combatant_info["current_move_display_name"] = display_name_of(move)
                combatant_info["current_move_stage"] = getattr(move, "current_stage", None)

            combatants_data.append(combatant_info)

        # Store in combat adapter state for frontend retrieval
        if hasattr(user, "combat_adapter_state"):
            user.combat_adapter_state["check_data"] = combatants_data

        # Also add summary to combat log
        if hasattr(user, "combat_log"):
            user.combat_log.append(
                {
                    "round": getattr(user, "combat_beat", 0),
                    "message": f"Jean checks the battlefield... {len(combatants_data)} combatant(s) detected.",
                    "type": "info",
                }
            )

    def _display_coordinate_info(self, user):
        """Display coordinate-based positioning information."""
        for enemy, distance in user.combat_proximity.items():
            if hasattr(enemy, "combat_position") and enemy.combat_position is not None:
                # Display coordinate position and facing
                pos_str = f"({enemy.combat_position.x}, {enemy.combat_position.y})"
                facing_str = enemy.combat_position.facing.name

                # Score the user's angle against the enemy's guard. This asks
                # "where does Jean stand relative to where the enemy is
                # looking?", so it is the defender-first question that
                # positions.attack_angle_diff owns -- not the attacker's own
                # frontal arc. The hand-rolled angle_to_target(user, enemy)
                # form used here was the exact 180-degree opposite, so this
                # label called a genuine rear position "front".
                angle_diff = positions.attack_angle_diff(
                    user.combat_position, enemy.combat_position
                )

                # Determine relative direction (front/flank/rear)
                if angle_diff < 45:
                    direction = "front"
                    color = "red"
                elif angle_diff < 90:
                    direction = "flank"
                    color = "yellow"
                else:
                    direction = "rear"
                    color = "green"

                cprint(
                    "{} at {} facing {} is {} ft away ({}, {}-facing)".format(
                        enemy.name,
                        pos_str,
                        facing_str,
                        int(distance),
                        direction,
                        facing_str,
                    ),
                    color,
                )
            else:
                # Fallback if enemy lacks coordinate position
                cprint(
                    "{} is {} ft from {}".format(enemy.name, int(distance), user.name),
                    "green",
                )

            # Show ally positioning relative to enemies
            if user.combat_list_allies:
                for ally in user.combat_list_allies:
                    if (
                        ally.name != "Jean"
                        and hasattr(ally, "combat_position")
                        and ally.combat_position is not None
                    ):
                        if (
                            hasattr(enemy, "combat_position")
                            and enemy.combat_position is not None
                        ):
                            # Same defender-first question as the enemy line
                            # above, asked for the ally instead of Jean:
                            # where does the ally stand relative to where the
                            # enemy is looking?
                            ally_angle_diff = positions.attack_angle_diff(
                                ally.combat_position, enemy.combat_position
                            )

                            if ally_angle_diff < 45:
                                ally_dir = "front"
                            elif ally_angle_diff < 90:
                                ally_dir = "flank"
                            else:
                                ally_dir = "rear"

                            cprint(
                                "  → {} at ({}, {}) is {} ft away ({}-facing)".format(
                                    ally.name,
                                    ally.combat_position.x,
                                    ally.combat_position.y,
                                    int(ally.combat_proximity.get(enemy, 0)),
                                    ally_dir,
                                ),
                                "cyan",
                            )
                        else:
                            cprint(
                                "  → {} is {} ft away".format(
                                    ally.name,
                                    int(ally.combat_proximity.get(enemy, 0)),
                                ),
                                "cyan",
                            )

    def _display_legacy_info(self, user):
        """Display legacy distance-based information (fallback)."""
        # In API mode, add to combat log
        if hasattr(user, "_combat_adapter") and hasattr(user, "combat_log"):
            for enemy, distance in user.combat_proximity.items():
                user.combat_log.append(
                    {
                        "round": getattr(user, "combat_beat", 0),
                        "message": f"{enemy.name} is {int(distance)} ft from {user.name}",
                        "type": "info",
                    }
                )
        else:
            # Terminal mode - print to console
            for enemy, distance in user.combat_proximity.items():
                cprint(
                    "{} is {} ft from {}".format(enemy.name, int(distance), user.name),
                    "green",
                )
                if user.combat_list_allies:
                    for ally in user.combat_list_allies:
                        if ally.name != "Jean":
                            cprint(
                                "{} is {} ft from {}".format(
                                    enemy.name,
                                    int(ally.combat_proximity[enemy]),
                                    ally.name,
                                ),
                                "cyan",
                            )


class Wait(Move):  # player chooses how many beats he'd like to wait
    display_name = 'Wait'
    web_animation = "pulse"

    def __init__(self, player):
        description = "Wait for the right opportunity to make your move."
        prep = 0
        execute = 0
        recoil = 0
        cooldown = 0
        fatigue_cost = 0
        super().__init__(
            name="Wait",
            description=description,
            xp_gain=0,
            current_stage=0,
            targeted=False,
            stage_beat=[prep, execute, recoil, cooldown],
            stage_announce=["Jean is waiting.", "", "", ""],
            fatigue_cost=fatigue_cost,
            beats_left=execute,
            target=player,
            user=player,
            category="Utility",
        )
        # Flag to indicate this move needs duration input
        self.needs_duration = True
        self.duration = None

    def execute(self, player):
        # Duration comes from the combat adapter's select_number flow; default
        # to 5 beats when unset. (No terminal prompt.)
        duration = self.duration if self.duration is not None else 5
        self.stage_beat[2] = max(1, duration - 2)
        if hasattr(player, "combat_log"):
            player.combat_log.append(
                {
                    "round": getattr(player, "combat_beat", 0),
                    "message": f"Jean waits for {duration} beats...",
                    "type": "info",
                }
            )


class Attack(Move):  # basic attack function, always uses equipped weapon, player only
    display_name = 'Attack'
    web_animation = "attack"

    def __init__(self, player):
        description = "Strike at your enemy with your equipped weapon."
        # These are placeholder values only: evaluate() (called below, right after
        # super().__init__()) immediately recomputes stage_beat (prep/execute/
        # recoil/cooldown), fatigue_cost, mvrange, power, and base_damage_type from
        # the player's equipped weapon, and cast() resets beats_left at selection
        # time. Real formulas for all of these live in evaluate() only — they used
        # to be duplicated here with diverging numbers (e.g. cooldown was computed
        # both as `3 - endurance/10` here and `5 - endurance/10` in evaluate()),
        # which was dead, confusing, and never actually took effect.
        weapon = "fist"  # placeholder; evaluate() fills in the real weapon name
        prep = 1
        execute = 1
        recoil = 1
        cooldown = 1
        fatigue_cost = 10
        mvrange = (0, 5)
        super().__init__(
            name="Attack",
            description=description,
            xp_gain=1,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            mvrange=mvrange,
            stage_announce=[
                f"{player.name} winds up for a strike...",
                colored(f"{player.name} strikes with his " + weapon + "!", "green"),
                f"{player.name} braces himself as his weapon recoils.",
                "",
            ],
            fatigue_cost=fatigue_cost,
            beats_left=prep,
            target=None,
            user=player,
            category="Offensive",
        )
        self.power = 0
        self.evaluate()
        if hasattr(player, "eq_weapon") and player.eq_weapon:
            self.base_damage_type = items.get_base_damage_type(player.eq_weapon)
        else:
            self.base_damage_type = "crushing"  # default for unarmed
        self.animations = default_animations.copy()
        self.animations["e"] = "hit.gif"

    def viable(self):
        # Re-evaluate dynamic attributes so that newly equipped weapons update power, range, and announce text
        # before viability is determined. Previously, evaluate() was only called during advance(), meaning that
        # selecting Attack right after equipping a new weapon still used stale (fists) stats.
        try:
            self.evaluate()
        except Exception:
            # Fail-safe: do not block viability list if evaluation errors; original logic proceeds
            pass
        viability = False
        has_weapon = False
        enemy_near = False

        # Defensive check: ensure self.user is actually an NPC object with combat_proximity
        if not hasattr(self.user, "combat_proximity"):
            return False

        if self.user.eq_weapon:
            has_weapon = True
            range_min = self.mvrange[0]
            range_max = self.mvrange[1]
            for enemy, distance in self.user.combat_proximity.items():
                if range_min <= distance <= range_max:
                    enemy_near = True
                    break

        if has_weapon and enemy_near:
            viability = True
        return viability

    def evaluate(
        self,
    ):  # adjusts the move's attributes to match the current game state
        power = (
            self.user.eq_weapon.damage
            + (self.user.strength * self.user.eq_weapon.str_mod)
            + (self.user.finesse * self.user.eq_weapon.fin_mod)
        )

        prep = int(
            (40 + (self.user.eq_weapon.weight * 3)) / self.user.speed
        )  # starting prep of 5
        if prep < 1:
            prep = 1

        execute = 1

        cooldown = 5 - int(self.user.endurance / 10)
        if cooldown < 0:
            cooldown = 0

        recoil = int(1 + (self.user.eq_weapon.weight / 2))

        wt_mult = max(4, 10 - 0.2 * self.user.strength)
        fatigue_cost = int(
            math.ceil(
                70 + (self.user.eq_weapon.weight * wt_mult) - (2 * self.user.endurance)
            )
        )
        fatigue_cost = max(10, fatigue_cost)
        fatigue_cost = _apply_carry_fatigue(self.user, fatigue_cost)

        # BladeMastery passive: sword attacks cost less fatigue (issue #395).
        # Basic Attack hand-rolls its own math instead of routing through
        # Move.standard_evaluate_attack, so the discount that every sword-specific
        # move gets must be mirrored here too — otherwise a purchased passive
        # silently fails to affect the player's most-used move.
        fatigue_cost = _apply_blade_mastery_discount(self.user, fatigue_cost, 10)

        mvrange = self.user.eq_weapon.wpnrange

        weapon_name = self.user.eq_weapon.name
        self.stage_announce[1] = colored(
            f"{self.user.name} strikes with his " + weapon_name + "!", "green"
        )
        self.power = power
        self.stage_beat = [prep, execute, recoil, cooldown]
        self.fatigue_cost = fatigue_cost
        self.mvrange = mvrange
        self.base_damage_type = items.get_base_damage_type(self.user.eq_weapon)

    def execute(self, player):
        glance = False  # switch for determining a glancing blow
        self.prep_colors()
        narrate(self.stage_announce[1])

        # Face the target when attacking
        if (
            hasattr(self.user, "combat_position")
            and self.user.combat_position is not None
            and hasattr(self.target, "combat_position")
            and self.target.combat_position is not None
        ):
            self.user.combat_position.facing = positions.turn_toward(
                self.user.combat_position, self.target.combat_position
            )

        if hasattr(self, "animations"):
            if self.animations["e"] != "None":
                animate(self.animations["e"], self.stage_announce[1])
        if self.viable():
            hit_chance = to_hit_chance(self.user, self.target, floor=5)
        else:
            hit_chance = (
                -1
            )  # if attacking is no longer viable (enemy is out of range), then auto miss

        # Shared to-hit modifiers: facing/angle accuracy (#394) + HauntingPresence
        # (issue #395/#421 — mirrors Move.standard_execute_attack, which the
        # hand-rolled basic Attack path bypasses).
        hit_chance = _apply_to_hit_modifiers(self.user, self.target, hit_chance)

        roll = random.randint(0, 100)
        # Facing/angle damage (issue #394) — the same shared curve
        # standard_execute_attack applies, added here because the basic Attack
        # hand-rolls its damage line and so silently skipped it. Applied to
        # power pre-protection, so armour keeps its full bite from every angle.
        power = apply_facing_damage(self.user, self.target, self.power)
        damage = (
            (
                (power * functions.combat_resistance(self.target, self.base_damage_type))
                - self.target.protection
            )
            * player.heat
        ) * random.uniform(0.8, 1.2)
        if damage <= 0:
            damage = 0
        if hit_chance >= roll and hit_chance - roll < 10:  # glancing blow
            damage /= 2
            glance = True
        damage = int(damage)
        player.combat_exp["Basic"] += 10
        if hit_chance >= roll:  # a hit!
            if functions.check_parry(self.target):
                self.parry()
            else:
                self.hit(damage, glance)
        else:
            self.miss()
        self.user.fatigue -= self.fatigue_cost
        # Prevent negative fatigue
        if self.user.fatigue < 0:
            self.user.fatigue = 0


class Disrupt(Move):
    """Break an enemy's wind-up before it lands (the "read the telegraph" verb).

    Combat is a beat machine: every move walks prep -> execute -> recoil ->
    cooldown, and ``Move.beats_until_resolve()`` already tells the client how
    far an enemy's move is from resolving. Disrupt is the answer to that
    readout — a short, cheap strike whose payoff is entirely conditional on
    connecting while the target's move is still in the **prep** stage. Land it
    in that window and the wind-up is cancelled outright; land it at any other
    moment and it is just a weak poke.

    Design notes (the balance levers, in one place so a future edit can see
    what each one is holding up):

    * ``POWER_SCALE`` keeps the damage well under a basic Attack. Disrupt is a
      tempo tool: using it costs you the swing you would otherwise have taken,
      so spamming it on cooldown is strictly worse damage than attacking.
    * ``STAGE_BEATS`` prep is a flat 1 — deliberately *not* derived from weapon
      weight or speed, because a Basic skill has to behave the same for every
      build, and a reaction verb that arrives late is not a reaction verb.
    * The 12-beat cooldown rations it. A full Disrupt cycle (prep + execute +
      recoil + cooldown, plus the beat each stage transition costs) is ~20
      beats, whereas an interrupted enemy is only held up for its own move's
      cooldown before it starts winding a fresh one.
    * The **brace** rule is the actual anti-perma-lock guarantee, and it is
      structural rather than a matter of tuning. Cooldown alone is not enough:
      an enemy whose telegraph is long enough (King Slime's Tidal Surge preps
      for 13 beats, and the debug dummy's for 25) stays inside the window for
      most of Jean's cycle, so a player who reads perfectly could otherwise
      cancel that move *every single time* it was ever used. So a cancel
      leaves the target braced, and the next Disrupt that lands in its window
      only applies ``states.Staggered`` — which delays the target's **next**
      move rather than stopping the one it is winding, so the wind-up still
      resolves. Landing that stagger spends the brace, and the one after it
      cancels again. Cancel uptime is therefore capped at every other
      successful read no matter how long the telegraph or how the cooldown is
      later retuned. See ``tests/test_disrupt.py``:
      ``test_perfect_play_cannot_lock_even_a_very_slow_enemy``.
    * Cancel and stagger are alternatives, never simultaneous. Stacking a
      +5-prep debuff onto a full cancel would compound cycle-over-cycle into
      exactly the lock the brace exists to prevent.

    Its execute() rolls to hit through the plain default path — plain
    ``to_hit_chance(..., floor=5)`` plus the shared modifier chain, with no
    situational modifier interposed — so ``Move.preview_hit_chance`` is
    already correct for it and needs no override. To keep that true by
    construction rather than by comment, execute() *calls*
    ``preview_hit_chance`` for the number it rolls against, so the preview and
    the dice cannot drift apart.
    """

    display_name = 'Disrupt'
    web_animation = "quick_attack"

    #: prep, execute, recoil, cooldown.
    STAGE_BEATS = (1, 1, 2, 12)
    #: Fraction of a basic weapon swing's power. Low on purpose — see above.
    POWER_SCALE = 0.35
    #: Fatigue is ``BASE_FATIGUE - endurance``, floored at MIN_FATIGUE.
    BASE_FATIGUE = 30
    MIN_FATIGUE = 8
    #: Attribute Disrupt sets on a target it has just cancelled, so the next
    #: successful read staggers instead of cancelling. Stored on the combatant
    #: rather than in a state because the effect is Disrupt's own alternation
    #: bookkeeping, not something any other system reads, times out, or
    #: displays. Private-by-convention, like ``_cleave_instinct_pending``.
    BRACE_ATTR = "_disrupt_braced"

    def __init__(self, player):
        description = (
            "A short, sharp strike thrown into an enemy's wind-up. It does "
            "little damage, but if it connects while the target is still "
            "preparing a move, that move is broken and never lands. A "
            "target whose guard has just been broken braces against the "
            "next one, which staggers it instead."
        )
        prep, execute, recoil, cooldown = self.STAGE_BEATS
        super().__init__(
            name="Disrupt",
            description=description,
            xp_gain=3,
            current_stage=0,
            stage_beat=[prep, execute, recoil, cooldown],
            targeted=True,
            # Melee reach, fixed rather than taken from the weapon: a Basic
            # skill every build can buy must not quietly become a ranged
            # interrupt in an archer's hands.
            mvrange=(0, 5),
            stage_announce=["This", "will", "update", "dynamically"],
            fatigue_cost=self.MIN_FATIGUE,
            beats_left=prep,
            target=None,
            user=player,
            category="Offensive",
        )
        self.power = 0
        self.base_damage_type = "crushing"
        self.evaluate()

    def viable(self):
        """In range of a hostile. Deliberately *not* gated on anything being
        mid-prep: the read is the player's to make (and to get wrong), and
        gating viability on it would leak the answer into the move list.
        """
        if not hasattr(self.user, "combat_proximity"):
            return False
        range_min, range_max = self.mvrange
        return any(
            range_min <= distance <= range_max
            for _, distance in self._hostiles_in_proximity()
        )

    def evaluate(self):
        # Re-seed the timing every beat. Move.parry() does
        # `self.stage_beat[2] += 10` to stagger a parried attacker, and every
        # move built through standard_evaluate_attack has that erased by the
        # fresh list it assigns each beat. Disrupt builds its timing from a
        # constant instead, so without this the penalty ACCUMULATED -- recoil
        # growing 2, 12, 22, ... permanently, and pickled into the save with
        # known_moves. Re-seeding makes Disrupt behave like every other move.
        self.stage_beat = list(self.STAGE_BEATS)
        weapon = getattr(self.user, "eq_weapon", None) or items.Fists()
        power = (
            weapon.damage
            + (self.user.strength * weapon.str_mod)
            + (self.user.finesse * weapon.fin_mod)
        ) * self.POWER_SCALE
        self.power = max(0, int(power))
        self.base_damage_type = items.get_base_damage_type(weapon)
        fatigue_cost = max(self.MIN_FATIGUE, self.BASE_FATIGUE - self.user.endurance)
        self.fatigue_cost = _apply_carry_fatigue(self.user, fatigue_cost)
        self.refresh_announcements(self.user)

    def refresh_announcements(self, user):
        target_name = getattr(self.target, "name", "his opponent")
        self.stage_announce = [
            colored(f"{user.name} coils, watching for the opening...", "yellow"),
            colored(f"{user.name} darts in to break {target_name}'s rhythm!", "green"),
            f"{user.name} settles back onto his heels.",
            "",
        ]

    @staticmethod
    def _winding_move(target):
        """The target's move if it is still winding up, else ``None``.

        ``move_in_progress`` returns the combatant's ``current_move`` when one
        is selected and otherwise falls back to a move left in recoil or
        cooldown — neither of which is stage 0 — so a stage-0 result here
        always means a genuine, unresolved wind-up rather than an idle move
        sitting at its reset stage.
        """
        if target is None or not target.is_alive():
            return None
        move = move_in_progress(target)
        if move is None:
            return None
        if getattr(move, "current_stage", None) != MOVE_STAGE_PREP:
            return None
        return move

    @staticmethod
    def _beats_until_target_can_act(winding_move):
        """Beats before ``winding_move``'s owner can cast again.

        The target still owes the rest of its current stage plus every stage
        after it before the next ``cast()`` reads a Staggered penalty. Summing
        the remaining stages is deliberately generous -- overshooting costs
        nothing (the state expires unused), while undershooting is exactly the
        silent no-op this exists to prevent.
        """
        stage_beat = getattr(winding_move, "stage_beat", None) or []
        current = getattr(winding_move, "current_stage", 0) or 0
        left = getattr(winding_move, "beats_left", 0) or 0
        try:
            remaining = sum(
                int(b) for b in stage_beat[current + 1:] if isinstance(b, (int, float))
            )
            return max(states.STAGGERED_DEFAULT_BEATS, int(left) + remaining + 1)
        except (TypeError, ValueError):
            return states.STAGGERED_DEFAULT_BEATS

    def _reward_read(self, winding_move):
        """Pay out the correct read on a strike that landed inside the window.

        Cancels the wind-up outright unless the target is already braced from
        a previous cancel, in which case it staggers instead and spends the
        brace. Either way the read earns Basic exp — the player made the call
        correctly.
        """
        target = self.target
        move_name = display_name_of(winding_move)
        if getattr(target, self.BRACE_ATTR, False):
            setattr(target, self.BRACE_ATTR, False)
            # Staggered adds prep beats to the target's NEXT cast, so the move
            # being wound right now still resolves. That is the point: the
            # braced case has to be strictly weaker than a cancel.
            #
            # The duration has to outlive that wind-up. Staggered's default of
            # three beats expires while the target is still burning the move it
            # pushed through -- execute, recoil and cooldown all come first --
            # so the penalty was collected by nothing and every braced read was
            # a silent no-op. Derive it from the target's own remaining stage
            # beats instead, plus a beat of margin.
            beats = self._beats_until_target_can_act(winding_move)
            applied = functions.inflict(
                states.Staggered(target, beats_max=beats), target
            )
            if applied:
                cprint(
                    f"{target.name} absorbs the disruption and pushes through "
                    f"{move_name}, but is knocked off balance.",
                    "yellow",
                )
            else:
                # Stun-resistant target: the brace was still spent, so the
                # anti-lock alternation holds, but do not narrate an effect
                # that did not land.
                cprint(
                    f"{target.name} absorbs the disruption and pushes through "
                    f"{move_name} unshaken.",
                    "yellow",
                )
        else:
            # The same ``interrupted`` flag War Cry sets: ``Move.advance``
            # picks it up on the target's next beat, abandons whatever prep
            # progress was made, and drops the move straight into its normal
            # cooldown.
            winding_move.interrupted = True
            setattr(target, self.BRACE_ATTR, True)
            cprint(
                f"{target.name}'s {move_name} is broken before it lands!",
                "cyan",
            )
        self.user.combat_exp["Basic"] += 15

    def execute(self, player):
        self.refresh_announcements(player)
        narrate(self.stage_announce[1])

        if (
            hasattr(self.user, "combat_position")
            and self.user.combat_position is not None
            and hasattr(self.target, "combat_position")
            and self.target.combat_position is not None
        ):
            self.user.combat_position.facing = positions.turn_toward(
                self.user.combat_position, self.target.combat_position
            )

        self.prep_colors()

        # Snapshot the window before anything else resolves: whether the read
        # was correct is a fact about the instant Jean connects, not about
        # what the dice or the damage did afterwards.
        winding_move = self._winding_move(self.target)

        preview = self.preview_hit_chance(self.target)
        hit_chance = preview if preview is not None else -1
        roll = random.randint(0, 100)

        glance = False
        # Facing/angle damage (issue #394) — same shared curve as
        # standard_execute_attack, which Disrupt's hand-rolled damage line
        # bypasses. Applied to power pre-protection.
        power = apply_facing_damage(self.user, self.target, self.power)
        damage = (
            (
                (
                    power
                    * functions.combat_resistance(self.target, self.base_damage_type)
                )
                - self.target.protection
            )
            * getattr(player, "heat", 1.0)
        ) * random.uniform(0.8, 1.2)
        damage = max(0, damage)
        if hit_chance >= roll and hit_chance - roll < 10:  # glancing blow
            damage /= 2
            glance = True
        damage = int(damage)

        player.combat_exp["Basic"] += 5
        if hit_chance >= roll:  # a hit!
            if functions.check_parry(self.target):
                self.parry()
            else:
                self.hit(damage, glance)
                # A parried or missed Disrupt breaks nothing: the payoff is
                # the reward for a strike that actually connected inside the
                # window, not for pressing the button at the right time.
                if winding_move is not None and self.target.is_alive():
                    self._reward_read(winding_move)
        else:
            self.miss()

        self.user.fatigue = max(0, self.user.fatigue - self.fatigue_cost)


class Rest(Move):  # standard rest to restore fatigue.
    display_name = 'Rest'
    web_animation = "heal"

    def __init__(self, player):
        description = "Rest for a moment to restore fatigue."
        prep = 1
        execute = 1
        recoil = 2
        cooldown = 0
        fatigue_cost = 0
        super().__init__(
            name="Rest",
            description=description,
            xp_gain=0,
            current_stage=0,
            targeted=False,
            stage_beat=[prep, execute, recoil, cooldown],
            stage_announce=[
                "Jean relaxes his muscles for a moment.",
                colored("Jean is resting.", "green"),
                "",
                "",
            ],
            fatigue_cost=fatigue_cost,
            beats_left=execute,
            target=player,
            user=player,
        )

    def viable(self):
        viability = True
        if self.user.fatigue >= self.user.maxfatigue:
            viability = False
        return viability

    def execute(self, player):
        narrate(self.stage_announce[1])
        recovery_amt = int(
            math.ceil((player.maxfatigue * 0.4) * random.uniform(0.8, 1.2))
        )
        if recovery_amt > player.maxfatigue - player.fatigue:
            recovery_amt = player.maxfatigue - player.fatigue
        player.fatigue += recovery_amt
        cprint("{} recovered {} FP!".format(player.name, recovery_amt), "green")
        player.combat_exp["Basic"] += 2


class UseItem(Move):
    display_name = 'Use Item'
    web_animation = "pulse"

    def __init__(self, player):
        description = "Use an item from your inventory."
        prep = 1
        execute = 1
        recoil = 1
        cooldown = 0
        fatigue_cost = 0
        super().__init__(
            name="Use Item",
            description=description,
            xp_gain=0,
            current_stage=0,
            targeted=False,
            stage_beat=[prep, execute, recoil, cooldown],
            stage_announce=[
                f"{player.name} opens his bag.",
                "",
                f"{player.name} closes his bag.",
                "",
            ],
            fatigue_cost=fatigue_cost,
            beats_left=execute,
            target=player,
            user=player,
        )

    def viable(self):
        if not self.user.inventory:
            return False
        for item in self.user.inventory:
            if item.type in ("Consumable", "Special"):
                return True
        return False

    def execute(self, player):
        # In the web client, using an item in combat is driven by the
        # /inventory/use route (item.use directly, with range enforcement); the
        # terminal item-picker menu has been removed. Selecting this move just
        # opens/closes the bag (flavor via stage_announce).
        player.combat_exp["Basic"] += 1


class CrusaderOath(Move):
    """Jean swears a fighting oath, igniting desperate conviction.

    Voluntarily entering the Fervent state — a risk/reward move.
    Cannot be used while Hollowed (the oath requires faith to swear on).
    Long cooldown prevents chaining.
    """
    display_name = "Crusader's Oath"

    web_animation = "buff"

    def __init__(self, player):
        prep = 2
        execute = 1
        recoil = 3
        cooldown = 30
        fatigue_cost = 20
        super().__init__(
            name="Crusader's Oath",
            description=(
                "Swear a fighting oath and enter the Fervent state — "
                "striking harder, but paying for it in blood and fatigue."
            ),
            xp_gain=2,
            current_stage=0,
            targeted=False,
            stage_beat=[prep, execute, recoil, cooldown],
            stage_announce=[
                colored(
                    f"{player.name} steadies his breathing and begins to swear an oath.",
                    "yellow",
                ),
                colored(f"The fire of conviction ignites in {player.name}!", "red"),
                colored(
                    f"{player.name} feels the cost of the oath settling into his limbs.",
                    "yellow",
                ),
                "",
            ],
            fatigue_cost=fatigue_cost,
            beats_left=prep,
            target=player,
            user=player,
            category="Utility",
        )

    def viable(self):
        if not getattr(self.user, "in_combat", False):
            return False
        if any(getattr(s, "statustype", "") == "apathy" for s in self.user.states):
            return False
        if any(isinstance(s, states.Fervent) for s in self.user.states):
            return False
        p = self.user
        if p.faith < min(p.strength, p.finesse, p.speed, p.endurance, p.charisma):
            return False
        return True

    def execute(self, player):
        narrate(self.stage_announce[1])
        fervent = states.Fervent(player)
        functions.inflict(fervent, player, force=True)
        player.fatigue = max(0, player.fatigue - self.fatigue_cost)
        player.combat_exp["Basic"] += 2
