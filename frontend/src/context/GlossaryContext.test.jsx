import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'

import { GlossaryProvider, useGlossary } from './GlossaryContext'

function Opener({ entryId = null, label = 'open' }) {
  const { openGlossary, closeGlossary, isGlossaryOpen } = useGlossary()
  return (
    <div>
      <button onClick={() => openGlossary(entryId)}>{label}</button>
      <button onClick={closeGlossary}>close from outside</button>
      <span data-testid="open-flag">{String(isGlossaryOpen)}</span>
    </div>
  )
}

const glossary = () => screen.queryByRole('dialog', { name: 'COMBAT GLOSSARY' })

describe('GlossaryProvider', () => {
  it('does not mount the panel until something opens it', () => {
    render(<GlossaryProvider><Opener /></GlossaryProvider>)
    expect(glossary()).toBeNull()
    expect(screen.getByTestId('open-flag')).toHaveTextContent('false')
  })

  it('opens the panel and reports itself open', () => {
    render(<GlossaryProvider><Opener /></GlossaryProvider>)
    fireEvent.click(screen.getByText('open'))
    expect(glossary()).toBeInTheDocument()
    expect(screen.getByTestId('open-flag')).toHaveTextContent('true')
  })

  it('returns focus to whatever opened it, rather than to the top of the document', () => {
    render(<GlossaryProvider><Opener /></GlossaryProvider>)
    const opener = screen.getByText('open')
    act(() => opener.focus())
    fireEvent.click(opener)
    // The panel takes focus for its filter box while it is open.
    expect(document.activeElement).not.toBe(opener)

    fireEvent.click(screen.getByRole('button', { name: 'Close combat glossary' }))
    expect(glossary()).toBeNull()
    expect(document.activeElement).toBe(opener)
  })

  it('survives closing when the opener has since left the document', () => {
    const { rerender } = render(<GlossaryProvider><Opener /></GlossaryProvider>)
    const opener = screen.getByText('open')
    act(() => opener.focus())
    fireEvent.click(opener)
    rerender(<GlossaryProvider><Opener label="renamed" /></GlossaryProvider>)
    expect(() => fireEvent.keyDown(document, { key: 'Escape' })).not.toThrow()
    expect(glossary()).toBeNull()
  })

  it('opens at the entry a tooltip named', () => {
    render(<GlossaryProvider><Opener entryId="heat" /></GlossaryProvider>)
    fireEvent.click(screen.getByText('open'))
    const row = screen.getByText('Heat').closest('li')
    expect(row.style.borderLeftColor).not.toBe('transparent')
  })

  it('opens on "?" from anywhere on the game surface', () => {
    render(<GlossaryProvider><Opener /></GlossaryProvider>)
    fireEvent.keyDown(document.body, { key: '?' })
    expect(glossary()).toBeInTheDocument()
  })

  it('leaves "?" alone while the player is typing it into a field', () => {
    render(
      <GlossaryProvider>
        <Opener />
        <input aria-label="chat" />
        <textarea aria-label="notes" />
      </GlossaryProvider>
    )
    fireEvent.keyDown(screen.getByLabelText('chat'), { key: '?' })
    expect(glossary()).toBeNull()
    fireEvent.keyDown(screen.getByLabelText('notes'), { key: '?' })
    expect(glossary()).toBeNull()
  })

  it('leaves "?" alone in a contenteditable, and when it carries a modifier', () => {
    render(
      <GlossaryProvider>
        <div contentEditable data-testid="editable" suppressContentEditableWarning />
      </GlossaryProvider>
    )
    const editable = screen.getByTestId('editable')
    // jsdom does not implement isContentEditable from the attribute alone.
    Object.defineProperty(editable, 'isContentEditable', { value: true })
    fireEvent.keyDown(editable, { key: '?' })
    expect(glossary()).toBeNull()

    fireEvent.keyDown(document.body, { key: '?', ctrlKey: true })
    expect(glossary()).toBeNull()
    fireEvent.keyDown(document.body, { key: 'a' })
    expect(glossary()).toBeNull()
  })

  it('does not lose the original opener when "?" is pressed again while open', () => {
    render(<GlossaryProvider><Opener /></GlossaryProvider>)
    const opener = screen.getByText('open')
    act(() => opener.focus())
    fireEvent.click(opener)

    // A second "?" lands on the panel's own filter box, which must not become
    // the thing focus returns to once the panel closes.
    fireEvent.keyDown(document.body, { key: '?' })
    fireEvent.click(screen.getByRole('button', { name: 'Close combat glossary' }))
    expect(document.activeElement).toBe(opener)
  })

  it('is inert, not fatal, for a component rendered outside a provider', () => {
    const spy = vi.fn()
    function Bare() {
      const { openGlossary, closeGlossary, isGlossaryOpen } = useGlossary()
      spy(isGlossaryOpen)
      return <button onClick={() => { openGlossary('beat'); closeGlossary() }}>bare</button>
    }
    render(<Bare />)
    expect(() => fireEvent.click(screen.getByText('bare'))).not.toThrow()
    expect(spy).toHaveBeenCalledWith(false)
    expect(glossary()).toBeNull()
  })
})
