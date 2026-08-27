import logging
from typing import Any, Dict, List, Optional, Tuple

from ai.llm_client import GenericLLMClient

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tactical thresholds
# ---------------------------------------------------------------------------
# Every number the strategist reasons with lives here exactly once. It used to
# be re-typed independently into three places that must agree — the static
# system prompt's prose, the heuristic fallback's scoring, and the runtime
# prompt builder's labels and alerts — with nothing linking them: the heat
# bands appeared at five sites, the 25%/50% HP and fatigue bands at nine, and
# "defensively vulnerable" existed in three mutually incompatible encodings.
# _SYSTEM_PROMPT below is an f-string over these constants, so the rule the
# model is told and the rule the code applies cannot drift apart.
_HP_CRITICAL_PCT = 0.25
_HP_LOW_PCT = 0.50
_FATIGUE_CRITICAL_PCT = 0.25
_FATIGUE_LOW_PCT = 0.50

# An enemy below this HP fraction is worth finishing off before a healthier one.
_FINISHABLE_HP_PCT = 0.30

_HEAT_BLAZING = 2.0
_HEAT_HOT = 1.2
_HEAT_COLD = 0.8
# ENGINE-OWNED. src/moves/_base.py Move.miss() calls change_heat(0.85) on Jean.
# Restated here only so the prompt can quote the cost of a miss; if that call
# changes, change this with it.
_HEAT_MISS_PENALTY = 0.85

# Dodge and Parry each take 1 prep + 1 execute beat, so a hit landing within
# this many beats is still (barely) defensible.
_DEFENSIVE_WINDOW_BEATS = 2

# Below both of these Jean's defenses will not meaningfully absorb a hit.
_LOW_EVASION = 15
_LOW_DEFENSE = 10

# A telegraphed hit is flagged potentially lethal at this fraction of current HP.
_LETHAL_HP_FRACTION = 0.5


def _pct(fraction: float) -> str:
    """Render a 0-1 threshold as the integer percentage the prompt prose uses."""
    return f"{int(round(fraction * 100))}%"


def _is_defensively_vulnerable(evasion: Any, combined_defense: Any) -> bool:
    """True when Jean's defenses will not meaningfully absorb an incoming hit.

    One encoding of the rule, used by both the heuristic fallback's scoring and
    the runtime prompt's vulnerability note. The system prompt states the
    complement of it ("reduce urgency if evasion >= X or combined defense >= Y")
    off the same two constants.
    """
    return (evasion or 0) < _LOW_EVASION and (combined_defense or 0) < _LOW_DEFENSE


def _player_defenses(player: Dict[str, Any]) -> Tuple[int, int]:
    """Return ``(evasion, defense + armor defense)`` from a serialized player."""
    stats = player.get("stats") or {}
    evasion = stats.get("evasion", 0)
    defense = stats.get("defense", 0)
    armor_defense = ((player.get("equipment") or {}).get("armor") or {}).get(
        "defense", 0
    )
    return evasion, defense + armor_defense


def _enemy_max_fatigue(enemy: Dict[str, Any]) -> int:
    """Max fatigue for a serialized enemy, tolerating both wire spellings.

    ``CombatantSerializer`` emits ``max_fatigue`` and its legacy ``maxfatigue``
    alias; never trust either alone, and never divide by zero.
    """
    return max(enemy.get("max_fatigue") or enemy.get("maxfatigue") or 1, 1)


def _incoming_beats(mip: Optional[Dict[str, Any]]) -> Optional[int]:
    """Beats until a charging enemy move lands, or None if nothing is coming.

    A pure read of the wire field ``beats_until_resolve``, which the engine
    computes in ``Move.beats_until_resolve`` (src/moves/_base.py) and the
    serializer puts on the payload. Deliberately performs NO arithmetic: this
    module used to walk the stage machine itself, and the copy had drifted from
    the engine in all three of its branches. The damaging one was recoil and
    cooldown — ``move_in_progress`` (src/combatant.py) intentionally keeps
    returning a move through its aftermath stages, so a move that had ALREADY
    HIT still carried a small ``beats_left`` and got announced to the model as
    an incoming attack, spending Jean's beat on a phantom Dodge.

    The engine returns None for exactly that case; None here means "not
    incoming", and every caller must skip rather than substitute a sentinel.
    """
    if not mip:
        return None
    beats = mip.get("beats_until_resolve")
    if isinstance(beats, bool) or not isinstance(beats, int):
        return None
    return beats


