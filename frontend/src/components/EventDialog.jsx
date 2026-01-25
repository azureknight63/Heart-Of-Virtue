import { useState, useEffect, useRef } from 'react'
import BaseDialog from './BaseDialog'
import GameButton from './GameButton'
import TypewriterOutput from './TypewriterOutput'
import { colors, spacing, commonStyles } from '../styles/theme'

/**
 * EventDialog - Displays event output text and handles player input for events
 * Supports choice selection, text input, and number input with keyboard shortcuts
 */
export default function EventDialog({ event, history = [], onClose, onSubmitInput }) {
    const [isComplete, setIsComplete] = useState(false)
    const [showInput, setShowInput] = useState(false)
    const [showHistory, setShowHistory] = useState(false)
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
        setIsComplete(false)
        setShowInput(false)
        setTextInput('')
        setNumberInput('')
        setValidationMessage('')
        setSelectedChoice(null)
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

    const handleChoiceSelect = (value) => {
        setSelectedChoice(value)
        setValidationMessage('')
        // Submit immediately for choice type as per user request
        if (onSubmitInput && eventId) {
            onSubmitInput(eventId, value)
        }
    }

    const validateInput = () => {
        setValidationMessage('')

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

    // Character counter for text input
    const charCount = textInput.length
    const charLimit = 500
    const charCountColor = charCount > charLimit ? colors.danger : charCount > charLimit * 0.9 ? colors.warning : colors.text.muted

    const handleGlobalInteraction = () => {
        if (isComplete && !needsInput) {
            onClose()
        }
    }

    return (
        <BaseDialog
            title={`✨ ${(!event?.name || event.name === event.type || /^[A-Z][a-z]+([A-Z][a-z]+)+$/.test(event.name) || event.name.includes('_')) ? 'Event' : event.name}`}
            onClose={handleGlobalInteraction}
            showCloseButton={!needsInput}
            zIndex={2000}
            maxWidth="700px"
        >
            <div
                ref={dialogRef}
                tabIndex={-1}
                onClick={handleGlobalInteraction}
                style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: spacing.lg,
                    outline: 'none',
                    height: '100%',
                }}
            >
                {/* Event History Toggle (only if multiple messages) */}
                {history.length > 1 && (
                    <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: `-${spacing.sm}` }}>
                        <button
                            onClick={(e) => {
                                e.stopPropagation();
                                setShowHistory(!showHistory);
                            }}
                            style={{
                                background: 'rgba(0, 204, 102, 0.1)',
                                border: '1px solid rgba(0, 204, 102, 0.4)',
                                color: colors.primary,
                                fontSize: '11px',
                                fontWeight: 'bold',
                                cursor: 'pointer',
                                padding: '4px 12px',
                                borderRadius: '4px',
                                textTransform: 'uppercase',
                                transition: 'all 0.2s ease',
                                display: 'flex',
                                alignItems: 'center',
                                gap: '6px'
                            }}
                        >
                            {showHistory ? '↩ Back to Present' : `📜 View Log (${history.length})`}
                        </button>
                    </div>
                )}

                {/* Event Text Output / History View */}
                {showHistory ? (
                    <div
                        onClick={(e) => e.stopPropagation()}
                        style={{
                            padding: '20px',
                            backgroundColor: 'rgba(0, 0, 0, 0.8)',
                            border: `2px dashed ${colors.primary}`,
                            borderRadius: '10px',
                            color: '#88ffcc',
                            fontFamily: 'monospace',
                            fontSize: '15px',
                            lineHeight: '1.8',
                            height: '350px',
                            overflowY: 'auto',
                            boxShadow: 'inset 0 0 20px rgba(0,0,0,1)',
                            display: 'flex',
                            flexDirection: 'column',
                            gap: '20px',
                            scrollbarWidth: 'thin',
                            scrollbarColor: `${colors.primary} rgba(0,0,0,0.5)`
                        }}
                        ref={(el) => {
                            if (el) el.scrollTop = el.scrollHeight;
                        }}
                    >
                        {history.map((text, idx) => (
                            <div key={idx} style={{
                                paddingBottom: idx === history.length - 1 ? '0' : '20px',
                                borderBottom: idx === history.length - 1 ? 'none' : '1px solid rgba(0, 204, 102, 0.2)',
                                whiteSpace: 'pre-wrap',
                                opacity: idx === history.length - 1 ? 1 : 0.6
                            }}>
                                <span style={{ color: colors.primary, marginRight: '10px', fontSize: '12px' }}>[{idx + 1}]</span>
                                {text}
                            </div>
                        ))}
                    </div>
                ) : (
                    <TypewriterOutput
                        text={eventText}
                        speed={50}
                        onComplete={() => {
                            setIsComplete(true)
                            if (needsInput) setShowInput(true)
                        }}
                        style={{
                            padding: '20px',
                            fontSize: '16px',
                            minHeight: '120px',
                            borderWidth: '2px',
                            borderColor: colors.primary,
                            color: '#88ffcc',
                        }}
                    />
                )}

                {/* Input Section */}
                {showInput && needsInput && (
                    <div style={{
                        display: 'flex',
                        flexDirection: 'column',
                        gap: spacing.md,
                        marginTop: spacing.sm,
                    }}>
                        {/* Input Prompt */}
                        <div style={{
                            color: colors.primary,
                            fontWeight: 'bold',
                            fontSize: '14px',
                            fontFamily: 'monospace',
                            textAlign: 'center',
                            marginBottom: spacing.xs,
                        }}>
                            {inputPrompt}
                        </div>

                        {/* Choice Buttons */}
                        {inputType === 'choice' && inputOptions.length > 0 && (
                            <div style={{
                                display: 'grid',
                                gridTemplateColumns: inputOptions.length <= 3 ? '1fr' : 'repeat(2, 1fr)',
                                gap: spacing.md,
                            }}>
                                {inputOptions.map((option, idx) => {
                                    const isSelected = selectedChoice === option.value
                                    const keyBinding = idx < 9 ? `[${idx + 1}]` : ''

                                    return (
                                        <GameButton
                                            key={idx}
                                            onClick={() => handleChoiceSelect(option.value)}
                                            variant={isSelected ? 'primary' : 'secondary'}
                                            style={{
                                                padding: '14px 20px',
                                                fontSize: '15px',
                                                borderColor: isSelected ? colors.primary : '#00cc66',
                                                backgroundColor: isSelected ? 'rgba(0, 102, 51, 0.6)' : 'rgba(0, 50, 25, 0.4)',
                                                color: '#88ffcc',
                                            }}
                                        >
                                            {keyBinding && <span style={{ color: colors.secondary, marginRight: '8px' }}>{keyBinding}</span>}
                                            {option.label}
                                        </GameButton>
                                    )
                                })}
                            </div>
                        )}

                        {/* Text Input */}
                        {inputType === 'text' && (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.sm }}>
                                <textarea
                                    ref={inputRef}
                                    value={textInput}
                                    onChange={(e) => setTextInput(e.target.value)}
                                    placeholder="Enter your text here..."
                                    maxLength={500}
                                    style={{
                                        padding: '12px',
                                        backgroundColor: 'rgba(0, 0, 0, 0.7)',
                                        border: `2px solid ${colors.primary}`,
                                        borderRadius: '6px',
                                        color: '#88ffcc',
                                        fontFamily: 'monospace',
                                        fontSize: '14px',
                                        minHeight: '100px',
                                        resize: 'vertical',
                                        outline: 'none',
                                    }}
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
                            <div style={{ display: 'flex', gap: spacing.sm, alignItems: 'center' }}>
                                <button
                                    onClick={() => setNumberInput(prev => String(Math.max((parseInt(prev) || 0) - 1, event?.min_value || 0)))}
                                    style={{
                                        padding: '12px 20px',
                                        backgroundColor: 'rgba(0, 50, 25, 0.6)',
                                        border: `2px solid ${colors.primary}`,
                                        borderRadius: '6px',
                                        color: colors.primary,
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
                                        border: `2px solid ${colors.primary}`,
                                        borderRadius: '6px',
                                        color: '#88ffcc',
                                        fontFamily: 'monospace',
                                        fontSize: '16px',
                                        textAlign: 'center',
                                        outline: 'none',
                                    }}
                                />
                                <button
                                    onClick={() => setNumberInput(prev => String(Math.min((parseInt(prev) || 0) + 1, event?.max_value || 999)))}
                                    style={{
                                        padding: '12px 20px',
                                        backgroundColor: 'rgba(0, 50, 25, 0.6)',
                                        border: `2px solid ${colors.primary}`,
                                        borderRadius: '6px',
                                        color: colors.primary,
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
                                ...commonStyles.errorBox,
                                color: validationSeverity === 'error' ? colors.danger : colors.warning,
                                borderColor: validationSeverity === 'error' ? colors.danger : colors.warning,
                                textAlign: 'center',
                            }}>
                                {validationMessage}
                            </div>
                        )}

                        {/* Submit Button - Only show for non-choice inputs */}
                        {inputType !== 'choice' && (
                            <GameButton
                                onClick={handleSubmit}
                                variant="primary"
                                style={{
                                    padding: '14px 24px',
                                    fontSize: '16px',
                                    marginTop: spacing.sm,
                                }}
                            >
                                Submit
                            </GameButton>
                        )}

                        {/* Keyboard shortcuts hint */}
                        {inputType === 'choice' && inputOptions.length > 0 && (
                            <div style={{
                                textAlign: 'center',
                                color: colors.text.muted,
                                fontSize: '12px',
                                fontStyle: 'italic',
                                marginTop: spacing.xs,
                            }}>
                                Press 1-{Math.min(inputOptions.length, 9)} to select
                            </div>
                        )}
                    </div>
                )}

                {/* Continue hint (if no input required) */}
                {!needsInput && isComplete && (
                    <div style={{
                        textAlign: 'center',
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        gap: spacing.md,
                        marginTop: spacing.lg,
                    }}>
                        <GameButton
                            onClick={onClose}
                            variant="secondary"
                            style={{ padding: '10px 30px' }}
                        >
                            Close
                        </GameButton>
                        <div style={{
                            color: colors.text.muted,
                            fontSize: '13px',
                            fontStyle: 'italic',
                        }}>
                            or click anywhere to continue...
                        </div>
                    </div>
                )}
            </div>
        </BaseDialog>
    )
}
