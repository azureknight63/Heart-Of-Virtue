import { useCallback, useState } from 'react'

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
 * success is, so the caller has one shape to render.
 *
 * @returns {{pray: () => Promise<{ok: boolean, message: string}>, isPraying: boolean}}
 */
export default function usePrayer() {
  const [isPraying, setIsPraying] = useState(false)

  const pray = useCallback(async () => {
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
  }, [])

  return { pray, isPraying }
}
