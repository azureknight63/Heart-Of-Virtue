"""The beta-2 cloud-save wipe: counts by default, deletes only on the exact phrase."""
import asyncio
import io
from types import SimpleNamespace

import pytest

from tools import wipe_cloud_saves as wipe


class FakeDb:
    """Stands in for ``src.api.db.db``: same ``execute(sql, params)`` coroutine."""

    def __init__(self, saves):
        self.saves = list(saves)
        self.statements = []

    async def execute(self, sql, params=None):
        self.statements.append(sql)
        text = " ".join(sql.split()).upper()
        if text.startswith("DELETE FROM SAVES"):
            self.saves.clear()
            return SimpleNamespace(rows=[])
        if "GROUP BY USER_ID" in text:
            per_user = {}
            for save in self.saves:
                per_user[save["user_id"]] = per_user.get(save["user_id"], 0) + 1
            return SimpleNamespace(rows=sorted(per_user.items()))
        if text.startswith("SELECT COUNT(*)"):
            stamps = [s["timestamp"] for s in self.saves]
            autosaves = sum(1 for s in self.saves if s["is_autosave"])
            return SimpleNamespace(rows=[(
                len(self.saves), autosaves,
                min(stamps) if stamps else None, max(stamps) if stamps else None,
            )])
        raise AssertionError(f"unexpected SQL: {sql}")


SAVES = [
    {"user_id": "u1", "timestamp": "2026-04-02 10:00:00", "is_autosave": True},
    {"user_id": "u1", "timestamp": "2026-04-10 10:00:00", "is_autosave": False},
    {"user_id": "u2", "timestamp": "2026-04-17 10:00:00", "is_autosave": True},
]


def _run(db, confirm=None):
    out = io.StringIO()
    code = asyncio.run(wipe.run(db, confirm=confirm, out=out))
    return code, out.getvalue()


def test_dry_run_reports_and_deletes_nothing():
    db = FakeDb(SAVES)
    code, text = _run(db)
    assert code == 0
    assert len(db.saves) == len(SAVES)
    assert not any("DELETE" in s.upper() for s in db.statements)
    assert "3 saves" in text and "2 autosaves" in text and "2 users" in text
    assert "2026-04-02 10:00:00" in text and "2026-04-17 10:00:00" in text
    assert wipe.CONFIRM_PHRASE in text


@pytest.mark.parametrize("phrase", ["yes", wipe.CONFIRM_PHRASE.lower(), wipe.CONFIRM_PHRASE + " ", ""])
def test_anything_but_the_exact_phrase_refuses(phrase):
    db = FakeDb(SAVES)
    code, text = _run(db, confirm=phrase)
    assert code != 0
    assert len(db.saves) == len(SAVES)
    assert not any("DELETE" in s.upper() for s in db.statements)
    assert "not deleted" in text.lower()


def test_exact_phrase_deletes_every_save_and_recounts():
    db = FakeDb(SAVES)
    code, text = _run(db, confirm=wipe.CONFIRM_PHRASE)
    assert code == 0
    assert db.saves == []
    assert sum("DELETE" in s.upper() for s in db.statements) == 1
    assert "0 saves" in text


def test_delete_touches_only_the_saves_table():
    db = FakeDb(SAVES)
    _run(db, confirm=wipe.CONFIRM_PHRASE)
    (delete,) = [s for s in db.statements if "DELETE" in s.upper()]
    assert " ".join(delete.split()).upper() == "DELETE FROM SAVES"


def test_empty_table_is_reported_plainly():
    code, text = _run(FakeDb([]))
    assert code == 0
    assert "0 saves" in text


@pytest.mark.parametrize("url, host", [
    ("libsql://hov-prod-someone.turso.io", "hov-prod-someone.turso.io"),
    ("https://user:secret@db.example.com:8080/x?authToken=abc", "db.example.com:8080"),
    ("libsql://db.example.com:notaport", "db.example.com"),
    ("", "(unset)"),
    (None, "(unset)"),
])
def test_database_host_never_shows_credentials(url, host):
    assert wipe.database_host(url) == host
