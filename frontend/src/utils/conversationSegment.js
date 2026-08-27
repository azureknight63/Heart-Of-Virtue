/**
 * The conversation `segment` — the single beat shape every conversation
 * surface reads.
 *
 * WHY THIS MODULE EXISTS
 * ----------------------
 * The shape has two producers and two consumers and used to be declared in
 * none of them:
 *
 *   producers   `chatSegment` in hooks/useNpcChat.js (live LLM chat), and the
 *               authored-event path in src/api/services/game_service.py, which
 *               serialises `src/narration.py`'s beats onto the wire.
 *   consumers   components/ConversationStage.jsx (the live/authored stage) and
 *               components/ConversationTranscript.jsx (recap strip + history).
 *
 * With no declaration, a field could be produced by one side and silently
 * dropped by the other — which is exactly what happened to `thought` and
 * `reactions` in `TranscriptEntry`. The typedef below is the contract, and the
 * per-field notes say which renderer honours what, so "the transcript ignores
 * this" is a documented decision rather than an unnoticed gap.
 *
 * The Python producer is not ours to edit from here; when a field is added
 * there it belongs in this typedef too.
 *
 * @typedef {Object} ConversationSegment
 * @property {string}  text            The spoken (or narrated) line.
 *   Honoured by: stage (typed out a character at a time), transcript.
 * @property {?string} speaker         Cast id of whoever is talking. Absent on
 *   a narration beat, which both renderers centre as italic prose with no
 *   portrait.
 *   Honoured by: stage, transcript.
 * @property {string}  emotion         The speaker's expression for THIS beat,
 *   resolved against utils/portraits' EMOTIONS (anything else normalises to
 *   'neutral').
 *   Honoured by: stage, transcript.
 * @property {string}  flavor          Stage direction / aside rendered above
 *   the line.
 *   Honoured by: stage, transcript.
 * @property {Object<string,string>} reactions  Listener id -> emotion, applied
 *   to cast members who are not speaking.
 *   Honoured by: stage only. The transcript renders one speaker per row, so a
 *   listener's reaction has nowhere to go — DELIBERATE, not an oversight.
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
 * Build a live-chat conversation segment.
 *
 * The defaults ARE the contract: every field the renderers read is present and
 * of the right type on every segment this returns, so neither consumer has to
 * defend against a half-built beat.
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
        text: text || '',
        speaker,
        emotion,
        flavor: flavor || '',
        reactions,
        in_conversation: true,
    }
}

export default conversationSegment
