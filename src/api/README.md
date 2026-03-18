# Heart of Virtue - Flask REST API

**Phase 1: Backend API Extraction & Foundation**

This directory contains the Flask-based REST API layer for Heart of Virtue, wrapping the existing Python game engine to enable web-based gameplay.

## Project Structure

```
src/api/
├── app.py                 # Flask app factory
├── config.py              # Configuration (dev, test, prod)
├── routes/                # REST endpoint blueprints
│   ├── world.py          # World navigation endpoints
│   ├── inventory.py      # Inventory management
│   ├── equipment.py      # Equipment system
│   ├── combat.py         # Combat endpoints
│   ├── player.py         # Player status
│   ├── saves.py          # Save/load management
│   └── auth.py           # Authentication
├── services/              # Business logic layer
│   ├── game_service.py   # Stateless game wrapper
│   └── session_manager.py # Session lifecycle
├── handlers/              # Event/error handlers
│   ├── websocket_handler.py
│   └── error_handler.py
├── middleware/            # Request/response middleware
│   └── auth_middleware.py
└── schemas/               # OpenAPI schemas
```

## Milestone 1: Flask Foundation (HV-37)

**Status:** In Progress  
**Timeline:** Nov 10-24, 2025  
**Effort:** 40-50 hours

### Deliverables

- [x] Flask project structure with app factory
- [x] GameService wrapper class skeleton
- [x] SessionManager (in-memory sessions)
- [x] All route blueprints (auth, world, player, inventory, equipment, combat, saves)
- [x] Error handling middleware
- [x] Request validation helpers
- [x] Unit tests for GameService & SessionManager (27 tests)
- [x] OpenAPI/Swagger configuration
- [ ] Install dependencies & full integration testing
- [ ] CI/CD ready

### Files Created

| File | Purpose | Status |
|------|---------|--------|
| `src/api/__init__.py` | Package init | ✅ |
| `src/api/app.py` | Flask app factory | ✅ |
| `src/api/config.py` | Configuration classes | ✅ |
| `src/api/services/session_manager.py` | Session management | ✅ |
| `src/api/services/game_service.py` | Game logic wrapper | ✅ |
| `src/api/services/validators.py` | Input validation | ✅ |
| `src/api/handlers/error_handler.py` | Global error handlers | ✅ |
| `src/api/routes/auth.py` | Auth endpoints | ✅ |
| `src/api/routes/world.py` | World navigation | ✅ |
| `src/api/routes/player.py` | Player status | ✅ |
| `src/api/routes/inventory.py` | Inventory management | ✅ |
| `src/api/routes/equipment.py` | Equipment system | ✅ |
| `src/api/routes/combat.py` | Combat endpoints | ✅ |
| `src/api/routes/saves.py` | Save management | ✅ |
| `src/api/schemas/openapi.py` | OpenAPI schema generator | ✅ |
| `tests/api/test_session_manager.py` | SessionManager tests (12) | ✅ |
| `tests/api/test_game_service.py` | GameService tests (15) | ✅ |
| `tests/api/test_routes_integration.py` | Integration tests (27) | ✅ |
| `tests/api/test_validators.py` | Validator tests (28) | ✅ |
| `tests/api/test_error_handlers.py` | Error handler tests (9) | ✅ |
| `requirements-api.txt` | Python dependencies | ✅ |

### Installation

```bash
# Activate virtual environment
.venv\Scripts\Activate.ps1

# Install API dependencies
pip install -r requirements-api.txt

# Run all API tests
pytest tests/api/ -v --cov=src/api

# Run specific test file
pytest tests/api/test_validators.py -v
```

### API Endpoints (Phase 1 - Complete)

**Health Check & Documentation**
```
GET /health                     # Server health status
GET /api/info                   # API information
GET /api/openapi.json           # OpenAPI 3.0 schema
GET /api/docs                   # Swagger UI
```

**Authentication** (3 endpoints)
```
POST /auth/login                # Create session
POST /auth/logout               # End session
GET /auth/validate              # Validate token
```

**World Navigation** (3 endpoints)
```
GET /world/                     # Current room info
POST /world/move                # Move in direction (north/south/east/west)
GET /world/tile?x=0&y=0        # Get tile at coordinates
```

**Player** (2 endpoints)
```
GET /player/status              # Health, level, experience
GET /player/stats               # Attributes (STR, DEX, VIT, etc.)
```

**Inventory** (3 endpoints)
```
GET /inventory/                 # List items and weight
POST /inventory/take            # Pick up item
POST /inventory/drop            # Drop item
```

**Equipment** (3 endpoints)
```
GET /equipment/                 # Current equipment by slot
POST /equipment/equip           # Equip item (recalc stats)
POST /equipment/unequip         # Remove equipment
```

**Combat** (3 endpoints)
```
POST /combat/start              # Initiate combat
POST /combat/move               # Execute action (attack/defend/cast/item/flee)
GET /combat/status              # Battle state
```

**Saves** (4 endpoints)
```
GET /saves/                     # List all saves
POST /saves/                    # Create new save
POST /saves/<id>/load           # Load save
DELETE /saves/<id>              # Delete save
```

## Usage Examples

### 1. Login & Create Session

```bash
curl -X POST http://localhost:5000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"character_name": "Jean Claire", "slot": 0}'
```

Response:
```json
{
  "success": true,
  "data": {
    "session_id": "abc123def456",
    "expires_at": "2025-01-15T10:30:00",
    "player": {
      "name": "Jean Claire",
      "level": 1,
      "experience": 0,
      "health": 100,
      "max_health": 100
    }
  }
}
```

