import { colors, shadows, spacing } from '../styles/theme'
import { lookupOr } from '../utils/lookup'

/**
 * The ✕ affordance, shared by the titled and title-less branches below.
 * Both rendered the same six style properties verbatim, differing only by
 * `marginLeft` — so a `colors.text.primary` → `colors.primary` correction had
 * to be made twice, which is the argument for having one copy.
 */
function CloseButton({ onClose, style = {} }) {
    return (
        <button
            onClick={onClose}
            style={{
                background: 'none',
                border: 'none',
                color: colors.primary,
                cursor: 'pointer',
                fontSize: '16px',
                padding: '0 4px',
                ...style,
            }}
        >
            ✕
        </button>
    )
}

/**
 * The class the panel root carries, exported because it is a CONTRACT.
 *
 * Anything that needs to find a GamePanel's root from an arbitrary descendant
 * (or from outside the component entirely, in a test) does it with
 * `closest(\`.${GAME_PANEL_CLASS}\`)` / `querySelector` rather than restating
 * the literal — so a rename here cannot silently break a lookup that agrees
 * with itself. `LeftPanel.categoryNavStacking.test.jsx` uses it to find
 * CombatMovePanel's real root and read its z-index (issue #575). Same
 * reasoning as `CATEGORY_NAV_LABEL` in utils/categories.js.
 *
 * Until #575 this was also how `useOccludedNavHandoff` resolved the panel it
 * hit-tested against; that hook is retired now that CombatMovePanel can no
 * longer occlude the category nav (see CombatMovePanel.jsx's
 * `COMBAT_MOVE_PANEL_Z_INDEX` and LeftPanel.jsx's
 * `HERO_PANEL_STACKING_Z_INDEX`).
 */
export const GAME_PANEL_CLASS = 'game-panel'

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
        // The title-less close button is absolutely positioned; without a
        // positioned ancestor here it anchors to whatever arbitrary ancestor
        // happens to be positioned. Declared before ...style so callers can
        // still override it.
        position: 'relative',
        backgroundColor: colors.bg.panel,
        border: `2px solid ${lookupOr(colors.border, borderVariant, colors.border.main)}`,
        borderRadius: '8px',
        padding: lookupOr(paddingValues, padding, paddingValues.large),
        boxShadow: glow ? shadows.glow : shadows.main,
        fontFamily: '"Courier New", monospace',
        ...style
    }

    return (
        <div className={`${GAME_PANEL_CLASS} border rounded p-lg bg-neutral-900 ${glow ? 'retro-glow' : ''} ${className}`} style={panelStyle}>
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
                        color: colors.primary
                    }}>
                        {title}
                    </h2>
                    {onClose && (
                        <CloseButton onClose={onClose} style={{ marginLeft: spacing.sm }} />
                    )}
                </div>
            )}
            {!title && onClose && (
                <div style={{ position: 'absolute', top: spacing.sm, right: spacing.sm }}>
                    <CloseButton onClose={onClose} />
                </div>
            )}
            <div style={{ position: 'relative' }}>
                {children}
            </div>
        </div>
    )
}
