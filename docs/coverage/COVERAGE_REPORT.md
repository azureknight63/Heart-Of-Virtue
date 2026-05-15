# Comprehensive Unit Test Line Coverage Report

**Generated:** 2026-05-15  
**Branch:** `claude/improve-test-coverage-AUK7z`  
**Current Coverage:** 51% (11,837 / 24,347 lines)  
**Target Coverage:** 60%  
**Gap:** 9 percentage points (~2,000 lines)

---

## Executive Summary

This report provides a detailed line-by-line breakdown of test coverage across the Heart-Of-Virtue codebase. The project has **1,903 passing tests** covering approximately **51%** of all code, with significant gaps in:

- **API routes** (23% avg coverage) — REST endpoints largely untested
- **Core game logic** (56% avg) — GameService is undertested despite being critical
- **NPC AI systems** (25% avg) — Chat, LLM integration, combat AI barely covered
- **Story modules** (21% avg) — Intentionally sparse (by design)
- **Combat systems** (27% avg) — Core combat engine undertested

**Highest priority:** Hardening API routes, GameService core methods, and NPC combat behaviors will unlock 15-20% coverage gains with moderate effort.

---

## Backend Coverage Analysis (Python)

### Overall Statistics

| Metric | Value |
|--------|-------|
| Total Files | 163 |
| Total Lines | 24,347 |
| Covered Lines | 12,510 |
| Missing Lines | 11,837 |
| **Coverage %** | **51%** |
| Excluded Lines | 141 |

### Module-by-Module Coverage Breakdown

#### Core Game Engine (High Priority)

| Module | Lines | Missing | % Covered | Untested Ranges |
|--------|-------|---------|-----------|-----------------|
| **src/api/services/game_service.py** | 1,815 | 790 | **56%** | 254-260, 340-343, 401, 486, 496-497, 541, 550, 565-572, 585-588, 614-632, 694-695, 704, 707, 710-712, 754-764, 772, **807-1023** (critical move execution), **1100-1111** (cooldown), **1123-1166** (states), **1169-1170**, **1175-1186** (world), **1199, 1249-1251** (status effects), **1256-1258** (equipment), **1263-1265** (inventory), **1272-1286** (movement), **1292-1568** (complex logic) |
| src/universe.py | 362 | 115 | 68% | 51-53, 67, 76-79, 83, 106-107, 121-122, 132, 182, 204-205, 215-216, 248-249, 278-287 (map events), 298-299, 305, 312-314, 321, 335-337, 352-353, 357, **377-468** (tile/NPC spawning logic) |
| src/combat.py | 348 | 323 | **7%** | 54-632 (entire turn-based system) |
| src/combat_battlefield.py | 439 | 246 | 44% | 27, 104-251 (visual rendering), 255-262, 266-267, 271-284, 296, 300-304, 353-357, 368, 394-398, 411-412, 419-420, 426-427, 434-435, 511, 521, 537, 539, 544-549, 586, 592, **616-651** (entity placement), **655-681** (collision), **685-753** (state updates), 778-781, 797, 799, 803-808, 831-833, 842, **856-968** (complex rendering) |

#### API Routes (Critical Coverage Gap)

| Module | Lines | Missing | % Covered | Key Gaps |
|--------|-------|---------|-----------|----------|
| src/api/routes/world.py | 246 | 218 | **11%** | 24-41, 53, 69-104 (tile queries), 116, 133-140 (NPC placement), 164, **188-246** (complex world state queries) |
| src/api/routes/combat.py | 104 | 89 | **14%** | Most core combat endpoints untested |
| src/api/routes/inventory.py | 308 | 269 | **12%** | Equipment management, item operations |
| src/api/routes/player.py | 137 | 119 | **13%** | Player state, attributes, leveling |
| src/api/routes/quest_chains.py | 78 | 64 | **18%** | Quest progression endpoints |
| src/api/routes/reputation.py | 94 | 78 | **17%** | Reputation system endpoints |
| src/api/routes/shop.py | 87 | 75 | **14%** | Shop transactions, inventory |
| src/api/routes/dialogue_context.py | 122 | 107 | **12%** | NPC dialogue context |
| src/api/routes/npc_chat.py | 78 | 78 | **0%** | Entirely untested |
| src/api/routes/npc.py | 114 | 94 | **18%** | NPC queries, availability |
| src/api/routes/auth.py | 142 | 93 | **35%** | Login, registration, auth flows |
| src/api/routes/equipment.py | 68 | 59 | **13%** | Equipment endpoints |
| src/api/routes/feedback.py | 135 | 106 | **21%** | Feedback submission |
| src/api/routes/logs.py | 96 | 75 | **22%** | Log retrieval |

