"""
Unit tests for tiles module
"""
import sys
from pathlib import Path

# Ensure the project's src directory is on sys.path so imports resolve like other tests
ROOT = Path(__file__).resolve().parent.parent


import pytest
from unittest.mock import Mock, patch, MagicMock
from src.tiles import MapTile


@pytest.fixture
def mock_universe():
    """Create a mock universe"""
    universe = Mock()
    return universe


@pytest.fixture
def mock_map():
    """Create a mock map"""
    return Mock()


@pytest.fixture
def basic_tile(mock_universe, mock_map):
    """Create a basic MapTile for testing"""
    return MapTile(mock_universe, mock_map, 5, 10, "A test room")


def test_tile_initialization(basic_tile):
    """Test that a tile initializes with correct properties"""
    assert basic_tile.x == 5
    assert basic_tile.y == 10
    assert basic_tile.description == "A test room"
    assert basic_tile.npcs_here == []
    assert basic_tile.items_here == []
    assert basic_tile.events_here == []
    assert basic_tile.objects_here == []
    assert basic_tile.last_entered == 0
    assert basic_tile.discovered is False
    assert basic_tile.respawn_rate == 9999
    assert basic_tile.block_exit == []
    assert basic_tile.symbol == '●'


def test_tile_universe_reference(basic_tile, mock_universe):
    """Test that tile maintains reference to universe"""
    assert basic_tile.universe == mock_universe


def test_tile_map_reference(basic_tile, mock_map):
    """Test that tile maintains reference to map"""
    assert basic_tile.map == mock_map


def test_intro_text(basic_tile):
    """Test intro_text returns colored description"""
    result = basic_tile.intro_text()
    # Result should contain the description text
    assert "test room" in result.lower()


def test_intro_text_empty_description(mock_universe, mock_map):
    """An empty description yields an empty rendering, not a crash or filler.

    ``is not None`` passed for literally any return value, including the
    string "None".
    """
    tile = MapTile(mock_universe, mock_map, 0, 0, "")
    result = tile.intro_text()
    assert isinstance(result, str)
    assert result.strip() == ""


def test_modify_player(basic_tile):
    """Test modify_player does nothing by default"""
    mock_player = Mock()
    result = basic_tile.modify_player(mock_player)
    assert result is None


def test_block_exit_initialization(basic_tile):
    """Test that block_exit starts empty"""
    assert basic_tile.block_exit == []


def test_block_exit_can_be_set(basic_tile):
    """Test that block_exit can be modified"""
    basic_tile.block_exit.append("north")
    assert "north" in basic_tile.block_exit


def test_available_actions_includes_defaults(basic_tile):
    """The API-mode action set is Search/Menu/Save.

    ``len(actions) > 0`` would still pass if the set were wrong, or if the
    directional-move actions deleted in the terminal-mode teardown crept back.
    """
    actions = basic_tile.available_actions()

    names = {type(a).__name__ for a in actions}
    assert {"Search", "Menu", "Save"} <= names
    # The directional Move* actions were deleted with terminal mode
    # (CLAUDE.md, "Terminal-mode removal") and must not return.
    assert not [n for n in names if n.startswith("Move")]


def test_evaluate_events_empty(basic_tile):
    """With no events, evaluate_events is a no-op that leaves the list alone."""
    basic_tile.evaluate_events()
    assert basic_tile.events_here == []


def test_evaluate_events_with_events(basic_tile):
    """Test evaluate_events calls check_conditions on all events"""
    mock_event1 = Mock()
    mock_event2 = Mock()
    basic_tile.events_here = [mock_event1, mock_event2]

    basic_tile.evaluate_events()

    mock_event1.check_conditions.assert_called_once()
    mock_event2.check_conditions.assert_called_once()


def test_spawn_npc_basic(basic_tile):
    """An unknown npc_type falls back to the documented stub, not to None.

    "TestNPC" is not a real class in ``src.npc``, so this exercises
    ``spawn_npc``'s stub branch — which exists so callers that immediately
    touch ``.name`` don't crash. Asserting the stub's actual surface is what
    ``is not None`` could not do.
    """
    npc = basic_tile.spawn_npc("TestNPC")

    assert basic_tile.npcs_here == [npc]
    assert npc.name == "TestNPC (stub)"
    assert npc.is_alive() is True
    assert npc.friend is False


