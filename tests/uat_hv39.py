"""
HV-39 UAT (User Acceptance Testing) Script

End-to-end tests for the complete inventory system including:
- 10 inventory endpoints
- 6 serializer classes
- 5 input validators
- GameService integration
- Full authentication and authorization

This script tests the API against a running Flask server.
Requires: Flask API running at http://localhost:5000
"""

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

import requests

ROOT = Path(__file__).resolve().parent.parent
API_BASE_URL = "http://localhost:5000/api"

# Color codes for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


class UATAPI:
    """API client for UAT testing."""

    def __init__(self, base_url: str = API_BASE_URL):
        """Initialize API client.

        Args:
            base_url: Base URL for API
        """
        self.base_url = base_url
        self.session_id: Optional[str] = None
        self.bearer_token: Optional[str] = None
        self.test_count = 0
        self.passed_count = 0
        self.failed_count = 0

    def log(self, message: str, color: str = BLUE) -> None:
        """Log a message to stdout."""
        print(f"{color}{message}{RESET}")

    def assert_response(
        self,
        response: requests.Response,
        expected_status: int,
        test_name: str,
        check_success: bool = True,
    ) -> bool:
        """Assert response status and optionally success field.

        Args:
            response: Response object
            expected_status: Expected HTTP status code
            test_name: Name of test for logging
            check_success: Whether to also check success field

        Returns:
            True if all checks pass
        """
        self.test_count += 1

        # Check status code
        if response.status_code != expected_status:
            self.log(
                f"❌ FAIL [{test_name}]: Expected status {expected_status}, got {response.status_code}",
                RED,
            )
            self.log(f"   Response: {response.text}", RED)
            self.failed_count += 1
            return False

        # Check JSON is valid
        try:
            data = response.json()
        except json.JSONDecodeError:
            self.log(
                f"❌ FAIL [{test_name}]: Response is not valid JSON",
                RED,
            )
            self.failed_count += 1
            return False

        # Check success field if requested
        if check_success and "success" in data:
            if not data.get("success"):
                self.log(
                    f"❌ FAIL [{test_name}]: success=false: {data.get('error')}",
                    RED,
                )
                self.failed_count += 1
                return False

        self.log(f"✓ PASS [{test_name}]", GREEN)
        self.passed_count += 1
        return True

    def get_auth_header(self) -> Dict[str, str]:
        """Get authorization header."""
        if not self.bearer_token:
            return {}
        return {"Authorization": f"Bearer {self.bearer_token}"}

    def print_summary(self) -> None:
        """Print test summary."""
        self.log("\n" + "=" * 60, BLUE)
        self.log(f"UAT Test Summary", BLUE)
        self.log("=" * 60, BLUE)
        self.log(f"Total tests: {self.test_count}", BLUE)
        self.log(f"Passed: {self.passed_count}", GREEN)
        self.log(f"Failed: {self.failed_count}", RED)

        if self.failed_count == 0:
            self.log(f"\n🎉 All tests passed!", GREEN)
        else:
            self.log(f"\n❌ {self.failed_count} test(s) failed", RED)

        self.log("=" * 60 + "\n", BLUE)


def test_api_health(api: UATAPI) -> bool:
    """Test API is reachable."""
    api.log("\n[TEST SUITE 1] API Health Check", YELLOW)

    try:
        response = requests.get(f"{api.base_url}/health", timeout=5)
        return api.assert_response(response, 200, "API health check")
    except requests.exceptions.ConnectionError:
        api.log("❌ FAIL [API health check]: Cannot connect to API server", RED)
        api.log("   Ensure Flask API is running on http://localhost:5000", RED)
        api.failed_count += 1
        api.test_count += 1
        return False


