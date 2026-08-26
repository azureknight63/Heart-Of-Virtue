"""
Unit tests for animations module
"""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from PIL import Image
import tempfile
import os


@pytest.fixture
def mock_gif():
    """Create a temporary mock GIF file for testing"""
    with tempfile.NamedTemporaryFile(suffix='.gif', delete=False) as tmp:
        # Create a simple 2-frame GIF
        img1 = Image.new('RGB', (10, 10), color='red')
        img2 = Image.new('RGB', (10, 10), color='blue')
        img1.save(tmp.name, save_all=True, append_images=[img2], duration=100, loop=0)
        yield tmp.name
    os.unlink(tmp.name)


def test_count_gif_frames(mock_gif):
    """Test counting frames in a GIF file"""
    from src.animations import count_gif_frames

    frame_count = count_gif_frames(mock_gif)
    assert frame_count == 2


def test_count_gif_frames_single_frame():
    """Test counting frames in a single-frame image"""
    from src.animations import count_gif_frames

    with tempfile.NamedTemporaryFile(suffix='.gif', delete=False) as tmp:
        tmp_name = tmp.name
        img = Image.new('RGB', (10, 10), color='green')
        img.save(tmp_name)

    try:
        frame_count = count_gif_frames(tmp_name)
        assert frame_count == 1
    finally:
        try:
            os.unlink(tmp_name)
        except PermissionError:
            pass  # File may still be locked on Windows


def test_function_exists_valid():
    """Test function_exists with a valid function"""
    from src.animations import function_exists

    class MockModule:
        def test_func(self):
            pass

    module = MockModule()
    assert function_exists(module, 'test_func') is True


def test_function_exists_invalid():
    """Test function_exists with an invalid function"""
    from src.animations import function_exists

    class MockModule:
        test_var = 123

    module = MockModule()
    assert function_exists(module, 'test_var') is False
    assert function_exists(module, 'nonexistent') is False


def test_function_exists_not_callable():
    """Test function_exists with a non-callable attribute"""
    from src.animations import function_exists

    class MockModule:
        test_attr = "not a function"

    module = MockModule()
    assert function_exists(module, 'test_attr') is False


@patch('src.animations.Screen')
def test_demo_prints_the_placeholder_text_within_screen_bounds(mock_screen):
    """demo() draws its placeholder text at a random in-bounds position.

    The old assertion was `assert screen_mock.print_at.called`, which held for
    any call with any arguments -- including drawing empty text off-screen.
    """
    from src.animations import demo

    screen_mock = Mock()
    screen_mock.width = 80
    screen_mock.height = 24
    screen_mock.colours = 8
    screen_mock.get_key.return_value = ord('q')  # exit after one frame

    demo(screen_mock)

    screen_mock.print_at.assert_called_once()
    (text, x, y), kwargs = screen_mock.print_at.call_args
    assert text == "This is the placeholder animation!"
    assert 0 <= x <= screen_mock.width
    assert 0 <= y <= screen_mock.height
    # Colours are picked from the screen's own palette, never beyond it.
    assert 0 <= kwargs["colour"] <= screen_mock.colours - 1
    assert 0 <= kwargs["bg"] <= screen_mock.colours - 1


@patch('src.animations.Screen')
def test_demo_exit_on_q(mock_screen):
    """Test demo exits when 'q' is pressed"""
    from src.animations import demo

    screen_mock = Mock()
    screen_mock.width = 80
    screen_mock.height = 24
    screen_mock.colours = 8
    screen_mock.get_key.return_value = ord('q')

    # Should return without error
    result = demo(screen_mock)
    assert result is None


@patch('src.animations.Screen')
def test_demo_exit_on_capital_q(mock_screen):
    """Test demo exits when 'Q' is pressed"""
    from src.animations import demo

    screen_mock = Mock()
    screen_mock.width = 80
    screen_mock.height = 24
    screen_mock.colours = 8
    screen_mock.get_key.return_value = ord('Q')

    result = demo(screen_mock)
    assert result is None


