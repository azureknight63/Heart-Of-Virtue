# HV-39: Milestone 3 - Inventory & Equipment System

**Status**: In Progress  
**Branch**: `api/hv-39-inventory-equipment`  
**Target**: Weeks 5-6 (Dec 9-22)  
**Effort**: 45-55 hours, 18-22 commits  
**Estimated Tests**: 80+ new tests, >85% coverage target

---

## Overview

HV-39 expands the Flask REST API with complete inventory and equipment management. Building on the HV-38 foundation (world navigation, 138 tests), HV-39 adds player inventory access, item management, equipment system, and dynamic stat calculation.

**Previous Milestone Recap (HV-38)**:
- ✅ 3 world navigation endpoints
- ✅ 6 serializer classes
- ✅ GameService with 18 methods
- ✅ 138 tests passing (>85% coverage)
- ✅ 9/9 UAT tests passing
- ✅ Merged to phase-1/backend-api

---

## Architecture Foundation

### Extending HV-38

**Existing Components to Leverage**:
1. **GameService** (18 methods)
   - `move_player()`, `get_tile()`, `trigger_tile_events()`, etc.
   - Will add: `get_inventory()`, `drop_item()`, `take_item()`, `equip_item()`, etc.

2. **Serializers Pattern** (6 classes in `src/api/serializers/world.py`)
   - ItemSerializer (items with quantity, rarity, weight, value)
   - Will extend: InventorySerializer, EquipmentSerializer

3. **Routes Pattern** (6 blueprints in `src/api/routes/`)
   - Bearer token auth on all endpoints
   - Session extraction helper
   - Input validation with reusable validators
   - JSON error responses

4. **Test Structure** (138 tests in `tests/api/`)
   - conftest.py with test fixtures
   - Minimal player with session
   - Test universe initialization

### New Components (HV-39)

**New Serializers** (`src/api/serializers/inventory.py`):
```python
class InventorySerializer:
    """Serialize player inventory"""
    - List all items with quantities
    - Filter by type (weapons, armor, consumables)
    - Include weight/value info

class EquipmentSerializer:
    """Serialize player equipment"""
    - Current equipped items
    - Stat bonuses from equipment
    - Equipped state (equipped vs in inventory)

class ItemDetailSerializer:
    """Deep item serialization"""
    - Full item attributes
    - Rarity level effects
    - Resistance modifiers
    - Merchandise flag
```

**New Routes** (`src/api/routes/inventory.py`):
```python
# Inventory Management
GET /inventory/              # List all inventory items
POST /inventory/take        # Take item from tile
POST /inventory/drop        # Drop item on ground
GET /inventory/examine      # Inspect specific item

# Equipment Management
GET /inventory/equipment    # List equipped items
POST /inventory/equip       # Equip an item
POST /inventory/unequip     # Unequip an item
GET /inventory/compare      # Compare items

# Stats & Currency
GET /inventory/stats        # Get current player stats
GET /inventory/currency     # Get gold/currency info
POST /inventory/currency/use # Spend currency
```

**GameService Enhancements**:
```python
def get_inventory(player: Player) -> List[Dict]
    """Get player inventory as JSON"""
    
def get_equipment(player: Player) -> Dict
    """Get current equipment state"""
    
def drop_item(player: Player, item_idx: int, tile) -> bool
    """Drop item from inventory to tile"""
    
def take_item(player: Player, item_idx: int, tile) -> bool
    """Take item from tile into inventory"""
    
def equip_item(player: Player, item_idx: int) -> Dict
    """Equip item, recalculate stats"""
    
def unequip_item(player: Player, slot: str) -> Dict
    """Unequip item from slot"""
    
def get_player_stats(player: Player) -> Dict
    """Get all character stats with equipment bonuses"""
    
def compare_items(item1: Item, item2: Item) -> Dict
    """Compare two items for swapping"""
```

---

## Detailed Deliverables

### 1. Inventory Serializers (150 lines)

**File**: `src/api/serializers/inventory.py`

