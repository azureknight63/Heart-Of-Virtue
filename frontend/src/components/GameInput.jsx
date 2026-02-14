import { colors, spacing } from '../styles/theme'
import GameText from './GameText'

/**
 * GameInput - A standardized input component with label and error support.
 */
export default function GameInput({
    label,
    error,
    id,
    className = '',
    containerStyle = {},
    style = {},
    ...props
}) {
    const inputStyle = {
        width: '100%',
        backgroundColor: '#1a1a2e',
        border: `2px solid ${error ? colors.danger : colors.primary}`,
        color: error ? colors.danger : colors.primary,
        borderRadius: '4px',
        padding: `${spacing.sm} ${spacing.md}`,
        fontFamily: 'monospace',
        outline: 'none',
        transition: 'all 200ms',
        ...style
    }

    return (
        <div className={`game-input-container ${className}`} style={{ display: 'flex', flexDirection: 'column', gap: spacing.sm, ...containerStyle }}>
            {label && (
                <label htmlFor={id}>
                    <GameText variant="primary" size="sm" weight="bold">
                        {label}
                    </GameText>
                </label>
            )}
            <input
                id={id}
                className="input-field"
                style={inputStyle}
                {...props}
            />
            {error && (
                <GameText variant="danger" size="xs">
                    {error}
                </GameText>
            )}
        </div>
    )
}
