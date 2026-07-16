import { readdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const PORTRAITS_DIR = join(dirname(fileURLToPath(import.meta.url)), '../../public/assets/portraits')

/**
 * Scans `public/assets/portraits/<character>/<expression>.png` on disk and
 * returns `{ [character]: [expression, ...] }`. Collection sheets
 * (`<name>_collection.png`) are reference art, not renderable expressions,
 * and are excluded. Kept in sync with the actual art on disk (rather than a
 * hand-maintained list) so newly added portraits are covered automatically.
 */
export function scanPortraitManifest() {
    const manifest = {}
    for (const entry of readdirSync(PORTRAITS_DIR, { withFileTypes: true })) {
        if (!entry.isDirectory()) continue
        const files = readdirSync(join(PORTRAITS_DIR, entry.name))
        manifest[entry.name] = files
            .filter((f) => f.endsWith('.png') && !f.endsWith('_collection.png'))
            .map((f) => f.replace(/\.png$/, ''))
            .sort()
    }
    return manifest
}

/** Flattens the manifest into `[character, expression]` pairs for `it.each`. */
export function portraitManifestPairs() {
    const manifest = scanPortraitManifest()
    return Object.keys(manifest)
        .sort()
        .flatMap((character) => manifest[character].map((expression) => [character, expression]))
}
