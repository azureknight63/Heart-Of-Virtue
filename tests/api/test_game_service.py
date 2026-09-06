"""Tests for GameService."""

from unittest.mock import patch

import pytest
from src.api.services.game_service import GameService  # type: ignore


class _FakeResult:
    """Minimal stand-in for a libsql result set."""

    def __init__(self, rows=None, rows_affected=0):
        self.rows = rows or []
        self.rows_affected = rows_affected


class _FakeDb:
    """Records every (sql, params) pair and answers save_game's SELECTs.

    ``rows`` and ``rows_affected`` are settable so a test can distinguish the
    service's behaviour from the fake's. A fake that always answered
    ``rows_affected=0`` made ``delete_save`` untestable: ``return False`` would
    have satisfied the assertion just as well as the real ownership-scoped
    DELETE.
    """

    def __init__(self, manual_save_count=0, rows=None, rows_affected=0):
        self.calls = []
        self._manual_save_count = manual_save_count
        self._rows = rows or []
        self._rows_affected = rows_affected

    async def execute(self, sql, params=None):
        self.calls.append((" ".join(sql.split()), params))
        if "COUNT(*)" in sql:
            return _FakeResult([[self._manual_save_count]])
        return _FakeResult(self._rows, rows_affected=self._rows_affected)


class MockTile:
    """Mock tile for testing."""

    def __init__(self, name="Test Tile", x=0, y=0):
        self.name = name
        self.description = f"Description of {name}"
        # The engine's MapTile exposes its coordinates as ``x``/``y``
        # (src/tiles.py); ``location_x``/``location_y`` are the *player's*
        # attribute names and nothing reads them off a tile, so the mock does
        # not carry them.
        self.x = x
        self.y = y
        self.exits = {
            "north": (x, y + 1),
            "south": (x, y - 1),
            "east": (x + 1, y),
            "west": (x - 1, y),
        }
        self.items_here = []
        self.npcs_here = []
        self.objects_here = []
        self.events_here = []


class MockUniverse:
    """Mock universe for testing with testing-map layout."""

    def __init__(self):
        # Layout from testing-map.json:
        # (2, 2): exits=['south', 'east', 'southeast']
        # (2, 3): exits=['north', 'east', 'northeast']
        # (3, 2): exits=['south', 'west', 'southeast', 'southwest']
        # (3, 3): exits=['northwest', 'north', 'west', 'east']
        self.tiles = {
            (2, 2): MockTile("Test Room A", 2, 2),
            (2, 3): MockTile("Test Room B", 2, 3),
            (3, 2): MockTile("Test Room C", 3, 2),
            (3, 3): MockTile("Test Room D", 3, 3),
            (1, 3): MockTile("Test Room E", 1, 3),  # North of (2, 3)
        }
        # Update exits to match actual map structure
        self.tiles[(2, 2)].exits = {
            "south": (2, 3),
            "east": (3, 2),
            "southeast": (3, 3),
        }
        self.tiles[(2, 3)].exits = {
            "north": (2, 2),
            "east": (3, 3),
            "northeast": (3, 2),
        }
        self.tiles[(3, 2)].exits = {
            "south": (3, 3),
            "west": (2, 2),
            "southeast": (3, 3),
            "southwest": (2, 3),
        }
        self.tiles[(3, 3)].exits = {
            "northwest": (2, 2),
            "north": (2, 3),
            "west": (2, 3),
            "east": (3, 3),  # Self-loop for testing
        }

    def get_tile(self, x, y):
        """Get tile at coordinates."""
        return self.tiles.get((x, y))


class MockPlayer:
    """Mock player for testing."""

    def __init__(self, name="Hero", x=0, y=0):
        self.name = name
        self.username = None
        self.location_x = x
        self.location_y = y
        self.universe = None # Will be set in setup_method
        self.level = 1
        self.exp = 0
        self.hp = 50
        self.maxhp = 50
        self.exp_to_level = 100
        self.fatigue = 150
        self.maxfatigue = 150
        self.inventory_list = []
        # Engine names. ``weight``/``max_carrying_capacity`` are inventions:
        # InventorySerializer reads ``weight_tolerance`` (falling back to 100.0)
        # and get_player_stats reads ``weight_current``, so the old attributes
        # were dead and every weight assertion measured the fallback.
        self.weight_current = 0
        self.weight_tolerance = 500
        self.strength = 10
        self.finesse = 10
        self.speed = 10
        self.endurance = 10
        self.charisma = 10
        self.intelligence = 10
        self.faith = 10
        self.in_combat = False
        self.time_elapsed = 0
        self.current_room = None


