import { describe, expect, it } from 'vitest'

import {
    byCitingFile,
    cite,
    readCommentedFiles,
    scanCitations,
    unanchored,
    verify,
} from './citations'

/**
 * Cross-file comment claims, held to the files they name.
 *
 * Six review rounds in a row produced fresh false prose, each time inside the
 * edit that fixed its predecessor. `tests/_cite.py` closed the Python half, and
 * the guards built on it all work — but every one of them derives facts about
 * the file it SITS IN. None could hold a claim about a DIFFERENT file, so the
 * residue migrated to cross-file comments and kept going.
 *
 * Three checks, because the claim has three ways to be wrong, and only the
 * third is new:
 *
 *   EXISTENCE     the named file is gone. Global and free — every filename in
 *                 every comment under src/, nothing registered.
 *   ANCHOR        the file exists but no longer says what the comment claims.
 *                 Needs a registration: only a person can say which literal
 *                 carries the claim.
 *   COMPLETENESS  a claim was added and nobody registered it. THIS is the floor
 *                 every guard in this repo has been missing, and it is where
 *                 all six rounds actually failed.
 */

/**
 * The registered claims.
 *
 * A file PARTICIPATES once it has one entry here, and from then on every file
 * its comments mention must be registered — so the next cross-file claim
 * written into a participating file fails until somebody anchors it. Files with
 * no entry are not policed for completeness, which keeps registration voluntary
 * and cheap rather than a wall in front of the first comment.
 */
const CITATIONS = [
    cite({
        where: 'hooks/useNpcChat.js',
        about: 'utils/conversationSegment.js',
        anchor: 'population',
        claim: 'that module records a population of importers, not a rule',
    }),
    cite({
        where: 'hooks/useNpcChat.js',
        about: 'ai/llm_client.py',
        anchor: 'JEAN_TONES',
        claim: "the engine owns the tone vocabulary as JEAN_TONES",
    }),
    cite({
        where: 'hooks/useNpcChat.js',
        about: 'hooks/useNpcChat.test.js',
        anchor: 'JEAN_TONES',
        claim: 'the suite pins TONE_EMOTIONS against the Python source',
    }),
    cite({
        where: 'hooks/useNpcChat.js',
        about: 'utils/logger.js',
        anchor: '/api/logs/browser',
        claim: 'console output is mirrored to the browser-log endpoint',
    }),
    cite({
        // The comment used to say just `npc_chat.py`, and the guard refused
        // it: two files carry that basename (the route and a harness
        // scenario). Making the COMMENT unambiguous was the fix — a reference
        // too vague to check is a reference a reader cannot follow either.
        where: 'hooks/useNpcChat.js',
        about: 'src/api/routes/npc_chat.py',
        anchor: 'rate_limited_response',
        claim: 'the route answers 429 for a burst, which is not a failed turn',
    }),
    cite({
        where: 'hooks/useNpcChat.js',
        about: 'utils/conversationSegment.consumers.test.js',
        anchor: 'viaBarrel',
        claim: 'that suite derives the real population of importers',
    }),
    cite({
        where: 'hooks/useNpcChat.js',
        about: 'test/citations.js',
        anchor: 'COMPLETENESS',
        claim: 'this module is what catches the cross-file defect described',
    }),
    cite({
        where: 'hooks/useNpcChat.js',
        about: 'src/api/services/game_service.py',
        anchor: 'def npc_chat_end',
        claim: 'npc_chat_end is what releases the server-side conversation',
    }),
    cite({
        where: 'hooks/useNpcChat.js',
        about: 'src/npc/_chat_llm.py',
        anchor: 'def _base_payload',
        claim:
            'both endpoint bodies are built through one payload builder, which is'
            + ' where conversation_ended is set',
    }),
    cite({
        where: 'styles/keyframes.test.js',
        about: 'tests/test_security_headers.py',
        anchor: '_STYLE_INJECTORS',
        claim: 'the Python side pins the same injector population by reflection',
    }),
    cite({
        // Registering the citation above made this file participate, so its
        // other cross-file claim needs an anchor too — which is the
        // completeness floor doing its job rather than an unrelated chore.
        where: 'styles/keyframes.test.js',
        about: 'styles/index.css',
        anchor: '@keyframes blink',
        claim: 'the stylesheet owns the name a component used to redeclare',
    }),
    cite({
        where: 'hooks/useNpcChat.js',
        about: 'test/sourceAudit.js',
        anchor: 'mapEmotion(table, key)',
        claim: 'that audit names this call as one it structurally cannot see',
    }),

    // utils/apiError.js, registered because its central claim IS a claim about
    // other files: "no response carries a `message` that is worse copy than
    // its `error`". That sentence used to cite one directory while asserting
    // something about the whole API. Every minter it now names is anchored to
    // the literal that puts it in the population.
    cite({
        where: 'utils/apiError.js',
        about: 'src/api/rate_limiter.py',
        anchor: 'def rate_limited_response',
        claim: 'the token-in-`error` shape is emitted by this helper',
    }),
    cite({
        where: 'utils/apiError.js',
        about: 'src/api/routes/auth.py',
        anchor: '"error": "validation_error"',
        claim: 'auth pairs a machine token in `error` with prose in `message`',
    }),
    cite({
        where: 'utils/apiError.js',
        about: 'src/api/handlers/error_handler.py',
        anchor: '"message": "An unexpected error occurred"',
        claim: 'the global handlers mint both fields, outside any route',
    }),
    cite({
        where: 'utils/apiError.js',
        about: 'src/api/app.py',
        anchor: '"error": "payload_too_large"',
        claim: 'the payload guard mints both fields, outside any route',
    }),
    cite({
        where: 'utils/apiError.js',
        about: 'src/api/services/game_service.py',
        anchor: '"message": "Please resolve the current event before taking combat actions."',
        claim: 'the service layer mints both fields, returned through a route',
    }),
    cite({
        where: 'utils/apiError.js',
        about: 'hooks/useNpcChat.js',
        anchor: 'apiErrorDetail(err)',
        claim: 'every caller passes the result straight to console.error',
    }),
    cite({
        where: 'utils/apiError.js',
        about: 'utils/logger.js',
        anchor: '/api/logs/browser',
        claim: 'console output is mirrored to the browser-log endpoint',
    }),

    cite({
        where: 'utils/logger.js',
        about: 'main.jsx',
        anchor: 'if (import.meta.env.DEV) {',
        claim: 'the transport is gated to development, so the leak was never in production',
    }),
    cite({
        where: 'utils/logger.js',
        about: 'api/client.js',
        anchor: 'config.headers.Authorization = ',
        claim: 'the interceptor is what attaches the Bearer header that leaked',
    }),
    cite({
        where: 'utils/logger.js',
        about: 'utils/logger.test.js',
        anchor: 'scrubSecrets',
        claim: 'the suite drives the scrubber directly, not only through the transport',
    }),

    cite({
        where: 'utils/lookup.js',
        about: 'utils/animationConfigs.js',
        anchor: 'Object.hasOwn',
        claim: 'that module reached the same rule first and wrote it inline',
    }),
    cite({
        where: 'utils/lookup.js',
        about: 'test/sourceAudit.js',
        anchor: 'findUnguardedTableLookups',
        claim: 'that audit is what holds a table added tomorrow to this rule',
    }),

    cite({
        where: 'pages/LoginPage.jsx',
        about: 'App.jsx',
        anchor: 'path="/login"',
        claim: '/login is a client-side route, not a server endpoint',
    }),
    cite({
        where: 'pages/LoginPage.jsx',
        about: 'api/client.js',
        anchor: 'apiClient.interceptors.request.use',
        claim: 'submission goes through the shared client, not a native form post',
    }),
    cite({
        where: 'pages/LoginPage.jsx',
        about: 'utils/apiError.js',
        anchor: 'apiErrorMessage',
        claim: 'this page deliberately does NOT use that precedence',
    }),
    cite({
        where: 'pages/LoginPage.jsx',
        about: 'src/api/routes/auth.py',
        anchor: '"error": "conflict_error"',
        claim: 'auth failures put a machine token in `error`, never player copy',
    }),

    cite({
        where: 'utils/eventIds.js',
        about: 'src/events.py',
        anchor: 'class PassagewayTransitionEvent',
        claim:
            'the constant is the engine class name, sent in events_triggered[].type',
    }),
]

