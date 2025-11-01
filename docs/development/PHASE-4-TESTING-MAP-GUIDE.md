# Phase 4 Testing Map Configuration Guide

**Version:** Phase 4 Ready  
**Date Created:** October 30, 2025  
**Map File:** `src/resources/maps/testing-map.json`  

---

## Overview

The testing map (`testing-map.json`) is the primary environment for Phase 4 manual combat testing. This guide explains how to set up combat scenarios, configure NPCs, and validate the coordinate-based positioning system.

---

## Map Structure

The testing map is a JSON file containing tile definitions. Each tile supports:

```json
{
  "(x, y)": {
    "id": "tile_id",
    "title": "Tile Title",
    "description": "Narrative description",
    "exits": ["north", "south", "east", "west"],
    "events": [],
    "items": [],
    "npcs": []
  }
}
```

**Key Components:**
- **Coordinates:** `(x, y)` format, 0-50 range
- **Exits:** Directional movement options (north, south, east, west, northeast, etc.)
- **Items:** Consumables, weapons, armor (JSON serialized)
- **NPCs:** Enemies for combat encounters
- **Events:** Tile-based events that trigger on entry

---

## Testing Locations for Phase 4

### Location A: Standard Formation Arena

**Tile Coordinates:** (25, 5) to (25, 45)  
**Purpose:** Test standard line vs line combat scenario  
**Setup:**

1. Create/update tile at (25, 25) - **Central Arena**
   - Clear, open space
   - Description: "A wide open arena suitable for lined-up combat."
   - Exits: Multiple directions for NPC spawning
   - Place 3-4 standard NPCs here

2. Player starts at (25, 15)
3. Enemies spawn at (25, 35)

**Test Objectives:**
- Verify standard scenario initialization ✅
- Test Advance/Withdraw moves ✅
- Validate distance calculations ✅
- Check damage modifiers (frontal) ✅

---

### Location B: Pincer Ambush Arena

**Tile Coordinates:** (20, 20) to (30, 30)  
**Purpose:** Test flanking and ambush scenarios  
**Setup:**

1. Create/update tile at (25, 25) - **Ambush Zone**
   - Description: "A confined area with multiple passages."
   - Exits: north, south, east, west (for flanking approach)
   - Place 4-5 enemies around player

2. Player starts at (25, 25) - surrounded
3. Enemies at: (15, 25), (35, 25), (25, 15), (25, 35)

**Test Objectives:**
- Verify pincer scenario initialization ✅
- Test FlankingManeuver effectiveness ✅
- Test TacticalRetreat with multiple threats ✅
- Validate flanking damage modifiers (+15-40%) ✅

---

### Location C: Melee Brawl Zone

**Tile Coordinates:** (22, 22) to (28, 28)  
**Purpose:** Test close-quarters chaotic combat  
**Setup:**

1. Create/update tile at (25, 25) - **Melee Center**
   - Description: "A tight confusing space with scattered obstacles."
   - Multiple NPCs in close proximity
   - Place 5-6 enemies in tight formation

2. Player starts at (25, 25) - mixed in with enemies
3. Enemies scattered within 2-3 square radius

**Test Objectives:**
- Test high-density positioning ✅
- Verify movement options in confined space ✅
- Test flanking from multiple angles ✅
- Validate deep flank damage (1.25x) ✅

---

### Location D: Boss Arena

**Tile Coordinates:** (10, 10) to (40, 40)  
**Purpose:** Test 1v1 combat with powerful single enemy  
**Setup:**

1. Create/update tile at (25, 25) - **Boss Arena**
   - Description: "An expansive coliseum with plenty of space."
   - Exits: none (trapped arena)
   - Place 1 powerful boss NPC

2. Player starts at (25, 10)
3. Boss spawns at (25, 40)
4. Large initial distance (~30 squares)

**Test Objectives:**
- Test long-range positioning ✅
- Verify BullCharge effectiveness ✅
- Test sustained damage/accuracy calculations ✅
- Validate all move types in 1v1 scenario ✅

---

## NPC Configuration for Testing

### Standard Enemy Types

