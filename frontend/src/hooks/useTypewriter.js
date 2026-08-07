import { useState, useEffect, useRef, useCallback } from 'react'

/**
 * useTypewriter - Hook for achieving a typewriter animation effect
 * @param {string} text - The full text to animate
 * @param {number} speed - The delay between characters in milliseconds (default: 30)
 * @returns {object} { displayedText, isComplete, finishImmediately, reset }
 */
export default function useTypewriter(text, speed = 30) {
    const [displayedText, setDisplayedText] = useState('')
    const [isComplete, setIsComplete] = useState(false)
    const intervalRef = useRef(null)

    const reset = useCallback(() => {
        setDisplayedText('')
        setIsComplete(false)
        if (intervalRef.current) clearInterval(intervalRef.current)
    }, [])

    const finishImmediately = useCallback(() => {
        if (!isComplete) {
            if (intervalRef.current) clearInterval(intervalRef.current)
            setDisplayedText(text)
            setIsComplete(true)
        }
    }, [text, isComplete])

    useEffect(() => {
        reset()

        // Nothing to type — an empty beat is complete the moment it starts.
        // Bailing out without this leaves isComplete false forever, which stalls
        // consumers that gate their "continue" affordance or auto-advance on it.
        if (!text) {
            setIsComplete(true)
            return
        }

        const chars = Array.from(text)
        let charsAdded = 0

        intervalRef.current = setInterval(() => {
            if (charsAdded >= chars.length) {
                setIsComplete(true)
                if (intervalRef.current) clearInterval(intervalRef.current)
                return
            }

            const charToAdd = chars[charsAdded]
            setDisplayedText(prev => prev + charToAdd)
            charsAdded++
        }, speed)

        return () => {
            if (intervalRef.current) clearInterval(intervalRef.current)
        }
    }, [text, speed, reset])

    return {
        displayedText,
        isComplete,
        finishImmediately,
        reset
    }
}
