# Quest Rewards System - Quick Reference

## How It Plugs Into the Game

```
┌─────────────────────────────────────────────────────────────────┐
│                        GAME LOOP (Current)                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Player Encounters Enemy  →  Combat Happens  →  Player Wins   │
│                                                                 │
│                            (No rewards system)                  │
│                            Game just ends there                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘


┌──────────────────────────────────────────────────────────────────────┐
│                 GAME LOOP (With Quest Rewards)                       │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Player Encounters Enemy  →  Combat  →  Player Wins              │
│                                           │                       │
│                                           ↓                       │
│                                  Complete Quest                   │
│                                           │                       │
│                          ┌────────────────┴──────────────┐        │
│                          ↓                               ↓        │
│                  Calculate Rewards            Distribute Rewards  │
│                  - Base amount               - Gold to inventory  │
│                  - Apply multipliers         - XP to player       │
│                  - Check bonuses             - Items added        │
│                                             - Reputation changed  │
│                          ↓                               ↓        │
│                          └────────────────┬──────────────┘        │
│                                           ↓                       │
│                                  Update Player State              │
│                                  - New level?                    │
│                                  - New skills?                   │
│                                  - Better stats?                 │
│                                           │                       │
│                                           ↓                       │
│                              Return to Game Stronger             │
│                                                                  │
└──────────────────────────────────────────────────────────────────────┘
```

## Concrete Numbers: Single Quest Example

```
Quest: "Defeat the Cave Bat"
Base Rewards: 100 gold, 200 XP

┌─────────────────────────────────────────────────────────────┐
│ If Player Takes EASY Route                                  │
├─────────────────────────────────────────────────────────────┤
│ Multiplier: 0.5x (easy difficulty)                          │
│ Reward: 50 gold, 100 XP                                     │
│ Use case: "Just want to progress fast"                      │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ If Player Takes NORMAL Route (Default)                      │
├─────────────────────────────────────────────────────────────┤
│ Multiplier: 1.0x (normal difficulty)                        │
│ Reward: 100 gold, 200 XP                                    │
│ Use case: "Standard playthrough"                            │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ If Player Takes HARD Route + No Deaths + Bonus Objectives   │
├─────────────────────────────────────────────────────────────┤
│ Multiplier: 1.5x (hard) × 1.2x (no deaths)                  │
│            × 1.25x (bonus) = 2.25x TOTAL                    │
│ Reward: 225 gold, 450 XP                                    │
│ Use case: "Hardcore challenge run, lots of rewards!"        │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ If Player Takes NIGHTMARE Route Perfectly                   │
├─────────────────────────────────────────────────────────────┤
│ Multiplier: 2.0x (nightmare) × 1.2x (no deaths)             │
│            × 1.25x (bonus) = 3.0x TOTAL                     │
│ Reward: 300 gold, 600 XP                                    │
│ Risk: If they die = 0 gold, 0 XP (complete loss!)          │
│ Use case: "Maximum challenge, maximum reward"               │
└─────────────────────────────────────────────────────────────┘
```

## Real Game Example: Chapter 1

```
STORY QUEST: "Clear the Starting Chamber"

Old System (Current):
  1. Player solves puzzle
  2. Wall opens
  3. "Quest complete!"
  4. Nothing else

New System (With Rewards):
  1. Player solves puzzle
  2. Wall opens
  3. Quest rewards calculated:
     ✓ 250 gold (new coins!)
     ✓ 500 XP (significant progress)
     ✓ "Bronze Key" item (new equipment!)
     ✓ +10 reputation with hermit (new relationship!)
  
  4. Player gets stronger:
     ✓ Level 2 → 3 (new HP, attack power)
     ✓ Inventory updated
     ✓ Story NPCs now recognize player differently
  
  5. Player continues game MORE POWERFUL
```

## How Leveling Works

```
XP Formula: 100 XP = 1 Level

Quest 1: 200 XP → Player at 200 XP
         200 / 100 = Level 2 ✓

Quest 2: 300 XP → Player at 500 XP
         500 / 100 = Level 5 ✓
         
         Each level gained:
         +5 HP
         +2 Attack Power
         +1 Defense

Quest 3 (Perfect): 600 XP → Player at 1100 XP
         1100 / 100 = Level 11 ✓
         
         Level 10: "Power Attack" skill unlocked!
         Level 15: "Defensive Stance" skill unlocked!
         Level 20: "Execute" skill unlocked!
```

## API Endpoints: What the Game Calls

```
Get Rewards Preview (Before Committing):
GET /api/quests/{quest_id}/rewards
Response: "This quest will give you 100 gold and 200 XP"

Complete a Quest (Do it):
POST /api/quests/{quest_id}/complete
Body: {difficulty: "hard", no_deaths: true, bonus: true}
Response: Complete status + new player stats + level ups

Award Gold (Testing/Admin):
POST /api/quests/award-gold
Body: {amount: 500}
Response: New gold total

Award Experience (Testing/Admin):
POST /api/quests/award-experience
Body: {amount: 1000}
Response: New XP + any level ups + skill unlocks

Award Items (Testing/Admin):
POST /api/quests/award-item
Body: {item_id: "bronze_key", item_name: "Bronze Key"}
Response: Item added to inventory

Award Reputation (Testing/Admin):
POST /api/quests/award-reputation
Body: {npc_id: "hermit", npc_name: "Old Hermit", amount: 50}
Response: Reputation updated

Check Progression:
GET /api/quests/progression
Response: {level: 5, xp: 850, quests_completed: 3, gold: 2500}
```

## Connection to Future Features

```
STAGE 1 (NOW): Quest Rewards
  └─ Players get gold, XP, items, reputation

STAGE 2 (NEXT): Reputation System
  └─ Uses reputation from Stage 1
  └─ Unlocks dialogue based on reputation
  └─ Makes NPCs react to player actions

STAGE 3: Quest Chains
  └─ Chains require completion of earlier quests
  └─ Story progression through quests
  └─ Multi-quest storylines

STAGE 4: NPC Schedules
  └─ NPCs move based on time
  └─ Quest availability changes
  └─ Time-sensitive rewards

STAGE 5: Dynamic Dialogue
  └─ AI remembers what quests you did
  └─ Generates contextual responses
  └─ References your reputation history
```

## The Core Benefit

```
Without Quest Rewards:
  Player: "I completed a quest... now what?"
  Game: "Um... you keep playing? Nothing changed though."

With Quest Rewards:
  Player: "I completed a quest!"
  Game: "Great! You're now level 3, gained 300 gold,
         got a new sword, and the blacksmith now likes you.
         You've unlocked a new questline!"
  Player: "Cool! Let's keep going!"

= MEANINGFUL PROGRESSION
```

---

**File**: `QUEST_REWARDS_INTEGRATION_EXAMPLES.md` for detailed scenarios

