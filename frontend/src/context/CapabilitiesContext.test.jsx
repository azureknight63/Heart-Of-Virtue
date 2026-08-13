import { render, screen, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
  CapabilitiesProvider,
  useCapabilities,
  isCombatSocketStreamingEnabled,
  _resetCapabilitiesCache,
} from './CapabilitiesContext'
import apiEndpoints from '../api/endpoints'

vi.mock('../api/endpoints', () => ({
  default: {
    app: {
      getInfo: vi.fn(),
    },
  },
}))

function CapabilitiesConsumer() {
  const caps = useCapabilities()
  return (
    <div>
      <div data-testid="loading">{String(caps.capabilitiesLoading)}</div>
      <div data-testid="streaming">{String(caps.combatSocketStreaming)}</div>
    </div>
  )
}

function ThrowsOutsideProvider() {
  useCapabilities()
  return null
}

describe('isCombatSocketStreamingEnabled', () => {
  it('follows the backend capability when enabled', () => {
    expect(isCombatSocketStreamingEnabled({ combat_socket_streaming: true })).toBe(true)
  })

  it('stays off when the backend capability is disabled or unavailable', () => {
    expect(isCombatSocketStreamingEnabled({ combat_socket_streaming: false })).toBe(false)
    expect(isCombatSocketStreamingEnabled(null)).toBe(false)
    expect(isCombatSocketStreamingEnabled({})).toBe(false)
  })
})

describe('CapabilitiesContext', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    _resetCapabilitiesCache()
  })

  it('throws when useCapabilities is called outside a CapabilitiesProvider', () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    expect(() => render(<ThrowsOutsideProvider />)).toThrow(
      'useCapabilities must be used within a CapabilitiesProvider'
    )
    consoleSpy.mockRestore()
  })

  it('starts in a loading state before discovery resolves', () => {
    apiEndpoints.app.getInfo.mockReturnValue(new Promise(() => {})) // never resolves
    render(<CapabilitiesProvider><CapabilitiesConsumer /></CapabilitiesProvider>)
    expect(screen.getByTestId('loading').textContent).toBe('true')
    expect(screen.getByTestId('streaming').textContent).toBe('false')
  })

  it('enables combat streaming when the backend capability is on', async () => {
    apiEndpoints.app.getInfo.mockResolvedValue({
      data: { features: { combat_socket_streaming: true } },
    })

    render(<CapabilitiesProvider><CapabilitiesConsumer /></CapabilitiesProvider>)

    await waitFor(() => {
      expect(screen.getByTestId('loading').textContent).toBe('false')
    })
    expect(screen.getByTestId('streaming').textContent).toBe('true')
  })

  it('stays disabled when the response has no features payload at all', async () => {
    apiEndpoints.app.getInfo.mockResolvedValue({ data: {} })

    render(<CapabilitiesProvider><CapabilitiesConsumer /></CapabilitiesProvider>)

    await waitFor(() => {
      expect(screen.getByTestId('loading').textContent).toBe('false')
    })
    expect(screen.getByTestId('streaming').textContent).toBe('false')
  })

  it('stays disabled when the backend capability is explicitly off', async () => {
    apiEndpoints.app.getInfo.mockResolvedValue({
      data: { features: { combat_socket_streaming: false } },
    })

    render(<CapabilitiesProvider><CapabilitiesConsumer /></CapabilitiesProvider>)

    await waitFor(() => {
      expect(screen.getByTestId('loading').textContent).toBe('false')
    })
    expect(screen.getByTestId('streaming').textContent).toBe('false')
  })

  it('falls back to disabled and warns when discovery is unavailable', async () => {
    const consoleSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
    const networkError = new Error('network down')
    apiEndpoints.app.getInfo.mockRejectedValue(networkError)

    render(<CapabilitiesProvider><CapabilitiesConsumer /></CapabilitiesProvider>)

    await waitFor(() => {
      expect(screen.getByTestId('loading').textContent).toBe('false')
    })
    expect(screen.getByTestId('streaming').textContent).toBe('false')
    expect(consoleSpy).toHaveBeenCalledWith(
      expect.stringContaining('Runtime capability discovery failed'),
      networkError
    )
    consoleSpy.mockRestore()
  })

  it('issues exactly one discovery request across simultaneous mounts (StrictMode double-invoke)', async () => {
    apiEndpoints.app.getInfo.mockResolvedValue({
      data: { features: { combat_socket_streaming: true } },
    })

    render(
      <>
        <CapabilitiesProvider><CapabilitiesConsumer /></CapabilitiesProvider>
        <CapabilitiesProvider><CapabilitiesConsumer /></CapabilitiesProvider>
      </>
    )

    const loadingCells = await screen.findAllByTestId('loading')
    await waitFor(() => {
      loadingCells.forEach((cell) => expect(cell.textContent).toBe('false'))
    })

    expect(apiEndpoints.app.getInfo).toHaveBeenCalledTimes(1)
  })

  it('does not update state after unmount (cancellation guard)', async () => {
    let resolveFetch
    apiEndpoints.app.getInfo.mockReturnValue(
      new Promise((resolve) => { resolveFetch = resolve })
    )

    const { unmount } = render(
      <CapabilitiesProvider><CapabilitiesConsumer /></CapabilitiesProvider>
    )
    unmount()

    // Resolving after unmount must not throw an act()/state-update warning.
    resolveFetch({ data: { features: { combat_socket_streaming: true } } })
    await Promise.resolve()
    await Promise.resolve()
  })
})
