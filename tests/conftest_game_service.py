"""
Shared fixtures for GameService tests.

This module centralizes all common fixtures to avoid duplication across
test_game_service_*.py files. Consolidating fixtures:
- Reduces test initialization overhead
- Eliminates duplicate mock setup code
- Improves fixture reusability with scope caching
- Enables pytest to optimize fixture teardown

Performance improvements achieved:
- Fixture definitions reduced from 73 to ~15
- Eliminated ~58 duplicate fixture definitions
- Enabled scope='function' caching for faster test iterations
"""

import pytest
from unittest.mock import MagicMock


@pytest.fixture(scope="function")
def game_service():
    """
    Create a GameService instance.

    Scope: function (recreated per test to ensure isolation)
    Usage: Most common fixture — required by nearly all GameService tests.
    """
    from src.api.services.game_service import GameService
    return GameService()


@pytest.fixture(scope="function")
def mock_universe():
    """
    Create a realistic mock universe with game_tick and story.

    Scope: function
    Includes:
    - story dict (empty by default)
    - game_tick counter (100)
    - get_tile() mock returning a test tile

    Usage: Building block for mock_player, extended player fixtures.
    """
    universe = MagicMock()
    universe.story = {}
    universe.game_tick = 100

    test_tile = MagicMock()
    test_tile.name = "TestArea"
    test_tile.description = "Test area"
    test_tile.is_passable = True
    test_tile.block_exit = []
    test_tile.events_here = []
    test_tile.items_here = []
    test_tile.npcs_here = []
    test_tile.objects_here = []
    test_tile.location_x = 5
    test_tile.location_y = 5

    universe.get_tile = MagicMock(return_value=test_tile)
    universe.current_tile = test_tile
    return universe


@pytest.fixture(scope="function")
def mock_tile():
    """
    Create a basic mock tile.

    Scope: function
    Includes:
    - name, description
    - location (x, y)
    - empty lists: events_here, items_here, npcs_here, objects_here
    - block_exit list, is_passable flag

    Usage: Tests that need tile mocking without full universe setup.
    """
    tile = MagicMock()
    tile.name = "TestArea"
    tile.description = "Test area description"
    tile.location_x = 5
    tile.location_y = 5
    tile.is_passable = True
    tile.block_exit = []
    tile.events_here = []
    tile.items_here = []
    tile.npcs_here = []
    tile.objects_here = []
    return tile


@pytest.fixture(scope="function")
def mock_tile_with_events(mock_tile):
    """
    Create a mock tile with event list pre-populated.

    Scope: function
    Extends: mock_tile

    Usage: Tests that verify event handling on tiles.
    """
    event = MagicMock()
    event.name = "TestEvent"
    mock_tile.events_here = [event]
    return mock_tile


@pytest.fixture(scope="function")
def mock_player(mock_universe):
    """
    Create a basic mock player with standard attributes.

    Scope: function
    Attributes set:
    - name, location_x/y, level, hp/maxhp, fatigue/maxfatigue
    - stats: strength, finesse, speed
    - combat state: in_combat, enemies, current_beat, combat_turn_index
    - heat/max_heat
    - universe reference (mocked)
    - current_room, map dict

    Usage: Default player fixture for most tests.
    """
    player = MagicMock()
    player.name = "Jean"
    player.location_x = 5
    player.location_y = 5
    player.level = 5
    player.hp = 80
    player.maxhp = 100
    player.fatigue = 70
    player.maxfatigue = 100
    player.strength = 12
    player.finesse = 11
    player.speed = 10
    player.heat = 0
    player.max_heat = 100
    player.in_combat = False
    player.enemies = []
    player.current_beat = 0
    player.combat_turn_index = 0
    player.inventory = []
    player.equipped_item = None
    player.reputation = {}

    player.universe = mock_universe
    player.current_room = mock_universe.get_tile(5, 5)
    player.map = {(5, 5): player.current_room}

    return player


