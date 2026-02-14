import React, { createContext, useContext, useState, useCallback } from 'react';
import { colors, spacing } from '../styles/theme';

const ToastContext = createContext();

export const useToast = () => {
    const context = useContext(ToastContext);
    if (!context) {
        throw new Error('useToast must be used within a ToastProvider');
    }
    return context;
};

/**
 * ToastProvider - Provides toast notification functionality throughout the app
 * Replaces native alert() calls with non-blocking UI notifications
 */
export const ToastProvider = ({ children }) => {
    const [toasts, setToasts] = useState([]);

    const addToast = useCallback((message, type = 'error', duration = 5000) => {
        const id = Date.now() + Math.random();
        const toast = { id, message, type, duration };
        
        setToasts(prev => [...prev, toast]);

        // Auto-remove toast after duration
        if (duration > 0) {
            setTimeout(() => {
                removeToast(id);
            }, duration);
        }

        return id;
    }, []);

    const removeToast = useCallback((id) => {
        setToasts(prev => prev.filter(t => t.id !== id));
    }, []);

    const toastHelpers = {
        success: (message, duration) => addToast(message, 'success', duration),
        error: (message, duration) => addToast(message, 'error', duration),
        warning: (message, duration) => addToast(message, 'warning', duration),
        info: (message, duration) => addToast(message, 'info', duration),
    };

    const getToastStyles = (type) => {
        const baseStyles = {
            position: 'fixed',
            top: '20px',
            right: '20px',
            padding: `${spacing.md} ${spacing.lg}`,
            borderRadius: '8px',
            fontFamily: 'monospace',
            fontSize: '14px',
            maxWidth: '400px',
            zIndex: 10000,
            boxShadow: '0 4px 12px rgba(0, 0, 0, 0.5)',
            border: '2px solid',
            animation: 'slideIn 0.3s ease-out',
            display: 'flex',
            alignItems: 'center',
            gap: spacing.md,
        };

        const typeStyles = {
            success: {
                backgroundColor: 'rgba(0, 50, 25, 0.95)',
                borderColor: colors.success,
                color: colors.success,
            },
            error: {
                backgroundColor: 'rgba(50, 10, 10, 0.95)',
                borderColor: colors.danger,
                color: colors.danger,
            },
            warning: {
                backgroundColor: 'rgba(50, 30, 0, 0.95)',
                borderColor: colors.warning,
                color: colors.warning,
            },
            info: {
                backgroundColor: 'rgba(0, 25, 50, 0.95)',
                borderColor: colors.info,
                color: colors.info,
            },
        };

        return { ...baseStyles, ...typeStyles[type] };
    };

    const getIcon = (type) => {
        switch (type) {
            case 'success': return '✓';
            case 'error': return '✕';
            case 'warning': return '⚠';
            case 'info': return 'ℹ';
            default: return '•';
        }
    };

    return (
        <ToastContext.Provider value={{ addToast, removeToast, ...toastHelpers }}>
            {children}
            {/* Toast Container */}
            <div style={{
                position: 'fixed',
                top: '20px',
                right: '20px',
                zIndex: 10000,
                display: 'flex',
                flexDirection: 'column',
                gap: spacing.md,
                pointerEvents: 'none',
            }}>
                {toasts.map((toast, index) => (
                    <div
                        key={toast.id}
                        style={{
                            ...getToastStyles(toast.type),
                            pointerEvents: 'auto',
                            transform: `translateY(${index * 10}px)`,
                        }}
                        onClick={() => removeToast(toast.id)}
                        role="alert"
                        aria-live="polite"
                    >
                        <span style={{ fontSize: '18px', fontWeight: 'bold' }}>
                            {getIcon(toast.type)}
                        </span>
                        <span style={{ flex: 1 }}>{toast.message}</span>
                        <button
                            onClick={(e) => {
                                e.stopPropagation();
                                removeToast(toast.id);
                            }}
                            style={{
                                background: 'none',
                                border: 'none',
                                color: 'inherit',
                                cursor: 'pointer',
                                fontSize: '16px',
                                padding: '0 4px',
                                opacity: 0.7,
                            }}
                            aria-label="Close notification"
                        >
                            ×
                        </button>
                    </div>
                ))}
            </div>
            <style>{`
                @keyframes slideIn {
                    from {
                        transform: translateX(100%);
                        opacity: 0;
                    }
                    to {
                        transform: translateX(0);
                        opacity: 1;
                    }
                }
            `}</style>
        </ToastContext.Provider>
    );
};

export default ToastContext;
