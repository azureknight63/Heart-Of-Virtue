import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

import GlossaryHelpButton from './GlossaryHelpButton'
import { accessibility, colors } from '../styles/theme'
import { hexToRgb } from '../test/hexToRgb'

const mocks = vi.hoisted(() => ({ isMobile: false, openGlossary: vi.fn() }))

vi.mock('../hooks/useMobile', () => ({ useMobile: () => mocks.isMobile }))
vi.mock('../context/GlossaryContext', () => ({
  useGlossary: () => ({ openGlossary: mocks.openGlossary, closeGlossary: vi.fn(), isGlossaryOpen: false }),
}))

beforeEach(() => {
  mocks.isMobile = false
  mocks.openGlossary.mockClear()
})

describe('GlossaryHelpButton', () => {
  it('is reachable and named for a screen reader, not just a bare "?"', () => {
    render(<GlossaryHelpButton />)
    const button = screen.getByRole('button', { name: 'Open combat glossary' })
    expect(button).toHaveTextContent('?')
    expect(button.getAttribute('title')).toBe('Open combat glossary')
  })

  it('opens the glossary, with no entry singled out', () => {
    render(<GlossaryHelpButton />)
    fireEvent.click(screen.getByRole('button'))
    expect(mocks.openGlossary).toHaveBeenCalledWith(null)
  })

  it('opens the glossary at a named entry when one is given', () => {
    render(<GlossaryHelpButton entryId="beat" label="What is a beat?" />)
    fireEvent.click(screen.getByRole('button', { name: 'What is a beat?' }))
    expect(mocks.openGlossary).toHaveBeenCalledWith('beat')
  })

  it('lights up on hover and on keyboard focus alike', () => {
    render(<GlossaryHelpButton />)
    const button = screen.getByRole('button')
    // "alike" is the claim, so capture the whole visual state and compare the
    // two paths against each other — not one property per path, which would
    // pass even if hover and focus rendered differently.
    const snapshot = () => [button.style.borderColor, button.style.backgroundColor,
      button.style.boxShadow, button.style.color].join(' | ')
    const resting = snapshot()

    fireEvent.mouseEnter(button)
    const hovered = snapshot()
    expect(hovered).not.toBe(resting)
    fireEvent.mouseLeave(button)
    expect(snapshot()).toBe(resting)

    fireEvent.focus(button)
    expect(snapshot()).toBe(hovered)
    fireEvent.blur(button)
    expect(snapshot()).toBe(resting)
  })

  it('is an 18px circle on a pointer device', () => {
    render(<GlossaryHelpButton />)
    const button = screen.getByRole('button')
    expect(button.style.width).toBe('18px')
    expect(button.style.borderRadius).toBe('50%')
  })

  it('grows to the platform minimum touch target on touch', () => {
    mocks.isMobile = true
    render(<GlossaryHelpButton />)
    const button = screen.getByRole('button')
    expect(button.style.width).toBe(accessibility.touchTarget)
    expect(button.style.height).toBe(accessibility.touchTarget)
  })

  it('accepts layout overrides from the strip it sits in', () => {
    render(<GlossaryHelpButton style={{ marginLeft: 'auto' }} />)
    expect(screen.getByRole('button').style.marginLeft).toBe('auto')
  })

  it('reads its glyph colour from the accent token rather than inlining a hex', () => {
    render(<GlossaryHelpButton />)
    // Derived from the token, so a component that inlined the same hex would
    // still pass — but a component that stopped tracking the token would not.
    expect(screen.getByRole('button').style.color).toBe(hexToRgb(colors.accent))
  })

  it('keeps its own size and shape when the container passes layout styles', () => {
    mocks.isMobile = true
    // A caller reaching for width/height must not be able to shrink the button
    // below the platform minimum touch target the component promises.
    render(<GlossaryHelpButton style={{ marginLeft: 'auto', width: '4px', height: '4px' }} />)
    const button = screen.getByRole('button')
    expect(button.style.marginLeft).toBe('auto')
    expect(button.style.width).toBe(accessibility.touchTarget)
    expect(button.style.height).toBe(accessibility.touchTarget)
  })
})
