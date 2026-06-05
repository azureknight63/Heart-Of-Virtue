"""Mastery moves — one per stat. Unlock when the stat exceeds 30 and is the player's highest."""

from neotermcolor import colored, cprint
import random
import states
import functions
from ._base import Move, _ensure_weapon_exp


def _all_stats(p):
    return [p.strength, p.finesse, p.speed, p.endurance, p.charisma, p.intelligence, p.faith]


def _is_highest(p, stat_val):
    return stat_val == max(_all_stats(p))


class Pulverize(Move):
    """Strength mastery: devastating overhead blow that ignores all protection."""

    def __init__(self, player):
        super().__init__(
            name="Pulverize",
            description=(
                "A thunderous overhead blow that shatters armor entirely and leaves the target "
                "reeling with resonant damage. Only available when Strength is your dominant stat."
            ),
            xp_gain=3,
            current_stage=0,
            targeted=True,
            stage_beat=[2, 1, 4, 35],
            stage_announce=[
                colored(f"{player.name} raises his weapon high, drawing on every ounce of strength.", "red"),
                colored(f"{player.name} drives down a crushing blow!", "red"),
                colored(f"{player.name} steadies himself after the devastating strike.", "yellow"),
                "",
            ],
            fatigue_cost=90,
            beats_left=2,
            target=player,
            user=player,
            category="Mastery",
            mvrange=(0, 5),
        )

    def learnable_when(self, player):
        return player.strength > 30 and _is_highest(player, player.strength)

    def viable(self):
        if not getattr(self.user, "in_combat", False):
            return False
        return _is_highest(self.user, self.user.strength)

    def execute(self, player):
        self.prep_colors()
        print(self.stage_announce[1])
        target = self.target
        hit_chance = max(5, int(98 - target.finesse + player.finesse * 0.7 + player.intelligence * 0.3))
        roll = random.randint(0, 100)
        power = int(player.eq_weapon.damage * 1.8 + player.strength * 3.0)
        # Ignores ALL protection — no protection subtraction
        damage = int(
            power * target.resistance.get("crushing", 1.0) * player.heat * random.uniform(0.8, 1.2)
        )
        damage = max(0, damage)
        _ensure_weapon_exp(player)
        player.combat_exp[player.eq_weapon.subtype] += 5
        player.combat_exp["Basic"] += 5
        player.fatigue = max(0, player.fatigue - self.fatigue_cost)
        if hit_chance >= roll:
            if functions.check_parry(target):
                self.parry()
            else:
                self.hit(damage, False)
                functions.inflict(states.Resonant(target), target, force=True)
        else:
            self.miss()


class KillingPrecision(Move):
    """Finesse mastery: surgically unerring strike that never misses."""

    def __init__(self, player):
        super().__init__(
            name="Killing Precision",
            description=(
                "A surgically precise thrust that never misses, ignores 80% of armor, "
                "and ignites your heat. Only available when Finesse is your dominant stat."
            ),
            xp_gain=3,
            current_stage=0,
            targeted=True,
            stage_beat=[1, 1, 2, 30],
            stage_announce=[
                colored(f"{player.name} centres his breathing and locates the gap.", "cyan"),
                colored(f"{player.name} drives a perfect, unerring strike!", "cyan"),
                colored(f"{player.name} withdraws, composure intact.", "yellow"),
                "",
            ],
            fatigue_cost=75,
            beats_left=1,
            target=player,
            user=player,
            category="Mastery",
            mvrange=(0, 5),
        )

    def learnable_when(self, player):
        return player.finesse > 30 and _is_highest(player, player.finesse)

    def viable(self):
        if not getattr(self.user, "in_combat", False):
            return False
        return _is_highest(self.user, self.user.finesse)

    def execute(self, player):
        self.prep_colors()
        print(self.stage_announce[1])
        target = self.target
        power = int(player.eq_weapon.damage * 1.5 + player.finesse * 2.5)
        # Only 20% of protection applies
        damage = int(
            (power * target.resistance.get("piercing", 1.0) - target.protection * 0.2)
            * player.heat * random.uniform(0.8, 1.2)
        )
        damage = max(1, damage)
        _ensure_weapon_exp(player)
        player.combat_exp[player.eq_weapon.subtype] += 5
        player.combat_exp["Basic"] += 5
        player.fatigue = max(0, player.fatigue - self.fatigue_cost)
        # Always hits — no roll, but parry can still work
        if functions.check_parry(target):
            self.parry()
        else:
            self.hit(damage, False)
            player.change_heat(1.5)


