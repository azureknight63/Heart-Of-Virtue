import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'

import GlossaryText from './GlossaryText'

const mocks = vi.hoisted(() => ({ isMobile: false, openGlossary: vi.fn() }))

vi.mock('../hooks/useMobile', () => ({ useMobile: () => mocks.isMobile }))
vi.mock('../context/GlossaryContext', () => ({
  useGlossary: () => ({ openGlossary: mocks.openGlossary, closeGlossary: vi.fn(), isGlossaryOpen: false }),
}))

const REASON = '⚠ Available in 5 beats'

const term = () => screen.getByRole('button', { name: /beats — what this means/i })

beforeEach(() => {
  mocks.isMobile = false
  mocks.openGlossary.mockClear()
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

  it('opens the explainer on click and closes it on a second click', () => {
    render(<GlossaryText text={REASON} />)
    fireEvent.click(term())
    expect(screen.getByRole('tooltip')).toBeInTheDocument()
    expect(term().getAttribute('aria-expanded')).toBe('true')
    expect(term().getAttribute('aria-describedby')).toBe(screen.getByRole('tooltip').id)

    fireEvent.click(term())
    expect(screen.queryByRole('tooltip')).toBeNull()
  })

  it('opens on hover and closes when the pointer leaves the term and its card', () => {
    render(<GlossaryText text={REASON} />)
    const wrapper = term().parentElement
    fireEvent.mouseEnter(wrapper)
    expect(screen.getByRole('tooltip')).toBeInTheDocument()
    fireEvent.mouseLeave(wrapper)
    expect(screen.queryByRole('tooltip')).toBeNull()
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
    fireEvent.click(term())
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('tooltip')).toBeNull()
  })

  it('ignores other keys while open', () => {
    render(<GlossaryText text={REASON} />)
    fireEvent.click(term())
    fireEvent.keyDown(document, { key: 'a' })
    expect(screen.getByRole('tooltip')).toBeInTheDocument()
  })

  it('dismisses when the player points at something else, but not at itself', () => {
    render(<GlossaryText text={REASON} />)
    fireEvent.click(term())
    fireEvent.mouseDown(screen.getByRole('tooltip'))
    expect(screen.getByRole('tooltip')).toBeInTheDocument()
    fireEvent.mouseDown(document.body)
    expect(screen.queryByRole('tooltip')).toBeNull()
  })

  it('places the card above the term when there is room, and below when there is not', () => {
    render(<GlossaryText text={REASON} />)
    fireEvent.click(term())
    // jsdom reports a zero rect: no room above, so the card flips below.
    expect(screen.getByRole('tooltip').style.top).toBe('calc(100% + 9px)')
    fireEvent.click(term())

    vi.spyOn(term(), 'getBoundingClientRect').mockReturnValue({ top: 600 })
    fireEvent.click(term())
    expect(screen.getByRole('tooltip').style.bottom).toBe('calc(100% + 9px)')
  })

  it('closes the explainer when the string it belongs to is replaced', () => {
    const { rerender } = render(<GlossaryText text={REASON} />)
    fireEvent.click(term())
    expect(screen.getByRole('tooltip')).toBeInTheDocument()
    rerender(<GlossaryText text="⚠ Not enough fatigue" />)
    expect(screen.queryByRole('tooltip')).toBeNull()
  })

  it('hands the entry it was explaining to the full glossary', () => {
    render(<GlossaryText text={REASON} />)
    fireEvent.click(term())
    fireEvent.click(screen.getByRole('button', { name: /open glossary/i }))
    expect(mocks.openGlossary).toHaveBeenCalledWith('beat')
    expect(screen.queryByRole('tooltip')).toBeNull()
  })

  it('gives each occurrence of a word its own independently-openable card', () => {
    render(<GlossaryText text="one beat, then another beat" />)
    const terms = screen.getAllByRole('button', { name: /beat — what this means/i })
    expect(terms).toHaveLength(2)
    fireEvent.click(terms[1])
    expect(terms[0].getAttribute('aria-expanded')).toBe('false')
    expect(terms[1].getAttribute('aria-expanded')).toBe('true')
  })

  describe('on touch', () => {
    beforeEach(() => { mocks.isMobile = true })

    it('docks the card in flow instead of floating it under the thumb', () => {
      render(<GlossaryText text={REASON} />)
      fireEvent.click(term())
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

    it('hands off to the full glossary from the docked card', () => {
      render(<GlossaryText text={REASON} />)
      fireEvent.click(term())
      fireEvent.click(screen.getByRole('button', { name: /open glossary/i }))
      expect(mocks.openGlossary).toHaveBeenCalledWith('beat')
    })

    it('dismisses on a tap elsewhere', () => {
      render(<GlossaryText text={REASON} />)
      fireEvent.click(term())
      act(() => { fireEvent.touchStart(document.body) })
      expect(screen.queryByRole('tooltip')).toBeNull()
    })
  })
})
