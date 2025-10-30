# HV-1: Coordinate-Based Combat Positioning
## Phase 1 Analysis Report

**Date:** October 30, 2025  
**Branch:** `HV-1-coordinate-combat-positioning`  
**Status:** Analysis Phase

---

## Executive Summary

The current combat system uses a **distance-based (1D) positioning model** where combatants track proximity to each other via a dictionary mapping:
```python
combat_proximity = {combatant: distance_in_feet}
```

This limits ability design and creates logical inconsistencies. The goal is to transition to a **coordinate-based (2D) positioning system** that supports more interesting tactical gameplay and ability design.

---

## Terminology & Key Concepts

**Grid Squares:** The new system uses a 50×50 grid of discrete coordinates. Each grid square represents approximately 1 foot of distance in tactical calculations.

**Distance Conversion:** The old system measured distance in feet. The new system stores positions as (x, y) coordinates and converts to distance when needed for move range checks. This maintains backward compatibility.

**Facing Direction:** 8 compass directions (N, NE, E, SE, S, SW, W, NW) representing which direction a combatant is looking. Attacking from different angles (frontal vs flanking vs rear) gives damage/accuracy modifiers.

---

## Current System Architecture

### 1. Data Structures

#### Primary Positioning Dict (1D Distance Model)
Located in:
- `src/player.py:228` - Player initialization
- `src/npc.py:146` - NPC initialization

```python
combat_proximity = {}  # dict: {unit: distance}
default_proximity = 20  # initial distance in feet
```

**Example:**
```python
player.combat_proximity = {
    enemy_a: 15,
    enemy_b: 23,
    ally_a: 8
}
```

#### Related Combat Lists
```python
combat_list: []              # enemies in active combat
combat_list_allies: [player] # player + friendly NPCs
```

### 2. Distance Initialization

**When Combat Starts:**

**File:** `src/npc.py:237-240` (NPC enters combat)
```python
player.combat_proximity[self] = int(self.default_proximity * random.uniform(0.75, 1.25))
for ally in player.combat_list_allies:
    ally.combat_proximity[self] = int(self.default_proximity * random.uniform(0.75, 1.25))
```

**Synchronization:** `src/combat.py:40-77` (every combat beat)
- The `synchronize_distances()` function:
  - Removes dead combatants from all proximity dicts
  - Adds new combatants that appeared mid-combat
  - Maintains bidirectional consistency (if A→B=10, then B→A=10)

### 3. Distance Usage in Moves

#### Target Filtering (Range-Based)
**File:** `src/moves.py:230-231`
```python
for enemy, distance in self.user.combat_proximity.items():
    if range_min <= distance <= range_max:
        enemy_near = True
```

Most move ranges:
- Melee weapons: 0-5 feet
- Ranged weapons: 0-20+ feet

#### Advance Move (Closing Distance)
**File:** `src/moves.py:426-470`
```python
def viable(self):
    if self.target in self.user.combat_proximity:
        distance = self.user.combat_proximity[self.target]
        if distance > 1:  # Only viable if not already close
            return True
```

During execution, reduces distance:
```python
user.combat_proximity[self.target] -= distance_moved
self.target.combat_proximity[user] = user.combat_proximity[self.target]
```

### 4. Key Limitations of 1D Distance Model

| Issue | Impact | Example |
|-------|--------|---------|
| **No directional info** | Abilities can't be directional or positional | AOE abilities can't target "left side" of battlefield |
| **Single distance value** | All combatants equidistant from player | Two enemies at same distance appear identical tactically |
| **No flanking/positioning** | No tactical depth from positioning | Can't implement "attacked from both sides" bonus |
| **No movement simulation** | Distance changes arbitrary | Advance move just decrements distance without spatial logic |
| **Collision/blocking impossible** | No sense of space occupation | Multiple units at same position is undefined |

---

## Code Dependencies

### Files with Direct combat_proximity Usage

#### 1. `src/player.py` (226 lines using combat_proximity)
- **L225-228:** Initialize `combat_list`, `combat_list_allies`, `combat_proximity`
- **L749-758:** Clean up dead enemies from proximity dict
- **L754-758:** Cleanup logic in `cleanup_combat_state()`

#### 2. `src/npc.py` (4 references)
- **L146-148:** Initialize `combat_proximity` and `default_proximity`
- **L237-240:** Initialize distances when entering combat

#### 3. `src/combat.py` (20+ references)
- **L40-77:** `synchronize_distances()` - core maintenance function
  - Cleans dead combatants
  - Ensures bidirectional consistency
  - Initializes new combatants mid-combat
- **L230-231, 426-470, 493-494, 513+:** Move targeting and range checks

#### 4. `src/moves.py` (30+ references)
- **L230-231:** Range-based move targeting
- **L426-432:** `Advance` move viability check (distance > 1)
- **L450-470:** `Advance` move execution (distance reduction)
- **L493-494:** AOE move range checks
- **L513+:** Various other moves use distance checks

