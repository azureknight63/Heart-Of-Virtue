"""
Combat-related serializers for combat state, combatants, and status effects.

This module provides serialization for:
- CombatState: Full battle state (turn order, combatants, status)
- Combatant: Character/NPC in combat (HP, moves, effects)
- StateEffect: Status effects and conditions
"""

import logging
from typing import Dict, List, Any, Optional, TYPE_CHECKING

from src.api.constants import ITEM_USE_RANGE
from src.api.serializers.inventory import _BONUS_ATTRS, _collect_equipped_items
from src.combatant import move_in_progress
from src.moves import attacker_accuracy
from src.moves._base import display_name_of

if TYPE_CHECKING:
    from src.player import Player
    from src.npc import NPC
    from src.states import State

logger = logging.getLogger(__name__)


def _num(obj, attr, default=0.0) -> float:
    """Read a numeric attribute defensively, coercing None/garbage to `default`."""
    try:
        value = getattr(obj, attr, default)
        if value is None:
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _as_dict(value) -> Dict:
    """Coerce a resistance-style attribute to a plain dict, tolerating junk."""
    if not value:
        return {}
    try:
        return dict(value)
    except (TypeError, ValueError):
        return {}


def _weapon_damage(combatant: Any) -> float:
    """Base weapon damage for a combatant.

    Player damage comes from the equipped weapon (`eq_weapon`); the Player
    class has no `damage` attribute of its own. NPCs don't equip weapons —
    their raw `damage` attribute is the engine's equivalent.
    """
    weapon = getattr(combatant, "eq_weapon", None)
    if weapon is not None:
        return _num(weapon, "damage")
    return _num(combatant, "damage")


def _attack_power(combatant: Any) -> float:
    """Effective attack power: weapon damage plus attribute scaling.

    Mirrors `Attack.evaluate()` in src/moves/_utility.py, the engine's own
    power formula for the basic attack:
        eq_weapon.damage + strength * str_mod + finesse * fin_mod
    NPCs have no weapon, so their flat `damage` is their attack power.
    SYNC RISK: keep in step with `Attack.evaluate()`.
    """
    weapon = getattr(combatant, "eq_weapon", None)
    if weapon is None:
        return _num(combatant, "damage")
    return (
        _num(weapon, "damage")
        + _num(combatant, "strength") * _num(weapon, "str_mod")
        + _num(combatant, "finesse") * _num(weapon, "fin_mod")
    )


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
        serialized_allies = [
            CombatantSerializer.serialize_combatant(a, reference=player) for a in allies
        ]
        return {
            "status": "active",
            "round": round_number,
            "current_turn_index": current_turn_index,
            "player": CombatantSerializer.serialize_combatant(player),
            "allies": serialized_allies,
            "enemies": [
                CombatantSerializer.serialize_combatant(e, reference=player)
                for e in enemies
            ],
            "turn_order": CombatStateSerializer._get_turn_order(player, enemies),
            "combatants": (
                [CombatantSerializer.serialize_combatant(player)]
                + serialized_allies
                + [
                    CombatantSerializer.serialize_combatant(e, reference=player)
                    for e in enemies
                ]
            ),
            "suggested_moves": getattr(player, "suggested_moves", []),
            "suggestions_loading": getattr(player, "suggestions_loading", False),
            "last_move_outcome": getattr(player, "last_move_summary", ""),
            "last_move_name": getattr(player, "last_move_name", None),

            "last_move_target_id": getattr(player, "last_move_target_id", None),
            "player_consumables": CombatStateSerializer._get_consumables(player),
        }

    @staticmethod
    def _get_consumables(player: "Player") -> List[Dict[str, Any]]:
        """Get consumable items from player inventory."""
        consumables = []
        if hasattr(player, "inventory"):
            for item in player.inventory:
                # Basic check for consumables: if it has a 'use' method or is a potion
                # For now, let's include everything with a value and quantity for the LLM to decide
                consumables.append(
                    {
                        "name": getattr(item, "name", "Unknown"),
                        "qty": getattr(item, "count", 1),
                        "value": getattr(item, "value", 0),
                        "description": getattr(item, "description", ""),
                    }
                )
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
        from src.player import Player

        return {
            "name": getattr(combatant, "name", "Unknown"),
            "type": ("player" if isinstance(combatant, Player) else "enemy"),
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
                CombatStateSerializer._calculate_experience(enemies) if victory else 0
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
                            "type": type(item).__name__,
                            "subtype": getattr(item, "subtype", None),
                            "weight": getattr(item, "weight", None),
                            "value": getattr(item, "value", None),
                            "enchantment_count": getattr(item, "_enchantment_count", getattr(item, "enchantment_count", 0)),
                            "description": getattr(item, "description", ""),
                        }
                    )
        return drops


