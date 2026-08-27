/**
 * Pure WAV-duration computation for the SFX manifest generator.
 *
 * Deliberately has no shebang and no CLI (`main()`) logic — it exists so this
 * logic can be imported directly by tests. Vite/Vitest's SSR module runner
 * wraps a transformed module's body in `new AsyncFunction(...)` to evaluate
 * it; a leading `#!/usr/bin/env node` shebang line is valid only at the very
 * start of a script/module source, so once it's wrapped inside a function
 * body it becomes a `SyntaxError: Invalid or unexpected token`. Importing
 * `generate-sfx-durations.mjs` (which keeps the shebang, for direct CLI
 * execution) from a test therefore fails; importing this shebang-free module
 * instead does not.
 *
 * See generate-sfx-durations.mjs for the CLI entry point that re-uses this.
 */
import { readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SOUNDS_DIR = join(__dirname, '..', 'public', 'assets', 'sounds', 'sfx');

/**
 * Exact duration (ms) of a PCM WAV from its header: data-chunk bytes / byteRate.
 * Walks the RIFF chunk list (chunks aren't always adjacent). Returns null for a
 * non-PCM / unparseable file so the caller can warn rather than emit a wrong number.
 */
export function wavDurationMs(buffer) {
  if (buffer.length < 12 || buffer.toString('ascii', 0, 4) !== 'RIFF') return null;
  if (buffer.toString('ascii', 8, 12) !== 'WAVE') return null;

  let byteRate = null;
  let dataSize = null;
  let offset = 12;
  while (offset + 8 <= buffer.length) {
    const id = buffer.toString('ascii', offset, offset + 4);
    const size = buffer.readUInt32LE(offset + 4);
    const body = offset + 8;
    if (id === 'fmt ' && body + 16 <= buffer.length) {
      byteRate = buffer.readUInt32LE(body + 8);
    } else if (id === 'data') {
      dataSize = size;
    }
    // Chunks are word-aligned: a padding byte follows an odd size.
    offset = body + size + (size % 2);
  }
  if (!byteRate || dataSize == null) return null;
  return Math.round((dataSize / byteRate) * 1000);
}

const cueOf = (filename) => filename.replace(/\.wav$/, '');

/** Map cue -> duration_ms for every WAV in the SFX directory. */
export function computeDurations(soundsDir = SOUNDS_DIR) {
  const durations = {};
  const warnings = [];
  for (const name of readdirSync(soundsDir)) {
    if (!name.endsWith('.wav')) continue;
    const ms = wavDurationMs(readFileSync(join(soundsDir, name)));
    if (ms == null) {
      warnings.push(name);
      continue;
    }
    durations[cueOf(name)] = ms;
  }
  return { durations, warnings };
}
