import apiClient from './client'

/**
 * npcChat - Axios endpoint wrappers for NPC chat API routes
 * Uses apiClient which automatically handles auth tokens via localStorage.authToken
 */

const BASE = '/api/npc/chat'

const npcChat = {
  /**
   * Open a conversation with an NPC
   * @param {string} npcId - NPC class name (e.g., 'Mynx', 'Gorran')
   * @returns {Promise} Response with { npc_key, display_name, loquacity, current_options, messages }
   */
  open: (npcId) => apiClient.post(`${BASE}/open`, { npc_id: npcId }),

  /**
   * Send a response from Jean to an NPC
   * @param {string} npcKey - Session key returned from /open
   * @param {string} jeanText - Jean's dialogue text
   * @param {string} jeanTone - 'direct', 'guarded', or 'open'
   * @returns {Promise} Response with updated NPC response and options
   */
  respond: (npcKey, jeanText, jeanTone = 'direct') =>
    apiClient.post(`${BASE}/respond`, {
      npc_key: npcKey,
      jean_text: jeanText,
      jean_tone: jeanTone,
    }),

  /**
   * End a conversation with an NPC
   * @param {string} npcKey - Session key returned from /open
   * @returns {Promise} Response confirming conversation ended
   */
  end: (npcKey) => apiClient.post(`${BASE}/end`, { npc_key: npcKey }),

  /**
   * Retrieve conversation history
   * @param {string} npcKey - Session key returned from /open
   * @returns {Promise} Response with full conversation history
   */
  history: (npcKey) => apiClient.get(`${BASE}/history/${npcKey}`),
}

export default npcChat
