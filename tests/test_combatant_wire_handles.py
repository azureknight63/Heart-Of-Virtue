"""Regression tests for the combatant wire-id scheme (issue #511).

``CombatantSerializer.stream_id`` used to interpolate ``id(combatant)`` — the
CPython heap address — into every combatant's wire id. That was wrong twice:

  1. raw process addresses shipped to the client in every combat poll, log line
     and socket emission, and
  2. ``id()`` values are RECYCLED. A dead combatant leaves ``combat_list`` and
     can be freed, so a later-spawned NPC inherits its address — and every
     client-held reference to the dead one (``last_move_target_id``, animation
     ``target_id``s, death-chain bookkeeping) then silently points at a
     different combatant. The identical hazard had already been found *inside*
     the adapter during #506, where an "already announced" set held
     ``id(enemy)`` and so skipped a reinforcement that reused a dead enemy's
     address. This file is the wire-level guard against the third sighting.

The hazard is not directly forceable — CPython gives no guarantee about *when*
it recycles an address — so it is pinned as a contract over the handle scheme:
handles are opaque, stable per combatant, unique across a fight (deaths
included), and persisted with the combatant.
"""

import gc
import pickle
import re
from unittest.mock import MagicMock

import pytest

from src.api.serializers.combat import CombatantSerializer
from src.combatant import COMBAT_HANDLE_ATTR, combatant_handle
from src.npc import NPC, Slime
from src.player import Player

#: What a wire id may look like: the bare ``player``, or a side prefix plus a
#: uuid4 hex handle. Pinned so a future "simplification" back to an address (or
#: to any other guessable/recycled token) fails loudly here.
_WIRE_ID = re.compile(r"^(?:player|(?:ally|enemy)_[0-9a-f]{32})$")


def _ally():
    npc = Slime()
    npc.friend = True
    return npc


class TestWireIdFormat:
    def test_stream_id_matches_the_pinned_scheme(self):
        assert _WIRE_ID.match(CombatantSerializer.stream_id(Player()))
        assert _WIRE_ID.match(CombatantSerializer.stream_id(Slime()))
        assert _WIRE_ID.match(CombatantSerializer.stream_id(_ally()))

    def test_stream_id_never_embeds_the_heap_address(self):
        """The core of #511: no CPython address may reach the client.

        Checked on both sides — an enemy and an ally — because the two took
        separate branches of ``stream_id`` and both interpolated ``id()``.
        """
        for combatant in (Slime(), _ally(), Player()):
            wire_id = CombatantSerializer.stream_id(combatant)
            assert str(id(combatant)) not in wire_id, (
                f"{type(combatant).__name__} leaks its heap address as "
                f"{wire_id!r}"
            )

    def test_the_side_prefix_still_distinguishes_allies_from_enemies(self):
        """The prefix is load-bearing client-side (``id.startsWith('enemy_')``
        in CombatMovePanel/SuggestedMovesPanel/useCombatCoordinator), so the
        handle swap must not have flattened it."""
        assert CombatantSerializer.stream_id(Slime()).startswith("enemy_")
        assert CombatantSerializer.stream_id(_ally()).startswith("ally_")
        assert CombatantSerializer.stream_id(Player()) == "player"


class TestHandleStability:
    def test_a_handle_is_stable_across_repeated_serializations(self):
        """The client matches an animation's ``target_id`` against a
        combatant's own ``id`` from a later poll; a handle that changed per
        call would break every such match."""
        enemy = Slime()
        ids = {CombatantSerializer.stream_id(enemy) for _ in range(5)}
        assert len(ids) == 1

        payload_ids = {
            CombatantSerializer.serialize_combatant(enemy)["id"] for _ in range(5)
        }
        assert payload_ids == ids

    def test_the_handle_outlives_a_side_switch(self):
        """A combatant that changes sides keeps its identity; only the prefix
        moves. (Charmed/turncoat NPCs are the real case.)"""
        npc = Slime()
        before = CombatantSerializer.stream_id(npc)
        npc.friend = True
        after = CombatantSerializer.stream_id(npc)
        assert before != after
        assert before.removeprefix("enemy_") == after.removeprefix("ally_")

    def test_distinct_combatants_never_share_a_wire_id(self):
        roster = [Slime() for _ in range(50)]
        wire_ids = [CombatantSerializer.stream_id(e) for e in roster]
        assert len(set(wire_ids)) == len(roster)


