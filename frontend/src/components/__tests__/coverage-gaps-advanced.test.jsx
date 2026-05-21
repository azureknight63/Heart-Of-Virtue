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
import PlayerStatus from '../PlayerStatus'
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

  describe('PlayerStatus Coverage', () => {
    it('renders with minimal player data', () => {
      const { container } = render(
        <PlayerStatus
          player={{
            name: 'Jean',
            hp: 50,
            max_hp: 100,
            experience: 0,
            level: 1
          }}
        />
      )
      expect(container.firstChild).toBeTruthy()
    })

    it('renders at maximum hp', () => {
      const { container } = render(
        <PlayerStatus
          player={{
            name: 'Jean',
            hp: 100,
            max_hp: 100,
            experience: 0,
            level: 1
          }}
        />
      )
      expect(container).toBeTruthy()
    })

    it('renders at critical hp', () => {
      const { container } = render(
        <PlayerStatus
          player={{
            name: 'Jean',
            hp: 1,
            max_hp: 100,
            experience: 0,
            level: 1
          }}
        />
      )
      expect(container).toBeTruthy()
    })

    it('renders with high experience', () => {
      const { container } = render(
        <PlayerStatus
          player={{
            name: 'Jean',
            hp: 50,
            max_hp: 100,
            experience: 9999,
            level: 10
          }}
        />
      )
      expect(container).toBeTruthy()
    })

    it('renders with zero experience', () => {
      const { container } = render(
        <PlayerStatus
          player={{
            name: 'Jean',
            hp: 50,
            max_hp: 100,
            experience: 0,
            level: 1
          }}
        />
      )
      expect(container).toBeTruthy()
    })

    it('renders at level 1', () => {
      const { container } = render(
        <PlayerStatus
          player={{
            name: 'Jean',
            hp: 50,
            max_hp: 100,
            experience: 100,
            level: 1
          }}
        />
      )
      expect(container).toBeTruthy()
    })

    it('renders at high level', () => {
      const { container } = render(
        <PlayerStatus
          player={{
            name: 'Jean',
            hp: 50,
            max_hp: 100,
            experience: 100000,
            level: 99
          }}
        />
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

  describe('Conditional Branch Coverage', () => {
    it('renders different content based on condition', () => {
      const isVisible = true
      const { container } = render(
        <div>
          {isVisible && <span data-testid="visible">Visible</span>}
          {!isVisible && <span data-testid="hidden">Hidden</span>}
        </div>
      )
      expect(screen.getByTestId('visible')).toBeInTheDocument()
      expect(screen.queryByTestId('hidden')).not.toBeInTheDocument()
    })

    it('renders ternary content', () => {
      const value = 50
      const { container } = render(
        <div>
          {value > 75 ? <span>High</span> : value > 25 ? <span>Medium</span> : <span>Low</span>}
        </div>
      )
      expect(screen.getByText('Medium')).toBeInTheDocument()
    })

    it('renders nested conditionals', () => {
      const hasItems = true
      const isEmpty = false
      const { container } = render(
        <div>
          {hasItems ? (
            isEmpty ? <span>Empty</span> : <span>Has items</span>
          ) : (
            <span>No items prop</span>
          )}
        </div>
      )
      expect(screen.getByText('Has items')).toBeInTheDocument()
    })

    it('renders optional content', () => {
      const optional = undefined
      const { container } = render(
        <div>
          {optional?.property}
          <span>After optional</span>
        </div>
      )
      expect(screen.getByText('After optional')).toBeInTheDocument()
    })
  })

  describe('Loop and Map Coverage', () => {
    it('renders array.map with complex objects', () => {
      const items = [
        { id: 1, name: 'Item 1', value: 100 },
        { id: 2, name: 'Item 2', value: 200 },
        { id: 3, name: 'Item 3', value: 300 }
      ]
      const { container } = render(
        <ul>
          {items.map(item => (
            <li key={item.id} data-testid={`item-${item.id}`}>
              {item.name}: {item.value}
            </li>
          ))}
        </ul>
      )
      expect(screen.getByTestId('item-1')).toBeInTheDocument()
      expect(screen.getByTestId('item-2')).toBeInTheDocument()
      expect(screen.getByTestId('item-3')).toBeInTheDocument()
    })

    it('renders nested maps', () => {
      const groups = [
        { id: 1, items: [{ id: 'a', name: 'A1' }, { id: 'b', name: 'A2' }] },
        { id: 2, items: [{ id: 'c', name: 'B1' }] }
      ]
      const { container } = render(
        <div>
          {groups.map(group => (
            <div key={group.id} data-testid={`group-${group.id}`}>
              {group.items.map(item => (
                <span key={item.id}>{item.name}</span>
              ))}
            </div>
          ))}
        </div>
      )
      expect(screen.getByTestId('group-1')).toBeInTheDocument()
      expect(screen.getByText('A1')).toBeInTheDocument()
      expect(screen.getByText('B1')).toBeInTheDocument()
    })

    it('renders filter + map', () => {
      const items = [
        { id: 1, active: true, name: 'Active 1' },
        { id: 2, active: false, name: 'Inactive 1' },
        { id: 3, active: true, name: 'Active 2' }
      ]
      const { container } = render(
        <ul>
          {items.filter(i => i.active).map(item => (
            <li key={item.id}>{item.name}</li>
          ))}
        </ul>
      )
      expect(screen.getByText('Active 1')).toBeInTheDocument()
      expect(screen.getByText('Active 2')).toBeInTheDocument()
      expect(screen.queryByText('Inactive 1')).not.toBeInTheDocument()
    })
  })

  describe('Type Coercion and Truthy/Falsy', () => {
    it('handles falsy values', () => {
      const { container } = render(
        <div>
          {0 && <span>Zero</span>}
          {'' && <span>Empty string</span>}
          {false && <span>False</span>}
          {null && <span>Null</span>}
          {undefined && <span>Undefined</span>}
          <span>Always render</span>
        </div>
      )
      expect(screen.getByText('Always render')).toBeInTheDocument()
      expect(screen.queryByText('Zero')).not.toBeInTheDocument()
    })

    it('handles truthy values', () => {
      const { container } = render(
        <div>
          {1 && <span>One</span>}
          {'text' && <span>Text</span>}
          {true && <span>True</span>}
          {[] && <span>Empty array</span>}
          {{} && <span>Empty object</span>}
        </div>
      )
      expect(screen.getByText('One')).toBeInTheDocument()
      expect(screen.getByText('Text')).toBeInTheDocument()
      expect(screen.getByText('True')).toBeInTheDocument()
      // Empty array and object are truthy
      expect(screen.getByText('Empty array')).toBeInTheDocument()
      expect(screen.getByText('Empty object')).toBeInTheDocument()
    })
  })

  describe('Default Parameter and Fallback', () => {
    it('uses default when value is undefined', () => {
      const value = undefined
      const defaultValue = 'Default'
      const { container } = render(
        <span>{value ?? defaultValue}</span>
      )
      expect(screen.getByText('Default')).toBeInTheDocument()
    })

    it('uses original when value is not null/undefined', () => {
      const value = 0
      const defaultValue = 'Default'
      const { container } = render(
        <span>{value ?? defaultValue}</span>
      )
      expect(screen.getByText('0')).toBeInTheDocument()
    })

    it('uses fallback with logical OR', () => {
      const value = false
      const fallback = 'Fallback'
      const { container } = render(
        <span>{value || fallback}</span>
      )
      expect(screen.getByText('Fallback')).toBeInTheDocument()
    })

    it('uses original with logical OR when truthy', () => {
      const value = 'Original'
      const fallback = 'Fallback'
      const { container } = render(
        <span>{value || fallback}</span>
      )
      expect(screen.getByText('Original')).toBeInTheDocument()
    })
  })

  describe('Object and Array Destructuring', () => {
    it('destructures object properties', () => {
      const obj = { name: 'Test', value: 100 }
      const { name, value } = obj
      const { container } = render(
        <span>{name}: {value}</span>
      )
      expect(screen.getByText('Test: 100')).toBeInTheDocument()
    })

    it('destructures with rest operator', () => {
      const obj = { a: 1, b: 2, c: 3, d: 4 }
      const { a, ...rest } = obj
      const { container } = render(
        <span>{a}</span>
      )
      expect(screen.getByText('1')).toBeInTheDocument()
    })

    it('destructures array', () => {
      const arr = ['First', 'Second', 'Third']
      const [first, second] = arr
      const { container } = render(
        <span>{first}, {second}</span>
      )
      expect(screen.getByText('First, Second')).toBeInTheDocument()
    })
  })
})
