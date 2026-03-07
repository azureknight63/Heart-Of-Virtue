import { useState } from 'react'
import { colors, spacing } from '../styles/theme'

/**
 * GameButton - A standardized button component for the Heart of Virtue UI.
 */
export default function GameButton({
    children,
    onClick,
    variant = 'secondary', // 'primary', 'secondary', 'danger', 'warning'
    size = 'medium',       // 'small', 'medium', 'large'
    disabled = false,
    style = {},
    className = '',
    title = '',
}) {
    const [isHovered, setIsHovered] = useState(false)

    const variants = {
        primary: {
            color: '#000000',
            backgroundColor: colors.primary,
            borderColor: colors.primary,
            hoverBg: '#00ffaa',
            hoverShadow: `0 0 12px ${colors.primary}aa`,
        },
        secondary: {
            color: colors.text.highlight,
            backgroundColor: 'transparent',
            borderColor: colors.text.highlight,
            hoverBg: `${colors.text.highlight}22`,
            hoverShadow: 'none',
        },
        danger: {
            color: '#ffffff',
            backgroundColor: colors.danger,
            borderColor: colors.danger,
            hoverBg: '#ff2222',
            hoverShadow: `0 0 12px ${colors.danger}aa`,
        },
        warning: {
            color: '#000000',
            backgroundColor: colors.secondary,
            borderColor: colors.secondary,
            hoverBg: '#ffbb00',
            hoverShadow: `0 0 10px ${colors.secondary}aa`,
        },
    }

    const sizes = {
        small: { padding: '4px 8px', fontSize: '11px' },
        medium: { padding: '8px 16px', fontSize: '13px' },
        large: { padding: '12px 24px', fontSize: '15px' },
    }

    const currentVariant = variants[variant] || variants.secondary
    const currentSize = sizes[size] || sizes.medium

    const baseStyle = {
        borderRadius: '6px',
        border: `2px solid ${currentVariant.borderColor}`,
        backgroundColor: isHovered && !disabled ? currentVariant.hoverBg : currentVariant.backgroundColor,
        color: currentVariant.color,
        boxShadow: isHovered && !disabled ? currentVariant.hoverShadow : 'none',
        cursor: disabled ? 'not-allowed' : 'pointer',
        fontFamily: 'monospace',
        fontWeight: 'bold',
        transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
        opacity: disabled ? 0.5 : 1,
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        textTransform: 'uppercase',
        letterSpacing: '0.5px',
        ...currentSize,
        ...style,
    }

    return (
        <button
            onClick={disabled ? undefined : onClick}
            onMouseEnter={() => !disabled && setIsHovered(true)}
            onMouseLeave={() => setIsHovered(false)}
            disabled={disabled}
            style={baseStyle}
            className={`game-btn ${className}`}
            title={title}
        >
            {children}
        </button>
    )
}
