/**
 * The one gate every client copy of a combat `end_state` passes through.
 *
 * The engine emits end_state only as `{id, status: 'victory' | 'defeat', ...}`
 * (ApiCombatAdapter builds `combat_end_summary` with a fresh uuid in both
 * branches). The id is what makes an end state resolvable: useCombatCoordinator
 * keys its dialog timer on it, and the timer is the only thing that clears the
 * "resolving" flags and lets GamePage leave combat mode. An end state stored
 * without one was never dispatched, so those flags stayed set forever -- a
 * permanent "Resolving battle..." with pending-event polling switched off
 * (#704). Such a payload is dropped here instead of stored.
 *
 * This is deliberately NOT applied in transformCombatData: LeftPanel's
 * `!combat?.end_state` gates must still see that the fight ended, id or not.
 */
import logger from './logger'

const RESOLVABLE_END_STATUSES = new Set(['victory', 'defeat'])

/**
 * True when `endState` is an end state the client can resolve: it carries an
 * id and a victory/defeat status.
 *
 * @param {*} endState - `combat.end_state` as polled.
 * @returns {boolean}
 */
export function isResolvableEndState(endState) {
    return Boolean(endState?.id) && RESOLVABLE_END_STATUSES.has(endState?.status)
}

/**
 * `combat.end_state` if it is resolvable, otherwise null. A present but
 * unresolvable payload is logged (when the dropped payload's shape changes --
 * eventOnChange compares against the last payload only, and the callers run
 * on every combat poll) so a backend regression shows up in the logs rather
 * than as a silently ignored fight end. `status` came off the wire, so only a
 * short prefix of a string (or the type of anything else) is logged.
 *
 * @param {*} endState - `combat.end_state` as polled.
 * @returns {Object|null}
 */
export function resolvableEndState(endState) {
    if (isResolvableEndState(endState)) return endState
    if (endState) {
        logger.eventOnChange('combat.end_state.dropped', {
            has_id: Boolean(endState.id),
            status: loggableStatus(endState.status),
        })
    }
    return null
}

const MAX_LOGGED_STATUS_LENGTH = 32

function loggableStatus(status) {
    if (status == null) return null
    return typeof status === 'string' ? status.slice(0, MAX_LOGGED_STATUS_LENGTH) : typeof status
}
