"""The battlefield art pipeline: prompt pack (tools/art_prompts.py), intake
(tools/sprite_intake.py) and the contract between them and src/terrain.py."""

import json

import pytest
from PIL import Image, ImageDraw

import src.terrain as terrain
from tools import art_prompts, sprite_intake

FRAME = art_prompts.FRAME_SIZE
ROWS = len(art_prompts.FACINGS)
IDLE_FRAMES = art_prompts.CLIPS["idle"]


class TestPromptPack:
    def test_pack_covers_every_roster_clip_and_region(self):
        pack = art_prompts.build_pack()
        assert len(pack["sprites"]) == len(art_prompts.ROSTER) * len(art_prompts.CLIPS)
        assert {t["region"] for t in pack["tilesets"]} == set(art_prompts.REGIONS)
        for sheet in pack["sprites"]:
            assert sheet["rows"] == ROWS
            assert sheet["frames"] == art_prompts.CLIPS[sheet["clip"]]
            assert f"{sheet['rows']} x {sheet['frames']} grid" in sheet["prompt"]
            assert art_prompts.CHROMA_HEX in sheet["prompt"]
        for tileset in pack["tilesets"]:
            # The opaque tile is named per region, never a generic "drop".
            opaque = tileset["variants"][-1]
            assert f'"{opaque}" tile is fully opaque' in tileset["prompt"]

    def test_region_palettes_match_the_engine_both_ways(self):
        """Every terrain variant the engine can emit has a tile prompt, and
        every prompt region/variant is one the engine emits."""
        assert set(art_prompts.REGIONS) == set(terrain.REGION_PALETTES)
        for region, palette in terrain.REGION_PALETTES.items():
            assert set(art_prompts.REGIONS[region]["variants"]) == set(palette.values()), region
            # The cliff variant is listed last: the tileset prompt relies on it.
            assert list(art_prompts.REGIONS[region]["variants"])[-1] == palette[terrain.CLIFF]

    def test_roster_slugs_are_unique_and_filename_safe(self):
        slugs = [e["slug"] for e in art_prompts.ROSTER]
        assert len(slugs) == len(set(slugs))
        assert all(s.isalnum() for s in slugs)
        assert art_prompts.SLUGS == frozenset(slugs)
        assert all(key.replace("_", "").isalnum() for key in art_prompts.REGIONS)

    def test_delivery_extensions_are_stripped(self):
        assert art_prompts.parse_sheet_filename("cavebat__idle.JPG") == ("cavebat", "idle")
        assert art_prompts.parse_sheet_filename("cavebat__idle.webp") == ("cavebat", "idle")
        assert art_prompts.parse_tileset_filename("tileset__arena.jpeg") == "arena"

    def test_prompt_names_every_frame_and_forbids_composites(self):
        prompt = art_prompts._sheet_prompt("A thing.", "attack", 6, "red")
        assert "1 = wind-up begins" in prompt and "6 = recoil back to rest" in prompt
        assert "containing ONLY this clip" in prompt and "No gridlines" in prompt
        assert "seamless loop" in art_prompts._sheet_prompt("A thing.", "idle", 4, "red")
        assert art_prompts.frame_phases("hurt", 1) == ["recoil from the hit"]
        assert len(art_prompts.frame_phases("death", 9)) == 9

    def test_filename_round_trip(self):
        assert art_prompts.parse_sheet_filename(art_prompts.sheet_filename("jean", "idle")) == ("jean", "idle")
        assert art_prompts.parse_tileset_filename(art_prompts.tileset_filename("grondia")) == "grondia"
        for bad in ("jean.png", "jeen__idle.png", "jean__dance.png", "..__idle.png", "__idle.png"):
            with pytest.raises(ValueError):
                art_prompts.parse_sheet_filename(bad)
        with pytest.raises(ValueError):
            art_prompts.parse_tileset_filename("tileset__moon.png")

    def test_write_pack_is_deterministic_and_removes_stale_docs(self, tmp_path):
        out = tmp_path / "a"
        out.mkdir()
        (out / "sprite-oldslug.md").write_text("stale")
        (out / "notes.md").write_text("keep me")
        first = art_prompts.write_pack(out)
        second = art_prompts.write_pack(tmp_path / "b")
        assert [p.name for p in first] == [p.name for p in second]
        for a, b in zip(first, second):
            assert a.read_bytes() == b.read_bytes()
        assert not (out / "sprite-oldslug.md").exists()
        assert (out / "notes.md").exists()
        pack = json.loads((out / "pack.json").read_text())
        assert pack["frame_size"] == FRAME
        # The markdown and the JSON are one rendering.
        doc = (out / "sprite-jean.md").read_text()
        assert pack["sprites"][0]["prompt"] in doc


