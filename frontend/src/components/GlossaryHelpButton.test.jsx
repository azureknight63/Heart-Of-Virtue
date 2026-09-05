import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

import GlossaryHelpButton from './GlossaryHelpButton'
import { accessibility, colors } from '../styles/theme'

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
    const resting = button.style.borderColor

    fireEvent.mouseEnter(button)
    expect(button.style.borderColor).not.toBe(resting)
    fireEvent.mouseLeave(button)
    expect(button.style.borderColor).toBe(resting)

    fireEvent.focus(button)
    expect(button.style.boxShadow).not.toBe('none')
    fireEvent.blur(button)
    expect(button.style.boxShadow).toBe('none')
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

  it('draws itself in the theme’s information colour, not a copied hex', () => {
    render(<GlossaryHelpButton />)
    const button = screen.getByRole('button')
    expect(button.style.color).toBe('rgb(0, 204, 255)')
    expect(colors.accent).toBe('#00ccff')
  })
})
