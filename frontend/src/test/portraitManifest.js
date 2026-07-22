import { readdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const PORTRAITS_DIR = join(dirname(fileURLToPath(import.meta.url)), '../../public/assets/portraits')

/**
 * Scans `public/assets/portraits/<character>/<expression>.png` on disk and
 * returns `{ [character]: [expression, ...] }`. Reference art is excluded:
 * collection sheets (`<name>_collection.png`), source exports
 * (`<name>_source.png`), and the bare source portrait named after the
 * character folder (`<name>.png`) are not renderable expressions. Kept in
 * sync with the actual art on disk (rather than a hand-maintained list) so
 * newly added portraits are covered automatically.
 */
export function scanPortraitManifest() {
    const manifest = {}
    for (const entry of readdirSync(PORTRAITS_DIR, { withFileTypes: true })) {
        if (!entry.isDirectory()) continue
        const slug = entry.name.replace(/[_-]+/g, '')
        const files = readdirSync(join(PORTRAITS_DIR, entry.name))
        manifest[entry.name] = files
            .filter((f) => {
                if (!f.endsWith('.png')) return false
                const base = f.replace(/\.png$/, '')
                if (base.endsWith('_collection') || base.endsWith('_source')) return false
                // Bare source portrait named after the character (any separator).
                if (base.replace(/[_-]+/g, '') === slug) return false
                return true
            })
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
