# Milestone 2 Phase 4 - Combat Serialization Plan

## Overview
Implement complete serialization for combat system to enable real-time combat state management and combat actions via the REST API. This phase builds on the serializers foundation and enables combat endpoints.

## Phase Goals
1. ✅ Create CombatState Serializer for battle state
2. ✅ Create CombatantSerializer for character/NPC combat info
3. ✅ Create MoveSerializer for combat abilities
4. ✅ Create StateEffectSerializer for status conditions
5. ✅ Integrate serializers into GameService combat methods
6. ✅ Implement combat action methods (attack, defend, use_move, etc.)
7. ✅ Pass all combat-related tests
8. ✅ Update OpenAPI schema with combat definitions

## Serializers to Implement

### 1. CombatStateSerializer (src/api/serializers/combat.py)
**Goal**: Serialize entire battle state

Combat state data:
- Active combatants (player and enemies)
- Turn order
- Current turn info
- Battle status (active, won, lost)
- Round number

Methods:
- `serialize_combat_state(combat_list, player, enemies)` - Full battle state
- `serialize_turn_data(combatant)` - Current turn information
- `serialize_battle_summary(combat_list, player, enemies)` - Quick battle status

### 2. CombatantSerializer (src/api/serializers/combat.py)
**Goal**: Serialize combatant information during battle

Combatant data:
- Name, level, type
- Current HP, max HP
- Damage, armor, resistances
- Status effects (poison, stun, sleep, etc.)
- Position in combat proximity
- Available moves/actions

Methods:
- `serialize_combatant(combatant)` - Full combatant state
- `serialize_combatant_list(combatants)` - Multiple combatants
- `serialize_health_bar(combatant)` - HP display data
- `serialize_status_effects(combatant)` - Conditions affecting combatant

### 3. MoveSerializer (src/api/serializers/combat.py)
**Goal**: Serialize combat moves/abilities

Move data:
- Name, description, damage type
- Damage/healing value
- Cost (MP, stamina, cooldown)
- Range, AoE
- Status effects applied
- Cooldown remaining

Methods:
- `serialize_move(move)` - Single move details
- `serialize_move_list(moves)` - Available moves
- `serialize_move_with_cooldown(move)` - Move state in battle

### 4. StateEffectSerializer (src/api/serializers/combat.py)
**Goal**: Serialize status effects and conditions

State effect data:
- Name, type (poison, stun, sleep, etc.)
- Damage per turn / healing per turn
- Duration remaining
- Severity (light, moderate, severe)
- Resistances

Methods:
- `serialize_state(state)` - Single effect
- `serialize_state_list(states)` - Multiple effects
- `serialize_state_with_duration(state, remaining)` - Effect with countdown

## GameService Methods to Implement

Update `src/api/services/game_service.py`:

1. `start_combat(player, enemy)` - Initiate combat with NPC/enemy
2. `get_combat_state(player)` - Current battle state
3. `execute_move(player, move_name, target_id)` - Execute combat action
4. `defend(player)` - Take defensive stance
5. `use_item_in_combat(player, item_index, target_id)` - Use consumable
6. `flee_combat(player)` - Attempt to escape
7. `get_available_moves(player)` - List usable moves
8. `end_combat(player, victory)` - Finish combat

## Routes Already Defined (need implementation)

Combat routes (src/api/routes/combat.py):
- `POST /combat/start` - Start combat with enemy
- `GET /combat/` - Get current combat state
- `POST /combat/move` - Execute move/action
- `POST /combat/defend` - Defend action
- `POST /combat/item` - Use item in combat
- `POST /combat/flee` - Attempt to flee
- `GET /combat/moves` - Available moves
- `POST /combat/end` - End combat

## Implementation Strategy

### Phase 4a: Core Serializers (Day 1)
1. Create CombatStateSerializer with battle state serialization
2. Create CombatantSerializer for character/NPC serialization
3. Create MoveSerializer for ability information
4. Create StateEffectSerializer for status conditions
5. Unit tests for each serializer

