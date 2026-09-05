import { describe, it, expect } from 'vitest'
import {
    auditKeyframes,
    animationNamesIn,
    stripComments,
    describeUnresolved,
    describeShadowed,
    readSourceFiles,
} from '../test/keyframeAudit'

/**
 * Every animation name used in `src` must resolve to a `@keyframes` that is
 * actually reachable from where it is used, and no name a global stylesheet
 * owns may be declared a second time anywhere.
 *
 * This replaces four separate one-at-a-time fixes, and it takes both halves to
 * replace all four. Keyframe names are document-global, so a component-local
 * `<style>` block fails in two opposite ways: it appears to define a name for
 * the whole app while actually only defining it while that component is
 * mounted (`fadeIn`, and a `spin` that only worked by accident of a Tailwind
 * class sitting on the same element — caught by `unresolved`), and it shadows
 * the global declaration of a name it does NOT own (`blink`, `pulse` — caught
 * by `shadowed`, and invisible to `unresolved`, because a redeclared name
 * still resolves).
 *
 * The scan is static because it has to be: jsdom loads no stylesheets, so
 * nothing rendered in this suite can tell "CSS supplied it" from "it was never
 * defined". The guard-the-guard block below runs the same function over
 * hand-built inputs with a known-missing keyframe, so a green result here is
 * evidence the scan works rather than evidence it found nothing to look at.
 */
describe('animation names resolve to a reachable @keyframes', () => {
    const files = readSourceFiles()
    const audit = auditKeyframes(files)

    it('scanned a meaningful number of files and found real declarations', () => {
        // Without this, deleting the walk or tightening the extension filter to
        // nothing would make every assertion below pass on an empty input.
        expect(files.length).toBeGreaterThan(50)
        expect(audit.declaredIn.size).toBeGreaterThan(20)
        // The stylesheet-owned names the earlier fixes moved out of components.
        for (const name of ['blink', 'pulse', 'pulse-opacity', 'npc-chat-spin', 'fade-in-scale']) {
            expect(audit.declaredIn.has(name), `${name} should be declared`).toBe(true)
        }
    })

    it('every animation name in src is declared globally or in its own file', () => {
        expect(audit.unresolved, describeUnresolved(audit.unresolved)).toEqual([])
    })

    it('no name a global stylesheet declares is declared a second time', () => {
        // The `blink`/`pulse` half. Both were declared in index.css AND
        // redeclared in a component `<style>` block, which made the component's
        // copy win app-wide for as long as it was mounted. The assertion above
        // cannot see this — a redeclared name still resolves everywhere — so
        // this is the check that actually closes those two bugs.
        expect(audit.shadowed, describeShadowed(audit.shadowed)).toEqual([])
    })

    it('no animation name is assembled from an interpolated variable', () => {
        // A name built at runtime cannot be checked by any static scan, so it
        // would be a permanent blind spot in the guard above. Interpolating the
        // DURATION is fine and common (HeroPanel does it); interpolating the
        // name is what this rejects.
        expect(audit.interpolated).toEqual([])
    })

    it('a name declared only in component <style> blocks is declared in exactly one of them', () => {
        // Visibility — that such a name is not used from anywhere else — is the
        // `unresolved` case above. What is left to check is that no two
        // components declare the same one, which `shadowed` deliberately does
        // not cover (it is scoped to names a global stylesheet owns).
        //
        // The remaining injectors (GameOverScreen, HeroPanel, ToastContext,
        // InteractPanel) are legitimate ONLY because each uses the name it
        // declares. This asserts the containment rather than trusting it: if a
        // fifth component starts using `slideIn` or `hero-heartbeat`, the
        // audit above goes red and this comment explains why.
        const localOnly = [...audit.declaredIn.entries()]
            .filter(([, paths]) => paths.every((p) => !p.startsWith('styles/')))
            .map(([name]) => name)

        expect(localOnly.length).toBeGreaterThan(0) // otherwise this is vacuous
        for (const name of localOnly) {
            expect(audit.declaredIn.get(name)).toHaveLength(1)
        }
    })
})

