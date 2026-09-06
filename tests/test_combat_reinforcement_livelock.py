"""The two guards that stop a mid-beat reinforcement spawn from looping forever.

``functions.add_enemies_to_combat`` calls
``ApiCombatAdapter.initialize_combat(reinit=True)``. When it is reached from
*inside* a beat -- an enemy move or a combat effect that spawns reinforcements
while the player's move is mid-``advance()`` -- that reinit re-enters the very
loop that is already running. Two guards stop it:

1. ``initialize_combat``'s ``if reinit and self._executing_move: return`` --
   without it the reinit falls through to
   ``_execute_move(player.current_move, resume=True)``, starting a *second*
   beat loop on the same move; that loop gives the summoning combatant another
   turn, which summons again. Unbounded recursion that pins the request thread
   and grows the roster without limit.
2. ``_reset_idle_move_stages`` sparing ``current_move`` -- without it the
   reinit rewinds the in-flight move to ``current_stage = 0`` while
   ``Move.advance``'s stage loop is walking it, and that loop only terminates
   once the counter passes 3. It never does.

Neither guard had a test in the default suite: ``grep -n
"_executing_move\\|_reset_idle_move_stages" tests/`` returned nothing. The only
coverage was ``tests/api/test_combat_midbattle_api.py``, which ``pytest.ini``
excludes from the default run -- so a refactor could re-arm either infinite
loop against a fully green suite.

Both failure modes hang rather than raise, so every test here runs the adapter
on a worker thread with a hard deadline: a livelock has to come back as a
FAILURE, never as a suite that never finishes. (The worker is left daemonized
and abandoned on timeout -- there is no safe way to kill a spinning thread, and
the process exits at the end of the run.)
"""

import threading

import pytest

import src.positions as positions
import src.functions as functions
from src.api.combat_adapter import ApiCombatAdapter
from src.moves._base import Move
from src.npc import CaveBat
from src.player import Player

#: Generous next to the sub-second real runtime, tight next to "forever".
_DEADLINE_SECONDS = 20


class SummoningMove(Move):
    """A player move that spawns one wave of reinforcements from a stage.

    This is the shape of the real defect: the spawn happens while
    ``Move.advance`` is walking this move's stages, i.e. with
    ``player.current_move is self`` and ``_execute_move`` already on the stack.
    """

    display_name = "Summoning Move"

    def __init__(self, user):
        super().__init__(
            name="Summoning Move",
            description="Spawns reinforcements mid-beat.",
            xp_gain=0,
            current_stage=0,
            beats_left=0,
            stage_announce=["", "", "", ""],
            target=user,
            user=user,
            stage_beat=[0, 0, 0, 0],
            targeted=False,
            mvrange=(0, 9999),
            instant=False,
            category="Test",
        )
        self.spawns = 0

    def viable(self):
        return True

    #: Bounds the roster (and this process's memory) when a guard is disarmed
    #: deliberately to prove these tests fail without it. Well above the one
    #: spawn a correct run produces, so it never masks the real assertion.
    _SPAWN_CAP = 25

    def process_stage(self, user):
        # Unconditional at stage 1, exactly like a real summoning combatant:
        # a self-limiting spawn would hide the recursion, because the SECOND
        # pass through this stage is the symptom.
        if self.current_stage == 1 and self.spawns < self._SPAWN_CAP:
            self.spawns += 1
            functions.add_enemies_to_combat(
                user, [CaveBat()], announcement="Reinforcements arrive!"
            )
        return super().process_stage(user)


def _player_in_combat():
    player = Player()
    player.in_combat = True
    player.combat_list = [CaveBat()]
    player.combat_list_allies = [player]
    player.combat_proximity = {}
    player.combat_log = []
    player.combat_exp = {}
    player.combat_events = []
    player.combat_beat = 1
    for enemy in player.combat_list:
        enemy.in_combat = True
        enemy.player_ref = player
        enemy.combat_list = player.combat_list_allies
        enemy.combat_list_allies = player.combat_list
        enemy.combat_proximity = {player: 10}
        player.combat_proximity[enemy] = 10
    return player


