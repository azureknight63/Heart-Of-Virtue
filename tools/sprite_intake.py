"""Intake for generated battlefield art: sprite sheets and region tilesets.

The prompt pack (``tools/art_prompts.py``) asks an image model for one PNG per
animation clip (rows = facings, columns = frames) and one PNG per region
tileset (one row of tiles). This tool turns those deliveries into what the
frontend actually loads:

* ``frontend/public/assets/sprites/<slug>/<clip>.png`` -- a strip of
  ``FRAME_SIZE`` squares, rows south/west/north, columns = frames
* ``frontend/public/assets/terrain/<region>/<variant>.png`` -- one tile each
* ``frontend/public/assets/sprites/manifest.json`` -- what exists, fetched by
  ``frontend/src/hooks/useSpriteManifest.js`` and read through
  ``frontend/src/utils/sprites.js``

Every step is tolerant of the usual model failures: the magenta background is
keyed by *hue* (JPEG exports and "creative" magentas drift far from #FF00FF,
and models draw dark magenta gridlines the prompt never asked for), cells are
found from the content itself (``find_cells``: runs of non-empty rows and
columns, so margins, gridlines and a slightly-off grid all slice cleanly; an
even split remains available as ``grid="even"``), a wrong frame count is
resampled to the spec's so the manifest never drifts from it, and each cell
is resampled with nearest-neighbour so pixels stay crisp. A sheet is normalised as one unit --
one crop box and one scale for every cell -- so the model's "identical scale,
feet on the same baseline" survives intake and frames do not pulse.

Deliveries are untrusted input: file names are validated against the roster
before they become paths, output paths are containment-checked, and decoded
images are size-capped.

    python tools/sprite_intake.py sheet   jean__idle.png [more.png ...] [--grid even]
    python tools/sprite_intake.py tileset tileset__verdette_caverns.png
    python tools/sprite_intake.py placeholders [--only jean slime] [--force]
    python tools/sprite_intake.py validate
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.art_prompts import (  # noqa: E402
    CHROMA_RGB,
    CLIPS,
    FACINGS,
    FRAME_SIZE,
    REGIONS,
    ROSTER,
    TILE_SIZE,
    parse_sheet_filename,
    parse_tileset_filename,
    spec_header,
)

ASSETS = ROOT / "frontend" / "public" / "assets"
SPRITES_DIR = ASSETS / "sprites"
TERRAIN_DIR = ASSETS / "terrain"
MANIFEST = SPRITES_DIR / "manifest.json"

CHROMA_TOLERANCE = 48

#: Hue key. Pillow's HSV hue runs 0-255, so magenta (300 degrees) is 213;
#: anything within ``CHROMA_HUE_TOLERANCE`` of it that is saturated and not
#: near-black is background. The saturation floor keeps dusky purples and
#: greys in a sprite; the value floor keeps true black outlines.
CHROMA_HUE = round(300 / 360 * 255)
CHROMA_HUE_TOLERANCE = 10
CHROMA_MIN_SATURATION = 140
CHROMA_MIN_VALUE = 40

#: Despill: JPEG blends the background into the sprite's outline, leaving a
#: halo of dull magenta. Pixels within ``DESPILL_REACH`` px of the keyed
#: background are keyed under this looser hue/saturation window too.
DESPILL_REACH = 2
DESPILL_HUE_TOLERANCE = 14
DESPILL_MIN_SATURATION = 70

#: ``find_cells``: a row/column of the keyed sheet counts as empty when its
#: mean alpha is below this (JPEG noise on the magenta and ringing along a
#: keyed gridline leave a few stray pixels); content runs closer together
#: than this fraction of the widest run are one cell (a detached spark, a
#: gap between legs; a keyed gridline with wings touching it on both sides
#: is wider than that); runs narrower than this fraction of it are specks.
GRID_EMPTY_ALPHA = 10
GRID_MERGE_GAP = 0.06
GRID_SPECK = 0.1

#: Largest delivery accepted, in pixels per side and in total. A 4096-square
#: sheet is already far more than any 3 x 6 grid needs.
MAX_IMAGE_SIDE = 4096
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_SIDE * MAX_IMAGE_SIDE

#: Manifest file paths the frontend will accept (mirrors sprites.js).
SAFE_FILE = re.compile(r"^(?:sprites|terrain)/[A-Za-z0-9_-]+/[A-Za-z0-9_-]+\.png$")
MAX_FRAMES = 64
GRID_MODES = ("auto", "even")


# ---------------------------------------------------------------------------
# Image helpers
# ---------------------------------------------------------------------------


def open_delivery(path: Path) -> Image.Image:
    """Decode a delivered image, refusing anything past ``MAX_IMAGE_SIDE``."""
    with Image.open(path) as image:
        width, height = image.size
        if width > MAX_IMAGE_SIDE or height > MAX_IMAGE_SIDE:
            raise ValueError(
                f"{path.name}: {width}x{height} exceeds {MAX_IMAGE_SIDE}px per side"
            )
        return image.convert("RGBA")


def _hsv_mask(hsv_bands, hue_tolerance: int, min_saturation: int) -> Image.Image:
    """255 where the pixel is magenta-hued, at least ``min_saturation``
    saturated and not near-black."""
    h, sat, val = hsv_bands
    lo, hi = CHROMA_HUE - hue_tolerance, CHROMA_HUE + hue_tolerance
    hue_ok = h.point(lambda v: 255 if lo <= v <= hi else 0)
    sat_ok = sat.point(lambda v: 255 if v >= min_saturation else 0)
    val_ok = val.point(lambda v: 255 if v >= CHROMA_MIN_VALUE else 0)
    return ImageChops.multiply(ImageChops.multiply(hue_ok, sat_ok), val_ok)


def key_out_background(
    image: Image.Image, tolerance: int = CHROMA_TOLERANCE
) -> Image.Image:
    """Return an RGBA copy with every magenta-ish pixel made transparent.

    A pixel is keyed when it is within ``tolerance`` of ``CHROMA_RGB`` on
    every channel *or* when its hue is magenta and it is saturated and not
    near-black (see ``CHROMA_HUE``): deliveries arrive as JPEG with the
    background drifted to (229, 64, 244), and models draw dark-magenta
    gridlines between cells. A second, looser pass (``DESPILL_*``) then
    keys the dull-magenta halo JPEG leaves along the outline, but only
    within ``DESPILL_REACH`` px of already-keyed background so a genuinely
    purple sprite keeps its interior. Done with Pillow channel ops rather
    than a Python pixel loop: a 1024-square delivery is a million pixels.
    """
    rgba = image.convert("RGBA")
    rgb = rgba.convert("RGB")
    chroma = Image.new("RGB", rgba.size, CHROMA_RGB)
    r, g, b = ImageChops.difference(rgb, chroma).split()
    farthest = ImageChops.lighter(ImageChops.lighter(r, g), b)
    near_box = farthest.point(lambda v: 255 if v <= tolerance else 0)

    hsv = rgb.convert("HSV").split()
    background = ImageChops.lighter(
        near_box, _hsv_mask(hsv, CHROMA_HUE_TOLERANCE, CHROMA_MIN_SATURATION)
    )
    spill = _hsv_mask(hsv, DESPILL_HUE_TOLERANCE, DESPILL_MIN_SATURATION)
    for _ in range(DESPILL_REACH):
        halo = background.filter(ImageFilter.MaxFilter(3))
        background = ImageChops.lighter(background, ImageChops.multiply(halo, spill))

    transparent = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    return Image.composite(transparent, rgba, background)


def _content_runs(profile: Sequence[int]) -> list[tuple[int, int]]:
    """Inclusive ``(start, end)`` runs of non-empty entries in a mean-alpha
    profile. Runs closer together than ``GRID_MERGE_GAP`` of the widest run
    are joined (a spark beside a hand, the gap between two legs) and runs
    narrower than ``GRID_SPECK`` of it are dropped (JPEG ringing along a
    keyed gridline, a stray pixel)."""
    runs: list[list[int]] = []
    for i, value in enumerate(profile):
        if value < GRID_EMPTY_ALPHA:
            continue
        if runs and i == runs[-1][1] + 1:
            runs[-1][1] = i
        else:
            runs.append([i, i])
    if not runs:
        return []
    widest = max(end - start + 1 for start, end in runs)
    speck = max(1, widest * GRID_SPECK)
    solid = [run for run in runs if run[1] - run[0] + 1 >= speck]
    merged: list[list[int]] = [solid[0]]
    for start, end in solid[1:]:
        if start - merged[-1][1] - 1 < widest * GRID_MERGE_GAP:
            merged[-1][1] = end
        else:
            merged.append([start, end])
    return [(start, end) for start, end in merged]


def _profile(alpha: Image.Image, axis: int) -> list[int]:
    """Mean alpha per column (``axis`` 0) or row (``axis`` 1), via a box
    resize so the whole image is reduced in C."""
    width, height = alpha.size
    size = (width, 1) if axis == 0 else (1, height)
    return list(alpha.resize(size, Image.BOX).tobytes())


def find_cells(image: Image.Image) -> list[list[Image.Image]]:
    """Locate the sheet's cells from its content instead of trusting the grid.

    ``image`` is a keyed sheet. Columns are runs of non-empty image columns,
    rows are runs of non-empty image rows; every cell is cut to the same
    width (centred on its column) and the same height (bottom-aligned on its
    row, so the feet baseline is kept), which is what ``normalise_sheet``
    expects. Returns ``[]`` for an empty sheet.
    """
    alpha = image.convert("RGBA").getchannel("A")
    col_runs = _content_runs(_profile(alpha, 0))
    row_runs = _content_runs(_profile(alpha, 1))
    if not col_runs or not row_runs:
        return []
    width, height = image.size
    cell_w = max(end - start + 1 for start, end in col_runs)
    cell_h = max(end - start + 1 for start, end in row_runs)
    cells = []
    for top, bottom in row_runs:
        y1 = min(height, bottom + 1)
        y0 = max(0, y1 - cell_h)
        row = []
        for left, right in col_runs:
            centre = (left + right + 1) // 2
            x0 = max(0, min(width - cell_w, centre - cell_w // 2))
            row.append(image.crop((x0, y0, x0 + cell_w, y0 + cell_h)))
        cells.append(row)
    return cells


def resample_columns(cells: Sequence[Sequence[Image.Image]], count: int):
    """Stretch or squeeze a sheet to ``count`` frames per row by repeating or
    dropping evenly spaced columns, so a delivery with the wrong frame count
    still registers as the spec's clip length."""
    found = len(cells[0])
    if found == count:
        return [list(row) for row in cells]
    picks = [
        round(i * (found - 1) / (count - 1)) if count > 1 else 0 for i in range(count)
    ]
    return [[row[i] for i in picks] for row in cells]


