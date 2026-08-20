"""
Tests for:
- src/npc/_eastern_descent.py (NomadCamper, NomadScout, NomadTrader)
- src/npc/_loot.py (NPCLootMixin: die, before_death, drop_inventory, roll_loot)

These are instantiation + behaviour tests.  No terminal output; all print/cprint
calls are silenced by conftest.patch_terminal_output autouse fixture.
"""

import sys
import os
import pytest
from unittest.mock import MagicMock, patch
from types import SimpleNamespace

# Ensure src is on the path


# ===========================================================================
# NomadCamper
# ===========================================================================


class TestNomadCamper:
    @pytest.fixture
    def npc(self):
        from src.npc._eastern_descent import NomadCamper

        return NomadCamper()

    def test_instantiation(self, npc):
        assert npc is not None

    def test_name(self, npc):
        assert npc.name == "Nomad"

    def test_not_aggressive(self, npc):
        assert npc.aggro is False

    def test_zero_damage(self, npc):
        assert npc.damage == 0

    def test_zero_exp_award(self, npc):
        assert npc.exp_award == 0

    def test_keywords_contain_talk(self, npc):
        assert "talk" in npc.keywords

    def test_pronouns_masculine(self, npc):
        assert npc.pronouns["personal"] == "he"
        assert npc.pronouns["possessive"] == "his"

    def test_chat_config_path_is_none(self, npc):
        assert npc._chat_config_path is None

    def test_talk_lines_not_empty(self, npc):
        assert len(npc._TALK_LINES) > 0

    def test_talk_prints_a_line(self, npc, capsys):
        player = SimpleNamespace()
        npc.talk(player)
        captured = capsys.readouterr()
        # Any non-empty output is acceptable; the method calls print()
        assert len(captured.out) > 0

    def test_talk_output_is_one_of_the_talk_lines(self, npc, capsys):
        player = SimpleNamespace()
        npc.talk(player)
        captured = capsys.readouterr()
        output = captured.out.strip()
        assert any(
            line[:30] in output for line in npc._TALK_LINES
        ), "talk() output not in _TALK_LINES"

    def test_description_nonempty(self, npc):
        assert len(npc.description) > 10

    def test_maxhp_positive(self, npc):
        assert npc.maxhp > 0

    def test_has_known_moves(self, npc):
        # known_moves may be [] if moves module failed to load in test isolation,
        # but the attribute must exist
        assert hasattr(npc, "known_moves")


# ===========================================================================
# NomadScout
# ===========================================================================


class TestNomadScout:
    @pytest.fixture
    def npc(self):
        from src.npc._eastern_descent import NomadScout

        return NomadScout()

    def test_instantiation(self, npc):
        assert npc is not None

    def test_name(self, npc):
        assert npc.name == "Nomad Scout"

    def test_not_aggressive(self, npc):
        assert npc.aggro is False

    def test_awareness_higher_than_camper(self, npc):
        from src.npc._eastern_descent import NomadCamper

        camper = NomadCamper()
        assert npc.awareness > camper.awareness

    def test_keywords_contain_talk(self, npc):
        assert "talk" in npc.keywords

    def test_pronouns_masculine(self, npc):
        assert npc.pronouns["personal"] == "he"

    def test_talk_lines_not_empty(self, npc):
        assert len(npc._TALK_LINES) > 0

    def test_talk_prints(self, npc, capsys):
        npc.talk(SimpleNamespace())
        assert len(capsys.readouterr().out) > 0

    def test_description_references_camp_edge(self, npc):
        assert (
            "camp" in npc.description.lower() or "approach" in npc.description.lower()
        )

    def test_speed_nonzero(self, npc):
        assert npc.speed > 0


# ===========================================================================
# NomadTrader
# ===========================================================================


class TestNomadTrader:
    @pytest.fixture
    def npc(self):
        from src.npc._eastern_descent import NomadTrader

        return NomadTrader()

    def test_instantiation(self, npc):
        assert npc is not None

    def test_name(self, npc):
        assert npc.name == "Nomad Trader"

    def test_not_aggressive(self, npc):
        assert npc.aggro is False

    def test_pronouns_feminine(self, npc):
        assert npc.pronouns["personal"] == "she"
        assert npc.pronouns["possessive"] == "her"

    def test_keywords_contain_talk(self, npc):
        assert "talk" in npc.keywords

    def test_talk_lines_not_empty(self, npc):
        assert len(npc._TALK_LINES) > 0

    def test_talk_prints(self, npc, capsys):
        npc.talk(SimpleNamespace())
        assert len(capsys.readouterr().out) > 0

    def test_has_charisma(self, npc):
        assert hasattr(npc, "charisma") and npc.charisma > 0

    def test_description_references_goods(self, npc):
        assert "bundle" in npc.description.lower() or "goods" in npc.description.lower()

    def test_maxhp_nonzero(self, npc):
        assert npc.maxhp > 0


