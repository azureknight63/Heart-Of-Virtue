# Heart of Virtue: Backend REST API Documentation

Complete reference for the Flask REST API layer that powers the Heart of Virtue web application.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Architecture](#architecture)
3. [API Endpoints](#api-endpoints)
4. [Authentication & Security](#authentication--security)
5. [Response Format](#response-format)
6. [Data Structures](#data-structures)
7. [Running the API](#running-the-api)
8. [Testing](#testing)
9. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Prerequisites
- Python 3.13
- Virtual environment activated: `.venv\Scripts\Activate.ps1`
- Dependencies installed: See `requirements-api.txt`

### Running the API Server

```powershell
# Activate environment
.venv\Scripts\Activate.ps1

# Start server (development)
python tools/run_api.py

# Output:
# WARNING in app.run() is not recommended for production...
# Running on http://127.0.0.1:5000
# Press CTRL+C to quit
```

### Verifying the API

```powershell
# Test basic connectivity
curl http://localhost:5000/api

# Expected: 200 OK with JSON response
```

---

## Architecture

### Overview

The Backend API is a **stateless Flask layer** that wraps the existing Heart of Virtue game engine:

```
┌──────────────────────────────────────┐
│  Frontend (React on Port 3000)       │
│  - Components                        │
│  - Hooks (usePlayer, useCombat, etc) │
│  - Axios client                      │
└──────────────────┬───────────────────┘
                   │ HTTP + Axios
                   │ Bearer Token Auth
                   ▼
┌──────────────────────────────────────┐
│  Backend API (Flask on Port 5000)    │
│  - 6 Route Blueprints (17 endpoints) │
│  - SessionManager (session lifecycle)│
│  - GameService (game logic wrapper)  │
│  - Input Validators (10 functions)   │
│  - Error Handlers (8 HTTP codes)     │
└──────────────────┬───────────────────┘
                   │
                   ▼
┌──────────────────────────────────────┐
│  Game Engine (Python)                │
│  - Player class (~1600 lines)        │
│  - Universe (map management)         │
│  - NPC/Combat systems               │
│  - Item/Equipment hierarchy          │
└──────────────────────────────────────┘
```

### Key Components

**SessionManager** (`src/api/services/session_manager.py`)
- Manages player sessions with 24-hour lifetime
- Stores sessions in-memory (Phase 1; database in Phase 2)
- Handles session creation, retrieval, and expiration cleanup
- Associates players with session IDs for authentication

**GameService** (`src/api/services/game_service.py`)
- Stateless wrapper around game engine
- Each method receives `Player` object, returns JSON-safe dict
- 18 core methods for all game operations
- Does NOT hold session state (SessionManager's responsibility)
- Easy to test with mocked universe

**Input Validators** (`src/api/services/validators.py`)
- 10 reusable validation functions
- Centralized, testable, used across all routes
- Returns tuple: `(is_valid: bool, error_message: Optional[str])`
- Examples: `validate_direction()`, `validate_item_slot()`, `validate_coordinates()`

**Error Handlers** (`src/api/handlers/error_handler.py`)
- Global HTTP error handlers for consistency
- Covers 8 HTTP status codes: 400, 401, 403, 404, 422, 429, 500, 503
- All errors return: `{success: false, error: "...", message: "..."}`
- Prevents duplicate error logic in individual routes

### File Organization

```
src/api/
├── __init__.py
├── app.py                    # Flask app factory
├── config.py                 # Environment-based configuration
├── services/
│   ├── __init__.py
│   ├── game_service.py       # GameService wrapper (18 methods)
│   ├── session_manager.py    # SessionManager (session lifecycle)
│   └── validators.py         # Input validation (10 functions)
├── routes/
│   ├── __init__.py
│   ├── auth.py              # Authentication endpoints (3)
│   ├── world.py             # World exploration endpoints (4)
│   ├── player.py            # Player status endpoints (4)
│   ├── inventory.py         # Inventory endpoints (3)
│   ├── equipment.py         # Equipment endpoints (2)
│   ├── combat.py            # Combat endpoints (4)
│   ├── saves.py             # Save/Load endpoints (4)
│   └── feedback.py          # Feedback → GitHub Issues (1)
├── handlers/
│   ├── __init__.py
│   └── error_handler.py      # Global error handlers (8)
└── schemas/
    ├── __init__.py
    └── openapi.py            # OpenAPI 3.0 schema generator

tests/api/
├── conftest.py              # Flask test fixtures
├── test_session_manager.py  # SessionManager tests (12)
├── test_game_service.py     # GameService tests (15)
├── test_validators.py       # Validator tests (28)
├── test_routes_integration.py # Integration tests (27)
└── test_error_handlers.py   # Error handler tests (9)
```

---

## API Endpoints

All endpoints are prefixed with `/api` and use Bearer token authentication (except login/register).

### Authentication (3 endpoints)

#### `POST /api/auth/register`
Create a new user account and session.

**Request:**
```json
{
  "username": "jean",
  "password": "mysecretpassword"
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "username": "jean",
    "message": "Account created successfully"
  }
}
```

**Error (400):**
```json
{
  "success": false,
  "error": "validation_error",
  "message": "Username already exists"
}
```

#### `POST /api/auth/login`
Authenticate and create a session.

**Request:**
```json
{
  "username": "jean",
  "password": "mysecretpassword"
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "username": "jean"
  }
}
```

**Error (401):**
```json
{
  "success": false,
  "error": "authentication_failed",
  "message": "Invalid username or password"
}
```

#### `POST /api/auth/logout`
Invalidate current session.

**Headers:**
```
Authorization: Bearer {session_id}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "message": "Logged out successfully"
  }
}
```

---

### Player Status (4 endpoints)

#### `GET /api/player/status`
Get current player status and inventory.

**Headers:**
```
Authorization: Bearer {session_id}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "id": "player_1",
    "name": "Jean",
    "hp": 75,
    "max_hp": 100,
    "fatigue": 60,
    "max_fatigue": 100,
    "level": 3,
    "experience": 1240,
    "next_level_exp": 2000,
    "strength": 15,
    "agility": 12,
    "intelligence": 10
  }
}
```

#### `GET /api/player/inventory`
Get player inventory.

**Response (200):**
```json
{
  "success": true,
  "data": {
    "items": [
      { "id": "item_1", "name": "Shortsword", "quantity": 1 },
      { "id": "item_2", "name": "Healing Potion", "quantity": 3 }
    ],
    "weight": 5.2,
    "weight_limit": 20
  }
}
```

#### `GET /api/player/equipment`
Get equipped items.

**Response (200):**
```json
{
  "success": true,
  "data": {
    "equipped": {
      "weapon": { "id": "item_1", "name": "Shortsword" },
      "armor": { "id": "item_2", "name": "Leather Armor" },
      "boots": null
    }
  }
}
```

#### `GET /api/player/stats`
Get detailed player statistics.

**Response (200):**
```json
{
  "success": true,
  "data": {
    "strength": 15,
    "agility": 12,
    "intelligence": 10,
    "hp": 75,
    "max_hp": 100,
    "fatigue": 60,
    "max_fatigue": 100,
    "armor_rating": 12
  }
}
```

---

### World Exploration (4 endpoints)

#### `GET /api/world/location`
Get current location details.

**Response (200):**
```json
{
  "success": true,
  "data": {
    "id": "loc_1",
    "name": "Tavern",
    "description": "A cozy tavern filled with adventurers",
    "x": 5,
    "y": 5,
    "exits": {
      "north": "loc_2",
      "south": "loc_3",
      "east": "loc_4"
    },
    "items": [
      { "id": "item_10", "name": "Gold Coin", "quantity": 5 }
    ],
    "npcs": [
      { "id": "npc_1", "name": "Innkeeper", "dialog": "Welcome, traveler!" }
    ]
  }
}
```

#### `POST /api/world/move`
Move to an adjacent location.

**Request:**
```json
{
  "direction": "north"
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "location": { "name": "Forest", "description": "..." },
    "combat_triggered": false
  }
}
```

**Error (400):**
```json
{
  "success": false,
  "error": "validation_error",
  "message": "Invalid direction. Use: north, south, east, west"
}
```

#### `GET /api/world/exits`
Get available exits from current location.

**Response (200):**
```json
{
  "success": true,
  "data": {
    "available": ["north", "south", "east"],
    "current_location": "Tavern"
  }
}
```

#### `GET /api/world/map`
Get discovered map.

**Response (200):**
```json
{
  "success": true,
  "data": {
    "discovered_locations": [
      { "x": 5, "y": 5, "name": "Tavern", "visited": true },
      { "x": 5, "y": 4, "name": "Forest", "visited": true }
    ],
    "current_pos": [5, 5]
  }
}
```

---

### Combat (4 endpoints)

#### `GET /api/combat/status`
Get current combat state.

**Response (200):**
```json
{
  "success": true,
  "data": {
    "in_combat": true,
    "player_hp": 75,
    "player_max_hp": 100,
    "enemies": [
      {
        "id": "enemy_1",
        "name": "Goblin",
        "hp": 18,
        "max_hp": 25,
        "level": 2
      },
      {
        "id": "enemy_2",
        "name": "Bat",
        "hp": 12,
        "max_hp": 15,
        "level": 1
      }
    ],
    "log": [
      { "type": "damage", "message": "Jean attacks Goblin for 12 damage" },
      { "type": "ability", "message": "Goblin uses slash attack!" }
    ]
  }
}
```

#### `POST /api/combat/start`
Initiate combat.

**Response (200):**
```json
{
  "success": true,
  "data": {
    "message": "Combat started!",
    "enemies": [...]
  }
}
```

#### `POST /api/combat/end`
End current combat.

**Response (200):**
```json
{
  "success": true,
  "data": {
    "message": "Combat ended",
    "rewards": { "experience": 150, "gold": 25 }
  }
}
```

#### `POST /api/combat/action`
Perform combat action.

**Request:**
```json
{
  "action": "attack",
  "target": "enemy_1"
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "result": "Jean attacks Goblin for 12 damage",
    "enemy_hp": 6,
    "log_entry": { "type": "damage", "message": "..." }
  }
}
```

---

### Inventory Management (3 endpoints)

#### `POST /api/inventory/use`
Use an item (consumable).

**Request:**
```json
{
  "item_id": "item_5"
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "message": "Used Healing Potion",
    "hp_restored": 25,
    "new_hp": 100
  }
}
```

#### `POST /api/inventory/drop`
Drop an item from inventory.

**Request:**
```json
{
  "item_id": "item_3"
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "message": "Dropped Healing Potion",
    "item_dropped": { "id": "item_3", "name": "Healing Potion" }
  }
}
```

#### `POST /api/inventory/pickup`
Pick up an item from current location.

**Request:**
```json
{
  "item_id": "item_10"
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "message": "Picked up Gold Coin",
    "inventory_count": 15
  }
}
```

---

### Equipment (2 endpoints)

#### `POST /api/equipment/equip`
Equip an item.

**Request:**
```json
{
  "item_id": "item_1",
  "slot": "weapon"
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "message": "Equipped Shortsword",
    "equipped": { "weapon": "Shortsword" }
  }
}
```

#### `POST /api/equipment/unequip`
Remove equipped item.

**Request:**
```json
{
  "slot": "armor"
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "message": "Unequipped Leather Armor",
    "item_returned_to_inventory": true
  }
}
```

---

### Save/Load (4 endpoints)

#### `POST /api/saves/save`
Save the current game.

**Request:**
```json
{
  "save_name": "My Save 1"
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "save_id": "save_12345",
    "save_name": "My Save 1",
    "timestamp": "2025-11-11T14:30:00Z"
  }
}
```

#### `POST /api/saves/load`
Load a saved game.

**Request:**
```json
{
  "save_id": "save_12345"
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "message": "Game loaded",
    "save_name": "My Save 1"
  }
}
```

#### `GET /api/saves/list`
List all saved games.

**Response (200):**
```json
{
  "success": true,
  "data": {
    "saves": [
      { "save_id": "save_12345", "name": "My Save 1", "timestamp": "2025-11-11T14:30:00Z" },
      { "save_id": "save_12346", "name": "My Save 2", "timestamp": "2025-11-10T10:15:00Z" }
    ]
  }
}
```

#### `DELETE /api/saves/delete/{save_id}`
Delete a saved game.

**Response (200):**
```json
{
  "success": true,
  "data": {
    "message": "Save deleted",
    "save_id": "save_12345"
  }
}
```

---

### Feedback (1 endpoint)

#### `POST /api/feedback/issue`
Submit in-game feedback that creates a GitHub issue on `azureknight63/heart-of-virtue`. Requires a valid session token. Rate-limited to 10 submissions per session per hour.

**Request:**
```json
{
  "type": "bug" | "feature" | "general",
  "title": "Short descriptive title (max 256 chars)",
  "anonymous": false,
  "fields": {
    // bug:     { "steps": "...", "expected": "...", "actual": "...", "severity": "low|medium|high" }
    // feature: { "description": "...", "use_case": "..." }
    // general: { "message": "...", "ratings": { "story": 1-5, "combat": 1-5, "audio": 1-5, "visuals": 1-5, "difficulty": 1-5 } }
  }
}
```

**Response (201):**
```json
{
  "success": true,
  "issue_url": "https://github.com/azureknight63/heart-of-virtue/issues/123"
}
```

**Error responses:**
- `400` — missing/invalid `title` or unknown `type`
- `429` — rate limit exceeded (10/hour per session)
- `503` — `GITHUB_TOKEN` not configured on the server

**Notes:**
- Set `GITHUB_TOKEN` in your environment (see `.env.example`). Without it, the route returns 503 and the game loop is unaffected.
- The `anonymous` flag omits the player's username from the GitHub issue body.

---

## Authentication & Security

### Bearer Token Authentication

All endpoints except `/auth/register` and `/auth/login` require Bearer token authentication.

**Header Format:**
```
Authorization: Bearer {session_id}
```

**Example with Axios (frontend):**
```javascript
import axios from 'axios'

const apiClient = axios.create({
  baseURL: 'http://localhost:5000/api'
})

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('authToken')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})
```

### Response Interceptor (Auth Error Handling)

```javascript
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('authToken')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)
```

### Session Lifecycle

1. **Login** → Backend creates session, returns `session_id`
2. **Frontend stores** → In localStorage as `authToken`
3. **Every request** → Frontend includes `Authorization: Bearer {session_id}`
4. **Backend validates** → Checks session is valid and not expired
5. **Expired token** → Backend returns 401, frontend redirects to login

**Session Duration:** 24 hours

---

## Response Format

### Success Response

All successful responses (2xx status codes) follow this format:

```json
{
  "success": true,
  "data": {
    "key1": "value1",
    "key2": "value2"
  }
}
```

**Status Codes:**
- `200 OK` - Successful request
- `201 Created` - Resource created successfully

### Error Response

All error responses (4xx/5xx status codes) follow this format:

```json
{
  "success": false,
  "error": "error_code",
  "message": "Human-readable error message"
}
```

**Common Error Codes:**
- `validation_error` - Input validation failed
- `authentication_failed` - Login failed
- `unauthorized` - Missing or invalid token (401)
- `forbidden` - Not allowed to perform action (403)
- `not_found` - Resource not found (404)
- `conflict` - Resource already exists (409)
- `server_error` - Internal server error (500)
- `service_unavailable` - Server temporarily unavailable (503)

**Status Codes:**
- `400 Bad Request` - Invalid input
- `401 Unauthorized` - Auth required or failed
- `403 Forbidden` - Insufficient permissions
- `404 Not Found` - Resource doesn't exist
- `422 Unprocessable Entity` - Validation failed
- `429 Too Many Requests` - Rate limit exceeded
- `500 Internal Server Error` - Server error
- `503 Service Unavailable` - Service down

---

## Data Structures

### Player Object

```json
{
  "id": "player_1",
  "name": "Jean",
  "hp": 75,
  "max_hp": 100,
  "fatigue": 60,
  "max_fatigue": 100,
  "level": 3,
  "experience": 1240,
  "next_level_exp": 2000,
  "strength": 15,
  "agility": 12,
  "intelligence": 10,
  "armor_rating": 8,
  "inventory": [
    { "id": "item_1", "name": "Shortsword", "quantity": 1 },
    { "id": "item_2", "name": "Healing Potion", "quantity": 3 }
  ]
}
```

### Location Object

```json
{
  "id": "loc_1",
  "name": "Tavern",
  "description": "A cozy tavern filled with adventurers",
  "x": 5,
  "y": 5,
  "exits": {
    "north": "loc_2",
    "south": "loc_3",
    "east": "loc_4"
  },
  "items": [
    { "id": "item_10", "name": "Gold Coin", "quantity": 5 }
  ],
  "npcs": [
    { "id": "npc_1", "name": "Innkeeper" }
  ]
}
```

### Combat State Object

```json
{
  "in_combat": true,
  "player_hp": 75,
  "player_max_hp": 100,
  "enemies": [
    {
      "id": "enemy_1",
      "name": "Goblin",
      "hp": 18,
      "max_hp": 25,
      "level": 2,
      "status": "normal"
    }
  ],
  "log": [
    {
      "type": "damage",
      "message": "Jean attacks Goblin for 12 damage"
    },
    {
      "type": "heal",
      "message": "Jean recovers 10 HP"
    }
  ]
}
```

---

## Running the API

### Development Server

```powershell
# Activate environment
.venv\Scripts\Activate.ps1

# Start with hot reload
python tools/run_api.py

# Server starts on http://127.0.0.1:5000
```

### Configuration

Environment variables (in `.env` or `config_dev.ini`):

```bash
FLASK_ENV=development
FLASK_HOST=127.0.0.1
FLASK_PORT=5000
FLASK_DEBUG=1
```

### Production Deployment

```powershell
# Build for production (if needed)
# Typically: gunicorn or similar WSGI server

# For testing:
python tools/run_api.py  # Do NOT use in production
```

---

## Testing

### Unit Tests

Run all API tests:

```powershell
pytest tests/api/ -v
```

Run specific test file:

```powershell
pytest tests/api/test_validators.py -v
```

Run with coverage:

```powershell
pytest tests/api/ --cov=src/api --cov-report=term-missing
```

### Integration Tests

Test full flow (auth → action → result):

```powershell
pytest tests/api/test_routes_integration.py -v
```

### Manual Testing with cURL

**Register:**
```powershell
curl -X POST http://localhost:5000/api/auth/register `
  -H "Content-Type: application/json" `
  -d '{"username":"test","password":"test123"}'
```

**Login:**
```powershell
$response = curl -X POST http://localhost:5000/api/auth/login `
  -H "Content-Type: application/json" `
  -d '{"username":"test","password":"test123"}'

# Extract session_id from response
```

**Get Player Status:**
```powershell
curl -X GET http://localhost:5000/api/player/status `
  -H "Authorization: Bearer {session_id}"
```

### Manual Testing with Postman

1. Create environment with variable: `session_id`
2. POST to `/api/auth/login`
3. In response, set `session_id` from response body
4. Use `Authorization: Bearer {{session_id}}` in headers
5. Test endpoints

### Swagger UI

Interactive API documentation:

```
http://localhost:5000/api/docs
```

OpenAPI schema:

```
http://localhost:5000/api/openapi.json
```

---

## Troubleshooting

### API Won't Start

**Error: "Address already in use"**
- Port 5000 is occupied
- Solution: Kill process on port 5000 or change port in config

```powershell
# Find process using port 5000
Get-NetTCPConnection -LocalPort 5000

# Kill process
Stop-Process -Id {pid} -Force
```

### CORS Errors in Frontend

**Error: "Access to XMLHttpRequest blocked by CORS"**
- CORS not enabled on backend
- Solution: Check `src/api/app.py` has CORS enabled

```python
from flask_cors import CORS
CORS(app, origins=['http://localhost:3000'])
```

### 401 Unauthorized

**Error: "Missing or invalid token"**
- Token not being sent or has expired
- Solution: Check `Authorization` header is present and valid

```powershell
# Verify header format
curl -i http://localhost:5000/api/player/status \
  -H "Authorization: Bearer {session_id}"
```

### 500 Server Error

**Error: "Internal server error"**
- Server crashed
- Solution: Check server logs for stack trace

```powershell
# Check terminal where server is running for error output
# Look for: File "src/api/app.py", line X
```

### Frontend Can't Connect

**Error: "Cannot connect to localhost:5000"**
- Backend not running
- Solution: Verify backend is running

```powershell
# Terminal 1 - Check if running
.venv\Scripts\Activate.ps1
python tools/run_api.py

# Terminal 2 - Test endpoint
curl http://localhost:5000/api
```

---

## API Checklist

Before deploying, verify:

- [ ] Backend runs on http://localhost:5000
- [ ] CORS headers present in responses
- [ ] `/api/auth/login` returns `session_id`
- [ ] Auth token works in `Authorization` header
- [ ] All endpoints respond with correct data
- [ ] Error responses are valid JSON
- [ ] 401 returns on expired tokens
- [ ] Frontend can login and see player data
- [ ] Frontend can move between locations
- [ ] Combat transitions work correctly

---

## Support

- **API Docs**: See Swagger UI at http://localhost:5000/api/docs
- **Code**: `src/api/` directory
- **Tests**: `tests/api/` directory
- **Configuration**: `src/api/config.py`

---

**Last Updated:** November 2025
**Status:** Production Ready ✅