def split_grid(image: Image.Image, rows: int, cols: int) -> list[list[Image.Image]]:
    """Divide ``image`` evenly into ``rows`` x ``cols`` cells."""
    if rows < 1 or cols < 1:
        raise ValueError("a sheet needs at least one row and one column")
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


def union_bbox(
    cells: Sequence[Sequence[Image.Image]],
) -> tuple[int, int, int, int] | None:
    """The smallest cell-local box containing every cell's content, so one
    crop applies to all of them; None when every cell is empty."""
    left = top = None
    right = bottom = None
    for row in cells:
        for cell in row:
            bbox = cell.getbbox()
            if bbox is None:
                continue
            left = bbox[0] if left is None else min(left, bbox[0])
            top = bbox[1] if top is None else min(top, bbox[1])
            right = bbox[2] if right is None else max(right, bbox[2])
            bottom = bbox[3] if bottom is None else max(bottom, bbox[3])
    if left is None:
        return None
    return left, top, right, bottom


def trim_to_content(cell: Image.Image) -> Image.Image:
    """Crop one cell's transparent margins (a fully transparent cell is
    returned unchanged). Used for tiles; sprite cells share a sheet-wide crop
    via ``normalise_sheet`` so their relative scale is preserved."""
    bbox = cell.getbbox()
    return cell.crop(bbox) if bbox else cell


