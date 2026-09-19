import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import {
    findNativeFormSubmissions,
    findUnguardedTableLookups,
    findWidthGatedTouchTargets,
    readSourceFiles,
} from './sourceAudit'

/**
 * Two static audits, each held to the same two obligations.
 *
 * The obligations matter more than the checks. A scan that reports nothing is
 * indistinguishable from a scan that looked at nothing, and every guard this
 * repo has had to rewrite failed in exactly that way — asserting one direction
 * only, or over a corpus that had quietly emptied. So each audit is asserted
 * BOTH ways:
 *
 *   it fires    on hand-built sources carrying the defect, with the count and
 *               the location pinned, so a scan that stopped working is loud.
 *   it is quiet on hand-built sources carrying the FIX, so the audit cannot be
 *               satisfied by reporting everything.
 *
 * and the real-corpus run additionally asserts that the corpus was read: the
 * file count, the number of table bindings actually resolved, and — the one
 * that has already caught something — that nothing failed to PARSE. A file the
 * parser rejects is skipped silently, so a syntax error would otherwise turn
 * every finding in that file into a pass.
 */

const FILES = readSourceFiles()

const source = (path, content) => ({ path, content })

describe('lookup tables are read prototype-safely', () => {
    it('reads a real corpus', () => {
        const { tableCount, unparsed } = findUnguardedTableLookups(FILES)
        expect(FILES.length).toBeGreaterThan(100)
        // Table bindings actually RESOLVED — the population the audit can hold
        // an opinion about. If a refactor broke the resolution, this drops and
        // the "no findings" assertion below stops meaning anything.
        expect(tableCount).toBeGreaterThan(50)
        expect(unparsed, unparsed.join('\n')).toEqual([])
    })

    it('reports a module-local table read with `||`', () => {
        const { findings } = findUnguardedTableLookups([
            source('utils/emotions.js', [
                'const TONE = { direct: "neutral" }',
                'export const pick = (tone) => TONE[tone] || "neutral"',
            ].join('\n')),
        ])
        expect(findings).toEqual([
            { where: 'utils/emotions.js', line: 2, receiver: 'TONE' },
        ])
    })

    it('reports `??` as well as `||`', () => {
        // `??` is not a fix for this: an inherited function is neither null nor
        // undefined, so the fallback is defeated just the same.
        const { findings } = findUnguardedTableLookups([
            source('utils/rank.js', [
                'const RANK = { common: 0 }',
                'export const of = (r) => RANK[r] ?? -1',
            ].join('\n')),
        ])
        expect(findings).toHaveLength(1)
    })

    it('follows a table imported by name from another module', () => {
        // The cross-module half is the part most likely to be quietly dead —
        // it involves path resolution, and a resolver that never resolves
        // anything reports nothing and looks exactly like a clean codebase.
        const { findings } = findUnguardedTableLookups([
            source('styles/theme.js', 'export const colors = { border: { main: "#fff" } }'),
            source('components/Panel.jsx', [
                "import { colors } from '../styles/theme'",
                'export const edge = (v) => colors.border[v] || colors.border.main',
            ].join('\n')),
        ])
        expect(findings).toEqual([
            { where: 'components/Panel.jsx', line: 2, receiver: 'colors.border' },
        ])
    })

    it('accepts an `Object.hasOwn` guard', () => {
        const { findings } = findUnguardedTableLookups([
            source('utils/configs.js', [
                'const CONFIGS = { pulse: 1 }',
                'export const get = (t) => Object.hasOwn(CONFIGS, t) ? CONFIGS[t] : CONFIGS.pulse',
            ].join('\n')),
        ])
        expect(findings).toEqual([])
    })

    it('accepts the shared helper', () => {
        const { findings } = findUnguardedTableLookups([
            source('utils/log.js', [
                "import { lookupOr } from './lookup'",
                'const COLORS = { damage: "red" }',
                'export const of = (t) => lookupOr(COLORS, t, "white")',
            ].join('\n')),
        ])
        expect(findings).toEqual([])
    })

    it('leaves an array index alone', () => {
        // The whole reason this is a parser and not a grep: `list[i] || 0` and
        // `TABLE[k] || 0` are the same characters.
        const { findings } = findUnguardedTableLookups([
            source('utils/pick.js', [
                'const list = [1, 2, 3]',
                'export const at = (i) => list[i] || 0',
            ].join('\n')),
        ])
        expect(findings).toEqual([])
    })

    it('finds no unguarded table lookup in the source', () => {
        const { findings } = findUnguardedTableLookups(FILES)
        const shown = findings.map((f) => `${f.where}:${f.line} ${f.receiver}[…] || …`)
        expect(findings, [
            'A lookup table is read with a dynamic key and an `||`/`??` fallback.',
            'A key of `constructor`, `toString`, `valueOf` or `__proto__` finds an',
            'INHERITED function there, which is truthy, so the fallback never runs.',
            'Use `lookupOr` from utils/lookup.js.',
            '',
            ...shown,
        ].join('\n')).toEqual([])
    })
})

