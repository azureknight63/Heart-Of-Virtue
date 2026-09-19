import {
    DISCLOSURE_GLYPHS,
    accessibility,
    colors,
    commonStyles,
    spacing,
} from '../styles/theme'

/**
 * CollapsibleSectionHeader — the one fold toggle (issue #625).
 *
 * Three sections hand-rolled this before: InteractPanel's target categories,
 * HeatMeter's "what moves it" helper, and CollapsibleRoomDescription's title
 * bar. They agreed on nothing but "a button that flips some state", and the
 * accessibility contract was whatever each one happened to remember — one had
 * `aria-controls`, one had no `type`, one signalled its state with a rotating
 * ▼ that says nothing to a screen reader.
 *
 * What this owns, for every fold in the app:
 *   - a real `<button type="button">`, so Enter/Space work and it can never
 *     submit an enclosing form;
 *   - `aria-expanded`, so the state is announced;
 *   - `aria-controls`, so the region it folds is reachable — which means the
 *     caller must keep that region MOUNTED with that id even while collapsed,
 *     and put the conditional inside it (see InteractPanel and HeatMeter);
 *   - the ▾/▸ glyph from `DISCLOSURE_GLYPHS`, aria-hidden so it never joins
 *     the accessible name, and present so the state is legible without colour;
 *   - a 44px minimum height (`accessibility.touchTarget`).
 *
 * Props:
 *   expanded    — current state; drives the glyph and aria-expanded.
 *   onToggle    — click handler.
 *   controlsId  — id of the region this header folds.
 *   compact     — drop the height floor. The single opt-out, and it exists for
 *                 one measured case: HeatMeter's helper sits in a
 *                 vertically-budgeted combat panel and keeps the floor on
 *                 phone-width viewports only (`useMobile`, max-width 767px;
 *                 issue #580). Don't reach for it otherwise.
 *   style       — merged over the base; callers own colour, borders and type
 *                 scale, never the contract above: the contract's keys are
 *                 applied AFTER `style` and any extra props, so neither can
 *                 replace them.
 *   children    — the label. Anything the caller likes; it lands after the
 *                 glyph and is what the accessible name is built from.
 */
function CollapsibleSectionHeader({
    expanded,
    onToggle,
    controlsId,
    compact = false,
    style,
    children,
    ...rest
}) {
    return (
        <button
            {...rest}
            type="button"
            onClick={onToggle}
            aria-expanded={expanded}
            aria-controls={controlsId}
            style={{
                ...commonStyles.eyebrowLabel,
                display: 'flex',
                alignItems: 'center',
                gap: spacing.sm,
                width: '100%',
                padding: `0 ${spacing.sm}`,
                background: 'transparent',
                border: 'none',
                color: colors.primary,
                fontWeight: 'bold',
                textAlign: 'left',
                cursor: 'pointer',
                ...style,
                // The contract, after the caller's style so it cannot be undone.
                minHeight: compact ? style?.minHeight : accessibility.touchTarget,
                touchAction: 'manipulation',
            }}
        >
            <span aria-hidden="true">
                {expanded ? DISCLOSURE_GLYPHS.expanded : DISCLOSURE_GLYPHS.collapsed}
            </span>
            {/* Literal space: flex `gap` separates the spans visually but leaves
                the DOM text as "▸Section", which is what assistive tech would
                read. Whitespace-only nodes are not flex items, so this costs
                nothing in the layout. */}
            {' '}
            {children}
        </button>
    )
}

export default CollapsibleSectionHeader
