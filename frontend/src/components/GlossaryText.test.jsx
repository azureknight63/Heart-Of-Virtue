import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'

import GlossaryText from './GlossaryText'

const mocks = vi.hoisted(() => ({
  isCoarse: false,
  openGlossary: vi.fn(),
  useMobile: vi.fn(() => false),
  activeAtHandOff: null,
}))

// Presentation is chosen by *pointer modality*, not viewport width — a 1024px
// tablet is a touch device. useMobile is mocked only so a test can assert this
// component never asks it.
vi.mock('../hooks/useCoarsePointer', () => ({ useCoarsePointer: () => mocks.isCoarse }))
vi.mock('../hooks/useMobile', () => ({ useMobile: mocks.useMobile }))
vi.mock('../context/GlossaryContext', () => ({
  useGlossary: () => ({ openGlossary: mocks.openGlossary, closeGlossary: vi.fn(), isGlossaryOpen: false }),
}))

const REASON = '⚠ Available in 5 beats'

const term = () => screen.getByRole('button', { name: /beats — what this means/i })

// The event sequence a browser actually produces for a tap or a click: the
// pointer goes down, the browser focuses the <button>, and only then does the
// click arrive. jsdom dispatches no focus of its own, which is why a suite that
// fires `click` alone cannot see the focus-then-click defect at all.
// `detail: 1` is what a browser sets on a click a pointer produced; jsdom
// defaults it to 0, which is the value a keyboard Enter really carries.
const tap = (el) => {
  fireEvent.pointerDown(el)
  fireEvent.focus(el)
  fireEvent.click(el, { detail: 1 })
}

beforeEach(() => {
  mocks.isCoarse = false
  mocks.openGlossary.mockClear()
  mocks.useMobile.mockClear()
  mocks.activeAtHandOff = null
  mocks.openGlossary.mockImplementation(() => { mocks.activeAtHandOff = document.activeElement })
})