# What a status effect MEANS for Jean, from both sides of the fight.
#
# Advice only. The effect's numbers are NOT here: they are the engine's, and
# they arrive on the wire as ``tactical_mechanics``, which every State
# interpolates from the same class constants its ``add_*`` assignments use
# (src/states.py). This table used to carry a hand-typed ``mechanics`` column
# beside the notes, and it had already gone stale in three places — it told the
# model Poisoned ticks every beat when ``Poisoned._EXECUTE_ON`` is 5, that
# Enflamed ticks every 3 beats when it burns every single one, and that Slimed
# drains fatigue, which it has never done. A wrong number in a combat prompt is
# worse than a missing one, so the numbers have exactly one owner now and this
# module contributes only the half an engine cannot know: which side of the
# fight is holding the effect.
#
# ``player_note`` and ``enemy_note`` are both written from JEAN's point of view
# (an enemy's Parrying reads "do not attack", not "you are parrying").
_STATUS_TACTICAL_NOTES: Dict[str, Dict[str, str]] = {
    "Disoriented": {
        "player_note": (
            "Dodge is less reliable; consider Rest or UseItem instead of "
            "defensive moves"
        ),
        "enemy_note": (
            "Easier to hit — press offense while their accuracy and defense "
            "are reduced"
        ),
    },
    "Slimed": {
        # Advice, not mechanics: this used to read "fatigue is burning faster
        # than normal", which Slimed has never done — it is an HP acid tick.
        "player_note": (
            "Acid is eating HP on a timer; end the fight rather than trade beats"
        ),
        "enemy_note": "Impaired and draining — good time to press the attack",
    },
    "Resonant": {
        "player_note": "HP draining through armor; end combat quickly or heal",
        "enemy_note": "Taking sustained damage — time is working in Jean's favour",
    },
    "Petrified": {
        "player_note": (
            "Slower and harder to dodge but tankier; prefer offense over evasion"
        ),
        "enemy_note": (
            "Slower but tankier — finesse-based moves may be less effective; "
            "sustain pressure"
        ),
    },
    "Fervent": {
        "player_note": (
            "Bonus damage now but bleeding resources — press the attack, don't stall"
        ),
        "enemy_note": (
            "Dealing more damage but bleeding resources — play defensively and "
            "outlast them"
        ),
    },
    "Poisoned": {
        "player_note": (
            "Each wasted beat costs HP; aggressive offense to end combat is preferred"
        ),
        "enemy_note": (
            "Time works in Jean's favour — no need to rush; avoid unnecessary risk"
        ),
    },
    "Enflamed": {
        "player_note": "Time pressure — prioritize finishing the fight quickly",
        "enemy_note": "Burning down — steady pressure is enough; avoid overcommitting",
    },
    "Hollowed": {
        "player_note": "Sustained drain; UseItem or Rest only if absolutely necessary",
        "enemy_note": "Weakening over time — Jean can afford a measured approach",
    },
    "Hawkeye": {
        "player_note": "Ranged attacks are more reliable now; prefer them if available",
        "enemy_note": (
            "Their ranged attacks are more reliable — close the distance or break "
            "line of fire"
        ),
    },
    "Dodging": {
        "player_note": "Already dodging; another Dodge would be redundant",
        "enemy_note": (
            "Harder to land hits right now — consider waiting a beat or using a "
            "guaranteed move"
        ),
    },
    "Parrying": {
        "player_note": "Already parrying; wait for the enemy to trigger it",
        "enemy_note": (
            "Do not attack — they will parry and deal recoil damage; wait for "
            "stance to expire"
        ),
    },
}


# Kept deliberately terse: this block is static and re-sent on every
# combat turn, so prose here is paid for once per beat forever. Trimming
# it from 795 to 490 tokens preserved all nine priorities, every
# threshold the model needs statically, and the output contract (the
# 2.0x BLAZING band moved to the runtime heat label and alert block).
#
# Do not trim the "between the two it is baseline" clause or the fatigue
# framing above the priorities. An earlier pass cut both as redundant --
# the heat bands were only ever described at the extremes -- and the
# model started answering Rest for a healthy player at 80% fatigue with
# no incoming threat, because nothing told it what to do at heat 1.0.
# It reproduced 3/3 against the trimmed prompt and 0/3 against this one.
# tests/integration/test_tactical_advisor_live.py is the guard; re-run
# it after editing this string.
_SYSTEM_PROMPT = (
    "You are the Tactical Strategist for Jean Claire (male human). Analyze the combat "
    "state and suggest the best moves. Weigh everything given: attributes, consumables, "
    "status effects, and the combat log's narrative flow.\n\n"
    "HEAT is Jean's damage/XP multiplier (0.5×–10×); the context labels the current band. "
    f"Above {_HEAT_HOT}×, favor offense and protect the streak — a miss drops heat "
    f"×{_HEAT_MISS_PENALTY}. "
    f"Below {_HEAT_COLD}×, land cheap hits to rebuild before committing to expensive moves. "
    "Between the two it is baseline: offense and defense trade evenly, so act on "
    "the situation.\n\n"
    "Fatigue is a resource to spend, not to hoard: Rest only when priority 1 or 4 "
    "below actually applies.\n\n"
    "PRIORITIES, in order:\n"
    f"1. Fatigue < {_pct(_FATIGUE_CRITICAL_PCT)}: prefer Rest; avoid high-cost offense.\n"
    "2. Telegraphed attack: Dodge/Parry take 2 beats (1 prep + 1 execute), so cast NOW. "
    f"beats_until_impact ≤ {_DEFENSIVE_WINDOW_BEATS} → strongly prefer them (90+); "
    "1 beat is the last chance. "
    f"Weigh estimated incoming damage against Jean's HP; reduce urgency if evasion ≥ "
    f"{_LOW_EVASION} or combined defense ≥ {_LOW_DEFENSE}. "
    "Cooldown ETAs are shown for unavailable defensive moves.\n"
    "3. Status effects: each carries a tactical note — honor it. Enemy effects are "
    "already written from Jean's perspective.\n"
    f"4. HP < {_pct(_HP_CRITICAL_PCT)}: prefer UseItem, Rest, or Withdraw over offense.\n"
    "5. Allies present: focus fire the weakest or most dangerous enemy; Jean may target "
    "what an ally is already engaging.\n"
    "6. Target Priority section, when shown, wins unless a more urgent threat "
    "(e.g. incoming lethal hit) overrides it.\n"
    "7. Enemy fatigue LOW/CRITICAL: they may Rest instead of attacking — press offense.\n"
    "8. Enemy > 5ft: Advance usually beats a short-reach attack.\n"
    "9. Enemy ≤ 1ft: Dodge or Withdraw before ranged/sweeping moves.\n\n"
    "Suggest only moves from 'Available Moves'. Each suggestion is a JSON object:\n"
    "- move_name: exact move name.\n"
    "- target_id: exact ID from the Enemies list when the move needs a target "
    "(e.g. 'enemy_12345'); null ONLY for self-targeted or non-targeted moves.\n"
    "- score: 1-100 tactical advantage.\n"
    "- reasoning: one brief sentence."
)