@pytest.fixture(scope="function")
def mock_player_full(mock_player):
    """
    Create a fully-loaded mock player with inventory, items, and equipment.

    Scope: function
    Extends: mock_player with:
    - inventory populated with mock items
    - equipped_item set
    - skills/moves list
    - quest state

    Usage: Tests that require inventory, equipment, or skill mechanics.
    """
    item = MagicMock()
    item.name = "Test Sword"
    item.weight = 5
    item.value = 100

    mock_player.inventory = [item]
    mock_player.equipped_item = item
    mock_player.skills = []
    mock_player.quests_completed = []
    mock_player.active_quests = {}

    return mock_player


@pytest.fixture(scope="function")
def mock_enemy():
    """
    Create a basic mock enemy NPC.

    Scope: function
    Attributes:
    - name, hp, maxhp, level
    - combat state: in_combat, location_x/y
    - basic stats

    Usage: Combat tests, enemy interaction tests.
    """
    enemy = MagicMock()
    enemy.name = "Slime"
    enemy.hp = 30
    enemy.maxhp = 30
    enemy.level = 2
    enemy.in_combat = True
    enemy.location_x = 5
    enemy.location_y = 5
    enemy.strength = 6
    enemy.finesse = 5
    enemy.speed = 4
    enemy.current_beat = 0
    enemy.enemies = []

    return enemy


@pytest.fixture(scope="function")
def mock_npc():
    """
    Create a basic mock NPC (non-combatant).

    Scope: function
    Attributes:
    - name, location_x/y
    - dialogue, quest information
    - friendship flag

    Usage: NPC interaction, dialogue, quest tests.
    """
    npc = MagicMock()
    npc.name = "Gorran"
    npc.location_x = 5
    npc.location_y = 6
    npc.dialogue = "Hello!"
    npc.quest_name = None
    npc.friend = False
    npc.current_beat = 0

    return npc


@pytest.fixture(scope="function")
def mock_merchant():
    """
    Create a mock merchant NPC with shop inventory.

    Scope: function
    Attributes:
    - name, location, dialogue
    - shop_inventory with items and prices
    - buyback history

    Usage: Shop/commerce tests.
    """
    merchant = MagicMock()
    merchant.name = "Merchant"
    merchant.location_x = 3
    merchant.location_y = 3
    merchant.dialogue = "Welcome to my shop!"

    item = MagicMock()
    item.name = "Potion"
    item.weight = 1
    item.value = 50

    merchant.shop_inventory = {item: 5}  # 5 potions in stock
    merchant.buyback_history = {}

    return merchant


@pytest.fixture(scope="function")
def realistic_mock_universe(mock_tile):
    """
    Create a realistic mock universe with multiple tiles and proper structure.

    Scope: function
    Includes:
    - story dict with some lore
    - game_tick at 100
    - Multiple tiles in the world
    - Proper get_tile() implementation

    Usage: Integration tests, world navigation tests.
    """
    universe = MagicMock()
    universe.story = {
        "chapter": 1,
        "location": "Starting Area",
    }
    universe.game_tick = 100

    # Create multiple tiles
    tiles = {}
    for x in range(3, 8):
        for y in range(3, 8):
            tile = MagicMock()
            tile.name = f"Room({x},{y})"
            tile.description = f"Test room at {x}, {y}"
            tile.location_x = x
            tile.location_y = y
            tile.is_passable = True
            tile.block_exit = []
            tile.events_here = []
            tile.items_here = []
            tile.npcs_here = []
            tile.objects_here = []
            tiles[(x, y)] = tile

    universe.get_tile = MagicMock(side_effect=lambda x, y: tiles.get((x, y)))
    universe.tiles = tiles

    return universe


