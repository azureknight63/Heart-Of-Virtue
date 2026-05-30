import logging
from typing import Any, Dict, List, Optional
from ai.llm_client import GenericLLMClient

logger = logging.getLogger(__name__)

# Tactical notes for each status effect, keyed by state name.
# Each entry is (short_effect, strategic_implication).
_STATUS_TACTICAL_NOTES: Dict[str, tuple] = {
    "Disoriented": (
        "−30% finesse, −25% protection",
        "Dodge is less reliable; consider Rest or UseItem instead of defensive moves",
    ),
    "Slimed": (
        "−20% finesse, −15% protection, fatigue drains on movement",
        "Fatigue is burning faster than normal; Rest urgency is elevated",
    ),
    "Resonant": (
        "−25% finesse, armor-piercing DoT every few beats",
        "HP draining through armor; end combat quickly or heal",
    ),
    "Petrified": (
        "−20% finesse, −35% speed, +25% protection",
        "Slower and harder to dodge but tankier; prefer offense over evasion",
    ),
    "Fervent": (
        "+30% strength, +15% finesse, −3 endurance; HP+fatigue drain every 5 beats",
        "Bonus damage now but bleeding resources — press the attack, don't stall",
    ),
    "Poisoned": (
        "DoT: HP draining every beat",
        "Each wasted beat costs HP; aggressive offense to end combat is preferred",
    ),
    "Enflamed": (
        "DoT: HP draining every 3 beats",
        "Time pressure — prioritize finishing the fight quickly",
    ),
    "Hollowed": (
        "HP+fatigue drain every 8 beats, −faith/−charisma/−endurance",
        "Sustained drain; UseItem or Rest only if absolutely necessary",
    ),
    "Hawkeye": (
        "+ranged accuracy",
        "Ranged attacks are more reliable now; prefer them if available",
    ),
    "Dodging": (
        "+evasion active",
        "Already dodging; another Dodge would be redundant",
    ),
    "Parrying": (
        "Parry stance active",
        "Already parrying; wait for the enemy to trigger it",
    ),
}

# Known NPC move damage multipliers relative to the attacker's base damage stat.
# Moves not listed here default to 1.0 (standard NpcAttack range).
_NPC_MOVE_DAMAGE_MULTIPLIERS: Dict[str, float] = {
    "SlimeVolley": 2.2,
    "TidalSurge": 2.5,
    "GorranClub": 2.0,      # damage * uniform(1.5, 3) — use midpoint ~2.25; conservative 2.0
    "VenomClaw": 1.0,        # standard damage + poison application
    "SpiderBite": 1.0,       # standard damage + poison
    "BatBite": 0.85,         # lower damage, drain (uniform 0.7–1.1 midpoint)
}


