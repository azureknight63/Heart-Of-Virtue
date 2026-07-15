#!/usr/bin/env python3
"""Serializer fuzzer for Heart of Virtue API serializers (issue #295).

Feeds plausible-but-degraded engine object graphs — real ``Player``/``NPC``/
``Item``/``State``/``Move``/world-``Object``/``Event`` instances with a random
subset of attributes deleted, set to ``None``, or swapped to a wrong type —
into every serializer entry point under ``src/api/serializers/*`` plus
``GameService._serialize_active_states``, and asserts the serializer contract
from CLAUDE.md:

  * Serializers **never raise** on a degraded object -- they emit a
    best-effort JSON dict, falling back to sane defaults for missing/bad
    fields.
  * Output is always **JSON-serializable** -- no live engine object (Item,
    NPC, custom class instance) leaks into the returned dict/list.

This mirrors the structure of ``tools/save_fuzzer.py`` (``Finding`` class,
seeded RNG, ``run_fuzz(iterations, seed)``, ``main()``) but targets the
serializer layer instead of the pickle loader, and pure in-memory engine
objects instead of pickled bytes -- no Flask app/session is built, so the
companion test can live directly under ``tests/`` (see CLAUDE.md's guidance
that only real-session integration tests belong in ``tests/api/``).

Usage:
    python tools/serializer_fuzzer.py                 # 500 iterations, random seed
    python tools/serializer_fuzzer.py --iterations 5000
    python tools/serializer_fuzzer.py --seed 1337      # reproducible run
"""

import os
import sys
import json
import random
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.player import Player  # noqa: E402
from src.npc import NPC, Merchant  # noqa: E402
from src.items import Longsword, LeatherArmor, GoldRing, Restorative, Gold  # noqa: E402
from src.states import State  # noqa: E402
from src.moves._unarmed import PowerStrike  # noqa: E402
from src.objects import Shrine, Crate  # noqa: E402
from src.events import Event  # noqa: E402
from src import secure_pickle as sp  # noqa: E402

from src.api.serializers.item_serializer import ItemSerializer  # noqa: E402
from src.api.serializers.npc_serializer import NPCSerializer  # noqa: E402
from src.api.serializers.object_serializer import ObjectSerializer  # noqa: E402
from src.api.serializers.event_serializer import EventSerializer  # noqa: E402
from src.api.serializers.shop_serializer import ShopSerializer  # noqa: E402
from src.api.serializers.reputation import NPCRelationshipSerializer  # noqa: E402
from src.api.serializers.inventory import (  # noqa: E402
    InventoryItemSerializer,
    InventorySerializer,
    EquipmentSlotSerializer,
    EquipmentSerializer,
    ItemDetailSerializer,
    ItemComparisonSerializer,
)
from src.api.serializers.npc_ai import (  # noqa: E402
    NPCAIStateSerializer,
    DialogueStateSerializer,
    NPCBehaviorProfileSerializer,
)
from src.api.serializers.combat import (  # noqa: E402
    CombatStateSerializer,
    CombatantSerializer,
    MoveSerializer,
    StateEffectSerializer,
)
from src.api.services.game_service import GameService  # noqa: E402


# ---------------------------------------------------------------------------
# Finding
# ---------------------------------------------------------------------------

class Finding:
    """An invariant violation, carrying enough context to reproduce it."""

    def __init__(self, seed, iteration, category, detail):
        self.seed = seed
        self.iteration = iteration
        self.category = category
        self.detail = detail

    def __str__(self):
        return (f"[seed={self.seed} iter={self.iteration} "
                f"{self.category}] {self.detail}")


def security_findings(findings):
    """All findings here are invariant breaches -- kept for API parity with
    save_fuzzer's split so tests/run_fuzz callers can share a shape."""
    return list(findings)


coverage_findings = lambda findings: []  # noqa: E731 - no informational category here


# ---------------------------------------------------------------------------
# Degradation primitives
# ---------------------------------------------------------------------------

def _bad_scalar(rng):
    """A value of a type callers plausibly don't expect for a given field."""
    return rng.choice([
        None,
        "",
        "not_a_number",
        float("nan"),
        float("inf"),
        float("-inf"),
        -999999,
        0,
        [],
        {},
        set(),
        object(),
    ])


