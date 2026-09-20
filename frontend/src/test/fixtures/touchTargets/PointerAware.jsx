// FIXTURE — deliberately CORRECT, never imported by the app.
//
// The same control as WidthGated.jsx with the right gate, and a second read
// with no gate at all. The audit must stay quiet about both: an audit that
// reports everything is as useless as one that reports nothing, and only
// asserting the quiet direction can tell the two apart.
import { useLargeTouchTargets } from '../../../hooks/useLargeTouchTargets'
import { useMobile } from '../../../hooks/useMobile'
import { accessibility, spacing } from '../../../styles/theme'

export default function PointerAware() {
    // Both questions live in this file, which is why a file-level check cannot
    // work: `useMobile` is here for LAYOUT and must not launder the floor.
    const isMobile = useMobile()
    const needsLargeTargets = useLargeTouchTargets()
    return (
        <div style={{ flexDirection: isMobile ? 'column' : 'row', gap: spacing.sm }}>
            <button style={{ minHeight: needsLargeTargets ? accessibility.touchTarget : '18px' }}>?</button>
            <button style={{ minHeight: accessibility.touchTarget }}>OK</button>
        </div>
    )
}
