import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import FleeButton from './FleeButton'

describe('FleeButton', () => {
  beforeEach(() => vi.clearAllMocks())

  it('renders the flee button in idle state', () => {
    render(<FleeButton onFlee={vi.fn()} />)
    expect(screen.getByTestId('flee-btn')).toBeDefined()
    expect(screen.queryByTestId('flee-confirm-prompt')).toBeNull()
  })

  it('clicking flee button shows inline confirmation and hides idle button', () => {
    render(<FleeButton onFlee={vi.fn()} />)
    fireEvent.click(screen.getByTestId('flee-btn'))
    expect(screen.getByTestId('flee-confirm-prompt')).toBeDefined()
    expect(screen.queryByTestId('flee-btn')).toBeNull()
  })

  it('Cancel dismisses confirmation and restores idle button', () => {
    render(<FleeButton onFlee={vi.fn()} />)
    fireEvent.click(screen.getByTestId('flee-btn'))
    fireEvent.click(screen.getByTestId('flee-confirm-cancel'))
    expect(screen.queryByTestId('flee-confirm-prompt')).toBeNull()
    expect(screen.getByTestId('flee-btn')).toBeDefined()
  })

  it('Confirm Flee calls onFlee once', async () => {
    const onFlee = vi.fn().mockResolvedValue(undefined)
    render(<FleeButton onFlee={onFlee} />)
    fireEvent.click(screen.getByTestId('flee-btn'))
    fireEvent.click(screen.getByTestId('flee-confirm-yes'))
    await waitFor(() => expect(onFlee).toHaveBeenCalledTimes(1))
  })

  it('shows disabled and loading text while onFlee is pending', async () => {
    let resolve
    const onFlee = vi.fn(() => new Promise(r => { resolve = r }))
    render(<FleeButton onFlee={onFlee} />)
    fireEvent.click(screen.getByTestId('flee-btn'))
    fireEvent.click(screen.getByTestId('flee-confirm-yes'))

    await waitFor(() => {
      const confirmBtn = screen.getByTestId('flee-confirm-yes')
      expect(confirmBtn.disabled).toBe(true)
      expect(confirmBtn.textContent).toBe('Fleeing...')
    })

    resolve()
  })

  it('resets to idle after onFlee resolves', async () => {
    const onFlee = vi.fn().mockResolvedValue(undefined)
    render(<FleeButton onFlee={onFlee} />)
    fireEvent.click(screen.getByTestId('flee-btn'))
    fireEvent.click(screen.getByTestId('flee-confirm-yes'))
    await waitFor(() => expect(screen.queryByTestId('flee-confirm-prompt')).toBeNull())
    expect(screen.getByTestId('flee-btn')).toBeDefined()
  })

  it('resets to idle even when onFlee rejects', async () => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
    const onFlee = vi.fn().mockRejectedValue(new Error('network error'))
    render(<FleeButton onFlee={onFlee} />)
    fireEvent.click(screen.getByTestId('flee-btn'))
    fireEvent.click(screen.getByTestId('flee-confirm-yes'))
    await waitFor(() => expect(screen.queryByTestId('flee-confirm-prompt')).toBeNull())
    expect(screen.getByTestId('flee-btn')).toBeDefined()
    consoleError.mockRestore()
  })

  it('applies mobile font size when isMobile is true', () => {
    const { container } = render(<FleeButton onFlee={vi.fn()} isMobile={true} />)
    const btn = container.querySelector('[data-testid="flee-btn"]')
    expect(btn.style.fontSize).toBe('11px')
  })
})
