#!/usr/bin/env python
"""Test world endpoints with real universe."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / 'src'))

from api.app import create_app
from api.config import DevelopmentConfig

print('='*70)
print('Testing World Endpoints with Real Universe')
print('='*70)

app, socketio = create_app(DevelopmentConfig)
client = app.test_client()

print('\n[1] Creating session...')
resp = client.post('/auth/login', json={'username': 'testplayer'}, content_type='application/json')
if resp.status_code == 201:
    session_id = resp.get_json()['session_id']
    auth_header = {'Authorization': f'Bearer {session_id}'}
    print(f'Session created: {session_id[:8]}...')
else:
    print(f'ERROR: Could not create session: {resp.status_code}')
    sys.exit(1)

print('\n[2] Testing GET /world/')
resp = client.get('/world/', headers=auth_header)
print(f'Status: {resp.status_code}')
if resp.status_code == 200:
    data = resp.get_json()
    if data.get('success'):
        room = data.get('room', {})
        print(f'Position: ({room.get("x")}, {room.get("y")})')
        print(f'Description: {room.get("description", "N/A")[:50]}...')
        print(f'Items: {len(room.get("items", []))}')
        print(f'NPCs: {len(room.get("npcs", []))}')
        print(f'Objects: {len(room.get("objects", []))}')
        print(f'Exits: {list(room.get("exits", {}).keys())}')
    else:
        print(f'API Error: {data.get("error")}')
else:
    print(f'HTTP Error: {resp.get_json()}')

print('\n[3] Testing GET /world/tile?x=2&y=2')
resp = client.get('/world/tile?x=2&y=2', headers=auth_header)
print(f'Status: {resp.status_code}')
if resp.status_code == 200:
    data = resp.get_json()
    if data.get('success'):
        tile = data.get('tile', {})
        print(f'Tile at (2, 2): Found')
        print(f'Items: {len(tile.get("items", []))}')
        print(f'NPCs: {len(tile.get("npcs", []))}')
    else:
        print(f'API Error: {data.get("error")}')
else:
    print(f'HTTP Error: {resp.get_json()}')

print('\n[4] Testing POST /world/move')
resp = client.post('/world/move', json={'direction': 'north'}, headers=auth_header, content_type='application/json')
print(f'Status: {resp.status_code}')
if resp.status_code == 200:
    data = resp.get_json()
    if data.get('success'):
        print(f'Moved: {data.get("moved")}')
        if data.get('moved'):
            new_pos = data.get('new_position', {})
            print(f'New position: ({new_pos.get("x")}, {new_pos.get("y")})')
            print(f'Events triggered: {len(data.get("events_triggered", []))}')
        else:
            print(f'Movement blocked: {data.get("error", "Unknown reason")}')
    else:
        print(f'API Error: {data.get("error")}')
else:
    print(f'HTTP Error: {resp.get_json()}')

print('\n' + '='*70)
print('World endpoint testing complete!')
print('='*70)
