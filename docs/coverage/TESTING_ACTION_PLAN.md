# Testing Action Plan: Quick Wins & Implementation Strategy

**Updated:** 2026-05-15  
**Current Coverage:** 51%  
**Next Target:** 60% (gap: 9 percentage points)  
**Estimated Effort to Target:** 12-15 hours

---

## Priority 1: GameService Core Methods (HIGHEST ROI)

### What's Missing

The `GameService` class is **1,815 lines** with only **56% coverage**. Most untested lines are in the core execution pipeline:

```python
# Lines 807-1023: execute_move() implementation [217 lines, ~0% covered]
# Lines 1100-1111: cooldown drain logic [11 lines, ~0% covered]
# Lines 1123-1166: status effect application [43 lines, ~0% covered]
# Lines 1292-1568: complex game events [276 lines, ~0% covered]
```

These methods are called on **every turn** and control:
- Move validation & execution
- Damage calculation
- Cooldown recovery
- Status effect application
- NPC reinforcement spawning

### Implementation Plan

#### Test 1: Basic Move Execution (45 min)

**File:** `tests/api/services/test_game_service_moves.py`

```python
def test_execute_move_basic():
    """Test executing a basic attack move."""
    player = create_test_player(hp=100)
    enemy = create_test_npc(hp=50)
    game_service = GameService()
    
    # Execute PowerStrike attack
    move = moves.PowerStrike()
    result = game_service.execute_move(player, move, target=enemy)
    
    assert result['success'] == True
    assert enemy.hp < 50  # Damage was applied
    assert 'damage' in result
    assert result['damage'] > 0

def test_execute_move_out_of_range():
    """Test move rejection when target is out of range."""
    player = create_test_player(x=0, y=0)
    enemy = create_test_npc(x=10, y=10)
    game_service = GameService()
    
    move = moves.PowerStrike()  # Melee, short range
    result = game_service.execute_move(player, move, target=enemy)
    
    assert result['success'] == False
    assert 'out of range' in result.get('error', '').lower()

def test_execute_move_on_cooldown():
    """Test move rejection when on cooldown."""
    player = create_test_player(hp=100)
    enemy = create_test_npc(hp=50)
    game_service = GameService()
    move = moves.PowerStrike()
    
    # Use move once
    game_service.execute_move(player, move, target=enemy)
    
    # Try again immediately (should be on cooldown)
    result = game_service.execute_move(player, move, target=enemy)
    
    assert result['success'] == False
    assert 'cooldown' in result.get('error', '').lower()
```

**Effort:** 45 min | **Lines covered:** ~30 | **Tests:** 3

---

#### Test 2: Cooldown Drain (30 min)

**File:** `tests/api/services/test_game_service_cooldowns.py`

```python
def test_cooldown_drain_per_beat():
    """Test cooldowns drain by 1 per beat during combat."""
    player = create_test_player(hp=100)
    enemy = create_test_npc(hp=50)
    game_service = GameService()
    
    move = moves.PowerStrike()  # 2-turn cooldown
    
    # Execute move, cooldown starts
    game_service.execute_move(player, move, target=enemy)
    assert player.cooldowns[move.name] == 2
    
    # Simulate combat beat
    game_service.drain_cooldowns(player)
    assert player.cooldowns[move.name] == 1
    
    # Another beat
    game_service.drain_cooldowns(player)
    assert player.cooldowns[move.name] == 0
    
    # Move should be available now
    result = game_service.execute_move(player, move, target=enemy)
    assert result['success'] == True

def test_cooldown_not_drain_outside_combat():
    """Test cooldowns don't drain when combat is not active."""
    player = create_test_player(hp=100)
    game_service = GameService()
    
    move = moves.PowerStrike()
    player.cooldowns[move.name] = 2
    
    # Drain outside combat (should not change)
    game_service.drain_cooldowns(player, in_combat=False)
    assert player.cooldowns[move.name] == 2
```

**Effort:** 30 min | **Lines covered:** ~11 | **Tests:** 2

---

