import { useCallback, useEffect, useState } from 'react'

import { player as playerApi } from '../api/endpoints'
import { apiErrorMessage } from '../utils/apiError'

export const JOURNAL_LOAD_FAILED = 'Could not load the journal. Please try again.'

/**
 * Fetch the player's journal — standing objectives and the scene transcript.
 *
 * A hook rather than a fetch inside the dialog, per the project rule that
 * stateful logic lives in `hooks/` (`.claude/rules/frontend.md`): the load /
 * error / retry cycle is then testable without rendering a dialog, and
 * `JournalDialog` is left as presentation.
 *
 * Fetches once on mount. Nothing invalidates it while it is open, and nothing
 * needs to: the journal is rendered inside a modal, so the story cannot
 * advance underneath it, and each open is a fresh mount.
 *
 * @returns {{journal: ?Object, isLoading: boolean, error: string, reload: Function}}
 */
export default function useJournal() {
    const [journal, setJournal] = useState(null)
    const [error, setError] = useState('')
    const [isLoading, setIsLoading] = useState(true)

    const reload = useCallback(async () => {
        setIsLoading(true)
        setError('')
        try {
            const response = await playerApi.getJournal()
            setJournal(response?.data?.journal || null)
        } catch (err) {
            setError(apiErrorMessage(err, JOURNAL_LOAD_FAILED))
        } finally {
            setIsLoading(false)
        }
    }, [])

    useEffect(() => {
        reload()
    }, [reload])

    return { journal, isLoading, error, reload }
}