def si_pixels(image):
    data = image.convert("RGBA").tobytes()
    return [tuple(data[i:i + 4]) for i in range(0, len(data), 4)]


def _fake_sheet(rows, cols, cell=40, gap=2, heights=None):
    """A delivered-looking sheet: magenta background, one coloured blob per
    cell. ``heights`` (per column) varies blob height so per-frame scale can
    be checked."""
    w = cols * cell + (cols + 1) * gap
    h = rows * cell + (rows + 1) * gap
    img = Image.new("RGB", (w, h), art_prompts.CHROMA_RGB)
    draw = ImageDraw.Draw(img)
    for r in range(rows):
        for c in range(cols):
            x0 = gap + c * (cell + gap)
            y0 = gap + r * (cell + gap)
            top = cell - (heights[c] if heights else cell - 4)
            draw.rectangle([x0 + 6, y0 + top, x0 + cell - 6, y0 + cell - 2], fill=(10 * (r + 1), 20 * (c + 1), 200))
    return img


def _model_sheet(rows, cols, cell=68, border=2, margin=14, chroma=(229, 64, 244)):
    """What image models actually deliver: a drifted magenta, dark magenta
    gridlines between cells, a wide outer margin, one blob per cell."""
    w = margin * 2 + cols * cell
    h = margin * 2 + rows * cell
    img = Image.new("RGB", (w, h), chroma)
    draw = ImageDraw.Draw(img)
    for r in range(rows):
        for c in range(cols):
            x0, y0 = margin + c * cell, margin + r * cell
            draw.rectangle([x0, y0, x0 + cell, y0 + cell], outline=(97, 0, 90), width=border)
            draw.rectangle([x0 + 20, y0 + 16, x0 + cell - 20, y0 + cell - 8], fill=(40, 30, 20))
            draw.point((x0 + 30, y0 + 24), fill=(255, 190, 40))  # amber eye
    return img