**Type A: Weak Melee Fighter**
```json
{
  "__class__": "some_melee_npc",
  "name": "Weak Goblin",
  "maxhp": 15,
  "hp": 15,
  "attack_power": 5,
  "defense": 2,
  "speed": 3
}
```
**Use Case:** Standard formation, melee scenario

**Type B: Flanking Specialist**
```json
{
  "__class__": "some_ranged_npc",
  "name": "Archer Scout",
  "maxhp": 12,
  "hp": 12,
  "attack_power": 7,
  "defense": 1,
  "speed": 5
}
```
**Use Case:** Pincer scenario, flanking tests

**Type C: Tough Tank**
```json
{
  "__class__": "some_tank_npc",
  "name": "Armored Knight",
  "maxhp": 40,
  "hp": 40,
  "attack_power": 8,
  "defense": 5,
  "speed": 2
}
```
**Use Case:** Melee scenario, boss arena (solo)

**Type D: Boss Enemy**
```json
{
  "__class__": "some_boss_npc",
  "name": "Master Necromancer",
  "maxhp": 100,
  "hp": 100,
  "attack_power": 15,
  "defense": 8,
  "speed": 4,
  "special_abilities": ["flanking_attack", "tactical_retreat"]
}
```
**Use Case:** Boss arena solo combat

---

## Setting Up Combat Encounters

### Manual Encounter Setup (Without Map Editor)

**Step 1: Create Testing Tile**

Edit `src/resources/maps/testing-map.json` and add a combat arena tile:

```json
"(25, 25)": {
  "id": "combat_arena_standard",
  "title": "Standard Combat Arena",
  "description": "A spacious open arena marked with combat circles. The ground is worn smooth from countless battles.",
  "exits": ["north", "south", "east", "west", "northeast", "northwest", "southeast", "southwest"],
  "events": [],
  "items": [
    {
      "__class__": "Restorative",
      "__module__": "items",
      "props": {
        "weight": 0.25,
        "maintype": "Consumable",
        "subtype": "Potion",
        "count": 3,
        "name": "Restorative",
        "power": 60,
        "value": 100
      }
    }
  ],
  "npcs": [
    {
      "__class__": "CaveBat",
      "__module__": "npc",
      "props": {
        "name": "Cave Bat 1",
        "maxhp": 8,
        "hp": 8,
        "attack_power": 3,
        "defense": 1,
        "speed": 4
      }
    },
    {
      "__class__": "CaveBat",
      "__module__": "npc",
      "props": {
        "name": "Cave Bat 2",
        "maxhp": 8,
        "hp": 8,
        "attack_power": 3,
        "defense": 1,
        "speed": 4
      }
    },
    {
      "__class__": "CaveBat",
      "__module__": "npc",
      "props": {
        "name": "Cave Bat 3",
        "maxhp": 8,
        "hp": 8,
        "attack_power": 3,
        "defense": 1,
        "speed": 4
      }
    }
  ]
}
```

**Step 2: Add Navigation**

Ensure player can reach the combat arena:

```json
"(24, 25)": {
  "description": "A hallway leading to the combat arena.",
  "exits": ["east"],
  ...
}
```

**Step 3: Configure Starting Scenario**

In `config_phase4_testing.ini`:

```ini
test_scenario = standard
startmap = testing-map
startposition = 25, 15
```

---

## Running Combat Scenarios

### Launch Game with Testing Configuration

```bash
# Activate environment
.venv\Scripts\Activate.ps1

# Start game with Phase 4 config (requires code changes to support config file parameter)
# For now, manually copy config:
Copy-Item config_phase4_testing.ini config_dev.ini -Force

# Start game
python src/game.py
```

### Game Flow

1. **Load Testing Map** → Game loads `testing-map`
2. **Position at Arena** → Player starts at configured location
3. **Enter Combat Tile** → Triggers combat with spawned NPCs
4. **Initialize Positions** → Coordinate system sets unit positions
5. **Execute Moves** → Test movement and positioning
6. **Verify Calculations** → Check distance, angle, damage modifiers

---

## Validation Checklist During Testing

### During Combat Entry

