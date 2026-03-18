# Milestone 2: World Navigation Implementation Plan

**Date Started:** November 8, 2025  
**Target Completion:** December 8, 2025 (4 weeks)  
**Branch:** `phase-2/world-navigation`

## Overview

Milestone 2 focuses on implementing real world navigation with the actual game universe. Key achievements from Milestone 1 enable this:
- ✅ Flask REST API foundation established
- ✅ GameService wrapper created
- ✅ Session management working
- ✅ 351 tests all passing
- ✅ GameService initialized with test universe

## Objectives

### Primary Goals
1. **Real Universe Integration** - Load actual game maps from JSON instead of mock tiles
2. **Complete World Endpoints** - GET /world, POST /world/move, GET /world/tile
3. **Comprehensive Serialization** - Tile data, items, NPCs, objects, events all JSON-safe
4. **Event System** - Trigger events on tile entry, event data serialization
5. **Integration Tests** - Full movement workflows with real game state

### Success Criteria
- ✅ Move through actual game maps without errors
- ✅ Items/NPCs/objects properly serialized to JSON
- ✅ Events trigger and serialize correctly
- ✅ All tile positions accessible
- ✅ Test coverage >85%
- ✅ <200ms response time on world endpoints

## Implementation Tasks

### Phase 1: Universe Loading (Days 1-3)
- [ ] Replace mock tiles with real game universe
- [ ] Test universe initialization with actual maps
- [ ] Verify get_tile() works with real coordinates
- [ ] Implement universe state management
- [ ] Add error handling for out-of-bounds access

### Phase 2: Serializers Enhancement (Days 4-7)
- [ ] Item serialization (all subtypes: Weapon, Armor, Consumable, etc.)
- [ ] NPC serialization (full AI state, equipment, inventory)
- [ ] Object serialization (doors, chests, shrines, etc.)
- [ ] Event serialization (event type, parameters, triggers)
- [ ] World state serialization (tile-by-tile data)

### Phase 3: Endpoint Enhancement (Days 8-11)
- [ ] GET /world/ - Load player's current tile with full context
- [ ] POST /world/move - Movement with boundary checking & event triggering
- [ ] GET /world/tile - Query any tile by coordinates
- [ ] Direction validation (north, south, east, west)
- [ ] Event processing on movement

### Phase 4: Testing & Validation (Days 12-14)
- [ ] Integration tests for 5-tile movement sequences
- [ ] Event triggering tests
- [ ] Serialization round-trip tests (object → JSON → validate)
- [ ] Edge cases (boundary tiles, blocked paths, invalid coordinates)
- [ ] Load testing (query all tiles in map)
- [ ] Manual testing walkthrough

### Phase 5: Documentation & Polish (Days 15-20)
- [ ] Update OpenAPI schema for world endpoints
- [ ] Swagger UI verification
- [ ] Error message clarity
- [ ] Performance optimization
- [ ] Final integration tests
- [ ] Documentation examples

## Technical Implementation Details

### 1. Universe Loading

**Current Implementation (Mock):**
```python
# src/api/app.py - Creates mock tiles for testing
test_tiles = {
    (0, 0): MockTile(...),
    (0, 1): MockTile(...),
    # ...
}
```

**Target Implementation (Real):**
```python
# src/api/app.py - Load from actual game files
from src.player import Player
from src.universe import Universe

# Create real player (or load from file)
player = Player()
player.name = "TestPlayer"
player.x = 0
player.y = 0

# Create real universe (loads all maps from JSON)
universe = Universe(player)  # Auto-loads from src/resources/maps/

# Verify tiles are accessible
tile = universe.get_tile(0, 0)  # Should return actual MapTile object
```

### 2. Serialization Strategy

**Item Hierarchy (from src/items.py):**
```python
# Need to serialize all these types
Item (base)
├── Weapon
├── Armor
├── Boots
├── Helm
├── Gloves
├── Accessory
├── Consumable
├── Special
├── Gold
```

**Serialization Pattern:**
```python
def serialize_item(item):
    """Convert item to JSON-safe dict."""
    return {
        "id": str(id(item)),  # Unique identifier
        "name": item.name,
        "type": type(item).__name__,  # "Weapon", "Armor", etc.
        "subtype": getattr(item, "subtype", None),  # "Sword", "Shield", etc.
        "description": item.description,
        "weight": getattr(item, "weight", 0),
        "quantity": getattr(item, "quantity", 1),
        "equipped": getattr(item, "equipped", False),
        # Modifiers for stat changes
        "modifiers": serialize_modifiers(item),
        # Combat properties
        "base_damage": getattr(item, "base_damage", 0),
        "base_damage_type": getattr(item, "base_damage_type", None),
        "armor_value": getattr(item, "armor_value", 0),
    }

def serialize_modifiers(item):
    """Convert stat modifiers to JSON."""
    if not hasattr(item, "stat_modifiers"):
        return {}
    return {
        "hp": item.stat_modifiers.get("hp", 0),
        "damage": item.stat_modifiers.get("damage", 0),
        "armor": item.stat_modifiers.get("armor", 0),
        # ... other stats
    }
```

### 3. Event System

**Event Serialization:**
```python
def serialize_event(event):
    """Convert event to JSON-safe dict."""
    return {
        "id": str(id(event)),
        "type": type(event).__name__,
        "module": type(event).__module__,
        "description": getattr(event, "description", ""),
        "repeatable": getattr(event, "repeat", False),
        # Event parameters if any
        "params": serialize_event_params(event),
    }

def serialize_event_params(event):
    """Serialize event-specific parameters."""
    if hasattr(event, "params") and event.params:
        return {k: str(v) for k, v in event.params.items()}
    return {}
```

### 4. Endpoint Response Format

