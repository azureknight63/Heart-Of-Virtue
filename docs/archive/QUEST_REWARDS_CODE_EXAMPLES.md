"""
CODE EXAMPLE: How the Base Game Would Use Quest Rewards System

This shows actual code patterns for integrating with the game.
"""

# ============================================================================
# EXAMPLE 1: Story Event with Quest Rewards
# ============================================================================

# In src/story/ch01.py (MODIFIED to use quest rewards)

from src.api.services.game_service import GameService


class Ch01_Rock_Rumbler_Defeated(Event):
    """
    Event triggered when player defeats the Rock Rumbler in chapter 1.
    
    BEFORE: Just gave player 50 gold
    AFTER: Uses quest rewards system
    """
    
    def __init__(self, player, tile, game_service=None, params=None, repeat=False):
        super().__init__(name='Ch01_Rock_Rumbler_Defeated', player=player, tile=tile)
        self.game_service = game_service
        self.repeat = repeat
        
    def check_conditions(self):
        """Check if Rock Rumbler has been defeated"""
        # NPC is dead = quest condition met
        rumbler = self.tile.npcs_here[0] if self.tile.npcs_here else None
        if rumbler and rumbler.health <= 0:
            self.pass_conditions_to_process()
    
    def process(self):
        """Complete the quest and show rewards"""
        from neotermcolor import cprint
        
        # Remove the defeated NPC
        self.tile.npcs_here.clear()
        
        # Complete the quest using GameService
        if self.game_service:
            result = self.game_service.complete_quest(
                player=self.player,
                quest_id="ch01_defeat_rock_rumbler",
                difficulty="normal",
                no_deaths=self.player.death_count == 0,
                bonus_objectives_completed=False
            )
            
            if result['success']:
                quest_comp = result['quest_completion']
                rewards = quest_comp['rewards_received']
                
                # Display rewards to player
                cprint("\n" + "="*50, 'magenta')
                cprint("QUEST COMPLETE: Defeat the Rock Rumbler", 'yellow')
                cprint("="*50, 'magenta')
                
                cprint(f"\n✓ Gold earned: {rewards['gold']}", 'yellow')
                cprint(f"✓ Experience: {rewards['experience']} XP", 'cyan')
                
                if rewards['items_received']:
                    cprint(f"✓ Items found:", 'green')
                    for item in rewards['items_received']:
                        cprint(f"  - {item}", 'green')
                
                if rewards['reputation_gained']:
                    cprint(f"✓ Reputation changed:", 'blue')
                    for npc_id, change in rewards['reputation_gained'].items():
                        npc_name = self._get_npc_name(npc_id)
                        relationship = "+" if change > 0 else ""
                        cprint(f"  - {npc_name}: {relationship}{change}", 'blue')
                
                # Show level up if it happened
                if 'level_up' in quest_comp:
                    level_up = quest_comp['level_up']
                    old_lvl = level_up['old_level']
                    new_lvl = level_up['new_level']
                    
                    cprint(f"\n🎉 LEVEL UP! {old_lvl} → {new_lvl}", 'green')
                    
                    stats = level_up['stat_increases']
                    cprint(f"  HP  +{stats['hp']}", 'yellow')
                    cprint(f"  ATK +{stats['attack']}", 'yellow')
                    cprint(f"  DEF +{stats['defense']}", 'yellow')
                    
                    if level_up['new_skills_unlocked']:
                        cprint(f"  🌟 New Skills: {', '.join(level_up['new_skills_unlocked'])}", 'magenta')
                
                cprint("\n" + "="*50 + "\n", 'magenta')
        else:
            # Fallback: old system (no GameService)
            cprint("You defeated the Rock Rumbler!", 'green')
            self.player.gold += 50


# ============================================================================
# EXAMPLE 2: Combat Victory with Quest Rewards
# ============================================================================

# In src/combat.py (MODIFIED to use quest rewards)

class Combat:
    """Combat system - MODIFIED"""
    
    def end_combat(self, game_service=None):
        """Handle end of combat"""
        winner = self.determine_winner()
        
        if winner == "player":
            # Player won! Award rewards
            rewards = self._calculate_combat_rewards()
            
            if game_service:
                # Use quest rewards system if available
                result = game_service.award_experience(
                    self.player,
                    rewards['experience']
                )
                
                result = game_service.award_gold(
                    self.player,
                    rewards['gold']
                )
                
                cprint(f"Victory! +{rewards['gold']} gold, +{rewards['experience']} XP", 'green')
                
                if 'level_up' in result.get('experience_update', {}):
                    level_info = result['experience_update']['level_up']
                    cprint(f"LEVEL UP! {level_info['old_level']} → {level_info['new_level']}", 'green')
            else:
                # Old system: direct modification
                self.player.gold += rewards['gold']
                self.player.experience += rewards['experience']
        else:
            # Player lost
            cprint("You were defeated!", 'red')


# ============================================================================
# EXAMPLE 3: Quest Hub NPC offering quests with previews
# ============================================================================

# In src/npc.py (MODIFIED to show quest rewards)

