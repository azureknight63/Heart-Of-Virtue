import { colors, shadows, spacing } from '../styles/theme'

/**
 * GamePanel - A standardized container component with retro styling.
 */
export default function GamePanel({
    children,
    className = '',
    style = {},
    padding = 'large',
    glow = true,
    borderVariant = 'main' // 'main', 'light', 'bright', 'success', 'danger'
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
        ...style
    }

    return (
        <div className={`game-panel ${glow ? 'retro-glow' : ''} ${className}`} style={panelStyle}>
            {children}
        </div>
    )
}
