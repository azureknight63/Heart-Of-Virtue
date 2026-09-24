"""The level-up resume must not restart a fight that is already over.

While attribute points are unspent, a fight a move or event would start is
stashed on ``player._combat_deferred_enemies`` and ``get_combat_status``
resumes it once the last point is spent. Clicking an enemy
(``start_combat``) does not defer, so the player can start and win that
very fight while the stash still names it. Spending the points afterwards
resumed the stash: a fight whose only enemy was a 0-HP corpse, with
``combat_active`` stuck true and every move refused ("Cannot move while in
combat"). The second live balance run for #655 hit it at the Mineral Pools
(2,5) Slime (``docs/qa/2026-09-24-balance-live-run-2.md``).
"""

import pytest

from src.api.services.game_service import GameService
from src.combatant import wire_handle
from src.npc import Slime
from tests._gs_fixtures import live_world


@pytest.fixture
def game_service():
    return GameService()


@pytest.fixture
def world():
    """A real world with Jean and one aggro Slime on the starting tile."""
    player, game_map = live_world(coords=((0, 0), (0, 1)))
    slime = Slime()
    slime.current_room = game_map[(0, 0)]
    game_map[(0, 0)].npcs_here.append(slime)
    return player, game_map, slime


def _stash_with_points_pending(game_service, player, enemies):
    player.pending_attribute_points = 1
    assert game_service._defer_combat_for_level_up(player, enemies)


def _win(game_service, player, slime):
    """Start the fight by clicking the Slime and end it with a real beat."""
    started = game_service.start_combat(player, wire_handle(slime))
    assert player.in_combat, started
    slime.hp = 0  # the killing blow; the beat below settles the death
    wait = next(m for m in player.known_moves if m.name == "Wait")
    game_service.execute_move(player, "move", str(player.known_moves.index(wait)))
    game_service.execute_move(player, "number", "3")  # the Wait prompt's minimum
    assert not player.in_combat, "the fight should have ended in victory"


def test_a_fight_won_while_stashed_is_not_resumed(game_service, world):
    player, _map, slime = world
    _stash_with_points_pending(game_service, player, [slime])
    _win(game_service, player, slime)

    player.pending_attribute_points = 0
    status = game_service.get_combat_status(player)

    assert not player.in_combat, "a won fight came back with a corpse in it"
    assert status["combat_active"] is False, status
    assert player._combat_deferred_enemies is None


def test_a_dead_stashed_enemy_is_not_resumed(game_service, world):
    player, game_map, slime = world
    _stash_with_points_pending(game_service, player, [slime])
    slime.hp = 0
    game_map[(0, 0)].npcs_here.remove(slime)

    player.pending_attribute_points = 0
    game_service.get_combat_status(player)

    assert not player.in_combat
    assert player._combat_deferred_enemies is None


def test_an_enemy_left_on_another_tile_is_not_resumed(game_service, world):
    """The stash is the fight on the tile Jean was on; walking away ends it."""
    player, game_map, slime = world
    _stash_with_points_pending(game_service, player, [slime])
    player.location_x, player.location_y = 0, 1
    player.current_room = game_map[(0, 1)]

    player.pending_attribute_points = 0
    game_service.get_combat_status(player)

    assert not player.in_combat
    assert player._combat_deferred_enemies is None


def test_a_living_stashed_enemy_still_resumes(game_service, world):
    """The control: the deferral's whole point is that this fight happens."""
    player, _map, slime = world
    _stash_with_points_pending(game_service, player, [slime])

    player.pending_attribute_points = 0
    status = game_service.get_combat_status(player)

    assert player.in_combat, status
    assert player.combat_list == [slime]
    assert player._combat_deferred_enemies is None