class QuestHubNPC:
    """An NPC that offers quests"""
    
    def __init__(self, name, game_service=None):
        self.name = name
        self.game_service = game_service
        self.quests = [
            "clear_cave",
            "defeat_bat_swarm",
            "find_ancient_artifact"
        ]
    
    def show_quest_details(self, quest_id):
        """Show player what they'll get for completing a quest"""
        if not self.game_service:
            print(f"Quest: {quest_id}")
            return
        
        # Get the rewards preview
        result = self.game_service.get_quest_rewards(self.player, quest_id)
        
        if result['success']:
            rewards = result['rewards']['rewards']
            
            print(f"\n{'='*50}")
            print(f"QUEST: {result['rewards']['quest_title']}")
            print(f"{'='*50}")
            print(f"\nRewards:")
            print(f"  • Gold: {rewards['gold']}")
            print(f"  • Experience: {rewards['experience']} XP")
            print(f"  • Items: {len(rewards['items'])} item(s)")
            print(f"  • Reputation: {len(rewards['reputation'])} NPC(s) affected")
            print(f"\nDifficulty: {rewards['conditions']['difficulty']}")
            print(f"{'='*50}\n")
            
            response = input("Accept this quest? (yes/no): ")
            return response.lower() == 'yes'
        
        return False


# ============================================================================
# EXAMPLE 4: Game initialization with GameService
# ============================================================================

# In src/game.py (MODIFIED to use GameService)

from src.api.services.game_service import GameService
from src.universe import Universe
from src.player import Player


class Game:
    """Main game class"""
    
    def __init__(self):
        self.universe = Universe()
        self.player = Player()
        
        # Initialize GameService for quest rewards
        self.game_service = GameService(self.universe)
        
        # Pass GameService to story events
        self._setup_story_events()
    
    def _setup_story_events(self):
        """Initialize story events with GameService"""
        # When adding events to tiles, pass the game_service
        tile = self.universe.get_tile(0, 0)
        
        from src.story.ch01 import Ch01_Rock_Rumbler_Defeated
        event = Ch01_Rock_Rumbler_Defeated(
            player=self.player,
            tile=tile,
            game_service=self.game_service  # ← Pass it here!
        )
        tile.events_here.append(event)
    
    def run_game_loop(self):
        """Main game loop"""
        while True:
            # Process events
            for event in self.universe.current_tile.events_here:
                if event.check_conditions():
                    event.process()  # Uses GameService internally!
            
            # ... rest of game loop ...


# ============================================================================
# EXAMPLE 5: CLI Menu showing progression
# ============================================================================

# In src/interface.py (MODIFIED)

def show_player_status(player, game_service=None):
    """Show player status including progression"""
    from neotermcolor import cprint
    
    print("\n" + "="*60)
    cprint(f"{'CHARACTER STATUS':^60}", 'cyan')
    print("="*60)
    
    cprint(f"Name: {player.name}", 'white')
    cprint(f"Level: {player.level}", 'yellow')
    cprint(f"Health: {player.health}/{player.max_health}", 'green')
    cprint(f"Attack: {player.attack}", 'red')
    cprint(f"Defense: {player.defense}", 'blue')
    cprint(f"\nGold: {player.gold}", 'yellow')
    cprint(f"Experience: {player.experience} XP", 'cyan')
    
    # Show progression if GameService available
    if game_service:
        prog = game_service.get_player_progression(player)
        if prog['success']:
            progression = prog['progression']
            cprint(f"\nQuests Completed: {progression['quests_completed']}", 'magenta')
            cprint(f"Playtime: {progression['playtime_hours']:.1f} hours", 'blue')
    
    print("="*60 + "\n")


# ============================================================================
# EXAMPLE 6: Saving/Loading with Rewards Data
# ============================================================================

# In src/functions.py (MODIFIED)

def save_player_with_rewards(player, filename):
    """Save player including quest rewards data"""
    import pickle
    
    save_data = {
        'player': player,
        'level': player.level,
        'experience': player.experience,
        'gold': player.gold,
        'completed_quests': player.completed_quests,
        'reputation': player.reputation,
        'completed_skills': player.completed_skills,
        'timestamp': __import__('datetime').datetime.now()
    }
    
    with open(filename, 'wb') as f:
        pickle.dump(save_data, f)


def load_player_with_rewards(filename):
    """Load player including quest rewards data"""
    import pickle
    
    with open(filename, 'rb') as f:
        save_data = pickle.load(f)
    
    player = save_data['player']
    # All quest data automatically restored:
    # - player.level
    # - player.experience
    # - player.gold
    # - player.completed_quests
    # - player.reputation
    # - player.completed_skills
    
    return player


# ============================================================================
# SUMMARY: Integration Points
# ============================================================================

"""
The quest rewards system integrates at these points:

1. STORY EVENTS (Ch01_Rock_Rumbler_Defeated, etc.)
   → After event completion, call game_service.complete_quest()
   → Display rewards to player
   → Player stats automatically updated

2. COMBAT SYSTEM
   → After victory, call game_service.award_experience()
   → Call game_service.award_gold()
   → Handle level ups

3. NPC DIALOGUE
   → Use game_service.get_quest_rewards() to preview
   → Show reputation changes
   → Quest availability based on reputation

4. PLAYER PROGRESSION
   → game_service.get_player_progression() for stats
   → Level-ups trigger skill unlocks
   → Stats affect combat calculations

5. SAVE/LOAD SYSTEM
   → Player.level, experience, reputation, quests auto-saved
   → Restore full progression state on load

6. USER INTERFACE
   → Display level, XP, gold prominently
   → Show quest completion rewards
   → Show progression stats

The GameService is just a thin wrapper - the game code stays mostly the same!
"""

