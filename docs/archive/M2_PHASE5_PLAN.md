# M2 Phase 5 - NPC AI & Dialogue Serialization Plan

## Objective

Extend serialization system to handle NPC behavior, dialogue, and AI state for complete game state snapshots and API support.

## Architecture Overview

### 4 New Serializers

1. **NPCAIStateSerializer** - NPC behavior and decision state
2. **DialogueStateSerializer** - Dialogue trees and conversation state
3. **QuestStateSerializer** - Quest progress and tracking
4. **NPCBehaviorProfileSerializer** - AI configuration and behavior trees

### 3 GameService Methods Per Serializer

- `get_npc_state(player, npc_id)` - Retrieve NPC state
- `update_npc_behavior(player, npc_id, behavior)` - Update NPC actions
- `get_dialogue_options(player, npc_id)` - Get available dialogue choices

### 6 New API Routes

```
GET  /npc/{npc_id}/state          - Get NPC current state
GET  /npc/{npc_id}/dialogue       - Get dialogue options
POST /npc/{npc_id}/dialogue       - Select dialogue choice
GET  /quests/active               - Get active quests
POST /quest/{quest_id}/accept     - Accept quest
POST /quest/{quest_id}/progress   - Update quest progress
```

## Implementation Timeline

### Stage 1: NPCAIStateSerializer (2-3 hours)
- [ ] Create serializer class
- [ ] Implement AI state serialization
- [ ] Handle behavior tracking
- [ ] Create 8 unit tests
- [ ] Integrate with GameService

### Stage 2: DialogueStateSerializer (2-3 hours)
- [ ] Create serializer class
- [ ] Implement dialogue tree serialization
- [ ] Handle conversation state
- [ ] Create 8 unit tests
- [ ] Integrate with GameService

### Stage 3: QuestStateSerializer (2-3 hours)
- [ ] Create serializer class
- [ ] Implement quest tracking
- [ ] Handle progress updates
- [ ] Create 8 unit tests
- [ ] Integrate with GameService

### Stage 4: API Routes & Integration (2-3 hours)
- [ ] Create 6 new API routes
- [ ] Implement route handlers
- [ ] Add validation
- [ ] Create integration tests
- [ ] Documentation

### Stage 5: Testing & Optimization (1-2 hours)
- [ ] Full integration tests
- [ ] Performance testing
- [ ] Edge case handling
- [ ] Final documentation

## Files to Create

### Serializers
```
src/api/serializers/npc_ai.py (400+ lines)
├── NPCAIStateSerializer
├── DialogueStateSerializer
├── QuestStateSerializer
└── NPCBehaviorProfileSerializer
```

### GameService
```
src/api/services/game_service.py (additions)
├── get_npc_state()
├── update_npc_behavior()
├── get_dialogue_options()
├── start_quest()
├── update_quest_progress()
└── ... (9 more NPC methods)
```

### Routes
```
src/api/routes/npc.py (NEW - 300+ lines)
├── GET /npc/{npc_id}/state
├── GET /npc/{npc_id}/dialogue
├── POST /npc/{npc_id}/dialogue
├── GET /quests/active
├── POST /quest/{quest_id}/accept
└── POST /quest/{quest_id}/progress
```

### Tests
```
tests/api/test_npc_serializer.py (NEW - 400+ lines)
└── 32 unit tests for all serializers

tests/api/test_npc_routes_integration.py (NEW - 300+ lines)
└── 20 integration tests for routes
```

## Data Structures

### NPC AI State
```python
{
    "npc_id": "mynx_001",
    "name": "Mynx",
    "current_behavior": "idle",
    "behavior_stack": ["patrol", "wander"],
    "emotion_state": "neutral",
    "aggression_level": 0.5,
    "trust_level": 0.75,
    "last_interaction": "2025-11-08T10:30:00Z",
    "memory": [
        {"event": "spoke_to_player", "timestamp": "...", "context": "..."},
        {"event": "combat_ended", "timestamp": "...", "context": "..."}
    ]
}
```

### Dialogue State
```python
{
    "npc_id": "mynx_001",
    "dialogue_tree": "mynx_welcome",
    "current_node": "greet_player",
    "options": [
        {"id": "opt_1", "text": "What's your story?", "next_node": "backstory"},
        {"id": "opt_2", "text": "Can you help?", "next_node": "quest_offer"}
    ],
    "conversation_history": [
        {"speaker": "mynx", "text": "Hello, traveler!"},
        {"speaker": "player", "text": "Hello"},
        {"speaker": "mynx", "text": "What brings you here?"}
    ]
}
```

### Quest State
```python
{
    "quest_id": "quest_001",
    "title": "The Stolen Amulet",
    "status": "active",
    "progress": 50,
    "objectives": [
        {"id": "obj_1", "text": "Find clues", "completed": true},
        {"id": "obj_2", "text": "Track suspect", "completed": false}
    ],
    "rewards": {
        "experience": 100,
        "gold": 50,
        "items": []
    },
    "started_at": "2025-11-08T10:00:00Z",
    "deadline": "2025-11-15T23:59:59Z"
}
```

## Dependencies & Integration

### Game Engine Integration
- Read from: `npc.py` for NPC state
- Read from: `events.py` for dialogue trees
- Interact with: `player.py` for quest tracking
- Use: `functions.py` for game utilities

### API Layer Integration
- Uses GameService pattern (established in Phase 4)
- Uses validator functions (from existing system)
- Uses error handlers (from existing system)
- Follows route pattern (from combat routes)

## Testing Strategy

### Unit Tests (32 total)
- Serializer tests: 8 per serializer × 4 = 32 tests
- Mock NPC objects with various states
- Test edge cases and error conditions
- Verify serialization/deserialization round-trip

### Integration Tests (20 total)
- Route validation tests: 8 tests
- GameService method tests: 12 tests
- End-to-end NPC interaction tests
- Quest progression tests

### Test Coverage Goals
- 100% of new serializer code
- 100% of new GameService methods
- 100% of new API routes
- All validation logic
- All error conditions

## Estimated Effort

| Phase | Tasks | Estimated Time | Status |
|-------|-------|-----------------|--------|
| 1 | NPC AI Serializer | 2-3 hours | Not Started |
| 2 | Dialogue Serializer | 2-3 hours | Not Started |
| 3 | Quest Serializer | 2-3 hours | Not Started |
| 4 | API Routes | 2-3 hours | Not Started |
| 5 | Testing & Docs | 1-2 hours | Not Started |
| **Total** | **All phases** | **9-14 hours** | **Not Started** |

## Success Criteria

- ✅ All 4 serializers implemented and tested
- ✅ All 12 GameService methods implemented
- ✅ All 6 API routes implemented
- ✅ 52 tests created and passing
- ✅ Zero regressions in existing tests
- ✅ Full documentation created
- ✅ Code review approved
- ✅ Ready for merge to backend-api

## Next Steps

1. Begin Stage 1: NPCAIStateSerializer
2. Follow with DialogueStateSerializer
3. Complete QuestStateSerializer
4. Implement API routes
5. Final testing and documentation
6. Merge to phase-1/backend-api

---

**Branch:** phase-2/npc-ai-serialization  
**Base:** phase-1/backend-api  
**Status:** Ready to begin  
**Start Date:** November 8, 2025