```python
class InventoryItemSchema:
    """Single inventory item with quantity"""
    index: int
    name: str
    type: str  # weapon, armor, consumable, etc.
    quantity: int
    rarity: str
    weight: float
    value: int
    can_equip: bool
    is_equipped: bool

class InventorySchema:
    """Player inventory summary"""
    total_weight: float
    weight_limit: float
    item_count: int
    items: List[InventoryItemSchema]

class EquipmentSlotSchema:
    """Single equipment slot"""
    slot: str  # head, chest, legs, hands, feet, back, ring1, ring2
    item_name: str
    stat_bonuses: Dict[str, float]
    resistance_bonuses: Dict[str, float]

class EquipmentSchema:
    """All equipped items"""
    equipped: Dict[str, EquipmentSlotSchema]
    unequipped_count: int
    total_equipped_bonuses: Dict[str, float]

class ItemComparisonSchema:
    """Compare two items"""
    item1: Dict  # equipped item
    item2: Dict  # candidate item
    damage_diff: float
    defense_diff: float
    weight_diff: float
    value_diff: int
    recommendation: str  # "upgrade", "downgrade", "sidegrade"
```

**Tests** (`tests/api/test_inventory_serializers.py` - 25 tests):
- Serialize weapon with stat bonuses
- Serialize armor with resistance modifiers
- Serialize inventory with multiple items
- Handle empty slots
- Calculate weight limits
- Compare items (upgrades/downgrades)
- Handle merchandise flags

---

### 2. Inventory Routes (200 lines)

**File**: `src/api/routes/inventory.py`

```python
@inventory_bp.route('/inventory/', methods=['GET'])
def get_inventory():
    """Get player inventory"""
    # Get session and player
    # Get inventory from GameService
    # Serialize with InventorySerializer
    # Return JSON

@inventory_bp.route('/inventory/examine', methods=['GET'])
def examine_item():
    """Examine specific item"""
    # Get session and player
    # Validate item_idx parameter
    # Get item details
    # Return full item schema

@inventory_bp.route('/inventory/drop', methods=['POST'])
def drop_item():
    """Drop item from inventory"""
    # Get session and player
    # Validate item_idx from JSON
    # Get current tile
    # Drop item on tile
    # Save session
    # Return success with new inventory

@inventory_bp.route('/inventory/take', methods=['POST'])
def take_item():
    """Take item from tile"""
    # Get session and player
    # Get current tile
    # Validate item_idx from JSON
    # Check weight limit
    # Take item into inventory
    # Save session
    # Return success with new inventory

@inventory_bp.route('/inventory/equipment', methods=['GET'])
def get_equipment():
    """Get current equipment"""
    # Get session and player
    # Get equipment from GameService
    # Serialize with EquipmentSerializer
    # Return JSON with stat bonuses

@inventory_bp.route('/inventory/equip', methods=['POST'])
def equip_item():
    """Equip an item"""
    # Get session and player
    # Validate item_idx from JSON
    # Call GameService.equip_item()
    # Recalculate player stats
    # Save session
    # Return success with new equipment

@inventory_bp.route('/inventory/unequip', methods=['POST'])
def unequip_item():
    """Unequip an item"""
    # Get session and player
    # Validate slot from JSON
    # Call GameService.unequip_item()
    # Recalculate player stats
    # Save session
    # Return success with new equipment

@inventory_bp.route('/inventory/compare', methods=['GET'])
def compare_items():
    """Compare two items"""
    # Get session and player
    # Get item1_idx and item2_idx from query params
    # Compare items
    # Return comparison schema

@inventory_bp.route('/inventory/stats', methods=['GET'])
def get_stats():
    """Get player stats"""
    # Get session and player
    # Get all stats with equipment bonuses
    # Return stats schema

@inventory_bp.route('/inventory/currency', methods=['GET'])
def get_currency():
    """Get currency info"""
    # Get session and player
    # Return gold/currency amounts

@inventory_bp.route('/inventory/currency/use', methods=['POST'])
def use_currency():
    """Spend currency"""
    # Get session and player
    # Validate amount from JSON
    # Spend currency
    # Save session
    # Return success with new balance
```

**Validators** (in `src/api/services/validators.py`):
- `validate_item_index(index: int, max_items: int) -> (bool, str)`
- `validate_weight_limit(current_weight: float, item_weight: float, limit: float) -> (bool, str)`
- `validate_equipment_slot(slot: str) -> (bool, str)`
- `validate_currency_amount(amount: int, available: int) -> (bool, str)`

