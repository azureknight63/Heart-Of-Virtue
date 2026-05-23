import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import BookReaderDialog, { paginateText } from './BookReaderDialog'

// ---------------------------------------------------------------------------
// paginateText unit tests
// ---------------------------------------------------------------------------
describe('paginateText', () => {
  it('returns a single page for short text', () => {
    const pages = paginateText('Hello world.')
    expect(pages).toHaveLength(1)
    expect(pages[0]).toBe('Hello world.')
  })

  it('returns a single empty page for empty input', () => {
    expect(paginateText('')).toEqual([''])
    expect(paginateText(null)).toEqual([''])
  })

  it('splits long text into multiple pages at sentence boundaries', () => {
    // Build text > 800 chars with clear sentence breaks
    const sentence = 'This is one sentence. '
    const text = sentence.repeat(50) // ~1100 chars
    const pages = paginateText(text)
    expect(pages.length).toBeGreaterThan(1)
    // No page exceeds CHARS_PER_PAGE
    pages.forEach(p => expect(p.length).toBeLessThanOrEqual(800))
    // Content is preserved across all pages
    const rejoined = pages.join(' ')
    expect(rejoined).toContain('This is one sentence')
  })

  it('preserves pipe characters in text without creating spurious split points', () => {
    // A sentence containing "|" should not be split at that character
    const text = 'Jambo sells: swords | shields | potions. That is all.'
    const pages = paginateText(text)
    // All content should survive intact in a single page
    expect(pages).toHaveLength(1)
    expect(pages[0]).toContain('swords | shields | potions')
  })

  it('pipe chars in long text survive pagination intact', () => {
    const sentence = 'The ratio is 3|2 and 5|4 in all cases here now. '
    const text = sentence.repeat(25) // > 800 chars
    const pages = paginateText(text)
    const rejoined = pages.join('\n')
    // Pipe characters must be preserved
    expect(rejoined).toContain('3|2')
    expect(rejoined).toContain('5|4')
  })

  it('handles text containing only whitespace gracefully', () => {
    const pages = paginateText('   ')
    expect(pages).toHaveLength(1)
  })

  it('force-splits a single sentence longer than CHARS_PER_PAGE', () => {
    const longWord = 'x'.repeat(1000)
    const pages = paginateText(longWord)
    expect(pages.length).toBeGreaterThan(1)
    const rejoined = pages.join('')
    expect(rejoined.replace(/\s/g, '')).toBe(longWord)
  })
})

// ---------------------------------------------------------------------------
// BookReaderDialog component tests
// ---------------------------------------------------------------------------
describe('BookReaderDialog', () => {
  const mockOnClose = vi.fn()

  const shortText = 'Jean reads the scroll carefully.'
  const longText = (() => {
    const s = 'This is a sentence in a very long book. '
    return s.repeat(30) // ~1200 chars → 2 pages
  })()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the book title', () => {
    render(<BookReaderDialog title="The Lost Tome" text={shortText} onClose={mockOnClose} />)
    expect(screen.getByText('The Lost Tome')).toBeDefined()
  })

  it('renders book content', () => {
    render(<BookReaderDialog title="Book" text={shortText} onClose={mockOnClose} />)
    expect(screen.getByText(shortText)).toBeDefined()
  })

  it('does not show page indicator for single-page text', () => {
    render(<BookReaderDialog title="Book" text={shortText} onClose={mockOnClose} />)
    expect(screen.queryByText(/Page \d+ \/ \d+/)).toBeNull()
  })

  it('shows page indicator for multi-page text', () => {
    render(<BookReaderDialog title="Book" text={longText} onClose={mockOnClose} />)
    expect(screen.getByText(/Page 1 \/ \d+/)).toBeDefined()
  })

  it('NEXT button is disabled on last page and PREV on first page', () => {
    render(<BookReaderDialog title="Book" text={shortText} onClose={mockOnClose} />)
    const prev = screen.getByText('← PREV')
    const next = screen.getByText('NEXT →')
    expect(prev.disabled).toBe(true)
    expect(next.disabled).toBe(true)
  })

  it('navigates forward with NEXT and back with PREV', () => {
    render(<BookReaderDialog title="Book" text={longText} onClose={mockOnClose} />)
    const next = screen.getByText('NEXT →')
    const prev = screen.getByText('← PREV')

    expect(screen.getByText(/Page 1 \//)).toBeDefined()
    expect(prev.disabled).toBe(true)

    fireEvent.click(next)
    expect(screen.getByText(/Page 2 \//)).toBeDefined()
    expect(prev.disabled).toBe(false)

    fireEvent.click(prev)
    expect(screen.getByText(/Page 1 \//)).toBeDefined()
  })

  it('calls onClose when CLOSE BOOK is clicked', () => {
    render(<BookReaderDialog title="Book" text={shortText} onClose={mockOnClose} />)
    fireEvent.click(screen.getByText('CLOSE BOOK'))
    expect(mockOnClose).toHaveBeenCalledOnce()
  })

  it('calls onClose when Escape is pressed', () => {
    render(<BookReaderDialog title="Book" text={shortText} onClose={mockOnClose} />)
    fireEvent.keyDown(window, { key: 'Escape' })
    expect(mockOnClose).toHaveBeenCalledOnce()
  })

  it('navigates pages with ArrowRight and ArrowLeft', () => {
    render(<BookReaderDialog title="Book" text={longText} onClose={mockOnClose} />)
    expect(screen.getByText(/Page 1 \//)).toBeDefined()

    fireEvent.keyDown(window, { key: 'ArrowRight' })
    expect(screen.getByText(/Page 2 \//)).toBeDefined()

    fireEvent.keyDown(window, { key: 'ArrowLeft' })
    expect(screen.getByText(/Page 1 \//)).toBeDefined()
  })

  it('does not go below page 1 or above last page via keyboard', () => {
    render(<BookReaderDialog title="Book" text={shortText} onClose={mockOnClose} />)
    // Single-page book — ArrowLeft/Right should be no-ops
    fireEvent.keyDown(window, { key: 'ArrowLeft' })
    fireEvent.keyDown(window, { key: 'ArrowRight' })
    expect(screen.queryByText(/Page \d+ \//)).toBeNull() // still no indicator (1 page)
  })

  it('clamps safePageIdx when text shrinks without unmounting', () => {
    // Render with long text on page 2, then switch to short text without unmounting.
    const { rerender } = render(
      <BookReaderDialog title="Book" text={longText} onClose={mockOnClose} />
    )
    fireEvent.keyDown(window, { key: 'ArrowRight' })
    expect(screen.getByText(/Page 2 \//)).toBeDefined()

    // Switch to short text (1 page) — safePageIdx must clamp to 0, no crash
    rerender(<BookReaderDialog title="Book" text={shortText} onClose={mockOnClose} />)
    // Should render the short text without undefined/blank
    expect(screen.getByText(shortText)).toBeDefined()
  })
})
