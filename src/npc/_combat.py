"""
NPCCombatMixin — AI move selection and combat engagement.

Mixed into NPC (_base.py).  Contains the four methods that govern how an
NPC chooses and executes moves in combat.

Attributes expected on the host class (provided by NPC.__init__):
    self.known_moves        list
    self.current_move       object | None
    self.fatigue            float
    self.maxfatigue         float
    self.in_combat          bool
    self.default_proximity  int
    self.combat_proximity   dict
    self.player_ref         Player | None
    self.ai_config          NPCAIConfig | None
"""

import random

import moves  # type: ignore


class NPCCombatMixin:
    """Combat AI and engagement behaviour for NPC."""

    def select_move(self):
        available_moves = self.refresh_moves()

        # Initialize AI config if we have a player reference (combat started)
        if (
            (not hasattr(self, "ai_config") or self.ai_config is None)
            and hasattr(self, "player_ref")
            and self.player_ref
        ):
            try:
                from npc_ai_config import NPCAIConfig

                self.ai_config = NPCAIConfig(self.player_ref)
            except ImportError:
                pass

        #  simple random selection; if you want something more complex, overwrite this for the specific NPC
        weighted_moves = []
        for move in available_moves:
            # Calculate tactical weight modifications
            weight = move.weight
            if hasattr(self, "ai_config") and self.ai_config:
                weight += self.ai_config.get_weighted_move_bonus(self, move.name)

            # Ensure at least 1 weight for viable moves
            weight = max(1, weight)

            for _ in range(weight):
                weighted_moves.append(move)

        if not weighted_moves:
            # Fallback if no moves generated
            return

        # If no offensive move is both affordable and viable, rest to recover fatigue.
        # This prevents the NPC from idling forever when the preferred attack costs more
        # fatigue than is currently available (e.g. after 2+ attacks drain the pool).
        # Use available_moves (deduplicated) rather than weighted_moves to avoid calling
        # viable() multiple times on the same object due to weight expansion.
        # Use getattr in case a move was created via __new__ without calling Move.__init__.
        can_attack = any(
            getattr(m, "category", "") == "Offensive"
            and m.fatigue_cost <= self.fatigue
            and m.viable()
            for m in available_moves
        )
        if not can_attack and self.fatigue < self.maxfatigue:
            # Only force-rest when advancing is not an option.  If a viable Advance move
            # exists the NPC should close distance rather than stand still and recover.
            can_advance = any(
                getattr(m, "name", "") == "Advance" for m in available_moves
            )
            if not can_advance:
                self.current_move = moves.NpcRest(self)
                return

        num_choices = len(weighted_moves) - 1
        max_attempts = 20  # Prevent infinite loops
        attempts = 0
        choice = 0

        while self.current_move is None and attempts < max_attempts:
            attempts += 1
            choice = random.randint(0, num_choices)
            if (weighted_moves[choice].fatigue_cost <= self.fatigue) and weighted_moves[
                choice
            ].viable():
                self.current_move = weighted_moves[choice]

        # Hard fallback: if all 20 random attempts failed, rest rather than doing nothing.
        if self.current_move is None:
            self.current_move = moves.NpcRest(self)
            return

        # Log NPC decision if debug tracing is enabled
        if hasattr(self, "player_ref") and self.player_ref:
            player = self.player_ref
            if hasattr(player, "combat_debug_manager") and player.combat_debug_manager:
                if player.combat_debug_manager.should_debug_ai_decisions():
                    flank_bonus = 0
                    retreat_prio = 0
                    if hasattr(self, "ai_config") and self.ai_config:
                        flank_bonus = self.ai_config.get_weighted_move_bonus(
                            self, self.current_move.name
                        )
                        retreat_prio = self.ai_config.calculate_retreat_priority(
                            self, []
                        )
                    player.combat_debug_manager.display_ai_debug_info(
                        self,
                        f"Selected {self.current_move.name}",
                        {
                            "fatigue_cost": self.current_move.fatigue_cost,
                            "original_weight": weighted_moves[choice].weight,
                            "ai_bonus": flank_bonus,
                            "retreat_priority": retreat_prio,
                        },
                    )

    def add_move(self, move, weight=1):
        """Adds a move to the NPC's known move list. Weight is the number of times to add."""
        self.known_moves.append(move)
        move.weight = weight

    def reset_combat_moves(self):
        """
        Resets all move states to stage 0 with 0 beats remaining.
        This ensures moves progress correctly when the NPC joins combat mid-fight.
        Called by combat_engage() and when allies join mid-combat.
        """
        for move in self.known_moves:
            move.current_stage = 0
            move.beats_left = 0

    def combat_engage(self, player):
        """
        Adds NPC to the proper combat lists and initializes.
        Resets all move states to ensure moves progress correctly from the start.
        """
        player.combat_list.append(self)
        player.combat_proximity[self] = int(
            self.default_proximity * random.uniform(0.75, 1.25)
        )
        if len(player.combat_list_allies) > 0:
            for ally in player.combat_list_allies:
                ally.combat_proximity[self] = int(
                    self.default_proximity * random.uniform(0.75, 1.25)
                )
        self.in_combat = True
        self.reset_combat_moves()
