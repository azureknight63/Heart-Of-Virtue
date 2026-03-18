# M2 Phase 3: Advanced NPC & Quest Features (Extended)

## Overview

**Phase 3 Extended** implements advanced features building on Phase 4-5 systems:
- Quest reward distribution (items, gold, XP, reputation)
- NPC relationship tracking and dynamic reputation
- Quest chains and multi-quest storylines
- Time-based NPC schedules and availability
- LLM-ready dialogue context system
- Dynamic dialogue generation (optional AI integration)

**Estimated Duration**: 12-16 hours
**Base Branch**: phase-1/backend-api
**Feature Branch**: phase-3/advanced-features (current)

## Architecture Overview

### Core Systems

#### 1. Quest Rewards
- Distribute items, gold, experience points
- Track reward conditions (difficulty, time limits)
- Update player inventory/stats after completion

#### 2. Reputation System
- Track reputation with NPCs (-100 to +100)
- Manage relationship attitudes (friendly, neutral, hostile)
- Store special flags (betrayed, romance, alliance, etc.)
- Affect dialogue options and quest availability

#### 3. Quest Chains
- Multi-quest storylines with dependencies
- Sequential objectives across quests
- Chain-level rewards
- Prerequisite validation

#### 4. NPC Schedules
- Time-based NPC locations
- Availability tracking
- Day/night cycle integration
- Quest availability based on schedule

#### 5. Dialogue Context
- Build context for LLM-driven dialogue
- Track conversation history
- Consider player reputation/relationships
- Generate contextual responses

## Implementation Stages

### Stage 1: Quest Rewards System (3-4 hours)

**Serializers**:
- `QuestRewardSerializer` - Quest reward data
- `RewardDistributionSerializer` - Distributed rewards
- `PlayerProgressSerializer` - XP/level progression

**GameService Methods**:
```python
get_quest_rewards(quest_id) -> Dict
distribute_quest_rewards(player, quest_id) -> Dict
award_experience(player, xp_amount) -> Dict
award_gold(player, gold_amount) -> Dict
award_reputation(player, npc_id, amount) -> Dict
add_quest_item(player, item_id) -> Dict
```

**Routes**:
```
POST /api/quests/<quest_id>/complete
  - Complete quest and distribute rewards
GET /api/quests/<quest_id>/rewards
  - Preview quest rewards
```

**Tests**: 25+ unit and integration tests

### Stage 2: Reputation System (3-4 hours)

**Serializers**:
- `NPCRelationshipSerializer` - NPC relationship data
- `PlayerReputationSerializer` - Player reputation state
- `RelationshipEventSerializer` - Relationship changes

**GameService Methods**:
```python
get_player_reputation(player) -> Dict
get_npc_relationship(player, npc_id) -> Dict
update_relationship(player, npc_id, change) -> Dict
set_relationship_flag(player, npc_id, flag, value) -> Dict
get_available_quests_for_reputation(player, npc_id) -> List
check_dialogue_locked(player, npc_id, dialogue_node) -> bool
```

**Routes**:
```
GET /api/player/reputation
  - Get all reputation scores
GET /api/npc/<npc_id>/relationship
  - Get specific relationship
PUT /api/npc/<npc_id>/relationship
  - Update relationship (admin/testing)
```

**Tests**: 30+ unit and integration tests

### Stage 3: Quest Chains (2-3 hours)

**Serializers**:
- `QuestChainSerializer` - Chain structure and metadata
- `ChainProgressSerializer` - Player progress in chain
- `DependencyValidator` - Quest prerequisite validation

**GameService Methods**:
```python
get_quest_chain(chain_id) -> Dict
get_available_quests(player, filter_type="all") -> List
validate_quest_prerequisites(player, quest_id) -> Tuple[bool, str]
complete_chain_objective(player, chain_id, quest_id) -> Dict
get_chain_progress(player, chain_id) -> Dict
```