**GET /world/**
```json
{
  "success": true,
  "room": {
    "x": 5,
    "y": 6,
    "name": "Forest Path",
    "description": "A winding path through...",
    "exits": {
      "north": {"x": 5, "y": 7},
      "south": {"x": 5, "y": 5},
      "east": {"x": 6, "y": 6}
    },
    "items": [
      {
        "id": "item_001",
        "name": "Gold Coin",
        "type": "Gold",
        "quantity": 5
      }
    ],
    "npcs": [
      {
        "id": "npc_001",
        "name": "Forest Guardian",
        "type": "NPC",
        "level": 12,
        "is_hostile": false
      }
    ],
    "objects": [
      {
        "id": "obj_001",
        "name": "Old Door",
        "type": "Door",
        "is_passable": false
      }
    ]
  }
}
```

**POST /world/move**
```json
{
  "success": true,
  "moved": true,
  "new_position": {"x": 5, "y": 7},
  "events_triggered": [
    {
      "type": "TileEntryEvent",
      "description": "The path ahead glows with magic..."
    }
  ],
  "room": { /* same as GET /world/ */ }
}
```

**GET /world/tile?x=5&y=6**
```json
{
  "success": true,
  "tile": { /* same tile structure as GET /world/ */ }
}
```

## Testing Strategy

### Unit Tests
```python
# test_world_serializers.py
- test_serialize_item_weapon()
- test_serialize_item_armor()
- test_serialize_npc_basic()
- test_serialize_event_basic()
- test_serialize_tile_full()

# test_world_endpoints.py
- test_get_current_room()
- test_move_valid_direction()
- test_move_invalid_direction()
- test_move_out_of_bounds()
- test_get_tile_valid()
- test_get_tile_invalid()
```

### Integration Tests
```python
# test_world_navigation_flow.py
- test_movement_sequence_5_tiles()
- test_event_trigger_on_movement()
- test_tile_state_consistency()
- test_multiple_players_isolation()
- test_map_boundary_conditions()
```

### Manual Test Cases
- [ ] Start at (0, 0), move north 3 times, verify position
- [ ] Query tile with items/NPCs/objects, verify serialization
- [ ] Trigger event on tile entry, verify event data
- [ ] Try moving into blocked/invalid location
- [ ] Check all exits from starting tile
- [ ] Load different maps, verify tile access

## Files to Create/Modify

### New Files
- `src/api/services/world_serializers.py` - Enhanced serialization (items, NPCs, events, etc.)
- `tests/api/test_world_serializers.py` - Serializer unit tests
- `tests/api/test_world_navigation_integration.py` - Full movement workflows
- `docs/WORLD_NAVIGATION_SPEC.md` - Detailed world navigation specification
- `M2_PROGRESS.md` - Milestone 2 progress tracking

### Modified Files
- `src/api/app.py` - Switch from mock to real universe loading
- `src/api/services/game_service.py` - Enhance world methods (move_player, trigger_tile_events)
- `src/api/routes/world.py` - Verify endpoints use real serializers
- `src/api/schemas/openapi.py` - Update world endpoint schemas

## Git Strategy

**Commits will follow this pattern:**
```
M2-1: Load real universe instead of mock tiles
M2-2: Implement item serialization for all subtypes
M2-3: Implement NPC serialization
M2-4: Implement object serialization
M2-5: Implement event serialization
M2-6: Add world endpoint tests
M2-7: Enhance GET /world/ endpoint with real data
M2-8: Enhance POST /world/move with event triggering
M2-9: Implement GET /world/tile endpoint
M2-10: Add integration tests for movement flows
M2-11: Performance optimization and polish
M2-12: Update OpenAPI schema and documentation
```

## Dependencies & Prerequisites

**Must Have (From Milestone 1):**
- ✅ Flask REST API working
- ✅ GameService initialized
- ✅ Session management
- ✅ 351 tests passing
- ✅ All endpoints verified

**Game Engine (Existing):**
- ✅ `src/universe.py` - Universe & map loading
- ✅ `src/player.py` - Player class
- ✅ `src/items.py` - Item hierarchy
- ✅ `src/npc.py` - NPC class
- ✅ `src/objects.py` - World objects
- ✅ `src/events.py` - Event system
- ✅ `src/resources/maps/*.json` - Map data

## Risk Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| Universe initialization fails | Low | High | Add universe loading unit tests early |
| Serialization misses edge cases | Medium | Medium | Test all item/NPC subtypes |
| Event system has unknown properties | Low | High | Document all event attributes |
| Performance degrades with large maps | Low | Medium | Profile & optimize hotspots |
| Map JSON corruption during testing | Low | Medium | Use backup copies, validate JSON schema |

## Success Metrics

**Code Quality:**
- ✅ >85% test coverage on API layer
- ✅ All serialization tests passing
- ✅ Integration tests cover 5+ movement sequences
- ✅ <200ms p95 response time

**Functionality:**
- ✅ Move through 10+ tiles without errors
- ✅ All tile data properly serialized
- ✅ Events trigger and display correctly
- ✅ Boundary conditions handled gracefully

**Documentation:**
- ✅ OpenAPI schema updated
- ✅ Example requests/responses documented
- ✅ Error codes documented
- ✅ Swagger UI displays all endpoints

## Timeline Estimate

| Phase | Duration | Status |
|-------|----------|--------|
| Universe Loading | Days 1-3 | Not started |
| Serializers | Days 4-7 | Not started |
| Endpoints | Days 8-11 | Not started |
| Testing | Days 12-14 | Not started |
| Polish | Days 15-20 | Not started |
| **Total** | **20 days** | **Estimated** |

---

**Created:** November 8, 2025  
**Branch:** phase-2/world-navigation  
**Next Steps:** Begin with universe loading verification

