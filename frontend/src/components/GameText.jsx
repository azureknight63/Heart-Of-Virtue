import { colors, fonts } from '../styles/theme'

/**
 * GameText - A standardized text component with variants.
 */
export default function GameText({
    children,
    variant = 'main', // 'main', 'muted', 'bright', 'highlight', 'warning', 'danger', 'success', 'dim', 'accent'
    size = 'md',      // 'xs', 'sm', 'md', 'lg', 'xl', 'xxl'
    weight = 'normal',
    align = 'left',
    className = '',
    style = {},
    as: Component = 'p',
    ...props
}) {
    const colorMap = {
        main: colors.text.main,
        muted: colors.text.muted,
        bright: colors.text.bright,
        highlight: colors.text.highlight,
        warning: colors.text.warning,
        danger: colors.text.danger,
        success: colors.text.success,
        dim: colors.text.dim,
        accent: colors.accent,
        primary: colors.primary,
        secondary: colors.secondary
    }

    const sizeMap = {
        xs: '0.75rem',
        sm: '0.875rem',
        md: '1rem',
        lg: '1.25rem',
        xl: '1.5rem',
        xxl: '2.25rem'
    }

    const textStyle = {
        color: colorMap[variant] || colors.text.main,
        fontSize: sizeMap[size] || sizeMap.md,
        fontWeight: weight,
        textAlign: align,
        fontFamily: variant === 'accent' || variant === 'primary' ? fonts.main : 'inherit',
        margin: 0,
        ...style
    }

    return (
        <Component className={`game-text ${className}`} style={textStyle} {...props}>
            {children}
        </Component>
    )
}