class CombatStrategist:
    """Strategist that suggests tactical moves during combat using an LLM."""

    def __init__(self, client: Optional[GenericLLMClient] = None):
        logger.info("DEBUG: Initializing CombatStrategist")
        self.client = client or GenericLLMClient()
        self.system_prompt = (
            "You are the Tactical Strategist for Jean Claire, a male human protagonist. "
            "Your goal is to analyze the current combat state and suggest the best moves.\n"
            "Consider Heat (affects damage/XP), Fatigue (resource for moves), and Distance (proximity to enemies).\n"
            "Consider everything provided in the context, including player attributes, consumables, "
            "status effects, and the narrative flow of the combat log.\n\n"

            "HEAT SYSTEM:\n"
            "Heat is Jean's damage multiplier, shown as 'Heat: Nx [label]'. It ranges from 0.5× to 10×.\n"
            "- COLD (< 0.8×): Attacks deal sub-baseline damage. Rebuild heat by landing hits before committing to expensive moves.\n"
            "- WARM (0.8–1.2×): Baseline. Normal offense/defense tradeoffs apply.\n"
            "- HOT (1.2–2.0×): Attacks deal meaningfully bonus damage. Favor offense; avoid missing (miss = ×0.85 heat drop).\n"
            "- BLAZING (> 2.0×): Major damage multiplier active. Press the attack aggressively; "
            "being hit or parried will collapse the combo.\n\n"

            "SITUATIONAL PRIORITIES — apply these before all else:\n"
            "1. FATIGUE CRITICAL (< 25% remaining): Prefer Rest if available. Avoid high-cost offensive moves.\n"
            "2. ENEMY TELEGRAPHING: Dodge and Parry each take 2 beats to become active (1 prep + 1 execute). "
            "They must be cast NOW to be effective. 'beats_until_impact' is the window available: "
            "≤ 2 beats → strongly prefer Dodge/Parry (90+); 1 beat → last chance. "
            "When estimated incoming damage is shown, weigh it against Jean's current HP. "
            "Reduce urgency if Jean's evasion ≥ 15 or combined defense ≥ 10. "
            "If a defensive move is on cooldown, its ETA is shown — factor that into timing.\n"
            "3. STATUS EFFECTS (player and enemy): Each active effect includes a tactical note. Honor it — "
            "e.g. Disoriented on Jean reduces Dodge reliability; Fervent means press the attack; "
            "DoT effects (Poisoned/Enflamed/Resonant) make stalling costly. "
            "Enemy status effects work the same way: Disoriented enemy is easier to hit; "
            "DoT on enemy means finishing the fight is less urgent since time works in your favour.\n"
            "4. HP CRITICAL (< 25%): Prioritize UseItem, Rest, or Withdraw over offense.\n"
            "5. ALLIES: If allies are present, coordinate — focus fire on the weakest or most dangerous "
            "enemy first. Jean can target enemies the ally is already engaging.\n"
            "6. TARGET PRIORITY (multiple enemies): When a 'Target Priority' section is shown, use it. "
            "Attack the highest-priority target unless a more urgent tactical need (e.g. incoming lethal hit "
            "from another enemy) overrides it.\n"
            "7. ENEMY FATIGUE: If an enemy's fatigue is shown as LOW or CRITICAL, "
            "they may Rest next turn instead of attacking — an opportunity to press offense.\n"
            "8. SAFE DISTANCE (enemy > 5ft): Advance is often better than short-reach attacks.\n"
            "9. POINT-BLANK (enemy ≤ 1ft): Dodge or Withdraw before using ranged/sweeping moves.\n\n"

            "Suggest only moves listed in the 'Available Moves' section. "
            "Format each suggestion as a JSON object with:\n"
            "- move_name: The exact name of the move.\n"
            "- target_id: The exact ID of the target (e.g., 'enemy_12345'). "
            "IMPORTANT: If the move requires a target, provide a valid target_id from the Enemies list. "
            "Use null ONLY if the move is strictly self-targeted or non-targeted.\n"
            "- score: 1-100 (tactical advantage estimate).\n"
            "- reasoning: A brief, one-sentence explanation."
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

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

                for s in raw_suggestions:
                    if isinstance(s, dict) and "move_name" in s:
                        try:
                            s["score"] = int(s.get("score", 0))
                        except (ValueError, TypeError):
                            s["score"] = 0
                        suggestions.append(s)

            except Exception as e:
                logger.error(f"DEBUG: Error in LLM suggestion flow: {e}", exc_info=True)

        if not suggestions:
            logger.info("DEBUG: Using heuristic fallback for combat suggestions.")
            return self._get_fallback_suggestions(combat_context, max_suggestions)

        suggestions.sort(key=lambda x: x["score"], reverse=True)
        results = suggestions[:max_suggestions]
        self._ensure_target_ids(results, combat_context)
        logger.info(f"DEBUG: CombatStrategist returning {len(results)} suggestions.")
        return results

    # ------------------------------------------------------------------
    # Heuristic fallback
    # ------------------------------------------------------------------

    def _get_fallback_suggestions(self, combat_context: Dict[str, Any], max_suggestions: int) -> List[Dict[str, Any]]:
        """Provide context-aware suggestions based on combat state when the LLM is unavailable."""
        available = [m for m in combat_context.get("available_moves", []) if m.get("available", True)]
        if not available:
            return [{"move_name": "Check", "target_id": None, "score": 10,
                     "reasoning": "No other moves available; reassess the battlefield."}]

        player = combat_context.get("player", {})
        hp = player.get("hp") or 0
        max_hp = player.get("max_hp") or 1
        fatigue = player.get("fatigue") or 0
        max_fatigue = player.get("max_fatigue") or 1
        heat = float(player.get("heat") or 1.0)

        hp_critical = hp / max_hp < 0.25
        fatigue_critical = fatigue / max_fatigue < 0.25
        fatigue_low = fatigue / max_fatigue < 0.50

        player_stats = player.get("stats", {})
        player_evasion = player_stats.get("evasion", 0)
        player_defense = player_stats.get("defense", 0)
        player_armor = (player.get("equipment", {}).get("armor") or {}).get("defense", 0)
        combined_defense = player_defense + player_armor
        defensively_vulnerable = player_evasion < 15 and combined_defense < 10

        # Active DoT on player accelerates urgency to end combat
        player_status_names = {s.get("name", "") for s in player.get("status_effects", [])}
        dot_active = bool(player_status_names & {"Poisoned", "Enflamed", "Resonant", "Hollowed"})

        # Dodge reliability is impaired by certain status effects
        dodge_impaired = bool(player_status_names & {"Disoriented", "Slimed", "Petrified"})

        # Enemy state: if any enemy has DoT, time is on Jean's side — slightly less aggressive
        enemy_dot_active = any(
            any(s.get("name", "") in {"Poisoned", "Enflamed", "Resonant"} for s in e.get("status_effects", []))
            for e in combat_context.get("enemies", [])
        )
        # If leading enemy is likely to Rest (low fatigue), that's an offensive window
        enemy_likely_resting = any(
            (e.get("fatigue") or 0) / max((e.get("max_fatigue") or e.get("maxfatigue") or 1), 1) < 0.25
            for e in combat_context.get("enemies", [])
        )

        # Beats-until-impact and estimated damage for the most threatening charge
        worst_threat = self._worst_incoming_threat(combat_context.get("enemies", []), hp)
        min_bui = worst_threat["beats_until_impact"]
        est_damage = worst_threat["estimated_damage"]
        est_lethal = worst_threat["potentially_lethal"]

        enemies_in_defensive_window = min_bui <= 2

        # Heat modifiers for offensive scoring
        heat_offensive_bonus = 0
        if heat >= 2.0:
            heat_offensive_bonus = 10   # BLAZING: attack now
        elif heat >= 1.2:
            heat_offensive_bonus = 5    # HOT: lean offensive
        elif heat < 0.8:
            heat_offensive_bonus = -10  # COLD: rebuild before spending resources

        category_scores = {
            "Offensive": 85,
            "Maneuver": 75,
            "Special": 70,
            "Defensive": 65,
            "Miscellaneous": 40,
        }

        scored_moves = []
        for m in available:
            name = m.get("name", "Unknown")
            if name == "Cancel":
                continue

            category = m.get("category", "Miscellaneous")
            base_score = category_scores.get(category, 40)

            # --- Situational overrides, in priority order ---

            if enemies_in_defensive_window and name in ("Dodge", "Parry"):
                if dodge_impaired and not est_lethal:
                    # Status effect reduces defensive move value when the hit is survivable
                    base_score = 60
                    reasoning = (
                        f"Attack in ~{min_bui} beat(s) but status effect impairs {name} reliability; "
                        "consider UseItem or accepting the hit."
                    )
                elif dodge_impaired and est_lethal:
                    # Even impaired, better than a one-shot
                    base_score = 88
                    reasoning = (
                        f"Incoming hit is potentially lethal in ~{min_bui} beat(s); "
                        f"{name} reliability is reduced by status effect but still preferable to dying."
                    )
                elif est_lethal:
                    base_score = 97
                    reasoning = (
                        f"Potentially lethal hit (~{est_damage} dmg) landing in ~{min_bui} beat(s); "
                        f"{name} is critical."
                    )
                elif defensively_vulnerable:
                    base_score = 95
                    reasoning = (
                        f"Attack landing in ~{min_bui} beat(s) and Jean's defenses are low "
                        f"(~{est_damage} estimated dmg); {name} now."
                    )
                else:
                    base_score = 80
                    reasoning = (
                        f"Attack in ~{min_bui} beat(s) (~{est_damage} estimated dmg); "
                        f"{name} is advisable but Jean's defenses may absorb it."
                    )

            elif fatigue_critical and name == "Rest":
                base_score = 90
                reasoning = "Fatigue critically low; Rest is essential to maintain move availability."

            elif hp_critical and name == "UseItem":
                base_score = 88
                reasoning = "HP critically low; use a healing consumable before engaging."

            elif dot_active and category == "Offensive":
                # Player DoT ticking — reward aggression to end the fight
                base_score = min(95, base_score + 8)
                reasoning = f"DoT is draining HP; {name} to end combat quickly."

            elif enemy_likely_resting and category == "Offensive":
                # Enemy likely to Rest next turn — safe offensive window
                base_score = min(95, base_score + 6)
                reasoning = f"Enemy fatigue is critical — they may Rest next turn; {name} to exploit the window."

            elif enemy_dot_active and category == "Offensive":
                # Enemy has DoT — time favours Jean, slightly less frantic
                reasoning = f"Enemy is poisoned/burning — {name} while time works in Jean's favour."

            elif fatigue_low and name in ("Wait", "Rest"):
                base_score = 72
                reasoning = f"Fatigue is low; {name} conserves resources for a better opportunity."

            elif name == "Advance":
                base_score = 80
                reasoning = "Close the distance to bring offensive moves into range."

            elif name in ("Wait", "Check"):
                base_score = 20
                reasoning = f"{name} cedes initiative; use only if no better option exists."

            elif category == "Offensive":
                base_score = min(99, base_score + heat_offensive_bonus)
                if heat >= 2.0:
                    reasoning = f"Heat is BLAZING ({heat:.1f}×); {name} for amplified damage — don't miss."
                elif heat >= 1.2:
                    reasoning = f"Heat is elevated ({heat:.1f}×); {name} while the combo holds."
                elif heat < 0.8:
                    reasoning = f"Heat is low ({heat:.1f}×); {name} to rebuild combo before committing."
                else:
                    reasoning = f"Tactical analysis unavailable; {name} is a viable fallback."

            else:
                reasoning = f"Tactical analysis unavailable; {name} is a viable fallback."

            scored_moves.append({
                "move_name": name,
                "target_id": None,
                "score": base_score,
                "reasoning": reasoning,
            })

        scored_moves.sort(key=lambda x: x["score"], reverse=True)

        if not scored_moves:
            scored_moves.append({
                "move_name": available[0].get("name", "Wait"),
                "target_id": None,
                "score": 10,
                "reasoning": "Standard tactical fallback; maintaining position.",
            })

        results = scored_moves[:max(1, min(3, max_suggestions))]
        self._ensure_target_ids(results, combat_context)
        return results

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    def _build_user_prompt(self, ctx: Dict[str, Any]) -> str:
        """Construct the context string for the LLM."""
        player = ctx.get("player", {})
        pos = player.get("position") or {}

        # Urgency flags
        hp = player.get("hp") or 0
        max_hp = player.get("max_hp") or 1
        fatigue = player.get("fatigue") or 0
        max_fatigue = player.get("max_fatigue") or 1
        heat = float(player.get("heat") or 1.0)
        hp_pct = hp / max_hp
        fatigue_pct = fatigue / max_fatigue
        hp_flag = " ⚠ HP CRITICAL" if hp_pct < 0.25 else (" LOW" if hp_pct < 0.50 else "")
        fatigue_flag = " ⚠ FATIGUE CRITICAL" if fatigue_pct < 0.25 else (" LOW" if fatigue_pct < 0.50 else "")

        # Heat label
        if heat >= 2.0:
            heat_label = f"{heat:.2f}× [BLAZING — attacks deal +{int((heat-1)*100)}% damage; protect this streak]"
        elif heat >= 1.2:
            heat_label = f"{heat:.2f}× [HOT — attacks deal +{int((heat-1)*100)}% bonus damage]"
        elif heat < 0.8:
            heat_label = f"{heat:.2f}× [COLD — attacks deal −{int((1-heat)*100)}% damage; land hits to rebuild]"
        else:
            heat_label = f"{heat:.2f}× [WARM — baseline damage]"

        p_attrs = ", ".join([f"{k}: {v}" for k, v in player.get("attributes", {}).items()])
        passives = self._extract_names(player.get("passives", []))

        p_stats = player.get("stats", {})
        p_evasion = p_stats.get("evasion", 0)
        p_defense = p_stats.get("defense", 0)
        p_armor_def = (player.get("equipment", {}).get("armor") or {}).get("defense", 0)

        p_consumables = ", ".join([
            f"{c.get('name', 'Item')} (Qty: {c.get('qty', 1)})"
            for c in player.get("consumables", [])
        ])

        # Status effects with mechanical context
        status_lines = self._format_status_effects(player.get("status_effects", []))

        player_block = (
            f"Player: {player.get('name', 'Jean')} (Male Human) "
            f"[HP: {hp}/{max_hp}{hp_flag}, "
            f"Fatigue: {fatigue}/{max_fatigue}{fatigue_flag}, "
            f"Heat: {heat_label}, "
            f"Pos: {pos.get('x')},{pos.get('y')}, Facing: {pos.get('facing')}]\n"
            f"Attributes: [{p_attrs}]\n"
            f"Combat Stats: [Evasion: {p_evasion}, Defense: {p_defense}, "
            f"Armor Defense: {p_armor_def}, Accuracy: {p_stats.get('accuracy', 80)}, "
            f"Speed: {p_stats.get('speed', 0)}]\n"
            f"Passives: {', '.join(passives) or 'None'}\n"
            f"Status Effects:\n{status_lines}\n"
            f"Consumables: [{p_consumables or 'None'}]"
        )

        # Enemies — beats_until_impact, estimated damage, status effects, fatigue
        enemy_list = []
        imminent_alerts = []
        enemies = ctx.get("enemies", [])
        for e in enemies:
            e_pos = e.get("position") or {}
            e_fatigue = e.get("fatigue", 0)
            e_max_fatigue = e.get("max_fatigue") or e.get("maxfatigue") or 1
            e_fat_pct = e_fatigue / e_max_fatigue if e_max_fatigue else 1.0
            fat_tag = " ⚠ FATIGUE CRITICAL — likely to Rest" if e_fat_pct < 0.25 else (
                " [fatigue LOW]" if e_fat_pct < 0.50 else ""
            )

            mip = e.get("move_in_process")
            mip_str = ""
            if mip:
                bui = self._beats_until_impact(mip)
                threat = self._estimate_incoming_damage(mip, e, hp)
                est_dmg = threat["estimated_damage"]
                lethal = threat["potentially_lethal"]

                lethal_tag = " ⚠ POTENTIALLY LETHAL" if lethal else ""
                mip_str = (
                    f", Charging: {mip.get('name')} "
                    f"({bui} beat{'s' if bui != 1 else ''} until impact, "
                    f"~{est_dmg} estimated dmg{lethal_tag})"
                )

                if bui <= 2:
                    qualifier = "Dodge/Parry NOW" if bui >= 2 else "last-chance Dodge/Parry"
                    vuln_note = (
                        f" Jean's evasion ({p_evasion}) and defense ({p_defense + p_armor_def}) "
                        "are low — this will hurt."
                        if p_evasion < 15 and (p_defense + p_armor_def) < 10
                        else " Jean's defenses may reduce impact."
                    )
                    imminent_alerts.append(
                        f"⚠ INCOMING: {e.get('name')} lands {mip.get('name')} "
                        f"in ~{bui} beat(s) (~{est_dmg} dmg{', LETHAL' if lethal else ''}). "
                        f"{qualifier}.{vuln_note}"
                    )

            # Enemy status effects
            e_statuses = self._format_status_effects(e.get("status_effects", []))
            status_str = f"\n    Status: {e_statuses.strip()}" if e_statuses.strip() != "None" else ""

            enemy_list.append(
                f"- {e.get('name')} [ID: {e.get('id')}, "
                f"HP: {e.get('hp')}/{e.get('max_hp')}, "
                f"Fatigue: {e_fatigue}/{e_max_fatigue}{fat_tag}, "
                f"Pos: {e_pos.get('x')},{e_pos.get('y')}, "
                f"Dist: {e.get('distance')}ft{mip_str}]{status_str}"
            )
        enemies_block = "Enemies:\n" + "\n".join(enemy_list)

        # Allies block
        allies = ctx.get("allies", [])
        if allies:
            ally_lines = []
            for a in allies:
                a_pos = a.get("position") or {}
                ally_lines.append(
                    f"- {a.get('name')} [ID: {a.get('id')}, "
                    f"HP: {a.get('hp')}/{a.get('max_hp')}, "
                    f"Pos: {a_pos.get('x')},{a_pos.get('y')}, "
                    f"Dist: {a.get('distance')}ft]"
                )
            allies_block = "Allies (friendly — do not attack):\n" + "\n".join(ally_lines) + "\n"
        else:
            allies_block = ""

        # Defensive cooldown ETAs
        def_cooldowns = ctx.get("defensive_cooldowns", {})
        if def_cooldowns:
            cd_parts = [f"{name} in {beats} beat{'s' if beats != 1 else ''}" for name, beats in def_cooldowns.items()]
            cooldown_note = "Defensive moves on cooldown: " + ", ".join(cd_parts) + "\n"
        else:
            cooldown_note = ""

        # Multi-enemy target priority
        priority_block = self._build_target_priority(enemies, hp) if len(enemies) > 1 else ""

        # Available moves — fatigue cost + description
        move_descriptions = []
        for m in ctx.get("available_moves", []):
            if not m.get("available", True):
                continue
            name = m.get("name")
            cost = m.get("fatigue_cost", 0)
            desc = m.get("description", "")
            cost_str = f" [Cost: {cost} fatigue]" if cost else " [No fatigue cost]"
            desc_str = f" — {desc}" if desc else ""
            targets = m.get("viable_targets", [])
            if targets:
                target_info = ", ".join([
                    f"{t.get('name')} (ID: {t.get('id')}, {t.get('distance')}ft)"
                    for t in targets
                ])
                move_descriptions.append(f"{name}{cost_str} [Targets: {target_info}]{desc_str}")
            else:
                move_descriptions.append(f"{name}{cost_str}{desc_str}")

        # Situational alert block
        alerts = []
        if hp_pct < 0.25:
            alerts.append("⚠ HP CRITICAL: Prioritize healing or defensive moves.")
        if fatigue_pct < 0.25:
            alerts.append("⚠ FATIGUE CRITICAL: Prefer Rest or zero-cost moves.")
        if heat >= 2.0:
            alerts.append(f"⚠ BLAZING HEAT ({heat:.2f}×): Maximize offense now — missing or being hit collapses the combo.")
        elif heat < 0.8:
            alerts.append(f"⚠ COLD HEAT ({heat:.2f}×): Land hits to rebuild combo before using expensive moves.")
        alerts.extend(imminent_alerts)
        alert_block = ("\nSITUATIONAL ALERTS:\n" + "\n".join(alerts) + "\n") if alerts else ""

        history_str = "\n".join(ctx.get("history", [])[-5:])
        return (
            f"{player_block}\n\n"
            f"{enemies_block}\n"
            f"{allies_block}"
            f"{cooldown_note}"
            f"{priority_block}"
            f"{alert_block}\n"
            f"Recent History:\n{history_str}\n"
            f"Previous Move: {ctx.get('last_move', 'None')}\n\n"
            f"Available Moves:\n" + "\n".join(f"  {d}" for d in move_descriptions)
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _format_status_effects(self, status_effects: List[Any]) -> str:
        """Render status effects with mechanical notes and remaining duration."""
        if not status_effects:
            return "  None"
        lines = []
        for s in status_effects:
            if not s:
                continue
            name = s.get("name", "Unknown") if isinstance(s, dict) else str(s)
            beats_left = s.get("beats_left", 0) if isinstance(s, dict) else 0
            duration_str = f", ~{beats_left} beats remaining" if beats_left > 0 else ""
            note_entry = _STATUS_TACTICAL_NOTES.get(name)
            if note_entry:
                effect_str, implication = note_entry
                lines.append(f"  {name} ({effect_str}{duration_str}) → {implication}")
            else:
                desc = s.get("description", "") if isinstance(s, dict) else ""
                lines.append(f"  {name}{duration_str}{': ' + desc if desc else ''}")
        return "\n".join(lines) if lines else "  None"

    @staticmethod
    def _beats_until_impact(mip: Dict[str, Any]) -> int:
        """
        Estimate beats until a charging enemy move lands.

        beats_left only covers the current stage. If the move is still in
        prep (current_stage == 0) we add one execute beat so callers see the
        full window before impact rather than just remaining prep time.
        """
        if not mip:
            return 99
        beats_left = mip.get("beats_left", 99)
        current_stage = mip.get("current_stage", 0)
        if current_stage == 0:
            return beats_left + 1  # remaining prep + one execute beat
        return beats_left

    @staticmethod
    def _estimate_incoming_damage(
        mip: Dict[str, Any],
        enemy: Dict[str, Any],
        player_hp: int,
    ) -> Dict[str, Any]:
        """
        Estimate damage range for a telegraphed enemy move.

        Uses the enemy's serialized damage stat and the known multiplier for
        the move name (falling back to 1.0 for unknown moves). Protection is
        not available for the enemy's view of the player, so the estimate is
        conservative (raw power before mitigation).
        """
        move_name = mip.get("name", "")
        multiplier = _NPC_MOVE_DAMAGE_MULTIPLIERS.get(move_name, 1.0)
        enemy_damage = (enemy.get("stats") or {}).get("damage", 0) or enemy.get("damage", 0)

        low = max(0, int(enemy_damage * multiplier * 0.8))
        high = max(0, int(enemy_damage * multiplier * 1.2))
        midpoint = (low + high) // 2

        return {
            "estimated_damage": f"{low}–{high}",
            "midpoint": midpoint,
            "potentially_lethal": midpoint >= player_hp * 0.5,  # hits for 50%+ of current HP
        }

    def _worst_incoming_threat(
        self, enemies: List[Dict[str, Any]], player_hp: int
    ) -> Dict[str, Any]:
        """Return the combined threat metrics for the most dangerous incoming charge."""
        best = {"beats_until_impact": 99, "estimated_damage": "0–0", "potentially_lethal": False}
        for e in enemies:
            mip = e.get("move_in_process")
            if not mip:
                continue
            bui = self._beats_until_impact(mip)
            threat = self._estimate_incoming_damage(mip, e, player_hp)
            if bui < best["beats_until_impact"] or (
                bui == best["beats_until_impact"] and threat["potentially_lethal"]
            ):
                best = {**threat, "beats_until_impact": bui}
        return best

    def _build_target_priority(self, enemies: List[Dict[str, Any]], player_hp: int) -> str:
        """
        Rank enemies by threat when multiple are present.

        Priority: (1) incoming lethal charge, (2) incoming non-lethal charge,
        (3) lowest HP% (finish them off), (4) default order.
        """
        scored = []
        for e in enemies:
            mip = e.get("move_in_process")
            lethal = False
            bui = 99
            if mip:
                bui = self._beats_until_impact(mip)
                threat = self._estimate_incoming_damage(mip, e, player_hp)
                lethal = threat["potentially_lethal"]

            hp = e.get("hp") or 0
            max_hp = e.get("max_hp") or 1
            hp_pct = hp / max_hp

            # Score: lower is higher priority
            priority = (
                0 if (lethal and bui <= 2) else
                1 if (mip and bui <= 2) else
                2 if hp_pct < 0.30 else
                3
            )
            scored.append((priority, hp_pct, e))

        scored.sort(key=lambda x: (x[0], x[1]))

        lines = ["Target Priority (highest → lowest):"]
        for rank, (priority, hp_pct, e) in enumerate(scored, 1):
            mip = e.get("move_in_process")
            reason = (
                "incoming LETHAL charge" if priority == 0 else
                "incoming charge" if priority == 1 else
                f"low HP ({int(hp_pct * 100)}%)" if priority == 2 else
                "standard threat"
            )
            lines.append(f"  {rank}. {e.get('name')} (ID: {e.get('id')}) — {reason}")
        return "\n".join(lines) + "\n"

    def _ensure_target_ids(self, suggestions: List[Dict[str, Any]], context: Dict[str, Any]):
        """Ensure targeted moves have a target_id, auto-filling if missing."""
        enemies = context.get("enemies", [])
        primary_target_id = enemies[0].get("id") if enemies else None
        targeted_move_names = {
            m.get("name") for m in context.get("available_moves", []) if m.get("targeted")
        }
        for s in suggestions:
            if s.get("move_name") in targeted_move_names and not s.get("target_id"):
                logger.info(f"DEBUG: Strategist auto-filling missing target_id for '{s.get('move_name')}'")
                s["target_id"] = primary_target_id

    def _extract_names(self, items: List[Any]) -> List[str]:
        """Extract 'name' from a list of objects or dicts."""
        extracted = []
        for item in items:
            if not item:
                continue
            if isinstance(item, dict):
                name = item.get("name")
                if name:
                    extracted.append(str(name))
            else:
                extracted.append(str(item))
        return extracted
