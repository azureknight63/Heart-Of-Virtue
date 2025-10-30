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

**New fields per combatant:**
```python
class CombatPosition:
    x: int              # 0-50
    y: int              # 0-20
    timestamp: int      # beat when position last updated
```

**Updated structures:**
```python
# OLD (keep for backward compatibility initially)
combat_proximity: {unit: distance}

# NEW (coordinate-based)
combat_positions: {unit: CombatPosition}

# Derived calculations (on-demand)
def get_distance(pos1, pos2) -> float:
    return sqrt((pos1.x - pos2.x)² + (pos1.y - pos2.y)²)
```

### 2b. Facing Direction System

**Overview:** Combatants have a **facing direction** (0-360°) or compass direction (N, NE, E, SE, S, SW, W, NW) that determines attack bonuses, accuracy penalties, and interactions with abilities.

#### Facing Direction Specification

```python
class CombatPosition:
    x: int              # 0-50
    y: int              # 0-50
    facing: int         # 0-359 degrees (or enum: N, NE, E, SE, S, SW, W, NW)
    timestamp: int      # beat when position last updated
```

**Direction angles (Cardinal + Diagonal):**
```
      N (0°/360°)
       |
W------+------E
 \     |     /
  \    |    /
   \   |   /
    \  |  /
     \ | /
      \|/
      S (180°)

N: 0°, NE: 45°, E: 90°, SE: 135°, S: 180°, SW: 225°, W: 270°, NW: 315°
```

#### Facing Direction Mechanics

**1. Attack Angle Calculation**
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

**2. Damage & Accuracy Modifiers Based on Angle**
```python
attack_angle_diff = calculate_attack_angle_difference(
    calculate_angle_to_target(attacker.pos, target.pos),
    target.pos.facing
)

# Damage and accuracy scale with angle
if 0 <= attack_angle_diff <= 45:           # Front quarter
    damage_mod = 0.85      # -15% damage
    accuracy_mod = 0.95    # -5% accuracy
elif 45 < attack_angle_diff <= 90:         # Flanking
    damage_mod = 1.15      # +15% damage
    accuracy_mod = 1.10    # +10% accuracy
elif 90 < attack_angle_diff <= 135:        # Deep flank / rear quarter
    damage_mod = 1.25      # +25% damage
    accuracy_mod = 1.20    # +20% accuracy
elif 135 < attack_angle_diff <= 180:       # Rear
    damage_mod = 1.40      # +40% damage
    accuracy_mod = 1.30    # +30% accuracy
```

**Example Scenarios:**
- **Frontal attack (0°):** Enemy facing you = normal damage/accuracy
- **Flanking attack (90°):** Enemy perpendicular to you = +15% damage, +10% accuracy
- **Backstab (180°):** Enemy facing away = +40% damage, +30% accuracy

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

Each combat encounter can specify:
```python
combat_scenario = {
    "type": "standard|pincer|melee|boss_arena|custom",
    "ally_spawn_zone": [(x_min, y_min), (x_max, y_max)],
    "enemy_spawn_zones": [[(x1_min, y1_min), (x1_max, y1_max)], ...],
    "formation_type": "spread|cluster|random",
    "spacing": 2,  # minimum squares between units
    "seed": None  # for reproducible positioning in tests
}
```

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
```python
def distance_from_coords(pos1, pos2) -> int:
    euclidean = sqrt((pos1.x - pos2.x)² + (pos1.y - pos2.y)²)
    return int(euclidean)  # round to feet
```

This allows existing "range 0-5" checks to work naturally:
- Adjacent squares: ~1-2 feet
- 5 squares apart: ~5-7 feet

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
2. **Movement boundaries:** Units can't move outside 50×20 grid
3. **Collision detection:** Two units can't occupy same square (or define stacking rules)
4. **Mid-combat additions:** New enemies spawned by events initialize correctly
5. **Non-square-based abilities:** AOE spells with radius affect by distance, not grid squares
6. **Backward compatibility:** Existing move ranges (melee 0-5, ranged 0-20) still work

### Questions to Resolve
- **Unit collision:** Can two units occupy same tile? Define stacking rules?
- **Diagonal movement:** Is movement 8-directional or 4-directional?
- **Grid visualization:** Should combat UI show a visible grid during battle?
- **Existing abilities:** Do all current moves translate cleanly to coordinate-based ranges?

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
- New move types: Turn, Whirl Attack, Feint & Pivot, Knockback/Stun Spin

**Files Modified (Phase 2):**
- `src/player.py` - Add combat_positions, facing direction
- `src/npc.py` - Add combat_positions, facing direction, spawn preferences
- `src/combat.py` - Update synchronize_distances(), initialize positions/facing
- `src/moves.py` - Update move range checks, add new positioning moves
- `src/positions.py` (new) - Utility module for coordinate math and facing calculations
- `src/states.py` - May add facing-dependent status effects

