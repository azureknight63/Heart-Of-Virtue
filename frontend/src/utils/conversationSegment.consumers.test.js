import { describe, it, expect } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

/**
 * Who imports the conversation-cast vocabulary, and by which path.
 *
 * `npcCast` and `JEAN_ID` live in `utils/conversationSegment.js` and are
 * re-exported by `hooks/useNpcChat.js`, so there are two spellings of the same
 * import. That module's docstring used to state a rule about which spelling
 * belonged where, and named three consumers that do not exist — the stage, the
 * transcript and this module's own tests all import `DEFAULT_EMOTION` and
 * nothing else.
 *
 * A paragraph cannot notice that it has gone stale, so this derives the answer
 * instead. It asserts the population, not a preference: if a direct importer
 * appears, this fails and the docstring is what needs rewriting. That is the
 * point — the failure is a prompt to update the prose, not a rule against
 * importing.
 */

const SRC = path.join(path.dirname(fileURLToPath(import.meta.url)), '..')
const BARREL_SYMBOLS = ['npcCast', 'JEAN_ID']

function sourceFiles(dir) {
    const found = []
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        const full = path.join(dir, entry.name)
        if (entry.isDirectory()) {
            found.push(...sourceFiles(full))
        } else if (/\.(jsx?|tsx?)$/.test(entry.name)) {
            found.push(full)
        }
    }
    return found
}

/** Every `import { ... } from '<spec>'` statement in a file. */
function importsOf(body) {
    const out = []
    const re = /import\s*\{([^}]*)\}\s*from\s*['"]([^'"]+)['"]/g
    let match
    while ((match = re.exec(body)) !== null) {
        const names = match[1]
            .split(',')
            .map((raw) => raw.trim().split(/\s+as\s+/)[0].trim())
            .filter(Boolean)
        out.push({ names, from: match[2] })
    }
    return out
}

function consumers() {
    const direct = []
    const viaBarrel = []
    for (const file of sourceFiles(SRC)) {
        const rel = path.relative(SRC, file).replace(/\\/g, '/')
        if (rel.startsWith('utils/conversationSegment')) continue
        if (rel.startsWith('hooks/useNpcChat.js')) continue
        const body = fs.readFileSync(file, 'utf8')
        for (const statement of importsOf(body)) {
            const wanted = statement.names.filter((n) => BARREL_SYMBOLS.includes(n))
            if (wanted.length === 0) continue
            if (/conversationSegment$|conversationSegment\.js$/.test(statement.from)) {
                direct.push(rel)
            } else if (/useNpcChat$|useNpcChat\.js$/.test(statement.from)) {
                viaBarrel.push(rel)
            }
        }
    }
    return { direct: [...new Set(direct)], viaBarrel: [...new Set(viaBarrel)] }
}

describe('conversation-cast import paths', () => {
    it('finds source files at all', () => {
        // Non-vacuity. A scan that reads nothing agrees with every claim.
        expect(sourceFiles(SRC).length).toBeGreaterThan(50)
    })

    it('re-exports the symbols it claims to re-export', () => {
        const hook = fs.readFileSync(path.join(SRC, 'hooks/useNpcChat.js'), 'utf8')
        for (const symbol of BARREL_SYMBOLS) {
            expect(hook, `useNpcChat should re-export ${symbol}`).toContain(symbol)
        }
    })

    it('is imported only through the hook barrel today', () => {
        const { direct, viaBarrel } = consumers()
        // The documented rule had two halves. The LIVE CHAT half was true:
        // the panel and the hook's own suite do import through the barrel.
        // The "everything else" half was not: it named the stage, the
        // transcript and this module's tests as direct importers, and all
        // three import DEFAULT_EMOTION only. Nobody imports directly.
        //
        // Sorted so the assertion does not depend on filesystem walk order.
        expect(direct).toEqual([])
        expect([...viaBarrel].sort()).toEqual([
            'components/NpcChatPanel.jsx',
            'hooks/useNpcChat.test.js',
        ])
    })
})
