import { colors, shadows, spacing } from '../styles/theme'

/**
 * GamePanel - A standardized container component with retro styling.
 */
export default function GamePanel({
    children,
    title,
    className = '',
    style = {},
    padding = 'large',
    glow = true,
    borderVariant = 'main', // 'main', 'light', 'bright', 'success', 'danger'
    onClose
}) {
    const paddingValues = {
        none: '0',
        small: spacing.sm,
        medium: spacing.md,
        large: spacing.lg,
        xl: spacing.xl
    }

    const panelStyle = {
        backgroundColor: colors.bg.panel,
        border: `2px solid ${colors.border[borderVariant] || colors.border.main}`,
        borderRadius: '8px',
        padding: paddingValues[padding] || paddingValues.large,
        boxShadow: glow ? shadows.glow : shadows.main,
        fontFamily: '"Courier New", monospace',
        ...style
    }

    return (
        <div className={`game-panel border rounded p-lg bg-neutral-900 ${glow ? 'retro-glow' : ''} ${className}`} style={panelStyle}>
            {title && (
                <div style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    marginBottom: spacing.md,
                    paddingBottom: spacing.md,
                    borderBottom: `1px solid ${colors.border.main}`
                }}>
                    <h2 style={{
                        margin: 0,
                        fontWeight: 'bold',
                        textAlign: 'center',
                        flex: 1,
                        color: colors.text.primary
                    }}>
                        {title}
                    </h2>
                    {onClose && (
                        <button
                            onClick={onClose}
                            style={{
                                background: 'none',
                                border: 'none',
                                color: colors.text.primary,
                                cursor: 'pointer',
                                fontSize: '16px',
                                padding: '0 4px',
                                marginLeft: spacing.sm
                            }}
                        >
                            ✕
                        </button>
                    )}
                </div>
            )}
            {!title && onClose && (
                <div style={{ position: 'absolute', top: spacing.sm, right: spacing.sm }}>
                    <button
                        onClick={onClose}
                        style={{
                            background: 'none',
                            border: 'none',
                            color: colors.text.primary,
                            cursor: 'pointer',
                            fontSize: '16px',
                            padding: '0 4px'
                        }}
                    >
                        ✕
                    </button>
                </div>
            )}
            <div style={{ position: 'relative' }}>
                {children}
            </div>
        </div>
    )
}
