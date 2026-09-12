"""
Tests for Ch02KingSlimeMemoryFlash guard conditions and story flag behavior.

Covers the fix for the MemoryFlash multi-fire bug (PR #202):
- check_conditions must bail early when needs_input=True (mid-flash)
- check_conditions must bail early when king_slime_flash_fired story flag is set
- process('continue') must persist the king_slime_flash_fired flag
- process(None) must NOT set the flag (only the completion pass does)

And the two acquisition guards:
- AfterDefeatingKingSlime grants the fragment to inventory with no floor
  drop, and the queued flash fires on that possession (#378/#371)
- the flash's opening beat places the fragment already in Jean's hand
  instead of narrating him acquiring it (#574)
"""

import re
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src import items
from tests._ch02_fixtures import (
    MineralFragment,
    holds_mineral_fragment,
    make_pools_map,
    real_arena_tile,
)

#: Jean -- by name or as "he" -- holding, carrying or clutching something;
#: group 1 is the word for what he holds.
_HELD_BY_JEAN = re.compile(
    r"\b(?:jean|he)(?: is)?(?: already)? "
    r"(?:hold(?:s|ing)?|carr(?:ies|ying)|clutch(?:es|ing)?) "
    r"(?:(?:the|a|his) )?(\w+)",
    re.IGNORECASE,
)

#: Something in Jean's hand, palm or grip. The possessive ties the hand to
#: him; ``_places_in_hand`` ties what is in it to the fragment by clause.
_IN_HIS_HAND = re.compile(r"\bin (?:his|jean's) (?:hands?|palm|grip)\b", re.IGNORECASE)

#: Where one clause of narration ends -- the em dash (U+2014) included,
#: since that is how this flash joins its clauses.
_CLAUSE_END = re.compile(r"[.!?;\u2014]")

#: The complaint ``_opening_beat_problems`` files when the opening never puts
#: the noun in Jean's grasp. Named because the tests below match on it.
_NOT_IN_HAND = "nothing places it in Jean's hand"

#: A phrase that narrates him acquiring it -- the framing #574 removed.
_ACQUIRING = re.compile(
    r"\b(?:pick(?:s|ed|ing)?\b.{0,20}\bup|reach(?:es|ed|ing)? (?:down|for)|"
    r"bend(?:s|ing)? (?:down|to)|stoop(?:s|ing)?|from the (?:floor|ground|stone|water))\b",
    re.IGNORECASE,
)


def _places_in_hand(text, noun):
    """Whether ``text`` puts the ``noun`` in Jean's grasp: Jean (or "he")
    holding, carrying or clutching the ``noun`` itself, or one clause that
    names the ``noun`` and puts something in his hand. Either way the grasp
    is tied to Jean, and named in the same breath as the ``noun``, so "The
    silence holds." and "He holds his breath." do not count. The clause
    branch is the looser of the two: it accepts a clause that names the
    ``noun`` alongside some OTHER thing in his hand."""
    if any(held.group(1).lower() == noun for held in _HELD_BY_JEAN.finditer(text)):
        return True
    return any(
        noun in clause.lower() and _IN_HIS_HAND.search(clause)
        for clause in _CLAUSE_END.split(text)
    )


def _opening_beat_problems(opening_lines, noun):
    """What is wrong with the flash's opening beat by #574's standard: it
    must name the fragment, place it already in Jean's hand, and never
    narrate him acquiring it. Empty when the opening is right."""
    text = " ".join(opening_lines)
    problems = []
    if noun not in text.lower():
        problems.append(f"the opening never names the {noun}")
    if not _places_in_hand(text, noun):
        problems.append(_NOT_IN_HAND)
    acquiring = _ACQUIRING.search(text)
    if acquiring:
        problems.append(f"it narrates acquiring it: {acquiring.group()!r}")
    return problems


def _mock_flash():
    """A ``Ch02KingSlimeMemoryFlash`` queued on a Mock tile, for a Mock
    player with no story gates set and nothing in inventory."""
    from src.story.ch02 import Ch02KingSlimeMemoryFlash

    tile = Mock()
    tile.events_here = []
    player = Mock()
    player.universe = Mock()
    player.universe.story = {}
    player.inventory = []
    flash = Ch02KingSlimeMemoryFlash(player=player, tile=tile)
    tile.events_here.append(flash)
    return flash