**Error Handling**:
- 400: Invalid item index
- 400: Weight limit exceeded
- 400: Item not equippable
- 404: Item not found
- 422: Invalid equipment slot

---

### 3. GameService Enhancements (250 lines)

**File**: `src/api/services/game_service.py`

```python
def get_inventory(self, player: Player) -> Dict:
    """Get full inventory as JSON-serializable dict"""
    items = []
    for idx, item in enumerate(player.inventory_list):
        items.append({
            'index': idx,
            'name': item.name,
            'type': item.__class__.__name__,
            'quantity': item.quantity if hasattr(item, 'quantity') else 1,
            'rarity': getattr(item, 'rarity', 'common'),
            'weight': getattr(item, 'weight', 0.0),
            'value': getattr(item, 'value', 0),
            'can_equip': hasattr(item, 'equip'),
            'is_equipped': getattr(item, 'equipped_state', False),
        })
    return {
        'total_weight': sum(getattr(item, 'weight', 0) for item in player.inventory_list),
        'weight_limit': player.carrying_capacity,
        'item_count': len(player.inventory_list),
        'items': items,
    }

def get_equipment(self, player: Player) -> Dict:
    """Get current equipment with stat bonuses"""
    equipment = {}
    for slot, item in player.equipped.items():
        if item:
            equipment[slot] = {
                'item_name': item.name,
                'armor_value': getattr(item, 'armor', 0),
                'stat_bonuses': getattr(item, 'stat_bonuses', {}),
                'resistance_bonuses': getattr(item, 'resistance_bonuses', {}),
            }
    return {
        'equipped': equipment,
        'unequipped_count': len([i for i in player.inventory_list if not getattr(i, 'equipped_state', False)]),
        'total_bonuses': self._calculate_equipment_bonuses(player),
    }

def drop_item(self, player: Player, item_idx: int, tile) -> bool:
    """Drop item from inventory to tile"""
    if item_idx < 0 or item_idx >= len(player.inventory_list):
        raise ValueError(f"Invalid item index: {item_idx}")
    
    item = player.inventory_list[item_idx]
    tile.items_here.append(item)
    player.inventory_list.pop(item_idx)
    return True

def take_item(self, player: Player, item_idx: int, tile) -> bool:
    """Take item from tile into inventory"""
    if item_idx < 0 or item_idx >= len(tile.items_here):
        raise ValueError(f"Invalid item index: {item_idx}")
    
    item = tile.items_here[item_idx]
    weight = getattr(item, 'weight', 0)
    if self._get_inventory_weight(player) + weight > player.carrying_capacity:
        raise ValueError("Weight limit exceeded")
    
    player.inventory_list.append(item)
    tile.items_here.pop(item_idx)
    return True

def equip_item(self, player: Player, item_idx: int) -> Dict:
    """Equip item from inventory"""
    if item_idx < 0 or item_idx >= len(player.inventory_list):
        raise ValueError(f"Invalid item index: {item_idx}")
    
    item = player.inventory_list[item_idx]
    if not hasattr(item, 'equip'):
        raise ValueError(f"Item {item.name} cannot be equipped")
    
    item.equip(player)  # Call item's equip method
    functions.refresh_stat_bonuses(player)
    return self.get_equipment(player)

def unequip_item(self, player: Player, slot: str) -> Dict:
    """Unequip item from slot"""
    if slot not in player.equipped:
        raise ValueError(f"Invalid equipment slot: {slot}")
    
    item = player.equipped[slot]
    if item:
        item.unequip(player)
        functions.refresh_stat_bonuses(player)
    return self.get_equipment(player)

def get_player_stats(self, player: Player) -> Dict:
    """Get all stats with equipment bonuses"""
    return {
        'health': player.health,
        'max_health': player.max_health,
        'stamina': player.stamina,
        'max_stamina': player.max_stamina,
        'attack': player.attack,
        'defense': player.defense,
        'magic_attack': player.magic_attack,
        'magic_defense': player.magic_defense,
        'speed': player.speed,
        'accuracy': player.accuracy,
        'evasion': player.evasion,
        'crit_chance': player.crit_chance,
        'equipment_bonuses': self._calculate_equipment_bonuses(player),
        'resistance_profiles': player.resistance_profiles,
    }

def compare_items(self, item1: Item, item2: Item) -> Dict:
    """Compare two items"""
    return {
        'item1': {
            'name': item1.name,
            'type': item1.__class__.__name__,
            'damage': getattr(item1, 'damage', 0),
            'armor': getattr(item1, 'armor', 0),
            'weight': getattr(item1, 'weight', 0),
            'value': getattr(item1, 'value', 0),
        },
        'item2': {
            'name': item2.name,
            'type': item2.__class__.__name__,
            'damage': getattr(item2, 'damage', 0),
            'armor': getattr(item2, 'armor', 0),
            'weight': getattr(item2, 'weight', 0),
            'value': getattr(item2, 'value', 0),
        },
        'comparison': {
            'damage_diff': getattr(item2, 'damage', 0) - getattr(item1, 'damage', 0),
            'armor_diff': getattr(item2, 'armor', 0) - getattr(item1, 'armor', 0),
            'weight_diff': getattr(item2, 'weight', 0) - getattr(item1, 'weight', 0),
            'value_diff': getattr(item2, 'value', 0) - getattr(item1, 'value', 0),
        },
    }

def _calculate_equipment_bonuses(self, player: Player) -> Dict:
    """Calculate total bonuses from equipped items"""
    bonuses = {
        'attack': 0, 'defense': 0, 'magic_attack': 0, 'magic_defense': 0,
        'speed': 0, 'accuracy': 0, 'evasion': 0, 'crit_chance': 0,
    }
    for slot, item in player.equipped.items():
        if item and hasattr(item, 'stat_bonuses'):
            for stat, bonus in item.stat_bonuses.items():
                if stat in bonuses:
                    bonuses[stat] += bonus
    return bonuses

def _get_inventory_weight(self, player: Player) -> float:
    """Calculate current inventory weight"""
    return sum(getattr(item, 'weight', 0) for item in player.inventory_list)
```

