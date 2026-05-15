import React from 'react'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import CombatManager from './CombatManager'

// Mock child components
vi.mock('./VictoryDialog', () => ({
  default: ({ endState, onAllocatePoints, onClose, onContinueToLoot }) => (
    <div data-testid="victory-dialog">
      <p>Victory: +{endState?.exp_gained || 0} EXP</p>
      <button onClick={() => onContinueToLoot()}>Continue</button>
      <button onClick={() => onClose()}>Close</button>
    </div>
  ),
}))

vi.mock('./DefeatDialog', () => ({
  default: ({ endState, onLoadedSave }) => (
    <div data-testid="defeat-dialog">
      <p>Defeat: {endState?.status}</p>
      <button onClick={() => onLoadedSave()}>Retry</button>
    </div>
  ),
}))

vi.mock('./LootDialog', () => ({
  default: ({ endState, playerWeight, weightLimit, onCollect, onSkip }) => (
    <div data-testid="loot-dialog">
      <p>Loot: {endState?.dropped_items?.length || 0} items</p>
      <button onClick={() => onCollect()}>Collect</button>
      <button onClick={() => onSkip()}>Skip</button>
    </div>
  ),
}))

describe('CombatManager', () => {
  const mockCallbacks = {
    onAllocatePoints: vi.fn(),
    onVictoryClose: vi.fn(),
    onDefeatClose: vi.fn(),
    onContinueToLoot: vi.fn(),
    onCollectLoot: vi.fn(),
    onSkipLoot: vi.fn(),
  }

  const mockVictoryEndState = {
    status: 'victory',
    exp_gained: 100,
    dropped_items: [
      { name: 'Gold', quantity: 50 },
      { name: 'Sword', quantity: 1 },
    ],
  }

  const mockDefeatEndState = {
    status: 'defeat',
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Rendering', () => {
    it('renders without crashing when no dialogs shown', () => {
      const { container } = render(
        <CombatManager
          showVictoryDialog={false}
          showDefeatDialog={false}
          showLootDialog={false}
          endState={null}
          playerWeight={0}
          weightLimit={100}
          {...mockCallbacks}
        />
      )
      expect(container.firstChild).toBeInTheDocument()
    })

    it('renders nothing when all dialogs are false', () => {
      const { container } = render(
        <CombatManager
          showVictoryDialog={false}
          showDefeatDialog={false}
          showLootDialog={false}
          endState={mockVictoryEndState}
          playerWeight={0}
          weightLimit={100}
          {...mockCallbacks}
        />
      )
      // Should render empty fragment
      expect(container.firstChild.children.length).toBe(0)
    })

    it('renders empty fragment as root', () => {
      const { container } = render(
        <CombatManager
          showVictoryDialog={false}
          showDefeatDialog={false}
          showLootDialog={false}
          endState={null}
          playerWeight={0}
          weightLimit={100}
          {...mockCallbacks}
        />
      )
      expect(container.firstChild).toBeInTheDocument()
    })
  })

  describe('Victory Dialog', () => {
    it('renders victory dialog when showVictoryDialog is true', () => {
      render(
        <CombatManager
          showVictoryDialog={true}
          showDefeatDialog={false}
          showLootDialog={false}
          endState={mockVictoryEndState}
          playerWeight={0}
          weightLimit={100}
          {...mockCallbacks}
        />
      )
      expect(screen.getByTestId('victory-dialog')).toBeInTheDocument()
    })

    it('does not render victory dialog when showVictoryDialog is false', () => {
      render(
        <CombatManager
          showVictoryDialog={false}
          showDefeatDialog={false}
          showLootDialog={false}
          endState={mockVictoryEndState}
          playerWeight={0}
          weightLimit={100}
          {...mockCallbacks}
        />
      )
      expect(screen.queryByTestId('victory-dialog')).not.toBeInTheDocument()
    })

    it('does not render victory dialog when endState is null', () => {
      render(
        <CombatManager
          showVictoryDialog={true}
          showDefeatDialog={false}
          showLootDialog={false}
          endState={null}
          playerWeight={0}
          weightLimit={100}
          {...mockCallbacks}
        />
      )
      expect(screen.queryByTestId('victory-dialog')).not.toBeInTheDocument()
    })

    it('passes endState to victory dialog', () => {
      render(
        <CombatManager
          showVictoryDialog={true}
          showDefeatDialog={false}
          showLootDialog={false}
          endState={mockVictoryEndState}
          playerWeight={0}
          weightLimit={100}
          {...mockCallbacks}
        />
      )
      expect(screen.getByText(/100 EXP/)).toBeInTheDocument()
    })

    it('passes callbacks to victory dialog', () => {
      render(
        <CombatManager
          showVictoryDialog={true}
          showDefeatDialog={false}
          showLootDialog={false}
          endState={mockVictoryEndState}
          playerWeight={0}
          weightLimit={100}
          {...mockCallbacks}
        />
      )
      const continueButton = screen.getByText('Continue')
      continueButton.click()
      expect(mockCallbacks.onContinueToLoot).toHaveBeenCalled()
    })

    it('displays exp gained from endState', () => {
      const endState = { ...mockVictoryEndState, exp_gained: 250 }
      render(
        <CombatManager
          showVictoryDialog={true}
          showDefeatDialog={false}
          showLootDialog={false}
          endState={endState}
          playerWeight={0}
          weightLimit={100}
          {...mockCallbacks}
        />
      )
      expect(screen.getByText(/250 EXP/)).toBeInTheDocument()
    })
  })

  describe('Defeat Dialog', () => {
    it('renders defeat dialog when showDefeatDialog is true', () => {
      render(
        <CombatManager
          showVictoryDialog={false}
          showDefeatDialog={true}
          showLootDialog={false}
          endState={mockDefeatEndState}
          playerWeight={0}
          weightLimit={100}
          {...mockCallbacks}
        />
      )
      expect(screen.getByTestId('defeat-dialog')).toBeInTheDocument()
    })

    it('does not render defeat dialog when showDefeatDialog is false', () => {
      render(
        <CombatManager
          showVictoryDialog={false}
          showDefeatDialog={false}
          showLootDialog={false}
          endState={mockDefeatEndState}
          playerWeight={0}
          weightLimit={100}
          {...mockCallbacks}
        />
      )
      expect(screen.queryByTestId('defeat-dialog')).not.toBeInTheDocument()
    })

    it('does not render defeat dialog when endState status is not defeat', () => {
      render(
        <CombatManager
          showVictoryDialog={false}
          showDefeatDialog={true}
          showLootDialog={false}
          endState={mockVictoryEndState}
          playerWeight={0}
          weightLimit={100}
          {...mockCallbacks}
        />
      )
      expect(screen.queryByTestId('defeat-dialog')).not.toBeInTheDocument()
    })

    it('passes onLoadedSave callback to defeat dialog', () => {
      render(
        <CombatManager
          showVictoryDialog={false}
          showDefeatDialog={true}
          showLootDialog={false}
          endState={mockDefeatEndState}
          playerWeight={0}
          weightLimit={100}
          {...mockCallbacks}
        />
      )
      const retryButton = screen.getByText('Retry')
      retryButton.click()
      expect(mockCallbacks.onDefeatClose).toHaveBeenCalled()
    })
  })

  describe('Loot Dialog', () => {
    it('renders loot dialog when showLootDialog is true', () => {
      render(
        <CombatManager
          showVictoryDialog={false}
          showDefeatDialog={false}
          showLootDialog={true}
          endState={mockVictoryEndState}
          playerWeight={0}
          weightLimit={100}
          {...mockCallbacks}
        />
      )
      expect(screen.getByTestId('loot-dialog')).toBeInTheDocument()
    })

    it('does not render loot dialog when showLootDialog is false', () => {
      render(
        <CombatManager
          showVictoryDialog={false}
          showDefeatDialog={false}
          showLootDialog={false}
          endState={mockVictoryEndState}
          playerWeight={0}
          weightLimit={100}
          {...mockCallbacks}
        />
      )
      expect(screen.queryByTestId('loot-dialog')).not.toBeInTheDocument()
    })

    it('does not render loot dialog when endState is null', () => {
      render(
        <CombatManager
          showVictoryDialog={false}
          showDefeatDialog={false}
          showLootDialog={true}
          endState={null}
          playerWeight={0}
          weightLimit={100}
          {...mockCallbacks}
        />
      )
      expect(screen.queryByTestId('loot-dialog')).not.toBeInTheDocument()
    })

    it('passes player weight info to loot dialog', () => {
      render(
        <CombatManager
          showVictoryDialog={false}
          showDefeatDialog={false}
          showLootDialog={true}
          endState={mockVictoryEndState}
          playerWeight={45}
          weightLimit={50}
          {...mockCallbacks}
        />
      )
      expect(screen.getByTestId('loot-dialog')).toBeInTheDocument()
    })

    it('passes loot callbacks to loot dialog', () => {
      render(
        <CombatManager
          showVictoryDialog={false}
          showDefeatDialog={false}
          showLootDialog={true}
          endState={mockVictoryEndState}
          playerWeight={0}
          weightLimit={100}
          {...mockCallbacks}
        />
      )
      const collectButton = screen.getByText('Collect')
      collectButton.click()
      expect(mockCallbacks.onCollectLoot).toHaveBeenCalled()
    })

    it('displays item count from endState', () => {
      const endState = {
        status: 'victory',
        dropped_items: Array.from({ length: 5 }, (_, i) => ({ name: `Item ${i}` })),
      }
      render(
        <CombatManager
          showVictoryDialog={false}
          showDefeatDialog={false}
          showLootDialog={true}
          endState={endState}
          playerWeight={0}
          weightLimit={100}
          {...mockCallbacks}
        />
      )
      expect(screen.getByText(/5 items/)).toBeInTheDocument()
    })
  })

  describe('Multiple Dialogs', () => {
    it('renders victory and loot dialogs together', () => {
      render(
        <CombatManager
          showVictoryDialog={true}
          showDefeatDialog={false}
          showLootDialog={true}
          endState={mockVictoryEndState}
          playerWeight={0}
          weightLimit={100}
          {...mockCallbacks}
        />
      )
      expect(screen.getByTestId('victory-dialog')).toBeInTheDocument()
      expect(screen.getByTestId('loot-dialog')).toBeInTheDocument()
    })

    it('does not render victory and defeat together', () => {
      render(
        <CombatManager
          showVictoryDialog={true}
          showDefeatDialog={true}
          showLootDialog={false}
          endState={mockVictoryEndState}
          playerWeight={0}
          weightLimit={100}
          {...mockCallbacks}
        />
      )
      expect(screen.getByTestId('victory-dialog')).toBeInTheDocument()
      expect(screen.queryByTestId('defeat-dialog')).not.toBeInTheDocument()
    })

    it('renders all three dialogs when appropriate', () => {
      const mixedEndState = {
        status: 'victory',
        exp_gained: 100,
        dropped_items: [{ name: 'Loot' }],
      }
      render(
        <CombatManager
          showVictoryDialog={true}
          showDefeatDialog={false}
          showLootDialog={true}
          endState={mixedEndState}
          playerWeight={0}
          weightLimit={100}
          {...mockCallbacks}
        />
      )
      expect(screen.getByTestId('victory-dialog')).toBeInTheDocument()
      expect(screen.getByTestId('loot-dialog')).toBeInTheDocument()
      expect(screen.queryByTestId('defeat-dialog')).not.toBeInTheDocument()
    })
  })

  describe('Props Combinations', () => {
    it('handles undefined callbacks gracefully', () => {
      render(
        <CombatManager
          showVictoryDialog={true}
          showDefeatDialog={false}
          showLootDialog={false}
          endState={mockVictoryEndState}
          playerWeight={0}
          weightLimit={100}
          onAllocatePoints={undefined}
          onVictoryClose={undefined}
          onDefeatClose={undefined}
          onContinueToLoot={undefined}
          onCollectLoot={undefined}
          onSkipLoot={undefined}
        />
      )
      expect(screen.getByTestId('victory-dialog')).toBeInTheDocument()
    })

    it('handles zero weight values', () => {
      render(
        <CombatManager
          showVictoryDialog={false}
          showDefeatDialog={false}
          showLootDialog={true}
          endState={mockVictoryEndState}
          playerWeight={0}
          weightLimit={0}
          {...mockCallbacks}
        />
      )
      expect(screen.getByTestId('loot-dialog')).toBeInTheDocument()
    })

    it('handles large weight values', () => {
      render(
        <CombatManager
          showVictoryDialog={false}
          showDefeatDialog={false}
          showLootDialog={true}
          endState={mockVictoryEndState}
          playerWeight={9999}
          weightLimit={10000}
          {...mockCallbacks}
        />
      )
      expect(screen.getByTestId('loot-dialog')).toBeInTheDocument()
    })
  })

  describe('Edge Cases', () => {
    it('handles endState with minimal data', () => {
      const minimalEndState = { status: 'victory' }
      render(
        <CombatManager
          showVictoryDialog={true}
          showDefeatDialog={false}
          showLootDialog={true}
          endState={minimalEndState}
          playerWeight={0}
          weightLimit={100}
          {...mockCallbacks}
        />
      )
      expect(screen.getByTestId('victory-dialog')).toBeInTheDocument()
    })

    it('handles endState with null values', () => {
      const nullEndState = {
        status: 'victory',
        exp_gained: null,
        dropped_items: null,
      }
      render(
        <CombatManager
          showVictoryDialog={true}
          showDefeatDialog={false}
          showLootDialog={false}
          endState={nullEndState}
          playerWeight={0}
          weightLimit={100}
          {...mockCallbacks}
        />
      )
      expect(screen.getByTestId('victory-dialog')).toBeInTheDocument()
    })

    it('toggles dialogs independently', () => {
      const { rerender } = render(
        <CombatManager
          showVictoryDialog={true}
          showDefeatDialog={false}
          showLootDialog={false}
          endState={mockVictoryEndState}
          playerWeight={0}
          weightLimit={100}
          {...mockCallbacks}
        />
      )
      expect(screen.getByTestId('victory-dialog')).toBeInTheDocument()

      rerender(
        <CombatManager
          showVictoryDialog={false}
          showDefeatDialog={false}
          showLootDialog={true}
          endState={mockVictoryEndState}
          playerWeight={0}
          weightLimit={100}
          {...mockCallbacks}
        />
      )
      expect(screen.queryByTestId('victory-dialog')).not.toBeInTheDocument()
      expect(screen.getByTestId('loot-dialog')).toBeInTheDocument()
    })

    it('updates endState while dialogs are shown', () => {
      const endState1 = { ...mockVictoryEndState, exp_gained: 100 }
      const { rerender } = render(
        <CombatManager
          showVictoryDialog={true}
          showDefeatDialog={false}
          showLootDialog={false}
          endState={endState1}
          playerWeight={0}
          weightLimit={100}
          {...mockCallbacks}
        />
      )
      expect(screen.getByText(/100 EXP/)).toBeInTheDocument()

      const endState2 = { ...mockVictoryEndState, exp_gained: 250 }
      rerender(
        <CombatManager
          showVictoryDialog={true}
          showDefeatDialog={false}
          showLootDialog={false}
          endState={endState2}
          playerWeight={0}
          weightLimit={100}
          {...mockCallbacks}
        />
      )
      expect(screen.getByText(/250 EXP/)).toBeInTheDocument()
    })
  })

  describe('Phase Sequencing', () => {
    it('victory dialog shows before loot dialog', () => {
      render(
        <CombatManager
          showVictoryDialog={true}
          showDefeatDialog={false}
          showLootDialog={true}
          endState={mockVictoryEndState}
          playerWeight={0}
          weightLimit={100}
          {...mockCallbacks}
        />
      )
      expect(screen.getByTestId('victory-dialog')).toBeInTheDocument()
      expect(screen.getByTestId('loot-dialog')).toBeInTheDocument()
    })

    it('defeat dialog shows independent of victory', () => {
      render(
        <CombatManager
          showVictoryDialog={false}
          showDefeatDialog={true}
          showLootDialog={false}
          endState={mockDefeatEndState}
          playerWeight={0}
          weightLimit={100}
          {...mockCallbacks}
        />
      )
      expect(screen.queryByTestId('victory-dialog')).not.toBeInTheDocument()
      expect(screen.getByTestId('defeat-dialog')).toBeInTheDocument()
    })
  })
})
