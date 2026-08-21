import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import DefeatDialog from './DefeatDialog';
import apiEndpoints from '../api/endpoints';
import { useAuth } from '../hooks/useApi';
import { makeSaveRow } from '../test/payloads';

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
  /**
   * Rows in the shape GameService.list_saves actually returns — id, name,
   * timestamp(+_ms), is_autosave, level, map_name, room_title, playtime.
   *
   * !!! PRODUCT BUG (found while replacing the old hand-written fixture) !!!
   *
   * FIXED: DefeatDialog.jsx's `saveOptions` memo used to build its label from `s.location`.
   * **No serializer emits `location`** — GameService.list_saves
   * (src/api/services/game_service.py:~3588) emits `map_name` and
   * `room_title`, and MainMenuPage.jsx:447 reads exactly those two. So the
   * defeat-screen save picker silently drops the place and shows only
   * "Name • Lv N", which is textbook wire-field-name drift: the read sits
   * behind `if (s.location)` and failed closed. It now reads map_name/room_title.
   *
   * The previous fixture invented `location: 'Dark Forest'`, so the test agreed
   * with the component and the drift was invisible — the exact failure mode
   * CLAUDE.md calls this codebase's dominant bug class.
   *
   * The expectations below therefore pin the CURRENT (wrong) label against a
   * REAL payload. When DefeatDialog is fixed to read map_name/room_title,
   * `LABELS` is the one place to update if the emitted fields ever change.
   */
  const mockSaves = [
    makeSaveRow({ id: 'save1', name: 'Hero Save', level: 5, map_name: 'Dark Grotto', room_title: 'Entry Hall' }),
    makeSaveRow({ id: 'save2', name: 'Auto Save', level: 4, map_name: 'Village', room_title: 'Well Square', is_autosave: true }),
  ];
  // DefeatDialog now reads the fields list_saves actually emits (map_name,
  // room_title), matching MainMenuPage. Previously it read `s.location`,
  // which no serializer sends, so the place was silently dropped.
  const LABELS = [
    'Hero Save • Lv 5 • Dark Grotto • Entry Hall',
    'Auto Save • Lv 4 • Village • Well Square',
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    useAuth.mockReturnValue({ logout: mockLogout });
    apiEndpoints.saves.list.mockResolvedValue({ data: { saves: mockSaves } });
  });

  it('renders defeat message and loads saves on mount', async () => {
    render(<DefeatDialog endState={{ message: 'You died.' }} onLoadedSave={mockOnLoadedSave} />);

    expect(screen.getByText('Defeat').textContent).toBe('Defeat');
    expect(screen.getByText('You died.').textContent).toBe('You died.');
    expect(screen.getByText('Loading…').textContent).toBe('Loading…');
    // The save list only exists once the fetch resolves.
    expect(screen.queryByRole('combobox')).toBeNull();

    await waitFor(() => expect(screen.queryByText('Loading…')).toBeNull());

    // One <option> per save, in server order (list_saves sorts newest first),
    // and the first is preselected so LOAD is immediately usable.
    const options = Array.from(screen.getByRole('combobox').options);
    expect(options.map((o) => o.textContent)).toEqual(LABELS);
    expect(options.map((o) => o.value)).toEqual(['save1', 'save2']);
    expect(screen.getByRole('combobox').value).toBe('save1');
    expect(apiEndpoints.saves.list).toHaveBeenCalledTimes(1);
  });

  it('handles save loading successfully', async () => {
    apiEndpoints.saves.load.mockResolvedValue({ success: true });

    render(<DefeatDialog endState={{}} onLoadedSave={mockOnLoadedSave} />);

    await waitFor(() => {
      expect(screen.getByText(LABELS[0])).toBeDefined();
    });

    const loadBtn = screen.getByText('LOAD');
    fireEvent.click(loadBtn);

    await waitFor(() => {
      // The SELECTED save's id, not the first row's name or index.
      expect(apiEndpoints.saves.load).toHaveBeenCalledWith('save1');
      expect(mockOnLoadedSave).toHaveBeenCalledTimes(1);
    });
    expect(screen.queryByText(/Failed/)).toBeNull();
  });

  it('loads the save the player actually picked, not the default', async () => {
    apiEndpoints.saves.load.mockResolvedValue({ success: true });
    render(<DefeatDialog endState={{}} onLoadedSave={mockOnLoadedSave} />);
    await waitFor(() => expect(screen.getByText(LABELS[0])).toBeDefined());

    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'save2' } });
    expect(screen.getByRole('combobox').value).toBe('save2');
    fireEvent.click(screen.getByText('LOAD'));

    await waitFor(() => expect(apiEndpoints.saves.load).toHaveBeenCalledWith('save2'));
    expect(apiEndpoints.saves.load).toHaveBeenCalledTimes(1);
  });

  it('handles save loading error', async () => {
    apiEndpoints.saves.load.mockRejectedValue(new Error('Load Failed'));

    render(<DefeatDialog endState={{}} onLoadedSave={mockOnLoadedSave} />);

    await waitFor(() => {
      expect(screen.getByText(LABELS[0])).toBeDefined();
    });

    const loadBtn = screen.getByText('LOAD');
    fireEvent.click(loadBtn);

    await waitFor(() => {
      expect(screen.getByText('Load Failed').textContent).toBe('Load Failed');
    });
    // A failed load must leave the dialog usable: the button comes back out of
    // its LOADING… state and a retry actually reaches the endpoint.
    expect(screen.getByText('LOAD').closest('button').disabled).toBe(false);
    expect(mockOnLoadedSave).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText('LOAD'));
    await waitFor(() => expect(apiEndpoints.saves.load).toHaveBeenCalledTimes(2));
  });

  it('handles start over (logout)', async () => {
    render(<DefeatDialog endState={{}} onLoadedSave={mockOnLoadedSave} />);

    await waitFor(() => {
      expect(screen.queryByText('Loading…')).toBeNull();
    });

    const startOverBtn = screen.getByText('START OVER');
    fireEvent.click(startOverBtn);

    await waitFor(() => {
      expect(mockLogout).toHaveBeenCalledTimes(1);
    });
    expect(mockLogout).toHaveBeenCalledWith();
    // Starting over is not loading a save.
    expect(apiEndpoints.saves.load).not.toHaveBeenCalled();
    expect(mockOnLoadedSave).not.toHaveBeenCalled();
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

  it('falls back to a generic message when fetching saves fails without one', async () => {
    apiEndpoints.saves.list.mockRejectedValue({});

    render(<DefeatDialog endState={{}} onLoadedSave={mockOnLoadedSave} />);

    await waitFor(() => {
      expect(screen.getByText('Failed to load saves.')).toBeDefined();
    });
  });

  it('falls back to a generic message when loading a save fails without a response or message', async () => {
    apiEndpoints.saves.load.mockRejectedValue({});

    render(<DefeatDialog endState={{}} onLoadedSave={mockOnLoadedSave} />);
    await waitFor(() => expect(screen.getByText(LABELS[0])).toBeDefined());

    fireEvent.click(screen.getByText('LOAD'));
    await waitFor(() => {
      expect(screen.getByText('Failed to load save.')).toBeDefined();
    });
  });

  it('falls back to a generic message when Start Over fails without one', async () => {
    mockLogout.mockRejectedValue({});
    render(<DefeatDialog endState={{}} onLoadedSave={mockOnLoadedSave} />);

    await waitFor(() => expect(screen.queryByText('Loading…')).toBeNull());
    fireEvent.click(screen.getByText('START OVER'));

    await waitFor(() => {
      expect(screen.getByText('Failed to start over.')).toBeDefined();
    });
  });

  it('omits the level segment when the server reports it as "?"', () => {
    // list_saves emits the STRING "?" when the row has no level, and the label
    // builder guards with `typeof s.level === 'number'` — so the fallback must
    // not leak "Lv ?" into the picker.
    apiEndpoints.saves.list.mockResolvedValue({
      data: { saves: [makeSaveRow({ id: 's3', name: 'Broken Save', level: '?' })] },
    });
    render(<DefeatDialog endState={{}} onLoadedSave={mockOnLoadedSave} />);

    return waitFor(() => {
      const label = screen.getByRole('combobox').options[0].textContent;
      // The claim is the level guard, not the place fields: a string level must
      // not leak "Lv ?" into the picker, while map_name/room_title still show.
      expect(label).not.toMatch(/Lv/);
      expect(label).toBe('Broken Save • Dark Grotto • Entry Hall');
    });
  });

  it('shows error if trying to load without a selected save', async () => {
    apiEndpoints.saves.list.mockResolvedValue({ data: { saves: [] } });
    render(<DefeatDialog endState={{}} onLoadedSave={mockOnLoadedSave} />);

    await waitFor(() => {
      expect(screen.getByText('No saves found.')).toBeDefined();
    });

    // With no saves, no LOAD button should be rendered at all
    const loadBtn = screen.queryByText('LOAD');
    expect(loadBtn, 'LOAD button should not render when no saves exist').toBeNull();
  });

  it('falls back to a generic defeat message when endState has none', async () => {
    render(<DefeatDialog endState={{}} onLoadedSave={mockOnLoadedSave} />);
    expect(screen.getByText('You have been defeated.')).toBeInTheDocument();
  });

  it('defaults the saves list to empty when the response has no data.saves', async () => {
    apiEndpoints.saves.list.mockResolvedValue({});
    render(<DefeatDialog endState={{}} onLoadedSave={mockOnLoadedSave} />);

    await waitFor(() => {
      expect(screen.getByText('No saves found.')).toBeInTheDocument();
    });
  });

  it('shows the LOADING… label on the button while a load is in flight', async () => {
    let resolveLoad;
    apiEndpoints.saves.load.mockReturnValue(new Promise((r) => { resolveLoad = r; }));
    render(<DefeatDialog endState={{}} onLoadedSave={mockOnLoadedSave} />);

    await waitFor(() => expect(screen.getByText(LABELS[0])).toBeInTheDocument());
    fireEvent.click(screen.getByText('LOAD'));

    expect(screen.getByText('LOADING…')).toBeInTheDocument();
    resolveLoad({ success: true });
    await waitFor(() => expect(mockOnLoadedSave).toHaveBeenCalledTimes(1));
  });

  it('prefers the server-provided error message when loading a save fails', async () => {
    apiEndpoints.saves.load.mockRejectedValue({ response: { data: { error: 'Save is corrupted.' } } });
    render(<DefeatDialog endState={{}} onLoadedSave={mockOnLoadedSave} />);

    await waitFor(() => expect(screen.getByText(LABELS[0])).toBeInTheDocument());
    fireEvent.click(screen.getByText('LOAD'));

    await waitFor(() => {
      expect(screen.getByText('Save is corrupted.')).toBeInTheDocument();
    });
  });

  it('shows an error and stops loading when logout fails on Start Over', async () => {
    mockLogout.mockRejectedValue(new Error('Logout failed'));
    render(<DefeatDialog endState={{}} onLoadedSave={mockOnLoadedSave} />);

    await waitFor(() => expect(screen.queryByText('Loading…')).toBeNull());
    fireEvent.click(screen.getByText('START OVER'));

    await waitFor(() => {
      expect(screen.getByText('Logout failed')).toBeInTheDocument();
    });
    expect(screen.getByText('START OVER')).not.toBeDisabled();
  });
});
