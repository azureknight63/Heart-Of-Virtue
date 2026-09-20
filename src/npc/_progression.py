"""
LevelSyncMixin / AllyProgressionMixin — static, player-uncontrolled leveling
for NPCs.

``LevelSyncMixin`` is the generic half: given a ``growth_profile`` (per-level
stat increments) and a target level, it deterministically applies per-level
stat deltas and does one stat refresh. It has no notion of combat exp or a
player-level cap, so any ``Combatant``-derived class can mix it in — hostile
NPCs use it for spawn-time region/level-table scaling (issue #617,
``src/npc_level_tables.py``), the same mechanism allies already used.

``AllyProgressionMixin(LevelSyncMixin)`` adds the ally-only pieces on top:
banking combat exp (``gain_exp``) and capping an ally's level at Jean's own
(``LEVEL_CAP``, ``CATCH_UP_MULTIPLIER``). It is mixed into ``Friend``
(_base.py); hostile ``NPC`` instances mix in ``LevelSyncMixin`` directly and
never see ``gain_exp`` at all.

Companion classes opt in by declaring a ``growth_profile`` (per-level stat
increments) and, optionally, a ``skill_schedule`` (level → move grants). A
class without a growth_profile never levels, which keeps flavor NPCs
(merchants, citizens, TheAdjutant) and untabled hostile classes inert with no
extra flags.

Design notes (docs/development/ally-progression-design.md):
  - Allies receive the same total exp Jean banks to his level track per
    victory; the award is made by ApiCombatAdapter._handle_victory().
  - exp_to_level uses the shared curve (combatant.exp_needed_for_level) with
    the ally's own (static) intelligence, so pacing matches Jean at
    intelligence parity by construction.
  - Ally level is hard-capped at Jean's level; banked exp resolves after
    Jean levels.  Allies 2+ levels behind gain exp at 1.5x until caught up.
  - Stat growth applies deterministic per-level deltas; the int() floors are
    computed against the cumulative curve so fractional rates never drift.
  - This mixin emits no narration; the combat adapter logs level-ups and
    skill learns from the event dicts returned here (mirrors the player's
    _level_up_api contract). Hostile NPCs going through LevelSyncMixin.
    sync_level directly never see this event dict at all.

Attributes expected on the host class (provided by NPC/Friend.__init__):
    self.name, self.intelligence, stat attributes with ``_base`` twins,
    self.known_moves, self.add_move (NPCCombatMixin)

``join_party`` (module level, below) is the one way an NPC enters
``player.combat_list_allies``; it is a plain function rather than a mixin
method because half its callers hand it allies that never inherit the mixin.
"""

import logging

from src.combatant import exp_needed_for_level  # type: ignore

logger = logging.getLogger(__name__)

LEVEL_CAP = 100
CATCH_UP_MULTIPLIER = 1.5


def join_party(player, ally, *, temporary=False):
    """Put ``ally`` in ``player``'s party and return it.

    ``player.combat_list_allies`` is the single source of truth for the status
    party, the battle allies and tile-following, so every join has to flag the
    NPC a friend, place it in that list exactly once (behind the player at
    index 0 -- the list is started with the player if there is none yet)
    and bring it up to Jean's level.

    ``sync_level`` is guarded because not every ally is an
    ``AllyProgressionMixin`` — flavour companions and test doubles reach here
    too, and a join is not the place to crash over missing progression.

    Args:
        player: the player whose party ``ally`` joins.
        ally: the NPC joining.
        temporary: True for an ally spawned for one fight only
            (``CombatEventConfig.ally_list``, issue #427).  Those are marked
            ``event_temp_ally`` so post-combat cleanup drops them again, start
            un-aggroed, and are deliberately *not* levelled — banking
            permanent growth on a throwaway spawn is not what the flag means.
    """
    ally.friend = True
    if temporary:
        ally.aggro = False
        ally.event_temp_ally = True
    if not isinstance(getattr(player, "combat_list_allies", None), list):
        player.combat_list_allies = [player]
    if ally not in player.combat_list_allies:
        player.combat_list_allies.append(ally)
    if not temporary and hasattr(ally, "sync_level"):
        ally.sync_level(getattr(player, "level", 1))
    return ally


