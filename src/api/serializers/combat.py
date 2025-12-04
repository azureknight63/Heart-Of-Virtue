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
    ) -> Dict[str, Any]:
        """
        Serialize entire battle state.

        Args:
            player: Player object in combat
            enemies: List of enemy NPCs
            current_turn_index: Index of current combatant
            round_number: Current battle round

        Returns:
            Dict with full combat state
        """
        return {
            "status": "active",
            "round": round_number,
            "current_turn_index": current_turn_index,
            "player": CombatantSerializer.serialize_combatant(player),
            "enemies": [CombatantSerializer.serialize_combatant(e) for e in enemies],
            "turn_order": CombatStateSerializer._get_turn_order(player, enemies),
        }

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
            "type": "player" if hasattr(combatant, "inventory") else "enemy",
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
        # Sort by speed (descending) - higher speed goes first
        try:
            combatants.sort(key=lambda x: x[1], reverse=True)
        except Exception as e:
            print(f"DEBUG: Sort failed in _get_turn_order. Combatants: {combatants}")
            print(f"DEBUG: Error: {e}")
            # Fallback: don't sort
            pass
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
    def serialize_combatant(combatant: Any) -> Dict[str, Any]:
        """
        Serialize combatant information during combat.

        Args:
            combatant: Player or NPC object

        Returns:
            Dict with combatant state
        """
        is_player = hasattr(combatant, "inventory")

        return {
            "id": "player" if is_player else getattr(combatant, "name", "enemy"),
            "name": getattr(combatant, "name", "Unknown"),
            "type": "player" if is_player else "npc",
            "level": getattr(combatant, "level", 1),
            "health": {
                "current": getattr(combatant, "health", 0),
                "max": getattr(combatant, "max_health", 100),
            },
            "stats": CombatantSerializer._serialize_combat_stats(combatant),
            "status_effects": CombatantSerializer._serialize_status_effects(
                combatant
            ),
            "equipment": CombatantSerializer._serialize_combat_equipment(combatant),
            "distance": getattr(combatant, "combat_proximity", 0),
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
    def _serialize_combat_stats(combatant: Any) -> Dict[str, int]:
        """Serialize combat-relevant stats."""
        return {
            "damage": getattr(combatant, "damage", 0),
            "armor": getattr(combatant, "armor", 0),
            "speed": getattr(combatant, "speed", 5),
            "accuracy": getattr(combatant, "accuracy", 80),
            "evasion": getattr(combatant, "evasion", 0),
        }

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
