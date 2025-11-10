# Quest Chains Integration Examples (Phase 3 Stage 3)

Complete guide for integrating quest chains into your game world. Chains allow players to complete multi-stage story arcs with prerequisites, branching paths, and progressive rewards.

## Table of Contents
1. [Basic Chain Progression](#basic-chain-progression)
2. [Chain Dependencies](#chain-dependencies)
3. [Branching Chains](#branching-chains)
4. [Reward Scaling](#reward-scaling)
5. [API Usage Patterns](#api-usage-patterns)
6. [Integration Checklist](#integration-checklist)

---

## 1. Basic Chain Progression

### Concept
Quest chains break lengthy story arcs into stages. Each stage is a complete quest that leads to the next. Players can pause between stages or rush through for time-based bonuses.

### Game World Setup

**Create chain definition in your universe or map JSON:**

```json
{
  "chains": {
    "dragonslayer_quest": {
      "name": "The Dragon Slayer",
      "description": "Face the ancient dragon threatening the realm",
      "stages": [
        {
          "stage_number": 0,
          "name": "Gather Supplies",
          "quest_id": "gather_supplies_01",
          "rewards": {
            "gold": 100,
            "experience": 500,
            "items": ["minor_potion"]
          }
        },
        {
          "stage_number": 1,
          "name": "Scout the Dragon's Lair",
          "quest_id": "scout_lair_01",
          "rewards": {
            "gold": 200,
            "experience": 1000,
            "items": ["map_to_lair"]
          }
        },
        {
          "stage_number": 2,
          "name": "Defeat the Dragon",
          "quest_id": "defeat_dragon_01",
          "rewards": {
            "gold": 500,
            "experience": 2500,
            "items": ["dragon_scales"],
            "title": "Dragon Slayer"
          }
        }
      ],
      "prerequisites": [],
      "difficulty": "normal"
    }
  }
}
```

### Player Progression Workflow

```python
# Initialize chain for player (typically in story event or NPC dialogue)
player.chain_progress["dragonslayer_quest"] = {
    "current_stage": 0,
    "completed_stages": []
}
player.active_chains.append("dragonslayer_quest")

# During gameplay, complete stage 0 quest
# ... player completes "gather_supplies_01" quest ...

# Advance to next stage via API
response = requests.post(
    "http://localhost:5000/api/quest-chains/dragonslayer_quest/advance",
    headers={"Authorization": f"Bearer {session_id}"},
    json={
        "current_stage": 0,
        "next_stage": 1
    }
)
# Response: { "success": true, "advancement": { "success": true, ... } }

# Continue through remaining stages
# Stage 1 -> Stage 2
# Then complete chain via API
response = requests.post(
    "http://localhost:5000/api/quest-chains/dragonslayer_quest/complete",
    headers={"Authorization": f"Bearer {session_id}"}
)
# Response: { "success": true, "completion": { "success": true, "status": "completed", ... } }
```

### Python Game Engine Integration

```python
from src.api.services.game_service import GameService
from src.api.serializers.quest_chains import ChainProgressionSerializer

# Initialize quest chain for player
def start_chain(player, chain_id, universe):
    if chain_id not in universe.chains:
        return {"success": False, "error": "Chain not found"}
    
    player.chain_progress[chain_id] = {
        "current_stage": 0,
        "completed_stages": []
    }
    player.active_chains.append(chain_id)
    
    return {"success": True, "message": f"Chain {chain_id} started"}

# Advance through chain
def progress_chain(player, chain_id, universe):
    game_service = GameService(universe)
    progress = game_service.get_chain_progress(player, chain_id)
    
    if not progress["success"]:
        return progress
    
    current = progress["progress"]["current_stage"]
    next_stage = current + 1
    
    # Verify stage count
    if next_stage >= len(universe.chains[chain_id]["stages"]):
        # Complete chain instead
        return game_service.complete_chain(player, chain_id)
    
    return game_service.advance_chain_stage(player, chain_id, current, next_stage)

# Example story event: Dragon Defeated
class DragonDefeated(Event):
    def process(self, player, game_state):
        # Advance the dragon slayer chain
        progress_chain(player, "dragonslayer_quest", game_state.universe)
        
        # Award stage rewards
        rewards = {
            "gold": 500,
            "experience": 2500,
            "items": ["dragon_scales"]
        }
        
        for gold_amount in [rewards["gold"]]:
            player.gold += gold_amount
        
        return f"You defeated the dragon! Chain progressed."
```

---

## 2. Chain Dependencies

### Concept
Chains can require other chains to be completed first. This gates content appropriately and forces story progression order.

### Setup: Gated Chain

```json
{
  "chains": {
    "recruit_army": {
      "name": "Recruit an Army",
      "description": "Build forces to battle the dragon",
      "stages": [
        {
          "stage_number": 0,
          "name": "Convince the Merchant",
          "quest_id": "convince_merchant_01",
          "prerequisites": [],
          "rewards": { "gold": 100, "experience": 200 }
        },
        {
          "stage_number": 1,
          "name": "Train Soldiers",
          "quest_id": "train_soldiers_01",
          "prerequisites": ["convince_merchant_01"],
          "rewards": { "gold": 200, "experience": 400 }
        }
      ],
      "prerequisites": ["dragonslayer_quest"],
      "difficulty": "hard"
    }
  }
}
```

### Validation Before Starting Chain

```python
def can_start_chain(player, chain_id, universe):
    """Check if player can start this chain."""
    chain = universe.chains.get(chain_id)
    if not chain:
        return False, "Chain not found"
    
    # Check prerequisites
    if chain.get("prerequisites"):
        missing = []
        for prereq in chain["prerequisites"]:
            if prereq not in player.completed_chains:
                missing.append(prereq)
        
        if missing:
            return False, f"Must complete {missing} first"
    
    return True, "Can start chain"

# API example
def get_chain_requirements(player, chain_id, universe):
    """Endpoint: GET /api/quest-chains/{chain_id}/requirements"""
    can_start, reason = can_start_chain(player, chain_id, universe)
    
    if not can_start:
        return {
            "success": False,
            "locked": True,
            "reason": reason
        }
    
    return {
        "success": True,
        "locked": False,
        "chain_id": chain_id,
        "chain_name": universe.chains[chain_id]["name"]
    }
```

### Check Prerequisites via API

```python
# Client code
def unlock_chain(player_session_id, chain_id):
    response = requests.post(
        f"http://localhost:5000/api/quest-chains/{chain_id}/prerequisites",
        headers={"Authorization": f"Bearer {player_session_id}"},
        json={"prerequisites": ["dragonslayer_quest", "recruit_army"]}
    )
    
    result = response.json()
    if result["data"]["all_prerequisites_met"]:
        print(f"✓ {chain_id} now available!")
    else:
        missing = result["data"]["missing_prerequisites"]
        print(f"✗ Still need: {missing}")
```

---

## 3. Branching Chains

### Concept
Some chains diverge into multiple paths based on player choices or reputation. Both paths are valid and lead to different rewards.

### Setup: Branching Quest Chain

```json
{
  "chains": {
    "undead_threat": {
      "name": "The Undead Threat",
      "stages": [
        {
          "stage_number": 0,
          "name": "Discover Undead Plot"
        },
        {
          "stage_number": 1,
          "type": "branch_point",
          "branches": [
            {
              "id": "peaceful_path",
              "name": "Peaceful Resolution",
              "reputation_gates": { "scholar": 50 },
              "next_stages": [2]
            },
            {
              "id": "violent_path",
              "name": "Military Strike",
              "reputation_gates": { "military": 50 },
              "next_stages": [3]
            }
          ]
        },
        {
          "stage_number": 2,
          "name": "Seal the Rift (Peacefully)",
          "rewards": {
            "gold": 100,
            "reputation": { "scholar": 50 }
          }
        },
        {
          "stage_number": 3,
          "name": "Destroy Undead Army",
          "rewards": {
            "gold": 300,
            "reputation": { "military": 50 }
          }
        }
      ],
      "prerequisites": []
    }
  }
}
```

### Accessing Available Branches

```python
from src.api.serializers.quest_chains import ChainBranchSerializer

def get_branch_options(player, chain_id, universe):
    """Get available branches at current stage."""
    chain = universe.chains[chain_id]
    current_stage = player.chain_progress[chain_id]["current_stage"]
    
    stage = chain["stages"][current_stage]
    
    if stage.get("type") != "branch_point":
        return {"success": False, "error": "Not a branch point"}
    
    branch_point = stage
    available = ChainBranchSerializer.get_available_branches(
        player, chain_id, branch_point
    )
    
    return {
        "success": True,
        "branches": [
            {
                "id": b["id"],
                "name": b["name"],
                "available": len(b.get("gates_failed", [])) == 0
            }
            for b in available
        ]
    }

# Usage in story
if get_branch_options(player, "undead_threat", universe)["success"]:
    # Present player with choice
    branches = ...["branches"]
    print(f"Choose your path:")
    for i, b in enumerate(branches):
        status = "✓" if b["available"] else "✗ (Locked)"
        print(f"  {i+1}. {b['name']} {status}")
```

---

## 4. Reward Scaling

### Concept
Rewards scale based on difficulty setting and stage progression speed. Early completion bonuses reward player efficiency.

### Difficulty Multipliers

```python
from src.api.serializers.quest_chains import ChainRewardSerializer

# Multipliers for different difficulties
DIFFICULTY_MULTIPLIERS = {
    "normal": 1.0,
    "hard": 1.5,
    "nightmare": 2.0
}

# Calculate final rewards
def get_chain_rewards(chain_id, difficulty, completion_time_seconds):
    chain = universe.chains[chain_id]
    base_gold = sum(s["rewards"]["gold"] for s in chain["stages"])
    base_xp = sum(s["rewards"]["experience"] for s in chain["stages"])
    
    # Difficulty multiplier
    diff_mult = DIFFICULTY_MULTIPLIERS.get(difficulty, 1.0)
    
    # Speed bonus (completed within time limit)
    time_limit_seconds = 3600  # 1 hour
    speed_bonus = 0.5 if completion_time_seconds < time_limit_seconds else 0
    
    # Final calculation
    final_gold = base_gold * diff_mult * (1 + speed_bonus)
    final_xp = base_xp * diff_mult * (1 + speed_bonus)
    
    return {
        "gold": int(final_gold),
        "experience": int(final_xp),
        "bonus_multiplier": diff_mult * (1 + speed_bonus)
    }

# Example
rewards = get_chain_rewards("dragonslayer_quest", "nightmare", 1800)
# Returns: {"gold": 3000, "experience": 7500, "bonus_multiplier": 3.0}
```

### Stage vs. Chain Completion Rewards

```json
{
  "chains": {
    "epic_quest": {
      "stages": [
        {
          "stage_number": 0,
          "rewards": {
            "gold": 100,
            "experience": 500
          }
        }
      ],
      "completion_rewards": {
        "gold": 1000,
        "experience": 5000,
        "items": ["epic_artifact"],
        "title": "Epic Hero",
        "achievement": "epic_quest_complete"
      }
    }
  }
}
```

### API Reward Query

```python
# Get completion bonus details
response = requests.get(
    "http://localhost:5000/api/quest-chains/epic_quest/rewards",
    headers={"Authorization": f"Bearer {session_id}"}
)

result = response.json()
print(f"Completion Gold Bonus: {result['data']['completion_rewards']['gold']}")
print(f"Speed Multiplier: {result['data']['speed_multiplier']}")
```

---

## 5. API Usage Patterns

### Get All Chains Progress

```python
import requests

session_id = "user_session_12345"
headers = {"Authorization": f"Bearer {session_id}"}

# Get player's progress across all chains
response = requests.get(
    "http://localhost:5000/api/quest-chains/progress",
    headers=headers
)

data = response.json()
if data["success"]:
    all_progress = data["data"]
    print(f"Active Chains: {all_progress['active_chains']}")
    print(f"Completed: {all_progress['completed_chains']}")
    print(f"Overall Progress: {all_progress['total_progress_percentage']}%")
```

### Get Specific Chain Progress

```python
# Get status of one chain
response = requests.get(
    "http://localhost:5000/api/quest-chains/dragonslayer_quest/progress",
    headers=headers
)

progress = response.json()["data"]
print(f"Stage: {progress['current_stage']}")
print(f"Completed: {progress['completed_stages']}")
print(f"Remaining: {progress['stages_remaining']}")
```

### Advance Chain

```python
# Move to next stage
response = requests.post(
    "http://localhost:5000/api/quest-chains/dragonslayer_quest/advance",
    headers=headers,
    json={
        "current_stage": 0,
        "next_stage": 1
    }
)

if response.json()["success"]:
    print("✓ Advanced to Stage 1")
```

### Complete Chain

```python
# Mark entire chain as done
response = requests.post(
    "http://localhost:5000/api/quest-chains/dragonslayer_quest/complete",
    headers=headers
)

if response.json()["success"]:
    data = response.json()["data"]
    print(f"✓ {data['chain_name']} Complete!")
    print(f"  Gold Bonus: {data['completion_rewards']['gold']}")
    print(f"  Title Earned: {data['title_unlocked']}")
```

### Check Prerequisites

```python
# Validate if player can access a chain
response = requests.post(
    "http://localhost:5000/api/quest-chains/recruit_army/prerequisites",
    headers=headers,
    json={"prerequisites": ["dragonslayer_quest"]}
)

check = response.json()["data"]
if check["can_proceed"]:
    print("✓ All requirements met - chain unlocked!")
else:
    print(f"✗ Missing: {check['missing_prerequisites']}")
```

---

## 6. Integration Checklist

### Pre-Implementation
- [ ] Define all quest chains in universe JSON or map files
- [ ] Determine difficulty settings for each chain
- [ ] Design stage progression and rewards
- [ ] Plan prerequisite chains and dependencies
- [ ] Identify branching points if any

### Code Implementation
- [ ] Create story events for each stage completion
- [ ] Implement chain initialization logic
- [ ] Add advancement hooks to quest completion handlers
- [ ] Set up completion rewards and achievements
- [ ] Create NPC dialogue for chain progression

### Testing
- [ ] Test basic chain progression (0 → 1 → 2)
- [ ] Test chain prerequisites blocking access
- [ ] Test branching path selection
- [ ] Test reward scaling by difficulty
- [ ] Test API endpoints with various auth tokens
- [ ] Test concurrent players with different chains

### UI/UX
- [ ] Display chain progress (X of Y stages)
- [ ] Show available branches at branch points
- [ ] Highlight locked chains with reason
- [ ] Display stage rewards before completion
- [ ] Show completion bonus breakdown

### Deployment
- [ ] Verify all chain data in production universe
- [ ] Test legacy saves load correctly
- [ ] Monitor API response times
- [ ] Set up logging for chain events
- [ ] Create admin panel for chain debugging

---

## Example: Complete Mini-Chain

```python
# Full working example: Small Training Chain

chain_definition = {
    "chains": {
        "basic_training": {
            "name": "Basic Training",
            "description": "Learn the basics from the Master",
            "stages": [
                {
                    "stage_number": 0,
                    "name": "Meet the Master",
                    "quest_id": "meet_master",
                    "rewards": {"gold": 50, "experience": 100}
                },
                {
                    "stage_number": 1,
                    "name": "Practice Sword",
                    "quest_id": "practice_sword",
                    "rewards": {"gold": 100, "experience": 250}
                },
                {
                    "stage_number": 2,
                    "name": "Defeat Training Dummy",
                    "quest_id": "defeat_dummy",
                    "rewards": {"gold": 200, "experience": 500}
                }
            ],
            "prerequisites": [],
            "difficulty": "normal",
            "completion_bonus": {
                "gold": 500,
                "experience": 1500,
                "title": "Trained Fighter"
            }
        }
    }
}

# Initialization in story
def start_basic_training(player, universe):
    player.chain_progress["basic_training"] = {
        "current_stage": 0,
        "completed_stages": []
    }
    player.active_chains.append("basic_training")

# Event: After talking to master
class MeetMasterEvent(Event):
    def process(self, player, game_state):
        start_basic_training(player, game_state.universe)
        return "The Master begins your training!"

# Event: After defeating training dummy
class DummyDefeatedEvent(Event):
    def process(self, player, game_state):
        game_service = GameService(game_state.universe)
        # Advance from stage 1 to stage 2
        result = game_service.advance_chain_stage(
            player, "basic_training", 1, 2
        )
        return "You've mastered sword combat!"

# Event: Training complete
class TrainingCompleteEvent(Event):
    def process(self, player, game_state):
        game_service = GameService(game_state.universe)
        result = game_service.complete_chain(player, "basic_training")
        
        if result["success"]:
            player.titles.append("Trained Fighter")
            return "✓ Basic Training Complete! You are now a Trained Fighter."
        
        return "Training still in progress..."
```

---

## Summary

Quest chains provide:
- **Progressive storytelling** through multi-stage arcs
- **Content gating** via prerequisites
- **Player agency** through branching paths
- **Reward scaling** based on difficulty and speed
- **Achievement tracking** for completion milestones
- **Flexible API** for seamless integration

Use these patterns to create engaging, rewarding quest experiences that guide players through your game's narrative!
