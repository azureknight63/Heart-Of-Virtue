import { render, screen, act, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { ToastProvider, useToast } from './ToastContext'

function ToastConsumer() {
  const toast = useToast()
  return (
    <div>
      <button onClick={() => toast.success('Saved!')}>fire-success</button>
      <button onClick={() => toast.error('Broke!')}>fire-error</button>
      <button onClick={() => toast.warning('Careful!')}>fire-warning</button>
      <button onClick={() => toast.info('FYI')}>fire-info</button>
      <button onClick={() => toast.addToast('Persistent', 'success', 0)}>fire-persistent</button>
      <button onClick={() => toast.addToast('Unknown type', 'mystery')}>fire-unknown</button>
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

  it('renders a success toast with its icon and message', () => {
    render(
      <ToastProvider>
        <ToastConsumer />
      </ToastProvider>
    )
    act(() => {
      fireEvent.click(screen.getByText('fire-success'))
    })
    expect(screen.getByText('Saved!')).toBeInTheDocument()
    expect(screen.getByText('✓')).toBeInTheDocument()
  })

  it('renders an error toast with its icon and message', () => {
    render(
      <ToastProvider>
        <ToastConsumer />
      </ToastProvider>
    )
    act(() => {
      fireEvent.click(screen.getByText('fire-error'))
    })
    expect(screen.getByText('Broke!')).toBeInTheDocument()
    expect(screen.getByText('✕')).toBeInTheDocument()
  })

  it('renders a warning toast with its icon and message', () => {
    render(
      <ToastProvider>
        <ToastConsumer />
      </ToastProvider>
    )
    act(() => {
      fireEvent.click(screen.getByText('fire-warning'))
    })
    expect(screen.getByText('Careful!')).toBeInTheDocument()
    expect(screen.getByText('⚠')).toBeInTheDocument()
  })

  it('renders an info toast with its icon and message', () => {
    render(
      <ToastProvider>
        <ToastConsumer />
      </ToastProvider>
    )
    act(() => {
      fireEvent.click(screen.getByText('fire-info'))
    })
    expect(screen.getByText('FYI')).toBeInTheDocument()
    expect(screen.getByText('ℹ')).toBeInTheDocument()
  })

  it('falls back to a default icon for an unrecognized toast type', () => {
    render(
      <ToastProvider>
        <ToastConsumer />
      </ToastProvider>
    )
    act(() => {
      fireEvent.click(screen.getByText('fire-unknown'))
    })
    expect(screen.getByText('Unknown type')).toBeInTheDocument()
    expect(screen.getByText('•')).toBeInTheDocument()
  })

  it('stacks multiple toasts at once', () => {
    render(
      <ToastProvider>
        <ToastConsumer />
      </ToastProvider>
    )
    act(() => {
      fireEvent.click(screen.getByText('fire-success'))
      fireEvent.click(screen.getByText('fire-error'))
    })
    expect(screen.getAllByRole('alert')).toHaveLength(2)
  })

  it('auto-removes a toast after its duration elapses', () => {
    render(
      <ToastProvider>
        <ToastConsumer />
      </ToastProvider>
    )
    act(() => {
      fireEvent.click(screen.getByText('fire-success'))
    })
    expect(screen.getByText('Saved!')).toBeInTheDocument()

    act(() => {
      vi.advanceTimersByTime(5000)
    })

    expect(screen.queryByText('Saved!')).not.toBeInTheDocument()
  })

  it('does not auto-remove a toast with duration 0', () => {
    render(
      <ToastProvider>
        <ToastConsumer />
      </ToastProvider>
    )
    act(() => {
      fireEvent.click(screen.getByText('fire-persistent'))
    })
    act(() => {
      vi.advanceTimersByTime(60000)
    })
    expect(screen.getByText('Persistent')).toBeInTheDocument()
  })

  it('removes a toast when clicked', () => {
    render(
      <ToastProvider>
        <ToastConsumer />
      </ToastProvider>
    )
    act(() => {
      fireEvent.click(screen.getByText('fire-success'))
    })
    act(() => {
      fireEvent.click(screen.getByText('Saved!'))
    })
    expect(screen.queryByText('Saved!')).not.toBeInTheDocument()
  })

  it('removes a toast via its close button', () => {
    render(
      <ToastProvider>
        <ToastConsumer />
      </ToastProvider>
    )
    act(() => {
      fireEvent.click(screen.getByText('fire-success'))
    })
    act(() => {
      fireEvent.click(screen.getByLabelText('Close notification'))
    })
    expect(screen.queryByText('Saved!')).not.toBeInTheDocument()
  })
})