describe('forms do not submit themselves natively', () => {
    it('reads a real corpus', () => {
        const { formCount, unparsed } = findNativeFormSubmissions(FILES)
        // Without this the suite passed while the only file containing a
        // `<form>` failed to parse: zero forms scanned, zero findings, green.
        expect(formCount).toBeGreaterThan(0)
        expect(unparsed, unparsed.join('\n')).toEqual([])
    })

    it('reports a native action and method', () => {
        const { findings } = findNativeFormSubmissions([
            source('pages/Login.jsx', [
                'export const F = () => (',
                '  <form action="/login" method="POST" onSubmit={s}>',
                '    <input name="password" type="password" />',
                '  </form>',
                ')',
            ].join('\n')),
        ])
        expect(findings.map((f) => f.attribute).sort()).toEqual(['action', 'method'])
    })

    it('leaves a handler-only form alone', () => {
        const { findings } = findNativeFormSubmissions([
            source('pages/Login.jsx', [
                'export const F = () => (',
                '  <form id="login-form" onSubmit={s}>',
                '    <input name="password" type="password" />',
                '  </form>',
                ')',
            ].join('\n')),
        ])
        expect(findings).toEqual([])
    })

    it('finds no natively-submitting form in the source', () => {
        const { findings } = findNativeFormSubmissions(FILES)
        const shown = findings.map((f) => `${f.where}:${f.line} ${f.attribute}`)
        expect(findings, [
            'A <form> carries a native `action`/`method` while submitting via JS.',
            'That is what the browser does when the handler does not run, so it is',
            'the credential path nobody tests. Drop the attributes.',
            '',
            ...shown,
        ].join('\n')).toEqual([])
    })
})

