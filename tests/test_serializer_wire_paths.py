"""Cross-path guards: one engine fact must reach every wire the same way.

Two defects motivated this file, and both were divergences rather than plain
mistakes — each path was individually plausible and only wrong relative to the
other:

  * ``State.hidden`` was honoured by ``GameService._serialize_active_states``
    (the player-status wire) and ignored by ``StateEffectSerializer`` (the
    combat wire), so ``Dodging``/``Parrying`` were suppressed on one and
    published on the other.
  * ``serialize_combat_state`` built the player and every enemy twice per
    snapshot — once for ``player``/``enemies`` and again for the flat
    ``combatants`` list — inside a loop that runs up to 20 times per action.

The expectations below are read off the engine (the ``hidden`` flag, the roster
handed in) rather than restated from the serializers, and the state guard
asserts both directions.
"""

from unittest.mock import patch

import pytest


def _npc(name="Goblin"):
    """A real ``src.npc.NPC`` — never a mock, which would agree with anything."""
    from src.npc import NPC

    npc = NPC(
        name=name,
        description="A generic foe",
        damage=15,
        aggro=True,
        exp_award=50,
        maxhp=100,
        protection=5,
        speed=8,
        finesse=9,
        endurance=10,
        strength=12,
        charisma=6,
        intelligence=7,
    )
    npc.hp = 80
    return npc


def _player():
    from src.items import Shortsword
    from src.player import Player

    player = Player()
    player.eq_weapon = Shortsword()
    return player


class TestHiddenStatesAreSuppressedOnEveryWirePath:
    """``State.hidden`` is the ENGINE's decision about player visibility."""

    @staticmethod
    def _discover_states():
        """Every constructible ``State`` subclass declared in src/states.py.

        By reflection, so a state added tomorrow — hidden or not — is covered
        the day it is written rather than the day someone remembers this file.
        """
        import inspect

        from src import states as states_module
        from src.states import State

        target = _npc(name="StateProbe")
        declared, built = [], {}
        for _, cls in inspect.getmembers(states_module, inspect.isclass):
            if not issubclass(cls, State) or cls is State:
                continue
            if cls.__module__ != states_module.__name__:
                continue
            declared.append(cls)
            try:
                built[cls.__name__] = cls(target)
            except Exception:
                # A state whose constructor wants more than a target. The
                # coverage floor asserted below stops these from quietly
                # hollowing the guard out.
                continue
        return declared, built

    def test_discovery_covers_most_states_and_finds_both_polarities(self):
        """Non-vacuity: the reflection must build states, and both kinds."""
        declared, built = self._discover_states()
        assert len(declared) >= 10
        assert len(built) >= 0.7 * len(declared), (
            f"only built {len(built)} of {len(declared)} declared states — "
            "the guard below would be testing almost nothing"
        )
        assert [s for s in built.values() if s.hidden], (
            "no hidden state was built; the filter would be untested"
        )
        assert [s for s in built.values() if not s.hidden], (
            "no visible state was built; the filter could drop everything "
            "and still pass"
        )

    def test_both_wire_paths_publish_exactly_the_non_hidden_states(self):
        from src.api.serializers.combat import CombatantSerializer
        from src.api.services.game_service import GameService

        _, built = self._discover_states()
        combatant = _player()
        combatant.states = list(built.values())

        visible = {s.name for s in built.values() if not s.hidden}
        hidden = {s.name for s in built.values() if s.hidden}
        assert visible and hidden

        combat_wire = CombatantSerializer.serialize_combatant(combatant)[
            "status_effects"
        ]
        status_wire = GameService._serialize_active_states(combatant)

        for label, wire in (("combat", combat_wire), ("player-status", status_wire)):
            names = {e["name"] for e in wire}
            assert visible <= names, (
                f"{label} wire dropped visible state(s): {sorted(visible - names)}"
            )
            assert not (hidden & names), (
                f"{label} wire published hidden state(s): {sorted(hidden & names)}"
            )

    def test_dodging_and_parrying_are_the_hidden_pair(self):
        """Ties the abstract guard to the two states that actually motivated it.

        Named here only as a sanity anchor — the guard above is derived from the
        flag, not from these names, so it still covers a third hidden state
        added later.
        """
        _, built = self._discover_states()
        assert {n for n, s in built.items() if s.hidden} == {"Dodging", "Parrying"}

    def test_both_wire_paths_agree_on_status_type_and_beats_left(self):
        """The secondary divergence: same fact, different name and type.

        The service path published the engine's ``statustype`` as
        ``status_type`` and coerced ``beats_left`` to a number; the serializer
        path published neither — its ``type`` is a DIFFERENT fact (the mapped
        UI polarity), and ``beats_left`` went out raw.
        """
        from src.api.serializers.combat import StateEffectSerializer
        from src.api.services.game_service import GameService
        from src.states import Poisoned

        combatant = _player()
        poison = Poisoned(combatant)
        poison.beats_left = "not a number"
        combatant.states = [poison]

        serializer_wire = StateEffectSerializer.serialize_state_list(combatant.states)
        service_wire = GameService._serialize_active_states(combatant)

        assert serializer_wire[0]["status_type"] == service_wire[0]["status_type"]
        assert serializer_wire[0]["status_type"] == poison.statustype == "poison"
        assert serializer_wire[0]["beats_left"] == service_wire[0]["beats_left"] == 0
        # `type` must not be mistaken for a rename of `status_type`: the
        # frontend matches on the raw engine value (ItemDetailDialog.jsx:949).
        assert serializer_wire[0]["type"] == "ailment" != poison.statustype

    @pytest.mark.parametrize("states", [None, "not a list", 42, []])
    def test_state_list_tolerates_a_degraded_states_attribute(self, states):
        """A corrupt save must not 500 the request (issue #295)."""
        from src.api.serializers.combat import StateEffectSerializer

        assert StateEffectSerializer.serialize_state_list(states) == []


