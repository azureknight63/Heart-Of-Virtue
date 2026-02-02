import json
import logging
from typing import Any, Dict, List, Optional
from ai.llm_client import GenericLLMClient

logger = logging.getLogger(__name__)

class CombatStrategist:
    """Strategist that suggests tactical moves during combat using an LLM."""

    def __init__(self, client: Optional[GenericLLMClient] = None):
        logger.info("DEBUG: Initializing CombatStrategist")
        self.client = client or GenericLLMClient()
        self.system_prompt = (
            "You are the Tactical Strategist for Jean Claire. Your goal is to analyze the current combat state and suggest the best moves.\n"
            "Consider Heat (affects damage/XP), Fatigue (resource for moves), and Distance (proximity to enemies).\n"
            "Consider everything provided in the context, including player attributes, consumables, status effects, and the narrative flow of the combat log.\n"
            "Suggest only moves that are currently listed in the 'Available Moves' section below. "
            "Format each suggestion as a JSON object with:\n"
            "- move_name: The exact name of the move.\n"
            "target_id: The exact ID of the target as provided in the context (e.g., 'enemy_12345'). "
            "IMPORTANT: If the move is listed as requiring a target (e.g., Attack, Advance), you MUST provide a valid target_id from the 'Enemies' list. "
            "Use null ONLY if the move is strictly self-targeted or non-targeted.\n"
            "- score: 1-100 (An estimate of how significant this move will be toward maximizing tactical advantage).\n"
            "- reasoning: A brief, one-sentence explanation of why this move is optimal."
        )

    def get_suggestions(self, combat_context: Dict[str, Any], max_suggestions: int = 1) -> List[Dict[str, Any]]:
        """Fetch movement suggestions from the LLM."""
        logger.info(f"DEBUG: CombatStrategist.get_suggestions called (max: {max_suggestions})")
        if not self.client.available():
            logger.warning(f"DEBUG: CombatStrategist.get_suggestions: client not available (reason: {self.client._unavailable_reason})")
            return self._get_fallback_suggestions(combat_context, max_suggestions)

        user_prompt = self._build_user_prompt(combat_context)
        
        try:
            # Let's refine the prompt to return a named object for easier parsing via GenericLLMClient
            wrapped_prompt = user_prompt + "\nReturn the result as a JSON object with a key 'suggestions' containing the list of move objects."
            
            logger.info(f"DEBUG: Requesting {max_suggestions} suggestions for {combat_context.get('player', {}).get('name')}")
            logger.info(f"DEBUG: STRATEGIST INPUT (first 200 chars): {wrapped_prompt[:200]}...")
            raw_response = self.client.generate_structured(self.system_prompt, wrapped_prompt)
            
            logger.info(f"DEBUG: STRATEGIST RAW RESPONSE: {raw_response}")

            if not raw_response or not isinstance(raw_response, dict):
                logger.warning(f"DEBUG: Strategist received empty or non-dict response from LLM of type {type(raw_response)}")
                return self._get_fallback_suggestions(combat_context, max_suggestions)
 
            suggestions = raw_response.get("suggestions", [])
            if not isinstance(suggestions, list):
                # Fallback: maybe it returned a list directly or in another key
                if isinstance(raw_response, list):
                    suggestions = raw_response
                else:
                    logger.warning(f"DEBUG: Strategist failed to parse suggestions from: {raw_response}")
                    return self._get_fallback_suggestions(combat_context, max_suggestions)
            
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
            
            logger.debug(f"DEBUG: Strategist found {len(valid_suggestions)} valid suggestions.")
            
            # If no valid suggestions found, use fallback
            if not valid_suggestions:
                return self._get_fallback_suggestions(combat_context, max_suggestions)

            # Sort by score descending
            valid_suggestions.sort(key=lambda x: x["score"], reverse=True)
            
            # Limit to requested count
            results = valid_suggestions[:max_suggestions]
            
            # Post-process results to ensure targeted moves have targets
            enemies = combat_context.get("enemies", [])
            primary_target_id = enemies[0].get("id") if enemies else None
            
            # Identify which moves in context are targeted
            targeted_moves = {}
            for m in combat_context.get("available_moves", []):
                if m.get("targeted"):
                    targeted_moves[m.get("name")] = True
            
            for s in results:
                m_name = s.get("move_name")
                if targeted_moves.get(m_name) and not s.get("target_id"):
                    logger.info(f"DEBUG: Strategist auto-filling missing target_id for targeted move '{m_name}'")
                    s["target_id"] = primary_target_id
                    
            return results

        except Exception as e:
            logger.error(f"DEBUG: Error fetching combat suggestions: {e}", exc_info=True)
            return self._get_fallback_suggestions(combat_context, max_suggestions)

    def _get_fallback_suggestions(self, combat_context: Dict[str, Any], max_suggestions: int) -> List[Dict[str, Any]]:
        """Provide basic suggestions if the LLM fails."""
        available = combat_context.get("available_moves", [])
        if not available:
            return []
            
        # Try to find a target if moves are targeted
        enemies = combat_context.get("enemies", [])
        primary_target_id = enemies[0].get("id") if enemies else None
            
        # Prioritize moves: Offensive > Maneuver > Defensive > Miscellaneous
        # But filter only those that are 'available'
        scored_moves = []
        for m in available:
            if not m.get("available", True):
                continue
            
            name = m.get("name", "Unknown")
            category = m.get("category", "Miscellaneous")
            
            # Skip noise
            if name in ["Cancel"]:
                continue
                
            # Basic scoring heuristic for fallback
            base_score = 40
            if category == "Offensive":
                base_score = 85
            elif category == "Maneuver":
                # High priority if far away? Let's just check if it's Advance
                if name == "Advance":
                    base_score = 80
                else: base_score = 75
            elif category == "Defensive":
                base_score = 65
            elif category == "Special":
                base_score = 70
                
            # Penalyze Wait/Check unless nothing else
            if name in ["Wait", "Check"]:
                base_score = 20

            target_id = primary_target_id if category in ["Offensive", "Maneuver"] else None
            
            scored_moves.append({
                "move_name": name,
                "target_id": target_id,
                "score": base_score,
                "reasoning": f"Tactical analysis delayed; {name} is a high-priority tactical alternative."
            })

        # Sort and limit
        scored_moves.sort(key=lambda x: x["score"], reverse=True)
        
        # Ensure we return at least one even if it's 'Check'
        if not scored_moves:
            return [{
                "move_name": "Check",
                "target_id": None,
                "score": 10,
                "reasoning": "No other moves available; reassess the battlefield."
            }]

        return scored_moves[:max(1, min(3, max_suggestions))]

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
        p_consumables = ", ".join([f"{c.get('name', 'Item')} (Qty: {c.get('qty', 1)}, Value: {c.get('value', 0)}g)" for c in player.get("consumables", [])])

        pos = player.get("position") or {}
        player_block = (
            f"Player: {player.get('name', 'Jean')} [HP: {player.get('hp')}/{player.get('max_hp')}, "
            f"Fatigue: {player.get('fatigue')}/{player.get('max_fatigue')}, Heat: {player.get('heat')}, "
            f"Pos: {pos.get('x')},{pos.get('y')}, Facing: {pos.get('facing')}]\n"
            f"Attributes: [{p_attrs}]\n"
            f"{p_effects}\n"
            f"Consumables: [{p_consumables or 'None'}]"
        )

        # Build Enemies block
        enemy_list = []
        for e in enemies:
            e_attrs = ", ".join([f"{k}: {v}" for k, v in e.get("attributes", {}).items()])
            mip = e.get("move_in_process")
            mip_str = f", Move In Process: {mip.get('name', 'Action')} (Beats Left: {mip.get('beats_left', 0)})" if mip else ""
            e_pos = e.get("position") or {}
            enemy_list.append(
                f"- {e.get('name')} [ID: {e.get('id')}, HP: {e.get('hp')}/{e.get('max_hp')}, "
                f"Pos: {e_pos.get('x')},{e_pos.get('y')}, Dist: {e.get('distance')}ft, Facing: {e_pos.get('facing')}{mip_str}]\n"
                f"  Attributes: [{e_attrs}]"
            )
        enemies_block = "Enemies:\n" + "\n".join(enemy_list)

        # Build Context block
        history_str = "\n".join(history[-5:]) # Last 5 log entries
        move_descriptions = []
        for m in available_moves:
            if not m.get("available", True):
                continue
            name = m.get("name")
            targets = m.get("viable_targets", [])
            if targets:
                target_names = [f"{t.get('name', 'Unknown')} (ID: {t.get('id', 'N/A')}, Dist: {t.get('distance', '?')}ft)" for t in targets]
                move_descriptions.append(f"{name} [Targets: {', '.join(target_names)}]")
            else:
                move_descriptions.append(name)
        moves_str = "; ".join(move_descriptions)

        return (
            f"{player_block}\n\n"
            f"{enemies_block}\n\n"
            f"Recent History:\n{history_str}\n"
            f"Previous Move: {last_move}\n\n"
            f"Available Moves: {moves_str}"
        )
