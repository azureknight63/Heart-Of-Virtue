import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
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

  it('renders commands correctly', async () => {
    render(<ActionsPanel onClose={mockOnClose} />);

    expect(screen.getByText(/Loading commands.../i)).toBeDefined();

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

    render(<ActionsPanel onClose={mockOnClose} onRefetch={mockOnRefetch} />);

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
    render(<ActionsPanel onClose={mockOnClose} />);

    await waitFor(() => screen.getByText(/Menu/i));
    
    fireEvent.click(screen.getByText(/Menu/i));

    expect(screen.getByText(/Opening menu.../i)).toBeDefined();

    await waitFor(() => {
      expect(screen.getByText(/Menu functionality coming soon./i)).toBeDefined();
    }, { timeout: 2000 });
  });

  it('handles Save action', async () => {
    apiEndpoints.saves.save.mockResolvedValue({ 
      data: { 
        message: 'Game saved!' 
      } 
    });

    render(<ActionsPanel onClose={mockOnClose} />);

    await waitFor(() => screen.getByText(/Save/i));
    
    fireEvent.click(screen.getByText(/Save/i));

    expect(screen.getByText(/Saving game.../i)).toBeDefined();

    await waitFor(() => {
      expect(apiEndpoints.saves.save).toHaveBeenCalled();
      expect(screen.getByText(/Game saved!/i)).toBeDefined();
    });
  });

  it('handles generic action', async () => {
    render(<ActionsPanel onClose={mockOnClose} />);

    await waitFor(() => screen.getByText(/Teleport/i));
    
    fireEvent.click(screen.getByText(/Teleport/i));

    expect(screen.getByText(/Teleport.../i)).toBeDefined();
  });

  it('shows tooltip on hover', async () => {
    render(<ActionsPanel onClose={mockOnClose} />);

    await waitFor(() => screen.getByText(/Search/i));
    
    const searchButton = screen.getAllByText(/Search/i)[0];
    fireEvent.mouseEnter(searchButton);

    expect(screen.getByText(/Search the current location/i)).toBeDefined();

    fireEvent.mouseLeave(searchButton);
    expect(screen.queryByText(/Search the current location/i)).toBeNull();
  });

  it('handles error state', async () => {
    apiEndpoints.world.getCommands.mockRejectedValue(new Error('Network error'));

    render(<ActionsPanel onClose={mockOnClose} />);

    await waitFor(() => {
      expect(screen.getByText(/Error loading commands/i)).toBeDefined();
    });
  });

  it('renders empty state', async () => {
    apiEndpoints.world.getCommands.mockResolvedValue({ data: { commands: [] } });

    render(<ActionsPanel onClose={mockOnClose} />);

    await waitFor(() => {
      expect(screen.getByText(/No commands available/i)).toBeDefined();
    });
  });

  it('handles Search with no messages', async () => {
    apiEndpoints.world.search.mockResolvedValue({ 
      data: { 
        messages: [] 
      } 
    });

    render(<ActionsPanel onClose={mockOnClose} />);

    await waitFor(() => screen.getByText(/Search/i));
    fireEvent.click(screen.getByText(/Search/i));

    await waitFor(() => {
      expect(screen.getByText(/Search complete./i)).toBeDefined();
    });
  });

  it('handles Search failure', async () => {
    apiEndpoints.world.search.mockResolvedValue({ data: null });

    render(<ActionsPanel onClose={mockOnClose} />);

    await waitFor(() => screen.getByText(/Search/i));
    fireEvent.click(screen.getByText(/Search/i));

    await waitFor(() => {
      expect(screen.getByText(/Search failed./i)).toBeDefined();
    });
  });

  it('handles Save failure', async () => {
    apiEndpoints.saves.save.mockResolvedValue({ data: null });

    render(<ActionsPanel onClose={mockOnClose} />);

    await waitFor(() => screen.getByText(/Save/i));
    fireEvent.click(screen.getByText(/Save/i));

    await waitFor(() => {
      expect(screen.getByText(/Save failed./i)).toBeDefined();
    });
  });

  it('handles action execution error', async () => {
    apiEndpoints.world.search.mockRejectedValue(new Error('Execution error'));

    render(<ActionsPanel onClose={mockOnClose} />);

    await waitFor(() => screen.getByText(/Search/i));
    fireEvent.click(screen.getByText(/Search/i));

    await waitFor(() => {
      expect(screen.getByText(/Command failed./i)).toBeDefined();
    });
  });

  it('handles close button hover', () => {
    render(<ActionsPanel onClose={mockOnClose} />);

    const closeButton = screen.getByText(/✕/i);
    fireEvent.mouseEnter(closeButton);
    expect(closeButton.style.backgroundColor).toBe('rgb(255, 102, 0)');

    fireEvent.mouseLeave(closeButton);
    expect(closeButton.style.backgroundColor).toBe('rgb(204, 68, 0)');
  });

  it('calls onClose when close button is clicked', async () => {
    render(<ActionsPanel onClose={mockOnClose} />);

    fireEvent.click(screen.getByText(/✕/i));
    expect(mockOnClose).toHaveBeenCalled();
  });
});