class LevelSyncMixin:
    """Deterministic per-level stat growth, with no exp/cap machinery.

    Any ``Combatant``-derived class can mix this in to gain ``sync_level`` --
    a silent, one-shot climb to a target level. It never grants exp and never
    caps against another combatant's level; callers that need that (allies
    joining the party) want ``AllyProgressionMixin`` instead.
    """

    # Per-level stat increments, e.g. {"maxhp": 14, "damage": 3, "protection": 0.5}.
    # Fractional rates grant a point every 1/rate levels via the int() floor.
    # None (the default) disables progression entirely for the class.
    growth_profile = None

    # Level → list of grants, each one of:
    #   ("NewMove", MoveClass, weight)   — learn MoveClass at the given AI weight
    #   ("WeightUp", selector, n)        — raise a known move's weight to n;
    #     selector is a move name string or a move class (class form matters
    #     for moves that share display names, e.g. GorranClub is "NPC_Attack")
    skill_schedule = None

    def sync_level(self, target_level):
        """Silently bring an NPC up to target_level (skills included).

        Story join-points call this so late companions arrive battle-ready
        and returning companions spawned as fresh instances don't reset.
        Hostile NPCs call this at spawn time (src/npc_level_tables.py) with
        a level rolled from their region's table -- no exp, no narration.
        """
        if not self.growth_profile:
            return
        self._ensure_progression_attrs()
        leveled = False
        while self.level < min(int(target_level), LEVEL_CAP):
            self._level_up(refresh_stats=False)
            leveled = True
        if leveled:
            # One stat refresh for the whole climb — growth deltas are already
            # applied per level; the refresh only re-derives live stats.
            self._refresh_stats()
        self.exp = max(0, self.exp)

    def _ensure_progression_attrs(self):
        """Backfill level/exp for instances from saves predating progression."""
        if getattr(self, "level", None) is None:
            self.level = 1
        if getattr(self, "exp", None) is None:
            self.exp = 0

    def _level_up(self, refresh_stats=True):
        """Advance one level: deterministic stat growth + scheduled skills.

        Returns an event dict shaped like the player's _level_up_api result.
        Callers that don't narrate level-ups (sync_level, hostile spawns)
        simply discard the return value.
        """
        old_level = self.level
        self.exp -= self.exp_to_level
        if self.exp < 0:
            self.exp = 0
        self.level += 1
        self._apply_growth(refresh_stats=refresh_stats)
        learned = self._apply_skill_schedule()
        return {
            "ally_level_up": True,
            "name": self.name,
            "old_level": int(old_level),
            "new_level": int(self.level),
            "skills_learned": learned,
        }

    @property
    def exp_to_level(self):
        """Exp needed for the next level — the shared curve with this NPC's intelligence.

        Hostile spawns never bank exp (sync_level always drives exp back to
        0), but ``_level_up`` reads this unconditionally on its way there, so
        it lives on the base mixin rather than only on the ally subclass.
        """
        return exp_needed_for_level(
            getattr(self, "level", 1) or 1, getattr(self, "intelligence", 10) or 10
        )

    def _apply_growth(self, refresh_stats=True):
        """Apply this level's deterministic stat deltas.

        Each delta is the difference between the cumulative curve at this
        level and the previous one (int floors included), so fractional rates
        never drift and no spawn-stat snapshot needs to be carried in saves.
        Current hp/fatigue rise by the max-pool deltas so leveling never
        leaves an ally proportionally more wounded.
        """
        pool_deltas = {}
        for stat, rate in self.growth_profile.items():
            delta = int(rate * (self.level - 1)) - int(rate * (self.level - 2))
            if delta == 0:
                continue
            base_attr = f"{stat}_base"
            setattr(self, base_attr, getattr(self, base_attr, 0) + delta)
            # Mirror onto the live stat for attributes reset_stats doesn't
            # cover (damage, protection); covered ones are re-derived by the
            # stat refresh below.
            setattr(self, stat, getattr(self, stat, 0) + delta)
            if stat in ("maxhp", "maxfatigue"):
                pool_deltas[stat] = delta
        if refresh_stats:
            self._refresh_stats()
        if pool_deltas.get("maxhp"):
            self.hp = min(self.maxhp, self.hp + pool_deltas["maxhp"])
        if pool_deltas.get("maxfatigue"):
            self.fatigue = min(self.maxfatigue, self.fatigue + pool_deltas["maxfatigue"])

    def _refresh_stats(self):
        """Re-derive live stats from bases + equipment/state bonuses."""
        import src.functions as functions  # local import: functions imports npc classes indirectly

        try:
            functions.refresh_stat_bonuses(self)
        except Exception as exc:
            # Never crash a level-up mid-combat over a stat refresh; log so
            # a systematic failure leaves a diagnostic trail.
            logger.warning(
                "Stat refresh failed for %s: %s", getattr(self, "name", "?"), exc
            )

    def _apply_skill_schedule(self):
        """Apply this level's scheduled grants. Returns names of newly learned moves."""
        learned = []
        for grant in (self.skill_schedule or {}).get(self.level, []):
            kind = grant[0]
            if kind == "NewMove":
                _, move_cls, weight = grant
                move = move_cls(self)
                if not any(m.name == move.name for m in self.known_moves):
                    self.add_move(move, weight)
                    learned.append(move.name)
            elif kind == "WeightUp":
                _, selector, new_weight = grant
                matched = False
                for m in self.known_moves:
                    if isinstance(selector, str):
                        is_match = m.name == selector
                    else:
                        is_match = isinstance(m, selector)
                    if is_match:
                        m.weight = new_weight
                        matched = True
                if not matched:
                    logger.warning(
                        "%s level %s WeightUp grant matched no known move: %r",
                        getattr(self, "name", "?"),
                        self.level,
                        selector,
                    )
        return learned


class AllyProgressionMixin(LevelSyncMixin):
    """Deterministic exp/level growth for ally NPCs, on top of LevelSyncMixin."""

    def gain_exp(self, amt, player_level):
        """Bank combat exp and resolve any level-ups, capped at the player's level.

        Returns a list of level-up event dicts for the combat adapter to log
        and surface (empty for non-progressing allies).
        """
        if not self.growth_profile:
            return []
        self._ensure_progression_attrs()
        cap = min(int(player_level), LEVEL_CAP)
        if self.level < cap - 1:
            amt = int(amt * CATCH_UP_MULTIPLIER)
        self.exp += int(amt)
        events = []
        while self.level < cap and self.exp >= self.exp_to_level:
            events.append(self._level_up())
        return events
