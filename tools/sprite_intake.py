"""Intake for generated battlefield art: sprite sheets and region tilesets.

The prompt pack (``tools/art_prompts.py``) asks an image model for one PNG per
animation clip (rows = facings, columns = frames) and one PNG per region
tileset (one row of tiles). This tool turns those deliveries into what the
frontend actually loads:

* ``frontend/public/assets/sprites/<slug>/<clip>.png`` -- a strip of
  ``FRAME_SIZE`` squares, rows south/west/north, columns = frames
* ``frontend/public/assets/terrain/<region>/<variant>.png`` -- one tile each
* ``frontend/public/assets/sprites/manifest.json`` -- what exists, read by
  ``frontend/src/utils/sprites.js`` at runtime

Every step is tolerant of the usual model failures: the magenta (#FF00FF)
background is keyed to transparency with a tolerance, cells are found by
dividing the image evenly (so a slightly-off grid still slices), and each cell
is resampled with nearest-neighbour so pixels stay crisp.

    python tools/sprite_intake.py sheet   jean__idle.png [more.png ...]
    python tools/sprite_intake.py tileset tileset__verdette_caverns.png
    python tools/sprite_intake.py placeholders [--only jean slime]
    python tools/sprite_intake.py validate
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable, Optional, Sequence, Tuple

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.art_prompts import (  # noqa: E402
    CLIPS,
    FACINGS,
    FRAME_SIZE,
    REGIONS,
    ROSTER,
    TILE_SIZE,
)

ASSETS = ROOT / "frontend" / "public" / "assets"
SPRITES_DIR = ASSETS / "sprites"
TERRAIN_DIR = ASSETS / "terrain"
MANIFEST = SPRITES_DIR / "manifest.json"

CHROMA = (255, 0, 255)
CHROMA_TOLERANCE = 48


# ---------------------------------------------------------------------------
# Image helpers
# ---------------------------------------------------------------------------


def key_out_background(
    image: Image.Image, tolerance: int = CHROMA_TOLERANCE
) -> Image.Image:
    """Return an RGBA copy with every near-magenta pixel made transparent."""
    rgba = image.convert("RGBA")
    pixels = rgba.load()
    width, height = rgba.size
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            if (
                abs(r - CHROMA[0]) <= tolerance
                and abs(g - CHROMA[1]) <= tolerance
                and abs(b - CHROMA[2]) <= tolerance
            ):
                pixels[x, y] = (0, 0, 0, 0)
    return rgba


def split_grid(image: Image.Image, rows: int, cols: int) -> list[list[Image.Image]]:
    """Divide ``image`` evenly into ``rows`` x ``cols`` cells."""
    width, height = image.size
    cells = []
    for r in range(rows):
        row = []
        for c in range(cols):
            box = (
                round(c * width / cols),
                round(r * height / rows),
                round((c + 1) * width / cols),
                round((r + 1) * height / rows),
            )
            row.append(image.crop(box))
        cells.append(row)
    return cells


def trim_to_content(cell: Image.Image) -> Image.Image:
    """Crop transparent margins so the sprite fills its frame consistently;
    a fully transparent cell is returned unchanged."""
    bbox = cell.getbbox()
    return cell.crop(bbox) if bbox else cell


def fit_square(cell: Image.Image, size: int) -> Image.Image:
    """Scale ``cell`` to fit in a ``size`` square (nearest-neighbour) and
    centre it, feet on the bottom edge."""
    trimmed = trim_to_content(cell)
    w, h = trimmed.size
    scale = min(size / w, size / h) if w and h else 1.0
    new_w, new_h = max(1, round(w * scale)), max(1, round(h * scale))
    resized = trimmed.resize((new_w, new_h), Image.NEAREST)
    frame = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    frame.paste(resized, ((size - new_w) // 2, size - new_h))
    return frame


def assemble_strip(cells: Sequence[Sequence[Image.Image]], size: int) -> Image.Image:
    rows, cols = len(cells), len(cells[0])
    strip = Image.new("RGBA", (cols * size, rows * size), (0, 0, 0, 0))
    for r, row in enumerate(cells):
        for c, cell in enumerate(row):
            strip.paste(fit_square(cell, size), (c * size, r * size))
    return strip


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------


def load_manifest(path: Path = MANIFEST) -> dict:
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data.setdefault("sprites", {})
                data.setdefault("terrain", {})
                return data
        except json.JSONDecodeError:
            pass
    return {
        "frame_size": FRAME_SIZE,
        "tile_size": TILE_SIZE,
        "facings": list(FACINGS),
        "clips": dict(CLIPS),
        "sprites": {},
        "terrain": {},
    }


def save_manifest(manifest: dict, path: Path = MANIFEST) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest["frame_size"] = FRAME_SIZE
    manifest["tile_size"] = TILE_SIZE
    manifest["facings"] = list(FACINGS)
    manifest["clips"] = dict(CLIPS)
    manifest["sprites"] = dict(sorted(manifest.get("sprites", {}).items()))
    manifest["terrain"] = dict(sorted(manifest.get("terrain", {}).items()))
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Intake
# ---------------------------------------------------------------------------


def parse_sheet_name(path: Path) -> Tuple[str, str]:
    """``jean__idle.png`` -> ``("jean", "idle")``."""
    stem = path.stem
    if "__" not in stem:
        raise ValueError(f"{path.name}: expected '<slug>__<clip>.png'")
    slug, clip = stem.split("__", 1)
    if clip not in CLIPS:
        raise ValueError(f"{path.name}: unknown clip {clip!r}; known: {sorted(CLIPS)}")
    return slug, clip


def intake_sheet(
    path: Path,
    rows: Optional[int] = None,
    cols: Optional[int] = None,
    sprites_dir: Path = SPRITES_DIR,
    manifest_path: Path = MANIFEST,
    slug: Optional[str] = None,
    clip: Optional[str] = None,
) -> Path:
    """Slice one delivered clip sheet into a normalised strip and register it."""
    if slug is None or clip is None:
        slug, clip = parse_sheet_name(path)
    rows = rows or len(FACINGS)
    cols = cols or CLIPS[clip]
    image = key_out_background(Image.open(path))
    cells = split_grid(image, rows, cols)
    strip = assemble_strip(cells, FRAME_SIZE)
    out = sprites_dir / slug / f"{clip}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    strip.save(out)

    manifest = load_manifest(manifest_path)
    entry = manifest["sprites"].setdefault(slug, {"clips": {}})
    entry["clips"][clip] = {
        "file": f"sprites/{slug}/{clip}.png",
        "frames": cols,
        "rows": rows,
    }
    save_manifest(manifest, manifest_path)
    return out


def parse_tileset_name(path: Path) -> str:
    stem = path.stem
    if not stem.startswith("tileset__"):
        raise ValueError(f"{path.name}: expected 'tileset__<region>.png'")
    region = stem.removeprefix("tileset__")
    if region not in REGIONS:
        raise ValueError(
            f"{path.name}: unknown region {region!r}; known: {sorted(REGIONS)}"
        )
    return region


def intake_tileset(
    path: Path,
    terrain_dir: Path = TERRAIN_DIR,
    manifest_path: Path = MANIFEST,
    region: Optional[str] = None,
) -> list[Path]:
    """Slice one delivered tileset row into per-variant tiles and register them."""
    region = region or parse_tileset_name(path)
    variants = list(REGIONS[region]["variants"].keys())
    image = key_out_background(Image.open(path))
    cells = split_grid(image, 1, len(variants))[0]
    out_dir = terrain_dir / region
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    manifest = load_manifest(manifest_path)
    tiles = manifest["terrain"].setdefault(region, {"tiles": {}})["tiles"]
    for variant, cell in zip(variants, cells):
        tile = cell.resize((TILE_SIZE, TILE_SIZE), Image.NEAREST)
        out = out_dir / f"{variant}.png"
        tile.save(out)
        tiles[variant] = f"terrain/{region}/{variant}.png"
        written.append(out)
    save_manifest(manifest, manifest_path)
    return written


# ---------------------------------------------------------------------------
# Placeholders: procedural stand-ins so the sprite path runs before art lands
# ---------------------------------------------------------------------------

_SIDE_COLOURS = {
    "hero": (0, 255, 136),
    "ally": (0, 204, 255),
    "enemy": (255, 68, 68),
}


def _placeholder_cell(
    initial: str, colour, facing: str, clip: str, frame: int, frames: int, size: int
) -> Image.Image:
    """A silhouette token that visibly changes per facing, clip and frame."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    t = frame / max(1, frames - 1)
    bob = int(2 * (1 - abs(2 * t - 1))) if clip in ("idle", "walk") else 0
    lean = {
        "attack": int(6 * (t if t < 0.5 else 1 - t)),
        "cast": 0,
        "defend": -3,
        "hurt": -int(5 * (1 - t)),
        "death": 0,
    }.get(clip, 0)
    height = size - 10
    if clip == "death":
        height = max(8, int((size - 10) * (1 - t)))
    r, g, b = colour
    body = [8 + lean, size - height + bob, size - 8 + lean, size - 2 + bob]
    draw.rounded_rectangle(
        body, radius=10, fill=(r, g, b, 220), outline=(255, 255, 255, 200), width=2
    )
    # Facing marker: a notch on the side the sprite faces.
    marker = {
        "south": [size // 2 - 4, size - 8, size // 2 + 4, size - 4],
        "north": [
            size // 2 - 4,
            size - height + bob + 2,
            size // 2 + 4,
            size - height + bob + 6,
        ],
        "west": [10 + lean, size // 2, 14 + lean, size // 2 + 8],
    }[facing]
    draw.rectangle(marker, fill=(255, 255, 255, 255))
    if clip == "cast":
        ring = 6 + int(10 * t)
        draw.ellipse(
            [
                size // 2 - ring,
                size // 2 - ring - 8,
                size // 2 + ring,
                size // 2 + ring - 8,
            ],
            outline=(255, 238, 170, 200),
            width=2,
        )
    if clip != "death" or t < 0.8:
        draw.text(
            (size // 2 - 4 + lean, size // 2 - 6 + bob), initial, fill=(0, 0, 0, 255)
        )
    return img


def write_placeholders(
    only: Optional[Iterable[str]] = None,
    sprites_dir: Path = SPRITES_DIR,
    manifest_path: Path = MANIFEST,
) -> list[Path]:
    wanted = set(only) if only else None
    written = []
    manifest = load_manifest(manifest_path)
    for entry in ROSTER:
        slug = entry["slug"]
        if wanted is not None and slug not in wanted:
            continue
        colour = _SIDE_COLOURS[entry["side"]]
        for clip, frames in CLIPS.items():
            cells = [
                [
                    _placeholder_cell(
                        entry["name"][0], colour, facing, clip, f, frames, FRAME_SIZE
                    )
                    for f in range(frames)
                ]
                for facing in FACINGS
            ]
            strip = Image.new(
                "RGBA", (frames * FRAME_SIZE, len(FACINGS) * FRAME_SIZE), (0, 0, 0, 0)
            )
            for r, row in enumerate(cells):
                for c, cell in enumerate(row):
                    strip.paste(cell, (c * FRAME_SIZE, r * FRAME_SIZE))
            out = sprites_dir / slug / f"{clip}.png"
            out.parent.mkdir(parents=True, exist_ok=True)
            strip.save(out)
            written.append(out)
            manifest["sprites"].setdefault(slug, {"clips": {}})["clips"][clip] = {
                "file": f"sprites/{slug}/{clip}.png",
                "frames": frames,
                "rows": len(FACINGS),
                "placeholder": True,
            }
    save_manifest(manifest, manifest_path)
    return written


# ---------------------------------------------------------------------------
# Validate
# ---------------------------------------------------------------------------


def validate(manifest_path: Path = MANIFEST, assets_dir: Path = ASSETS) -> dict:
    """Report what the manifest has, what is still a placeholder, what is
    missing, and any manifest entry whose file is gone."""
    manifest = load_manifest(manifest_path)
    report = {
        "complete": [],
        "placeholder": [],
        "missing": [],
        "broken": [],
        "tilesets_missing": [],
    }
    for entry in ROSTER:
        slug = entry["slug"]
        clips = manifest["sprites"].get(slug, {}).get("clips", {})
        if not clips:
            report["missing"].append(slug)
            continue
        have = set(clips)
        if have < set(CLIPS):
            report["missing"].append(f"{slug} ({', '.join(sorted(set(CLIPS) - have))})")
        for clip, info in clips.items():
            if not (assets_dir / info["file"]).exists():
                report["broken"].append(f"{slug}/{clip}")
        if any(info.get("placeholder") for info in clips.values()):
            report["placeholder"].append(slug)
        elif have >= set(CLIPS):
            report["complete"].append(slug)
    for region in REGIONS:
        if region not in manifest["terrain"]:
            report["tilesets_missing"].append(region)
    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sheet = sub.add_parser(
        "sheet", help="intake one or more '<slug>__<clip>.png' sprite sheets"
    )
    sheet.add_argument("paths", nargs="+", type=Path)
    sheet.add_argument("--rows", type=int, help="override facing row count")
    sheet.add_argument("--cols", type=int, help="override frame column count")

    tileset = sub.add_parser(
        "tileset", help="intake one or more 'tileset__<region>.png' rows"
    )
    tileset.add_argument("paths", nargs="+", type=Path)

    ph = sub.add_parser("placeholders", help="write procedural placeholder strips")
    ph.add_argument("--only", nargs="*", help="slugs to write (default: whole roster)")

    sub.add_parser("validate", help="report manifest completeness")

    args = parser.parse_args(argv)
    if args.command == "sheet":
        for path in args.paths:
            out = intake_sheet(path, rows=args.rows, cols=args.cols)
            print(f"wrote {out.relative_to(ROOT)}")
    elif args.command == "tileset":
        for path in args.paths:
            for out in intake_tileset(path):
                print(f"wrote {out.relative_to(ROOT)}")
    elif args.command == "placeholders":
        for out in write_placeholders(args.only):
            print(f"wrote {out.relative_to(ROOT)}")
    elif args.command == "validate":
        report = validate()
        for key, items in report.items():
            print(f"{key}: {', '.join(items) if items else '-'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
