# HV-38: Milestone 2 - World Navigation & Tile System

**Branch**: `api/hv-38-world-navigation`  
**Status**: IN PROGRESS  
**Target**: 50-60 hours, 20-25 commits  
**Success Metrics**: >85% test coverage, all movement endpoints working

## Overview

Expand the Flask API to support full world navigation, tile queries, and event integration. This builds on the HV-37 foundation (SessionManager, GameService, error handlers) to create a playable game world.

## Key Deliverables

### 1. World Route Handler (`src/api/routes/world.py`)
- **GET /world/** - Current room/tile data (description, items, NPCs, events)
- **POST /world/move** - Player movement (direction: north/south/east/west)
- **GET /world/tile** - Tile queries (x, y coordinates)
- All endpoints require Bearer token auth
- Return consistent JSON with success/error fields

### 2. Movement Endpoints (Enhanced)
- Validate all 4 cardinal directions
- Check tile existence (no OOB movements)
- Trigger entry events on arrival
- Return room data after movement
- Handle blocked paths/objects

### 3. World/Tile Serializers
- `WorldSerializer` - Convert Universe/maps to API JSON
- `TileSerializer` - Convert MapTile objects to JSON
- `ItemSerializer` - Items on tiles
- `NPCSerializer` - NPCs with stats/inventory
- `EventSerializer` - Event data and triggers

### 4. Event System Integration
- Connect tile entry events to world endpoints
- Fire "on_enter" events when player moves
- Return triggered events in movement response
- Handle event consequences (dialogue, combat, items)

### 5. Integration Tests (>85% coverage)
- Test all 4 movement directions
- Test OOB movement validation
- Test event triggers on entry
- Test tile queries
- Test serialization of complex objects

## Technical Approach

### Phase 1: Expand GameService (Hours 1-8)
1. Add `move_player(player, direction)` → returns movement result
2. Add `get_current_room(player)` → returns room data
3. Add `get_tile(x, y)` → returns tile data
4. Add `trigger_tile_events(player, tile)` → fires events

### Phase 2: Create World Routes (Hours 9-20)
1. Create `src/api/routes/world.py` with 3 endpoints
2. Implement auth/validation for all routes
3. Add error handling for invalid movements
4. Format responses with proper JSON structure

### Phase 3: Build Serializers (Hours 21-32)
1. Create `src/api/serializers/world.py`
2. Implement TileSerializer (handles NPCs, items, objects)
3. Implement ItemSerializer (equipment, consumables)
4. Implement EventSerializer (with consequences)

### Phase 4: Event Integration (Hours 33-44)
1. Wire tile entry events to movement endpoint
2. Execute event logic after player moves
3. Return event results in response
4. Handle dialogue/combat/item pickups

### Phase 5: Testing & Polish (Hours 45-60)
1. Write 30+ integration tests for world endpoints
2. Test edge cases (map boundaries, blocked tiles)
3. Test event firing and consequences
4. Achieve >85% coverage
5. Code cleanup and documentation

## API Endpoints (Draft)

```
GET /world/
├─ Headers: Authorization: Bearer <session_id>
└─ Response: {success: true, room: {x, y, name, description, exits, items, npcs, events}}

POST /world/move
├─ Headers: Authorization: Bearer <session_id>
├─ Body: {direction: "north"|"south"|"east"|"west"}
└─ Response: {success: true, new_position: {x, y}, room: {...}, events_triggered: [...]}

GET /world/tile?x=1&y=2
├─ Headers: Authorization: Bearer <session_id>
└─ Response: {success: true, tile: {x, y, name, items, npcs, objects}}
```

## Dependencies

- **GameService** enhancements (move_player, get_tile, trigger_events)
- **Universe/Map** system for world data
- **Event system** (already exists in game engine)
- **Serializers** for JSON conversion
- **Test fixtures** for world state setup

## Known Challenges

1. **Circular imports** - GameService imports game engine modules
2. **Event system complexity** - Different event types with different logic
3. **Tile serialization** - NPCs/items can have complex nested data
4. **Test isolation** - Need to mock Universe for tests

## Success Criteria

- ✅ Can move between all tiles in test map
- ✅ Items/NPCs/objects serialize correctly
- ✅ Event triggers fire on tile entry
- ✅ OOB movements return 400 error
- ✅ Test coverage >85%
- ✅ All 89 HV-37 tests still passing

## Git Workflow

1. Create endpoint stubs with proper decorators
2. Implement movement logic (GameService method)
3. Add serializers for tile data
4. Wire event triggers
5. Write comprehensive tests
6. Clean up and optimize
7. Commit with clear messages

## Estimated Timeline

| Phase | Hours | Commits | Status |
|-------|-------|---------|--------|
| GameService expansion | 8 | 3 | Pending |
| World routes | 12 | 5 | Pending |
| Serializers | 12 | 4 | Pending |
| Event integration | 12 | 5 | Pending |
| Testing & Polish | 16 | 8 | Pending |
| **Total** | **60** | **25** | **IN PROGRESS** |

---

**Next Step**: Expand GameService with movement and tile methods

