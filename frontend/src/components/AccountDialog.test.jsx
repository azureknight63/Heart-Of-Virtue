import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import AccountDialog from './AccountDialog';
import { useAuth } from '../hooks/useApi';

const mockNavigate = vi.fn();

// Mock useAuth
vi.mock('../hooks/useApi', () => ({
  useAuth: vi.fn()
}));

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

describe('AccountDialog', () => {
  const mockLogout = vi.fn();
  const mockOnClose = vi.fn();
  const mockPlayer = {
    premium: true
  };

  beforeEach(() => {
    vi.clearAllMocks();
    useAuth.mockReturnValue({
      logout: mockLogout
    });
    // Mock localStorage
    const localStorageMock = (function () {
      let store = {};
      return {
        getItem: function (key) {
          return store[key] || null;
        },
        setItem: function (key, value) {
          store[key] = value.toString();
        },
        clear: function () {
          store = {};
        }
      };
    })();
    Object.defineProperty(window, 'localStorage', {
      value: localStorageMock
    });
  });

  it('labels the two fields and shows the stored username under USERNAME', () => {
    window.localStorage.setItem('username', 'TestHero');
    render(<MemoryRouter><AccountDialog player={mockPlayer} onClose={mockOnClose} /></MemoryRouter>);

    expect(screen.getByText('⚔️ Account Details').textContent).toBe('⚔️ Account Details');
    // The value must sit under its own label, not merely exist somewhere.
    expect(screen.getByText('USERNAME').parentElement.textContent).toBe('USERNAMETestHero');
    expect(screen.getByText('ACCOUNT STATUS').parentElement.textContent)
      .toBe('ACCOUNT STATUS👑 Premium');
  });

  it.each([
    ['a premium player', { premium: true }, '👑 Premium'],
    ['a standard player', { premium: false }, '⭐ Standard'],
    ['a player with no premium field', {}, '⭐ Standard'],
    ['no player object at all', null, '⭐ Standard'],
    ['an undefined player', undefined, '⭐ Standard'],
  ])('shows %s as %s', (_label, player, expected) => {
    // `player?.premium` must degrade to Standard rather than crashing — the
    // dialog can open before the player payload has loaded.
    window.localStorage.setItem('username', 'StandardJoe');
    render(<MemoryRouter><AccountDialog player={player} onClose={mockOnClose} /></MemoryRouter>);
    expect(screen.getByText(expected).textContent).toBe(expected);
    expect(screen.getByText('StandardJoe').textContent).toBe('StandardJoe');
  });

  it('renders "Unknown" if username is not in localStorage', () => {
    render(<MemoryRouter><AccountDialog player={mockPlayer} onClose={mockOnClose} /></MemoryRouter>);
    expect(screen.getByText('USERNAME').parentElement.textContent).toBe('USERNAMEUnknown');
  });

  it('calls onClose when Close button is clicked', () => {
    render(<MemoryRouter><AccountDialog player={mockPlayer} onClose={mockOnClose} /></MemoryRouter>);
    const closeBtn = screen.getByText('Close');
    fireEvent.click(closeBtn);
    expect(mockOnClose).toHaveBeenCalledTimes(1);
    // Dismissing the dialog must not sign the player out.
    expect(mockLogout).not.toHaveBeenCalled();
  });

  it('awaits logout before closing, so the dialog cannot outlive the session teardown', async () => {
    let finishLogout;
    mockLogout.mockImplementation(() => new Promise((resolve) => { finishLogout = resolve }));
    render(<MemoryRouter><AccountDialog player={mockPlayer} onClose={mockOnClose} /></MemoryRouter>);

    fireEvent.click(screen.getByText('Log Out'));
    await waitFor(() => expect(mockLogout).toHaveBeenCalledTimes(1));
    expect(mockLogout).toHaveBeenCalledWith();
    // Ordering is the whole point of the `await` in handleLogout.
    expect(mockOnClose).not.toHaveBeenCalled();

    finishLogout();
    await waitFor(() => expect(mockOnClose).toHaveBeenCalledTimes(1));
    // Logging out is not a navigation — routing is AuthContext's job.
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it('closes when clicking the overlay', () => {
    const { container } = render(<MemoryRouter><AccountDialog player={mockPlayer} onClose={mockOnClose} /></MemoryRouter>);
    const overlay = container.firstChild;
    fireEvent.click(overlay);
    expect(mockOnClose).toHaveBeenCalledTimes(1);
    expect(mockLogout).not.toHaveBeenCalled();
  });

  it('does not close when clicking the dialog content', () => {
    render(<MemoryRouter><AccountDialog player={mockPlayer} onClose={mockOnClose} /></MemoryRouter>);
    const dialogContent = screen.getByText('⚔️ Account Details').parentElement;
    fireEvent.click(dialogContent);
    expect(mockOnClose).not.toHaveBeenCalled();
  });

  it('navigates to the main menu and closes when Main Menu is clicked', () => {
    render(<MemoryRouter><AccountDialog player={mockPlayer} onClose={mockOnClose} /></MemoryRouter>);
    fireEvent.click(screen.getByText('Main Menu'));

    expect(mockNavigate).toHaveBeenCalledWith('/menu');
    expect(mockOnClose).toHaveBeenCalledTimes(1);
    // Leaving for the menu is not a logout — the session must survive.
    expect(mockLogout).not.toHaveBeenCalled();
  });

});
