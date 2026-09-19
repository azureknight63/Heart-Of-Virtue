import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import CollapsibleSectionHeader from './CollapsibleSectionHeader'
import { DISCLOSURE_GLYPHS, accessibility } from '../styles/theme'

/**
 * Issue #625: three fold toggles (InteractPanel's category headers, HeatMeter's
 * "what moves it" helper, CollapsibleRoomDescription's title bar) each carried
 * their own accessibility contract, and only the first carried a complete one.
 * These tests pin the contract this component now owns for all three.
 */
const renderHeader = (props = {}) =>
  render(
    <CollapsibleSectionHeader
      expanded={false}
      onToggle={() => {}}
      controlsId="section-body"
      {...props}
    >
      <span>Section</span>
    </CollapsibleSectionHeader>
  )

describe('CollapsibleSectionHeader', () => {
  it('is a real button, and type="button" so it cannot submit a form', () => {
    renderHeader()
    const header = screen.getByRole('button')
    expect(header.tagName).toBe('BUTTON')
    expect(header.getAttribute('type')).toBe('button')
  })

  it('announces its state through aria-expanded', () => {
    const { rerender } = renderHeader({ expanded: false })
    expect(screen.getByRole('button')).toHaveAttribute('aria-expanded', 'false')

    rerender(
      <CollapsibleSectionHeader expanded onToggle={() => {}} controlsId="section-body">
        <span>Section</span>
      </CollapsibleSectionHeader>
    )
    expect(screen.getByRole('button')).toHaveAttribute('aria-expanded', 'true')
  })

  it('points at the region it folds through aria-controls', () => {
    renderHeader({ controlsId: 'rules-panel' })
    expect(screen.getByRole('button')).toHaveAttribute('aria-controls', 'rules-panel')
  })

  it('shows the state as a glyph, so it is never colour-only', () => {
    const { rerender } = renderHeader({ expanded: false })
    expect(screen.getByRole('button').textContent.trim()).toMatch(
      new RegExp(`^${DISCLOSURE_GLYPHS.collapsed}`)
    )

    rerender(
      <CollapsibleSectionHeader expanded onToggle={() => {}} controlsId="section-body">
        <span>Section</span>
      </CollapsibleSectionHeader>
    )
    expect(screen.getByRole('button').textContent.trim()).toMatch(
      new RegExp(`^${DISCLOSURE_GLYPHS.expanded}`)
    )
  })

  it('hides the glyph from assistive tech so the accessible name is the label', () => {
    renderHeader()
    // "▸ Section" would be read out glyph and all without this.
    expect(screen.getByRole('button', { name: 'Section' })).toBeInTheDocument()
  })

  it('calls onToggle when clicked', () => {
    const onToggle = vi.fn()
    renderHeader({ onToggle })
    fireEvent.click(screen.getByRole('button'))
    expect(onToggle).toHaveBeenCalledTimes(1)
  })

  it('meets the touch-target minimum by default', () => {
    renderHeader()
    expect(screen.getByRole('button').style.minHeight).toBe(accessibility.touchTarget)
  })

  it('drops the height floor only when a caller asks for compact', () => {
    // The one opt-out: HeatMeter's helper sits inside a vertical-budgeted
    // combat panel and takes the floor on touch pointers only (issue #580).
    renderHeader({ compact: true })
    expect(screen.getByRole('button').style.minHeight).toBe('')
  })

  it('lets a caller restyle it without losing the contract', () => {
    renderHeader({ style: { color: 'rgb(1, 2, 3)', fontSize: '9px' } })
    const header = screen.getByRole('button')
    expect(header.style.color).toBe('rgb(1, 2, 3)')
    expect(header.style.fontSize).toBe('9px')
    // Contract survives the override.
    expect(header.getAttribute('type')).toBe('button')
    expect(header.style.minHeight).toBe(accessibility.touchTarget)
  })

  it('renders the label after the glyph with real whitespace between them', () => {
    // Flex `gap` spaces the spans visually but leaves the DOM text as
    // "▸Section", which is what assistive tech reads.
    renderHeader()
    expect(screen.getByRole('button').textContent).toContain(
      `${DISCLOSURE_GLYPHS.collapsed} Section`
    )
  })
})