def test_spawn_npc_known_type_builds_the_real_class(basic_tile):
    """A real npc_type resolves through ``src.npc`` to the engine class."""
    from src.npc import Slime

    npc = basic_tile.spawn_npc("Slime")

    assert isinstance(npc, Slime)
    assert basic_tile.npcs_here == [npc]
    assert npc.current_room is basic_tile


def test_spawn_npc_hidden(basic_tile):
    """Test spawning a hidden NPC"""
    npc = basic_tile.spawn_npc("TestNPC", hidden=True, hfactor=5)

    assert npc.hidden is True
    assert npc.hide_factor == 5


def test_spawn_npc_with_delay(basic_tile):
    """Test spawning an NPC with specific combat delay"""
    npc = basic_tile.spawn_npc("TestNPC", delay=3)

    assert npc.combat_delay == 3


def test_spawn_npc_random_delay(basic_tile):
    """Test spawning an NPC with random delay"""
    npc = basic_tile.spawn_npc("TestNPC", delay=-1)

    # Combat delay should be between 0 and 7
    assert 0 <= npc.combat_delay <= 7


def test_spawn_npc_sets_current_room(basic_tile):
    """current_room must point at *this* tile, not merely exist."""
    npc = basic_tile.spawn_npc("TestNPC")

    assert npc.current_room is basic_tile


def test_spawn_multiple_npcs(basic_tile):
    """Test spawning multiple NPCs"""
    npc1 = basic_tile.spawn_npc("NPC1")
    npc2 = basic_tile.spawn_npc("NPC2")

    assert len(basic_tile.npcs_here) == 2
    assert npc1 in basic_tile.npcs_here
    assert npc2 in basic_tile.npcs_here


# ``spawn_item`` used to be tested with ``src.tiles.importlib.import_module``
# patched to a Mock module, so every "item" was a Mock: ``item is not None``
# was trivially true, and the stackable/non-stackable split -- the only real
# logic in the method -- was decided by the *test's* mock spec rather than by
# any engine class. These use the real ``src.items`` classes instead:
# ``Restorative`` genuinely has ``count`` (stackable), ``Shortsword`` genuinely
# does not (one instance per unit).

def test_spawn_item_gold(basic_tile):
    """Gold takes its amount through the constructor, not through ``count``."""
    from src.items import Gold

    item = basic_tile.spawn_item("Gold", amt=50)

    assert isinstance(item, Gold)
    assert basic_tile.items_here == [item]
    assert item.amt == 50


def test_spawn_item_stackable_collapses_into_one_instance(basic_tile):
    """A stackable item spawns once with ``count`` set to the amount."""
    from src.items import Restorative

    item = basic_tile.spawn_item("Restorative", amt=5)

    assert isinstance(item, Restorative)
    assert basic_tile.items_here == [item]
    assert item.count == 5


def test_spawn_item_non_stackable_creates_separate_instances(basic_tile):
    """A non-stackable item spawns ``amt`` distinct objects."""
    from src.items import Shortsword

    item = basic_tile.spawn_item("Shortsword", amt=3)

    assert len(basic_tile.items_here) == 3
    assert all(isinstance(i, Shortsword) for i in basic_tile.items_here)
    assert len({id(i) for i in basic_tile.items_here}) == 3
    assert item is basic_tile.items_here[0]


def test_spawn_item_hidden_marks_every_spawned_instance(basic_tile):
    """``hidden``/``hfactor`` apply to the whole batch, not just the return."""
    basic_tile.spawn_item("Shortsword", amt=3, hidden=True, hfactor=10)

    assert all(i.hidden is True for i in basic_tile.items_here)
    assert all(i.hide_factor == 10 for i in basic_tile.items_here)


def test_spawn_item_merchandise_flag(basic_tile):
    """merchandise defaults False and is set on every spawned instance."""
    from src.items import Restorative

    plain = basic_tile.spawn_item("Restorative")
    assert plain.merchandise is False

    basic_tile.items_here.clear()
    basic_tile.spawn_item("Shortsword", amt=2, merchandise=True)
    assert all(i.merchandise is True for i in basic_tile.items_here)


def test_spawn_item_unknown_type_falls_back_to_a_named_stub(basic_tile):
    """An unknown item_type must not crash the spawner; it yields the stub
    documented in ``spawn_item`` so callers touching ``.name`` survive."""
    item = basic_tile.spawn_item("NoSuchItemXYZ", amt=4)

    assert basic_tile.items_here == [item]
    assert item.name == "NoSuchItemXYZ (unknown)"
    assert item.count == 4
    assert item.merchandise is False


