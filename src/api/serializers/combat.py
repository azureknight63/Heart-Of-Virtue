"""
Combat-related serializers for combat state, combatants, and status effects.

This module provides serialization for:
- CombatState: Full battle state (turn order, combatants, status)
- Combatant: Character/NPC in combat (HP, moves, effects)
- StateEffect: Status effects and conditions
"""

import logging
import math
from typing import Dict, List, Any, Optional, TYPE_CHECKING

from src.api.constants import ITEM_USE_RANGE
from src.api.serializers.inventory import _BONUS_ATTRS, _collect_equipped_items
from src.combatant import combatant_handle, move_in_progress
from src.moves import attacker_accuracy
from src.moves._base import display_name_of

if TYPE_CHECKING:
    from src.player import Player
    from src.npc import NPC
    from src.states import State

logger = logging.getLogger(__name__)


def _num(obj, attr, default=0.0) -> float:
    """Read a numeric attribute defensively, coercing None/garbage to `default`.

    Non-finite values are coerced too, and that part is load-bearing rather
    than tidiness: ``float('nan')`` raises neither TypeError nor ValueError, so
    it used to pass straight through. Flask's JSON provider serialises it as a
    bare ``NaN`` token, which is not valid JSON -- so `JSON.parse` rejects the
    response and the ENTIRE combat poll fails, not just the field. A single
    poisoned stat would take the fight down rather than degrade one number.
    """
    try:
        value = getattr(obj, attr, default)
        if value is None:
            return float(default)
        value = float(value)
    except (TypeError, ValueError):
        return float(default)
    if not math.isfinite(value):
        return float(default)
    return value


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
        # Serialize each entity ONCE. `player`/`allies`/`enemies` and the flat
        # `combatants` list are four views of the same three lists of dicts, so
        # they cannot disagree, and the expensive per-combatant walk (inventory,
        # known_moves, states, plus the engine's get_effective_range_max /
        # get_accuracy_falloff queries for the active move) is paid once per
        # entity per snapshot instead of twice.
        #
        # This matters because the call site is inside ApiCombatAdapter's
        # `while beats_processed < max_beats` loop (max_beats = 20, see
        # combat_adapter.py:1286), which serializes a fresh snapshot per beat —
        # so a single player action paid the duplicate up to 20 times over.
        #
        # Aliasing is safe: nothing mutates a per-combatant dict after
        # construction (the adapter only ever assigns TOP-LEVEL keys on the
        # returned state — "log", "combat_id", "beat", "heat", … — and
        # combat_beat_stream's diff_combatants only reads), and
        # `harden_serializer` runs json_safe over the whole payload on the way
        # out, which deep-copies it, so the wire sees independent objects
        # regardless.
        serialized_player = CombatantSerializer.serialize_combatant(player)
        serialized_allies = [
            CombatantSerializer.serialize_combatant(a, reference=player) for a in allies
        ]
        serialized_enemies = [
            CombatantSerializer.serialize_combatant(e, reference=player)
            for e in enemies
        ]
        serialized_combatants = (
            [serialized_player] + serialized_allies + serialized_enemies
        )
        return {
            "status": "active",
            "round": round_number,
            "current_turn_index": current_turn_index,
            "player": serialized_player,
            "allies": serialized_allies,
            "enemies": serialized_enemies,
            "turn_order": CombatStateSerializer._get_turn_order(serialized_combatants),
            "combatants": serialized_combatants,
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
    def _get_turn_order(serialized_combatants: List[Dict[str, Any]]) -> List[str]:
        """Wire ids of everyone in the fight, in roster order.

        NOT an initiative order, despite what this docstring used to claim.
        The engine is beat-based (``Move.advance`` / ``player.combat_beat``);
        there is no per-round initiative sequence for this layer to mirror, and
        synthesising a speed sort here would be the API inventing game logic the
        engine does not have. The previous implementation built ``(name, speed)``
        pairs, never sorted them, and returned only the names — so the "speed"
        half was pure decoration.

        Derived from the already-serialized roster so ``turn_order[i]`` is
        always ``combatants[i]["id"]``. The ids it used to emit were hand-rolled
        ``enemy_<list index>``, which matched neither
        ``CombatantSerializer.stream_id`` (``enemy_<id(obj)>``, what the
        ``combatants``/``enemies`` payloads and the beat streamer use) nor
        ``GameService``'s own ``turn_order`` (game_service.py:2438), and left
        allies out of the roster entirely. ``frontend/src/test/payloads.js``
        already documents the intended contract as
        ``[player.id, enemies[0].id]``.

        ``.get`` rather than ``[...]``: ``harden_serializer`` turns a combatant
        that fails to serialize into ``{}``, and index alignment with
        ``combatants`` matters more than hiding that — a ``null`` in the slot
        says "this one degraded" without taking the whole combat state down
        with it (which subscripting would, via the ``_safe`` boundary).
        """
        return [c.get("id") for c in serialized_combatants]

    @staticmethod
    def _get_available_actions(combatant: Any) -> List[str]:
        """Get available actions for combatant this turn.

        The engine attribute is ``known_moves`` (src/combatant.py); there is no
        ``moves`` on Player, NPC or Combatant, so the branch that read it never
        fired and a real combatant with twelve castable moves reported none of
        them. Passive moves are excluded — they are not actions anyone chooses
        (they are reported separately by ``_serialize_passives``) — and the wire
        carries the move's display name, matching every other move-name field in
        this module.
        """
        actions = ["attack", "defend", "flee"]
        for move in getattr(combatant, "known_moves", None) or []:
            if not getattr(move, "passive", False):
                actions.append(display_name_of(move))
        if hasattr(combatant, "inventory"):
            actions.append("use_item")
        return actions

    @staticmethod
    def _calculate_experience(enemies: List["NPC"]) -> int:
        """Total experience awarded by the defeated enemies.

        The engine attribute is ``exp_award`` (``NPC.__init__``,
        src/npc/_base.py). This read ``exp_reward`` and fell back to
        ``level * 10``; NPCs have neither name, so every real battle summary
        awarded 0. There is no ``level`` fallback any more for the same
        reason — an NPC's award is the only thing the engine actually stores.
        """
        total = 0
        for enemy in enemies:
            total += int(_num(enemy, "exp_award"))
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
                            "enchantment_count": getattr(
                                item,
                                "_enchantment_count",
                                getattr(item, "enchantment_count", 0),
                            ),
                            "description": getattr(item, "description", ""),
                        }
                    )
        return drops


