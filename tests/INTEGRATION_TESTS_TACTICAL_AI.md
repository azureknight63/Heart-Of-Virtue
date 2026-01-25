# Integration Test Suite for Tactical Strategist AI

## Overview
This document describes the integration test suite created for the Tactical Strategist AI and Enhanced Combat Visualization features. These tests verify end-to-end functionality across the full stack.

## Test Files Created

### Backend Integration Tests
**File**: `tests/api/test_tactical_ai_integration.py`

#### Helper Functions
- `create_mock_move(name)`: Creates a simple mock move for testing without complex initialization
- `create_test_enemy(name, hp)`: Creates a properly initialized test enemy NPC
- `ensure_player_room(player)`: Ensures player has a current_room for combat initialization

#### Test Classes

##### TestTacticalStrategistIntegration (5 tests)
1. **test_full_combat_cycle_with_ai_suggestions**
   - Verifies complete combat flow: start → AI suggests → execute → victory
   - Checks that AI suggestions are present in battle state
   - Validates combat log contains player actions

2. **test_ai_suggestions_increase_with_passive_skills**
   - Tests that unlocking "Strategic Insight" increases suggestion count
   - Verifies "Master Tactician" further increases suggestions
   - Ensures graceful handling when LLM is unavailable

3. **test_combined_move_and_target_execution**
   - Tests one-click move+target execution from AI suggestion
   - Validates `select_move_and_target` command type
   - Verifies move execution appears in combat log

4. **test_status_effects_serialization**
   - Tests that status effects are properly serialized for frontend
   - Verifies combatant data includes active_effects array
   - Checks effect data structure (name, type, description, duration)

5. **test_ai_context_includes_combat_history**
   - Verifies AI receives combat history for context-aware suggestions
   - Checks that combat log accumulates over multiple turns
   - Validates last_move_summary is captured

##### TestEnhancedCombatVisualizationIntegration (2 tests)
1. **test_status_effects_in_combat_state**
   - Verifies status effects appear in serialized combat state
   - Checks all combatants have required fields (name, hp, max_hp)
   - Validates combatant array structure

2. **test_beat_states_include_position_data**
   - Tests that beat states include position/distance data
   - Verifies each beat state has combatant position information
   - Checks for either coordinate (x, y) or distance data

### Frontend Integration Tests
**File**: `frontend/src/pages/GamePage.integration.test.jsx`

#### Test Suite: Tactical AI Integration Tests (5 tests)

1. **displays AI suggestions during combat**
   - Mocks combat state with AI suggestions
   - Verifies "TACTICAL ADVISOR" panel appears
   - Checks suggestion data is rendered

2. **executes combined move and target from AI suggestion click**
   - Simulates clicking an AI suggestion
   - Verifies `select_move_and_target` API call is made
   - Validates correct move_name and target_id are sent

3. **displays status effects with icons**
   - Mocks combat state with active effects (Burn, Shield)
   - Verifies emoji icons are rendered (🔥, 🛡️)
   - Tests StatusEffectsIconPanel integration

4. **shows previous move analysis in suggestions panel**
   - Mocks battle state with last_move_outcome
   - Verifies "ANALYSIS OF PREVIOUS CYCLE" appears
   - Checks outcome text is displayed

5. **updates status effects when combat state changes**
   - Simulates combat state update adding Poison effect
   - Verifies new effect icon appears (🧪)
   - Tests reactive UI updates

## Test Execution

### Running Backend Integration Tests
```bash
# All integration tests
$env:PYTHONPATH="src"; .venv\Scripts\pytest.exe tests/api/test_tactical_ai_integration.py -v

# Specific test class
$env:PYTHONPATH="src"; .venv\Scripts\pytest.exe tests/api/test_tactical_ai_integration.py::TestTacticalStrategistIntegration -v

# Single test
$env:PYTHONPATH="src"; .venv\Scripts\pytest.exe tests/api/test_tactical_ai_integration.py::TestTacticalStrategistIntegration::test_full_combat_cycle_with_ai_suggestions -v
```

### Running Frontend Integration Tests
```bash
cd frontend
npm test src/pages/GamePage.integration.test.jsx
```

## Key Integration Points Tested

### Backend → Frontend Data Flow
✅ Combat state serialization
✅ AI suggestions in battle_state
✅ Status effects in combatant data
✅ Beat states with position data
✅ Combat log accumulation

### Frontend → Backend Command Flow
✅ Combat start API call
✅ Move execution with `select_move_and_target`
✅ Combat status polling
✅ Combined move+target commands

### AI Strategist Integration
✅ Suggestion generation during combat
✅ Context building from combat history
✅ Passive skill effects on suggestion count
✅ Graceful degradation when LLM unavailable

### Combat Visualization Integration
✅ Status effect icon mapping
✅ Effect tooltip data
✅ Position/distance data for battlefield
✅ Real-time UI updates

## Mock Strategy

### Backend Mocks
- **SimpleMockMove**: Minimal move implementation for testing
- **MockRoom**: Simple room with npcs_here list
- **MockEffect**: Status effect with required fields

### Frontend Mocks
- **API endpoints**: All `api.combat.*` and `api.player.*` calls mocked
- **Combat state**: Complete battle_state objects with suggestions
- **Status effects**: Active effects arrays with proper structure

## Known Limitations

1. **LLM Integration**: Tests use mocks rather than real LLM calls
   - Rationale: Speed, reliability, no external dependencies
   - Real LLM testing should be done manually or in E2E tests

2. **Complex Move Mechanics**: Tests use simplified mock moves
   - Rationale: Avoid complex initialization requirements
   - Full move testing covered in unit tests

3. **Socket.IO Events**: Not tested in integration suite
   - Rationale: Requires complex async test setup
   - Real-time features should be tested in E2E tests

## Future Enhancements

### Potential Additions
1. **E2E Tests**: Full browser automation with Playwright/Cypress
2. **Performance Tests**: Measure AI response time under load
3. **Stress Tests**: Multiple concurrent combat sessions
4. **Visual Regression**: Screenshot comparison for UI consistency
5. **Accessibility Tests**: Keyboard navigation and screen reader support

### Test Data Improvements
1. **Fixtures**: Shared test data for common scenarios
2. **Factories**: Dynamic test data generation
3. **Snapshots**: JSON snapshot testing for API responses

## Success Criteria

Integration tests are considered successful when:
- ✅ All backend API endpoints return expected data structures
- ✅ Frontend components correctly display backend data
- ✅ User actions trigger correct API calls
- ✅ AI suggestions flow from backend to frontend
- ✅ Status effects render with correct icons and data
- ✅ Combat state updates propagate to UI
- ✅ Error cases are handled gracefully

## Conclusion

The integration test suite provides comprehensive coverage of the Tactical Strategist AI and Enhanced Combat Visualization features across the full stack. Tests verify data flow, API contracts, UI rendering, and user interactions, ensuring the features work correctly end-to-end.
