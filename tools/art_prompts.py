"""Generate the Gemini / Nano Banana prompt pack for battlefield art.

The battlefield draws every combatant as an animated 3/4-top-down sprite and
every terrain cell from a per-region tileset (see docs/development/art-pipeline.md).
The art is produced outside the repo by an image model; this module owns the
*specification* of what is asked for so the prompts, the intake tool
(``tools/sprite_intake.py``) and the frontend manifest agree on frame sizes,
clip names, facings and file names.

Run ``python tools/art_prompts.py`` to (re)write ``docs/development/art-prompts/``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "docs" / "development" / "art-prompts"

# ---------------------------------------------------------------------------
# Sheet specification (shared by prompts, intake and frontend)
# ---------------------------------------------------------------------------

FRAME_SIZE = 64  # px, square, after intake normalisation

#: Chroma key the prompts ask for behind every cell and the intake keys to
#: transparency. One definition; ``sprite_intake`` imports it.
CHROMA_RGB = (255, 0, 255)
CHROMA_HEX = "#%02X%02X%02X" % CHROMA_RGB

#: Delivery file-name convention: ``<slug>__<clip>.png`` and
#: ``tileset__<region>.png``. ``sheet_filename``/``tileset_filename`` build
#: them and ``parse_sheet_filename``/``parse_tileset_filename`` invert them,
#: so the two directions cannot drift apart.
SHEET_SEPARATOR = "__"
TILESET_PREFIX = "tileset"

#: Facings drawn. East is mirrored from west at render time, so three rows.
FACINGS = ("south", "west", "north")

#: Animation clips and their frame counts. Dict order is only the order the
#: docs list them in: each clip is requested as its own image (one sheet per
#: clip: rows = facings, columns = frames) because image models keep a 3x6
#: grid coherent far more reliably than a 21x6 one, so no row order across
#: clips is ever relied upon.
CLIPS = {
    "idle": 4,
    "walk": 6,
    "attack": 6,
    "cast": 6,
    "defend": 4,
    "hurt": 3,
    "death": 6,
}

#: What each clip is used for in combat, for the prompt and for reviewers.
CLIP_NOTES = {
    "idle": "breathing / weight-shift loop used whenever the combatant is waiting",
    "walk": "movement loop used while advancing, withdrawing or flanking",
    "attack": "one committed strike: wind-up (first third of the frames), swing/impact (middle third), recoil (last third)",
    "cast": "a focused non-weapon action: raising a hand, gathering energy, bracing a shout; used for buffs, specials and supernatural moves",
    "defend": "guard raised: parry / dodge stance held, then relaxed",
    "hurt": "flinch from a hit: recoil, hold, recover",
    "death": "collapse to the ground; final frame is the resting corpse (it is held on screen)",
}

STYLE_BLOCK = """\
STYLE: 16-bit pixel art sprite sheet, crisp hand-placed pixels, no anti-aliasing, \
no blur, no gradients, no outlines thicker than one pixel. 3/4 top-down RPG view \
(camera pitched about 60 degrees, as in a SNES-era tactical RPG). Muted, slightly \
desaturated palette with one strong accent colour per character. Dark-fantasy \
tone: worn, practical, grounded. Read clearly at 48 px on a dark #0a0a0a field. \
No text, no labels, no watermark, no drop shadow (the game draws its own)."""

LAYOUT_BLOCK = """\
LAYOUT: a single PNG containing a strict {rows} x {cols} grid of equal square cells \
({rows} rows, {cols} columns), every cell the same size, with hairline gaps of \
solid magenta ({chroma}) between cells and a solid magenta background behind \
every cell. One sprite per cell, centred, feet on the same baseline in every cell, \
identical scale in every cell. Row 1 = facing SOUTH (toward the viewer), \
row 2 = facing WEST (left), row 3 = facing NORTH (away). Columns are the \
animation frames in order, left to right. Do not draw anything outside the cells."""


def _sheet_prompt(subject: str, clip: str, frames: int, accent: str) -> str:
    return "\n\n".join(
        [
            f"SUBJECT: {subject} Accent colour: {accent}.",
            f"ANIMATION: '{clip}' -- {CLIP_NOTES[clip]}. Exactly {frames} frames per row, "
            f"a smooth loop where the clip is a loop (idle, walk) and a clean start-to-end "
            f"sequence otherwise. The pose must be recognisably the same character in all "
            f"{frames * len(FACINGS)} cells.",
            LAYOUT_BLOCK.format(rows=len(FACINGS), cols=frames, chroma=CHROMA_HEX),
            STYLE_BLOCK,
        ]
    )


# ---------------------------------------------------------------------------
# Roster. A slug is what ``CombatantSerializer.sprite_key`` emits for the
# combatant: ``jean`` for the player, otherwise the NPC class name lower-cased
# (or the class's own ``sprite_key`` attribute). Non-combat NPCs (Mynx, the
# nomads, Grondites) and debug-only fighters (Testexp, TheAdjutant) are left
# out deliberately: they keep the glyph token.
# ---------------------------------------------------------------------------

ROSTER = [
    {
        "slug": "jean",
        "name": "Jean Claire",
        "side": "hero",
        "accent": "grey-green scarf teal",
        "subject": (
            "Jean Claire, a lean man of 32, slightly taller than average, short dark-brown "
            "shaggy hair, several days' stubble, heavy brow, blue-grey eyes. Wears a layered "
            "brown leather and oilcloth travelling coat with a raised collar, a grey-green "
            "wrapped neck scarf, crossed leather chest straps with brass buckles, dark "
            "trousers, worn boots. Carries a plain one-handed sword; a rosary hangs at his "
            "belt. Practical, not knightly -- a traveller who has learned to fight."
        ),
    },
    {
        "slug": "gorran",
        "name": "Gorran (Golemite ally)",
        "side": "ally",
        "accent": "luminous moss cyan",
        "subject": (
            "Gorran, a massive Golemite: a broad, heavily built humanoid of living stone, "
            "angular faceted grey-green rock plates, glowing pale-cyan eyes set deep in a "
            "helm-like stone head, no visible mouth. A star-shaped patch of luminous "
            "pale-green moss grows on one shoulder. Moves slowly and deliberately, swings a "
            "heavy stone club two-handed. Roughly one and a half times Jean's height."
        ),
    },
    {
        "slug": "mara",
        "name": "Mara (nomad ally)",
        "side": "ally",
        "accent": "blue-grey scarf",
        "subject": (
            "Mara, a lean nomad woman in her late twenties, below average height, dark "
            "auburn curly hair cut to the shoulder and tied back loosely, sharp green eyes. "
            "Layered olive and brown travel gear, a blue-grey scarf, pack straps across the "
            "chest, laced boots; a worn crucifix on a knotted cord at her neck. Fights with "
            "a dagger in hand and a short bow slung across her back. Watchful, unhurried."
        ),
    },
    {
        "slug": "slime",
        "name": "Slime",
        "side": "enemy",
        "accent": "murky green",
        "subject": (
            "A common cave slime: a knee-high amorphous gelatinous blob, translucent pale to "
            "murky green, no limbs or face, surface rippling into pseudopod bulges; small "
            "swallowed pebbles and insect chitin visible suspended inside it. It attacks by "
            "surging forward and slapping with a pseudopod; it casts by swelling; it dies by "
            "deflating into a puddle."
        ),
    },
    {
        "slug": "elderslime",
        "name": "Elder Slime",
        "side": "enemy",
        "accent": "brown-green with amber inclusions",
        "subject": (
            "An Elder Slime: a slime the size of a small cart, thick and heavy, murky "
            "green-brown, studded with visible mineral inclusions and small stones. Slow, "
            "deliberate; a faint suggestion of intelligence in how it watches. Attacks with a "
            "ponderous heave; dies by slumping and going dull."
        ),
    },
    {
        "slug": "kingslime",
        "name": "King Slime (boss)",
        "side": "enemy",
        "accent": "deep green with crystal shards",
        "subject": (
            "The King Slime: a colossal mass of pulsating deep-green slime, its body studded "
            "with crystalline shards and corroded stone fragments consumed over centuries. It "
            "rears upward for its attack like a wave about to break, churns and glows when it "
            "casts, and collapses outward in a spreading pool when it dies. It should fill "
            "its cell edge to edge -- larger than any other combatant."
        ),
    },
    {
        "slug": "rockrumbler",
        "name": "Rock Rumbler",
        "side": "enemy",
        "accent": "ember-orange eyes",
        "subject": (
            "A Rock Rumbler: a burly low quadruped like a stout crocodile armoured in "
            "interlocking rocky plates and mineral crust, grey-brown stone, short powerful "
            "limbs, a heavy club-like tail, small deep-set glowing ember-orange eyes, a blunt "
            "toothed maw. Attacks with a lunging bite and a tail slam; dies by collapsing into "
            "a heap that looks like loose rock."
        ),
    },
    {
        "slug": "cavebat",
        "name": "Cave Bat",
        "side": "enemy",
        "accent": "faint amber eyes",
        "subject": (
            "A cave bat: a small leathery-winged bat, dark brown to black fur, membranous "
            "wings, short hooked claws, faintly glowing amber eyes. Always airborne -- idle is "
            "a hovering wing-beat, walk is a swooping flight, attack is a dive-bite, death is "
            "a tumble to the ground with wings crumpled."
        ),
    },
    {
        "slug": "giantspider",
        "name": "Giant Spider",
        "side": "enemy",
        "accent": "toxic green drool",
        "subject": (
            "A giant cave spider the size of a large dog: black bristling wiry hair, eight "
            "long jointed legs, a cluster of gleaming eyes, sharp mandibles dripping "
            "faintly glowing green venom. Attacks with a rearing bite; dies curled on its back."
        ),
    },
    {
        "slug": "lurker",
        "name": "Lurker (boss)",
        "side": "enemy",
        "accent": "sickly yellow eyes",
        "subject": (
            "A Lurker: a grisly demon of the dark, vaguely humanoid and wrong in proportion -- "
            "elongated torso, long thin arms ending in hooked poisonous claws, hunched, "
            "skin like wet charcoal, faintly glowing sickly-yellow eyes, no other features. "
            "Attacks with a raking double-claw swipe; casts by spreading its arms in a "
            "shroud of darkness; dies folding in on itself."
        ),
    },
    {
        "slug": "talushound",
        "name": "Talus Hound",
        "side": "enemy",
        "accent": "pale amber eyes",
        "subject": (
            "A Talus Hound: a lean shaggy quadruped the size of a large dog, layered mottled "
            "grey-brown hide that reads as rock camouflage, heavily muscled legs, a broad "
            "low-set head, pale amber eyes. A pack hunter: idle is a low prowl, walk is a "
            "loping run, attack is a leaping bite, death is a sprawl."
        ),
    },
    {
        "slug": "scarpadder",
        "name": "Scarp Adder",
        "side": "enemy",
        "accent": "pale blue tongue",
        "subject": (
            "A Scarp Adder: a thick-bodied serpent, scales layered like flakes of split "
            "shale, dark grey with silver edges, a broad triangular head with heat-sensing "
            "jaw pits and a flickering pale-blue tongue. Coiled when idle, uncoils to move, "
            "strikes with a fast lunge, dies stretched out limp."
        ),
    },
    {
        "slug": "corruptedstonecreature",
        "name": "Corrupted Stone Creature",
        "side": "enemy",
        "accent": "sick iridescent green slurry",
        "subject": (
            "A Corrupted Stone Creature: a lurching vaguely humanoid mass of pebbles, rock "
            "fragments and crystalline shards loosely bound in a grey slurry streaked with "
            "sickly iridescent green; no face, though one fragment might be an eye. It trails "
            "slurry as it moves. Attacks with a heavy overhand slam; casts by grinding and "
            "swelling; dies by falling apart into a pile of stones."
        ),
    },
    {
        "slug": "wailwraith",
        "name": "Wail Wraith (boss)",
        "side": "enemy",
        "accent": "dust-grey with rust",
        "subject": (
            "A Wail Wraith: a ragged shape woven from sound and absence, more heard than "
            "seen -- no stable silhouette, edges blurring like heat haze, briefly cohering "
            "into a hooded near-humanoid form then fraying. Dust-grey and rust, no eyes or "
            "face. It does not walk; it drifts. Attack is a keening lunge, cast is a "
            "spreading toll, death is unravelling into threads of dust."
        ),
    },
    {
        "slug": "statusdummy",
        "name": "Pell (training dummy)",
        "side": "enemy",
        "accent": "bleached linen",
        "subject": (
            "Pell, a training dummy: a featureless humanoid shape woven from pale dream-stuff "
            "and bleached linen, stitched seams, no face, standing on a short post. It sways "
            "when struck and slumps on its post when 'killed'. It holds no malice."
        ),
    },
]

# ---------------------------------------------------------------------------
# Region tilesets (variants match src/terrain.py REGION_PALETTES)
# ---------------------------------------------------------------------------

TILE_SIZE = 64

REGIONS = {
    "arena": {
        "name": "Proving Grounds (testing arena)",
        "mood": "a clean dreamlike training floor: pale grey stone slabs, soft even light, no debris",
        "variants": {
            "arena_floor": "smooth pale stone floor slab, three subtle variations",
            "rubble": "loose grey stone rubble scattered on the floor",
            "slime": "a puddle of translucent green slime",
            "stone_shelf": "a raised stone shelf top, one step up, with a lit front edge",
            "boulder": "a single rounded grey boulder",
            "stone_wall": "a solid dressed-stone wall block, top-down",
            "drop": "a black drop-off into nothing, edge lit",
        },
    },
    "verdette_caverns": {
        "name": "Verdette Caverns",
        "mood": "a damp limestone cave lit by veins of living rose-pink crystal; cool grey-violet wet stone, teal-green lichen, bone-white guano stains",
        "variants": {
            "cavern_floor": "wet grey-violet cave floor with faint pink crystal glow, three variations",
            "shallow_water": "ankle-deep dark still water mirroring pink crystal light",
            "slime": "a sheet of sweet-putrid green slime clinging to the floor",
            "rock_shelf": "a raised natural rock shelf, one step up, lit front edge",
            "crystal_cluster": "a cluster of jutting rose-pink crystals, impassable",
            "crystal_wall": "a cave wall shot through with pink crystal veins, top-down",
            "chasm": "a black crevasse in the cave floor, edge lit faintly pink",
        },
    },
    "eastern_descent": {
        "name": "Eastern Descent",
        "mood": "open-air pale grey mountain rock under a cold blue-white sky; lichen green, dun scrub, wind-scoured",
        "variants": {
            "mountain_rock": "pale grey undressed mountain rock ground, three variations",
            "scree": "loose grey scree and gravel",
            "thornbrush": "a low tangle of dry thorn scrub",
            "ledge": "a raised rock ledge, one step up, lit front edge",
            "boulder": "a cart-horse-sized pale grey boulder with lichen, impassable",
            "rock_face": "a sheer rock face block, top-down",
            "cliff_edge": "the edge of a cliff falling away to haze below",
        },
    },
    "dark_grotto": {
        "name": "Dark Grotto",
        "mood": "near-black wet limestone; slow drips, pale grit, ghost-white dew-beaded mushrooms, a thin silver shaft of daylight",
        "variants": {
            "grotto_floor": "wet black-grey limestone floor, three variations",
            "rubble": "pale grit and fallen ceiling rubble",
            "slime": "a slick of dark green slime",
            "rock_shelf": "a raised limestone shelf, one step up",
            "fallen_rock": "a large fallen rock slab, impassable",
            "grotto_wall": "wet black limestone wall, top-down",
            "chasm": "a black hole in the floor",
        },
    },
    "mineral_pools": {
        "name": "Grondelith Mineral Pools",
        "mood": "polished Golemite stone basins holding luminous milky-blue spring water, turning to sickly iridescent green slime where corrupted",
        "variants": {
            "polished_stone": "polished pale stone floor with carved swirling channels, three variations",
            "luminous_pool": "a basin of glowing milky-blue spring water",
            "corrupted_slime": "a thick sheet of iridescent green corrupted slime, acid-pitted stone beneath",
            "basin_rim": "a raised carved basin rim, one step up",
            "mineral_spire": "a fractured crystalline mineral spire, impassable",
            "channel_wall": "a carved stone channel wall, top-down",
            "chasm": "a dissolved hole in the floor, edges acid-pitted",
        },
    },
    "grondia": {
        "name": "Grondia",
        "mood": "a warm amber-lit stone city carved inside a bluff: cool grey stone floors, heat-crystal glow, carved sigils",
        "variants": {
            "carved_floor": "smooth carved grey stone floor with faint worn channels, three variations",
            "market_clutter": "crates, rolled linen and stone counters cluttering the floor",
            "slime": "a puddle of green slime",
            "dais": "a raised carved stone dais, one step up",
            "stone_pillar": "a carved stone pillar, impassable",
            "carved_wall": "a carved stone wall with faded bas-relief, top-down",
            "drop": "a railing-less drop to a lower terrace",
        },
    },
    "wailing_badlands": {
        "name": "Wailing Badlands",
        "mood": "gray-and-rust wind-scoured badlands under a dust haze; shattered stone spires, rust-stained rock",
        "variants": {
            "dust_flat": "hard-packed grey dust flat, three variations",
            "rust_rubble": "rust-red loose rubble",
            "dust_sink": "a sink of fine choking dust",
            "block_top": "the flat top of a fallen inscribed stone block, one step up",
            "fallen_block": "a massive fallen stone block with half-legible inscriptions, impassable",
            "stone_spire": "the base of a cracked stone spire, top-down",
            "crevasse": "a hidden crevasse in the flat",
        },
    },
}

TILE_LAYOUT = """\
LAYOUT: a single PNG containing a strict 1 x {cols} row of equal square tiles \
({cols} tiles, left to right, in the order listed), hairline gaps of solid magenta \
({chroma}) between tiles and a solid magenta background wherever a tile is \
transparent (the "{opaque}" tile is fully opaque). Each tile must be seamless \
with its own copies on all four sides (the floor tiles especially). Top-down 3/4 \
view matching the sprite sheets: the ground is seen from above at about 60 degrees, \
raised features show a lit top face and a short shaded front face."""

TILE_STYLE = """\
STYLE: 16-bit pixel art tileset, crisp pixels, no anti-aliasing, no blur, no text. \
Muted desaturated palette; the region's accent colour appears only where the \
description says so. Every tile must read at 40 px on a dark #0a0a0a field and must \
stay legible under a 75%-size character sprite standing on it -- keep floor tiles \
low-contrast and features high-contrast."""


