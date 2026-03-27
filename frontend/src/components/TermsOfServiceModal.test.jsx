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

    it('switches back to Terms of Service tab', () => {
        render(<TermsOfServiceModal onClose={onClose} />)
        fireEvent.click(screen.getByRole('tab', { name: /Privacy Policy/i }))
        fireEvent.click(screen.getByRole('tab', { name: /Terms of Service/i }))
        expect(screen.getByText(/1\. Acceptance/i)).toBeDefined()
    })

    it('calls onClose when Close button is clicked', () => {
        render(<TermsOfServiceModal onClose={onClose} />)
        fireEvent.click(screen.getByRole('button', { name: /Close/i }))
        expect(onClose).toHaveBeenCalledOnce()
    })
})
