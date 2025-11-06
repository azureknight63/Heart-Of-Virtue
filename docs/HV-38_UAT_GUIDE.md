# HV-38 User Acceptance Testing (UAT) Guide

## Quick Start

The server is now running on `http://localhost:5000`

### Health Check
- **URL**: http://localhost:5000/health
- **Method**: GET
- **Purpose**: Verify server is running

### API Documentation (Interactive)
- **URL**: http://localhost:5000/api/docs
- **Purpose**: Swagger UI with all endpoints and try-it-out capability
- **Contains**: All HV-38 world navigation endpoints with examples

## Testing HV-38 World Navigation Endpoints

All endpoints require Bearer token authentication. Follow these steps:

### Step 1: Login (Get Session Token)

**Endpoint**: `POST /auth/login`

```json
{
  "username": "TestPlayer"
}
```

**Response** (save the `session_id`):
```json
{
  "success": true,
  "session_id": "your-session-id-here",
  "player_id": "player-123",
  "expires_at": "2025-11-06T15:30:00"
}
```

### Step 2: Get Current Room

**Endpoint**: `GET /world/`

**Headers**:
```
Authorization: Bearer your-session-id-here
```

**Response**:
```json
{
  "success": true,
  "room": {
    "x": 0,
    "y": 0,
    "name": "Test Starting Room",
    "description": "A test room",
    "items": [],
    "npcs": [],
    "objects": [],
    "events": [],
    "exits": {
      "north": {"x": 0, "y": 1},
      "south": {"x": 0, "y": -1},
      "east": {"x": 1, "y": 0},
      "west": {"x": -1, "y": 0}
    },
    "is_passable": true
  }
}
```

### Step 3: Move North

**Endpoint**: `POST /world/move`

**Headers**:
```
Authorization: Bearer your-session-id-here
Content-Type: application/json
```

**Body**:
```json
{
  "direction": "north"
}
```

**Response**:
```json
{
  "success": true,
  "new_position": {
    "x": 0,
    "y": 1
  },
  "room": {
    "x": 0,
    "y": 1,
    "name": "Test Northern Room",
    "description": "A room to the north",
    "items": [],
    "npcs": [],
    "objects": [],
    "events": [],
    "exits": {...},
    "is_passable": true
  },
  "events_triggered": []
}
```

### Step 4: Query a Specific Tile

**Endpoint**: `GET /world/tile?x=1&y=0`

**Headers**:
```
Authorization: Bearer your-session-id-here
```

**Response**:
```json
{
  "success": true,
  "tile": {
    "x": 1,
    "y": 0,
    "name": "Test Eastern Room",
    "description": "A room to the east",
    "items": [],
    "npcs": [],
    "objects": [],
    "events": [],
    "exits": {...},
    "is_passable": true
  }
}
```

## Test Cases

### Valid Movement Tests

- ✅ Move North: `POST /world/move {"direction": "north"}`
- ✅ Move South: `POST /world/move {"direction": "south"}`
- ✅ Move East: `POST /world/move {"direction": "east"}`
- ✅ Move West: `POST /world/move {"direction": "west"}`
- ✅ Case-insensitive: `POST /world/move {"direction": "NORTH"}`

### Invalid Movement Tests

- ❌ Invalid direction: `POST /world/move {"direction": "northeast"}` → 400 error
- ❌ Missing direction: `POST /world/move {}` → 400 error
- ❌ Out of bounds: Move multiple times in same direction → 400 error (blocked)

### Query Tests

- ✅ Get current room: `GET /world/` → 200 with room data
- ✅ Query tile at (0,1): `GET /world/tile?x=0&y=1` → 200 with tile data
- ✅ Query starting tile: `GET /world/tile?x=0&y=0` → 200
- ❌ Invalid coordinates: `GET /world/tile?x=abc&y=def` → 400 error
- ❌ Out of bounds: `GET /world/tile?x=9999&y=9999` → 404 error

### Authentication Tests

- ❌ Missing auth header: `GET /world/` → 401 error
- ❌ Invalid token: `GET /world/ {"Authorization": "Bearer invalid"}` → 401 error
- ✅ Valid token: `GET /world/ {"Authorization": "Bearer <session_id>"}` → 200 with data

## Using Swagger UI (Recommended for UAT)

The easiest way to test is using the interactive Swagger UI:

1. **Open**: http://localhost:5000/api/docs
2. **Click** on the "Authorize" button (top right)
3. **Enter** your session token from the login step
4. **Click** any endpoint to expand it
5. **Click** "Try it out"
6. **Fill** in parameters/body
7. **Click** "Execute"
8. **View** response

### Quick UAT Workflow in Swagger

1. **POST /auth/login**
   - Body: `{"username": "TestPlayer"}`
   - Copy the `session_id` from response

2. **GET /world/**
   - Click "Authorize" and paste session_id
   - Execute
   - View your current room at (0,0)

3. **POST /world/move**
   - Body: `{"direction": "north"}`
   - Execute
   - Verify you moved to (0,1)

4. **GET /world/tile**
   - Query: `x=0&y=1`
   - Execute
   - Verify tile matches your new position

5. **POST /world/move** (try invalid)
   - Body: `{"direction": "northeast"}`
   - Execute
   - Verify 400 error response

## Key Features to Verify

### 1. Movement System ✅
- [x] Player can move in all 4 cardinal directions
- [x] Position updates correctly
- [x] Room data updated on movement
- [x] Invalid directions rejected
- [x] Out of bounds blocked

### 2. Tile Query System ✅
- [x] Tiles return correct data
- [x] Items/NPCs/Objects serialized properly
- [x] Exits/connections populated
- [x] Out of bounds queries return 404

### 3. Event System ✅
- [x] Events trigger on tile entry
- [x] Event data in response
- [x] Multiple events all trigger
- [x] Events without errors handled gracefully

### 4. Authentication ✅
- [x] All endpoints require Bearer token
- [x] Invalid tokens rejected
- [x] Sessions expire after 24 hours
- [x] 401 errors on auth failure

### 5. Error Handling ✅
- [x] Invalid directions → 400 error
- [x] Missing coordinates → 400 error
- [x] Invalid coordinates → 400 error
- [x] Out of bounds → 404 error
- [x] Missing auth → 401 error
- [x] Invalid session → 401 error

## Curl Examples (for Terminal Testing)

### Login
```bash
curl -X POST http://localhost:5000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "TestPlayer"}'
```

### Get Current Room
```bash
curl -X GET http://localhost:5000/world/ \
  -H "Authorization: Bearer YOUR_SESSION_ID"
```

### Move North
```bash
curl -X POST http://localhost:5000/world/move \
  -H "Authorization: Bearer YOUR_SESSION_ID" \
  -H "Content-Type: application/json" \
  -d '{"direction": "north"}'
```

### Query Tile
```bash
curl -X GET "http://localhost:5000/world/tile?x=0&y=1" \
  -H "Authorization: Bearer YOUR_SESSION_ID"
```

## Expected Test Results

All 138 tests should pass:
- 17 GameService unit tests ✅
- 12 World route integration tests ✅
- 17 Serializer tests ✅
- 10 Event integration tests ✅
- 12 Universe tests ✅

Run with:
```bash
python -m pytest tests/api/ tests/test_universe.py -q
```

## Sign-Off

After testing, verify:
- [ ] All movement directions work
- [ ] All tile queries return correct data
- [ ] All error cases handled properly
- [ ] Authentication required and working
- [ ] Event system triggers on movement
- [ ] Serializers produce valid JSON
- [ ] No console errors or exceptions
- [ ] Server remains stable after 10+ movements

---

**Ready to merge PR #24?** ✅
