import React from 'react'
import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { render, screen, waitFor, act, fireEvent } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import GameOverScreen from './GameOverScreen'

const mockNavigate = vi.fn()
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

describe('GameOverScreen', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.runOnlyPendingTimers()
    vi.useRealTimers()
  })

  const renderWithRouter = (component) => {
    return render(
      <BrowserRouter>
        {component}
      </BrowserRouter>
    )
  }

  describe('Rendering', () => {
    it('renders game over screen container', () => {
      const { container } = renderWithRouter(
        <GameOverScreen />
      )
      expect(container.firstChild).toBeInTheDocument()
    })

    it('displays game over title', () => {
      renderWithRouter(<GameOverScreen />)
      expect(screen.getByText(/GAME OVER/i)).toBeInTheDocument()
    })

    it('renders main menu button', () => {
      renderWithRouter(<GameOverScreen />)
      // Button appears after 1500ms delay
      act(() => {
        vi.advanceTimersByTime(1500)
        vi.runAllTimers()
      })
      expect(screen.getByText(/MAIN MENU/i)).toBeInTheDocument()
    })

    it('renders with custom message when provided', () => {
      renderWithRouter(
        <GameOverScreen message="You have fallen in battle!" />
      )
      expect(screen.getByText('You have fallen in battle!')).toBeInTheDocument()
    })

    it('renders without message prop', () => {
      renderWithRouter(<GameOverScreen />)
      expect(screen.getByText(/GAME OVER/i)).toBeInTheDocument()
    })
  })

  describe('Message Display', () => {
    it('displays custom game over message', () => {
      const customMessage = 'You were defeated by the final boss'
      renderWithRouter(
        <GameOverScreen message={customMessage} />
      )
      expect(screen.getByText(customMessage)).toBeInTheDocument()
    })

    it('handles long messages', () => {
      const longMessage = 'A'.repeat(200)
      renderWithRouter(
        <GameOverScreen message={longMessage} />
      )
      expect(screen.getByText(longMessage)).toBeInTheDocument()
    })

    it('handles special characters in message', () => {
      const specialMessage = 'Game Over: !@#$%^&*()'
      renderWithRouter(
        <GameOverScreen message={specialMessage} />
      )
      expect(screen.getByText(specialMessage)).toBeInTheDocument()
    })

    it('displays empty message string when provided', () => {
      renderWithRouter(
        <GameOverScreen message="" />
      )
      expect(screen.getByText(/GAME OVER/i)).toBeInTheDocument()
    })
  })

  describe('Button Styling', () => {
    it('main menu button is a button element', () => {
      renderWithRouter(<GameOverScreen />)
      act(() => {
        vi.advanceTimersByTime(1500)
        vi.runAllTimers()
      })
      const menuButton = screen.getByText(/MAIN MENU/i)
      expect(menuButton.tagName).toBe('BUTTON')
    })

    it('buttons exist in the component', () => {
      const { container } = renderWithRouter(
        <GameOverScreen />
      )
      act(() => {
        vi.advanceTimersByTime(1500)
        vi.runAllTimers()
      })
      const buttons = container.querySelectorAll('button')
      expect(buttons.length).toBeGreaterThan(0)
    })
  })

  describe('Edge Cases', () => {
    it('renders with null message', () => {
      renderWithRouter(
        <GameOverScreen message={null} />
      )
      expect(screen.getByText(/GAME OVER/i)).toBeInTheDocument()
    })

    it('renders with undefined message', () => {
      renderWithRouter(
        <GameOverScreen message={undefined} />
      )
      expect(screen.getByText(/GAME OVER/i)).toBeInTheDocument()
    })

    it('handles rapid re-renders', () => {
      const { rerender } = renderWithRouter(
        <GameOverScreen message="Game Over 1" />
      )

      for (let i = 0; i < 5; i++) {
        rerender(
          <BrowserRouter>
            <GameOverScreen message={`Game Over ${i}`} />
          </BrowserRouter>
        )
      }

      act(() => {
        vi.advanceTimersByTime(1500)
        vi.runAllTimers()
      })
      expect(screen.getByText(/MAIN MENU/i)).toBeInTheDocument()
    })
  })

  describe('Accessibility', () => {
    it('title is readable to screen readers', () => {
      renderWithRouter(
        <GameOverScreen />
      )
      expect(screen.getByText(/GAME OVER/i)).toBeInTheDocument()
    })

    it('message text is readable to screen readers when provided', () => {
      const message = 'You died in the dungeon'
      renderWithRouter(
        <GameOverScreen message={message} />
      )
      expect(screen.getByText(message)).toBeInTheDocument()
    })

    it('buttons are keyboard accessible', () => {
      renderWithRouter(<GameOverScreen />)
      act(() => {
        vi.advanceTimersByTime(1500)
        vi.runAllTimers()
      })
      const menuButton = screen.getByText(/MAIN MENU/i)
      expect(menuButton.tagName).toBe('BUTTON')
    })
  })

  describe('Main menu navigation', () => {
    it('navigates to /menu when the MAIN MENU button is clicked', () => {
      renderWithRouter(<GameOverScreen />)
      act(() => {
        vi.advanceTimersByTime(1500)
        vi.runAllTimers()
      })
      fireEvent.click(screen.getByText(/MAIN MENU/i))
      expect(mockNavigate).toHaveBeenCalledWith('/menu')
    })
  })
})
