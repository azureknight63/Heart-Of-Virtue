import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

import GlossaryTooltipCard from './GlossaryTooltipCard'
import { getGlossaryEntry } from '../data/combatGlossary'

const beat = getGlossaryEntry('beat')

describe('GlossaryTooltipCard', () => {
  it('shows the short definition and the how-you-see-it line, not the long body', () => {
    render(<GlossaryTooltipCard entry={beat} />)
    expect(screen.getByRole('tooltip')).toBeInTheDocument()
    expect(screen.getByText(beat.term)).toBeInTheDocument()
    expect(screen.getByText(beat.short)).toBeInTheDocument()
    expect(screen.getByText(beat.tell)).toBeInTheDocument()
    expect(screen.queryByText(beat.body)).toBeNull()
  })

  it('hands off to the full glossary', () => {
    const onOpenGlossary = vi.fn()
    render(<GlossaryTooltipCard entry={beat} onOpenGlossary={onOpenGlossary} />)
    fireEvent.click(screen.getByRole('button', { name: /open glossary/i }))
    expect(onOpenGlossary).toHaveBeenCalledTimes(1)
  })

  it('floats above the term when asked, with the pointer on its underside', () => {
    const { container } = render(<GlossaryTooltipCard entry={beat} placement="top" />)
    const card = screen.getByRole('tooltip')
    expect(card.style.position).toBe('absolute')
    // Flush against the term, with the visual gap paid for in padding — see
    // "pays for the gap in padding" below.
    expect(card.style.bottom).toBe('100%')
    expect(card.style.paddingBottom).toBe('9px')
    const arrow = container.querySelector('[aria-hidden="true"]')
    expect(arrow.style.bottom).toBe('-7px')
  })

  it('flips below the term, pointer on top, when there is no room above', () => {
    const { container } = render(<GlossaryTooltipCard entry={beat} placement="bottom" />)
    const card = screen.getByRole('tooltip')
    expect(card.style.top).toBe('100%')
    expect(card.style.paddingTop).toBe('9px')
    expect(container.querySelector('[aria-hidden="true"]').style.top).toBe('-7px')
  })

  it('pays for the gap to the term in padding, not in an offset', () => {
    // An offset gap is 9px of *nothing* between the term and the card. The
    // term's wrapper dismisses on mouseleave, so crossing that nothing
    // dismissed the card the pointer was travelling to, and the hand-off
    // button could not be reached with a mouse at all. Padding keeps the two
    // boxes contiguous; the chrome moves to an inner element so the padding
    // stays invisible.
    render(<GlossaryTooltipCard entry={beat} placement="bottom" />)
    const card = screen.getByRole('tooltip')
    expect(card.style.top).not.toMatch(/calc/)
    // The positioning box draws nothing itself.
    expect(card.style.backgroundColor).toBe('')
    expect(card.style.border).toBe('')
    const chrome = card.firstElementChild
    expect(chrome.style.backgroundColor).not.toBe('')
    expect(chrome.style.border).not.toBe('')
    expect(chrome).toContainElement(screen.getByText(beat.short))
  })

  it('docks in flow with no pointer, so a thumb cannot cover it', () => {
    const { container } = render(<GlossaryTooltipCard entry={beat} docked />)
    const card = screen.getByRole('tooltip')
    expect(card.style.position).toBe('relative')
    expect(card.style.width).toBe('100%')
    // Nothing to bridge: the docked card sits in flow under the line.
    expect(card.style.paddingTop).toBe('')
    expect(card.style.paddingBottom).toBe('')
    expect(container.querySelector('[aria-hidden="true"]')).toBeNull()
  })

  it('carries the id the term points its aria-describedby at', () => {
    render(<GlossaryTooltipCard entry={beat} id="tip-1" />)
    expect(screen.getByRole('tooltip').id).toBe('tip-1')
  })
})
