"""UI-gated call paths: the server enforces what the client only hides.

The React client never offers these actions mid-fight (the INTERACT, SKILLS
and shop panels are exploration-only; the inventory shows only Consumables and
the Swap Weapon tab in combat; every combat control waits on `isMyTurn`). A
direct API call used to do them anyway -- a free full heal from a Healing
Spring mid-fight, an armour swap, shopping. Maintainer rule (2026-09-24): if
the player cannot do it through the UI, the server does not allow it either.
"""

import pytest

from src import items
from src.api.services.game_service import (
    GameService,
    _NOT_DURING_COMBAT_MESSAGE,
    _NOT_YOUR_TURN_MESSAGE,
)
from src.combatant import wire_handle
from src.events import LootEvent
from src.narration import capture_narration
from src.objects import Container, HealingSpring
from tests._gs_fixtures import live_world
from tests.test_swap_weapon import _combat


@pytest.fixture
def fighting():
    """A real Jean on a real tile, mid-fight."""
    player, game_map = live_world()
    player.in_combat = True
    return player, game_map[(0, 0)]


class TestInteractIsRefusedMidFight:
    def test_a_healing_spring_cannot_be_drunk_mid_fight(self, fighting):
        player, tile = fighting
        spring = HealingSpring(player, tile)
        tile.objects_here.append(spring)
        player.hp = 1

        result = GameService().interact_with_target(player, wire_handle(spring), "drink")

        assert result == {"success": False, "message": _NOT_DURING_COMBAT_MESSAGE}
        assert player.hp == 1

    def test_a_container_cannot_be_looted_mid_fight(self, fighting):
        player, tile = fighting
        chest = Container(player=player, tile=tile, name="Chest", inventory=[items.Restorative()])
        tile.objects_here.append(chest)

        result = GameService().interact_with_target(player, wire_handle(chest), "take_all")

        assert result == {"success": False, "message": _NOT_DURING_COMBAT_MESSAGE}
        assert not any(isinstance(i, items.Restorative) for i in player.inventory)

    def test_the_same_interaction_still_works_out_of_combat(self, fighting):
        """Positive control: the guard is about combat, not about springs."""
        player, tile = fighting
        player.in_combat = False
        spring = HealingSpring(player, tile)
        tile.objects_here.append(spring)
        player.hp = 1

        result = GameService().interact_with_target(player, wire_handle(spring), "drink")

        assert result.get("success") is not False
        assert player.hp == player.maxhp


def test_starting_a_second_fight_mid_fight_is_refused(fighting):
    player, _tile = fighting
    result = GameService().start_combat(player, "anything")
    assert result == {"error": _NOT_DURING_COMBAT_MESSAGE}


class TestEquipmentIsFrozenMidFight:
    def test_armour_cannot_be_equipped_mid_fight(self, fighting):
        player, _tile = fighting
        jerkin = items.PaddedJerkin()
        player.inventory.append(jerkin)

        result = GameService().equip_item(player, jerkin)

        assert result == {"error": _NOT_DURING_COMBAT_MESSAGE}
        assert jerkin.isequipped is False

    def test_armour_cannot_be_unequipped_mid_fight(self, fighting):
        player, _tile = fighting
        jerkin = items.PaddedJerkin()
        player.inventory.append(jerkin)
        player.in_combat = False
        with capture_narration():
            GameService().equip_item(player, jerkin)
        assert jerkin.isequipped is True
        player.in_combat = True

        result = GameService().unequip_item(player, jerkin)

        assert result == {"error": _NOT_DURING_COMBAT_MESSAGE}
        assert jerkin.isequipped is True


@pytest.mark.parametrize("call", [
    lambda gs, p: gs.get_shop_state(p, "merchant"),
    lambda gs, p: gs.shop_buy(p, "merchant", "item", 1),
    lambda gs, p: gs.shop_sell(p, "merchant", "item", 1),
    lambda gs, p: gs.shop_buyback(p, "merchant", "item"),
    lambda gs, p: gs.learn_skill(p, "Basic", "Anything"),
    lambda gs, p: gs.npc_chat_open(p, "someone"),
    lambda gs, p: gs.npc_chat_respond(p, "someone", "hello"),
], ids=["shop_state", "shop_buy", "shop_sell", "shop_buyback", "learn_skill",
        "npc_chat_open", "npc_chat_respond"])
def test_exploration_only_routes_refuse_mid_fight(fighting, call):
    player, _tile = fighting
    result = call(GameService(), player)
    assert result.get("success") is False
    assert result.get("error") == _NOT_DURING_COMBAT_MESSAGE


def test_search_is_refused_mid_fight(fighting):
    player, _tile = fighting
    result = GameService().search(player)
    assert result == {"success": False, "message": _NOT_DURING_COMBAT_MESSAGE}


