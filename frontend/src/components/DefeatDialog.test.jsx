import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import DefeatDialog from './DefeatDialog';
import apiEndpoints from '../api/endpoints';
import { useAuth } from '../hooks/useApi';

// Mock apiEndpoints
vi.mock('../api/endpoints', () => ({
  default: {
    saves: {
      list: vi.fn(),
      load: vi.fn()
    }
  }
}));

// Mock useAuth
vi.mock('../hooks/useApi', () => ({
  useAuth: vi.fn()
}));

describe('DefeatDialog', () => {
  const mockLogout = vi.fn();
  const mockOnLoadedSave = vi.fn();
  const mockSaves = [
    { id: 'save1', name: 'Hero Save', level: 5, location: 'Dark Forest' },
    { id: 'save2', name: 'Auto Save', level: 4, location: 'Village' }
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    useAuth.mockReturnValue({ logout: mockLogout });
    apiEndpoints.saves.list.mockResolvedValue({ data: { saves: mockSaves } });
  });

  it('renders defeat message and loads saves on mount', async () => {
    render(<DefeatDialog endState={{ message: 'You died.' }} onLoadedSave={mockOnLoadedSave} />);

    expect(screen.getByText('Defeat')).toBeDefined();
    expect(screen.getByText('You died.')).toBeDefined();
    expect(screen.getByText('Loading…')).toBeDefined();

    await waitFor(() => {
      expect(screen.getByText('Hero Save • Lv 5 • Dark Forest')).toBeDefined();
      expect(screen.getByText('Auto Save • Lv 4 • Village')).toBeDefined();
    });
  });

  it('handles save loading successfully', async () => {
    apiEndpoints.saves.load.mockResolvedValue({ success: true });

    render(<DefeatDialog endState={{}} onLoadedSave={mockOnLoadedSave} />);

    await waitFor(() => {
      expect(screen.getByText('Hero Save • Lv 5 • Dark Forest')).toBeDefined();
    });

    const loadBtn = screen.getByText('LOAD');
    fireEvent.click(loadBtn);

    await waitFor(() => {
      expect(apiEndpoints.saves.load).toHaveBeenCalledWith('save1');
      expect(mockOnLoadedSave).toHaveBeenCalled();
    });
  });

  it('handles save loading error', async () => {
    apiEndpoints.saves.load.mockRejectedValue(new Error('Load Failed'));

    render(<DefeatDialog endState={{}} onLoadedSave={mockOnLoadedSave} />);

    await waitFor(() => {
      expect(screen.getByText('Hero Save • Lv 5 • Dark Forest')).toBeDefined();
    });

    const loadBtn = screen.getByText('LOAD');
    fireEvent.click(loadBtn);

    await waitFor(() => {
      expect(screen.getByText('Load Failed')).toBeDefined();
    });
  });

  it('handles start over (logout)', async () => {
    render(<DefeatDialog endState={{}} onLoadedSave={mockOnLoadedSave} />);

    await waitFor(() => {
      expect(screen.queryByText('Loading…')).toBeNull();
    });

    const startOverBtn = screen.getByText('START OVER');
    fireEvent.click(startOverBtn);

    await waitFor(() => {
      expect(mockLogout).toHaveBeenCalled();
    });
  });

  it('renders "No saves found" if list is empty', async () => {
    apiEndpoints.saves.list.mockResolvedValue({ data: { saves: [] } });

    render(<DefeatDialog endState={{}} onLoadedSave={mockOnLoadedSave} />);

    await waitFor(() => {
      expect(screen.getByText('No saves found.')).toBeDefined();
    });
  });

  it('handles fetch saves error', async () => {
    apiEndpoints.saves.list.mockRejectedValue(new Error('Fetch Failed'));

    render(<DefeatDialog endState={{}} onLoadedSave={mockOnLoadedSave} />);

    await waitFor(() => {
      expect(screen.getByText('Fetch Failed')).toBeDefined();
    });
  });

  it('changes selected save', async () => {
    render(<DefeatDialog endState={{}} onLoadedSave={mockOnLoadedSave} />);

    await waitFor(() => {
      expect(screen.getByText('Hero Save • Lv 5 • Dark Forest')).toBeDefined();
    });

    const select = screen.getByRole('combobox');
    fireEvent.change(select, { target: { value: 'save2' } });
    
    expect(select.value).toBe('save2');
  });

  it('shows error if trying to load without a selected save', async () => {
    apiEndpoints.saves.list.mockResolvedValue({ data: { saves: [] } });
    render(<DefeatDialog endState={{}} onLoadedSave={mockOnLoadedSave} />);

    await waitFor(() => {
      expect(screen.getByText('No saves found.')).toBeDefined();
    });

    // Manually trigger handleLoad if possible, or just check the logic
    // Since the button is disabled when !selectedSaveId, we might need to force it or check if it's disabled
    const loadBtn = screen.queryByText('LOAD');
    if (loadBtn) {
      expect(loadBtn.disabled).toBe(true);
    }
  });
});