- [ ] Testing map loads successfully
- [ ] Player positioned at correct coordinate
- [ ] All NPCs visible on screen
- [ ] Combat initialized without errors
- [ ] Position system activated (if logged)

### During Movement

- [ ] Player coordinates update after move
- [ ] NPC coordinates update after their action
- [ ] Distance to enemies recalculated
- [ ] Facing direction shown/updated
- [ ] No out-of-bounds positioning errors

### During Combat Calculation

- [ ] Damage values show position bonuses (if enabled)
- [ ] Accuracy values reflect angle calculations
- [ ] Flanking bonuses visible in combat log
- [ ] Rear attack bonus confirmed (+40%)

### After Combat

- [ ] All positions tracked correctly
- [ ] AI made logical positioning decisions
- [ ] No crashes or memory issues
- [ ] Combat log complete and accurate

---

## Debug Output Locations

When `debug_mode = True` in config:

- **Position Output:** Console or `combat_testing_phase4.log`
- **Distance Log:** Each calculated distance between units
- **Angle Log:** Attack angle for each action
- **Modifier Log:** Damage/accuracy multipliers applied

**Check Points:**
```
[Distance Calculation] Player to Enemy: 15.5 feet
[Angle Calculation] Attack angle: 45 degrees
[Damage Modifier] Angle 45° = 1.15x (+15%)
[NPC Decision] CaveBat_1 using Advance (moves 3 squares)
```

---

## Common Testing Scenarios

### Scenario 1: Frontal Assault
1. Player at (25, 15), Enemy at (25, 35)
2. Expected angle: 180° (rear to enemy)
3. Expected damage: 1.40x (+40% bonus)
4. Test Advance → should close to 2-4 squares

### Scenario 2: Flanking Position
1. Player at (25, 25), Enemy at (25, 25)
2. Player moves to (35, 25) → 90° angle (flank)
3. Expected damage: 1.15x (+15% bonus)
4. Test FlankingManeuver → should execute successfully

### Scenario 3: Surrounded
1. Player at (25, 25), surrounded by 4 enemies
2. Enemies at (25, 15), (25, 35), (15, 25), (35, 25)
3. Test TacticalRetreat → should move away from nearest
4. Verify multiple threat distances calculated

### Scenario 4: Boss 1v1
1. Player at (25, 10), Boss at (25, 40)
2. Distance: ~30 squares
3. Test BullCharge → should close 4-6 squares
4. Test repositioning for flanking advantage

---

## Troubleshooting

### Combat Won't Start
- Check NPC JSON formatting
- Verify all `__class__` and `__module__` fields correct
- Ensure tile has `npcs` array populated
- Check `startmap` in config matches file name

### Positions Not Displaying
- Verify `debug_positions = True` in config
- Check `show_unit_positions = True`
- Look in `combat_testing_phase4.log` for output
- Ensure position system initialized (check for errors)

### Incorrect Damage Modifiers
- Verify angle calculation is correct
- Check distance units (should be feet/squares)
- Confirm facing direction set before attack
- Review modifier calculation ranges in config

### Movement Not Working
- Check grid boundaries (0-50)
- Verify NPC AI enabled
- Confirm move type available for unit
- Check distance to target is correct

---

## Map Editor Integration (Future)

Current testing uses pre-configured JSON tiles. In future iterations:

1. Use `utils/map_generator.py` for visual editing
2. Save configurations directly
3. Test scenarios become persistent
4. Live scenario switching

**To Use Map Editor:**

```bash
python utils/map_generator.py
```

---

## Next Steps After Phase 4

- [ ] Document all test results in PHASE-4-TESTING-RESULTS.md
- [ ] Create performance benchmarks
- [ ] Log all issues found
- [ ] Validate NPC AI improvements
- [ ] Compare Phase 3 predictions with Phase 4 reality
- [ ] Prepare Phase 5 (production deployment)

---

**Files Reference:**
- Config: `config_phase4_testing.ini`
- Map: `src/resources/maps/testing-map.json`
- Log: `combat_testing_phase4.log` (generated during testing)
- Checklist: `PHASE-4-TESTING-CHECKLIST.md`

