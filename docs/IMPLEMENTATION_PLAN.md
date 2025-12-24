# Heart of Virtue - Web Migration Implementation Plan

**Phase 1: Backend API Extraction & Flask Foundation**

**Document Version:** 1.0  
**Created:** November 5, 2025  
**Target Start:** Week of November 10, 2025  
**Estimated Duration:** 6-8 weeks  

---

## Executive Summary

This document outlines the complete implementation plan for Phase 1 of the Heart of Virtue web migration: extracting the existing Python game engine into a Flask-based REST API with WebSocket support for real-time combat.

**Phase 1 Scope:**
- Extract core game logic into a stateless GameService wrapper
- Build REST API layer with 15+ endpoints covering world navigation, inventory, combat, and saves
- Implement session management for player persistence
- Add WebSocket support for real-time combat updates
- Comprehensive test coverage with integration tests
- Deployment-ready backend with documentation

**Success Criteria:**
- ✅ All core game operations accessible via REST/WebSocket APIs
- ✅ 80%+ test coverage for API layer
- ✅ Backend deployable to cloud (tested locally)
- ✅ API documentation complete (OpenAPI/Swagger)
- ✅ Frontend team can begin React implementation

---

## Project Context

### Current State
- **Codebase:** 18,883 LOC across 42 Python files
- **Project Age:** 712 commits over ~2 years
- **Historical Velocity:** ~1 commit/day average
- **Current UI:** Terminal-based (asciimatics + neotermcolor)
- **Game Engine:** Mature and stable (player, combat, NPC, inventory, tiles, maps)

### Target State (End of Phase 1)
- **Architecture:** Flask + Python game engine + in-memory session storage
- **API Format:** JSON REST + WebSocket
- **Deployment:** Standalone Python server (Docker-ready)
- **Frontend Ready:** React team can build against documented API

### Technology Stack
| Component | Technology | Justification |
|-----------|-----------|---------------|
| Web Framework | Flask 2.3+ | Lightweight, Pythonic, integrates seamlessly with existing code |
| WebSocket | Flask-SocketIO | Battle real-time updates without polling |
| Session Storage | In-memory (Phase 1) | Fast iteration; migrate to Redis/DB in Phase 2 |
| Testing | pytest + pytest-asyncio | Async test support for WebSocket, existing pytest infrastructure |
| Documentation | OpenAPI 3.0 + Swagger UI | Auto-generated API docs, widely used in web dev |
| Deployment | Docker (optional) | Tested locally, ready for cloud deployment |

---

## Phase 1 Milestones

### Milestone 1: Foundation (Weeks 1-2) - **Target: Nov 10-24**
**Deliverables:**
- Flask project structure with blueprints
- GameService wrapper (basic version)
- Session manager (in-memory)
- Unit tests for GameService & session manager
- OpenAPI schema skeleton

**Success Metrics:**
- ✅ Can create/load/save player via API
- ✅ Session IDs persist for 24 hours
- ✅ Test coverage >80%
- ✅ Swagger UI displays available endpoints

**Commits:** 15-20  
**Effort:** 40-50 hours

---

### Milestone 2: World Navigation (Weeks 3-4) - **Target: Nov 25-Dec 8**
**Deliverables:**
- World endpoint (current room/map data)
- Movement endpoints (north/south/east/west)
- Tile queries (items, NPCs, objects, events)
- Map/world state serializers
- Integration tests for navigation

**Success Metrics:**
- ✅ Can move between all tiles in test map
- ✅ Items/NPCs/objects serialize correctly
- ✅ Event triggers fire on tile entry
- ✅ Test coverage >85%

**Commits:** 20-25  
**Effort:** 50-60 hours

---

### Milestone 3: Inventory & Equipment (Weeks 5-6) - **Target: Dec 9-22**
**Deliverables:**
- Inventory endpoints (list, drop, take, examine)
- Equipment endpoints (equip, unequip, compare)
- Item serializers (full item hierarchy)
- Stat calculation endpoints
- Currency/gold management
- Integration tests for inventory operations

**Success Metrics:**
- ✅ Full inventory visible via API
- ✅ Equipment changes update stats
- ✅ Weight system enforced
- ✅ Merchandise flags respected
- ✅ Test coverage >85%

**Commits:** 18-22  
**Effort:** 45-55 hours

---

### Milestone 4: Combat System (Weeks 6-7) - **Target: Dec 23-Jan 5**
**Deliverables:**
- Combat initiation endpoint
- Move execution endpoints (attack, defend, cast, item use)
- WebSocket real-time updates (turn notifications, damage, status)
- Combat state serializers
- NPC AI integration
- Combat log endpoint
- Comprehensive combat tests

