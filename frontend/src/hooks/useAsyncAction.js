import { useState, useCallback } from 'react'
import { apiErrorMessage } from '../utils/apiError'

/**
 * useAsyncAction - Custom hook for managing state of asynchronous actions
 * @param {Function} actionFn - The async function to execute
 * @param {Object} options - Success and error callbacks
 */
export default function useAsyncAction(actionFn, { onSuccess, onError } = {}) {
    const [isLoading, setIsLoading] = useState(false)
    const [error, setError] = useState(null)
    const [data, setData] = useState(null)

    const execute = useCallback(async (...args) => {
        setIsLoading(true)
        setError(null)
        try {
            const result = await actionFn(...args)
            setData(result)
            if (onSuccess) onSuccess(result)
            return result
        } catch (err) {
            // `err.message` stays in the fallback, not ahead of the server's
            // copy: it is axios's transport wording, which is all there is to
            // say when the request never reached a route.
            const errorMessage = apiErrorMessage(err, err.message || 'An unexpected error occurred')
            setError(errorMessage)
            if (onError) onError(errorMessage)
        } finally {
            setIsLoading(false)
        }
    }, [actionFn, onSuccess, onError])

    const reset = useCallback(() => {
        setIsLoading(false)
        setError(null)
        setData(null)
    }, [])

    return { execute, isLoading, error, data, reset, setError, loading: isLoading } // Added 'loading' alias for convenience
}
