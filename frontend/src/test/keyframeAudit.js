import { readdirSync, readFileSync } from 'node:fs'
import { dirname, join, relative, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

const SRC_DIR = join(dirname(fileURLToPath(import.meta.url)), '..')

/**
 * Static audit of CSS animation names against the `@keyframes` that declare
 * them.
 *
 * WHY THIS EXISTS
 * ---------------
 * `@keyframes` names are document-global no matter which element declares
 * them. A component that injects its own `<style>` block therefore does two
 * things at once: it competes with every other declaration of that name in the
 * app, and it makes the name available to every other component whether or not
 * that was intended. Both halves have bitten this codebase:
 *
 *   `blink`   TypewriterOutput declared it locally; it shadowed index.css's
 *             copy app-wide for as long as any typewriter was mid-line.
 *   `pulse`   NpcChatPanel declared it locally; it replaced the animation
 *             BattlefieldGrid's targeting reticle was using.
 *   `fadeIn`  Declared only inside ItemDetailDialog and USED by ActionsPanel,
 *             whose message therefore animated only while an item dialog
 *             happened to be open.
 *
 * Each was found by eye and fixed one at a time. This closes the class, and it
 * takes TWO checks to do it, because the two halves above fail in opposite
 * directions:
 *
 *   RESOLUTION  every animation name a source file uses must resolve to a
 *               `@keyframes` that either sits in a global stylesheet or is
 *               declared in that same file. Catches `fadeIn` and `spin` —
 *               names used where nothing declares them.
 *   SHADOWING   no name may be declared in more than one place once a global
 *               stylesheet declares it. Catches `blink` and `pulse`. A
 *               resolution check structurally CANNOT see these: a component
 *               that redeclares a global name still resolves it, which is
 *               exactly what makes the shadowing silent.
 *
 * jsdom does not load stylesheets, so no rendering test can check this. The
 * audit is deliberately static — it reads the files.
 */

const GLOBAL_STYLESHEET_DIR = 'styles'

/**
 * Whether a path is a stylesheet whose `@keyframes` this audit treats as
 * document-global: everything under `src/styles/*.css`.
 *
 * Deliberately broader than "actually global for the whole app life", and the
 * gap is worth knowing about. `index.css` is imported unconditionally by
 * `main.jsx`, so its keyframes really are always present; `landing.css` is
 * imported by `LandingPage.jsx` alone, so treating its names as global is a
 * PERMISSIVE approximation — a component animating with `lpBreathe` would not
 * be reported unresolved even on a route where the landing page never
 * mounted. Left broad on purpose: narrowing it means teaching this file the
 * bundle's import graph, and the failure it would prevent (a name resolving
 * only on one route) has never occurred, while the false positives from
 * getting the graph wrong would land on every run.
 */
function isGlobalStylesheet(path) {
    return path.startsWith(`${GLOBAL_STYLESHEET_DIR}/`) && path.endsWith('.css')
}

/**
 * Shorthand keywords that can appear in an `animation` value. Anything left
 * over after these, times, numbers and functions are removed is taken to be
 * the animation NAME. Erring toward "this is a name" is intentional: a keyword
 * missing from this list surfaces as a loud unresolved-name failure that takes
 * one line to fix, whereas erring the other way would silently reopen the hole
 * this audit exists to close.
 */
const ANIMATION_KEYWORDS = new Set([
    'normal', 'reverse', 'alternate', 'alternate-reverse',
    'none', 'forwards', 'backwards', 'both',
    'running', 'paused', 'infinite',
    'linear', 'ease', 'ease-in', 'ease-out', 'ease-in-out',
    'step-start', 'step-end',
    'initial', 'inherit', 'unset', 'revert', 'revert-layer',
])

/**
 * Characters after which a `/` begins a regex literal rather than a division.
 *
 * `)` and `]` are absent because after those a `/` divides. `<` and `>` are
 * absent for a JSX-specific reason: every closing tag in the file is a `<`
 * immediately followed by a `/`, and reading those as regex openers put the
 * lexer inside a "regex" for the rest of the line — long enough to swallow the
 * `{/*` that starts the next comment. No real code writes `a < /re/`.
 */
const REGEX_CAN_FOLLOW = new Set([...'(,=:[!&|?{};+-*%~^'])

/** Keywords after which a `/` also begins a regex (`return /x/.test(s)`). */
const REGEX_CAN_FOLLOW_KEYWORD =
    /\b(?:return|typeof|instanceof|in|of|case|do|else|yield|await|new|delete|void|throw)\s*$/

/**
 * Remove comments, so prose ABOUT a keyframe is never mistaken for one.
 *
 * Necessary rather than fastidious: several of the comments in this codebase
 * discuss `@keyframes blink` and `@keyframes pulse` by name, precisely because
 * those were the bugs. A naive scan reads them as declarations and concludes
 * those names are defined everywhere they are discussed.
 *
 * Walks the source tracking string, template, comment AND regex-literal state.
 * Regex literals are not an optional refinement: this module's own
 * `/\banimation(?:Name)?\s*:\s*(?:`([^`]*)`|'([^']*)'|"([^"]*)")/g` contains
 * an odd number of backticks, and a stripper that ignored regexes read the
 * first one as opening a template literal and treated the entire rest of the
 * file as string content — silently disabling comment removal from that point
 * on. The mistake failed loudly here only by luck.
 *
 * A `/` is read as starting a regex when the previous significant character is
 * one that cannot end an expression (the standard heuristic; `)` and `]` can,
 * so `(a + b) / 2` stays division).
 */
export function stripComments(source) {
    return lexJavaScript(source).code
}

/**
 * The comments themselves, which is the other half the same pass already knows.
 *
 * Exposed because prose about ANOTHER file is this repo's dominant defect
 * class, and `test/citations.js` can only hold a comment to its claim if it can
 * find the comments without also finding the code that quotes a filename in a
 * string. Sharing the lexer rather than writing a second one is not tidiness:
 * every trap in the docstring above (a regex literal holding a backtick, an
 * apostrophe in JSX text, a closing tag read as a regex opener) would have to
 * be rediscovered by the copy, and the copy fails SILENTLY — a mis-lexed file
 * yields fewer comments, and fewer comments is fewer claims to check.
 *
 * @returns {Array<{text: string, line: number, index: number}>} Comment bodies
 *   without their delimiters, in source order, each with the 1-based line its
 *   opener sits on.
 */
export function collectComments(source) {
    return lexJavaScript(source).comments
}

/**
 * One pass over JavaScript source, yielding the code with comments removed and
 * the comments themselves.
 *
 * The state machine is the one `stripComments` shipped with; the only addition
 * is that comment bodies are accumulated rather than discarded. See
 * `stripComments` for why each state exists.
 *
 * A `/` is read as starting a regex when the previous significant character is
 * one that cannot end an expression (the standard heuristic; `)` and `]` can,
 * so `(a + b) / 2` stays division).
 */
function lexJavaScript(source) {
    let out = ''
    const comments = []
    let i = 0
    let state = 'code'
    let quote = ''
    let inCharClass = false
    let lastSignificant = ''
    let commentStart = 0
    let commentText = ''
    const endComment = () => {
        comments.push({
            text: commentText,
            line: source.slice(0, commentStart).split('\n').length,
            index: commentStart,
        })
        commentText = ''
    }
    while (i < source.length) {
        const c = source[i]
        const next = source[i + 1]
        if (state === 'code') {
            if (c === '/' && next === '/') { state = 'line'; commentStart = i; i += 2; continue }
            if (c === '/' && next === '*') { state = 'block'; commentStart = i; i += 2; continue }
            if (c === '/' && (
                lastSignificant === ''
                || REGEX_CAN_FOLLOW.has(lastSignificant)
                || REGEX_CAN_FOLLOW_KEYWORD.test(out)
            )) {
                state = 'regex'
                inCharClass = false
                out += c
                i += 1
                continue
            }
            if (c === '"' || c === "'" || c === '`') { state = 'string'; quote = c }
            if (c.trim()) lastSignificant = c
            out += c
            i += 1
        } else if (state === 'string') {
            if (c === '\\') { out += c + (next ?? ''); i += 2; continue }
            // A ' or " string cannot contain a raw newline — that is the JS
            // grammar, not a shortcut. Enforcing it bounds the damage when an
            // apostrophe in JSX TEXT (`<p>Jean's sword</p>`) is misread as a
            // string opener: without this the mis-lex runs to end of file and
            // silently disables comment stripping from that point on, which is
            // how a comment quoting `@keyframes spin` came to register as a
            // declaration of it.
            if (c === '\n' && quote !== '`') { state = 'code'; lastSignificant = '' }
            else if (c === quote) { state = 'code'; lastSignificant = c }
            out += c
            i += 1
        } else if (state === 'regex') {
            if (c === '\\') { out += c + (next ?? ''); i += 2; continue }
            // Same safety valve as for quoted strings: a regex literal cannot
            // span a newline either, so a misidentified one can never run past
            // the end of its line and disable comment stripping wholesale.
            if (c === '\n') { state = 'code'; lastSignificant = '' }
            else if (c === '[') inCharClass = true
            else if (c === ']') inCharClass = false
            else if (c === '/' && !inCharClass) { state = 'code'; lastSignificant = c }
            out += c
            i += 1
        } else if (state === 'line') {
            if (c === '\n') { state = 'code'; out += c; endComment() }
            else commentText += c
            i += 1
        } else { // block
            if (c === '*' && next === '/') { state = 'code'; endComment(); i += 2; continue }
            // Preserve newlines so reported line numbers stay accurate.
            if (c === '\n') out += c
            commentText += c
            i += 1
        }
    }
    // A comment that runs to end of file is still a comment: closing it here
    // keeps a claim written on the last line of a file from being invisible.
    if (state === 'line' || state === 'block') endComment()
    return { code: out, comments }
}

/** Split on commas/whitespace that are not inside parentheses. */
function splitTopLevel(value, separators) {
    const parts = []
    let depth = 0
    let current = ''
    for (const c of value) {
        if (c === '(') depth += 1
        if (c === ')') depth -= 1
        if (depth === 0 && separators.includes(c)) {
            if (current.trim()) parts.push(current.trim())
            current = ''
        } else {
            current += c
        }
    }
    if (current.trim()) parts.push(current.trim())
    return parts
}

/**
 * Pull the animation NAMES out of one `animation` / `animation-name` value.
 *
 * Handles the comma-separated multi-animation form, functions containing their
 * own commas (`cubic-bezier(.36,.07,.19,.97)`), and `${...}` interpolation in
 * any position except the name itself — an interpolated NAME is unresolvable
 * by static reading and is reported separately rather than guessed at.
 */
export function animationNamesIn(value) {
    const names = []
    let interpolated = false
    for (const part of splitTopLevel(value, ',')) {
        for (const token of splitTopLevel(part, ' \t\n')) {
            if (token.includes('${')) { interpolated = true; continue }
            if (token.includes('(')) continue // cubic-bezier(...), steps(...)
            if (/^-?[\d.]+m?s$/i.test(token)) continue // duration or delay
            if (/^-?[\d.]+$/.test(token)) continue // iteration count
            if (ANIMATION_KEYWORDS.has(token.toLowerCase())) continue
            names.push(token)
        }
    }
    return { names, interpolated }
}

// The trailing `{` is load-bearing, not decoration: it is what separates a
// real declaration from prose NAMING one. Comment stripping is best-effort on
// JSX (whose text content is not JavaScript), and a false DECLARATION is the
// dangerous direction — it makes the audit permissive and silent, where a
// false usage merely fails loudly. Requiring the block closes that direction.
const DECLARATION_RE = /@keyframes\s+([A-Za-z_-][\w-]*)\s*\{/g
const CSS_USAGE_RE = /\banimation(?:-name)?\s*:\s*([^;}]+)/g
// CSS-in-JS: the value must be quoted, which is also what keeps a prose
// mention of `animation:` in a comment from registering as a usage.
const JS_USAGE_RE = /\banimation(?:Name)?\s*:\s*(?:`([^`]*)`|'([^']*)'|"([^"]*)")/g

function lineOf(source, index) {
    return source.slice(0, index).split('\n').length
}

/**
 * Every shipped `.css`, `.js` and `.jsx` file under `src`.
 *
 * Tests and test support are skipped because neither ships a stylesheet, and
 * both carry `animation` values that are not CSS at all: a combat beat's
 * `animation` field names a move TYPE (`'attack'`), and the fixtures in
 * `src/test/` are full of them.
 */
export function readSourceFiles(root = SRC_DIR) {
    const files = []
    const walk = (dir) => {
        for (const entry of readdirSync(dir, { withFileTypes: true })) {
            const full = join(dir, entry.name)
            if (entry.isDirectory()) {
                if (entry.name !== 'test') walk(full)
                continue
            }
            if (!/\.(css|jsx?)$/.test(entry.name)) continue
            if (/\.test\.jsx?$/.test(entry.name)) continue
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
 * Audit a set of `{path, content}` files.
 *
 * Taking the files as an argument rather than reading the disk itself is what
 * makes this falsifiable: the suite runs it over the real `src` AND over
 * hand-built inputs with a known-missing keyframe, so "the scan passes" is
 * evidence rather than an assumption.
 *
 * A name resolves if it is declared in a global stylesheet — as
 * `isGlobalStylesheet` defines that, deliberately permissively; see its
 * docstring — or in the same file that uses it.
 *
 * `shadowed` is the other half — see SHADOWING in the module header. It is
 * every name with more than one declaration where at least one of them is a
 * global stylesheet's, which is the shape `blink` and `pulse` had. Two
 * declarations in components alone are not listed here because the
 * `localOnly` case in the suite already rejects that shape.
 *
 * @returns {{unresolved: Array, interpolated: Array, shadowed: Array,
 *   declaredIn: Map<string, string[]>}}
 */
export function auditKeyframes(files) {
    const declaredIn = new Map()
    const globalNames = new Set()

    for (const { path, content } of files) {
        const clean = stripComments(content)
        const isGlobal = isGlobalStylesheet(path)
        DECLARATION_RE.lastIndex = 0
        let m
        while ((m = DECLARATION_RE.exec(clean))) {
            const name = m[1]
            if (!declaredIn.has(name)) declaredIn.set(name, [])
            declaredIn.get(name).push(path)
            if (isGlobal) globalNames.add(name)
        }
    }

    // Every declaration is pushed, not every declaring FILE, so a stylesheet
    // that declares the same name twice is listed too — the second block
    // silently wins over the first, which is the same failure at smaller scale.
    const shadowed = [...declaredIn.entries()]
        .filter(([, paths]) => paths.length > 1 && paths.some(isGlobalStylesheet))
        .map(([name, paths]) => ({ name, paths }))

    const unresolved = []
    const interpolated = []

    for (const { path, content } of files) {
        const clean = stripComments(content)
        const isCss = path.endsWith('.css')
        const re = isCss ? CSS_USAGE_RE : JS_USAGE_RE
        re.lastIndex = 0
        let m
        while ((m = re.exec(clean))) {
            const value = isCss ? m[1] : (m[1] ?? m[2] ?? m[3])
            const line = lineOf(clean, m.index)
            const { names, interpolated: hasInterp } = animationNamesIn(value)
            if (hasInterp && names.length === 0) {
                interpolated.push({ path, line, value: value.trim() })
                continue
            }
            for (const name of names) {
                const sites = declaredIn.get(name) || []
                if (globalNames.has(name) || sites.includes(path)) continue
                unresolved.push({
                    path,
                    line,
                    name,
                    value: value.trim(),
                    declaredElsewhereIn: sites,
                })
            }
        }
    }

    return { unresolved, interpolated, shadowed, declaredIn }
}

/** One human-readable line per unresolved usage, for a failure message. */
export function describeUnresolved(unresolved) {
    return unresolved
        .map((u) => {
            const where = u.declaredElsewhereIn.length
                ? `declared ONLY in ${u.declaredElsewhereIn.join(', ')} — a component-local `
                  + '<style> block is not visible unless that component is mounted'
                : 'no @keyframes of that name exists in src (Tailwind supplies a few, '
                  + 'but only via its animate-* utility classes — use the class, not the name)'
            return `${u.path}:${u.line} uses "${u.name}" (${u.value}): ${where}`
        })
        .join('\n')
}

/** One human-readable line per shadowed name, for a failure message. */
export function describeShadowed(shadowed) {
    return shadowed
        .map((s) => `"${s.name}" is declared in ${s.paths.join(' AND ')} — `
            + 'keyframe names are document-global, so whichever declaration is '
            + 'in the document last wins for every other user of that name')
        .join('\n')
}