### Files with Indirect Impact
- **`src/states.py`:** Status effects could reference distance (check for effects relying on proximity)
- **`src/animations.py`:** Visual rendering might use distance for positioning
- **`src/interface.py`:** Combat UI displays might reference positioning

---

## Proposed Coordinate System Design

### 1. Battlefield Grid Specification

**Grid Type:** 2D Cartesian plane (x, y)  
**Dimensions:** 50×50 squares (width × height)
- x: 0-50 (left to right)
- y: 0-50 (front to back)

**Reasoning:**
- 50×50 provides maximum tactical flexibility for diverse combat scenarios
- Square grid supports all directional movement (cardinal + diagonal)
- Large enough for sophisticated positioning mechanics (flanking, encirclement, etc.)
- Manageable for typical 4-6 combatant encounters while allowing room for additional NPCs
- Can be configured per combat scenario if needed (e.g., arena, hallway, open field)

### 2. Data Structure Extensions

**New CombatPosition class (to be created in `src/positions.py`):**

```python
from dataclasses import dataclass
from enum import Enum

class Direction(Enum):
    """8 compass directions for facing"""
    N = 0      # North (0°)
    NE = 45    # Northeast
    E = 90     # East
    SE = 135   # Southeast
    S = 180    # South
    SW = 225   # Southwest
    W = 270    # West
    NW = 315   # Northwest

@dataclass
class CombatPosition:
    """Represents a combatant's position and facing on the 50×50 battlefield"""
    x: int                           # 0-50, left to right
    y: int                           # 0-50, front to back
    facing: Direction = Direction.N  # Which direction facing (affects attack angles)
```

**Integration:**

Existing structures (maintained for backward compatibility):
```python
# OLD - still used but derived from coordinates
combat_proximity: {unit: distance}

# NEW - source of truth
combat_positions: {unit: CombatPosition}

# Helper function for backward compatibility
def get_distance(pos1: CombatPosition, pos2: CombatPosition) -> int:
    """Convert coordinates to distance in feet"""
    dx = pos1.x - pos2.x
    dy = pos1.y - pos2.y
    return int(sqrt(dx² + dy²))
```

**Added to Player and NPC classes:**
```python
class Player:
    combat_position: Optional[CombatPosition] = None  # None outside combat
    # ... existing fields remain ...

class NPC:
    combat_position: Optional[CombatPosition] = None  # None outside combat
    # ... existing fields remain ...
```

### 2b. Facing Direction System

**Overview:** Combatants have a **facing direction** (8 compass directions: N, NE, E, SE, S, SW, W, NW) that determines attack bonuses, accuracy penalties, and interactions with abilities.

*Note: Initial implementation uses 8 discrete directions (simpler) rather than continuous 360° angles. Smooth rotation can be added later if needed.*

#### Facing Direction Mechanics

The facing direction is stored in `CombatPosition.facing` and is used to calculate attack angle advantages.
When an attacker at position A1 attacks a target at position T1:
```python
def calculate_angle_to_target(attacker_pos, target_pos) -> int:
    """Calculate angle from attacker to target (0-359°)"""
    dx = target_pos.x - attacker_pos.x
    dy = target_pos.y - attacker_pos.y
    angle = atan2(dy, dx) * 180 / π
    return angle % 360

def calculate_attack_angle_difference(attack_angle, target_facing) -> int:
    """How many degrees is the attack from the target's facing direction?
    0° = frontal (target facing attacker)
    180° = rear (target facing away)
    90° or 270° = flanking
    """
    diff = abs(attack_angle - target_facing)
    if diff > 180:
        diff = 360 - diff
    return diff  # 0-180°
```

**2. Damage & Accuracy Modifiers Based on Attack Angle**

The attack angle difference (0-180°) determines how much damage and accuracy the attacker gets/loses:

```python
attack_angle_diff = calculate_attack_angle_difference(
    calculate_angle_to_target(attacker.pos, target.pos),
    target.pos.facing
)

# Modifier tiers based on angle difference
if 0 <= attack_angle_diff <= 45:           # Front quarter
    damage_multiplier = 0.85      # -15% damage (defended position)
    accuracy_multiplier = 0.95    # -5% accuracy (target can see you)
elif 45 < attack_angle_diff <= 90:         # Flanking
    damage_multiplier = 1.15      # +15% damage (partial defense)
    accuracy_multiplier = 1.10    # +10% accuracy (harder to defend)
elif 90 < attack_angle_diff <= 135:        # Deep flank / rear quarter
    damage_multiplier = 1.25      # +25% damage (mostly vulnerable)
    accuracy_multiplier = 1.20    # +20% accuracy (very hard to defend)
elif 135 < attack_angle_diff <= 180:       # Rear/Backstab
    damage_multiplier = 1.40      # +40% damage (no defense possible)
    accuracy_multiplier = 1.30    # +30% accuracy (guaranteed hit essentially)

# Apply modifiers to final damage calculation
final_damage = base_damage * damage_multiplier
final_accuracy = base_accuracy * accuracy_multiplier
```

**Application Examples:**
- Frontal attack (0°): Normal combat, target can defend
- Flanking attack (90°): Target's shield/armor less effective, +15% damage
- Backstab (180°): Target unaware, +40% damage, +30% accuracy
- Diagonal rear (135°): Deep vulnerability, +25% damage

