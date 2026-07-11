"""Tests for SessionManager."""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Ensure the project's src directory is on sys.path
ROOT = Path(__file__).resolve().parent.parent.parent


import pytest
from src.api.services.session_manager import SessionManager, Session  # type: ignore


class TestSession:
    """Test Session class."""

    def test_session_creation(self):
        """Test creating a new session."""
        session = Session("sess_123", "player_456", "testuser", datetime.now())

        assert session.session_id == "sess_123"
        assert session.player_id == "player_456"
        assert session.username == "testuser"
        assert not session.is_expired()

    def test_session_expiration(self):
        """Test session expiration."""
        past_time = datetime.now() - timedelta(days=2)
        session = Session("sess_123", "player_456", "testuser", past_time)

        assert session.is_expired()

    def test_session_update_access_time(self):
        """Test updating session access time."""
        from unittest.mock import patch, MagicMock

        now = datetime.now()
        session = Session("sess_123", "player_456", "testuser", now)
        original_expires = session.expires_at

        # Mock datetime.now() and timedelta to simulate time passage
        future_time = now + timedelta(seconds=1)
        with patch('src.api.services.session_manager.datetime') as mock_datetime:
            # Make sure we return the correct values for datetime.now() calls
            mock_datetime.now.return_value = future_time
            mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
            session.update_access_time()

        assert session.last_accessed > now
        assert session.expires_at > original_expires

    def test_session_to_dict(self):
        """Test converting session to dictionary."""
        session = Session("sess_123", "player_456", "testuser", datetime.now())
        session_dict = session.to_dict()

        assert session_dict["session_id"] == "sess_123"
        assert session_dict["player_id"] == "player_456"
        assert session_dict["username"] == "testuser"
        assert "created_at" in session_dict
        assert "expires_at" in session_dict


class TestSessionManager:
    """Test SessionManager class."""

    def test_create_session(self):
        """Test creating a new session."""
        manager = SessionManager()

        session_id, player_id = manager.create_session("testuser")

        assert session_id is not None
        assert player_id is not None
        assert session_id != player_id

    def test_get_session_valid(self):
        """Test retrieving a valid session."""
        manager = SessionManager()
        session_id, _ = manager.create_session("testuser")

        session = manager.get_session(session_id)

        assert session is not None
        assert session.session_id == session_id
        assert session.username == "testuser"

    def test_get_session_invalid(self):
        """Test retrieving an invalid session."""
        manager = SessionManager()

        session = manager.get_session("invalid_id")

        assert session is None

    def test_get_session_expired(self):
        """Test that expired sessions return None."""
        manager = SessionManager()
        session_id, _ = manager.create_session("testuser")

        # Manually expire the session
        session = manager.sessions[session_id]
        session.expires_at = datetime.now() - timedelta(hours=1)

        result = manager.get_session(session_id)

        assert result is None
        assert session_id not in manager.sessions

    def test_get_player(self):
        """Test retrieving a player from a session."""
        manager = SessionManager()
        session_id, player_id = manager.create_session("testuser")

        # Set a dummy player
        manager.players[player_id] = "dummy_player_object"

        player = manager.get_player(session_id)

        assert player == "dummy_player_object"

    def test_get_player_invalid_session(self):
        """Test getting player from invalid session."""
        manager = SessionManager()

        player = manager.get_player("invalid_id")

        assert player is None

    def test_set_player(self):
        """Test setting a player for a session."""
        manager = SessionManager()
        session_id, player_id = manager.create_session("testuser")

        result = manager.set_player(session_id, "test_player")

        assert result is True
        assert manager.players[player_id] == "test_player"

    def test_set_player_invalid_session(self):
        """Test setting player for invalid session."""
        manager = SessionManager()

        result = manager.set_player("invalid_id", "test_player")

        assert result is False

    def test_expire_session(self):
        """Test expiring a session."""
        manager = SessionManager()
        session_id, player_id = manager.create_session("testuser")

        result = manager.expire_session(session_id)

        assert result is True
        assert session_id not in manager.sessions
        assert player_id not in manager.players

    def test_expire_invalid_session(self):
        """Test expiring an invalid session."""
        manager = SessionManager()

        result = manager.expire_session("invalid_id")

        assert result is False

    def test_cleanup_expired(self):
        """Test cleaning up expired sessions."""
        manager = SessionManager()

        # Create multiple sessions
        ids = []
        for i in range(3):
            session_id, _ = manager.create_session(f"user{i}")
            ids.append(session_id)

        # Expire first two
        for session_id in ids[:2]:
            manager.sessions[session_id].expires_at = datetime.now() - timedelta(
                hours=1
            )

        count = manager.cleanup_expired()

        assert count == 2
        assert ids[0] not in manager.sessions
        assert ids[1] not in manager.sessions
        assert ids[2] in manager.sessions

    def test_get_active_session_count(self):
        """Test counting active sessions."""
        manager = SessionManager()

        for i in range(3):
            manager.create_session(f"user{i}")

        count = manager.get_active_session_count()

        assert count == 3

    def test_get_all_sessions(self):
        """Test retrieving all sessions."""
        manager = SessionManager()

        for i in range(3):
            manager.create_session(f"user{i}")

        sessions = manager.get_all_sessions()

        assert len(sessions) == 3
        assert all("session_id" in s for s in sessions)
        assert all("username" in s for s in sessions)