def _bad_container(rng):
    """A value that looks like a container but is malformed for its expected shape."""
    return rng.choice([
        None,
        "a_string_not_a_list",
        123,
        {},
        [],
        [None, None, None],
        {None: object()},
        {"weapon": object()},  # non-Item value in an equipment-like dict
        list(range(2000)),  # oversized
        set([1, 2, 3]),
    ])


# Attributes commonly read by the serializers under test, across all roles.
# Fuzzing adds/overwrites these (even if the current engine class doesn't set
# them itself) because degraded/legacy objects can carry stale or foreign
# attributes that a real save produced under an older schema.
_INTERESTING_ATTRS = [
    "name", "description", "hp", "maxhp", "max_hp", "health", "max_health",
    "level", "states", "inventory", "known_moves", "combat_proximity",
    "combat_position", "combat_list", "equipped", "resistance", "resistances",
    "add_resistance", "status_resistance", "add_status_resistance",
    "status_effects", "keywords", "interactions", "weight", "value", "power",
    "quantity", "count", "subtype", "maintype", "equip_states", "hidden",
    "hide_factor", "announce", "merchandise", "isequipped", "eq_weapon",
    "current_move", "reputation", "shop_name", "buy_modifier",
    "sell_modifier", "_buyback_ledger", "memory", "trust", "aggression",
    "mood", "dialogue_flags", "friend", "is_hostile", "aggro",
    "loquacity_max", "loquacity_current", "loquacity_threshold",
    "speed", "damage", "armor", "accuracy", "evasion", "defense",
    "attack_power", "strength", "finesse", "endurance", "intelligence",
    "charisma", "fatigue", "maxfatigue", "stat_bonuses",
    "resistance_bonuses", "damage_per_turn", "healing_per_turn",
    "resistable", "beats_left", "state_type", "applies_state",
    "base_damage", "damage_type", "mp_cost", "stamina_cost", "range",
    "cooldown_max", "cooldown", "move_type", "category", "passive",
]


def degrade(obj, rng, n=None):
    """Mutate a subset of obj's attributes to None/wrong-type/malformed values.

    Operates on real, freshly constructed engine instances (never shared
    across iterations) so failures are attributable to the specific mutation.
    """
    attrs = set(getattr(obj, "__dict__", {}).keys()) | set(_INTERESTING_ATTRS)
    attrs = list(attrs)
    rng.shuffle(attrs)
    if n is None:
        n = rng.randint(1, min(6, len(attrs)))
    for attr in attrs[:n]:
        choice = rng.random()
        try:
            if choice < 0.5:
                setattr(obj, attr, _bad_scalar(rng))
            else:
                setattr(obj, attr, _bad_container(rng))
        except Exception:
            # Some attributes are read-only properties on real engine classes;
            # skip rather than treat as a fuzzer bug.
            continue
    return obj


# ---------------------------------------------------------------------------
# Sample pool of real, constructible engine instances (factories -- always
# build fresh so degradation in one iteration can't bleed into another)
# ---------------------------------------------------------------------------

def _mk_player():
    return Player()


def _mk_npc():
    return NPC("Fuzz NPC", "a fuzz target", 5, True, 10)


def _mk_merchant():
    return Merchant("Fuzz Merchant", "sells things", 1, False, 5, 10)


def _mk_item():
    return random.choice([Longsword, LeatherArmor, GoldRing, Restorative, Gold])()


def _mk_state():
    return State("FuzzState", target=None)


def _mk_move():
    return PowerStrike(Player())


def _mk_object():
    return Shrine()


def _mk_container():
    return Crate(None, None)


def _mk_event():
    return Event("FuzzEvent")


def _mk_legacy_placeholder():
    """A ``_legacy_placeholder`` instance in the exact shape SafeUnpickler
    synthesizes for a missing legacy class (issue #13's secure_pickle)."""
    u = sp.SafeUnpickler.__new__(sp.SafeUnpickler)
    cls = u._make_placeholder("src.story.ch_fuzz", "GoneEvent")
    return cls()


_FACTORIES = {
    "player": _mk_player,
    "npc": _mk_npc,
    "merchant": _mk_merchant,
    "item": _mk_item,
    "state": _mk_state,
    "move": _mk_move,
    "object": _mk_object,
    "container": _mk_container,
    "event": _mk_event,
    "legacy_placeholder": _mk_legacy_placeholder,
}


# ---------------------------------------------------------------------------
# JSON-serializability check
# ---------------------------------------------------------------------------

