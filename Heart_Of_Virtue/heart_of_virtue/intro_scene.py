import time
import functions
from termcolor import colored, cprint

def intro():
    cprint(r"""
                _
               (_)
               |=|              __  __
               |=|              ||  ||  ____  ___     ____    __||__
           /|__|_|__|\          ||__||  ||    ||\\    || ))   --||--
          (    ( )    )         ||__||  ||-   ||_\\   || \\     ||
           \|\/\"/\/|/          ||  ||  ||__  ||  \\  ||  \\    ||
             |  Y  |            ||  ||
             |  |  |           '--''--'              OF
             |  |  |
            _|  |  |                     __           __
         __/ |  |  |\                    \ \         / /
        /  \ |  |  |  \                   \ \       / / ___     __       ____   ____
           __|  |  |   |                   \ \     / /  ||\\    ||      //  \\  || ))
        /\/  |  |  |   |\                   \ \   / /   ||_\\   ||____  ||  ||  || \\
         <   +\ |  |\ />  \                  \ \_/ /    ||  \\  \|----  \\__//  ||  \\
          >   + \  | LJ    |                  \___/
                + \|+  \  < \
          (O)      +    |    )                        By Alexander Egbert
           |             \  /\
         ( | )   (o)      \/  )
        _\\|//__( | )______)_/
                \\|//
    """, "cyan")
    functions.print_slow("Darkness. Silence. Jean is surrounded by these. They seem to hang around him like a thick "
            "fog, suffocating his senses, his consciousness. He tries to cry out into the void, but he can't feel"
            " his mouth moving. He can't feel anything. He'd panic but that all seems so pointless now, here"
            " in this thick soup of nullity. Not even the sound of his own heart beating or his breath"
            " escaping his lungs seems to penetrate the blackness and the quiet.")
    print("\n" * 2)
    time.sleep(10)
    functions.print_slow("Gradually, a noise begins to rise out of the void. Indistinct and quiet at first, "
                         "like a whisper, but slowly coming into focus.")
    print("\n" * 3)
    time.sleep(5)
    functions.print_slow("'The body of Christ...'")
    print("\n" * 2)
    time.sleep(5)
    functions.print_slow("'The body of Christ...'")
    time.sleep(5)
    functions.print_slow("Slowly, light and sound begin to pour back into Jean's awareness. After what seems like an "
               "eternity, he opens his eyes...")
    print("\n" * 4)
    time.sleep(10)