describe('the audit itself fails when it should', () => {
    // Guard-the-guard. A scan that cannot fail proves nothing, and every case
    // here is a shape that actually occurred in this repo.

    it('reports a name with no @keyframes anywhere', () => {
        const { unresolved } = auditKeyframes([
            { path: 'components/Ghost.jsx', content: "const s = { animation: 'ghost-drift 1s linear infinite' }" },
        ])

        expect(unresolved).toHaveLength(1)
        expect(unresolved[0]).toMatchObject({ name: 'ghost-drift', path: 'components/Ghost.jsx' })
        expect(describeUnresolved(unresolved)).toContain('no @keyframes of that name exists')
    })

    it('reports a name declared only in a DIFFERENT file’s local <style> block', () => {
        // Exactly the `fadeIn` bug: ActionsPanel used a name ItemDetailDialog
        // declared, so the animation ran only while that dialog was mounted.
        const { unresolved } = auditKeyframes([
            { path: 'components/Owner.jsx', content: '<style>{`@keyframes borrowed { from { opacity: 0 } }`}</style>' },
            { path: 'components/Borrower.jsx', content: "const s = { animation: 'borrowed 0.3s ease-out' }" },
        ])

        expect(unresolved).toHaveLength(1)
        expect(unresolved[0].name).toBe('borrowed')
        expect(unresolved[0].declaredElsewhereIn).toEqual(['components/Owner.jsx'])
        expect(describeUnresolved(unresolved)).toContain('not visible unless that component is mounted')
    })

    it('reports a component that REDECLARES a name a global stylesheet owns', () => {
        // Exactly the `blink`/`pulse` bug, and the case the resolution check
        // is blind to: `unresolved` is empty here, because the component's own
        // declaration resolves its own usage and index.css resolves everyone
        // else's. Only the declaration count says anything is wrong.
        const { unresolved, shadowed } = auditKeyframes([
            { path: 'styles/index.css', content: '@keyframes pulse { to { opacity: 1 } }' },
            {
                path: 'components/Shadower.jsx',
                content: "const s = { animation: 'pulse 1s' }\n"
                    + '<style>{`@keyframes pulse { to { opacity: 0.5 } }`}</style>',
            },
        ])

        expect(unresolved).toEqual([])
        expect(shadowed).toEqual([
            { name: 'pulse', paths: ['styles/index.css', 'components/Shadower.jsx'] },
        ])
        expect(describeShadowed(shadowed)).toContain('styles/index.css AND components/Shadower.jsx')
    })

    it('reports a stylesheet that declares the same name twice', () => {
        const { shadowed } = auditKeyframes([
            {
                path: 'styles/index.css',
                content: '@keyframes drift { to { opacity: 1 } }\n@keyframes drift { to { opacity: 0 } }',
            },
        ])

        expect(shadowed.map((s) => s.name)).toEqual(['drift'])
    })

    it('does not call two component-local declarations shadowing', () => {
        // Not this check's job: no global declaration is being overridden, and
        // the localOnly case in the suite above already rejects the shape. Two
        // overlapping rules that both fire would make either one unremovable.
        const { shadowed } = auditKeyframes([
            { path: 'components/A.jsx', content: "const s = { animation: 'own 1s' }\n<style>{`@keyframes own { to { opacity: 1 } }`}</style>" },
            { path: 'components/B.jsx', content: "const s = { animation: 'own 1s' }\n<style>{`@keyframes own { to { opacity: 0 } }`}</style>" },
        ])

        expect(shadowed).toEqual([])
    })

    it('accepts a name the same file declares, and one a global stylesheet declares', () => {
        const { unresolved } = auditKeyframes([
            { path: 'styles/index.css', content: '@keyframes shared { to { opacity: 1 } }' },
            { path: 'components/SelfContained.jsx', content: "const s = { animation: 'own 1s' }\n<style>{`@keyframes own { to { opacity: 1 } }`}</style>" },
            { path: 'components/UsesGlobal.jsx', content: "const s = { animation: 'shared 1s' }" },
        ])

        expect(unresolved).toEqual([])
    })

    it('reads the name out of a multi-animation value and flags only the missing one', () => {
        const { unresolved } = auditKeyframes([
            { path: 'styles/index.css', content: '@keyframes rise { to { opacity: 1 } }' },
            {
                path: 'components/Two.jsx',
                content: "const s = { animation: 'rise 0.6s ease-out both, glow 2.6s ease-in-out infinite 0.6s' }",
            },
        ])

        expect(unresolved.map((u) => u.name)).toEqual(['glow'])
    })

    it('does not count prose naming a keyframe as declaring one, even unstripped', () => {
        // Belt and braces for the case above. Comment stripping is best-effort
        // on JSX, so the declaration pattern also requires the opening brace of
        // a real block. A name mentioned in prose is not a declaration, and the
        // usage below must still be reported as unresolved.
        const { unresolved, declaredIn } = auditKeyframes([
            {
                path: 'components/Prose.jsx',
                content: [
                    "<p>Nobody's `@keyframes drift` is written anywhere in this repo:</p>",
                    "const s = { animation: 'drift 1s linear' }",
                ].join('\n'),
            },
        ])

        expect(declaredIn.has('drift')).toBe(false)
        expect(unresolved.map((u) => u.name)).toEqual(['drift'])
    })

    it('is not fooled by a comment that discusses a keyframe by name', () => {
        // Several comments in this codebase name `@keyframes blink` and
        // `@keyframes pulse` while explaining the bugs they caused. Counting
        // those as declarations would make every such name resolve everywhere.
        const { unresolved } = auditKeyframes([
            {
                path: 'components/Talky.jsx',
                content: [
                    '// The `@keyframes drift` that used to sit right here moved to index.css.',
                    '/* @keyframes drift { from { opacity: 0 } } */',
                    "const s = { animation: 'drift 1s linear' }",
                ].join('\n'),
            },
        ])

        expect(unresolved.map((u) => u.name)).toEqual(['drift'])
    })

    it('flags a name that is only reachable via a Tailwind utility class', () => {
        // `spin` has no `@keyframes` in this repo — Tailwind emits it, and only
        // because `animate-spin` appears in a scanned file. Restating the value
        // inline looked self-sufficient while silently depending on the class
        // beside it, so removing the "redundant" class would have killed it.
        const { unresolved } = auditKeyframes([
            {
                path: 'components/Spinner.jsx',
                content: '<div className="animate-spin" style={{ animation: \'spin 1s linear infinite\' }} />',
            },
        ])

        expect(unresolved.map((u) => u.name)).toEqual(['spin'])
        expect(describeUnresolved(unresolved)).toContain('use the class, not the name')
    })
})