def test_authentication(api: UATAPI) -> bool:
    """Test authentication flow."""
    api.log("\n[TEST SUITE 2] Authentication", YELLOW)

    # Test 1: Create new session
    response = requests.post(f"{api.base_url}/auth/login", json={"character_name": "TestPlayer"})

    if not api.assert_response(response, 200, "Create session", check_success=True):
        return False

    data = response.json()
    if "data" not in data or "session_id" not in data["data"]:
        api.log(
            "❌ FAIL [Extract session ID]: No session_id in response",
            RED,
        )
        api.failed_count += 1
        api.test_count += 1
        return False

    api.session_id = data["data"]["session_id"]
    api.bearer_token = api.session_id
    api.log(f"✓ Session ID obtained: {api.session_id[:16]}...", GREEN)
    api.passed_count += 1
    api.test_count += 1

    # Test 2: Verify bearer token works
    response = requests.get(
        f"{api.base_url}/world/status",
        headers=api.get_auth_header(),
    )
    return api.assert_response(response, 200, "Verify bearer token auth")


def test_inventory_endpoints(api: UATAPI) -> bool:
    """Test inventory endpoints."""
    api.log("\n[TEST SUITE 3] Inventory Endpoints", YELLOW)

    if not api.bearer_token:
        api.log("❌ SKIP [Inventory endpoints]: No authentication", RED)
        return False

    # Test 1: Get inventory (GET /inventory/)
    response = requests.get(
        f"{api.base_url}/inventory/",
        headers=api.get_auth_header(),
    )
    if not api.assert_response(response, 200, "GET /inventory/"):
        return False

    data = response.json()
    if "data" not in data or "items" not in data["data"]:
        api.log(
            "❌ FAIL [Inventory structure]: Missing 'items' in response",
            RED,
        )
        api.failed_count += 1
        api.test_count += 1
        return False

    api.log(f"✓ Inventory contains {len(data['data']['items'])} items", GREEN)
    api.passed_count += 1
    api.test_count += 1

    # Test 2: Get currency (GET /inventory/currency)
    response = requests.get(
        f"{api.base_url}/inventory/currency",
        headers=api.get_auth_header(),
    )
    api.assert_response(response, 200, "GET /inventory/currency")

    # Test 3: Get equipment (GET /inventory/equipment)
    response = requests.get(
        f"{api.base_url}/inventory/equipment",
        headers=api.get_auth_header(),
    )
    if not api.assert_response(response, 200, "GET /inventory/equipment"):
        return False

    data = response.json()
    if "data" not in data or not isinstance(data["data"], dict):
        api.log(
            "❌ FAIL [Equipment structure]: Equipment should be a dict",
            RED,
        )
        api.failed_count += 1
        api.test_count += 1
        return False

    api.log(f"✓ Equipment structure valid", GREEN)
    api.passed_count += 1
    api.test_count += 1

    # Test 4: Get player stats (GET /inventory/stats)
    response = requests.get(
        f"{api.base_url}/inventory/stats",
        headers=api.get_auth_header(),
    )
    api.assert_response(response, 200, "GET /inventory/stats")

    return True


def test_inventory_validation(api: UATAPI) -> bool:
    """Test inventory endpoint validation."""
    api.log("\n[TEST SUITE 4] Inventory Validation", YELLOW)

    if not api.bearer_token:
        api.log("❌ SKIP [Inventory validation]: No authentication", RED)
        return False

    # Test 1: Missing authentication header
    response = requests.get(f"{api.base_url}/inventory/")
    if response.status_code != 401:
        api.log(
            f"❌ FAIL [Missing auth]: Expected 401, got {response.status_code}",
            RED,
        )
        api.failed_count += 1
    else:
        api.log("✓ PASS [Missing auth header returns 401]", GREEN)
        api.passed_count += 1
    api.test_count += 1

    # Test 2: Invalid session ID
    response = requests.get(
        f"{api.base_url}/inventory/",
        headers={"Authorization": "Bearer invalid-session-id"},
    )
    if response.status_code != 401:
        api.log(
            f"❌ FAIL [Invalid session]: Expected 401, got {response.status_code}",
            RED,
        )
        api.failed_count += 1
    else:
        api.log("✓ PASS [Invalid session returns 401]", GREEN)
        api.passed_count += 1
    api.test_count += 1

    # Test 3: Examine with invalid index
    response = requests.get(
        f"{api.base_url}/inventory/examine",
        params={"index": 99999},
        headers=api.get_auth_header(),
    )
    if response.status_code != 400:
        api.log(
            f"❌ FAIL [Invalid index]: Expected 400, got {response.status_code}",
            RED,
        )
        api.failed_count += 1
    else:
        api.log("✓ PASS [Invalid index returns 400]", GREEN)
        api.passed_count += 1
    api.test_count += 1

    return True