#### Test 3: Status Effect Application (60 min)

**File:** `tests/api/services/test_game_service_status.py`

```python
def test_apply_status_effect():
    """Test applying a status effect to target."""
    player = create_test_player(hp=100)
    enemy = create_test_npc(hp=50)
    game_service = GameService()
    
    # Apply Weakened debuff (reduces damage)
    effect = states.Weakened()
    game_service.apply_status_effect(enemy, effect, source=player)
    
    assert effect.name in [e.name for e in enemy.active_states]
    assert enemy.get_state_status(effect.name).duration == effect.default_duration

def test_status_resistance():
    """Test status effect resistance reduces application chance."""
    enemy = create_test_npc(hp=50)
    enemy.status_resistances = {'weakened': 0.8}  # 80% resistance
    game_service = GameService()
    
    effect = states.Weakened()
    
    # Test multiple applications — most should fail
    success_count = 0
    for _ in range(100):
        result = game_service.apply_status_effect(
            enemy, effect, source=None, force=False
        )
        if result:
            success_count += 1
    
    # With 80% resistance, ~20% should succeed
    assert 5 < success_count < 35  # Loose bounds for randomness

def test_status_duration_tick():
    """Test status effects tick down each turn."""
    enemy = create_test_npc(hp=50)
    game_service = GameService()
    
    effect = states.Weakened()
    game_service.apply_status_effect(enemy, effect, duration=3)
    
    # Check initial duration
    active = [e for e in enemy.active_states if e.name == 'weakened'][0]
    assert active.duration == 3
    
    # Tick down
    game_service.tick_status_effects(enemy)
    active = [e for e in enemy.active_states if e.name == 'weakened'][0]
    assert active.duration == 2
    
    # Tick again
    game_service.tick_status_effects(enemy)
    assert active.duration == 1

def test_status_stacking():
    """Test multiple instances of same status stack correctly."""
    enemy = create_test_npc(hp=50)
    game_service = GameService()
    
    effect1 = states.Burn(damage=5)
    effect2 = states.Burn(damage=5)
    
    game_service.apply_status_effect(enemy, effect1)
    game_service.apply_status_effect(enemy, effect2)
    
    burn_effects = [e for e in enemy.active_states if e.name == 'burn']
    assert len(burn_effects) == 2  # Both should be active
    
    # Damage should stack
    total_damage = sum(e.damage for e in burn_effects)
    assert total_damage == 10
```

**Effort:** 60 min | **Lines covered:** ~40 | **Tests:** 4

---

#### Test 4: Combat Beat Progression (45 min)

**File:** `tests/api/services/test_game_service_combat_flow.py`

```python
def test_combat_beat_progression():
    """Test a complete turn of combat."""
    player = create_test_player(hp=100)
    enemy = create_test_npc(hp=50)
    combat = create_test_combat(player, [enemy])
    game_service = GameService()
    
    # Player turn
    move = moves.PowerStrike()
    game_service.execute_move(player, move, target=enemy)
    
    # NPC turn
    npc_move = enemy.select_action()
    game_service.execute_move(enemy, npc_move, target=player)
    
    # Drain cooldowns and tick status effects
    game_service.drain_cooldowns(player)
    game_service.drain_cooldowns(enemy)
    game_service.tick_status_effects(player)
    game_service.tick_status_effects(enemy)
    
    # Combat should still be active
    assert not game_service.is_combat_over(combat)

def test_npc_reinforcement_spawn():
    """Test reinforcement NPCs spawn correctly."""
    player = create_test_player(hp=100)
    combat = create_test_combat(player, [])
    game_service = GameService()
    
    # Schedule reinforcement event
    event = create_reinforcement_event(
        npc_class='Slime',
        spawn_tile=(3, 3),
        wave=1
    )
    player.universe.pending_events.append(event)
    
    # Process events
    game_service.process_universe_events(player)
    
    # Check reinforcement spawned
    assert len(combat.npcs) > 0
    assert any(npc.name == 'Slime' for npc in combat.npcs)

def test_combat_victory():
    """Test combat ends when last enemy defeated."""
    player = create_test_player(hp=100)
    enemy = create_test_npc(hp=10)
    combat = create_test_combat(player, [enemy])
    game_service = GameService()
    
    # Deal fatal damage
    move = moves.PowerStrike()
    result = game_service.execute_move(player, move, target=enemy)
    
    # Check combat is over
    assert game_service.is_combat_over(combat)
    assert result['victory'] == True
```