describe('animation value parsing', () => {
    it('ignores durations, delays, counts, keywords and timing functions', () => {
        expect(animationNamesIn('screen-shake 0.42s cubic-bezier(.36,.07,.19,.97) both').names)
            .toEqual(['screen-shake'])
        expect(animationNamesIn('pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite').names)
            .toEqual(['pulse'])
        expect(animationNamesIn('fade 1s steps(4, end) 0.5s 3 alternate forwards').names)
            .toEqual(['fade'])
    })

    it('keeps a static name that sits beside an interpolated duration', () => {
        // HeroPanel's `hero-heartbeat ${animationDuration} infinite ease-in-out`
        // — checkable, because only the timing is dynamic.
        const { names, interpolated } = animationNamesIn('hero-heartbeat ${animationDuration} infinite ease-in-out')
        expect(names).toEqual(['hero-heartbeat'])
        expect(interpolated).toBe(true)
    })

    it('reports a value whose NAME is interpolated as uncheckable rather than guessing', () => {
        const { unresolved, interpolated } = auditKeyframes([
            { path: 'components/Dyn.jsx', content: 'const s = { animation: `${name} 1s linear infinite` }' },
        ])

        expect(unresolved).toEqual([])
        expect(interpolated).toEqual([{ path: 'components/Dyn.jsx', line: 1, value: '${name} 1s linear infinite' }])
    })
})

describe('comment stripping', () => {
    it('leaves strings, template literals and URLs intact', () => {
        expect(stripComments('const u = "https://example.com" // trailing'))
            .toBe('const u = "https://example.com" ')
        expect(stripComments('const t = `a /* not a comment */ b`'))
            .toBe('const t = `a /* not a comment */ b`')
    })

    it('preserves newlines so reported line numbers stay accurate', () => {
        const stripped = stripComments('/*\n\n*/\nconst a = 1')
        expect(stripped.split('\n')).toHaveLength(4)
    })

    it('is not derailed by a regex literal containing quote characters', () => {
        // The bug this audit shipped with, caught by the audit scanning its own
        // source: a stripper that ignores regex literals reads the lone backtick
        // in `/`([^`]*)`|'…'/` as opening a template literal and treats the
        // whole remainder of the file as string content — so every comment
        // after that point survives, and prose naming a keyframe reads as a
        // declaration. Silent, and it disables the guard rather than the file.
        const source = [
            "const RE = /`([^`]*)`|'([^']*)'/g",
            '// @keyframes ghost { to { opacity: 1 } }',
            'const done = 1',
        ].join('\n')

        const stripped = stripComments(source)

        expect(stripped).not.toContain('@keyframes')
        expect(stripped).toContain('const done = 1')
    })

    it('confines a mis-read apostrophe in JSX text to its own line', () => {
        // JSX text content is not JavaScript, so `Jean's` looks like a string
        // opener to any JS lexer. A ' string cannot span a newline, so the
        // mis-read ends at the line break instead of swallowing the rest of the
        // file — which is what let a comment quoting a keyframe name through.
        const source = [
            "<p>Jean's sword</p>",
            '// @keyframes ghost { to { opacity: 1 } }',
            'const done = 1',
        ].join('\n')

        expect(stripComments(source)).not.toContain('@keyframes')
    })

    it('does not read a JSX closing tag as the start of a regex literal', () => {
        // `</div>` is a `<` followed by a `/` — the classic regex-start
        // position for a JS lexer, and present on nearly every line of JSX in
        // this codebase. Misreading one put the lexer "inside a regex" long
        // enough to swallow the comment opener that followed it.
        const source = [
            '<div>text</div>',
            '{/* @keyframes ghost { to { opacity: 1 } } */}',
            'const done = 1',
        ].join('\n')

        const stripped = stripComments(source)

        expect(stripped).not.toContain('@keyframes')
        expect(stripped).toContain('const done = 1')
    })

    it('tells a regex literal from a division', () => {
        expect(stripComments('const half = (a + b) / 2 // trailing')).toBe('const half = (a + b) / 2 ')
        expect(stripComments("const ok = s.replace(/'/g, '') // trailing")).toBe("const ok = s.replace(/'/g, '') ")
        expect(stripComments("function f() { return /'/.test(s) } // trailing"))
            .toBe("function f() { return /'/.test(s) } ")
    })
})
