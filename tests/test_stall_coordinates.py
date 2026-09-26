"""Stalled players are located by map, room AND tile coordinates.

A room name alone is ambiguous: several tiles share a name ("Cave Entrance"
appears more than once on some maps). Saves therefore record the player's tile
coordinates, and the stall report groups and shows them.
"""

import asyncio
import re
import sqlite3
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api import migrations
from src.api.services import analytics_report as report
from src.api.services.analytics import SCHEMA_STATEMENTS

NOW = 1_800_000_000
DAY = report.DAY


def _columns_to_params(sql, params):
    """{column: value} for an INSERT ... VALUES or UPDATE ... SET statement."""
    sql = " ".join(sql.split())
    insert = re.search(r"INSERT INTO saves \(([^)]*)\)", sql)
    if insert:
        return dict(zip([c.strip() for c in insert.group(1).split(",")], params))
    assignments = re.search(r"SET (.*) WHERE", sql).group(1)
    names = [a.split("=")[0].strip() for a in assignments.split(",")]
    names = [n for n in names if n != "timestamp"]  # CURRENT_TIMESTAMP, no param
    return dict(zip(names, params))


def _result(rows=()):
    r = MagicMock()
    r.rows = list(rows)
    return r


@pytest.fixture
def saving(monkeypatch):
    from src.api.services import game_service as gs_module
    from tests._combat_fixtures import make_player

    import src.api.db
    import src.secure_pickle

    # save_game imports both at call time, so patch them where they live.
    db = MagicMock()
    db.execute = AsyncMock()
    monkeypatch.setattr(src.api.db, "db", db)
    monkeypatch.setattr(src.secure_pickle, "serialize_for_save", lambda player: b"blob")
    player = make_player()
    player.location_x, player.location_y = 14, 5
    return gs_module.GameService(), player, db


class TestSavesRecordCoordinates:
    def test_manual_save(self, saving):
        service, player, db = saving
        db.execute.side_effect = [_result(rows=[[0]]), _result()]
        asyncio.run(service.save_game(player, "Before the gate", "u1"))
        written = _columns_to_params(*db.execute.call_args_list[-1].args)
        assert (written["location_x"], written["location_y"]) == (14, 5)

    def test_first_autosave(self, saving):
        service, player, db = saving
        db.execute.side_effect = [_result(rows=[]), _result()]
        asyncio.run(service.save_game(player, "Auto", "u1", is_autosave=True))
        written = _columns_to_params(*db.execute.call_args_list[-1].args)
        assert (written["location_x"], written["location_y"]) == (14, 5)

    def test_autosave_update(self, saving):
        service, player, db = saving
        db.execute.side_effect = [_result(rows=[["save-1"]]), _result()]
        asyncio.run(service.save_game(player, "Auto", "u1", is_autosave=True))
        sql, params = db.execute.call_args_list[-1].args
        written = _columns_to_params(sql, params)
        assert (written["location_x"], written["location_y"]) == (14, 5)
        assert params[-1] == "save-1"  # the WHERE id stays last


class TestSchema:
    def test_new_databases_get_the_columns(self):
        conn = sqlite3.connect(":memory:")
        conn.execute(migrations.USERS_TABLE)
        conn.execute(migrations.SAVES_TABLE)
        columns = {row[1] for row in conn.execute("PRAGMA table_info(saves)")}
        assert {"location_x", "location_y"} <= columns

    def test_existing_databases_get_them_by_backfill(self):
        mock_db = MagicMock()
        mock_db.batch = AsyncMock()
        mock_db.execute = AsyncMock()
        mock_db.close = AsyncMock()
        from unittest.mock import patch

        with patch("src.api.migrations.db", mock_db):
            asyncio.run(migrations.init_db())
        run = [c.args[0] for c in mock_db.execute.call_args_list]
        assert "ALTER TABLE saves ADD COLUMN location_x INTEGER" in run
        assert "ALTER TABLE saves ADD COLUMN location_y INTEGER" in run


class TestStallReport:
    @pytest.fixture
    def db(self):
        conn = sqlite3.connect(":memory:")
        for stmt in (migrations.USERS_TABLE, migrations.SAVES_TABLE, *SCHEMA_STATEMENTS):
            conn.execute(stmt)
        return conn

    def autosave(self, conn, uid, room, x, y, days_ago=10):
        conn.execute(
            "INSERT INTO saves (id, user_id, name, data, timestamp, is_autosave, level, map_name, "
            "room_title, location_x, location_y) VALUES (?, ?, 'Autosave', x'00', "
            "datetime(?, 'unixepoch'), 1, 2, 'dark-grotto', ?, ?, ?)",
            [uid, uid, NOW - days_ago * DAY, room, x, y],
        )

    def stalled(self, conn):
        async def execute(sql, params=None):
            return conn.execute(sql, params or []).fetchall()

        return asyncio.run(report.build_report(execute, now=NOW))["progress"]["stalled"]

    def test_same_room_name_on_two_tiles_is_two_rows(self, db):
        self.autosave(db, "a", "Cave Entrance", 14, 5)
        self.autosave(db, "b", "Cave Entrance", 14, 5)
        self.autosave(db, "c", "Cave Entrance", 3, 9)
        assert self.stalled(db) == [
            {"map": "dark-grotto", "room": "Cave Entrance", "x": 14, "y": 5, "players": 2},
            {"map": "dark-grotto", "room": "Cave Entrance", "x": 3, "y": 9, "players": 1},
        ]

    def test_saves_from_before_coordinates_report_none(self, db):
        self.autosave(db, "old", "Slime Pool", None, None)
        assert self.stalled(db) == [
            {"map": "dark-grotto", "room": "Slime Pool", "x": None, "y": None, "players": 1}
        ]

    def test_text_and_digest_show_the_coordinates(self, db):
        self.autosave(db, "a", "Cave Entrance", 14, 5)

        async def execute(sql, params=None):
            return db.execute(sql, params or []).fetchall()

        r = asyncio.run(report.build_report(execute, now=NOW))
        assert "Cave Entrance (14, 5)" in report.format_text(r)
        assert "dark-grotto / Cave Entrance (14, 5) (1)" in report.format_digest(r, 1024)
