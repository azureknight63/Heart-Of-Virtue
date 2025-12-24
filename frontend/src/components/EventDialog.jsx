import { useState, useEffect, useRef } from 'react'

/**
 * EventDialog - Displays event output text and handles player input for events
 * Supports choice selection, text input, and number input with keyboard shortcuts
 */
export default function EventDialog({ event, onClose, onSubmitInput }) {
    const [displayedText, setDisplayedText] = useState('')
    const [isComplete, setIsComplete] = useState(false)
    const [showInput, setShowInput] = useState(false)
    const [textInput, setTextInput] = useState('')
    const [numberInput, setNumberInput] = useState('')
    const [validationMessage, setValidationMessage] = useState('')
    const [validationSeverity, setValidationSeverity] = useState('') // 'warning' or 'error'
    const [selectedChoice, setSelectedChoice] = useState(null)
    
    const inputRef = useRef(null)
    const dialogRef = useRef(null)

    // Extract event data
    const eventText = event?.output_text || event?.message || event?.description || ''
    const needsInput = event?.needs_input || false
    const inputType = event?.input_type || 'choice'
    const inputPrompt = event?.input_prompt || 'Your choice:'
    const inputOptions = event?.input_options || []
    const eventId = event?.event_id

    useEffect(() => {
        setDisplayedText('')
        setIsComplete(false)
        setShowInput(false)
        setTextInput('')
        setNumberInput('')
        setValidationMessage('')
        setSelectedChoice(null)

        if (!eventText) return

        const words = eventText.split(' ')
        let wordsAdded = 0

        const intervalId = setInterval(() => {
            if (wordsAdded >= words.length) {
                setIsComplete(true)
                // Show input after text is complete if event requires input
                if (needsInput) {
                    setShowInput(true)
                }
                clearInterval(intervalId)
                return
            }

            // Capture the word to add in this tick's closure
            const wordToAdd = words[wordsAdded]

            setDisplayedText(prev => {
                return prev ? `${prev} ${wordToAdd}` : wordToAdd
            })

            wordsAdded++
        }, 50) // Adjust speed here (ms per word)

        return () => clearInterval(intervalId)
    }, [eventText, needsInput])

    // Focus input when shown
    useEffect(() => {
        if (showInput && (inputType === 'text' || inputType === 'number')) {
            inputRef.current?.focus()
        }
    }, [showInput, inputType])

    // Keyboard shortcuts for choices (1-9) and Enter to submit
    useEffect(() => {
        const handleKeyDown = (e) => {
            if (!showInput) return

            // Handle number keys for choices
            if (inputType === 'choice' && inputOptions.length > 0) {
                const keyNum = parseInt(e.key)
                if (keyNum >= 1 && keyNum <= Math.min(9, inputOptions.length)) {
                    e.preventDefault()
                    const choice = inputOptions[keyNum - 1]
                    setSelectedChoice(keyNum - 1)
                    handleChoiceSelect(choice.value)
                }
            }

            // Handle Enter key
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                handleSubmit()
            }
        }

        if (dialogRef.current) {
            dialogRef.current.addEventListener('keydown', handleKeyDown)
        }

        return () => {
            if (dialogRef.current) {
                dialogRef.current.removeEventListener('keydown', handleKeyDown)
            }
        }
    }, [showInput, inputType, inputOptions, textInput, numberInput, selectedChoice])

    const finishImmediately = () => {
        if (!isComplete) {
            setDisplayedText(eventText)
            setIsComplete(true)
            if (needsInput) {
                setShowInput(true)
            }
        }
    }

    const handleChoiceSelect = (value) => {
        setSelectedChoice(value)
        setValidationMessage('')
    }

    const validateInput = () => {
        if (inputType === 'choice' && !selectedChoice) {
            setValidationMessage('Please select an option')
            setValidationSeverity('error')
            return false
        }

        if (inputType === 'text') {
            const trimmed = textInput.trim()
            if (!trimmed) {
                setValidationMessage('Input cannot be empty')
                setValidationSeverity('error')
                return false
            }
            if (trimmed.length > 500) {
                setValidationMessage(`Input too long (${trimmed.length}/500 characters)`)
                setValidationSeverity('error')
                return false
            }
            // Warning for short inputs
            if (trimmed.length < 3) {
                setValidationMessage('Input seems short, but will be accepted')
                setValidationSeverity('warning')
            }
        }

        if (inputType === 'number') {
            const num = parseInt(numberInput)
            if (isNaN(num)) {
                setValidationMessage('Please enter a valid number')
                setValidationSeverity('error')
                return false
            }
            const minValue = event?.min_value
            const maxValue = event?.max_value
            if (minValue !== undefined && num < minValue) {
                setValidationMessage(`Number must be at least ${minValue}`)
                setValidationSeverity('error')
                return false
            }
            if (maxValue !== undefined && num > maxValue) {
                setValidationMessage(`Number must be at most ${maxValue}`)
                setValidationSeverity('error')
                return false
            }
        }

        setValidationMessage('')
        return true
    }

    const handleSubmit = () => {
        if (!validateInput()) return

        let userInput = ''
        if (inputType === 'choice') {
            userInput = selectedChoice
        } else if (inputType === 'text') {
            userInput = textInput.trim()
        } else if (inputType === 'number') {
            userInput = numberInput
        }

        if (onSubmitInput && eventId) {
            onSubmitInput(eventId, userInput)
        }
    }

    const handleContinue = () => {
        if (!needsInput && isComplete) {
            onClose()
        }
    }

    // Character counter for text input
    const charCount = textInput.length
    const charLimit = 500
    const charCountColor = charCount > charLimit ? '#ff4444' : charCount > charLimit * 0.9 ? '#ffaa00' : '#888'

    return (
        <div
            style={{
                position: 'fixed',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                backgroundColor: 'rgba(0, 0, 0, 0.85)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                zIndex: 2000,
            }}
            onClick={!needsInput && isComplete ? handleContinue : finishImmediately}
        >
            <div
                ref={dialogRef}
                tabIndex={-1}
                style={{
                    backgroundColor: 'rgba(10, 20, 10, 0.98)',
                    border: '3px solid #00cc66',
                    borderRadius: '12px',
                    padding: '24px',
                    width: '90%',
                    maxWidth: '700px',
                    maxHeight: '80vh',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '16px',
                    boxShadow: '0 0 30px rgba(0, 204, 102, 0.6), inset 0 0 20px rgba(0, 0, 0, 0.8)',
                    overflowY: 'auto',
                    outline: 'none',
                }}
                onClick={(e) => e.stopPropagation()}
            >
                {/* Header */}
                <div style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    borderBottom: '2px solid #00cc66',
                    paddingBottom: '12px',
                }}>
                    <div style={{
                        color: '#00ff88',
                        fontWeight: 'bold',
                        fontSize: '18px',
                        fontFamily: 'monospace',
                        textShadow: '0 0 8px rgba(0, 255, 136, 0.8)',
                    }}>
                        ✨ {event?.name || 'Event'}
                    </div>
                    {!needsInput && (
                        <button
                            onClick={onClose}
                            style={{
                                padding: '6px 12px',
                                backgroundColor: '#004422',
                                color: '#00ff88',
                                border: '2px solid #00cc66',
                                borderRadius: '6px',
                                cursor: 'pointer',
                                fontSize: '14px',
                                fontFamily: 'monospace',
                                fontWeight: 'bold',
                                transition: 'all 0.2s',
                            }}
                            onMouseEnter={(e) => {
                                e.target.style.backgroundColor = '#006633'
                                e.target.style.boxShadow = '0 0 10px rgba(0, 204, 102, 0.8)'
                            }}
                            onMouseLeave={(e) => {
                                e.target.style.backgroundColor = '#004422'
                                e.target.style.boxShadow = 'none'
                            }}
                        >
                            Close
                        </button>
                    )}
                </div>

                {/* Event Text Output */}
                <div
                    onClick={finishImmediately}
                    style={{
                        padding: '16px',
                        backgroundColor: 'rgba(0, 0, 0, 0.7)',
                        border: '2px solid #00cc66',
                        borderRadius: '8px',
                        color: '#88ffcc',
                        fontFamily: 'monospace',
                        fontSize: '16px',
                        lineHeight: '1.8',
                        whiteSpace: 'pre-wrap',
                        minHeight: '120px',
                        maxHeight: '400px',
                        overflowY: 'auto',
                        boxShadow: 'inset 0 0 15px rgba(0,0,0,0.9)',
                        cursor: isComplete ? 'default' : 'pointer',
                    }}
                >
                    {displayedText}
                    {!isComplete && (
                        <span style={{
                            borderRight: '3px solid #00cc66',
                            marginLeft: '4px',
                            animation: 'blink 1s step-end infinite'
                        }}>&nbsp;</span>
                    )}
                </div>

                {/* Input Section */}
                {showInput && needsInput && (
                    <div style={{
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '12px',
                        marginTop: '8px',
                    }}>
                        {/* Input Prompt */}
                        <div style={{
                            color: '#00ff88',
                            fontWeight: 'bold',
                            fontSize: '14px',
                            fontFamily: 'monospace',
                            textAlign: 'center',
                            marginBottom: '4px',
                        }}>
                            {inputPrompt}
                        </div>

                        {/* Choice Buttons */}
                        {inputType === 'choice' && inputOptions.length > 0 && (
                            <div style={{
                                display: 'grid',
                                gridTemplateColumns: inputOptions.length <= 3 ? '1fr' : 'repeat(2, 1fr)',
                                gap: '12px',
                            }}>
                                {inputOptions.map((option, idx) => {
                                    const isSelected = selectedChoice === option.value
                                    const keyBinding = idx < 9 ? `[${idx + 1}]` : ''
                                    
                                    return (
                                        <button
                                            key={idx}
                                            onClick={() => handleChoiceSelect(option.value)}
                                            style={{
                                                padding: '14px 20px',
                                                backgroundColor: isSelected ? 'rgba(0, 102, 51, 0.6)' : 'rgba(0, 50, 25, 0.4)',
                                                border: `2px solid ${isSelected ? '#00ff88' : '#00cc66'}`,
                                                borderRadius: '6px',
                                                color: '#88ffcc',
                                                fontFamily: 'monospace',
                                                fontSize: '15px',
                                                cursor: 'pointer',
                                                textAlign: 'center',
                                                fontWeight: 'bold',
                                                transition: 'all 0.2s',
                                                boxShadow: isSelected ? '0 0 12px rgba(0, 255, 136, 0.5)' : 'none',
                                            }}
                                            onMouseEnter={(e) => {
                                                e.currentTarget.style.backgroundColor = 'rgba(0, 102, 51, 0.6)'
                                                e.currentTarget.style.borderColor = '#00ff88'
                                                e.currentTarget.style.boxShadow = '0 0 12px rgba(0, 255, 136, 0.5)'
                                            }}
                                            onMouseLeave={(e) => {
                                                e.currentTarget.style.backgroundColor = isSelected ? 'rgba(0, 102, 51, 0.6)' : 'rgba(0, 50, 25, 0.4)'
                                                e.currentTarget.style.borderColor = isSelected ? '#00ff88' : '#00cc66'
                                                e.currentTarget.style.boxShadow = isSelected ? '0 0 12px rgba(0, 255, 136, 0.5)' : 'none'
                                            }}
                                        >
                                            {keyBinding && <span style={{ color: '#ffaa00', marginRight: '8px' }}>{keyBinding}</span>}
                                            {option.label}
                                        </button>
                                    )
                                })}
                            </div>
                        )}

                        {/* Text Input */}
                        {inputType === 'text' && (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                                <textarea
                                    ref={inputRef}
                                    value={textInput}
                                    onChange={(e) => setTextInput(e.target.value)}
                                    placeholder="Enter your text here..."
                                    maxLength={500}
                                    style={{
                                        padding: '12px',
                                        backgroundColor: 'rgba(0, 0, 0, 0.7)',
                                        border: '2px solid #00cc66',
                                        borderRadius: '6px',
                                        color: '#88ffcc',
                                        fontFamily: 'monospace',
                                        fontSize: '14px',
                                        minHeight: '100px',
                                        resize: 'vertical',
                                        outline: 'none',
                                    }}
                                    onFocus={(e) => e.target.style.borderColor = '#00ff88'}
                                    onBlur={(e) => e.target.style.borderColor = '#00cc66'}
                                />
                                <div style={{
                                    textAlign: 'right',
                                    fontSize: '12px',
                                    color: charCountColor,
                                    fontFamily: 'monospace',
                                }}>
                                    {charCount}/{charLimit} characters
                                </div>
                            </div>
                        )}

                        {/* Number Input */}
                        {inputType === 'number' && (
                            <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                                <button
                                    onClick={() => setNumberInput(prev => String(Math.max((parseInt(prev) || 0) - 1, event?.min_value || 0)))}
                                    style={{
                                        padding: '12px 20px',
                                        backgroundColor: 'rgba(0, 50, 25, 0.6)',
                                        border: '2px solid #00cc66',
                                        borderRadius: '6px',
                                        color: '#00ff88',
                                        fontFamily: 'monospace',
                                        fontSize: '18px',
                                        fontWeight: 'bold',
                                        cursor: 'pointer',
                                    }}
                                >
                                    -
                                </button>
                                <input
                                    ref={inputRef}
                                    type="number"
                                    value={numberInput}
                                    onChange={(e) => setNumberInput(e.target.value)}
                                    placeholder="0"
                                    min={event?.min_value}
                                    max={event?.max_value}
                                    style={{
                                        flex: 1,
                                        padding: '12px',
                                        backgroundColor: 'rgba(0, 0, 0, 0.7)',
                                        border: '2px solid #00cc66',
                                        borderRadius: '6px',
                                        color: '#88ffcc',
                                        fontFamily: 'monospace',
                                        fontSize: '16px',
                                        textAlign: 'center',
                                        outline: 'none',
                                    }}
                                    onFocus={(e) => e.target.style.borderColor = '#00ff88'}
                                    onBlur={(e) => e.target.style.borderColor = '#00cc66'}
                                />
                                <button
                                    onClick={() => setNumberInput(prev => String(Math.min((parseInt(prev) || 0) + 1, event?.max_value || 999)))}
                                    style={{
                                        padding: '12px 20px',
                                        backgroundColor: 'rgba(0, 50, 25, 0.6)',
                                        border: '2px solid #00cc66',
                                        borderRadius: '6px',
                                        color: '#00ff88',
                                        fontFamily: 'monospace',
                                        fontSize: '18px',
                                        fontWeight: 'bold',
                                        cursor: 'pointer',
                                    }}
                                >
                                    +
                                </button>
                            </div>
                        )}

                        {/* Validation Message */}
                        {validationMessage && (
                            <div style={{
                                padding: '8px 12px',
                                backgroundColor: validationSeverity === 'error' ? 'rgba(139, 0, 0, 0.3)' : 'rgba(139, 69, 0, 0.3)',
                                border: `2px solid ${validationSeverity === 'error' ? '#ff4444' : '#ffaa00'}`,
                                borderRadius: '6px',
                                color: validationSeverity === 'error' ? '#ff6666' : '#ffcc66',
                                fontFamily: 'monospace',
                                fontSize: '13px',
                                textAlign: 'center',
                            }}>
                                {validationMessage}
                            </div>
                        )}

                        {/* Submit Button */}
                        <button
                            onClick={handleSubmit}
                            style={{
                                padding: '14px 24px',
                                backgroundColor: 'rgba(0, 102, 51, 0.6)',
                                border: '2px solid #00ff88',
                                borderRadius: '6px',
                                color: '#00ff88',
                                fontFamily: 'monospace',
                                fontSize: '16px',
                                fontWeight: 'bold',
                                cursor: 'pointer',
                                marginTop: '8px',
                                transition: 'all 0.2s',
                            }}
                            onMouseEnter={(e) => {
                                e.target.style.backgroundColor = 'rgba(0, 153, 76, 0.8)'
                                e.target.style.boxShadow = '0 0 15px rgba(0, 255, 136, 0.7)'
                            }}
                            onMouseLeave={(e) => {
                                e.target.style.backgroundColor = 'rgba(0, 102, 51, 0.6)'
                                e.target.style.boxShadow = 'none'
                            }}
                        >
                            Submit {inputType === 'choice' && '(Enter)'}
                        </button>

                        {/* Keyboard shortcuts hint */}
                        {inputType === 'choice' && inputOptions.length > 0 && (
                            <div style={{
                                textAlign: 'center',
                                color: '#666',
                                fontSize: '12px',
                                fontStyle: 'italic',
                                marginTop: '4px',
                            }}>
                                Press 1-{Math.min(inputOptions.length, 9)} to select, Enter to submit
                            </div>
                        )}
                    </div>
                )}

                {/* Continue hint (if no input required) */}
                {!needsInput && isComplete && (
                    <div style={{
                        textAlign: 'center',
                        color: '#666',
                        fontSize: '13px',
                        fontStyle: 'italic',
                        marginTop: '8px',
                    }}>
                        Click anywhere to continue...
                    </div>
                )}

                <style>{`
          @keyframes blink {
            50% { border-color: transparent; }
          }
        `}</style>
            </div>
        </div>
    )
}
