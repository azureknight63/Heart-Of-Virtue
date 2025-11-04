# HV-1: Coordinate-Based Combat Positioning
## Implementation Status Report

**Date:** November 4, 2025  
**Branch:** `HV-1-coordinate-combat-positioning`  
**Status:** Major Implementation Complete (Phase 2 & 3 Underway)

---

## Summary

From the **HV-1 Phase 1 Analysis**, the following proposed features and moves have been implemented:

### ✅ IMPLEMENTED (18 moves/features)

#### Movement Moves (Already Available)
- ✅ **Advance** - Move toward designated target
- ✅ **Withdraw** - Move away from nearest enemy

#### Facing Direction Moves (NEW - HV-1 Specific)
- ✅ **Turn** - Rotate to face a direction or target
- ✅ **WhirlAttack** - Spin strike hitting nearby enemies
- ✅ **FeintAndPivot** - Attack and reposition behind target
- ✅ **KnockbackStunSpin** - Attack with knockback and rotation effect

#### Skill-Gated Movement Tier 1
- ✅ **BullCharge** - Charge toward enemy with momentum bonus
- ✅ **TacticalRetreat** - Move away while maintaining ranged angle
- ✅ **FlankingManeuver** - Reposition to side of enemy for advantage

#### Standard Combat Moves (Pre-existing)
- ✅ Dodge, Parry, Check, Wait, Attack, Rest, UseItem
- ✅ Slash, PommelStrike, ShootBow, QuietMovement, PowerStrike, Jab
- ✅ Special NPC moves: GorranClub, VenomClaw, SpiderBite, BatBite

#### Infrastructure
- ✅ `CombatPosition` class (coordinates x, y + facing direction)
- ✅ Distance calculation from coordinates
- ✅ Facing direction system (8 compass directions)
- ✅ Attack angle calculations and modifiers (frontal, flank, backstab)
- ✅ Position initialization at combat start

---

## ❌ NOT YET IMPLEMENTED (5 features)

### Tier 2 (Intermediate Skills) - Skill-Unlocked

**1. QuickSwap (Position Swap with Ally)**
- Proposed: Swap positions with nearby ally for tactical repositioning
- Status: ❌ Not implemented
- Estimated complexity: **Medium**
- Dependencies: 
  - Multi-unit positioning system (allies in combat)
  - Position swap validation (no collision)
  - Distance calculation for "nearby" definition
  - Beat/fatigue cost integration

**2. Repositioning (Advanced Positioning Skill)**
- Proposed: Advanced tactical repositioning system
- Status: ❌ Not implemented (related: `TacticalPositioning` exists but for different purpose)
- Estimated complexity: **Medium**
- Note: The existing `TacticalPositioning` move appears to be a different feature
- Dependencies:
  - Coordinate system fully operational
  - Skill unlock system integration
  - Position validation

### Tier 3 (Advanced Skills) - High-Level Play

**3. DimensionalShift (Teleport)**
- Proposed: Teleport to specified coordinate within range
- Status: ❌ Not implemented
- Estimated complexity: **High**
- Unlock requirement: Level 20+ with spatial magic tome
- Dependencies:
  - Coordinate selection UI
  - Range validation
  - Combat UI updates
  - Possible spell system integration

**4. CombatDance (Rapid Repositioning Chain)**
- Proposed: Chain rapid movements (3 sequential micro-moves)
- Status: ❌ Not implemented
- Estimated complexity: **High**
- Requirements: Dexterity 50+ + Dance skill tome
- Dependencies:
  - Movement chaining system
  - Evasion bonus effect
  - Multiple micro-move tracking
  - Animation system integration

### Boss/Unique Abilities

**5. Additional Boss-Specific Variants**
- Proposed: Boss-specific movement/positioning abilities
- Status: ❌ Partially implemented (only standard bosses have unique attacks)
- Examples not yet implemented:
  - Boss-specific "Intimidating Presence" (enemies in front take penalty)
  - Boss-only positioning abilities
  - "Only vulnerable to backstabs" mechanic
- Estimated complexity: **Medium-High**
- Dependencies:
  - Boss template system
  - Custom ability attachment
  - Special mechanic validation

---

## Implementation Details by Category

### ✅ COMPLETE: Core Positioning System

**Coordinate System:**
- `CombatPosition` data structure (x, y, facing)
- 50×50 grid basis
- Euclidean distance conversion

**Facing Direction:**
- 8 compass directions (N, NE, E, SE, S, SW, W, NW)
- Attack angle calculation (0-180°)
- Damage/accuracy modifiers based on angle:
  - Frontal (0-45°): 0.85 damage, 0.95 accuracy
  - Flanking (45-90°): 1.15 damage, 1.10 accuracy
  - Deep flank (90-135°): 1.25 damage, 1.20 accuracy
  - Backstab (135-180°): 1.40 damage, 1.30 accuracy

**Position Initialization:**
- Combat scenarios: standard, pincer, melee, boss arena
- NPC spawn preferences (alone, cluster, formation)
- Formation roles (leader, flanker, support)

### ✅ COMPLETE: Implemented Moves

**Movement Primitives:**
- Advance (2 squares toward target)
- Withdraw (2 squares away from nearest)

**Tier 1 Offensive Positioning:**
- Turn (change facing direction)
- BullCharge (5 squares + momentum bonus)
- TacticalRetreat (2 squares away while maintaining angle)
- FlankingManeuver (3 squares to perpendicular position)

**Tier 1 Attack Variants:**
- WhirlAttack (360° spin hitting nearby enemies)
- FeintAndPivot (attack + reposition behind target)
- KnockbackStunSpin (attack + rotation effect)

### ❓ PARTIAL: Skills System Integration

