# HV-1: Phase 3 - Advanced Positioning Moves
## Implementation Plan

**Date:** November 2, 2025  
**Status:** Planning Phase  
**Branch:** `HV-1-coordinate-combat-positioning`  
**Target:** Implement 4 facing-dependent moves with full test coverage

---

## Phase 3 Overview

Phase 3 implements advanced combat moves that leverage the coordinate-based positioning system from Phase 1-2. These moves enable tactical gameplay where combatants rotate their facing direction, reposition around targets, and create strategic opportunities based on attack angles.

### Core Objectives

1. ✅ Implement 4 new facing-dependent moves
2. ✅ Integrate with existing move system and cooldowns
3. ✅ Add fatigue and beat cost management
4. ✅ Create comprehensive test suite
5. ✅ Maintain backward compatibility
6. ✅ Document all features

### Success Criteria

- All 4 new moves functional and tested
- 100% pass rate on new test suite (40+ tests)
- Integration with combat system verified
- No regression in existing 781 tests
- Complete documentation

---

## New Moves to Implement

### 1. **Turn** (Basic Facing Rotation)
**Purpose:** Allow players to rotate to face a selected direction or target  
**Skill Level:** Basic (available to all)

**Specifications:**
- **Cost:** 1-2 beats
- **Fatigue Cost:** 5-10 (low)
- **Viability:** Always available during combat
- **Effect:** Rotate player facing to selected direction (8 compass directions or toward specific target)

**Implementation Details:**
```python
class Turn(Move):
    name = "Turn"
    description = "Rotate to face a new direction or target"
    beats_cost = 2
    fatigue_cost = 8
    requires_target = False  # Player selects direction, not target
    
    def viable(self):
        """Turn is always viable in combat"""
        return self.user in self.user.combat_list or len(self.user.combat_proximity) > 0
    
    def execute(self, user, *args):
        """Execute turn, rotating player's facing direction"""
        if args and hasattr(args[0], 'combat_position'):
            # Target provided - face toward target
            target = args[0]
            new_facing = calculate_facing_toward(user.combat_position, target.combat_position)
        else:
            # Player selects direction via UI
            new_facing = player_select_facing_direction()
        
        old_facing = user.combat_position.facing
        user.combat_position.facing = new_facing
        
        self.user.log_move(f"{user.name} turned to face {direction_name(new_facing)}")
        return {
            'success': True,
            'old_facing': old_facing,
            'new_facing': new_facing
        }
```

**Tactical Uses:**
- Prevent backstabs by facing incoming threats
- Prepare for enemy advance
- Face multiple enemies in different directions
- Low-risk positioning adjustment

---

### 2. **Whirl Attack** (AOE Spin Strike)
**Purpose:** Damage multiple nearby enemies while rotating facing  
**Skill Level:** Intermediate (requires 5+ beats management)

**Specifications:**
- **Cost:** 3-4 beats
- **Fatigue Cost:** 25-35 (medium-high)
- **Range:** 5 squares radius (approximately melee + 2)
- **Targets:** All enemies within radius
- **Effect:** Damage all nearby enemies, random facing after attack

**Implementation Details:**
```python
class WhirlAttack(Move):
    name = "Whirl Attack"
    description = "Spin attack hitting all nearby enemies, ends with random facing"
    beats_cost = 4
    fatigue_cost = 30
    requires_target = False  # AOE move
    
    def viable(self):
        """Whirl is viable if there are enemies in range"""
        nearby = get_enemies_within_radius(
            self.user,
            self.user.combat_position,
            radius=5
        )
        return len(nearby) > 0
    
    def execute(self, user):
        """Execute whirl attack, damaging all nearby enemies"""
        nearby_enemies = get_enemies_within_radius(user, user.combat_position, radius=5)
        
        if not nearby_enemies:
            self.user.log_move(f"{user.name} whirled but hit nothing!")
            return {'success': False, 'reason': 'No nearby enemies'}
        
        # Damage each nearby enemy
        total_damage = 0
        for enemy in nearby_enemies:
            # Calculate damage with angle modifiers
            angle_diff = calculate_attack_angle_difference(
                angle_to_target(user.combat_position, enemy.combat_position),
                enemy.combat_position.facing
            )
            damage = self.calculate_damage(user, angle_diff=angle_diff)
            enemy.take_damage(damage)
            total_damage += damage
            
            self.user.log_move(f"{user.name}'s whirl attacked {enemy.name} for {damage} damage!")
        
        # Rotate to random facing
        old_facing = user.combat_position.facing
        new_facing = random.choice(list(Direction))
        user.combat_position.facing = new_facing
        
        self.user.log_move(f"{user.name} ended facing {direction_name(new_facing)}")
        
        return {
            'success': True,
            'targets_hit': len(nearby_enemies),
            'total_damage': total_damage,
            'old_facing': old_facing,
            'new_facing': new_facing
        }
```

