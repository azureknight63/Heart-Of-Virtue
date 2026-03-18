"""
Combat-related serializers for combat state, combatants, moves, and status effects.

This module provides serialization for:
- CombatState: Full battle state (turn order, combatants, status)
- Combatant: Character/NPC in combat (HP, moves, effects)
- Move: Combat abilities/actions
- StateEffect: Status effects and conditions
"""

from typing import Dict, List, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from player import Player
    from npc import NPC
    from moves import Move
    from states import State


class CombatStateSerializer:
    """Serialize complete combat state for API responses."""

    @staticmethod
    def serialize_combat_state(
        player: "Player",
        enemies: List["NPC"],
        current_turn_index: int = 0,
        round_number: int = 1,
        allies: List["NPC"] = None,
    ) -> Dict[str, Any]:
        """
        Serialize entire battle state.

        Args:
            player: Player object in combat
            enemies: List of enemy NPCs
            current_turn_index: Index of current combatant
            round_number: Current battle round
            allies: List of allied NPCs (party members, excluding the player)

        Returns:
            Dict with full combat state
        """
        allies = allies or []
        serialized_allies = [CombatantSerializer.serialize_combatant(a, reference=player) for a in allies]
        return {
            "status": "active",
            "round": round_number,
            "current_turn_index": current_turn_index,
            "player": CombatantSerializer.serialize_combatant(player),
            "allies": serialized_allies,
            "enemies": [CombatantSerializer.serialize_combatant(e, reference=player) for e in enemies],
            "turn_order": CombatStateSerializer._get_turn_order(player, enemies),
            "combatants": (
                [CombatantSerializer.serialize_combatant(player)]
                + serialized_allies
                + [CombatantSerializer.serialize_combatant(e, reference=player) for e in enemies]
            ),
            "suggested_moves": getattr(player, "suggested_moves", []),
            "suggestions_loading": getattr(player, "suggestions_loading", False),
            "last_move_outcome": getattr(player, "last_move_summary", ""),
            "last_move_name": getattr(player, "last_move_name", None),
            "last_move_target_id": getattr(player, "last_move_target_id", None),
            "player_consumables": CombatStateSerializer._get_consumables(player)
        }

    @staticmethod
    def _get_consumables(player: "Player") -> List[Dict[str, Any]]:
        """Get consumable items from player inventory."""
        consumables = []
        if hasattr(player, "inventory"):
            for item in player.inventory:
                # Basic check for consumables: if it has a 'use' method or is a potion
                # For now, let's include everything with a value and quantity for the LLM to decide
                consumables.append({
                    "name": getattr(item, "name", "Unknown"),
                    "qty": getattr(item, "count", 1),
                    "value": getattr(item, "value", 0),
                    "description": getattr(item, "description", "")
                })
        return consumables

    @staticmethod
    def serialize_turn_data(combatant: Any) -> Dict[str, Any]:
        """
        Serialize current turn information for a combatant.

        Args:
            combatant: Player or NPC currently taking turn

        Returns:
            Dict with turn data
        """
        return {
            "name": getattr(combatant, "name", "Unknown"),
            "type": "player" if combatant.__class__.__name__ == "Player" else "enemy",
            "available_actions": CombatStateSerializer._get_available_actions(
                combatant
            ),
        }

    @staticmethod
    def serialize_battle_summary(
        player: "Player", enemies: List["NPC"], victory: bool
    ) -> Dict[str, Any]:
        """
        Serialize battle result summary.

        Args:
            player: Player in combat
            enemies: Enemy list
            victory: Whether player won

        Returns:
            Dict with battle result
        """
        return {
            "status": "victory" if victory else "defeat",
            "player_hp": player.hp,
            "enemies_defeated": sum(1 for e in enemies if e.hp <= 0),
            "total_enemies": len(enemies),
            "experience_gained": (
                CombatStateSerializer._calculate_experience(enemies)
                if victory
                else 0
            ),
            "items_dropped": (
                CombatStateSerializer._get_drops(enemies) if victory else []
            ),
        }

    @staticmethod
    def _get_turn_order(player: "Player", enemies: List["NPC"]) -> List[str]:
        """Get turn order based on initiative/speed."""
        combatants = [("player", getattr(player, "speed", 10))] + [
            (f"enemy_{i}", getattr(e, "speed", 5)) for i, e in enumerate(enemies)
        ]
        return [c[0] for c in combatants]

    @staticmethod
    def _get_available_actions(combatant: Any) -> List[str]:
        """Get available actions for combatant this turn."""
        actions = ["attack", "defend", "flee"]
        if hasattr(combatant, "moves"):
            actions.extend(getattr(combatant, "moves", []))
        if hasattr(combatant, "inventory"):
            actions.append("use_item")
        return actions

    @staticmethod
    def _calculate_experience(enemies: List["NPC"]) -> int:
        """Calculate total experience from defeated enemies."""
        total = 0
        for enemy in enemies:
            if hasattr(enemy, "exp_reward"):
                total += enemy.exp_reward
            elif hasattr(enemy, "level"):
                total += enemy.level * 10
        return total

    @staticmethod
    def _get_drops(enemies: List["NPC"]) -> List[Dict[str, Any]]:
        """Get items dropped by defeated enemies."""
        drops = []
        for enemy in enemies:
            if hasattr(enemy, "inventory"):
                for item in getattr(enemy, "inventory", []):
                    drops.append(
                        {
                            "name": getattr(item, "name", "Unknown"),
                            "quantity": getattr(item, "count", 1),
                        }
                    )
        return drops


