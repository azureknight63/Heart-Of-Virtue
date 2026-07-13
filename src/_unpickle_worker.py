"""Subprocess worker for sandboxed legacy unpickling (issue #13, Phase 4).

Run as ``python -m src._unpickle_worker`` with the raw save bytes on stdin. The
worker unpickles the save *in this isolated child process* (so any code the
pickle executes cannot touch the parent's memory), converts the result to the
data-only v2 schema, and writes that JSON to stdout. The parent therefore never
unpickles untrusted bytes itself -- it only parses primitive JSON.

Combined with a wall-clock timeout enforced by the parent, this bounds both the
blast radius (isolation) and the resource cost (CPU/time) of loading a save of
uncertain provenance.
"""

import io
import sys
import json


def main():
    raw = sys.stdin.buffer.read()
    # Imported here (not at module top) so import failures surface as a clean
    # non-zero exit with a message on stderr rather than an import-time crash.
    from src.secure_pickle import safe_pickle_load
    from src.save_format import player_to_data

    # Strict mode is the right default for untrusted input; the parent sets the
    # env var when it wants it. safe_pickle_load handles header + size cap.
    obj = safe_pickle_load(io.BytesIO(raw))
    if obj is None:
        sys.stderr.write("worker: failed to deserialize save\n")
        return 2
    sys.stdout.write(json.dumps(player_to_data(obj)))
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised via subprocess
    sys.exit(main())