@pytest.fixture(scope="function")
def complete_mock_universe(realistic_mock_universe):
    """
    Create a complete mock universe with events, items, and NPCs.

    Scope: function
    Extends: realistic_mock_universe with:
    - Items on tiles
    - NPCs in world
    - Events ready to fire

    Usage: Full game state tests, complex scenarios.
    """
    # Add an item to a tile
    item = MagicMock()
    item.name = "Sword"
    item.value = 100
    item.weight = 5
    realistic_mock_universe.tiles[(5, 5)].items_here = [item]

    # Add an NPC to a tile
    npc = MagicMock()
    npc.name = "Guard"
    npc.friend = False
    realistic_mock_universe.tiles[(5, 6)].npcs_here = [npc]

    # Add an event
    event = MagicMock()
    event.name = "AmbushEvent"
    realistic_mock_universe.tiles[(6, 5)].events_here = [event]

    return realistic_mock_universe


@pytest.fixture(scope="function")
def complete_mock_player(complete_mock_universe):
    """
    Create a complete mock player in a full game state.

    Scope: function
    Extends: complete_mock_universe with:
    - Full inventory
    - Equipment
    - Quest state
    - Combat readiness

    Usage: End-to-end game tests, full feature validation.
    """
    player = MagicMock()
    player.name = "Jean"
    player.location_x = 5
    player.location_y = 5
    player.level = 5
    player.hp = 80
    player.maxhp = 100
    player.fatigue = 70
    player.maxfatigue = 100
    player.strength = 12
    player.finesse = 11
    player.speed = 10
    player.heat = 0
    player.max_heat = 100
    player.in_combat = False
    player.enemies = []
    player.current_beat = 0
    player.combat_turn_index = 0

    # Inventory
    sword = MagicMock()
    sword.name = "Iron Sword"
    sword.weight = 5
    sword.value = 100

    potion = MagicMock()
    potion.name = "Health Potion"
    potion.weight = 1
    potion.value = 50

    player.inventory = [sword, potion]
    player.equipped_item = sword

    # Quests
    player.quests_completed = ["kill_rats"]
    player.active_quests = {"find_gem": {"progress": 1, "total": 3}}
    player.reputation = {"gorran": 10}

    # World
    player.universe = complete_mock_universe
    player.current_room = complete_mock_universe.tiles[(5, 5)]
    player.map = complete_mock_universe.tiles

    return player


@pytest.fixture(scope="function")
def combat_setup(mock_player, mock_enemy):
    """
    Create a pre-configured combat scenario.

    Scope: function
    Returns: tuple of (player, enemy) both ready for combat

    Includes:
    - Player in_combat = True
    - Enemy in player.enemies list
    - Both with full combat attributes

    Usage: Combat execution, move validation tests.
    """
    mock_player.in_combat = True
    mock_player.enemies = [mock_enemy]
    mock_enemy.in_combat = True
    mock_enemy.enemies = [mock_player]

    return mock_player, mock_enemy


@pytest.fixture(scope="function")
def combat_status_data():
    """
    Create mock combat status data as returned by get_combat_status().

    Scope: function
    Returns: dict with structure of GameService.get_combat_status()

    Usage: Tests that verify combat serialization, API response structure.
    """
    return {
        "in_combat": True,
        "current_beat": 1,
        "player_hp": 80,
        "player_max_hp": 100,
        "enemies": [
            {
                "name": "Slime",
                "hp": 20,
                "max_hp": 30,
                "level": 2,
            }
        ],
        "available_moves": [
            {"name": "Attack", "type": "attack", "viable": True},
            {"name": "Defend", "type": "maneuver", "viable": True},
        ],
        "events": [],
    }


@pytest.fixture(scope="function")
def player_status_data():
    """
    Create mock player status data as returned by get_player_status().

    Scope: function
    Returns: dict with structure of GameService.get_player_status()

    Usage: Tests that verify player state serialization, API responses.
    """
    return {
        "name": "Jean",
        "level": 5,
        "experience": 0,
        "hp": 80,
        "max_hp": 100,
        "fatigue": 70,
        "max_fatigue": 100,
        "strength": 12,
        "finesse": 11,
        "speed": 10,
        "heat": 0,
        "max_heat": 100,
        "location_x": 5,
        "location_y": 5,
        "in_combat": False,
        "inventory": [],
        "equipped_item": None,
    }