#### Facing Direction Abilities

**Passive Abilities:**
- "Situational Awareness" - reduce flanking/backstab penalty by 50%
- "Defensive Stance" - front damage modifier becomes 0.95 (reduce penalty)
- "Glass Cannon" - backstab damage increased to +60% but frontal damage increased to -30%

**Active Abilities (new move types):**

1. **"Turn" Move** - Player can spend a beat to rotate facing direction
   ```python
   class Turn(Move):
       def execute(self, user):
           """Rotate to face a selected direction or target"""
           # Prompt player to select facing direction
           new_facing = player_select_facing()
           user.combat_position.facing = new_facing
           print(f"{user.name} turned to face {direction_name(new_facing)}")
   ```
   - Cost: 1-2 beats
   - Fatigue: Low
   - Strategic use: Prevent backstabs, prepare for incoming attack

2. **"Whirl Attack" / "Spin Strike"** - Damages nearby enemies while rotating
   ```python
   class WhirlAttack(Move):
       def execute(self, user):
           """Attack all nearby enemies while rotating facing"""
           for enemy in get_nearby_enemies(user, radius=5):
               self.damage_target(enemy)
           # Randomly rotate facing to a new direction
           user.combat_position.facing = random_facing()
   ```
   - Cost: 3-4 beats
   - Fatigue: Medium-High
   - Effect: Hits multiple enemies, unpredictable facing after

3. **"Feint & Pivot"** - Attack from front while repositioning behind target
   ```python
   class FeintAndPivot(Move):
       def execute(self, user, target):
           """Attack target, then reposition behind them"""
           # Attack from current position
           self.damage_target(target)
           # Move to position behind target (180° from target's current facing)
           behind_pos = calculate_position_behind(target, distance=2)
           user.combat_position.x = behind_pos.x
           user.combat_position.y = behind_pos.y
           # Face the same direction as target (to make backstab on their turn impossible)
           user.combat_position.facing = target.combat_position.facing
   ```
   - Cost: 4-5 beats
   - Fatigue: High
   - Effect: Strong positioning ability, high skill requirement

4. **"Knockback/Stun Spin"** - Powerful attack that forces target to turn away
   ```python
   class StunSpin(Move):
       def execute(self, user, target):
           """Attack target with knockback effect that rotates their facing"""
           damage = self.calculate_damage(user)
           target.take_damage(damage)
           
           # Rotate target's facing away from attacker (180° flip)
           angle_to_attacker = calculate_angle_to_target(target.pos, user.pos)
           new_facing = (angle_to_attacker + 180) % 360
           target.combat_position.facing = new_facing
           
           print(f"{target.name} was spun around!")
   ```
   - Cost: 3-4 beats
   - Fatigue: Medium-High
   - Effect: Stun + facing change
   - Status effect: "Disoriented" (duration 2-3 beats)

#### Enemy AI Integration

**NPC Decision Making:**
```python
def npc_select_move(enemy):
    """NPC AI considers facing direction when choosing moves"""
    
    # Assess current situation
    threats = get_attacking_enemies(enemy)
    threats_behind = [t for t in threats if is_behind(t, enemy)]
    threats_front = [t for t in threats if not is_behind(t, enemy)]
    
    # Decision logic
    if len(threats_behind) > 0 and threats_behind_count > 1:
        # Multiple enemies behind = use Turn move
        return Turn(target_direction="towards_main_threat")
    elif threats_behind_count == 1:
        # Single threat behind = consider Whirl Attack
        if enemy.fatigue > 50:
            return WhirlAttack()
    elif threats_front_count > 2:
        # Surrounded = try to escape or repositioning move
        return Retreat()
    else:
        # Normal attack conditions
        return standard_attack_selection()
```

**Boss Behavior:**
- Bosses use "Turn" strategically to force players into suboptimal positioning
- Some bosses may have "Intimidating Presence" - enemies in front take more damage penalty
- Unique bosses could have special moves that require understanding facing (e.g., "only vulnerable to backstabs")

#### Facing Direction Persistence & Rules

**Initial Facing:**
- On combat start, all units face toward nearest enemy
  - Allies face toward enemy team center
  - Enemies face toward player/ally team center
- Player can specify initial facing direction preference

**Facing Direction Changes:**
- Changes when using "Turn" move
- Changes as side effect of certain attacks (knockback, stun spin)
- Changes via status effects ("Disoriented", "Confused")
- Does **NOT** automatically change when moving with "Advance" move (intentional - requires explicit "Turn" action)

**Edge Cases:**
- Units can have 8 discrete directions (N, NE, E, SE, S, SW, W, NW) or smooth 360° rotation
  - Discrete is simpler for initial implementation
  - Smooth enables more complex calculation later
- What happens if a unit is moved by an ability? Does facing change?
  - **Rule:** Facing only changes explicitly via Turn move or ability side effect, not via movement

### 2c. Combat Movement System

#### Overview

