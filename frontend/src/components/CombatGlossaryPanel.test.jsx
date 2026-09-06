import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, within } from '@testing-library/react'

import CombatGlossaryPanel from './CombatGlossaryPanel'
import { GLOSSARY_ENTRIES, getGlossaryEntry } from '../data/combatGlossary'

const mocks = vi.hoisted(() => ({ isMobile: false, hasMore: false }))

vi.mock('../hooks/useMobile', () => ({ useMobile: () => mocks.isMobile }))
vi.mock('../hooks/useHorizontalScrollEnd', () => ({
  default: () => ({ hasMore: mocks.hasMore, ref: () => {}, check: () => {} }),
}))

const entriesShown = () => within(screen.getByRole('list')).getAllByRole('heading', { level: 4 })

beforeEach(() => {
  mocks.isMobile = false
  mocks.hasMore = false
})

describe('CombatGlossaryPanel', () => {
  it('is a labelled dialog listing every term', () => {
    render(<CombatGlossaryPanel onClose={() => {}} />)
    const dialog = screen.getByRole('dialog', { name: 'COMBAT GLOSSARY' })
    expect(dialog.getAttribute('aria-modal')).toBe('true')
    expect(entriesShown()).toHaveLength(GLOSSARY_ENTRIES.length)
  })

  it('puts the keyboard straight into the filter box', () => {
    render(<CombatGlossaryPanel onClose={() => {}} />)
    expect(document.activeElement).toBe(screen.getByLabelText('Filter glossary terms'))
  })

  it('renders the long body, not the tooltip’s short form', () => {
    render(<CombatGlossaryPanel onClose={() => {}} />)
    const beat = getGlossaryEntry('beat')
    expect(screen.getByText(beat.tell)).toBeInTheDocument()
    expect(screen.queryByText(beat.short)).toBeNull()
  })

  it('splits a multi-line body into its own paragraphs', () => {
    render(<CombatGlossaryPanel onClose={() => {}} />)
    const stages = getGlossaryEntry('stages')
    for (const line of stages.body.split('\n')) {
      expect(screen.getByText(line)).toBeInTheDocument()
    }
  })

  it('filters as the player types, and says so when nothing matches', () => {
    render(<CombatGlossaryPanel onClose={() => {}} />)
    const search = screen.getByLabelText('Filter glossary terms')

    fireEvent.change(search, { target: { value: 'backswing' } })
    expect(entriesShown().map(h => h.textContent)).toEqual(['The four stages'])

    fireEvent.change(search, { target: { value: 'zzzz' } })
    expect(screen.queryAllByRole('heading', { level: 4 })).toHaveLength(0)
    expect(screen.getByText('No terms match that filter.')).toBeInTheDocument()
  })

  it('narrows to a category and back to All', () => {
    render(<CombatGlossaryPanel onClose={() => {}} />)
    const all = screen.getByRole('button', { name: 'All' })
    const resources = screen.getByRole('button', { name: 'Resources' })
    expect(all.getAttribute('aria-pressed')).toBe('true')

    fireEvent.click(resources)
    expect(resources.getAttribute('aria-pressed')).toBe('true')
    expect(all.getAttribute('aria-pressed')).toBe('false')
    const shown = entriesShown().map(h => h.textContent)
    expect(shown).toContain('Heat')
    expect(shown).not.toContain('Beat')

    fireEvent.click(all)
    expect(entriesShown()).toHaveLength(GLOSSARY_ENTRIES.length)
  })

  it('closes on the ✕, on Escape, and on a click outside — but not inside', () => {
    const onClose = vi.fn()
    const { container } = render(<CombatGlossaryPanel onClose={onClose} />)

    fireEvent.click(screen.getByRole('dialog'))
    expect(onClose).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: 'Close combat glossary' }))
    expect(onClose).toHaveBeenCalledTimes(1)

    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).toHaveBeenCalledTimes(2)

    fireEvent.keyDown(document, { key: 'a' })
    expect(onClose).toHaveBeenCalledTimes(2)

    fireEvent.click(container.firstChild)
    expect(onClose).toHaveBeenCalledTimes(3)
  })

  it('brings the entry a tooltip handed off into view and marks it', () => {
    const scrollIntoView = vi.fn()
    const original = Element.prototype.scrollIntoView
    Element.prototype.scrollIntoView = scrollIntoView
    try {
      render(<CombatGlossaryPanel onClose={() => {}} focusEntryId="heat" />)
      expect(scrollIntoView).toHaveBeenCalledWith({ block: 'center' })
      const row = screen.getByText('Heat').closest('li')
      expect(row.style.borderLeftColor).not.toBe('transparent')
    } finally {
      Element.prototype.scrollIntoView = original
    }
  })

  it('does not scroll anywhere when no entry was singled out', () => {
    const scrollIntoView = vi.fn()
    const original = Element.prototype.scrollIntoView
    Element.prototype.scrollIntoView = scrollIntoView
    try {
      render(<CombatGlossaryPanel onClose={() => {}} />)
      expect(scrollIntoView).not.toHaveBeenCalled()
    } finally {
      Element.prototype.scrollIntoView = original
    }
  })

  it('hides the filter-row scroll cue once the row is scrolled to its end', () => {
    render(<CombatGlossaryPanel onClose={() => {}} />)
    expect(screen.queryByTestId('glossary-filter-scroll-cue')).toBeNull()
  })

  it('shows the scroll cue while the filter row still has chips off its right edge', () => {
    mocks.hasMore = true
    render(<CombatGlossaryPanel onClose={() => {}} />)
    expect(screen.getByTestId('glossary-filter-scroll-cue')).toBeInTheDocument()
  })

  it('becomes a full-height sheet with a grabber on touch', () => {
    mocks.isMobile = true
    render(<CombatGlossaryPanel onClose={() => {}} />)
    const dialog = screen.getByRole('dialog')
    expect(dialog.style.position).toBe('fixed')
    expect(dialog.style.top).toBe('52px')
    expect(dialog.style.borderRadius).toBe('8px 8px 0 0')
  })
})
