import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import ChangelogPanel from './ChangelogPanel'
import { CHANGELOG } from '../data/changelog'
import { expectFoldContract } from '../test/foldContract'

describe('ChangelogPanel', () => {
  it('renders the toggle button with the latest version number', () => {
    render(<ChangelogPanel />)
    expect(screen.getByText(`Changelog (v${CHANGELOG[0].version})`)).toBeDefined()
  })

  it('hides entries by default', () => {
    render(<ChangelogPanel />)
    expect(screen.queryByText(CHANGELOG[0].highlights[0])).toBeNull()
    expect(screen.getByRole('button')).toHaveProperty('ariaExpanded', 'false')
  })

  it('shows entries by default when defaultOpen is true', () => {
    render(<ChangelogPanel defaultOpen={true} />)
    expect(screen.getByText(CHANGELOG[0].highlights[0])).toBeDefined()
  })

  it('toggles entries open on click when closed', () => {
    render(<ChangelogPanel />)
    fireEvent.click(screen.getByRole('button'))
    expect(screen.getByText(CHANGELOG[0].highlights[0])).toBeDefined()
    expect(screen.getByRole('button')).toHaveProperty('ariaExpanded', 'true')
  })

  it('toggles entries closed on click when open', () => {
    render(<ChangelogPanel defaultOpen={true} />)
    fireEvent.click(screen.getByRole('button'))
    expect(screen.queryByText(CHANGELOG[0].highlights[0])).toBeNull()
  })

  it('renders every changelog entry version and its highlights when open', () => {
    render(<ChangelogPanel defaultOpen={true} />)
    CHANGELOG.forEach((entry) => {
      expect(screen.getByText(`v${entry.version} — ${entry.date}`)).toBeDefined()
      entry.highlights.forEach((highlight) => {
        expect(screen.getByText(highlight)).toBeDefined()
      })
    })
  })

  // Issue #640: moved onto CollapsibleSectionHeader. It had aria-expanded but
  // no aria-controls, and a rotating ▼ as its only state signal.
  it('honours the fold contract in both states', () => {
    render(<ChangelogPanel />)
    const header = screen.getByRole('button', { name: /changelog/i })
    const region = expectFoldContract(header, { expanded: false })
    expect(region.textContent).toBe('')

    fireEvent.click(header)
    expect(expectFoldContract(header, { expanded: true })).toBe(region)
    expect(region.textContent).toContain(CHANGELOG[0].highlights[0])
  })
})
