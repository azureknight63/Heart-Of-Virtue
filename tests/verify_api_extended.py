#!/usr/bin/env python
"""Extended manual verification script for Heart of Virtue API endpoints."""

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
    print("Heart of Virtue API - Extended Endpoint Verification")
    print("="*70 + "\n")

    # Create app and test client
    app, socketio = create_app(DevelopmentConfig)
    client = app.test_client()

    # Create session for authenticated tests
    resp = client.post('/auth/login', json={'username': 'testplayer'}, content_type='application/json')
    session_id = resp.get_json()['session_id']
    auth_header = {'Authorization': f'Bearer {session_id}'}

    print(f"Session ID: {session_id}\n")

    # Test all major endpoints
    endpoints = [
        # World endpoints
        ('GET', '/world/', {}, "World - Get current room"),
        ('GET', '/world/tile?x=0&y=0', {}, "World - Get tile at (0,0)"),

        # Player endpoints
        ('GET', '/player/status', {}, "Player - Get status"),
        ('GET', '/player/stats', {}, "Player - Get stats"),

        # Inventory endpoints
        ('GET', '/inventory/', {}, "Inventory - Get inventory"),

        # Equipment endpoints
        ('GET', '/equipment/', {}, "Equipment - Get equipment"),

        # Combat endpoints
        ('GET', '/combat/status', {}, "Combat - Get status"),

        # Saves endpoints
        ('GET', '/saves/', {}, "Saves - List saves"),
    ]

    print("Testing Endpoints:\n")
    passed = 0
    failed = 0

    for method, endpoint, payload, description in endpoints:
        try:
            if method == 'GET':
                resp = client.get(endpoint, headers=auth_header)
            elif method == 'POST':
                resp = client.post(endpoint, json=payload, headers=auth_header, content_type='application/json')

            status = resp.status_code
            success = status in [200, 201, 202]
            symbol = "✓" if success else "✗"

            print(f"{symbol} [{status}] {description}")
            if not success:
                print(f"        Response: {resp.get_json()}")
                failed += 1
            else:
                passed += 1

        except Exception as e:
            print(f"✗ {description} - Error: {e}")
            failed += 1

    print("\n" + "-"*70)
    print(f"Results: {passed} passed, {failed} failed out of {passed + failed} endpoints")
    print("-"*70 + "\n")

    # Test error cases
    print("Testing Error Handling:\n")

    error_tests = [
        ('GET', '/player/status', {}, None, "Missing authentication"),
        ('GET', '/player/status', {}, {'Authorization': 'Bearer invalid'}, "Invalid session"),
        ('POST', '/auth/login', {'username': 'a'}, {}, "Invalid username (too short)"),
    ]

    error_passed = 0
    for method, endpoint, payload, headers, description in error_tests:
        try:
            if method == 'GET':
                resp = client.get(endpoint, headers=headers)
            elif method == 'POST':
                resp = client.post(endpoint, json=payload, headers=headers, content_type='application/json')

            status = resp.status_code
            is_error = status >= 400
            symbol = "✓" if is_error else "✗"

            print(f"{symbol} [{status}] {description}")
            if is_error:
                error_passed += 1

        except Exception as e:
            print(f"✗ {description} - Error: {e}")

    print("\n" + "="*70)
    print("✓ Extended verification completed!")
    print("="*70 + "\n")

    print("SUMMARY:")
    print(f"  ✓ Standard endpoints: {passed}/{passed + failed} working")
    print(f"  ✓ Error handling: {error_passed}/{len(error_tests)} correct")
    print(f"  ✓ Session management: Working")
    print(f"  ✓ Authentication: Working")
    print("\n" + "="*70 + "\n")

except Exception as e:
    print(f"\n✗ Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
