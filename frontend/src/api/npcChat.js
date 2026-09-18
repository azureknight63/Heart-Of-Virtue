import apiClient from './client'

/**
 * npcChat - Axios endpoint wrappers for NPC chat API routes
 * Uses apiClient, which sends the HttpOnly session cookie with every request
 */

// apiClient already prefixes baseURL ('/api'), so paths here must be relative to it.
const BASE = '/npc/chat'

/**
 * How long the client will wait for one conversation turn before giving up.
 *
 * Issue #618: a `/respond` that never answered pinned the panel at
 * WAITING_NPC — `loading` derives from the phase, so the spinner ran forever,
 * the options stayed withdrawn and the tester sat there for over 90 seconds.
 * `apiClient` deliberately carries NO global timeout (a blanket one would also
 * cut off `/game/new` and `/saves/{id}/load`, which build a universe and are
 * legitimately slow), so the bound is scoped to the three chat calls here.
 *
 * Derived from the engine's own turn budget rather than picked:
 * `_turn_deadline` (src/npc/_chat_llm.py) allows a turn
 * `max(_CHAT_DEADLINE_SECONDS, _MAX_TURN_STAGES x NPC_CHAT_LLM_TIMEOUT)`
 * = max(12, 4 x 6) = 24 seconds of provider work. That budget only refuses to
 * OPEN a further stage, it never aborts one already in flight, and a single
 * stage walks the whole provider fallback chain — so the honest server-side
 * ceiling is 24s plus the tail of the last stage to start. 45s clears that with
 * room for the Flask round trip, while staying far short of the uncapped
 * chain walk this exists to stop the player watching.
 *
 * Raising NPC_CHAT_LLM_TIMEOUT server-side widens the engine budget without
 * widening this; the engine logs a warning when it is set above 6s, and this
 * number should move with it.
 */
export const NPC_CHAT_TIMEOUT_MS = 45000

// Every LLM-backed chat call carries the deadline. `/end` needs it as much as
// the other two: `handleEndConversation` (hooks/useNpcChat.js) latches
// `endingRef` before awaiting, so a hung `/end` makes a second click a no-op
// and strands the panel on screen with no way out at all.
const TURN_CONFIG = { timeout: NPC_CHAT_TIMEOUT_MS }

const npcChat = {
  /**
   * Open a conversation with an NPC
   * @param {string} npcId - NPC class name (e.g., 'Mynx', 'Gorran')
   * @returns {Promise} Response with { npc_key, npc_name, npc_opening, jean_options,
   *   loquacity_current, loquacity_max, conversation_ended, reputation, relationship }
   */
  open: (npcId) => apiClient.post(`${BASE}/open`, { npc_id: npcId }, TURN_CONFIG),

  /**
   * Send a response from Jean to an NPC
   * @param {string} npcKey - Session key returned from /open
   * @param {string} jeanText - Jean's dialogue text
   * @param {string} jeanTone - 'direct', 'guarded', or 'open'
   * @returns {Promise} Response with { npc_response, jean_options, loquacity_current,
   *   loquacity_max, conversation_ended, reputation, reputation_delta, relationship }
   */
  respond: (npcKey, jeanText, jeanTone = 'direct') =>
    apiClient.post(
      `${BASE}/respond`,
      {
        npc_key: npcKey,
        jean_text: jeanText,
        jean_tone: jeanTone,
      },
      TURN_CONFIG
    ),

  /**
   * End a conversation with an NPC
   * @param {string} npcKey - Session key returned from /open
   * @returns {Promise} Response confirming conversation ended
   */
  end: (npcKey) => apiClient.post(`${BASE}/end`, { npc_key: npcKey }, TURN_CONFIG),

  /**
   * Retrieve conversation history.
   *
   * No production caller: the panel renders its history from the segments it
   * already holds, which carry the per-turn emotion and flavor the server
   * record does not (see ConversationHistoryDialog). Kept as the client's
   * coverage of the endpoint the API actually exposes, and encoded because it
   * is the one URL here built by interpolation rather than a JSON body.
   *
   * @param {string} npcKey - Session key returned from /open
   * @returns {Promise} Response with full conversation history
   */
  history: (npcKey) => apiClient.get(`${BASE}/history/${encodeURIComponent(npcKey)}`),
}

export default npcChat
