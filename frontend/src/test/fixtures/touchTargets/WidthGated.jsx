// FIXTURE — deliberately defective, never imported by the app.
//
// Carries issue #639's shape: a 44px floor traded for an 18px control on the
// answer to a question about viewport WIDTH. sourceAudit.test.js scans this
// directory and asserts the audit reports this file, so a scanner that quietly
// stopped walking, stopped parsing or stopped matching cannot pass.
import { useMobile } from '../../../hooks/useMobile'
import { accessibility } from '../../../styles/theme'

export default function WidthGated() {
    const isMobile = useMobile()
    return <button style={{ minHeight: isMobile ? accessibility.touchTarget : '18px' }}>?</button>
}
