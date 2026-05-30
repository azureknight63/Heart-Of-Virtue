"""
Tests for Ch02KingSlimeMemoryFlash guard conditions and story flag behavior.

Covers the fix for the MemoryFlash multi-fire bug (PR #202):
- check_conditions must bail early when needs_input=True (mid-flash)
- check_conditions must bail early when king_slime_flash_fired story flag is set
- process('continue') must persist the king_slime_flash_fired flag
- process(None) must NOT set the flag (only the completion pass does)
"""

import unittest
from unittest.mock import Mock, patch
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


# ch02 checks `i.__class__.__name__ == "MineralFragment"` — the class name must match exactly.
MineralFragment = type('MineralFragment', (), {})


class TestCh02KingSlimeMemoryFlashGuards(unittest.TestCase):

    def setUp(self):
        self.tile = Mock()
        self.tile.events_here = []

        self.player = Mock()
        self.player.universe = Mock()
        self.player.universe.story = {}
        self.player.inventory = []

    def _make_flash(self):
        from story.ch02 import Ch02KingSlimeMemoryFlash
        flash = Ch02KingSlimeMemoryFlash(player=self.player, tile=self.tile)
        self.tile.events_here.append(flash)
        return flash

    # ------------------------------------------------------------------
    # check_conditions guards
    # ------------------------------------------------------------------

    def test_check_conditions_skips_when_needs_input_true(self):
        """Mid-flash (needs_input=True) must not re-queue the flash."""
        flash = self._make_flash()
        flash.needs_input = True
        flash.pass_conditions_to_process = Mock()

        flash.check_conditions()

        flash.pass_conditions_to_process.assert_not_called()

    def test_check_conditions_skips_when_story_flag_set(self):
        """After king_slime_flash_fired is set, check_conditions must not fire."""
        self.player.universe.story["king_slime_flash_fired"] = "1"
        flash = self._make_flash()
        flash.pass_conditions_to_process = Mock()

        flash.check_conditions()

        flash.pass_conditions_to_process.assert_not_called()

    def test_check_conditions_removes_self_when_story_flag_set(self):
        """When the story flag guard trips, the event removes itself from tile.events_here."""
        self.player.universe.story["king_slime_flash_fired"] = "1"
        flash = self._make_flash()
        self.assertIn(flash, self.tile.events_here)

        flash.check_conditions()

        self.assertNotIn(flash, self.tile.events_here)

    def test_check_conditions_fires_with_mineral_fragment(self):
        """check_conditions calls pass_conditions_to_process when a MineralFragment is in inventory."""
        self.player.inventory = [MineralFragment()]
        flash = self._make_flash()
        flash.pass_conditions_to_process = Mock()

        flash.check_conditions()

        flash.pass_conditions_to_process.assert_called_once()

    def test_check_conditions_does_not_fire_without_mineral_fragment(self):
        """check_conditions does not fire when no MineralFragment is in inventory."""
        class IronSword:
            pass
        self.player.inventory = [IronSword()]
        flash = self._make_flash()
        flash.pass_conditions_to_process = Mock()

        flash.check_conditions()

        flash.pass_conditions_to_process.assert_not_called()

    # ------------------------------------------------------------------
    # process() story flag
    # ------------------------------------------------------------------

    @patch('src.story.effects.memory_border')
    @patch('src.story.effects.cprint')
    @patch('src.story.effects.time.sleep')
    def test_process_completion_sets_story_flag(self, _sleep, _cprint, _border):
        """process('continue') must set king_slime_flash_fired='1' in player.universe.story."""
        flash = self._make_flash()

        flash.process("continue")

        self.assertEqual(self.player.universe.story.get("king_slime_flash_fired"), "1")

    @patch('src.story.effects.memory_border')
    @patch('src.story.effects.cprint')
    @patch('src.story.effects.time.sleep')
    def test_process_first_pass_does_not_set_story_flag(self, _sleep, _cprint, _border):
        """process(None) (first display pass) must NOT set king_slime_flash_fired."""
        flash = self._make_flash()

        flash.process(None)

        self.assertNotIn("king_slime_flash_fired", self.player.universe.story)


if __name__ == "__main__":
    unittest.main()