#: ── The combat wire-id prefix vocabulary, single-sourced ────────────────────
#:
#: A combat wire id is a side prefix plus the combatant's opaque handle. The
#: prefixes are minted in :meth:`CombatantSerializer.stream_id` below and
#: parsed back apart in two other files (``src/api/combat_adapter.py``'s
#: ``_strip_combatant_prefix`` and ``src/api/routes/inventory.py``'s
#: ``_resolve_ally_target``). Both parsers pass an unrecognised prefix through
#: unchanged -- so spelled as literals on three sides, adding or renaming a
#: side makes every id of that side resolve to nobody, with no error anywhere.
#: Naming them once here and deriving both parsers from them removes that.
PLAYER_ID = "player"
ALLY_ID_PREFIX = "ally_"
ENEMY_ID_PREFIX = "enemy_"

#: Every side prefix, for parsers that strip whichever one is present.
COMBATANT_ID_PREFIXES = (ENEMY_ID_PREFIX, ALLY_ID_PREFIX)


def strip_combatant_prefix(target_id: str) -> str:
    """Strip whichever side prefix ``target_id`` carries, leaving the handle.

    Derived from :data:`COMBATANT_ID_PREFIXES` rather than a literal list, so a
    new side is understood by every parser the moment it is minted. An id with
    no known prefix is returned unchanged -- a bare handle is a legal input.
    """
    for prefix in COMBATANT_ID_PREFIXES:
        if target_id.startswith(prefix):
            return target_id[len(prefix):]
    return target_id