**Tactical Uses:**
- Clear groups of weak enemies
- Damage multiple enemies when surrounded
- Unpredictable positioning after attack (enemy can't backstab)
- High risk/high reward move

**Balance Notes:**
- Damage per target slightly reduced vs single-target attacks
- Random facing adds strategic element (unpredictable but risky)
- High fatigue cost prevents spam

---

### 3. **Feint & Pivot** (Repositioning Attack)
**Purpose:** Attack target then reposition behind them  
**Skill Level:** Advanced (requires tactical thinking)

**Specifications:**
- **Cost:** 4-5 beats
- **Fatigue Cost:** 40-50 (high)
- **Effect:** Attack target, then move behind target facing same direction
- **Range:** Must be within melee range to execute

**Implementation Details:**
```python
class FeintAndPivot(Move):
    name = "Feint & Pivot"
    description = "Attack target then reposition behind them"
    beats_cost = 5
    fatigue_cost = 45
    requires_target = True
    
    def viable(self):
        """Feint is viable if target is within melee range"""
        if not self.target:
            return False
        distance = distance_from_coords(
            self.user.combat_position,
            self.target.combat_position
        )
        return distance <= 5  # Melee range
    
    def execute(self, user, target):
        """Execute feint and pivot"""
        if not self.viable():
            self.user.log_move(f"{user.name} tried feint & pivot but {target.name} was too far away!")
            return {'success': False, 'reason': 'Target out of range'}
        
        # Phase 1: Attack from current position
        attack_angle = angle_to_target(user.combat_position, target.combat_position)
        angle_diff = calculate_attack_angle_difference(attack_angle, target.combat_position.facing)
        damage = self.calculate_damage(user, angle_diff=angle_diff)
        target.take_damage(damage)
        
        self.user.log_move(f"{user.name} attacked {target.name} for {damage} damage!")
        
        # Phase 2: Calculate position behind target
        behind_pos = calculate_position_behind(target.combat_position, distance=2)
        
        # Check collision
        if is_position_occupied(behind_pos, excluded=[user, target]):
            self.user.log_move(f"{user.name} couldn't complete pivot - blocked!")
            return {
                'success': False,
                'reason': 'Position blocked',
                'damage_dealt': damage
            }
        
        # Phase 3: Reposition and face same direction as target
        old_pos = user.combat_position.copy()
        user.combat_position.x = behind_pos.x
        user.combat_position.y = behind_pos.y
        user.combat_position.facing = target.combat_position.facing
        
        self.user.log_move(f"{user.name} pivoted behind {target.name}!")
        
        return {
            'success': True,
            'damage_dealt': damage,
            'old_position': old_pos,
            'new_position': user.combat_position.copy(),
            'new_facing': user.combat_position.facing
        }
```

**Tactical Uses:**
- Set up backstab opportunity for next turn
- Escape frontal position after attack
- Position for allies to attack frontally
- High-skill move with big payoff

**Balance Notes:**
- Can fail if position behind target is occupied
- High beat and fatigue cost
- Requires correct distance (not too close, not too far)

---

### 4. **Knockback/Stun Spin** (Enemy Repositioning)
**Purpose:** Powerful attack that forces target to face away  
**Skill Level:** Advanced (crowd control element)

**Specifications:**
- **Cost:** 3-4 beats
- **Fatigue Cost:** 35-45 (medium-high)
- **Effect:** Damage target + force facing away + apply "Disoriented" status
- **Status Duration:** 2-3 beats
- **Status Effect:** "Disoriented" reduces accuracy and defense

**Implementation Details:**
```python
class KnockbackStunSpin(Move):
    name = "Knockback Stun Spin"
    description = "Powerful attack that spins target away, applying Disoriented status"
    beats_cost = 4
    fatigue_cost = 40
    requires_target = True
    
    def viable(self):
        """Knockback is viable if target exists"""
        return self.target is not None and self.target in self.user.combat_proximity
    
    def execute(self, user, target):
        """Execute knockback attack"""
        # Phase 1: Calculate and apply damage
        angle_to_target = angle_to_target(user.combat_position, target.combat_position)
        angle_diff = calculate_attack_angle_difference(angle_to_target, target.combat_position.facing)
        
        # Knockback has bonus damage for this move type
        base_damage = self.calculate_damage(user, angle_diff=angle_diff)
        knockback_bonus = 1.15  # +15% damage for this move
        damage = int(base_damage * knockback_bonus)
        
        target.take_damage(damage)
        self.user.log_move(f"{user.name} hit {target.name} with knockback spin for {damage} damage!")
        
        # Phase 2: Rotate target's facing away from attacker
        # Calculate angle away from attacker
        angle_away_from_attacker = (angle_to_target + 180) % 360
        new_facing = angle_to_direction(angle_away_from_attacker)
        target.combat_position.facing = new_facing
        
        self.user.log_move(f"{target.name} was spun around to face {direction_name(new_facing)}!")
        
        # Phase 3: Apply Disoriented status effect
        disoriented = DisoriientedStatus(
            duration_beats=3,
            accuracy_penalty=-20,
            defense_penalty=-15
        )
        target.apply_status(disoriented)
        
        self.user.log_move(f"{target.name} is now Disoriented!")
        
        return {
            'success': True,
            'damage_dealt': damage,
            'target_new_facing': new_facing,
            'status_applied': 'Disoriented',
            'status_duration': 3
        }
```

**Tactical Uses:**
- Prevent enemy from backstabbing allies
- Disrupt enemy strategy
- Crowd control in group fights
- Reduce accuracy/defense of tough enemies

**Balance Notes:**
- Bonus damage justifies high cost
- Status effect has defined duration
- Can be cleansed by certain abilities/items

---

## Implementation Architecture

### New Classes/Updates

#### 1. Base Classes (`src/moves.py`)

**Update Move class with facing support:**
```python
class Move:
    # Existing fields...
    
    # New fields for Phase 3
    affects_facing: bool = False  # Does this move change facing?
    is_positioning_move: bool = False  # Is this a positioning/movement move?
    affected_by_facing: bool = False  # Does target's facing affect this move?
```

#### 2. New Status Effect (`src/states.py`)

**Add Disoriented status:**
```python
class Disoriented(StatusEffect):
    """Applied by Knockback/Stun Spin - reduces accuracy and defense"""
    name = "Disoriented"
    accuracy_penalty = -20
    defense_penalty = -15
    duration_beats = 3
```

#### 3. Helper Functions (`src/positions.py` - updates)

**Add positioning helpers:**
```python
def calculate_facing_toward(pos1: CombatPosition, pos2: CombatPosition) -> Direction:
    """Calculate facing direction from pos1 toward pos2"""
    angle = angle_to_target(pos1, pos2)
    return angle_to_direction(angle)

def calculate_position_behind(target_pos: CombatPosition, distance: int = 2) -> CombatPosition:
    """Calculate position behind target"""
    # 180° from target's facing
    behind_angle = (target_pos.facing.value + 180) % 360
    dx = distance * cos(radians(behind_angle))
    dy = distance * sin(radians(behind_angle))
    
    new_x = clamp(target_pos.x + dx, 0, 50)
    new_y = clamp(target_pos.y + dy, 0, 50)
    
    return CombatPosition(x=int(new_x), y=int(new_y), facing=Direction.N)

def is_position_occupied(pos: CombatPosition, excluded: List = None) -> bool:
    """Check if position is occupied by any combatant"""
    # Implementation checks current combat state
    pass

def angle_to_direction(angle: int) -> Direction:
    """Convert angle (0-360) to closest Direction enum"""
    # Map angle ranges to directions
    pass
```

### Integration Points

**1. Combat System (`src/combat.py`)**
- Add new moves to move pool based on player/enemy level
- Handle facing changes during combat loop
- Apply facing modifiers to damage calculations

**2. Move Selection (`src/moves.py`)**
- Update Move viability checks to consider position
- Add facing-awareness to AI move selection

**3. Combat Display (`src/combat_battlefield.py`)**
- Show facing direction arrows for all combatants
- Highlight Disoriented status

---

## Test Coverage Plan

### Test File: `tests/test_phase3_advanced_moves.py`

**Test Categories (40+ tests):**

```python
class TestTurnMove:
    # 5 tests
    - test_turn_to_direction()
    - test_turn_toward_target()
    - test_turn_always_viable()
    - test_turn_cost_and_fatigue()
    - test_turn_facing_change()

class TestWhirlAttack:
    # 8 tests
    - test_whirl_attack_damages_nearby_enemies()
    - test_whirl_attack_range_5_squares()
    - test_whirl_attack_fails_if_no_enemies()
    - test_whirl_attack_random_facing()
    - test_whirl_attack_multiple_targets()
    - test_whirl_attack_angle_modifiers()
    - test_whirl_attack_cost_and_fatigue()
    - test_whirl_attack_with_different_facing()

class TestFeintPivot:
    # 10 tests
    - test_feint_pivot_basic_execution()
    - test_feint_pivot_requires_melee_range()
    - test_feint_pivot_fails_if_target_far()
    - test_feint_pivot_attack_damage()
    - test_feint_pivot_repositions_behind_target()
    - test_feint_pivot_faces_same_direction_as_target()
    - test_feint_pivot_fails_if_position_blocked()
    - test_feint_pivot_cost_and_fatigue()
    - test_feint_pivot_with_multiple_enemies_nearby()
    - test_feint_pivot_angle_calculations()

class TestKnockbackStunSpin:
    # 10 tests
    - test_knockback_damages_target()
    - test_knockback_bonus_damage()
    - test_knockback_rotates_facing()
    - test_knockback_applies_disoriented_status()
    - test_disoriented_reduces_accuracy()
    - test_disoriented_reduces_defense()
    - test_disoriented_duration_beats()
    - test_knockback_cost_and_fatigue()
    - test_knockback_with_angle_variations()
    - test_knockback_status_stacking()

class TestIntegration:
    # 7 tests
    - test_moves_available_in_combat()
    - test_moves_respect_cooldowns()
    - test_facing_changes_affect_next_attacks()
    - test_all_moves_work_together()
    - test_position_updates_in_combat_log()
    - test_moves_with_multiple_combatants()
    - test_moves_with_mixed_facing_directions()
```

---

## Implementation Phases

### Phase 3a: Core Moves (Week 1)
1. Update Move class with facing support
2. Implement Turn move
3. Implement Whirl Attack
4. Create basic tests (15+ tests)

### Phase 3b: Advanced Moves (Week 2)
5. Implement Feint & Pivot
6. Implement Knockback/Stun Spin
7. Add Disoriented status effect
8. Expand tests (25+ more tests)

### Phase 3c: Integration & Polish (Week 3)
9. Integrate with combat system
10. Update combat display
11. Balance pass
12. Complete test suite (40+ tests)
13. Documentation

---

## File Modifications Required

| File | Type | Changes |
|------|------|---------|
| `src/moves.py` | Update | Add new move classes, update Move base class |
| `src/states.py` | Update | Add Disoriented status effect |
| `src/positions.py` | Update | Add positioning helper functions |
| `src/combat.py` | Update | Integrate new moves, apply facing modifiers |
| `src/combat_battlefield.py` | Update | Display facing arrows, status effects |
| `tests/test_phase3_advanced_moves.py` | Create | Comprehensive test suite |

---

## Success Metrics

| Metric | Target | Status |
|--------|--------|--------|
| All 4 moves implemented | ✓ | Pending |
| Test coverage | 40+ tests passing | Pending |
| No regression | 781 existing tests still pass | Pending |
| Documentation | Complete with examples | Pending |
| Integration | Moves work in combat | Pending |
| Balance | Moves feel tactical and useful | Pending |

---

## Next Steps to Begin Implementation

1. **Create Phase 3 branch or continue on HV-1 branch**
2. **Start with Turn move (simplest)**
3. **Add corresponding tests**
4. **Commit with clear messages**
5. **Move to Whirl Attack**
6. **Continue with Feint & Pivot**
7. **Finish with Knockback/Stun Spin**
8. **Integration testing and polish**

---

## References

- **HV-1-PHASE-1-ANALYSIS.md:** Full specifications (lines 250-400)
- **HV-1-IMPLEMENTATION-STATUS.md:** Current status
- **src/positions.py:** Coordinate system (753 lines)
- **src/moves.py:** Existing move system
- **tests/test_uat_combat_coordinate_system.py:** Position system tests

---

**Ready to proceed with Phase 3 implementation?**

Estimated timeline: **3 weeks** with comprehensive testing and documentation