def wrap_suggestions_prompt(user_prompt: str, max_suggestions: int) -> str:
    """Wrap a built combat context with the JSON output instruction.

    Public because the shape of the request the model actually receives is not
    only ``get_suggestions``' business: ``tools/measure_llm_tokens.py`` sizes
    the real production prompt and used to keep a hand-copy of this f-string,
    with a comment admitting it "mirrors that wrapper exactly". It is the
    wrapper now — import it rather than restating it.
    """
    return (
        f"{user_prompt}\nReturn the result as a JSON object with a key 'suggestions' "
        f"containing a list of exactly {max_suggestions} move objects."
    )


class CombatLLMAdapter(GenericLLMClient):
    """``GenericLLMClient`` with per-feature combat overrides.

    The base client reads only the global ``MYNX_LLM_*`` variables, so the
    strategist could not be pointed at a different model without moving Mynx
    too — and the two want opposite things: combat runs a request per beat and
    wants something fast and cheap, Mynx runs occasionally and wants something
    capable. Mirrors the convention ``NpcChatLLMAdapter`` established for NPC
    chat (ai/llm_client.py).

      - COMBAT_LLM_ENABLED=1                  -> override MYNX_LLM_ENABLED
      - COMBAT_LLM_PROVIDER=ollama|openrouter -> override MYNX_LLM_PROVIDER
      - COMBAT_LLM_MODEL=<model_id>           -> override MYNX_LLM_MODEL

    Each list falls back to the MYNX_* name, so an existing MYNX_*-only
    configuration keeps working exactly as before.
    """

    # Declared as data rather than re-applied after super().__init__(): the
    # base class resolves the gate, runs model discovery and validates the
    # provider *inside* __init__, so an override applied afterwards had combat
    # dialling a host the base class had checked for nothing. See
    # GenericLLMClient._resolve_provider.
    #
    # The gate DOES fall back to MYNX_LLM_ENABLED, where NpcChatLLMAdapter's
    # deliberately does not, and the difference is real rather than an
    # oversight. Chat is player-authored prose being shipped to a third party,
    # so switching on the mynx pet must not switch that on by implication.
    # Combat is not: the strategist reads a battlefield the operator's own
    # engine produced, and until this branch it was a bare GenericLLMClient
    # gated on MYNX_LLM_ENABLED alone. Dropping the fallback would silently
    # turn the Tactical Advisor off on every existing install at upgrade — a
    # regression, not a tightening. An explicit COMBAT_LLM_ENABLED=0 still
    # wins, because _first_env takes the first non-empty value.
    _ENABLED_ENV_VARS = ("COMBAT_LLM_ENABLED", "MYNX_LLM_ENABLED")
    _PROVIDER_ENV_VARS = ("COMBAT_LLM_PROVIDER", "MYNX_LLM_PROVIDER")
    _MODEL_ENV_VARS = ("COMBAT_LLM_MODEL", "MYNX_LLM_MODEL")