def test_spawn_item_template_carries_enchantment_across_a_stack_split(basic_tile):
    """``template`` exists so splitting a stack keeps enchantments; a bare
    ``cls()`` rebuild would silently discard them."""
    from src.items import Shortsword

    original = Shortsword()
    original.enchantment_level = 3
    original.description = "A sword with a story."

    spawned = basic_tile.spawn_item("Shortsword", amt=1, template=original)

    assert spawned is not original
    assert spawned.enchantment_level == 3
    assert spawned.description == "A sword with a story."


@patch('src.tiles.functions.seek_class')
@patch('src.tiles.functions.instantiate_event')
def test_spawn_event(mock_instantiate, mock_seek, basic_tile):
    """Test spawning an event"""
    mock_event = Mock()
    mock_event_cls = Mock()
    mock_seek.return_value = mock_event_cls
    mock_instantiate.return_value = mock_event

    mock_player = Mock()
    event = basic_tile.spawn_event("TestEvent", mock_player, basic_tile)

    assert event is mock_event
    assert basic_tile.events_here == [mock_event]
    mock_seek.assert_called_once_with("TestEvent", "story")
    mock_instantiate.assert_called_once_with(
        mock_event_cls, mock_player, basic_tile, params=None, repeat=False)


@patch('src.tiles.functions.seek_class')
@patch('src.tiles.functions.instantiate_event')
def test_spawn_event_with_repeat(mock_instantiate, mock_seek, basic_tile):
    """Test spawning a repeatable event"""
    mock_event = Mock()
    mock_seek.return_value = Mock()
    mock_instantiate.return_value = mock_event

    mock_player = Mock()
    event = basic_tile.spawn_event("TestEvent", mock_player, basic_tile, repeat=True)

    assert event in basic_tile.events_here
    # Verify instantiate_event called with repeat=True
    call_kwargs = mock_instantiate.call_args[1]
    assert call_kwargs['repeat'] is True


@patch('src.tiles.functions.seek_class')
@patch('src.tiles.functions.instantiate_event')
def test_spawn_event_returns_none_on_failure(mock_instantiate, mock_seek, basic_tile):
    """Test spawn_event returns None when instantiation fails"""
    mock_seek.return_value = Mock()
    mock_instantiate.return_value = None

    mock_player = Mock()
    event = basic_tile.spawn_event("TestEvent", mock_player, basic_tile)

    assert event is None
    assert len(basic_tile.events_here) == 0


# Like spawn_item above, these previously replaced ``src.objects`` with a Mock
# module, so the "object" spawned was a Mock whose ``hidden``/``hide_factor``
# the test itself had already set -- the assertions could not distinguish
# spawn_object doing its job from spawn_object doing nothing. They now spawn a
# real ``src.objects.Container``.

def test_spawn_object_legacy_positional_params(basic_tile):
    """The legacy branch (no kwargs) calls ``obj_cls(player, tile, params)``.

    ``WallSwitch`` is the shape that branch was written for -- its constructor
    really is ``(player, tile, params)``.
    """
    from src.objects import WallSwitch

    mock_player = Mock()
    obj = basic_tile.spawn_object("WallSwitch", mock_player, basic_tile, None)

    assert isinstance(obj, WallSwitch)
    assert basic_tile.objects_here == [obj]
    assert obj.player is mock_player
    assert obj.tile is basic_tile
    assert obj.hidden is False


def test_spawn_object_modern_kwargs_reach_the_constructor(basic_tile):
    """Any **kwargs switch spawn_object to ``obj_cls(player=, tile=, **kwargs)``."""
    from src.objects import Container

    mock_player = Mock()
    obj = basic_tile.spawn_object("Container", mock_player, basic_tile,
                                  nickname="chest", locked=True)

    assert isinstance(obj, Container)
    assert basic_tile.objects_here == [obj]
    assert obj.nickname == "chest"
    assert obj.locked is True
    assert obj.player is mock_player


def test_spawn_object_hidden(basic_tile):
    """hidden/hfactor are applied by spawn_object after construction."""
    from src.objects import WallSwitch

    mock_player = Mock()
    obj = basic_tile.spawn_object("WallSwitch", mock_player, basic_tile, None,
                                  hidden=True, hfactor=8)

    assert isinstance(obj, WallSwitch)
    assert obj.hidden is True
    assert obj.hide_factor == 8