**Effort:** 45 min | **Lines covered:** ~60 | **Tests:** 3

---

### Subtotal: Priority 1

- **Total effort:** 180 minutes (3 hours)
- **New tests:** 12
- **Expected coverage gain:** +2-3%
- **Lines covered:** ~140 critical lines
- **Impact:** Core game loop now tested; catches most move/combat bugs

---

## Priority 2: API Route Integration Tests (HIGH ROI)

### What's Missing

API routes have only **11-23% coverage**. Most endpoints are untested:

| Route | Coverage | Missing Lines |
|-------|----------|---------------|
| `/api/world/<x>/<y>` | 11% | 58 |
| `/api/combat/status` | 14% | 89 |
| `/api/inventory/use-item` | 12% | 269 |
| `/api/equipment/equip` | 13% | 59 |
| `/api/npc/chat` | 0% | 78 |

### Implementation Plan

#### Test 5: World API (40 min)

**File:** `tests/api/routes/test_world_routes.py`

```python
def test_get_tile_data(client, test_player):
    """Test GET /api/world/<x>/<y> returns tile data."""
    x, y = 5, 5
    
    response = client.get(
        f'/api/world/{x}/{y}',
        headers={'Authorization': f'Bearer {test_player.token}'}
    )
    
    assert response.status_code == 200
    data = response.json
    
    assert 'tile' in data
    assert 'npcs' in data
    assert 'objects' in data
    assert data['x'] == x
    assert data['y'] == y

def test_get_tile_with_npcs(client, test_player):
    """Test tile data includes NPCs."""
    # Place Gorran on tile (5, 5)
    test_player.universe.tiles[5][5].npcs = [create_test_npc(name='Gorran')]
    
    response = client.get(
        '/api/world/5/5',
        headers={'Authorization': f'Bearer {test_player.token}'}
    )
    
    assert response.status_code == 200
    data = response.json
    
    assert len(data['npcs']) > 0
    assert data['npcs'][0]['name'] == 'Gorran'

def test_get_tile_out_of_bounds(client, test_player):
    """Test tile query rejects out-of-bounds coordinates."""
    response = client.get(
        '/api/world/999/999',
        headers={'Authorization': f'Bearer {test_player.token}'}
    )
    
    assert response.status_code == 404
```

**Effort:** 40 min | **Lines covered:** ~25 | **Tests:** 3

---

#### Test 6: Combat Status API (35 min)

**File:** `tests/api/routes/test_combat_routes.py`

```python
def test_get_combat_status(client, test_player_in_combat):
    """Test GET /api/combat/status returns current combat state."""
    response = client.get(
        '/api/combat/status',
        headers={'Authorization': f'Bearer {test_player_in_combat.token}'}
    )
    
    assert response.status_code == 200
    data = response.json
    
    assert 'player_stats' in data
    assert 'enemies' in data
    assert 'available_moves' in data
    assert data['in_combat'] == True

def test_combat_status_not_in_combat(client, test_player):
    """Test combat status when not in combat."""
    response = client.get(
        '/api/combat/status',
        headers={'Authorization': f'Bearer {test_player.token}'}
    )
    
    assert response.status_code == 200
    assert response.json['in_combat'] == False

def test_get_available_moves(client, test_player_in_combat):
    """Test GET /api/combat/moves returns available moves."""
    response = client.get(
        '/api/combat/moves',
        headers={'Authorization': f'Bearer {test_player_in_combat.token}'}
    )
    
    assert response.status_code == 200
    data = response.json
    
    assert len(data['moves']) > 0
    assert all('name' in m for m in data['moves'])
    assert all('cooldown' in m for m in data['moves'])
```

