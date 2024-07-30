from random import randint
import sys
import time
from pathlib import Path

from asciimatics.effects import Cycle, Stars, BannerText, Print, Scroll
from asciimatics.renderers import FigletText, ColourImageFile, ImageFile
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


def play_gif(screen, file):
    """
    Plays the selected gif file.
    :param screen: the Screen object; handled by the Screen.wrapper function
    :param file: the name of the file without any path or extension
    """
    filepath = f"./resources/animations/{file}.gif"
    if Path(filepath).exists():
        scenes = []
        effects = [
            Print(screen,
                  ColourImageFile(screen, filepath, screen.height - 2,
                                  uni=screen.unicode_aware, dither=screen.unicode_aware),
                  0, 0, speed=1, stop_frame=count_gif_frames(filepath), transparent=False),
        ]
        scenes.append(Scene(effects))
        screen.play(scenes, repeat=False, stop_on_resize=True)
    else:
        print("### Animation not found!")


def animate_to_main_screen(animation):
    """
    Plays the selected animation on the primary screen
    :param screen: The screen object
    :param animation: Name of one of the animation functions defined in the animations.py module OR the
    filename of a gif in resources/animations, as a string
    """
    if ".gif" in animation:
        file_to_play = animation.replace(".gif", "")
        Screen.wrapper(func=play_gif, arguments=[file_to_play])
    else:
        if function_exists('animations.py', animation):
            Screen.wrapper(getattr('animations.py', animation))  # execute the animation
        else:
            print("### Animation not found!")


if __name__ == "__main__":
    main()
