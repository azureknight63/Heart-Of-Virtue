import { useCallback, useRef, useState } from 'react'

import { player as playerApi } from '../api/endpoints'
import { apiErrorMessage } from '../utils/apiError'

export const PRAYER_FAILED = 'Jean could not pray just now. Please try again.'

/**
 * Jean prays (issue #646): `POST /api/pray`, the out-of-combat cure for
 * Hollowed. The engine decides the cost and the outcome; this hook only
 * carries the request and turns either answer into one line of prose.
 *
 * Never rejects: a refusal (mid-fight, too spent) arrives as a 400 whose
 * `error` is the engine's own sentence, and it is returned the same way a
 * success is, so the caller has one shape to render. One prayer at a time: a
 * call while one is in flight returns that same promise.
 *
 * @returns {{pray: () => Promise<{ok: boolean, message: string}>, isPraying: boolean}}
 */
export default function usePrayer() {
  const [isPraying, setIsPraying] = useState(false)
  // The prayer in flight, if any. `isPraying` disables the button only after a
  // re-render, so a double click that lands before it would send two POSTs;
  // a second call while one is running shares the first one's answer instead.
  const inFlightRef = useRef(null)

  const pray = useCallback(() => {
    if (inFlightRef.current) return inFlightRef.current
    const request = (async () => {
      setIsPraying(true)
      try {
        const response = await playerApi.pray()
        const data = response?.data
        if (data?.success) {
          return { ok: true, message: data.message }
        }
        return { ok: false, message: apiErrorMessage(data, PRAYER_FAILED) }
      } catch (err) {
        return { ok: false, message: apiErrorMessage(err, PRAYER_FAILED) }
      } finally {
        inFlightRef.current = null
        setIsPraying(false)
      }
    })()
    inFlightRef.current = request
    return request
  }, [])

  return { pray, isPraying }
}
