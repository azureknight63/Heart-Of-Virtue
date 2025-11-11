# Stage 5: Dialogue Context System - Implementation Plan

## Overview
Implement a comprehensive dialogue context management system that tracks conversation state, player choices, NPC responses, and story progression through dialogues. This stage builds on the NPC Availability system (Stage 4) to provide rich, stateful conversations.

## Architecture

### Core Concept
Dialogue Context System = NPC dialogue state + conversation history + branching paths + story impact

**Key Features:**
- Conversation history tracking (who said what, when)
- Dialogue branching based on story state and player choices
- NPC personality/tone influence on responses
- Consequences system (choices affect NPC availability, reputation, quest progress)
- Dialogue node system with conditions and effects

### Design Pattern (Following Stages 1-4)
```
Stage 5 Components (same as Stages 1-4):
- Serializers (5-6 classes): Transform dialogue data
- GameService Methods (5 methods): Business logic
- API Endpoints (5 endpoints): HTTP routes
- Tests (26 + 22 + 28 = 76 total)
```

## Implementation Roadmap

### Phase 5A: Serializers (26 tests)
**5-6 Serializer Classes:**

1. **DialogueNodeSerializer** (dialogues as tree nodes)
   - node_id, text, speaker, condition_check
   - choices (branching paths)
   - effects (story changes on selection)
   - npc_tone/personality modifiers

2. **ConversationHistorySerializer** (track past dialogues)
   - conversation_id, npc_id, player_id, timestamp
   - exchanged_messages list
   - choices_made array
   - outcome/consequence

3. **DialogueChoiceSerializer** (player interaction points)
   - choice_id, text, condition_check
   - target_node_id (where it leads)
   - story_gate_impact (story switches changed)
   - reputation_impact (NPC reputation delta)

4. **DialogueConditionSerializer** (when dialogue available)
   - Required story gates
   - NPC reputation threshold
   - Player level/stats
   - Previous choice history

5. **DialogueEffectSerializer** (consequences)
   - story_switch changes
   - reputation_delta
   - quest_progress_update
   - item_reward
   - unlock_location

6. **DialogueContextSerializer** (aggregate)
   - current_node, conversation_history
   - available_choices (filtered by conditions)
   - conversation_state (started/ongoing/completed)

### Phase 5B: GameService Methods (22 tests)
**5 Methods in GameService:**

1. **start_dialogue(player, npc_id, dialogue_id)**
   - Validate NPC available (uses Stage 4)
   - Load dialogue tree
   - Return initial node + available choices
   - Create conversation_history record

2. **get_dialogue_node(player, node_id)**
   - Load dialogue node
   - Filter choices by player conditions
   - Check if node already visited
   - Return formatted response

3. **select_dialogue_choice(player, conversation_id, choice_id)**
   - Validate choice exists and is available
   - Apply effects (story gates, reputation, items)
   - Move to next node
   - Update conversation history
   - Return next node

4. **get_conversation_history(player, npc_id)**
   - Retrieve all past conversations with NPC
   - Show conversation branches taken
   - Display reputation changes over time
   - Useful for player reference

5. **get_available_dialogues(player, npc_id)**
   - List all possible dialogues with NPC
   - Filter by story gates/conditions
   - Show dialogue starts available
   - Return dialogue descriptions

### Phase 5C: API Endpoints (28 tests)
**5 Endpoints:**

1. **POST /api/npcs/<npc_id>/dialogue/start**
   - Body: { dialogue_id }
   - Returns: Current dialogue node + choices
   - Auth: Bearer token required

2. **GET /api/dialogue/<node_id>**
   - Returns: Full node data + filtered choices
   - Auth: Bearer token required

3. **POST /api/dialogue/choose**
   - Body: { conversation_id, choice_id }
   - Returns: Next node + effects applied
   - Auth: Bearer token required

4. **GET /api/npcs/<npc_id>/dialogue/history**
   - Returns: Conversation history with NPC
   - Query params: limit, offset
   - Auth: Bearer token required

5. **GET /api/npcs/<npc_id>/dialogue/available**
   - Returns: Available dialogues list
   - Filtered by player conditions
   - Auth: Bearer token required

### Test Structure (76 total)
- Serializers: 26 tests (6 classes × 4-5 tests each)
- GameService: 22 tests (5 methods × 4-5 tests each)
- Routes: 28 tests (5 endpoints × 5-6 tests each)
  - Auth requirements
  - Data validation
  - Effect application
  - Error handling
  - Edge cases

## Data Model Example

```json
{
  "dialogue_tree": {
    "greeting_001": {
      "node_id": "greeting_001",
      "text": "Greetings, traveler! What brings you to my shop?",
      "speaker": "merchant_npc",
      "npc_tone": "friendly",
      "choices": [
        {
          "choice_id": "greeting_001_a",
          "text": "I'm looking for potions.",
          "target_node": "merchant_potions_001",
          "conditions": { "story_gates": [] },
          "effects": { "reputation_delta": 5 }
        },
        {
          "choice_id": "greeting_001_b",
          "text": "Just passing through.",
          "target_node": "merchant_goodbye_001",
          "conditions": { "story_gates": [] },
          "effects": { "reputation_delta": 0 }
        }
      ]
    }
  },
  "conversation_history": {
    "conversation_001": {
      "conversation_id": "conversation_001",
      "npc_id": "merchant_npc",
      "player_id": "player_001",
      "started_at": "2025-11-10T10:00:00Z",
      "nodes_visited": ["greeting_001", "merchant_potions_001"],
      "choices_made": ["greeting_001_a"],
      "status": "ongoing"
    }
  }
}
```

## Dependencies
- Builds on Stage 4: NPC Availability (uses npc_id, availability checks)
- Uses existing player story system
- Integrates with reputation system (Stage 2)
- Affects quest progression (Stage 3)

## Success Criteria
- ✅ 76 total tests (100% passing)
- ✅ All 5 endpoints fully functional
- ✅ Dialogue branching working
- ✅ Consequences system active
- ✅ Conversation history tracking
- ✅ Integration with existing systems

## Timeline Estimate
- Serializers: 3-4 hours
- GameService: 2-3 hours
- Routes: 2-3 hours
- Testing: 4-5 hours
- **Total: 12-15 hours**

## Integration Checklist
- [ ] Dialogue nodes stored in resources/dialogue/ (JSON files)
- [ ] Conversation history persisted in player save
- [ ] Story gate impacts working
- [ ] Reputation changes applied
- [ ] Quest progress updates triggered
- [ ] NPC availability integration complete
- [ ] OpenAPI schema updated
- [ ] Swagger UI reflects new endpoints