**Effort:** 35 min | **Lines covered:** ~30 | **Tests:** 3

---

#### Test 7: Inventory Use Item (50 min)

**File:** `tests/api/routes/test_inventory_routes.py`

```python
def test_use_consumable(client, test_player):
    """Test POST /api/inventory/use-item with consumable."""
    # Add health potion to inventory
    potion = create_test_item('HealthPotion', quantity=3)
    test_player.inventory.add_item(potion)
    
    initial_hp = test_player.hp
    
    response = client.post(
        '/api/inventory/use-item',
        json={'item_id': potion.id},
        headers={'Authorization': f'Bearer {test_player.token}'}
    )
    
    assert response.status_code == 200
    data = response.json
    
    assert data['success'] == True
    assert test_player.hp > initial_hp  # HP recovered
    assert data['remaining_quantity'] == 2

def test_use_item_not_in_inventory(client, test_player):
    """Test using item that doesn't exist in inventory."""
    response = client.post(
        '/api/inventory/use-item',
        json={'item_id': 99999},  # Non-existent item
        headers={'Authorization': f'Bearer {test_player.token}'}
    )
    
    assert response.status_code == 404

def test_use_equippable_fails(client, test_player):
    """Test using non-consumable item fails."""
    sword = create_test_item('IronSword')
    test_player.inventory.add_item(sword)
    
    response = client.post(
        '/api/inventory/use-item',
        json={'item_id': sword.id},
        headers={'Authorization': f'Bearer {test_player.token}'}
    )
    
    assert response.status_code == 400
    assert 'cannot use' in response.json['error'].lower()
```

**Effort:** 50 min | **Lines covered:** ~50 | **Tests:** 3

---

### Subtotal: Priority 2

- **Total effort:** 125 minutes (2 hours)
- **New tests:** 9
- **Expected coverage gain:** +2-3%
- **Lines covered:** ~105
- **Impact:** Main user-facing APIs now tested; catches routing/serialization bugs

---

## Priority 3: Cleanup & Missing Tests (MEDIUM ROI)

### Test 8: Remove Broken Test File (5 min)

**File:** `frontend/src/components/coverage-100-percent.test.jsx`

This test file imports a non-existent component `LevelUpScreen` and causes test suite failures.

```bash
rm frontend/src/components/coverage-100-percent.test.jsx
```

**Impact:** Fixes frontend test failure; unblocks CI

---

### Test 9: Status Effect Core Tests (45 min)

**File:** `tests/test_states.py`

Focus on the untested 45% of `src/states.py`:

```python
def test_weakened_stat_reduction():
    """Test Weakened reduces outgoing damage."""
    player = create_test_player()
    player.apply_state(states.Weakened())
    
    base_damage = 100
    weakened_damage = player.apply_damage_modification(base_damage)
    
    assert weakened_damage < base_damage

def test_burn_damage_per_turn():
    """Test Burn applies damage each turn."""
    enemy = create_test_npc(hp=100)
    enemy.apply_state(states.Burn(damage=10))
    
    initial_hp = enemy.hp
    
    # Apply damage from burn status
    game_service.apply_status_damage(enemy)
    
    assert enemy.hp == initial_hp - 10

def test_status_immunity():
    """Test status immunity prevents application."""
    enemy = create_test_npc(hp=50)
    enemy.status_immunities.add('burn')
    
    result = game_service.apply_status_effect(enemy, states.Burn())
    
    assert result == False
    assert 'burn' not in [e.name for e in enemy.active_states]
```

**Effort:** 45 min | **Lines covered:** ~25 | **Tests:** 3

---

### Subtotal: Priority 3

- **Total effort:** 50 minutes
- **New tests:** 3 + 1 removal
- **Expected coverage gain:** +1%
- **Lines covered:** ~25
- **Impact:** Status effect mechanics now tested; fixes test suite

---

## Summary: Tier 1 Complete