class TestAddressRecyclingHazard:
    def test_a_reinforcement_that_reuses_a_dead_enemys_address_gets_a_new_id(self):
        """The #511 hazard, exercised as directly as CPython allows.

        A combatant is created, its wire id recorded, then dropped and
        collected — freeing its heap block. Fresh combatants of the same type
        are then spawned, exactly as a reinforcement wave does. CPython's
        allocator very often hands the freed block straight back, at which
        point the OLD scheme minted the *same* ``enemy_<id>`` for a different
        NPC and every stale client reference silently retargeted.

        The assertion holds whether or not the address is actually reused (the
        allocator gives no guarantee), so this test never flakes; when reuse
        does happen it is a true reproduction, which is why the reuse is
        reported rather than required.
        """
        doomed = Slime()
        dead_wire_id = CombatantSerializer.stream_id(doomed)
        dead_address = id(doomed)
        del doomed
        gc.collect()

        reinforcements = []
        reused_the_address = False
        for _ in range(200):
            spawn = Slime()
            reinforcements.append(spawn)
            if id(spawn) == dead_address:
                reused_the_address = True

        wire_ids = [CombatantSerializer.stream_id(s) for s in reinforcements]
        assert dead_wire_id not in wire_ids, (
            "a reinforcement inherited the dead combatant's wire id "
            f"(address reused: {reused_the_address}) — stale client-held "
            "target ids now point at the wrong NPC"
        )
        assert len(set(wire_ids)) == len(wire_ids)


class TestPersistence:
    def test_the_handle_survives_a_pickle_round_trip(self):
        """The handle is persisted combatant state: ``Combatant.__getstate__``
        must not strip it, or every load reminted identities and reintroduced
        the aliasing per reload."""
        enemy = Slime()
        before = CombatantSerializer.stream_id(enemy)
        restored = pickle.loads(pickle.dumps(enemy))
        assert CombatantSerializer.stream_id(restored) == before

    def test_getstate_keeps_the_handle(self):
        enemy = Slime()
        handle = combatant_handle(enemy)
        assert enemy.__getstate__()[COMBAT_HANDLE_ATTR] == handle

    def test_a_save_written_before_the_handle_existed_still_loads(self):
        """Backwards compatibility: pre-#511 saves hold combatants with no
        handle at all. They must mint one lazily rather than raising."""
        legacy = Slime()
        legacy.__dict__.pop(COMBAT_HANDLE_ATTR, None)
        assert not hasattr(legacy, COMBAT_HANDLE_ATTR)

        wire_id = CombatantSerializer.stream_id(legacy)
        assert _WIRE_ID.match(wire_id)
        # ...and the lazily minted handle is itself stable from then on.
        assert CombatantSerializer.stream_id(legacy) == wire_id

    def test_two_legacy_combatants_do_not_collide_on_load(self):
        legacy = []
        for _ in range(10):
            npc = Slime()
            npc.__dict__.pop(COMBAT_HANDLE_ATTR, None)
            legacy.append(npc)
        wire_ids = {CombatantSerializer.stream_id(n) for n in legacy}
        assert len(wire_ids) == len(legacy)


class TestHandleMinting:
    def test_the_mint_is_atomic_so_concurrent_polls_agree(self):
        """The combat poll and the socket beat emitter run on different
        threads. A plain ``setattr`` mint lets both find no handle, both mint,
        and the second overwrite the id the first already shipped — leaving
        the client holding an id that resolves to nobody. The mint therefore
        goes through ``__dict__.setdefault``, which is atomic under the GIL.
        """
        enemy = Slime()
        enemy.__dict__.pop(COMBAT_HANDLE_ATTR, None)
        # Whoever got there first wins, and everyone reads that value back.
        enemy.__dict__[COMBAT_HANDLE_ATTR] = "a" * 32
        assert combatant_handle(enemy) == "a" * 32

    def test_a_plain_mock_gets_one_stable_handle(self):
        """``stream_id`` is handed MagicMocks all over the adapter's own tests
        and by the beat streamer's fixtures. ``getattr`` on a Mock manufactures
        a child Mock rather than raising, so the mint has to reject a non-str
        "existing" handle — and must then stay stable, or mock-driven id
        comparisons pass or fail at random.
        """
        double = MagicMock()
        first = combatant_handle(double)
        assert re.fullmatch(r"[0-9a-f]{32}", first)
        assert combatant_handle(double) == first
        assert CombatantSerializer.stream_id(double).endswith(first)

    def test_a_dictless_combatant_with_a_slot_for_the_handle_uses_setattr(self):
        """``__dict__.setdefault`` is the fast path, not the only one: an
        object with a slot for the handle has no instance dict at all and must
        fall through to ``setattr`` rather than land in the weak registry.
        """
        from src.combatant import _FALLBACK_HANDLES

        class Slotted:
            __slots__ = ("friend", COMBAT_HANDLE_ATTR)

            def __init__(self):
                self.friend = False

        slotted = Slotted()
        handle = combatant_handle(slotted)
        assert getattr(slotted, COMBAT_HANDLE_ATTR) == handle
        assert combatant_handle(slotted) == handle
        assert slotted not in _FALLBACK_HANDLES

    def test_a_combatant_that_can_hold_the_handle_nowhere_still_serializes(self):
        """Last resort: no instance dict, no slot, not weak-referenceable.

        Unreachable for a real combatant, but a serializer must degrade to an
        unstable id rather than raise — a raised exception here takes down the
        whole combat poll, not one field (same reasoning as ``_num``'s
        non-finite coercion above it in the serializer).
        """

        class Nowhere:
            __slots__ = ("friend",)

            def __init__(self):
                self.friend = False

        nowhere = Nowhere()
        assert re.fullmatch(r"[0-9a-f]{32}", combatant_handle(nowhere))
        assert CombatantSerializer.stream_id(nowhere).startswith("enemy_")

    def test_a_test_double_that_cannot_hold_an_attribute_still_gets_a_handle(self):
        """``stream_id`` runs over whatever the adapter hands it; a spec'd
        mock rejects ``setattr``. The weak fallback registry must cover that
        without falling back to ``id()``."""

        class Sealed:
            __slots__ = ("friend", "__weakref__")

            def __init__(self):
                self.friend = False

        sealed = Sealed()
        first = combatant_handle(sealed)
        assert first == combatant_handle(sealed)
        assert str(id(sealed)) not in first

    def test_the_fallback_registry_does_not_outlive_its_combatant(self):
        """An ``id()``-keyed cache would be the very hazard #511 closes; the
        fallback is weak-keyed, so its entry dies with the object."""
        from src.combatant import _FALLBACK_HANDLES

        class Sealed:
            __slots__ = ("friend", "__weakref__")

            def __init__(self):
                self.friend = False

        before = len(_FALLBACK_HANDLES)
        sealed = Sealed()
        combatant_handle(sealed)
        assert len(_FALLBACK_HANDLES) == before + 1
        del sealed
        gc.collect()
        assert len(_FALLBACK_HANDLES) == before