describe('GlossaryText', () => {
  it('renders a string with no known terms verbatim and with nothing to click', () => {
    render(<GlossaryText text="⚠ Not enough mana" />)
    expect(screen.getByText('⚠ Not enough mana')).toBeInTheDocument()
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('makes only the glossary noun interactive, leaving the rest of the line alone', () => {
    const { container } = render(<GlossaryText text={REASON} />)
    expect(term()).toHaveTextContent('beats')
    // The engine's string is still rendered exactly as it arrived.
    expect(container.textContent).toBe(REASON)
    expect(term().getAttribute('aria-expanded')).toBe('false')
  })

  it('survives the real pointer sequence — hover, then focus, then click', () => {
    render(<GlossaryText text={REASON} />)
    const wrapper = term().parentElement
    fireEvent.mouseEnter(wrapper)
    expect(screen.getByRole('tooltip')).toBeInTheDocument()
    // A browser focuses a <button> on pointer-down and React flushes that
    // update before the click. Toggling on the state the click *sees* closed
    // the card the same interaction had just opened.
    tap(term())
    expect(screen.getByRole('tooltip')).toBeInTheDocument()
    expect(term().getAttribute('aria-expanded')).toBe('true')
    expect(term().getAttribute('aria-describedby')).toBe(screen.getByRole('tooltip').id)
  })

  it('closes on Enter, which arrives with no pointer to correct for', () => {
    render(<GlossaryText text={REASON} />)
    fireEvent.focus(term())
    expect(screen.getByRole('tooltip')).toBeInTheDocument()
    // Enter/Space fire a click with detail 0 and no preceding pointerdown.
    fireEvent.click(term())
    expect(screen.queryByRole('tooltip')).toBeNull()
  })

  it('ignores a pointerdown the player dragged away from', () => {
    // No click follows that pointerdown, so its recorded state is still in
    // the ref when the next keyboard press arrives. Reading it there would
    // make Enter fail to close the card.
    render(<GlossaryText text={REASON} />)
    fireEvent.pointerDown(term())          // pressed, then dragged off: no click
    fireEvent.focus(term())
    expect(screen.getByRole('tooltip')).toBeInTheDocument()
    fireEvent.click(term())                // Enter, detail 0
    expect(screen.queryByRole('tooltip')).toBeNull()
  })

  it('opens on hover and closes when the pointer leaves the wrapper', () => {
    render(<GlossaryText text={REASON} />)
    const wrapper = term().parentElement
    fireEvent.mouseEnter(wrapper)
    expect(screen.getByRole('tooltip')).toBeInTheDocument()
    fireEvent.mouseLeave(wrapper)
    expect(screen.queryByRole('tooltip')).toBeNull()
  })

  it('leaves no gap for the pointer to fall through on its way to the card', () => {
    // The wrapper carries the dismissing onMouseLeave and the card is inside
    // it, so hovering the card is not "leaving the term" — but only as long as
    // the two boxes touch. Offsetting the card by 9px put 9px of the *parent*
    // between them: crossing it fired onMouseLeave and dismissed the card the
    // player was reaching for, making "Open glossary →" mouse-unreachable.
    render(<GlossaryText text={REASON} />)
    fireEvent.mouseEnter(term().parentElement)
    const card = screen.getByRole('tooltip')
    expect(term().parentElement.contains(card)).toBe(true)
    expect(card.style.top).toBe('100%')
    expect(card.style.paddingTop).toBe('9px')
  })

  it('opens on keyboard focus and survives tabbing into the card it just opened', () => {
    render(<GlossaryText text={REASON} />)
    fireEvent.focus(term())
    const handOff = screen.getByRole('button', { name: /open glossary/i })

    // relatedTarget inside the wrapper: the player is moving *into* the card.
    fireEvent.blur(term().parentElement, { relatedTarget: handOff })
    expect(screen.getByRole('tooltip')).toBeInTheDocument()

    fireEvent.blur(term().parentElement, { relatedTarget: document.body })
    expect(screen.queryByRole('tooltip')).toBeNull()
  })

  it('dismisses on Escape', () => {
    render(<GlossaryText text={REASON} />)
    tap(term())
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('tooltip')).toBeNull()
  })

  it('ignores other keys while open', () => {
    render(<GlossaryText text={REASON} />)
    tap(term())
    fireEvent.keyDown(document, { key: 'a' })
    expect(screen.getByRole('tooltip')).toBeInTheDocument()
  })

  it('dismisses when the player points at something else, but not at itself', () => {
    render(<GlossaryText text={REASON} />)
    tap(term())
    fireEvent.mouseDown(screen.getByRole('tooltip'))
    expect(screen.getByRole('tooltip')).toBeInTheDocument()
    fireEvent.mouseDown(document.body)
    expect(screen.queryByRole('tooltip')).toBeNull()
  })

  it('places the card above the term when there is room, and below when there is not', () => {
    render(<GlossaryText text={REASON} />)
    tap(term())
    // jsdom reports a zero rect: no room above, so the card flips below.
    expect(screen.getByRole('tooltip').style.top).toBe('100%')
    fireEvent.keyDown(document, { key: 'Escape' })

    vi.spyOn(term(), 'getBoundingClientRect').mockReturnValue({ top: 600 })
    tap(term())
    expect(screen.getByRole('tooltip').style.bottom).toBe('100%')
  })

  it('closes the explainer when the string it belongs to is replaced', () => {
    const { rerender } = render(<GlossaryText text={REASON} />)
    tap(term())
    expect(screen.getByRole('tooltip')).toBeInTheDocument()
    rerender(<GlossaryText text="⚠ Not enough fatigue" />)
    expect(screen.queryByRole('tooltip')).toBeNull()
  })

  it('hands the entry it was explaining to the full glossary', () => {
    render(<GlossaryText text={REASON} />)
    tap(term())
    fireEvent.click(screen.getByRole('button', { name: /open glossary/i }))
    expect(mocks.openGlossary).toHaveBeenCalledWith('beat')
    expect(screen.queryByRole('tooltip')).toBeNull()
  })

  it('puts focus back on the term before handing off, so the panel can restore it', () => {
    // The panel records document.activeElement as the element to return focus
    // to on close. At hand-off that is the tooltip's own "Open glossary"
    // button, which the same commit unmounts — leaving the player at <body>
    // mid-fight.
    render(<GlossaryText text={REASON} />)
    fireEvent.focus(term())
    fireEvent.click(screen.getByRole('button', { name: /open glossary/i }))
    expect(mocks.activeAtHandOff).toBe(term())
  })

  it('chooses its presentation from the pointer, never from the viewport width', () => {
    render(<GlossaryText text={REASON} />)
    tap(term())
    expect(mocks.useMobile).not.toHaveBeenCalled()
  })

  it('gives each occurrence of a word its own independently-openable card', () => {
    render(<GlossaryText text="one beat, then another beat" />)
    const terms = screen.getAllByRole('button', { name: /beat — what this means/i })
    expect(terms).toHaveLength(2)
    tap(terms[1])
    expect(terms[0].getAttribute('aria-expanded')).toBe('false')
    expect(terms[1].getAttribute('aria-expanded')).toBe('true')
  })

  describe('on a coarse pointer (touch, stylus, a tablet of any width)', () => {
    beforeEach(() => { mocks.isCoarse = true })

    it('opens the docked card on a real tap, and closes it on the next one', () => {
      // The whole mobile presentation hung on this: with no hover handlers to
      // mask it, focus-then-click opened and immediately closed the card, so
      // the docked card could never be reached at all.
      render(<GlossaryText text={REASON} />)
      tap(term())
      expect(screen.getByRole('tooltip')).toBeInTheDocument()

      // Second tap: the term already holds focus, so no focus event this time.
      fireEvent.pointerDown(term())
      fireEvent.click(term(), { detail: 1 })
      expect(screen.queryByRole('tooltip')).toBeNull()
    })

    it('docks the card in flow instead of floating it under the thumb', () => {
      render(<GlossaryText text={REASON} />)
      tap(term())
      const card = screen.getByRole('tooltip')
      expect(card.style.position).toBe('relative')
      // Docked outside the term's wrapper, so it is not covered by the tap.
      expect(term().parentElement.contains(card)).toBe(false)
    })

    it('does not open on hover, where there is no pointer to hover with', () => {
      render(<GlossaryText text={REASON} />)
      fireEvent.mouseEnter(term().parentElement)
      expect(screen.queryByRole('tooltip')).toBeNull()
    })

    it('hands off to the full glossary from the docked card, term refocused', () => {
      render(<GlossaryText text={REASON} />)
      tap(term())
      fireEvent.click(screen.getByRole('button', { name: /open glossary/i }))
      expect(mocks.openGlossary).toHaveBeenCalledWith('beat')
      expect(mocks.activeAtHandOff).toBe(term())
    })

    it('dismisses on a tap elsewhere', () => {
      render(<GlossaryText text={REASON} />)
      tap(term())
      act(() => { fireEvent.touchStart(document.body) })
      expect(screen.queryByRole('tooltip')).toBeNull()
    })
  })
})