const SCAN = scanCitations(readCommentedFiles())

describe('cross-file comment claims', () => {
    it('scans a real body of files', () => {
        // Non-vacuity for all three checks below: an empty scan agrees with
        // every claim ever written.
        expect(SCAN.files ?? readCommentedFiles().length).toBeGreaterThan(100)
        expect(SCAN.mentions.length).toBeGreaterThan(50)
    })

    it('names no file that does not exist', () => {
        // EXISTENCE. Global, and it needs no registration, so it can never
        // fall behind the codebase the way a hand-kept list does.
        const broken = SCAN.dangling.map((d) => `${d.where} -> ${d.spelling}`)
        expect(broken, broken.join('\n')).toEqual([])
    })

    it('finds every registered anchor still in the file it names', () => {
        // ANCHOR. This is what a line number could never give you: a stale
        // `:123` still renders as a plausible reference.
        const broken = verify(CITATIONS)
        expect(broken, broken.join('\n')).toEqual([])
    })

    it('has every claim of a participating file registered', () => {
        // COMPLETENESS, in both directions. A new mention in a participating
        // file fails as unregistered; a registration whose comment was deleted
        // fails as stale.
        const registered = byCitingFile(CITATIONS)
        const mentioned = byCitingFile(SCAN.mentions)
        const problems = []
        for (const [where, claimed] of registered) {
            const found = mentioned.get(where) ?? new Set()
            for (const about of found) {
                if (!claimed.has(about)) {
                    problems.push(
                        `${where} mentions ${about} in a comment but registers no `
                        + `citation for it — add one to CITATIONS, with the literal `
                        + `that carries the claim`
                    )
                }
            }
            for (const about of claimed) {
                if (!found.has(about)) {
                    problems.push(
                        `${where} registers a citation about ${about}, but no comment `
                        + `there mentions it any more — delete the registration`
                    )
                }
            }
        }
        expect(problems, problems.join('\n')).toEqual([])
    })

    it('counts its own blind spot', () => {
        // An unanchored citation is acceptable; an uncounted one is how the
        // class this file exists to close got started. `unanchored` still
        // resolves the path, so a note cannot name a deleted file.
        expect(unanchored(CITATIONS)).toHaveLength(0)
    })
})