class CombatStrategist:
    """Strategist that suggests tactical moves during combat using an LLM."""

    def __init__(self, client: Optional[GenericLLMClient] = None):
        logger.debug("Initializing CombatStrategist")
        self.client = client or CombatLLMAdapter()
        # Static text, built once at import (see _SYSTEM_PROMPT above); this is
        # a reference, not a re-concatenation. Kept as an instance attribute
        # because tools/measure_llm_tokens.py reads it off a live strategist.
        self.system_prompt = _SYSTEM_PROMPT

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def get_suggestions(
        self, combat_context: Dict[str, Any], max_suggestions: int = 1
    ) -> List[Dict[str, Any]]:
        """Fetch movement suggestions from the LLM or fallback to heuristics.

        ``GenericLLMClient.generate_structured`` is typed and documented as
        returning a dict or None — it explicitly discards a non-dict payload —
        so the response is unpacked as dict-or-nothing. Anything else is a
        contract violation on the client's side, not a shape to handle here.
        """
        logger.debug(
            "CombatStrategist.get_suggestions called (max: %s)", max_suggestions
        )

        suggestions = []
        if self.client.available():
            try:
                user_prompt = self._build_user_prompt(combat_context)
                wrapped_prompt = wrap_suggestions_prompt(user_prompt, max_suggestions)

                logger.debug(
                    "Requesting %s suggestions for %s",
                    max_suggestions,
                    combat_context.get("player", {}).get("name"),
                )
                raw_response = self.client.generate_structured(
                    self.system_prompt, wrapped_prompt
                )

                raw_suggestions = (
                    raw_response.get("suggestions", [])
                    if isinstance(raw_response, dict)
                    else []
                )

                for s in raw_suggestions:
                    if isinstance(s, dict) and "move_name" in s:
                        try:
                            s["score"] = int(s.get("score", 0))
                        except (ValueError, TypeError):
                            s["score"] = 0
                        suggestions.append(s)

            except Exception as e:
                logger.error("Error in LLM suggestion flow: %s", e, exc_info=True)

        if not suggestions:
            logger.debug("Using heuristic fallback for combat suggestions.")
            return self._get_fallback_suggestions(combat_context, max_suggestions)

        suggestions.sort(key=lambda x: x["score"], reverse=True)
        results = suggestions[:max_suggestions]
        self._ensure_target_ids(results, combat_context)
        logger.debug("CombatStrategist returning %s suggestions.", len(results))
        return results

    # ------------------------------------------------------------------
    # Heuristic fallback
    # ------------------------------------------------------------------

    def _derive_tactical_state(self, ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Reduce a combat context to the flags the fallback scorer needs.

        Every threshold comparison in the heuristic path happens here, once,
        against the module constants — so the scorer below is pure branching on
        named booleans rather than a second copy of the same arithmetic.
        """
        player = ctx.get("player", {})
        hp = player.get("hp") or 0
        max_hp = player.get("max_hp") or 1
        fatigue = player.get("fatigue") or 0
        max_fatigue = player.get("max_fatigue") or 1
        heat = float(player.get("heat") or 1.0)

        evasion, combined_defense = _player_defenses(player)

        player_status_names = {
            s.get("name", "") for s in player.get("status_effects", [])
        }
        enemies = ctx.get("enemies", [])

        # Beats-until-impact and estimated damage for the most threatening charge
        worst_threat = self._worst_incoming_threat(enemies, hp)
        incoming_beats = worst_threat["beats_until_resolve"]

        # Heat modifiers for offensive scoring
        if heat >= _HEAT_BLAZING:
            heat_offensive_bonus = 10  # BLAZING: attack now
        elif heat >= _HEAT_HOT:
            heat_offensive_bonus = 5  # HOT: lean offensive
        elif heat < _HEAT_COLD:
            heat_offensive_bonus = -10  # COLD: rebuild before spending resources
        else:
            heat_offensive_bonus = 0

        return {
            "heat": heat,
            "heat_offensive_bonus": heat_offensive_bonus,
            "hp_critical": hp / max_hp < _HP_CRITICAL_PCT,
            "fatigue_critical": fatigue / max_fatigue < _FATIGUE_CRITICAL_PCT,
            "fatigue_low": fatigue / max_fatigue < _FATIGUE_LOW_PCT,
            "defensively_vulnerable": _is_defensively_vulnerable(
                evasion, combined_defense
            ),
            # Active DoT on player accelerates urgency to end combat
            "dot_active": bool(
                player_status_names & {"Poisoned", "Enflamed", "Resonant", "Hollowed"}
            ),
            # Dodge reliability is impaired by certain status effects
            "dodge_impaired": bool(
                player_status_names & {"Disoriented", "Slimed", "Petrified"}
            ),
            # If any enemy has DoT, time is on Jean's side — slightly less aggressive
            "enemy_dot_active": any(
                any(
                    s.get("name", "") in {"Poisoned", "Enflamed", "Resonant"}
                    for s in e.get("status_effects", [])
                )
                for e in enemies
            ),
            # If an enemy is likely to Rest (low fatigue), that's an offensive window
            "enemy_likely_resting": any(
                (e.get("fatigue") or 0) / _enemy_max_fatigue(e) < _FATIGUE_CRITICAL_PCT
                for e in enemies
            ),
            "incoming_beats": incoming_beats,
            "in_defensive_window": (
                incoming_beats is not None and incoming_beats <= _DEFENSIVE_WINDOW_BEATS
            ),
            "estimated_damage": worst_threat["estimated_damage"],
            "incoming_lethal": worst_threat["potentially_lethal"],
        }

    @staticmethod
    def _score_defensive_move(name: str, state: Dict[str, Any]) -> Tuple[int, str]:
        """Score Dodge/Parry against a hit that is still inside the defensive window.

        Ordered most-constrained first: an impaired Dodge is worth little
        against a survivable hit and a great deal against a lethal one, so the
        two impairment branches must both be tested before the plain lethal
        branch, which would otherwise swallow them.
        """
        min_bui = state["incoming_beats"]
        est_damage = state["estimated_damage"]
        est_lethal = state["incoming_lethal"]

        if state["dodge_impaired"] and not est_lethal:
            # Status effect reduces defensive move value when the hit is survivable
            return 60, (
                f"Attack in ~{min_bui} beat(s) but status effect impairs {name} "
                "reliability; consider UseItem or accepting the hit."
            )
        if state["dodge_impaired"] and est_lethal:
            # Even impaired, better than a one-shot
            return 88, (
                f"Incoming hit is potentially lethal in ~{min_bui} beat(s); "
                f"{name} reliability is reduced by status effect but still "
                "preferable to dying."
            )
        if est_lethal:
            return 97, (
                f"Potentially lethal hit (~{est_damage} dmg) landing in "
                f"~{min_bui} beat(s); {name} is critical."
            )
        if state["defensively_vulnerable"]:
            return 95, (
                f"Attack landing in ~{min_bui} beat(s) and Jean's defenses are "
                f"low (~{est_damage} estimated dmg); {name} now."
            )
        return 80, (
            f"Attack in ~{min_bui} beat(s) (~{est_damage} estimated dmg); "
            f"{name} is advisable but Jean's defenses may absorb it."
        )

    @staticmethod
    def _score_move(move: Dict[str, Any], state: Dict[str, Any]) -> Tuple[int, str]:
        """Score one available move against the derived tactical state.

        Returns ``(score, reasoning)``. Branches are ordered by the same
        priority list the system prompt gives the model.
        """
        name = move.get("name", "Unknown")
        category = move.get("category", "Miscellaneous")
        base_score = {
            "Offensive": 85,
            "Maneuver": 75,
            "Special": 70,
            "Defensive": 65,
            "Miscellaneous": 40,
        }.get(category, 40)

        heat = state["heat"]

        if state["in_defensive_window"] and name in ("Dodge", "Parry"):
            return CombatStrategist._score_defensive_move(name, state)

        if state["fatigue_critical"] and name == "Rest":
            return 90, (
                "Fatigue critically low; Rest is essential to maintain move availability."
            )

        if state["hp_critical"] and name == "UseItem":
            return 88, "HP critically low; use a healing consumable before engaging."

        if state["dot_active"] and category == "Offensive":
            # Player DoT ticking — reward aggression to end the fight
            return min(95, base_score + 8), (
                f"DoT is draining HP; {name} to end combat quickly."
            )

        if state["enemy_likely_resting"] and category == "Offensive":
            # Enemy likely to Rest next turn — safe offensive window
            return min(95, base_score + 6), (
                f"Enemy fatigue is critical — they may Rest next turn; {name} to "
                "exploit the window."
            )

        if state["enemy_dot_active"] and category == "Offensive":
            # Enemy has DoT — time favours Jean, slightly less frantic
            return base_score, (
                f"Enemy is poisoned/burning — {name} while time works in Jean's favour."
            )

        if state["fatigue_low"] and name in ("Wait", "Rest"):
            return (
                72,
                f"Fatigue is low; {name} conserves resources for a better opportunity.",
            )

        if name == "Advance":
            return 80, "Close the distance to bring offensive moves into range."

        if name in ("Wait", "Check"):
            return 20, f"{name} cedes initiative; use only if no better option exists."

        if category == "Offensive":
            score = min(99, base_score + state["heat_offensive_bonus"])
            if heat >= _HEAT_BLAZING:
                return score, (
                    f"Heat is BLAZING ({heat:.1f}×); {name} for amplified damage — "
                    "don't miss."
                )
            if heat >= _HEAT_HOT:
                return (
                    score,
                    f"Heat is elevated ({heat:.1f}×); {name} while the combo holds.",
                )
            if heat < _HEAT_COLD:
                return score, (
                    f"Heat is low ({heat:.1f}×); {name} to rebuild combo before committing."
                )
            return score, f"Tactical analysis unavailable; {name} is a viable fallback."

        return (
            base_score,
            f"Tactical analysis unavailable; {name} is a viable fallback.",
        )

    def _get_fallback_suggestions(
        self, combat_context: Dict[str, Any], max_suggestions: int
    ) -> List[Dict[str, Any]]:
        """Provide context-aware suggestions based on combat state when the LLM is unavailable."""
        available = [
            m
            for m in combat_context.get("available_moves", [])
            if m.get("available", True)
        ]
        if not available:
            return [
                {
                    "move_name": "Check",
                    "target_id": None,
                    "score": 10,
                    "reasoning": "No other moves available; reassess the battlefield.",
                }
            ]

        state = self._derive_tactical_state(combat_context)

        scored_moves = []
        for m in available:
            if m.get("name", "Unknown") == "Cancel":
                continue
            score, reasoning = self._score_move(m, state)
            scored_moves.append(
                {
                    "move_name": m.get("name", "Unknown"),
                    "target_id": None,
                    "score": score,
                    "reasoning": reasoning,
                }
            )

        scored_moves.sort(key=lambda x: x["score"], reverse=True)

        if not scored_moves:
            scored_moves.append(
                {
                    "move_name": available[0].get("name", "Wait"),
                    "target_id": None,
                    "score": 10,
                    "reasoning": "Standard tactical fallback; maintaining position.",
                }
            )

        results = scored_moves[: max(1, min(3, max_suggestions))]
        self._ensure_target_ids(results, combat_context)
        return results

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    def _build_user_prompt(self, ctx: Dict[str, Any]) -> str:
        """Construct the context string for the LLM.

        Pure assembly: every section is built by its own ``_*_block`` helper,
        in the order the system prompt's priorities expect to read them.
        """
        player = ctx.get("player", {})
        enemies = ctx.get("enemies", [])

        hp = player.get("hp") or 0
        hp_pct = hp / (player.get("max_hp") or 1)
        fatigue_pct = (player.get("fatigue") or 0) / (player.get("max_fatigue") or 1)
        heat = float(player.get("heat") or 1.0)

        enemies_block, imminent_alerts = self._enemy_block(enemies, player, hp)
        # Multi-enemy target priority
        priority_block = (
            self._build_target_priority(enemies, hp) if len(enemies) > 1 else ""
        )
        history_str = "\n".join(ctx.get("history", [])[-5:])

        return (
            f"{self._player_block(player, hp_pct, fatigue_pct, heat)}\n\n"
            f"{enemies_block}\n"
            f"{self._ally_block(ctx.get('allies', []))}"
            f"{self._cooldown_block(ctx.get('defensive_cooldowns', {}))}"
            f"{priority_block}"
            f"{self._alert_block(imminent_alerts, hp_pct, fatigue_pct, heat)}\n"
            f"Recent History:\n{history_str}\n"
            f"Previous Move: {ctx.get('last_move', 'None')}\n\n"
            f"Available Moves:\n{self._moves_block(ctx.get('available_moves', []))}"
        )

    @staticmethod
    def _heat_label(heat: float) -> str:
        """Render the heat band the system prompt's HEAT paragraph refers to."""
        if heat >= _HEAT_BLAZING:
            return (
                f"{heat:.2f}× [BLAZING — attacks deal +{int((heat - 1) * 100)}% damage; "
                "protect this streak]"
            )
        if heat >= _HEAT_HOT:
            return f"{heat:.2f}× [HOT — attacks deal +{int((heat - 1) * 100)}% bonus damage]"
        if heat < _HEAT_COLD:
            return (
                f"{heat:.2f}× [COLD — attacks deal −{int((1 - heat) * 100)}% damage; "
                "land hits to rebuild]"
            )
        return f"{heat:.2f}× [WARM — baseline damage]"

    def _player_block(
        self,
        player: Dict[str, Any],
        hp_pct: float,
        fatigue_pct: float,
        heat: float,
    ) -> str:
        """Jean's vitals, attributes, stats, passives, statuses and consumables."""
        pos = player.get("position") or {}
        hp_flag = (
            " ⚠ HP CRITICAL"
            if hp_pct < _HP_CRITICAL_PCT
            else (" LOW" if hp_pct < _HP_LOW_PCT else "")
        )
        fatigue_flag = (
            " ⚠ FATIGUE CRITICAL"
            if fatigue_pct < _FATIGUE_CRITICAL_PCT
            else (" LOW" if fatigue_pct < _FATIGUE_LOW_PCT else "")
        )

        p_attrs = ", ".join(
            [f"{k}: {v}" for k, v in player.get("attributes", {}).items()]
        )
        passives = self._extract_names(player.get("passives", []))

        p_stats = player.get("stats", {})
        p_evasion, _ = _player_defenses(player)
        p_armor_def = ((player.get("equipment") or {}).get("armor") or {}).get(
            "defense", 0
        )

        p_consumables = ", ".join(
            [
                f"{c.get('name', 'Item')} (Qty: {c.get('qty', 1)})"
                for c in player.get("consumables", [])
            ]
        )

        # Status effects with mechanical context
        status_lines = self._format_status_effects(player.get("status_effects", []))

        return (
            f"Player: {player.get('name', 'Jean')} (Male Human) "
            f"[HP: {player.get('hp') or 0}/{player.get('max_hp') or 1}{hp_flag}, "
            f"Fatigue: {player.get('fatigue') or 0}/{player.get('max_fatigue') or 1}"
            f"{fatigue_flag}, "
            f"Heat: {self._heat_label(heat)}, "
            f"Pos: {pos.get('x')},{pos.get('y')}, Facing: {pos.get('facing')}]\n"
            f"Attributes: [{p_attrs}]\n"
            f"Combat Stats: [Evasion: {p_evasion}, Defense: {p_stats.get('defense', 0)}, "
            f"Armor Defense: {p_armor_def}, Accuracy: {p_stats.get('accuracy', 80)}, "
            f"Speed: {p_stats.get('speed', 0)}]\n"
            f"Passives: {', '.join(passives) or 'None'}\n"
            f"Status Effects:\n{status_lines}\n"
            f"Consumables: [{p_consumables or 'None'}]"
        )

    def _enemy_block(
        self,
        enemies: List[Dict[str, Any]],
        player: Dict[str, Any],
        player_hp: int,
    ) -> Tuple[str, List[str]]:
        """Enemy roster plus the imminent-attack alerts it generated.

        Returns ``(block, imminent_alerts)`` — the alerts belong at the top of
        the SITUATIONAL ALERTS section (system prompt priority 2) rather than
        inline here, so they are handed back rather than emitted.
        """
        p_evasion, p_combined_defense = _player_defenses(player)
        enemy_list = []
        imminent_alerts: List[str] = []

        for e in enemies:
            e_pos = e.get("position") or {}
            e_fatigue = e.get("fatigue", 0)
            e_max_fatigue = _enemy_max_fatigue(e)
            e_fat_pct = e_fatigue / e_max_fatigue
            fat_tag = (
                " ⚠ FATIGUE CRITICAL — likely to Rest"
                if e_fat_pct < _FATIGUE_CRITICAL_PCT
                else (" [fatigue LOW]" if e_fat_pct < _FATIGUE_LOW_PCT else "")
            )

            mip = e.get("move_in_process")
            bui = _incoming_beats(mip)
            mip_str = ""
            # A move still in recoil/cooldown is reported by the engine with
            # bui None: its effect already landed, so it is not a threat and
            # must not be announced as one.
            if bui is not None:
                threat = self._estimate_incoming_damage(mip, e, player_hp)
                est_dmg = threat["estimated_damage"]
                lethal = threat["potentially_lethal"]

                lethal_tag = " ⚠ POTENTIALLY LETHAL" if lethal else ""
                mip_str = (
                    f", Charging: {mip.get('name')} "
                    f"({bui} beat{'s' if bui != 1 else ''} until impact, "
                    f"~{est_dmg} estimated dmg{lethal_tag})"
                )

                if bui <= _DEFENSIVE_WINDOW_BEATS:
                    qualifier = (
                        "Dodge/Parry NOW"
                        if bui >= _DEFENSIVE_WINDOW_BEATS
                        else "last-chance Dodge/Parry"
                    )
                    vuln_note = (
                        f" Jean's evasion ({p_evasion}) and defense "
                        f"({p_combined_defense}) are low — this will hurt."
                        if _is_defensively_vulnerable(p_evasion, p_combined_defense)
                        else " Jean's defenses may reduce impact."
                    )
                    imminent_alerts.append(
                        f"⚠ INCOMING: {e.get('name')} lands {mip.get('name')} "
                        f"in ~{bui} beat(s) (~{est_dmg} dmg"
                        f"{', LETHAL' if lethal else ''}). "
                        f"{qualifier}.{vuln_note}"
                    )

            # Enemy status effects — use enemy perspective notes
            e_statuses = self._format_status_effects(
                e.get("status_effects", []), perspective="enemy"
            )
            status_str = (
                f"\n    Status: {e_statuses.strip()}"
                if e_statuses.strip() != "None"
                else ""
            )

            enemy_list.append(
                f"- {e.get('name')} [ID: {e.get('id')}, "
                f"HP: {e.get('hp')}/{e.get('max_hp')}, "
                f"Fatigue: {e_fatigue}/{e_max_fatigue}{fat_tag}, "
                f"Pos: {e_pos.get('x')},{e_pos.get('y')}, "
                f"Dist: {e.get('distance')}ft{mip_str}]{status_str}"
            )

        return "Enemies:\n" + "\n".join(enemy_list), imminent_alerts

    @staticmethod
    def _ally_block(allies: List[Dict[str, Any]]) -> str:
        """Friendly combatants, or an empty string when Jean fights solo."""
        if not allies:
            return ""
        ally_lines = []
        for a in allies:
            a_pos = a.get("position") or {}
            ally_lines.append(
                f"- {a.get('name')} [ID: {a.get('id')}, "
                f"HP: {a.get('hp')}/{a.get('max_hp')}, "
                f"Pos: {a_pos.get('x')},{a_pos.get('y')}, "
                f"Dist: {a.get('distance')}ft]"
            )
        return "Allies (friendly — do not attack):\n" + "\n".join(ally_lines) + "\n"

    @staticmethod
    def _cooldown_block(def_cooldowns: Dict[str, Any]) -> str:
        """ETAs for defensive moves the player cannot cast yet."""
        if not def_cooldowns:
            return ""
        cd_parts = [
            f"{name} in {beats} beat{'s' if beats != 1 else ''}"
            for name, beats in def_cooldowns.items()
        ]
        return "Defensive moves on cooldown: " + ", ".join(cd_parts) + "\n"

    @staticmethod
    def _alert_block(
        imminent_alerts: List[str],
        hp_pct: float,
        fatigue_pct: float,
        heat: float,
    ) -> str:
        """Situational alerts, ordered by system prompt priority (most urgent first).

        INCOMING attacks (priority 2) lead; HP/fatigue/heat follow.
        """
        alerts = list(imminent_alerts)  # priority 2: telegraphed attacks
        if hp_pct < _HP_CRITICAL_PCT:
            alerts.append("⚠ HP CRITICAL: Prioritize healing or defensive moves.")
        if fatigue_pct < _FATIGUE_CRITICAL_PCT:
            alerts.append("⚠ FATIGUE CRITICAL: Prefer Rest or zero-cost moves.")
        if heat >= _HEAT_BLAZING:
            alerts.append(
                f"⚠ BLAZING HEAT ({heat:.2f}×): Maximize offense now — missing or "
                "being hit collapses the combo."
            )
        elif heat < _HEAT_COLD:
            alerts.append(
                f"⚠ COLD HEAT ({heat:.2f}×): Land hits to rebuild combo before using "
                "expensive moves."
            )
        if not alerts:
            return ""
        return "\nSITUATIONAL ALERTS:\n" + "\n".join(alerts) + "\n"

    @staticmethod
    def _moves_block(available_moves: List[Dict[str, Any]]) -> str:
        """Available moves with fatigue cost, description and viable targets."""
        move_descriptions = []
        for m in available_moves:
            if not m.get("available", True):
                continue
            name = m.get("name")
            cost = m.get("fatigue_cost", 0)
            desc = m.get("description", "")
            cost_str = f" [Cost: {cost} fatigue]" if cost else " [No fatigue cost]"
            desc_str = f" — {desc}" if desc else ""
            targets = m.get("viable_targets", [])
            if targets:
                target_info = ", ".join(
                    [
                        f"{t.get('name')} (ID: {t.get('id')}, {t.get('distance')}ft)"
                        for t in targets
                    ]
                )
                move_descriptions.append(
                    f"{name}{cost_str} [Targets: {target_info}]{desc_str}"
                )
            else:
                move_descriptions.append(f"{name}{cost_str}{desc_str}")
        return "\n".join(f"  {d}" for d in move_descriptions)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_status_effects(
        status_effects: List[Any],
        perspective: str = "player",
    ) -> str:
        """
        Render status effects with mechanical notes and remaining duration.

        The mechanical half is ENGINE-OWNED and read straight off the wire:
        ``tactical_mechanics``, which ``State`` (src/states.py) interpolates
        from the same class constants its ``add_*`` assignments multiply by, so
        the model is never told a modifier or a tick interval the engine does
        not actually apply. ``description`` — player-facing prose — is the
        fallback for a state that declares no tactical summary.

        This module supplies only the half the engine cannot know: which side
        of the fight is holding the effect. Pass perspective="enemy" for an
        enemy's effects so the implication is written from Jean's viewpoint,
        not the affected entity's.
        """
        note_key = "enemy_note" if perspective == "enemy" else "player_note"
        if not status_effects:
            return "  None"
        lines = []
        for s in status_effects:
            if not s:
                continue
            is_dict = isinstance(s, dict)
            name = s.get("name", "Unknown") if is_dict else str(s)
            beats_left = s.get("beats_left", 0) if is_dict else 0
            mechanics = (
                (s.get("tactical_mechanics") or s.get("description") or "").strip()
                if is_dict
                else ""
            )
            note_entry = _STATUS_TACTICAL_NOTES.get(name)
            if note_entry:
                detail_parts = [mechanics] if mechanics else []
                if beats_left > 0:
                    detail_parts.append(f"~{beats_left} beats remaining")
                detail = f" ({', '.join(detail_parts)})" if detail_parts else ""
                lines.append(f"  {name}{detail} → {note_entry[note_key]}")
            else:
                duration_str = (
                    f", ~{beats_left} beats remaining" if beats_left > 0 else ""
                )
                lines.append(
                    f"  {name}{duration_str}{': ' + mechanics if mechanics else ''}"
                )
        return "\n".join(lines) if lines else "  None"

    @staticmethod
    def _estimate_incoming_damage(
        mip: Dict[str, Any],
        enemy: Dict[str, Any],
        player_hp: int,
    ) -> Dict[str, Any]:
        """
        Estimate damage range for a telegraphed enemy move.

        Uses the enemy's serialized damage stat and the move's own
        ``damage_multiplier``, which the serializer reads off the live move
        object (``Move._DAMAGE_MULTIPLIER``). This module used to keep a local
        table keyed on move CLASS names while the wire carries the runtime
        INSTANCE name, so every heavy hitter in the game — SlimeVolley ("Slime
        Volley"), TidalSurge ("Tidal Surge"), GorranClub ("NPC_Attack") — missed
        the lookup and was estimated at 1.0x, and the POTENTIALLY LETHAL flag
        never fired for the moves that most needed it.

        Protection is not available for the enemy's view of the player, so the
        estimate is conservative (raw power before mitigation).
        """
        try:
            multiplier = float(mip.get("damage_multiplier", 1.0))
        except (TypeError, ValueError):
            multiplier = 1.0
        enemy_damage = (enemy.get("stats") or {}).get("damage", 0) or enemy.get(
            "damage", 0
        )

        low = max(0, int(enemy_damage * multiplier * 0.8))
        high = max(0, int(enemy_damage * multiplier * 1.2))
        midpoint = (low + high) // 2

        return {
            "estimated_damage": f"{low}–{high}",
            "midpoint": midpoint,
            "potentially_lethal": midpoint >= player_hp * _LETHAL_HP_FRACTION,
        }

    def _worst_incoming_threat(
        self, enemies: List[Dict[str, Any]], player_hp: int
    ) -> Dict[str, Any]:
        """Return the combined threat metrics for the most dangerous incoming charge.

        ``beats_until_resolve`` is None when nothing is actually incoming —
        every enemy is idle, or its move has already landed and is only playing
        out its recoil/cooldown. Callers must test for None rather than compare
        against a sentinel.
        """
        best: Dict[str, Any] = {
            "beats_until_resolve": None,
            "estimated_damage": "0–0",
            "midpoint": 0,
            "potentially_lethal": False,
        }
        for e in enemies:
            mip = e.get("move_in_process")
            bui = _incoming_beats(mip)
            if bui is None:
                continue
            threat = self._estimate_incoming_damage(mip, e, player_hp)
            current = best["beats_until_resolve"]
            if (
                current is None
                or bui < current
                or (bui == current and threat["potentially_lethal"])
            ):
                best = {**threat, "beats_until_resolve": bui}
        return best

    @staticmethod
    def _rank_enemies(
        enemies: List[Dict[str, Any]], player_hp: int
    ) -> List[Tuple[int, float, Dict[str, Any]]]:
        """Rank enemies by threat, highest priority first.

        Returns ``(priority, hp_pct, enemy)`` tuples sorted by that key, where a
        LOWER priority number is more urgent: (0) incoming lethal charge,
        (1) incoming non-lethal charge, (2) lowest HP% (finish them off),
        (3) default order.

        The single owner of this ranking. ``_build_target_priority`` renders it
        for the model and ``_priority_target_id`` picks a target from it; the
        two used to hold verbatim copies of this loop kept in step only by a
        docstring saying they matched, so diverging them would have made the
        priority list the model was shown disagree with the target actually
        filled into its suggestion.
        """
        scored = []
        for e in enemies:
            mip = e.get("move_in_process")
            bui = _incoming_beats(mip)
            lethal = (
                CombatStrategist._estimate_incoming_damage(mip, e, player_hp)[
                    "potentially_lethal"
                ]
                if bui is not None
                else False
            )
            hp_pct = (e.get("hp") or 0) / (e.get("max_hp") or 1)
            imminent = bui is not None and bui <= _DEFENSIVE_WINDOW_BEATS

            priority = (
                0
                if (lethal and imminent)
                else 1 if imminent else 2 if hp_pct < _FINISHABLE_HP_PCT else 3
            )
            scored.append((priority, hp_pct, e))

        # Stable sort: enemies tied on (priority, hp_pct) keep wire order, which
        # is what _priority_target_id's first-wins tie-break used to do.
        scored.sort(key=lambda x: (x[0], x[1]))
        return scored

    def _build_target_priority(
        self, enemies: List[Dict[str, Any]], player_hp: int
    ) -> str:
        """Render the enemy threat ranking for the prompt when several are present."""
        lines = ["Target Priority (highest → lowest):"]
        for rank, (priority, hp_pct, e) in enumerate(
            self._rank_enemies(enemies, player_hp), 1
        ):
            reason = (
                "incoming LETHAL charge"
                if priority == 0
                else (
                    "incoming charge"
                    if priority == 1
                    else (
                        f"low HP ({int(hp_pct * 100)}%)"
                        if priority == 2
                        else "standard threat"
                    )
                )
            )
            lines.append(f"  {rank}. {e.get('name')} (ID: {e.get('id')}) — {reason}")
        return "\n".join(lines) + "\n"

    def _priority_target_id(
        self, enemies: List[Dict[str, Any]], player_hp: int
    ) -> Optional[str]:
        """Return the ID of the highest-priority enemy, per `_rank_enemies`."""
        ranked = self._rank_enemies(enemies, player_hp)
        return ranked[0][2].get("id") if ranked else None

    def _ensure_target_ids(
        self, suggestions: List[Dict[str, Any]], context: Dict[str, Any]
    ):
        """
        Ensure targeted moves resolve to a valid, in-range target_id.

        Each move's own `viable_targets` (already range-filtered by
        CombatAdapter._get_available_targets, using that move's mvrange /
        get_effective_range_max) is the sole source of truth for who it can hit.
        A missing target_id — or one that isn't among that move's viable
        targets (e.g. an LLM hallucination) — is replaced with the
        highest-priority target drawn from that move's own viable set, never
        from the global enemy list. Fixes issue #122 ("Tactical Advisor
        targets far enemies"): previously a missing target_id was auto-filled
        from the highest-priority enemy across the WHOLE fight, which could
        be out of range for the specific move being suggested.

        A targeted move with zero viable targets is dropped from the results
        entirely — a move that cannot reach anyone should never be suggested.
        """
        enemies_by_id = {
            e.get("id"): e for e in context.get("enemies", []) if isinstance(e, dict)
        }
        player_hp = (context.get("player") or {}).get("hp") or 1
        moves_by_name = {
            m.get("name"): m
            for m in context.get("available_moves", [])
            if isinstance(m, dict)
        }

        kept: List[Dict[str, Any]] = []
        for s in suggestions:
            move = moves_by_name.get(s.get("move_name"))

            if move is None or not move.get("targeted"):
                kept.append(s)
                continue

            viable_targets = move.get("viable_targets") or []
            viable_ids = {
                t.get("id")
                for t in viable_targets
                if isinstance(t, dict) and t.get("id")
            }

            if not viable_ids:
                # Targeted move with nothing in range — cannot be suggested at all.
                logger.debug(
                    "Dropping suggestion for '%s' — no viable target in range",
                    s.get("move_name"),
                )
                continue

            if s.get("target_id") not in viable_ids:
                # Rank only the enemies THIS move can actually reach — not every
                # enemy in the fight.
                scoped_enemies = [
                    enemies_by_id[i] for i in viable_ids if i in enemies_by_id
                ]
                if scoped_enemies:
                    new_target_id = self._priority_target_id(scoped_enemies, player_hp)
                else:
                    # No richer enemy data available to rank by — fall back to the
                    # nearest of the move's own viable targets. Same dict guard as
                    # viable_ids above, in case a non-dict entry ever slips through.
                    dict_targets = [t for t in viable_targets if isinstance(t, dict)]
                    new_target_id = (
                        min(dict_targets, key=lambda t: t.get("distance", 0)).get("id")
                        if dict_targets
                        else None
                    )
                logger.debug(
                    "Resolving target_id for '%s' to in-range target %s",
                    s.get("move_name"),
                    new_target_id,
                )
                s["target_id"] = new_target_id

            kept.append(s)

        suggestions[:] = kept

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