### Phase 4b: GameService Integration (Day 2)
1. Implement start_combat() method
2. Implement get_combat_state() method
3. Implement execute_move() method
4. Implement defend(), use_item_in_combat(), flee_combat()
5. Integration tests for game service

### Phase 4c: Route Integration & Testing (Day 3)
1. Wire serializers into combat routes
2. Fix failing combat-related tests
3. Verify all combat tests passing
4. Update OpenAPI schema for combat endpoints

## Test Coverage

**Target**: All combat tests passing

**Current Status**: Routes defined but serializers need implementation
- Combat routes exist but return stubs
- GameService combat methods are TODO

**Work Required**:
- Implement 4 serializer classes
- Implement 8 GameService methods
- Integrate into routes
- Update tests to use real serializers

## Files to Create/Modify

### New Files
- `src/api/serializers/combat.py` - All 4 serializers
- `tests/api/test_combat_serializer.py` - Serializer tests

### Modified Files
- `src/api/services/game_service.py` - Add combat methods
- `src/api/routes/combat.py` - Use CombatStateSerializer, etc.
- `src/api/schemas/openapi.py` - Add combat endpoint schemas

## Architecture Notes

**Combat State Flow**:
```python
class CombatStateSerializer:
    @staticmethod
    def serialize_combat_state(combat_list, player, enemies):
        """Full combat state for API response"""
        return {
            "active": True,
            "turn_number": turn,
            "current_turn": serialize_combatant(current_combatant),
            "player": serialize_combatant(player),
            "enemies": [serialize_combatant(e) for e in enemies],
            "turn_order": get_turn_order(),
        }
```

**Combatant Serialization**:
```python
class CombatantSerializer:
    @staticmethod
    def serialize_combatant(combatant):
        """Character/NPC state during combat"""
        return {
            "name": combatant.name,
            "level": combatant.level,
            "hp": combatant.health,
            "max_hp": combatant.max_health,
            "status_effects": [serialize_state(s) for s in combatant.states],
            "available_moves": [serialize_move(m) for m in get_moves()],
        }
```

## Success Criteria

1. ✅ All 4 serializers implemented and tested
2. ✅ GameService has all 8 combat methods
3. ✅ Combat routes working with serializers
4. ✅ All combat tests passing
5. ✅ No regression in existing tests
6. ✅ OpenAPI schema updated with combat endpoints

## Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Complex turn order logic | Incorrect action sequence | Unit test turn ordering thoroughly |
| Status effect application | Incorrect damage/healing | Mock status effects with known values |
| Move validation | Invalid moves executed | Validate move names against available list |
| Combat state mutations | Shared state bugs | Use fresh serialization each turn |
| Performance with many combatants | Slow API responses | Cache serializer output between turns |

## Timeline

| Phase | Days | Tasks |
|-------|------|-------|
| 4a | 1 | Create 4 serializers + unit tests |
| 4b | 1 | GameService methods + integration tests |
| 4c | 1 | Route integration + final testing |

**Estimated Completion**: ~3 working days from phase start

## Next Phase (M2 Phase 5)

After combat serialization:
- NPC/AI state serialization
- Dialogue system serialization
- Quest/Story state serialization
- Full world state snapshot

Then move to:
- Phase 3: Advanced features (skills, spells, etc.)
- Phase 4: Persistence layer (save/load)
- Phase 5: Multiplayer considerations

## Current Combat System Notes

From codebase analysis:
- `src/combat.py` - Main combat engine
- `src/moves.py` - Move/ability definitions
- `src/states.py` - Status effects (poison, stun, sleep, etc.)
- Combat uses turn-based system with `combat_list` and `combat_list_allies`
- Player combat accessed via `player.combat()` method
- Moves have cooldowns, damage types, resistances
- Status effects have repeating damage, conditions, duration