class TestCh02KingSlimeMemoryFlashGuards(unittest.TestCase):

    def setUp(self):
        self.flash = _mock_flash()
        self.player = self.flash.player
        self.tile = self.flash.tile

    # ------------------------------------------------------------------
    # check_conditions guards
    # ------------------------------------------------------------------

    def test_check_conditions_skips_when_needs_input_true(self):
        """Mid-flash (needs_input=True) must not re-queue the flash."""
        self.flash.needs_input = True
        self.flash.pass_conditions_to_process = Mock()

        self.flash.check_conditions()

        self.flash.pass_conditions_to_process.assert_not_called()

    def test_check_conditions_skips_when_story_flag_set(self):
        """After king_slime_flash_fired is set, check_conditions must not fire."""
        self.player.universe.story["king_slime_flash_fired"] = "1"
        self.flash.pass_conditions_to_process = Mock()

        self.flash.check_conditions()

        self.flash.pass_conditions_to_process.assert_not_called()

    def test_check_conditions_removes_self_when_story_flag_set(self):
        """When the story flag guard trips, the event removes itself from tile.events_here."""
        self.player.universe.story["king_slime_flash_fired"] = "1"
        self.assertIn(self.flash, self.tile.events_here)

        self.flash.check_conditions()

        self.assertNotIn(self.flash, self.tile.events_here)

    def test_check_conditions_fires_with_mineral_fragment(self):
        """check_conditions calls pass_conditions_to_process when a MineralFragment is in inventory."""
        self.player.inventory = [MineralFragment()]
        self.flash.pass_conditions_to_process = Mock()

        self.flash.check_conditions()

        self.flash.pass_conditions_to_process.assert_called_once()

    def test_check_conditions_does_not_fire_without_mineral_fragment(self):
        """check_conditions does not fire when no MineralFragment is in inventory."""
        class IronSword:
            pass
        self.player.inventory = [IronSword()]
        self.flash.pass_conditions_to_process = Mock()

        self.flash.check_conditions()

        self.flash.pass_conditions_to_process.assert_not_called()

    # ------------------------------------------------------------------
    # process() story flag
    # ------------------------------------------------------------------

    @patch('src.story.effects.memory_border')
    @patch('src.story.effects.time.sleep')
    def test_process_completion_sets_story_flag_and_finishes(self, _sleep, _border):
        """process('continue') closes the flash: flag set, no further input wanted."""
        from src.narration import capture_narration

        self.flash.process(None)  # first pass must happen before the completion pass
        with capture_narration() as msgs:
            self.flash.process("continue")

        self.assertEqual(self.player.universe.story.get("king_slime_flash_fired"), "1")
        self.assertFalse(self.flash.needs_input)
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

        with capture_narration() as msgs:
            self.flash.process(None)

        self.assertNotIn("king_slime_flash_fired", self.player.universe.story)
        self.assertTrue(self.flash.needs_input)
        self.assertEqual(
            [o["value"] for o in self.flash.input_options], ["continue"]
        )

        # Jean's solo cast is staged, and his introspective beats are thoughts.
        begin = next(m for m in msgs if m.get("type") == "conversation_begin")
        self.assertEqual([c["id"] for c in begin["cast"]], ["Jean"])
        thoughts = {m["text"]: m for m in msgs if m.get("thought")}
        self.assertIn("Pain — sudden, immediate, real.", thoughts)
        self.assertEqual(thoughts["emptiness."]["emotion"], "sad")
        self.assertTrue(all(m["speaker"] == "Jean" for m in thoughts.values()))
        # The API description mirrors the narrated prose for non-staged clients.
        self.assertIn("BOOM.", self.flash.description)


