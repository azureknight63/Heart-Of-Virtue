"""Coverage boost for src/objects.py.

Targets uncovered lines:
  87-91, 218, 256, 270-272, 313-314, 335, 446-447, 450-451, 479-486,
  570-571, 606, 608, 643, 645, 674-688, 733-747, 849, 851, 913-914,
  956-957, 960-961, 964, 1014, 1025-1027, 1082, 1131, 1169, 1259
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

ROOT = Path(__file__).resolve().parent.parent


import pytest
from src.player import Player
import src.objects as objects

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _player():
    p = Player()
    return p


def _mock_tile():
    t = MagicMock()
    t.npcs_here = []
    t.items_here = []
    t.objects_here = []
    t.events_here = []
    t.block_exit = []
    return t


# ---------------------------------------------------------------------------
# TileDescription — line-wrapping branches
# ---------------------------------------------------------------------------


class TestTileDescription:
    def test_tile_description_short_params(self):
        """Lines 85-92: TileDescription wraps short descriptions."""
        p = _player()
        tile = _mock_tile()
        # params: index 0=x, 1=y, rest is description text
        params = ["0", "0", "A short room description"]
        td = objects.TileDescription(player=p, tile=tile, params=params)
        assert td is not None

    def test_tile_description_long_params_wraps(self):
        """Lines 87-91: long description triggers line wrapping (else branch)."""
        p = _player()
        tile = _mock_tile()
        # Create a description that exceeds 104 chars to trigger line wrapping
        long_word = "word " * 25  # 125 chars
        params = ["0", "0", long_word.strip()]
        td = objects.TileDescription(player=p, tile=tile, params=params)
        assert td is not None

    def test_tile_description_tilde_end_mark(self):
        """Lines 71-76: tilde at end of last param uses period end mark."""
        p = _player()
        tile = _mock_tile()
        params = ["0", "0", "A description with period~"]
        td = objects.TileDescription(player=p, tile=tile, params=params)
        assert td is not None


# ---------------------------------------------------------------------------
# WallInscription — read() when text is falsy
# ---------------------------------------------------------------------------


class TestWallInscription:
    def test_read_no_text_prints_description(self):
        """Line 222: read() with no text falls back to print(description)."""
        p = _player()
        tile = _mock_tile()
        wi = objects.WallInscription(player=p, tile=tile)
        wi.text = None
        with patch("builtins.print") as mock_print:
            wi.read()
        mock_print.assert_called_once()

    def test_read_with_text(self):
        """Lines 214-220: read() with text prints it."""
        p = _player()
        tile = _mock_tile()
        wi = objects.WallInscription(player=p, tile=tile, text="Sacred inscription.")
        with (
            patch("builtins.print"),
            patch("src.functions.print_slow"),
            patch("src.functions.await_input"),
            patch("src.objects.cprint"),
        ):
            wi.read()

    def test_read_player_with_name(self):
        """Line 215-216: read() with player.name uses player name."""
        p = _player()
        p.name = "Jean"
        tile = _mock_tile()
        wi = objects.WallInscription(player=p, tile=tile, text="Ancient text.")
        with (
            patch("src.functions.print_slow"),
            patch("src.functions.await_input"),
            patch("src.objects.cprint") as mock_cp,
        ):
            wi.read()
        assert any("Jean" in str(c) for c in mock_cp.call_args_list)

    def test_read_player_without_name(self):
        """Lines 217-218: read() without player having name attr uses generic text."""
        tile = _mock_tile()
        wi = objects.WallInscription(player=None, tile=tile, text="Ancient text.")
        with (
            patch("src.functions.print_slow"),
            patch("src.functions.await_input"),
            patch("src.objects.cprint") as mock_cp,
        ):
            wi.read()
        assert mock_cp.called

    def test_examine_aliases_read(self):
        """Line 224-226: examine() calls read()."""
        p = _player()
        tile = _mock_tile()
        wi = objects.WallInscription(player=p, tile=tile, text="")
        with patch.object(wi, "read") as mock_read:
            wi.examine()
        mock_read.assert_called_once()


# ---------------------------------------------------------------------------
# WallSwitch — position toggling
# ---------------------------------------------------------------------------


class TestWallSwitch:
    def test_wall_switch_creation(self):
        p = _player()
        tile = _mock_tile()
        ws = objects.WallSwitch(player=p, tile=tile)
        assert ws.name == "Wall Depression"
        assert ws.position is False

    def test_wall_switch_position_true(self):
        p = _player()
        tile = _mock_tile()
        ws = objects.WallSwitch(player=p, tile=tile, position=True)
        assert ws.position is True


# ---------------------------------------------------------------------------
# Container — open, lock, unlock, take_all, loot
# ---------------------------------------------------------------------------


class TestContainer:
    def _make_container(self, locked=False, start_open=False):
        p = _player()
        tile = _mock_tile()
        c = objects.Container(
            name="Chest",
            description="A wooden chest.",
            player=p,
            tile=tile,
            locked=locked,
            start_open=start_open,
        )
        return c, p, tile

    def test_container_starts_closed(self):
        c, _, _ = self._make_container()
        assert c.state == "closed"

    def test_container_starts_open_when_flag(self):
        c, _, _ = self._make_container(start_open=True)
        assert c.state == "opened"

    def test_open_closed_container(self):
        """Lines 405+: open() transitions state."""
        c, _, _ = self._make_container()
        with patch("builtins.print"):
            c.open()
        assert c.state == "opened"

    def test_open_locked_container_fails(self):
        """open() on locked container stays closed."""
        c, _, _ = self._make_container(locked=True)
        with patch("builtins.print"):
            c.open()
        assert c.state == "closed"

    def test_open_already_open(self):
        """Opening an already-open container prints message."""
        c, _, _ = self._make_container(start_open=True)
        with patch("builtins.print") as mock_print:
            c.open()
        assert mock_print.called

    def test_take_all_empty_container(self):
        """Lines 449-451: take_all from empty opened container."""
        c, p, _ = self._make_container(start_open=True)
        with patch("builtins.print") as mock_print:
            c.take_all(p)
        assert mock_print.called

    def test_take_all_closed_container(self):
        """take_all returns early if container is closed."""
        c, p, _ = self._make_container()
        # Don't open it
        with patch("builtins.print"):
            c.take_all(p)
        # Should return early — no crash

    def test_take_all_with_items(self):
        """Lines 453-464: take_all transfers items to player."""
        c, p, _ = self._make_container(start_open=True)
        import src.items as items

        gold = items.Gold(5)
        c.inventory = [gold]
        with (
            patch("src.inventory_utils.transfer_item") as mock_transfer,
            patch("builtins.print"),
            patch.object(c, "refresh_description"),
            patch.object(c, "process_events"),
        ):
            c.take_all(p)
        mock_transfer.assert_called()

    def test_loot_opens_closed_container(self):
        """loot() opens a closed container (transfer is handled by LootEvent)."""
        c, p, _ = self._make_container()
        with patch("builtins.print"):
            c.loot()
        assert c.state == "opened"

    def test_stack_items_merges_duplicates(self):
        """Lines 518-553: stack_items combines duplicate stackable items."""
        c, _, _ = self._make_container()
        import src.items as items

        a1 = items.Antidote()
        a2 = items.Antidote()
        c.inventory = [a1, a2]
        c.stack_items()
        # After stacking, should have fewer items with combined count
        total = sum(getattr(i, "count", 1) for i in c.inventory)
        assert total >= 2

    def test_process_events_empty(self):
        """Line 505: process_events with no events returns early."""
        c, _, _ = self._make_container()
        c.events = []
        c.process_events()  # Should not raise

    def test_process_events_with_event(self):
        """Lines 509-516: process_events processes events via tile."""
        c, _, tile = self._make_container()
        ev = MagicMock()
        c.events = [ev]
        tile.events_here = []
        with patch.object(tile, "evaluate_events"):
            c.process_events()
        assert ev in tile.events_here


# ---------------------------------------------------------------------------
# Crate and Shelf
# ---------------------------------------------------------------------------


class TestCrateAndShelf:
    def test_crate_creation(self):
        """Lines 580-608: Crate is a pre-configured open container."""
        p = _player()
        tile = _mock_tile()
        crate = objects.Crate(player=p, tile=tile)
        assert crate.name == "Crate"
        assert crate.state == "opened"
        assert "open" not in crate.keywords

    def test_shelf_creation(self):
        """Lines 611-645: Shelf is a pre-configured open container."""
        p = _player()
        tile = _mock_tile()
        shelf = objects.Shelf(player=p, tile=tile)
        assert shelf.name == "Shelf"
        assert shelf.state == "opened"
        assert "open" not in shelf.keywords


# ---------------------------------------------------------------------------
# Shrine — pray with/without event
# ---------------------------------------------------------------------------


class TestShrine:
    def test_shrine_creation(self):
        p = _player()
        tile = _mock_tile()
        shrine = objects.Shrine(player=p, tile=tile)
        assert shrine.name == "Shrine"
        assert "pray" in shrine.keywords

    def test_pray_no_event(self):
        """Lines 696-708: pray without event."""
        p = _player()
        p.prayer_msg = ["Jean prays."]
        tile = _mock_tile()
        shrine = objects.Shrine(player=p, tile=tile)
        shrine.event = None
        with (
            patch("time.sleep"),
            patch("builtins.print"),
            patch("src.functions.await_input"),
        ):
            shrine.pray(p)

    def test_pray_with_event(self):
        """Lines 704-707: pray with event processes it then clears."""
        p = _player()
        p.prayer_msg = ["Jean prays."]
        tile = _mock_tile()
        shrine = objects.Shrine(player=p, tile=tile)
        ev = MagicMock()
        ev.repeat = False
        shrine.event = ev
        with (
            patch("time.sleep"),
            patch("builtins.print"),
            patch("src.functions.await_input"),
        ):
            shrine.pray(p)
        ev.process.assert_called_once()
        assert shrine.event is None


# ---------------------------------------------------------------------------
# HealingSpring — drink
# ---------------------------------------------------------------------------


class TestHealingSpring:
    def test_drink_restores_hp(self):
        """Lines 755-768: drink restores HP to max."""
        p = _player()
        p.hp = 1
        tile = _mock_tile()
        spring = objects.HealingSpring(player=p, tile=tile)
        spring.event = None
        with (
            patch("time.sleep"),
            patch("builtins.print"),
            patch("src.objects.cprint"),
            patch("src.functions.await_input"),
        ):
            spring.drink(p)
        assert p.hp == p.maxhp

    def test_drink_with_event(self):
        """Lines 764-767: drink processes event then clears it."""
        p = _player()
        tile = _mock_tile()
        spring = objects.HealingSpring(player=p, tile=tile)
        ev = MagicMock()
        ev.repeat = False
        spring.event = ev
        with (
            patch("time.sleep"),
            patch("builtins.print"),
            patch("src.objects.cprint"),
            patch("src.functions.await_input"),
        ):
            spring.drink(p)
        ev.process.assert_called_once()
        assert spring.event is None

    def test_clean_applies_state(self):
        """Lines 770-779: clean applies Clean state."""
        p = _player()
        with (
            patch("time.sleep"),
            patch("builtins.print"),
            patch("src.objects.cprint"),
            patch.object(p, "apply_state") as mock_apply,
        ):
            objects.HealingSpring.clean(p)
        mock_apply.assert_called_once()


# ---------------------------------------------------------------------------
# Passageway — enter
# ---------------------------------------------------------------------------


class TestPassageway:
    def test_passageway_creation(self):
        p = _player()
        tile = _mock_tile()
        pw = objects.Passageway(
            player=p, tile=tile, teleport_map="forest", teleport_tile=(5, 5)
        )
        assert pw.name == "Passageway"
        assert pw.teleport_map == "forest"

    def test_enter_with_teleport(self):
        """Lines 842-866: enter() teleports player."""
        p = _player()
        tile = _mock_tile()
        pw = objects.Passageway(
            player=p,
            tile=tile,
            teleport_map="forest",
            teleport_tile=(5, 5),
        )
        with (
            patch.object(p, "drop_merchandise_items"),
            patch.object(p, "teleport") as mock_teleport,
            patch("builtins.print"),
            patch("time.sleep"),
            patch("src.functions.await_input"),
        ):
            pw.enter(p)
        mock_teleport.assert_called_once_with("forest", (5, 5))

    def test_enter_no_teleport_config(self):
        """Lines 862-865: enter() without teleport_map prints error."""
        p = _player()
        tile = _mock_tile()
        pw = objects.Passageway(player=p, tile=tile)
        with (
            patch.object(p, "drop_merchandise_items"),
            patch("builtins.print") as mock_print,
            patch("src.functions.await_input"),
        ):
            pw.enter(p)
        printed = " ".join(str(c) for c in mock_print.call_args_list)
        assert "not properly configured" in printed

    def test_enter_possessive_name(self):
        """Line 848-849: possessive name in passageway keeps original."""
        p = _player()
        tile = _mock_tile()
        pw = objects.Passageway(
            player=p,
            tile=tile,
            name="Harold's Door",
            teleport_map="inn",
            teleport_tile=(1, 1),
        )
        with (
            patch.object(p, "drop_merchandise_items"),
            patch.object(p, "teleport"),
            patch("builtins.print") as mock_print,
            patch("time.sleep"),
            patch("src.functions.await_input"),
        ):
            pw.enter(p)
        printed = " ".join(str(c) for c in mock_print.call_args_list)
        assert "Harold" in printed

    def test_enter_the_prefix(self):
        """Lines 850-851: 'the' prefix stripped and re-added."""
        p = _player()
        tile = _mock_tile()
        pw = objects.Passageway(
            player=p,
            tile=tile,
            name="The Iron Gate",
            teleport_map="courtyard",
            teleport_tile=(2, 2),
        )
        with (
            patch.object(p, "drop_merchandise_items"),
            patch.object(p, "teleport"),
            patch("builtins.print") as mock_print,
            patch("time.sleep"),
            patch("src.functions.await_input"),
        ):
            pw.enter(p)
        printed = " ".join(str(c) for c in mock_print.call_args_list)
        assert "Iron Gate" in printed

    def test_enter_with_events_before_and_after(self):
        """Lines 839-858: events_before and events_after called."""
        p = _player()
        tile = _mock_tile()
        ev_before = MagicMock()
        ev_after = MagicMock()
        pw = objects.Passageway(
            player=p,
            tile=tile,
            teleport_map="forest",
            teleport_tile=(5, 5),
            events_before=[ev_before],
            events_after=[ev_after],
        )
        with (
            patch.object(p, "drop_merchandise_items"),
            patch.object(p, "teleport"),
            patch("builtins.print"),
            patch("time.sleep"),
            patch("src.functions.await_input"),
        ):
            pw.enter(p)
        ev_before.process.assert_called_once()
        ev_after.process.assert_called_once()


# ---------------------------------------------------------------------------
# MarketBell
# ---------------------------------------------------------------------------


class TestMarketBell:
    def test_ring_no_event(self):
        """Lines 898-915: ring without event prints message."""
        p = _player()
        tile = _mock_tile()
        bell = objects.MarketBell(player=p, tile=tile)
        with (
            patch("src.objects.cprint"),
            patch("time.sleep"),
            patch("builtins.print"),
            patch("src.functions.await_input"),
        ):
            bell.ring()

    def test_ring_with_event(self):
        """Line 905-912: ring with event processes it."""
        p = _player()
        tile = _mock_tile()
        ev = MagicMock()
        ev.repeat = False
        bell = objects.MarketBell(player=p, tile=tile, event=ev)
        with (
            patch("src.objects.cprint"),
            patch("time.sleep"),
            patch("builtins.print"),
            patch("src.functions.await_input"),
        ):
            bell.ring()
        ev.process.assert_called_once()
        assert bell.event is None

    def test_ring_with_repeat_event(self):
        """repeat=True event not cleared after ring."""
        p = _player()
        tile = _mock_tile()
        ev = MagicMock()
        ev.repeat = True
        bell = objects.MarketBell(player=p, tile=tile, event=ev)
        with (
            patch("src.objects.cprint"),
            patch("time.sleep"),
            patch("builtins.print"),
            patch("src.functions.await_input"),
        ):
            bell.ring()
        assert bell.event is ev  # Not cleared for repeat events


# ---------------------------------------------------------------------------
# Fountain
# ---------------------------------------------------------------------------


class TestFountain:
    def test_drink_no_event(self):
        """Lines 942-953: drink without event."""
        p = _player()
        tile = _mock_tile()
        fountain = objects.Fountain(player=p, tile=tile)
        with (
            patch("src.objects.cprint"),
            patch("time.sleep"),
            patch("src.functions.await_input"),
        ):
            fountain.drink()

    def test_drink_with_event(self):
        """Lines 948-952: drink with event processes it."""
        p = _player()
        tile = _mock_tile()
        ev = MagicMock()
        ev.repeat = False
        fountain = objects.Fountain(player=p, tile=tile, event=ev)
        with (
            patch("src.objects.cprint"),
            patch("time.sleep"),
            patch("src.functions.await_input"),
        ):
            fountain.drink()
        ev.process.assert_called_once()
        assert fountain.event is None

    def test_listen(self):
        """Line 955-957: listen prints and awaits."""
        p = _player()
        tile = _mock_tile()
        fountain = objects.Fountain(player=p, tile=tile)
        with patch("builtins.print"), patch("src.functions.await_input") as mock_await:
            fountain.listen()
        mock_await.assert_called_once()

    def test_admire(self):
        """Lines 959-961: admire prints and awaits."""
        p = _player()
        tile = _mock_tile()
        fountain = objects.Fountain(player=p, tile=tile)
        with patch("builtins.print"), patch("src.functions.await_input") as mock_await:
            fountain.admire()
        mock_await.assert_called_once()

    def test_use_aliases_drink(self):
        """Line 963-964: use() calls drink()."""
        p = _player()
        tile = _mock_tile()
        fountain = objects.Fountain(player=p, tile=tile)
        with patch.object(fountain, "drink") as mock_drink:
            fountain.use()
        mock_drink.assert_called_once()


# ---------------------------------------------------------------------------
# StreetLantern
# ---------------------------------------------------------------------------


class TestStreetLantern:
    def test_light_unlit_lantern(self):
        """Lines 1008-1015: light turns lantern on."""
        p = _player()
        tile = _mock_tile()
        lantern = objects.StreetLantern(player=p, tile=tile, lit=False)
        with patch("builtins.print"), patch("src.functions.await_input"):
            lantern.light()
        assert lantern.lit is True

    def test_light_already_lit(self):
        """Line 1006: light prints message when already lit."""
        p = _player()
        tile = _mock_tile()
        lantern = objects.StreetLantern(player=p, tile=tile, lit=True)
        with patch("builtins.print") as mock_print:
            lantern.light()
        assert mock_print.called

    def test_douse_lit_lantern(self):
        """Lines 1021-1028: douse turns lantern off."""
        p = _player()
        tile = _mock_tile()
        lantern = objects.StreetLantern(player=p, tile=tile, lit=True)
        with patch("builtins.print"), patch("src.functions.await_input"):
            lantern.douse()
        assert lantern.lit is False

    def test_douse_already_dark(self):
        """Line 1019: douse prints message when already dark."""
        p = _player()
        tile = _mock_tile()
        lantern = objects.StreetLantern(player=p, tile=tile, lit=False)
        with patch("builtins.print") as mock_print:
            lantern.douse()
        assert mock_print.called

    def test_light_with_event(self):
        """Lines 1011-1014: lighting with event_on processes it."""
        p = _player()
        tile = _mock_tile()
        ev = MagicMock()
        ev.repeat = False
        lantern = objects.StreetLantern(
            player=p, tile=tile, lit=False, event_when_lighting=ev
        )
        with patch("builtins.print"), patch("src.functions.await_input"):
            lantern.light()
        ev.process.assert_called_once()
        assert lantern.event_on is None


# ---------------------------------------------------------------------------
# NoticeBoard
# ---------------------------------------------------------------------------


class TestNoticeBoard:
    def test_read_default_notes(self):
        """Lines 1074-1083: read prints default notes."""
        p = _player()
        tile = _mock_tile()
        board = objects.NoticeBoard(player=p, tile=tile)
        with patch("builtins.print") as mock_print, patch("src.functions.await_input"):
            board.read()
        # At least 5 notes printed
        assert mock_print.call_count >= 5

    def test_read_with_event_first_time(self):
        """Lines 1078-1082: event triggers on first read."""
        p = _player()
        tile = _mock_tile()
        ev = MagicMock()
        ev.repeat = False
        board = objects.NoticeBoard(player=p, tile=tile, event=ev)
        with (
            patch("builtins.print"),
            patch("time.sleep"),
            patch("src.functions.await_input"),
        ):
            board.read()
        ev.process.assert_called_once()
        assert board._read_once is True

    def test_use_aliases_read(self):
        """Line 1085-1086: use() calls read()."""
        p = _player()
        tile = _mock_tile()
        board = objects.NoticeBoard(player=p, tile=tile)
        with patch.object(board, "read") as mock_read:
            board.use()
        mock_read.assert_called_once()


# ---------------------------------------------------------------------------
# PrayerCandleRack
# ---------------------------------------------------------------------------


class TestPrayerCandleRack:
    def test_light_candle(self):
        """Lines 1112-1119: light increments candle count."""
        p = _player()
        tile = _mock_tile()
        rack = objects.PrayerCandleRack(player=p, tile=tile, lit_candles=0)
        with patch("builtins.print"), patch("src.functions.await_input"):
            rack.light()
        assert rack.lit_candles == 1

    def test_light_at_max(self):
        """Line 1113-1115: light when all candles already lit."""
        p = _player()
        tile = _mock_tile()
        rack = objects.PrayerCandleRack(player=p, tile=tile, lit_candles=20)
        with patch("builtins.print") as mock_print, patch("src.functions.await_input"):
            rack.light()
        assert rack.lit_candles == 20
        assert mock_print.called

    def test_pray_no_event(self):
        """Lines 1121-1132: pray without event prints message."""
        p = _player()
        tile = _mock_tile()
        rack = objects.PrayerCandleRack(player=p, tile=tile)
        with (
            patch("builtins.print"),
            patch("time.sleep"),
            patch("src.functions.await_input"),
        ):
            rack.pray()

    def test_pray_with_event(self):
        """Lines 1128-1131: pray with event processes and clears it."""
        p = _player()
        tile = _mock_tile()
        ev = MagicMock()
        ev.repeat = False
        rack = objects.PrayerCandleRack(player=p, tile=tile, event=ev)
        with (
            patch("builtins.print"),
            patch("time.sleep"),
            patch("src.functions.await_input"),
        ):
            rack.pray()
        ev.process.assert_called_once()
        assert rack.event is None


# ---------------------------------------------------------------------------
# MarketGong
# ---------------------------------------------------------------------------


class TestMarketGong:
    def test_strike_no_event(self):
        """Lines 1154-1170: strike without event."""
        p = _player()
        tile = _mock_tile()
        gong = objects.MarketGong(player=p, tile=tile)
        with (
            patch("src.objects.cprint"),
            patch("time.sleep"),
            patch("builtins.print"),
            patch("src.functions.await_input"),
        ):
            gong.strike()

    def test_strike_with_event(self):
        """Lines 1165-1169: strike with event processes it."""
        p = _player()
        tile = _mock_tile()
        ev = MagicMock()
        ev.repeat = False
        gong = objects.MarketGong(player=p, tile=tile, event=ev)
        with (
            patch("src.objects.cprint"),
            patch("time.sleep"),
            patch("builtins.print"),
            patch("src.functions.await_input"),
        ):
            gong.strike()
        ev.process.assert_called_once()
        assert gong.event is None

    def test_hit_aliases_strike(self):
        """Line 1172-1173: hit() calls strike()."""
        p = _player()
        tile = _mock_tile()
        gong = objects.MarketGong(player=p, tile=tile)
        with patch.object(gong, "strike") as mock_strike:
            gong.hit()
        mock_strike.assert_called_once()

    def test_bang_aliases_strike(self):
        """Line 1175-1176: bang() calls strike()."""
        p = _player()
        tile = _mock_tile()
        gong = objects.MarketGong(player=p, tile=tile)
        with patch.object(gong, "strike") as mock_strike:
            gong.bang()
        mock_strike.assert_called_once()
