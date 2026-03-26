
import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from story.effects import WhisperingStatue
import functions

class TestWhisperingStatue(unittest.TestCase):
    def setUp(self):
        self.player = MagicMock()
        self.tile = MagicMock()
        self.event = WhisperingStatue(self.player, self.tile)

    @patch('functions.await_input')
    @patch('story.effects.cprint')
    @patch('story.effects.input')
    @patch('story.effects.time.sleep')
    @patch('builtins.print')
    def test_correct_answer(self, mock_print, mock_sleep, mock_input, mock_cprint, mock_await):
        # Setup input for correct answer ("1")
        mock_input.return_value = "1"

        # Run process
        self.event.process()

        # Verify interactions
        mock_input.assert_called_once()

        # Verify success outcome
        # Should spawn Gold (as per my implementation)
        self.tile.spawn_item.assert_called_with('Gold', amt=500)

        # Verify failure outcome did NOT happen
        self.tile.spawn_npc.assert_not_called()

    @patch('functions.await_input')
    @patch('story.effects.cprint')
    @patch('story.effects.input')
    @patch('story.effects.time.sleep')
    @patch('builtins.print')
    def test_incorrect_answer(self, mock_print, mock_sleep, mock_input, mock_cprint, mock_await):
        # Setup input for incorrect answer ("2")
        mock_input.return_value = "2"

        # Run process
        self.event.process()

        # Verify interactions
        mock_input.assert_called_once()

        # Verify failure outcome
        # Should spawn Slime
        self.tile.spawn_npc.assert_called_with('Slime')

        # Verify success outcome did NOT happen
        self.tile.spawn_item.assert_not_called()

if __name__ == '__main__':
    unittest.main()