class CombatantSerializer:
    """Serialize individual combatant state (player or NPC in combat)."""

    @staticmethod
    def serialize_combatant(combatant: Any, reference: Any = None) -> Dict[str, Any]:
        """
        Serialize combatant information during combat.

        Args:
            combatant: Player or NPC object
            reference: Reference entity (usually player) to calculate distance from

        Returns:
            Dict with combatant state
        """
        is_player = combatant.__class__.__name__ == "Player"

        return {
            "id": "player" if is_player else f"enemy_{id(combatant)}",
            "name": getattr(combatant, "name", "Unknown"),
            "type": "player" if is_player else "npc",
            "level": getattr(combatant, "level", 1),
            "health": {
                "current": getattr(combatant, "hp", getattr(combatant, "health", 0)),
                "max": getattr(combatant, "maxhp", getattr(combatant, "max_health", 100)),
            },
            "hp": getattr(combatant, "hp", getattr(combatant, "health", 0)),
            "max_hp": getattr(combatant, "maxhp", getattr(combatant, "max_health", 100)),
            "fatigue": getattr(combatant, "fatigue", 0),
            "max_fatigue": getattr(combatant, "maxfatigue", getattr(combatant, "max_fatigue", 100)),
            "maxfatigue": getattr(combatant, "maxfatigue", getattr(combatant, "max_fatigue", 100)),
            "heat": getattr(combatant, "heat", 1.0) if is_player else 1.0,
            "stats": CombatantSerializer._serialize_combat_stats(combatant),
            "attributes": CombatantSerializer._serialize_base_attributes(combatant),
            "status_effects": CombatantSerializer._serialize_status_effects(
                combatant
            ),
            "passives": CombatantSerializer._serialize_passives(combatant),
            "equipment": CombatantSerializer._serialize_combat_equipment(combatant),
            "distance": CombatantSerializer._get_distance(combatant, reference),
            "position": CombatantSerializer._serialize_position(combatant),
            "current_move": CombatantSerializer._serialize_active_move(combatant),
            "move_in_process": CombatantSerializer._serialize_active_move(combatant), # Alias for Strategist
        }

    @staticmethod
    def _serialize_active_move(combatant: Any) -> Optional[Dict[str, Any]]:
        """Serialize currently active/charging move."""
        if hasattr(combatant, "current_move") and combatant.current_move:
            move = combatant.current_move
            return {
                "name": getattr(move, "name", "Unknown"),
                "category": getattr(move, "category", "Miscellaneous"),
                "description": getattr(move, "description", ""),
                "current_stage": getattr(move, "current_stage", 0),
                "beats_left": getattr(move, "beats_left", 0),
                "total_beats": getattr(move, "stage_beat", [0, 0, 0, 0])[getattr(move, "current_stage", 0)] if hasattr(move, "stage_beat") else 0,
            }
        return None

    @staticmethod
    def _get_distance(combatant: Any, reference: Any = None) -> int:
        """Safely get distance value."""
        prox = getattr(combatant, "combat_proximity", 0)
        if isinstance(prox, dict):
            if reference and reference in prox:
                return prox[reference]
            # If we can't resolve the distance to the reference, return 0
            # This handles cases where prox is a dict (new system) but we don't have the key
            return 0
        # Handle legacy scalar distance
        return prox

    @staticmethod
    def _serialize_position(combatant: Any) -> Optional[Dict[str, Any]]:
        """Serialize combat position coordinates."""
        if not hasattr(combatant, "combat_position") or combatant.combat_position is None:
            return None
        
        pos = combatant.combat_position
        return {
            "x": pos.x,
            "y": pos.y,
            "facing": pos.facing.name if hasattr(pos, "facing") and hasattr(pos.facing, "name") else "N"
        }


    @staticmethod
    def serialize_combatant_list(combatants: List[Any]) -> List[Dict[str, Any]]:
        """
        Serialize multiple combatants.

        Args:
            combatants: List of Player/NPC objects

        Returns:
            List of serialized combatants
        """
        return [CombatantSerializer.serialize_combatant(c) for c in combatants]

    @staticmethod
    def serialize_health_bar(combatant: Any) -> Dict[str, Any]:
        """
        Serialize health bar information for UI display.

        Args:
            combatant: Player or NPC

        Returns:
            Dict with HP percentage and status
        """
        current_hp = getattr(combatant, "health", 0)
        max_hp = getattr(combatant, "max_health", 100)

        hp_percent = (current_hp / max_hp * 100) if max_hp > 0 else 0
        status = "healthy"
        if hp_percent <= 25:
            status = "critical"
        elif hp_percent <= 50:
            status = "wounded"
        elif hp_percent <= 75:
            status = "injured"

        return {
            "current": current_hp,
            "max": max_hp,
            "percent": hp_percent,
            "status": status,
        }

    @staticmethod
    def _serialize_combat_stats(combatant: Any) -> Dict[str, Any]:
        """Serialize combat-relevant stats."""
        return {
            "damage": int(getattr(combatant, "damage", 0)),
            "armor": int(getattr(combatant, "armor", 0)),
            "speed": int(getattr(combatant, "speed", 5)),
            "accuracy": int(getattr(combatant, "accuracy", 80)),
            "evasion": int(getattr(combatant, "evasion", 0)),
            "defense": int(getattr(combatant, "defense", 0)),
            "attack_power": int(getattr(combatant, "attack_power", 0)),
        }

    @staticmethod
    def _serialize_base_attributes(combatant: Any) -> Dict[str, int]:
        """Serialize base RPG attributes."""
        return {
            "strength": int(getattr(combatant, "strength", 0)),
            "finesse": int(getattr(combatant, "finesse", 0)),
            "speed": int(getattr(combatant, "speed", 0)),
            "endurance": int(getattr(combatant, "endurance", 0)),
            "intelligence": int(getattr(combatant, "intelligence", 0)),
            "charisma": int(getattr(combatant, "charisma", 0)),
        }

    @staticmethod
    def _serialize_passives(combatant: Any) -> List[Dict[str, Any]]:
        """Serialize passive skills/moves with metadata for UI."""
        passives = []
        if hasattr(combatant, "known_moves"):
            for move in combatant.known_moves:
                if getattr(move, "passive", False):
                    passives.append({
                        "name": move.name,
                        "type": "passive",
                        "description": getattr(move, "description", "Passive skill."),
                        "category": getattr(move, "category", "Miscellaneous")
                    })
        return passives

    @staticmethod
    def _serialize_status_effects(combatant: Any) -> List[Dict[str, Any]]:
        """Serialize active status effects on combatant."""
        effects = []
        if hasattr(combatant, "states"):
            for state in getattr(combatant, "states", []):
                effects.append(StateEffectSerializer.serialize_state(state))
        return effects

    @staticmethod
    def _serialize_combat_equipment(combatant: Any) -> Dict[str, Any]:
        """Serialize equipped items relevant to combat."""
        equipment = {
            "weapon": None,
            "armor": None,
            "resistances": {},
        }

        if hasattr(combatant, "equipped"):
            eq = getattr(combatant, "equipped", {})
            if "weapon" in eq and eq["weapon"]:
                equipment["weapon"] = {
                    "name": getattr(eq["weapon"], "name", "Unarmed"),
                    "damage_type": getattr(eq["weapon"], "damage_type", "physical"),
                }
            if "body" in eq and eq["body"]:
                equipment["armor"] = {
                    "name": getattr(eq["body"], "name", "No Armor"),
                    "defense": getattr(eq["body"], "defense", 0),
                }

        # Add resistances
        if hasattr(combatant, "resistances"):
            equipment["resistances"] = dict(getattr(combatant, "resistances", {}))

        return equipment