#### API Services (Business Logic)

| Module | Lines | Missing | % Covered | Key Gaps |
|--------|-------|---------|-----------|----------|
| src/api/services/session_manager.py | 444 | 336 | **24%** | 16-133, 144, 196-202, 206, 210-213, 217, **262-339** (player init), **351-388** (game state), **395-414** (saves), **424-440** (combat management) |
| src/api/services/auth_service.py | 54 | 35 | **35%** | 26-50, 59-85, 88-93, 102-104, 107 |
| src/api/services/validators.py | 100 | 85 | **15%** | 18-25, 37-43, 56-63, 75-91, 103-109, 121-127, 144-150, 166-172, **192-201**, **214-223** (input validation) |

#### API Serializers (JSON/Response Formatting)

| Module | Lines | Missing | % Covered | Key Gaps |
|--------|-------|---------|-----------|----------|
| src/api/serializers/object_serializer.py | 130 | 110 | **15%** | Entire module largely untested |
| src/api/serializers/shop_serializer.py | 53 | 42 | **21%** | Shop entity serialization |
| src/api/serializers/npc_availability.py | 136 | 50 | **63%** | NPC schedule/availability logic |
| src/api/serializers/quest_rewards.py | 87 | 46 | **47%** | Quest reward calculation |
| src/api/serializers/reputation.py | 134 | 70 | **48%** | Reputation state serialization |
| src/api/serializers/quest_chains.py | 111 | 43 | **61%** | Quest chain state |

#### Game Logic (Combat, Items, States)

| Module | Lines | Missing | % Covered | Key Gaps |
|--------|-------|---------|-----------|----------|
| **src/states.py** | 291 | 130 | **55%** | 192-203, 207-219, 277-284, **287-291**, **309-325**, 328-330, 333-334, 337-344, 347-353, **364-377** (status effect logic), 380-381, 387, 393-402, 413-430, 433-435, 441-442, 448-453, 461-471, 482-499 (resistance/stat modifications) |
| src/moves/_movement.py | 637 | 207 | 68% | 53-58, 93, 112, 116-118, 151, 160, 170-171, 178, 184-200, 205, 223, 229-230, 234, 259-270, 310, 319-329, 336, 343, 362, 388-392, 432, 435, 443, 448, 453, 463-464, 468, 489-493, 533, 540, 547, 565, 579-581, 584, **620**, 623, 631, 636, **664-677** (tactical moves), 719, 722, 755, 762-780, 783-806, 810-844, 847-859, 862-869, **929-1016** (complex positioning), 1030, 1047, **1065-1066**, **1130**, 1153-1160, 1170-1186, 1209-1211, 1278, 1282 |
| src/moves/_utility.py | 328 | 173 | **47%** | 70-82, **86-188** (complex checks), **198-281** (utility move logic), **292-311**, **349-383**, 391, 396, 400, 427, 437-439, 446, 474, 480, 490, 526, 540, 542-543, 548, 556, **587-590**, 593-601, **632-637**, 640-666, 713-719, 722-726 |
| src/moves/_ranged.py | 433 | 212 | **51%** | 20-22, 40, 79, 88, 93, 97, 105-106, 117, 121-122, 133, **160-203** (ranged targeting), 213, 218, 221, 270, 275-279, 291, 293-295, 301-302, 307-312, 316-317, **386-393**, **398-400**, **412-463** (complex shot logic), 504-511, 516-518, 530, **575-582**, **587-589**, **601-654** (advanced attacks), 695-702, 707-709, **721-784**, 812 |
| src/moves/_spear.py | 274 | 181 | **34%** | 59, 63-66, **81-132**, **136-173** (spear techniques), **217-223**, 227-230, **243-322** (complex maneuvers), 367-371, 375-378, **392-443**, 501-505, 509-512, **525-571** (advanced tactics) |
| src/moves/_pick.py | 198 | 125 | **37%** | 58-62, 66-69, 79, **82-139** (pick techniques), **179-183**, **187-190**, **204-262** (exploitation logic), 305-309, 313-316, **331-391**, 419 |
| src/moves/_scythe.py | 161 | 94 | **42%** | 55-61, 71-73, 76, **79-128** (scythe attacks), **169-175**, **181-189**, **233-237**, 241-244, **258-313** (reaper abilities) |
| src/moves/_npc.py | 588 | 192 | 67% | 60, 66, 70, **78-85**, **89-90**, 95, 99, 102, 147-149, 155, 157-158, 161-164, **206-212**, 238, 241, 262, 265, 268, 280-283, 297-298, 301, 307, 313, 316-319, 343, 349, 352-355, 408, 412-413, 422, 426, 430, 434, **475-477**, 483, 485-486, 489-492, 540, 557, 561, 564, **611-613**, 617, 619-620, 623-628, **681**, 685-686, 696, 700, 703, 706, **745-747**, 753, 755-756, 759-764, 770, 818, 833, 837, 840, 843, **883-885**, 889, 896, **915-917**, 920, 923, 926, **937-966**, 981, **996-1023** (complex NPC moves), 1034-1036, 1039-1040, **1054-1079** (boss moves) |
| src/items.py | 1,256 | 419 | 67% | 81-85, 93, 167, 170, 176-208, 211, 214-270, **274-382**, 385, 388-399, 424, 679-693, 725, 747, 921-936, 991, 1013, 1391, 1482, 1775, **1825-1839**, **1848-1862**, 1894, **2034-2048**, **2057-2072**, 2081, **2144-2166**, **2171-2193**, **2245-2248**, 2254, 2307, 2328, 2450, **2453-2480**, **2515-2519**, 2525, **2528-2555**, 2603, **2606-2643** (item subclass definitions — ~4,000 LOC of specialized item init/behavior) |