**Success Metrics:**
- ✅ Combat flows via WebSocket without polling
- ✅ All move types (attack, defend, cast, item) functional
- ✅ NPC AI makes decisions
- ✅ Status effects apply correctly
- ✅ Combat resolves to victory/defeat
- ✅ Test coverage >85%

**Commits:** 25-30  
**Effort:** 65-75 hours

---

### Milestone 5: Saves & Polish (Week 8) - **Target: Jan 6-12**
**Deliverables:**
- Save management endpoints (list, create, load, delete)
- Error handling & validation layer
- Rate limiting for API endpoints
- Documentation review & OpenAPI finalization
- Performance optimization & load testing
- Final integration tests

**Success Metrics:**
- ✅ Saves persist across sessions
- ✅ Can load any previous save
- ✅ API responds in <200ms under normal load
- ✅ Error messages are clear & actionable
- ✅ Full API documentation complete

**Commits:** 15-20  
**Effort:** 40-50 hours

---

## Implementation Architecture

### Directory Structure
```
src/
  api/                          # NEW: Flask application
    __init__.py
    app.py                      # Flask app factory
    config.py                   # Configuration (DEBUG, SECRET_KEY, etc.)
    
    routes/
      __init__.py
      world.py                  # GET /world, /world/move, /world/tile
      inventory.py              # GET/POST /inventory/*, /equipment/*
      combat.py                 # POST /combat/start, /combat/move, GET /combat/status
      player.py                 # GET /player/status, /player/stats
      saves.py                  # GET/POST /saves/*
      
    handlers/
      __init__.py
      websocket_handler.py       # SocketIO events for real-time combat
      error_handler.py           # Global error handling
      
    services/
      __init__.py
      game_service.py            # Wrapper around Universe + Player (stateless)
      session_manager.py         # Player session lifecycle
      serializers.py             # JSON serialization (Player, Item, NPC, etc.)
      validators.py              # Input validation
      
    middleware/
      __init__.py
      auth_middleware.py         # Session ID validation
      
    schemas/
      __init__.py
      openapi.yaml               # OpenAPI/Swagger schema
      
  game/                         # EXISTING: Unchanged game engine
    player.py
    combat.py
    npc.py
    items.py
    universe.py
    ... (all other existing modules)
    
tests/
  api/                          # NEW: API tests
    __init__.py
    test_game_service.py
    test_routes_world.py
    test_routes_inventory.py
    test_routes_combat.py
    test_routes_player.py
    test_routes_saves.py
    test_websocket_combat.py
    test_session_manager.py
    test_serializers.py
    test_integration_flow.py
```

---

## API Specification (RESTful + WebSocket)

### Authentication Flow
**Session-based (no OAuth initially)**
```
POST /auth/login
  body: { username, password }
  → { session_id, player_id, expires_at }

POST /auth/logout
  headers: { Authorization: Bearer <session_id> }
  → { success: true }
```

### World Navigation
```
GET /world
  headers: { Authorization: Bearer <session_id> }
  → { current_room, description, exits, items, npcs, objects }

POST /world/move
  body: { direction: "north|south|east|west" }
  headers: { Authorization: Bearer <session_id> }
  → { current_room, moved: true, events_triggered: [...] }

GET /world/tile
  query: { x, y }
  → { tile_data, items, npcs, objects, events }
```

### Inventory
```
GET /inventory
  → { items: [...], weight: 150/500, gold: 2500 }

POST /inventory/take
  body: { item_id }
  → { success: true, item_name, new_weight }

POST /inventory/drop
  body: { item_id }
  → { success: true, item_name }

POST /inventory/examine
  body: { item_id }
  → { name, description, weight, subtype, modifiers, ... }

GET /equipment
  → { head, body, hands, feet, back, neck, equipped: [...] }

POST /equipment/equip
  body: { item_id }
  → { success: true, stat_changes: { hp: +10, damage: +5, ... } }

POST /equipment/unequip
  body: { slot: "head|body|..." }
  → { success: true, stat_changes: {...} }
```

### Combat
```
POST /combat/start
  body: { enemy_id }
  → { combat_id, combatants: [...], distance: [...], turn_order: [...] }

POST /combat/move
  body: { move_type: "attack|defend|cast|item", move_id, target_id? }
  → { success: true, queued: true, turn: 5 }

GET /combat/status
  → { combat_active: true, current_turn, combatants, log_entries: [...] }

WebSocket: /socket.io
  Events:
    - combat:turn_ready → { player_turn_in: 30s }
    - combat:action → { actor, move, target, damage, status, ... }
    - combat:end → { victor, loot, exp_gained }
```

### Player Status
```
GET /player/status
  → { name, level, exp, hp, max_hp, state: "normal|poisoned|...", ... }

GET /player/stats
  → { strength, dexterity, vitality, intelligence, wisdom, speed, ... }
```

