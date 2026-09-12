import { useCallback, useEffect, useMemo, useState } from 'react'
import apiEndpoints from '../api/endpoints'
import { apiErrorMessage } from '../utils/apiError'
import logger from '../utils/logger'
import {
    SAVE_LABEL_SEPARATOR,
    fetchSavesNewestFirst,
    saveDisplayName,
    saveSummaryParts,
} from '../utils/localSave'

/**
 * What each exit says when its own REQUEST failed and the server error
 * carried no message of its own. Exported beside the line above because the
 * dialog's tests assert on all three, and a hand-typed copy passes whether or
 * not the hook still uses that wording.
 */
export const LOAD_SAVE_FAILED = 'Failed to load save.'
export const START_OVER_FAILED = 'Failed to start over.'

// The two exits, as `submittingAction` names whichever is in flight.
const LOAD_SAVE = 'load'
const START_OVER = 'startOver'

/**
 * useDefeatRecovery — the state and actions behind DefeatDialog.
 *
 * Owns the save list (newest first, the order MainMenuPage shows and Continue
 * targets), the selected save, and the two ways out of a defeat: load a save,
 * or start a fresh run. Both exits have the same shape — one request, then
 * tell the parent the underlying run changed — which is why they share
 * `recover` rather than being two copies of a try/submit/finally block. Not
 * built on `useAsyncAction`: that hook binds one action per instance with its
 * own loading/error pair, and this dialog reports one submitting flag and one
 * error line across both exits.
 *
 * Issue #587: "start over" is POST /game/new, the same call MainMenuPage's
 * New Game button makes; it never logs the player out.
 *
 * @param {object} options
 * @param {Function} [options.onRunChanged] - called once either exit's
 *   request succeeds, so the parent can reset out of defeat. If it rejects,
 *   nothing is shown: the run HAS changed, the parent is already re-fetching,
 *   and there is no action for the player to take -- so it is logged, not
 *   rendered. A failed REQUEST is different, and shows its own message, else
 *   the exit's fallback copy.
 * @returns {{isLoadingSaves: boolean, isSubmitting: boolean,
 *   isRestoringSave: boolean, error: string,
 *   saveOptions: Array<{id: string, label: string}>, selectedSaveId: string,
 *   setSelectedSaveId: Function, loadSave: Function, startOver: Function}}
 *   DefeatDialog's whole contract with this hook. `isSubmitting` is "either
 *   exit is in flight", which disables both buttons; `isRestoringSave` is
 *   "the LOAD one is", which only that button's label reads. `isLoadingSaves`
 *   is the unrelated list fetch -- it was one character from `isLoadingSave`,
 *   which is why the restore flag is spelled the way it is now.
 */
export default function useDefeatRecovery({ onRunChanged } = {}) {
    const [isLoadingSaves, setIsLoadingSaves] = useState(false)
    // Which exit is in flight, or null. Both exits share the disabled
    // state, but only the one the player pressed may say what it is doing:
    // a single `isSubmitting` had START OVER relabel LOAD as 'LOADING…'.
    // `START_OVER` is therefore a sentinel that is merely NOT `LOAD_SAVE` --
    // the START OVER button has no in-flight label of its own to derive, so
    // there is deliberately no `isStartingOver` in the returned object.
    const [submittingAction, setSubmittingAction] = useState(null)
    const [error, setError] = useState('')
    const [saves, setSaves] = useState([])
    const [selectedSaveId, setSelectedSaveId] = useState('')

    useEffect(() => {
        let mounted = true

        const fetchSaves = async () => {
            try {
                setIsLoadingSaves(true)
                setError('')
                const list = await fetchSavesNewestFirst(() => apiEndpoints.saves.list())
                if (!mounted) return
                setSaves(list)
                if (list.length > 0) {
                    setSelectedSaveId(list[0].id)
                }
            } catch (e) {
                if (!mounted) return
                setError(apiErrorMessage(e, e?.message || 'Failed to load saves.'))
            } finally {
                if (mounted) setIsLoadingSaves(false)
            }
        }

        fetchSaves()

        return () => {
            mounted = false
        }
    }, [])

    const saveOptions = useMemo(
        () => saves.map((row) => ({
            id: row.id,
            label: [saveDisplayName(row), ...saveSummaryParts(row)].join(SAVE_LABEL_SEPARATOR),
        })),
        [saves],
    )

    /**
     * One request that changes the run, then the parent's callback.
     *
     * Unlike the list fetch above, neither exit guards its `setState` on a
     * `mounted` flag: on the success path the parent's `onRunChanged`
     * normally unmounts this dialog before `finally` runs, and React 18 no
     * longer warns about a set on an unmounted component.
     */
    const recover = useCallback(async (action, request, fallbackMessage) => {
        setError('')
        let runChanged = false
        try {
            setSubmittingAction(action)
            await request()
            runChanged = true
            if (typeof onRunChanged === 'function') {
                await onRunChanged()
            }
        } catch (e) {
            if (runChanged) {
                // The request SUCCEEDED and only the parent's refresh threw.
                // Reporting `fallbackMessage` here would tell the player their
                // save did not load when it did, so this path is deliberately
                // not an error line -- it is logged instead. There is nothing
                // for the player to do about it either way: the parent is
                // already re-fetching, and the dialog is closing.
                logger.event('defeat.recovery.refresh_failed', {
                    action,
                    message: e?.message || null,
                })
            } else {
                setError(apiErrorMessage(e, e?.message || fallbackMessage))
            }
        } finally {
            setSubmittingAction(null)
        }
    }, [onRunChanged])

    const loadSave = useCallback(async () => {
        // DefeatDialog disables LOAD until a save is selected; this guards any
        // other caller of the hook.
        if (!selectedSaveId) {
            setError('Select a save to load.')
            return
        }
        await recover(
            LOAD_SAVE,
            () => apiEndpoints.saves.load(selectedSaveId),
            LOAD_SAVE_FAILED,
        )
    }, [recover, selectedSaveId])

    const startOver = useCallback(
        () => recover(START_OVER, () => apiEndpoints.saves.newGame(), START_OVER_FAILED),
        [recover],
    )

    return {
        isLoadingSaves,
        isSubmitting: submittingAction !== null,
        isRestoringSave: submittingAction === LOAD_SAVE,
        error,
        saveOptions,
        selectedSaveId,
        setSelectedSaveId,
        loadSave,
        startOver,
    }
}
