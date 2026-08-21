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
    it('renders the death screen full-bleed over the game, with no message of its own', () => {
      // `expect(container.firstChild).toBeInTheDocument()` is true for ANY
      // rendered node — it could not tell this screen from an empty <div>.
      const { container } = renderWithRouter(<GameOverScreen />)
      const root = container.firstChild

      expect(root).toHaveTextContent(/GAME OVER/i)
      // It must cover the viewport: a death screen the player can click past is
      // not a death screen.
      expect(root.style.position).toBe('fixed')
      expect(root.style.zIndex).not.toBe('')
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
    it.each([[null], [undefined], ['']])(
      'still shows the GAME OVER heading and the retry control for a %p message',
      (message) => {
        renderWithRouter(<GameOverScreen message={message} />)
        expect(screen.getByText(/GAME OVER/i)).toBeInTheDocument()
        // The player must never be stranded on a dead screen with no way out,
        // whatever the server did or did not send as a death message — the
        // escape hatch appears once the reveal delay elapses.
        act(() => { vi.advanceTimersByTime(1500) })
        expect(screen.getByRole('button', { name: /MAIN MENU/i })).toBeInTheDocument()
      }
    )

    it('cancels the reveal cleanly when unmounted before the delay elapses', () => {
      // No rAF has been scheduled yet, so the cleanup must tolerate both frame
      // ids being undefined rather than calling cancelAnimationFrame(undefined).
      const cancelSpy = vi.spyOn(globalThis, 'cancelAnimationFrame')
      const { unmount } = renderWithRouter(<GameOverScreen message="Died" />)
      expect(() => unmount()).not.toThrow()
      expect(cancelSpy).not.toHaveBeenCalled()
      cancelSpy.mockRestore()
    })

    it('cancels the queued animation frames when unmounted after the delay', () => {
      // Regression: the inner rAF cleanup used to be returned from inside the
      // rAF callback, where React discards it, so the second frame was never
      // cancellable and could set state on an unmounted tree.
      const cancelSpy = vi.spyOn(globalThis, 'cancelAnimationFrame')
      const rafSpy = vi.spyOn(globalThis, 'requestAnimationFrame')
      const { unmount } = renderWithRouter(<GameOverScreen message="Died" />)
      act(() => {
        vi.advanceTimersByTime(1500)
      })
      const scheduled = rafSpy.mock.results.map((r) => r.value)
      expect(scheduled.length).toBeGreaterThan(0)

      unmount()
      // Cancelled BY HANDLE, not merely "cancelAnimationFrame ran": a bare
      // toHaveBeenCalled() passes for a cleanup that cancels the wrong frame
      // and leaves the real one running against an unmounted tree.
      const cancelled = cancelSpy.mock.calls.map(([id]) => id)
      expect(cancelled).toContain(scheduled.at(-1))
      cancelSpy.mockRestore()
      rafSpy.mockRestore()
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