class CombatantSerializer:
    """Serialize individual combatant state (player or NPC in combat)."""

    @staticmethod
    def stream_id(combatant: Any) -> str:
        """Canonical wire id for a combatant: ``player`` / ``ally_<id>`` /
        ``enemy_<id>``.

        Single source of truth for the combatant-id scheme so the serialized
        combat state and the beat streamer (issue #436) can never diverge.
        """
        from src.player import Player

        if isinstance(combatant, Player):
            return "player"
        if getattr(combatant, "friend", False):
            return f"ally_{id(combatant)}"
        return f"enemy_{id(combatant)}"

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
        from src.player import Player

        is_player = isinstance(combatant, Player)
        # Derive in_range from distance to the reference (player). Allies within 5 ft
        # are targetable with healing items; enemies within range are attackable.
        distance_to_ref = CombatantSerializer._get_distance(combatant, reference)
        in_range = distance_to_ref <= ITEM_USE_RANGE if reference is not None else True

        active_move = CombatantSerializer._serialize_active_move(combatant)
        return {
            "id": CombatantSerializer.stream_id(combatant),
            "in_range": in_range,
            "name": getattr(combatant, "name", "Unknown"),
            "battle_symbol": getattr(combatant, "battle_symbol", None),
            "type": "player" if is_player else "npc",
            "level": getattr(combatant, "level", 1),
            "health": {
                "current": getattr(combatant, "hp", getattr(combatant, "health", 0)),
                "max": getattr(
                    combatant, "maxhp", getattr(combatant, "max_health", 100)
                ),
            },
            "hp": getattr(combatant, "hp", getattr(combatant, "health", 0)),
            "max_hp": getattr(
                combatant, "maxhp", getattr(combatant, "max_health", 100)
            ),
            "fatigue": getattr(combatant, "fatigue", 0),
            "max_fatigue": getattr(
                combatant, "maxfatigue", getattr(combatant, "max_fatigue", 100)
            ),
            "maxfatigue": getattr(
                combatant, "maxfatigue", getattr(combatant, "max_fatigue", 100)
            ),
            "heat": getattr(combatant, "heat", 1.0) if is_player else 1.0,
            "stats": CombatantSerializer._serialize_combat_stats(combatant),
            "attributes": CombatantSerializer._serialize_base_attributes(combatant),
            "status_effects": CombatantSerializer._serialize_status_effects(combatant),
            "passives": CombatantSerializer._serialize_passives(combatant),
            "equipment": CombatantSerializer._serialize_combat_equipment(combatant),
            "distance": distance_to_ref,
            "position": CombatantSerializer._serialize_position(combatant),
            "current_move": active_move,
            "move_in_process": active_move,  # Alias for Strategist
        }

    @staticmethod
    def _serialize_active_move(combatant: Any) -> Optional[Dict[str, Any]]:
        """Serialize currently active/charging move."""
        move = move_in_progress(combatant)
        if move:
            return {
                "name": getattr(move, "name", "Unknown"),
                "display_name": display_name_of(move),
                "category": getattr(move, "category", "Miscellaneous"),
                "description": getattr(move, "description", ""),
                "current_stage": getattr(move, "current_stage", 0),
                "beats_left": getattr(move, "beats_left", 0),
                "total_beats": (
                    getattr(move, "stage_beat", [0, 0, 0, 0])[
                        getattr(move, "current_stage", 0)
                    ]
                    if hasattr(move, "stage_beat")
                    else 0
                ),
                "target_id": CombatantSerializer._serialize_move_target_id(move),
                "mvrange": CombatantSerializer._serialize_move_range(move),
            }
        return None

    @staticmethod
    def _serialize_move_target_id(move: Any) -> Optional[str]:
        """Canonical wire id of a move's target, or None when untargeted /
        no target has been selected yet.

        ``Move.target`` (see ``src/moves/_base.py``) holds a single combatant
        reference — never a list (verified via ``grep -rn "self.target"
        src/moves/``); some moves (e.g. ``PowerStrike``) default it to the
        move's own ``user`` in ``__init__`` purely as a placeholder until the
        adapter's target-selection command overwrites it, and untargeted
        moves (``Move.targeted is False`` — buffs, ``Rest``, passives) leave
        that placeholder in place for their whole life since nothing ever
        assigns a real target. ``combat_adapter.py`` already gates its own
        target lookup the same way (``if move.targeted and move.target``), so
        this mirrors that convention rather than inventing a new one.

        MUST resolve through ``CombatantSerializer.stream_id`` rather than a
        hand-rolled id — that is the only thing that guarantees this matches
        the id ``serialize_combatant`` emits for the same entity, per the
        wire-field-name-drift gotcha in CLAUDE.md.
        """
        if not getattr(move, "targeted", False):
            return None
        target = getattr(move, "target", None)
        if target is None or isinstance(target, (list, tuple, set)):
            # Defensive: no real Move.target is ever a collection today, but
            # a collection can't be resolved to a single wire id either way.
            return None
        return CombatantSerializer.stream_id(target)

    @staticmethod
    def _serialize_move_range(move: Any) -> Optional[Dict[str, int]]:
        """Move reach as ``{"min": int, "max": int}``, or None when the move
        exposes no ``mvrange``.

        Reads ``move.mvrange`` (see ``src/moves/_base.py``) as-is — this layer
        never reimplements range arithmetic. Some moves compute an *effective*
        max separately (ranged weapons with distance decay override
        ``get_effective_range_max`` in ``src/moves/_ranged.py``); when that
        returns a non-None value it is preferred for ``max`` because it's what
        the engine itself uses for targeting/hit-chance at this moment, while
        the static ``mvrange[1]`` would understate/overstate the real reach.

        The override takes the *user* whose move it is, so an NPC's reach is
        computed from the NPC's own weapon — not the player's, which is what
        passing a fixed reference would do.
        """
        mvrange = getattr(move, "mvrange", None)
        if not mvrange or len(mvrange) != 2:
            return None
        range_min, range_max = mvrange

        # Every Move has get_effective_range_max (the base returns None — see
        # src/moves/_base.py), so this is a plain call, matching how
        # combat_adapter._get_available_targets already invokes it. It is
        # deliberately not wrapped in try/except: an override that raises is a
        # real engine bug, and swallowing it here would ship a silently wrong
        # threat radius instead — the exact silent-failure mode this payload's
        # contract test exists to prevent.
        effective_max = move.get_effective_range_max(getattr(move, "user", None))
        if effective_max is not None:
            range_max = effective_max

        try:
            return {"min": int(range_min), "max": int(range_max)}
        except (TypeError, ValueError):
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
        if (
            not hasattr(combatant, "combat_position")
            or combatant.combat_position is None
        ):
            return None

        pos = combatant.combat_position
        return {
            "x": pos.x,
            "y": pos.y,
            "facing": (
                pos.facing.name
                if hasattr(pos, "facing") and hasattr(pos.facing, "name")
                else "N"
            ),
        }

    @staticmethod
    def serialize_combatant_list(
        combatants: List[Any],
    ) -> List[Dict[str, Any]]:
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
        """Serialize combat-relevant stats, derived from real engine attributes.

        Player/NPC/Combatant have no `armor`, `accuracy`, `evasion`,
        `defense` or `attack_power` attributes — reading them returned the
        fallback default for every combatant (issue #430). Each stat below is
        derived from what the engine actually stores:

        * `damage` / `attack_power` — the equipped weapon (`eq_weapon`) for
          the Player, the flat `damage` attribute for NPCs.
        * `defense` — `protection`, the flat value the engine subtracts from
          incoming damage.
        * `accuracy` / `evasion` — the two halves of the engine's hit-chance
          formula, split so `accuracy - target_evasion` reproduces the engine
          value: `accuracy` comes from `moves.attacker_accuracy` (the base plus
          the attacker's weighted finesse/intelligence) and `evasion` is the
          defender-side subtrahend, their own finesse. `_num` sanitizes the
          inputs first — the engine helper owns the arithmetic, this layer
          owns tolerating junk attribute values.
        """
        finesse = _num(combatant, "finesse")
        protection = _num(combatant, "protection")
        return {
            "damage": round(_weapon_damage(combatant)),
            "speed": int(_num(combatant, "speed", 5)),
            "accuracy": attacker_accuracy(finesse, _num(combatant, "intelligence")),
            "evasion": int(round(finesse)),
            "defense": int(round(protection)),
            "attack_power": round(_attack_power(combatant)),
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
                    passives.append(
                        {
                            "name": move.name,
                            "display_name": display_name_of(move),
                            "type": "passive",
                            "description": getattr(
                                move, "description", "Passive skill."
                            ),
                            "category": getattr(move, "category", "Miscellaneous"),
                        }
                    )
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
        """Serialize equipped items relevant to combat.

        Sourced from the real engine model (issue #430): there is no
        `combatant.equipped` dict — equipment is derived from the inventory's
        `isequipped`/`maintype` fields (shared with the inventory serializer
        via `_collect_equipped_items`, with `eq_weapon` as the weapon
        fallback) — and the resistance dict is singular `resistance`, not
        `resistances`.

        The armour entry reports `protection`, the engine's real armour stat;
        it deliberately does not report a `defense` key, because `defense` in
        `stats` is already the *total* protection (gear included) and a
        consumer summing the two would double-count.
        """
        equipment = {
            "weapon": None,
            "armor": None,
            "resistances": {},
        }

        # Contained failure: a degraded combatant with a non-iterable
        # inventory must cost only the equipment block, not the whole
        # combatant payload (the `_safe` boundary would blank the entire dict,
        # emptying the battlefield UI).
        try:
            equipped = _collect_equipped_items(combatant)
        except Exception:  # noqa: BLE001 - degraded engine object
            logger.warning("combat equipment collection failed", exc_info=True)
            equipped = {}

        weapon = equipped.get("weapon")
        if weapon is not None:
            equipment["weapon"] = {
                "name": getattr(weapon, "name", "Unarmed"),
                "damage": round(_num(weapon, "damage")),
                "damage_type": CombatantSerializer._weapon_damage_type(weapon),
            }
        body = equipped.get("body")
        if body is not None:
            equipment["armor"] = {
                "name": getattr(body, "name", "No Armor"),
                "protection": round(_num(body, "protection")),
            }

        # Real attribute is singular `resistance` (see src/combatant.py).
        equipment["resistances"] = _as_dict(getattr(combatant, "resistance", None))

        return equipment

    @staticmethod
    def _weapon_damage_type(weapon: Any) -> str:
        """Base damage type of a weapon.

        Engine weapons have no `damage_type` attribute; the canonical accessor
        is `items.get_base_damage_type` (which honours enchantment overrides).
        """
        from src.items import get_base_damage_type  # local import: see inventory.py

        try:
            return get_base_damage_type(weapon)
        except Exception:
            return "physical"


# Maps a State's `statustype` (see src/states.py — the real attribute; there
# is no `state_type`) to the frontend's status-effect vocabulary consumed by
# StatusEffectsIconPanel.jsx: "buff" (green), "debuff" (red), "ailment"
# (gold). Damage/corruption-over-time types are "ailment"; pure stat
# penalties or action-denial are "debuff"; net-positive effects are "buff".
# "generic" is the State default and is used by both buffs (Dodging,
# SecretPlansState, StoneBulwarkState) and debuffs (Quarried), so it is
# resolved from the state's own modifiers instead — see `_GENERIC_STATUSTYPE`.
_STATUSTYPE_CATEGORY = {
    "poison": "ailment",
    "enflamed": "ailment",
    "slimed": "ailment",
    "stun": "debuff",
    "stone": "debuff",
    "disoriented": "debuff",
    "apathy": "debuff",
    "clean": "buff",
    "enraged": "buff",
    "revive": "buff",
}

# The catch-all statustype whose polarity must be inferred per state.
_GENERIC_STATUSTYPE = "generic"

# Scalar stat-modifier attributes a State may expose. Sourced from the
# inventory serializer's `_BONUS_ATTRS` (itself mirroring
# functions.refresh_stat_bonuses' bonuses_map) plus `add_protection`, which
# only states and armour use.
_STATE_MODIFIER_ATTRS = tuple(_BONUS_ATTRS) + ("add_protection",)

# Values already in the frontend's vocabulary pass through unchanged so a
# state (real or mocked) that already reports a valid type is not remapped.
_VALID_EFFECT_TYPES = {"buff", "debuff", "ailment"}


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
            "type": StateEffectSerializer._get_effect_type(state),
            "description": getattr(state, "description", ""),
            "severity": StateEffectSerializer._get_severity(state),
            "beats_left": getattr(state, "beats_left", 0),
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
    def _get_effect_type(state: "State") -> str:
        """Map a State's `statustype` to the frontend buff/debuff/ailment vocabulary."""
        statustype = getattr(state, "statustype", _GENERIC_STATUSTYPE)
        if statustype in _VALID_EFFECT_TYPES:
            return statustype
        if statustype == _GENERIC_STATUSTYPE:
            return StateEffectSerializer._generic_effect_type(state)
        return _STATUSTYPE_CATEGORY.get(statustype, "debuff")

    @staticmethod
    def _generic_effect_type(state: "State") -> str:
        """Resolve the ambiguous "generic" statustype from the state's own modifiers.

        Real states share this default across opposite polarities — Dodging and
        StoneBulwarkState grant bonuses while Quarried strips protection — so
        any negative scalar `add_*` modifier marks the state a debuff.
        """
        for attr in _STATE_MODIFIER_ATTRS:
            if _num(state, attr) < 0:
                return "debuff"
        return "buff"

    @staticmethod
    def _get_severity(state: "State") -> str:
        """Determine severity level of state effect from its effect category.

        Real `State` objects have no generic damage-per-turn attribute (each
        subclass computes damage inline in `effect()`), so severity is
        derived from the same category used for `type`: ailments (poison,
        burn, corrosion) are severe, pure debuffs are moderate, and buffs are
        light.
        """
        category = StateEffectSerializer._get_effect_type(state)
        if category == "ailment":
            return "severe"
        elif category == "debuff":
            return "moderate"
        else:
            return "light"
