import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import TermsOfServiceModal from './TermsOfServiceModal'

describe('TermsOfServiceModal', () => {
    const onClose = vi.fn()

    it('renders Terms of Service tab by default', () => {
        render(<TermsOfServiceModal onClose={onClose} />)
        expect(screen.getByText(/Terms & Privacy/i)).toBeDefined()
        expect(screen.getByText(/1\. Acceptance/i)).toBeDefined()
    })

    it('switches to Privacy Policy tab', () => {
        render(<TermsOfServiceModal onClose={onClose} />)
        fireEvent.click(screen.getByRole('tab', { name: /Privacy Policy/i }))
        expect(screen.getByText(/What We Collect/i)).toBeDefined()
    })

    it('describes the gameplay analytics that are actually running', () => {
        // Must match src/api/services/analytics.py: pseudonymous player ids,
        // no account id, username, email or IP; and no longer "planned".
        render(<TermsOfServiceModal onClose={onClose} />)
        fireEvent.click(screen.getByRole('tab', { name: /Privacy Policy/i }))
        const text = document.body.textContent
        expect(text).not.toMatch(/We plan to add/i)
        expect(text).toMatch(/pseudonymous/i)
        expect(text).toMatch(/None of it carries your\s+username, email address or IP address/i)
        // Where the data goes, and what else is counted (the digest and the
        // autosave tables would otherwise contradict "not shared").
        expect(text).toMatch(/private Discord channel/i)
        expect(text).toMatch(/cloud\s+autosaves/i)
        // Honest about what pseudonymous means, and Discord listed as a recipient.
        expect(text).toMatch(/We hold the key/i)
        expect(text).toMatch(/Discord — the developer's private channel/i)
        expect(text).not.toMatch(/never individual players/i)
    })

    it('switches back to Terms of Service tab', () => {
        render(<TermsOfServiceModal onClose={onClose} />)
        fireEvent.click(screen.getByRole('tab', { name: /Privacy Policy/i }))
        fireEvent.click(screen.getByRole('tab', { name: /Terms of Service/i }))
        expect(screen.getByText(/1\. Acceptance/i)).toBeDefined()
    })

    it('calls onClose when Close button is clicked', () => {
        render(<TermsOfServiceModal onClose={onClose} />)
        // The footer button, not BaseDialog's "Close dialog" ✕.
        fireEvent.click(screen.getByRole('button', { name: /^Close$/i }))
        expect(onClose).toHaveBeenCalledOnce()
    })
})
