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
            "You are the Tactical Strategist for Jean Claire, a male human protagonist. Your goal is to analyze the current combat state and suggest the best moves.\n"
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
        """Fetch movement suggestions from the LLM or fallback to heuristics."""
        logger.info(f"DEBUG: CombatStrategist.get_suggestions called (max: {max_suggestions})")
        
        suggestions = []
        if self.client.available():
            try:
                user_prompt = self._build_user_prompt(combat_context)
                wrapped_prompt = (
                    f"{user_prompt}\nReturn the result as a JSON object with a key 'suggestions' "
                    f"containing a list of exactly {max_suggestions} move objects."
                )
                
                logger.info(f"DEBUG: Requesting {max_suggestions} suggestions for {combat_context.get('player', {}).get('name')}")
                raw_response = self.client.generate_structured(self.system_prompt, wrapped_prompt)
                
                if isinstance(raw_response, dict):
                    raw_suggestions = raw_response.get("suggestions", [])
                elif isinstance(raw_response, list):
                    raw_suggestions = raw_response
                else:
                    raw_suggestions = []

                # Sanitize and validate suggestions from LLM
                for s in raw_suggestions:
                    if isinstance(s, dict) and "move_name" in s:
                        try:
                            s["score"] = int(s.get("score", 0))
                        except (ValueError, TypeError):
                            s["score"] = 0
                        suggestions.append(s)

            except Exception as e:
                logger.error(f"DEBUG: Error in LLM suggestion flow: {e}", exc_info=True)

        # If LLM failed or provided no valid suggestions, use fallback
        if not suggestions:
            logger.info("DEBUG: Using heuristic fallback for combat suggestions.")
            return self._get_fallback_suggestions(combat_context, max_suggestions)

        # Post-process: sort, limit, and ensure targets
        suggestions.sort(key=lambda x: x["score"], reverse=True)
        results = suggestions[:max_suggestions]
        
        self._ensure_target_ids(results, combat_context)
        logger.info(f"DEBUG: CombatStrategist returning {len(results)} suggestions.")
        return results

    def _ensure_target_ids(self, suggestions: List[Dict[str, Any]], context: Dict[str, Any]):
        """Ensure targeted moves have a target_id, auto-filling if missing."""
        enemies = context.get("enemies", [])
        primary_target_id = enemies[0].get("id") if enemies else None
        
        targeted_move_names = {
            m.get("name") for m in context.get("available_moves", []) 
            if m.get("targeted")
        }
        
        for s in suggestions:
            if s.get("move_name") in targeted_move_names and not s.get("target_id"):
                logger.info(f"DEBUG: Strategist auto-filling missing target_id for '{s.get('move_name')}'")
                s["target_id"] = primary_target_id

    def _get_fallback_suggestions(self, combat_context: Dict[str, Any], max_suggestions: int) -> List[Dict[str, Any]]:
        """Provide basic suggestions based on move categories if the LLM fails."""
        available = [m for m in combat_context.get("available_moves", []) if m.get("available", True)]
        if not available:
            return [{
                "move_name": "Check", "target_id": None, "score": 10,
                "reasoning": "No other moves available; reassess the battlefield."
            }]

        # Scoring weights for fallback
        category_scores = {
            "Offensive": 85,
            "Maneuver": 75,
            "Special": 70,
            "Defensive": 65,
            "Miscellaneous": 40
        }
        
        scored_moves = []
        for m in available:
            name = m.get("name", "Unknown")
            if name in ["Cancel"]: continue
            
            category = m.get("category", "Miscellaneous")
            base_score = category_scores.get(category, 40)
            
            # Specific move adjustments
            if name == "Advance": base_score = 80
            elif name in ["Wait", "Check"]: base_score = 20

            scored_moves.append({
                "move_name": name,
                "target_id": None, # Will be filled by _ensure_target_ids
                "score": base_score,
                "reasoning": f"Tactical analysis delayed; {name} is a viable tactical alternative."
            })

        scored_moves.sort(key=lambda x: x["score"], reverse=True)
        
        # FINAL SAFETY: If we somehow ended up with no scored moves but had available ones,
        # just take the first available one to avoid returning an empty list.
        if not scored_moves and available:
            scored_moves.append({
                "move_name": available[0].get("name", "Wait"),
                "target_id": None,
                "score": 10,
                "reasoning": "Standard tactical fallback; maintaining position."
            })
            
        results = scored_moves[:max(1, min(3, max_suggestions))]
        self._ensure_target_ids(results, combat_context)
        return results

    def _build_user_prompt(self, ctx: Dict[str, Any]) -> str:
        """Construct the context string for the LLM."""
        player = ctx.get("player", {})
        pos = player.get("position") or {}
        
        # Player Stats & Effects
        p_attrs = ", ".join([f"{k}: {v}" for k, v in player.get("attributes", {}).items()])
        passives = self._extract_names(player.get('passives', []))
        statuses = self._extract_names(player.get('status_effects', []))
        
        p_consumables = ", ".join([
            f"{c.get('name', 'Item')} (Qty: {c.get('qty', 1)})" 
            for c in player.get("consumables", [])
        ])

        player_block = (
            f"Player: {player.get('name', 'Jean')} (Male Human) [HP: {player.get('hp')}/{player.get('max_hp')}, "
            f"Fatigue: {player.get('fatigue')}/{player.get('max_fatigue')}, Heat: {player.get('heat')}, "
            f"Pos: {pos.get('x')},{pos.get('y')}, Facing: {pos.get('facing')}]\n"
            f"Attributes: [{p_attrs}]\n"
            f"Passives: {', '.join(passives)}\n"
            f"Status: {', '.join(statuses)}\n"
            f"Consumables: [{p_consumables or 'None'}]"
        )

        # Enemies
        enemy_list = []
        for e in ctx.get("enemies", []):
            e_pos = e.get("position") or {}
            mip = e.get("move_in_process")
            mip_str = f", Charging: {mip.get('name')} ({mip.get('beats_left')} beats)" if mip else ""
            enemy_list.append(
                f"- {e.get('name')} [ID: {e.get('id')}, HP: {e.get('hp')}/{e.get('max_hp')}, "
                f"Pos: {e_pos.get('x')},{e_pos.get('y')}, Dist: {e.get('distance')}ft{mip_str}]"
            )
        enemies_block = "Enemies:\n" + "\n".join(enemy_list)

        # Move Options
        move_descriptions = []
        for m in ctx.get("available_moves", []):
            if not m.get("available", True): continue
            name = m.get("name")
            targets = m.get("viable_targets", [])
            if targets:
                target_info = ", ".join([f"{t.get('name')} (ID: {t.get('id')}, {t.get('distance')}ft)" for t in targets])
                move_descriptions.append(f"{name} [Targets: {target_info}]")
            else:
                move_descriptions.append(name)
        
        history_str = "\n".join(ctx.get("history", [])[-5:])
        return (
            f"{player_block}\n\n{enemies_block}\n\n"
            f"Recent History:\n{history_str}\n"
            f"Previous Move: {ctx.get('last_move', 'None')}\n\n"
            f"Available Moves: {'; '.join(move_descriptions)}"
        )

    def _extract_names(self, items: List[Any]) -> List[str]:
        """Helper to extract 'name' from a list of objects or dictionaries."""
        extracted = []
        for item in items:
            if not item: continue
            if isinstance(item, dict):
                name = item.get('name')
                if name: extracted.append(str(name))
            else:
                extracted.append(str(item))
        return extracted