describe('the 44px touch-target floor is decided by the pointer, not the width (issue #639)', () => {
    const FIXTURES = join(dirname(fileURLToPath(import.meta.url)), 'fixtures', 'touchTargets')

    it('reads a real corpus', () => {
        const { readCount, unparsed } = findWidthGatedTouchTargets(FILES)
        // The population the audit can hold an opinion about. A refactor that
        // renamed the token would drop this to zero and turn "no findings"
        // into a statement about nothing.
        expect(readCount).toBeGreaterThan(20)
        expect(unparsed, unparsed.join('\n')).toEqual([])
    })

    it('reports a floor gated on a width hook, over a real directory', () => {
        // Run through readSourceFiles, not hand-built strings: a scanner that
        // stopped WALKING reports nothing and looks exactly like clean code.
        const files = readSourceFiles(FIXTURES)
        expect(files.map((f) => f.path).sort()).toEqual(['PointerAware.jsx', 'WidthGated.jsx'])

        const { findings, readCount } = findWidthGatedTouchTargets(files)
        expect(readCount).toBe(3)
        expect(findings).toEqual([
            { where: 'WidthGated.jsx', line: 12, guard: 'isMobile', reason: 'width-gated' },
        ])
    })

    it('stays quiet on a pointer-aware gate in a file that also uses useMobile', () => {
        // The reason the guard must be the INNERMOST conditional and not the
        // file: BaseDialog legitimately holds both hooks, so any file-level
        // check passes the moment either name appears anywhere in it.
        const { findings } = findWidthGatedTouchTargets([
            source('components/Panel.jsx', [
                "import { useMobile } from '../hooks/useMobile'",
                "import { useLargeTouchTargets } from '../hooks/useLargeTouchTargets'",
                'export const P = () => {',
                '  const isMobile = useMobile()',
                '  const needsLargeTargets = useLargeTouchTargets()',
                '  const layout = isMobile ? "column" : "row"',
                '  return <button style={{ flexDirection: layout, minHeight: needsLargeTargets ? accessibility.touchTarget : "18px" }} />',
                '}',
            ].join('\n')),
        ])
        expect(findings).toEqual([])
    })

    it('credits `useMobile() || useCoarsePointer()`, which is what || means here', () => {
        // Battlefield.jsx's shape (#564). The floor applies when EITHER is
        // true, so the width half does not make it width-gated.
        const { findings } = findWidthGatedTouchTargets([
            source('components/Battlefield.jsx', [
                'const needsLargeTargets = useMobile() || useCoarsePointer()',
                'export const T = () => <b style={{ minHeight: needsLargeTargets ? accessibility.touchTarget : "26px" }} />',
            ].join('\n')),
        ])
        expect(findings).toEqual([])
    })

    it('does NOT credit `useMobile() && useCoarsePointer()` — && is not ||', () => {
        // The trap in the audit itself: `&&` narrows to devices that are BOTH
        // narrow AND coarse, which is the phone — a landscape tablet fails the
        // width half and loses the floor. Treating the two operators alike
        // would wave through the exact defect the audit is for.
        const { findings } = findWidthGatedTouchTargets([
            source('components/Panel.jsx', [
                'const gate = useMobile() && useCoarsePointer()',
                'export const T = () => <b style={{ minHeight: gate ? accessibility.touchTarget : "26px" }} />',
            ].join('\n')),
        ])
        expect(findings).toEqual([
            { where: 'components/Panel.jsx', line: 2, guard: 'gate', reason: 'width-gated' },
        ])
    })

    it('reads `x && touchTarget` as a gate and `x || touchTarget` as a fallback', () => {
        // `isMobile && token` withholds the floor from everyone else. `x ||
        // token` yields the token whenever x is falsy, so the token is the
        // DEFAULT and x cannot take it away — different shapes, and calling
        // them both gates would report the safe one.
        const gated = findWidthGatedTouchTargets([
            source('components/A.jsx', [
                'const isMobile = useMobile()',
                'export const T = () => <b style={{ minHeight: isMobile && accessibility.touchTarget }} />',
            ].join('\n')),
        ])
        expect(gated.findings).toHaveLength(1)

        // Same width-only identifier on the left, so the OPERATOR is the only
        // difference between this and the case above.
        const fallback = findWidthGatedTouchTargets([
            source('components/B.jsx', [
                'const isMobile = useMobile()',
                'export const T = () => <b style={{ minHeight: isMobile || accessibility.touchTarget }} />',
            ].join('\n')),
        ])
        expect(fallback.findings).toEqual([])
    })

    it('reports a device-named guard it cannot resolve at all', () => {
        // ShopDialog's QtyPicker took `isMobile` as a PROP threaded down from
        // GamePage. Nothing in the module can prove it is pointer-aware, and
        // "cannot prove" is the honest verdict — it was in fact wrong.
        const { findings } = findWidthGatedTouchTargets([
            source('components/ShopDialog.jsx', [
                'function QtyPicker({ isMobile }) {',
                '  const btnSize = isMobile ? accessibility.touchTarget : "26px"',
                '  return <button style={{ width: btnSize }} />',
                '}',
            ].join('\n')),
        ])
        expect(findings).toEqual([
            { where: 'components/ShopDialog.jsx', line: 2, guard: 'isMobile', reason: 'unprovable' },
        ])
    })

    it('leaves an unconditional floor alone', () => {
        const { findings, readCount } = findWidthGatedTouchTargets([
            source('components/GameButton.jsx', [
                'export const B = () => <button style={{ minHeight: accessibility.touchTarget }} />',
            ].join('\n')),
        ])
        expect(readCount).toBe(1)
        expect(findings).toEqual([])
    })

    it('leaves a guard on the component rather than the device alone', () => {
        // LeftPanel's HeaderButton: `square` is about the button's shape. The
        // audit has no opinion about it, and says so in its docstring.
        const { findings } = findWidthGatedTouchTargets([
            source('components/LeftPanel.jsx', [
                'function HeaderButton({ square = false }) {',
                '  return <button style={{ minWidth: square ? accessibility.touchTarget : undefined }} />',
                '}',
            ].join('\n')),
        ])
        expect(findings).toEqual([])
    })

    it('finds no width-gated touch target in the source', () => {
        const { findings } = findWidthGatedTouchTargets(FILES)
        const shown = findings.map((f) => `${f.where}:${f.line} guarded by [${f.guard}] — ${f.reason}`)
        expect(findings, [
            'A 44px touch-target floor is decided by a guard that is not pointer-aware.',
            '`useMobile` is `(max-width: 767px)`: a tablet in landscape is wider than',
            'that and is still being pointed at with a thumb (issue #639). Gate the',
            'floor on `useLargeTouchTargets()` instead, and keep `useMobile` for',
            'layout. A guard arriving as a prop cannot be proven pointer-aware —',
            'call the hook where the floor is decided.',
            '',
            ...shown,
        ].join('\n')).toEqual([])
    })
})
