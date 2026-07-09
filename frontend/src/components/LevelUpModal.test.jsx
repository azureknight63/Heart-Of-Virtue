import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import LevelUpModal from './LevelUpModal'
import { useAudio } from '../context/AudioContext'

vi.mock('./BaseDialog', () => ({
  default: ({ children, title }) => (
    <div data-testid="base-dialog">
      <h2>{title}</h2>
      {children}
    </div>
  ),
}))

vi.mock('./GameButton', () => ({
  default: ({ children, onClick, disabled }) => (
    <button onClick={onClick} disabled={disabled}>{children}</button>
  ),
}))

vi.mock('./GameText', () => ({
  default: ({ children }) => <span>{children}</span>,
}))

vi.mock('../context/AudioContext', () => ({
  useAudio: vi.fn(),
}))

function makePlayer(overrides = {}) {
  return {
    pending_attribute_points: 3,
    pending_level_ups: [],
    strength_base: 10,
    finesse_base: 9,
    speed_base: 11,
    endurance_base: 8,
    charisma_base: 7,
    intelligence_base: 6,
    faith_base: 5,
    ...overrides,
  }
}

describe('LevelUpModal', () => {
  const onAllocatePoints = vi.fn()
  const playSFX = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
    useAudio.mockReturnValue({ playSFX })
  })

  it('renders available points and attribute options', () => {
    render(<LevelUpModal player={makePlayer()} onAllocatePoints={onAllocatePoints} />)
    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.getByText('Strength (10)')).toBeInTheDocument()
    expect(screen.getByText('Finesse (9)')).toBeInTheDocument()
    expect(screen.getByText('Faith (5)')).toBeInTheDocument()
  })

  it('treats a missing player as zero remaining points', () => {
    render(<LevelUpModal player={undefined} onAllocatePoints={onAllocatePoints} />)
    expect(screen.getByText('0')).toBeInTheDocument()
    expect(screen.getByText('ALLOCATE POINTS').closest('button')).toBeDisabled()
  })

  it('plays the level_up SFX when there are pending level-ups', () => {
    render(
      <LevelUpModal
        player={makePlayer({ pending_level_ups: [{ old_level: 4, new_level: 5, points_awarded: 3 }] })}
        onAllocatePoints={onAllocatePoints}
      />
    )
    expect(playSFX).toHaveBeenCalledWith('level_up')
    expect(screen.getByText(/LEVEL 4/)).toBeInTheDocument()
    expect(screen.getByText('5')).toBeInTheDocument()
    expect(screen.getByText('+3 attribute points awarded')).toBeInTheDocument()
  })

  it('does not play the SFX when there are no pending level-ups', () => {
    render(<LevelUpModal player={makePlayer()} onAllocatePoints={onAllocatePoints} />)
    expect(playSFX).not.toHaveBeenCalled()
  })

  it('changes the selected attribute via the dropdown', () => {
    render(<LevelUpModal player={makePlayer()} onAllocatePoints={onAllocatePoints} />)
    const select = screen.getByRole('combobox')
    fireEvent.change(select, { target: { value: 'faith_base' } })
    expect(select.value).toBe('faith_base')
  })

  it('rejects a non-numeric or zero amount', async () => {
    render(<LevelUpModal player={makePlayer()} onAllocatePoints={onAllocatePoints} />)
    const input = screen.getByRole('spinbutton')
    fireEvent.change(input, { target: { value: '0' } })
    await act(async () => {
      fireEvent.click(screen.getByText('ALLOCATE POINTS'))
    })
    expect(screen.getByText(/Enter a valid point amount\./)).toBeInTheDocument()
    expect(onAllocatePoints).not.toHaveBeenCalled()
  })

  it('rejects allocating more points than available', async () => {
    render(<LevelUpModal player={makePlayer({ pending_attribute_points: 2 })} onAllocatePoints={onAllocatePoints} />)
    const input = screen.getByRole('spinbutton')
    fireEvent.change(input, { target: { value: '5' } })
    await act(async () => {
      fireEvent.click(screen.getByText('ALLOCATE POINTS'))
    })
    expect(screen.getByText(/Not enough points available\./)).toBeInTheDocument()
    expect(onAllocatePoints).not.toHaveBeenCalled()
  })

  it('allocates points successfully and resets the amount field', async () => {
    onAllocatePoints.mockResolvedValue({ success: true })
    render(<LevelUpModal player={makePlayer()} onAllocatePoints={onAllocatePoints} />)
    const input = screen.getByRole('spinbutton')
    fireEvent.change(input, { target: { value: '2' } })
    await act(async () => {
      fireEvent.click(screen.getByText('ALLOCATE POINTS'))
    })
    expect(onAllocatePoints).toHaveBeenCalledWith('strength_base', 2)
    expect(input.value).toBe('1')
    expect(screen.queryByText(/Enter a valid/)).not.toBeInTheDocument()
  })

  it('shows a server-provided error when allocation is rejected', async () => {
    onAllocatePoints.mockResolvedValue({ success: false, error: 'Attribute already maxed.' })
    render(<LevelUpModal player={makePlayer()} onAllocatePoints={onAllocatePoints} />)
    await act(async () => {
      fireEvent.click(screen.getByText('ALLOCATE POINTS'))
    })
    expect(screen.getByText(/Attribute already maxed\./)).toBeInTheDocument()
  })

  it('shows a default error when the API omits one on rejection', async () => {
    onAllocatePoints.mockResolvedValue({ success: false })
    render(<LevelUpModal player={makePlayer()} onAllocatePoints={onAllocatePoints} />)
    await act(async () => {
      fireEvent.click(screen.getByText('ALLOCATE POINTS'))
    })
    expect(screen.getByText(/Failed to allocate points\./)).toBeInTheDocument()
  })

  it('shows a network error message when allocation throws', async () => {
    onAllocatePoints.mockRejectedValue(new Error('network down'))
    render(<LevelUpModal player={makePlayer()} onAllocatePoints={onAllocatePoints} />)
    await act(async () => {
      fireEvent.click(screen.getByText('ALLOCATE POINTS'))
    })
    expect(screen.getByText(/network down/)).toBeInTheDocument()
  })

  it('prefers err.response.data.error over err.message on allocation failure', async () => {
    onAllocatePoints.mockRejectedValue({ response: { data: { error: 'server rejected' } } })
    render(<LevelUpModal player={makePlayer()} onAllocatePoints={onAllocatePoints} />)
    await act(async () => {
      fireEvent.click(screen.getByText('ALLOCATE POINTS'))
    })
    expect(screen.getByText(/server rejected/)).toBeInTheDocument()
  })

  it('randomizes remaining points via the Randomize button', async () => {
    onAllocatePoints.mockResolvedValue({ success: true })
    render(<LevelUpModal player={makePlayer({ pending_attribute_points: 4 })} onAllocatePoints={onAllocatePoints} />)
    await act(async () => {
      fireEvent.click(screen.getByText('RANDOMIZE'))
    })
    expect(onAllocatePoints).toHaveBeenCalledWith('randomize', 4)
  })

  it('shows a default error when randomize fails without a message', async () => {
    onAllocatePoints.mockResolvedValue({ success: false })
    render(<LevelUpModal player={makePlayer()} onAllocatePoints={onAllocatePoints} />)
    await act(async () => {
      fireEvent.click(screen.getByText('RANDOMIZE'))
    })
    expect(screen.getByText(/Failed to randomize points\./)).toBeInTheDocument()
  })

  it('shows a network error message when randomize throws', async () => {
    onAllocatePoints.mockRejectedValue(new Error('boom'))
    render(<LevelUpModal player={makePlayer()} onAllocatePoints={onAllocatePoints} />)
    await act(async () => {
      fireEvent.click(screen.getByText('RANDOMIZE'))
    })
    expect(screen.getByText(/boom/)).toBeInTheDocument()
  })

  it('prefers err.response.data.error over err.message on randomize failure', async () => {
    onAllocatePoints.mockRejectedValue({ response: { data: { error: 'server rejected randomize' } } })
    render(<LevelUpModal player={makePlayer()} onAllocatePoints={onAllocatePoints} />)
    await act(async () => {
      fireEvent.click(screen.getByText('RANDOMIZE'))
    })
    expect(screen.getByText(/server rejected randomize/)).toBeInTheDocument()
  })

  it('clears a stale error once the amount is brought back within range', () => {
    render(<LevelUpModal player={makePlayer({ pending_attribute_points: 2 })} onAllocatePoints={onAllocatePoints} />)
    const input = screen.getByRole('spinbutton')
    fireEvent.change(input, { target: { value: '5' } })
    fireEvent.click(screen.getByText('ALLOCATE POINTS'))
    expect(screen.getByText(/Not enough points available\./)).toBeInTheDocument()

    fireEvent.change(input, { target: { value: '1' } })
    expect(screen.queryByText(/Not enough points available\./)).not.toBeInTheDocument()
  })

  it('disables both action buttons while a submission is in flight', async () => {
    let resolveFn
    onAllocatePoints.mockReturnValue(new Promise((resolve) => { resolveFn = resolve }))
    render(<LevelUpModal player={makePlayer()} onAllocatePoints={onAllocatePoints} />)

    fireEvent.click(screen.getByText('ALLOCATE POINTS'))
    expect(screen.getByText('ALLOCATING...')).toBeInTheDocument()
    expect(screen.getByText('ALLOCATING...').closest('button')).toBeDisabled()
    expect(screen.getByText('RANDOMIZE').closest('button')).toBeDisabled()

    await act(async () => {
      resolveFn({ success: true })
    })
  })

  it('disables allocation buttons when there are no points remaining', () => {
    render(<LevelUpModal player={makePlayer({ pending_attribute_points: 0 })} onAllocatePoints={onAllocatePoints} />)
    expect(screen.getByText('ALLOCATE POINTS').closest('button')).toBeDisabled()
    expect(screen.getByText('RANDOMIZE').closest('button')).toBeDisabled()
  })

  it('omits the numeric suffix for attributes with a non-numeric value', () => {
    render(<LevelUpModal player={makePlayer({ strength_base: undefined })} onAllocatePoints={onAllocatePoints} />)
    expect(screen.getByText('Strength')).toBeInTheDocument()
  })
})
