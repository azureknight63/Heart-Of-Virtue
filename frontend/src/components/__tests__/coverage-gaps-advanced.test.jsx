/**
 * Advanced Coverage Gap Tests - Deep coverage for complex components
 * Focuses on specific low-coverage areas and branch paths
 */

import React from 'react'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import GamePanel from '../GamePanel'
import StatsPanel from '../StatsPanel'
import SkillsPanel from '../SkillsPanel'
import CooldownTray from '../CooldownTray'
import CombatLog from '../CombatLog'
import { colors } from '../../styles/theme'
import { makePlayer } from '../../test/payloads'

describe('Advanced Coverage Gap Tests', () => {
  describe('GamePanel Advanced Coverage', () => {
    const mockOnClose = vi.fn()

    beforeEach(() => {
      vi.clearAllMocks()
    })

    it('renders with title and onClose handler', () => {
      render(
        <GamePanel title="Test Panel" onClose={mockOnClose}>
          <p>Content</p>
        </GamePanel>
      )
      expect(screen.getByText('Test Panel')).toBeInTheDocument()
    })

    it('renders without title but with onClose', () => {
      render(
        <GamePanel onClose={mockOnClose}>
          <p>Content</p>
        </GamePanel>
      )
      const buttons = screen.getAllByRole('button')
      expect(buttons.length).toBeGreaterThan(0)
    })

    it('calls onClose when close button clicked (with title)', () => {
      render(
        <GamePanel title="Test" onClose={mockOnClose}>
          <p>Content</p>
        </GamePanel>
      )
      const button = screen.getByRole('button')
      fireEvent.click(button)
      expect(mockOnClose).toHaveBeenCalled()
    })

    it('applies the padding token it was given, distinct from the default', () => {
      // Was: `expect(container.firstChild).toBeInTheDocument()`, which is true
      // of any rendered panel and so proved nothing about `padding`.
      const { container: small } = render(<GamePanel padding="small" onClose={mockOnClose}>c</GamePanel>)
      const { container: dflt } = render(<GamePanel onClose={mockOnClose}>c</GamePanel>)
      expect(small.firstChild.style.padding).toBeTruthy()
      expect(small.firstChild.style.padding).not.toBe(dflt.firstChild.style.padding)
    })

    it('applies the border variant it was given, distinct from the default', () => {
      const { container: danger } = render(<GamePanel borderVariant="danger" onClose={mockOnClose}>c</GamePanel>)
      const { container: dflt } = render(<GamePanel onClose={mockOnClose}>c</GamePanel>)
      expect(danger.firstChild.style.border).toBeTruthy()
      expect(danger.firstChild.style.border).not.toBe(dflt.firstChild.style.border)
    })

    it('applies glow style when glow=true', () => {
      const { container } = render(
        <GamePanel glow={true} onClose={mockOnClose}>
          <p>Content</p>
        </GamePanel>
      )
      expect(container.firstChild).toHaveClass('retro-glow')
    })

    it('removes glow style when glow=false', () => {
      const { container } = render(
        <GamePanel glow={false} onClose={mockOnClose}>
          <p>Content</p>
        </GamePanel>
      )
      // The paired `glow={true}` test above asserts the class is present, so
      // this one has to assert its ABSENCE — it previously asserted only that
      // the panel existed, which is equally true with the glow left on.
      expect(container.firstChild).not.toHaveClass('retro-glow')
    })

    it('handles custom className', () => {
      const { container } = render(
        <GamePanel className="custom-panel" onClose={mockOnClose}>
          <p>Content</p>
        </GamePanel>
      )
      expect(container.firstChild).toHaveClass('custom-panel')
    })

    it('applies custom style prop', () => {
      const { container } = render(
        <GamePanel style={{ opacity: 0.5 }} onClose={mockOnClose}>
          <p>Content</p>
        </GamePanel>
      )
      const panel = container.firstChild
      expect(panel).toHaveStyle({ opacity: 0.5 })
    })
  })

  describe('StatsPanel Coverage', () => {
    it('returns null when player is not provided', () => {
      const { container } = render(
        <div>
          <StatsPanel player={null} />
        </div>
      )
      expect(container.querySelector('[role="dialog"]')).not.toBeInTheDocument()
    })

    it('renders with minimal player data', () => {
      const { container } = render(
        <StatsPanel
          player={{
            hp: 50,
            max_hp: 100,
            fatigue: 30,
            max_fatigue: 50,
            protection: 5,
            level: 1,
            attack_damage_min: 5,
            attack_damage_max: 10,
            hit_accuracy: 75,
            evasion_chance: 20,
            strength: 10,
            finesse: 10,
            speed: 10,
            endurance: 10,
            charisma: 10,
            intelligence: 10,
            faith: 10
          }}
          onClose={vi.fn()}
        />
      )
      expect(container.querySelector('[role="dialog"]')).toBeInTheDocument()
    })

    // These two used to differ ONLY in the numbers they passed, and both
    // asserted the same thing — that a dialog rendered. Nothing read a single
    // stat back out, so StatsPanel could have shown all zeroes at 99 and both
    // stayed green. They are now one parametrised case that reads the numbers
    // back, with the zero row kept because 0 is the value most likely to be
    // swallowed by a `||` fallback.
    it.each([
      ['high', { hp: 999, max_hp: 999, fatigue: 999, max_fatigue: 999, protection: 99, level: 99, attack_damage_min: 99, attack_damage_max: 199 }],
      ['zero', { hp: 0, max_hp: 100, fatigue: 0, max_fatigue: 50, protection: 0, level: 0, attack_damage_min: 0, attack_damage_max: 0 }],
    ])('renders %s stat values verbatim rather than a fallback', (_label, stats) => {
      const player = makePlayer({ ...stats, hit_accuracy: 0, evasion_chance: 0 })
      const { container } = render(<StatsPanel player={player} onClose={vi.fn()} />)

      expect(container.querySelector('[role="dialog"]')).toBeInTheDocument()
      expect(container.textContent).toContain(`${stats.hp}/${stats.max_hp}`)
      expect(container.textContent).toContain(`${stats.fatigue}/${stats.max_fatigue}`)
      expect(container.textContent).toContain(`${stats.attack_damage_min}-${stats.attack_damage_max}`)
      expect(container.textContent).toContain(String(stats.level))
    })
  })

  describe('CooldownTray Coverage', () => {
    // WHAT WAS HERE: six tests passing `cooldowns={[...]}` — a prop
    // CooldownTray does not accept (it takes `moves`) — each asserting
    // `expect(container).toBeTruthy()`. The render-container div testing
    // -library creates is truthy unconditionally, including when the component
    // returns null, which is exactly what every one of those renders did. Six
    // tests, one wrong prop name, zero coverage of the tray.
    const move = (name, over = {}) => ({ id: name, name, category: 'Offensive', cooldown_remaining: 3, ...over })

    it('renders nothing for an empty move list', () => {
      const { container } = render(<CooldownTray moves={[]} />)
      expect(container.firstChild).toBeNull()
    })

    it('counts the cooling moves in the header and shows each remaining beat count', () => {
      render(<CooldownTray moves={[
        move('Power Strike', { cooldown_remaining: 4 }),
        move('Reap', { cooldown_remaining: 7 }),
        move('Riposte', { cooldown_remaining: 9 }),
      ]} />)

      expect(screen.getByText('Cooldown')).toBeInTheDocument()
      // Header count sits next to the "Cooldown" label.
      expect(screen.getByText('Cooldown').parentElement.textContent).toBe('Cooldown3')
      // Collapsed cards show the beats remaining, not the move name.
      expect(screen.getByText('4')).toBeInTheDocument()
      expect(screen.getByText('7')).toBeInTheDocument()
      expect(screen.getByText('9')).toBeInTheDocument()
      expect(screen.queryByText('Power Strike')).toBeNull()
    })

    it('reveals a very long move name in full when expanded', () => {
      const longName = 'A'.repeat(100)
      const { container } = render(<CooldownTray moves={[move(longName)]} />)
      fireEvent.mouseEnter(container.firstChild)
      expect(screen.getByText(longName)).toBeInTheDocument()
    })
  })

  describe('CombatLog Coverage', () => {
    // WHAT WAS HERE: seven tests each ending in `expect(container).toBeTruthy()`
    // — the render container, which testing-library creates and which is truthy
    // whatever the component does. CombatLog writes each entry through
    // `dangerouslySetInnerHTML` (with DOMPurify), and not one of the seven read
    // a single rendered message back out, let alone the sanitisation.
    //
    // The message rendering, the animation-entry filter, the DOMPurify
    // behaviour and the empty/null-log placeholders are all covered by
    // coverage-gaps-final.test.jsx's CombatLog block, so only the one thing it
    // does NOT assert — the per-type colour table and its fallback — lives
    // here, rather than a second weaker copy of all of it.
    it('colours an entry by its type and falls back for an unknown type', () => {
      render(<CombatLog log={[
        { id: 1, type: 'damage', message: 'Took a hit' },
        { id: 2, type: 'heal', message: 'Patched up' },
        { id: 3, type: 'no-such-type', message: 'Uncategorised' },
      ]} />)

      expect(screen.getByText('Took a hit')).toHaveStyle({ color: colors.danger })
      expect(screen.getByText('Patched up')).toHaveStyle({ color: colors.success })
      expect(screen.getByText('Uncategorised')).toHaveStyle({ color: colors.text.main })
    })

  })

  // The blocks below replace ~16 tests that rendered inline <div> literals to
  // assert on React and JavaScript semantics (ternaries, array.map, truthy/
  // falsy coercion, ?? vs ||, destructuring). They exercised no project code.
  // Each theme is now driven through the real components this file imports.

  describe('Conditional rendering in the real panels', () => {
    it('renders a GamePanel title only when one is supplied', () => {
      const { rerender } = render(<GamePanel title="INVENTORY">body</GamePanel>)
      expect(screen.getByText('INVENTORY')).toBeInTheDocument()

      rerender(<GamePanel>body</GamePanel>)
      expect(screen.queryByText('INVENTORY')).toBeNull()
      expect(screen.getByText('body')).toBeInTheDocument()
    })

    it('renders a GamePanel close affordance only when onClose is supplied', () => {
      const onClose = vi.fn()
      const { container, rerender } = render(<GamePanel title="T" onClose={onClose}>body</GamePanel>)
      const closeButton = container.querySelector('button')
      expect(closeButton).toBeTruthy()

      fireEvent.click(closeButton)
      expect(onClose).toHaveBeenCalledTimes(1)

      rerender(<GamePanel title="T">body</GamePanel>)
      expect(container.querySelector('button')).toBeNull()
    })

    it('falls back to the default padding for an unknown padding token', () => {
      const { container: known } = render(<GamePanel padding="none">a</GamePanel>)
      const { container: unknown } = render(<GamePanel padding="not-a-size">a</GamePanel>)
      const { container: fallback } = render(<GamePanel padding="large">a</GamePanel>)

      expect(known.firstChild.style.padding).not.toBe(fallback.firstChild.style.padding)
      expect(unknown.firstChild.style.padding).toBe(fallback.firstChild.style.padding)
    })
  })

  describe('List rendering in CooldownTray', () => {
    const move = (id, over = {}) => ({ id, name: `Move ${id}`, category: 'Offensive', cooldown_remaining: 2, ...over })

    it('renders nothing when there are no cooling moves', () => {
      const { container, rerender } = render(<CooldownTray moves={[]} />)
      expect(container.firstChild).toBeNull()

      rerender(<CooldownTray moves={null} />)
      expect(container.firstChild).toBeNull()

      rerender(<CooldownTray />)
      expect(container.firstChild).toBeNull()
    })

    it('shows the cooling-move count and one card per move', () => {
      render(<CooldownTray moves={[move(1), move(2), move(3)]} />)
      expect(screen.getByText('Cooldown')).toBeInTheDocument()
      expect(screen.getByText('3')).toBeInTheDocument()
    })

    it('swaps to the expanded layout on hover and back on leave', () => {
      const { container } = render(<CooldownTray moves={[move(1, { name: 'Power Strike' })]} />)
      const tray = container.firstChild

      // Collapsed cards show the icon and remaining beats, not the move name.
      expect(screen.queryByText('Power Strike')).toBeNull()

      fireEvent.mouseEnter(tray)
      expect(screen.getByText('Power Strike')).toBeInTheDocument()

      fireEvent.mouseLeave(tray)
      expect(screen.queryByText('Power Strike')).toBeNull()
    })

    it('renders moves of every category without needing a known one', () => {
      const moves = [
        move(1, { category: 'Offensive' }),
        move(2, { category: 'Defensive' }),
        move(3, { category: 'Maneuver' }),
        move(4, { category: 'Utterly Unknown' }),
      ]
      expect(() => render(<CooldownTray moves={moves} />)).not.toThrow()
      expect(screen.getByText('4')).toBeInTheDocument()
    })
  })

  describe('Absent and partial player data in StatsPanel', () => {
    it('does not crash when the player has no stats at all', () => {
      expect(() => render(<StatsPanel player={{}} onClose={vi.fn()} />)).not.toThrow()
    })

    it('closes via its close handler', () => {
      // The `if (button)` guard that used to wrap this assertion meant the
      // test passed with ZERO assertions the moment the close control moved or
      // was removed — the exact failure it exists to catch.
      const onClose = vi.fn()
      const { container } = render(<StatsPanel player={{ name: 'Jean', level: 3 }} onClose={onClose} />)
      const button = container.querySelector('button')
      expect(button).not.toBeNull()
      fireEvent.click(button)
      expect(onClose).toHaveBeenCalledTimes(1)
    })
  })
})
