import React, { useState } from 'react';

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
    const [isHovered, setIsHovered] = useState(false);

    const variants = {
        primary: {
            color: '#000000',
            backgroundColor: '#00ff88',
            borderColor: '#00ff88',
            hoverBg: '#00ffaa',
            hoverShadow: '0 0 8px #00ff88',
        },
        secondary: {
            color: '#00ccff',
            backgroundColor: 'transparent',
            borderColor: '#00ccff',
            hoverBg: 'rgba(0, 204, 255, 0.2)',
            hoverShadow: 'none',
        },
        danger: {
            color: '#ffff00',
            backgroundColor: '#cc0000',
            borderColor: '#ff0000',
            hoverBg: '#ff0000',
            hoverShadow: '0 0 10px #ff0000',
        },
        warning: {
            color: '#ffff00',
            backgroundColor: '#cc4400',
            borderColor: '#ff6600',
            hoverBg: '#ff6600',
            hoverShadow: '0 0 8px rgba(255, 102, 0, 0.8)',
        },
    };

    const sizes = {
        small: { padding: '4px 8px', fontSize: '12px' },
        medium: { padding: '8px 16px', fontSize: '14px' },
        large: { padding: '12px 24px', fontSize: '16px' },
    };

    const currentVariant = variants[variant] || variants.secondary;
    const currentSize = sizes[size] || sizes.medium;

    const baseStyle = {
        borderRadius: '4px',
        border: `2px solid ${currentVariant.borderColor}`,
        backgroundColor: isHovered ? currentVariant.hoverBg : currentVariant.backgroundColor,
        color: currentVariant.color,
        boxShadow: isHovered ? currentVariant.hoverShadow : 'none',
        cursor: disabled ? 'not-allowed' : 'pointer',
        fontFamily: 'monospace',
        fontWeight: 'bold',
        transition: 'all 0.2s',
        opacity: disabled ? 0.6 : 1,
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        ...currentSize,
        ...style,
    };

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
    );
}