The new coordinate-based movement system supports both **basic movement moves** (available to all combatants by default) and **advanced movement skills** (unlocked through progression). This creates a skill-based movement hierarchy where veteran fighters and intelligent enemies have sophisticated tactical movement options unavailable to novices.

#### Basic Movement Moves (Always Available)

All combatants start with access to two fundamental movement moves:

**1. Advance (Toward Designated Target)**
```python
class Advance(Move):
    """Move toward a specified enemy target"""
    
    def viable(self):
        """Can only advance if target exists and distance > 1"""
        if not self.target or self.target not in self.user.combat_proximity:
            return False
        distance = self.user.combat_proximity[self.target]
        return distance > 1  # Already adjacent
    
    def execute(self, user, target):
        """Move up to 2 grid squares toward target"""
        current_pos = user.combat_position
        target_pos = target.combat_position
        
        # Calculate direction toward target (normalized to -1, 0, or 1)
        dx = sign(target_pos.x - current_pos.x)
        dy = sign(target_pos.y - current_pos.y)
        
        # Move 2 squares in that direction
        # Note: grid squares are equivalent to ~1 foot each
        movement_distance = 2
        new_x = current_pos.x + (dx * movement_distance)
        new_y = current_pos.y + (dy * movement_distance)
        
        # Clamp to grid bounds
        new_x = clamp(new_x, 0, 50)
        new_y = clamp(new_y, 0, 50)
        
        # Update position
        user.combat_position.x = new_x
        user.combat_position.y = new_y
        
        # Recalculate distances for proximity dict
        recalculate_proximity(user, all_combatants)
        
        print(f"{user.name} advanced toward {target.name}!")
```

**Costs:**
- Beats: 1-2 beats
- Fatigue: 5-10 (low cost, frequent use)
- Status: Can be interrupted if user is controlled/stunned

**Behavior:**
- Moves in straight line toward target (moving diagonally if target is diagonal)
- **Collision handling:** If blocked by another unit, move fails silently (player can try different target)
- Cannot pass through other units; stops at last valid position before collision
- Updates all distance calculations for proximity-based move eligibility

**2. Withdraw (Away from Nearest Enemy)**
```python
class Withdraw(Move):
    """Move away from nearest enemy"""
    
    def viable(self):
        """Always viable if at least one enemy exists and distance < 40"""
        if not self.user.combat_proximity:
            return False
        nearest_distance = min(self.user.combat_proximity.values())
        return nearest_distance < 40  # Only viable if not already far away
    
    def execute(self, user):
        """Move 2-3 squares away from nearest enemy"""
        # Find nearest enemy
        nearest_enemy = min(
            user.combat_proximity.keys(),
            key=lambda e: user.combat_proximity[e]
        )
        
        current_pos = user.combat_position
        enemy_pos = nearest_enemy.combat_position
        
        # Calculate direction away from nearest enemy
        dx = sign(current_pos.x - enemy_pos.x)
        dy = sign(current_pos.y - enemy_pos.y)
        
        # Move 2 squares
        squares_moved = 2
        new_x = current_pos.x + (dx * squares_moved)
        new_y = current_pos.y + (dy * squares_moved)
        
        # Clamp to grid bounds
        new_x = clamp(new_x, 0, 50)
        new_y = clamp(new_y, 0, 50)
        
        # Update position
        user.combat_position.x = new_x
        user.combat_position.y = new_y
        
        # Recalculate distances
        recalculate_proximity(user, all_combatants)
        
        print(f"{user.name} withdrew from combat!")
```

**Costs:**
- Beats: 1-2 beats
- Fatigue: 5-10 (same as Advance)
- Status: Can be used defensively or tactically

**Behavior:**
- Moves away from nearest enemy (most immediate threat)
- Good for escaping melee, regrouping, or repositioning
- Cannot pass through other units (stop if blocked)

#### Advanced Movement Skills (Skill-Unlocked)

As combatants gain experience and unlock movement skills, they gain access to sophisticated tactical movement:

**Tier 1 (Novice Skills) - Learned Early**

**1. Rush / Bull Charge**
```python
class BullCharge(Move):
    """Charge toward enemy with increased damage on next attack"""
    
    def viable(self):
        if not self.target or self.target not in self.user.combat_proximity:
            return False
        distance = self.user.combat_proximity[self.target]
        return distance > 5  # Only viable from distance
    
    def execute(self, user, target):
        """Move 4-6 squares toward target with momentum bonus"""
        # Move more squares than basic Advance
        current_pos = user.combat_position
        target_pos = target.combat_position
        
        dx = sign(target_pos.x - current_pos.x)
        dy = sign(target_pos.y - current_pos.y)
        
        squares_moved = 5  # More movement than Advance
        new_x = clamp(current_pos.x + (dx * squares_moved), 0, 50)
        new_y = clamp(current_pos.y + (dy * squares_moved), 0, 50)
        
        user.combat_position.x = new_x
        user.combat_position.y = new_y
        
        # Apply momentum bonus (next attack +20% damage)
        user.apply_status_effect("Momentum", duration=2_beats)
        
        print(f"{user.name} charged toward {target.name}!")
```

