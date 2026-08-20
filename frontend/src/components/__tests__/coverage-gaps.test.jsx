/**
 * Coverage Gap Tests - Targeted tests to reach 95%+ coverage
 * Focuses on uncovered branches and edge cases in key components
 */

import React from 'react'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import GameInput from '../GameInput'
import GameButton from '../GameButton'
import RoomContents from '../RoomContents'
import { colors } from '../../styles/theme'

describe('Coverage Gap Tests', () => {
  describe('GameInput Edge Cases', () => {
    it('handles maxLength prop correctly', () => {
      const handleChange = vi.fn()
      const { container } = render(
        <GameInput
          value="test"
          onChange={handleChange}
          maxLength={5}
          placeholder="Type..."
        />
      )
      const input = container.querySelector('input')
      expect(input.maxLength).toBe(5)
    })

    it('disables input when disabled prop is true', () => {
      const handleChange = vi.fn()
      const { container } = render(
        <GameInput
          value="test"
          onChange={handleChange}
          disabled={true}
          placeholder="Type..."
        />
      )
      const input = container.querySelector('input')
      expect(input.disabled).toBe(true)
      fireEvent.change(input, { target: { value: 'new' } })
      // onChange should still fire even though input is disabled (browser behavior)
      expect(handleChange).toHaveBeenCalled()
    })

    it('handles autoFocus prop', () => {
      const { container } = render(
        <GameInput
          value=""
          onChange={vi.fn()}
          autoFocus={true}
          placeholder="Type..."
        />
      )
      const input = container.querySelector('input')
      expect(input).toHaveFocus()
    })

    it('renders with specific placeholder', () => {
      const { container } = render(
        <GameInput
          value="test"
          onChange={vi.fn()}
          placeholder="Enter text..."
        />
      )
      const input = container.querySelector('input')
      expect(input.placeholder).toBe('Enter text...')
    })
  })

  describe('GameButton Variant Coverage', () => {
    // The four tests that used to open this block ("renders with danger /
    // warning / success variant", "applies size prop correctly") each asserted
    // only `expect(button).toBeInTheDocument()`. Removing every variant and
    // size style from GameButton.jsx would have left all four green, and one
    // of them passed `variant="success"`, which GameButton.jsx does not define
    // at all. The real per-variant and per-size style assertions live in
    // GameButton.test.jsx's "Variants" and "Sizes" blocks, which cover the same
    // lines and actually read the resulting backgroundColor/borderColor/
    // fontSize — so these were deleted rather than duplicated here.

    it('disables button when disabled prop is true', () => {
      const onClick = vi.fn()
      const { container } = render(
        <GameButton disabled={true} onClick={onClick}>
          Disabled
        </GameButton>
      )
      const button = container.querySelector('button')
      expect(button.disabled).toBe(true)
      fireEvent.click(button)
      expect(onClick).not.toHaveBeenCalled()
    })

    it('applies custom className', () => {
      const { container } = render(
        <GameButton className="custom-class" onClick={vi.fn()}>
          Custom
        </GameButton>
      )
      const button = container.querySelector('button')
      expect(button).toHaveClass('custom-class')
    })

    it('applies custom style', () => {
      const { container } = render(
        <GameButton style={{ padding: '10px' }} onClick={vi.fn()}>
          Styled
        </GameButton>
      )
      const button = container.querySelector('button')
      expect(button).toHaveStyle({ padding: '10px' })
    })
  })

  // A "RoomContents Edge Cases" block used to sit here with six tests (null
  // location, empty content, items, hidden items, NPCs, objects). Every one is
  // strictly subsumed by the "Resilience to absent data" and "Interaction
  // wiring on room entities" blocks further down THIS file, which drive the
  // same component with the same inputs and assert more (the empty-room line,
  // the default "There is a X here." phrasing, per-entity skipping). They were
  // removed rather than kept as a second, weaker copy.

  describe('Props Combination Coverage', () => {
    it('composes variant, size and className without one clobbering another', () => {
      // The point of this test is that the three style sources merge; the
      // previous version asserted only the className, so a variant or size
      // regression passed straight through it.
      const { container } = render(
        <GameButton
          variant="danger"
          size="large"
          disabled={false}
          className="custom"
          onClick={vi.fn()}
        >
          Multi-prop Button
        </GameButton>
      )
      const button = container.querySelector('button')
      expect(button).toHaveClass('game-btn', 'custom')
      expect(button).toHaveStyle({ backgroundColor: colors.danger, borderColor: colors.danger })
      expect(button).toHaveStyle({ fontSize: '15px', padding: '12px 24px' })
      expect(button.disabled).toBe(false)
    })

    it('handles prop overrides correctly', () => {
      const { container } = render(
        <GameInput
          value="test"
          onChange={vi.fn()}
          placeholder="Type..."
          disabled={true}
          maxLength={10}
          autoFocus={true}
        />
      )
      const input = container.querySelector('input')
      expect(input.disabled).toBe(true)
      expect(input.maxLength).toBe(10)
      expect(input.placeholder).toBe('Type...')
    })
  })

  // The blocks below replace ~21 tests that rendered inline <div> literals and
  // asserted on React's own semantics (conditional rendering, event dispatch,
  // list keys, inline styles, ARIA on bare elements). They tested React, not
  // this project. Each theme is now exercised against the real components this
  // file already imports.

  describe('Resilience to absent data', () => {
    it('renders nothing when RoomContents has no location', () => {
      const { container } = render(<RoomContents location={null} onInteract={vi.fn()} />)
      expect(container.firstChild).toBeNull()
    })

    it('shows the empty-room line when a location has no contents', () => {
      render(<RoomContents location={{ description: 'A bare cell.' }} onInteract={vi.fn()} />)
      expect(screen.getByText('A bare cell.')).toBeInTheDocument()
      expect(screen.getByText('(Nothing else here...)')).toBeInTheDocument()
    })

    it('renders a GameButton with no onClick without crashing when clicked', () => {
      render(<GameButton>Inert</GameButton>)
      expect(() => fireEvent.click(screen.getByText('Inert'))).not.toThrow()
    })
  })

  describe('State updates through the real input', () => {
    it('drives a controlled value through successive keystrokes', () => {
      // Read the value inside the handler: GameInput passes the DOM node
      // straight through, so by the time a spy's recorded event is inspected
      // React has already reset input.value to match the value prop.
      const seen = []
      function Harness() {
        const [value, setValue] = React.useState('')
        return (
          <GameInput
            value={value}
            onChange={(e) => { seen.push(e.target.value); setValue(e.target.value) }}
          />
        )
      }
      const { container } = render(<Harness />)
      const input = container.querySelector('input')

      fireEvent.change(input, { target: { value: 'a' } })
      fireEvent.change(input, { target: { value: 'ab' } })

      expect(seen).toEqual(['a', 'ab'])
      expect(input.value).toBe('ab')
    })

    it('forwards disabled to the DOM input, so focus and typing are blocked', () => {
      // Renamed from "does not emit change events while disabled", which the
      // body never checked — and could not: fireEvent.change dispatches
      // directly and bypasses the disabled gate a real user hits. What IS
      // assertable is that the flag reaches the DOM node, which is what makes
      // the browser refuse focus and keystrokes.
      const onChange = vi.fn()
      const { container } = render(<GameInput value="" onChange={onChange} disabled />)
      const input = container.querySelector('input')

      expect(input.disabled).toBe(true)
      input.focus()
      expect(input).not.toHaveFocus()
      fireEvent.keyDown(input, { key: 'a' })
      expect(onChange).not.toHaveBeenCalled()
    })
  })

  describe('Interaction wiring on room entities', () => {
    it('renders an item announcement and its default phrasing', () => {
      const location = {
        description: 'A storeroom.',
        items: [
          { id: 1, name: 'Restorative', announce: 'A vial glints on the shelf.' },
          { id: 2, name: 'Rusted Key' },
        ],
      }
      const { container } = render(<RoomContents location={location} onInteract={vi.fn()} />)
      // renderTextWithLinks splits entity names into their own clickable nodes,
      // so assert on the assembled text rather than a single text node.
      expect(container.textContent).toContain('A vial glints on the shelf.')
      expect(container.textContent).toContain('There is a Rusted Key here.')
    })

    it('omits hidden entities from the room narrative', () => {
      const location = {
        description: 'A quiet hall.',
        items: [{ id: 1, name: 'Hidden Cache', announce: 'You should not see this.', hidden: true }],
      }
      render(<RoomContents location={location} onInteract={vi.fn()} />)
      expect(screen.queryByText(/You should not see this\./)).toBeNull()
      expect(screen.getByText('(Nothing else here...)')).toBeInTheDocument()
    })

    it('renders NPC and object idle messages, skipping those without one', () => {
      const location = {
        description: 'A workshop.',
        npcs: [
          { id: 'n1', name: 'Gorran', idle_message: 'Gorran sharpens a blade.' },
          { id: 'n2', name: 'Silent Watcher' },
        ],
        objects: [{ id: 'o1', name: 'Anvil', idle_message: 'The anvil is scarred from long use.' }],
      }
      const { container } = render(<RoomContents location={location} onInteract={vi.fn()} />)
      expect(container.textContent).toContain('Gorran sharpens a blade.')
      expect(container.textContent).toContain('The anvil is scarred from long use.')
      expect(container.textContent).not.toContain('Silent Watcher')
    })
  })

  describe('Rendering many entities', () => {
    it('renders one line per announced item without collapsing duplicates', () => {
      const location = {
        description: 'A hoard.',
        items: Array.from({ length: 8 }, (_, i) => ({ id: i, name: 'Gold Coin' })),
      }
      const { container } = render(<RoomContents location={location} onInteract={vi.fn()} />)
      const occurrences = container.textContent.split('There is a Gold Coin here.').length - 1
      expect(occurrences).toBe(8)
    })
  })
})
