import { readFileSync, existsSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, it, expect } from 'vitest'
import { SPRITE_CLIPS, DEFAULT_FACINGS, isSafeAssetPath } from '../utils/sprites'
import { normalizeManifest } from '../hooks/useSpriteManifest'

const ASSETS = join(dirname(fileURLToPath(import.meta.url)), '../../public/assets')
const MANIFEST = join(ASSETS, 'sprites/manifest.json')

// The committed manifest is what production fetches; every file it names must
// ship, and every clip name must be one the renderer knows. Python's
// tests/test_art_pipeline.py checks the same thing from the intake side.
describe('committed sprite manifest', () => {
  // The RAW file is what is checked: normalizeManifest drops what it does not
  // like, so validating its output would let a bad entry through silently.
  const raw = JSON.parse(readFileSync(MANIFEST, 'utf-8'))
  const manifest = normalizeManifest(raw)

  it('parses to the shape the renderer expects', () => {
    expect(manifest).not.toBeNull()
    expect(manifest.facings).toEqual([...DEFAULT_FACINGS])
    expect(Object.keys(raw.sprites).length).toBeGreaterThan(0)
    // The spec header pins the clip set the renderer knows, in order.
    expect(Object.keys(raw.clips)).toEqual([...SPRITE_CLIPS])
  })

  it('names only files that exist and clips the renderer knows', () => {
    for (const [slug, entry] of Object.entries(raw.sprites)) {
      expect(entry.clips.idle, `${slug} needs an idle clip`).toBeDefined()
      for (const [clip, info] of Object.entries(entry.clips)) {
        expect(SPRITE_CLIPS, `${slug}/${clip}`).toContain(clip)
        expect(isSafeAssetPath(info.file), info.file).toBe(true)
        expect(existsSync(join(ASSETS, info.file)), info.file).toBe(true)
        expect(info.frames, `${slug}/${clip} frames`).toBe(raw.clips[clip])
        expect(info.rows).toBe(DEFAULT_FACINGS.length)
      }
    }
    for (const [region, block] of Object.entries(raw.terrain)) {
      for (const [variant, file] of Object.entries(block.tiles)) {
        expect(isSafeAssetPath(file), `${region}/${variant}`).toBe(true)
        expect(existsSync(join(ASSETS, file)), file).toBe(true)
      }
    }
  })

  it('loses nothing in normalisation', () => {
    expect(Object.keys(manifest.sprites).sort()).toEqual(Object.keys(raw.sprites).sort())
    for (const slug of Object.keys(raw.sprites)) {
      expect(Object.keys(manifest.sprites[slug].clips).sort()).toEqual(Object.keys(raw.sprites[slug].clips).sort())
    }
    expect(Object.keys(manifest.terrain).sort()).toEqual(Object.keys(raw.terrain).sort())
  })
})
