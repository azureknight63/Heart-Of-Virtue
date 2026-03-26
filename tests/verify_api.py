#!/usr/bin/env python
"""Manual verification script for the Heart of Virtue API."""

import sys
from pathlib import Path
import json

# Setup paths
ROOT = Path(__file__).resolve().parent
SRC_DIR = ROOT / "src"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SRC_DIR))

try:
    from src.api.app import create_app
    from src.api.config import DevelopmentConfig

    print("\n" + "="*70)
    print("Heart of Virtue API - Manual Verification")
    print("="*70 + "\n")

    # Create app
    print("[1/5] Creating Flask app...")
    app, socketio = create_app(DevelopmentConfig)
    print("      ✓ App created successfully")

    # Create test client
    print("[2/5] Creating test client...")
    client = app.test_client()
    print("      ✓ Test client created")

    # Test health endpoint
    print("[3/5] Testing /health endpoint...")
    resp = client.get('/health')
    print(f"      Status: {resp.status_code}")
    print(f"      Response: {json.dumps(resp.get_json(), indent=8)}")

    # Test API info endpoint
    print("\n[4/5] Testing /api/info endpoint...")
    resp = client.get('/api/info')
    print(f"      Status: {resp.status_code}")
    print(f"      Response: {json.dumps(resp.get_json(), indent=8)}")

    # Test auth endpoint
    print("\n[5/5] Testing /auth/login endpoint...")
    resp = client.post(
        '/auth/login',
        json={'username': 'testplayer'},
        content_type='application/json'
    )
    print(f"      Status: {resp.status_code}")
    data = resp.get_json()
    if 'session_id' in data:
        print(f"      Session ID: {data['session_id']}")
        print(f"      Player ID: {data.get('player_id', 'N/A')}")
        session_id = data['session_id']

        # Test authenticated endpoint with session
        print(f"\n[BONUS] Testing authenticated endpoint /player/status...")
        resp = client.get(
            '/player/status',
            headers={'Authorization': f'Bearer {session_id}'}
        )
        print(f"      Status: {resp.status_code}")
        print(f"      Response: {json.dumps(resp.get_json(), indent=8)}")

    print("\n" + "="*70)
    print("✓ All endpoint tests completed successfully!")
    print("="*70 + "\n")

except Exception as e:
    print(f"\n✗ Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
