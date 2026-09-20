// FIXTURE — deliberately defective, never imported by the app.
//
// Issue #639 written with an ampersand, and split across TWO declarators so
// that no single declaration contains the `&&`. `isMobile && isCoarse` is
// narrow AND coarse, which is a phone: the ~1024px landscape tablet the issue
// is about is coarse and NOT narrow, fails the width half, and loses the
// floor. The audit used to classify each identifier on its own and pass the
// guard the moment ANY of them reached a pointer hook, so this shape — the one
// a well-meaning "make it stricter" edit produces — went unreported.
import { useCoarsePointer } from '../../../hooks/useCoarsePointer'
import { useMobile } from '../../../hooks/useMobile'
import { accessibility } from '../../../styles/theme'

export default function AndGated() {
    const isMobile = useMobile()
    const isCoarse = useCoarsePointer()
    return (
        <button style={{ ...(isMobile && isCoarse ? { minWidth: accessibility.touchTarget } : {}) }}>
            ?
        </button>
    )
}
