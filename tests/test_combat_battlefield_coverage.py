"""
Coverage tests for src/combat_battlefield.py (CombatBattlefieldWindow).

This module is tkinter-based, but tkinter may not be installed (and even
where it is, there's no $DISPLAY) in the CI/dev environments used for this
suite (see `_TKINTER_AVAILABLE` guard at the top of the module). To exercise
the tkinter-dependent code paths (create_window,
on_close, _render_initial_grid, update_display, _apply_grid_tags,
_apply_color_tags) without a real display, these tests monkeypatch the
module-level `tk` reference with a lightweight fake that mimics the small
slice of the tkinter API the module actually uses (widget constructors return
MagicMocks; layout/constant attributes are plain sentinel strings; TclError
is a real Exception subclass so `except tk.TclError` clauses work correctly).

Everything else (render_grid, set_combatant, _update_viewport,
update_all_combatants) runs against the real (non-tkinter) logic, since those
methods only touch tkinter objects behind `if self.text_widget:` /
`if self.window:` guards that are naturally None when tkinter is unavailable.
"""

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest

import src.combat_battlefield as battlefield_module
from src.combat_battlefield import CombatBattlefieldWindow


@dataclass
class MockPosition:
    """Mock position object mirroring CombatPosition's x/y/facing surface."""

    x: float
    y: float
    facing: object = None

    def copy(self):
        return MockPosition(self.x, self.y, self.facing)


class _NoCopyPosition:
    """Position-like object without a .copy() method, used to exercise the
    AttributeError/TypeError fallback in set_combatant's history tracking."""

    def __init__(self, x, y):
        self.x = x
        self.y = y


# ---------------------------------------------------------------------------
# Fake tkinter module used to exercise create_window/on_close/_render_initial
# _grid/update_display/_apply_grid_tags/_apply_color_tags without a display.
# ---------------------------------------------------------------------------


class _FakeTclError(Exception):
    """Stand-in for tkinter.TclError — a real Exception subclass so it can
    be used in `except tk.TclError:` clauses."""


class _FakeTk:
    """Minimal fake of the tkinter module surface used by combat_battlefield.py."""

    TclError = _FakeTclError
    BOTH = "both"
    X = "x"
    LEFT = "left"
    NONE = "none"
    FLAT = "flat"
    DISABLED = "disabled"
    NORMAL = "normal"
    END = "end"
    W = "w"

    def __init__(self):
        self.Tk = MagicMock(name="Tk")
        self.Frame = MagicMock(name="Frame")
        self.Label = MagicMock(name="Label")
        self.Text = MagicMock(name="Text")
        # _apply_color_tags() does `while True: pos = search(...); if not pos: break`.
        # An unconfigured MagicMock return value is always truthy, which would spin
        # forever and balloon memory. Default to None (falsy) so any test that
        # doesn't explicitly configure `.search` terminates immediately.
        self.Text.return_value.search.return_value = None


@pytest.fixture
def fake_tk_env():
    """Patch the module's tk reference + availability flag with a fake tkinter."""
    fake_tk = _FakeTk()
    with (
        patch.object(battlefield_module, "tk", fake_tk),
        patch.object(battlefield_module, "_TKINTER_AVAILABLE", True),
    ):
        yield fake_tk


# ---------------------------------------------------------------------------
# create_window
# ---------------------------------------------------------------------------


class TestCreateWindow:
    def test_returns_early_when_tkinter_unavailable(self):
        """When tkinter isn't importable, create_window is a no-op.

        Forces the module's _TKINTER_AVAILABLE flag to False rather than
        relying on the ambient environment actually lacking tkinter — CI
        runners have tkinter installed (just no $DISPLAY), which would
        otherwise let this test fall through to a real tk.Tk() call and
        fail with TclError instead of exercising the guard clause.
        """
        with patch.object(battlefield_module, "_TKINTER_AVAILABLE", False):
            window = CombatBattlefieldWindow()
            window.create_window()
        assert window.window is None
        assert window.is_open is False

    def test_returns_early_when_already_open(self, fake_tk_env):
        window = CombatBattlefieldWindow()
        window.is_open = True
        window.create_window()
        # Should not have constructed a new Tk() since it returned immediately.
        fake_tk_env.Tk.assert_not_called()

    def test_builds_full_window_with_fake_tkinter(self, fake_tk_env):
        window = CombatBattlefieldWindow(title="Test Battlefield")
        window.create_window()

        assert window.is_open is True
        assert window.window is not None
        assert window.text_widget is not None
        fake_tk_env.Tk.assert_called_once()
        # Window title/geometry/protocol calls happened on the mock Tk instance.
        window.window.title.assert_called_with("Test Battlefield")
        window.window.protocol.assert_called_once()
        # Grid tags configured on the text widget.
        assert window.text_widget.tag_config.call_count >= 10


