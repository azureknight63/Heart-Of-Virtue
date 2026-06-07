"""
Tests for:
- src/api/services/auth_service.py (validation logic and encrypt/decrypt, no DB)
- src/api/serializers/npc_availability.py (pure serializer classes)
"""

import pytest
import os
from unittest.mock import MagicMock, AsyncMock, patch
from cryptography.fernet import Fernet

from src.api.serializers.npc_availability import (
    AvailabilityReason,
    NPCLocationSerializer,
    NPCAvailabilitySerializer,
    LocationNPCSerializer,
    NPCTimelineSerializer,
    NPCEventTriggerSerializer,
)

# ===========================================================================
# AuthService — tested in isolation (no DB calls)
# ===========================================================================


class TestAuthServiceInit:
    """Test that AuthService can be constructed with/without env key."""

    def test_init_generates_key_when_env_absent(self):
        """Without ENCRYPTION_KEY env var, a key should be generated and stored."""
        from src.api.services.auth_service import AuthService

        with patch.dict(os.environ, {}, clear=True):
            # Remove key if set
            os.environ.pop("ENCRYPTION_KEY", None)
            svc = AuthService()
            assert svc.fernet is not None

    def test_init_uses_env_key_when_present(self):
        """If ENCRYPTION_KEY is set, AuthService must use it for the Fernet instance."""
        from src.api.services.auth_service import AuthService

        key = Fernet.generate_key().decode()
        with patch.dict(os.environ, {"ENCRYPTION_KEY": key}):
            svc = AuthService()
            assert svc.fernet is not None

    def test_encrypt_decrypt_roundtrip(self):
        """Encrypted email should decrypt back to original plaintext."""
        from src.api.services.auth_service import AuthService

        svc = AuthService()
        email = "test@example.com"
        encrypted = svc.fernet.encrypt(email.encode()).decode()
        decrypted = svc.decrypt_email(encrypted)
        assert decrypted == email

    def test_decrypt_email_method(self):
        from src.api.services.auth_service import AuthService

        svc = AuthService()
        plaintext = "jean@virtue.medieval"
        token = svc.fernet.encrypt(plaintext.encode()).decode()
        assert svc.decrypt_email(token) == plaintext


