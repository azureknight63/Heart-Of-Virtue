# Stage 2: Reputation System - Integration Examples

This document provides concrete examples of how the reputation system integrates with the base game and connects to other Phase 3 systems.

## Table of Contents
1. Simple Reputation Flow
2. Reputation-Based Content Gating
3. Story Event Integration
4. Reputation & Dialogue System
5. NPC Relationship Progression
6. API Usage Patterns

---

## 1. Simple Reputation Flow

### Example: Meeting an NPC

```python
from src.player import Player
from src.api.services.game_service import GameService

# Player encounters the Blacksmith
player = game_session.player
game_service = GameService(universe)

# Initial state - no prior reputation
current_rep = player.reputation.get("blacksmith", 0)
# Output: 0 (neutral)

# Player completes a quest for the blacksmith
game_service.update_reputation(
    player, "blacksmith", 30, "quest_complete"
)
# Blacksmith reputation is now 30 (favorable)

# Check current relationship
relationship = game_service.get_npc_relationship(player, "blacksmith")
print(f"Attitude: {relationship['relationship']['attitude']}")
# Output: "favorable" (emoji: 🙂)

# Can now access favorable dialogue
dialogue_check = game_service.check_dialogue_available(
    player, "blacksmith", "quest_offer"
)
# Output: available = True
```

### Example: Reputation Decline

```python
# Player insults the Blacksmith during dialogue
game_service.update_reputation(
    player, "blacksmith", -20, "dialogue_choice"
)
# Reputation: 30 -> 10

relationship = game_service.get_npc_relationship(player, "blacksmith")
print(f"Attitude: {relationship['relationship']['attitude']}")
# Output: "neutral" (emoji: 😐)

# Some dialogue becomes unavailable at neutral
dialogue_check = game_service.check_dialogue_available(
    player, "blacksmith", "special_dialogue"
)
# Output: available = False, locked_reason = "Blacksmith doesn't want to talk about that..."
```

---

## 2. Reputation-Based Content Gating

### Dialogue Gating

```python
# Thresholds define when dialogue is accessible:
# - greeting_friendly: >= 25 reputation
# - quest_offer: >= 0 reputation
# - special_dialogue: >= 50 reputation
# - secret_revealed: >= 75 reputation
# - betrayal_available: <= -50 reputation

# Example: Secret dialogue unlocks at +75 reputation
game_service.update_reputation(player, "wizard", 75, "major_quest_complete")

secret_available = game_service.check_dialogue_available(
    player, "wizard", "secret_revealed"
)
print(secret_available["available"])  # True
print(secret_available["locked_reason"])  # None
```

### Quest Gating

```python
# Quest types have different reputation requirements:
# - normal_quest: >= 0 reputation
# - important_quest: >= 25 reputation
# - difficult_quest: >= 50 reputation
# - secret_quest: >= 75 reputation

# Example: Secret quest only available to trusted NPCs
current_rep = player.reputation.get("dragon_slayer", 10)

# Try to get secret quest at +10 reputation
quest_check = game_service.check_quest_available(
    player, "dragon_slayer", "secret_quest"
)
print(quest_check["available"])  # False
print(quest_check["locked_reason"])
# Output: "Dragon Slayer Guild doesn't trust you with this quest..."

# After proving yourself, reputation increases to 80
game_service.update_reputation(
    player, "dragon_slayer", 70, "defeated_elder_dragon"
)

# Now secret quest is available
quest_check = game_service.check_quest_available(
    player, "dragon_slayer", "secret_quest"
)
print(quest_check["available"])  # True
```

---

## 3. Story Event Integration

### Dynamic Event Triggers

```python
from src.events import Event

class Ch02_Blacksmith_Betrayal(Event):
    """Triggers if player reputation with blacksmith falls below -50."""
    
    def check_conditions(self):
        blacksmith_rep = self.player.reputation.get("blacksmith", 0)
        # Event only triggers at hostile level
        return blacksmith_rep <= -50
    
    def process(self):
        """The blacksmith refuses to sell to you."""
        self.player.current_text = (
            "The Blacksmith turns his back on you.\n"
            '"I\'ll never work with someone like you," he mutters.'
        )
        
        # Set betrayed flag for future reference
        game_service.set_relationship_flag(
            self.player, "blacksmith", "betrayed", True
        )
        
        return True  # Event completed


class Ch02_Merchant_Alliance(Event):
    """Triggers if player reaches +50 reputation with merchant."""
    
    def check_conditions(self):
        merchant_rep = self.player.reputation.get("merchant", 0)
        return merchant_rep >= 50
    
    def process(self):
        """The merchant offers special discounts."""
        self.player.current_text = (
            "The Merchant grins widely.\n"
            '"You\'ve been a great customer. I have a special offer for you..."'
        )
        
        # Set alliance flag
        game_service.set_relationship_flag(
            self.player, "merchant", "alliance", True
        )
        
        # Give reputation bonus item access
        return True


# In chapter initialization
def initialize_chapter_2():
    """Set up Chapter 2 events."""
    # Automatically triggers when conditions met
    player.events_here.append(
        Ch02_Blacksmith_Betrayal(player, current_tile, repeat=True)
    )
    player.events_here.append(
        Ch02_Merchant_Alliance(player, current_tile, repeat=True)
    )
```

