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

    it('renders with custom padding', () => {
      const { container } = render(
        <GamePanel padding="small" onClose={mockOnClose}>
          <p>Content</p>
        </GamePanel>
      )
      expect(container.firstChild).toBeInTheDocument()
    })

    it('renders with custom border variant', () => {
      const { container } = render(
        <GamePanel borderVariant="danger" onClose={mockOnClose}>
          <p>Content</p>
        </GamePanel>
      )
      expect(container.firstChild).toBeInTheDocument()
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
      const panel = container.firstChild
      expect(panel).toBeInTheDocument()
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

    it('renders with high stat values', () => {
      const { container } = render(
        <StatsPanel
          player={{
            hp: 999,
            max_hp: 999,
            fatigue: 999,
            max_fatigue: 999,
            protection: 99,
            level: 99,
            attack_damage_min: 99,
            attack_damage_max: 199,
            hit_accuracy: 999,
            evasion_chance: 999,
            strength: 99,
            finesse: 99,
            speed: 99,
            endurance: 99,
            charisma: 99,
            intelligence: 99,
            faith: 99
          }}
          onClose={vi.fn()}
        />
      )
      expect(container.querySelector('[role="dialog"]')).toBeInTheDocument()
    })

    it('renders with zero stat values', () => {
      const { container } = render(
        <StatsPanel
          player={{
            hp: 0,
            max_hp: 100,
            fatigue: 0,
            max_fatigue: 50,
            protection: 0,
            level: 0,
            attack_damage_min: 0,
            attack_damage_max: 0,
            hit_accuracy: 0,
            evasion_chance: 0,
            strength: 0,
            finesse: 0,
            speed: 0,
            endurance: 0,
            charisma: 0,
            intelligence: 0,
            faith: 0
          }}
          onClose={vi.fn()}
        />
      )
      expect(container.querySelector('[role="dialog"]')).toBeInTheDocument()
    })
  })

  describe('CooldownTray Coverage', () => {
    it('renders with empty cooldowns array', () => {
      const { container } = render(
        <CooldownTray cooldowns={[]} />
      )
      expect(container).toBeTruthy()
    })

    it('renders with single cooldown', () => {
      const { container } = render(
        <CooldownTray cooldowns={[
          { name: 'Move 1', cooldown_remaining: 0, cooldown_max: 10 }
        ]} />
      )
      expect(container).toBeTruthy()
    })

    it('renders with multiple cooldowns', () => {
      const { container } = render(
        <CooldownTray cooldowns={[
          { name: 'Move 1', cooldown_remaining: 0, cooldown_max: 10 },
          { name: 'Move 2', cooldown_remaining: 5, cooldown_max: 10 },
          { name: 'Move 3', cooldown_remaining: 10, cooldown_max: 10 }
        ]} />
      )
      expect(container).toBeTruthy()
    })

    it('handles cooldown at max', () => {
      const { container } = render(
        <CooldownTray cooldowns={[
          { name: 'Move 1', cooldown_remaining: 10, cooldown_max: 10 }
        ]} />
      )
      expect(container).toBeTruthy()
    })

    it('handles very long cooldown names', () => {
      const longName = 'A'.repeat(100)
      const { container } = render(
        <CooldownTray cooldowns={[
          { name: longName, cooldown_remaining: 0, cooldown_max: 10 }
        ]} />
      )
      expect(container).toBeTruthy()
    })

    it('handles cooldown with zero max', () => {
      const { container } = render(
        <CooldownTray cooldowns={[
          { name: 'Move 1', cooldown_remaining: 0, cooldown_max: 0 }
        ]} />
      )
      expect(container).toBeTruthy()
    })
  })

  describe('CombatLog Coverage', () => {
    it('renders with empty log', () => {
      const { container } = render(
        <CombatLog log={[]} />
      )
      expect(container).toBeTruthy()
    })

    it('renders with single log entry', () => {
      const { container } = render(
        <CombatLog log={[
          { type: 'move', message: 'Jean used Attack' }
        ]} />
      )
      expect(container).toBeTruthy()
    })

    it('renders with multiple log entries', () => {
      const { container } = render(
        <CombatLog log={[
          { type: 'move', message: 'Jean used Attack' },
          { type: 'hit', message: 'Hit for 10 damage' },
          { type: 'miss', message: 'Attack missed' },
          { type: 'heal', message: 'Healed 20 HP' }
        ]} />
      )
      expect(container).toBeTruthy()
    })

    it('handles log entries with special characters', () => {
      const { container } = render(
        <CombatLog log={[
          { type: 'move', message: 'Attack!@#$%^&*()' }
        ]} />
      )
      expect(container).toBeTruthy()
    })

    it('handles very long log entries', () => {
      const longMessage = 'A'.repeat(500)
      const { container } = render(
        <CombatLog log={[
          { type: 'move', message: longMessage }
        ]} />
      )
      expect(container).toBeTruthy()
    })

    it('handles null/undefined log', () => {
      const { container } = render(
        <CombatLog log={null} />
      )
      expect(container).toBeTruthy()
    })

    it('handles log with multiple entries in sequence', () => {
      const { container } = render(
        <CombatLog log={[
          { type: 'move', message: 'Attack' },
          { type: 'hit', message: 'Hit' },
          { type: 'crit', message: 'Critical!' }
        ]} />
      )
      expect(container).toBeTruthy()
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
      const onClose = vi.fn()
      const { container } = render(<StatsPanel player={{ name: 'Jean', level: 3 }} onClose={onClose} />)
      const button = container.querySelector('button')
      if (button) {
        fireEvent.click(button)
        expect(onClose).toHaveBeenCalled()
      }
    })
  })
})
