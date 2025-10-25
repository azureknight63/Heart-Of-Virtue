from random import randint
import sys
# import time
from pathlib import Path

# Avoid importing src.functions at module import time to prevent circular imports.
# clean_string is imported only where needed (inside animate_to_main_screen).

from asciimatics.effects import Cycle, Stars, Print
from asciimatics.renderers import FigletText, ColourImageFile, ImageFile, SpeechBubble
from asciimatics.scene import Scene
from asciimatics.screen import Screen
from asciimatics.exceptions import ResizeScreenError

from PIL import Image


def count_gif_frames(gif_path):
    with Image.open(gif_path) as img:
        frame_count = 0
        try:
            while True:
                img.seek(frame_count)  # Move to the next frame
                frame_count += 1
        except EOFError:
            pass  # Reached the end of the GIF
    return frame_count


def function_exists(module, function_name):
    return hasattr(module, function_name) and callable(getattr(module, function_name))


def main():
    # input("### args: "+" ".join(sys.argv))
    # input("len(sys.argv): " + str(len(sys.argv)))
    # input(f"{sys.argv[1]}")
    if len(sys.argv) < 3:
        animation = sys.argv[1]
        # input(animation)
        if ".gif" in animation:
            file_to_play = animation.replace(".gif", "")
            Screen.wrapper(func=play_gif, arguments=[file_to_play])
        else:
            if function_exists('animations.py', animation):
                Screen.wrapper(getattr('animations.py', animation))  # execute the animation
            else:
                print("### Animation not found!")
    else:
        # Screen.wrapper(demo)
        input("### no arguments passed to script!")
        try:
            Screen.wrapper(demo)
            sys.exit(0)
        except ResizeScreenError:
            pass
    # time.sleep(10)
    # input("Press any key to close")


def demo(screen):
    while True:
        screen.print_at('This is the placeholder animation!',
                        randint(0, screen.width), randint(0, screen.height),
                        colour=randint(0, screen.colours - 1),
                        bg=randint(0, screen.colours - 1))
        ev = screen.get_key()
        if ev in (ord('Q'), ord('q')):
            return
        screen.refresh()


def demo2(screen):
    effects = [
        Cycle(
            screen,
            FigletText("ASCIIMATICS", font='big'),
            int(screen.height / 2 - 8)),
        Cycle(
            screen,
            FigletText("ROCKS!", font='big'),
            int(screen.height / 2 + 3)),
        Stars(screen, 200)
    ]
    screen.play([Scene(effects, 500)])


def play_gif(screen, file, text=""):
    """
    Plays the selected gif file.
    :param screen: the Screen object; handled by the Screen.wrapper function
    :param file: the name of the file without any path or extension
    :param text: Text to display with the animation, if any.
    """
    filepath = f"./resources/animations/{file}.gif"
    if Path(filepath).exists():
        scenes = []
        effects = [
            Print(screen,
                  ColourImageFile(screen, filepath, screen.height - 2,
                                  uni=screen.unicode_aware, dither=screen.unicode_aware),
                  0, 0, speed=1, stop_frame=count_gif_frames(filepath), transparent=False),
            Print(screen,
                  SpeechBubble(text),
                  0
                  )
        ]
        scenes.append(Scene(effects))
        screen.play(scenes, repeat=False, stop_on_resize=True)
    else:
        print("### Animation not found!")


def display_static_image(screen, file):
    """
        Plays the selected static image file.
        :param screen: the Screen object; handled by the Screen.wrapper function
        :param file: the name of the file with extension, no path
        """
    filepath = f"./resources/images/{file}"
    if Path(filepath).exists():
        effects = [
            Print(screen,
                  ColourImageFile(screen, filepath, screen.height - 2,
                                  uni=screen.unicode_aware, dither=screen.unicode_aware),
                  0, 0),
        ]
        scene = Scene(effects, 500)
        screen.play(scene, repeat=False, stop_on_resize=True)
    else:
        print("### Animation not found!")


def title_scene(screen):  # just for testing. I don't think I actually want to use this!
    effects = [
        Print(screen,
              ColourImageFile(screen, "./resources/images/title_scene.png", screen.height),
              0,
              speed=1, transparent=False,
              stop_frame=100)
    ]
    screen.play([Scene(effects, 0)], repeat=False)
    effects = [
        Print(screen,
              ImageFile("./resources/images/title_scene.png", 30),
              # ColourImageFile(screen, "./resources/images/title_scene.png", screen.height),
              0,
              speed=1, transparent=False,
              stop_frame=100)
    ]
    screen.play([Scene(effects, 0)], repeat=False)


def animate_to_main_screen(animation, rawtext=""):
    """
    Plays the selected animation on the primary screen
    :param animation: Name of one of the animation functions defined in the animations.py module OR the
    filename of a gif in resources/animations, as a string
    :param rawtext: Text to display with the animation, if any. You can pass in colored text (color will be stripped)
    """
    # Import here to avoid circular import: functions imports moves, and moves imports animations.
    from functions import clean_string
    import sys
    
    text = clean_string(rawtext)
    if ".gif" in animation:
        file_to_play = animation.replace(".gif", "")
        Screen.wrapper(func=play_gif, arguments=[file_to_play, text])
    else:
        # Get the current module to check for the animation function
        current_module = sys.modules[__name__]
        if hasattr(current_module, animation) and callable(getattr(current_module, animation)):
            animation_func = getattr(current_module, animation)
            if text:
                Screen.wrapper(func=animation_func, arguments=[text])
            else:
                Screen.wrapper(animation_func)
        else:
            print("### Animation not found!")


def image_to_main_screen(image):
    """
        Displays the selected image on the primary screen
        :param image: Name of image resources/images, as a string, includes extension
        """
    Screen.wrapper(func=display_static_image, arguments=[image])


def memory_flash(screen):
    """
    Displays a memory flash animation - a shimmering, ethereal effect
    to indicate Jean is remembering something from his past.
    Text pulses between magenta and white for an ethereal, dreamlike quality.
    """
    # Duration reduced by 40%: 60 frames -> 36 frames (~1.8 seconds at 20fps)
    # Create multiple Print effects at different frames to simulate color cycling
    effects = []
    
    # Alternate between magenta (5) and white (7) every 6 frames
    for i in range(6):
        color = 5 if i % 2 == 0 else 7  # Magenta, then White
        effects.append(
            Print(
                screen,
                FigletText("A MEMORY ECHOES", font='banner'),
                y=int(screen.height / 2 - 4),
                colour=color,
                speed=1,
                start_frame=i * 6,
                stop_frame=(i + 1) * 6)
        )
    
    # Add stars effect throughout
    effects.append(Stars(screen, 300))
    
    screen.play([Scene(effects, 48)], repeat=False, stop_on_resize=True)


if __name__ == "__main__":
    main()
