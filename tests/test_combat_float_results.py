"""Per-beat combat *results* -- what the floating battlefield text shows (#667).

"-33 HP", "+22 HP", "+ Staggered", "- Poisoned", "Miss!", "Parried!": every one
of those is a fact the engine already decided. The client must not derive them
from prose or invent them, so ``ApiCombatAdapter`` measures them off the real
combatants around each beat and ships them as structured ``results``:

* ``{"id", "kind": "hp", "delta"}``                     -- signed HP change
* ``{"id", "kind": "status", "status", "change"}``      -- ``added``/``removed``
* ``{"id", "kind": "outcome", "outcome"}``              -- a resolution with no
  HP footprint (miss, parry, ...), read off the beat's animation carriers

Default (log-driven) path: the results ride on the beat's LAST log entry, so
they surface when the client reveals that beat. Streaming path: the streamer
copies them onto the ``combat:beat`` as ``results``.
"""

from src.api.combat_beat_stream import CombatBeatStreamer
from src.api.schemas import combat_beat as cb
from src.api.serializers.combat import CombatantSerializer
from src.moves._base import OUTCOME_MISS, publish_outcome
from src.narration import narrate
import src.states as states
from tests._combat_fixtures import run_scripted_beat as _run_scripted_beat, seeded


# ── the pure builder ────────────────────────────────────────────────────────


def test_hp_loss_and_gain_become_signed_hp_results():
    before = {"enemy_a": (40, frozenset()), "player": (10, frozenset())}
    after = {"enemy_a": (7, frozenset()), "player": (32, frozenset())}

    results = cb.build_beat_results(before, after)

    assert {"id": "enemy_a", "kind": "hp", "delta": -33} in results
    assert {"id": "player", "kind": "hp", "delta": 22} in results


def test_status_gained_and_cleared_are_reported_by_name():
    before = {"enemy_a": (40, frozenset({"Poisoned"}))}
    after = {"enemy_a": (40, frozenset({"Staggered"}))}

    results = cb.build_beat_results(before, after)

    assert results == [
        {"id": "enemy_a", "kind": "status", "status": "Staggered", "change": "added"},
        {"id": "enemy_a", "kind": "status", "status": "Poisoned", "change": "removed"},
    ]


def test_only_outcomes_without_an_hp_footprint_become_outcome_results():
    """A hit/glance is already told by its HP number; a miss or parry is not."""
    resolutions = [
        {"target_id": "enemy_a", "outcome": "hit"},
        {"target_id": "enemy_b", "outcome": "miss"},
        {"target_id": "enemy_c", "outcome": "parry"},
        {"target_id": "enemy_d", "outcome": "absorb"},
        {"target_id": None, "outcome": "miss"},
        {"target_id": "enemy_e", "outcome": "not-an-outcome"},
    ]

    results = cb.build_beat_results({}, {}, resolutions)

    assert results == [
        {"id": "enemy_b", "kind": "outcome", "outcome": "miss"},
        {"id": "enemy_c", "kind": "outcome", "outcome": "parry"},
        {"id": "enemy_d", "kind": "outcome", "outcome": "absorb"},
    ]


def test_a_combatant_with_no_baseline_or_already_dead_reports_nothing():
    before = {"enemy_dead": (0, frozenset({"Poisoned"}))}
    after = {
        "enemy_dead": (0, frozenset()),
        "enemy_new": (20, frozenset({"Staggered"})),
    }

    assert cb.build_beat_results(before, after) == []


def test_a_killing_blow_keeps_its_damage_but_not_the_statuses_death_wiped():
    before = {"enemy_a": (12, frozenset({"Poisoned"}))}
    after = {"enemy_a": (0, frozenset())}

    assert cb.build_beat_results(before, after) == [
        {"id": "enemy_a", "kind": "hp", "delta": -12},
    ]


def test_an_overkill_blow_reports_only_the_hp_actually_lost():
    """Floating text shows HP removed, not the raw overkill (maintainer
    decision 2026-09-24): a 45-point hit on a 10-HP Slime reads -10 HP."""
    before = {"enemy_a": (10, frozenset())}
    after = {"enemy_a": (-35, frozenset())}

    assert cb.build_beat_results(before, after) == [
        {"id": "enemy_a", "kind": "hp", "delta": -10},
    ]


def test_results_are_capped():
    before = {f"enemy_{i}": (50, frozenset()) for i in range(100)}
    after = {f"enemy_{i}": (40, frozenset()) for i in range(100)}

    assert len(cb.build_beat_results(before, after)) == cb.MAX_BEAT_RESULTS


def test_every_result_kind_and_change_is_in_the_declared_vocabulary():
    before = {"a": (10, frozenset({"X"}))}
    after = {"a": (5, frozenset({"Y"}))}
    resolutions = [{"target_id": "a", "outcome": "miss"}]

    for result in cb.build_beat_results(before, after, resolutions):
        assert result["kind"] in cb.RESULT_KINDS
        if result["kind"] == "status":
            assert result["change"] in cb.STATUS_RESULT_CHANGES
        if result["kind"] == "outcome":
            assert result["outcome"] in cb.TEXT_OUTCOMES
    assert set(cb.TEXT_OUTCOMES) <= set(cb.OUTCOMES)


