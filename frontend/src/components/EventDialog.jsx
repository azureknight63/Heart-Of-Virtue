import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react'
import BaseDialog from './BaseDialog'
import GameButton from './GameButton'
import GameText from './GameText'
import GameInput from './GameInput'
import TypewriterOutput from './TypewriterOutput'
import { colors, spacing, commonStyles, fonts } from '../styles/theme'
import { cleanTerminalLineBreaks } from '../utils/entityUtils'

/**
 * EventDialog - Displays event output text and handles player input for events
 * Supports choice selection, text input, and number input with keyboard shortcuts
 */
function EventDialog({ event, history = [], onClose, onSubmitInput }) {
    const [isComplete, setIsComplete] = useState(false)
    const [showInput, setShowInput] = useState(false)
    const [showHistory, setShowHistory] = useState(false)
    const [textInput, setTextInput] = useState('')
    const [numberInput, setNumberInput] = useState('')
    const [validationMessage, setValidationMessage] = useState('')
    const [validationSeverity, setValidationSeverity] = useState('') // 'warning' or 'error'
    const [selectedChoice, setSelectedChoice] = useState(null)
    const [isSubmitting, setIsSubmitting] = useState(false)

    const inputRef = useRef(null)
    const dialogRef = useRef(null)

    // Earthbound-style damage effect: shake screen + red flash
    const handleDamageHit = useCallback(() => {
        document.body.classList.add('damage-shake', 'damage-flash-active')
        setTimeout(() => {
            document.body.classList.remove('damage-shake', 'damage-flash-active')
        }, 500)
    }, [])

    // Remove body classes if dialog unmounts mid-animation
    useEffect(() => {
        return () => {
            document.body.classList.remove('damage-shake', 'damage-flash-active')
        }
    }, [])

    // Extract event data
    const rawText = event?.output_text || event?.message || event?.description || ''
    // Memoize text cleaning to avoid recomputing 3-pass regex on every render
    const eventText = useMemo(() => {
        if (event?.is_death_scene || !rawText) return rawText
        return cleanTerminalLineBreaks(rawText)
    }, [rawText, event?.is_death_scene])
    const needsInput = event?.needs_input || false
    const inputType = event?.input_type || 'choice'
    const inputPrompt = event?.input_prompt || 'Your choice:'
    const inputOptions = event?.input_options || []
    const eventId = event?.event_id
    const isDeathScene = event?.is_death_scene || false

    useEffect(() => {
        // Death scenes show all text at once — mark complete immediately so the
        // Close button appears without waiting for a (non-existent) typewriter.
        setIsComplete(isDeathScene)
        setShowInput(false)
        setTextInput('')
        setNumberInput('')
        setValidationMessage('')
        setSelectedChoice(null)
        setIsSubmitting(false)
    }, [eventText, needsInput, isDeathScene])

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
            if (isSubmitting) return

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
    }, [showInput, inputType, inputOptions, textInput, numberInput, selectedChoice, isSubmitting])

    const handleChoiceSelect = (value) => {
        if (isSubmitting) return
        setIsSubmitting(true)
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
            const maxLength = event?.input_max_length ?? 500
            if (!trimmed) {
                setValidationMessage('Input cannot be empty')
                setValidationSeverity('error')
                return false
            }
            if (trimmed.length > maxLength) {
                setValidationMessage(`Input too long (${trimmed.length}/${maxLength} characters)`)
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
            const minValue = event?.input_min ?? event?.min_value
            const maxValue = event?.input_max ?? event?.max_value
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
        if (isSubmitting) return
        if (!validateInput()) return

        setIsSubmitting(true)
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
    const charLimit = event?.input_max_length ?? 500
    const charCountColor = charCount > charLimit ? colors.danger : charCount > charLimit * 0.9 ? colors.warning : colors.text.muted

    const handleGlobalInteraction = () => {
        if (isSubmitting) return
        if (isComplete && !needsInput) {
            setIsSubmitting(true)
            onClose()
        }
    }

    const dialogTitle = `✨ ${(!event?.name || event.name === event.type || /^[A-Z][a-z]+([A-Z][a-z]+)+$/.test(event.name) || event.name.includes('_')) ? 'Event' : event.name}`

    // Use wider dialog for memory events due to pre-formatted text
    const isMemoryEvent = /memory|flash/i.test(event?.type || '') ||
        /memory|flash/i.test(event?.name || '') ||
        /MEMORY STIRS/i.test(eventText)
    const dialogMaxWidth = isDeathScene ? '1100px' : isMemoryEvent ? '900px' : '800px'
    const dialogWidth = isDeathScene ? '98%' : isMemoryEvent ? '95%' : '90%'

    return (
        <BaseDialog
            title={dialogTitle}
            onClose={handleGlobalInteraction}
            showCloseButton={!needsInput}
            zIndex={3000}
            maxWidth={dialogMaxWidth}
            width={dialogWidth}
            allowInternalScroll={false}
        >
            <div
                ref={dialogRef}
                className="event-dialog-body"
                tabIndex={-1}
                onClick={handleGlobalInteraction}
                style={{
                    display: 'flex',
                    flexDirection: 'column',
                    gap: spacing.lg,
                    outline: 'none',
                    height: '100%',
                    maxHeight: '75vh', // Keep dialog from getting too tall
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
                                border: `1px solid ${colors.border.success}`,
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
                            <GameText variant="primary" size="xs" weight="bold">
                                {showHistory ? '↩ Back' : `📜 Log (${history.length})`}
                            </GameText>
                        </button>
                    </div>
                )}

                {/* Event Text Output / History View */}
                {showHistory ? (
                    <div
                        onClick={(e) => e.stopPropagation()}
                        style={{
                            padding: spacing.md,
                            backgroundColor: colors.bg.panelDeep,
                            border: `2px dashed ${colors.border.light}`,
                            borderRadius: '10px',
                            flex: 1,
                            overflowY: 'auto',
                            display: 'flex',
                            flexDirection: 'column',
                            gap: spacing.md,
                        }}
                        ref={(el) => {
                            if (el) el.scrollTop = el.scrollHeight;
                        }}
                    >
                        {history.map((text, idx) => (
                            <div key={idx} style={{
                                paddingBottom: idx === history.length - 1 ? '0' : spacing.lg,
                                borderBottom: idx === history.length - 1 ? 'none' : `1px solid ${colors.border.light}`,
                                whiteSpace: 'pre',
                                opacity: idx === history.length - 1 ? 1 : 0.6
                            }}>
                                <GameText variant="muted" size="xs" style={{ display: 'inline', marginRight: spacing.sm }}>
                                    [{idx + 1}]
                                </GameText>
                                <GameText variant="success" size="md" style={{ display: 'inline' }}>
                                    {text}
                                </GameText>
                            </div>
                        ))}
                    </div>
                ) : isDeathScene ? (
                    /* Death scene: show all at once, bright red, monospace pre-aligned, with glow */
                    <div
                        style={{
                            padding: spacing.lg,
                            flex: 1,
                            overflowX: 'auto',
                            overflowY: 'auto',
                            maxHeight: '500px',
                            background: 'rgba(20, 0, 0, 0.92)',
                            border: '2px solid #660000',
                            borderRadius: '8px',
                            boxShadow: 'inset 0 0 40px rgba(180, 0, 0, 0.25), 0 0 20px rgba(150, 0, 0, 0.4)',
                        }}
                    >
                        <pre style={{
                            margin: 0,
                            color: '#ff2222',
                            fontFamily: 'monospace',
                            fontSize: '13px',
                            lineHeight: '1.4',
                            whiteSpace: 'pre',
                            textShadow: '0 0 8px rgba(255, 50, 50, 0.9), 0 0 20px rgba(200, 0, 0, 0.6)',
                        }}>
                            {eventText}
                        </pre>
                    </div>
                ) : (
                    <TypewriterOutput
                        text={eventText}
                        speed={25}
                        onComplete={() => {
                            setIsComplete(true)
                            if (needsInput) setShowInput(true)
                        }}
                        onDamageHit={handleDamageHit}
                        style={{
                            padding: spacing.lg,
                            flex: 1,
                            maxHeight: '450px',
                            overflowY: 'auto',
                            border: `2px solid ${colors.secondary}`,
                            color: colors.success,
                            whiteSpace: isMemoryEvent ? 'pre' : 'pre-wrap',
                            fontSize: '16px',
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
                        <GameText variant="primary" size="sm" weight="bold" align="center" style={{ marginBottom: spacing.xs }}>
                            {inputPrompt}
                        </GameText>

                        {/* Choice Buttons */}
                        {inputType === 'choice' && inputOptions.length > 0 && (
                            <div style={{
                                display: 'grid',
                                gridTemplateColumns: inputOptions.length <= 3 ? '1fr' : 'repeat(2, 1fr)',
                                gap: spacing.md,
                            }}>
                                {inputOptions.map((option, idx) => {
                                    const isSelected = selectedChoice === option.value
                                    const keyBinding = idx < 9 ? `[${idx + 1}] ` : ''

                                    return (
                                        <GameButton
                                            key={idx}
                                            onClick={() => handleChoiceSelect(option.value)}
                                            variant={isSelected ? 'primary' : 'secondary'}
                                            disabled={isSubmitting}
                                            style={{
                                                padding: '14px 20px',
                                                fontSize: '15px',
                                                backgroundColor: isSelected ? 'rgba(0, 102, 51, 0.4)' : 'rgba(0, 50, 25, 0.2)',
                                                opacity: isSubmitting ? 0.6 : 1,
                                            }}
                                        >
                                            <span style={{ color: colors.secondary, marginRight: spacing.sm }}>{keyBinding}</span>
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
                                        padding: spacing.md,
                                        backgroundColor: colors.bg.panelDeep,
                                        border: `2px solid ${colors.border.light}`,
                                        borderRadius: '6px',
                                        color: colors.text.main,
                                        fontFamily: fonts.main,
                                        fontSize: '14px',
                                        minHeight: '100px',
                                        resize: 'vertical',
                                        outline: 'none',
                                    }}
                                />
                                <GameText variant="muted" size="xs" align="right" style={{ color: charCountColor }}>
                                    {charCount}/{charLimit} characters
                                </GameText>
                            </div>
                        )}

                        {/* Number Input */}
                        {inputType === 'number' && (
                            <div style={{ display: 'flex', gap: spacing.sm, alignItems: 'center' }}>
                                <GameButton
                                    onClick={() => setNumberInput(prev => String(Math.max((parseInt(prev) || 0) - 1, event?.min_value || 0)))}
                                    size="large"
                                >
                                    -
                                </GameButton>
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
                                        padding: spacing.md,
                                        backgroundColor: colors.bg.panelDeep,
                                        border: `2px solid ${colors.border.light}`,
                                        borderRadius: '6px',
                                        color: colors.text.main,
                                        fontFamily: fonts.main,
                                        fontSize: '16px',
                                        textAlign: 'center',
                                        outline: 'none',
                                    }}
                                />
                                <GameButton
                                    onClick={() => setNumberInput(prev => String(Math.min((parseInt(prev) || 0) + 1, event?.max_value || 999)))}
                                    size="large"
                                >
                                    +
                                </GameButton>
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
                                <GameText variant={validationSeverity === 'error' ? 'danger' : 'warning'} size="sm">
                                    {validationMessage}
                                </GameText>
                            </div>
                        )}

                        {/* Submit Button - Only show for non-choice inputs */}
                        {inputType !== 'choice' && (
                            <GameButton
                                onClick={handleSubmit}
                                variant="primary"
                                disabled={isSubmitting}
                                style={{
                                    marginTop: spacing.sm,
                                }}
                            >
                                {isSubmitting ? 'Submitting...' : 'Submit'}
                            </GameButton>
                        )}

                        {/* Keyboard shortcuts hint */}
                        {inputType === 'choice' && inputOptions.length > 0 && (
                            <GameText variant="muted" size="xs" align="center" style={{ fontStyle: 'italic', marginTop: spacing.xs }}>
                                Press 1-{Math.min(inputOptions.length, 9)} to select
                            </GameText>
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
                            onClick={handleGlobalInteraction}
                            variant="secondary"
                            disabled={isSubmitting}
                            style={{
                                padding: '10px 40px',
                            }}
                        >
                            {isSubmitting ? 'Closing...' : 'Close'}
                        </GameButton>
                        <GameText variant="muted" size="sm" style={{ fontStyle: 'italic' }}>
                            or click anywhere to continue...
                        </GameText>
                    </div>
                )}
            </div>
        </BaseDialog>
    )
}

export default React.memo(EventDialog)
