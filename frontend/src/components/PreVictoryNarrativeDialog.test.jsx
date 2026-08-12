import React from 'react'
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import PreVictoryNarrativeDialog from './PreVictoryNarrativeDialog'

// TypewriterOutput fires onComplete immediately so tests don't need fake timers.
vi.mock('./TypewriterOutput', () => {
  // Named with a capital so the hooks lint rule can see this is a component;
  // as an inline `default:` arrow it read as a plain function calling a hook.
  function MockTypewriterOutput({ text, onComplete }) {
    React.useEffect(() => {
      onComplete && onComplete()
    }, [])
    return <div data-testid="typewriter">{text}</div>
  }
  return { default: MockTypewriterOutput }
})

describe('PreVictoryNarrativeDialog', () => {
  it('renders the narration text', () => {
    render(<PreVictoryNarrativeDialog text="The camp erupts in cheers." onClose={vi.fn()} />)
    expect(screen.getByText('The camp erupts in cheers.')).toBeInTheDocument()
  })

  it('shows a Continue button once the typewriter completes', () => {
    render(<PreVictoryNarrativeDialog text="Victory is ours." onClose={vi.fn()} />)
    expect(screen.getByText('Continue')).toBeInTheDocument()
  })

  it('calls onClose when Continue is clicked', () => {
    const onClose = vi.fn()
    render(<PreVictoryNarrativeDialog text="Victory is ours." onClose={onClose} />)
    screen.getByText('Continue').click()
    expect(onClose).toHaveBeenCalled()
  })
})