Current status of skill unlock system for movement moves:
- ✅ Moves are defined with appropriate cost/fatigue
- ✅ Level requirements documented
- ❓ Skill unlock logic may need integration
- ❓ "Momentum", "Flanking_Position" status effects may need validation
- ❓ Skill tome/book system may need verification

---

## Proposed vs. Actual Implementation

| Feature | Proposed | Actual | Status |
|---------|----------|--------|--------|
| Basic Advance/Withdraw | Yes | Full | ✅ |
| Turn Move | Yes | Full | ✅ |
| WhirlAttack | Yes | Full (KnockbackStunSpin added) | ✅ |
| FeintAndPivot | Yes | Full | ✅ |
| BullCharge | Yes | Full | ✅ |
| TacticalRetreat | Yes | Full | ✅ |
| FlankingManeuver | Yes | Full | ✅ |
| Coordinate System | Yes | Full | ✅ |
| Facing Direction | Yes | Full | ✅ |
| Attack Angle Modifiers | Yes | Full | ✅ |
| QuickSwap | Yes | Missing | ❌ |
| DimensionalShift | Yes | Missing | ❌ |
| CombatDance | Yes | Missing | ❌ |
| Combat Scenarios | Yes | Partial | ⚠️ |
| NPC Movement AI | Outlined | Partial | ⚠️ |

---

## Remaining Work (Priority Order)

### P1: Complete Tier 2 Skills
1. **QuickSwap**
   - Swap positions with nearby ally
   - Validation: both units remain in bounds
   - Cost: 1-2 beats, 10-15 fatigue
   - Files: `src/moves.py`

2. **Repositioning (Advanced)**
   - Advanced tactical positioning skill
   - Check naming: conflicts with `TacticalPositioning`?
   - Cost: 2-3 beats, 20-25 fatigue
   - Files: `src/moves.py`

### P2: Advanced Tier 3 Skills (High-Level Play)
3. **DimensionalShift**
   - Player selects destination (up to 8 squares)
   - Can choose new facing post-teleport
   - Cost: 3-4 beats, 40-50 fatigue
   - Unlock: Level 20+ + "Spatial Magic" tome
   - Files: `src/moves.py`, possibly `src/skilltree.py`

4. **CombatDance**
   - 3 sequential micro-movements (1-2 squares each)
   - Apply evasion bonus (hard to target)
   - Cost: 4-5 beats, 50 fatigue
   - Requirements: Dexterity 50+ + "Dance" tome
   - Files: `src/moves.py`, `src/states.py` (evasion effect)

### P3: Boss-Specific Abilities
5. **Unique Boss Positioning Mechanics**
   - Intimidating Presence (enemies in front take penalty)
   - Only vulnerable to backstabs (special boss pattern)
   - Boss-specific custom moves
   - Files: `src/npc.py`, `src/moves.py`

---

## Test Coverage Status

### Tests for Implemented Features
```bash
# Run tests for coordinate system
pytest tests/core/test_positions.py -v

# Run tests for movement moves
pytest tests/combat/test_advance_integration.py -v
pytest tests/combat/test_advance_viable.py -v

# Run tests for combat system
pytest tests/combat/ -v
```

### Tests Needed for Remaining Features
- [ ] `test_quickswap.py` - Position swap mechanics
- [ ] `test_dimensional_shift.py` - Teleportation validation
- [ ] `test_combat_dance.py` - Rapid repositioning chain
- [ ] `test_boss_special_mechanics.py` - Boss-specific abilities

---

## Files Changed/To Change

### Already Modified (Phase 2)
- ✅ `src/player.py` - combat_positions, facing direction
- ✅ `src/npc.py` - combat_positions, facing direction, spawn preferences
- ✅ `src/combat.py` - position initialization, synchronize_distances
- ✅ `src/moves.py` - New movement moves implemented
- ✅ `src/positions.py` - Utility module for coordinate math

### To Modify (Remaining Work)
- `src/moves.py` - Add QuickSwap, DimensionalShift, CombatDance
- `src/skilltree.py` - Link skill unlocks to move availability
- `src/states.py` - Add evasion/status effects for CombatDance
- `src/npc.py` - Boss-specific ability system

---

## Risk Assessment (Updated)

| Risk | Likelihood | Severity | Mitigation |
|------|------------|----------|-----------|
| Tier 3 skills too powerful | Medium | Medium | Balance against boss difficulty |
| Teleportation abuse | Low | High | Add cooldown, restrict by level/mp |
| Position overlap edge cases | Low | Medium | Comprehensive collision testing |
| NPC AI doesn't use new moves | Medium | Medium | Implement AI selection logic in `npc_select_move()` |
| Performance with many repositioning | Low | Low | Profile and optimize if needed |

---

## Next Steps

1. **Implement QuickSwap** - Ally position swapping
2. **Implement DimensionalShift** - Teleportation ability
3. **Implement CombatDance** - Evasion sequence
4. **Add boss-specific variants** - Unique positioning mechanics
5. **Comprehensive testing** - Test all combinations of moves + positioning
6. **Balance pass** - Ensure costs/benefits are appropriate
7. **Update NPC AI** - Teach enemies when to use new moves
8. **Documentation** - Update player-facing guides

---

## References

- **Main Issue:** HV-1 (Coordinate-based Combat Positioning)
- **Analysis Document:** `docs/development/HV-1-PHASE-1-ANALYSIS.md`
- **Moves Module:** `src/moves.py`
- **Positions Module:** `src/positions.py`
- **Combat Module:** `src/combat.py`

**Branch:** `HV-1-coordinate-combat-positioning`  
**Current Phase:** Phase 3 (Gradual Refactoring + New Features)

---

**Last Updated:** November 4, 2025