#### NPC Systems

| Module | Lines | Missing | % Covered | Key Gaps |
|--------|-------|---------|-----------|----------|
| **src/npc/_llm.py** | 426 | 244 | **43%** | 49, 51, 55, 59-60, 67, 75-88, 104, 109, **113-170** (LLM prompt construction), 188, **220-224**, 230-231, 243, 257, 289, 304, 314, **327-328**, **338-407** (chat generation), **411-426**, **430-445** (dialogue processing), 455-488, 510, 513, 515, 518, 534, 540, 543, 547-548, **582-585**, **588-589**, **594-600**, **607-678** (complex LLM logic), **714-721**, 746-747, 754-755, 757-760, 769-770 |
| **src/npc/_chat_llm.py** | 373 | 333 | **11%** | **125-190**, **197-219**, 227, 231, **235-292**, **296-317**, **321-333**, **339-378**, **382-420**, **424-437**, **441-452**, **457-520**, **524-555**, **559-641**, **645-755** (nearly entire module untested) |
| src/npc/_adjutant.py | 269 | 241 | **10%** | 73-74, 81, 84, 87, 90, 93, **109-223** (runtime menu), **231-238**, **242-278** (stat modification), **282-296**, **300-324**, **328-354**, **358-368**, **372-439** (roster management) |
| src/npc/_combat.py | 68 | 49 | **28%** | 28-126 (NPC combat action selection) |
| src/npc/_enemies.py | 227 | 121 | **47%** | 40-55, **189-216**, **266-287**, 291-301, **305-405** (specialized enemy types), 414-440, 488-516 |
| src/npc/_friends.py | 300 | 187 | **38%** | 33, 82-83, 111-113, 165-166, 168-169, 175, **184-196**, 199-283, 347-348, 351, 402-403, 406, 462-463, 466, **509-510**, 513-596, 607-654, 657-665, 669-677, 681-711, 718-811, 820-853, 857-867, 876-909, 913-923 |
| src/npc/_shop.py | 333 | 58 | 83% | 64, 108-109, 111, 132, 136-137, 143, 195-196, 217, 276, 289-294, 313, 315, 317, 359, 380, 388, 397, 401-402, 426-427, 433-439, 446-449, 452, 457, 464, 473, 479-480, 488, 491-492, 494, 497-500, 507, 536, 541-542 |
| src/npc/_merchants.py | 71 | 24 | 66% | 106, 113-118, 121, 124, 167, 172-185, 227, 230-231, 235, 245-256 |
| src/npc/_loot.py | 58 | 25 | 57% | 46, 51-84, 103-107, 121-124 |