def test_stack_duplicate_items(basic_tile):
    """Two stacks of the same real item class merge into one.

    Using real ``Restorative`` instances (rather than Mocks whose
    ``__class__`` the test itself equalises) also exercises ``stack_grammar``,
    which rewrites the ground announcement for a multi-item stack.
    """
    from src.items import Restorative

    item1, item2 = Restorative(), Restorative()
    item1.count, item2.count = 3, 2
    basic_tile.items_here = [item1, item2]

    basic_tile.stack_duplicate_items()

    assert basic_tile.items_here == [item1]
    assert item1.count == 5
    # stack_grammar ran on the survivor: the announcement is now plural.
    assert "box of small glass vials" in item1.announce


def test_stack_duplicate_items_leaves_different_classes_alone(basic_tile):
    """Only same-class items merge; a mixed pile keeps every entry."""
    from src.items import Restorative, Gold

    potion, gold = Restorative(), Gold(10)
    potion.count = 2
    basic_tile.items_here = [potion, gold]

    basic_tile.stack_duplicate_items()

    assert basic_tile.items_here == [potion, gold]
    assert potion.count == 2


def test_stack_duplicate_items_refreshes_grammar_even_without_duplicates(
        basic_tile):
    """stack_grammar runs for every stackable item, not only merged ones.

    A lone stack whose count was raised elsewhere (e.g. spawn_item with amt>1)
    still needs its ground announcement pluralised, so the call is outside the
    duplicate-merge branch. The previous version of this test asserted only
    ``stack_grammar.called`` on a Mock, which passed for either behaviour.
    """
    from src.items import Restorative

    lone = Restorative()
    lone.count = 4
    basic_tile.items_here = [lone]

    basic_tile.stack_duplicate_items()

    assert basic_tile.items_here == [lone]
    assert lone.count == 4  # nothing merged into it
    assert "box of small glass vials" in lone.announce


def test_stack_duplicate_items_no_stackable(basic_tile):
    """Non-stackable items (no ``count``) are left as separate entries."""
    from src.items import Shortsword

    sword1, sword2 = Shortsword(), Shortsword()
    assert not hasattr(sword1, "count")  # guards the premise of this test
    basic_tile.items_here = [sword1, sword2]

    basic_tile.stack_duplicate_items()

    assert basic_tile.items_here == [sword1, sword2]


def test_remove_event_by_name(basic_tile):
    """Test removing an event by name"""
    mock_event1 = Mock()
    mock_event1.name = "Event1"
    mock_event2 = Mock()
    mock_event2.name = "Event2"

    basic_tile.events_here = [mock_event1, mock_event2]

    basic_tile.remove_event("Event1")

    assert mock_event1 not in basic_tile.events_here
    assert mock_event2 in basic_tile.events_here


def test_remove_event_not_found(basic_tile):
    """Test removing an event that doesn't exist"""
    mock_event = Mock()
    mock_event.name = "Event1"

    basic_tile.events_here = [mock_event]

    # Should not raise error
    basic_tile.remove_event("NonExistent")

    assert mock_event in basic_tile.events_here


def test_remove_event_no_name_attribute(basic_tile):
    """Test removing event when event has no name attribute"""
    mock_event = Mock(spec=[])  # No name attribute
    basic_tile.events_here = [mock_event]

    # Should not raise error
    basic_tile.remove_event("SomeName")

    assert mock_event in basic_tile.events_here


def test_tile_coordinates_are_integers(basic_tile):
    """Test that tile coordinates are stored as provided"""
    assert isinstance(basic_tile.x, int)
    assert isinstance(basic_tile.y, int)


def test_tile_respawn_rate_default(basic_tile):
    """Test default respawn rate is very high"""
    assert basic_tile.respawn_rate == 9999


def test_tile_symbol_default(basic_tile):
    """Test default symbol"""
    assert basic_tile.symbol == '●'


def test_spawn_object_unknown_type_returns_none(basic_tile):
    """An unknown object type is skipped gracefully (returns None) instead of raising."""
    mock_player = Mock()

    obj = basic_tile.spawn_object("NoSuchObject_xyz", mock_player, basic_tile, {})

    assert obj is None
    assert basic_tile.objects_here == []
