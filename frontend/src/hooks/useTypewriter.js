import { useState, useEffect, useRef, useCallback } from 'react'

/**
 * useTypewriter - Hook for achieving a typewriter animation effect
 * @param {string} text - The full text to animate
 * @param {number} speed - The delay between words in milliseconds (default: 30)
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

        if (!text) return

        const words = text.split(' ')
        let wordsAdded = 0

        intervalRef.current = setInterval(() => {
            if (wordsAdded >= words.length) {
                setIsComplete(true)
                if (intervalRef.current) clearInterval(intervalRef.current)
                return
            }

            const wordToAdd = words[wordsAdded]
            setDisplayedText(prev => prev ? `${prev} ${wordToAdd}` : wordToAdd)
            wordsAdded++
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
