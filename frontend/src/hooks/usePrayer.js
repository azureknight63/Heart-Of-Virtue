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
 * call while one is in flight gets that prayer's answer, marked `joined`.
 *
 * @returns {{pray: () => Promise<{ok: boolean, message: string, joined?: boolean}>, isPraying: boolean}}
 */
export default function usePrayer() {
  const [isPraying, setIsPraying] = useState(false)
  // The prayer in flight, if any. `isPraying` disables the button only after a
  // re-render, so a double click that lands before it would send two POSTs;
  // a second call while one is running shares the first one's answer instead.
  const inFlightRef = useRef(null)

  const pray = useCallback(() => {
    // A joined call is marked, so the caller can skip the side effects (the
    // toast, the HUD refetch) the first call already runs.
    if (inFlightRef.current) {
      return inFlightRef.current.then((outcome) => ({ ...outcome, joined: true }))
    }
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
        setIsPraying(false)
      }
    })()
    inFlightRef.current = request
    // Cleared once settled, and only if it is still this request: a
    // playerApi.pray() that throws synchronously settles before this line runs, so clearing
    // inside the IIFE left the ref holding a settled promise for good.
    request.then(() => {
      if (inFlightRef.current === request) inFlightRef.current = null
    })
    return request
  }, [])

  return { pray, isPraying }
}
