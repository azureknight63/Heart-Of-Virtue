import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import CollapsibleRoomDescription from './CollapsibleRoomDescription'

vi.mock('./RoomContents', () => ({
  default: ({ onInteract }) => (
    <div data-testid="room-contents">
      <button onClick={onInteract}>Interact</button>
    </div>
  )
}))

const loc = { name: 'Dark Grotto', description: 'Damp stone.' }

describe('CollapsibleRoomDescription', () => {
  it('returns null when location is undefined', () => {
    const { container } = render(<CollapsibleRoomDescription />)
    expect(container.firstChild).toBeNull()
  })

  it('renders location name in the header button', () => {
    render(<CollapsibleRoomDescription location={loc} />)
    expect(screen.getByText('Dark Grotto')).toBeDefined()
  })

  it('shows content by default (defaultOpen=true)', () => {
    render(<CollapsibleRoomDescription location={loc} defaultOpen={true} />)
    expect(screen.getByTestId('room-contents')).toBeDefined()
  })

  it('hides content when defaultOpen=false', () => {
    render(<CollapsibleRoomDescription location={loc} defaultOpen={false} />)
    expect(screen.queryByTestId('room-contents')).toBeNull()
  })

  it('toggles content open on header click when closed', () => {
    render(<CollapsibleRoomDescription location={loc} defaultOpen={false} />)
    expect(screen.queryByTestId('room-contents')).toBeNull()
    fireEvent.click(screen.getByText('Dark Grotto'))
    expect(screen.getByTestId('room-contents')).toBeDefined()
  })

  it('toggles content closed on header click when open', () => {
    render(<CollapsibleRoomDescription location={loc} defaultOpen={true} />)
    expect(screen.getByTestId('room-contents')).toBeDefined()
    fireEvent.click(screen.getByText('Dark Grotto'))
    expect(screen.queryByTestId('room-contents')).toBeNull()
  })

  it('forwards onInteract to RoomContents', () => {
    const onInteract = vi.fn()
    render(<CollapsibleRoomDescription location={loc} onInteract={onInteract} defaultOpen={true} />)
    fireEvent.click(screen.getByText('Interact'))
    expect(onInteract).toHaveBeenCalledTimes(1)
  })

  it('falls back to "Current Location" when location has no name', () => {
    render(<CollapsibleRoomDescription location={{ description: 'Some place.' }} defaultOpen={true} />)
    expect(screen.getByText('Current Location')).toBeDefined()
  })
})