def test_examine_endpoint(api: UATAPI) -> bool:
    """Test examine item endpoint."""
    api.log("\n[TEST SUITE 5] Examine Item Endpoint", YELLOW)

    if not api.bearer_token:
        api.log("❌ SKIP [Examine endpoint]: No authentication", RED)
        return False

    # Test: Examine first item (if any exist)
    response = requests.get(
        f"{api.base_url}/inventory/examine",
        params={"index": 0},
        headers=api.get_auth_header(),
    )

    # Response could be 200 (item exists) or 400 (no item at index)
    if response.status_code == 200:
        data = response.json()
        if data.get("success"):
            api.log(f"✓ PASS [Examine item]: Item details retrieved", GREEN)
            api.passed_count += 1
        else:
            api.log(f"✓ PASS [Examine item]: Valid error response", GREEN)
            api.passed_count += 1
    elif response.status_code == 400:
        api.log(f"✓ PASS [Examine item]: Returns 400 for empty inventory", GREEN)
        api.passed_count += 1
    else:
        api.log(
            f"❌ FAIL [Examine item]: Unexpected status {response.status_code}",
            RED,
        )
        api.failed_count += 1

    api.test_count += 1
    return True


def test_compare_endpoint(api: UATAPI) -> bool:
    """Test compare items endpoint."""
    api.log("\n[TEST SUITE 6] Compare Items Endpoint", YELLOW)

    if not api.bearer_token:
        api.log("❌ SKIP [Compare endpoint]: No authentication", RED)
        return False

    # Test: Compare items (endpoint may return success or error based on inventory)
    response = requests.post(
        f"{api.base_url}/inventory/compare",
        json={"index1": 0, "index2": 1},
        headers=api.get_auth_header(),
    )

    if response.status_code in [200, 400]:
        api.log(
            f"✓ PASS [Compare items]: Endpoint responds with {response.status_code}",
            GREEN,
        )
        api.passed_count += 1
    else:
        api.log(
            f"❌ FAIL [Compare items]: Unexpected status {response.status_code}",
            RED,
        )
        api.failed_count += 1

    api.test_count += 1
    return True


def test_equipment_endpoints(api: UATAPI) -> bool:
    """Test equipment modification endpoints."""
    api.log("\n[TEST SUITE 7] Equipment Endpoints", YELLOW)

    if not api.bearer_token:
        api.log("❌ SKIP [Equipment endpoints]: No authentication", RED)
        return False

    # Test 1: Equip item
    response = requests.post(
        f"{api.base_url}/inventory/equip",
        json={"index": 0, "slot": "main_hand"},
        headers=api.get_auth_header(),
    )

    if response.status_code in [200, 400, 422]:
        api.log(
            f"✓ PASS [Equip item]: Endpoint responds with {response.status_code}",
            GREEN,
        )
        api.passed_count += 1
    else:
        api.log(
            f"❌ FAIL [Equip item]: Unexpected status {response.status_code}",
            RED,
        )
        api.failed_count += 1

    api.test_count += 1

    # Test 2: Unequip item
    response = requests.post(
        f"{api.base_url}/inventory/unequip",
        json={"slot": "main_hand"},
        headers=api.get_auth_header(),
    )

    if response.status_code in [200, 400]:
        api.log(
            f"✓ PASS [Unequip item]: Endpoint responds with {response.status_code}",
            GREEN,
        )
        api.passed_count += 1
    else:
        api.log(
            f"❌ FAIL [Unequip item]: Unexpected status {response.status_code}",
            RED,
        )
        api.failed_count += 1

    api.test_count += 1
    return True