def _tileset_prompt(region: dict) -> str:
    variants = region["variants"]
    order = ", ".join(
        f"{i + 1}. {desc} [{key}]" for i, (key, desc) in enumerate(variants.items())
    )
    opaque = list(variants)[-1]  # the CLIFF variant is always listed last
    return "\n\n".join(
        [
            f"SUBJECT: terrain tileset for {region['name']}: {region['mood']}.",
            f"TILES, in this order: {order}.",
            TILE_LAYOUT.format(cols=len(variants), chroma=CHROMA_HEX, opaque=opaque),
            TILE_STYLE,
        ]
    )


# ---------------------------------------------------------------------------
# Writers
# ---------------------------------------------------------------------------


#: Every slug the roster defines; the intake refuses anything else.
SLUGS = frozenset(entry["slug"] for entry in ROSTER)

#: Tiles per region tileset: every region mirrors the engine's kinds exactly.
TILES_PER_REGION = len(next(iter(REGIONS.values()))["variants"])
assert all(
    len(region["variants"]) == TILES_PER_REGION for region in REGIONS.values()
), "every region tileset must have the same tile count"


def sheet_filename(slug: str, clip: str) -> str:
    return f"{slug}{SHEET_SEPARATOR}{clip}.png"


def tileset_filename(region_key: str) -> str:
    return f"{TILESET_PREFIX}{SHEET_SEPARATOR}{region_key}.png"