---

### 4. Integration Tests (300+ lines)

**File**: `tests/api/test_inventory_integration.py`

```python
# Test suite covering:
# - 8 inventory route tests
# - 6 equipment route tests
# - 5 currency/stats tests
# - 15+ edge case tests
# Total: 35+ comprehensive tests

test_get_inventory_success()
    # Player has items in inventory
    # Response includes all items with correct data
    
test_get_inventory_empty()
    # Player has no items
    # Response returns empty list
    
test_drop_item_success()
    # Player drops item from inventory
    # Item appears on current tile
    # Inventory updated
    
test_drop_item_weight_recalculated()
    # After drop, inventory weight reduced
    
test_drop_item_invalid_index()
    # Return 400 with error message
    
test_take_item_success()
    # Player takes item from tile
    # Item appears in inventory
    # Tile updated
    
test_take_item_weight_limit()
    # Taking item would exceed weight limit
    # Return 400 "Weight limit exceeded"
    
test_equip_item_success()
    # Player equips weapon/armor
    # Item marked as equipped
    # Stats recalculated
    
test_equip_item_wrong_slot()
    # Attempting to equip incompatible item
    # Return 400 with error
    
test_unequip_item_success()
    # Player unequips item
    # Item returns to inventory
    # Stats recalculated
    
test_get_equipment()
    # Response includes all equipped items
    # Total bonuses calculated
    
test_compare_items()
    # Compare two items
    # Response shows damage/armor/weight diffs
    
test_get_stats()
    # Response includes all character stats
    # Bonuses from equipment included
    
test_get_currency()
    # Response includes gold amount
    
test_use_currency_success()
    # Spend gold
    # Balance updated
    
test_use_currency_insufficient_funds()
    # Not enough gold
    # Return 400
    
# ... additional edge cases
```

---

### 5. GameService Tests (30+ tests)

**File**: `tests/api/test_game_service_inventory.py`

- Test each GameService method
- Test stat calculation
- Test weight limits
- Test merchandise flags
- Test item serialization

---

## Development Workflow

### Phase 1: Serializers (Days 1-2)
1. Create `src/api/serializers/inventory.py`
2. Write InventorySerializer, EquipmentSerializer, ItemDetailSerializer
3. Write 25+ serializer tests
4. All tests passing ✅