class MoveSerializer:
    """Serialize combat moves and abilities."""

    @staticmethod
    def serialize_move(move: "Move") -> Dict[str, Any]:
        """
        Serialize combat move information.

        Args:
            move: Move object from moves.py

        Returns:
            Dict with move details
        """
        return {
            "name": getattr(move, "name", "Unknown Move"),
            "description": getattr(move, "description", ""),
            "type": getattr(move, "move_type", "physical"),
            "category": getattr(move, "category", "Miscellaneous"),
            "damage": {
                "base": getattr(move, "base_damage", 0),
                "type": getattr(move, "damage_type", "physical"),
            },
            "cost": {
                "mp": getattr(move, "mp_cost", 0),
                "stamina": getattr(move, "stamina_cost", 0),
            },
            "range": getattr(move, "range", "melee"),
            "cooldown": {
                "base": getattr(move, "cooldown_max", 0),
                "remaining": getattr(move, "cooldown", 0),
            },
            "accuracy": getattr(move, "accuracy", 100),
            "effects": MoveSerializer._serialize_move_effects(move),
        }

    @staticmethod
    def serialize_move_list(moves: List["Move"]) -> List[Dict[str, Any]]:
        """
        Serialize list of available moves.

        Args:
            moves: List of Move objects

        Returns:
            List of serialized moves
        """
        return [MoveSerializer.serialize_move(m) for m in moves]

    @staticmethod
    def serialize_move_with_cooldown(
        move: "Move", cooldown_remaining: int = 0
    ) -> Dict[str, Any]:
        """
        Serialize move with current cooldown state.

        Args:
            move: Move object
            cooldown_remaining: Current cooldown counter

        Returns:
            Dict with move and cooldown info
        """
        move_data = MoveSerializer.serialize_move(move)
        move_data["cooldown"]["remaining"] = cooldown_remaining
        move_data["available"] = cooldown_remaining <= 0
        return move_data

    @staticmethod
    def _serialize_move_effects(move: "Move") -> List[Dict[str, Any]]:
        """Serialize status effects applied by move."""
        effects = []
        if hasattr(move, "applies_state") and getattr(move, "applies_state"):
            state = getattr(move, "applies_state")
            effects.append(
                {
                    "type": getattr(state, "name", "Unknown"),
                    "duration": getattr(state, "duration", 1),
                    "severity": StateEffectSerializer._get_severity(state),
                }
            )
        return effects