def parse_sheet_filename(name: str):
    """``jean__idle.png`` -> ``("jean", "idle")``; raises ``ValueError`` for an
    unknown slug or clip so a mis-named delivery cannot create a stray sprite
    (or, via ``..``, a file outside the sprites directory)."""
    stem = name[:-4] if name.lower().endswith(".png") else name
    if SHEET_SEPARATOR not in stem:
        raise ValueError(f"{name}: expected '<slug>{SHEET_SEPARATOR}<clip>.png'")
    slug, clip = stem.split(SHEET_SEPARATOR, 1)
    if slug not in SLUGS:
        raise ValueError(f"{name}: unknown slug {slug!r}; known: {sorted(SLUGS)}")
    if clip not in CLIPS:
        raise ValueError(f"{name}: unknown clip {clip!r}; known: {sorted(CLIPS)}")
    return slug, clip


def parse_tileset_filename(name: str) -> str:
    """``tileset__verdette_caverns.png`` -> ``"verdette_caverns"``."""
    stem = name[:-4] if name.lower().endswith(".png") else name
    prefix = f"{TILESET_PREFIX}{SHEET_SEPARATOR}"
    if not stem.startswith(prefix):
        raise ValueError(f"{name}: expected '{prefix}<region>.png'")
    region = stem.removeprefix(prefix)
    if region not in REGIONS:
        raise ValueError(f"{name}: unknown region {region!r}; known: {sorted(REGIONS)}")
    return region


