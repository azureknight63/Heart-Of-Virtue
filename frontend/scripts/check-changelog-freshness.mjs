#!/usr/bin/env node
// Runs as the "prebuild" npm lifecycle script — npm invokes this automatically
// before `npm run build`, so a production build fails if the login screen's
// changelog panel hasn't been synced with the latest CHANGELOG.md entry.
import { readFileSync } from 'node:fs'
import { fileURLToPath, pathToFileURL } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(__dirname, '../..')
const changelogMdPath = path.join(repoRoot, 'CHANGELOG.md')
const changelogJsPath = path.resolve(__dirname, '../src/data/changelog.js')

const md = readFileSync(changelogMdPath, 'utf8')
const versionHeading = md.match(/^##\s*\[([\d.]+)\]/m)

if (!versionHeading) {
  console.warn('[changelog-check] No version heading found in CHANGELOG.md — skipping freshness check.')
  process.exit(0)
}

const latestMdVersion = versionHeading[1]
const { CHANGELOG } = await import(pathToFileURL(changelogJsPath))
const knownVersions = new Set(CHANGELOG.map((entry) => entry.version))

if (!knownVersions.has(latestMdVersion)) {
  console.error(`
[changelog-check] frontend/src/data/changelog.js is stale.

CHANGELOG.md's newest entry is v${latestMdVersion}, but it isn't reflected in
the login screen's changelog panel (frontend/src/data/changelog.js).

Before deploying:
  1. Open CHANGELOG.md and read the v${latestMdVersion} entry.
  2. Condense it into 2-4 short highlight bullets (match the tone/length of
     the existing entries in frontend/src/data/changelog.js).
  3. Prepend a new { version, date, highlights } object to the CHANGELOG
     array in frontend/src/data/changelog.js (newest entry first).
  4. Re-run the build.
`)
  process.exit(1)
}

console.log(`[changelog-check] frontend/src/data/changelog.js is up to date (v${latestMdVersion}).`)