**Costs:** Beats: 2-3, Fatigue: 15-20  
**Unlock:** Unlocked after ~5 combat encounters or via "Charge" skill tome

**2. Kiting / Tactical Retreat**
```python
class TacticalRetreat(Move):
    """Move away while maintaining angle to continue attacking"""
    
    def viable(self):
        # Must have ranged weapon or ranged ability
        has_ranged = (
            hasattr(self.user, 'eq_weapon') and
            hasattr(self.user.eq_weapon, 'range') and
            self.user.eq_weapon.range > 5
        )
        return has_ranged and len(self.user.combat_proximity) > 0
    
    def execute(self, user):
        """Move away while facing target (maintain kiting angle)"""
        # Move away from nearest enemy
        nearest = min(
            user.combat_proximity.keys(),
            key=lambda e: user.combat_proximity[e]
        )
        
        current_pos = user.combat_position
        enemy_pos = nearest.combat_position
        
        # Calculate perpendicular movement (kiting circle)
        # Move away but also sideways to maintain angle
        angle = atan2(current_pos.y - enemy_pos.y, current_pos.x - enemy_pos.x)
        perp_angle = angle + π/2  # 90° perpendicular
        
        move_dist = 2
        new_x = clamp(current_pos.x + cos(perp_angle) * move_dist, 0, 50)
        new_y = clamp(current_pos.y + sin(perp_angle) * move_dist, 0, 50)
        
        user.combat_position.x = new_x
        user.combat_position.y = new_y
        
        # Face the enemy (for kiting angle advantage)
        user.combat_position.facing = calculate_angle_to_target(
            user.combat_position, enemy_pos
        )
        
        print(f"{user.name} kited away from {nearest.name}!")
```

**Costs:** Beats: 2-3, Fatigue: 15-20  
**Unlock:** Requires ranged weapon proficiency + "Kiting" skill tome

**Tier 2 (Intermediate Skills) - Learned Later**

**3. Flanking Maneuver**
```python
class FlankingManeuver(Move):
    """Move to side of enemy for tactical advantage"""
    
    def viable(self):
        if not self.target or self.target not in self.user.combat_proximity:
            return False
        distance = self.user.combat_proximity[self.target]
        return 2 <= distance <= 20  # Works at mid-range
    
    def execute(self, user, target):
        """Move to perpendicular position (90° from target's facing)"""
        current_pos = user.combat_position
        target_pos = target.combat_position
        target_facing = target.combat_position.facing
        
        # Calculate 90° perpendicular position
        perp_angle = target_facing + π/2  # 90° to the side
        distance_from_target = 3
        
        new_x = clamp(
            target_pos.x + cos(perp_angle) * distance_from_target, 0, 50
        )
        new_y = clamp(
            target_pos.y + sin(perp_angle) * distance_from_target, 0, 50
        )
        
        user.combat_position.x = new_x
        user.combat_position.y = new_y
        
        # Face the target
        user.combat_position.facing = calculate_angle_to_target(
            user.combat_position, target_pos
        )
        
        # Apply flanking bonus (next attack +20% damage)
        user.apply_status_effect("Flanking_Position", duration=2_beats)
        
        print(f"{user.name} maneuvered to flank {target.name}!")
```

**Costs:** Beats: 2-3, Fatigue: 20-25  
**Unlock:** Requires intermediate combat skill + "Flanking" skill book

**4. Repositioning (Swap Position with Ally)**
```python
class QuickSwap(Move):
    """Swap positions with nearby ally for tactical repositioning"""
    
    def viable(self):
        nearby_allies = [
            ally for ally in self.user.party
            if distance_between(
                self.user.combat_position,
                ally.combat_position
            ) <= 4 and ally != self.user
        ]
        return len(nearby_allies) > 0
    
    def execute(self, user, target_ally):
        """Exchange positions with selected ally"""
        temp_pos = (user.combat_position.x, user.combat_position.y)
        user.combat_position.x = target_ally.combat_position.x
        user.combat_position.y = target_ally.combat_position.y
        
        target_ally.combat_position.x = temp_pos[0]
        target_ally.combat_position.y = temp_pos[1]
        
        # Recalculate all distances
        recalculate_proximity(user, all_combatants)
        recalculate_proximity(target_ally, all_combatants)
        
        print(f"{user.name} and {target_ally.name} switched positions!")
```

**Costs:** Beats: 1-2, Fatigue: 10-15  
**Unlock:** Requires ally in combat + "Coordination" skill

**Tier 3 (Advanced Skills) - High-Level Play**

**5. Dimensional Shift / Teleport**
```python
class DimensionalShift(Move):
    """Teleport to specified coordinate within range"""
    
    def viable(self):
        # High-level ability
        return self.user.level >= 20 and "Dimensional_Shift" in self.user.unlocked_skills
    
    def execute(self, user):
        """Player selects destination within 8 square range"""
        destination = player_select_coordinate(
            max_distance=8,
            current_pos=user.combat_position
        )
        
        user.combat_position.x = destination.x
        user.combat_position.y = destination.y
        
        # Can choose new facing direction
        user.combat_position.facing = player_select_facing()
        
        # Recalculate distances
        recalculate_proximity(user, all_combatants)
        
        print(f"{user.name} disappeared and reappeared at coordinates!")
```

