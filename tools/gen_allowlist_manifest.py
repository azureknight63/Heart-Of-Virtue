#!/usr/bin/env python3
"""Regenerate the save-deserialization allow-list manifest (issue #13, Phase 4).

The strict-mode allow-list in ``src.secure_pickle`` is derived automatically by
introspecting the engine modules, so it never drifts behind the code at runtime.
This script materializes that live allow-list to a sorted, human-diffable
manifest file so drift is also visible in review, and so ``test_secure_pickle``
can assert the checked-in manifest still matches the code.

Usage:
    python tools/gen_allowlist_manifest.py            # write the manifest
    python tools/gen_allowlist_manifest.py --check    # exit 1 if out of date
"""

import os
import sys
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src import secure_pickle  # noqa: E402

MANIFEST_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "docs", "development", "save-allowlist-manifest.json",
)


def build_manifest():
    """Return the current allow-list as a sorted, JSON-serializable manifest."""
    entries = [
        {"module": module, "name": name}
        for module, name in sorted(secure_pickle.get_allowlist())
    ]
    return {
        "header_version": secure_pickle.HEADER_VERSION,
        "count": len(entries),
        "classes": entries,
    }


def _serialize(manifest):
    return json.dumps(manifest, indent=2, sort_keys=True) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true",
        help="Exit non-zero if the manifest on disk is out of date.",
    )
    args = parser.parse_args(argv)

    manifest_text = _serialize(build_manifest())

    if args.check:
        if not os.path.exists(MANIFEST_PATH):
            print(f"Manifest missing: {MANIFEST_PATH}", file=sys.stderr)
            return 1
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            current = f.read()
        if current != manifest_text:
            print(
                "Allow-list manifest is out of date. Run "
                "`python tools/gen_allowlist_manifest.py` to regenerate.",
                file=sys.stderr,
            )
            return 1
        print("Allow-list manifest is up to date.")
        return 0

    os.makedirs(os.path.dirname(MANIFEST_PATH), exist_ok=True)
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        f.write(manifest_text)
    print(f"Wrote {MANIFEST_PATH} ({build_manifest()['count']} classes).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
