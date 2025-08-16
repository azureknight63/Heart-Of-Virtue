import subprocess
# import threading
import os


def open_window(animation):
    """
    Opens a separate terminal window to display the animation.
    :param animation: Name of one of the animation functions defined in the animations.py module OR the
    filename of a gif in resources/animations, as a string
    """
    if os.name == 'nt':  # for Windows
        subprocess.call(f"start /wait python animations.py {animation}", shell=True)

    else:
        print("### Non-windows environments not yet supported for animations! ###")