def spec_header() -> dict:
    """The spec fields the prompt pack and the manifest both carry."""
    return {
        "frame_size": FRAME_SIZE,
        "tile_size": TILE_SIZE,
        "facings": list(FACINGS),
        "clips": dict(CLIPS),
    }


def build_pack() -> dict:
    """All prompts as data, so the intake tool and tests share one source."""
    sprites = []
    for entry in ROSTER:
        for clip, frames in CLIPS.items():
            sprites.append(
                {
                    "slug": entry["slug"],
                    "name": entry["name"],
                    "clip": clip,
                    "frames": frames,
                    "rows": len(FACINGS),
                    "deliver_as": sheet_filename(entry["slug"], clip),
                    "prompt": _sheet_prompt(
                        entry["subject"], clip, frames, entry["accent"]
                    ),
                }
            )
    tilesets = [
        {
            "region": key,
            "name": region["name"],
            "variants": list(region["variants"].keys()),
            "deliver_as": tileset_filename(key),
            "prompt": _tileset_prompt(region),
        }
        for key, region in REGIONS.items()
    ]
    return {**spec_header(), "sprites": sprites, "tilesets": tilesets}


def _sprite_doc(entry: dict, sheets: list[dict]) -> str:
    """Markdown for one combatant: one fenced prompt per clip."""
    lines = [
        f"# Sprite sheets: {entry['name']}",
        "",
        f"Slug: `{entry['slug']}`  ",
        f"Side: {entry['side']}",
        "",
        "One image per clip. Deliver each as the file name shown; the intake tool "
        "slices it by the stated grid and normalises frames to "
        f"{FRAME_SIZE}x{FRAME_SIZE}.",
        "",
    ]
    for sheet in sheets:
        lines.extend(
            [
                f"## {sheet['clip']} -- deliver as `{sheet['deliver_as']}` "
                f"({sheet['rows']} rows x {sheet['frames']} cols)",
                "",
                "```text",
                sheet["prompt"],
                "```",
                "",
            ]
        )
    return "\n".join(lines)


