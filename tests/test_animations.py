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
def test_demo_screen_output(mock_screen):
    """Test demo function prints to screen"""
    from src.animations import demo
    
    # Mock screen object
    screen_mock = Mock()
    screen_mock.width = 80
    screen_mock.height = 24
    screen_mock.colours = 8
    screen_mock.get_key.return_value = ord('q')  # Exit immediately
    
    demo(screen_mock)
    
    # Verify print_at was called
    assert screen_mock.print_at.called


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
    
    # Verify methods were called
    assert mock_count.called
    assert screen_mock.play.called


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
    
    assert screen_mock.play.called


@patch('src.animations.Path')
@patch('builtins.print')
def test_display_static_image_not_exists(mock_print, mock_path):
    """Test display_static_image when file doesn't exist"""
    from src.animations import display_static_image
    
    screen_mock = Mock()
    mock_path.return_value.exists.return_value = False
    
    display_static_image(screen_mock, "nonexistent.png")
    
    mock_print.assert_called_with("### Animation not found!")


@patch('src.animations.Screen')
@patch('src.animations.function_exists')
def test_animate_to_main_screen_gif(mock_func_exists, mock_screen):
    """Test animate_to_main_screen with a gif file"""
    from src.animations import animate_to_main_screen
    
    # Don't actually run the screen wrapper
    mock_screen.wrapper = Mock()
    
    animate_to_main_screen("test.gif", "some text")
    
    # Verify wrapper was called
    assert mock_screen.wrapper.called


@patch('src.animations.Screen')
@patch('src.animations.function_exists')
@patch('src.animations.getattr')
def test_animate_to_main_screen_function(mock_getattr, mock_func_exists, mock_screen):
    """Test animate_to_main_screen with a function name"""
    from src.animations import animate_to_main_screen
    
    mock_func_exists.return_value = True
    mock_screen.wrapper = Mock()
    
    animate_to_main_screen("demo", "")
    
    assert mock_screen.wrapper.called


@patch('src.animations.Screen')
@patch('src.animations.function_exists')
@patch('builtins.print')
def test_animate_to_main_screen_not_found(mock_print, mock_func_exists, mock_screen):
    """Test animate_to_main_screen with non-existent animation"""
    from src.animations import animate_to_main_screen
    
    mock_func_exists.return_value = False
    
    animate_to_main_screen("nonexistent", "")
    
    mock_print.assert_called_with("### Animation not found!")


@patch('src.animations.Screen')
def test_image_to_main_screen(mock_screen):
    """Test image_to_main_screen function"""
    from src.animations import image_to_main_screen
    
    mock_screen.wrapper = Mock()
    
    image_to_main_screen("test.png")
    
    assert mock_screen.wrapper.called


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
    
    assert screen_mock.play.called
