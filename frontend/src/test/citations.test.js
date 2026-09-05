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