### Saves
```
GET /saves
  → { saves: [ { id, name, timestamp, location, level } ] }

POST /saves
  body: { name }
  → { save_id, created_at }

POST /saves/:id/load
  → { success: true, player_data }

DELETE /saves/:id
  → { success: true }
```

---

## Technical Implementation Details

### GameService (Core Abstraction)
**Responsibility:** Provide stateless interface to game logic  
**Location:** `src/api/services/game_service.py`

```python
class GameService:
    def __init__(self, universe):
        self.universe = universe
    
    # World
    def get_current_room(self, player) -> dict
    def move_player(self, player, direction: str) -> dict
    def get_tile(self, x: int, y: int) -> dict
    
    # Inventory
    def get_inventory(self, player) -> dict
    def take_item(self, player, item_id) -> dict
    def drop_item(self, player, item_id) -> dict
    def examine_item(self, player, item_id) -> dict
    
    # Equipment
    def get_equipment(self, player) -> dict
    def equip_item(self, player, item_id) -> dict
    def unequip_item(self, player, slot) -> dict
    
    # Combat
    def start_combat(self, player, enemy_id) -> dict
    def execute_move(self, player, move_type, move_id, target_id=None) -> dict
    def get_combat_status(self, player) -> dict
    
    # Player
    def get_player_status(self, player) -> dict
    def get_player_stats(self, player) -> dict
    
    # Saves
    def save_game(self, player, name: str) -> str
    def load_game(self, player_id: str) -> Player
    def list_saves(self) -> list
    def delete_save(self, save_id: str) -> bool
```

### Session Manager
**Responsibility:** Manage player sessions (create, load, save, expire)  
**Location:** `src/api/services/session_manager.py`

```python
class SessionManager:
    def __init__(self):
        self.sessions = {}  # session_id → Session
        self.players = {}   # player_id → Player
    
    def create_session(self, username) -> str  # Returns session_id
    def get_session(self, session_id) -> Session
    def get_player(self, session_id) -> Player
    def save_session(self, session_id) -> bool
    def expire_session(self, session_id) -> bool
    def cleanup_expired() → None  # Called periodically
```

### Serializers
**Responsibility:** Convert game objects to JSON-safe dicts  
**Location:** `src/api/services/serializers.py`

```python
# Each class returns a serializable dict
class PlayerSerializer:
    @staticmethod
    def serialize(player) -> dict

class ItemSerializer:
    @staticmethod
    def serialize(item) -> dict

class NPCSerializer:
    @staticmethod
    def serialize(npc) -> dict

class TileSerializer:
    @staticmethod
    def serialize(tile) -> dict

class BattlefieldSerializer:
    @staticmethod
    def serialize(battlefield) -> dict
```

### WebSocket Integration (Combat Real-Time)
**Framework:** Flask-SocketIO  
**Events:**
- `combat:player_turn` → Frontend displays "Your turn" UI
- `combat:npc_turn` → Frontend shows NPC taking action
- `combat:damage` → Frontend animates damage number
- `combat:status_change` → Frontend updates status effects
- `combat:end` → Frontend shows victory/defeat screen

---

## Testing Strategy

### Unit Tests
**Target Coverage:** 85%+
- GameService methods (isolated, mocked universe)
- SessionManager (CRUD operations)
- Serializers (all item/NPC types)
- Validators (input validation)

### Integration Tests
**Scope:** Full request → response cycles
- World navigation (move through 5 tiles)
- Inventory workflow (take, equip, drop)
- Combat flow (start → 3 turns → victory)
- Save/load cycle (save game → load → verify state)
- WebSocket combat updates (real-time message flow)

### Load Testing
**Goal:** Ensure <200ms response time under load
- 50 concurrent sessions
- Sustained 10 req/sec
- Memory profiling (target: <500MB for 50 sessions)

### Manual Testing Checklist
- [ ] New player creation flow
- [ ] Save/load preserves all state
- [ ] NPC AI responds to player actions
- [ ] Combat ends in victory/defeat
- [ ] Event triggers on tile entry
- [ ] Serialization round-trip (object → JSON → object)

---

## Development Workflow

### Prerequisites
- Python 3.13+
- Virtual environment activated (`.venv/Scripts/Activate.ps1`)
- Dependencies installed (`pip install -r requirements-api.txt`)

### Daily Workflow
```powershell
# Activate environment
.venv\Scripts\Activate.ps1

# Create feature branch
git checkout -b api/feature-name

# Make changes, run tests frequently
pytest tests/api/ -v --cov=src/api --cov-report=term-missing

# Commit with reference to Jira ticket
git commit -m "HOVU-123: Implement world navigation endpoints"

# Push for review
git push -u origin api/feature-name
```

