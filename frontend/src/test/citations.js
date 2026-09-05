import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs'
import { dirname, join, relative, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

import { collectComments } from './keyframeAudit'

/**
 * Cross-file citations for JavaScript comments — `tests/_cite.py` pointed the
 * other way.
 *
 * WHY THIS EXISTS
 * ---------------
 * Six review rounds in a row produced fresh false prose, each time inside the
 * edit that fixed its predecessor. `tests/_cite.py` closed the Python half by
 * refusing to WRITE a fact: a citation names a file and an *anchor* — a literal
 * that file is claimed to contain — and the line numbers are computed at
 * failure time, so they cannot be stale.
 *
 * It did not close the class, and the reason was precise. Every guard built on
 * it derives facts about the file it SITS IN. None can derive a claim about a
 * DIFFERENT file, so the residue migrated to cross-file comments — a comment in
 * `hooks/useNpcChat.js` describing what `utils/conversationSegment.js`'s
 * docstring says, a comment in `utils/eventIds.js` naming a Python class in
 * `src/events.py`. Both of the last round's Majors were that shape, and both
 * were minted BY the fix for the round before.
 *
 * THREE CHECKS, BECAUSE THE CLAIM HAS THREE WAYS TO GO WRONG
 * ----------------------------------------------------------
 *   EXISTENCE    the file named is gone. Global and free: EVERY
 *                extension-bearing filename in EVERY comment under `src` must
 *                name at least one real file under the search roots. Nothing
 *                has to be registered for this to hold, so it can never fall
 *                behind the codebase.
 *   ANCHOR       the file exists but no longer says what the comment claims.
 *                This needs a registered citation, because only a human can say
 *                which literal carries the claim.
 *   COMPLETENESS a claim was added and nobody registered it. This is the floor
 *                every guard in this repo has been missing, and it is the one
 *                that matters: the previous six rounds each failed here, not at
 *                the other two. For a PARTICIPATING file — one carrying at
 *                least one registration — the set of files its comments mention
 *                must EQUAL the set its registrations name. Both directions: a
 *                new mention fails as unregistered, and a registration whose
 *                comment was deleted fails as stale.
 *
 * WHERE THE COMPLETENESS FLOOR STOPS, SAID OUT LOUD
 * -------------------------------------------------
 * A file with no registrations is not participating, so a FIRST cross-file
 * claim in a fresh file is caught by EXISTENCE but not by COMPLETENESS. That is
 * a deliberate trade — requiring every filename mention under `src` to be
 * registered would price the guard out of use — and it is stated here rather
 * than papered over, because a guard that overstates its reach is the defect
 * class this module exists to close. Registering the first claim in a file is
 * one line, and from that line on the file is held to every claim it makes.
 *
 * Usage:
 *
 *     cite({
 *         where: 'hooks/useNpcChat.js',
 *         about: 'utils/conversationSegment.js',
 *         anchor: 'nothing imports these two names from here directly',
 *         claim: 'the re-export comment quotes that docstring',
 *     })
 */

const SRC_DIR = join(dirname(fileURLToPath(import.meta.url)), '..')
const REPO_ROOT = join(SRC_DIR, '..', '..')

/**
 * Directories a citation may name a file in — the JS mirror of `_cite.py`'s
 * `_SEARCH_ROOTS`, and narrow for the same reason: a citation resolving into
 * `node_modules` is a citation of somebody else's code, which this repo has no
 * business pinning.
 *
 * `frontend` rather than `frontend/src` because comments legitimately cite the
 * build config beside it (`vite.config.js`); `public` joins the skip list in
 * exchange, so the walk does not index several hundred portrait PNGs to reach
 * it.
 */
export const SEARCH_ROOTS = ['frontend', 'src', 'ai', 'tools', 'tests']

const SKIP_DIRS = new Set([
    'node_modules', '__pycache__', '.git', 'dist', 'build', 'coverage', 'public',
])

/** Extensions that make a comment token unambiguously a FILENAME. */
const SOURCE_EXTENSIONS = ['js', 'jsx', 'mjs', 'py', 'css', 'json']

/**
 * A filename carrying one of {@link SOURCE_EXTENSIONS}, optionally qualified by
 * a path.
 *
 * The lookbehind rejects a candidate glued to a preceding `.`, `*`, `/`, `-` or
 * word character, which is what keeps a glob written in prose — a star, a dot,
 * then a test-file extension — from reading as a citation of a file whose name
 * is the bare word "test". `pages/GamePage.handlers.test.jsx`, whose stem
 * carries dots of its own, still matches whole.
 */
const FILENAME_PATTERN =
    '(?<![\\w.*/-])((?:[A-Za-z0-9_][\\w.-]*/)*[A-Za-z0-9_][\\w.-]*\\.(?:'
    + SOURCE_EXTENSIONS.join('|')
    + '))\\b'

/**
 * A path-qualified module reference with the extension left off —
 * `utils/conversationSegment`, `src/api/routes/npc_chat`.
 *
 * Requiring the slash is not cosmetic. Without it, `combat.turn_number` (a WIRE
 * FIELD, discussed constantly in these comments) offers `combat` as a stem, and
 * `src/api/serializers/combat.py` exists — so a guard that appended extensions
 * to bare words would report a wire field as a citation of a serializer.
 */
const MODULE_PATH_PATTERN = '(?<![\\w.*/-])([A-Za-z0-9_][\\w.-]*(?:/[\\w.-]+)+)'

export class CitationError extends Error {}

let indexCache = null

/** basename -> every path carrying it, built once per process. */
function fileIndex() {
    if (indexCache) return indexCache
    const found = new Map()
    for (const root of SEARCH_ROOTS) {
        const base = join(REPO_ROOT, root.split('/').join(sep))
        if (!existsSync(base)) continue
        const walk = (dir) => {
            for (const entry of readdirSync(dir, { withFileTypes: true })) {
                if (entry.isDirectory()) {
                    if (!SKIP_DIRS.has(entry.name)) walk(join(dir, entry.name))
                    continue
                }
                if (!found.has(entry.name)) found.set(entry.name, [])
                found.get(entry.name).push(join(dir, entry.name))
            }
        }
        walk(base)
    }
    indexCache = found
    return indexCache
}

/** Whether an absolute path sits inside one of {@link SEARCH_ROOTS}. */
function underASearchRoot(path) {
    const rel = relative(REPO_ROOT, path)
    if (rel.startsWith('..')) return false
    const parts = rel.split(sep)
    if (parts.some((part) => SKIP_DIRS.has(part))) return false
    return SEARCH_ROOTS.some((root) => {
        const wanted = root.split('/')
        return wanted.every((segment, i) => parts[i] === segment)
    })
}

/**
 * The one file `name` denotes, as an absolute path.
 *
 * Resolution mirrors `_cite.py`'s `Read.path`: a spelling that exists outright
 * wins — tried against the repo root and against `src`, since a comment in this
 * tree writes both `frontend/src/utils/portraits.js` and `utils/portraits.js` —
 * otherwise the basename index is consulted and a path-qualified name filters
 * it by suffix. `underASearchRoot` gates the direct branch; the index branch
 * inherits the same boundary structurally, because it is only ever built by
 * walking those roots.
 *
 * @throws {CitationError} when nothing matches, or when more than one does.
 */
export function resolveCitedFile(name) {
    const spelled = name.split('/').join(sep)
    for (const candidate of [join(REPO_ROOT, spelled), join(SRC_DIR, spelled)]) {
        if (existsSync(candidate) && statSync(candidate).isFile() && underASearchRoot(candidate)) {
            return candidate
        }
    }
    const base = name.split('/').pop()
    let candidates = fileIndex().get(base) || []
    if (name !== base) {
        candidates = candidates.filter((p) => p.endsWith(sep + spelled) || p.endsWith(spelled))
    }
    if (candidates.length === 1) return candidates[0]
    if (candidates.length === 0) {
        throw new CitationError(
            'names "' + name + '", which does not exist under ' + SEARCH_ROOTS.join(', ')
        )
    }
    const shown = candidates.map((p) => relative(REPO_ROOT, p).split(sep).join('/')).sort()
    throw new CitationError(
        'names "' + name + '", which is ambiguous between ' + shown.join(', ')
        + ' — cite a repo-relative path instead of a bare basename'
    )
}

/**
 * How a resolved path is spelled back to the reader: `src`-relative for the
 * frontend's own files, repo-relative for everything else. Computed, so the
 * two halves of the completeness comparison below cannot disagree about how to
 * name the same file.
 */
export function citedName(absolutePath) {
    const fromSrc = relative(SRC_DIR, absolutePath)
    if (!fromSrc.startsWith('..')) return fromSrc.split(sep).join('/')
    return relative(REPO_ROOT, absolutePath).split(sep).join('/')
}

/**
 * The name a MENTION is filed under.
 *
 * A mention is only a claim that the file exists, so an ambiguous basename is
 * tolerated here and filed under the spelling as written — `inventory.py` names
 * four real files, and prose loosely pointing at "the inventory serializer" is
 * not wrong, merely imprecise. A registered {@link cite} is a claim about
 * CONTENTS and gets no such latitude: {@link verify} resolves it strictly, so
 * the completeness comparison below is what forces a participating file to
 * disambiguate.
 *
 * @returns {?string} The filed name, or `null` when nothing of that name exists.
 */
function mentionName(name) {
    try {
        return citedName(resolveCitedFile(name))
    } catch {
        const base = name.split('/').pop()
        const candidates = (fileIndex().get(base) || []).filter(
            (p) => name === base || p.endsWith(sep + name.split('/').join(sep))
        )
        return candidates.length > 1 ? name : null
    }
}

/**
 * The same, for a reference that may have had its extension left off. Returns
 * `null` rather than throwing when nothing resolves: an extension-less token is
 * as likely to be a directory, or a fragment of prose, as a module.
 */
function resolveModuleReference(name) {
    for (const candidate of [name, ...SOURCE_EXTENSIONS.map((ext) => name + '.' + ext)]) {
        try {
            return resolveCitedFile(candidate)
        } catch {
            /* try the next extension */
        }
    }
    return null
}

/** Every `.js`/`.jsx`/`.mjs` file under `src`, shipped and test alike. */
export function readCommentedFiles(root = SRC_DIR) {
    const files = []
    const walk = (dir) => {
        for (const entry of readdirSync(dir, { withFileTypes: true })) {
            const full = join(dir, entry.name)
            if (entry.isDirectory()) {
                if (!SKIP_DIRS.has(entry.name)) walk(full)
                continue
            }
            if (!/\.(jsx?|mjs)$/.test(entry.name)) continue
            files.push({
                path: relative(root, full).split(sep).join('/'),
                content: readFileSync(full, 'utf8'),
            })
        }
    }
    walk(root)
    return files
}

/**
 * Every other-file reference made by a comment in `files`.
 *
 * Taking the files as an argument rather than reading the disk is what makes
 * this falsifiable: the suite runs it over the real `src` AND over hand-built
 * inputs with a known-dangling citation, so a green result is evidence the scan
 * works rather than evidence it looked at nothing.
 *
 * A reference to the citing file itself is dropped — a file describing its own
 * contents is not a cross-file claim, and nearly every module docstring names
 * its own module.
 *
 * @param {Array<{path: string, content: string}>} files
 * @returns {{mentions: Array, dangling: Array}} `mentions` are references
 *   naming something real, each `{where, about, spelling, line}`; `dangling`
 *   are extension-bearing names that name nothing at all, each
 *   `{where, spelling, line}`.
 */
export function scanCitations(files) {
    const mentions = []
    const dangling = []
    // Fresh per scan: a /g regex carries `lastIndex` between calls, and a
    // shared one silently skips the first match of every other comment.
    const filenameRe = new RegExp(FILENAME_PATTERN, 'g')
    const modulePathRe = new RegExp(MODULE_PATH_PATTERN, 'g')
    const wholeFilename = new RegExp('^' + FILENAME_PATTERN + '$')
    for (const { path, content } of files) {
        const seen = new Set()
        const record = (spelling, about, line) => {
            if (about === path || seen.has(about)) return
            seen.add(about)
            mentions.push({ where: path, about, spelling, line })
        }
        for (const comment of collectComments(content)) {
            for (const match of comment.text.matchAll(filenameRe)) {
                const about = mentionName(match[1])
                if (about) {
                    record(match[1], about, comment.line)
                } else {
                    dangling.push({
                        where: path,
                        spelling: match[1],
                        line: comment.line,
                    })
                }
            }
            for (const match of comment.text.matchAll(modulePathRe)) {
                if (wholeFilename.test(match[1])) continue
                const resolved = resolveModuleReference(match[1])
                if (resolved) record(match[1], citedName(resolved), comment.line)
            }
        }
    }
    return { mentions, dangling }
}

/**
 * One registered cross-file claim.
 *
 * `where` is the file whose comment makes the claim; `about` is the file the
 * claim is about; `anchor` is a literal that file must contain — normally the
 * sentence or identifier the comment repeats. `note` replaces the anchor where
 * the claim is about a file's SHAPE rather than any one literal; such an entry
 * still resolves `about`, so "unanchored" means "no literal to pin to", never
 * "nobody looked".
 */
export function cite({ where, about, anchor = null, note = null, claim = '' }) {
    if (!where || !about) {
        throw new CitationError('a citation needs both `where` and `about`')
    }
    if (!anchor && !note) {
        throw new CitationError(
            where + ' -> ' + about + ': give an anchor, or a note saying why there is none'
        )
    }
    return { where, about, anchor, note, claim }
}

/** 1-based lines of `about` containing `anchor`. Empty when it does not. */
export function anchorLines(citation) {
    const path = resolveCitedFile(citation.about)
    if (!citation.anchor) return []
    return readFileSync(path, 'utf8')
        .split('\n')
        .map((text, i) => (text.includes(citation.anchor) ? i + 1 : 0))
        .filter(Boolean)
}

/** `utils/conversationSegment.js:35 "nothing imports…"` — computed, never stored. */
export function describe(citation) {
    if (!citation.anchor) return citation.about + ' (' + citation.note + ')'
    let hits
    try {
        hits = anchorLines(citation)
    } catch (error) {
        return citation.about + ' UNRESOLVABLE: ' + error.message
    }
    if (hits.length === 0) {
        return citation.about + ' ANCHOR NOT FOUND: "' + citation.anchor + '"'
    }
    const shown = hits.slice(0, 4).join(',') + (hits.length > 4 ? '...' : '')
    return citation.about + ':' + shown + ' "' + citation.anchor + '"'
}

/**
 * Every registered citation whose file no longer resolves, or whose anchor is
 * no longer in it. This is the half a line number cannot give you: a stale
 * `:123` still renders as a plausible reference; a stale anchor is a failure.
 */
export function verify(citations) {
    const broken = []
    for (const citation of citations) {
        let path
        try {
            // Resolved for every citation, anchored or not: an unanchored entry
            // still claims the file exists, and that claim is the half a note
            // cannot otherwise be held to.
            path = resolveCitedFile(citation.about)
        } catch (error) {
            broken.push(citation.where + ' ' + error.message)
            continue
        }
        if (!citation.anchor) continue
        if (!readFileSync(path, 'utf8').includes(citation.anchor)) {
            broken.push(
                citation.where + ' claims ' + citation.about + ' contains "'
                + citation.anchor + '" — it does not. ' + citation.claim
            )
        }
    }
    return broken
}

/** Citations carrying a note instead of an anchor, so the blind spot is countable. */
export function unanchored(citations) {
    const loose = citations.filter((c) => !c.anchor)
    for (const citation of loose) resolveCitedFile(citation.about)
    return loose
}

/** Group `{where, about}` pairs into `where -> Set(about)`. */
export function byCitingFile(entries) {
    const grouped = new Map()
    for (const entry of entries) {
        if (!grouped.has(entry.where)) grouped.set(entry.where, new Set())
        grouped.get(entry.where).add(entry.about)
    }
    return grouped
}