class TestCombatStateSerializesEachCombatantOnce:
    """``serialize_combat_state`` runs once per beat inside the adapter's loop.

    ``ApiCombatAdapter._execute_move`` re-serializes the whole battlefield after
    every beat, up to ``max_beats = 20`` for a single player action
    (combat_adapter.py:1286-1349), so a duplicated per-combatant walk —
    inventory, ``known_moves``, ``states``, plus the engine's
    ``get_effective_range_max``/``get_accuracy_falloff`` queries — is paid up to
    20 times over for one click.
    """

    def _roster(self):
        player = _player()
        allies = [_npc(name=f"Ally{i}") for i in range(3)]
        for ally in allies:
            ally.friend = True
        enemies = [_npc(name=f"Foe{i}") for i in range(4)]
        return player, allies, enemies

    def test_one_serialize_call_per_entity(self):
        from src.api.serializers.combat import (
            CombatantSerializer,
            CombatStateSerializer,
        )

        player, allies, enemies = self._roster()
        roster = [player] + allies + enemies
        real = CombatantSerializer.serialize_combatant
        seen = []

        def counting(combatant, reference=None):
            seen.append(combatant)
            return real(combatant, reference=reference)

        with patch.object(
            CombatantSerializer, "serialize_combatant", staticmethod(counting)
        ):
            CombatStateSerializer.serialize_combat_state(
                player, enemies, allies=allies
            )

        # Expectation derived from the roster handed in, not a literal count —
        # and identity-compared, so serializing the wrong entity twice fails too.
        assert seen == roster, (
            f"expected exactly one serialization per combatant "
            f"({len(roster)}), got {len(seen)}"
        )

    def test_the_flat_roster_is_the_three_views_concatenated(self):
        """``combatants`` is genuinely consumed (combat_beat_stream, frontend).

        Reusing the already-built dicts is what makes it impossible for it to
        disagree with the ``player``/``allies``/``enemies`` views it repeats.
        """
        from src.api.serializers.combat import CombatStateSerializer

        player, allies, enemies = self._roster()
        state = CombatStateSerializer.serialize_combat_state(
            player, enemies, allies=allies
        )

        assert state["combatants"] == (
            [state["player"]] + state["allies"] + state["enemies"]
        )
        assert len(state["combatants"]) == 1 + len(allies) + len(enemies)
        assert state["turn_order"] == [c["id"] for c in state["combatants"]]
