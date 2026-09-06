"""The instant-move stage loop is bounded, like the multi-beat loop beside it.

``_execute_move_inner`` runs an instant move's stages inside one request:

    while self.player.current_move == move:
        move.advance(self.player)
        if self.player.current_move is None:
            break

The multi-beat loop directly below it has carried ``max_beats = 20`` since it
was written. This one had no bound at all, so a move whose ``advance()`` fails
to release ``current_move`` parks the request thread forever — and now that the
thread holds ``_beat_lock`` for the whole call, it parks every later request on
that adapter behind it too. That is the same failure mode as the two infinite
loops this branch fixed, one ``while`` away from them.

The bound is a bug backstop, not a feature: tripping it means a broken move, so
it logs at ERROR and abandons the move through ``_detach_current_move`` (the
helper that pairs the ``current_move`` clear with the animation-channel
discard) rather than leaving it attached for the next status poll to resume
into the same spin.
"""

import logging

import pytest

from src.api.combat_adapter import MAX_INSTANT_STAGES, ApiCombatAdapter
from src.moves import Check
from src.npc import Slime
from tests._combat_fixtures import engage, make_npc, make_player


class NeverFinishes(Check):
    """An instant move whose ``advance()`` never releases ``current_move``.

    Subclasses a REAL instant move (``Check``) so everything the adapter does
    around the loop — the cast capture, the animation build, the pending-move
    bookkeeping — runs for real; only the stage machine is broken.
    """

    def __init__(self, player):
        super().__init__(player)
        self.name = "Never Finishes"
        self.advances = 0

    def advance(self, user):
        self.advances += 1
        user.current_move = self


@pytest.fixture
def combat():
    player = make_player()
    slime = make_npc(Slime, name="Test Slime", hp=20, maxhp=20)
    engage(player, [slime])
    adapter = ApiCombatAdapter(player)
    adapter.initialize_combat([slime])
    player._combat_adapter = adapter
    adapter._stream_combat_result = lambda *a, **k: None
    return adapter, player


def test_a_move_that_never_releases_current_move_does_not_spin_forever(
    combat, caplog
):
    adapter, player = combat
    move = NeverFinishes(player)
    player.current_move = move

    with caplog.at_level(logging.ERROR, logger="src.api.combat_adapter"):
        adapter._execute_move(move)

    assert move.advances == MAX_INSTANT_STAGES, (
        f"the instant loop ran {move.advances} times against a bound of "
        f"{MAX_INSTANT_STAGES}"
    )
    assert any(
        "Never Finishes" in record.getMessage() for record in caplog.records
    ), "tripping the bound must be logged, not swallowed"


def test_the_abandoned_move_is_detached_rather_than_left_to_be_resumed(combat):
    """Leaving it attached hands the next status poll the same spin.

    ``get_combat_status``'s resume branch calls ``_execute_move(current_move)``,
    so a bounded loop that left ``current_move`` set would merely turn one
    hung request into an endless series of them.
    """
    adapter, player = combat
    move = NeverFinishes(player)
    player.current_move = move

    adapter._execute_move(move)

    assert player.current_move is None
    assert not hasattr(player, "_pending_animation"), (
        "the abandoned wind-up's animation channel was left armed"
    )


def test_a_well_behaved_instant_move_is_untouched(combat):
    """The bound must not clip a real instant move.

    ``Check`` resolves its stages in a handful of advances, well inside the
    ceiling, and must finish normally with nothing logged against it.
    """
    adapter, player = combat
    move = Check(player)
    player.current_move = move

    result = adapter._execute_move(move)

    assert player.current_move is None
    assert "error" not in result