def _assert_json_safe(seed, i, label, value, findings):
    try:
        json.dumps(value)
    except (TypeError, ValueError) as exc:
        findings.append(Finding(seed, i, "non-json-leak",
                                f"{label} returned non-JSON-serializable output: "
                                f"{type(exc).__name__}: {exc}"))


def _call(seed, i, label, fn, findings):
    """Invoke fn(); record a crash Finding on any exception, else JSON-check."""
    try:
        result = fn()
    except Exception as exc:  # noqa: BLE001 - any raise here is the invariant breach
        findings.append(Finding(seed, i, "crash",
                                f"{label} raised {type(exc).__name__}: {exc}"))
        return
    _assert_json_safe(seed, i, label, result, findings)


# ---------------------------------------------------------------------------
# Per-role serializer drivers
# ---------------------------------------------------------------------------

def _fuzz_item(seed, i, rng, findings):
    item = degrade(_mk_item(), rng)
    _call(seed, i, "ItemSerializer.serialize", lambda: ItemSerializer.serialize(item), findings)
    _call(seed, i, "ItemSerializer.serialize_list",
          lambda: ItemSerializer.serialize_list([item, degrade(_mk_item(), rng)]), findings)
    _call(seed, i, "ItemSerializer.serialize_with_effects",
          lambda: ItemSerializer.serialize_with_effects(item), findings)
    _call(seed, i, "ItemSerializer.serialize_inventory",
          lambda: ItemSerializer.serialize_inventory([item], include_effects=True), findings)
    _call(seed, i, "ItemSerializer.serialize_container",
          lambda: ItemSerializer.serialize_container([item]), findings)

    player = degrade(_mk_player(), rng)
    _call(seed, i, "InventoryItemSerializer.serialize",
          lambda: InventoryItemSerializer.serialize(item, 0, player), findings)
    _call(seed, i, "ItemDetailSerializer.serialize",
          lambda: ItemDetailSerializer.serialize(item), findings)
    other = degrade(_mk_item(), rng)
    _call(seed, i, "ItemComparisonSerializer.serialize",
          lambda: ItemComparisonSerializer.serialize(item, other), findings)
    _call(seed, i, "EquipmentSlotSerializer.serialize",
          lambda: EquipmentSlotSerializer.serialize("weapon", item), findings)


def _fuzz_npc(seed, i, rng, findings):
    npc = degrade(_mk_npc(), rng)
    _call(seed, i, "NPCSerializer.serialize", lambda: NPCSerializer.serialize(npc), findings)
    _call(seed, i, "NPCSerializer.serialize_list",
          lambda: NPCSerializer.serialize_list([npc, degrade(_mk_npc(), rng)]), findings)
    _call(seed, i, "NPCSerializer.serialize_with_stats",
          lambda: NPCSerializer.serialize_with_stats(npc), findings)
    _call(seed, i, "NPCSerializer.serialize_merchant",
          lambda: NPCSerializer.serialize_merchant(npc), findings)
    _call(seed, i, "NPCSerializer.serialize_with_inventory",
          lambda: NPCSerializer.serialize_with_inventory(npc), findings)
    _call(seed, i, "NPCSerializer.serialize_for_combat",
          lambda: NPCSerializer.serialize_for_combat(npc), findings)

    _call(seed, i, "NPCAIStateSerializer.serialize_npc_ai_state",
          lambda: NPCAIStateSerializer.serialize_npc_ai_state(npc), findings)
    _call(seed, i, "DialogueStateSerializer.serialize_dialogue_state",
          lambda: DialogueStateSerializer.serialize_dialogue_state(npc), findings)
    _call(seed, i, "DialogueStateSerializer.serialize_dialogue_options",
          lambda: DialogueStateSerializer.serialize_dialogue_options(npc), findings)
    _call(seed, i, "NPCBehaviorProfileSerializer.serialize_behavior_profile",
          lambda: NPCBehaviorProfileSerializer.serialize_behavior_profile(npc), findings)


