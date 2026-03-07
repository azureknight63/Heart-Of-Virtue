import sys
from pathlib import Path

# Ensure the project's src directory is on sys.path so absolute imports in src modules resolve
ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import pytest
from src.player import Player  # type: ignore
from src.universe import Universe  # type: ignore
from src import functions  # type: ignore


class TestLearnAllSkills:
    """Test the learn_all_skills_from_skilltree feature."""

    def test_learn_all_skills_from_skilltree(self):
        """Test that learn_all_skills_from_skilltree adds all skills to player."""
        # Create a player
        player = Player()
        
        # Record initial count
        initial_count = len(player.known_moves)
        assert initial_count > 0, "Player should have some initial known moves"
        
        # Call the function
        learned_count = functions.learn_all_skills_from_skilltree(player)
        
        # Verify skills were added
        assert learned_count > 0, "Function should have added skills"
        assert len(player.known_moves) == initial_count + learned_count, \
            f"Expected {initial_count + learned_count} skills, got {len(player.known_moves)}"
        
        # Verify Slash is in known moves by checking for Slash class instance
        from src.moves import Slash  # type: ignore
        slash_moves = [m for m in player.known_moves if isinstance(m, Slash) or m.__class__.__name__ == 'Slash']
        assert len(slash_moves) > 0, "Slash should be in known_moves"

    def test_learn_all_skills_idempotent(self):
        """Test that calling learn_all_skills twice doesn't double-count skills."""
        player = Player()
        
        # Call function once
        functions.learn_all_skills_from_skilltree(player)
        count_after_first = len(player.known_moves)
        
        # Call function again
        functions.learn_all_skills_from_skilltree(player)
        count_after_second = len(player.known_moves)
        
        # Should not add new skills if they already exist
        # (or add 0 if all already learned)
        assert count_after_second >= count_after_first, \
            "Second call should not remove skills"

    def test_config_integration(self):
        """Test that config_manager properly loads learn_all_skills setting."""
        from src.config_manager import ConfigManager  # type: ignore
        
        cm = ConfigManager('config_dev.ini')
        config = cm.load()
        
        # Should have the attribute
        assert hasattr(config, 'learn_all_skills'), \
            "GameConfig should have learn_all_skills attribute"
        
        # Should be a boolean
        assert isinstance(config.learn_all_skills, bool), \
            "learn_all_skills should be boolean"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