def test_a_queued_loot_dialog_cannot_be_answered_mid_fight(fighting):
    player, tile = fighting
    chest = Container(player=player, tile=tile, name="Chest", inventory=[items.Restorative()])
    event = LootEvent("Loot", player=player, tile=tile, container=chest)
    session = {"pending_events": {"e1": {"event": event, "event_data": {"needs_input": True}}}}

    result = GameService().process_event_input(player, "e1", "0", session_data=session)

    assert result == {"success": False, "error": _NOT_DURING_COMBAT_MESSAGE}
    assert not any(isinstance(i, items.Restorative) for i in player.inventory)


class TestCombatTurnGates:
    def test_fleeing_while_a_move_winds_up_is_refused(self):
        player, _game_map = live_world()
        adapter, enemy = _combat(player)
        player._combat_adapter = adapter
        enemy.combat_proximity = {player: 100}
        winding = next(m for m in player.known_moves if m.name == "Rest")
        # Long enough a windup to be abortable (ABORTABLE_MIN_PREP_BEATS).
        from src.api.combat_adapter import ABORTABLE_MIN_PREP_BEATS
        winding.stage_beat = [ABORTABLE_MIN_PREP_BEATS, 1, 1, 0]
        winding.current_stage = 0
        winding.beats_left = 3
        player.current_move = winding

        result = GameService().flee_combat(player)

        assert result.get("requires_abort") is True
        assert player.in_combat is True

    def test_an_item_cannot_be_used_off_turn(self):
        player, _game_map = live_world()
        adapter, _enemy = _combat(player)
        player._combat_adapter = adapter
        potion = items.Restorative()
        player.inventory.append(potion)
        player.hp = 1
        adapter.awaiting_input = False

        result = GameService().use_item(player, potion)

        assert result == {"error": _NOT_YOUR_TURN_MESSAGE}
        assert player.hp == 1


def test_a_floor_potion_heals_once_then_is_gone():
    """Drinking a potion lying on the floor (#665 made the verb dispatch) must
    consume it: it used to heal, fail to remove itself from an inventory it was
    never in, and stay on the floor to be drunk again forever."""
    player, game_map = live_world()
    tile = game_map[(0, 0)]
    potion = items.Restorative()
    tile.items_here.append(potion)
    handle = wire_handle(potion)
    player.hp = 1

    first = GameService().interact_with_target(player, handle, "drink")
    healed = player.hp
    player.hp = 1
    GameService().interact_with_target(player, handle, "drink")

    assert first.get("success") is not False
    assert healed > 1
    assert player.hp == 1, "the same floor potion healed twice"
    assert all(i is not potion for i in tile.items_here)


def test_a_potion_in_an_open_container_heals_once_then_is_gone():
    """The same defect's twin: a consumable drunk straight out of a chest."""
    player, game_map = live_world()
    tile = game_map[(0, 0)]
    potion = items.Restorative()
    chest = Container(player=player, tile=tile, name="Chest", inventory=[potion])
    chest.state = "opened"
    tile.objects_here.append(chest)
    handle = wire_handle(potion)
    player.hp = 1

    first = GameService().interact_with_target(player, handle, "drink")
    healed = player.hp
    player.hp = 1
    GameService().interact_with_target(player, handle, "drink")

    assert first.get("success") is not False
    assert healed > 1
    assert player.hp == 1, "the same chest potion healed twice"
    assert all(i is not potion for i in chest.inventory)


def test_reading_a_floor_book_leaves_it_on_the_floor():
    """Only consumables are moved into the pack to be used: a Book's READ
    resolves to ``use`` too, and reading must not pick the book up."""
    player, game_map = live_world()
    tile = game_map[(0, 0)]
    book = items.Book(name="Ledger", text="Nothing of note.")
    tile.items_here.append(book)

    GameService().interact_with_target(player, wire_handle(book), "read")

    assert any(i is book for i in tile.items_here)
    assert all(i is not book for i in player.inventory)


def test_a_floor_potion_too_heavy_to_lift_never_spends_one_from_the_pack():
    """If the unit cannot be picked up, nothing is drunk -- least of all the
    same kind of potion Jean already carries."""
    player, game_map = live_world()
    tile = game_map[(0, 0)]
    carried = items.Restorative()
    player.inventory.append(carried)
    floor = items.Restorative()
    tile.items_here.append(floor)
    player.weight_tolerance = 0  # nothing more can be carried
    player.hp = 1

    GameService().interact_with_target(player, wire_handle(floor), "drink")

    assert player.hp == 1
    assert carried in player.inventory and carried.count == 1
    assert any(i is floor for i in tile.items_here)