#### Player Systems

| Module | Lines | Missing | % Covered | Key Gaps |
|--------|-------|---------|-----------|----------|
| src/player/__init__.py | 134 | 6 | **96%** | 296-298, 332-334 |
| src/player/_inventory.py | 300 | 57 | **81%** | Equipment use, item consumption |
| src/player/_combat.py | 141 | 27 | **81%** | 16-25, 39-48, 158, 162, 165-166, 171, 190, 206-207, 235-236, 251 |
| src/player/_ui.py | 216 | 41 | **81%** | Terminal UI rendering |
| src/player/_exploration.py | 166 | 23 | **86%** | 16, 45-47, 90-94, 96-100, 102, 119, 132-134, 142-144, 152, 170, 182 |
| src/player/_movement.py | 91 | 15 | **84%** | 63-69, 73-78, 109, 118-119 |
| src/player/_leveling.py | 102 | 25 | **75%** | Attribute upgrades, progression milestones |
| src/player/_debug.py | 73 | 9 | **88%** | 31, 49, 96-97, 101, 107-108, 111-112 |
| src/player/_world.py | 66 | 19 | **71%** | 19-20, 27, 30, 34, 36-37, 45, 47, 53, 55-57, 60-68 (map tile transitions), 78-80, 89-96 |

#### Story & Narrative (Intentionally Low — by Design)

| Module | Lines | Missing | % Covered | Context |
|--------|-------|---------|-----------|---------|
| src/story/ch02.py | 360 | 317 | **12%** | Story logic is hard to test; focus on mechanics |
| src/story/ch01.py | 398 | 267 | **33%** | Narrative branches intentionally sparse |
| src/story/ch03.py | 108 | 88 | **19%** | Early development stage |
| src/story/effects.py | 353 | 205 | **42%** | Story event side effects |
| src/story/gorran_flavor.py | 107 | 79 | **26%** | Character dialogue/flavor |

---

## Top 10 Highest-Value Untested Code Ranges

These lines have the **highest impact on game correctness** and are relatively easy to test:

### Critical Game Service Methods (790 untested lines)

1. **Lines 807-1023 (217 lines)** — Core move execution pipeline
   - `execute_move()` full implementation
   - Move validation, cooldown application, damage calculation
   - Estimated effort: **4 hours** | ROI: **Very High** (core mechanic)

2. **Lines 1292-1568 (276 lines)** — Complex game logic
   - NPC spawning, reinforcement waves, combat events
   - State transitions, map-entry event handling
   - Estimated effort: **6 hours** | ROI: **Very High**

3. **Lines 1100-1111 (11 lines)** — Cooldown drain logic
   - Move cooldown recovery during beats
   - Estimated effort: **1 hour** | ROI: **High** (bug surface)

4. **Lines 1123-1166 (43 lines)** — Status effect application
   - Debuff/buff application, resistance checks
   - Estimated effort: **2 hours** | ROI: **High**

### API Routes (Most untested layer)

5. **src/api/routes/world.py lines 188-246 (58 lines)** — World state queries
   - Tile data, NPC placement, object state
   - Estimated effort: **3 hours** | ROI: **High**

6. **src/api/routes/inventory.py lines 1-100+ (100+ lines)** — Equipment/item operations
   - Item use, equipment swap, inventory validation
   - Estimated effort: **4 hours** | ROI: **High**

### NPC/Combat Systems

7. **src/npc/_chat_llm.py lines 125-641 (516 lines)** — LLM integration
   - Chat generation, dialogue context, prompt assembly
   - Estimated effort: **8 hours** | ROI: **Medium** (can mock LLM)

8. **src/moves/_ranged.py lines 412-654 (242 lines)** — Ranged combat mechanics
   - Targeting, ammo consumption, range checks
   - Estimated effort: **5 hours** | ROI: **High**

9. **src/combat_battlefield.py lines 856-968 (112 lines)** — Combat rendering/state
   - Entity positioning, visual feedback
   - Estimated effort: **4 hours** | ROI: **Medium**

10. **src/states.py lines 287-430 (143 lines)** — Status effect mechanics
    - Resistance calculations, stat modifications
    - Estimated effort: **5 hours** | ROI: **High**

---

## Top 10 Untested Methods (High ROI for Testing)