class TestGameService:
    """Test GameService class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.universe = MockUniverse()
        self.service = GameService()
        # Position player at (2, 3) which has north and east exits
        self.player = MockPlayer(x=2, y=3)
        self.player.universe = self.universe
        self.player.current_room = self.universe.get_tile(2, 3)

    def test_get_current_room(self):
        """Test getting current room data."""
        result = self.service.get_current_room(self.player)

        assert result["x"] == 2
        assert result["y"] == 3
        assert result["name"] == "Test Room B"
        assert "description" in result
        assert "exits" in result
        assert len(result["exits"]) > 0

    def test_move_player_valid(self):
        """Test moving player in valid direction."""
        # Player starts at (2, 3). Valid directions: north, east, northeast
        result = self.service.move_player(self.player, "north")

        assert result["success"] is True
        assert result["new_position"]["x"] == 2
        assert result["new_position"]["y"] == 2
        assert self.player.location_x == 2
        assert self.player.location_y == 2

    def test_move_player_invalid_direction(self):
        """Test moving in invalid direction."""
        result = self.service.move_player(self.player, "invalid")

        assert "error" in result

    def test_move_player_blocked(self):
        """Test moving to blocked exit."""
        # Try to move to a tile that doesn't exist
        self.player.location_x = 1
        self.player.location_y = 0
        result = self.service.move_player(self.player, "south")

        assert "error" in result

    def test_get_tile(self):
        """Test getting tile data."""
        result = self.service.get_tile(self.player, 2, 3)

        assert result["x"] == 2
        assert result["y"] == 3
        assert result["name"] == "Test Room B"
        assert "items" in result
        assert "npcs" in result

    def test_get_tile_invalid(self):
        """Test getting non-existent tile."""
        result = self.service.get_tile(self.player, 99, 99)

        assert "error" in result

    def test_get_inventory(self):
        """Test getting player inventory."""
        result = self.service.get_inventory(self.player)

        assert result["items"] == []
        assert result["item_count"] == 0
        assert result["total_weight"] == 0
        # Read off the engine's `weight_tolerance`, not the serializer's 100.0
        # fallback -- this is the assertion that fails if the mock drifts back
        # to a name the engine has never had.
        assert result["weight_limit"] == self.player.weight_tolerance
        assert result["weight_percentage"] == 0.0

    def test_get_equipment(self):
        """Test getting player equipment."""
        result = self.service.get_equipment(self.player)

        assert "equipped" in result
        assert "total_stat_bonuses" in result
        assert isinstance(result["equipped"], dict)

    def test_get_player_status(self):
        """Test getting player status."""
        result = self.service.get_player_status(self.player)

        assert result["name"] == "Hero"
        assert result["level"] == 1
        assert "hp" in result
        assert "max_hp" in result

    def test_get_player_stats(self):
        """Test getting player stats."""
        result = self.service.get_player_stats(self.player)

        assert result["strength"] == 10
        assert result["finesse"] == 10
        assert result["speed"] == 10
        assert result["endurance"] == 10
        assert result["charisma"] == 10
        assert result["intelligence"] == 10
        assert result["faith"] == 10

    def test_get_combat_status(self):
        """Test getting combat status (not in combat)."""
        result = self.service.get_combat_status(self.player)

        assert result["combat_active"] is False
        assert "log" in result

    def test_trigger_tile_events_empty(self):
        """Test triggering events when no events exist."""
        tile = self.universe.get_tile(2, 3)
        result = self.service.trigger_tile_events(self.player, tile)

        assert result == []

    def test_trigger_tile_events_with_events(self):
        """Test triggering events on a tile with events."""
        tile = self.universe.get_tile(2, 3)

        # Create a mock event
        class MockEvent:
            def __init__(self):
                self.description = "Test event description"
                self.processed = False

            def process(self):
                self.processed = True

            def check_conditions(self):
                self.process()

        event = MockEvent()
        tile.events_here.append(event)

        result = self.service.trigger_tile_events(self.player, tile)

        assert len(result) == 1
        assert result[0]["type"] == "MockEvent"
        assert result[0]["description"] == "Test event description"
        assert event.processed is True

    def test_get_tile_enhanced(self):
        """Test getting enhanced tile data with NPCs and items."""
        tile = self.universe.get_tile(2, 3)

        # Add mock item. ItemSerializer reads `count` and hardcodes 1 as its
        # default, so a mock carrying `quantity` left `count == 1` no matter
        # what it said -- the stack size assertion could not fail.
        class MockItem:
            def __init__(self):
                self.name = "Test Item"
                self.description = "A test item"
                self.count = 3

        # Add mock NPC. The engine has no `health`/`max_health`/`is_hostile`:
        # NPCSerializer reads `hp`/`maxhp` and derives hostility from
        # `aggro` and `friend` (see its own comment).
        class MockNPC:
            def __init__(self):
                self.name = "Test NPC"
                self.level = 5
                self.hp = 50
                self.maxhp = 100
                self.aggro = True
                self.friend = False

        # Add mock object
        class MockObject:
            def __init__(self):
                self.name = "Test Object"
                self.description = "A test object"
                self.is_passable = True

        tile.items_here.append(MockItem())
        tile.npcs_here.append(MockNPC())
        tile.objects_here = [MockObject()]

        result = self.service.get_tile(self.player, 2, 3)

        assert result["name"] == "Test Room B"
        assert len(result["items"]) == 1
        assert result["items"][0]["name"] == "Test Item"
        assert result["items"][0]["count"] == 3
        assert len(result["npcs"]) == 1
        npc = result["npcs"][0]
        assert npc["name"] == "Test NPC"
        assert npc["level"] == 5
        assert npc["health"] == 50
        assert npc["max_health"] == 100
        assert npc["is_hostile"] is True
        assert len(result["objects"]) == 1
        assert result["objects"][0]["name"] == "Test Object"
        assert "exits" in result

    @pytest.mark.asyncio
    async def test_save_game(self):
        """Test saving a game.

        save_game is async and DB-backed (Turso): it takes the DB user id and
        writes a row, so the test drives it with a fake db.
        """
        db = _FakeDb()
        with patch("src.api.db.db", db):
            save_id = await self.service.save_game(
                self.player, "Test Save", "user-1"
            )

        assert save_id is not None
        assert isinstance(save_id, str)
        sql, params = db.calls[-1]
        assert sql.startswith("INSERT INTO saves")
        assert params[0] == save_id
        assert params[1] == "user-1"
        assert params[2] == "Test Save"
        assert isinstance(params[3], bytes)

    @pytest.mark.asyncio
    async def test_list_saves_maps_every_row_column(self):
        """A seeded row exercises the row-mapping loop, not just the SQL.

        With no rows the loop never runs, so nothing downstream of the query
        was covered -- including the `timestamp_ms` epoch derivation the
        frontend's save ordering depends on (CLAUDE.md, "Save-list ordering").
        """
        row = [
            "save-1",
            "Cellar",
            "2026-04-23 22:15:00",  # SQLite CURRENT_TIMESTAMP, UTC
            0,
            7,
            "Dark Grotto",
            "Mineral Pools",
            3600,
        ]
        db = _FakeDb(rows=[row])
        with patch("src.api.db.db", db):
            result = await self.service.list_saves("user-1", timezone="UTC")

        sql, params = db.calls[-1]
        assert "FROM saves" in sql
        assert params == ["user-1"]

        assert len(result) == 1
        save = result[0]
        assert save["id"] == "save-1"
        assert save["name"] == "Cellar"
        assert save["is_autosave"] is False
        assert save["level"] == 7
        assert save["map_name"] == "Dark Grotto"
        assert save["room_title"] == "Mineral Pools"
        assert save["playtime"] == 3600
        # Derived from the UTC instant *before* the display conversion, so it
        # is timezone-independent; the display string is not.
        assert save["timestamp_ms"] == 1776982500000  # 2026-04-23T22:15:00Z
        assert save["timestamp"] == "2026-04-23 22:15:00 UTC"

    @pytest.mark.asyncio
    async def test_list_saves_tolerates_an_unparseable_timestamp(self):
        """A row whose timestamp will not parse keeps the raw string, no ms."""
        row = ["save-2", "Odd", "not-a-timestamp", 1, None, None, None, None]
        db = _FakeDb(rows=[row])
        with patch("src.api.db.db", db):
            result = await self.service.list_saves("user-1", timezone="UTC")

        save = result[0]
        assert save["timestamp"] == "not-a-timestamp"
        assert save["timestamp_ms"] is None
        assert save["is_autosave"] is True
        assert save["level"] == "?"
        assert save["map_name"] == "Unknown"
        assert save["room_title"] == "Unknown"
        assert save["playtime"] == 0

    @pytest.mark.asyncio
    async def test_save_game_rejects_the_twenty_first_manual_save(self):
        """The manual-save cap is enforced before anything is written.

        `_FakeDb.manual_save_count` had no caller passing a non-zero value, so
        this guard was never reached.
        """
        db = _FakeDb(manual_save_count=20)
        with patch("src.api.db.db", db):
            with pytest.raises(ValueError, match="Maximum number of manual saves"):
                await self.service.save_game(self.player, "One Too Many", "user-1")

        assert not any(sql.startswith("INSERT INTO saves") for sql, _ in db.calls)

    @pytest.mark.asyncio
    async def test_delete_save_of_another_users_save_deletes_nothing(self):
        """Ownership is scoped in SQL: no matching row means no deletion."""
        db = _FakeDb(rows_affected=0)
        with patch("src.api.db.db", db):
            result = await self.service.delete_save("test_save_id", "user-1")

        assert result is False
        sql, params = db.calls[-1]
        assert sql.startswith("DELETE FROM saves")
        assert params == ["test_save_id", "user-1"]

    @pytest.mark.asyncio
    async def test_delete_save_of_own_save_reports_success(self):
        """A DELETE that matched a row reports True.

        Without this case `delete_save` could be `return False` and the
        negative test above would still pass -- it was asserting a property of
        the fake, not of the service.
        """
        db = _FakeDb(rows_affected=1)
        with patch("src.api.db.db", db):
            result = await self.service.delete_save("test_save_id", "user-1")

        assert result is True
