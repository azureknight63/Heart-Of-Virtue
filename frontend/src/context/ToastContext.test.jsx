import { render, screen, act, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ToastProvider, useToast } from './ToastContext'
import { colors } from '../styles/theme'

/** jsdom normalises inline colours to rgb(); theme.js stores hex. */
const rgb = (hex) => {
  const n = parseInt(hex.slice(1), 16)
  return `rgb(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255})`
}

let lastToastId

function ToastConsumer() {
  const toast = useToast()
  return (
    <div>
      <button onClick={() => { lastToastId = toast.success('Saved!') }}>fire-success</button>
      <button onClick={() => toast.error('Broke!')}>fire-error</button>
      <button onClick={() => toast.warning('Careful!')}>fire-warning</button>
      <button onClick={() => toast.info('FYI')}>fire-info</button>
      <button onClick={() => toast.addToast('Persistent', 'success', 0)}>fire-persistent</button>
      <button onClick={() => toast.addToast('Unknown type', 'mystery')}>fire-unknown</button>
      <button onClick={() => toast.success('Brief', 1000)}>fire-brief</button>
      <button onClick={() => toast.removeToast(lastToastId)}>remove-last</button>
    </div>
  )
}

function ThrowsOutsideProvider() {
  useToast()
  return null
}

describe('ToastContext', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.runOnlyPendingTimers()
    vi.useRealTimers()
  })

  it('throws when useToast is called outside a ToastProvider', () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    expect(() => render(<ThrowsOutsideProvider />)).toThrow(
      'useToast must be used within a ToastProvider'
    )
    consoleSpy.mockRestore()
  })

  const mount = () => render(
    <ToastProvider>
      <ToastConsumer />
    </ToastProvider>
  )
  const fire = (label) => act(() => { fireEvent.click(screen.getByText(label)) })

  // Four near-identical tests plus a fifth for the default, each asserting only
  // that the message and the glyph existed somewhere. The type ALSO drives the
  // toast's border/text colour, which no test read — a swapped success/error
  // palette (green "Save failed") was invisible.
  it.each([
    ['success', 'fire-success', 'Saved!', '✓', colors.success],
    ['error', 'fire-error', 'Broke!', '✕', colors.danger],
    ['warning', 'fire-warning', 'Careful!', '⚠', colors.warning],
    ['info', 'fire-info', 'FYI', 'ℹ', colors.info],
  ])('renders a %s toast with its own icon, message and palette', (_type, button, message, icon, color) => {
    mount()
    fire(button)

    const toast = screen.getByRole('alert')
    expect(toast.textContent).toBe(`${icon}${message}×`)
    expect(toast.style.color).toBe(rgb(color))
    expect(toast.style.borderColor).toBe(rgb(color))
  })

  it('falls back to a bullet icon and an unstyled palette for an unrecognized type', () => {
    mount()
    fire('fire-unknown')

    const toast = screen.getByRole('alert')
    expect(toast.textContent).toBe('•Unknown type×')
    // typeStyles has no `mystery` entry, so only the base styles apply.
    expect(toast.style.color).toBe('')
  })

  it('stacks toasts in fire order, offsetting each one down the column', () => {
    mount()
    fire('fire-success')
    fire('fire-error')

    const alerts = screen.getAllByRole('alert')
    expect(alerts.map((a) => a.textContent)).toEqual(['✓Saved!×', '✕Broke!×'])
    // Index-based offset: without it the two stack exactly on top of each other.
    expect(alerts.map((a) => a.style.transform))
      .toEqual(['translateY(0px)', 'translateY(10px)'])
  })

  it('auto-removes a toast at 5000ms by default, and not a tick sooner', () => {
    mount()
    fire('fire-success')
    expect(screen.getByRole('alert').textContent).toBe('✓Saved!×')

    act(() => { vi.advanceTimersByTime(4999) })
    expect(screen.getByRole('alert').textContent).toBe('✓Saved!×')

    act(() => { vi.advanceTimersByTime(1) })
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('honours an explicit shorter duration', () => {
    // The helpers forward their `duration` argument through to addToast; a
    // helper that dropped it would silently give every toast the 5s default.
    mount()
    fire('fire-brief')

    act(() => { vi.advanceTimersByTime(999) })
    expect(screen.getByRole('alert').textContent).toBe('✓Brief×')

    act(() => { vi.advanceTimersByTime(1) })
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('does not auto-remove a toast with duration 0, and schedules no timer for it', () => {
    mount()
    fire('fire-persistent')
    expect(vi.getTimerCount()).toBe(0)

    act(() => { vi.advanceTimersByTime(60000) })
    expect(screen.getByRole('alert').textContent).toBe('✓Persistent×')
  })

  it.each([
    ['the toast body', () => fireEvent.click(screen.getByText('Saved!'))],
    ['its close button', () => fireEvent.click(screen.getByLabelText('Close notification'))],
    ['removeToast with the id addToast returned', () => fireEvent.click(screen.getByText('remove-last'))],
  ])('removes a toast via %s', (_label, dismiss) => {
    mount()
    fire('fire-success')
    act(() => { dismiss() })
    expect(screen.queryByRole('alert')).toBeNull()
    // Dismissing early also cancels the auto-dismiss timer; the orphan would
    // otherwise fire a setState for a toast that no longer exists.
    expect(vi.getTimerCount()).toBe(0)
  })

  it('dismisses only the clicked toast, leaving the rest up', () => {
    mount()
    fire('fire-success')
    fire('fire-error')

    act(() => { fireEvent.click(screen.getByText('Broke!')) })
    const remaining = screen.getAllByRole('alert')
    expect(remaining).toHaveLength(1)
    expect(remaining[0].textContent).toBe('✓Saved!×')
    expect(vi.getTimerCount()).toBe(1)
  })

  it('stops the click from bubbling when the close button is used', () => {
    // The row's onClick and the button's onClick both call removeToast for the
    // same id, so without stopPropagation this is merely redundant — but the
    // observable guarantee is that one click removes one toast, not two.
    mount()
    fire('fire-success')
    fire('fire-error')

    act(() => { fireEvent.click(screen.getAllByLabelText('Close notification')[0]) })
    expect(screen.getAllByRole('alert')).toHaveLength(1)
  })

  it('clears outstanding auto-dismiss timers when the provider unmounts', () => {
    const { unmount } = mount()
    fire('fire-success')
    fire('fire-error')
    expect(vi.getTimerCount()).toBe(2)

    unmount()
    expect(vi.getTimerCount()).toBe(0)
  })
})
