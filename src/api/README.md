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
- [ ] Basic route blueprints
- [ ] Unit tests for GameService & SessionManager
- [ ] OpenAPI/Swagger configuration
- [ ] CI/CD ready

### Files Created

| File | Purpose | Status |
|------|---------|--------|
| `src/api/__init__.py` | Package init | ✅ |
| `src/api/app.py` | Flask app factory | ✅ |
| `src/api/config.py` | Configuration classes | ✅ |
| `src/api/services/session_manager.py` | Session management | ✅ |
| `src/api/services/game_service.py` | Game logic wrapper | ✅ |
| `tests/api/test_session_manager.py` | SessionManager tests | ✅ |
| `tests/api/test_game_service.py` | GameService tests | ✅ |
| `requirements-api.txt` | Python dependencies | ✅ |

### Installation

```bash
# Activate virtual environment
.venv\Scripts\Activate.ps1

# Install API dependencies
pip install -r requirements-api.txt

# Run tests
pytest tests/api/ -v --cov=src/api
```

### API Endpoints (Phase 1 - Planned)

**Health Check**
```
GET /health
GET /api/info
```

**Authentication** (Phase 2)
```
POST /auth/login
POST /auth/logout
```

**World Navigation** (Phase 2)
```
GET /world                      # Current room
POST /world/move                # Move in direction
GET /world/tile?x=0&y=0        # Tile info
```

**Inventory** (Phase 3)
```
GET /inventory
POST /inventory/take
POST /inventory/drop
POST /inventory/examine
```

**Equipment** (Phase 3)
```
GET /equipment
POST /equipment/equip
POST /equipment/unequip
```

**Combat** (Phase 4)
```
POST /combat/start
POST /combat/move
GET /combat/status
WebSocket /socket.io            # Real-time updates
```

**Player** (Phase 2)
```
GET /player/status
GET /player/stats
```

**Saves** (Phase 5)
```
GET /saves
POST /saves
POST /saves/:id/load
DELETE /saves/:id
```

## Running the API Server

```bash
# Development mode
python -m src.api.app

# Or with Flask CLI
export FLASK_APP=src/api/app.py
export FLASK_ENV=development
flask run

# With SocketIO support (for real-time combat)
python -m src.api.socketio_server
```

Server will start at `http://localhost:5000`

## Testing

```bash
# All tests
pytest tests/api/ -v

# With coverage report
pytest tests/api/ --cov=src/api --cov-report=term-missing

# Specific test file
pytest tests/api/test_session_manager.py -v

# Specific test
pytest tests/api/test_session_manager.py::TestSessionManager::test_create_session -v
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
