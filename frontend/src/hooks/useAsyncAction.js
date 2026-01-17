import { useState, useCallback } from 'react'

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
            const errorMessage = err.response?.data?.error || err.message || 'An unexpected error occurred'
            setError(errorMessage)
            if (onError) onError(errorMessage)
            throw err
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
