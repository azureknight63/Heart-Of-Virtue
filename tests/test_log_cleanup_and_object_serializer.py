"""
Tests for:
  - src/api/utils/log_cleanup.py    (LogCleanupManager)
  - src/api/serializers/object_serializer.py (ObjectSerializer)

Neither module requires Flask or a live DB — they operate on filesystem paths
and plain Python objects, making them straightforward to unit-test.
"""

import os
import time
import tempfile
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.api.utils.log_cleanup import LogCleanupManager
from src.api.serializers.object_serializer import ObjectSerializer

# ---------------------------------------------------------------------------
# LogCleanupManager
# ---------------------------------------------------------------------------


class TestLogCleanupManagerInit:
    def test_defaults_stored(self):
        mgr = LogCleanupManager("/tmp/logs")
        assert mgr.retention_days == 7
        assert mgr.max_size_bytes == 100 * 1024 * 1024

    def test_custom_params(self):
        mgr = LogCleanupManager("/tmp/logs", retention_days=14, max_size_mb=50)
        assert mgr.retention_days == 14
        assert mgr.max_size_bytes == 50 * 1024 * 1024

    def test_logs_dir_stored_as_path(self):
        mgr = LogCleanupManager("/tmp/logs")
        assert isinstance(mgr.logs_dir, Path)


