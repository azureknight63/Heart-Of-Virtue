import { readFileSync, existsSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, it, expect } from 'vitest'
import { SPRITE_CLIPS } from '../utils/sprites'
import { normalizeManifest } from '../hooks/useSpriteManifest'

const ASSETS = join(dirname(fileURLToPath(import.meta.url)), '../../public/assets')
const MANIFEST = join(ASSETS, 'sprites/manifest.json')

// The committed manifest is what production fetches; every file it names must
// ship, and every clip name must be one the renderer knows. Python's
// tests/test_art_pipeline.py checks the same thing from the intake side.
describe('committed sprite manifest', () => {
  const manifest = normalizeManifest(JSON.parse(readFileSync(MANIFEST, 'utf-8')))

  it('parses to the shape the renderer expects', () => {
    expect(manifest).not.toBeNull()
    expect(manifest.facings).toEqual(['south', 'west', 'north'])
    expect(Object.keys(manifest.sprites).length).toBeGreaterThan(0)
  })

  it('names only files that exist and clips the renderer knows', () => {
    for (const [slug, entry] of Object.entries(manifest.sprites)) {
      expect(entry.clips.idle, `${slug} needs an idle clip`).toBeDefined()
      for (const [clip, info] of Object.entries(entry.clips)) {
        expect(SPRITE_CLIPS, `${slug}/${clip}`).toContain(clip)
        expect(existsSync(join(ASSETS, info.file)), info.file).toBe(true)
        expect(info.frames).toBeGreaterThan(0)
        expect(info.rows).toBe(3)
      }
    }
    for (const region of Object.values(manifest.terrain)) {
      for (const file of Object.values(region.tiles || {})) {
        expect(existsSync(join(ASSETS, file)), file).toBe(true)
      }
    }
  })
})
