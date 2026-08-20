"""Behaviour tests for the WhisperingStatue riddle event.

The statue is driven entirely by the structured interaction protocol — the
player's choice arrives as ``user_input`` and the event answers with state
changes (a Gold spawn or a scripted Slime ambush) plus narration. There is no
``input()`` left in the engine, so these tests exercise the real path.
"""

import unittest
from unittest.mock import MagicMock, patch

from src.narration import capture_narration
from src.story.effects import WhisperingStatue


class TestWhisperingStatue(unittest.TestCase):
    def setUp(self):
        self.player = MagicMock()
        self.player.name = "Jean"
        self.tile = MagicMock()
        self.tile.events_here = []
        self.event = WhisperingStatue(self.player, self.tile)
        self.tile.events_here.append(self.event)
        sleep_patcher = patch('src.story.effects.time.sleep')
        sleep_patcher.start()
        self.addCleanup(sleep_patcher.stop)

    def _run(self, **kwargs):
        with capture_narration() as msgs:
            self.event.process(**kwargs)
        return msgs

    def test_riddle_is_presented_with_three_distinct_choices(self):
        """The prompt and its options are what the client renders."""
        self.assertEqual(
            self.event.input_options,
            [
                {"value": "1", "label": "A River"},
                {"value": "2", "label": "The Wind"},
                {"value": "3", "label": "A Shadow"},
            ],
        )
        self.assertEqual(self.event.get_input_options(), self.event.input_options)
        self.assertIn("mouth but never speak", self.event.get_input_prompt())
        self.assertIn("Jean", self.event.description)

    def test_correct_answer(self):
        msgs = self._run(user_input="1")

        # Correct answer ("1") spawns Gold; no Slime ambush.
        self.tile.spawn_item.assert_called_once_with('Gold', amt=500)
        self.tile.spawn_npc.assert_not_called()
        # Event completes, no longer needs input, and retires from the tile.
        self.assertTrue(self.event.completed)
        self.assertFalse(self.event.needs_input)
        self.assertNotIn(self.event, self.tile.events_here)
        # The reward is announced by name, in the reward colour.
        reward = next(m for m in msgs if "pouch of Gold" in m["text"])
        self.assertIn("Jean", reward["text"])
        self.assertEqual(reward["color"], "green")
        self.assertNotIn("Slime", "\n".join(m["text"] for m in msgs))

    def test_incorrect_answer_spawns_a_pre_aggroed_ambush(self):
        msgs = self._run(user_input="2")

        # Wrong answer spawns a Slime; no Gold reward.
        self.tile.spawn_npc.assert_called_once_with('Slime')
        self.tile.spawn_item.assert_not_called()
        # awareness=999 is load-bearing: it is what makes check_for_combat()
        # start the ambush regardless of Jean's finesse. A default-awareness
        # slime would leave the "punishment" as a harmless decoration.
        self.assertEqual(self.tile.spawn_npc.return_value.awareness, 999)
        self.assertTrue(self.event.completed)
        self.assertFalse(self.event.needs_input)
        self.assertIn(
            "A Slime oozes out from cracks in the earth!",
            [m["text"] for m in msgs],
        )

    def test_third_option_is_also_wrong(self):
        """Only "1" is correct — every other option takes the punishment branch."""
        self._run(user_input="3")
        self.tile.spawn_npc.assert_called_once_with('Slime')
        self.tile.spawn_item.assert_not_called()

    def test_no_input_defaults_to_correct_answer(self):
        # When called without user_input, the riddle defaults to the safe "1"
        # so a dropped/blank answer never punishes the player.
        self._run()
        self.tile.spawn_item.assert_called_once_with('Gold', amt=500)
        self.tile.spawn_npc.assert_not_called()

    def test_repeating_statue_stays_on_the_tile(self):
        repeating = WhisperingStatue(self.player, self.tile, repeat=True)
        self.tile.events_here.append(repeating)

        with capture_narration():
            repeating.process(user_input="1")

        self.assertIn(repeating, self.tile.events_here)


if __name__ == '__main__':
    unittest.main()