class TestAuthServiceValidation:
    """Test validation rules without any DB interaction."""

    @pytest.fixture
    def svc(self):
        from src.api.services.auth_service import AuthService

        return AuthService()

    @pytest.mark.asyncio
    async def test_create_user_short_username_raises(self, svc):
        with pytest.raises(ValueError, match="at least 4"):
            await svc.create_user("abc", "validpassword12345", "x@y.com")

    @pytest.mark.asyncio
    async def test_create_user_short_password_raises(self, svc):
        with pytest.raises(ValueError, match="at least 16"):
            await svc.create_user("validuser", "short", "x@y.com")

    @pytest.mark.asyncio
    async def test_create_user_valid_calls_db(self, svc):
        """Valid inputs should invoke db.execute (mocked) and return user dict."""
        mock_db = AsyncMock()
        with patch("src.api.services.auth_service.db", mock_db):
            result = await svc.create_user(
                "jeanclaire", "a_very_long_password_123", "jean@virtue.com"
            )
        assert result["username"] == "jeanclaire"
        assert "id" in result
        assert result["is_premium"] is False
        mock_db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_authenticate_user_no_rows_returns_none(self, svc):
        mock_result = MagicMock()
        mock_result.rows = []
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        with patch("src.api.services.auth_service.db", mock_db):
            result = await svc.authenticate_user("nobody", "password")

        assert result is None

    @pytest.mark.asyncio
    async def test_authenticate_user_wrong_password_returns_none(self, svc):
        """ph.verify raises on bad password — method should catch and return None.

        argon2-cffi PasswordHasher.verify is a C-extension method and cannot be
        patched directly on an instance.  We replace svc.ph entirely with a mock.
        """
        mock_result = MagicMock()
        mock_result.rows = [("uid1", "jeanclaire", "$argon2...", False, "UTC")]
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        mock_ph = MagicMock()
        mock_ph.verify.side_effect = Exception("bad password")
        svc.ph = mock_ph

        with patch("src.api.services.auth_service.db", mock_db):
            result = await svc.authenticate_user("jeanclaire", "wrong_password")

        assert result is None

    @pytest.mark.asyncio
    async def test_authenticate_user_correct_password_returns_dict(self, svc):
        """When verify succeeds, method should return user dict."""
        mock_result = MagicMock()
        mock_result.rows = [("uid1", "jeanclaire", "hash_placeholder", False, "UTC")]
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        mock_ph = MagicMock()
        mock_ph.verify.return_value = None
        mock_ph.check_needs_rehash.return_value = False
        svc.ph = mock_ph

        with patch("src.api.services.auth_service.db", mock_db):
            result = await svc.authenticate_user("jeanclaire", "correct_password")

        assert result is not None
        assert result["username"] == "jeanclaire"
        assert result["id"] == "uid1"

    @pytest.mark.asyncio
    async def test_authenticate_user_rehashes_when_needed(self, svc):
        """If check_needs_rehash returns True, db.execute is called a second time."""
        mock_result = MagicMock()
        mock_result.rows = [("uid1", "jeanclaire", "old_hash", False, "UTC")]
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        mock_ph = MagicMock()
        mock_ph.verify.return_value = None
        mock_ph.check_needs_rehash.return_value = True
        mock_ph.hash.return_value = "new_hash"
        svc.ph = mock_ph

        with patch("src.api.services.auth_service.db", mock_db):
            await svc.authenticate_user("jeanclaire", "good_password")

        # First call = SELECT, second call = UPDATE for rehash
        assert mock_db.execute.await_count == 2

    @pytest.mark.asyncio
    async def test_get_user_by_id_not_found_returns_none(self, svc):
        mock_result = MagicMock()
        mock_result.rows = []
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        with patch("src.api.services.auth_service.db", mock_db):
            result = await svc.get_user_by_id("no-such-id")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_user_by_id_found(self, svc):
        mock_result = MagicMock()
        mock_result.rows = [("uid1", "jeanclaire", False, "Europe/London")]
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        with patch("src.api.services.auth_service.db", mock_db):
            result = await svc.get_user_by_id("uid1")

        assert result["id"] == "uid1"
        assert result["username"] == "jeanclaire"
        assert result["timezone"] == "Europe/London"

    @pytest.mark.asyncio
    async def test_get_user_by_id_null_timezone_defaults(self, svc):
        """Null timezone in DB should default to America/New_York."""
        mock_result = MagicMock()
        mock_result.rows = [("uid1", "jeanclaire", True, None)]
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        with patch("src.api.services.auth_service.db", mock_db):
            result = await svc.get_user_by_id("uid1")

        assert result["timezone"] == "America/New_York"

    @pytest.mark.asyncio
    async def test_update_user_timezone_returns_bool(self, svc):
        mock_result = MagicMock()
        mock_result.rows_affected = 1
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        with patch("src.api.services.auth_service.db", mock_db):
            ok = await svc.update_user_timezone("uid1", "Asia/Tokyo")

        assert ok is True

    @pytest.mark.asyncio
    async def test_update_user_timezone_no_rows_affected_returns_false(self, svc):
        mock_result = MagicMock()
        mock_result.rows_affected = 0
        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        with patch("src.api.services.auth_service.db", mock_db):
            ok = await svc.update_user_timezone("no-such-id", "UTC")

        assert ok is False


# ===========================================================================
# AvailabilityReason enum
# ===========================================================================


class TestAvailabilityReason:
    def test_enum_values(self):
        assert AvailabilityReason.STORY_GATE_NOT_MET.value == "story_gate_not_met"
        assert (
            AvailabilityReason.TICK_REQUIREMENT_NOT_MET.value
            == "tick_requirement_not_met"
        )
        assert AvailabilityReason.NOT_IN_WORLD.value == "not_in_world"
        assert AvailabilityReason.AVAILABLE.value == "available"


# ===========================================================================
# NPCLocationSerializer
# ===========================================================================


