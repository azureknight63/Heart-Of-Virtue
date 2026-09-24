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
 * Sized from the engine's turn budget, which is now ENFORCED: every provider
 * call is clipped to what the turn has left and the chain stops once it is
 * spent, so a turn ends at `_TURN_CEILING_SECONDS` (src/npc/_chat_llm.py) plus
 * at most one call. This waits a little longer than that, and stays inside the
 * production worker's timeout (deploy/heart-of-virtue.service: 120s, and on an
 * eventlet worker that bounds a STALLED worker rather than a slow request).
 * Both bounds are derived from the engine constants by
 * tests/test_npc_chat_turn_budget.py, not restated here.
 */
export const NPC_CHAT_TIMEOUT_MS = 28000

// Every chat call carries the deadline. `/end` is not LLM-backed, and nothing
// on screen waits on it any more: `handleEndConversation` (hooks/useNpcChat.js)
// closes the panel first and sends it fire-and-forget. The deadline still
// bounds it, so an `/end` the worker never answers settles and is logged
// instead of hanging with no limit but the browser's own.
const TURN_CONFIG = { timeout: NPC_CHAT_TIMEOUT_MS }

const npcChat = {
  /**
   * Open a conversation with an NPC
   * @param {string} npcId - NPC class name (e.g., 'Mynx', 'Gorran')
   * @returns {Promise} Response with { npc_key, open_token, npc_name, npc_opening, jean_options,
   *   loquacity_current, loquacity_max, conversation_ended, reputation, relationship }
   */
  open: (npcId) => apiClient.post(`${BASE}/open`, { npc_id: npcId }, TURN_CONFIG),

  /**
   * Send a response from Jean to an NPC
   * @param {string} npcKey - Session key returned from /open
   * @param {string} jeanText - Jean's dialogue text
   * @param {string} jeanTone - Jean's portrait emotion for the line (the tone of the option picked)
   * @param {object} [options]
   * @param {string} [options.turnId] - Idempotency key for this turn (#636): one per
   *   option click, reused by that click's Retry, so a turn the server already
   *   committed is replayed instead of run twice. Omitted, the field is not sent.
   * @param {number} [options.timeoutMs] - This request's own deadline, for a re-send
   *   that must end with the turn's first deadline rather than start a fresh
   *   one. Omitted, the full `NPC_CHAT_TIMEOUT_MS` applies.
   * @returns {Promise} Response with { npc_response, jean_options, loquacity_current,
   *   loquacity_max, conversation_ended, reputation, reputation_delta, relationship }
   */
  respond: (npcKey, jeanText, jeanTone = 'direct', { turnId, timeoutMs } = {}) =>
    apiClient.post(
      `${BASE}/respond`,
      {
        npc_key: npcKey,
        jean_text: jeanText,
        jean_tone: jeanTone,
        ...(turnId ? { turn_id: turnId } : {}),
      },
      // Truthy, not `!= null`: axios reads `timeout: 0` as no deadline at all.
      timeoutMs ? { timeout: timeoutMs } : TURN_CONFIG
    ),

  /**
   * End a conversation with an NPC
   * @param {string} npcKey - Session key returned from /open
   * @param {string} [openToken] - The `open_token` /open returned (#674). The
   *   server clears its active-chat marker only for the open it names, so a
   *   late /end cannot clear a quick re-open of the same NPC. Omitted, the
   *   field is not sent and the server matches on the key alone.
   * @returns {Promise} Response confirming conversation ended
   */
  end: (npcKey, openToken) =>
    apiClient.post(
      `${BASE}/end`,
      { npc_key: npcKey, ...(openToken ? { open_token: openToken } : {}) },
      TURN_CONFIG
    ),

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