class TestCh02KingSlimeMemoryFlashFiresAfterInventoryOnlyGrant(unittest.TestCase):
    """Guard for #378/#371: the fragment reaches Jean by a direct grant.

    ``AfterDefeatingKingSlime`` grants the MineralFragment straight into
    inventory and never spawns it as a floor item. This runs the real grant
    path -- a real ``Player``, a real ``MapTile``, the real event classes, the
    real item -- and checks that when the already-queued
    ``Ch02KingSlimeMemoryFlash`` decides to fire, the fragment is in the
    player's inventory (what its ``check_conditions`` reads) and absent from
    the tile's floor items (the engine's grant contract). It asserts no
    prose; ``TestCh02KingSlimeMemoryFlashOpensWithTheFragmentInHand`` below
    holds the scene to that grant (#574).
    """

    def test_the_floor_check_can_actually_fail(self):
        """Positive control: a real tile's ``spawn_item`` puts the fragment on
        the floor, so the ``tile.items_here == []`` check in
        ``test_flash_fires_on_inventory_grant_with_no_floor_drop`` is
        observing something."""
        tile = real_arena_tile()
        tile.spawn_item("MineralFragment")
        self.assertTrue(holds_mineral_fragment(tile.items_here))

    def test_flash_fires_on_inventory_grant_with_no_floor_drop(self):
        from src.player import Player
        from src.story.ch02 import AfterDefeatingKingSlime, Ch02KingSlimeMemoryFlash

        player = Player()
        # A strict double, unlike the Mock universe above: an attribute the
        # event reaches for that this namespace lacks raises rather than
        # auto-mocking, so the real grant path is exercised as written.
        player.universe = SimpleNamespace(story={}, maps=[make_pools_map()])
        player.map = {}  # skip the Gorran-teleport atrium lookup
        tile = real_arena_tile()  # King Slime already dead: no NPCs here

        event = AfterDefeatingKingSlime(player=player, tile=tile)
        with patch("src.story.ch02.print_slow"):
            event.check_conditions()  # King absent on this tile -> runs process()

        # Engine truth (#378/#371): the fragment is inventory-only.
        self.assertTrue(
            holds_mineral_fragment(player.inventory),
            "AfterDefeatingKingSlime must grant the fragment straight to inventory",
        )
        self.assertEqual(
            tile.items_here, [],
            "the fragment must never be spawned as a floor item (#378/#371)",
        )

        flashes = [
            e for e in tile.events_here if isinstance(e, Ch02KingSlimeMemoryFlash)
        ]
        self.assertTrue(flashes, "AfterDefeatingKingSlime must queue the memory flash")
        flash = flashes[0]

        # This is the real check_conditions on the real, queued flash instance --
        # not a re-derivation of its logic -- confirming it fires on possession.
        flash.pass_conditions_to_process = Mock()
        flash.check_conditions()
        flash.pass_conditions_to_process.assert_called_once()


class TestCh02KingSlimeMemoryFlashOpensWithTheFragmentInHand(unittest.TestCase):
    """Guard for #574: the flash's opening read as though Jean had just
    picked a sharp fragment off the floor -- a pickup that no longer happens
    since the grant went straight to inventory. The opening beat, every line
    narrated before Jean's first thought (the pain), must name the fragment
    and place it already in his hand, and nothing in the flash may narrate
    him acquiring it."""

    #: The word the scene uses for the item, taken from the item itself.
    NOUN = items.MineralFragment().name.split()[-1].lower()

    def test_the_check_rejects_the_opening_it_replaced(self):
        """Positive control: the pre-#574 opening line, and a plain pickup."""
        self.assertTrue(_opening_beat_problems(["The edge catches Jean's finger."], self.NOUN))
        self.assertTrue(_opening_beat_problems(
            ["Jean picks the fragment up off the stone; it is in his hand now."], self.NOUN
        ))

    def test_a_grasp_word_not_tied_to_jean_and_the_fragment_does_not_count(self):
        """The in-hand half of the check rejects a grasp word that is not
        tied to Jean, and one that never shares a clause with the fragment.
        The shipped opening passing the same check is
        ``test_the_real_flash_opens_with_the_fragment_already_in_hand``."""
        for opening in (
            "The silence holds.",
            f"The {self.NOUN} glints on the stone. The silence holds.",
            f"The {self.NOUN} holds the light.",
            f"He holds his breath; the {self.NOUN} glints.",
            f"His sword is in his hand. The {self.NOUN} glints on the stone.",
            f"His sword is in his hand \u2014 the {self.NOUN} glints on the stone.",
        ):
            with self.subTest(opening=opening):
                self.assertIn(_NOT_IN_HAND, _opening_beat_problems([opening], self.NOUN))

    def test_other_ways_of_putting_it_in_his_hand_count(self):
        """The check accepts phrasings the shipped line does not use, so each
        branch of the in-hand half is shown to accept something."""
        for opening in (
            f"Jean holds the {self.NOUN}; the edge catches his finger.",
            f"He is already clutching the {self.NOUN}.",
            f"The {self.NOUN} is in his palm.",
        ):
            with self.subTest(opening=opening):
                self.assertEqual(_opening_beat_problems([opening], self.NOUN), [])

    @patch("src.story.effects.memory_border")
    def test_the_real_flash_opens_with_the_fragment_already_in_hand(self, _border):
        from src.narration import capture_narration

        flash = _mock_flash()
        with capture_narration() as msgs:
            flash.process(None)

        spoken = [m for m in msgs if (m.get("text") or "").strip()]
        first_thought = next((i for i, m in enumerate(spoken) if m.get("thought")), None)
        self.assertIsNotNone(first_thought, "the flash has no thought beat to end its opening")
        opening = [m["text"] for m in spoken[:first_thought]]
        self.assertTrue(opening, "the flash narrates nothing before Jean's first thought")
        self.assertEqual(_opening_beat_problems(opening, self.NOUN), [], opening)
        whole = " ".join(m["text"] for m in spoken)
        self.assertIsNone(_ACQUIRING.search(whole), whole)


if __name__ == "__main__":
    unittest.main()
