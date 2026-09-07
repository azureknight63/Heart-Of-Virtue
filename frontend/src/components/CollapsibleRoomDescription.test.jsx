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

  it('scrolls description to top when location changes', () => {
    const { rerender } = render(<CollapsibleRoomDescription location={{ id: 'loc1', name: 'Grotto 1', description: 'First location' }} defaultOpen={true} />)
    const scrollContainer = screen.getByTestId('room-contents').parentElement
    scrollContainer.scrollTop = 100
    expect(scrollContainer.scrollTop).toBe(100)

    rerender(<CollapsibleRoomDescription location={{ id: 'loc2', name: 'Grotto 2', description: 'Second location' }} defaultOpen={true} />)

    expect(scrollContainer.scrollTop).toBe(0)
  })

  it('shows top and bottom scroll fade indicators when content overflows', () => {
    const { container } = render(<CollapsibleRoomDescription location={loc} defaultOpen={true} />)
    const scrollContainer = screen.getByTestId('room-contents').parentElement

    Object.defineProperty(scrollContainer, 'scrollHeight', { value: 500, configurable: true })
    Object.defineProperty(scrollContainer, 'clientHeight', { value: 100, configurable: true })
    Object.defineProperty(scrollContainer, 'scrollTop', { value: 200, configurable: true, writable: true })
    fireEvent.scroll(scrollContainer)

    const fadeIndicators = container.querySelectorAll('[style*="linear-gradient"]')
    expect(fadeIndicators.length).toBe(2)
  })

  // Issue #537 — the description box measured clientHeight: 200 with 149px of
  // unused panel space directly below it, so NPC-presence lines appended
  // after RoomContents (e.g. "Rock Rumbler Gepijak is shuffling about.") were
  // never reachable even though there was plenty of room to grow into.
  it('does not cap the scroll box at the old 200px clip', () => {
    render(<CollapsibleRoomDescription location={loc} defaultOpen={true} />)
    const scrollContainer = screen.getByTestId('room-contents').parentElement
    const maxHeight = parseInt(scrollContainer.style.maxHeight, 10)

    expect(Number.isNaN(maxHeight)).toBe(false)
    // 200px (the old cap) + the reported 149px of empty panel below it.
    expect(maxHeight).toBeGreaterThanOrEqual(300)
  })

  // The persistent "▼ scroll ▼" hint used to paint directly over the last
  // visible line of text instead of sitting below it. The scroll container
  // must reserve blank space for the indicator once it overflows, so the
  // fade/label overlaps empty padding rather than real content.
  it('reserves space below the text for the bottom scroll hint instead of overlapping it', () => {
    render(<CollapsibleRoomDescription location={loc} defaultOpen={true} />)
    const scrollContainer = screen.getByTestId('room-contents').parentElement

    Object.defineProperty(scrollContainer, 'scrollHeight', { value: 500, configurable: true })
    Object.defineProperty(scrollContainer, 'clientHeight', { value: 100, configurable: true })
    Object.defineProperty(scrollContainer, 'scrollTop', { value: 0, configurable: true, writable: true })
    fireEvent.scroll(scrollContainer)

    const paddingBottom = parseInt(scrollContainer.style.paddingBottom || '0', 10)
    expect(paddingBottom).toBeGreaterThan(0)
  })

  it('does not reserve scroll-hint space when the content does not overflow', () => {
    render(<CollapsibleRoomDescription location={loc} defaultOpen={true} />)
    const scrollContainer = screen.getByTestId('room-contents').parentElement

    // No overrides — jsdom's default 0/0 geometry means nothing overflows.
    fireEvent.scroll(scrollContainer)

    const paddingBottom = parseInt(scrollContainer.style.paddingBottom || '0', 10)
    expect(paddingBottom).toBe(0)
  })
})