# ---------------------------------------------------------------------------
# on_close / close
# ---------------------------------------------------------------------------


class TestOnCloseAndClose:
    def test_on_close_destroys_window(self, fake_tk_env):
        window = CombatBattlefieldWindow()
        window.create_window()
        window.on_close()
        assert window.is_open is False
        assert window.window is None
        assert window.text_widget is None

    def test_on_close_swallows_tclerror(self, fake_tk_env):
        window = CombatBattlefieldWindow()
        window.create_window()
        window.window.destroy.side_effect = battlefield_module.tk.TclError("boom")
        # Should not raise.
        window.on_close()
        assert window.is_open is False

    def test_on_close_noop_when_no_window(self):
        window = CombatBattlefieldWindow()
        window.is_open = False
        window.on_close()
        assert window.window is None

    def test_close_calls_on_close_when_open(self, fake_tk_env):
        window = CombatBattlefieldWindow()
        window.create_window()
        window.close()
        assert window.is_open is False

    def test_close_noop_when_not_open(self):
        window = CombatBattlefieldWindow()
        window.is_open = False
        # Should not raise even without a window.
        window.close()
        assert window.is_open is False


# ---------------------------------------------------------------------------
# _render_initial_grid
# ---------------------------------------------------------------------------


class TestRenderInitialGrid:
    def test_noop_without_text_widget(self):
        window = CombatBattlefieldWindow()
        window.text_widget = None
        window._render_initial_grid()  # Should not raise.

    def test_renders_grid_text_into_widget(self, fake_tk_env):
        window = CombatBattlefieldWindow()
        window.create_window()  # populates text_widget via fake tkinter
        window.text_widget.reset_mock()
        window._render_initial_grid()
        window.text_widget.insert.assert_called_once()
        args, _ = window.text_widget.insert.call_args
        assert "#" in args[1]  # border characters present

    def test_swallows_tclerror(self, fake_tk_env):
        window = CombatBattlefieldWindow()
        window.create_window()
        window.text_widget.delete.side_effect = battlefield_module.tk.TclError("x")
        window._render_initial_grid()  # Should not raise.


# ---------------------------------------------------------------------------
# _get_direction_char
# ---------------------------------------------------------------------------


class TestGetDirectionChar:
    @pytest.mark.parametrize(
        "facing,expected",
        [
            (0, "↑"),
            (45, "↗"),
            (90, "→"),
            (135, "↘"),
            (180, "↓"),
            (225, "↙"),
            (270, "←"),
            (315, "↖"),
        ],
    )
    def test_cardinal_and_diagonal_directions(self, facing, expected):
        window = CombatBattlefieldWindow()
        assert window._get_direction_char(facing) == expected

    def test_normalizes_values_over_360(self):
        window = CombatBattlefieldWindow()
        assert window._get_direction_char(360) == "↑"
        assert window._get_direction_char(405) == "↗"  # 405 % 360 == 45

    def test_fallback_dot_for_unmatched_facing(self):
        """359 degrees is >22.5 away from both 0 and 315 -> falls through to '·'."""
        window = CombatBattlefieldWindow()
        assert window._get_direction_char(359) == "·"


# ---------------------------------------------------------------------------
# _get_health_indicator
# ---------------------------------------------------------------------------


class TestGetHealthIndicator:
    def test_critical_below_quarter(self):
        window = CombatBattlefieldWindow()
        assert window._get_health_indicator(0.1) == "!!"

    def test_injured_below_three_quarters(self):
        window = CombatBattlefieldWindow()
        assert window._get_health_indicator(0.5) == "!"

    def test_healthy_returns_empty(self):
        window = CombatBattlefieldWindow()
        assert window._get_health_indicator(1.0) == ""


# ---------------------------------------------------------------------------
# _update_viewport
# ---------------------------------------------------------------------------