class TestNPCLocationSerializer:
    def test_serialize_basic(self):
        location = {
            "location_id": "loc_1",
            "map_name": "Grondia",
            "coords": [5, 10],
            "description": "A crossroads",
        }
        result = NPCLocationSerializer.serialize(location)
        assert result["location_id"] == "loc_1"
        assert result["map_name"] == "Grondia"
        assert result["coords"] == [5, 10]
        assert result["description"] == "A crossroads"

    def test_serialize_defaults(self):
        result = NPCLocationSerializer.serialize({})
        assert result["coords"] == [0, 0]
        assert result["description"] == "Unknown location"

    def test_deserialize_converts_coords_to_tuple(self):
        loc_dict = {"location_id": "l1", "coords": [3, 7]}
        result = NPCLocationSerializer.deserialize(loc_dict)
        assert isinstance(result["coords"], tuple)
        assert result["coords"] == (3, 7)

    def test_deserialize_defaults(self):
        result = NPCLocationSerializer.deserialize({})
        assert result["coords"] == (0, 0)
        assert result["description"] == "Unknown location"

    def test_get_location_no_locations(self):
        npc_data = {"locations": []}
        result = NPCLocationSerializer.get_location(npc_data, 100, {})
        assert result is None

    def test_get_location_story_gate_not_met(self):
        npc_data = {
            "locations": [
                {
                    "location_id": "loc_1",
                    "available_after_story": "ch01_complete",
                    "available_after_ticks": 0,
                    "coords": [1, 1],
                }
            ]
        }
        result = NPCLocationSerializer.get_location(npc_data, 100, {})
        assert result is None

    def test_get_location_story_gate_met(self):
        npc_data = {
            "locations": [
                {
                    "location_id": "loc_1",
                    "available_after_story": "ch01_complete",
                    "available_after_ticks": 0,
                    "coords": [1, 1],
                }
            ]
        }
        result = NPCLocationSerializer.get_location(
            npc_data, 100, {"ch01_complete": "1"}
        )
        assert result is not None
        assert result["location_id"] == "loc_1"

    def test_get_location_tick_requirement_not_met(self):
        npc_data = {
            "locations": [
                {
                    "location_id": "loc_1",
                    "available_after_ticks": 500,
                    "coords": [1, 1],
                }
            ]
        }
        result = NPCLocationSerializer.get_location(npc_data, 100, {})
        assert result is None

    def test_get_location_tick_requirement_met(self):
        npc_data = {
            "locations": [
                {
                    "location_id": "loc_1",
                    "available_after_ticks": 50,
                    "coords": [1, 1],
                }
            ]
        }
        result = NPCLocationSerializer.get_location(npc_data, 100, {})
        assert result is not None

    def test_is_at_location_true(self):
        npc_data = {
            "locations": [
                {"location_id": "market", "available_after_ticks": 0, "coords": [2, 3]}
            ]
        }
        assert (
            NPCLocationSerializer.is_at_location("gorran", "market", npc_data, 100, {})
            is True
        )

    def test_is_at_location_false_wrong_id(self):
        npc_data = {
            "locations": [
                {"location_id": "market", "available_after_ticks": 0, "coords": [2, 3]}
            ]
        }
        assert (
            NPCLocationSerializer.is_at_location("gorran", "tavern", npc_data, 100, {})
            is False
        )

    def test_is_at_location_false_no_location(self):
        npc_data = {"locations": []}
        assert (
            NPCLocationSerializer.is_at_location("gorran", "market", npc_data, 0, {})
            is False
        )


# ===========================================================================
# NPCAvailabilitySerializer
# ===========================================================================