def _tileset_doc(tileset: dict) -> str:
    """Markdown for one region tileset: tile order plus the fenced prompt."""
    region = REGIONS[tileset["region"]]
    lines = [
        f"# Tileset: {tileset['name']}",
        "",
        f"Region key: `{tileset['region']}`  ",
        f"Deliver as `{tileset['deliver_as']}` (1 row x {len(tileset['variants'])} tiles).",
        "",
        "Tile order and the variant key each one becomes:",
        "",
    ]
    for i, (vkey, desc) in enumerate(region["variants"].items()):
        lines.append(f"{i + 1}. `{vkey}` -- {desc}")
    lines.extend(["", "```text", tileset["prompt"], "```", ""])
    return "\n".join(lines)


def write_pack(out_dir: Path = OUT_DIR) -> list[Path]:
    """Write README, one sprite doc per combatant, one tileset doc per region
    and ``pack.json`` -- all rendered from one ``build_pack()`` so the markdown
    and the JSON can never disagree. Stale docs from a renamed slug or region
    are removed so the directory always equals the pack."""
    out_dir.mkdir(parents=True, exist_ok=True)
    pack = build_pack()
    written = []

    readme = out_dir / "README.md"
    readme.write_text(_readme_text(pack), encoding="utf-8")
    written.append(readme)

    for entry in ROSTER:
        sheets = [sheet for sheet in pack["sprites"] if sheet["slug"] == entry["slug"]]
        path = out_dir / f"sprite-{entry['slug']}.md"
        path.write_text(_sprite_doc(entry, sheets), encoding="utf-8")
        written.append(path)

    for tileset in pack["tilesets"]:
        path = out_dir / f"tileset-{tileset['region']}.md"
        path.write_text(_tileset_doc(tileset), encoding="utf-8")
        written.append(path)

    manifest = out_dir / "pack.json"
    manifest.write_text(json.dumps(pack, indent=2), encoding="utf-8")
    written.append(manifest)

    keep = {p.name for p in written}
    for stale in out_dir.glob("*.md"):
        if stale.name not in keep and (
            stale.name.startswith("sprite-") or stale.name.startswith("tileset-")
        ):
            stale.unlink()
    return written