class TestUpdateViewport:
    def test_no_combatants_shows_full_grid(self):
        window = CombatBattlefieldWindow()
        window._update_viewport()
        assert window.viewport_x_min == 0
        assert window.viewport_x_max == window.GRID_WIDTH - 1
        assert window.viewport_y_min == 0
        assert window.viewport_y_max == window.GRID_HEIGHT - 1

    def test_skips_entries_with_none_position(self):
        window = CombatBattlefieldWindow()
        window.combatants_data["ghost"] = {"position": None}
        window.set_combatant("e1", MockPosition(10, 10))
        window._update_viewport()
        # Should compute bounds using only the valid combatant.
        assert window.viewport_x_min <= 10 <= window.viewport_x_max

    def test_all_combatants_outside_grid_shows_full_grid(self):
        window = CombatBattlefieldWindow()
        window.set_combatant("far", MockPosition(1000, 1000))
        window._update_viewport()
        assert window.viewport_x_min == 0
        assert window.viewport_x_max == window.GRID_WIDTH - 1
        assert window.viewport_y_min == 0
        assert window.viewport_y_max == window.GRID_HEIGHT - 1

    def test_left_and_top_edge_expansion(self):
        """A combatant near the top-left corner should trigger both the
        left-edge-expand-right and top-edge-expand-down branches."""
        window = CombatBattlefieldWindow()
        window.set_combatant("corner", MockPosition(0, 0))
        window._update_viewport()
        assert window.viewport_x_min == 0
        assert window.viewport_x_max > window.margin  # expanded past bare margin
        assert window.viewport_y_min == 0
        assert window.viewport_y_max > window.margin

    def test_right_and_bottom_edge_expansion(self):
        """A combatant near the bottom-right corner should trigger both the
        right-edge-expand-left and bottom-edge-expand-up branches."""
        window = CombatBattlefieldWindow()
        gw, gh = window.GRID_WIDTH - 1, window.GRID_HEIGHT - 1
        window.set_combatant("corner", MockPosition(gw, gh))
        window._update_viewport()
        assert window.viewport_x_max == gw
        assert window.viewport_x_min < gw - window.margin
        assert window.viewport_y_max == gh
        assert window.viewport_y_min < gh - window.margin


# ---------------------------------------------------------------------------
# render_grid
# ---------------------------------------------------------------------------


class TestRenderGrid:
    def test_skips_combatant_with_none_position_in_overlay(self):
        window = CombatBattlefieldWindow()
        window.set_combatant("e1", MockPosition(10, 10))
        # Directly inject an entry with a None position to hit the "continue"
        # branch in the combatant-overlay loop (distinct from the viewport
        # loop's equivalent branch, already exercised above).
        window.combatants_data["ghost"] = {"position": None}
        text = window.render_grid()
        assert isinstance(text, str)

    def test_skips_combatant_outside_fixed_viewport(self):
        """Force a fixed viewport (bypassing _update_viewport) so a combatant
        whose position falls outside it hits the render-time viewport skip."""
        window = CombatBattlefieldWindow()
        window.set_combatant("in_view", MockPosition(12, 12))
        window.set_combatant("out_of_view", MockPosition(2, 2))
        with patch.object(window, "_update_viewport"):
            window.viewport_x_min = 10
            window.viewport_x_max = 20
            window.viewport_y_min = 10
            window.viewport_y_max = 20
            text = window.render_grid()
        assert "E" in text  # in_view combatant rendered
        assert isinstance(text, str)

    def test_ally_alive_character(self):
        window = CombatBattlefieldWindow()
        window.set_combatant("ally1", MockPosition(10, 10), is_ally=True)
        text = window.render_grid()
        assert "A" in text

    def test_dead_player_ally_enemy_lowercase(self):
        window = CombatBattlefieldWindow()
        window.set_combatant("p", MockPosition(5, 5), is_player=True, is_alive=False)
        window.set_combatant("a", MockPosition(6, 6), is_ally=True, is_alive=False)
        window.set_combatant("e", MockPosition(7, 7), is_alive=False)
        text = window.render_grid()
        assert "j" in text
        assert "a" in text  # dead ally lowercase
        assert "e" in text  # dead enemy lowercase

    def test_vertical_breadcrumb_padding(self):
        """Vertical movement (same x, different y) exercises the dx==0,dy!=0
        breadcrumb padding branch (single char + space)."""
        window = CombatBattlefieldWindow()
        window.set_combatant("mover", MockPosition(10, 10))
        window.set_combatant("mover", MockPosition(10, 15))
        text = window.render_grid()
        assert isinstance(text, str)

    def test_breadcrumb_with_no_direction_defaults_to_double(self):
        """Directly craft a movement_history with two identical positions so
        the Bresenham line is a single point with direction (0, 0), landing
        in the 'no direction info' fallback branch."""
        window = CombatBattlefieldWindow()
        from collections import deque

        window.set_combatant("e1", MockPosition(20, 20))
        # Manually seed a duplicate-position pair to force direction (0, 0).
        window.movement_history["e1"] = deque(
            [MockPosition(20, 20), MockPosition(20, 20)], maxlen=3
        )
        # Move combatant elsewhere so the breadcrumb segment isn't overwritten
        # by the combatant's own current-position overlay.
        window.combatants_data["e1"]["position"] = MockPosition(30, 30)
        text = window.render_grid()
        assert isinstance(text, str)