class TestApplyStartingEquipment:
    """_apply_starting_equipment must fully wire config items into the player —
    not just mark isequipped in the display, but set eq_weapon and recalc protection."""

    def _sm(self, specs):
        """SessionManager with starting_equipment injected directly (no CONFIG_FILE needed)."""
        sm = SessionManager()
        sm.starting_equipment = list(specs)
        return sm

    def test_weapon_replaces_fists_as_eq_weapon(self):
        player = self._sm(["Shortsword:0"])._create_player_for_session("tester")

        assert player.eq_weapon is not player.fists
        assert player.eq_weapon.maintype == "Weapon"

    def test_weapon_damage_exceeds_fists(self):
        player = self._sm(["Shortsword:0"])._create_player_for_session("tester")

        assert player.eq_weapon.damage > player.fists.damage

    def test_weapon_item_flags_correct(self):
        player = self._sm(["Shortsword:0"])._create_player_for_session("tester")

        sword = next(
            (i for i in player.inventory
             if getattr(i, "maintype", None) == "Weapon" and i is not player.fists),
            None,
        )
        assert sword is not None, "Shortsword not found in inventory"
        assert sword.isequipped is True
        assert "unequip" in sword.interactions
        assert "equip" not in sword.interactions

    def test_armor_raises_protection_above_endurance_base(self):
        player = self._sm(["LeatherArmor:0"])._create_player_for_session("tester")

        assert player.protection > player.endurance / 10

    def test_armor_protection_value_is_included(self):
        player = self._sm(["LeatherArmor:0"])._create_player_for_session("tester")

        # LeatherArmor contributes 4 protection; endurance/10 is the stat base.
        # str_mod/fin_mod contributions can only add more, so >= is a safe bound.
        assert player.protection >= player.endurance / 10 + 4

    def test_new_armor_unequips_conflicting_default_armor(self):
        player = self._sm(["LeatherArmor:0"])._create_player_for_session("tester")

        # After equipping LeatherArmor, no other Armor-slot item should remain equipped.
        # This is an unconditional assertion — if the default kit changes and there is
        # no conflict item, the slot-conflict logic is still verified by the protection
        # value tests; but if there IS an Armor item, it must be unequipped.
        still_equipped_armor = [
            i for i in player.inventory
            if getattr(i, "maintype", None) == "Armor"
            and getattr(i, "isequipped", False)
            and i.name != "Leather Armor"
        ]
        assert still_equipped_armor == [], (
            f"Slot conflict not resolved — these Armor items are still equipped: "
            f"{[i.name for i in still_equipped_armor]}"
        )

    def test_full_leather_set_composite_protection(self):
        player = self._sm(
            ["Shortsword:0", "LeatherArmor:0", "LeatherCap:0", "LeatherGloves:0", "LeatherBoots:0"]
        )._create_player_for_session("tester")

        assert player.eq_weapon is not player.fists
        assert player.eq_weapon.maintype == "Weapon"
        # 4 (Armor) + 2 (Cap) + 2 (Gloves) + 3 (Boots) = 11 minimum from leather set
        assert player.protection >= player.endurance / 10 + 11

    def test_unknown_item_class_skipped_valid_items_still_applied(self):
        player = self._sm(
            ["NonExistentItem:0", "Shortsword:0"]
        )._create_player_for_session("tester")

        assert player.eq_weapon is not player.fists

    def test_empty_starting_equipment_leaves_fists(self):
        sm = SessionManager()
        sm.starting_equipment = []
        player = sm._create_player_for_session("tester")

        assert player.eq_weapon is player.fists

    def test_minimal_player_fallback_does_not_raise(self):
        from src.api.services.session_manager import MinimalPlayer

        sm = SessionManager()
        sm.starting_equipment = ["Shortsword:0"]
        minimal = MinimalPlayer("tester")
        sm._apply_starting_equipment(minimal)  # must not raise
