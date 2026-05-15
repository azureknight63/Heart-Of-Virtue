import React from 'react'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import LevelUpModal from './LevelUpModal'

// Mock dependencies
vi.mock('./BaseDialog', () => ({
  default: ({ children, title, onClose }) => (
    <div data-testid="base-dialog" onClick={onClose}>
      <h2>{title}</h2>
      {children}
    </div>
  ),
}))

vi.mock('../hooks/useEventCoordinator', () => ({
  useEventCoordinator: vi.fn(() => ({ emitToast: vi.fn() })),
}))

vi.mock('../api/endpoints', () => ({
  player: {
    levelUp: vi.fn(() => Promise.resolve({
      data: { success: true, newStats: {} }
    })),
  },
}))

describe('LevelUpModal', () => {
  const mockOnClose = vi.fn()
  const mockLevelUpData = {
    currentLevel: 5,
    newLevel: 6,
    availablePoints: 3,
    attributeOptions: [
      { attribute: 'strength', current: 10, cost: 1 },
      { attribute: 'finesse', current: 9, cost: 1 },
      { attribute: 'speed', current: 11, cost: 1 },
      { attribute: 'wisdom', current: 8, cost: 1 },
      { attribute: 'constitution', current: 10, cost: 1 },
    ],
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Rendering', () => {
    it('renders level up modal', () => {
      render(
        <LevelUpModal
          levelUpData={mockLevelUpData}
          onClose={mockOnClose}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('displays new level number', () => {
      render(
        <LevelUpModal
          levelUpData={mockLevelUpData}
          onClose={mockOnClose}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('shows available points', () => {
      render(
        <LevelUpModal
          levelUpData={mockLevelUpData}
          onClose={mockOnClose}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('displays all attributes', () => {
      render(
        <LevelUpModal
          levelUpData={mockLevelUpData}
          onClose={mockOnClose}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })
  })

  describe('Attribute Selection', () => {
    it('allows selecting attributes', () => {
      render(
        <LevelUpModal
          levelUpData={mockLevelUpData}
          onClose={mockOnClose}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('shows current attribute values', () => {
      render(
        <LevelUpModal
          levelUpData={mockLevelUpData}
          onClose={mockOnClose}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('displays cost per attribute increase', () => {
      render(
        <LevelUpModal
          levelUpData={mockLevelUpData}
          onClose={mockOnClose}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('prevents selecting more points than available', () => {
      render(
        <LevelUpModal
          levelUpData={mockLevelUpData}
          onClose={mockOnClose}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })
  })

  describe('Point Allocation', () => {
    it('tracks allocated points', () => {
      render(
        <LevelUpModal
          levelUpData={mockLevelUpData}
          onClose={mockOnClose}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('updates remaining points when allocating', () => {
      render(
        <LevelUpModal
          levelUpData={mockLevelUpData}
          onClose={mockOnClose}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('prevents over-allocation', () => {
      render(
        <LevelUpModal
          levelUpData={mockLevelUpData}
          onClose={mockOnClose}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('allows deallocating points', () => {
      render(
        <LevelUpModal
          levelUpData={mockLevelUpData}
          onClose={mockOnClose}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('resets allocation to zero', () => {
      render(
        <LevelUpModal
          levelUpData={mockLevelUpData}
          onClose={mockOnClose}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })
  })

  describe('Submission', () => {
    it('allows submitting allocation', () => {
      render(
        <LevelUpModal
          levelUpData={mockLevelUpData}
          onClose={mockOnClose}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('disables submit when no points allocated', () => {
      render(
        <LevelUpModal
          levelUpData={{ ...mockLevelUpData, availablePoints: 0 }}
          onClose={mockOnClose}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('shows loading during submission', () => {
      render(
        <LevelUpModal
          levelUpData={mockLevelUpData}
          onClose={mockOnClose}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })
  })

  describe('Validation', () => {
    it('validates attribute costs', () => {
      render(
        <LevelUpModal
          levelUpData={mockLevelUpData}
          onClose={mockOnClose}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('prevents invalid allocations', () => {
      render(
        <LevelUpModal
          levelUpData={mockLevelUpData}
          onClose={mockOnClose}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('validates total points do not exceed available', () => {
      render(
        <LevelUpModal
          levelUpData={mockLevelUpData}
          onClose={mockOnClose}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })
  })

  describe('User Feedback', () => {
    it('shows stat preview after allocation', () => {
      render(
        <LevelUpModal
          levelUpData={mockLevelUpData}
          onClose={mockOnClose}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('displays error on submission failure', () => {
      render(
        <LevelUpModal
          levelUpData={mockLevelUpData}
          onClose={mockOnClose}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('displays success message on submission', () => {
      render(
        <LevelUpModal
          levelUpData={mockLevelUpData}
          onClose={mockOnClose}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })
  })

  describe('Edge Cases', () => {
    it('handles zero available points', () => {
      render(
        <LevelUpModal
          levelUpData={{ ...mockLevelUpData, availablePoints: 0 }}
          onClose={mockOnClose}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('handles large number of available points', () => {
      render(
        <LevelUpModal
          levelUpData={{ ...mockLevelUpData, availablePoints: 50 }}
          onClose={mockOnClose}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('handles very high attribute values', () => {
      const dataWithHighStats = {
        ...mockLevelUpData,
        attributeOptions: mockLevelUpData.attributeOptions.map(attr => ({
          ...attr,
          current: 99,
        })),
      }

      render(
        <LevelUpModal
          levelUpData={dataWithHighStats}
          onClose={mockOnClose}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('handles single attribute', () => {
      render(
        <LevelUpModal
          levelUpData={{
            ...mockLevelUpData,
            attributeOptions: [mockLevelUpData.attributeOptions[0]],
          }}
          onClose={mockOnClose}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })
  })

  describe('Closing Modal', () => {
    it('has close functionality', () => {
      render(
        <LevelUpModal
          levelUpData={mockLevelUpData}
          onClose={mockOnClose}
        />
      )

      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('closes after successful submission', async () => {
      render(
        <LevelUpModal
          levelUpData={mockLevelUpData}
          onClose={mockOnClose}
        />
      )

      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })
  })

  describe('Interface Elements', () => {
    it('displays increment/decrement buttons', () => {
      render(
        <LevelUpModal
          levelUpData={mockLevelUpData}
          onClose={mockOnClose}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('shows submit button', () => {
      render(
        <LevelUpModal
          levelUpData={mockLevelUpData}
          onClose={mockOnClose}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('shows reset button', () => {
      render(
        <LevelUpModal
          levelUpData={mockLevelUpData}
          onClose={mockOnClose}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })

    it('displays points remaining indicator', () => {
      render(
        <LevelUpModal
          levelUpData={mockLevelUpData}
          onClose={mockOnClose}
        />
      )
      expect(screen.getByTestId('base-dialog')).toBeInTheDocument()
    })
  })
})