# ---------------------------------------------------------------------------
# update_display
# ---------------------------------------------------------------------------


class TestUpdateDisplay:
    def test_noop_when_not_open(self):
        window = CombatBattlefieldWindow()
        window.is_open = False
        window.update_display()  # Should not raise.

    def test_noop_when_no_text_widget(self):
        window = CombatBattlefieldWindow()
        window.is_open = True
        window.text_widget = None
        window.update_display()  # Should not raise.

    def test_updates_widget_and_info_label(self, fake_tk_env):
        window = CombatBattlefieldWindow()
        window.create_window()
        window.set_combatant("e1", MockPosition(10, 10))
        window.set_beat(3)
        window.update_display()
        window.info_label.config.assert_called_with(text="Beat: 3 | Combatants: 1")

    def test_swallows_tclerror_and_marks_closed(self, fake_tk_env):
        window = CombatBattlefieldWindow()
        window.create_window()
        window.text_widget.insert.side_effect = battlefield_module.tk.TclError("x")
        window.update_display()
        assert window.is_open is False


# ---------------------------------------------------------------------------
# _apply_grid_tags
# ---------------------------------------------------------------------------


class TestApplyGridTags:
    def test_noop_without_text_widget(self):
        window = CombatBattlefieldWindow()
        window.text_widget = None
        window._apply_grid_tags()  # Should not raise.

    def test_tags_borders_and_breadcrumbs(self, fake_tk_env):
        window = CombatBattlefieldWindow()
        window.create_window()
        window.text_widget.get.return_value = "##\n#·#\n##"
        window._apply_grid_tags()
        # Both border ('#') and breadcrumb ('·') tag_add calls should occur.
        tag_names = {c.args[0] for c in window.text_widget.tag_add.call_args_list}
        assert "border" in tag_names
        assert "breadcrumb" in tag_names

    def test_swallows_tclerror(self, fake_tk_env):
        window = CombatBattlefieldWindow()
        window.create_window()
        window.text_widget.get.side_effect = battlefield_module.tk.TclError("x")
        window._apply_grid_tags()  # Should not raise.


# ---------------------------------------------------------------------------
# _apply_color_tags
# ---------------------------------------------------------------------------


class TestApplyColorTags:
    def test_noop_without_text_widget(self):
        window = CombatBattlefieldWindow()
        window.text_widget = None
        window._apply_color_tags()  # Should not raise.

    def test_tags_each_combatant_type_and_health_state(self, fake_tk_env):
        window = CombatBattlefieldWindow()
        window.create_window()

        # Populate every branch: player/ally/enemy x healthy/injured/critical/dead.
        window.set_combatant("p", MockPosition(1, 1), is_player=True, health_percent=1.0)
        window.set_combatant(
            "p_inj", MockPosition(2, 2), is_player=True, health_percent=0.5
        )
        window.set_combatant(
            "p_crit", MockPosition(3, 3), is_player=True, health_percent=0.1
        )
        window.set_combatant("a", MockPosition(4, 4), is_ally=True, health_percent=1.0)
        window.set_combatant(
            "a_inj", MockPosition(5, 5), is_ally=True, health_percent=0.5
        )
        window.set_combatant(
            "a_crit", MockPosition(6, 6), is_ally=True, health_percent=0.1
        )
        window.set_combatant("e", MockPosition(7, 7), health_percent=1.0)
        window.set_combatant("e_inj", MockPosition(8, 8), health_percent=0.5)
        window.set_combatant("e_crit", MockPosition(9, 9), health_percent=0.1)
        window.set_combatant("dead", MockPosition(10, 10), is_alive=False)

        # Make search() return the display text once, then None to stop looping.
        seen = set()

        def _search(display_text, start, end):
            if display_text in seen:
                return None
            seen.add(display_text)
            return "1.0"

        window.text_widget.search.side_effect = _search
        window._apply_color_tags()

        tag_names = {c.args[0] for c in window.text_widget.tag_add.call_args_list}
        assert "dead" in tag_names

    def test_swallows_search_errors(self, fake_tk_env):
        window = CombatBattlefieldWindow()
        window.create_window()
        window.set_combatant("e1", MockPosition(1, 1))
        window.text_widget.search.side_effect = battlefield_module.tk.TclError("x")
        window._apply_color_tags()  # Should not raise.


