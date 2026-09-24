import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import AttributePointAllocator from './AttributePointAllocator'

/**
 * A live browser check (2026-09-19) found both allocator controls unnamed:
 * the accessibility tree read `combobox "Strength (16)"` (the selected
 * option, not a label) and `textbox "1"` (the current value). A screen
 * reader announced a value with no question attached to it.
 */
const makeProps = (overrides = {}) => ({
  attrOptions: [
    { key: 'strength_base', label: 'Strength', value: 16 },
    { key: 'faith_base', label: 'Faith', value: 9 },
  ],
  selectedAttr: 'strength_base',
  onSelectAttr: vi.fn(),
  amount: '1',
  onAmountChange: vi.fn(),
  onAllocate: vi.fn(),
  onRandomize: vi.fn(),
  remainingPoints: 3,
  isSubmitting: false,
  error: null,
  ...overrides,
})

describe('AttributePointAllocator accessible names', () => {
  it('names the attribute picker', () => {
    render(<AttributePointAllocator {...makeProps()} />)
    expect(screen.getByRole('combobox', { name: /attribute/i })).toBeInTheDocument()
  })

  it('names the points input', () => {
    render(<AttributePointAllocator {...makeProps()} />)
    expect(screen.getByRole('spinbutton', { name: /points/i })).toBeInTheDocument()
  })

  // jsdom applies no stylesheet, so toBeVisible cannot catch a class-based
  // visually-hidden label; this pins the names to <label> text, not aria-label.
  it('takes both names from <label> elements, so sighted and voice-control players see them', () => {
    render(<AttributePointAllocator {...makeProps()} />)
    expect(screen.getByText(/attribute/i, { selector: 'label' })).toBeVisible()
    expect(screen.getByText(/points/i, { selector: 'label' })).toBeVisible()
  })

  it('keeps each label on its own control when two allocators are mounted', () => {
    // A hard-coded id would point both labels at the first allocator's
    // controls and leave the second pair unnamed.
    render(
      <>
        <AttributePointAllocator {...makeProps()} />
        <AttributePointAllocator {...makeProps()} />
      </>
    )
    expect(screen.getAllByRole('combobox', { name: /attribute/i })).toHaveLength(2)
    expect(screen.getAllByRole('spinbutton', { name: /points/i })).toHaveLength(2)
  })
})

describe('AttributePointAllocator touch sizing', () => {
  it('gives both fields the 44px touch floor and a 16px font (no iOS focus zoom)', () => {
    render(<AttributePointAllocator {...makeProps()} />)
    for (const field of [screen.getByRole('combobox'), screen.getByRole('spinbutton')]) {
      expect(field.style.minHeight).toBe('44px')
      expect(field.style.fontSize).toBe('16px')
    }
  })
})
