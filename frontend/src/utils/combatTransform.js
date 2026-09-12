/**
 * The client-side combat object, built from any get_combat_state()-shaped
 * payload (a status poll, an action response, or a socket event).
 *
 * `battle_state` is spread flat, then a FIXED set of top-level keys is copied
 * with defaults. Anything else at the top level of the payload never reaches
 * the client, which is why new per-poll combat fields belong inside
 * `battle_state` (.claude/rules/frontend.md). Its own module, free of React
 * and the API client, so the test payload builders build their client-shape
 * fixture by running it rather than re-listing its defaults.
 */
export const transformCombatData = (data) => ({
  ...data.battle_state,
  log: data.log || [],
  beat_states: data.beat_states || [],
  end_state: data.end_state || null,
  combat_active: data.combat_active,
  suggested_moves: data.suggested_moves || [],
  suggestions_loading: data.suggestions_loading || false,
  events_triggered: data.events_triggered || [],
  last_move_outcome: data.last_move_outcome || '',
  last_move_name: data.last_move_name || null,
  last_move_target_id: data.last_move_target_id || null
})