class LightningAssault(Move):
    """Speed mastery: three rapid strikes; Disoriented if all land."""

    def __init__(self, player):
        super().__init__(
            name="Lightning Assault",
            description=(
                "Three consecutive strikes so fast they blur into one lethal instant. "
                "If all three land, the target is left Disoriented. "
                "Only available when Speed is your dominant stat."
            ),
            xp_gain=3,
            current_stage=0,
            targeted=True,
            stage_beat=[1, 1, 1, 30],
            stage_announce=[
                colored(f"{player.name} shifts his weight and explodes forward.", "cyan"),
                colored(f"{player.name} unleashes a blinding flurry of blows!", "cyan"),
                colored(f"{player.name} resets his stance.", "yellow"),
                "",
            ],
            fatigue_cost=70,
            beats_left=1,
            target=player,
            user=player,
            category="Mastery",
            mvrange=(0, 5),
        )

    def learnable_when(self, player):
        return player.speed > 30 and _is_highest(player, player.speed)

    def viable(self):
        if not getattr(self.user, "in_combat", False):
            return False
        return _is_highest(self.user, self.user.speed)

    def execute(self, player):
        self.prep_colors()
        print(self.stage_announce[1])
        target = self.target
        hit_chance = max(5, int(98 - target.finesse + player.finesse * 0.7 + player.intelligence * 0.3))
        _ensure_weapon_exp(player)
        player.combat_exp[player.eq_weapon.subtype] += 5
        player.combat_exp["Basic"] += 5
        player.fatigue = max(0, player.fatigue - self.fatigue_cost)
        hits_landed = 0
        for _ in range(3):
            roll = random.randint(0, 100)
            power = int(player.eq_weapon.damage * 0.55 + player.speed * 0.75)
            damage = int(
                (power * target.resistance.get("slashing", 1.0) - target.protection)
                * player.heat * random.uniform(0.8, 1.2)
            )
            damage = max(0, damage)
            if hit_chance >= roll:
                if functions.check_parry(target):
                    self.parry()
                else:
                    self.hit(damage, False)
                    hits_landed += 1
                    if not target.is_alive():
                        break
            else:
                self.miss()
        if hits_landed == 3:
            functions.inflict(states.Disoriented(target), target, force=True)
            cprint(f"{target.name} is left reeling from the relentless assault!", "yellow")


