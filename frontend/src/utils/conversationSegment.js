/**
 * The conversation `segment` — the single beat shape every conversation
 * surface reads — plus the cast vocabulary those beats are addressed to.
 *
 * WHY THIS MODULE EXISTS
 * ----------------------
 * The shape is written on both sides of the wire and read by every surface
 * that renders a beat, and it used to be declared in none of them. Who those
 * are, without a count in front of them — a hand-written total is a second
 * thing to keep true, and nothing here derives one:
 *
 *   producers   this module's own `conversationSegment` factory (live LLM
 *               chat — hooks/useNpcChat.js calls it once per beat), and the
 *               authored-event path in src/api/services/game_service.py, which
 *               serialises `src/narration.py`'s beats onto the wire.
 *   consumers   components/ConversationStage.jsx (the live/authored stage),
 *               components/ConversationTranscript.jsx (recap strip + history),
 *               and `ReplyAnnouncer` in components/NpcChatPanel.jsx (the
 *               screen-reader channel for the live chat).
 *
 * With no declaration, a field could be produced by one side and silently
 * dropped by the other — which is exactly what happened to `thought` and
 * `reactions` in `TranscriptEntry`, and then again to the announcer, which
 * read three fields while claiming two renderers existed. The typedef below is
 * the contract, and the per-field notes say which renderer honours what, so
 * "the transcript ignores this" is a documented decision rather than an
 * unnoticed gap.
 *
 * The Python producer is not ours to edit from here; when a field is added
 * there it belongs in this typedef too.
 *
 * TWO IMPORT PATHS, ONE OF WHICH NOBODY USES
 * ------------------------------------------
 * `npcCast` and `JEAN_ID` are also re-exported by hooks/useNpcChat.js, so
 * there are two spellings of the same import. Only the barrel is in use: the
 * chat panel and the hook's own suite import through it, and nothing imports
 * these two names from here directly.
 *
 * That is a population, not a rule — `conversationSegment.consumers.test.js`
 * DERIVES it by scanning source. Add a direct importer and that test fails,
 * at which point this paragraph is what needs updating.
 *
 * @typedef {Object} ConversationSegment
 * @property {string}  text            The spoken (or narrated) line.
 *   Honoured by: stage (typed out a character at a time), transcript,
 *   announcer (announced whole, never per keystroke).
 * @property {?string} speaker         Cast id of whoever is talking. Absent on
 *   a narration beat, which both renderers centre as italic prose with no
 *   portrait.
 *   Honoured by: stage, transcript, announcer (which announces the NPC's
 *   beats only — Jean's words are the option the player just chose).
 * @property {string}  emotion         The speaker's expression for THIS beat,
 *   resolved against utils/portraits' EMOTIONS (anything else normalises to
 *   'neutral').
 *   Honoured by: stage, transcript.
 * @property {string}  flavor          Stage direction / aside rendered above
 *   the line.
 *   Honoured by: stage, transcript, announcer (behind an explicit lead-in —
 *   an aside is flavor, not speech, so it must not be heard as part of the
 *   spoken line).
 * @property {Object<string,string>} reactions  Listener id -> emotion, applied
 *   to cast members who are not speaking.
 *   Honoured by: stage only. The transcript renders one speaker per row and
 *   the announcer is a text channel, so a listener's reaction has nowhere to
 *   go in either — DELIBERATE, not an oversight.
 * @property {boolean} in_conversation Whether the cast is staged for this beat.
 *   A falsy value renders the beat as pre-conversation prose.
 *   Honoured by: stage only (the transcript is always a conversation record).
 * @property {boolean} [thought]       Renders the line as interior monologue.
 *   Honoured by: stage only (authored events; the live chat never sets it).
 * @property {Array}  [enter]          Cast-entrance ops `{id, name, side,
 *   emotion, transition}`.
 *   Honoured by: stage only — the transcript has no staging to change.
 * @property {Array}  [exit]           Cast-exit ops `{id, transition, span}`.
 *   Honoured by: stage only.
 */

/** The emotion a portrait wears when nothing more specific has been resolved. */
export const DEFAULT_EMOTION = 'neutral'

/**
 * Jean is always the player's side of a conversation — the cast roster, the
 * optimistic segment speaker, the NPC's reaction key and the announcer's
 * "skip Jean's own words" rule all need to agree on the same id, so it is
 * declared once beside the shape they all describe rather than repeated as a
 * string literal free to drift.
 */
export const JEAN_ID = 'Jean'

/**
 * Hard ceiling on a model-authored string, in characters.
 *
 * `src/npc/_chat_llm.py` clamps an NPC line to `MAX_NPC_SENTENCES` (3) — three
 * SENTENCES, with no character bound anywhere between the model and this
 * factory. The stage types the line out one character at a time, so an
 * unbounded line is an unbounded number of interval ticks and full
 * `ConversationStage` re-renders. The bound belongs here, in the module that
 * declares the contract, rather than in whichever renderer notices first.
 *
 * Generous on purpose: three sentences of period prose run to roughly 300
 * characters, so this only ever fires on output that already escaped the
 * server-side clamp.
 */
export const MAX_SEGMENT_CHARS = 600

/**
 * Coerce one model-authored field to a bounded string.
 *
 * @param {*} value - Whatever the producer supplied for this field.
 * @returns {string} The value as a string, never longer than
 *   {@link MAX_SEGMENT_CHARS}, with an ellipsis marking a truncation so a cut
 *   line does not read as a line the NPC simply stopped mid-word.
 */
function boundedText(value) {
    const text = value || ''
    if (text.length <= MAX_SEGMENT_CHARS) return text
    return `${text.slice(0, MAX_SEGMENT_CHARS - 1)}…`
}

/**
 * The cast a live NPC conversation is staged with: Jean on the left, the NPC
 * on the right. Lives beside {@link JEAN_ID} because it is the roster the
 * `speaker` and `reactions` keys of every segment are resolved against.
 *
 * @param {string} npcId - Cast id for the NPC (its class name).
 * @param {?string} npcName - Display name; falls back to the id before the
 *   server has told us what the NPC is called.
 * @returns {Array<{id: string, name: string, side: string, emotion: string}>}
 */
export function npcCast(npcId, npcName) {
    return [
        { id: JEAN_ID, name: JEAN_ID, side: 'left', emotion: DEFAULT_EMOTION },
        { id: npcId, name: npcName || npcId, side: 'right', emotion: DEFAULT_EMOTION },
    ]
}

/**
 * Build a live-chat conversation segment.
 *
 * The defaults ARE the contract: every field the renderers read is present and
 * of the right type on every segment this returns, so no consumer has to
 * defend against a half-built beat — nor against an unbounded one, since both
 * model-authored fields are capped here.
 *
 * Authored-event segments arrive already-formed from the server and are NOT
 * passed through here — this is the live producer's factory. Both shapes are
 * described by the {@link ConversationSegment} typedef above.
 *
 * @param {Object} beat
 * @param {string} beat.text
 * @param {?string} beat.speaker
 * @param {string} [beat.emotion]
 * @param {string} [beat.flavor]
 * @param {Object<string,string>} [beat.reactions]
 * @returns {ConversationSegment}
 */
export function conversationSegment({
    text,
    speaker,
    emotion = DEFAULT_EMOTION,
    flavor = '',
    reactions = {},
}) {
    return {
        text: boundedText(text),
        speaker,
        emotion,
        flavor: boundedText(flavor),
        reactions,
        in_conversation: true,
    }
}

export default conversationSegment