**Costs:** Beats: 3-4, Fatigue: 40-50  
**Unlock:** Level 20+ with rare "Spatial Magic" tome or boss drops

**6. Combat Dance / Evasion Choreography**
```python
class CombatDance(Move):
    """Chain rapid repositioning moves in sequence"""
    
    def viable(self):
        return "Combat_Dance" in self.user.unlocked_skills and self.user.endurance >= 50
    
    def execute(self, user):
        """Execute 3 sequential micro-movements"""
        for _ in range(3):
            # Each micro-movement: move 1-2 squares in random direction
            angle = random() * 2 * π
            dx = cos(angle) * random_int(1, 2)
            dy = sin(angle) * random_int(1, 2)
            
            user.combat_position.x = clamp(user.combat_position.x + dx, 0, 50)
            user.combat_position.y = clamp(user.combat_position.y + dy, 0, 50)
        
        # Gain evasion bonus for several beats (hard to target while dancing)
        user.apply_status_effect("Evasion_Bonus", duration=3_beats, bonus=20)
        
        print(f"{user.name} executed a combat dance, becoming harder to hit!")
```

**Costs:** Beats: 4-5, Fatigue: 50  
**Unlock:** Dexterity 50+ + "Dance" skill tome

#### Enemy AI Movement Selection

**Low-level Enemies (Level 1-5):**
- Only have access to: Advance, Withdraw
- Decision logic:
  ```python
  if distance_to_player < 5:
      use_move(Advance, target=player)
  elif distance_to_player > 20 or health_low:
      use_move(Withdraw)
  else:
      use_basic_attack()
  ```

**Intermediate Enemies (Level 6-15):**
- Unlock: Bull Charge, Tactical Retreat, Flanking Maneuver
- Decision logic considers:
  - Health status (withdraw if < 30% HP)
  - Number of allies nearby (group tactics)
  - Player positioning (flank if possible)
  - Ranged weapon availability (kite if ranged)

**High-level / Intelligent Enemies (Level 16+, Boss):**
- Access to: All movement skills + custom variations
- Advanced tactics:
  - Coordinate flanking attacks with allies
  - Use Repositioning to swap defensive positions
  - Chain movement skills across multiple turns
  - Boss-specific movement abilities (Dimensional Shift for final bosses)

#### Movement Constraints & Balance

**Grid Collision:**
- Units cannot occupy the same coordinate
- If blocked by another unit, movement move fails (can try different target direction)
- Consider queue system: if multiple units try to occupy same tile, resolve conflicts with priority (higher initiative wins?)

**Movement Speed Scaling:**
- Speed stat affects beat cost of movement moves
- Formula: `adjusted_beats = base_beats * (1 - speed_bonus%)`
- Example: Speed 120 → 20% faster movement

**Stamina/Fatigue System:**
- Movement moves cost fatigue
- Low fatigue limits available movement options
- At 0 fatigue, only Advance/Withdraw available (cannot afford advanced moves)

**Special Cases:**
- Immobilized/Paralyzed status: Cannot use any movement move
- Slowed status: Movement costs +50% beats, -50% distance moved
- Haste status: Movement costs -25% beats, +25% distance moved
- "Rooted" status: Can still Turn, but cannot move positions (only Advance/Withdraw fail)

### 3. Position Initialization Strategy

#### Default Positioning
**At combat start (standard encounter):**
1. Create a 50×50 grid
2. Player + allies spawn near: **(15, 25)** - left-center area
3. First enemy spawns near: **(35, 25)** - right-center area (mirrored from allies)
4. Additional enemies/allies form loose groups around their team's starting position

**Example 3-enemy layout (default melee formation):**
```
        0                              50
    0   . . . . . . . . . . . . . . . .
   10   . . . . . . . . . . . . . . . .
   20   . . . . . . . . . . . . . . . .
   25   P . . . . . . . . . . . E . . .
   30   . . . . . . . . . . . . . . . .
   40   . . . . . . . . . . . . . . . .
   50   . . . . . . . . . . . . . . . .

P = Player + allies (cluster around 15, 25)
E = Enemies (cluster around 35, 25)
```

#### Configurable Combat Scenarios

The positioning system supports **scenario-based initialization** for varied tactical situations:

**Standard Formation (Default)**
- Allies near (15, 25), enemies near (35, 25)
- Expected: 1v1 or small group combat
- Distance: ~20 squares (~20 feet) - good for ranged engagement

**Pincer Attack (Ambush)**
- Player team spawns center: (25, 25)
- Enemy team split left and right:
  - Left flank: (10, 15)
  - Right flank: (10, 35)
- Expected: Surrounded scenario, tactical retreat or central defense
- Difficulty modifier: +20% enemy damage or +1 enemy level

```
   15   E . . . . . . . . . . . . . . E
   25   . . . . . P . . . . . . . . . .
   35   E . . . . . . . . . . . . . . E
```