class TestIntake:
    def test_hue_key_takes_drifted_magenta_and_gridlines_but_not_the_sprite(self):
        img = Image.new("RGB", (7, 1), art_prompts.CHROMA_RGB)
        img.putpixel((1, 0), (229, 64, 244))  # JPEG-drifted background
        img.putpixel((2, 0), (97, 0, 90))  # dark magenta gridline
        img.putpixel((3, 0), (194, 69, 199))  # ringing beside the line
        img.putpixel((4, 0), (40, 30, 20))  # bat fur
        img.putpixel((5, 0), (120, 80, 140))  # dusky purple: a sprite colour
        img.putpixel((6, 0), (140, 0, 255))  # violet, off-hue
        alpha = [px[3] for px in si_pixels(sprite_intake.key_out_background(img))]
        assert alpha == [0, 0, 0, 0, 255, 255, 255]

    def test_despill_keys_the_halo_only_next_to_background(self):
        halo = (150, 90, 150)  # dull magenta: too unsaturated for the main key
        img = Image.new("RGB", (9, 1), (40, 30, 20))
        img.putpixel((0, 0), art_prompts.CHROMA_RGB)
        img.putpixel((1, 0), halo)  # 1 px from background: spill
        img.putpixel((2, 0), halo)  # 2 px: still spill
        img.putpixel((3, 0), halo)  # 3 px: the sprite's own purple
        img.putpixel((7, 0), halo)  # interior: kept
        alpha = [px[3] for px in si_pixels(sprite_intake.key_out_background(img))]
        assert alpha == [0, 0, 0, 255, 255, 255, 255, 255, 255]

    def test_find_cells_locates_the_grid_through_margins_and_gridlines(self):
        keyed = sprite_intake.key_out_background(_model_sheet(ROWS, 5))
        cells = sprite_intake.find_cells(keyed)
        assert (len(cells), len(cells[0])) == (ROWS, 5)
        sizes = {cell.size for row in cells for cell in row}
        assert len(sizes) == 1  # one width, one height, for every cell
        for row in cells:
            for cell in row:
                assert cell.getbbox() is not None
        assert sprite_intake.find_cells(Image.new("RGBA", (8, 8), (0, 0, 0, 0))) == []

    def test_content_runs_merge_near_gaps_and_drop_specks(self):
        # 1-px internal gap merges; a lone 40-alpha spike (gridline ringing)
        # is a speck; a 12-px gap is a real cell boundary.
        profile = [0] * 3 + [200] * 20 + [0] + [200] * 20 + [0] * 12 + [40] + [0] * 5 + [200] * 20
        assert sprite_intake._content_runs(profile) == [(3, 43), (62, 81)]
        assert sprite_intake._content_runs([0, 0, 0]) == []

    def test_auto_intake_resamples_wrong_frame_count_and_accepts_jpeg(self, tmp_path, capsys):
        sheet = tmp_path / "cavebat__walk.jpg"
        _model_sheet(ROWS, 5).save(sheet, quality=90)  # spec wants 6
        out = sprite_intake.intake_sheet(sheet, sprites_dir=tmp_path / "s", manifest_path=tmp_path / "m.json")
        strip = Image.open(out)
        assert strip.size == (art_prompts.CLIPS["walk"] * FRAME, ROWS * FRAME)
        assert "5 frames per row, expected 6" in capsys.readouterr().err
        data = json.loads((tmp_path / "m.json").read_text())
        assert data["sprites"]["cavebat"]["clips"]["walk"]["frames"] == art_prompts.CLIPS["walk"]
        assert sprite_intake.resample_columns([[1, 2, 3, 4, 5]], 6) == [[1, 2, 3, 3, 4, 5]]
        assert sprite_intake.resample_columns([[1, 2, 3, 4, 5]], 4) == [[1, 2, 4, 5]]
        assert sprite_intake.resample_columns([[1, 2]], 1) == [[1]]

    def test_auto_intake_rejects_wrong_row_count_and_empty_sheets(self, tmp_path):
        sheet = tmp_path / "cavebat__hurt.png"
        _model_sheet(2, 3).save(sheet)
        with pytest.raises(ValueError, match="found 2 facing rows, expected 3"):
            sprite_intake.intake_sheet(sheet, sprites_dir=tmp_path / "s", manifest_path=tmp_path / "m.json")
        # the even split is the escape hatch
        sprite_intake.intake_sheet(sheet, rows=2, sprites_dir=tmp_path / "s", manifest_path=tmp_path / "m.json", grid="even")
        blank = tmp_path / "cavebat__idle.png"
        Image.new("RGB", (64, 64), art_prompts.CHROMA_RGB).save(blank)
        with pytest.raises(ValueError, match="no sprite content"):
            sprite_intake.intake_sheet(blank, sprites_dir=tmp_path / "s", manifest_path=tmp_path / "m.json")
        with pytest.raises(ValueError, match="grid must be"):
            sprite_intake.intake_sheet(sheet, sprites_dir=tmp_path / "s", manifest_path=tmp_path / "m.json", grid="magic")

    def test_key_out_background(self):
        img = Image.new("RGB", (4, 1), art_prompts.CHROMA_RGB)
        img.putpixel((0, 0), (250, 10, 245))  # near-magenta fringe
        img.putpixel((3, 0), (0, 0, 255))
        keyed = sprite_intake.key_out_background(img)
        assert keyed.getpixel((0, 0))[3] == 0
        assert keyed.getpixel((1, 0))[3] == 0
        assert keyed.getpixel((3, 0)) == (0, 0, 255, 255)

    def test_sheet_intake_writes_strip_and_manifest(self, tmp_path):
        sheet = tmp_path / "jean__idle.png"
        _fake_sheet(ROWS, IDLE_FRAMES).save(sheet)
        sprites = tmp_path / "sprites"
        manifest = sprites / "manifest.json"
        out = sprite_intake.intake_sheet(sheet, sprites_dir=sprites, manifest_path=manifest)
        assert out == (sprites / "jean" / "idle.png").resolve()
        strip = Image.open(out)
        assert strip.size == (IDLE_FRAMES * FRAME, ROWS * FRAME)
        assert strip.getpixel((0, 0))[3] == 0
        for f in range(IDLE_FRAMES):
            assert strip.crop((f * FRAME, 0, (f + 1) * FRAME, FRAME)).getbbox() is not None
        data = json.loads(manifest.read_text())
        assert data["sprites"]["jean"]["clips"]["idle"] == {"file": "sprites/jean/idle.png", "frames": IDLE_FRAMES, "rows": ROWS}
        assert data["facings"] == list(art_prompts.FACINGS)

    def test_sheet_normalisation_keeps_one_scale_and_baseline(self, tmp_path):
        """A short frame beside a tall one is not blown up to fill its cell:
        one crop box and one scale apply to the whole sheet."""
        sheet = tmp_path / "jean__hurt.png"
        _fake_sheet(ROWS, 3, heights=[36, 18, 36]).save(sheet)
        strip = Image.open(sprite_intake.intake_sheet(sheet, sprites_dir=tmp_path / "s", manifest_path=tmp_path / "m.json"))
        tall = strip.crop((0, 0, FRAME, FRAME)).getbbox()
        short = strip.crop((FRAME, 0, 2 * FRAME, FRAME)).getbbox()
        assert tall[3] == short[3] == FRAME  # feet on the same baseline
        assert (short[3] - short[1]) < (tall[3] - tall[1])  # scale preserved
        assert (tall[2] - tall[0]) == (short[2] - short[0])

    def test_sheet_name_validation_and_containment(self, tmp_path):
        with pytest.raises(ValueError):
            sprite_intake.parse_sheet_name(tmp_path / "jean.png")
        with pytest.raises(ValueError):
            sprite_intake.parse_sheet_name(tmp_path / "jean__dance.png")
        assert sprite_intake.parse_sheet_name(tmp_path / "slime__death.png") == ("slime", "death")
        for bad in ("..__idle.png", "jeen__idle.png", "__idle.png"):
            sheet = tmp_path / bad
            _fake_sheet(ROWS, IDLE_FRAMES).save(sheet)
            with pytest.raises(ValueError):
                sprite_intake.intake_sheet(sheet, sprites_dir=tmp_path / "s", manifest_path=tmp_path / "m.json")
        assert not (tmp_path / "idle.png").exists()
        # An explicit slug override still cannot escape the sprites directory.
        good = tmp_path / "jean__idle.png"
        _fake_sheet(ROWS, IDLE_FRAMES).save(good)
        with pytest.raises(ValueError):
            sprite_intake.intake_sheet(good, sprites_dir=tmp_path / "s", manifest_path=tmp_path / "m.json", slug="..")

    def test_grid_overrides_are_bounded(self, tmp_path):
        sheet = tmp_path / "jean__idle.png"
        _fake_sheet(ROWS, IDLE_FRAMES).save(sheet)
        with pytest.raises(ValueError):
            sprite_intake.intake_sheet(sheet, rows=-1, sprites_dir=tmp_path / "s", manifest_path=tmp_path / "m.json")
        with pytest.raises(ValueError):
            sprite_intake.intake_sheet(sheet, cols=999, sprites_dir=tmp_path / "s", manifest_path=tmp_path / "m.json")
        with pytest.raises(ValueError):
            sprite_intake.split_grid(Image.new("RGBA", (4, 4)), -1, 2)

    def test_oversized_delivery_is_refused(self, tmp_path):
        big = tmp_path / "jean__idle.png"
        Image.new("RGB", (sprite_intake.MAX_IMAGE_SIDE + 1, 8)).save(big)
        with pytest.raises(ValueError):
            sprite_intake.intake_sheet(big, sprites_dir=tmp_path / "s", manifest_path=tmp_path / "m.json")

    def test_tileset_intake_trims_the_gap(self, tmp_path):
        variants = list(art_prompts.REGIONS["verdette_caverns"]["variants"])
        sheet = tmp_path / "tileset__verdette_caverns.png"
        _fake_sheet(1, len(variants)).save(sheet)
        terrain_dir = tmp_path / "terrain"
        manifest = tmp_path / "manifest.json"
        written = sprite_intake.intake_tileset(sheet, terrain_dir=terrain_dir, manifest_path=manifest)
        assert [p.name for p in written] == [f"{v}.png" for v in variants]
        for p in written:
            tile = Image.open(p)
            assert tile.size == (art_prompts.TILE_SIZE, art_prompts.TILE_SIZE)
            # No transparent sliver from the keyed-out gap on any edge.
            assert tile.getbbox() == (0, 0, art_prompts.TILE_SIZE, art_prompts.TILE_SIZE)
        data = json.loads(manifest.read_text())
        assert data["terrain"]["verdette_caverns"]["tiles"]["shallow_water"] == "terrain/verdette_caverns/shallow_water.png"
        with pytest.raises(ValueError):
            sprite_intake.parse_tileset_name(tmp_path / "tileset__moon.png")

    def test_placeholders_report_and_never_clobber_real_art(self, tmp_path):
        sprites = tmp_path / "sprites"
        manifest = sprites / "manifest.json"
        written = sprite_intake.write_placeholders(["jean", "slime"], sprites_dir=sprites, manifest_path=manifest)
        assert len(written) == 2 * len(art_prompts.CLIPS)
        report = sprite_intake.validate(manifest_path=manifest, assets_dir=tmp_path)
        assert {r.split(" ")[0] for r in report["placeholder"]} == {"jean", "slime"}
        assert any(r.startswith("gorran (") for r in report["missing"])
        assert report["broken"] == []
        assert {r.split(" ")[0] for r in report["tilesets_missing"]} == set(art_prompts.REGIONS)
        # A real delivery replaces the placeholder flag for that clip only ...
        sheet = tmp_path / "jean__idle.png"
        _fake_sheet(ROWS, IDLE_FRAMES).save(sheet)
        real = sprite_intake.intake_sheet(sheet, sprites_dir=sprites, manifest_path=manifest)
        data = json.loads(manifest.read_text())
        assert "placeholder" not in data["sprites"]["jean"]["clips"]["idle"]
        assert data["sprites"]["jean"]["clips"]["walk"]["placeholder"] is True
        # ... and a later placeholder run leaves the delivered strip alone.
        before = real.read_bytes()
        sprite_intake.write_placeholders(["jean"], sprites_dir=sprites, manifest_path=manifest)
        assert real.read_bytes() == before
        assert "placeholder" not in json.loads(manifest.read_text())["sprites"]["jean"]["clips"]["idle"]
        sprite_intake.write_placeholders(["jean"], sprites_dir=sprites, manifest_path=manifest, force=True)
        assert json.loads(manifest.read_text())["sprites"]["jean"]["clips"]["idle"]["placeholder"] is True
        report = sprite_intake.validate(manifest_path=manifest, assets_dir=tmp_path)
        assert report["placeholder"][0].startswith("jean (")

    def test_validate_flags_wrong_size_and_missing_tiles(self, tmp_path):
        sprites = tmp_path / "sprites"
        manifest = sprites / "manifest.json"
        sprite_intake.write_placeholders(["jean"], sprites_dir=sprites, manifest_path=manifest)
        (sprites / "jean" / "walk.png").unlink()
        Image.new("RGBA", (8, 8)).save(sprites / "jean" / "cast.png")
        data = json.loads(manifest.read_text())
        data["terrain"] = {"grondia": {"tiles": {"dais": "terrain/grondia/dais.png"}}}
        manifest.write_text(json.dumps(data))
        report = sprite_intake.validate(manifest_path=manifest, assets_dir=tmp_path)
        assert "jean/walk" in report["broken"] and "jean/cast" in report["broken"]
        assert "grondia/dais" in report["broken"]
        assert any(r.startswith("grondia (") for r in report["tilesets_missing"])

    def test_manifest_load_tolerates_garbage_and_drops_unsafe_entries(self, tmp_path, capsys):
        bad = tmp_path / "manifest.json"
        bad.write_text("{not json")
        data = sprite_intake.load_manifest(bad)
        assert data["sprites"] == {} and data["frame_size"] == FRAME
        assert "not valid JSON" in capsys.readouterr().err
        bad.write_text(json.dumps({
            "sprites": {"jean": {"clips": {"idle": {"file": "sprites/../x.png"}, "walk": {"file": "sprites/jean/walk.png", "frames": "6"}}}},
            "terrain": {"grondia": {"tiles": {"dais": "terrain/grondia/dais.png", "bad": "/etc/passwd"}}},
        }))
        data = sprite_intake.load_manifest(bad)
        assert data["sprites"]["jean"]["clips"] == {"walk": {"file": "sprites/jean/walk.png", "frames": 6, "rows": ROWS}}
        assert data["terrain"]["grondia"]["tiles"] == {"dais": "terrain/grondia/dais.png"}
        assert "dropping manifest" in capsys.readouterr().err


def test_committed_manifest_matches_disk():
    """Whatever art is checked in must be reachable by the frontend and be
    the size the manifest claims."""
    report = sprite_intake.validate()
    assert report["broken"] == []
