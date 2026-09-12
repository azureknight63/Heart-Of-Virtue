import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import DefeatDialog from './DefeatDialog';
import apiEndpoints from '../api/endpoints';
import { useAuth } from '../hooks/useApi';
import { makeSaveRow } from '../test/payloads';
import { LOAD_SAVE_FAILED, START_OVER_FAILED } from '../hooks/useDefeatRecovery';

vi.mock('../api/endpoints', () => ({
  default: {
    saves: {
      list: vi.fn(),
      load: vi.fn(),
      newGame: vi.fn()
    }
  }
}));

// Tripwire: DefeatDialog must never call useAuth().logout() (#587);
// mockLogout is asserted not called below.
vi.mock('../hooks/useApi', () => ({
  useAuth: vi.fn()
}));

/** What axios resolves with for a successful /saves/load or /game/new. */
const OK = { data: { success: true } };

describe('DefeatDialog', () => {
  // The in-flight label, named once: a negative assertion against a
  // hand-typed copy passes whether or not the copy is even spelled right.
  const LOADING_LABEL = 'LOADING…';

  const mockLogout = vi.fn();
  const mockOnRunChanged = vi.fn();
  /**
   * Rows in the shape GameService.list_saves actually returns — id, name,
   * timestamp(+_ms), is_autosave, level, map_name, room_title, playtime.
   * `LABELS` below pins the whole label for both rows (name, level, map,
   * room); the level-guard and untitled-name tests further down spell the
   * separator out themselves.
   * Both rows share makeSaveRow's timestamp, so their order is the server's;
   * the mount test gives them distinct times to exercise the client's sort.
   */
  const mockSaves = [
    makeSaveRow({ id: 'save1', name: 'Hero Save', level: 5, map_name: 'Dark Grotto', room_title: 'Entry Hall' }),
    makeSaveRow({ id: 'save2', name: 'Auto Save', level: 4, map_name: 'Village', room_title: 'Well Square', is_autosave: true }),
  ];
  const LABELS = [
    'Hero Save • Lv 5 • Dark Grotto • Entry Hall',
    'Auto Save • Lv 4 • Village • Well Square',
  ];

  const renderDialog = (endState = {}) =>
    render(<DefeatDialog endState={endState} onRunChanged={mockOnRunChanged} />);
  /** The first save's option has rendered: the list fetch resolved. */
  const waitForSaves = () =>
    waitFor(() => expect(screen.getByText(LABELS[0])).toBeInTheDocument());
  /** The list fetch has settled, whatever it returned. */
  const waitForListSettled = () =>
    waitFor(() => {
      // The request too, not only the spinner's absence: the spinner is
      // absent before the fetch starts, so a hook that ever set its loading
      // flag after an await would let this resolve on the pre-fetch render.
      // Same trap the sibling hook suite's `renderSettled` documents.
      expect(apiEndpoints.saves.list).toHaveBeenCalled();
      expect(screen.queryByText('Loading…')).toBeNull();
    });

  beforeEach(() => {
    vi.clearAllMocks();
    useAuth.mockReturnValue({ logout: mockLogout });
    apiEndpoints.saves.list.mockResolvedValue({ data: { saves: mockSaves } });
  });

  it('renders the defeat message and lists the saves newest first', async () => {
    // Served oldest first, with distinct times, so the order on screen can
    // only come from the client's compareSavesByRecency sort.
    apiEndpoints.saves.list.mockResolvedValue({
      data: {
        saves: [
          { ...mockSaves[0], timestamp_ms: Date.UTC(2026, 0, 1) },
          { ...mockSaves[1], timestamp_ms: Date.UTC(2026, 0, 2) },
        ],
      },
    });
    renderDialog({ message: 'You died.' });

    expect(screen.getByText('Defeat').textContent).toBe('Defeat');
    expect(screen.getByText('You died.').textContent).toBe('You died.');
    expect(screen.getByText('Loading…').textContent).toBe('Loading…');
    // The save list only exists once the fetch resolves.
    expect(screen.queryByRole('combobox')).toBeNull();

    await waitForListSettled();

    // One <option> per save, newest first, and the newest is preselected so
    // LOAD is immediately usable.
    const options = Array.from(screen.getByRole('combobox').options);
    expect(options.map((o) => o.textContent)).toEqual([LABELS[1], LABELS[0]]);
    expect(options.map((o) => o.value)).toEqual(['save2', 'save1']);
    expect(screen.getByRole('combobox').value).toBe('save2');
    expect(apiEndpoints.saves.list).toHaveBeenCalledTimes(1);
  });

  it('loads the preselected save and tells the parent the run changed', async () => {
    apiEndpoints.saves.load.mockResolvedValue(OK);
    renderDialog();
    await waitForSaves();

    fireEvent.click(screen.getByText('LOAD'));

    await waitFor(() => {
      // The SELECTED save's id, not the first row's name or index.
      expect(apiEndpoints.saves.load).toHaveBeenCalledWith('save1');
      expect(mockOnRunChanged).toHaveBeenCalledTimes(1);
    });
    expect(screen.queryByText(/Failed/)).toBeNull();
  });

  it('loads the save the player actually picked, not the default', async () => {
    apiEndpoints.saves.load.mockResolvedValue(OK);
    renderDialog();
    await waitForSaves();

    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'save2' } });
    expect(screen.getByRole('combobox').value).toBe('save2');
    fireEvent.click(screen.getByText('LOAD'));

    await waitFor(() => expect(apiEndpoints.saves.load).toHaveBeenCalledWith('save2'));
    expect(apiEndpoints.saves.load).toHaveBeenCalledTimes(1);
  });

  it('shows the load error and leaves LOAD usable for a retry', async () => {
    apiEndpoints.saves.load.mockRejectedValue(new Error('Load Failed'));
    renderDialog();
    await waitForSaves();

    fireEvent.click(screen.getByText('LOAD'));

    await waitFor(() => {
      expect(screen.getByText('Load Failed').textContent).toBe('Load Failed');
    });
    // A failed load must leave the dialog usable: the button comes back out of
    // its LOADING… state and a retry actually reaches the endpoint.
    expect(screen.getByText('LOAD').closest('button')).not.toBeDisabled();
    expect(mockOnRunChanged).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText('LOAD'));
    await waitFor(() => expect(apiEndpoints.saves.load).toHaveBeenCalledTimes(2));
  });

  it('starts a fresh run via /game/new on Start Over, without logging out', async () => {
    // Issue #587: START OVER used to call logout(), which killed the session
    // and dumped the (often unauthenticated test-bypass) player on the login
    // page with no way back in. It must call the same `saves.newGame()`
    // (POST /game/new) that MainMenuPage's New Game calls, and it must NOT
    // touch logout at all.
    apiEndpoints.saves.newGame.mockResolvedValue(OK);
    renderDialog();
    await waitForListSettled();

    fireEvent.click(screen.getByText('START OVER'));

    await waitFor(() => {
      expect(apiEndpoints.saves.newGame).toHaveBeenCalledTimes(1);
    });
    expect(apiEndpoints.saves.newGame).toHaveBeenCalledWith();
    expect(mockLogout).not.toHaveBeenCalled();
    // Starting over is not loading a save.
    expect(apiEndpoints.saves.load).not.toHaveBeenCalled();
    // The parent (GamePage, via CombatManager's onDefeatClose) is told the
    // underlying run changed so it can reset out of the defeat state — the
    // same signal a successful Load Save sends.
    await waitFor(() => expect(mockOnRunChanged).toHaveBeenCalledTimes(1));
  });

  it('blames nothing when the parent fails to refresh after a successful Start Over', async () => {
    // The request itself succeeded, so the dialog must not say the exit
    // failed. It says nothing at all: the run HAS changed, the parent is
    // already re-fetching, and no wording would give the player an action.
    apiEndpoints.saves.newGame.mockResolvedValue(OK);
    mockOnRunChanged.mockRejectedValueOnce(new Error('refetch failed'));
    renderDialog();
    await waitForListSettled();

    fireEvent.click(screen.getByText('START OVER'));

    // The run DID start over, so the dialog must not blame the request.
    // It says nothing at all instead: the parent is already re-fetching and
    // the dialog is on its way out, so there is nothing to tell the player.
    await waitFor(() => expect(mockOnRunChanged).toHaveBeenCalled());
    expect(screen.queryByText(START_OVER_FAILED)).toBeNull();
    expect(screen.queryByText(/failed/i)).toBeNull();
  });

  it('renders "No saves found" if list is empty', async () => {
    apiEndpoints.saves.list.mockResolvedValue({ data: { saves: [] } });
    renderDialog();

    await waitFor(() => {
      expect(screen.getByText('No saves found.')).toBeDefined();
    });
  });

  it('shows the fetch error when listing saves fails', async () => {
    apiEndpoints.saves.list.mockRejectedValue(new Error('Fetch Failed'));
    renderDialog();

    await waitFor(() => {
      expect(screen.getByText('Fetch Failed')).toBeDefined();
    });
  });

  it('falls back to a generic message when fetching saves fails without one', async () => {
    apiEndpoints.saves.list.mockRejectedValue({});
    renderDialog();

    await waitFor(() => {
      expect(screen.getByText('Failed to load saves.')).toBeDefined();
    });
  });

  it('falls back to a generic message when loading a save fails without a response or message', async () => {
    apiEndpoints.saves.load.mockRejectedValue({});
    renderDialog();
    await waitForSaves();

    fireEvent.click(screen.getByText('LOAD'));
    await waitFor(() => {
      expect(screen.getByText(LOAD_SAVE_FAILED)).toBeDefined();
    });
  });

  it('falls back to a generic message when Start Over fails without one', async () => {
    apiEndpoints.saves.newGame.mockRejectedValue({});
    renderDialog();
    await waitForListSettled();

    fireEvent.click(screen.getByText('START OVER'));

    await waitFor(() => {
      expect(screen.getByText(START_OVER_FAILED)).toBeDefined();
    });
    expect(mockLogout).not.toHaveBeenCalled();
    expect(mockOnRunChanged).not.toHaveBeenCalled();
  });

  it('omits the level segment when the server reports it as "?"', () => {
    // list_saves emits the STRING "?" when the row has no level, and the label
    // builder (saveSummaryParts in utils/localSave.js) guards with
    // `typeof row?.level === 'number'` — so the fallback must not leak "Lv ?"
    // into the picker.
    apiEndpoints.saves.list.mockResolvedValue({
      data: { saves: [makeSaveRow({ id: 's3', name: 'Broken Save', level: '?' })] },
    });
    renderDialog();

    return waitFor(() => {
      const label = screen.getByRole('combobox').options[0].textContent;
      // The claim is the level guard, not the place fields: a string level must
      // not leak "Lv ?" into the picker, while map_name/room_title still show.
      expect(label).not.toMatch(/Lv/);
      expect(label).toBe('Broken Save • Dark Grotto • Entry Hall');
    });
  });

  it('labels a save with no name "Untitled Save", as the main menu does', () => {
    // The picker used to join the raw name, so a nameless row opened with the
    // separator and nothing before it.
    apiEndpoints.saves.list.mockResolvedValue({
      data: { saves: [makeSaveRow({ id: 's4', name: '' })] },
    });
    renderDialog();

    return waitFor(() => {
      const label = screen.getByRole('combobox').options[0].textContent;
      expect(label.startsWith('Untitled Save • ')).toBe(true);
    });
  });

  it('does not render LOAD when there are no saves', async () => {
    apiEndpoints.saves.list.mockResolvedValue({ data: { saves: [] } });
    renderDialog();

    await waitFor(() => {
      expect(screen.getByText('No saves found.')).toBeDefined();
    });

    expect(screen.queryByText('LOAD'), 'LOAD button should not render when no saves exist').toBeNull();
  });

  it('falls back to a generic defeat message when endState has none', async () => {
    renderDialog();
    expect(screen.getByText('You have been defeated.')).toBeInTheDocument();
  });

  it('defaults the saves list to empty when the response has no data.saves', async () => {
    apiEndpoints.saves.list.mockResolvedValue({});
    renderDialog();

    await waitFor(() => {
      expect(screen.getByText('No saves found.')).toBeInTheDocument();
    });
  });

  it('shows the LOADING… label on the button while a load is in flight', async () => {
    let resolveLoad;
    apiEndpoints.saves.load.mockReturnValue(new Promise((r) => { resolveLoad = r; }));
    renderDialog();
    await waitForSaves();

    fireEvent.click(screen.getByText('LOAD'));

    expect(screen.getByText(LOADING_LABEL)).toBeInTheDocument();
    resolveLoad(OK);
    await waitFor(() => expect(mockOnRunChanged).toHaveBeenCalledTimes(1));
  });

  it('leaves the LOAD label alone while START OVER is in flight', async () => {
    // Both buttons disable while either exit runs, but only the pressed one
    // may say what it is doing: a single isSubmitting flag had START OVER
    // relabel LOAD as LOADING…, as if a save were being restored.
    let resolveNewGame;
    apiEndpoints.saves.newGame.mockReturnValue(new Promise((r) => { resolveNewGame = r; }));
    renderDialog();
    await waitForSaves();

    fireEvent.click(screen.getByText('START OVER'));

    expect(screen.getByText('LOAD').closest('button')).toBeDisabled();
    expect(screen.queryByText(LOADING_LABEL)).not.toBeInTheDocument();
    resolveNewGame(OK);
    await waitFor(() => expect(mockOnRunChanged).toHaveBeenCalledTimes(1));
  });

  it('prefers the server-provided error message when loading a save fails', async () => {
    apiEndpoints.saves.load.mockRejectedValue({ response: { data: { error: 'Save is corrupted.' } } });
    renderDialog();
    await waitForSaves();

    fireEvent.click(screen.getByText('LOAD'));

    await waitFor(() => {
      expect(screen.getByText('Save is corrupted.')).toBeInTheDocument();
    });
  });

  it('shows an error and re-enables START OVER when starting a new game fails', async () => {
    apiEndpoints.saves.newGame.mockRejectedValue(new Error('New game failed'));
    renderDialog();
    await waitForListSettled();

    fireEvent.click(screen.getByText('START OVER'));

    await waitFor(() => {
      expect(screen.getByText('New game failed')).toBeInTheDocument();
    });
    expect(screen.getByText('START OVER').closest('button')).not.toBeDisabled();
    // A failed Start Over must not have logged the player out or left the
    // defeat dialog thinking the run restarted.
    expect(mockLogout).not.toHaveBeenCalled();
    expect(mockOnRunChanged).not.toHaveBeenCalled();
  });

  it('tells the parent the run restarted only after /game/new resolves, and holds the button until then', async () => {
    // A deferred promise, so the in-flight state is observable: resolving
    // `newGame` immediately would let an implementation that fired the
    // callback first (or never disabled the button) pass the same assertions.
    let resolveNewGame;
    apiEndpoints.saves.newGame.mockReturnValue(new Promise((r) => { resolveNewGame = r; }));
    renderDialog();
    await waitForListSettled();

    fireEvent.click(screen.getByText('START OVER'));

    expect(apiEndpoints.saves.newGame).toHaveBeenCalledTimes(1);
    expect(mockOnRunChanged).not.toHaveBeenCalled();
    expect(screen.getByText('START OVER').closest('button')).toBeDisabled();

    resolveNewGame(OK);
    await waitFor(() => expect(mockOnRunChanged).toHaveBeenCalledTimes(1));
    expect(screen.getByText('START OVER').closest('button')).not.toBeDisabled();
  });
});