def _readme_text(pack: dict) -> str:
    n_sheets = len(pack["sprites"])
    return f"""# Battlefield art prompt pack

Generated by `python tools/art_prompts.py` -- edit that file, not these.

## What to generate

* **{n_sheets} sprite sheets**: {len(ROSTER)} combatants x {len(CLIPS)} clips
  (`sprite-<slug>.md`). Each sheet is one image: {len(FACINGS)} rows (south, west,
  north facing) x N frames. East is mirrored from west by the game.
* **{len(REGIONS)} tilesets**: one image per region (`tileset-<region>.md`), one row
  of {TILES_PER_REGION} tiles in a fixed order.

Paste each fenced prompt into Gemini / Nano Banana 2 as-is. Where the model
supports a reference image, attach the character's portrait
(`frontend/public/assets/portraits/<slug>/neutral.png`) for Jean, Gorran and
Mara so the sprite keeps their face and palette.

## Delivering results

Save each result under the file name its heading shows and run:

```bash
python tools/sprite_intake.py sheet  path/to/jean__idle.png          # one clip
python tools/sprite_intake.py sheet  path/to/*.png                    # many
python tools/sprite_intake.py tileset path/to/tileset__verdette_caverns.png
python tools/sprite_intake.py validate                                # what is still missing
```

The intake tool keys the magenta ({CHROMA_HEX}) background to transparency, splits
the image into the expected grid, resamples every cell to
{pack["frame_size"]}x{pack["frame_size"]} with nearest-neighbour sampling (pixels stay
crisp), writes one strip per clip under `frontend/public/assets/sprites/<slug>/`
(or `frontend/public/assets/terrain/<region>/`), and updates
`frontend/public/assets/sprites/manifest.json`, which the battlefield reads at
runtime. A combatant or region with no manifest entry keeps its procedural
placeholder, so partial deliveries are fine.

If a generated sheet's grid is not exact (the usual failure), crop the image to
the outer magenta border before intake; the tool divides the image evenly, so a
skewed border is the one thing it cannot fix. `--rows/--cols` override the
expected grid when a model returns a different but consistent layout.

## Checklist per sheet

- [ ] Same character, same scale, same baseline in every cell
- [ ] Row order south / west / north
- [ ] Frame count matches the heading
- [ ] Solid {CHROMA_HEX} background, no anti-aliased fringe against it
- [ ] Nothing drawn across cell gaps
"""


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT_DIR)
    args = parser.parse_args(argv)
    for path in write_pack(args.out):
        shown = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
        print(f"wrote {shown}")


if __name__ == "__main__":
    main()