class TestNPCAvailabilitySerializer:
    def _npc_available(self):
        return {
            "availability_conditions": {"story_gates": [], "min_ticks_after_gate": 0},
            "locations": [
                {"location_id": "market", "available_after_ticks": 0, "coords": [1, 1]}
            ],
        }

    def test_check_story_gates_none_required(self):
        ok, missing = NPCAvailabilitySerializer.check_story_gates(
            {"availability_conditions": {}}, {}
        )
        assert ok is True
        assert missing is None

    def test_check_story_gates_all_met(self):
        npc_data = {"availability_conditions": {"story_gates": ["ch01_done"]}}
        ok, missing = NPCAvailabilitySerializer.check_story_gates(
            npc_data, {"ch01_done": "1"}
        )
        assert ok is True

    def test_check_story_gates_one_missing(self):
        npc_data = {
            "availability_conditions": {"story_gates": ["ch01_done", "ch02_done"]}
        }
        ok, missing = NPCAvailabilitySerializer.check_story_gates(
            npc_data, {"ch01_done": "1"}
        )
        assert ok is False
        assert missing == "ch02_done"

    def test_check_tick_requirements_met(self):
        npc_data = {"availability_conditions": {"min_ticks_after_gate": 100}}
        ok, remaining = NPCAvailabilitySerializer.check_tick_requirements(
            npc_data, game_tick=200, gate_completion_tick=50
        )
        assert ok is True
        assert remaining is None

    def test_check_tick_requirements_not_met(self):
        npc_data = {"availability_conditions": {"min_ticks_after_gate": 100}}
        ok, remaining = NPCAvailabilitySerializer.check_tick_requirements(
            npc_data, game_tick=100, gate_completion_tick=50
        )
        assert ok is False
        assert remaining == 50  # 150 - 100

    def test_is_available_fully_available(self):
        npc_data = self._npc_available()
        ok, reason = NPCAvailabilitySerializer.is_available(npc_data, 100, {})
        assert ok is True
        assert reason == AvailabilityReason.AVAILABLE

    def test_is_available_story_gate_blocks(self):
        npc_data = {
            "availability_conditions": {"story_gates": ["ch01_done"]},
            "locations": [{"location_id": "x", "coords": [0, 0]}],
        }
        ok, reason = NPCAvailabilitySerializer.is_available(npc_data, 100, {})
        assert ok is False
        assert reason == AvailabilityReason.STORY_GATE_NOT_MET

    def test_is_available_tick_not_met(self):
        npc_data = {
            "availability_conditions": {"story_gates": [], "min_ticks_after_gate": 500},
            "locations": [{"location_id": "x", "coords": [0, 0]}],
        }
        ok, reason = NPCAvailabilitySerializer.is_available(npc_data, 10, {})
        assert ok is False
        assert reason == AvailabilityReason.TICK_REQUIREMENT_NOT_MET

    def test_is_available_no_locations(self):
        npc_data = {
            "availability_conditions": {"story_gates": [], "min_ticks_after_gate": 0},
            "locations": [],
        }
        ok, reason = NPCAvailabilitySerializer.is_available(npc_data, 100, {})
        assert ok is False
        assert reason == AvailabilityReason.NOT_IN_WORLD

    def test_serialize_available_npc(self):
        npc_data = self._npc_available()
        result = NPCAvailabilitySerializer.serialize(npc_data, 100, {})
        assert result["available"] is True
        assert result["reason"] == AvailabilityReason.AVAILABLE.value
        assert result["story_gates_met"] is True
        assert result["tick_requirements_met"] is True
        assert result["in_world"] is True
        assert result["current_location"] is not None

    def test_serialize_unavailable_npc(self):
        npc_data = {
            "availability_conditions": {
                "story_gates": ["needs_this"],
                "min_ticks_after_gate": 0,
            },
            "locations": [],
        }
        result = NPCAvailabilitySerializer.serialize(npc_data, 100, {})
        assert result["available"] is False
        assert result["story_gates_met"] is False
        assert result["missing_gate"] == "needs_this"


# ===========================================================================
# LocationNPCSerializer
# ===========================================================================


class TestLocationNPCSerializer:
    def _make_npc_data(self, npc_id, location_id, ticks=0):
        return {
            "npc_id": npc_id,
            "name": f"NPC_{npc_id}",
            "locations": [
                {
                    "location_id": location_id,
                    "available_after_ticks": ticks,
                    "coords": [1, 1],
                }
            ],
        }

    def test_get_npcs_at_location_single_match(self):
        all_npcs = [self._make_npc_data("gorran", "market")]
        result = LocationNPCSerializer.get_npcs_at_location("market", all_npcs, 100, {})
        assert len(result) == 1
        assert result[0]["npc_id"] == "gorran"
        assert result[0]["available"] is True

    def test_get_npcs_at_location_no_match(self):
        all_npcs = [self._make_npc_data("gorran", "market")]
        result = LocationNPCSerializer.get_npcs_at_location("tavern", all_npcs, 100, {})
        assert result == []

    def test_get_npcs_at_location_multiple(self):
        all_npcs = [
            self._make_npc_data("gorran", "market"),
            self._make_npc_data("mynx", "market"),
            self._make_npc_data("elder", "temple"),
        ]
        result = LocationNPCSerializer.get_npcs_at_location("market", all_npcs, 100, {})
        assert len(result) == 2
        ids = {n["npc_id"] for n in result}
        assert "gorran" in ids
        assert "mynx" in ids

    def test_serialize(self):
        all_npcs = [self._make_npc_data("gorran", "market")]
        result = LocationNPCSerializer.serialize(
            "market", "The Market", all_npcs, 100, {}
        )
        assert result["location_id"] == "market"
        assert result["location_name"] == "The Market"
        assert result["npc_count"] == 1


