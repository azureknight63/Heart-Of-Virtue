#!/usr/bin/env python
"""Test world endpoints with real universe."""

import sys
import json
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / 'src'))

from flask import Flask
from src.api.app import create_app
from src.api.config import TestingConfig

app, socketio = create_app(TestingConfig)

with app.app_context():
    with app.test_client() as client:
        print("=" * 70)
        print("Testing World Movement with Real Universe")
        print("=" * 70)

        # Create session
        print("\n[1] Creating session...")
        resp = client.post('/auth/login', json={"username": "TestPlayer"})
        data = resp.get_json()
        print(f"Response: {data}")
        session_id = data['session_id']
        print(f"Session created: {session_id[:10]}...")

        headers = {"Authorization": f"Bearer {session_id}"}

        # Get current room
        print("\n[2] GET /world/ - Current room")
        resp = client.get('/world/', headers=headers)
        print(f"Status: {resp.status_code}")
        data = resp.get_json()
        print(f"Response keys: {data.keys()}")
        room = data.get('room') or data.get('data')
        print(f"Status: {resp.status_code}")
        print(f"Position: ({room['x']}, {room['y']})")
        print(f"Description: {room['description'][:50]}...")
        print(f"Exits: {list(room['exits'].keys())}")

        # Test movement SOUTH (valid)
        print("\n[3] POST /world/move south (VALID)")
        resp = client.post('/world/move',
                          json={"direction": "south"},
                          headers=headers)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.get_json()['room']
            print(f"New position: ({data['x']}, {data['y']})")
            print(f"New room: {data['description'][:50]}...")
            print(f"New exits: {list(data['exits'].keys())}")
        else:
            print(f"Error: {resp.get_json()['error']}")

        # Test movement EAST (valid from (1,1))
        print("\n[4] POST /world/move east (VALID from (1,1))")
        # First go back to (1,1)
        resp = client.post('/world/move',
                          json={"direction": "north"},
                          headers=headers)
        print(f"Returned to starting position: ({resp.get_json()['room']['x']}, {resp.get_json()['room']['y']})")

        # Now move east
        resp = client.post('/world/move',
                          json={"direction": "east"},
                          headers=headers)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            data = resp.get_json()['room']
            print(f"New position: ({data['x']}, {data['y']})")
            print(f"New room: {data['description'][:50]}...")
            print(f"New exits: {list(data['exits'].keys())}")
        else:
            print(f"Error: {resp.get_json()['error']}")

        # Test movement NORTH (invalid from (1,1))
        print("\n[5] POST /world/move north (INVALID from (1,1))")
        # Go back to (1,1)
        resp = client.post('/world/move',
                          json={"direction": "west"},
                          headers=headers)
        if resp.status_code == 200:
            pos = resp.get_json()['room']
            print(f"Returned to: ({pos['x']}, {pos['y']})")

        resp = client.post('/world/move',
                          json={"direction": "north"},
                          headers=headers)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 400:
            print(f"✅ Correctly blocked: {resp.get_json()['error']}")
        else:
            print(f"❌ Should have been blocked")
            print(f"Response: {resp.get_json()}")

        print("\n" + "=" * 70)
        print("Movement testing complete!")
        print("=" * 70)
