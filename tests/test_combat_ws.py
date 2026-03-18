
import os
import sys
from pathlib import Path
import unittest
import json

# Set testing environment variables
os.environ["FLASK_ENV"] = "testing"
os.environ["CONFIG_FILE"] = "config_phase4_testing.ini"

# Add src to path for proper module imports
ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from src.api.app import create_app
from src.api.config import TestingConfig
from flask_socketio import SocketIOTestClient

class TestCombatWebSocket(unittest.TestCase):
    def setUp(self):
        self.app, self.socketio = create_app(TestingConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        
        # Create a session
        response = self.client.post('/api/auth/login', json={
            "username": "TestPlayer",
            "password": "password"
        })
        self.session_id = response.get_json()['data']['session_id']
        self.auth_headers = {"Authorization": f"Bearer {self.session_id}"}

    def tearDown(self):
        self.app_context.pop()

    def test_combat_websocket_flow(self):
        # 1. Connect to WebSocket
        ws_client = self.socketio.test_client(self.app)
        self.assertTrue(ws_client.is_connected())
        
        # 2. Join combat room
        ws_client.emit('combat:join', {'session_id': self.session_id})
        
        # 3. Verify join response (if any) or just proceed
        # In our sockets.py, joining a room doesn't emit a confirmation yet, but we can check room membership if needed
        # However, test_client doesn't easily expose room membership on the server side.
        
        # 4. Start combat via REST
        # First, find an enemy in the current room
        room_resp = self.client.get('/api/world/', headers=self.auth_headers)
        room_data = room_resp.get_json().get('room', {})
        print(f"[DEBUG] Room data (inner): {json.dumps(room_data, indent=2)}")
        
        enemies = room_data.get('npcs', [])
        if not enemies:
            # Try searching to find hidden enemies
            self.client.post('/api/world/search', headers=self.auth_headers)
            room_resp = self.client.get('/api/world/', headers=self.auth_headers)
            room_data = room_resp.get_json().get('room', {})
            enemies = room_data.get('npcs', [])
            
        self.assertTrue(len(enemies) > 0, "No enemies found in current room for testing")
        enemy_id = enemies[0]['id']
        print(f"[DEBUG] Starting combat with enemy: {enemy_id}")

        response = self.client.post('/api/combat/start', 
                                   headers=self.auth_headers,
                                   json={"enemy_id": enemy_id})
        
        if response.status_code != 201:
            print(f"[DEBUG] Combat start failed: {response.get_json()}")
        self.assertEqual(response.status_code, 201)
        
        # 5. Check for 'combat:started' event on WebSocket
        received = ws_client.get_received()
        
        # Filter for combat:started
        started_events = [e for e in received if e['name'] == 'combat:started']
        self.assertTrue(len(started_events) > 0, "Should have received combat:started event")
        
        # 6. Execute a move via REST
        response = self.client.post('/api/combat/move',
                                   headers=self.auth_headers,
                                   json={
                                       "move_type": "attack",
                                       "move_id": "0",  # Index of Attack move
                                       "target_id": "enemy_1"
                                   })
        
        self.assertEqual(response.status_code, 200)
        
        # 7. Check for 'combat:log' and 'combat:update' events
        received = ws_client.get_received()
        
        log_events = [e for e in received if e['name'] == 'combat:log']
        update_events = [e for e in received if e['name'] == 'combat:update']
        turn_events = [e for e in received if e['name'] == 'combat:turn']
        
        self.assertTrue(len(log_events) > 0, "Should have received combat:log events")
        self.assertTrue(len(update_events) > 0, "Should have received combat:update event")
        self.assertTrue(len(turn_events) > 0, "Should have received combat:turn event")
        
        # 8. Verify event data
        last_update = update_events[-1]['args'][0]
        self.assertIn('battle_state', last_update)
        self.assertTrue(last_update['battle_state']['awaiting_input'])

if __name__ == '__main__':
    unittest.main()