class Ironhide(Move):
    """Endurance mastery: purge ailments, recover HP and fatigue."""

    def __init__(self, player):
        super().__init__(
            name="Ironhide",
            description=(
                "Dig in with sheer grit — heal 30% of max HP, purge all active ailments, "
                "and restore 60 fatigue. "
                "Only available when Endurance is your dominant stat."
            ),

            xp_gain=3,
            current_stage=0,
            targeted=False,
            stage_beat=[1, 1, 1, 40],
            stage_announce=[
                colored(f"{player.name} sets his jaw and braces against the pain.", "yellow"),
                colored(f"{player.name} refuses to fall — sheer will closes his wounds!", "yellow"),
                colored(f"{player.name} exhales, tension bleeding out of his frame.", "yellow"),
                "",
            ],
            fatigue_cost=25,
            beats_left=1,
            target=player,
            user=player,
            category="Mastery",
        )

    def learnable_when(self, player):
        return player.endurance > 30 and _is_highest(player, player.endurance)

    def viable(self):
        if not getattr(self.user, "in_combat", False):
            return False
        return _is_highest(self.user, self.user.endurance)

    def execute(self, player):
        print(self.stage_announce[1])
        heal = int(player.maxhp * 0.30)
        player.hp = min(player.hp + heal, player.maxhp)
        cprint(f"{player.name} recovers {heal} HP!", "green")
        # Purge negative ailment types
        negative_types = {"poison", "stun", "stone", "disoriented", "enflamed"}
        removed = [s for s in player.states if getattr(s, "statustype", "") in negative_types]
        for state in removed:
            player.states.remove(state)
            if hasattr(state, "on_removal"):
                try:
                    state.on_removal(player)
                except Exception:
                    pass
        if removed:
            cprint(f"All ailments purged from {player.name}!", "green")
        player.fatigue = min(player.fatigue + 60, player.maxfatigue)
        player.combat_exp["Basic"] += 5
        player.fatigue = max(0, player.fatigue - self.fatigue_cost)
        functions.refresh_stat_bonuses(player)


class WarCry(Move):
    """Charisma mastery: interrupts all winding enemy moves and stuns for 1 beat."""

    def __init__(self, player):
        super().__init__(
            name="War Cry",
            description=(
                "A thunderous battle command that interrupts every enemy's winding move "
                "and stuns the entire field for one beat. "
                "Only available when Charisma is your dominant stat."
            ),
            xp_gain=3,
            current_stage=0,
            targeted=False,
            stage_beat=[1, 1, 2, 30],
            stage_announce=[
                colored(f"{player.name} draws breath for a battle command.", "magenta"),
                colored(f"{player.name} unleashes a war cry that shakes the field!", "magenta"),
                colored(f"{player.name} surveys the stunned field.", "yellow"),
                "",
            ],
            fatigue_cost=60,
            beats_left=1,
            target=player,
            user=player,
            category="Mastery",
        )

    def learnable_when(self, player):
        return player.charisma > 30 and _is_highest(player, player.charisma)

    def viable(self):
        if not getattr(self.user, "in_combat", False):
            return False
        return _is_highest(self.user, self.user.charisma)

    def execute(self, player):
        print(self.stage_announce[1])
        affected = 0
        for enemy in list(getattr(player, "combat_list", [])):
            if not enemy.is_alive():
                continue
            # Interrupt any move in prep or execute stage
            cm = getattr(enemy, "current_move", None)
            if cm is not None and getattr(cm, "current_stage", -1) in (0, 1):
                cm.interrupted = True
            # Apply brief stun (beats_max=2 gives 1 effective skip of move selection)
            functions.inflict(states.WarCryStunned(enemy), enemy, force=True)
            affected += 1
        if affected:
            cprint(f"{affected} {'enemy' if affected == 1 else 'enemies'} recoil from the war cry!", "magenta")
        player.combat_exp["Basic"] += 5
        player.fatigue = max(0, player.fatigue - self.fatigue_cost)


