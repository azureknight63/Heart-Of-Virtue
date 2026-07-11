
import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add src to path

from src.story.effects import WhisperingStatue
import src.functions as functions

class TestWhisperingStatue(unittest.TestCase):
    def setUp(self):
        self.player = MagicMock()
        self.tile = MagicMock()
        self.event = WhisperingStatue(self.player, self.tile)

    @patch('src.story.effects.cprint')
    @patch('src.story.effects.time.sleep')
    def test_correct_answer(self, mock_sleep, mock_cprint):
        # Structured protocol: the player's choice arrives via user_input.
        self.event.process(user_input="1")

        # Correct answer ("1") spawns Gold; no Slime ambush.
        self.tile.spawn_item.assert_called_with('Gold', amt=500)
        self.tile.spawn_npc.assert_not_called()
        # Event completes and no longer needs input.
        self.assertTrue(self.event.completed)
        self.assertFalse(self.event.needs_input)

    @patch('src.story.effects.cprint')
    @patch('src.story.effects.time.sleep')
    def test_incorrect_answer(self, mock_sleep, mock_cprint):
        self.event.process(user_input="2")

        # Wrong answer spawns a Slime; no Gold reward.
        self.tile.spawn_npc.assert_called_with('Slime')
        self.tile.spawn_item.assert_not_called()

    @patch('src.story.effects.cprint')
    @patch('src.story.effects.time.sleep')
    def test_no_input_defaults_to_correct_answer(self, mock_sleep, mock_cprint):
        # When called without user_input, the riddle defaults to the safe "1".
        self.event.process()
        self.tile.spawn_item.assert_called_with('Gold', amt=500)
        self.tile.spawn_npc.assert_not_called()

if __name__ == '__main__':
    unittest.main()
