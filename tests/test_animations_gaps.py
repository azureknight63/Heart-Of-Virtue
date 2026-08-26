"""tests/test_animations_gaps.py

Coverage tests for src/animations.py — targeting uncovered lines:
58-78, 95, 219-238, 257-277, 281
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# set_api_mode
# ---------------------------------------------------------------------------


def test_set_api_mode_true():
    """set_api_mode(True) sets the module _API_MODE flag."""
    import src.animations as animations

    animations.set_api_mode(True)
    assert animations._API_MODE is True
    # Reset
    animations.set_api_mode(False)


def test_set_api_mode_false():
    """set_api_mode(False) clears the module _API_MODE flag."""
    import src.animations as animations

    animations.set_api_mode(True)
    animations.set_api_mode(False)
    assert animations._API_MODE is False


# ---------------------------------------------------------------------------
# animate_to_main_screen — API mode suppresses animation
# ---------------------------------------------------------------------------


def test_animate_to_main_screen_api_mode_returns_early():
    """animate_to_main_screen returns immediately when _API_MODE is True."""
    import src.animations as animations

    animations.set_api_mode(True)
    try:
        # Screen.wrapper should NOT be called; if it were, it would raise
        with patch.object(animations, "Screen") as mock_screen:
            animations.animate_to_main_screen("some_animation", "text")
            mock_screen.wrapper.assert_not_called()
    finally:
        animations.set_api_mode(False)


# ---------------------------------------------------------------------------
# animate_to_main_screen — gif path (line 223-225)
# ---------------------------------------------------------------------------


def test_animate_to_main_screen_no_terminal_returns_early():
    """animate_to_main_screen skips when stdout is not a real terminal
    (pytest/CI/headless) — curses would raise 'setupterm' otherwise."""
    import src.animations as animations

    animations.set_api_mode(False)
    with patch.object(animations, "_terminal_available", return_value=False):
        with patch.object(animations.Screen, "wrapper") as mock_wrapper:
            animations.animate_to_main_screen("flash.gif", "rawtext")
    mock_wrapper.assert_not_called()


def test_animate_to_main_screen_gif_strips_the_extension_from_the_name():
    """play_gif takes a bare stem, so the .gif suffix must be stripped.

    The old assertion was a bare `assert_called_once()`, which would have held
    even if the full "flash.gif" (or an empty string) had been forwarded --
    play_gif re-appends ".gif", so passing it through unstripped resolves to
    "flash.gif.gif" and the animation silently never plays.
    """
    import src.animations as animations

    animations.set_api_mode(False)
    with patch.object(animations, "_terminal_available", return_value=True):
        with patch.object(animations.Screen, "wrapper") as mock_wrapper:
            animations.animate_to_main_screen("flash.gif", "")

    mock_wrapper.assert_called_once_with(
        func=animations.play_gif, arguments=["flash", ""]
    )


# ---------------------------------------------------------------------------
# animate_to_main_screen — function path (lines 228-236)
# ---------------------------------------------------------------------------


def test_animate_to_main_screen_dispatches_a_named_function_positionally():
    """With no text, the function is passed positionally with no arguments list.

    The old assertion was a bare `assert_called_once()`, which could not tell
    the no-text branch (positional) from the with-text branch (keyword +
    arguments) -- the two are different call shapes in the source.
    """
    import src.animations as animations

    animations.set_api_mode(False)
    with patch.object(animations, "_terminal_available", return_value=True):
        with patch.object(animations.Screen, "wrapper") as mock_wrapper:
            animations.animate_to_main_screen("demo", "")

    mock_wrapper.assert_called_once_with(animations.demo)


def test_animate_to_main_screen_function_with_text():
    """animate_to_main_screen passes text as argument when provided."""
    import src.animations as animations

    animations.set_api_mode(False)
    with patch.object(animations, "_terminal_available", return_value=True):
        with patch.object(animations.Screen, "wrapper") as mock_wrapper:
            animations.animate_to_main_screen("demo", "some text here")
    mock_wrapper.assert_called_once()
    # Verify arguments were passed
    _, kwargs = mock_wrapper.call_args
    assert "arguments" in kwargs


def test_animate_to_main_screen_not_found(capsys):
    """animate_to_main_screen prints error for unknown function names."""
    import src.animations as animations

    animations.set_api_mode(False)
    with patch.object(animations, "_terminal_available", return_value=True):
        animations.animate_to_main_screen("nonexistent_function_xyz", "")
    out = capsys.readouterr().out
    assert "Animation not found" in out


# ---------------------------------------------------------------------------
# main() — lines 58-78
# ---------------------------------------------------------------------------


def test_main_no_args_gif(monkeypatch):
    """main() with a .gif argument dispatches play_gif with the bare stem."""
    import src.animations as animations

    monkeypatch.setattr(sys, "argv", ["animations.py", "test.gif"])
    with patch.object(animations.Screen, "wrapper") as mock_wrapper:
        animations.main()

    # Unlike animate_to_main_screen, main() passes no text argument.
    mock_wrapper.assert_called_once_with(
        func=animations.play_gif, arguments=["test"]
    )


def test_main_no_args_function_exists(monkeypatch):
    """main() with a function name that exists in the module dispatches it."""
    import src.animations as animations

    monkeypatch.setattr(sys, "argv", ["animations.py", "demo"])
    with patch.object(animations.Screen, "wrapper") as mock_wrapper:
        animations.main()
    # The module-level ``demo`` function should be dispatched to Screen.wrapper.
    mock_wrapper.assert_called_once_with(animations.demo)


def test_main_no_args_not_found(monkeypatch, capsys):
    """main() with an unknown animation name prints the error and plays nothing.

    The old version called ``capsys.readouterr()`` and threw the result away
    with the comment "either path runs without exception" -- so the test named
    "not found" could not distinguish the error path from a successful play.
    """
    import src.animations as animations

    monkeypatch.setattr(sys, "argv", ["animations.py", "nonexistent_anim"])
    with patch.object(animations.Screen, "wrapper") as mock_wrapper:
        animations.main()

    assert "### Animation not found!" in capsys.readouterr().out
    mock_wrapper.assert_not_called()


def test_main_too_many_args(monkeypatch):
    """main() with two extra args prompts input then calls Screen.wrapper(demo)."""
    import src.animations as animations
    import pytest

    monkeypatch.setattr(sys, "argv", ["animations.py", "arg1", "arg2"])
    with patch("builtins.input", return_value=""):
        with patch.object(animations.Screen, "wrapper") as mock_wrapper:
            with pytest.raises(SystemExit):
                animations.main()
    mock_wrapper.assert_called_once()


def test_main_resize_screen_error_is_swallowed_without_exiting(monkeypatch):
    """A terminal resize aborts the demo but must not kill the process.

    The happy path of this branch calls ``sys.exit(0)``; the ResizeScreenError
    path deliberately does not. The old version asserted nothing, so it could
    not tell those two apart -- a regression that let SystemExit escape on a
    resize would still have passed.
    """
    import src.animations as animations
    from asciimatics.exceptions import ResizeScreenError

    monkeypatch.setattr(sys, "argv", ["animations.py", "arg1", "arg2"])
    with patch("builtins.input", return_value="") as mock_input:
        with patch.object(
            animations.Screen, "wrapper", side_effect=ResizeScreenError("resize")
        ) as mock_wrapper:
            animations.main()  # must NOT raise SystemExit

    mock_input.assert_called_once_with("### no arguments passed to script!")
    mock_wrapper.assert_called_once_with(animations.demo)


# ---------------------------------------------------------------------------
# memory_flash (lines 249-277)
# ---------------------------------------------------------------------------


def test_memory_flash_runs():
    """memory_flash creates Print effects and calls screen.play."""
    import src.animations as animations

    screen_mock = MagicMock()
    screen_mock.height = 24

    with patch.object(animations, "Print") as mock_print_cls:
        with patch.object(animations, "Stars") as mock_stars_cls:
            with patch.object(animations, "Scene"):
                animations.memory_flash(screen_mock)

    # Should create 6 Print effects + 1 Stars effect
    assert mock_print_cls.call_count == 6
    mock_stars_cls.assert_called_once_with(screen_mock, 300)
    screen_mock.play.assert_called_once()


def test_memory_flash_scene_config():
    """memory_flash passes Scene with duration 48."""
    import src.animations as animations

    screen_mock = MagicMock()
    screen_mock.height = 24

    captured_scene_args = []

    def mock_scene(effects, duration):
        captured_scene_args.append((effects, duration))
        return MagicMock()

    with patch.object(animations, "Print", return_value=MagicMock()):
        with patch.object(animations, "Stars", return_value=MagicMock()):
            with patch.object(animations, "Scene", side_effect=mock_scene):
                animations.memory_flash(screen_mock)

    assert len(captured_scene_args) == 1
    _, duration = captured_scene_args[0]
    assert duration == 48


def test_memory_flash_alternates_colors():
    """memory_flash alternates between color 5 (magenta) and 7 (white)."""
    import src.animations as animations

    screen_mock = MagicMock()
    screen_mock.height = 24

    colors_used = []

    def capture_print(*args, **kwargs):
        colors_used.append(kwargs.get("colour"))
        return MagicMock()

    with patch.object(animations, "Print", side_effect=capture_print):
        with patch.object(animations, "Stars", return_value=MagicMock()):
            with patch.object(animations, "Scene", return_value=MagicMock()):
                animations.memory_flash(screen_mock)

    assert 5 in colors_used  # magenta
    assert 7 in colors_used  # white
    assert colors_used[0] == 5  # starts with magenta


def test_memory_flash_stop_on_resize():
    """memory_flash passes stop_on_resize=True to screen.play."""
    import src.animations as animations

    screen_mock = MagicMock()
    screen_mock.height = 24

    with patch.object(animations, "Print", return_value=MagicMock()):
        with patch.object(animations, "Stars", return_value=MagicMock()):
            with patch.object(animations, "Scene", return_value=MagicMock()):
                animations.memory_flash(screen_mock)

    _, play_kwargs = screen_mock.play.call_args
    assert play_kwargs.get("stop_on_resize") is True
    assert play_kwargs.get("repeat") is False
