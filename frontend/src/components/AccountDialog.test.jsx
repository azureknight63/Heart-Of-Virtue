import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import AccountDialog from './AccountDialog';
import { useAuth } from '../hooks/useApi';

// Mock useAuth
vi.mock('../hooks/useApi', () => ({
  useAuth: vi.fn()
}));

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

  it('renders account details correctly for premium user', () => {
    window.localStorage.setItem('username', 'TestHero');
    render(<AccountDialog player={mockPlayer} onClose={mockOnClose} />);

    expect(screen.getByText('⚔️ Account Details')).toBeDefined();
    expect(screen.getByText('TestHero')).toBeDefined();
    expect(screen.getByText('👑 Premium')).toBeDefined();
  });

  it('renders account details correctly for standard user', () => {
    window.localStorage.setItem('username', 'StandardJoe');
    render(<AccountDialog player={{ premium: false }} onClose={mockOnClose} />);

    expect(screen.getByText('StandardJoe')).toBeDefined();
    expect(screen.getByText('⭐ Standard')).toBeDefined();
  });

  it('renders "Unknown" if username is not in localStorage', () => {
    render(<AccountDialog player={mockPlayer} onClose={mockOnClose} />);
    expect(screen.getByText('Unknown')).toBeDefined();
  });

  it('calls onClose when Close button is clicked', () => {
    render(<AccountDialog player={mockPlayer} onClose={mockOnClose} />);
    const closeBtn = screen.getByText('Close');
    fireEvent.click(closeBtn);
    expect(mockOnClose).toHaveBeenCalled();
  });

  it('calls logout and onClose when Log Out button is clicked', async () => {
    render(<AccountDialog player={mockPlayer} onClose={mockOnClose} />);
    const logoutBtn = screen.getByText('Log Out');
    fireEvent.click(logoutBtn);

    await waitFor(() => {
      expect(mockLogout).toHaveBeenCalled();
      expect(mockOnClose).toHaveBeenCalled();
    });
  });

  it('closes when clicking the overlay', () => {
    const { container } = render(<AccountDialog player={mockPlayer} onClose={mockOnClose} />);
    const overlay = container.firstChild;
    fireEvent.click(overlay);
    expect(mockOnClose).toHaveBeenCalled();
  });

  it('does not close when clicking the dialog content', () => {
    render(<AccountDialog player={mockPlayer} onClose={mockOnClose} />);
    const dialogContent = screen.getByText('⚔️ Account Details').parentElement;
    fireEvent.click(dialogContent);
    expect(mockOnClose).not.toHaveBeenCalled();
  });

});
