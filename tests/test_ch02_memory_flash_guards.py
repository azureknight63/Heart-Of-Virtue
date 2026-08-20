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
        from src.story.ch02 import Ch02KingSlimeMemoryFlash
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
    @patch('src.story.effects.time.sleep')
    def test_process_completion_sets_story_flag_and_finishes(self, _sleep, _border):
        """process('continue') closes the flash: flag set, no further input wanted."""
        from src.narration import capture_narration

        flash = self._make_flash()
        flash.process(None)  # first pass must happen before the completion pass
        with capture_narration() as msgs:
            flash.process("continue")

        self.assertEqual(self.player.universe.story.get("king_slime_flash_fired"), "1")
        self.assertFalse(flash.needs_input)
        # The closing pass emits the chrome rule, not another copy of the memory.
        self.assertTrue(any(m.get("type") == "memory_chrome" for m in msgs))
        self.assertFalse(any("BOOM." == m.get("text") for m in msgs))

    @patch('src.story.effects.memory_border')
    @patch('src.story.effects.time.sleep')
    def test_process_first_pass_shows_the_memory_and_waits(self, _sleep, _border):
        """The display pass narrates the memory and pauses — without arming the flag.

        The flag is what stops the flash re-firing, so setting it on the display
        pass would be indistinguishable from "already fired" if the player never
        clicked Continue.
        """
        from src.narration import capture_narration

        flash = self._make_flash()
        with capture_narration() as msgs:
            flash.process(None)

        self.assertNotIn("king_slime_flash_fired", self.player.universe.story)
        self.assertTrue(flash.needs_input)
        self.assertEqual(
            [o["value"] for o in flash.input_options], ["continue"]
        )

        # Jean's solo cast is staged, and his introspective beats are thoughts.
        begin = next(m for m in msgs if m.get("type") == "conversation_begin")
        self.assertEqual([c["id"] for c in begin["cast"]], ["Jean"])
        thoughts = {m["text"]: m for m in msgs if m.get("thought")}
        self.assertIn("Pain — sudden, immediate, real.", thoughts)
        self.assertEqual(thoughts["emptiness."]["emotion"], "sad")
        self.assertTrue(all(m["speaker"] == "Jean" for m in thoughts.values()))
        # The API description mirrors the narrated prose for non-staged clients.
        self.assertIn("BOOM.", flash.description)


if __name__ == "__main__":
    unittest.main()