class CombatantSerializer:
    """Serialize individual combatant state (player or NPC in combat)."""

    @staticmethod
    def stream_id(combatant: Any) -> str:
        """Canonical wire id for a combatant: ``player`` / ``ally_<handle>`` /
        ``enemy_<handle>``.

        Single source of truth for the combatant-id scheme so the serialized
        combat state and the beat streamer (issue #436) can never diverge.

        The suffix is the combatant's stable opaque handle
        (``src.combatant.combatant_handle``), NOT ``id(combatant)``: heap
        addresses both leaked process layout to the client and were recycled
        onto later-spawned NPCs, silently aliasing stale client-held ids onto a
        different combatant. See the handle's comment block in
        ``src/combatant.py`` for the full rationale (issue #511).

        The prefix still depends on live state (``friend``), so a combatant
        that changes sides changes wire id -- that is deliberate and unchanged:
        the client keys allies and enemies apart by prefix.
        """
        from src.player import Player

        if isinstance(combatant, Player):
            return PLAYER_ID
        if getattr(combatant, "friend", False):
            return f"{ALLY_ID_PREFIX}{combatant_handle(combatant)}"
        return f"{ENEMY_ID_PREFIX}{combatant_handle(combatant)}"

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
            # `hp`/`maxhp`/`maxfatigue` are the engine's own names (see
            # src/combatant.py). The secondary `health`/`max_health`/
            # `max_fatigue` fallbacks these reads used to chain into named
            # nothing: no class under src/ defines them and nothing anywhere
            # assigns them, so they could only ever have masked a real
            # AttributeError with a plausible-looking default. Removed rather
            # than kept "just in case" — a fallback to a name with no writer is
            # not defence, it is a silent wrong answer waiting to happen.
            "health": {
                "current": getattr(combatant, "hp", 0),
                "max": getattr(combatant, "maxhp", 100),
            },
            "hp": getattr(combatant, "hp", 0),
            "max_hp": getattr(combatant, "maxhp", 100),
            "fatigue": getattr(combatant, "fatigue", 0),
            "max_fatigue": getattr(combatant, "maxfatigue", 100),
            "maxfatigue": getattr(combatant, "maxfatigue", 100),
            # Heat multiplier. Only the player has one — `standard_execute_attack`
            # (src/moves/_base.py) multiplies Jean's damage by it and nothing scales
            # NPC damage, so enemies report the neutral 1.0.
            #
            # Rounded to 2dp because the per-beat decay (ApiCombatAdapter._update_heat)
            # does NOT round the way Player.change_heat does — heat drifts to values
            # like 1.6234567891 — and this is the number the client renders directly
            # (HeatMeter, via frontend/src/utils/heat.js). Rounding on the wire
            # keeps the displayed multiplier and its client-derived per-beat delta
            # stable instead of jittering in the eighth decimal. `_num` (rather than a
            # bare getattr) matches every other numeric field here and stops a None or
            # non-numeric heat reaching the client as a NaN multiplier.
            "heat": round(_num(combatant, "heat", 1.0), 2) if is_player else 1.0,
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
                # Beats until the move's effect actually lands. `beats_left`
                # above is beats left in the CURRENT STAGE, which is a much
                # smaller number — the battlefield countdown badge renders
                # this one instead. Computed by the engine (Move.
                # beats_until_resolve) so the stage machine has one owner.
                #
                # Reached through _call_move_method: an absent countdown must
                # not blank a whole fighter. See _move_method's docstring.
                "beats_until_resolve": CombatantSerializer._call_move_method(
                    move, "beats_until_resolve"
                ),
                "target_id": CombatantSerializer._serialize_move_target_id(move),
                "mvrange": CombatantSerializer._serialize_move_range(move),
                "falloff": CombatantSerializer._serialize_move_falloff(move),
                "damage_multiplier": (
                    CombatantSerializer._serialize_damage_multiplier(move)
                ),
            }
        return None

    @staticmethod
    def _move_method(move: Any, name: str):
        """Return ``move``'s bound engine method ``name``, or None if absent.

        Every real Move (src/moves/_base.py) defines these, so this is not a
        guard against engine bugs — a method that *raises* still propagates,
        exactly as :meth:`_serialize_move_range` documents. It guards the one
        case where ``current_move`` is not a Move at all: a save written while
        a move was in flight, whose move class has since been renamed or
        removed, restores as a synthesized legacy placeholder (see
        ``src/secure_pickle.py``) carrying none of Move's API. That
        AttributeError escaped :meth:`_serialize_active_move` and the _safe
        boundary then replaced the WHOLE combatant with ``{}`` — no name, no
        hp, no position on the wire — so the battlefield rendered empty for
        every fighter, Jean included, with only a log warning to show for it.
        """
        method = getattr(move, name, None)
        return method if callable(method) else None

    @staticmethod
    def _call_move_method(move: Any, name: str, *args):
        """Call ``move``'s engine method ``name``, or return None if absent.

        The conditional-call idiom that goes with :meth:`_move_method`, in one
        place instead of copy-pasted at each call site. Deliberately NOT
        wrapped in try/except: absence resolves to None here, and a method that
        *raises* still propagates — see :meth:`_move_method` and
        :meth:`_serialize_move_range` for why swallowing it would ship a
        silently wrong payload instead of a loud bug.
        """
        method = CombatantSerializer._move_method(move, name)
        return method(*args) if method is not None else None

    @staticmethod
    def _serialize_damage_multiplier(move: Any) -> float:
        """Power multiple this move applies to its user's base damage.

        Read off the move object so the number has exactly one owner. The
        Tactical Advisor estimates incoming damage from this to decide whether
        a telegraphed hit is potentially lethal; it used to carry its own
        ``{move name: multiplier}`` table instead, which was keyed on CLASS
        names while the wire carries ``move.name`` (the runtime *instance*
        name) — so ``SlimeVolley`` arrived as ``"Slime Volley"``, missed the
        table, and the heaviest hits in the game were estimated at 1.0x.

        ``Move`` (src/moves/_base.py) declares ``_DAMAGE_MULTIPLIER = 1.0``,
        so every move answers this and the default below is only a coercion
        guard. ANY move that hits for more or less than its user's raw damage
        must override it — that is not a ``TelegraphedSurge`` privilege. Most
        of the declarations in src/moves/_npc.py are on plain ``Move``
        subclasses (NpcAttack, GorranClub, VenomClaw, SpiderBite, BatBite,
        SeismicSlam, TwinFangs), so an audit that only looks at the surge
        family will miss them and leave a new heavy move understating itself
        at 1.0.

        Two ways to declare it, both in src/moves/_npc.py:
          * a move with a fixed factor states it outright (SlimeVolley,
            TidalSurge, WailStrike, SeismicSlam, TwinFangs);
          * a move that rolls a range declares ``_POWER_ROLL_MIN``/``_MAX``
            and derives this as their midpoint, so retuning the roll moves
            the wire value with it (NpcAttack, GorranClub, VenomClaw,
            SpiderBite, BatBite).
        Either way the number is a MIDPOINT on the user's raw damage, never a
        ceiling: the surge family's factor is applied on top of a power
        ``NpcAttack.evaluate`` has already rolled through ``uniform(0.8,
        1.2)``, and ``_estimate_incoming_damage`` renders the wire value as a
        ±20% band and flags lethality off that band's midpoint.

        ``tests/test_npc_moves_coverage.py::TestDeclaredDamageMultiplier``
        discovers the declaring classes by reflection and pins each against
        what ``evaluate()`` really rolls, so it cannot go stale by omission.
        """
        try:
            return float(getattr(move, "_DAMAGE_MULTIPLIER", 1.0))
        except (TypeError, ValueError):
            return 1.0

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
        # src/moves/_base.py), matching how combat_adapter.
        # _get_available_targets already invokes it. Reached via
        # _call_move_method, which resolves *absence* only — there is still no
        # try/except here: an override that raises is a real engine bug, and
        # swallowing it would ship a silently wrong threat radius instead, the
        # exact silent-failure mode this payload's contract test exists to
        # prevent.
        effective_max = CombatantSerializer._call_move_method(
            move, "get_effective_range_max", getattr(move, "user", None)
        )
        if effective_max is not None:
            range_max = effective_max

        try:
            return {"min": int(range_min), "max": int(range_max)}
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _serialize_move_falloff(move: Any) -> Optional[Dict[str, float]]:
        """Accuracy decay curve as ``{"start": ft, "per_ft": points}``, or None
        when the move's accuracy does not decay with distance.

        Straight passthrough of ``Move.get_accuracy_falloff`` (src/moves/
        _base.py) — the engine owns the curve; this layer only names its
        fields for the wire. A decaying move has no real maximum reach: it can
        be fired at any distance and simply decays toward the 2% floor, which
        is why ``mvrange.max`` for one of these is the (very large) distance
        at which a 100-point hit chance would reach zero rather than a wall.
        The client draws the difference — a dissolving gradient for a decaying
        move, a hard ring for a bounded one.
        """
        falloff = CombatantSerializer._call_move_method(
            move, "get_accuracy_falloff", getattr(move, "user", None)
        )
        if not falloff:
            return None
        start, per_ft = falloff
        try:
            return {"start": float(start), "per_ft": float(per_ft)}
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

    # `serialize_health_bar` was removed (issue #430 class).
    #
    # It read `combatant.health` / `combatant.max_health` — names no engine
    # class defines and nothing under src/ ever assigns — so every real
    # combatant serialized as {"current": 0, "max": 100, "percent": 0.0,
    # "status": "critical"}, a full-health Jean included. It had no production
    # caller: nothing in src/ or frontend/ consumed it, and no frontend code
    # spoke its "healthy/injured/wounded/critical" vocabulary. Deleted rather
    # than repaired to `hp`/`maxhp`, because the bucket thresholds were a
    # display policy invented here with no engine counterpart, and
    # `serialize_combatant` already publishes the raw `health.current` /
    # `health.max` the client actually renders from. tools/serializer_fuzzer.py
    # still calls it and must drop that call.

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
        """Serialize a combatant's PLAYER-VISIBLE active status effects.

        Delegates the whole list — including the ``hidden`` filter — to
        ``StateEffectSerializer.serialize_state_list``, which is the single
        owner of State->wire translation. This used to serialize every state
        unfiltered while ``GameService._serialize_active_states`` dropped the
        hidden ones, so ``Dodging`` and ``Parrying`` (the engine's only two
        ``hidden=True`` states, src/states.py:287 and :308) appeared on the
        combat payload and vanished from the player-status payload.
        """
        return StateEffectSerializer.serialize_state_list(
            getattr(combatant, "states", None)
        )

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
#
# EVERY other statustype src/states.py can construct must appear below. The
# `.get(..., "debuff")` fallback in `_get_effect_type` is a coercion guard for
# a mocked or third-party state, NOT a licence to leave a real one unmapped —
# it is what let "death" serialize as a moderate debuff. Both directions are
# pinned by tests/test_npc_moves_coverage.py::TestStatustypeCategoryTable.
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
    # Not a stat penalty and not a tick — DeathKnell's execute, which zeroes HP
    # on application. Categorised with the ailments so it reads as gold/severe
    # rather than as a moderate debuff, which is what the `.get(...)` default
    # below silently gave it.
    "death": "ailment",
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

        ``description`` is the player-facing prose the status panel shows;
        ``tactical_mechanics`` is the engine's own terse statement of what the
        effect actually does — the applied modifiers and the tick interval —
        which ai/combat_strategist.py puts in the combat LLM prompt. Both live
        on ``State`` (src/states.py) and are interpolated from the same class
        constants the ``add_*`` assignments use, so neither can drift from the
        real numbers; the strategist used to hand-copy that column and had
        already gone stale on three effects. Defaults to "" for a state that
        declares none, which the strategist falls back out of.

        Args:
            state: State object from states.py

        Returns:
            Dict with state information
        """
        return {
            "name": str(getattr(state, "name", "Unknown Effect")),
            "type": StateEffectSerializer._get_effect_type(state),
            # The engine's own `statustype` verbatim ("poison", "stun", …),
            # alongside the mapped buff/debuff/ailment `type` above. They are
            # NOT two names for one value: `type` is this layer's UI polarity
            # vocabulary, `status_type` is the engine's effect identity, and
            # the frontend matches on the raw one (ItemDetailDialog.jsx:949 and
            # :1029 compare `s.status_type === 'poison'`). Emitting both is what
            # lets GameService._serialize_active_states delegate here instead of
            # keeping the second, divergent copy of this translation.
            "status_type": str(getattr(state, "statustype", _GENERIC_STATUSTYPE)),
            "description": getattr(state, "description", ""),
            "tactical_mechanics": getattr(state, "tactical_mechanics", ""),
            "severity": StateEffectSerializer._get_severity(state),
            "beats_left": StateEffectSerializer._beats_left(state),
        }

    @staticmethod
    def _beats_left(state: "State") -> float:
        """Remaining beats as a number, never a string or ``None``.

        A degraded/legacy save can carry junk here; the client counts down
        against it, so a non-number has to become 0 rather than reach the wire.
        ``bool`` is excluded explicitly — it is an ``int`` subclass, and
        ``True`` is not a duration.
        """
        beats = getattr(state, "beats_left", 0)
        if isinstance(beats, bool) or not isinstance(beats, (int, float)):
            return 0
        return beats

    @staticmethod
    def is_hidden(state: "State") -> bool:
        """Whether the engine marks this state as not shown to the player.

        ``State.__init__`` takes ``hidden`` (src/states.py:78/114) and only
        ``Dodging`` (:287) and ``Parrying`` (:308) set it. The flag is the
        engine's decision, so every State->wire path must honour it — this is
        the single place that reads it.
        """
        return bool(getattr(state, "hidden", False))

    @staticmethod
    def serialize_state_list(states: List["State"]) -> List[Dict[str, Any]]:
        """Serialize the player-visible states of a list, dropping hidden ones.

        The ``hidden`` filter lives here rather than at each call site: it used
        to exist only in ``GameService._serialize_active_states``, so the same
        ``Dodging``/``Parrying`` state was suppressed on the player-status wire
        and published on the combat wire.

        Tolerates ``None`` and a non-sequence ``states`` (a corrupt save must
        not 500 the request — issue #295); individual unserializable entries are
        skipped rather than taking the whole list down with them.
        """
        if not isinstance(states, (list, tuple)):
            return []
        result = []
        for state in states:
            try:
                if StateEffectSerializer.is_hidden(state):
                    continue
                result.append(StateEffectSerializer.serialize_state(state))
            except Exception:  # noqa: BLE001 - skip an unserializable state
                logger.warning("state serialization failed", exc_info=True)
        return result

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