# ── the adapter measures the real engine around a real beat ──────────────────


def _beat_results(result, index=0):
    """The results the adapter attached to beat ``index``'s last log entry."""
    log = result["beat_states"][index]["log"]
    assert log, "the beat narrated nothing, so there is nowhere to attach results"
    return log[-1].get("results")


def test_a_beat_ships_the_real_hp_and_status_changes_on_its_last_log_entry():
    poison = {}

    def prepare(player):
        # Jean enters the beat poisoned and hurt, so the cure and the heal
        # below are real changes against a real baseline.
        with seeded():
            poison["state"] = states.Poisoned(player)
        player.states.append(poison["state"])
        player.hp = player.maxhp - 10

    def effect(player, slime):
        slime.hp -= 33
        slime.states.append(states.Staggered(slime))
        player.hp += 5
        player.states.remove(poison["state"])
        narrate("Scripted things happen.")

    result, slime = _run_scripted_beat(effect, prepare=prepare)

    results = _beat_results(result)
    slime_id = CombatantSerializer.stream_id(slime)
    assert results is not None, "no results were attached to the beat"
    assert {"id": slime_id, "kind": "hp", "delta": -33} in results
    assert {
        "id": slime_id, "kind": "status", "status": "Staggered", "change": "added",
    } in results
    assert {"id": "player", "kind": "hp", "delta": 5} in results
    assert {
        "id": "player", "kind": "status", "status": "Poisoned", "change": "removed",
    } in results


def test_a_published_miss_becomes_an_outcome_result_for_its_target():
    def effect(player, slime):
        publish_outcome(player, OUTCOME_MISS, slime)
        narrate("Jean's attack just missed!")

    result, slime = _run_scripted_beat(effect)

    assert {
        "id": CombatantSerializer.stream_id(slime), "kind": "outcome", "outcome": "miss",
    } in _beat_results(result)


def test_a_killing_blow_still_reports_its_damage_after_the_corpse_is_removed():
    """The adapter drops a dead enemy from ``combat_list`` inside the beat.

    A diff of the post-beat roster would therefore never see the blow that
    killed it -- the most important number of the fight. The adapter measures
    the combatants it snapshotted BEFORE the beat, so the corpse still counts.
    """

    def effect(player, slime):
        slime.hp = 0
        narrate("The slime bursts.")

    result, slime = _run_scripted_beat(effect, slime_hp=21)

    assert not result["beat_states"][0]["enemies"], "the corpse should be gone"
    assert {
        "id": CombatantSerializer.stream_id(slime), "kind": "hp", "delta": -21,
    } in _beat_results(result)


def test_a_quiet_beat_attaches_no_results():
    def effect(player, slime):
        narrate("Jean waits.")

    result, _ = _run_scripted_beat(effect)

    assert not _beat_results(result)


# ── the streaming path forwards the same results ────────────────────────────


class _FakeSocketIO:
    def __init__(self):
        self.emits = []

    def emit(self, event, payload, room=None):
        self.emits.append((event, payload, room))


def test_streamed_beats_carry_the_results_of_their_log_window():
    sock = _FakeSocketIO()
    streamer = CombatBeatStreamer(
        sock, "combat_s1", initial_combatants=[{"id": "enemy_a", "hp": 40}]
    )
    results = [{"id": "enemy_a", "kind": "hp", "delta": -33}]
    snapshot = {
        "combatants": [{"id": "enemy_a", "hp": 7}],
        "log": [
            {"message": "Jean struck the Slime for 33 damage!"},
            {"message": "Attack animation", "results": results,
             "animation": {"source_id": "player", "target_id": "enemy_a",
                           "type": "attack", "outcome": "hit"}},
        ],
    }

    streamer.stream_beats([snapshot])

    beats = [payload for event, payload, _ in sock.emits if event == cb.BEAT_EVENT]
    assert len(beats) == 1
    assert beats[0]["results"] == results
    assert cb.validate_beat(beats[0]) == []


def test_a_beat_whose_only_news_is_a_result_is_still_streamed():
    """A miss changes no HP and carries no death, but it is still news."""
    sock = _FakeSocketIO()
    streamer = CombatBeatStreamer(
        sock, "combat_s1", initial_combatants=[{"id": "enemy_a", "hp": 40}]
    )
    snapshot = {
        "combatants": [{"id": "enemy_a", "hp": 40}],
        "log": [{"message": "x", "results": [
            {"id": "enemy_a", "kind": "outcome", "outcome": "miss"}]}],
    }

    streamer.stream_beats([snapshot])

    assert [e for e, _, _ in sock.emits] == [cb.BEAT_EVENT]


def test_build_beat_defaults_results_to_empty():
    beat = cb.build_beat(1, "player", "enemy_a", "attack", "hit")

    assert beat["results"] == []
    assert "results" in cb.BEAT_FIELDS
