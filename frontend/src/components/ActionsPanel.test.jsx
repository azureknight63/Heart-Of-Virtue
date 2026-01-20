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
      search: vi.fn(),
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
    { name: 'Search', debug: false },
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
      expect(screen.getByText(/Search/i)).toBeDefined();
    }, { timeout: 2000 });
  });

  it('handles Search action', async () => {
    apiEndpoints.world.search.mockResolvedValue({
      data: {
        messages: ['You found something!']
      }
    });

    renderWithRouter(<ActionsPanel onClose={mockOnClose} onRefetch={mockOnRefetch} />);

    await waitFor(() => screen.getByText(/Search/i));

    fireEvent.click(screen.getByText(/Search/i));

    expect(screen.getByText(/Searching.../i)).toBeDefined();

    await waitFor(() => {
      expect(apiEndpoints.world.search).toHaveBeenCalled();
      expect(screen.getByText(/You found something!/i)).toBeDefined();
      expect(mockOnRefetch).toHaveBeenCalled();
    });
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

    await waitFor(() => screen.getByText(/Search/i));

    const searchButton = screen.getAllByText(/Search/i)[0];
    fireEvent.mouseEnter(searchButton);

    expect(screen.getByText(/Search the current location/i)).toBeDefined();

    fireEvent.mouseLeave(searchButton);
    expect(screen.queryByText(/Search the current location/i)).toBeNull();
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

  it('handles Search with no messages', async () => {
    apiEndpoints.world.search.mockResolvedValue({
      data: {
        messages: []
      }
    });

    renderWithRouter(<ActionsPanel onClose={mockOnClose} />);

    await waitFor(() => screen.getByText(/Search/i));
    fireEvent.click(screen.getByText(/Search/i));

    await waitFor(() => {
      expect(screen.getByText(/Search complete./i)).toBeDefined();
    });
  });

  it('handles Search failure', async () => {
    apiEndpoints.world.search.mockResolvedValue({ data: null });

    renderWithRouter(<ActionsPanel onClose={mockOnClose} />);

    await waitFor(() => screen.getByText(/Search/i));
    fireEvent.click(screen.getByText(/Search/i));

    await waitFor(() => {
      expect(screen.getByText(/Search failed./i)).toBeDefined();
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
    apiEndpoints.world.search.mockRejectedValue(new Error('Execution error'));

    renderWithRouter(<ActionsPanel onClose={mockOnClose} />);

    await waitFor(() => screen.getByText(/Search/i));
    fireEvent.click(screen.getByText(/Search/i));

    await waitFor(() => {
      expect(screen.getByText(/Command failed./i)).toBeDefined();
    });
  });

  it('handles close button hover', () => {
    renderWithRouter(<ActionsPanel onClose={mockOnClose} />);

    const closeButton = screen.getByText(/✕/i);
    fireEvent.mouseEnter(closeButton);
    // BaseDialog uses color for hover, not backgroundColor
    expect(closeButton.style.color).toBe('rgb(255, 238, 170)'); // #ffeeaa

    fireEvent.mouseLeave(closeButton);
    expect(closeButton.style.color).toBe('rgb(136, 136, 136)'); // #888888
  });

  it('calls onClose when close button is clicked', async () => {
    renderWithRouter(<ActionsPanel onClose={mockOnClose} />);

    fireEvent.click(screen.getByText(/✕/i));
    expect(mockOnClose).toHaveBeenCalled();
  });
});
