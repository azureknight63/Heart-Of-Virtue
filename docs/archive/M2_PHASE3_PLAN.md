# Milestone 2 Phase 3 - Inventory & Equipment Serialization Plan

## Overview
Implement complete serialization for player inventory and equipment systems to enable full inventory management via the REST API. This phase builds on the serializers foundation and enables inventory endpoints to work properly.

## Phase Goals
1. ✅ Create InventorySerializer for full inventory serialization
2. ✅ Create EquipmentSerializer for equipment state serialization  
3. ✅ Create ItemComparisonSerializer for equip/unequip decisions
4. ✅ Integrate serializers into GameService inventory methods
5. ✅ Fix inventory/equipment routes to use serializers
6. ✅ Pass all inventory-related tests
7. ✅ Update OpenAPI schema with full inventory responses

## Serializers to Implement

### 1. InventorySerializer (src/api/serializers/inventory.py)
**Goal**: Convert player inventory to JSON

Inventory structure:
- Items list with quantity tracking
- Weight calculations
- Stacking logic (consumables stack, equipment doesn't)
- Categorized by type (Weapons, Armor, Consumables, etc.)

Methods:
- `serialize_inventory(player)` - Full inventory with items
- `serialize_inventory_summary(player)` - Quick summary (count, weight, capacity)
- `serialize_inventory_by_category(player)` - Items organized by type
- `serialize_inventory_item(item, quantity)` - Single item with quantity

### 2. EquipmentSerializer (src/api/serializers/inventory.py)
**Goal**: Convert equipment state to JSON

Equipment data:
- Current equipment in each slot (head, body, legs, feet, hands, accessory x2, weapon, shield)
- Equipment stats (bonuses, resistances)
- Equipped status per item
- Stat totals from equipment

Methods:
- `serialize_equipment_state(player)` - All equipped items with stats
- `serialize_equipment_slot(player, slot_name)` - Single slot details
- `serialize_equipment_comparison(item1, item2)` - For unequip/equip decisions

### 3. ItemComparisonSerializer (src/api/serializers/inventory.py)
**Goal**: Help with equip/unequip decisions

Comparison data:
- Current item stats
- New item stats
- Stat deltas (what changes if equipped)
- Warnings (lower stats, breaking effect, etc.)

Methods:
- `compare_equipment(current_item, new_item)` - Side-by-side comparison
- `calculate_stat_delta(item1, item2)` - What changes

## GameService Methods to Implement

Update `src/api/services/game_service.py`:

1. `get_inventory(player)` - Returns full inventory with items
2. `get_inventory_summary(player)` - Quick summary for status display
3. `get_equipped_items(player)` - Current equipment state
4. `equip_item(player, item_index)` - Equip an item from inventory
5. `unequip_item(player, slot_name)` - Unequip from slot
6. `drop_item(player, item_index)` - Drop item from inventory
7. `examine_item(player, item_index)` - Get details on item
8. `compare_items(player, item_index)` - Compare with equipped item

## Routes Already Defined (need implementation)

Inventory routes (src/api/routes/inventory.py):
- `GET /inventory/` - Get full inventory
- `GET /inventory/summary` - Quick summary
- `GET /inventory/<int:item_id>/` - Examine item
- `POST /inventory/drop` - Drop item
- `POST /inventory/examine` - Get item details
- `POST /inventory/compare` - Compare items

Equipment routes (src/api/routes/equipment.py):
- `GET /equipment/` - Get equipped items
- `GET /equipment/<slot>` - Get item in slot
- `POST /equipment/equip` - Equip item from inventory
- `POST /equipment/unequip` - Unequip from slot
- `POST /equipment/compare` - Compare for equipping

## Implementation Strategy

### Phase 3a: Core Serializers (Day 1)
1. Create InventorySerializer with basic item list
2. Create EquipmentSerializer with equipped items
3. Create ItemComparisonSerializer for decisions
4. Unit tests for each serializer

### Phase 3b: GameService Integration (Day 2)
1. Implement get_inventory() method
2. Implement get_equipped_items() method
3. Implement equip_item() and unequip_item()
4. Integration tests for game service

### Phase 3c: Route Integration & Testing (Day 3)
1. Wire serializers into inventory routes
2. Wire serializers into equipment routes
3. Fix failing inventory/equipment tests
4. Verify all tests passing

## Test Coverage

**Target**: All inventory/equipment tests passing

**Current Status**: Routes defined but serializers missing
- Inventory routes exist but return empty/stub responses
- Equipment routes exist but not integrated
- Tests likely failing due to missing serializers

**Work Required**:
- Implement 3 serializer classes
- Integrate into GameService
- Wire into routes
- Update tests to use real serializers

## Files to Create/Modify

### New Files
- `src/api/serializers/inventory.py` - All 3 serializers
- `tests/api/test_inventory_serializer.py` - Inventory tests
- `tests/api/test_equipment_serializer.py` - Equipment tests

### Modified Files
- `src/api/services/game_service.py` - Add inventory/equipment methods
- `src/api/routes/inventory.py` - Use InventorySerializer
- `src/api/routes/equipment.py` - Use EquipmentSerializer
- `src/api/schemas/openapi.py` - Add inventory/equipment schemas

## Architecture Notes

**Inventory Structure**:
```python
class InventorySerializer:
    @staticmethod
    def serialize_inventory(player):
        """Full inventory with items and weights"""
        return {
            "items": [
                {
                    "id": str(i),
                    "name": item.name,
                    "type": type(item).__name__,
                    "quantity": getattr(item, "quantity", 1),
                    "weight": getattr(item, "weight", 0),
                    "value": getattr(item, "value", 0),
                    ...
                }
                for i, item in enumerate(player.inventory)
            ],
            "weight": total_weight,
            "capacity": player.inventory_capacity,
            "count": len(player.inventory),
        }
```

**Equipment Structure**:
```python
class EquipmentSerializer:
    @staticmethod
    def serialize_equipment_state(player):
        """Current equipment with stats"""
        return {
            "slots": {
                "head": serialize_slot(player.head),
                "body": serialize_slot(player.body),
                "legs": serialize_slot(player.legs),
                # ... other slots
            },
            "stats": {
                "health": player.max_health,
                "damage": player.damage,
                "resistances": player.resistances,
                # ... other stats
            }
        }
```

## Success Criteria

1. ✅ All serializers implemented and tested
2. ✅ GameService has full inventory/equipment methods
3. ✅ Inventory routes working with serializers
4. ✅ Equipment routes working with serializers
5. ✅ All inventory/equipment tests passing
6. ✅ No regression in existing tests
7. ✅ OpenAPI schema updated with inventory/equipment definitions

## Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Missing attributes on items | 500 errors on serialization | Use getattr() with defaults everywhere |
| Circular references in inventory | Infinite recursion | Serialize to basic types only (no objects) |
| Weight calculation edge cases | Incorrect capacity display | Test all item types and stacking scenarios |
| Equipment slot mismatches | Wrong item in wrong slot | Validate slot names against player attributes |
| Performance on large inventories | Slow API responses | Consider pagination for 50+ items |

## Timeline

| Phase | Days | Tasks |
|-------|------|-------|
| 3a | 1 | Create 3 serializers + unit tests |
| 3b | 1 | GameService methods + integration tests |
| 3c | 1 | Route integration + final testing |

**Estimated Completion**: ~3 working days from phase start

## Next Phase (M2 Phase 4)

After inventory/equipment serialization:
- Combat state serialization
- Combat moves serialization
- Skill tree serialization
- NPC state serialization