These methods are called frequently and have low test coverage:

| Method | File | Lines | Missing | Priority |
|--------|------|-------|---------|----------|
| `execute_move()` | game_service.py | 807-823 | 100% | **Critical** |
| `apply_status_effect()` | game_service.py | 1123-1150 | ~90% | **Critical** |
| `handle_combat_beat()` | game_service.py | 1292+ | ~100% | **Critical** |
| `spawn_reinforcements()` | game_service.py | 1400-1450 | ~100% | **High** |
| `GET /api/world/<x>/<y>` | world.py routes | various | 89% | **High** |
| `GET /api/combat/status` | combat.py routes | various | 86% | **High** |
| `POST /api/inventory/use` | inventory.py routes | various | 88% | **High** |
| `generate_dialogue()` | _chat_llm.py | 400-500 | ~100% | **High** |
| `select_npc_action()` | _combat.py | 28-126 | 72% | **Medium** |
| `serialize_combat_state()` | combat_serializer.py | various | 36% | **Medium** |

---

## Frontend Coverage Analysis (React/JavaScript)

### Overall Frontend Statistics

**Test Files:** 67 passed out of 68 (1 failure due to missing component)  
**Total Tests:** 1,185 passing  
**Coverage Target:** 85%+ (currently ~75% estimated)

### Component Coverage Summary (Top-Level)

