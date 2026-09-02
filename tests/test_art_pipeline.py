"""The battlefield art pipeline: prompt pack (tools/art_prompts.py), intake
(tools/sprite_intake.py) and the contract between them and src/terrain.py."""

import json

import pytest
from PIL import Image, ImageDraw

import src.terrain as terrain
from tools import art_prompts, sprite_intake


class TestPromptPack:
    def test_pack_covers_every_roster_clip_and_region(self):
        pack = art_prompts.build_pack()
        assert len(pack["sprites"]) == len(art_prompts.ROSTER) * len(art_prompts.CLIPS)
        assert {t["region"] for t in pack["tilesets"]} == set(art_prompts.REGIONS)
        for sheet in pack["sprites"]:
            assert sheet["rows"] == len(art_prompts.FACINGS)
            assert sheet["frames"] == art_prompts.CLIPS[sheet["clip"]]
            assert f"{sheet['rows']} x {sheet['frames']} grid" in sheet["prompt"]
            assert "#FF00FF" in sheet["prompt"]

    def test_region_palettes_match_the_engine(self):
        """Every terrain variant the engine can emit has a tile prompt, and
        every prompt tile is a variant the engine emits."""
        for region, palette in terrain.REGION_PALETTES.items():
            assert region in art_prompts.REGIONS, region
            prompt_variants = set(art_prompts.REGIONS[region]["variants"])
            assert prompt_variants == set(palette.values()), region

    def test_roster_slugs_are_unique_and_filename_safe(self):
        slugs = [e["slug"] for e in art_prompts.ROSTER]
        assert len(slugs) == len(set(slugs))
        assert all(s.isalnum() for s in slugs)

    def test_write_pack_is_deterministic(self, tmp_path):
        first = art_prompts.write_pack(tmp_path / "a")
        second = art_prompts.write_pack(tmp_path / "b")
        assert [p.name for p in first] == [p.name for p in second]
        for a, b in zip(first, second):
            assert a.read_bytes() == b.read_bytes()
        assert (tmp_path / "a" / "README.md").exists()
        assert json.loads((tmp_path / "a" / "pack.json").read_text())["frame_size"] == art_prompts.FRAME_SIZE


def _fake_sheet(rows, cols, cell=40, gap=2):
    """A delivered-looking sheet: magenta background, one coloured blob per cell
    with a distinct colour so slicing can be checked."""
    w = cols * cell + (cols + 1) * gap
    h = rows * cell + (rows + 1) * gap
    img = Image.new("RGB", (w, h), sprite_intake.CHROMA)
    draw = ImageDraw.Draw(img)
    for r in range(rows):
        for c in range(cols):
            x0 = gap + c * (cell + gap)
            y0 = gap + r * (cell + gap)
            draw.ellipse([x0 + 6, y0 + 4, x0 + cell - 6, y0 + cell - 2], fill=(10 * (r + 1), 20 * (c + 1), 200))
    return img


class TestIntake:
    def test_key_out_background(self):
        img = Image.new("RGB", (4, 1), sprite_intake.CHROMA)
        img.putpixel((0, 0), (250, 10, 245))  # near-magenta fringe
        img.putpixel((3, 0), (0, 0, 255))
        keyed = sprite_intake.key_out_background(img)
        assert keyed.getpixel((0, 0))[3] == 0
        assert keyed.getpixel((1, 0))[3] == 0
        assert keyed.getpixel((3, 0)) == (0, 0, 255, 255)

    def test_sheet_intake_writes_strip_and_manifest(self, tmp_path):
        sheet = tmp_path / "jean__idle.png"
        _fake_sheet(3, art_prompts.CLIPS["idle"]).save(sheet)
        sprites = tmp_path / "sprites"
        manifest = sprites / "manifest.json"
        out = sprite_intake.intake_sheet(sheet, sprites_dir=sprites, manifest_path=manifest)
        assert out == sprites / "jean" / "idle.png"
        strip = Image.open(out)
        assert strip.size == (art_prompts.CLIPS["idle"] * art_prompts.FRAME_SIZE, 3 * art_prompts.FRAME_SIZE)
        # Corners between sprites are transparent; each frame has content.
        assert strip.getpixel((0, 0))[3] == 0
        for f in range(art_prompts.CLIPS["idle"]):
            frame = strip.crop((f * 64, 0, (f + 1) * 64, 64))
            assert frame.getbbox() is not None
        data = json.loads(manifest.read_text())
        assert data["sprites"]["jean"]["clips"]["idle"] == {"file": "sprites/jean/idle.png", "frames": 4, "rows": 3}
        assert data["facings"] == list(art_prompts.FACINGS)

    def test_sheet_name_validation(self, tmp_path):
        with pytest.raises(ValueError):
            sprite_intake.parse_sheet_name(tmp_path / "jean.png")
        with pytest.raises(ValueError):
            sprite_intake.parse_sheet_name(tmp_path / "jean__dance.png")
        assert sprite_intake.parse_sheet_name(tmp_path / "slime__death.png") == ("slime", "death")

    def test_tileset_intake(self, tmp_path):
        variants = list(art_prompts.REGIONS["verdette_caverns"]["variants"])
        sheet = tmp_path / "tileset__verdette_caverns.png"
        _fake_sheet(1, len(variants)).save(sheet)
        terrain_dir = tmp_path / "terrain"
        manifest = tmp_path / "manifest.json"
        written = sprite_intake.intake_tileset(sheet, terrain_dir=terrain_dir, manifest_path=manifest)
        assert [p.name for p in written] == [f"{v}.png" for v in variants]
        assert all(Image.open(p).size == (art_prompts.TILE_SIZE, art_prompts.TILE_SIZE) for p in written)
        data = json.loads(manifest.read_text())
        assert data["terrain"]["verdette_caverns"]["tiles"]["shallow_water"] == "terrain/verdette_caverns/shallow_water.png"
        with pytest.raises(ValueError):
            sprite_intake.parse_tileset_name(tmp_path / "tileset__moon.png")

    def test_placeholders_and_validate(self, tmp_path):
        sprites = tmp_path / "sprites"
        manifest = sprites / "manifest.json"
        written = sprite_intake.write_placeholders(["jean", "slime"], sprites_dir=sprites, manifest_path=manifest)
        assert len(written) == 2 * len(art_prompts.CLIPS)
        report = sprite_intake.validate(manifest_path=manifest, assets_dir=tmp_path)
        assert set(report["placeholder"]) == {"jean", "slime"}
        assert "gorran" in report["missing"]
        assert report["broken"] == []
        assert set(report["tilesets_missing"]) == set(art_prompts.REGIONS)
        # A real delivery replaces the placeholder flag for that clip.
        sheet = tmp_path / "jean__idle.png"
        _fake_sheet(3, 4).save(sheet)
        sprite_intake.intake_sheet(sheet, sprites_dir=sprites, manifest_path=manifest)
        data = json.loads(manifest.read_text())
        assert "placeholder" not in data["sprites"]["jean"]["clips"]["idle"]
        assert data["sprites"]["jean"]["clips"]["walk"]["placeholder"] is True

    def test_manifest_load_tolerates_garbage(self, tmp_path):
        bad = tmp_path / "manifest.json"
        bad.write_text("{not json")
        data = sprite_intake.load_manifest(bad)
        assert data["sprites"] == {} and data["frame_size"] == art_prompts.FRAME_SIZE


def test_committed_manifest_matches_disk():
    """Whatever art is checked in must be reachable by the frontend."""
    report = sprite_intake.validate()
    assert report["broken"] == []