@pytest.fixture
def adapter(monkeypatch):
    """A real adapter over a real player, mid-fight, with one enemy."""
    monkeypatch.setattr(positions, "initialize_combat_positions", lambda **kw: None)
    player = _player_in_combat()
    adapter = ApiCombatAdapter(player)
    player._combat_adapter = adapter
    return adapter


def _arm(player):
    """Select a SummoningMove the way _handle_move_selection would.

    ``Move.advance`` only walks a move that is the user's ``current_move``, so
    a test that merely constructs one never reaches ``process_stage``.
    """
    move = SummoningMove(player)
    move.target = player
    player.known_moves = list(getattr(player, "known_moves", [])) + [move]
    player.current_move = move
    return move


def _run_with_deadline(fn):
    """Run ``fn`` on a worker thread; fail (don't hang) if it overruns.

    Returns whatever ``fn`` returned. A livelock inside ``fn`` shows up as an
    explicit failure naming the guard that is missing.
    """
    box = {}

    def target():
        try:
            box["value"] = fn()
        except BaseException as exc:  # RecursionError included
            box["error"] = exc

    worker = threading.Thread(target=target, daemon=True)
    worker.start()
    worker.join(_DEADLINE_SECONDS)
    if worker.is_alive():
        pytest.fail(
            f"the adapter did not return within {_DEADLINE_SECONDS}s -- a "
            "mid-beat reinforcement spawn is looping. Check "
            "initialize_combat's `reinit and self._executing_move` guard and "
            "_reset_idle_move_stages sparing current_move."
        )
    if "error" in box:
        raise box["error"]
    return box["value"]


def test_a_mid_beat_reinforcement_spawn_terminates(adapter):
    """The whole point: ``_execute_move`` returns, and returns a state."""
    player = adapter.player
    move = _arm(player)

    result = _run_with_deadline(lambda: adapter._execute_move(move))

    assert isinstance(result, dict)
    assert move.spawns == 1


def test_the_spawn_adds_exactly_one_wave(adapter):
    """Termination alone is not enough -- the runaway also grew the roster.

    The recursive form summoned again on every re-entry, so the enemy list was
    unbounded even in the runs that happened to unwind. Exactly one CaveBat
    joins the one already fighting.
    """
    player = adapter.player
    before = len(player.combat_list)
    move = _arm(player)

    _run_with_deadline(lambda: adapter._execute_move(move))

    # Enemies may die during the beat, so count arrivals rather than survivors.
    assert move.spawns == 1
    assert len(player.combat_list) <= before + 1


def test_the_in_flight_move_is_not_rewound_by_the_reinit(adapter):
    """Guard 2, isolated from the beat loop.

    ``_reset_idle_move_stages`` must spare ``current_move``: rewinding a move
    that ``Move.advance`` is mid-walk traps that stage loop, which exits only
    once the stage counter passes 3.
    """
    player = adapter.player
    move = SummoningMove(player)
    move.current_stage = 2
    move.beats_left = 3
    player.current_move = move
    player.known_moves = [move]

    ApiCombatAdapter._reset_idle_move_stages(player)

    assert move.current_stage == 2, "the in-flight move was rewound"
    assert move.beats_left == 3


def test_idle_moves_are_still_rewound(adapter):
    """...and the sparing is surgical: everything else still resets.

    Negative control for the test above -- without this, `spare everything`
    would pass it.
    """
    player = adapter.player
    active = SummoningMove(player)
    idle = SummoningMove(player)
    idle.current_stage = 3
    idle.beats_left = 7
    player.current_move = active
    player.known_moves = [active, idle]

    ApiCombatAdapter._reset_idle_move_stages(player)

    assert idle.current_stage == 0
    assert idle.beats_left == 0


def test_a_reinit_from_inside_a_beat_does_not_start_a_second_loop(adapter):
    """Guard 1, isolated: while ``_executing_move`` is set, a reinit returns
    state instead of resuming ``current_move``.

    Resuming is what re-entered ``_execute_move`` on a move already being
    advanced -- the recursion itself.
    """
    player = adapter.player
    move = SummoningMove(player)
    player.current_move = move
    player.known_moves = [move]
    adapter._executing_move = True

    calls = []
    adapter._execute_move = lambda *a, **kw: calls.append((a, kw))

    adapter.initialize_combat([CaveBat()], reinit=True)

    assert calls == [], "the reinit resumed the in-flight move a second time"