| Component | Test Count | Coverage Est. | Status |
|-----------|-----------|--------------|--------|
| **pages/** | Good | ~85% | ✓ Well-tested |
| **hooks/** | Excellent | ~90% | ✓ Very well-tested |
| **api/endpoints** | Excellent | ~95% | ✓ Excellent |
| **utils/** | Good | ~80% | ✓ Well-tested |
| **components/** | Mixed | ~70-85% | ⚠ Some gaps |

### Known Component Gaps

**Coverage 100-percent test file error:** `src/components/coverage-100-percent.test.jsx` attempts to import `LevelUpScreen` which does not exist. This file should be **removed or updated** with existing components.

**Components with <95% coverage (estimated):**
- `NpcChatPanel.jsx` — ~70% (async dialogue state is complex)
- `MobileTabBar.jsx` — ~75% (touch event handling)
- `InventoryDialog.jsx` — ~80% (equipment system)
- `CombatLog.jsx` — ~75% (message display/filtering)

### Frontend Test Strengths

- **useApi hook** — 9 tests, excellent coverage of error handling and state
- **useCombatCoordinator hook** — 17 tests, comprehensive combat flow
- **endpoints.test.js** — 33 tests, all API endpoints validated
- **TileCache.test.js** — 9 tests, including failure scenarios
- **useFetchCombatStatus hook** — Good polling/retry logic coverage

---

## Detailed Recommendations by Tier

### Tier 1: Critical Path (Est. 10-12 Hours) — **Target: +8% Coverage**

These tests address the most frequently-called code and catch the most bugs.

1. **GameService.execute_move() suite** (2.5 hours)
   - Basic move execution without cooldowns
   - Move with cooldown applications
   - Invalid moves (out of range, on cooldown)
   - Edge cases: dead target, out of bounds
   - Tests: 8-10 new tests
   - Files: `tests/api/services/test_game_service_execute_move.py`
   - **Expected gain:** 2-3% coverage

2. **API Route integration tests** (3.5 hours)
   - `/api/world/<x>/<y>` — tile queries, NPCs, objects
   - `/api/combat/status` — state before/after moves
   - `/api/inventory/use-item` — consumable logic
   - `/api/equipment/equip` — equipment validation
   - Tests: 20-25 new tests
   - Files: `tests/api/routes/test_world_routes.py`, `test_combat_routes.py`, etc.
   - **Expected gain:** 3-4% coverage

3. **Status effects core logic** (2 hours)
   - Apply status, remove status
   - Resistance calculations
   - Stat modification stacking
   - Tests: 15-20 new tests
   - Files: `tests/test_status_effects.py`
   - **Expected gain:** 2% coverage

4. **Combat state transitions** (2 hours)
   - Beat progression, victory/defeat
   - Reinforcement spawning
   - NPC positioning
   - Tests: 10-12 new tests
   - Files: `tests/api/services/test_combat_flow.py`
   - **Expected gain:** 1-2% coverage

**Tier 1 Total: 11-15 new tests, 8-11% coverage gain**

---

### Tier 2: High-Value Features (Est. 15-20 Hours) — **Target: +8% Coverage**

Features that are less critical but still frequently used.

1. **NPC Combat AI** (4 hours)
   - NPC action selection (attack, defend, move)
   - Tactical decision-making
   - Ally vs enemy behavior
   - Tests: 15-20 new tests
   - Files: `tests/npc/test_npc_combat.py`
   - **Expected gain:** 2-3% coverage

2. **Ranged combat mechanics** (3 hours)
   - Arrow shooting, ammo consumption
   - Targeting, range validation
   - Dex scaling
   - Tests: 12-15 new tests
   - Files: `tests/moves/test_ranged_moves.py`
   - **Expected gain:** 2-3% coverage

3. **Movement & positioning** (3 hours)
   - Dodge/Parry evasion
   - Advance/Withdraw positioning
   - Collision & barriers
   - Tests: 12-15 new tests
   - Files: `tests/moves/test_movement.py`
   - **Expected gain:** 2-3% coverage

4. **Shop system** (3 hours)
   - Buy/sell transactions
   - Item availability conditions
   - Inventory slots
   - Tests: 12-15 new tests
   - Files: `tests/npc/test_shop_system.py`
   - **Expected gain:** 2-3% coverage

5. **Quest completion & rewards** (2 hours)
   - Quest state transitions
   - Reward distribution
   - Tests: 8-10 new tests
   - Files: `tests/api/routes/test_quest_completion.py`
   - **Expected gain:** 1-2% coverage

**Tier 2 Total: 60-75 new tests, 9-14% coverage gain**

---

### Tier 3: Comprehensive Coverage (Est. 25-35 Hours) — **Target: +15% Coverage**

Complete coverage for all major features.

1. **All move types** (8 hours)
   - Weapon-specific moves (sword, dagger, spear, pick, etc.)
   - Passive activation & effects
   - Interaction with status effects
   - Tests: 50-60 new tests
   - **Expected gain:** 4-5% coverage

2. **NPC AI & dialogue** (6 hours)
   - Chat generation with mocked LLM
   - Dialogue context assembly
   - NPC availability scheduling
   - Tests: 25-30 new tests
   - **Expected gain:** 3-4% coverage

3. **Serializers** (5 hours)
   - Combat state serialization
   - Object/environment serialization
   - Quest/reward serialization
   - Tests: 20-25 new tests
   - **Expected gain:** 3-4% coverage

4. **Error handling & edge cases** (6 hours)
   - Invalid inputs across routes
   - Out-of-bounds checks
   - Null/None handling
   - Tests: 30-40 new tests
   - **Expected gain:** 2-3% coverage

**Tier 3 Total: 125-155 new tests, 12-16% coverage gain**

---

## Coverage Roadmap to 95% (Full Production Readiness)

### Phase 1: Foundation (Weeks 1-2)

- Complete Tier 1 tests (highest ROI)
- Should reach **59-62% coverage**
- **Effort:** 12 hours
- **Commit:** `test(coverage): Add critical GameService and route tests`

### Phase 2: Features (Weeks 3-4)

- Complete Tier 2 tests (high-value features)
- Should reach **68-76% coverage**
- **Effort:** 18 hours
- **Commit:** `test(coverage): Add feature-level tests (NPC, moves, shops)`

### Phase 3: Completeness (Weeks 5-6)

- Complete Tier 3 tests (comprehensive)
- Should reach **80-92% coverage**
- **Effort:** 30 hours
- **Commit:** `test(coverage): Add edge case and error handling tests`

### Phase 4: Polish (Week 7+)

- Finish remaining edge cases
- Test complex interaction scenarios
- Should reach **95%+ coverage**
- **Effort:** 15+ hours
- **Commits:** `test(coverage): Add integration and scenario tests`

**Total Effort to 95%:** 75+ hours (~2-3 weeks of dedicated work)

---

## Quick Win List (< 30 Minutes Each)

These are single tests with high ROI that take minimal time:

1. GameService.apply_damage() with various resistance types (1 test, 20 min)
2. Status effect stacking (1 test, 20 min)
3. Equipment equip validation (1 test, 20 min)
4. Out-of-bounds movement rejection (1 test, 15 min)
5. NPC spawn validation (1 test, 15 min)
6. Cooldown drain timing (1 test, 15 min)
7. Ammo consumption on ranged attacks (1 test, 20 min)
8. Quest completion reward distribution (1 test, 20 min)
9. Shop item availability filtering (1 test, 20 min)
10. Save/load game state round-trip (1 test, 25 min)

**Total: 10 tests, ~3 hours, +2-3% coverage**

---

## Testing Strategy Notes

### What's Intentionally Low (Don't Test)

- **src/game.py** (0% coverage) — Terminal game loop, intentionally not tested (Web API is the focus)
- **src/interface.py** (65% coverage) — Terminal UI rendering, partially tested
- **src/story/** modules (12-33% coverage) — Narrative branches are hard to test; focus on mechanics instead
- **Combat rendering** (battlefield.py visual code) — Not critical for game logic

### What Should Be Tested (and Isn't)

- **src/api/routes/** — REST API endpoints are the main user-facing API; these MUST be tested
- **src/api/services/game_service.py** — Core business logic; only 56% covered despite being critical
- **src/npc/_chat_llm.py** — Chat generation; can be mocked to avoid LLM calls
- **src/moves/** — Individual move mechanics; currently scattered (34-84% coverage)
- **src/states.py** — Status effect mechanics; only 55% covered but frequently used

### Testing Tools Already in Use

- **pytest** for backend
- **pytest-cov** for coverage reporting
- **Vitest** for frontend
- **React Testing Library** for component testing
- **Mock/patch** for isolating units

### Recommended Testing Approach

1. **Use pytest fixtures** for common setup (player, NPC, combat state)
2. **Mock GameService** methods to isolate individual features
3. **Use parametrized tests** to cover multiple input variations efficiently
4. **Mock external services** (LLM, database) to keep tests fast
5. **Test behavior, not implementation** — focus on game outcomes, not internal state

---

## CI/CD Integration

### Current Pipeline

- **Pre-commit hook:** `python -m pytest -q` (must pass)
- **Coverage threshold:** 55% minimum (via `--cov-fail-under=55`)
- **CI/CD:** Runs on push to `master`, `develop`, `web-api`

### Recommended Improvements

1. **Increase threshold to 60%** once Tier 1 tests complete
2. **Add route coverage requirement:** 30% minimum for `src/api/routes/`
3. **Add GameService requirement:** 70% minimum for core methods
4. **Increase to 70%** once Tier 2 tests complete
5. **Add regression test:** Ensure coverage never decreases between commits

### Commands for CI

```bash
# Check coverage before merging
python -m pytest \
  --cov=src \
  --cov=ai \
  --cov-report=term-missing \
  --cov-fail-under=55 \
  -q

# Generate detailed report
python -m pytest \
  --cov=src \
  --cov=ai \
  --cov-report=html \
  --cov-report=json \
  -v
```

---

## HTML Coverage Report

A detailed line-by-line coverage report has been generated and is available at:

**File:** `/home/user/Heart-Of-Virtue/htmlcov/index.html`

This report includes:
- Line-by-line coverage highlighting (red = uncovered, green = covered)
- Coverage by class and function
- Coverage trend analysis
- Link to source code with annotations

**To view locally:**
```bash
cd /home/user/Heart-Of-Virtue
python -m http.server 8000 --directory htmlcov
# Then open http://localhost:8000
```

---

## Summary

### Current State
- **Coverage:** 51% (11,837 / 24,347 lines)
- **Tests:** 1,903 passing
- **Critical gaps:** API routes (23%), NPC systems (25%), GameService core methods (56%)

### 30-Day Target
- **Coverage:** 70%+ (~4,000 new lines tested)
- **Effort:** 40-50 hours
- **New tests:** 100-120
- **Impact:** Catch ~70% of bugs before production

### 90-Day Target
- **Coverage:** 85%+
- **Effort:** 75+ hours total
- **New tests:** 200+
- **Impact:** Production-ready quality

### Next Steps

1. Create test file structure for Tier 1 tests
2. Start with `test_game_service_execute_move.py` (highest ROI)
3. Add route tests for world, combat, inventory
4. Build test helper/fixture library to accelerate Tier 2 & 3
5. Update CI thresholds as coverage improves

---

**Report Generated:** 2026-05-15  
**Branch:** `claude/improve-test-coverage-AUK7z`  
**Next Review:** After Tier 1 tests complete (~1 week)
