"""
CONCRETE INTEGRATION EXAMPLES: Quest Rewards System with Base Game

This document shows exactly how the quest rewards system integrates with
the existing Heart of Virtue game using real examples from the codebase.
"""

# ============================================================================
# EXAMPLE 1: Simple Quest Reward in the Game Flow
# ============================================================================

"""
SCENARIO: Player defeats a Cave Bat and completes a "Clear the Cave" quest

Current Game Flow (Without Rewards):
1. Player encounters Cave Bat (NPC enemy)
2. Combat happens
3. Player wins
4. Bat dies, drops some gold
5. Game says "Quest complete!" 
6. That's it. No rewards system.

With Quest Rewards System:
1. Player encounters Cave Bat
2. Combat happens (difficulty: normal)
3. Player wins with no deaths
4. complete_quest() is called with:
   - quest_id: "cave_bat_clear"
   - difficulty: "normal" (they didn't skip it, didn't do nightmare)
   - no_deaths: True (they didn't die)
   - bonus_objectives_completed: False (e.g., no "don't use items" bonus)
   
5. Quest Rewards System Calculates:
   - Base rewards from quest definition:
     * Gold: 500
     * XP: 250
     * Items: ["bronze_dagger"]
     * Reputation: {"cave_guide": 25}
   
   - Applies multiplier:
     * difficulty "normal" = 1.0x
     * no_deaths = 1.2x
     * bonus_objectives = 1.0x (not completed)
     * TOTAL MULTIPLIER: 1.0 × 1.2 = 1.2x
   
   - Final rewards:
     * Gold: 500 × 1.2 = 600 (20% bonus for no deaths!)
     * XP: 250 × 1.2 = 300
     * Items: ["bronze_dagger"]
     * Reputation: {"cave_guide": 25}

6. Player's State Updates:
   - Gold: 1000 → 1600
   - Experience: 500 → 800
   - Level check: 800 XP / 100 per level = Level 8
   - Inventory: +bronze_dagger
   - Reputation: cave_guide +25 (now friendly with guide)

7. API Response:
{
  "success": true,
  "quest_completion": {
    "rewards_received": {
      "gold": 600,
      "experience": 300,
      "items_received": ["bronze_dagger"],
      "reputation_gained": {"cave_guide": 25}
    },
    "player_state_after": {
      "gold": 1600,
      "experience": 800,
      "level": 8,
      "inventory_count": 5,
      "inventory_weight": 45
    },
    "level_up": {
      "old_level": 7,
      "new_level": 8,
      "stat_increases": {
        "hp": 5,
        "attack": 2,
        "defense": 1
      },
      "new_skills_unlocked": []  // No skills at level 8
    },
    "conditions_applied": ["no_deaths_bonus"]
  }
}
"""

# ============================================================================
# EXAMPLE 2: Nightmare Difficulty vs Easy Difficulty
# ============================================================================

"""
SCENARIO: Same "Clear the Cave" quest, but different approaches

Approach 1: Easy Difficulty
- Player: "I want to skip this and move on, set to easy"
- Rewards multiplier: 0.5x
- Base gold: 500 × 0.5 = 250
- Base XP: 250 × 0.5 = 125
- Why? Easy = quick, less challenging

Approach 2: Normal Difficulty (Default)
- Rewards multiplier: 1.0x
- Base gold: 500 × 1.0 = 500
- Base XP: 250 × 1.0 = 250
- Why? Balanced, default difficulty

Approach 3: Hard Difficulty
- Player: "I want a challenge"
- Rewards multiplier: 1.5x
- Base gold: 500 × 1.5 = 750
- Base XP: 250 × 1.5 = 375
- Why? Riskier, more rewarding

Approach 4: Nightmare Difficulty (Hardcore)
- Player: "I want MAXIMUM rewards"
- Rewards multiplier: 2.0x
- Base gold: 500 × 2.0 = 1000 (!!!)
- Base XP: 250 × 2.0 = 500 (!!!)
- But... if they die, they get NOTHING
- Why? High risk, high reward

API Call for Nightmare:
POST /api/quests/cave_bat_clear/complete
{
  "difficulty": "nightmare",
  "no_deaths": true,
  "bonus_objectives_completed": true
}

Result with all bonuses:
- nightmare (2.0x) × no_deaths (1.2x) × bonus (1.25x) = 3.0x
- Gold: 500 × 3.0 = 1500
- XP: 250 × 3.0 = 750
- Could jump 2-3 levels from one quest!

This rewards hardcore players while allowing casual play.
"""

# ============================================================================
# EXAMPLE 3: Integration with Existing Story Events
# ============================================================================

