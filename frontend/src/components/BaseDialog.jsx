import React from 'react';

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
    className = '',
    contentClassName = '',
}) {
    const isDanger = variant === 'danger';
    const isWarning = variant === 'warning';

    const theme = {
        borderColor: isDanger ? '#cc0000' : (isWarning ? '#ffaa00' : '#00ff88'),
        backgroundColor: isDanger ? 'rgba(25, 10, 10, 0.98)' : (isWarning ? 'rgba(30, 15, 0, 0.95)' : '#1a1a2e'),
        glowColor: isDanger ? 'rgba(204, 0, 0, 0.6)' : (isWarning ? 'rgba(255, 170, 0, 0.5)' : '#00ff88'),
        titleColor: isDanger ? '#ff5555' : (isWarning ? '#ffff00' : '#00ff88'),
        overlayColor: isDanger ? 'rgba(0, 0, 0, 0.9)' : (isWarning ? 'rgba(0, 0, 0, 0.7)' : 'rgba(0, 0, 0, 0.7)'),
    };

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
                backgroundColor: theme.overlayColor,
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
                    backgroundColor: theme.backgroundColor,
                    border: `3px solid ${theme.borderColor}`,
                    borderRadius: '8px',
                    padding: '24px',
                    boxShadow: `0 0 20px ${theme.glowColor}`,
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
                            borderBottom: `2px solid ${theme.borderColor}`,
                            paddingBottom: '10px',
                            marginBottom: '20px',
                        }}
                    >
                        {title && (
                            <div
                                id="base-dialog-title"
                                style={{
                                    fontSize: '20px',
                                    fontWeight: 'bold',
                                    color: theme.titleColor,
                                    textAlign: 'center',
                                    flex: 1,
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
                                    color: '#888',
                                    cursor: 'pointer',
                                    fontSize: '20px',
                                    marginLeft: '10px',
                                    padding: '4px',
                                }}
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
    );
}