def test_item_management_endpoints(api: UATAPI) -> bool:
    """Test item management endpoints (take, drop)."""
    api.log("\n[TEST SUITE 8] Item Management Endpoints", YELLOW)

    if not api.bearer_token:
        api.log("❌ SKIP [Item management]: No authentication", RED)
        return False

    # Test 1: Take item
    response = requests.post(
        f"{api.base_url}/inventory/take",
        json={"item_id": "test-item-1"},
        headers=api.get_auth_header(),
    )

    if response.status_code in [200, 400, 422]:
        api.log(
            f"✓ PASS [Take item]: Endpoint responds with {response.status_code}",
            GREEN,
        )
        api.passed_count += 1
    else:
        api.log(
            f"❌ FAIL [Take item]: Unexpected status {response.status_code}",
            RED,
        )
        api.failed_count += 1

    api.test_count += 1

    # Test 2: Drop item
    response = requests.post(
        f"{api.base_url}/inventory/drop",
        json={"index": 0},
        headers=api.get_auth_header(),
    )

    if response.status_code in [200, 400, 422]:
        api.log(
            f"✓ PASS [Drop item]: Endpoint responds with {response.status_code}",
            GREEN,
        )
        api.passed_count += 1
    else:
        api.log(
            f"❌ FAIL [Drop item]: Unexpected status {response.status_code}",
            RED,
        )
        api.failed_count += 1

    api.test_count += 1
    return True


def test_error_handling(api: UATAPI) -> bool:
    """Test error handling and edge cases."""
    api.log("\n[TEST SUITE 9] Error Handling & Edge Cases", YELLOW)

    if not api.bearer_token:
        api.log("❌ SKIP [Error handling]: No authentication", RED)
        return False

    # Test 1: Invalid JSON in request
    response = requests.post(
        f"{api.base_url}/inventory/equip",
        data="invalid json",
        headers={**api.get_auth_header(), "Content-Type": "application/json"},
    )

    if response.status_code in [400, 422]:
        api.log(
            f"✓ PASS [Invalid JSON]: Returns {response.status_code}",
            GREEN,
        )
        api.passed_count += 1
    else:
        api.log(
            f"❌ FAIL [Invalid JSON]: Expected 400/422, got {response.status_code}",
            RED,
        )
        api.failed_count += 1

    api.test_count += 1

    # Test 2: Missing required fields
    response = requests.post(
        f"{api.base_url}/inventory/equip",
        json={"index": 0},  # missing 'slot'
        headers=api.get_auth_header(),
    )

    if response.status_code in [400, 422]:
        api.log(
            f"✓ PASS [Missing required field]: Returns {response.status_code}",
            GREEN,
        )
        api.passed_count += 1
    else:
        api.log(
            f"❌ FAIL [Missing required field]: Expected 400/422, got {response.status_code}",
            RED,
        )
        api.failed_count += 1

    api.test_count += 1

    # Test 3: Invalid slot name
    response = requests.post(
        f"{api.base_url}/inventory/equip",
        json={"index": 0, "slot": "invalid_slot_name"},
        headers=api.get_auth_header(),
    )

    if response.status_code in [400, 422]:
        api.log(
            f"✓ PASS [Invalid slot]: Returns {response.status_code}",
            GREEN,
        )
        api.passed_count += 1
    else:
        api.log(
            f"❌ FAIL [Invalid slot]: Expected 400/422, got {response.status_code}",
            RED,
        )
        api.failed_count += 1

    api.test_count += 1
    return True


def main() -> int:
    """Run UAT tests.

    Returns:
        0 if all tests pass, 1 if any fail
    """
    print("\n" + "=" * 60)
    print("HV-39 UAT (User Acceptance Testing)")
    print("Inventory System - End-to-End Tests")
    print("=" * 60 + "\n")

    api = UATAPI()

    # Run test suites
    test_suites = [
        test_api_health,
        test_authentication,
        test_inventory_endpoints,
        test_inventory_validation,
        test_examine_endpoint,
        test_compare_endpoint,
        test_equipment_endpoints,
        test_item_management_endpoints,
        test_error_handling,
    ]

    for test_suite in test_suites:
        try:
            test_suite(api)
        except Exception as e:
            api.log(f"❌ EXCEPTION in {test_suite.__name__}: {e}", RED)
            api.failed_count += 1
            api.test_count += 1

    # Print summary
    api.print_summary()

    return 0 if api.failed_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
