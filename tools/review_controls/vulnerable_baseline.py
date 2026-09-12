"""Deliberately vulnerable fixture — NOT production code. See README.md.

A save-file reader with a path traversal in `read_save_blob`, reachable from two
request handlers. The two patches in this directory fix it differently; the point
of the fixture is that one of them only looks like a fix.
"""

import os

SAVE_DIR = "/var/hov/saves"


def read_save_blob(save_name):
    """Return the raw bytes of a save file by name."""
    path = os.path.join(SAVE_DIR, save_name)
    with open(path, "rb") as handle:
        return handle.read()


def handle_load_request(request):
    """GET /api/saves/load?name=... — load a save for the current player."""
    return read_save_blob(request.args["name"])


def handle_import_request(request):
    """POST /api/saves/import — read a save the player is re-importing."""
    return read_save_blob(request.form["name"])