# ===========================================================================
# NPCTimelineSerializer
# ===========================================================================


class TestNPCTimelineSerializer:
    def test_get_timeline_entry_game_start(self):
        location = {
            "location_id": "loc_1",
            "available_after_story": "game_start",
            "available_after_ticks": 0,
            "description": "Starting area",
        }
        result = NPCTimelineSerializer.get_timeline_entry(location)
        assert result["trigger"] == "Game start"
        assert result["story_gate"] == "game_start"
        assert result["tick_requirement"] == 0

    def test_get_timeline_entry_with_story_gate(self):
        location = {
            "location_id": "loc_2",
            "available_after_story": "ch01_complete",
            "available_after_ticks": 50,
        }
        result = NPCTimelineSerializer.get_timeline_entry(location)
        assert "ch01_complete" in result["trigger"]
        assert "50" in result["trigger"]

    def test_get_timeline_entry_no_story_gate(self):
        location = {"location_id": "loc_3", "available_after_ticks": 0}
        result = NPCTimelineSerializer.get_timeline_entry(location)
        # No story gate means "game_start" should be treated as default trigger
        assert result["trigger"] == "Game start"

    def test_serialize_timeline(self):
        npc_data = {
            "npc_id": "gorran",
            "name": "Gorran",
            "locations": [
                {
                    "location_id": "loc_a",
                    "available_after_story": "game_start",
                    "available_after_ticks": 0,
                    "priority": 1,
                },
                {
                    "location_id": "loc_b",
                    "available_after_story": "ch01_done",
                    "available_after_ticks": 0,
                    "priority": 2,
                },
            ],
        }
        result = NPCTimelineSerializer.serialize(npc_data)
        assert result["npc_id"] == "gorran"
        assert len(result["timeline"]) == 2
        # sorted by priority
        assert result["timeline"][0]["location_id"] == "loc_a"

    def test_serialize_empty_locations(self):
        npc_data = {"npc_id": "gorran", "name": "Gorran", "locations": []}
        result = NPCTimelineSerializer.serialize(npc_data)
        assert result["timeline"] == []


# ===========================================================================
# NPCEventTriggerSerializer
# ===========================================================================


class TestNPCEventTriggerSerializer:
    def test_check_trigger_no_conditions(self):
        assert NPCEventTriggerSerializer.check_trigger_conditions({}, 100, {}) is True

    def test_check_trigger_story_gate_met(self):
        trigger = {"required_story_gate": "ch01_done"}
        assert (
            NPCEventTriggerSerializer.check_trigger_conditions(
                trigger, 100, {"ch01_done": "1"}
            )
            is True
        )

    def test_check_trigger_story_gate_not_met(self):
        trigger = {"required_story_gate": "ch01_done"}
        assert (
            NPCEventTriggerSerializer.check_trigger_conditions(trigger, 100, {})
            is False
        )

    def test_check_trigger_tick_not_met(self):
        trigger = {"required_min_ticks": 200}
        assert (
            NPCEventTriggerSerializer.check_trigger_conditions(trigger, 100, {})
            is False
        )

    def test_check_trigger_tick_met(self):
        trigger = {"required_min_ticks": 50}
        assert (
            NPCEventTriggerSerializer.check_trigger_conditions(trigger, 100, {}) is True
        )

    def test_get_active_triggers_all_active(self):
        npc_data = {
            "triggers": [
                {"id": "t1", "required_min_ticks": 0},
                {"id": "t2", "required_story_gate": "ch01_done"},
            ]
        }
        active = NPCEventTriggerSerializer.get_active_triggers(
            npc_data, 100, {"ch01_done": "1"}
        )
        assert len(active) == 2

    def test_get_active_triggers_some_inactive(self):
        npc_data = {
            "triggers": [
                {"id": "t1", "required_min_ticks": 0},
                {"id": "t2", "required_story_gate": "ch02_done"},
            ]
        }
        active = NPCEventTriggerSerializer.get_active_triggers(npc_data, 100, {})
        assert len(active) == 1
        assert active[0]["id"] == "t1"

    def test_get_active_triggers_no_triggers(self):
        npc_data = {"triggers": []}
        active = NPCEventTriggerSerializer.get_active_triggers(npc_data, 100, {})
        assert active == []