class SecretPlans(Move):
    """Intelligence mastery: +30% speed and damage for player and all allies; resets cooldowns."""

    def __init__(self, player):
        super().__init__(
            name="Secret Plans",
            description=(
                "Reveal the hidden agenda. Jean and all allies gain +30% speed and damage "
                "for 25 beats, and all move cooldowns reset immediately. "
                "Only available when Intelligence is your dominant stat."
            ),
            xp_gain=3,
            current_stage=0,
            targeted=False,
            stage_beat=[2, 1, 2, 50],
            stage_announce=[
                colored(f"{player.name} reads the field and pieces together the advantage.", "cyan"),
                colored(f"{player.name} puts the plan into motion!", "cyan"),
                colored(f"The plan is set. {player.name} stands ready.", "yellow"),
                "",
            ],
            fatigue_cost=75,
            beats_left=2,
            target=player,
            user=player,
            category="Mastery",
        )

    def learnable_when(self, player):
        return player.intelligence > 30 and _is_highest(player, player.intelligence)

    def viable(self):
        if not getattr(self.user, "in_combat", False):
            return False
        return _is_highest(self.user, self.user.intelligence)

    def execute(self, player):
        print(self.stage_announce[1])
        targets = [player] + list(getattr(player, "combat_list_allies", []))
        for entity in targets:
            if not entity.is_alive():
                continue
            functions.inflict(states.SecretPlansState(entity), entity, force=True)
            # Reset cooldowns: set beats_left = 0 on all moves in cooldown stage
            for move in getattr(entity, "known_moves", []):
                if getattr(move, "current_stage", -1) == 3:
                    move.beats_left = 0
        cprint(f"Secret Plans activated — {len(targets)} combatant(s) surging!", "cyan")
        player.combat_exp["Basic"] += 5
        player.fatigue = max(0, player.fatigue - self.fatigue_cost)


class BloodOfMartyrs(Move):
    """Faith mastery: absorb all damage for 40 beats, then detonate for 2× absorbed."""

    def __init__(self, player):
        super().__init__(
            name="Blood of Martyrs",
            description=(
                "Take every blow for 40 beats — absorbing all incoming damage. "
                "Then unleash a map-wide pure energy blast equal to twice the amount absorbed. "
                "Only available when Faith is your dominant stat."
            ),
            xp_gain=3,
            current_stage=0,
            targeted=False,
            # 40-beat prep (absorbing), 1-beat execute (detonation), 5 recoil, 55 cooldown
            stage_beat=[40, 1, 5, 55],
            stage_announce=[
                colored(f"{player.name} opens himself to every blow, faith holding him upright.", "yellow"),
                colored(f"{player.name} releases the gathered pain as a wave of holy fire!", "yellow"),
                colored(f"{player.name} sinks to one knee, spent but unbroken.", "yellow"),
                "",
            ],
            fatigue_cost=40,
            beats_left=40,
            target=player,
            user=player,
            category="Mastery",
        )
        self._absorb_state = None

    def learnable_when(self, player):
        return player.faith > 30 and _is_highest(player, player.faith)

    def viable(self):
        if not getattr(self.user, "in_combat", False):
            return False
        # Cannot stack — block if absorption is already active
        if any(getattr(s, "_absorbing", False) for s in getattr(self.user, "states", [])):
            return False
        return _is_highest(self.user, self.user.faith)

    def cast(self):
        """Override cast to apply the absorption state before the prep phase begins."""
        super().cast()
        absorb_state = states.BloodOfMartyrsState(self.user)
        result = functions.inflict(absorb_state, self.user, force=True)
        # Keep a reference so execute() can read the absorbed total
        self._absorb_state = result if result else absorb_state

    def execute(self, player):
        print(self.stage_announce[1])
        # Collect absorbed damage from the state
        absorbed = 0
        for state in list(player.states):
            if getattr(state, "_absorbing", False):
                absorbed = getattr(state, "absorbed", 0)
                player.states.remove(state)
                break
        self._absorb_state = None
        detonation = int(absorbed * 2)
        if detonation <= 0:
            cprint(f"{player.name} releases the oath, but no damage was absorbed.", "yellow")
        else:
            cprint(
                f"{player.name} unleashes {detonation} pure holy damage across the battlefield!",
                "yellow",
            )
            for enemy in list(getattr(player, "combat_list", [])):
                if enemy.is_alive():
                    # Pure damage — bypasses protection and resistance scaling (pure type, resist=1.0)
                    pure_damage = int(detonation * enemy.resistance.get("pure", 1.0))
                    enemy.hp -= pure_damage
                    cprint(f"  {enemy.name} takes {pure_damage} damage!", "red")
        player.combat_exp["Basic"] += 5
        player.fatigue = max(0, player.fatigue - self.fatigue_cost)
