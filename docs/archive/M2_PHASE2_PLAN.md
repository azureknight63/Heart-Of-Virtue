# Milestone 2 Phase 2 - Serializers Enhancement Plan

## Overview
Implement complete serialization for game world objects to enable full tile responses with items, NPCs, objects, and events. This phase addresses the 9 failing event integration tests and enables rich API responses.

## Phase Goals
1. ✅ Complete item serialization
2. ✅ Complete NPC serialization  
3. ✅ Complete object serialization
4. ✅ Complete event serialization
5. ✅ Pass all 351+ tests
6. ✅ Update OpenAPI schema with full tile responses

## Serializers to Implement

### 1. Item Serialization (src/api/serializers/item_serializer.py)
**Goal**: Convert Item objects to JSON-safe dictionaries

Items to serialize:
- Base properties: name, type, description, value, weight
- Equipment state: equipped status, stat bonuses, resistances
- Consumables: effect description, power level, quantity
- Special: hidden status, merchandise flag

Serialize methods:
- `serialize_item(item)` - Basic properties
- `serialize_item_with_effects(item)` - Full detailed info
- `serialize_inventory(items)` - List of items

### 2. NPC Serialization (src/api/serializers/npc_serializer.py)
**Goal**: Convert NPC/Enemy objects to JSON

NPC data:
- Identity: name, type, level, description
- Combat stats: HP, damage, resistances
- AI state: behavior, hostility, dialogue
- Inventory: items they carry (for shops/bosses)

Methods:
- `serialize_npc(npc)` - Combat-relevant stats
- `serialize_npc_full(npc)` - With inventory/dialogue
- `serialize_merchant_npc(npc)` - Shop inventory

### 3. Object Serialization (src/api/serializers/object_serializer.py)
**Goal**: Convert world objects (chests, doors, shrines) to JSON

Object properties:
- Identity: name, type, description
- State: locked/unlocked, open/closed, passability
- Contents: items in containers
- Interactions: keywords, events triggered

Methods:
- `serialize_object(obj)` - Static properties
- `serialize_object_with_contents(obj)` - Including container items
- `serialize_interactive_object(obj)` - With interaction options

### 4. Event Serialization (src/api/serializers/event_serializer.py)
**Goal**: Convert game events to JSON for tile responses

Event data:
- Type: quest event, combat event, story event
- Description: user-facing text
- Conditions: when event triggers
- Consequences: what happens when processed
- State: processed, active, complete

Methods:
- `serialize_event(event)` - Basic event data
- `serialize_event_consequence(event)` - Outcome when processed
- `serialize_event_list(events)` - Multiple events

### 5. Tile Serializer Enhancement (src/api/serializers/tile_serializer.py)
**Goal**: Enhance GameService.get_tile() with full serialization

Complete tile response:
```json
{
  "x": 1,
  "y": 1,
  "name": "Damp Cavern",
  "description": "...",
  "exits": {"north": {x, y}, "south": {x, y}},
  "items": [{name, type, value}],
  "npcs": [{name, level, hostile}],
  "objects": [{name, type, passable}],
  "events": [{type, description}]
}
```

## Implementation Strategy

### Phase 2a: Core Serializers (Days 1-2)
1. Create serializers directory structure
2. Implement ItemSerializer with basic properties
3. Implement NPCSerializer with combat stats
4. Implement ObjectSerializer
5. Create unit tests for each serializer

### Phase 2b: Event Serialization & Testing (Days 3-4)
1. Implement EventSerializer
2. Fix failing event integration tests
3. Update GameService.get_tile() to use all serializers
4. Update GameService.move_player() to include events

### Phase 2c: API Integration & Documentation (Days 5)
1. Update OpenAPI schema with full tile definitions
2. Create integration tests for serialized responses
3. Verify 351+ tests passing
4. Clean up test utilities

## Test Coverage

**Target**: 351+ tests passing (100%)

**Current Status**: 342/351 passing (97.4%)
- 9 event integration tests failing
- All other tests passing

**Work Required**:
- Fix 9 event integration tests via EventSerializer
- Add 10+ serializer unit tests
- Add 10+ integration tests for full tile responses

## Files to Create/Modify

### New Files
- `src/api/serializers/__init__.py` - Serializer exports
- `src/api/serializers/item_serializer.py` - Item serialization
- `src/api/serializers/npc_serializer.py` - NPC serialization
- `src/api/serializers/object_serializer.py` - Object serialization
- `src/api/serializers/event_serializer.py` - Event serialization
- `src/api/serializers/tile_serializer.py` - Enhanced tile serialization
- `tests/api/test_item_serializer.py` - Item tests
- `tests/api/test_npc_serializer.py` - NPC tests
- `tests/api/test_object_serializer.py` - Object tests
- `tests/api/test_event_serializer.py` - Event tests

### Modified Files
- `src/api/services/game_service.py` - Use serializers in get_tile() and move_player()
- `src/api/schemas/openapi.py` - Add full Tile schema definition
- `tests/api/test_events_integration.py` - Should pass after EventSerializer

## Architecture Notes

**Serializer Pattern**:
```python
class ItemSerializer:
    @staticmethod
    def serialize(item):
        """Convert Item to JSON-safe dict"""
        return {
            "name": item.name,
            "type": type(item).__name__,
            "description": item.description,
            # ... other properties
        }
    
    @staticmethod
    def serialize_list(items):
        """Serialize multiple items"""
        return [ItemSerializer.serialize(item) for item in items]
```

**GameService Integration**:
```python
def get_tile(self, x: int, y: int) -> Dict[str, Any]:
    tile = self.universe.get_tile(x, y)
    
    # Use serializers
    items = ItemSerializer.serialize_list(tile.items_here)
    npcs = NPCSerializer.serialize_list(tile.npcs_here)
    objects = ObjectSerializer.serialize_list(tile.objects_here)
    events = EventSerializer.serialize_list(tile.events_here)
    
    return {
        "x": x, "y": y,
        "items": items,
        "npcs": npcs,
        "objects": objects,
        "events": events,
        # ... other properties
    }
```

## Success Criteria

1. ✅ All serializers implemented and tested
2. ✅ 351+ tests passing
3. ✅ Full tile responses include items, NPCs, objects, events
4. ✅ Event integration tests passing
5. ✅ OpenAPI schema documents complete Tile response
6. ✅ No regression in existing endpoints

## Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Circular references in object graphs | Serialization infinite loop | Use ID-based references, avoid full serialization of nested objects |
| Missing attribute errors | 500 errors on serialization | Use getattr() with defaults everywhere |
| Event processing side effects | Unexpected game state changes | Mark events as processed after serialization, don't trigger automatically |
| Performance on complex tiles | Slow API responses | Cache serialized data, consider pagination for large inventories |

## Timeline

| Phase | Days | Tasks |
|-------|------|-------|
| 2a | 1-2 | Create 4 core serializers + unit tests |
| 2b | 3-4 | Event serializer + integration tests |
| 2c | 5 | API integration + documentation |

**Estimated Completion**: ~5 working days from phase start