class TestAdapterResolvesByHandle:
    """The wire id round-trips: what the adapter publishes is what it accepts.

    ``_lookup_combatant`` strips the prefix and compares the remainder against
    the combatant. When that comparison read ``str(id(...))`` it agreed with
    the old ``stream_id`` by coincidence of sharing one expression; the two
    now have to agree on the handle, which is what this pins.
    """

    @staticmethod
    def _adapter(player):
        from src.api.combat_adapter import ApiCombatAdapter

        adapter = ApiCombatAdapter.__new__(ApiCombatAdapter)
        adapter.player = player
        return adapter

    def _fight(self):
        player = Player()
        enemy = Slime()
        ally = _ally()
        player.combat_list = [enemy]
        player.combat_list_allies = [player, ally]
        return player, enemy, ally

    def test_a_published_wire_id_resolves_back_to_its_combatant(self):
        player, enemy, ally = self._fight()
        adapter = self._adapter(player)

        for combatant in (enemy, ally):
            wire_id = CombatantSerializer.stream_id(combatant)
            assert adapter._lookup_combatant(wire_id) is combatant

    def test_a_heap_address_no_longer_resolves_to_anybody(self):
        """Proves the lookup moved off ``id()`` rather than merely gaining a
        second accepted spelling — a stale address must resolve to nothing."""
        player, enemy, _ = self._fight()
        adapter = self._adapter(player)
        assert adapter._lookup_combatant(f"enemy_{id(enemy)}") is None

    def test_a_dead_enemys_wire_id_stops_resolving_once_it_leaves_the_roster(self):
        player, enemy, _ = self._fight()
        adapter = self._adapter(player)
        stale = CombatantSerializer.stream_id(enemy)

        player.combat_list = []
        reinforcement = Slime()
        player.combat_list = [reinforcement]

        assert adapter._lookup_combatant(stale) is None, (
            "a stale target id resolved onto the reinforcement — the exact "
            "mis-retarget #511 closes"
        )
        assert (
            adapter._lookup_combatant(CombatantSerializer.stream_id(reinforcement))
            is reinforcement
        )


def test_ally_route_targeting_agrees_with_the_serializer():
    """``/inventory/use``'s ally resolver consumes ``stream_id``'s output; the
    two are in different modules and drifted apart is a silent no-target."""
    from src.api.routes.inventory import _resolve_ally_target

    player = Player()
    ally = _ally()
    player.combat_list_allies = [player, ally]

    assert (
        _resolve_ally_target(player, CombatantSerializer.stream_id(ally)) is ally
    )
    assert _resolve_ally_target(player, f"ally_{id(ally)}") is None


def _bare_npc():
    return NPC("Nobody", "nothing", 10, 0, 1, 1, 1, 1, 1, 1)


@pytest.mark.parametrize(
    "factory",
    [Slime, _ally, Player, _bare_npc],
    ids=["enemy", "ally", "player", "bare-npc"],
)
def test_every_combatant_kind_has_an_opaque_handle(factory):
    combatant = factory()
    handle = combatant_handle(combatant)
    assert re.fullmatch(r"[0-9a-f]{32}", handle)
    assert str(id(combatant)) not in handle