**Routes**:
```
GET /api/quests/chains
  - List all chains
GET /api/quests/chains/<chain_id>
  - Get chain with progress
GET /api/quests/available
  - Get available quests with dependency check
```

**Tests**: 20+ unit and integration tests

### Stage 4: NPC Schedules (2-3 hours)

**Serializers**:
- `NPCScheduleSerializer` - NPC schedule data
- `ScheduleStateSerializer` - Current schedule state
- `TimeStateSerializer` - In-game time state

**GameService Methods**:
```python
get_npc_schedule(npc_id) -> Dict
get_npc_current_location(npc_id, game_time) -> Dict
check_npc_availability(npc_id, game_time) -> bool
get_available_npcs(game_time) -> List
update_game_time(hours) -> Dict
get_game_time() -> Dict
```

**Routes**:
```
GET /api/npc/<npc_id>/schedule
  - Get NPC's schedule
GET /api/npc/available
  - Get currently available NPCs
POST /api/game/time
  - Update game time
GET /api/game/time
  - Get current game time
```

**Tests**: 20+ unit and integration tests

### Stage 5: Dialogue Context & Generation (3-4 hours)

**Serializers**:
- `DialogueContextSerializer` - Context for dialogue
- `DialogueGenerationRequestSerializer` - LLM request format
- `DialogueResponseCacheSerializer` - Cache dialogue responses

**Services**:
- `DialogueContextBuilder` - Build context from game state
- `DialogueGeneratorService` (LLM wrapper) - Call LLM API
- `DialogueResponseCache` - Cache generated responses

**GameService Methods**:
```python
get_dialogue_context(player, npc_id) -> Dict
generate_dialogue_response(context, player_choice) -> Dict
cache_dialogue_response(npc_id, context_hash, response) -> bool
get_cached_response(npc_id, context_hash) -> Optional[Dict]
build_dialogue_options(context) -> List
```

**Routes**:
```
GET /api/npc/<npc_id>/dialogue/context
  - Get dialogue context for generation
POST /api/npc/<npc_id>/dialogue/generate
  - Generate dialogue (with LLM)
POST /api/npc/<npc_id>/dialogue/cache
  - Cache dialogue responses (admin)
GET /api/npc/<npc_id>/dialogue/cache
  - Get cache stats
```

**Tests**: 25+ unit and integration tests (with mock LLM)

### Stage 6: Integration & Testing (2-3 hours)

**Integration Tests**: 40+ tests covering:
- Complete quest reward flow
- Reputation affecting dialogue
- Chain progression with rewards
- Schedule-based availability
- Dialogue generation with context

**Documentation**:
- Inline code documentation
- M2_PHASE3_COMPLETE.md
- API endpoint guide

**Verification**:
- 150+ total new tests
- 100% pass rate
- Zero regressions
- Performance acceptable

## Data Models

```python
# Quest Reward
{
  "quest_id": "quest_001",
  "rewards": {
    "gold": 100,
    "experience": 250,
    "items": [
      {"item_id": "sword_001", "quantity": 1}
    ],
    "reputation": {
      "NPC1": 10,
      "NPC2": -5
    }
  },
  "conditions": {
    "difficulty": "normal",
    "time_limit": 3600,
    "no_deaths": True
  }
}

# NPC Relationship
{
  "npc_id": "NPC1",
  "reputation_score": 45,  # -100 to +100
  "attitude": "friendly",
  "dialogues_completed": 12,
  "quests_completed": 5,
  "special_flags": {
    "betrayed": False,
    "romance": False,
    "allied": True
  }
}

# Quest Chain
{
  "chain_id": "ch01",
  "name": "The Lost Artifact",
  "quests": ["quest_001", "quest_002", "quest_003"],
  "dependencies": {
    "quest_002": ["quest_001"],
    "quest_003": ["quest_002"]
  },
  "rewards": {
    "gold": 500,
    "experience": 1000
  }
}

# NPC Schedule
{
  "npc_id": "NPC1",
  "schedule": {
    "Monday": {
      "06:00": "home",
      "09:00": "tavern",
      "12:00": "shop",
      "18:00": "tavern",
      "22:00": "home"
    },
    "Tuesday": {
      "06:00": "home",
      "08:00": "training_grounds",
      "14:00": "tavern",
      "22:00": "home"
    }
  },
  "availability": {
    "available_daytime": True,
    "available_nighttime": False,
    "holiday_closed": True
  }
}

# Dialogue Context
{
  "npc_id": "NPC1",
  "player_name": "Jean",
  "reputation": 45,
  "attitude": "friendly",
  "previous_dialogue": [
    {"speaker": "npc", "text": "Hello there..."},
    {"speaker": "player", "text": "I need help"}
  ],
  "current_quests": ["quest_001"],
  "completed_quests": ["quest_001"],
  "location": "tavern",
  "time_of_day": "evening",
  "npc_mood": "happy"
}
```