### Code Quality Standards
- **Format:** Black (auto-format on save)
- **Lint:** flake8 (line length 100, ignore E501)
- **Type Hints:** Required for all public methods
- **Docstrings:** Google-style for public functions
- **Test Coverage:** >85% in `src/api/`, >70% overall

### Pull Request Process
1. Create feature branch from `phase-1/backend-api`
2. Write code + tests (TDD where possible)
3. Run full test suite locally
4. Push and open PR
5. Code review + CI passes
6. Merge to `phase-1/backend-api`
7. Final merge to `master` at milestone completion

---

## Resource Requirements

### Personnel
- **Primary Developer:** 1 FTE (6-8 weeks)
- **Tech Lead/Reviewer:** 0.25 FTE (design reviews, unblocking)
- **QA/Testing:** 0.15 FTE (manual testing, test infrastructure)

### Infrastructure (Phase 1 Local Development)
- Development machine (4GB RAM, SSD recommended)
- Git repository (already set up)
- Optional: Docker for isolated testing

### Infrastructure (Phase 2 Deployment)
- Cloud hosting (AWS/Azure/Render/Railway)
- Database (PostgreSQL or managed service)
- Redis (for session storage)
- CDN for frontend assets
- SSL/TLS certificates

---

## Risk Management

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| Game engine has hidden dependencies | Medium | High | Spike week 1: document all imports & dependencies |
| Combat system is tightly coupled to terminal I/O | Medium | High | Refactor I/O layer early (Week 2) |
| Real-time WebSocket updates unreliable | Low | High | Prototype WebSocket in Milestone 4 spike |
| Session management causes data races | Low | Medium | Use locks/queues, comprehensive integration tests |
| JSON serialization misses edge cases | Medium | Medium | Test all item/NPC subtypes early |
| Performance degradation with many sessions | Low | Medium | Load test weekly, optimize hot paths |

---

## Success Criteria & Acceptance

### Phase 1 Complete When:
- ✅ All 5 milestones delivered on schedule
- ✅ API documentation 100% complete (Swagger UI)
- ✅ Test coverage >85% for `src/api/`
- ✅ 15+ endpoints tested and working
- ✅ WebSocket combat tested in browser
- ✅ Save/load cycle preserves all game state
- ✅ Performance benchmarks met (<200ms p95)
- ✅ Ready for React frontend team to begin Phase 2

### Phase 1 Outcomes Enabling Phase 2:
- Documented REST API (OpenAPI schema)
- Working example WebSocket implementation
- JSON serialization patterns established
- Session management reference implementation
- Deployment-ready server code

---

## Post-Phase 1: Phase 2 Handoff

**Frontend Team Will:**
1. Review OpenAPI schema and example requests
2. Set up React with TypeScript
3. Build responsive two-panel layout (per mockup)
4. Implement real-time WebSocket client
5. Add combat animations and visual effects

**Backend Support During Phase 2:**
- 0.25 FTE debugging API issues
- 0.25 FTE performance optimization
- 0.1 FTE documentation updates

---

## Appendices

### Appendix A: Dependency Analysis
**Key existing modules used by GameService:**
- `universe.py` - Map/tile management
- `player.py` - Player state & methods
- `combat.py` - Combat execution
- `items.py` - Item system
- `npc.py` - Enemy AI
- `moves.py` - Combat moves
- `functions.py` - Utility functions

**Dependencies to avoid exposing:**
- Terminal I/O (asciimatics, neotermcolor)
- Input system (blocking input())
- Tkinter (CombatBattlefieldWindow)

### Appendix B: Sample Request/Response

**POST /world/move**
```json
Request:
{
  "direction": "north"
}

Response:
{
  "current_room": { "x": 5, "y": 6, "name": "Forest Path" },
  "description": "A winding forest path...",
  "exits": ["north", "south", "east"],
  "items": [
    { "id": "item_001", "name": "Gold Coin", "quantity": 5 }
  ],
  "npcs": [
    { "id": "npc_001", "name": "Forest Guardian", "level": 12 }
  ],
  "events_triggered": [
    { "event_id": "ch01_start", "message": "The path ahead glows..." }
  ],
  "moved": true
}
```

### Appendix C: Estimated Commit History
**Total Phase 1 commits:** ~100-120
- Foundation: 15-20
- Navigation: 20-25
- Inventory: 18-22
- Combat: 25-30
- Polish: 15-20
- Misc/fixes: 10-15

**Average commit size:** ~150 LOC (API layer only, game engine unchanged)

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Nov 5, 2025 | Initial implementation plan |
| (Future) | TBD | Milestone completions, risk adjustments |

---

**Document Owner:** Development Team  
**Last Updated:** November 5, 2025  
**Review Status:** Ready for approval