class TestCleanupOldLogs:
    def test_nonexistent_dir_returns_error(self):
        mgr = LogCleanupManager("/nonexistent/path/xyz")
        result = mgr.cleanup_old_logs()
        assert result["deleted_count"] == 0
        assert "error" in result

    def test_empty_dir_returns_zero_deletions(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = LogCleanupManager(tmpdir, retention_days=1)
            result = mgr.cleanup_old_logs()
        assert result["deleted_count"] == 0
        assert result["deleted_size"] == 0

    def test_old_log_deleted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "old.log"
            log_file.write_text("old log content")
            # Make the file appear 10 days old
            old_time = time.time() - 10 * 86400
            os.utime(log_file, (old_time, old_time))

            mgr = LogCleanupManager(tmpdir, retention_days=7)
            result = mgr.cleanup_old_logs()

        assert result["deleted_count"] == 1
        assert result["deleted_size"] > 0

    def test_recent_log_not_deleted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "recent.log"
            log_file.write_text("recent content")

            mgr = LogCleanupManager(tmpdir, retention_days=7)
            result = mgr.cleanup_old_logs()

        assert result["deleted_count"] == 0

    def test_only_log_files_cleaned_not_other_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Non-log file that is old
            txt_file = Path(tmpdir) / "notes.txt"
            txt_file.write_text("notes")
            old_time = time.time() - 10 * 86400
            os.utime(txt_file, (old_time, old_time))

            mgr = LogCleanupManager(tmpdir, retention_days=1)
            result = mgr.cleanup_old_logs()

            # Both assertions must be inside the context so the tmpdir still exists
            assert result["deleted_count"] == 0
            assert txt_file.exists()

    def test_deleted_size_mb_in_result(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "big.log"
            log_file.write_bytes(b"x" * 1024)
            old_time = time.time() - 10 * 86400
            os.utime(log_file, (old_time, old_time))

            mgr = LogCleanupManager(tmpdir, retention_days=7)
            result = mgr.cleanup_old_logs()

        assert "deleted_size_mb" in result

    def test_multiple_old_logs_all_deleted(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            old_time = time.time() - 10 * 86400
            for i in range(3):
                f = Path(tmpdir) / f"old_{i}.log"
                f.write_text("content")
                os.utime(f, (old_time, old_time))

            mgr = LogCleanupManager(tmpdir, retention_days=7)
            result = mgr.cleanup_old_logs()

        assert result["deleted_count"] == 3


class TestCleanupBySize:
    def test_nonexistent_dir_returns_error(self):
        mgr = LogCleanupManager("/nonexistent/path/xyz")
        result = mgr.cleanup_by_size()
        assert result["deleted_count"] == 0
        assert "error" in result

    def test_no_deletion_when_under_limit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "small.log"
            log_file.write_bytes(b"x" * 100)

            mgr = LogCleanupManager(tmpdir, max_size_mb=100)
            result = mgr.cleanup_by_size()

        assert result["deleted_count"] == 0

    def test_oldest_deleted_when_over_limit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create two 600 KB files — total 1.2 MB; limit is 1 MB
            older = Path(tmpdir) / "older.log"
            newer = Path(tmpdir) / "newer.log"
            chunk = b"x" * 600 * 1024
            older.write_bytes(chunk)
            newer.write_bytes(chunk)

            # Make older file actually older
            old_time = time.time() - 3600
            os.utime(older, (old_time, old_time))

            mgr = LogCleanupManager(tmpdir, max_size_mb=1)
            result = mgr.cleanup_by_size()

        assert result["deleted_count"] >= 1

    def test_empty_dir_no_deletion(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = LogCleanupManager(tmpdir, max_size_mb=1)
            result = mgr.cleanup_by_size()
        assert result["deleted_count"] == 0


class TestCleanupCombined:
    def test_combined_cleanup_returns_aggregate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = LogCleanupManager(tmpdir)
            result = mgr.cleanup()
        assert "age_cleanup" in result
        assert "size_cleanup" in result
        assert "total_deleted_count" in result
        assert "total_deleted_size_mb" in result
        assert result["total_deleted_count"] == 0

    def test_combined_cleanup_sums_deletions(self):
        """Verify total_deleted_count = age_deleted + size_deleted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = LogCleanupManager(tmpdir)
            result = mgr.cleanup()
        expected = (
            result["age_cleanup"]["deleted_count"]
            + result["size_cleanup"]["deleted_count"]
        )
        assert result["total_deleted_count"] == expected


class TestGetStats:
    def test_nonexistent_dir_returns_zeros(self):
        mgr = LogCleanupManager("/nonexistent/xyz")
        stats = mgr.get_stats()
        assert stats["total_files"] == 0
        assert stats["oldest_file"] is None

    def test_empty_dir_returns_zeros(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = LogCleanupManager(tmpdir)
            stats = mgr.get_stats()
        assert stats["total_files"] == 0

    def test_with_log_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "a.log").write_text("hello")
            (Path(tmpdir) / "b.log").write_text("world")

            mgr = LogCleanupManager(tmpdir)
            stats = mgr.get_stats()

        assert stats["total_files"] == 2
        assert stats["total_size"] > 0
        assert stats["oldest_file"] is not None
        assert stats["newest_file"] is not None

    def test_total_size_mb_calculated(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "c.log").write_bytes(b"x" * 1024)
            mgr = LogCleanupManager(tmpdir)
            stats = mgr.get_stats()
        assert "total_size_mb" in stats
        assert stats["total_size_mb"] >= 0

    def test_oldest_and_newest_names_present(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            f1 = Path(tmpdir) / "first.log"
            f2 = Path(tmpdir) / "second.log"
            f1.write_text("a")
            old_time = time.time() - 3600
            os.utime(f1, (old_time, old_time))
            f2.write_text("b")

            mgr = LogCleanupManager(tmpdir)
            stats = mgr.get_stats()

        assert stats["oldest_file"]["name"] == "first.log"
        assert stats["newest_file"]["name"] == "second.log"


# ---------------------------------------------------------------------------
# ObjectSerializer
# ---------------------------------------------------------------------------


class _SimpleObj:
    """Minimal stand-in for a world object."""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


class TestObjectSerializerBase:
    def test_serialize_none_returns_empty(self):
        assert ObjectSerializer.serialize(None) == {}

    def test_serialize_empty_dict_returns_empty(self):
        assert ObjectSerializer._serialize_base({}) == {}

    def test_basic_attributes_serialized(self):
        obj = _SimpleObj(
            name="Chest", description="A wooden chest.", aliases=[], action_aliases=[]
        )
        data = ObjectSerializer._serialize_base(obj)
        assert data["name"] == "Chest"
        assert data["description"] == "A wooden chest."

    def test_dict_input_works(self):
        d = {
            "name": "Gate",
            "description": "Iron gate.",
            "aliases": [],
            "action_aliases": [],
        }
        data = ObjectSerializer._serialize_base(d)
        assert data["name"] == "Gate"
        assert data["type"] == "dict"

    def test_id_defaults_to_python_id_for_objects(self):
        obj = _SimpleObj(name="X", description="", aliases=[], action_aliases=[])
        data = ObjectSerializer._serialize_base(obj)
        assert str(id(obj)) == data["id"]

    def test_custom_id_used_when_present(self):
        obj = _SimpleObj(
            id="obj-42", name="X", description="", aliases=[], action_aliases=[]
        )
        data = ObjectSerializer._serialize_base(obj)
        assert data["id"] == "obj-42"

    def test_is_passable_included_when_present(self):
        obj = _SimpleObj(
            name="Wall",
            description="",
            aliases=[],
            action_aliases=[],
            is_passable=False,
        )
        data = ObjectSerializer._serialize_base(obj)
        assert "is_passable" in data
        assert data["is_passable"] is False

    def test_hidden_included_when_present(self):
        obj = _SimpleObj(
            name="Secret",
            description="",
            aliases=[],
            action_aliases=[],
            hidden=True,
            hide_factor=80,
        )
        data = ObjectSerializer._serialize_base(obj)
        assert data["hidden"] is True
        assert data["hide_factor"] == 80

    def test_locked_attribute_included(self):
        obj = _SimpleObj(
            name="Door", description="", aliases=[], action_aliases=[], locked=True
        )
        data = ObjectSerializer._serialize_base(obj)
        assert data["locked"] is True

    def test_state_sets_opened_true_for_opened(self):
        obj = _SimpleObj(
            name="Door", description="", aliases=[], action_aliases=[], state="opened"
        )
        data = ObjectSerializer._serialize_base(obj)
        assert data["state"] == "opened"
        assert data["opened"] is True

    def test_state_sets_opened_false_for_closed(self):
        obj = _SimpleObj(
            name="Door", description="", aliases=[], action_aliases=[], state="closed"
        )
        data = ObjectSerializer._serialize_base(obj)
        assert data["opened"] is False

    def test_opened_attribute_fallback(self):
        obj = _SimpleObj(
            name="Chest", description="", aliases=[], action_aliases=[], opened=True
        )
        data = ObjectSerializer._serialize_base(obj)
        assert data["opened"] is True

    def test_keywords_unchanged_when_no_lock_or_opened(self):
        obj = _SimpleObj(
            name="Box",
            description="",
            aliases=[],
            action_aliases=[],
            keywords=["push", "pull"],
        )
        data = ObjectSerializer._serialize_base(obj)
        assert set(data["keywords"]) == {"push", "pull"}

    def test_keywords_gain_unlock_when_locked(self):
        obj = _SimpleObj(
            name="Door",
            description="",
            aliases=[],
            action_aliases=[],
            keywords=["examine"],
            locked=True,
            state="closed",
        )
        data = ObjectSerializer._serialize_base(obj)
        assert "unlock" in data["keywords"]
        assert "open" not in data["keywords"]

    def test_keywords_gain_open_when_unlocked_and_closed(self):
        obj = _SimpleObj(
            name="Door",
            description="",
            aliases=[],
            action_aliases=[],
            keywords=["examine"],
            locked=False,
            state="closed",
        )
        data = ObjectSerializer._serialize_base(obj)
        assert "open" in data["keywords"]

    def test_keywords_no_open_when_already_opened(self):
        obj = _SimpleObj(
            name="Door",
            description="",
            aliases=[],
            action_aliases=[],
            keywords=["examine"],
            locked=False,
            state="opened",
        )
        data = ObjectSerializer._serialize_base(obj)
        # Already opened — neither open nor unlock should be added
        assert "open" not in data["keywords"]
        assert "unlock" not in data["keywords"]

    def test_open_message_included(self):
        obj = _SimpleObj(
            name="Door",
            description="",
            aliases=[],
            action_aliases=[],
            open_message="It swings open.",
        )
        data = ObjectSerializer._serialize_base(obj)
        assert data["open_message"] == "It swings open."

    def test_idle_message_included(self):
        obj = _SimpleObj(
            name="Statue",
            description="",
            aliases=[],
            action_aliases=[],
            idle_message="stands there.",
        )
        data = ObjectSerializer._serialize_base(obj)
        assert data["idle_message"] == "stands there."


class TestObjectSerializeList:
    def test_empty_list_returns_empty(self):
        assert ObjectSerializer.serialize_list([]) == []

    def test_none_returns_empty(self):
        assert ObjectSerializer.serialize_list(None) == []

    def test_single_object(self):
        obj = _SimpleObj(
            name="Rock", description="A grey rock.", aliases=[], action_aliases=[]
        )
        result = ObjectSerializer.serialize_list([obj])
        assert len(result) == 1
        assert result[0]["name"] == "Rock"

    def test_multiple_objects(self):
        objs = [
            _SimpleObj(name=f"Item{i}", description="", aliases=[], action_aliases=[])
            for i in range(3)
        ]
        result = ObjectSerializer.serialize_list(objs)
        assert len(result) == 3
        names = {r["name"] for r in result}
        assert names == {"Item0", "Item1", "Item2"}


class TestObjectSerializeContainer:
    def test_is_container_flag_set(self):
        obj = _SimpleObj(name="Chest", description="", aliases=[], action_aliases=[])
        data = ObjectSerializer.serialize_container(obj)
        assert data["is_container"] is True

    def test_empty_container_has_zero_count(self):
        obj = _SimpleObj(name="Box", description="", aliases=[], action_aliases=[])
        data = ObjectSerializer.serialize_container(obj)
        assert data["item_count"] == 0
        assert data["contents"] == []

    def test_inventory_attribute_serialized(self):
        item = MagicMock()
        item.name = "Sword"
        item.description = "Sharp"
        item.type_name = "Weapon"
        # Make serialize_list return a predictable value
        obj = _SimpleObj(name="Chest", description="", aliases=[], action_aliases=[])
        obj.inventory = [item]
        with patch(
            "src.api.serializers.item_serializer.ItemSerializer.serialize_list"
        ) as mock_sl:
            mock_sl.return_value = [{"name": "Sword"}]
            data = ObjectSerializer.serialize_container(obj)
        assert data["item_count"] == 1
        assert len(data["contents"]) == 1

    def test_capacity_included_when_present(self):
        obj = _SimpleObj(
            name="Bag", description="", aliases=[], action_aliases=[], capacity=20
        )
        data = ObjectSerializer.serialize_container(obj)
        assert data["capacity"] == 20

    def test_items_here_fallback(self):
        item = MagicMock()
        obj = _SimpleObj(name="Pile", description="", aliases=[], action_aliases=[])
        obj.items_here = [item]
        with patch(
            "src.api.serializers.item_serializer.ItemSerializer.serialize_list"
        ) as mock_sl:
            mock_sl.return_value = [{"name": "Stone"}]
            data = ObjectSerializer.serialize_container(obj)
        assert data["item_count"] == 1


class TestObjectSerializeInteractive:
    def test_has_events_false_when_no_events(self):
        obj = _SimpleObj(name="Shrine", description="", aliases=[], action_aliases=[])
        data = ObjectSerializer.serialize_interactive(obj)
        assert data["has_events"] is False

    def test_has_events_true_when_events_present(self):
        obj = _SimpleObj(name="Shrine", description="", aliases=[], action_aliases=[])
        obj.events = [MagicMock(), MagicMock()]
        data = ObjectSerializer.serialize_interactive(obj)
        assert data["has_events"] is True
        assert data["events"] == 2

    def test_consequence_included(self):
        obj = _SimpleObj(
            name="Lever",
            description="",
            aliases=[],
            action_aliases=[],
            consequence_text="The gate slides open.",
        )
        data = ObjectSerializer.serialize_interactive(obj)
        assert data["consequence"] == "The gate slides open."

    def test_one_time_only_included(self):
        obj = _SimpleObj(
            name="Altar",
            description="",
            aliases=[],
            action_aliases=[],
            one_time_only=True,
        )
        data = ObjectSerializer.serialize_interactive(obj)
        assert data["one_time_only"] is True


class TestObjectSerializeDoor:
    def test_is_door_flag_set(self):
        obj = _SimpleObj(name="Gate", description="", aliases=[], action_aliases=[])
        data = ObjectSerializer.serialize_door(obj)
        assert data["is_door"] is True

    def test_opened_and_locked_included(self):
        obj = _SimpleObj(
            name="Gate",
            description="",
            aliases=[],
            action_aliases=[],
            opened=False,
            locked=True,
        )
        data = ObjectSerializer.serialize_door(obj)
        assert data["opened"] is False
        assert data["locked"] is True

    def test_leads_to_included(self):
        obj = _SimpleObj(
            name="Gate",
            description="",
            aliases=[],
            action_aliases=[],
            leads_to="Throne Room",
        )
        data = ObjectSerializer.serialize_door(obj)
        assert data["leads_to"] == "Throne Room"

    def test_locked_message_included(self):
        obj = _SimpleObj(
            name="Gate",
            description="",
            aliases=[],
            action_aliases=[],
            locked_message="It won't budge.",
        )
        data = ObjectSerializer.serialize_door(obj)
        assert data["locked_message"] == "It won't budge."


class TestObjectSerializeShrine:
    def test_is_shrine_flag_set(self):
        obj = _SimpleObj(
            name="Holy Shrine", description="", aliases=[], action_aliases=[]
        )
        data = ObjectSerializer.serialize_shrine(obj)
        assert data["is_shrine"] is True

    def test_blessing_text_included(self):
        obj = _SimpleObj(
            name="Shrine",
            description="",
            aliases=[],
            action_aliases=[],
            blessing_text="May the Light guide you.",
        )
        data = ObjectSerializer.serialize_shrine(obj)
        assert data["blessing"] == "May the Light guide you."

    def test_blessing_effect_included(self):
        obj = _SimpleObj(
            name="Shrine",
            description="",
            aliases=[],
            action_aliases=[],
            blessing_effect={"hp_restore": 20},
        )
        data = ObjectSerializer.serialize_shrine(obj)
        assert data["blessing_effect"] == {"hp_restore": 20}

    def test_last_blessed_at_included(self):
        obj = _SimpleObj(
            name="Shrine",
            description="",
            aliases=[],
            action_aliases=[],
            last_blessed_at="2026-01-01T00:00:00",
        )
        data = ObjectSerializer.serialize_shrine(obj)
        assert data["last_blessed_at"] == "2026-01-01T00:00:00"