def _fuzz_merchant(seed, i, rng, findings):
    merchant = degrade(_mk_merchant(), rng)
    player = degrade(_mk_player(), rng)
    _call(seed, i, "ShopSerializer.serialize_state",
          lambda: ShopSerializer.serialize_state(merchant, player, 0), findings)
    _call(seed, i, "ShopSerializer.get_effective_buy_modifier",
          lambda: ShopSerializer.get_effective_buy_modifier(merchant, player), findings)
    _call(seed, i, "ShopSerializer.get_effective_sell_modifier",
          lambda: ShopSerializer.get_effective_sell_modifier(merchant, player), findings)
    _call(seed, i, "ShopSerializer.serialize_player_sellable",
          lambda: ShopSerializer.serialize_player_sellable(player, 0.5), findings)

    reputation = rng.choice([50, -50, 0, "bad", None, float("nan")])
    _call(seed, i, "NPCRelationshipSerializer.serialize_relationship",
          lambda: NPCRelationshipSerializer.serialize_relationship("id", "Name", reputation),
          findings)


def _fuzz_state(seed, i, rng, findings):
    state = degrade(_mk_state(), rng)
    _call(seed, i, "StateEffectSerializer.serialize_state",
          lambda: StateEffectSerializer.serialize_state(state), findings)
    _call(seed, i, "StateEffectSerializer.serialize_state_list",
          lambda: StateEffectSerializer.serialize_state_list([state]), findings)
    _call(seed, i, "StateEffectSerializer.serialize_state_with_duration",
          lambda: StateEffectSerializer.serialize_state_with_duration(state, 3), findings)


def _fuzz_move(seed, i, rng, findings):
    move = degrade(_mk_move(), rng)
    _call(seed, i, "MoveSerializer.serialize_move",
          lambda: MoveSerializer.serialize_move(move), findings)
    _call(seed, i, "MoveSerializer.serialize_move_list",
          lambda: MoveSerializer.serialize_move_list([move]), findings)
    _call(seed, i, "MoveSerializer.serialize_move_with_cooldown",
          lambda: MoveSerializer.serialize_move_with_cooldown(move, 2), findings)


def _fuzz_object(seed, i, rng, findings):
    obj = degrade(rng.choice([_mk_object, _mk_container])(), rng)
    _call(seed, i, "ObjectSerializer.serialize", lambda: ObjectSerializer.serialize(obj), findings)
    _call(seed, i, "ObjectSerializer.serialize_list",
          lambda: ObjectSerializer.serialize_list([obj]), findings)
    _call(seed, i, "ObjectSerializer.serialize_container",
          lambda: ObjectSerializer.serialize_container(obj), findings)
    _call(seed, i, "ObjectSerializer.serialize_interactive",
          lambda: ObjectSerializer.serialize_interactive(obj), findings)
    _call(seed, i, "ObjectSerializer.serialize_door",
          lambda: ObjectSerializer.serialize_door(obj), findings)
    _call(seed, i, "ObjectSerializer.serialize_shrine",
          lambda: ObjectSerializer.serialize_shrine(obj), findings)

    # Dict-shaped "object" (the is_dict branch in ObjectSerializer._serialize_base)
    dict_obj = {"name": rng.choice([None, 123]), "keywords": rng.choice([None, "nope"])}
    _call(seed, i, "ObjectSerializer.serialize(dict)",
          lambda: ObjectSerializer.serialize(dict_obj), findings)


def _fuzz_event(seed, i, rng, findings):
    event = degrade(_mk_event(), rng)
    _call(seed, i, "EventSerializer.serialize", lambda: EventSerializer.serialize(event), findings)
    _call(seed, i, "EventSerializer.serialize_list",
          lambda: EventSerializer.serialize_list([event]), findings)
    _call(seed, i, "EventSerializer.serialize_with_conditions",
          lambda: EventSerializer.serialize_with_conditions(event), findings)
    _call(seed, i, "EventSerializer.serialize_with_consequences",
          lambda: EventSerializer.serialize_with_consequences(event), findings)
    _call(seed, i, "EventSerializer.serialize_story_event",
          lambda: EventSerializer.serialize_story_event(event), findings)
    _call(seed, i, "EventSerializer.serialize_combat_event",
          lambda: EventSerializer.serialize_combat_event(event), findings)
    _call(seed, i, "EventSerializer.serialize_conditional_event",
          lambda: EventSerializer.serialize_conditional_event(event), findings)
    _call(seed, i, "EventSerializer.serialize_with_input",
          lambda: EventSerializer.serialize_with_input(event), findings)


