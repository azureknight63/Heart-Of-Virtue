from random import randint
import sys
from pathlib import Path

import functions

# Optional dependencies: asciimatics & Pillow
try:
    from asciimatics.effects import Cycle, Stars, Print
    from asciimatics.renderers import FigletText, ColourImageFile, ImageFile, SpeechBubble
    from asciimatics.scene import Scene
    from asciimatics.screen import Screen
    from asciimatics.exceptions import ResizeScreenError
    ASCIIMATICS_AVAILABLE = True
except ImportError:  # provide light stubs so core game/tests don't crash
    ASCIIMATICS_AVAILABLE = False
    class Screen:  # minimal stub
        @staticmethod
        def wrapper(func, arguments=None):
            # call target func with None screen; swallow failures
            try:
                if arguments:
                    func(None, *arguments)
                else:
                    func(None)
            except Exception:
                print("[animation skipped]")
    class Scene:  # placeholder
        def __init__(self, *_, **__):
            pass
    class Cycle:  # placeholders for effects
        def __init__(self, *_, **__):
            pass
    class Stars:
        def __init__(self, *_, **__):
            pass
    class Print:
        def __init__(self, *_, **__):
            pass
    class FigletText:
        def __init__(self, *_, **__):
            pass
    class ColourImageFile:
        def __init__(self, *_, **__):
            pass
    class ImageFile:
        def __init__(self, *_, **__):
            pass
    class SpeechBubble:
        def __init__(self, *_, **__):
            pass
    class ResizeScreenError(Exception):
        pass

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


def count_gif_frames(gif_path):
    if not PIL_AVAILABLE:
        return 0
    with Image.open(gif_path) as img:
        frame_count = 0
        try:
            while True:
                img.seek(frame_count)
                frame_count += 1
        except EOFError:
            pass
    return frame_count


def function_exists(module, function_name):
    return hasattr(module, function_name) and callable(getattr(module, function_name))


def main():
    if len(sys.argv) < 3:
        animation = sys.argv[1]
        if ".gif" in animation:
            file_to_play = animation.replace(".gif", "")
            if ASCIIMATICS_AVAILABLE and PIL_AVAILABLE:
                Screen.wrapper(func=play_gif, arguments=[file_to_play])
            else:
                print(f"[animation skipped: {file_to_play}.gif]")
        else:
            if function_exists('animations.py', animation) and ASCIIMATICS_AVAILABLE:
                Screen.wrapper(getattr('animations.py', animation))
            else:
                print("### Animation not found or asciimatics not available!")
    else:
        try:
            if ASCIIMATICS_AVAILABLE:
                Screen.wrapper(demo)
        except ResizeScreenError:
            pass


def demo(screen):
    if not ASCIIMATICS_AVAILABLE:
        print("[demo animation skipped]")
        return
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
    if not ASCIIMATICS_AVAILABLE:
        print("[demo2 animation skipped]")
        return
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
    if not (ASCIIMATICS_AVAILABLE and PIL_AVAILABLE):
        print(f"[gif animation skipped: {file}.gif]")
        return
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
    if not ASCIIMATICS_AVAILABLE:
        print(f"[static image skipped: {file}]")
        return
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


def title_scene(screen):
    if not ASCIIMATICS_AVAILABLE:
        print("[title scene skipped]")
        return
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
              0,
              speed=1, transparent=False,
              stop_frame=100)
    ]
    screen.play([Scene(effects, 0)], repeat=False)


def animate_to_main_screen(animation, rawtext=""):
    text = functions.clean_string(rawtext)
    if not ASCIIMATICS_AVAILABLE:
        print(f"[animation skipped: {animation}] {text}")
        return
    if ".gif" in animation:
        file_to_play = animation.replace(".gif", "")
        Screen.wrapper(func=play_gif, arguments=[file_to_play, text])
    else:
        if function_exists('animations.py', animation):
            if text:
                Screen.wrapper(func=getattr('animations.py', animation), arguments=[text])
            else:
                Screen.wrapper(getattr('animations.py', animation))
        else:
            print("### Animation not found!")


def image_to_main_screen(image):
    if not ASCIIMATICS_AVAILABLE:
        print(f"[image display skipped: {image}]")
        return
    Screen.wrapper(func=display_static_image, arguments=[image])


if __name__ == "__main__":
    main()