# ---------------------------------------------------------------------------
# set_combatant
# ---------------------------------------------------------------------------


class TestSetCombatant:
    def test_removes_combatant_when_position_none(self):
        window = CombatBattlefieldWindow()
        window.set_combatant("e1", MockPosition(1, 1))
        assert "e1" in window.combatants_data
        window.set_combatant("e1", None)
        assert "e1" not in window.combatants_data
        assert "e1" not in window.movement_history

    def test_remove_nonexistent_combatant_is_noop(self):
        window = CombatBattlefieldWindow()
        window.set_combatant("ghost", None)  # Should not raise.
        assert "ghost" not in window.combatants_data

    def test_ally_alive_display_char(self):
        window = CombatBattlefieldWindow()
        window.set_combatant("a1", MockPosition(1, 1), is_ally=True)
        assert window.combatants_data["a1"]["display_text"].startswith(
            window.ALLY_CHAR
        )

    def test_dead_player_ally_enemy_display_chars(self):
        window = CombatBattlefieldWindow()
        window.set_combatant("p", MockPosition(1, 1), is_player=True, is_alive=False)
        window.set_combatant("a", MockPosition(2, 2), is_ally=True, is_alive=False)
        window.set_combatant("e", MockPosition(3, 3), is_alive=False)
        assert window.combatants_data["p"]["display_text"].startswith(
            window.PLAYER_CHAR.lower()
        )
        assert window.combatants_data["a"]["display_text"].startswith(
            window.ALLY_CHAR.lower()
        )
        assert window.combatants_data["e"]["display_text"].startswith(
            window.ENEMY_CHAR.lower()
        )

    def test_health_percent_clamped(self):
        window = CombatBattlefieldWindow()
        window.set_combatant("e1", MockPosition(1, 1), health_percent=5.0)
        assert window.combatants_data["e1"]["health_percent"] == 1.0
        window.set_combatant("e1", MockPosition(1, 1), health_percent=-5.0)
        assert window.combatants_data["e1"]["health_percent"] == 0.0

    def test_history_copy_fallback_on_exception(self):
        """A position without .copy() should fall back to appending the
        position object as-is (still hits the try/except path since hasattr
        is False and the except branch is only reachable via an actual
        exception; this exercises the non-copy path deterministically)."""
        window = CombatBattlefieldWindow()
        pos1 = _NoCopyPosition(1, 1)
        pos2 = _NoCopyPosition(2, 2)
        window.set_combatant("e1", pos1)
        window.set_combatant("e1", pos2)
        assert list(window.movement_history["e1"])[-1] is pos2

    def test_history_append_raises_is_swallowed(self):
        """Force position.copy() itself to raise so the except branch runs."""
        window = CombatBattlefieldWindow()

        class RaisingCopyPosition:
            def __init__(self, x, y):
                self.x = x
                self.y = y

            def copy(self):
                raise TypeError("cannot copy")

        pos1 = RaisingCopyPosition(1, 1)
        pos2 = RaisingCopyPosition(2, 2)
        window.set_combatant("e1", pos1)
        window.set_combatant("e1", pos2)
        assert list(window.movement_history["e1"])[-1] is pos2


# ---------------------------------------------------------------------------
# set_beat
# ---------------------------------------------------------------------------


class TestSetBeat:
    def test_updates_beat_number(self):
        window = CombatBattlefieldWindow()
        window.set_beat(42)
        assert window.beat_number == 42


# ---------------------------------------------------------------------------
# update_all_combatants
# ---------------------------------------------------------------------------


class _FakeFacingEnum:
    def __init__(self, value):
        self.value = value


class _FakeCombatPosition:
    def __init__(self, x, y, facing=None):
        self.x = x
        self.y = y
        self.facing = facing

    def copy(self):
        return _FakeCombatPosition(self.x, self.y, self.facing)


class _FakeCombatant:
    """Minimal stand-in for Player/NPC used to drive update_all_combatants."""

    def __init__(
        self,
        name=None,
        combat_position=None,
        current_health=100,
        maxhealth=100,
        alive=True,
    ):
        if name is not None:
            self.name = name
        self.combat_position = combat_position
        self.current_health = current_health
        self.maxhealth = maxhealth
        self._alive = alive

    def is_alive(self):
        return self._alive