class StateEffectSerializer:
    """Serialize status effects and conditions."""

    @staticmethod
    def serialize_state(state: "State") -> Dict[str, Any]:
        """
        Serialize individual status effect.

        Args:
            state: State object from states.py

        Returns:
            Dict with state information
        """
        return {
            "name": getattr(state, "name", "Unknown Effect"),
            "type": getattr(state, "state_type", "buff"),
            "description": getattr(state, "description", ""),
            "damage_per_turn": getattr(state, "damage_per_turn", 0),
            "healing_per_turn": getattr(state, "healing_per_turn", 0),
            "severity": StateEffectSerializer._get_severity(state),
            "resistable": getattr(state, "resistable", True),
        }

    @staticmethod
    def serialize_state_list(states: List["State"]) -> List[Dict[str, Any]]:
        """
        Serialize multiple status effects.

        Args:
            states: List of State objects

        Returns:
            List of serialized states
        """
        return [StateEffectSerializer.serialize_state(s) for s in states]

    @staticmethod
    def serialize_state_with_duration(
        state: "State", duration_remaining: int = 0
    ) -> Dict[str, Any]:
        """
        Serialize status effect with remaining duration.

        Args:
            state: State object
            duration_remaining: Turns remaining

        Returns:
            Dict with state and duration info
        """
        state_data = StateEffectSerializer.serialize_state(state)
        state_data["duration_remaining"] = duration_remaining
        state_data["active"] = duration_remaining > 0
        return state_data

    @staticmethod
    def _get_severity(state: "State") -> str:
        """Determine severity level of state effect."""
        damage = getattr(state, "damage_per_turn", 0)

        if damage == 0:
            return "light"
        elif damage <= 5:
            return "moderate"
        else:
            return "severe"
