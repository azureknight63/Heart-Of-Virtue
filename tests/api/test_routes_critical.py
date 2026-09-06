"""Critical integration tests for API routes.

Tests for:
- Auth routes: register, logout, validate
- World routes: current room, movement, explored map
- Combat routes: status, start, move
- Inventory routes: list, equipment, use, drop, floor pickup
- Player routes: status, stats
- Saves routes: create, list, load (cloud-only)
- NPC routes: room roster, chat
- Quest routes: xfailed -- no quest system exists (see NO_QUEST_SYSTEM)
- Error handling: malformed bodies and bad credentials

Every request below must name a URL that exists in ``app.url_map``, and every
assertion must name one status code. ``in [200, 404]`` against a URL with no
route is satisfied by the 404, so it tests nothing; the whole class of that
mistake is now caught by ``tests/api/test_route_prefix_contract.py``.

There is no ``/api/dialogue`` blueprint and no design for one: staged dialogue
reaches the client through ``/api/npc/chat/*`` and ``/api/world/events``, which
are covered here and in ``test_events_integration.py``. The two tests that
posted to ``/api/dialogue/*`` were deleted rather than xfailed, because a
marker on a URL that is never going to exist is a skip wearing a disguise.
"""

import pytest


#: Applied to every test in the quest family. ``strict=True`` so the day a
#: quest blueprint lands, the unexpected pass fails the suite and forces the
#: marker off instead of quietly masking a working feature.
NO_QUEST_SYSTEM = pytest.mark.xfail(
    reason=(
        "No quest system exists in this tree: no quest, quest-chain or "
        "npc-quest blueprint is registered in src/api/routes/, GameService "
        "carries no quest method, and src/ defines no Quest class -- so every "
        "/api/quests/*, /api/quest-chains/* and /api/npc/quests/* URL 404s."
    ),
    strict=True,
)


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
        """Test successful logout.

        Logout is unconditionally 200 (issue #493) -- see the sibling test
        below, which proves it succeeds even with no credential at all.
        """
        session_id, player, session_manager = authenticated_session

        response = client.post('/api/auth/logout',
                             headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code == 200
        assert response.get_json()['success'] is True

    def test_logout_without_auth_still_clears_the_cookie(self, client):
        """Logout is deliberately NOT @require_auth (issue #493).

        401-ing on an expired/unknown credential left the browser pinned to a
        dead cookie it could no longer clear itself, so logout now always
        succeeds and always clears the cookie.
        """
        response = client.post('/api/auth/logout')
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        set_cookie = response.headers.get('Set-Cookie', '')
        assert 'hov_session=' in set_cookie
        assert ('Max-Age=0' in set_cookie or 'Expires=' in set_cookie)

    def test_session_validation(self, client, authenticated_session):
        """A live session validates and reports its player id."""
        session_id, player, session_manager = authenticated_session

        response = client.get('/api/auth/validate',
                            headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code == 200
        data = response.get_json()
        assert data['valid'] is True
        assert data['player_id']


class TestWorldRoutes:
    """Test world navigation and location routes.

    There is no ``/api/world/room``; the current room is ``GET /api/world``,
    an arbitrary tile is ``GET /api/world/tile?x=&y=`` and the discovered map
    is ``GET /api/world/explored``.
    """

    @staticmethod
    def _room(client, session_id):
        """Return the current room payload, asserting the request succeeded."""
        response = client.get('/api/world',
                            headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        return data['room']

    def _assert_move(self, client, session_id, direction):
        """Move one step and assert the outcome the tile's own exits imply.

        This cross-checks two serializers against each other: a direction the
        room payload advertises must move the player to exactly the
        coordinates that payload named, and one it does not advertise must be
        refused by name. Neither branch accepts a range of statuses.
        """
        exits = self._room(client, session_id)['exits']

        response = client.post('/api/world/move',
                             json={'direction': direction},
                             headers={'Authorization': f'Bearer {session_id}'})
        data = response.get_json()

        if direction in exits:
            assert response.status_code == 200
            assert data['new_position'] == exits[direction]
        else:
            assert response.status_code == 400
            assert data['success'] is False
            assert data['error'] == f'Cannot go {direction} from here'

    def test_get_current_room_success(self, client, authenticated_session):
        """The current room carries a name, a description and its exits."""
        session_id, player, session_manager = authenticated_session

        room = self._room(client, session_id)
        assert room['name']
        assert room['description']
        assert isinstance(room['exits'], dict)
        assert room['x'] == player.location_x
        assert room['y'] == player.location_y

    def test_get_current_room_unauthenticated(self, client):
        """Test getting current room without authentication."""
        response = client.get('/api/world')
        assert response.status_code == 401
        assert response.get_json()['success'] is False

    def test_move_player_north(self, client, authenticated_session):
        """Test moving player north."""
        session_id, player, session_manager = authenticated_session
        self._assert_move(client, session_id, 'north')

    def test_move_player_south(self, client, authenticated_session):
        """Test moving player south."""
        session_id, player, session_manager = authenticated_session
        self._assert_move(client, session_id, 'south')

    def test_move_player_east(self, client, authenticated_session):
        """Test moving player east."""
        session_id, player, session_manager = authenticated_session
        self._assert_move(client, session_id, 'east')

    def test_move_player_west(self, client, authenticated_session):
        """Test moving player west."""
        session_id, player, session_manager = authenticated_session
        self._assert_move(client, session_id, 'west')

    def test_move_abbreviated_direction_is_rejected(self, client, authenticated_session):
        """The route takes full direction names only -- 'n' is not 'north'.

        Every directional test in this class used to send 'n'/'s'/'e'/'w' and
        accept ``in [200, 400]``, so all four passed on the same rejection.
        """
        session_id, player, session_manager = authenticated_session

        response = client.post('/api/world/move',
                             json={'direction': 'n'},
                             headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert data['error'].startswith("Invalid direction 'n'.")

    def test_move_invalid_direction(self, client, authenticated_session):
        """Test moving in invalid direction."""
        session_id, player, session_manager = authenticated_session

        response = client.post('/api/world/move',
                             json={'direction': 'invalid'},
                             headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert data['error'].startswith("Invalid direction 'invalid'.")

    def test_move_missing_direction(self, client, authenticated_session):
        """Test move request without direction."""
        session_id, player, session_manager = authenticated_session

        response = client.post('/api/world/move',
                             json={},
                             headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert data['error'] == 'Missing direction'

    def test_get_surrounding_tiles(self, client, authenticated_session):
        """The explored map records a tile once the client has read the room.

        A brand-new session has explored nothing: the starting tile is only
        recorded when something actually reads it, which every client does
        before it draws the map.
        """
        session_id, player, session_manager = authenticated_session
        headers = {'Authorization': f'Bearer {session_id}'}

        before = client.get('/api/world/explored', headers=headers)
        assert before.status_code == 200
        assert before.get_json()['explored_tiles'] == {}

        self._room(client, session_id)

        response = client.get('/api/world/explored', headers=headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True

        explored = data['explored_tiles']
        here = [key for key in explored
                if key.endswith(f':{player.location_x},{player.location_y}')]
        assert len(here) == 1
        assert 'exits' in explored[here[0]]


class TestCombatRoutes:
    """Test combat-related routes.

    ``/api/combat/move`` and ``/api/combat/start`` report a *refused* action
    with HTTP 200 and ``success: false`` in the body, reserving 4xx for
    malformed requests. That is the shipped contract the client reads, so it
    is what these tests assert -- the inconsistency is reported rather than
    silently normalised here.
    """

    def test_get_combat_status_no_combat(self, client, authenticated_session):
        """Test getting combat status when not in combat."""
        session_id, player, session_manager = authenticated_session

        response = client.get('/api/combat/status',
                            headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['combat_active'] is False
        assert data['battle_state'] is None

    def test_execute_move_without_combat(self, client, authenticated_session):
        """Executing a move outside combat is refused in the body, not the status."""
        session_id, player, session_manager = authenticated_session

        response = client.post('/api/combat/move',
                             json={'move_type': 'attack'},
                             headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is False
        assert data['error'] == 'Not in combat'

    def test_execute_move_missing_move_type(self, client, authenticated_session):
        """A malformed combat move -- no move_type -- is a 400."""
        session_id, player, session_manager = authenticated_session

        response = client.post('/api/combat/move',
                             json={},
                             headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert data['error'] == 'Missing move_type'

    def test_start_combat_requires_enemy_id(self, client, authenticated_session):
        """Starting combat without naming an enemy is a 400."""
        session_id, player, session_manager = authenticated_session

        response = client.post('/api/combat/start',
                             json={},
                             headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert data['error'] == 'Missing enemy_id'

    def test_start_combat_unknown_enemy(self, client, authenticated_session):
        """An enemy id that names nothing in the room is refused in the body."""
        session_id, player, session_manager = authenticated_session

        response = client.post('/api/combat/start',
                             json={'enemy_id': 'nonexistent'},
                             headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is False
        assert data['error'] == 'Enemy not found'


class TestInventoryRoutes:
    """Test inventory and item management routes."""

    def test_get_inventory_success(self, client, authenticated_session):
        """Test getting player inventory."""
        session_id, player, session_manager = authenticated_session

        response = client.get('/api/inventory',
                            headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        inventory = data['inventory']
        assert isinstance(inventory['items'], list)
        assert inventory['item_count'] == len(inventory['items'])

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

    def test_use_item_not_in_inventory(self, client, authenticated_session):
        """Using an item the player does not hold is a 400, not a crash."""
        session_id, player, session_manager = authenticated_session

        response = client.post('/api/inventory/use',
                             json={'item_id': 'nonexistent'},
                             headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert data['error'] == 'Item not found in inventory'

    def test_drop_item(self, client, authenticated_session):
        """Dropping an item the player does not hold is a 400."""
        session_id, player, session_manager = authenticated_session

        response = client.post('/api/inventory/drop',
                             json={'item_id': 'nonexistent'},
                             headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert data['error'] == 'Item not found in inventory'

    def test_pick_up_item(self, client, authenticated_session):
        """Picking an item up off the floor moves it out of the room.

        There is no ``/api/inventory/pickup`` and there will not be one: the
        ``take`` verb was removed in the terminal teardown, so pickup goes
        through ``/api/world/interact`` (``Item.take()`` /
        ``interact_with_target``).
        """
        session_id, player, session_manager = authenticated_session
        headers = {'Authorization': f'Bearer {session_id}'}

        room = client.get('/api/world', headers=headers).get_json()['room']
        floor_items = room['items']
        assert floor_items, 'starting tile is expected to carry a floor item'
        target = floor_items[0]

        response = client.post('/api/world/interact',
                             json={'target_id': target['id'], 'action': 'take'},
                             headers=headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['target_name'] == target['name']

        remaining = client.get('/api/world', headers=headers).get_json()['room']
        assert target['id'] not in [item['id'] for item in remaining['items']]

    def test_pick_up_unknown_target(self, client, authenticated_session):
        """An id that names nothing in the room is reported, not crashed on."""
        session_id, player, session_manager = authenticated_session

        response = client.post('/api/world/interact',
                             json={'target_id': 'nonexistent', 'action': 'take'},
                             headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is False
        assert data['message'] == 'Target not found.'


class TestPlayerStatusRoutes:
    """Test player status and character routes.

    The player blueprint is mounted at the API root: ``/api/status``,
    ``/api/stats``, ``/api/full-state``, ``/api/skills``. There is no
    ``/api/player`` prefix.
    """

    def test_get_player_status_success(self, client, authenticated_session):
        """Test getting player status."""
        session_id, player, session_manager = authenticated_session

        response = client.get('/api/status',
                            headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        status = data['status']
        assert status['name'] == player.name
        assert status['level'] == player.level
        assert status['hp'] == player.hp

    def test_get_player_stats(self, client, authenticated_session):
        """Test getting player stats."""
        session_id, player, session_manager = authenticated_session

        response = client.get('/api/stats',
                            headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        stats = data['stats']
        for attribute in ('strength', 'finesse', 'speed', 'endurance',
                          'charisma', 'intelligence', 'faith'):
            assert isinstance(stats[attribute], (int, float))

    def test_get_player_health(self, client, authenticated_session):
        """Health lives in the status payload; there is no player-health route."""
        session_id, player, session_manager = authenticated_session

        response = client.get('/api/status',
                            headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code == 200
        status = response.get_json()['status']
        assert status['hp'] == player.hp
        assert status['max_hp'] == player.maxhp
        assert 0 < status['hp'] <= status['max_hp']

    def test_get_player_experience(self, client, authenticated_session):
        """Experience lives in the status payload, not in /api/stats."""
        session_id, player, session_manager = authenticated_session

        response = client.get('/api/status',
                            headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code == 200
        status = response.get_json()['status']
        assert status['exp'] == player.exp
        assert isinstance(status['exp_to_next_level'], int)
        assert status['max_exp'] > 0


class TestSaveRoutes:
    """Test save and load routes."""

    # The save API is cloud-only: POST/GET /api/saves, POST /api/saves/<id>/load,
    # DELETE /api/saves/<id>. There are no /saves/auto, /saves/manual,
    # /saves/list or /saves/load endpoints. A test-bypass session carries no
    # db_user_id (see CLAUDE.md, "How auth works"), so every write path is
    # refused with 403 and the read path reports an empty list.

    def test_auto_save_without_db_user_is_refused(self, client, authenticated_session):
        """Auto-save on a session with no db_user_id is refused, not silently lost."""
        session_id, player, session_manager = authenticated_session

        response = client.post('/api/saves',
                             json={'is_autosave': True},
                             headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code == 403
        data = response.get_json()
        assert data['success'] is False
        assert 'registered account' in data['error']

    def test_manual_save_without_db_user_is_refused(self, client, authenticated_session):
        """Manual save on a session with no db_user_id is refused."""
        session_id, player, session_manager = authenticated_session

        response = client.post('/api/saves',
                             json={'name': 'checkpoint_1'},
                             headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code == 403
        data = response.get_json()
        assert data['success'] is False
        assert 'registered account' in data['error']

    def test_list_saves(self, client, authenticated_session):
        """Listing saves for a session with no db_user_id yields an empty list."""
        session_id, player, session_manager = authenticated_session

        response = client.get('/api/saves',
                            headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['saves'] == []

    def test_load_save(self, client, authenticated_session):
        """Loading a save on a session with no db_user_id is refused."""
        session_id, player, session_manager = authenticated_session

        response = client.post('/api/saves/nonexistent/load',
                             json={},
                             headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code == 403
        data = response.get_json()
        assert data['success'] is False
        assert 'registered account' in data['error']


class TestNPCRoutes:
    """Test NPC interaction routes.

    There is no NPC directory blueprint (no ``/api/npc/room``, no
    ``/api/npc/info``, no ``/api/npc/<id>/profile``): the room's NPC roster
    ships inside the room payload, and conversation is ``/api/npc/chat/*``.
    """

    def test_get_npcs_in_room(self, client, authenticated_session):
        """The room payload carries the NPC roster for the current tile."""
        session_id, player, session_manager = authenticated_session

        response = client.get('/api/world',
                            headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code == 200
        room = response.get_json()['room']
        npcs = room['npcs']
        assert isinstance(npcs, list)
        # The default starting tile is unpopulated (see test_default_starting_map).
        assert npcs == []

    def test_talk_to_npc(self, client, authenticated_session):
        """Opening chat with an NPC that is not here is a 400 naming the id."""
        session_id, player, session_manager = authenticated_session

        response = client.post('/api/npc/chat/open',
                             json={'npc_id': 'nonexistent'},
                             headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert data['error'] == "NPC 'nonexistent' not found"

    def test_talk_to_npc_missing_id(self, client, authenticated_session):
        """Opening chat with no npc_id at all is a 400."""
        session_id, player, session_manager = authenticated_session

        response = client.post('/api/npc/chat/open',
                             json={},
                             headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert data['error'] == 'npc_id is required'


@NO_QUEST_SYSTEM
class TestQuestRoutes:
    """Test quest-related routes.

    Every test here asserts the endpoint a quest feature would expose. All of
    them xfail today because no such blueprint is registered; the class-level
    ``NO_QUEST_SYSTEM`` marker is strict, so they fail the suite the moment
    one is.
    """

    def test_get_active_quests(self, client, authenticated_session):
        """Test getting active quests."""
        session_id, player, session_manager = authenticated_session

        response = client.get('/api/quests/active',
                            headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code == 200

    def test_get_available_quests(self, client, authenticated_session):
        """Test getting available quests."""
        session_id, player, session_manager = authenticated_session

        response = client.get('/api/quests/available',
                            headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code == 200

    def test_get_completed_quests(self, client, authenticated_session):
        """Test getting completed quests."""
        session_id, player, session_manager = authenticated_session

        response = client.get('/api/quests/completed',
                            headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code == 200

    def test_accept_quest(self, client, authenticated_session):
        """Test accepting a quest.

        The quest id is deliberately unknown, so a landed feature could
        answer 200 or 400; the only claim here is that the route exists.
        """
        session_id, player, session_manager = authenticated_session

        response = client.post('/api/quests/accept',
                             json={'quest_id': 'nonexistent'},
                             headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code != 404

    def test_abandon_quest(self, client, authenticated_session):
        """Test abandoning a quest (route-registered check, as above)."""
        session_id, player, session_manager = authenticated_session

        response = client.post('/api/quests/abandon',
                             json={'quest_id': 'nonexistent'},
                             headers={'Authorization': f'Bearer {session_id}'})
        assert response.status_code != 404


class TestErrorHandling:
    """Test error handling across routes.

    These previously requested ``/api/world/room``, which has no route: they
    got the same 404 for a missing header, an invalid session and a malformed
    header alike, and would have passed with authentication deleted entirely.
    They now use ``/api/world/tile``, a real ``@require_auth`` route, and
    assert the specific 401 body the middleware emits for each case.
    """

    def test_missing_json_body(self, client, authenticated_session):
        """A POST with no body at all is a 400 from the route's validation.

        ``/api/world/move`` reads its body with ``get_json(silent=True)``, so
        "no body" and "unparseable body" are indistinguishable to it; both
        land on the missing-field check below.
        """
        session_id, player, session_manager = authenticated_session

        response = client.post(
            '/api/world/move',
            headers={'Authorization': f'Bearer {session_id}'}
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert data['error'] == 'Missing direction'

    def test_invalid_json(self, client, authenticated_session):
        """Malformed JSON is a 400, never a 500."""
        session_id, player, session_manager = authenticated_session

        response = client.post(
            '/api/world/move',
            data='invalid json',
            content_type='application/json',
            headers={'Authorization': f'Bearer {session_id}'}
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert data['error'] == 'Missing direction'

    def test_expired_session(self, client):
        """A well-formed Bearer naming no live session is a 401."""
        response = client.get(
            '/api/world/tile',
            headers={'Authorization': 'Bearer expired_session_id'}
        )
        assert response.status_code == 401
        data = response.get_json()
        assert data['success'] is False
        assert data['error'] == 'Invalid or expired session'

    def test_malformed_auth_header(self, client):
        """An Authorization header that is not a Bearer is a 401."""
        response = client.get(
            '/api/world/tile',
            headers={'Authorization': 'InvalidBearer token'}
        )
        assert response.status_code == 401
        data = response.get_json()
        assert data['success'] is False
        assert data['error'] == 'Missing or invalid session credentials'

    def test_missing_auth_header(self, client):
        """No credential at all is a 401."""
        response = client.get('/api/world/tile')
        assert response.status_code == 401
        data = response.get_json()
        assert data['success'] is False
        assert data['error'] == 'Missing or invalid session credentials'