### 2. Move Player

```bash
curl -X POST http://localhost:5000/world/move \
  -H "Authorization: Bearer abc123def456" \
  -H "Content-Type: application/json" \
  -d '{"direction": "north"}'
```

### 3. Get Inventory

```bash
curl -X GET http://localhost:5000/inventory/ \
  -H "Authorization: Bearer abc123def456"
```

Response:
```json
{
  "success": true,
  "data": {
    "items": [
      {"name": "Shortsword", "type": "weapon", "weight": 5},
      {"name": "Leather Armor", "type": "armor", "weight": 10}
    ],
    "total_weight": 15,
    "max_weight": 100
  }
}
```

### 4. Equip Item

```bash
curl -X POST http://localhost:5000/equipment/equip \
  -H "Authorization: Bearer abc123def456" \
  -H "Content-Type: application/json" \
  -d '{"item_index": 0}'
```

### 5. Start Combat

```bash
curl -X POST http://localhost:5000/combat/start \
  -H "Authorization: Bearer abc123def456" \
  -H "Content-Type: application/json" \
  -d '{"enemy_id": "cave_bat_1"}'
```

### 6. Create Save

```bash
curl -X POST http://localhost:5000/saves/ \
  -H "Authorization: Bearer abc123def456" \
  -H "Content-Type: application/json" \
  -d '{"save_name": "After Boss Fight"}'
```

## API Documentation

### Swagger UI
Once the server is running, access interactive API documentation at:
```
http://localhost:5000/api/docs
```

### OpenAPI Schema
Download the complete OpenAPI 3.0 schema at:
```
http://localhost:5000/api/openapi.json
```

## Running the API Server

```bash
# Development mode (with auto-reload)
python tools/run_api.py

# Or manually with Flask CLI
export FLASK_APP=src/api/app.py
export FLASK_ENV=development
flask run

# With SocketIO support (for real-time combat)
python tools/run_api.py --socketio
```

Server will start at `http://localhost:5000`

## Testing

```bash
# All API tests
pytest tests/api/ -v

# With coverage report
pytest tests/api/ --cov=src/api --cov-report=term-missing

# Specific test file
pytest tests/api/test_validators.py -v

# Specific test
pytest tests/api/test_validators.py::test_validate_direction_valid -v

# Run validator tests only
pytest tests/api/test_validators.py -v

# Run error handler tests only
pytest tests/api/test_error_handlers.py -v

# Run all integration tests
pytest tests/api/test_routes_integration.py -v
```

## Architecture Notes

### GameService Pattern
The `GameService` class provides a **stateless** interface to the game engine. Each method:
- Takes a `Player` object as input
- Uses `self.universe` to query world state
- Returns JSON-serializable dictionaries
- Does NOT hold session state (that's `SessionManager`'s job)

### Session Management
The `SessionManager` handles:
- Session creation (24-hour lifetime)
- Session expiration cleanup
- Player-session association
- In-memory storage (Phase 1 only; Phase 2 will use database)

### Error Handling
All endpoints return JSON with structure:
```json
{
  "success": true|false,
  "data": {},
  "error": "error message if applicable"
}
```

Global error handlers manage all HTTP errors:
- **400**: Bad Request (validation errors)
- **401**: Unauthorized (invalid session)
- **403**: Forbidden (insufficient permissions)
- **404**: Not Found (missing resource)
- **422**: Unprocessable Entity (semantic error)
- **429**: Too Many Requests (rate limit)
- **500**: Internal Server Error (unexpected exception)

### Input Validation
All request data is validated using helper functions in `services/validators.py`:
- `validate_required_fields()` - Check required fields present
- `validate_direction()` - Cardinal directions only
- `validate_coordinates()` - X/Y bounds checking
- `validate_item_slot()` - Equipment slot validation
- `validate_combat_action()` - Legal combat actions
- And more...

## Next Steps (Phase 2+)


1. **Database Integration**: Replace in-memory sessions with PostgreSQL
2. **Authentication**: Add JWT/OAuth support
3. **Route Implementations**: Build all endpoint blueprints
4. **WebSocket**: Real-time combat updates via SocketIO
5. **Rate Limiting**: Throttle API endpoints
6. **Logging**: Centralized request/response logging
7. **Documentation**: Generate OpenAPI schema from code
8. **Performance**: Load testing and optimization

## Jira Tracking

- **Epic**: HV-36 - Phase 1: Backend API Extraction & Flask Foundation
- **Story**: HV-37 - Milestone 1: Flask Foundation & Session Management
- **Stories**: HV-38 through HV-41 - Milestones 2-5

See `docs/IMPLEMENTATION_PLAN.md` for full details.

## Code Quality Standards

- **Format**: Black (100 char line length)
- **Lint**: flake8 (max 100 chars, ignore E501)
- **Type Hints**: Required for all public methods
- **Docstrings**: Google-style
- **Test Coverage**: >85% for API layer

```bash
# Format code
black src/api tests/api

# Check lint
flake8 src/api tests/api --max-line-length=100 --ignore=E501

# Type check (with mypy when set up)
# mypy src/api
```

## Resources

- [IMPLEMENTATION_PLAN.md](../../docs/IMPLEMENTATION_PLAN.md) - Full implementation timeline
- [BACKEND_API_ARCHITECTURE.md](../../docs/BACKEND_API_ARCHITECTURE.md) - API design document
- [Flask Documentation](https://flask.palletsprojects.com/)
- [Flask-SocketIO](https://python-socketio.readthedocs.io/)

---

**Document**: API Foundation README  
**Created**: November 5, 2025  
**Status**: Phase 1 In Progress