**Melee (Chaos)**
- All units spawn randomly across the entire 50×50 grid
- Minimum distance constraints: no two units spawn adjacent
- Expected: Chaotic, non-standard positioning
- Encourages movement and tactical repositioning

**Boss Arena (Centered)**
- Single boss spawns center: (25, 25)
- Player team spawns front: (25, 10)
- Expected: Linear approach to single powerful enemy
- Supports boss-specific positioning mechanics

**Formation vs Cluster**
- **Formation scenario:** Units spread in lines/rows for tactical advantage
  - Example: "Shield wall" formation with 3-4 unit spacing
- **Cluster scenario:** Units spawn close together for mutual support
  - Example: Bandits who travel together, spawn within 2-3 squares

#### Combat Scenario Specification

Each combat encounter specifies how units spawn. Scenarios are defined in map JSON or combat events:

```python
combat_scenario = {
    "type": "standard|pincer|melee|boss_arena|custom",
    
    # Spawn zones: [(x_min, y_min), (x_max, y_max)]
    "ally_spawn_zone": [(10, 15), (20, 35)],    # Rectangular area for allies to spawn in
    "enemy_spawn_zones": [                       # Can have multiple zones (for split formations)
        [(35, 15), (45, 35)],                    # Primary enemy zone
        [(5, 5), (15, 10)]                       # Optional secondary zone (ambush)
    ],
    
    # How units are arranged within their zone
    "formation_type": "spread|cluster|random",
    "spacing": 2,                                # Minimum squares between units (for collision avoidance)
    "seed": None                                 # For reproducible positioning in tests/debugging
}
```

**How Scenarios are Used:**
1. Combat initiates with scenario type (default: "standard")
2. Allies randomly spawn within `ally_spawn_zone`
3. Enemies randomly spawn within `enemy_spawn_zones`
4. `formation_type` affects spacing (spread = 4-5 square gaps, cluster = 1-2 square gaps)
5. Individual NPC `spawn_preference` can override general formation logic

#### NPC & Enemy Preferences

Individual NPCs/enemies can have spawning preferences:

```python
class NPC:
    # New attributes for positioning
    spawn_preference = "alone|cluster|formation"  # AI spawning preference
    formation_role = "leader|flanker|support|independent"
    preferred_distance = 20  # feet (converted to ~squares at spawn)
```

**Examples:**
- **Lone Wolf (bandit leader):** `spawn_preference="alone"` - spawns separated from other bandits
- **Shield Bearer (guard):** `spawn_preference="cluster"` - stays grouped with allies
- **Archer (tactical):** `spawn_preference="formation"` - takes position in organized line
- **Boss (Unique):** `spawn_preference="independent"` - center arena positioning

#### Player/Ally Passive & Active Abilities

The coordinate system enables ability interactions with positioning:

**Passive abilities:**
- "Tactical Advantage" - allies gain +5% accuracy if all spawn within 5 squares
- "Leader's Aura" - enemies nearby player must spend extra turn to move away
- "Ambush Specialist" - if player encounters pincer attack, first attack gain +25% damage

**Active abilities (during combat):**
- "Rally" - reposition allies to tighter formation (+defense, -mobility)
- "Scatter" - spread allies out (-density, +individual evasion)
- "Flanking Maneuver" - move allies to specific coordinates for tactical bonus

#### Combat Initialization in Code

```python
# Pseudocode structure
def initialize_combat_positions(player, enemies, scenario="standard"):
    grid = CombatGrid(50, 50)
    
    # Get scenario config
    config = COMBAT_SCENARIOS.get(scenario, COMBAT_SCENARIOS["standard"])
    
    # Spawn allies
    for ally in player.combat_list_allies:
        if hasattr(ally, 'spawn_preference'):
            pos = calculate_spawn_with_preference(
                ally, 
                config['ally_spawn_zone'],
                player.combat_list_allies,
                config['formation_type']
            )
        else:
            pos = random_position_in_zone(config['ally_spawn_zone'])
        grid.place_unit(ally, pos)
    
    # Spawn enemies
    for i, enemy in enumerate(enemies):
        zone = config['enemy_spawn_zones'][i % len(config['enemy_spawn_zones'])]
        if hasattr(enemy, 'spawn_preference'):
            pos = calculate_spawn_with_preference(
                enemy,
                zone,
                enemies,
                config['formation_type']
            )
        else:
            pos = random_position_in_zone(zone)
        grid.place_unit(enemy, pos)
    
    return grid
```

### 4. Distance Calculation

**From coordinates to distance (for backward compatibility):**

The coordinate system uses **grid squares** as the primary unit. For compatibility with the old distance-based move ranges (melee 0-5 feet, ranged 0-20+ feet), we need to convert coordinates to distance:

```python
def distance_from_coords(pos1: CombatPosition, pos2: CombatPosition) -> int:
    """
    Calculate Euclidean distance between two positions in feet.
    Each grid square ≈ 1 foot for combat purposes.
    """
    dx = pos1.x - pos2.x
    dy = pos1.y - pos2.y
    euclidean_distance = sqrt(dx² + dy²)
    return int(euclidean_distance)  # round to nearest foot
```