"""
In src/story/ch01.py, after defeating enemies in the cave:

BEFORE (Current Code):
--------
def process(self):
    # Player defeats Rock Rumbler
    cprint("You defeated the Rock Rumbler!", 'green')
    player.gold += 50  # Just give gold directly
    # That's it. No progression.

AFTER (With Quest Rewards):
--------
def process(self):
    # Player defeats Rock Rumbler
    cprint("You defeated the Rock Rumbler!", 'green')
    
    # Call the API to complete the quest
    result = game_service.complete_quest(
        player,
        quest_id="ch01_rock_rumbler_defeat",
        difficulty="normal",
        no_deaths=player.death_count == 0,
        bonus_objectives_completed=False
    )
    
    # Display results to player
    rewards = result['quest_completion']['rewards_received']
    cprint(f"You earned {rewards['gold']} gold!", 'yellow')
    cprint(f"You earned {rewards['experience']} experience!", 'cyan')
    
    if rewards['items_received']:
        cprint(f"You found: {', '.join(rewards['items_received'])}", 'magenta')
    
    if 'level_up' in result['quest_completion']:
        level_info = result['quest_completion']['level_up']
        cprint(f"LEVEL UP! {level_info['old_level']} → {level_info['new_level']}", 'green')
        cprint(f"HP +{level_info['stat_increases']['hp']}", 'yellow')
        cprint(f"ATK +{level_info['stat_increases']['attack']}", 'yellow')
        cprint(f"DEF +{level_info['stat_increases']['defense']}", 'yellow')
"""

# ============================================================================
# EXAMPLE 4: How Reputation Affects Future NPCs
# ============================================================================

"""
SCENARIO: Cave Guide NPC - Before and After Quest

BEFORE completing "Clear the Cave" quest:
- Player has no reputation with cave_guide
- When talking to cave_guide:
  - Dialogue: "This cave is dangerous. I wouldn't go in if I were you."
  - Quest offer: LOCKED (requires 0 reputation)
  - Options: Limited dialogue choices

AFTER completing "Clear the Cave" quest:
- complete_quest() adds reputation:
  "reputation_gained": {"cave_guide": 25}
- Player reputation with cave_guide: 0 → 25 (friendly)

When talking to cave_guide AGAIN:
- Dialogue: "You cleared the cave? You're tougher than you look!"
- Quest offer: UNLOCKED (now has 25+ reputation)
- New dialogue option: "Tell me about the deeper caves..."
  (This would be locked at 0 reputation)

In Phase 2 (Reputation System), we'll add:
if player.reputation.get('cave_guide', 0) >= 25:
    dialogue_options.append("About those deeper caves...")
    
This creates dynamic dialogue based on reputation!
"""

# ============================================================================
# EXAMPLE 5: Real Game Integration - Complete Flow
# ============================================================================

"""
FULL GAME SESSION EXAMPLE:

Session Start:
- Player: Level 1, 0 XP, 100 gold, 0 reputation with all NPCs

Step 1: Fight Cave Bat (Normal, No Deaths)
POST /api/quests/cave_bat_defeat/complete
{
  "difficulty": "normal",
  "no_deaths": true
}
Result:
- Gold: 100 → 170 (70 gold reward)
- XP: 0 → 50
- Level: 1 → 1 (needs 100 XP)
- Reputation: bat_trainer +10

Step 2: Fight Cave Bat Again (Hard Difficulty)
POST /api/quests/cave_bat_defeat/complete
{
  "difficulty": "hard",
  "no_deaths": false  // They took damage
}
Result:
- Gold: 170 → 295 (125 gold: 100 × 1.5 hard multiplier)
- XP: 50 → 137 (87 XP: 200 × 1.5 hard)
- Level: 1 → 1 (now at 137/200 to level 2)
- Reputation: bat_trainer +15 (total +25, friendly!)

Step 3: Get Level-Up Milestone
Need 63 more XP. Do a quest worth 100+ XP.
GET /api/quests/progression
{
  "level": 1,
  "experience": 137,
  "quests_completed": 2,
  "gold": 295,
  "playtime_hours": 0.5
}

Step 4: Complete Level-Up Quest
POST /api/quests/clear_south_passage/complete
{
  "difficulty": "normal",
  "no_deaths": true,
  "bonus_objectives_completed": true
}
Result with (1.0 × 1.2 × 1.25 = 1.5x multiplier):
- XP gained: 500 × 1.5 = 750
- Total XP: 137 + 750 = 887
- Level calculation: 887 / 100 = Level 8 (!)
- LEVEL UP CHAIN:
  * Level 2: +5 HP, +2 ATK, +1 DEF
  * Level 3: +5 HP, +2 ATK, +1 DEF
  * Level 4: +5 HP, +2 ATK, +1 DEF
  * Level 5: +5 HP, +2 ATK, +1 DEF (UNLOCK "Power Attack" skill!)
  * Level 6: +5 HP, +2 ATK, +1 DEF
  * Level 7: +5 HP, +2 ATK, +1 DEF
  * Level 8: +5 HP, +2 ATK, +1 DEF

Response:
{
  "success": true,
  "quest_completion": {
    "level_up": {
      "old_level": 1,
      "new_level": 8,
      "stat_increases": {
        "hp": 35,      // 5 × 7 levels
        "attack": 14,  // 2 × 7 levels
        "defense": 7   // 1 × 7 levels
      },
      "new_skills_unlocked": ["Power Attack"]  // At level 5!
    }
  }
}

Player State After This Quest:
- Level: 1 → 8 (HUGE jump from one perfect quest!)
- HP: 50 → 85 (+35)
- ATK: 10 → 24 (+14)
- DEF: 5 → 12 (+7)
- Gold: 295 → 1045 (+750 from quest)
- Quests completed: 3
- Skills: ["Power Attack"] (NEW!)

Now they're powerful enough to tackle the next story area!
"""