def fit_square(cell: Image.Image, size: int, box=None) -> Image.Image:
    """Crop ``cell`` to ``box`` (its own content when None), scale it to fit
    a ``size`` square with nearest-neighbour sampling and centre it, feet on
    the bottom edge."""
    cropped = cell.crop(box) if box else trim_to_content(cell)
    w, h = cropped.size
    scale = min(size / w, size / h) if w and h else 1.0
    new_w, new_h = max(1, round(w * scale)), max(1, round(h * scale))
    resized = cropped.resize((new_w, new_h), Image.NEAREST)
    frame = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    frame.paste(resized, ((size - new_w) // 2, size - new_h))
    return frame


def paste_grid(cells: Sequence[Sequence[Image.Image]], size: int) -> Image.Image:
    """Lay ``size``-square cells out as a strip (rows x cols)."""
    rows, cols = len(cells), len(cells[0])
    strip = Image.new("RGBA", (cols * size, rows * size), (0, 0, 0, 0))
    for r, row in enumerate(cells):
        for c, cell in enumerate(row):
            strip.paste(cell, (c * size, r * size))
    return strip


def normalise_sheet(cells: Sequence[Sequence[Image.Image]], size: int) -> Image.Image:
    """Turn a delivered sheet's cells into a strip of ``size`` squares.

    Every cell is cropped by the *same* box (the union of their content) and
    scaled by the same factor, so a wind-up frame with an outstretched arm
    stays the same size as the idle frame beside it and the feet baseline
    the prompt asked for is kept across frames and facings.
    """
    box = union_bbox(cells)
    return paste_grid(
        [[fit_square(cell, size, box) for cell in row] for row in cells], size
    )


def assemble_strip(cells: Sequence[Sequence[Image.Image]], size: int) -> Image.Image:
    """Alias of ``normalise_sheet`` kept for callers that predate it."""
    return normalise_sheet(cells, size)


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------


def _clean_entry(info) -> dict | None:
    """One manifest clip entry, or None when it is not something the
    frontend would accept (an unsafe path, an absurd frame count)."""
    if not isinstance(info, dict) or not SAFE_FILE.match(str(info.get("file", ""))):
        return None
    try:
        frames = max(1, min(MAX_FRAMES, int(info.get("frames", 1))))
        rows = max(1, min(MAX_FRAMES, int(info.get("rows", len(FACINGS)))))
    except (TypeError, ValueError):
        return None
    entry = {"file": info["file"], "frames": frames, "rows": rows}
    if info.get("placeholder"):
        entry["placeholder"] = True
    return entry


def load_manifest(path: Path = MANIFEST) -> dict:
    """The manifest on disk, or a fresh one.

    Tolerant by design (a corrupt or hand-edited manifest never blocks an
    intake run) but never silent: a file that cannot be parsed is reported on
    stderr before it is replaced, and entries that the frontend would reject
    are dropped with a note.
    """
    manifest = {**spec_header(), "sprites": {}, "terrain": {}}
    if not path.exists():
        return manifest
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print(
            f"warning: {path} is not valid JSON; starting a fresh manifest",
            file=sys.stderr,
        )
        return manifest
    if not isinstance(data, dict):
        print(
            f"warning: {path} is not a JSON object; starting a fresh manifest",
            file=sys.stderr,
        )
        return manifest
    for slug, sprite in (data.get("sprites") or {}).items():
        clips = {}
        for clip, info in (
            sprite.get("clips") if isinstance(sprite, dict) else {}
        ).items():
            entry = _clean_entry(info)
            if entry is None:
                print(
                    f"warning: dropping manifest entry {slug}/{clip}", file=sys.stderr
                )
                continue
            clips[clip] = entry
        if clips:
            manifest["sprites"][slug] = {"clips": clips}
    for region, block in (data.get("terrain") or {}).items():
        tiles = {}
        for variant, file in (
            block.get("tiles") if isinstance(block, dict) else {}
        ).items():
            if SAFE_FILE.match(str(file)):
                tiles[variant] = file
            else:
                print(
                    f"warning: dropping manifest tile {region}/{variant}",
                    file=sys.stderr,
                )
        if tiles:
            manifest["terrain"][region] = {"tiles": tiles}
    return manifest


def save_manifest(manifest: dict, path: Path = MANIFEST) -> None:
    """Write ``manifest`` with the spec header refreshed and entries sorted
    (the caller's dict is left untouched)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    out = {
        **spec_header(),
        "sprites": dict(sorted(manifest.get("sprites", {}).items())),
        "terrain": dict(sorted(manifest.get("terrain", {}).items())),
    }
    path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")


def _clip_paths(sprites_dir: Path, slug: str, clip: str) -> tuple[Path, str]:
    """Where a clip strip lives on disk and how the manifest names it. The
    output is containment-checked against ``sprites_dir``."""
    out = (sprites_dir / slug / f"{clip}.png").resolve()
    out.relative_to(sprites_dir.resolve())  # raises ValueError on escape
    return out, f"sprites/{slug}/{clip}.png"


def _register_clip(
    manifest: dict,
    slug: str,
    clip: str,
    file: str,
    frames: int,
    rows: int,
    placeholder: bool = False,
) -> None:
    entry = {"file": file, "frames": frames, "rows": rows}
    if placeholder:
        entry["placeholder"] = True
    manifest["sprites"].setdefault(slug, {"clips": {}})["clips"][clip] = entry


# Retained names for callers that predate the shared parsers.
def parse_sheet_name(path: Path) -> tuple[str, str]:
    """``jean__idle.png`` -> ``("jean", "idle")`` (see ``parse_sheet_filename``)."""
    return parse_sheet_filename(path.name)


def parse_tileset_name(path: Path) -> str:
    """``tileset__verdette_caverns.png`` -> ``"verdette_caverns"``."""
    return parse_tileset_filename(path.name)


# ---------------------------------------------------------------------------
# Intake
# ---------------------------------------------------------------------------


def intake_sheet(
    path: Path,
    rows: int | None = None,
    cols: int | None = None,
    sprites_dir: Path = SPRITES_DIR,
    manifest_path: Path = MANIFEST,
    slug: str | None = None,
    clip: str | None = None,
    manifest: dict | None = None,
    grid: str = "auto",
) -> Path:
    """Slice one delivered clip sheet into a normalised strip and register it.

    ``slug``/``clip`` default to the file name's; each may be overridden on
    its own. ``rows``/``cols`` default to the spec's grid for the clip. With
    ``grid="auto"`` the cells are located from the content (``find_cells``):
    a wrong number of facing rows is an error, a wrong number of frames is
    resampled to ``cols`` with a warning. ``grid="even"`` divides the image
    by ``rows`` x ``cols`` blindly. Pass ``manifest`` to batch several
    intakes under one load/save.
    """
    parsed_slug, parsed_clip = parse_sheet_filename(path.name)
    slug = slug or parsed_slug
    clip = clip or parsed_clip
    if clip not in CLIPS:
        raise ValueError(f"unknown clip {clip!r}; known: {sorted(CLIPS)}")
    if grid not in GRID_MODES:
        raise ValueError(f"grid must be one of {GRID_MODES}, not {grid!r}")
    rows = rows or len(FACINGS)
    cols = cols or CLIPS[clip]
    if rows < 1 or cols < 1 or rows > MAX_FRAMES or cols > MAX_FRAMES:
        raise ValueError(f"grid {rows}x{cols} is out of range")
    image = key_out_background(open_delivery(path))
    if grid == "auto":
        cells = find_cells(image)
        if not cells:
            raise ValueError(f"{path.name}: no sprite content found after keying")
        if len(cells) != rows:
            raise ValueError(
                f"{path.name}: found {len(cells)} facing rows, expected {rows}; "
                "regenerate the sheet or pass grid='even' (--grid even)"
            )
        if len(cells[0]) != cols:
            print(
                f"warning: {path.name} has {len(cells[0])} frames per row, "
                f"expected {cols}; resampled to {cols}",
                file=sys.stderr,
            )
            cells = resample_columns(cells, cols)
    else:
        cells = split_grid(image, rows, cols)
    strip = normalise_sheet(cells, FRAME_SIZE)
    out, file = _clip_paths(sprites_dir, slug, clip)
    out.parent.mkdir(parents=True, exist_ok=True)
    strip.save(out)

    own = manifest is None
    manifest = load_manifest(manifest_path) if own else manifest
    _register_clip(manifest, slug, clip, file, cols, rows)
    if own:
        save_manifest(manifest, manifest_path)
    return out


def intake_tileset(
    path: Path,
    terrain_dir: Path = TERRAIN_DIR,
    manifest_path: Path = MANIFEST,
    region: str | None = None,
    manifest: dict | None = None,
) -> list[Path]:
    """Slice one delivered tileset row into per-variant tiles and register them.

    Each tile is trimmed to its content before resizing so the keyed-out
    hairline gap never becomes a transparent sliver on a seamless floor.
    """
    region = region or parse_tileset_filename(path.name)
    variants = list(REGIONS[region]["variants"].keys())
    image = key_out_background(open_delivery(path))
    cells = split_grid(image, 1, len(variants))[0]
    out_dir = (terrain_dir / region).resolve()
    out_dir.relative_to(terrain_dir.resolve())
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    own = manifest is None
    manifest = load_manifest(manifest_path) if own else manifest
    tiles = manifest["terrain"].setdefault(region, {"tiles": {}})["tiles"]
    for variant, cell in zip(variants, cells):
        content = trim_to_content(cell)
        w, h = content.size
        if w and h and abs(w - h) > max(2, w // 10):
            print(
                f"warning: {path.name} tile {variant} is {w}x{h}, not square",
                file=sys.stderr,
            )
        tile = content.resize((TILE_SIZE, TILE_SIZE), Image.NEAREST)
        out = out_dir / f"{variant}.png"
        tile.save(out)
        tiles[variant] = f"terrain/{region}/{variant}.png"
        written.append(out)
    if own:
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
_BODY_INSET = 8  # px from the cell edge to the body on each side
_BODY_MARGIN = 10  # px kept clear above the body
_BODY_RADIUS = 10
_BOB_PX = 2  # idle/walk vertical bob amplitude
_LEAN_PX = {"attack": 6, "hurt": -5, "defend": -3}  # horizontal lean per clip
_DEATH_FADE_AT = 0.8  # fraction of the death clip after which the initial vanishes
_CAST_RING_COLOUR = (255, 238, 170, 200)
_CAST_RING_MIN, _CAST_RING_GROWTH = 6, 10


def _triangle(t: float) -> float:
    """0 -> 1 -> 0 over t in [0, 1]."""
    return 1 - abs(2 * t - 1)


def _placeholder_cell(
    initial: str,
    colour: tuple[int, int, int],
    facing: str,
    clip: str,
    frame: int,
    frames: int,
    size: int,
) -> Image.Image:
    """A silhouette token that visibly changes per facing, clip and frame."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    t = frame / max(1, frames - 1)
    bob = int(_BOB_PX * _triangle(t)) if clip in ("idle", "walk") else 0
    if clip == "attack":
        lean = int(_LEAN_PX["attack"] * _triangle(t) / 2)
    elif clip == "hurt":
        lean = int(_LEAN_PX["hurt"] * (1 - t))
    else:
        lean = _LEAN_PX.get(clip, 0)
    height = size - _BODY_MARGIN
    if clip == "death":
        height = max(8, int((size - _BODY_MARGIN) * (1 - t)))
    r, g, b = colour
    body = [
        _BODY_INSET + lean,
        size - height + bob,
        size - _BODY_INSET + lean,
        size - 2 + bob,
    ]
    draw.rounded_rectangle(
        body,
        radius=_BODY_RADIUS,
        fill=(r, g, b, 220),
        outline=(255, 255, 255, 200),
        width=2,
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
        "west": [
            _BODY_INSET + 2 + lean,
            size // 2,
            _BODY_INSET + 6 + lean,
            size // 2 + 8,
        ],
    }[facing]
    draw.rectangle(marker, fill=(255, 255, 255, 255))
    if clip == "cast":
        ring = _CAST_RING_MIN + int(_CAST_RING_GROWTH * t)
        draw.ellipse(
            [
                size // 2 - ring,
                size // 2 - ring - 8,
                size // 2 + ring,
                size // 2 + ring - 8,
            ],
            outline=_CAST_RING_COLOUR,
            width=2,
        )
    if clip != "death" or t < _DEATH_FADE_AT:
        draw.text(
            (size // 2 - 4 + lean, size // 2 - 6 + bob), initial, fill=(0, 0, 0, 255)
        )
    return img


def _placeholder_strip(entry: dict, clip: str, frames: int) -> Image.Image:
    colour = _SIDE_COLOURS[entry["side"]]
    cells = [
        [
            _placeholder_cell(
                entry["name"][0], colour, facing, clip, frame, frames, FRAME_SIZE
            )
            for frame in range(frames)
        ]
        for facing in FACINGS
    ]
    return paste_grid(cells, FRAME_SIZE)


def write_placeholders(
    only: Iterable[str] | None = None,
    sprites_dir: Path = SPRITES_DIR,
    manifest_path: Path = MANIFEST,
    force: bool = False,
) -> list[Path]:
    """Write procedural stand-in strips for the roster (or ``only`` slugs).

    A clip that already holds real art (a manifest entry without the
    ``placeholder`` flag) is left alone unless ``force`` is set, so re-running
    the command after deliveries never clobbers them.
    """
    wanted = set(only) if only else None
    written = []
    manifest = load_manifest(manifest_path)
    for entry in ROSTER:
        slug = entry["slug"]
        if wanted is not None and slug not in wanted:
            continue
        existing = manifest["sprites"].get(slug, {}).get("clips", {})
        for clip, frames in CLIPS.items():
            if not force and clip in existing and not existing[clip].get("placeholder"):
                continue
            out, file = _clip_paths(sprites_dir, slug, clip)
            out.parent.mkdir(parents=True, exist_ok=True)
            _placeholder_strip(entry, clip, frames).save(out)
            written.append(out)
            _register_clip(
                manifest, slug, clip, file, frames, len(FACINGS), placeholder=True
            )
    save_manifest(manifest, manifest_path)
    return written


# ---------------------------------------------------------------------------
# Validate
# ---------------------------------------------------------------------------


def _strip_ok(path: Path, info: dict) -> bool:
    """A strip exists and is exactly frames x rows squares of FRAME_SIZE."""
    if not path.exists():
        return False
    try:
        with Image.open(path) as image:
            return image.size == (
                info["frames"] * FRAME_SIZE,
                info["rows"] * FRAME_SIZE,
            )
    except (OSError, ValueError):
        return False


def validate(manifest_path: Path = MANIFEST, assets_dir: Path = ASSETS) -> dict:
    """Report what the manifest has, what is still a placeholder, what is
    missing, and any entry whose file is gone or the wrong size."""
    manifest = load_manifest(manifest_path)
    report = {
        "complete": [],
        "placeholder": [],
        "missing": [],
        "broken": [],
        "tilesets_missing": [],
    }
    expected = set(CLIPS)
    for entry in ROSTER:
        slug = entry["slug"]
        clips = manifest["sprites"].get(slug, {}).get("clips", {})
        have = set(clips)
        if have < expected:
            report["missing"].append(f"{slug} ({', '.join(sorted(expected - have))})")
        for clip, info in clips.items():
            if not _strip_ok(assets_dir / info["file"], info):
                report["broken"].append(f"{slug}/{clip}")
        placeholders = sorted(
            clip for clip, info in clips.items() if info.get("placeholder")
        )
        if placeholders:
            report["placeholder"].append(f"{slug} ({', '.join(placeholders)})")
        elif have >= expected:
            report["complete"].append(slug)
    for region, block in REGIONS.items():
        tiles = manifest["terrain"].get(region, {}).get("tiles", {})
        absent = [v for v in block["variants"] if v not in tiles]
        if absent:
            report["tilesets_missing"].append(f"{region} ({', '.join(absent)})")
        for variant, file in tiles.items():
            if not (assets_dir / file).exists():
                report["broken"].append(f"{region}/{variant}")
    return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _report_written(paths: Iterable[Path]) -> None:
    for out in paths:
        shown = out.relative_to(ROOT) if out.is_relative_to(ROOT) else out
        print(f"wrote {shown}")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sheet = sub.add_parser(
        "sheet", help="intake one or more '<slug>__<clip>.png' sprite sheets"
    )
    sheet.add_argument("paths", nargs="+", type=Path)
    sheet.add_argument(
        "--rows", type=int, help="override facing row count (single file only)"
    )
    sheet.add_argument(
        "--cols", type=int, help="override frame column count (single file only)"
    )
    sheet.add_argument(
        "--grid",
        choices=GRID_MODES,
        default="auto",
        help="auto: locate cells from the content (default); even: divide by rows x cols",
    )

    tileset = sub.add_parser(
        "tileset", help="intake one or more 'tileset__<region>.png' rows"
    )
    tileset.add_argument("paths", nargs="+", type=Path)

    placeholders = sub.add_parser(
        "placeholders", help="write procedural placeholder strips"
    )
    placeholders.add_argument(
        "--only", nargs="*", help="slugs to write (default: whole roster)"
    )
    placeholders.add_argument(
        "--force", action="store_true", help="overwrite delivered art too"
    )

    sub.add_parser("validate", help="report manifest completeness")

    args = parser.parse_args(argv)
    if args.command == "sheet":
        if (args.rows or args.cols) and len(args.paths) > 1:
            parser.error("--rows/--cols apply to one sheet at a time")
        manifest = load_manifest()
        written = [
            intake_sheet(
                path, rows=args.rows, cols=args.cols, manifest=manifest, grid=args.grid
            )
            for path in args.paths
        ]
        save_manifest(manifest)
        _report_written(written)
    elif args.command == "tileset":
        manifest = load_manifest()
        written = []
        for path in args.paths:
            written.extend(intake_tileset(path, manifest=manifest))
        save_manifest(manifest)
        _report_written(written)
    elif args.command == "placeholders":
        _report_written(write_placeholders(args.only, force=args.force))
    elif args.command == "validate":
        for key, items in validate().items():
            print(f"{key}: {', '.join(items) if items else '-'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
