#!/usr/bin/env python
"""Debug invalid direction test."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / 'src'))

from src.api.app import create_app
from src.api.config import TestingConfig

app, socketio = create_app(TestingConfig)

with app.app_context():
    with app.test_client() as client:
        # Create session
        resp = client.post('/auth/login', json={"username": "Test"})
        session_id = resp.get_json()['session_id']
        headers = {"Authorization": f"Bearer {session_id}"}
        
        # Get current room
        resp = client.get('/world/', headers=headers)
        room = resp.get_json()['room']
        print(f"Player at ({room['x']}, {room['y']})")
        print(f"Valid exits: {list(room['exits'].keys())}")
        
        # Try southwest
        resp = client.post('/world/move', json={"direction": "southwest"}, headers=headers)
        print(f"\nMove southwest: {resp.status_code}")
        print(f"Response: {resp.get_json()}")