def _fuzz_legacy_placeholder(seed, i, rng, findings):
    """The exact object shape SafeUnpickler synthesizes for missing legacy
    classes -- must survive every serializer untouched (no further
    degradation; this shape alone is the interesting case)."""
    placeholder = _mk_legacy_placeholder()
    _call(seed, i, "ItemSerializer.serialize(placeholder)",
          lambda: ItemSerializer.serialize(placeholder), findings)
    _call(seed, i, "NPCSerializer.serialize_with_inventory(placeholder)",
          lambda: NPCSerializer.serialize_with_inventory(placeholder), findings)
    _call(seed, i, "ObjectSerializer.serialize(placeholder)",
          lambda: ObjectSerializer.serialize(placeholder), findings)
    _call(seed, i, "EventSerializer.serialize_with_input(placeholder)",
          lambda: EventSerializer.serialize_with_input(placeholder), findings)


def _fuzz_combat(seed, i, rng, findings):
    """Combat-state / combatant serialization, including GameService's
    _serialize_active_states helper (CLAUDE.md-named fuzz target)."""
    player = degrade(_mk_player(), rng)
    reference = _mk_player()  # a healthy reference, as combat_adapter passes

    _call(seed, i, "CombatantSerializer.serialize_combatant(player)",
          lambda: CombatantSerializer.serialize_combatant(player, reference=reference), findings)

    npc1 = degrade(_mk_npc(), rng)
    npc2 = degrade(_mk_npc(), rng)
    _call(seed, i, "CombatantSerializer.serialize_combatant(npc)",
          lambda: CombatantSerializer.serialize_combatant(npc1, reference=reference), findings)
    _call(seed, i, "CombatantSerializer.serialize_combatant_list",
          lambda: CombatantSerializer.serialize_combatant_list([player, npc1, npc2]), findings)
    _call(seed, i, "CombatantSerializer.serialize_health_bar",
          lambda: CombatantSerializer.serialize_health_bar(npc1), findings)

    _call(seed, i, "CombatStateSerializer.serialize_combat_state",
          lambda: CombatStateSerializer.serialize_combat_state(
              player, [npc1, npc2], allies=[degrade(_mk_npc(), rng)]), findings)
    _call(seed, i, "CombatStateSerializer.serialize_turn_data",
          lambda: CombatStateSerializer.serialize_turn_data(npc1), findings)
    _call(seed, i, "CombatStateSerializer.serialize_battle_summary",
          lambda: CombatStateSerializer.serialize_battle_summary(player, [npc1, npc2], True),
          findings)

    _call(seed, i, "GameService._serialize_active_states",
          lambda: GameService._serialize_active_states(player), findings)
    _call(seed, i, "GameService._serialize_active_states(npc)",
          lambda: GameService._serialize_active_states(npc1), findings)


def _fuzz_inventory_equipment(seed, i, rng, findings):
    player = degrade(_mk_player(), rng)
    _call(seed, i, "InventorySerializer.serialize",
          lambda: InventorySerializer.serialize(player), findings)
    _call(seed, i, "EquipmentSerializer.serialize",
          lambda: EquipmentSerializer.serialize(player), findings)


_CATEGORIES = (
    _fuzz_item,
    _fuzz_npc,
    _fuzz_merchant,
    _fuzz_state,
    _fuzz_move,
    _fuzz_object,
    _fuzz_event,
    _fuzz_legacy_placeholder,
    _fuzz_combat,
    _fuzz_inventory_equipment,
)


def run_fuzz(iterations=500, seed=None):
    """Run the fuzzer and return a list of :class:`Finding` (empty == clean)."""
    if seed is None:
        seed = random.randrange(2 ** 32)
    rng = random.Random(seed)
    findings = []
    for i in range(iterations):
        check = rng.choice(_CATEGORIES)
        try:
            check(seed, i, rng, findings)
        except Exception as exc:  # noqa: BLE001 - the harness itself must not die
            findings.append(Finding(seed, i, "harness-error",
                                    f"{check.__name__}: {type(exc).__name__}: {exc}"))
    return findings


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=500)
    parser.add_argument("--seed", type=int, default=None,
                        help="Fix the RNG seed for a reproducible run.")
    args = parser.parse_args(argv)

    findings = run_fuzz(args.iterations, args.seed)

    if findings:
        print(f"FAIL: {len(findings)} serializer invariant violation(s):")
        seen = set()
        for f in findings:
            if f.detail not in seen:
                seen.add(f.detail)
                print("  " + str(f))
        return 1
    print(f"OK: {args.iterations} iterations, no serializer invariant violations.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
