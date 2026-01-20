import { colors, spacing } from '../styles/theme'

/**
 * BaseDialog - A reusable dialog component to reduce DRY violations in modals.
 */
export default function BaseDialog({
    children,
    title,
    onClose,
    variant = 'default', // 'default', 'danger', 'warning'
    maxWidth = '400px',
    zIndex = 1000,
    showCloseButton = true,
    padding = spacing.xl,
    className = '',
    contentClassName = '',
}) {
    const isDanger = variant === 'danger'
    const isWarning = variant === 'warning'

    const themeStyles = {
        borderColor: isDanger ? colors.danger : (isWarning ? colors.secondary : colors.primary),
        backgroundColor: isDanger ? 'rgba(25, 10, 10, 0.98)' : (isWarning ? 'rgba(30, 15, 0, 0.95)' : colors.bg.main),
        glowColor: isDanger ? 'rgba(204, 0, 0, 0.6)' : (isWarning ? 'rgba(255, 170, 0, 0.5)' : colors.primary),
        titleColor: isDanger ? '#ff5555' : (isWarning ? colors.gold : colors.primary),
        overlayColor: 'rgba(0, 0, 0, 0.7)',
    }

    return (
        <div
            className={`modal-overlay ${className}`}
            style={{
                position: 'fixed',
                top: 0,
                left: 0,
                right: 0,
                bottom: 0,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                zIndex,
                backgroundColor: themeStyles.overlayColor,
                backdropFilter: 'blur(3px)',
            }}
            onClick={onClose}
        >
            <div
                className={`modal-content ${contentClassName}`}
                role="dialog"
                aria-modal="true"
                aria-labelledby={title ? "base-dialog-title" : undefined}
                style={{
                    maxWidth,
                    width: '90%',
                    backgroundColor: themeStyles.backgroundColor,
                    border: `3px solid ${themeStyles.borderColor}`,
                    borderRadius: '8px',
                    padding: padding,
                    boxShadow: `0 0 20px ${themeStyles.glowColor}66`,
                    fontFamily: 'monospace',
                    display: 'flex',
                    flexDirection: 'column',
                    maxHeight: '90vh',
                }}
                onClick={(e) => e.stopPropagation()}
            >
                {(title || showCloseButton) && (
                    <div
                        style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center',
                            borderBottom: `2px solid ${themeStyles.borderColor}44`,
                            paddingBottom: spacing.sm,
                            marginBottom: spacing.md,
                        }}
                    >
                        {title && (
                            <div
                                id="base-dialog-title"
                                style={{
                                    fontSize: '20px',
                                    fontWeight: 'bold',
                                    color: themeStyles.titleColor,
                                    textAlign: 'center',
                                    flex: 1,
                                    textTransform: 'uppercase',
                                    letterSpacing: '1px'
                                }}
                            >
                                {title}
                            </div>
                        )}
                        {showCloseButton && (
                            <button
                                onClick={onClose}
                                style={{
                                    background: 'none',
                                    border: 'none',
                                    color: colors.text.muted,
                                    cursor: 'pointer',
                                    fontSize: '22px',
                                    marginLeft: spacing.sm,
                                    padding: '4px',
                                    transition: 'color 0.2s'
                                }}
                                onMouseEnter={(e) => e.target.style.color = colors.text.highlight}
                                onMouseLeave={(e) => e.target.style.color = colors.text.muted}
                            >
                                ✕
                            </button>
                        )}
                    </div>
                )}

                <div style={{ flex: 1, overflowY: 'auto' }}>
                    {children}
                </div>
            </div>
        </div>
    )
}