**Distance Ranges (Converted from Grid Squares):**
- Adjacent/Melee: 0-3 feet (touching, very close)
- Sword/Axe range: 0-5 feet (1-2 squares away)
- Bow/Magic range: 0-20 feet (3-7 squares away)
- Distant ranged: 0-40+ feet (8+ squares away)

**Note on terminology:**
- The old system used "feet" as distance units
- The new system uses grid coordinates (0-50 x, 0-50 y)
- Distance calculation converts coordinates back to feet for backward compatibility
- Existing move range checks (e.g., "range 0-5 feet") will work transparently

---

## Migration Strategy (Multi-Phase)

### Phase 1 (Current): Analysis ✓
- [x] Identify all distance-based code
- [x] Document limitations and use cases
- [x] Design new coordinate system

### Phase 2: Core Implementation
- Add coordinate fields to Player and NPC
- Initialize positions at combat start
- Create distance utility functions
- Update `synchronize_distances()` to handle coordinates

### Phase 3: Gradual Refactoring
- Refactor moves one at a time to use coordinates
- Maintain backward compatibility (distance dict still populated)
- Add new coordinate-aware abilities

### Phase 4: Cleanup & Validation
- Remove distance-only code paths
- Comprehensive testing
- Verify edge cases and special scenarios

---

## Edge Cases & Constraints

### Must-Handle Scenarios
1. **Combat spawn consistency:** Same enemy types/counts always spawn predictably
2. **Movement boundaries:** Units can't move outside 50×50 grid
3. **Collision detection:** Two units can't occupy same square (or define stacking rules)
4. **Mid-combat additions:** New enemies spawned by events initialize correctly
5. **Non-square-based abilities:** AOE spells with radius affect by distance, not grid squares
6. **Backward compatibility:** Existing move ranges (melee 0-5, ranged 0-20) still work

### Design Decisions (Finalized)

- **Unit collision:** No stacking - two units cannot occupy the same coordinate
- **Movement directions:** 8-directional (cardinal + diagonal) for maximum tactical flexibility
- **Grid visualization:** Combat UI will show relevant positioning info; full grid view optional via player preference or "Battlefield Awareness" skill
- **Existing abilities:** All current moves will work; ranges translate cleanly from feet to grid squares

---

## Risk Assessment

| Risk | Likelihood | Severity | Mitigation |
|------|------------|----------|-----------|
| Combat becomes unbalanced | Medium | High | Maintain same distance ranges initially |
| Movement feels artificial | Medium | Medium | Test move feel, iterate grid size |
| Test failures post-refactor | High | Medium | Comprehensive unit tests before phase 3 |
| Circular dependencies | Low | High | Careful import structure in new modules |
| Performance degradation | Low | Low | Profile coordinate calculations vs distance |

---

## Next Steps

1. **Immediate (Phase 2 prep):**
   - Design `CombatPosition` class structure
   - Create utility module for coordinate math
   - Plan initialization logic

2. **Phase 2 begins:**
   - Add coordinate tracking to `src/player.py` and `src/npc.py`
   - Implement position initialization in combat start
   - Update `synchronize_distances()` function

3. **Validation:**
   - Create test suite for coordinate system
   - Verify distance calculations match old system
   - Test all move types with new positions

---

## References

**Related Jira Issue:** HV-1  
**Epic:** HV-7 (Demo 1 - One-Hour Vertical Slice)  

**Key Features Implemented:**
- Coordinate-based (x, y) positioning system on 50×50 grid
- Facing direction (8 compass directions) with attack angle calculations
- Configurable combat scenarios (standard, pincer, melee, boss arena, custom)
- NPC spawn preferences and formation behaviors
- Player/ally passive and active positioning abilities
- Facing-dependent damage/accuracy modifiers (frontal, flank, backstab)
- New positioning move types: Turn, Whirl Attack, Feint & Pivot, Knockback/Stun Spin
- **Skill-gated movement system:**
  - Basic moves (Advance, Withdraw) available to all
  - Tier 1 skills (Bull Charge, Tactical Retreat, Flanking)
  - Tier 2 skills (Repositioning, Quick Swap)
  - Tier 3 skills (Dimensional Shift, Combat Dance)
  - Level/intelligence-based NPC movement AI
- Movement constraints (collision, stamina scaling, status effects)

**Files Modified (Phase 2):**
- `src/player.py` - Add combat_positions, facing direction, movement skills
- `src/npc.py` - Add combat_positions, facing direction, spawn preferences, AI movement selection
- `src/combat.py` - Update synchronize_distances(), initialize positions/facing, handle collision
- `src/moves.py` - Refactor Advance/Withdraw, add new movement skills (Bull Charge, Tactical Retreat, etc.)
- `src/positions.py` (new) - Utility module for coordinate math, angle calculations, distance functions
- `src/states.py` - May add facing-dependent and movement-dependent status effects
- `src/skilltree.py` - Integrate movement skill progression