class TestUpdateAllCombatants:
    def test_player_without_combat_position_is_skipped(self):
        window = CombatBattlefieldWindow()
        player = _FakeCombatant(name="Jean", combat_position=None)
        window.update_all_combatants(player, [], [])
        assert "Jean" not in window.combatants_data

    def test_player_default_name_when_missing_name_attr(self):
        window = CombatBattlefieldWindow()

        class NoName:
            combat_position = _FakeCombatPosition(1, 1)
            current_health = 50
            maxhealth = 100

            def is_alive(self):
                return True

        window.update_all_combatants(NoName(), [], [])
        assert "Player" in window.combatants_data

    def test_player_facing_enum_and_raw_numeric(self):
        window = CombatBattlefieldWindow()
        player = _FakeCombatant(
            name="Jean",
            combat_position=_FakeCombatPosition(5, 5, facing=_FakeFacingEnum(90)),
        )
        window.update_all_combatants(player, [], [])
        assert window.combatants_data["Jean"]["facing_value"] == 90

        window2 = CombatBattlefieldWindow()
        player2 = _FakeCombatant(
            name="Jean", combat_position=_FakeCombatPosition(5, 5, facing=180)
        )
        window2.update_all_combatants(player2, [], [])
        assert window2.combatants_data["Jean"]["facing_value"] == 180

    def test_ally_skipped_when_same_name_as_player(self):
        window = CombatBattlefieldWindow()
        player = _FakeCombatant(name="Jean", combat_position=_FakeCombatPosition(1, 1))
        duplicate_ally = _FakeCombatant(
            name="Jean", combat_position=_FakeCombatPosition(9, 9)
        )
        window.update_all_combatants(player, [duplicate_ally], [])
        # Only the player's own position should be recorded under "Jean".
        assert window.combatants_data["Jean"]["position"].x == 1

    def test_ally_default_name_and_health(self):
        window = CombatBattlefieldWindow()
        player = _FakeCombatant(name="Jean", combat_position=_FakeCombatPosition(1, 1))

        class NamelessAlly:
            combat_position = _FakeCombatPosition(2, 2)

            def is_alive(self):
                return True

        ally = NamelessAlly()
        window.update_all_combatants(player, [ally], [])
        expected_name = f"Ally_{id(ally)}"
        assert expected_name in window.combatants_data
        assert window.combatants_data[expected_name]["health_percent"] == 1.0

    def test_enemy_default_name_and_health_and_facing(self):
        window = CombatBattlefieldWindow()
        player = _FakeCombatant(name="Jean", combat_position=_FakeCombatPosition(1, 1))

        class NamelessEnemy:
            combat_position = _FakeCombatPosition(8, 8, facing=_FakeFacingEnum(270))
            current_health = 10
            maxhealth = 40

            def is_alive(self):
                return True

        enemy = NamelessEnemy()
        window.update_all_combatants(player, [], [enemy])
        expected_name = f"Enemy_{id(enemy)}"
        assert expected_name in window.combatants_data
        assert window.combatants_data[expected_name]["health_percent"] == 0.25
        assert window.combatants_data[expected_name]["facing_value"] == 270

    def test_stale_combatants_removed(self):
        window = CombatBattlefieldWindow()
        player = _FakeCombatant(name="Jean", combat_position=_FakeCombatPosition(1, 1))
        enemy = _FakeCombatant(
            name="Goblin", combat_position=_FakeCombatPosition(5, 5)
        )
        window.update_all_combatants(player, [], [enemy])
        assert "Goblin" in window.combatants_data
        assert "Goblin" in window.movement_history

        # Next call omits the enemy entirely -> should be cleaned up.
        window.update_all_combatants(player, [], [])
        assert "Goblin" not in window.combatants_data
        assert "Goblin" not in window.movement_history

    def test_full_bulk_update_player_ally_enemy(self):
        window = CombatBattlefieldWindow()
        player = _FakeCombatant(name="Jean", combat_position=_FakeCombatPosition(1, 1))
        ally = _FakeCombatant(
            name="Gorran", combat_position=_FakeCombatPosition(2, 2)
        )
        enemy = _FakeCombatant(
            name="Slime", combat_position=_FakeCombatPosition(3, 3)
        )
        window.update_all_combatants(player, [ally], [enemy])
        assert set(window.combatants_data.keys()) == {"Jean", "Gorran", "Slime"}
