import React from 'react'
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import PreVictoryNarrativeDialog from './PreVictoryNarrativeDialog'

// A CONTROLLABLE TypewriterOutput stand-in. The previous mock fired
// `onComplete` from a mount effect, so the pre-completion state never existed
// in any test — "shows a Continue button once the typewriter completes" was
// really just "shows a Continue button", and would have passed against a
// dialog that offered the button (and the ✕) before the narration had played.
vi.mock('./TypewriterOutput', () => {
  function MockTypewriterOutput({ text, speed, onComplete }) {
    return (
      <div data-testid="typewriter" data-speed={String(speed)}>
        {text}
        <button onClick={() => onComplete && onComplete()}>finish typing</button>
      </div>
    )
  }
  return { default: MockTypewriterOutput }
})

describe('PreVictoryNarrativeDialog', () => {
  const setup = (text = 'The camp erupts in cheers.') => {
    const onClose = vi.fn()
    render(<PreVictoryNarrativeDialog text={text} onClose={onClose} />)
    const finish = () => fireEvent.click(screen.getByText('finish typing'))
    return { onClose, finish }
  }

  it('forwards the narration text and speed to the typewriter', () => {
    setup('The camp erupts in cheers.')
    const tw = screen.getByTestId('typewriter')
    expect(tw.textContent).toContain('The camp erupts in cheers.')
    expect(tw.getAttribute('data-speed')).toBe('25')
  })

  it('titles itself Victory', () => {
    setup()
    expect(screen.getByText('✨ Victory').textContent).toBe('✨ Victory')
  })

  it('offers no way out until the narration finishes', () => {
    // Both exits are gated on isComplete: the Continue button is not rendered
    // and BaseDialog's ✕ is suppressed via showCloseButton={isComplete}.
    const { onClose } = setup()
    expect(screen.queryByText('Continue')).toBeNull()
    expect(screen.queryByRole('button', { name: '✕' })).toBeNull()
    expect(onClose).not.toHaveBeenCalled()
  })

  it('reveals Continue once the typewriter completes', () => {
    const { finish } = setup()
    finish()
    expect(screen.getByText('Continue').textContent).toBe('Continue')
    // The narration stays on screen behind the button.
    expect(screen.getByTestId('typewriter').textContent)
      .toContain('The camp erupts in cheers.')
  })

  it('calls onClose exactly once when Continue is clicked', () => {
    const { onClose, finish } = setup()
    finish()
    fireEvent.click(screen.getByText('Continue'))
    // Twice would advance GamePage past the victory dialog it precedes.
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('renders an empty narration without offering a premature exit', () => {
    const { onClose } = setup('')
    expect(screen.getByTestId('typewriter').textContent).toBe('finish typing')
    expect(screen.queryByText('Continue')).toBeNull()
    expect(onClose).not.toHaveBeenCalled()
  })
})