| Priority | Tests | Effort | Coverage Gain | Total Effort |
|----------|-------|--------|---------------|--------------|
| **Priority 1** (GameService) | 12 | 180 min | +2-3% | 3 hours |
| **Priority 2** (API routes) | 9 | 125 min | +2-3% | 2 hours |
| **Priority 3** (Cleanup/states) | 4 | 50 min | +1% | 1 hour |
| **TOTAL** | **25** | **355 min** | **+5-7%** | **6 hours** |

### Expected Result After Tier 1

- **Coverage:** 56-58% (from 51%)
- **Tests:** 1,928+ (from 1,903)
- **CI threshold:** Can increase to 55% (currently 55%)
- **Next milestone:** 60% target (gap: 2-4 percentage points)

---

## How to Execute These Tests

### Step 1: Create Test Files

```bash
mkdir -p tests/api/services
mkdir -p tests/api/routes
touch tests/api/services/test_game_service_moves.py
touch tests/api/services/test_game_service_cooldowns.py
touch tests/api/services/test_game_service_status.py
touch tests/api/services/test_game_service_combat_flow.py
touch tests/api/routes/test_world_routes.py
touch tests/api/routes/test_combat_routes.py
touch tests/api/routes/test_inventory_routes.py
```

### Step 2: Use Test Fixtures (Already Exist)

The project already has fixtures in `tests/conftest.py`:

```python
import pytest
from tests.conftest import (
    test_player,
    test_npc,
    test_combat,
    test_client,
)
```

### Step 3: Run Tests & Check Coverage

```bash
python -m pytest tests/api/services/test_game_service_moves.py -v

# Check coverage on new tests only
python -m pytest tests/api/services/ --cov=src/api/services/game_service --cov-report=term-missing -v

# After all Tier 1 tests
python -m pytest --cov=src --cov-report=html -q
```

### Step 4: Commit After Each Priority

```bash
# After Priority 1
git add tests/api/services/
git commit -m "test(game-service): Add core move execution and cooldown tests"

# After Priority 2
git add tests/api/routes/
git commit -m "test(api-routes): Add world, combat, and inventory integration tests"

# After Priority 3
git add tests/ frontend/
git commit -m "test(cleanup): Remove broken frontend test and add status effect tests"

# Final
git push origin claude/improve-test-coverage-AUK7z
```

---

## Estimated Timeline

- **Day 1:** Priority 1 tests (GameService) — 3 hours
- **Day 2:** Priority 2 tests (API routes) — 2 hours
- **Day 3:** Priority 3 tests (cleanup) — 1 hour
- **Day 4:** Debugging & refinement — 2 hours

**Total: 8 days of focused work → 56-58% coverage**

Then move to Tier 2 (next 15 hours → 65-75% coverage).

---

## Continuation: Tier 2 Planning (After Tier 1)

Once Tier 1 is complete, start Tier 2:

1. **NPC Combat AI** (4 hours)
   - Test `npc._combat.select_action()`
   - Different AI personalities (aggressive, defensive, tactical)
   - Tests: 15-20

2. **Ranged Mechanics** (3 hours)
   - Targeting, range validation, ammo
   - Tests: 12-15

3. **Movement & Positioning** (3 hours)
   - Dodge/Parry/Advance/Withdraw
   - Tests: 12-15

4. **Shop System** (3 hours)
   - Buy/sell with gold, inventory slots
   - Tests: 12-15

5. **Quest Completion** (2 hours)
   - Quest state transitions, rewards
   - Tests: 8-10

**Tier 2 Total: 60-75 new tests, +8-10% coverage**

---

## References

- **Coverage Report:** `/home/user/Heart-Of-Virtue/docs/coverage/COVERAGE_REPORT.md`
- **HTML Report:** `/home/user/Heart-Of-Virtue/docs/coverage/index.html`
- **Test Fixtures:** `tests/conftest.py`
- **GameService:** `src/api/services/game_service.py`
- **Routes:** `src/api/routes/`

---

**Next Action:** Start with Priority 1, Test 1 (Basic Move Execution). Estimated time: 45 minutes.
