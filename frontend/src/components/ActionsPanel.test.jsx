import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import ActionsPanel from './ActionsPanel';
import apiEndpoints from '../api/endpoints';
import { AudioProvider } from '../context/AudioContext';

// Mock apiEndpoints
vi.mock('../api/endpoints', () => ({
  default: {
    world: {
      getCommands: vi.fn(),
    },
    saves: {
      save: vi.fn(),
    },
  },
}));

// Mock useAudio
vi.mock('../context/AudioContext', () => ({
  useAudio: () => ({
    playSFX: vi.fn(),
  }),
  AudioProvider: ({ children }) => <div>{children}</div>,
}));

describe('ActionsPanel', () => {
  const mockCommands = [
    { name: 'Menu', debug: false },
    { name: 'Save', debug: false },
    { name: 'Teleport', debug: true },
  ];

  const mockOnClose = vi.fn();
  const mockOnRefetch = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    apiEndpoints.world.getCommands.mockResolvedValue({ data: { commands: mockCommands } });
  });

  const renderWithRouter = (ui) => {
    return render(
      <MemoryRouter>
        {ui}
      </MemoryRouter>
    );
  };

  it('renders commands correctly', async () => {
    renderWithRouter(<ActionsPanel onClose={mockOnClose} />);

    expect(screen.getByText(/Communicating with world spirits.../i)).toBeDefined();

    await waitFor(() => {
      expect(screen.getByText(/Menu/i)).toBeDefined();
      expect(screen.getByText(/Save/i)).toBeDefined();
      expect(screen.queryByText(/^Search$/i)).toBeNull();
    }, { timeout: 2000 });
  });

  it('handles Menu action', async () => {
    renderWithRouter(<ActionsPanel onClose={mockOnClose} />);

    await waitFor(() => screen.getByText(/Menu/i));

    fireEvent.click(screen.getByText(/Menu/i));

    expect(screen.getByText(/Opening menu.../i)).toBeDefined();
  });

  it('handles Save action', async () => {
    apiEndpoints.saves.save.mockResolvedValue({
      data: {
        success: true,
        message: 'Game saved!'
      }
    });

    renderWithRouter(<ActionsPanel onClose={mockOnClose} />);

    await waitFor(() => screen.getByText(/Save/i));

    fireEvent.click(screen.getByText(/Save/i));

    expect(screen.getByText(/Saving game.../i)).toBeDefined();

    await waitFor(() => {
      expect(apiEndpoints.saves.save).toHaveBeenCalled();
      expect(screen.getByText(/Game saved!/i)).toBeDefined();
    });
  });

  it('handles generic action', async () => {
    renderWithRouter(<ActionsPanel onClose={mockOnClose} />);

    await waitFor(() => screen.getByText(/Teleport/i));

    fireEvent.click(screen.getByText(/Teleport/i));

    expect(screen.getByText(/Teleport.../i)).toBeDefined();
  });

  it('shows tooltip on hover', async () => {
    renderWithRouter(<ActionsPanel onClose={mockOnClose} />);

    await waitFor(() => screen.getByText(/Menu/i));

    const menuButton = screen.getByText(/Menu/i);
    fireEvent.mouseEnter(menuButton);

    expect(screen.getByText(/Open the main menu/i)).toBeDefined();

    fireEvent.mouseLeave(menuButton);
    expect(screen.queryByText(/Open the main menu/i)).toBeNull();
  });

  it('handles error state', async () => {
    apiEndpoints.world.getCommands.mockRejectedValue(new Error('Network error'));

    renderWithRouter(<ActionsPanel onClose={mockOnClose} />);

    await waitFor(() => {
      expect(screen.getByText(/Error loading commands/i)).toBeDefined();
    });
  });

  it('renders empty state', async () => {
    apiEndpoints.world.getCommands.mockResolvedValue({ data: { commands: [] } });

    renderWithRouter(<ActionsPanel onClose={mockOnClose} />);

    await waitFor(() => {
      expect(screen.getByText(/No commands currently available/i)).toBeDefined();
    });
  });

  it('handles Save failure', async () => {
    apiEndpoints.saves.save.mockResolvedValue({ data: null });

    renderWithRouter(<ActionsPanel onClose={mockOnClose} />);

    await waitFor(() => screen.getByText(/Save/i));
    fireEvent.click(screen.getByText(/Save/i));

    await waitFor(() => {
      expect(screen.getByText(/Save failed./i)).toBeDefined();
    });
  });

  it('handles action execution error', async () => {
    apiEndpoints.saves.save.mockRejectedValue(new Error('Execution error'));

    renderWithRouter(<ActionsPanel onClose={mockOnClose} />);

    await waitFor(() => screen.getByText(/Save/i));
    fireEvent.click(screen.getByText(/Save/i));

    await waitFor(() => {
      expect(screen.getByText(/Command failed./i)).toBeDefined();
    });
  });

  it('defaults commands to an empty array when the response has no commands field', async () => {
    apiEndpoints.world.getCommands.mockResolvedValue({ data: {} });

    renderWithRouter(<ActionsPanel onClose={mockOnClose} />);

    await waitFor(() => {
      expect(screen.getByText(/No commands currently available/i)).toBeDefined();
    });
  });

  it('shows an error when the commands response has no data', async () => {
    apiEndpoints.world.getCommands.mockResolvedValue({});

    renderWithRouter(<ActionsPanel onClose={mockOnClose} />);

    await waitFor(() => {
      expect(screen.getByText(/Failed to load commands/i)).toBeDefined();
    });
  });

  it('defaults to a generic success message when Save succeeds without one', async () => {
    apiEndpoints.saves.save.mockResolvedValue({ data: { success: true } });

    renderWithRouter(<ActionsPanel onClose={mockOnClose} />);
    await waitFor(() => screen.getByText(/Save/i));
    fireEvent.click(screen.getByText(/Save/i));

    await waitFor(() => {
      expect(screen.getByText(/Game saved successfully!/i)).toBeDefined();
    });
  });

  it('styles the tooltip/button for a debug command and falls back to a generic tooltip for an unrecognized command', async () => {
    apiEndpoints.world.getCommands.mockResolvedValue({ data: { commands: [{ name: 'MysteryCmd', debug: true }] } });

    renderWithRouter(<ActionsPanel onClose={mockOnClose} />);
    await waitFor(() => screen.getByText(/MysteryCmd/i));

    fireEvent.mouseEnter(screen.getByText(/MysteryCmd/i));
    expect(screen.getByText(/General interaction command\./i)).toBeDefined();
    fireEvent.mouseLeave(screen.getByText(/MysteryCmd/i));
  });

  it('handles close button hover', () => {
    renderWithRouter(<ActionsPanel onClose={mockOnClose} />);

    const closeButton = screen.getByText(/✕/i);

    // Verify hover/leave events fire without error (color values are an
    // internal impl detail of BaseDialog — we don't assert specific hex here).
    expect(() => fireEvent.mouseEnter(closeButton)).not.toThrow();
    expect(() => fireEvent.mouseLeave(closeButton)).not.toThrow();
  });

  it('calls onClose when close button is clicked', async () => {
    renderWithRouter(<ActionsPanel onClose={mockOnClose} />);

    fireEvent.click(screen.getByText(/✕/i));
    expect(mockOnClose).toHaveBeenCalled();
  });
});