# ===========================================================================
# NPCLootMixin — die / before_death / drop_inventory / roll_loot
# ===========================================================================


class TestNPCLootMixinDeathSequence:
    """``die`` / ``before_death`` orchestration, on real engine objects.

    The three classes this replaces drove ``NPCLootMixin`` methods with a
    ``MagicMock`` "npc" and a ``MagicMock`` room, which meant:

    * ``spawn_item`` accepted item names that do not exist in ``src.items``
      (``GoldCoin``, ``DiamondGem``, ``SlimeGoop`` are none of them classes),
      so the assertions described drops the engine could never produce;
    * ``test_before_death_calls_drop_inventory`` asserted only that a mock's
      own auto-generated ``drop_inventory`` attribute was called — the real
      method never ran;
    * ``test_drop_inventory_records_api_drops_when_player_ref`` set
      ``player.__dict__["combat_drops"] = []`` itself and then asserted
      ``hasattr(player, "combat_drops")``;
    * ``test_roll_loot_no_current_room_prints_error`` asserted
      ``"ERR" in captured.out or True`` — unconditionally true.

    The per-method drop arithmetic (survival rolls, quantities, loot chances)
    now lives in ``tests/test_npc_loot_coverage.py``, asserted against a real
    ``MapTile`` under a seeded RNG. What remains here is the sequencing that
    file does not cover: revive interception and the death narration.
    """

    @pytest.fixture
    def corpse(self):
        """A real ``Slime`` (NPC -> NPCLootMixin -> Combatant) on a real tile."""
        from tests._gs_fixtures import live_world
        from src.npc import Slime

        player, game_map = live_world()
        tile = game_map[(0, 0)]
        npc = Slime()
        npc.name = "Slime"
        npc.current_room = tile
        npc.player_ref = player
        npc.loot = None
        npc.inventory = []
        npc.states = []
        return npc, tile

    def test_die_narrates_and_runs_the_death_sequence(self, corpse):
        from src.narration import capture_narration

        npc, _ = corpse

        with capture_narration() as messages:
            npc.die()

        assert [m["text"] for m in messages] == [
            "Slime exploded into fragments of light!"
        ]

    def test_a_revive_state_cancels_death_entirely(self, corpse):
        """``check_revive`` lives on the shared ``Combatant`` base, so this is
        the NPC half of the contract Player also relies on."""
        from src.narration import capture_narration

        npc, tile = corpse
        npc.loot = {"Gold": {"chance": 100, "qty": 5}}

        class _PhoenixRevive:
            name = "PhoenixRevive"

            def __init__(self):
                self.fired = False

            def try_revive(self, target):
                self.fired = True
                target.hp = 25
                return True

        revive = _PhoenixRevive()
        npc.states = [revive]

        with capture_narration() as messages:
            npc.die()

        assert revive.fired is True
        assert npc.hp == 25
        assert messages == []
        # No loot rolled, nothing on the floor: it never died.
        assert tile.items_here == []

    def test_before_death_reports_that_death_should_proceed(self, corpse):
        npc, _ = corpse
        assert npc.before_death() is True

    def test_before_death_skips_the_loot_roll_without_a_loot_table(self, corpse):
        npc, tile = corpse
        npc.loot = None

        npc.before_death()

        assert tile.items_here == []

    def test_before_death_rolls_the_loot_table_when_one_exists(self, corpse):
        import random

        npc, tile = corpse
        npc.loot = {"WoodenArrow": {"chance": 100, "qty": 2}}

        random.seed(7)
        npc.before_death()

        assert [(type(i).__name__, i.count) for i in tile.items_here] == [
            ("WoodenArrow", 2)
        ]

    def test_before_death_stacks_duplicate_drops_into_one_pile(self, corpse):
        """The stacking step is what stops a corpse leaving five separate
        one-arrow entries the player has to pick up individually."""
        import random

        import src.items as items

        npc, tile = corpse
        carried = items.WoodenArrow()
        carried.count = 6
        npc.inventory = [carried]
        npc.embedded_arrows = ["WoodenArrow", "WoodenArrow"]

        random.seed(0)
        npc.before_death()

        assert len(tile.items_here) == 1
        assert type(tile.items_here[0]).__name__ == "WoodenArrow"

    def test_before_death_survives_a_room_without_an_items_list(self, corpse):
        """Guarded by ``hasattr(current_room, "items_here")`` — a stub room must
        not crash the death handler."""
        npc, _ = corpse

        class _BareRoom:
            pass

        npc.current_room = _BareRoom()

        assert npc.before_death() is True
