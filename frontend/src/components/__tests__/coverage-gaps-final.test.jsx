/**
 * Behavioural tests for CombatLog and EventManager.
 *
 * This file previously held ~26 tests that rendered inline `<div>` literals and
 * asserted on React's own semantics (`{true && <span/>}`, `{0 && <span/>}`,
 * destructuring, `??` vs `||`). Those exercised no project code. The
 * EventManager cases were no better: they passed `events`/`onEvent`, props the
 * component does not accept, and only asserted `container` was truthy — so they
 * passed no matter what the component did.
 *
 * Everything here now drives the real components through their real contracts.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent, within } from '@testing-library/react'
import CombatLog from '../CombatLog'
import EventManager from '../EventManager'

vi.mock('../EventDialog', () => ({
  default: ({ event, history, onClose, onSubmitInput }) => (
    <div data-testid="event-dialog">
      <span data-testid="event-text">{event?.output_text}</span>
      <span data-testid="history-count">{(history || []).length}</span>
      <button onClick={onClose}>close</button>
      <button onClick={() => onSubmitInput('answer')}>submit</button>
    </div>
  ),
}))

describe('EventManager', () => {
  const onClose = vi.fn()
  const onSubmitInput = vi.fn()

  beforeEach(() => vi.clearAllMocks())

  it('renders nothing when there is no current event', () => {
    const { container } = render(
      <EventManager currentEvent={null} eventHistory={[]} onClose={onClose} onSubmitInput={onSubmitInput} />
    )
    expect(container.firstChild).toBeNull()
    expect(screen.queryByTestId('event-dialog')).toBeNull()
  })

  it.each([undefined, null, 0, ''])('renders nothing for the falsy currentEvent %p', (value) => {
    const { container } = render(
      <EventManager currentEvent={value} eventHistory={[]} onClose={onClose} onSubmitInput={onSubmitInput} />
    )
    expect(container.firstChild).toBeNull()
  })

  it('renders the dialog and forwards the event and history when an event exists', () => {
    render(
      <EventManager
        currentEvent={{ output_text: 'A door creaks open.' }}
        eventHistory={['first', 'second']}
        onClose={onClose}
        onSubmitInput={onSubmitInput}
      />
    )
    expect(screen.getByTestId('event-text')).toHaveTextContent('A door creaks open.')
    expect(screen.getByTestId('history-count')).toHaveTextContent('2')
  })

  it('forwards close and input-submission callbacks to the dialog', () => {
    render(
      <EventManager
        currentEvent={{ output_text: 'Answer the riddle.' }}
        eventHistory={[]}
        onClose={onClose}
        onSubmitInput={onSubmitInput}
      />
    )
    fireEvent.click(screen.getByText('close'))
    expect(onClose).toHaveBeenCalledTimes(1)

    fireEvent.click(screen.getByText('submit'))
    expect(onSubmitInput).toHaveBeenCalledWith('answer')
  })

  it('tolerates a missing eventHistory', () => {
    render(
      <EventManager currentEvent={{ output_text: 'No history.' }} onClose={onClose} onSubmitInput={onSubmitInput} />
    )
    expect(screen.getByTestId('history-count')).toHaveTextContent('0')
  })
})

describe('CombatLog', () => {
  const entry = (over = {}) => ({ message: 'Jean strikes.', type: 'combat', timestamp: '10:00:00', ...over })

  it('shows the placeholder when the log is empty', () => {
    render(<CombatLog log={[]} />)
    expect(screen.getByText('Combat started...')).toBeInTheDocument()
  })

  it('renders each entry message with its timestamp', () => {
    render(<CombatLog log={[entry({ message: 'Jean strikes.' }), entry({ message: 'Slime recoils.' })]} />)
    expect(screen.getByText('Jean strikes.')).toBeInTheDocument()
    expect(screen.getByText('Slime recoils.')).toBeInTheDocument()
    expect(screen.getAllByText('[10:00:00]')).toHaveLength(2)
  })

  it('omits animation entries, which carry no player-facing text', () => {
    render(<CombatLog log={[entry({ message: 'visible' }), entry({ message: 'hidden', type: 'animation' })]} />)
    expect(screen.getByText('visible')).toBeInTheDocument()
    expect(screen.queryByText('hidden')).toBeNull()
  })

  it('sanitizes markup in a log message instead of executing it', () => {
    render(<CombatLog log={[entry({ message: '<img src=x onerror="alert(1)">bit by a bat' })]} />)
    const img = document.querySelector('img')
    // DOMPurify keeps the element but strips the event-handler attribute.
    expect(img?.getAttribute('onerror')).toBeNull()
    expect(screen.getByText(/bit by a bat/)).toBeInTheDocument()
  })

  it('keeps safe inline markup in a log message', () => {
    render(<CombatLog log={[entry({ message: 'a <b>critical</b> hit' })]} />)
    expect(screen.getByText('critical').tagName).toBe('B')
  })

  it('collapses and expands when the header is clicked', () => {
    render(<CombatLog log={[entry({ message: 'Jean strikes.' })]} />)
    const header = screen.getByText('Combat Log').parentElement

    expect(screen.getByText('Jean strikes.')).toBeInTheDocument()
    expect(within(header).getByText('▼')).toBeInTheDocument()

    fireEvent.click(header)
    expect(screen.queryByText('Jean strikes.')).toBeNull()
    expect(within(header).getByText('▶')).toBeInTheDocument()

    fireEvent.click(header)
    expect(screen.getByText('Jean strikes.')).toBeInTheDocument()
  })

  it('falls back to a generated timestamp when an entry has none', () => {
    render(<CombatLog log={[{ message: 'no timestamp', type: 'combat' }]} />)
    // Locale decides 12- vs 24-hour, so match the shape rather than the format.
    expect(screen.getByText(/^\[\d{2}:\d{2}:\d{2}.*\]$/)).toBeInTheDocument()
  })

  it('renders distinct entries that share a message and round', () => {
    // The backend deliberately allows duplicate text from different sources;
    // both must survive to the DOM rather than collapsing to one node.
    render(<CombatLog log={[entry({ message: 'The bat bites.', id: 'a' }), entry({ message: 'The bat bites.', id: 'b' })]} />)
    expect(screen.getAllByText('The bat bites.')).toHaveLength(2)
  })

  it('applies the applied className to the container', () => {
    const { container } = render(<CombatLog log={[]} className="my-log" />)
    expect(container.firstChild).toHaveClass('my-log')
  })

  it('starts a resize drag only when resizing is allowed', () => {
    const { container, rerender } = render(<CombatLog log={[entry()]} allowResize />)
    const handle = container.querySelector('div[style*="ns-resize"]')
    expect(handle).toBeTruthy()

    rerender(<CombatLog log={[entry()]} allowResize={false} />)
    expect(container.querySelector('div[style*="ns-resize"]')).toBeNull()
  })

  it('resizes the panel as the pointer is dragged', () => {
    const { container } = render(<CombatLog log={[entry()]} allowResize />)
    const panel = container.firstChild
    const handle = container.querySelector('div[style*="ns-resize"]')

    panel.getBoundingClientRect = () => ({ bottom: 300 })
    fireEvent.mouseDown(handle)
    fireEvent.mouseMove(document, { clientY: 260 })

    // Dragging the bottom edge upward by 40px grows the panel from 150 to 190.
    expect(panel.style.height).toBe('190px')

    fireEvent.mouseUp(document)
    fireEvent.mouseMove(document, { clientY: 100 })
    expect(panel.style.height).toBe('190px')
  })

  it('clamps the height to the allowed range', () => {
    const { container } = render(<CombatLog log={[entry()]} allowResize />)
    const panel = container.firstChild
    const handle = container.querySelector('div[style*="ns-resize"]')

    panel.getBoundingClientRect = () => ({ bottom: 300 })
    fireEvent.mouseDown(handle)

    fireEvent.mouseMove(document, { clientY: 5000 })
    expect(panel.style.height).toBe('50px')

    fireEvent.mouseMove(document, { clientY: -5000 })
    expect(panel.style.height).toBe('400px')
  })

  it('tolerates a missing log prop, rendering an empty body under the header', () => {
    // `.not.toThrow()` alone passed for a component that rendered nothing at
    // all. Pin what actually happens instead.
    //
    // NOTE the asymmetry: `log={[]}` shows "Combat started...", but an ABSENT
    // log shows nothing, because the guard is `log?.length === 0` and
    // `undefined === 0` is false. Harmless today — LeftPanel is the only call
    // site and always passes an array — but if a second caller ever omits it,
    // the panel goes blank rather than showing the placeholder.
    const { container } = render(<CombatLog />)
    expect(screen.getByText('Combat Log')).toBeInTheDocument()
    expect(screen.queryByText('Combat started...')).toBeNull()
    expect(container.querySelector('div[style*="overflow-y: auto"]').children).toHaveLength(0)
  })

  it('auto-scrolls to the newest entry when the log grows', () => {
    const { container, rerender } = render(<CombatLog log={[entry({ message: 'one' })]} />)
    const scroller = container.querySelector('div[style*="overflow-y: auto"]')
    Object.defineProperty(scroller, 'scrollHeight', { value: 900, configurable: true })

    rerender(<CombatLog log={[entry({ message: 'one' }), entry({ message: 'two' })]} />)
    expect(scroller.scrollTop).toBe(900)
  })
})
