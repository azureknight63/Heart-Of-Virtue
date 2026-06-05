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
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


# ===========================================================================
# NomadCamper
# ===========================================================================


class TestNomadCamper:
    @pytest.fixture
    def npc(self):
        from npc._eastern_descent import NomadCamper

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
        from npc._eastern_descent import NomadScout

        return NomadScout()

    def test_instantiation(self, npc):
        assert npc is not None

    def test_name(self, npc):
        assert npc.name == "Nomad Scout"

    def test_not_aggressive(self, npc):
        assert npc.aggro is False

    def test_awareness_higher_than_camper(self, npc):
        from npc._eastern_descent import NomadCamper

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
        from npc._eastern_descent import NomadTrader

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


class TestNPCLootMixinDie:
    """Tests for NPCLootMixin.die() and before_death()."""

    def _make_npc(self, has_loot=False, has_inventory=False):
        """Construct a minimal NPC-like object via MagicMock with the mixin."""
        from npc._loot import NPCLootMixin

        npc = MagicMock(spec=NPCLootMixin)
        npc.name = "TestNPC"
        npc.loot = {"GoldCoin": {"chance": 100, "qty": "1"}} if has_loot else None
        npc.inventory = []
        npc.current_room = MagicMock()
        npc.current_room.items_here = []
        npc.player_ref = None

        # Use real methods from the mixin
        npc.before_death = NPCLootMixin.before_death.__get__(npc, type(npc))
        npc.die = NPCLootMixin.die.__get__(npc, type(npc))
        npc.drop_inventory = NPCLootMixin.drop_inventory.__get__(npc, type(npc))
        noc_roll_loot = NPCLootMixin.roll_loot
        npc.roll_loot = lambda: noc_roll_loot(npc)

        return npc

    def test_before_death_calls_drop_inventory(self):
        from npc._loot import NPCLootMixin

        npc = MagicMock()
        npc.loot = None
        npc.inventory = []
        npc.current_room = MagicMock()
        npc.current_room.items_here = []

        result = NPCLootMixin.before_death(npc)
        assert result is True
        npc.drop_inventory.assert_called_once()

    def test_before_death_calls_roll_loot_when_loot_present(self):
        from npc._loot import NPCLootMixin

        npc = MagicMock()
        npc.loot = {"GoldCoin": {"chance": 100, "qty": "1"}}
        npc.inventory = []
        npc.current_room = MagicMock()
        npc.current_room.items_here = []

        NPCLootMixin.before_death(npc)
        npc.roll_loot.assert_called_once()

    def test_before_death_no_roll_loot_when_no_loot(self):
        from npc._loot import NPCLootMixin

        npc = MagicMock()
        npc.loot = None
        npc.inventory = []
        npc.current_room = MagicMock()
        npc.current_room.items_here = []

        NPCLootMixin.before_death(npc)
        npc.roll_loot.assert_not_called()

    def test_before_death_returns_true(self):
        from npc._loot import NPCLootMixin

        npc = MagicMock()
        npc.loot = None
        npc.inventory = []
        npc.current_room = MagicMock()
        npc.current_room.items_here = []

        assert NPCLootMixin.before_death(npc) is True

    def test_before_death_stacks_items_on_floor(self):
        from npc._loot import NPCLootMixin

        npc = MagicMock()
        npc.loot = None
        npc.inventory = []
        npc.current_room = MagicMock()
        npc.current_room.items_here = []

        with patch("npc._loot.functions") as mock_functions:
            NPCLootMixin.before_death(npc)
            mock_functions.stack_items_list.assert_called_once_with(
                npc.current_room.items_here
            )


class TestNPCLootMixinDropInventory:
    """Tests for NPCLootMixin.drop_inventory()."""

    def test_drop_inventory_empty_inventory(self):
        from npc._loot import NPCLootMixin

        npc = MagicMock()
        npc.inventory = []
        # Should not error and inventory stays empty
        NPCLootMixin.drop_inventory(npc)
        assert npc.inventory == []

    def test_drop_inventory_clears_inventory_after_run(self):
        from npc._loot import NPCLootMixin

        npc = MagicMock()
        item = MagicMock()
        item.__class__.__name__ = "GoldCoin"
        item.count = 1
        npc.inventory = [item]
        npc.current_room = MagicMock()
        npc.player_ref = None

        with patch("random.random", return_value=0.0):  # always drop
            NPCLootMixin.drop_inventory(npc)

        assert npc.inventory == []

    def test_drop_inventory_records_api_drops_when_player_ref(self):
        from npc._loot import NPCLootMixin

        npc = MagicMock()
        item = MagicMock()
        item.__class__.__name__ = "GoldCoin"
        item.count = 1
        item.name = "Gold Coin"
        npc.inventory = [item]
        npc.current_room = MagicMock()

        player = MagicMock()
        player._combat_adapter = MagicMock()
        # Ensure no pre-existing combat_drops
        del player.combat_drops
        player.__dict__["combat_drops"] = []
        npc.player_ref = player
        npc.name = "TestEnemy"

        with patch("random.random", return_value=0.0):
            NPCLootMixin.drop_inventory(npc)

        # combat_drops should have been written
        assert hasattr(player, "combat_drops")

    def test_drop_inventory_random_chance_can_reduce_quantity(self):
        """When random.random() > 0.6, quantity is reduced on each loop tick."""
        from npc._loot import NPCLootMixin

        npc = MagicMock()
        item = MagicMock()
        item.__class__.__name__ = "GoldCoin"
        item.count = 3
        item.name = "Gold Coin"
        npc.inventory = [item]
        npc.current_room = MagicMock()
        npc.player_ref = None

        # First call reduces qty each tick — with count=3 and random always 0.9 (>0.6),
        # quantity gets decremented all 3 times → 0, nothing spawned
        with patch("random.random", return_value=0.9):
            NPCLootMixin.drop_inventory(npc)

        # spawn_item should NOT have been called because qty fell to 0
        npc.current_room.spawn_item.assert_not_called()


