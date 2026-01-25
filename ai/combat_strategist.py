import json
import logging
from typing import Any, Dict, List, Optional
from ai.llm_client import GenericLLMClient

logger = logging.getLogger(__name__)

class CombatStrategist:
    """Strategist that suggests tactical moves during combat using an LLM."""

    def __init__(self, client: Optional[GenericLLMClient] = None):
        self.client = client or GenericLLMClient()
        self.system_prompt = (
            "You are the Tactical Strategist for Jean Claire. Your goal is to analyze the current combat state and suggest the best moves.\n"
            "Consider Heat (affects damage/XP), Fatigue (resource for moves), and Distance (proximity to enemies).\n"
            "Consider everything provided in the context, including player attributes, consumables, status effects, and the narrative flow of the combat log.\n"
            "Suggest up to 10 moves, sorted by tactical advantage (highest score first).\n"
            "Format each suggestion as a JSON object with:\n"
            "- move_name: The exact name of the move.\n"
            "- target_id: The exact ID of the target as provided in the context (e.g., 'enemy_12345'). Use null if the move is not targeted or is self-targeted.\n"
            "- score: 1-100 (An estimate of how significant this move will be toward maximizing tactical advantage).\n"
            "- reasoning: A brief, one-sentence explanation of why this move is optimal."
        )

    def get_suggestions(self, combat_context: Dict[str, Any], max_suggestions: int = 1) -> List[Dict[str, Any]]:
        """Fetch movement suggestions from the LLM."""
        if not self.client.available():
            return []

        user_prompt = self._build_user_prompt(combat_context)
        
        try:
            # We use generate_structured to get an array of JSON objects
            # Note: client.generate_structured returns a Dict. If the LLM returns a List, 
            # we might need to handle it or wrap it in our prompt.
            # To be safe, we'll ask for a wrapper object or just parse the list if we can.
            
            # Let's refine the prompt to return a named object for easier parsing via GenericLLMClient
            wrapped_prompt = user_prompt + "\nReturn the result as a JSON object with a key 'suggestions' containing the list of move objects."
            
            raw_response = self.client.generate_structured(self.system_prompt, wrapped_prompt)
            
            if not raw_response or not isinstance(raw_response, dict):
                return []

            suggestions = raw_response.get("suggestions", [])
            if not isinstance(suggestions, list):
                # Fallback: maybe it returned a list directly or in another key
                if isinstance(raw_response, list):
                    suggestions = raw_response
                else:
                    return []
            
            # Sanitize and sort
            valid_suggestions = []
            for s in suggestions:
                if isinstance(s, dict) and "move_name" in s:
                    # Coerce score to int
                    try:
                        s["score"] = int(s.get("score", 0))
                    except (ValueError, TypeError):
                        s["score"] = 0
                    valid_suggestions.append(s)
            
            # Sort by score descending
            valid_suggestions.sort(key=lambda x: x["score"], reverse=True)
            
            # Limit to requested count
            return valid_suggestions[:max_suggestions]

        except Exception as e:
            logger.error(f"Error fetching combat suggestions: {e}")
            return []

    def _build_user_prompt(self, ctx: Dict[str, Any]) -> str:
        """Construct the context string for the LLM."""
        player = ctx.get("player", {})
        enemies = ctx.get("enemies", [])
        history = ctx.get("history", [])
        last_move = ctx.get("last_move", "None")
        available_moves = ctx.get("available_moves", [])

        # Build Player block
        p_attrs = ", ".join([f"{k}: {v}" for k, v in player.get("attributes", {}).items()])
        p_effects = f"Passives: {', '.join(player.get('passives', []))}\nStatus: {', '.join(player.get('active_effects', []))}"
        p_consumables = ", ".join([f"{c['name']} (Qty: {c['qty']}, Value: {c['value']}g)" for c in player.get("consumables", [])])

        player_block = (
            f"Player: {player.get('name', 'Jean')} [HP: {player.get('hp')}/{player.get('max_hp')}, "
            f"Fatigue: {player.get('fatigue')}/{player.get('max_fatigue')}, Heat: {player.get('heat')}, "
            f"Pos: {player.get('x')},{player.get('y')}, Facing: {player.get('facing')}]\n"
            f"Attributes: [{p_attrs}]\n"
            f"{p_effects}\n"
            f"Consumables: [{p_consumables or 'None'}]"
        )

        # Build Enemies block
        enemy_list = []
        for e in enemies:
            e_attrs = ", ".join([f"{k}: {v}" for k, v in e.get("attributes", {}).items()])
            mip = e.get("move_in_process")
            mip_str = f", Move In Process: {mip['name']} (Beats Left: {mip['beats_left']})" if mip else ""
            enemy_list.append(
                f"- {e.get('name')} [ID: {e.get('id')}, HP: {e.get('hp')}/{e.get('max_hp')}, "
                f"Pos: {e.get('x')},{e.get('y')}, Dist: {e.get('distance')}ft, Facing: {e.get('facing')}{mip_str}]\n"
                f"  Attributes: [{e_attrs}]"
            )
        enemies_block = "Enemies:\n" + "\n".join(enemy_list)

        # Build Context block
        history_str = "\n".join(history[-5:]) # Last 5 log entries
        moves_str = ", ".join([m.get("name") for m in available_moves])

        return (
            f"{player_block}\n\n"
            f"{enemies_block}\n\n"
            f"Recent History:\n{history_str}\n"
            f"Previous Move: {last_move}\n\n"
            f"Available Moves: {moves_str}"
        )