# ============================================================================
# EXAMPLE 6: How Quest Rewards Work with the REST API
# ============================================================================

"""
CLIENT SIDE (Web/Mobile/CLI):

1. Check what a quest offers BEFORE committing:
   GET /api/quests/cave_bat_defeat/rewards
   {
     "rewards": {
       "gold": 100,
       "experience": 200,
       "items": [{"item_id": "bat_fang", "name": "Bat Fang"}],
       "reputation": {"bat_trainer": 10}
     }
   }

2. Decide difficulty and do the quest:
   POST /api/quests/cave_bat_defeat/complete
   {
     "difficulty": "hard",
     "no_deaths": true,
     "bonus_objectives_completed": false
   }
   
   Gets back:
   {
     "success": true,
     "quest_completion": {
       "rewards_received": {
         "gold": 150,
         "experience": 300,
         "items_received": ["bat_fang"],
         "reputation_gained": {"bat_trainer": 10}
       },
       "player_state_after": {
         "gold": 1150,
         "experience": 850,
         "level": 8,
         "inventory_count": 5,
         "inventory_weight": 42
       },
       "level_up": {
         "old_level": 7,
         "new_level": 8,
         "stat_increases": {"hp": 5, "attack": 2, "defense": 1},
         "new_skills_unlocked": []
       },
       "conditions_applied": ["no_deaths_bonus"]
     }
   }

3. Refresh player UI:
   - Show new gold amount
   - Show level up animation
   - Show new HP/ATK/DEF
   - Show new items in inventory
   - Update quest log

4. Check progression:
   GET /api/quests/progression
   {
     "progression": {
       "level": 8,
       "experience": 850,
       "quests_completed": 1,
       "gold": 1150,
       "playtime_hours": 2.5,
       "achievements_unlocked": 5
     }
   }
"""

# ============================================================================
# EXAMPLE 7: Connection to Phase 3's Other Systems
# ============================================================================

"""
How Quest Rewards connects to the rest of Phase 3:

QUEST REWARDS (Stage 1) ← You are here
    ↓
REPUTATION SYSTEM (Stage 2)
    - Uses reputation from quest rewards
    - Unlocks reputation-gated dialogue
    - Affects NPC availability
    
QUEST CHAINS (Stage 3)
    - Chains require completing prerequisite quests
    - Quest rewards matter (need XP to be strong enough)
    - Reputation gates chain progression
    
NPC SCHEDULES (Stage 4)
    - Quest availability based on time/NPC location
    - Reward distribution timing
    - Schedule-specific quest variations
    
DIALOGUE CONTEXT (Stage 5)
    - Generate contextual dialogue based on quest history
    - Remember what quests player completed
    - Reference reputation history in dialogue
    - LLM uses this context for dynamic responses

EXAMPLE: Quest Chain with LLM Dialogue
---------
Player completes "Defeat Cave Bats" (Stage 1 - This System!)
  → Gains reputation with cave_guide (+25)
  
cave_guide reputation unlocks quest chain (Stage 3 - Chains!)
  → "Explore the Deep Caves" quest becomes available
  
When talking to cave_guide (Stage 5 - Dialogue!)
  → System builds context:
     - Player has completed 3 quests
     - Player has reputation +25 with cave_guide
     - Player is level 8
     - Player completed "Defeat Cave Bats"
  
  → LLM generates dialogue:
     "Welcome back! I heard you cleared out those cave bats.
      You're ready for something bigger. The deep caves need
      someone with your skill level. I can pay well..."
      
  (Not generic dialogue - it's aware of what you did!)
"""

# ============================================================================
# SUMMARY: Why This Matters
# ============================================================================

"""
The Quest Rewards System is the FOUNDATION for everything else:

1. Without it, quests don't matter → no progression
2. With it, quests drive the game forward
3. Difficulty scaling rewards risk/reward decisions
4. Reputation from quests gates future content
5. Leveling from quests creates character growth
6. Context for future dialogue and interactions

The base game needed this structure to make quests meaningful.
Now quests are the core progression mechanic!
"""

