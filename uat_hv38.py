#!/usr/bin/env python3
"""HV-38 UAT Script - Comprehensive endpoint testing"""

import requests
import json
import sys

BASE_URL = "http://localhost:5000"

def print_test(name, status, data):
    """Print test result"""
    print(f"\n{'='*60}")
    print(f"TEST: {name}")
    print(f"{'='*60}")
    print(f"Status: {status}")
    print(f"Response: {json.dumps(data, indent=2)}")

def test_login():
    """Test login endpoint"""
    response = requests.post(f"{BASE_URL}/auth/login", json={"username": "TestPlayer"})
    print_test("LOGIN", response.status_code, response.json())
    
    if response.status_code == 201:
        return response.json()["session_id"]
    return None

def test_get_current_room(session_id):
    """Test get current room"""
    headers = {"Authorization": f"Bearer {session_id}"}
    response = requests.get(f"{BASE_URL}/world/", headers=headers)
    data = response.json()
    print_test("GET CURRENT ROOM", response.status_code, data)
    
    if response.status_code == 200 and data.get("success"):
        room = data["room"]
        print(f"\n✓ Current position: ({room['x']}, {room['y']})")
        print(f"✓ Room name: {room['name']}")
        print(f"✓ Available exits: {room['exits']}")
    return response.status_code == 200

def test_move_north(session_id):
    """Test moving north"""
    headers = {"Authorization": f"Bearer {session_id}"}
    response = requests.post(f"{BASE_URL}/world/move", 
                            json={"direction": "north"},
                            headers=headers)
    data = response.json()
    print_test("MOVE NORTH", response.status_code, data)
    
    if response.status_code == 200 and data.get("success"):
        pos = data["new_position"]
        print(f"\n✓ Moved to: ({pos['x']}, {pos['y']})")
        print(f"✓ New room: {data['room']['name']}")
        print(f"✓ Events triggered: {len(data['events_triggered'])}")
    return response.status_code == 200

def test_query_tile(session_id, x, y):
    """Test querying a specific tile"""
    headers = {"Authorization": f"Bearer {session_id}"}
    response = requests.get(f"{BASE_URL}/world/tile?x={x}&y={y}", headers=headers)
    data = response.json()
    print_test(f"QUERY TILE ({x}, {y})", response.status_code, data)
    
    if response.status_code == 200 and data.get("success"):
        tile = data["tile"]
        print(f"\n✓ Tile: {tile['name']}")
        print(f"✓ Has {len(tile['items'])} items")
        print(f"✓ Has {len(tile['npcs'])} NPCs")
        print(f"✓ Has {len(tile['objects'])} objects")
    return response.status_code == 200

def test_invalid_direction(session_id):
    """Test invalid direction"""
    headers = {"Authorization": f"Bearer {session_id}"}
    response = requests.post(f"{BASE_URL}/world/move",
                            json={"direction": "northeast"},
                            headers=headers)
    data = response.json()
    print_test("INVALID DIRECTION (northeast)", response.status_code, data)
    return response.status_code == 400

def test_case_insensitive(session_id):
    """Test case-insensitive direction"""
    headers = {"Authorization": f"Bearer {session_id}"}
    response = requests.post(f"{BASE_URL}/world/move",
                            json={"direction": "SOUTH"},
                            headers=headers)
    data = response.json()
    print_test("CASE INSENSITIVE (SOUTH)", response.status_code, data)
    
    if response.status_code == 200 and data.get("success"):
        print(f"\n✓ Direction recognized despite uppercase")
        print(f"✓ Moved to: {data['new_position']}")
    return response.status_code == 200

def test_missing_auth():
    """Test missing authentication"""
    response = requests.get(f"{BASE_URL}/world/")
    data = response.json()
    print_test("MISSING AUTH", response.status_code, data)
    return response.status_code == 401

def test_invalid_token():
    """Test invalid token"""
    headers = {"Authorization": "Bearer invalid-token"}
    response = requests.get(f"{BASE_URL}/world/", headers=headers)
    data = response.json()
    print_test("INVALID TOKEN", response.status_code, data)
    return response.status_code == 401

def test_out_of_bounds(session_id):
    """Test out of bounds tile query"""
    headers = {"Authorization": f"Bearer {session_id}"}
    response = requests.get(f"{BASE_URL}/world/tile?x=9999&y=9999", headers=headers)
    data = response.json()
    print_test("OUT OF BOUNDS TILE", response.status_code, data)
    return response.status_code == 404

def main():
    """Run all UAT tests"""
    print("\n" + "="*60)
    print("HV-38 USER ACCEPTANCE TESTING")
    print("="*60)
    
    results = {}
    
    # Authentication tests
    print("\n\n>>> AUTHENTICATION TESTS")
    session_id = test_login()
    results["Login"] = session_id is not None
    
    results["Missing Auth"] = test_missing_auth()
    results["Invalid Token"] = test_invalid_token()
    
    if not session_id:
        print("\n❌ Login failed - cannot continue")
        return False
    
    # World navigation tests
    print("\n\n>>> WORLD NAVIGATION TESTS")
    results["Get Current Room"] = test_get_current_room(session_id)
    results["Move North"] = test_move_north(session_id)
    results["Query Tile (0,1)"] = test_query_tile(session_id, 0, 1)
    
    # Validation tests
    print("\n\n>>> VALIDATION TESTS")
    results["Invalid Direction"] = test_invalid_direction(session_id)
    results["Case Insensitive"] = test_case_insensitive(session_id)
    results["Out of Bounds"] = test_out_of_bounds(session_id)
    
    # Summary
    print("\n\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\n{'='*60}")
    print(f"TOTAL: {passed}/{total} tests passed")
    print(f"{'='*60}\n")
    
    if passed == total:
        print("🎉 All UAT tests passed! Ready for merge.")
        return True
    else:
        print(f"⚠️  {total - passed} test(s) failed.")
        return False

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Error running UAT: {e}")
        sys.exit(1)
