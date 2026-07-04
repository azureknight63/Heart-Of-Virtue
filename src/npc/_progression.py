"""
AllyProgressionMixin — static, player-uncontrolled leveling for ally NPCs.

Mixed into Friend (_base.py).  Companion classes opt in by declaring a
``growth_profile`` (per-level stat increments) and, optionally, a
``skill_schedule`` (level → move grants).  A Friend subclass without a
growth_profile never levels, which keeps flavor NPCs (merchants, citizens,
TheAdjutant) inert with no extra flags.

Design notes (docs/development/ally-progression-design.md):
  - Allies receive the same total exp Jean banks to his level track per
    victory; the award is made by ApiCombatAdapter._handle_victory().
  - exp_to_level reuses the player's formula with the ally's own (static)
    intelligence, so pacing matches Jean at intelligence parity.
  - Ally level is hard-capped at Jean's level; banked exp resolves after
    Jean levels.  Allies 2+ levels behind gain exp at 1.5x until caught up.
  - Stat growth recomputes absolutely from spawn-time bases so fractional
    rates never drift across save/load.
  - This mixin emits no narration; the combat adapter logs level-ups and
    skill learns from the event dicts returned here (mirrors the player's
    _level_up_api contract).

Attributes expected on the host class (provided by NPC/Friend.__init__):
    self.name, self.intelligence, stat attributes with ``_base`` twins,
    self.known_moves, self.add_move (NPCCombatMixin)
"""

LEVEL_CAP = 100
CATCH_UP_MULTIPLIER = 1.5


class AllyProgressionMixin:
    """Deterministic exp/level growth for ally NPCs."""

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

    @property
    def exp_to_level(self):
        """Exp needed for the next level — the player's curve with this ally's intelligence."""
        level = int(getattr(self, "level", 1) or 1)
        intelligence = int(getattr(self, "intelligence", 10) or 10)
        return level * max(1, 165 - intelligence)

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

    def sync_level(self, target_level):
        """Silently bring a joining ally up to target_level (skills included).

        Story join-points call this so late companions arrive battle-ready
        and returning companions spawned as fresh instances don't reset.
        """
        if not self.growth_profile:
            return
        self._ensure_progression_attrs()
        while self.level < min(int(target_level), LEVEL_CAP):
            self._level_up()
        self.exp = max(0, self.exp)

    def _ensure_progression_attrs(self):
        """Backfill level/exp for instances from saves predating progression."""
        if getattr(self, "level", None) is None:
            self.level = 1
        if getattr(self, "exp", None) is None:
            self.exp = 0

    def _level_up(self):
        """Advance one level: deterministic stat growth + scheduled skills.

        Returns an event dict shaped like the player's _level_up_api result.
        """
        old_level = self.level
        self.exp -= self.exp_to_level
        if self.exp < 0:
            self.exp = 0
        self.level += 1
        self._apply_growth()
        learned = self._apply_skill_schedule()
        return {
            "ally_level_up": True,
            "name": self.name,
            "old_level": int(old_level),
            "new_level": int(self.level),
            "skills_learned": learned,
        }

    def _apply_growth(self):
        """Recompute grown stats absolutely from spawn-time bases.

        Recompute-from-spawn (rather than accumulate) keeps fractional rates
        drift-free and is idempotent across save/load.  Current hp/fatigue
        rise by the max-pool deltas so leveling never leaves an ally
        proportionally more wounded.
        """
        import functions  # local import: functions imports npc classes indirectly

        if not hasattr(self, "_spawn_bases"):
            self._spawn_bases = {
                stat: getattr(self, f"{stat}_base", getattr(self, stat, 0))
                for stat in self.growth_profile
            }
        pool_deltas = {}
        for stat, rate in self.growth_profile.items():
            base_attr = f"{stat}_base"
            new_base = self._spawn_bases[stat] + int(rate * (self.level - 1))
            old_base = getattr(self, base_attr, self._spawn_bases[stat])
            delta = new_base - old_base
            if delta == 0:
                continue
            setattr(self, base_attr, new_base)
            # Mirror onto the live stat for attributes reset_stats doesn't
            # cover (damage, protection); covered ones are recomputed below.
            setattr(self, stat, getattr(self, stat, new_base) + delta)
            if stat in ("maxhp", "maxfatigue"):
                pool_deltas[stat] = delta
        try:
            functions.refresh_stat_bonuses(self)
        except Exception:
            pass  # stat refresh must never crash a level-up mid-combat
        if pool_deltas.get("maxhp"):
            self.hp = min(self.maxhp, self.hp + pool_deltas["maxhp"])
        if pool_deltas.get("maxfatigue"):
            self.fatigue = min(self.maxfatigue, self.fatigue + pool_deltas["maxfatigue"])

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
                for m in self.known_moves:
                    if (
                        m.name == selector
                        if isinstance(selector, str)
                        else isinstance(m, selector)
                    ):
                        m.weight = new_weight
        return learned