@patch('src.animations.Path')
@patch('src.animations.count_gif_frames')
@patch('src.animations.ColourImageFile')
@patch('src.animations.SpeechBubble')
@patch('src.animations.Print')
@patch('src.animations.Scene')
def test_play_gif_file_exists(mock_scene, mock_print, mock_bubble, mock_image,
                               mock_count, mock_path):
    """Test play_gif when file exists"""
    from src.animations import play_gif

    # Setup mocks
    screen_mock = Mock()
    screen_mock.height = 24
    screen_mock.unicode_aware = True
    mock_path.return_value.exists.return_value = True
    mock_count.return_value = 10

    play_gif(screen_mock, "test_animation", "test text")

    # The frame count is read from the resolved gif path and the scene is
    # played once, non-repeating and resize-safe. The old assertions were
    # `assert mock_count.called` / `assert screen_mock.play.called`, which
    # said nothing about which file was opened or how it was played.
    mock_count.assert_called_once_with("./resources/animations/test_animation.gif")
    screen_mock.play.assert_called_once()
    (scenes,), play_kwargs = screen_mock.play.call_args
    assert len(scenes) == 1
    assert play_kwargs == {"repeat": False, "stop_on_resize": True}


@patch('src.animations.Path')
@patch('builtins.print')
def test_play_gif_file_not_exists(mock_print, mock_path):
    """Test play_gif when file doesn't exist"""
    from src.animations import play_gif

    screen_mock = Mock()
    mock_path.return_value.exists.return_value = False

    play_gif(screen_mock, "nonexistent", "")

    # Should print error message
    mock_print.assert_called_with("### Animation not found!")


@patch('src.animations.Path')
@patch('src.animations.ColourImageFile')
@patch('src.animations.Print')
@patch('src.animations.Scene')
def test_display_static_image_exists(mock_scene, mock_print, mock_image, mock_path):
    """Test display_static_image when file exists"""
    from src.animations import display_static_image

    screen_mock = Mock()
    screen_mock.height = 24
    screen_mock.unicode_aware = True
    mock_path.return_value.exists.return_value = True

    display_static_image(screen_mock, "test.png")

    # The image is resolved under resources/images and played once, without
    # repeating. `assert screen_mock.play.called` proved none of that.
    mock_path.assert_called_once_with("./resources/images/test.png")
    screen_mock.play.assert_called_once()
    _, play_kwargs = screen_mock.play.call_args
    assert play_kwargs == {"repeat": False, "stop_on_resize": True}


@patch('src.animations.Path')
@patch('builtins.print')
def test_display_static_image_not_exists(mock_print, mock_path):
    """Test display_static_image when file doesn't exist"""
    from src.animations import display_static_image

    screen_mock = Mock()
    mock_path.return_value.exists.return_value = False

    display_static_image(screen_mock, "nonexistent.png")

    mock_print.assert_called_with("### Animation not found!")


# NOTE: three tests named ``test_animate_to_main_screen_{gif,function,not_found}``
# used to live here. They called ``animate_to_main_screen`` and asserted nothing
# ("Test that it runs without error"). Worse, under pytest ``_terminal_available()``
# is False, so the function returned on its second line and none of the branches
# they were named for ever executed. Every branch they claimed to cover is really
# covered in tests/test_animations_gaps.py -- ``test_animate_to_main_screen_gif_path_detail``,
# ``test_animate_to_main_screen_existing_function`` and
# ``test_animate_to_main_screen_not_found`` -- which force ``_terminal_available``
# True and assert on the dispatched function and arguments.


@patch('src.animations.Screen')
def test_image_to_main_screen(mock_screen):
    """Test image_to_main_screen function"""
    from src.animations import image_to_main_screen

    mock_screen.wrapper = Mock()

    image_to_main_screen("test.png")

    # It must dispatch display_static_image with the image name -- not merely
    # call Screen.wrapper with something.
    from src.animations import display_static_image

    mock_screen.wrapper.assert_called_once_with(
        func=display_static_image, arguments=["test.png"]
    )


@patch('src.animations.Screen')
@patch('src.animations.ColourImageFile')
@patch('src.animations.ImageFile')
def test_title_scene(mock_image_file, mock_colour_image, mock_screen):
    """Test title_scene function"""
    from src.animations import title_scene

    screen_mock = Mock()
    screen_mock.height = 24

    title_scene(screen_mock)

    # Should call play twice (color and non-color versions)
    assert screen_mock.play.call_count >= 1


@patch('src.animations.Screen')
@patch('src.animations.Cycle')
@patch('src.animations.Stars')
def test_demo2(mock_stars, mock_cycle, mock_screen):
    """Test demo2 function"""
    from src.animations import demo2

    screen_mock = Mock()
    screen_mock.height = 24

    demo2(screen_mock)

    # Two Cycle banners plus a Stars field, played as one scene.
    assert mock_cycle.call_count == 2
    mock_stars.assert_called_once_with(screen_mock, 200)
    screen_mock.play.assert_called_once()
    (scenes,), _ = screen_mock.play.call_args
    assert len(scenes) == 1