---

## 4. Reputation & Dialogue System (Future Integration with Stage 5)

### Context-Aware Dialogue

```python
# When displaying NPC dialogue, include reputation context

def display_merchant_dialogue(player):
    """Display different dialogue based on reputation."""
    
    merchant_rep = player.reputation.get("merchant", 0)
    relationship = game_service.get_npc_relationship(player, "merchant")
    
    if merchant_rep >= 75:
        greeting = "Ah, my dearest friend! How wonderful to see you!"
        # Full access to special items and quests
        dialogue_options = [
            "Browse exclusive wares",
            "Hear a secret",
            "Invest in my business",
            "Leave"
        ]
    elif merchant_rep >= 50:
        greeting = "Welcome back, dear friend!"
        # Normal access
        dialogue_options = [
            "Buy items",
            "Special quest",
            "Leave"
        ]
    elif merchant_rep >= 0:
        greeting = "Hello there. What do you need?"
        # Limited access
        dialogue_options = [
            "Browse",
            "Leave"
        ]
    elif merchant_rep > -25:
        greeting = "I'm not sure I trust you..."
        dialogue_options = [
            "Explain yourself",
            "Leave"
        ]
    else:
        # Hostile or betrayed
        greeting = "Get out of my shop!"
        dialogue_options = [
            "Try to reconcile",
            "Leave"
        ]
    
    # Display
    print(f"{greeting}")
    print(f"Attitude: {relationship['relationship']['emoji']} {relationship['relationship']['attitude']}")
    for i, option in enumerate(dialogue_options, 1):
        print(f"{i}. {option}")
    
    # In Stage 5, this could feed into LLM dialogue generation
    # with reputation as context parameter
```

---

## 5. NPC Relationship Progression

### Multi-Stage Reputation Arc

```python
# Example: Romance storyline (using reputation flags)

def progress_romance(player, npc_id="healer"):
    """Example of multi-stage relationship progression."""
    
    current_rep = player.reputation.get(npc_id, 0)
    game_service = GameService(universe)
    
    # Stage 1: First meeting (rep 0-20)
    if 0 <= current_rep < 20:
        print("The Healer greets you warmly.")
    
    # Stage 2: Growing friendship (rep 20-50)
    elif 20 <= current_rep < 50:
        # Unlock romance flag opportunity
        if game_service.check_dialogue_available(player, npc_id, "special_dialogue"):
            print("The Healer smiles at you with newfound warmth...")
            # Option to set romance flag here
    
    # Stage 3: Romance unlocked (rep 50+)
    elif current_rep >= 50:
        # Check if romance flag already set
        flags = game_service.get_npc_relationship(player, npc_id)
        
        if flags["flags"]["flags"].get("romance"):
            print("The Healer gazes at you with obvious affection...")
            # Romance storyline available
        else:
            print("The Healer cares deeply for you...")
            # Option to initiate romance
            game_service.set_relationship_flag(
                player, npc_id, "romance", True
            )
```

### Complex Relationship Scenarios

```python
# Example: Alliance with former enemies

game_service.update_reputation(player, "dragon_slayer", 60, "mutual_enemy_defeated")

# After reaching friendly status, can unlock alliance quest
if player.reputation["dragon_slayer"] >= 50:
    # Show alliance option
    print("The Dragon Slayer extends their hand...")
    game_service.set_relationship_flag(
        player, "dragon_slayer", "alliance", True
    )
    
    # This opens up new story paths
    # - Combined quests with dragon slayer
    # - Access to legendary weapons
    # - Story branches unavailable to solo players
```

---

## 6. API Usage Patterns

### Getting All Relationships

```http
GET /api/reputation/player
Authorization: Bearer session_id
```

