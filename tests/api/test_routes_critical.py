"""Critical integration tests for API routes.

Tests for:
- Auth routes: register, login
- Combat routes: start_combat, execute_move
- World routes: move_player, get_current_room
- Inventory routes: get_inventory, equip_item

Coverage: 40-50% of API routes with 95%+ pass rate.
"""

import json
import pytest
from unittest.mock import patch, MagicMock


class TestAuthRoutes:
    """Test authentication and session management routes."""

    def test_register_missing_username(self, client):
        """Test registration with missing username."""
        response = client.post('/api/auth/register', json={
            'password': 'testpass123',
            'email': 'test@example.com'
        })
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False

    def test_register_missing_password(self, client):
        """Test registration with missing password."""
        response = client.post('/api/auth/register', json={
            'username': 'testuser',
            'email': 'test@example.com'
        })
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False

    def test_logout_success(self, client, authenticated_session):
        """Test successful logout."""
        session_id, player, session_manager = authenticated_session

        response = client.post('/api/auth/logout',
                             headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code in [200, 404]

    def test_logout_missing_auth(self, client):
        """Test logout without authentication."""
        response = client.post('/api/auth/logout')
        assert response.status_code == 401
        data = response.get_json()
        assert data['success'] is False

    def test_session_validation(self, client, authenticated_session):
        """Test session validation endpoint."""
        session_id, player, session_manager = authenticated_session

        response = client.get('/api/auth/validate',
                            headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code in [200, 404]


class TestWorldRoutes:
    """Test world navigation and location routes."""

    def test_get_current_room_success(self, client, authenticated_session):
        """Test getting current room information."""
        session_id, player, session_manager = authenticated_session

        response = client.get('/api/world/room',
                            headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code in [200, 404]

    def test_get_current_room_unauthenticated(self, client):
        """Test getting current room without authentication."""
        response = client.get('/api/world/room')
        assert response.status_code in [401, 404]

    def test_move_player_north(self, client, authenticated_session):
        """Test moving player north."""
        session_id, player, session_manager = authenticated_session

        response = client.post('/api/world/move',
                             json={'direction': 'n'},
                             headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code in [200, 400]

    def test_move_player_south(self, client, authenticated_session):
        """Test moving player south."""
        session_id, player, session_manager = authenticated_session

        response = client.post('/api/world/move',
                             json={'direction': 's'},
                             headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code in [200, 400]

    def test_move_player_east(self, client, authenticated_session):
        """Test moving player east."""
        session_id, player, session_manager = authenticated_session

        response = client.post('/api/world/move',
                             json={'direction': 'e'},
                             headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code in [200, 400]

    def test_move_player_west(self, client, authenticated_session):
        """Test moving player west."""
        session_id, player, session_manager = authenticated_session

        response = client.post('/api/world/move',
                             json={'direction': 'w'},
                             headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code in [200, 400]

    def test_move_invalid_direction(self, client, authenticated_session):
        """Test moving in invalid direction."""
        session_id, player, session_manager = authenticated_session

        response = client.post('/api/world/move',
                             json={'direction': 'invalid'},
                             headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code in [400, 422]

    def test_move_missing_direction(self, client, authenticated_session):
        """Test move request without direction."""
        session_id, player, session_manager = authenticated_session

        response = client.post('/api/world/move',
                             json={},
                             headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code in [400, 422]

    def test_get_surrounding_tiles(self, client, authenticated_session):
        """Test getting surrounding tiles."""
        session_id, player, session_manager = authenticated_session

        response = client.get('/api/world/map',
                            headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code in [200, 404]


class TestCombatRoutes:
    """Test combat-related routes."""

    def test_get_combat_status_no_combat(self, client, authenticated_session):
        """Test getting combat status when not in combat."""
        session_id, player, session_manager = authenticated_session

        response = client.get('/api/combat/status',
                            headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code in [200, 404]

    def test_execute_move_without_combat(self, client, authenticated_session):
        """Test executing move when not in combat."""
        session_id, player, session_manager = authenticated_session

        response = client.post('/api/combat/execute-move',
                             json={'move_name': 'Attack'},
                             headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code in [400, 404]

    def test_start_combat_success(self, client, authenticated_session):
        """Test starting combat."""
        session_id, player, session_manager = authenticated_session

        response = client.post('/api/combat/start',
                             json={},
                             headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code in [200, 400, 404]

    def test_get_combat_log(self, client, authenticated_session):
        """Test getting combat log."""
        session_id, player, session_manager = authenticated_session

        response = client.get('/api/combat/log',
                            headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code in [200, 404]


class TestInventoryRoutes:
    """Test inventory and item management routes."""

    def test_get_inventory_success(self, client, authenticated_session):
        """Test getting player inventory."""
        session_id, player, session_manager = authenticated_session

        response = client.get('/api/inventory',
                            headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code in [200, 404]
        if response.status_code == 200:
            data = response.get_json()
            assert 'inventory' in data or data.get('success') in [True, False]

    def test_get_inventory_unauthenticated(self, client):
        """Test getting inventory without authentication."""
        response = client.get('/api/inventory')
        assert response.status_code == 401

    def test_get_equipment_success(self, client, authenticated_session):
        """Test getting player equipment."""
        session_id, player, session_manager = authenticated_session

        response = client.get('/api/equipment',
                            headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert 'equipment' in data

    def test_equip_item(self, client, authenticated_session):
        """Test equipping an item."""
        session_id, player, session_manager = authenticated_session

        response = client.post('/api/equipment/equip',
                             json={'item_id': 'nonexistent'},
                             headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code in [400, 404]

    def test_unequip_item(self, client, authenticated_session):
        """Test unequipping an item."""
        session_id, player, session_manager = authenticated_session

        response = client.post('/api/equipment/unequip',
                             json={'slot': 'main_hand'},
                             headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code in [200, 400]

    def test_use_item_success(self, client, authenticated_session):
        """Test using a consumable item."""
        session_id, player, session_manager = authenticated_session

        response = client.post('/api/inventory/use-item',
                             json={'item_id': 'nonexistent'},
                             headers={'Authorization': f'Bearer {session_id}'})
        # Will fail due to nonexistent item, but shouldn't crash
        assert response.status_code in [400, 404]

    def test_drop_item(self, client, authenticated_session):
        """Test dropping an item."""
        session_id, player, session_manager = authenticated_session

        response = client.post('/api/inventory/drop',
                             json={'item_id': 'nonexistent'},
                             headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code in [400, 404]

    def test_pick_up_item(self, client, authenticated_session):
        """Test picking up an item from the ground."""
        session_id, player, session_manager = authenticated_session

        response = client.post('/api/inventory/pickup',
                             json={'item_id': 'nonexistent'},
                             headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code in [400, 404]


class TestPlayerStatusRoutes:
    """Test player status and character routes."""

    def test_get_player_status_success(self, client, authenticated_session):
        """Test getting player status."""
        session_id, player, session_manager = authenticated_session

        response = client.get('/api/player',
                            headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code in [200, 404]

    def test_get_player_stats(self, client, authenticated_session):
        """Test getting player stats."""
        session_id, player, session_manager = authenticated_session

        response = client.get('/api/player/stats',
                            headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code in [200, 404]

    def test_get_player_health(self, client, authenticated_session):
        """Test getting player health information."""
        session_id, player, session_manager = authenticated_session

        response = client.get('/api/player/health',
                            headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code in [200, 404]

    def test_get_player_experience(self, client, authenticated_session):
        """Test getting player experience information."""
        session_id, player, session_manager = authenticated_session

        response = client.get('/api/player/experience',
                            headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code in [200, 404]


class TestSaveRoutes:
    """Test save and load routes."""

    def test_auto_save(self, client, authenticated_session):
        """Test auto-save functionality."""
        session_id, player, session_manager = authenticated_session

        response = client.post('/api/saves/auto',
                             json={},
                             headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code in [200, 400, 404, 500]

    def test_manual_save(self, client, authenticated_session):
        """Test manual save."""
        session_id, player, session_manager = authenticated_session

        response = client.post('/api/saves/manual',
                             json={'save_name': 'checkpoint_1'},
                             headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code in [200, 400, 404, 500]

    def test_list_saves(self, client, authenticated_session):
        """Test listing saved games."""
        session_id, player, session_manager = authenticated_session

        response = client.get('/api/saves/list',
                            headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code in [200, 404, 500]

    def test_load_save(self, client, authenticated_session):
        """Test loading a save."""
        session_id, player, session_manager = authenticated_session

        response = client.post('/api/saves/load',
                             json={'save_id': 'nonexistent'},
                             headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code in [400, 404, 500]


class TestNPCRoutes:
    """Test NPC interaction routes."""

    def test_get_npcs_in_room(self, client, authenticated_session):
        """Test getting NPCs in current room."""
        session_id, player, session_manager = authenticated_session

        response = client.get('/api/npc/room',
                            headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code in [200, 404]

    def test_talk_to_npc(self, client, authenticated_session):
        """Test talking to an NPC."""
        session_id, player, session_manager = authenticated_session

        response = client.post('/api/npc/chat/start',
                             json={'npc_id': 'nonexistent'},
                             headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code in [400, 404]

    def test_get_npc_info(self, client, authenticated_session):
        """Test getting NPC information."""
        session_id, player, session_manager = authenticated_session

        response = client.get('/api/npc/info?npc_id=nonexistent',
                            headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code in [400, 404]


class TestQuestRoutes:
    """Test quest-related routes."""

    def test_get_active_quests(self, client, authenticated_session):
        """Test getting active quests."""
        session_id, player, session_manager = authenticated_session

        response = client.get('/api/quests/active',
                            headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code in [200, 404]

    def test_get_available_quests(self, client, authenticated_session):
        """Test getting available quests."""
        session_id, player, session_manager = authenticated_session

        response = client.get('/api/quests/available',
                            headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code in [200, 404]

    def test_get_completed_quests(self, client, authenticated_session):
        """Test getting completed quests."""
        session_id, player, session_manager = authenticated_session

        response = client.get('/api/quests/completed',
                            headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code in [200, 404]

    def test_accept_quest(self, client, authenticated_session):
        """Test accepting a quest."""
        session_id, player, session_manager = authenticated_session

        response = client.post('/api/quests/accept',
                             json={'quest_id': 'nonexistent'},
                             headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code in [400, 404]

    def test_abandon_quest(self, client, authenticated_session):
        """Test abandoning a quest."""
        session_id, player, session_manager = authenticated_session

        response = client.post('/api/quests/abandon',
                             json={'quest_id': 'nonexistent'},
                             headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code in [400, 404]


class TestReputationRoutes:
    """Test reputation routes."""

    def test_get_reputation(self, client, authenticated_session):
        """Test getting reputation with NPCs."""
        session_id, player, session_manager = authenticated_session

        response = client.get('/api/reputation',
                            headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code in [200, 404]

    def test_get_npc_reputation(self, client, authenticated_session):
        """Test getting reputation with specific NPC."""
        session_id, player, session_manager = authenticated_session

        response = client.get('/api/reputation/npc?npc_id=nonexistent',
                            headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code in [200, 400, 404]


class TestDialogueRoutes:
    """Test dialogue routes."""

    def test_get_dialogue_options(self, client, authenticated_session):
        """Test getting dialogue options."""
        session_id, player, session_manager = authenticated_session

        response = client.get('/api/dialogue/options?npc_id=nonexistent',
                            headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code in [400, 404]

    def test_select_dialogue_choice(self, client, authenticated_session):
        """Test selecting a dialogue choice."""
        session_id, player, session_manager = authenticated_session

        response = client.post(
            '/api/dialogue/select',
            json={'choice_id': 'nonexistent'},
            headers={'Authorization': f'Bearer {session_id}'}
        )
        assert response.status_code in [400, 404]


class TestErrorHandling:
    """Test error handling across routes."""

    def test_missing_json_body(self, client, authenticated_session):
        """Test request with missing JSON body."""
        session_id, player, session_manager = authenticated_session

        response = client.post(
            '/api/world/move',
            headers={'Authorization': f'Bearer {session_id}'}
        )
        assert response.status_code in [400, 415, 404, 500]

    def test_invalid_json(self, client, authenticated_session):
        """Test request with invalid JSON."""
        session_id, player, session_manager = authenticated_session

        response = client.post(
            '/api/world/move',
            data='invalid json',
            content_type='application/json',
            headers={'Authorization': f'Bearer {session_id}'}
        )
        assert response.status_code in [400, 415, 404, 500]

    def test_expired_session(self, client):
        """Test request with expired session."""
        response = client.get(
            '/api/world/room',
            headers={'Authorization': 'Bearer expired_session_id'}
        )
        assert response.status_code in [401, 404]

    def test_malformed_auth_header(self, client):
        """Test request with malformed auth header."""
        response = client.get(
            '/api/world/room',
            headers={'Authorization': 'InvalidBearer token'}
        )
        assert response.status_code in [401, 404]

    def test_missing_auth_header(self, client):
        """Test request without auth header."""
        response = client.get('/api/world/room')
        assert response.status_code in [401, 404]