## Files to Create

### Stage 1
- `src/api/serializers/quest_rewards.py` (300+ lines)
- `tests/api/test_quest_rewards_serializer.py` (250+ lines)

### Stage 2
- `src/api/serializers/relationships.py` (350+ lines)
- `tests/api/test_relationships_serializer.py` (250+ lines)

### Stage 3
- `src/api/serializers/quest_chains.py` (250+ lines)
- `tests/api/test_quest_chains_serializer.py` (200+ lines)

### Stage 4
- `src/api/serializers/npc_schedules.py` (250+ lines)
- `tests/api/test_npc_schedules_serializer.py` (200+ lines)

### Stage 5
- `src/api/serializers/dialogue_context.py` (250+ lines)
- `src/api/services/dialogue_generator.py` (300+ lines)
- `tests/api/test_dialogue_generator.py` (250+ lines)

### Stage 6
- `tests/api/test_advanced_features_integration.py` (400+ lines)
- `M2_PHASE3_COMPLETE.md` (documentation)

## Files to Modify

- `src/api/services/game_service.py` (+500+ lines, 30+ methods)
- `src/api/routes/npc.py` (+200+ lines, 8+ routes)
- `src/api/services/validators.py` (+50+ lines, 3+ validators)
- `src/api/services/__init__.py` (exports)
- `src/api/routes/__init__.py` (already updated)
- `src/api/app.py` (already registered)

## Testing Strategy

### Unit Tests
- Stage 1: 25+ tests (rewards, items, gold, XP, reputation)
- Stage 2: 30+ tests (reputation tracking, attitudes, flags)
- Stage 3: 20+ tests (chains, dependencies, prerequisites)
- Stage 4: 20+ tests (schedules, availability, time)
- Stage 5: 25+ tests (context building, LLM mock, caching)

### Integration Tests (Stage 6)
- 40+ end-to-end tests
- Multi-feature workflows
- Error scenarios
- Edge cases

### Total Target
- **New Tests**: 180+
- **Pass Rate**: 100%
- **Execution Time**: ~40-50s

## Success Criteria

✅ All quest rewards distributed correctly
✅ Reputation affects dialogue options
✅ Quest chains validate prerequisites
✅ NPC schedules functional
✅ Dialogue context builds properly
✅ 180+ new tests, all passing
✅ Zero regressions
✅ Full documentation
✅ LLM integration optional but working

## Timeline Estimate

| Stage | Effort | Timeline |
|-------|--------|----------|
| 1. Rewards | 3-4h | Day 1 |
| 2. Reputation | 3-4h | Day 1-2 |
| 3. Chains | 2-3h | Day 2 |
| 4. Schedules | 2-3h | Day 2 |
| 5. Dialogue | 3-4h | Day 2-3 |
| 6. Integration | 2-3h | Day 3 |
| **Total** | **15-21h** | **~3 days** |

## Ready to Begin

**Status**: ✅ Branch created and ready
**Branch**: phase-3/advanced-features
**Base**: phase-1/backend-api
**Next**: Begin Stage 1 (Quest Rewards)

---

Phase 3 Extended Plan ready for implementation ✅