Response:
```json
{
  "success": true,
  "data": {
    "total_npcs": 8,
    "relationships": {
      "merchant": {
        "npc_id": "merchant",
        "npc_name": "Merchant",
        "reputation": 60,
        "attitude": "friendly",
        "emoji": "😊",
        "trust_level": "High Trust",
        "locked_dialogue": false
      },
      "blacksmith": {
        "npc_id": "blacksmith",
        "npc_name": "Blacksmith",
        "reputation": -40,
        "attitude": "hostile",
        "emoji": "😠",
        "trust_level": "Distrusting",
        "locked_dialogue": true
      }
    },
    "friendly_npcs": 5,
    "hostile_npcs": 1,
    "highest_reputation": 80,
    "lowest_reputation": -50
  }
}
```

### Updating Reputation

```http
PUT /api/reputation/npc/merchant
Authorization: Bearer session_id
Content-Type: application/json

{
  "amount": 15,
  "reason": "quest_complete"
}
```

Response:
```json
{
  "success": true,
  "data": {
    "npc_id": "merchant",
    "npc_name": "Merchant",
    "old_reputation": 45,
    "new_reputation": 60,
    "change": 15,
    "direction": "positive",
    "reason": "quest_complete",
    "old_attitude": "favorable",
    "new_attitude": "friendly",
    "attitude_changed": true
  }
}
```

### Setting Relationship Flags

```http
POST /api/reputation/npc/merchant/flag/alliance
Authorization: Bearer session_id
Content-Type: application/json

{
  "value": true
}
```

Response:
```json
{
  "success": true,
  "data": {
    "success": true,
    "npc_id": "merchant",
    "flag": "alliance",
    "old_value": false,
    "new_value": true,
    "changed": true
  }
}
```

### Checking Content Availability

```http
GET /api/reputation/dialogue/merchant/secret_revealed
Authorization: Bearer session_id
```

Response:
```json
{
  "success": true,
  "data": {
    "dialogue_node": "secret_revealed",
    "available": true,
    "locked_reason": null
  }
}
```

---

## Connection to Phase 3 Systems

### Reputation → Quest Chains (Stage 3)

```python
# Quest chains can be locked behind reputation
class Ch03_Alliance_Quest_Chain:
    """Multi-stage quest chain unlocked by merchant alliance."""
    
    def __init__(self, player):
        self.player = player
        self.stages = [
            {"name": "Fetch goods", "rep_required": 50},
            {"name": "Deliver personally", "rep_required": 60},
            {"name": "Business deal", "rep_required": 75},
        ]
    
    def get_available_stages(self):
        """Return stages player can access."""
        current_rep = self.player.reputation.get("merchant", 0)
        return [s for s in self.stages if current_rep >= s["rep_required"]]
```

### Reputation → NPC Schedules (Stage 4)

```python
# NPC availability might depend on reputation
def is_npc_available(npc_id, player):
    """Check if NPC is available to talk."""
    reputation = player.reputation.get(npc_id, 0)
    
    # At very low reputation, NPC might avoid you
    if reputation <= -75:
        return False  # NPC won't talk to you
    
    # Otherwise, check schedule (Stage 4)
    return check_npc_schedule(npc_id)
```

### Reputation → Dialogue Generation (Stage 5)

```python
# Reputation as context for LLM dialogue generation
def generate_dialogue(npc_id, player, dialogue_prompt):
    """Generate NPC dialogue with reputation context."""
    
    reputation = player.reputation.get(npc_id, 0)
    relationship = get_npc_relationship(player, npc_id)
    flags = get_relationship_flags(player, npc_id)
    
    # Pass as context to LLM
    context = {
        "reputation": reputation,
        "attitude": relationship["attitude"],
        "trust_level": relationship["trust_level"],
        "flags": flags,
        "dialogue_locks": serialize_dialogue_locks(player, npc_id, AVAILABLE_DIALOGUES),
    }
    
    # LLM generates dialogue consistent with relationship
    # e.g., "kind and warm" at +80 vs "cold and distant" at -40
    return llm_client.generate_dialogue(
        npc_id=npc_id,
        prompt=dialogue_prompt,
        context=context,
    )
```

---

## Summary

The Reputation System provides:

- **Dynamic Content**: Dialogue and quests gate based on reputation thresholds
- **Story Progression**: Events trigger based on relationship milestones
- **Long-term Consequences**: Reputation persists and affects future interactions
- **Branching Narratives**: Different story paths available at different reputation levels
- **Character Agency**: Player choices (dialogue, quests) directly impact relationships

This creates an interconnected game world where relationships matter and player decisions have lasting consequences.