### Phase 2: Routes (Days 3-4)
1. Create `src/api/routes/inventory.py`
2. Implement all 10 endpoints
3. Add validators to `src/api/services/validators.py`
4. Write 35+ integration tests
5. All tests passing ✅

### Phase 3: GameService (Days 5-6)
1. Enhance `src/api/services/game_service.py`
2. Add inventory operations methods
3. Add stat calculation methods
4. Write 30+ unit tests
5. All tests passing ✅

### Phase 4: Integration & UAT (Days 7)
1. Run full test suite (100+ tests)
2. Create `uat_hv39.py` script
3. Run UAT against running server
4. Fix any issues found
5. All 9+ UAT tests passing ✅

### Phase 5: Documentation & Merge (Day 7-8)
1. Create completion summary document
2. Create PR to phase-1/backend-api
3. Squash merge
4. Tag release as v1.2.0-alpha

---

## Success Criteria

| Criterion | Target | Notes |
|-----------|--------|-------|
| Inventory endpoints | 4 endpoints | GET /inventory/, POST /drop, POST /take, GET /examine |
| Equipment endpoints | 4 endpoints | GET /equipment, POST /equip, POST /unequip, GET /compare |
| Stats endpoints | 2 endpoints | GET /stats, GET /currency |
| Serializers | 3 classes | InventorySerializer, EquipmentSerializer, ItemDetailSerializer |
| GameService methods | 8 new methods | get_inventory, drop_item, take_item, equip_item, etc. |
| Tests | 100+ tests | All inventory/equipment operations tested |
| Test coverage | >85% | All code paths covered |
| Routes authenticated | 10/10 endpoints | Bearer token required on all |
| UAT tests | 9+ tests passing | Comprehensive end-to-end testing |
| Documentation | Complete | Guides, API docs, test results |

---

## Known Dependencies

1. **HV-38 Completion** ✅ (world navigation, 138 tests)
2. **GameService pattern** ✅ (18 existing methods)
3. **Serializer pattern** ✅ (6 existing serializers)
4. **Player class** ✅ (inventory_list, equipped, carrying_capacity)
5. **functions.refresh_stat_bonuses()** ✅ (stat recalculation)
6. **Item classes** ✅ (Weapon, Armor, etc. with equip/unequip)

---

## Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Weight limit edge cases | Medium | Comprehensive unit tests for weight calculations |
| Stat calculation errors | High | Test stat updates after each equip/unequip |
| Merchandise flag conflicts | Medium | Clear validation logic in routes |
| Circular equipment dependencies | Low | Player class handles equipment slots properly |

---

## Timeline & Commits

**Total Commits**: 18-22  
**Total Effort**: 45-55 hours  

**Commit breakdown**:
1. Add HV-39 planning document
2. Create inventory serializers with tests
3. Add equipment serializers with tests
4. Create inventory route handler with validators
5. Add inventory integration tests (GET /inventory/)
6. Add item drop/take tests and functionality
7. Create equipment route handler
8. Add equip/unequip tests and functionality
9. Add comparison and stats endpoints
10. Enhance GameService with inventory operations
11. Add GameService inventory unit tests
12. Add comprehensive edge case tests
13. Create UAT script (uat_hv39.py)
14. Fix any UAT issues
15. Add completion summary document
16. Create PR #25 to phase-1/backend-api
17. Squash merge to phase-1/backend-api
18. Tag v1.2.0-alpha release

---

## Next Milestone (HV-40)

After HV-39 completion, next phase will be:

**HV-40: Milestone 4 - Combat System Integration**
- Combat endpoints (start battle, take action, check status)
- Spell/ability serializers
- Move system integration
- Turn-based battle management
- Loot & experience endpoints

---

## References

- **HV-36**: Backend API architecture & planning
- **HV-37**: Flask foundation & session management (DONE)
- **HV-38**: World navigation & tile system (DONE, merged)
- **HV-39**: This milestone (IN PROGRESS)
- **Player class**: `src/player.py` (1600+ lines)
- **Item hierarchy**: `src/items.py` (Weapon, Armor, Boots, etc.)
- **Functions**: `src/functions.py` (stat bonuses, serialization)

---

**Branch**: `api/hv-39-inventory-equipment`  
**Status**: In Progress  
**Started**: 2025-11-05  
**Estimated Completion**: 2025-11-12
