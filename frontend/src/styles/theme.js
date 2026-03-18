/**
 * theme.js - Centralized design tokens and shared style objects
 * Use these constants to maintain visual consistency across the application.
 */

export const colors = {
    // Brand Colors
    primary: '#00ff88',       // Lime Green
    primaryDark: '#00cc66',   // Darker lime for active/hover states
    primaryHover: '#00ffaa',  // Lighter lime for hover effects
    secondary: '#ffaa00',     // Orange
    secondaryHover: '#ffbb00', // Lighter orange for hover effects
    accent: '#00ccff',        // Cyan
    gold: '#ffcc00',          // Gold

    // Semantic Colors
    success: '#00ff88',
    warning: '#ffaa00',
    danger: '#ff4444',
    dangerDark: '#cc0000',    // Darker danger for muted/active states
    dangerHover: '#ff2222',   // Brighter danger for hover effects
    info: '#00ccff',
    special: '#9944ff',       // Purple for special/supernatural moves

    // Pre-computed Alpha Variants (Performance Optimization)
    alpha: {
        primary: {
            10: '#00ff881A',
            20: '#00ff8833',
            30: '#00ff884D',
            40: '#00ff8866',
            60: '#00ff8899',
            80: '#00ff88CC',
        },
        secondary: {
            10: '#ffaa001A',
            20: '#ffaa0033',
            30: '#ffaa004D',
            40: '#ffaa0066',
            60: '#ffaa0099',
            80: '#ffaa00CC',
        },
        danger: {
            10: '#ff44441A',
            20: '#ff444433',
            30: '#ff44444D',
            40: '#ff444466',
            60: '#ff444499',
            80: '#ff4444CC',
        },
        info: {
            10: '#00ccff1A',
            20: '#00ccff33',
            30: '#00ccff4D',
            40: '#00ccff66',
            60: '#00ccff99',
            80: '#00ccffCC',
        },
        special: {
            10: '#9944ff1A',
            20: '#9944ff33',
            30: '#9944ff4D',
            40: '#9944ff66',
            60: '#9944ff99',
            80: '#9944ffCC',
        },
    },

    // Neutral / Background Colors
    text: {
        main: '#e0e0e0',
        muted: '#888888',
        bright: '#ffffff',
        inverse: '#000000',   // Black text for use on bright/light backgrounds
        highlight: '#ffeeaa',
        warning: '#ffcc88',
        danger: '#ffaaaa',
        success: '#ccffcc',
        dim: '#666666',
    },

    bg: {
        main: '#0a0a0a',
        input: '#1a1a2e',     // Input field background
        panel: 'rgba(0, 0, 0, 0.3)',
        panelLight: 'rgba(0, 0, 0, 0.2)',
        panelHeavy: 'rgba(0, 0, 0, 0.7)',
        panelDeep: 'rgba(0, 0, 0, 0.9)',
        overlay: 'rgba(0, 0, 0, 0.75)',
        dialog: 'rgba(20, 10, 0, 0.4)',
        error: '#7f1d1d',
        success: '#064e3b',
        highlight: 'rgba(255, 170, 0, 0.1)',
        highlightLight: 'rgba(255, 170, 0, 0.05)',
        positive: 'rgba(0, 255, 136, 0.1)',
        positiveLight: 'rgba(0, 255, 136, 0.05)',
        negative: 'rgba(255, 68, 68, 0.1)',
        negativeLight: 'rgba(255, 68, 68, 0.05)',
        terminal: 'rgba(0, 255, 136, 0.15)',
        muted: 'rgba(255, 255, 255, 0.05)',
    },

    border: {
        main: 'rgba(255, 170, 0, 0.3)',
        light: 'rgba(255, 170, 0, 0.1)',
        bright: '#ffaa00',
        success: '#00ff88',
        danger: '#ff4444',
    },

    // Entity specific
    entities: {
        npc: '#00ff88',
        item: '#00ccff',
        object: '#ffaa00',
    }
}

export const shadows = {
    main: '0 4px 12px rgba(0, 0, 0, 0.5)',
    glow: '0 0 15px rgba(255, 170, 0, 0.2)',
    inset: 'inset 0 2px 10px rgba(0, 0, 0, 0.5)',
}

export const spacing = {
    xs: '4px',
    sm: '8px',
    md: '12px',
    lg: '16px',
    xl: '20px',
    xxl: '24px',
}

export const fonts = {
    main: "'Courier New', monospace",
    serif: "Georgia, 'Times New Roman', serif",
}

export const commonStyles = {
    typewriterBox: {
        marginTop: spacing.sm,
        padding: spacing.lg,
        backgroundColor: colors.bg.panelHeavy,
        border: `1px solid ${colors.border.main}`,
        borderRadius: '8px',
        color: colors.text.warning,
        fontFamily: fonts.main,
        fontSize: '14px',
        lineHeight: '1.6',
        whiteSpace: 'pre-wrap',
        maxHeight: '200px',
        overflowY: 'auto',
        boxShadow: shadows.inset,
        position: 'relative',
    },
    errorBox: {
        color: colors.danger,
        fontSize: '13px',
        padding: '10px',
        backgroundColor: 'rgba(255, 68, 68, 0.1)',
        borderRadius: '6px',
        border: `1px solid rgba(255, 68, 68, 0.3)`,
        fontFamily: fonts.main,
    },
    infoCard: {
        backgroundColor: 'rgba(0, 0, 0, 0.3)',
        border: `1px solid ${colors.border.light}`,
        borderRadius: '6px',
        padding: spacing.lg,
        overflowY: 'auto',
        color: colors.warning,
        fontSize: '15px',
        fontFamily: fonts.main,
        lineHeight: '1.6',
        display: 'flex',
        flexDirection: 'column',
        gap: spacing.md,
    }
}

export default {
    colors,
    shadows,
    spacing,
    fonts,
    commonStyles
}
