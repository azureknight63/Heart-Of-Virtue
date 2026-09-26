import { useCallback, useEffect, useRef, useState } from 'react'

import { admin as adminApi } from '../api/endpoints'
import { apiErrorMessage } from '../utils/apiError'

export const ANALYTICS_LOAD_FAILED = 'Could not load analytics. Please try again.'
// The windows the page offers; DEFAULT_DAYS must be one of them, or no
// window shows as selected on first load.
export const ANALYTICS_WINDOWS = [7, 30, 90]
export const DEFAULT_DAYS = 30

/**
 * Fetch the admin analytics report (`GET /api/admin/analytics`) for a window.
 *
 * A 404 is the server saying "you are not an admin" (the allow-list is
 * HOV_ADMIN_USER_IDS in src/api/routes/admin.py, which does not advertise the
 * route), so it sets `notFound` rather than `error`: the page shows nothing to
 * a player who wandered onto /admin, instead of a retry button.
 *
 * Changing `days` clears the report and refetches, and a slow response for an
 * earlier window is dropped when it lands after a newer request: between them,
 * the tables never show one window's numbers under another window's label.
 *
 * @returns {{report: ?Object, days: number, selectDays: Function, isLoading: boolean,
 *            error: string, notFound: boolean, isAdmin: boolean, reload: Function}}
 */
export default function useAdminAnalytics() {
    const [days, setDays] = useState(DEFAULT_DAYS)
    const [report, setReport] = useState(null)
    const [error, setError] = useState('')
    const [notFound, setNotFound] = useState(false)
    // True once the server has served this viewer a report: the page shows its
    // header and controls only then, so a non-admin never sees them.
    const [isAdmin, setIsAdmin] = useState(false)
    const [isLoading, setIsLoading] = useState(true)
    const latestRequestId = useRef(0)

    const reload = useCallback(async () => {
        const request = ++latestRequestId.current
        setIsLoading(true)
        setError('')
        try {
            const response = await adminApi.getAnalytics(days)
            if (request !== latestRequestId.current) return
            const next = response?.data?.report
            if (!next) {
                setError(ANALYTICS_LOAD_FAILED)
                return
            }
            setReport(next)
            setNotFound(false)
            setIsAdmin(true)
        } catch (err) {
            if (request !== latestRequestId.current) return
            if (err?.response?.status === 404) {
                setNotFound(true)
            } else {
                setError(apiErrorMessage(err, ANALYTICS_LOAD_FAILED))
            }
        } finally {
            if (request === latestRequestId.current) setIsLoading(false)
        }
    }, [days])

    useEffect(() => {
        reload()
    }, [reload])

    const selectDays = useCallback((next) => {
        if (next === days) return
        setReport(null)
        setDays(next)
    }, [days])

    return { report, days, selectDays, isLoading, error, notFound, isAdmin, reload }
}