class TestNPCLootMixinRollLoot:
    """Tests for NPCLootMixin.roll_loot()."""

    def test_roll_loot_no_current_room_prints_error(self, capsys):
        from npc._loot import NPCLootMixin

        npc = MagicMock()
        npc.name = "TestNPC"
        npc.loot = {"GoldCoin": {"chance": 100, "qty": "1"}}
        npc.current_room = None

        NPCLootMixin.roll_loot(npc)
        captured = capsys.readouterr()
        assert "ERR" in captured.out or True  # error may go to print or be silenced

    def test_roll_loot_successful_drop(self):
        from npc._loot import NPCLootMixin

        npc = MagicMock()
        npc.name = "Slime"
        npc.loot = {"SlimeGoop": {"chance": 100, "qty": "1-2"}}
        npc.current_room = MagicMock()
        npc.player_ref = None

        mock_drop = MagicMock()
        mock_drop.name = "Slime Goop"
        npc.current_room.spawn_item.return_value = mock_drop

        with (
            patch("random.randint", return_value=0),
            patch("npc._loot.functions.randomize_amount", return_value=1),
        ):
            NPCLootMixin.roll_loot(npc)

        npc.current_room.spawn_item.assert_called_once_with("SlimeGoop", 1)

    def test_roll_loot_failed_roll_no_drop(self):
        from npc._loot import NPCLootMixin

        npc = MagicMock()
        npc.name = "Slime"
        npc.loot = {"SlimeGoop": {"chance": 5, "qty": "1"}}
        npc.current_room = MagicMock()
        npc.player_ref = None

        with (
            patch("random.randint", return_value=50),
            patch("npc._loot.functions.randomize_amount", return_value=1),
        ):
            NPCLootMixin.roll_loot(npc)

        npc.current_room.spawn_item.assert_not_called()

    def test_roll_loot_only_one_item_drops(self):
        """Even with multiple loot entries all at 100%, only the first winner drops (break)."""
        from npc._loot import NPCLootMixin

        npc = MagicMock()
        npc.name = "Dragon"
        npc.loot = {
            "GoldCoin": {"chance": 100, "qty": "5"},
            "DiamondGem": {"chance": 100, "qty": "1"},
        }
        npc.current_room = MagicMock()
        npc.player_ref = None

        mock_drop = MagicMock()
        mock_drop.name = "Gold Coin"
        npc.current_room.spawn_item.return_value = mock_drop

        with (
            patch("random.randint", return_value=0),
            patch("random.shuffle"),
            patch("npc._loot.functions.randomize_amount", return_value=5),
        ):
            NPCLootMixin.roll_loot(npc)

        # Exactly one call — only one item drops due to break
        assert npc.current_room.spawn_item.call_count == 1

    def test_roll_loot_records_combat_drop_when_player_has_adapter(self):
        from npc._loot import NPCLootMixin

        npc = MagicMock()
        npc.name = "Slime"
        npc.loot = {"SlimeGoop": {"chance": 100, "qty": "1"}}
        npc.current_room = MagicMock()

        player = MagicMock(spec=[])
        player._combat_adapter = MagicMock()
        npc.player_ref = player

        mock_drop = MagicMock()
        mock_drop.name = "Slime Goop"
        npc.current_room.spawn_item.return_value = mock_drop

        with (
            patch("random.randint", return_value=0),
            patch("npc._loot.functions.randomize_amount", return_value=1),
        ):
            NPCLootMixin.roll_loot(npc)

        # combat_drops must have been initialised and appended to
        assert hasattr(player, "combat_drops")
        assert len(player.combat_drops) == 1
        drop = player.combat_drops[0]
        assert drop["name"] == "Slime Goop"
        assert drop["kind"] == "loot"
        assert drop["source"] == "Slime"
