import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import React, { useState } from 'react';
import MainMenuPage from './MainMenuPage';
import { saves } from '../api/endpoints';
import { MemoryRouter } from 'react-router-dom';

// Mock useNavigate
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
    const actual = await vi.importActual('react-router-dom');
    return {
        ...actual,
        useNavigate: () => mockNavigate,
    };
});

// Mock useAuth
vi.mock('../hooks/useApi', () => ({
    useAuth: () => ({
        logout: vi.fn(),
    }),
}));

// Mock useAudio - create stable mocks outside to prevent recreation
const mockAudioContext = {
    playBGM: vi.fn(),
    playSFX: vi.fn(),
    musicVolume: 0.5,
    setMusicVolume: vi.fn(),
    sfxVolume: 0.5,
    setSfxVolume: vi.fn(),
    isMusicMuted: false,
    setIsMusicMuted: vi.fn(),
    isSfxMuted: false,
    setIsSfxMuted: vi.fn(),
};

vi.mock('../context/AudioContext', () => {
    return {
        useAudio: () => mockAudioContext,
        AudioProvider: ({ children }) => <div>{children}</div>,
    };
});

// Mock ToastContext
vi.mock('../context/ToastContext', () => ({
    useToast: () => ({
        showError: vi.fn(),
        showSuccess: vi.fn(),
        showInfo: vi.fn(),
    }),
    ToastProvider: ({ children }) => <div>{children}</div>,
}));

// Mock saves API
vi.mock('../api/endpoints', () => ({
    saves: {
        list: vi.fn(),
        load: vi.fn(),
        delete: vi.fn(),
        newGame: vi.fn(),
    },
}));

describe('MainMenuPage', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('renders Continue button when saves exist', async () => {
        const mockSaves = [
            { id: 1, name: 'Save 1', timestamp: '2023-01-01T10:00:00Z', level: 1, map_name: 'Map 1', room_title: 'Room 1' },
            { id: 2, name: 'Save 2', timestamp: '2023-01-02T10:00:00Z', level: 2, map_name: 'Map 2', room_title: 'Room 2' },
        ];
        saves.list.mockResolvedValue({ data: { saves: mockSaves } });

        render(
            <MemoryRouter>
                <MainMenuPage />
            </MemoryRouter>
        );

        await waitFor(() => {
            expect(screen.getByText(/Continue/i)).toBeDefined();
        });
    });

    it('does not render Continue or Load Game buttons when no saves exist', async () => {
        saves.list.mockResolvedValue({ data: { saves: [] } });

        render(
            <MemoryRouter>
                <MainMenuPage />
            </MemoryRouter>
        );

        await waitFor(() => {
            expect(screen.queryByText(/Continue/i)).toBeNull();
            expect(screen.queryByText(/Load Game/i)).toBeNull();
        });
    });

    it('loads the most recent save when Continue is clicked', async () => {
        const mockSaves = [
            { id: 'old', name: 'Old Save', timestamp: '2023-01-01', level: 1, map_name: 'Map 1', room_title: 'Room 1' },
            { id: 'new', name: 'New Save', timestamp: '2023-01-02', level: 2, map_name: 'Map 2', room_title: 'Room 2' },
        ];
        saves.list.mockResolvedValue({ data: { saves: mockSaves } });
        saves.load.mockResolvedValue({ success: true });

        render(
            <MemoryRouter>
                <MainMenuPage />
            </MemoryRouter>
        );

        await waitFor(() => screen.getByText(/Continue/i));
        fireEvent.click(screen.getByText(/Continue/i));

        expect(saves.load).toHaveBeenCalledWith('new');
        await waitFor(() => {
            expect(mockNavigate).toHaveBeenCalledWith('/game');
        });
    });

    it('navigates to game on New Game click', async () => {
        saves.list.mockResolvedValue({ data: { saves: [] } });

        render(
            <MemoryRouter>
                <MainMenuPage />
            </MemoryRouter>
        );

        fireEvent.click(screen.getByText(/New Game/i));
        await waitFor(() => {
            expect(mockNavigate).toHaveBeenCalledWith('/game');
        });
    });

    it('opens load modal on Load Game click', async () => {
        const mockSaves = [
            { id: 1, name: 'Save 1', timestamp: '2023-01-01T10:00:00Z', level: 1, map_name: 'Map 1', room_title: 'Room 1' }
        ];
        saves.list.mockResolvedValue({ data: { saves: mockSaves } });

        render(
            <MemoryRouter>
                <MainMenuPage />
            </MemoryRouter>
        );

        await waitFor(() => screen.getByText(/Load Game/i));
        fireEvent.click(screen.getByText(/Load Game/i));

        await waitFor(() => {
            expect(screen.getByText(/Save 1/i)).toBeDefined();
        });
    });

    it('deletes saves from the load modal', async () => {
        const mockSaves = [
            { id: 'old', name: 'Old Save', timestamp: '2023-01-01', level: 1, map_name: 'Map 1', room_title: 'Room 1' },
            { id: 'new', name: 'New Save', timestamp: '2023-01-02', level: 2, map_name: 'Map 2', room_title: 'Room 2' },
        ];
        saves.list.mockResolvedValue({ data: { saves: mockSaves } });
        saves.delete.mockResolvedValue({ success: true });

        vi.spyOn(window, 'confirm').mockReturnValue(true);

        render(
            <MemoryRouter>
                <MainMenuPage />
            </MemoryRouter>
        );

        await waitFor(() => expect(screen.getByText(/Continue/i)).toBeDefined());

        fireEvent.click(screen.getAllByText(/Load Game/i)[0]);

        await waitFor(() => screen.getByText(/New Save/i));
        // The text is inside a p inside a div inside another div (the slot)
        const newSaveText = screen.getByText(/New Save/i);
        // Find the slot by going up to the div that has the buttons
        const newSaveSlot = newSaveText.closest('div[style*="justify-content: space-between"]');
        const deleteNewButton = within(newSaveSlot).getByText(/Delete/i);

        fireEvent.click(deleteNewButton);
        expect(saves.delete).toHaveBeenCalledWith('new');

        await waitFor(() => {
            expect(screen.queryByText(/New Save/i)).toBeNull();
        });
    });

    it('opens settings modal on Settings click', async () => {
        saves.list.mockResolvedValue({ data: { saves: [] } });
        render(
            <MemoryRouter>
                <MainMenuPage />
            </MemoryRouter>
        );

        fireEvent.click(screen.getByText(/Settings/i));
        expect(screen.getByText(/Audio Settings/i)).toBeDefined();
    });

    it('opens credits modal on Credits click', async () => {
        saves.list.mockResolvedValue({ data: { saves: [] } });
        render(
            <MemoryRouter>
                <MainMenuPage />
            </MemoryRouter>
        );

        fireEvent.click(screen.getByText(/Credits/i));
        expect(screen.getByText(/The Development Team/i)).toBeDefined();
    });

    it('navigates to login on Logout click', async () => {
        saves.list.mockResolvedValue({ data: { saves: [] } });
        render(
            <MemoryRouter>
                <MainMenuPage />
            </MemoryRouter>
        );

        fireEvent.click(screen.getByText(/Logout/i));
        await waitFor(() => {
            expect(mockNavigate).toHaveBeenCalledWith('/login');
        });
    });

    it('handles volume slider changes', async () => {
        saves.list.mockResolvedValue({ data: { saves: [] } });
        render(
            <MemoryRouter>
                <MainMenuPage />
            </MemoryRouter>
        );

        fireEvent.click(screen.getByText(/Settings/i));

        // Test that settings modal opens and sliders exist
        const sliders = screen.getAllByRole('slider');
        expect(sliders.length).toBeGreaterThan(0);

        fireEvent.change(sliders[0], { target: { value: '0.8' } });
        expect(mockAudioContext.setMusicVolume).toHaveBeenCalledWith(0.8);

        fireEvent.change(sliders[1], { target: { value: '0.2' } });
        expect(mockAudioContext.setSfxVolume).toHaveBeenCalledWith(0.2);
    });

    it('defaults music/sfx volume to 0% when undefined', () => {
        saves.list.mockResolvedValue({ data: { saves: [] } });
        const originalMusic = mockAudioContext.musicVolume;
        const originalSfx = mockAudioContext.sfxVolume;
        mockAudioContext.musicVolume = undefined;
        mockAudioContext.sfxVolume = undefined;

        render(<MemoryRouter><MainMenuPage /></MemoryRouter>);
        fireEvent.click(screen.getByText(/Settings/i));

        expect(screen.getAllByText('0%').length).toBe(2);
        mockAudioContext.musicVolume = originalMusic;
        mockAudioContext.sfxVolume = originalSfx;
    });

    it('defaults the load-modal save list to empty when the response has no data.saves', async () => {
        saves.list.mockResolvedValueOnce({ data: { saves: [{ id: 'a', name: 'A', timestamp: '2023-01-01', level: 1, map_name: 'M', room_title: 'R' }] } });
        render(<MemoryRouter><MainMenuPage /></MemoryRouter>);
        await waitFor(() => screen.getByText(/Load Game/i));

        saves.list.mockResolvedValueOnce({});
        fireEvent.click(screen.getByText(/Load Game/i));

        await waitFor(() => {
            expect(screen.getByText(/No saves found\./i)).toBeInTheDocument();
        });
    });

    it('activates a save row via keyboard (Enter/Space)', async () => {
        const mockSaves = [{ id: 'cloud-1', name: 'Cloud Save', timestamp: '2023-01-01', level: 1, map_name: 'M', room_title: 'R' }];
        saves.list.mockResolvedValue({ data: { saves: mockSaves } });
        saves.load.mockResolvedValue({});

        render(<MemoryRouter><MainMenuPage /></MemoryRouter>);
        await waitFor(() => screen.getByText(/Load Game/i));
        fireEvent.click(screen.getByText(/Load Game/i));
        await waitFor(() => screen.getByText(/Cloud Save/i));

        const row = screen.getByText(/Cloud Save/i).closest('[style*="cursor: pointer"]');
        fireEvent.keyDown(row, { key: 'Enter' });

        await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/game'));
    });

    it('shows "Untitled Save" when a save has no name', async () => {
        const mockSaves = [{ id: 'a', timestamp: '2023-01-01', level: 1, map_name: 'M', room_title: 'R' }];
        saves.list.mockResolvedValue({ data: { saves: mockSaves } });

        render(<MemoryRouter><MainMenuPage /></MemoryRouter>);
        await waitFor(() => screen.getByText(/Load Game/i));
        fireEvent.click(screen.getByText(/Load Game/i));

        await waitFor(() => {
            expect(screen.getByText('Untitled Save')).toBeInTheDocument();
        });
    });

    it('closes the settings and credits modals', () => {
        saves.list.mockResolvedValue({ data: { saves: [] } });
        render(<MemoryRouter><MainMenuPage /></MemoryRouter>);

        fireEvent.click(screen.getByText(/Settings/i));
        fireEvent.click(screen.getByText('✕'));
        expect(screen.queryByText(/Audio Settings/i)).not.toBeInTheDocument();

        fireEvent.click(screen.getByText(/Credits/i));
        fireEvent.click(screen.getByText('✕'));
        expect(screen.queryByText(/The Development Team/i)).not.toBeInTheDocument();
    });

    it('closes the load-game modal', async () => {
        saves.list.mockResolvedValue({ data: { saves: [{ id: 1, name: 'Save 1', timestamp: '2023-01-01', level: 1, map_name: 'M', room_title: 'R' }] } });
        render(<MemoryRouter><MainMenuPage /></MemoryRouter>);

        await waitFor(() => screen.getByText(/Load Game/i));
        fireEvent.click(screen.getByText(/Load Game/i));
        await waitFor(() => screen.getByText(/Save 1/i));

        fireEvent.click(screen.getByText('✕'));
        expect(screen.queryByText(/Save 1/i)).not.toBeInTheDocument();
    });

    it('shows an empty state in the load modal when the re-fetched list comes back empty', async () => {
        // Mount with one save so the "Load Game" button renders...
        saves.list.mockResolvedValueOnce({
            data: { saves: [{ id: 1, name: 'S', timestamp: '2023-01-01', level: 1, map_name: 'M', room_title: 'R' }] },
        });
        render(<MemoryRouter><MainMenuPage /></MemoryRouter>);
        await waitFor(() => screen.getByText(/Load Game/i));

        // ...but the re-fetch triggered by opening the modal returns none.
        saves.list.mockResolvedValueOnce({ data: { saves: [] } });
        fireEvent.click(screen.getByText(/Load Game/i));

        await waitFor(() => {
            expect(screen.getByText(/No saves found\./i)).toBeInTheDocument();
        });
    });

    it('regression guard: a cloud save stamped in the future does not steal Continue from a live session', async () => {
        // The local blob's timestamp comes from the BROWSER clock (new Date() in
        // useAutosave); a cloud row's timestamp_ms comes from the SERVER clock
        // (SQLite CURRENT_TIMESTAMP). Ranking one against the other means a
        // browser running slow makes every cloud autosave look newer than the
        // live session, sending Continue down saves.load() and replacing the
        // in-memory session with a snapshot up to 20 ticks old. Continue must
        // key off the blob's freshness against its own clock, not a cross-clock
        // race — so even a cloud row dated an hour ahead must not win.
        localStorage.setItem('hov_local_autosave', JSON.stringify({
            timestamp: new Date(Date.now() - 60_000).toISOString(),
            player: { level: 9, map_name: 'Dark Grotto', room_title: 'Entrance', playtime: 120 },
        }));
        saves.list.mockResolvedValue({
            data: {
                saves: [{
                    id: 'cloud-ahead',
                    name: 'Cloud Save',
                    timestamp: '2099-01-01T00:00:00Z',
                    timestamp_ms: Date.now() + 60 * 60 * 1000,
                    level: 3, map_name: 'M', room_title: 'R',
                }],
            },
        });

        render(<MemoryRouter><MainMenuPage /></MemoryRouter>);

        await waitFor(() => screen.getByText(/Continue/i));
        fireEvent.click(screen.getByText(/Continue/i));

        await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/game'));
        expect(saves.load).not.toHaveBeenCalled();

        localStorage.removeItem('hov_local_autosave');
    });

    it('falls back to the newest cloud save when the local blob is stale', async () => {
        // A blob older than the freshness window belongs to a server session
        // that is almost certainly gone, so loading the cloud save is correct.
        localStorage.setItem('hov_local_autosave', JSON.stringify({
            timestamp: new Date(Date.now() - 48 * 60 * 60 * 1000).toISOString(),
            player: { level: 9, map_name: 'Dark Grotto', room_title: 'Entrance', playtime: 120 },
        }));
        saves.list.mockResolvedValue({
            data: { saves: [{ id: 'cloud-1', name: 'Cloud Save', timestamp: '2023-01-01T00:00:00Z', level: 3, map_name: 'M', room_title: 'R' }] },
        });
        saves.load.mockResolvedValue({ success: true });

        render(<MemoryRouter><MainMenuPage /></MemoryRouter>);

        await waitFor(() => screen.getByText(/Continue/i));
        fireEvent.click(screen.getByText(/Continue/i));

        await waitFor(() => expect(saves.load).toHaveBeenCalledWith('cloud-1'));

        localStorage.removeItem('hov_local_autosave');
    });

    it('regression guard: a more-recent local autosave keeps Continue resuming the live session instead of loading an older cloud save', async () => {
        // This is the progress-loss bug from issue #487: if the local blob were
        // dropped from the Continue decision (e.g. by only ever comparing cloud
        // saves), Continue would silently re-target the newest CLOUD save here
        // and overwrite the live in-memory session with an older one.
        localStorage.setItem('hov_local_autosave', JSON.stringify({
            timestamp: new Date(Date.now() - 60_000).toISOString(),
            player: { level: 9, map_name: 'Dark Grotto', room_title: 'Entrance', playtime: 120 },
        }));
        saves.list.mockResolvedValue({
            data: { saves: [{ id: 'cloud-1', name: 'Cloud Save', timestamp: '2020-01-01T00:00:00Z', level: 3, map_name: 'M', room_title: 'R' }] },
        });

        render(<MemoryRouter><MainMenuPage /></MemoryRouter>);

        await waitFor(() => screen.getByText(/Continue/i));
        fireEvent.click(screen.getByText(/Continue/i));

        // Local autosave is the most recent -> Continue just navigates, no saves.load call.
        await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/game'));
        expect(saves.load).not.toHaveBeenCalled();

        localStorage.removeItem('hov_local_autosave');
    });

    it('does not show a valid local autosave as a selectable row in the Load Game list', async () => {
        // The local blob is real and more recent than the cloud save, so it
        // drives the Continue decision (see the regression-guard test above) —
        // but it must never appear as a row a player can click in the modal.
        localStorage.setItem('hov_local_autosave', JSON.stringify({
            timestamp: new Date(Date.now() - 60_000).toISOString(),
            player: { level: 9, map_name: 'Dark Grotto', room_title: 'Entrance' },
        }));
        saves.list.mockResolvedValue({
            data: { saves: [{ id: 'cloud-1', name: 'Cloud Save', timestamp: '2020-01-01T00:00:00Z', level: 3, map_name: 'M', room_title: 'R' }] },
        });

        render(<MemoryRouter><MainMenuPage /></MemoryRouter>);
        await waitFor(() => screen.getByText(/Load Game/i));
        fireEvent.click(screen.getByText(/Load Game/i));

        await waitFor(() => screen.getByText(/Cloud Save/i));
        expect(screen.queryByText(/Local Autosave/i)).not.toBeInTheDocument();

        localStorage.removeItem('hov_local_autosave');
    });

    it('loads the newest cloud save on Continue when there is no local autosave', async () => {
        // Companion to the regression guard above: with no local blob at all,
        // Continue must fall back to the ordinary cloud-load path.
        const mockSaves = [
            { id: 'old', name: 'Old Save', timestamp: '2020-01-01T00:00:00Z', level: 1, map_name: 'Map 1', room_title: 'Room 1' },
            { id: 'new', name: 'New Save', timestamp: '2023-01-02T00:00:00Z', level: 2, map_name: 'Map 2', room_title: 'Room 2' },
        ];
        saves.list.mockResolvedValue({ data: { saves: mockSaves } });
        saves.load.mockResolvedValue({ success: true });

        render(<MemoryRouter><MainMenuPage /></MemoryRouter>);

        await waitFor(() => screen.getByText(/Continue/i));
        fireEvent.click(screen.getByText(/Continue/i));

        expect(saves.load).toHaveBeenCalledWith('new');
        await waitFor(() => {
            expect(mockNavigate).toHaveBeenCalledWith('/game');
        });
    });

    it('defaults a local autosave\'s map/room fields without crashing when absent', async () => {
        localStorage.setItem('hov_local_autosave', JSON.stringify({
            timestamp: new Date(Date.now() - 60_000).toISOString(),
            player: { level: 9 },
        }));
        saves.list.mockResolvedValue({ data: { saves: [] } });

        render(<MemoryRouter><MainMenuPage /></MemoryRouter>);
        await waitFor(() => {
            expect(screen.getByText(/Continue/i)).toBeInTheDocument();
        });
        localStorage.removeItem('hov_local_autosave');
    });

    it('defaults the save list to empty when the response has no data.saves', async () => {
        saves.list.mockResolvedValue({});
        render(<MemoryRouter><MainMenuPage /></MemoryRouter>);

        await waitFor(() => {
            expect(screen.queryByText(/Continue/i)).not.toBeInTheDocument();
        });
    });

    it('does not offer a corrupted local autosave as a loadable save', async () => {
        // Asserts behaviour rather than a log line: the invalid blob must not
        // become a selectable row, and must be discarded so it cannot fail
        // again on every mount.
        const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
        localStorage.setItem('hov_local_autosave', 'not valid json');
        saves.list.mockResolvedValue({ data: { saves: [] } });

        render(<MemoryRouter><MainMenuPage /></MemoryRouter>);

        await waitFor(() => {
            expect(screen.queryByText(/Continue/i)).not.toBeInTheDocument();
        });
        expect(screen.queryByText(/Local Autosave/i)).not.toBeInTheDocument();
        expect(localStorage.getItem('hov_local_autosave')).toBeNull();
        warnSpy.mockRestore();
    });

    it('surfaces a valid local autosave as a resumable Continue, not as a loadable save row', async () => {
        localStorage.setItem('hov_local_autosave', JSON.stringify({
            timestamp: new Date(Date.now() - 60_000).toISOString(),
            player: { level: 12, map_name: 'dark-grotto', room_title: 'Wall Depression' },
        }));
        saves.list.mockResolvedValue({ data: { saves: [] } });

        render(<MemoryRouter><MainMenuPage /></MemoryRouter>);

        // Honest labelling: this is a session resume, not a save load.
        await waitFor(() => {
            expect(screen.getByText(/Continue \(Resume Session\)/i)).toBeInTheDocument();
        });
        // No cloud saves and the local entry is never a row, so there is
        // nothing for a Load Game modal to show.
        expect(screen.queryByText(/Load Game/i)).not.toBeInTheDocument();
        expect(localStorage.getItem('hov_local_autosave')).not.toBeNull();
        localStorage.removeItem('hov_local_autosave');
    });

    it('does not offer a local autosave whose player payload is hostile', async () => {
        // A blob that parses as JSON but carries no usable player must be
        // rejected just as firmly as malformed JSON.
        const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {});
        localStorage.setItem('hov_local_autosave', JSON.stringify({
            timestamp: new Date(Date.now() - 60_000).toISOString(),
            player: { level: 'not-a-number' },
        }));
        saves.list.mockResolvedValue({ data: { saves: [] } });

        render(<MemoryRouter><MainMenuPage /></MemoryRouter>);

        await waitFor(() => {
            expect(screen.queryByText(/Local Autosave/i)).not.toBeInTheDocument();
        });
        expect(localStorage.getItem('hov_local_autosave')).toBeNull();
        warnSpy.mockRestore();
    });

    it('handles a failed initial saves.list call gracefully', async () => {
        const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
        saves.list.mockRejectedValue(new Error('offline'));

        render(<MemoryRouter><MainMenuPage /></MemoryRouter>);

        await waitFor(() => {
            expect(errorSpy).toHaveBeenCalledWith('Failed to initialize menu saves', expect.any(Error));
        });
        expect(screen.queryByText(/Continue/i)).not.toBeInTheDocument();
        errorSpy.mockRestore();
    });

    it('plays an error SFX and does not navigate when New Game fails', async () => {
        saves.list.mockResolvedValue({ data: { saves: [] } });
        saves.newGame.mockRejectedValue(new Error('server down'));

        render(<MemoryRouter><MainMenuPage /></MemoryRouter>);
        fireEvent.click(screen.getByText(/New Game/i));

        await waitFor(() => {
            expect(mockAudioContext.playSFX).toHaveBeenCalledWith('error');
        });
        expect(mockNavigate).not.toHaveBeenCalledWith('/game');
    });

    it('navigates immediately for a local-autosave Continue without calling saves.load', async () => {
        localStorage.setItem('hov_local_autosave', JSON.stringify({
            timestamp: new Date(Date.now() - 60_000).toISOString(),
            player: { level: 1, map_name: 'M', room_title: 'R' },
        }));
        saves.list.mockResolvedValue({ data: { saves: [] } });

        render(<MemoryRouter><MainMenuPage /></MemoryRouter>);
        await waitFor(() => screen.getByText(/Continue/i));
        fireEvent.click(screen.getByText(/Continue/i));

        expect(saves.load).not.toHaveBeenCalled();
        await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith('/game'));
        localStorage.removeItem('hov_local_autosave');
    });

    it('does nothing when Continue is clicked with no recent save', () => {
        saves.list.mockResolvedValue({ data: { saves: [] } });
        render(<MemoryRouter><MainMenuPage /></MemoryRouter>);
        expect(screen.queryByText(/Continue/i)).not.toBeInTheDocument();
    });

    it('plays an error SFX when Continue fails to load a cloud save', async () => {
        const mockSaves = [{ id: 'a', name: 'A', timestamp: '2023-01-01', level: 1, map_name: 'M', room_title: 'R' }];
        saves.list.mockResolvedValue({ data: { saves: mockSaves } });
        saves.load.mockRejectedValue(new Error('load failed'));

        render(<MemoryRouter><MainMenuPage /></MemoryRouter>);
        await waitFor(() => screen.getByText(/Continue/i));
        fireEvent.click(screen.getByText(/Continue/i));

        await waitFor(() => {
            expect(mockAudioContext.playSFX).toHaveBeenCalledWith('error');
        });
        expect(mockNavigate).not.toHaveBeenCalledWith('/game');
    });

    it('logs an error when re-listing saves for the load modal fails', async () => {
        const errorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
        const mockSaves = [{ id: 'a', name: 'A', timestamp: '2023-01-01', level: 1, map_name: 'M', room_title: 'R' }];
        saves.list.mockResolvedValueOnce({ data: { saves: mockSaves } });
        saves.list.mockRejectedValueOnce(new Error('list failed'));

        render(<MemoryRouter><MainMenuPage /></MemoryRouter>);
        await waitFor(() => screen.getByText(/Load Game/i));
        fireEvent.click(screen.getByText(/Load Game/i));

        await waitFor(() => {
            expect(errorSpy).toHaveBeenCalledWith('Failed to list saves', expect.any(Error));
        });
        errorSpy.mockRestore();
    });

    it('confirms a save selection from the load modal via the Enter key', async () => {
        const mockSaves = [{ id: 'cloud-1', name: 'Cloud Save', timestamp: '2023-01-01', level: 1, map_name: 'M', room_title: 'R' }];
        saves.list.mockResolvedValue({ data: { saves: mockSaves } });
        saves.load.mockResolvedValue({});

        render(<MemoryRouter><MainMenuPage /></MemoryRouter>);
        await waitFor(() => screen.getByText(/Load Game/i));
        fireEvent.click(screen.getByText(/Load Game/i));
        await waitFor(() => screen.getByText(/Cloud Save/i));

        fireEvent.keyDown(screen.getByText(/Cloud Save/i).closest('[role="button"]'), { key: 'Enter' });
        expect(saves.load).toHaveBeenCalledWith('cloud-1');
    });

    it('plays an error SFX when confirming a load fails', async () => {
        const mockSaves = [{ id: 'cloud-1', name: 'Cloud Save', timestamp: '2023-01-01', level: 1, map_name: 'M', room_title: 'R' }];
        saves.list.mockResolvedValue({ data: { saves: mockSaves } });
        saves.load.mockRejectedValue(new Error('nope'));

        render(<MemoryRouter><MainMenuPage /></MemoryRouter>);
        await waitFor(() => screen.getByText(/Load Game/i));
        fireEvent.click(screen.getByText(/Load Game/i));
        await waitFor(() => screen.getByText(/Cloud Save/i));
        fireEvent.click(screen.getByText(/Cloud Save/i));

        await waitFor(() => {
            expect(mockAudioContext.playSFX).toHaveBeenCalledWith('error');
        });
    });

    it('cancels save deletion when the confirm dialog is dismissed', async () => {
        const mockSaves = [{ id: 'cloud-1', name: 'Cloud Save', timestamp: '2023-01-01', level: 1, map_name: 'M', room_title: 'R' }];
        saves.list.mockResolvedValue({ data: { saves: mockSaves } });
        vi.spyOn(window, 'confirm').mockReturnValue(false);

        render(<MemoryRouter><MainMenuPage /></MemoryRouter>);
        await waitFor(() => screen.getByText(/Load Game/i));
        fireEvent.click(screen.getByText(/Load Game/i));
        await waitFor(() => screen.getByText(/Cloud Save/i));
        fireEvent.click(screen.getByText(/Delete/i));

        expect(saves.delete).not.toHaveBeenCalled();
        expect(screen.getByText(/Cloud Save/i)).toBeInTheDocument();
    });

    it('plays an error SFX when deleting a cloud save fails', async () => {
        const mockSaves = [{ id: 'cloud-1', name: 'Cloud Save', timestamp: '2023-01-01', level: 1, map_name: 'M', room_title: 'R' }];
        saves.list.mockResolvedValue({ data: { saves: mockSaves } });
        saves.delete.mockRejectedValue(new Error('nope'));
        vi.spyOn(window, 'confirm').mockReturnValue(true);

        render(<MemoryRouter><MainMenuPage /></MemoryRouter>);
        await waitFor(() => screen.getByText(/Load Game/i));
        fireEvent.click(screen.getByText(/Load Game/i));
        await waitFor(() => screen.getByText(/Cloud Save/i));
        fireEvent.click(screen.getByText(/Delete/i));

        await waitFor(() => {
            expect(mockAudioContext.playSFX).toHaveBeenCalledWith('error');
        });
    });

    it('navigates to the landing page via the back-to-home link', () => {
        saves.list.mockResolvedValue({ data: { saves: [] } });
        render(<MemoryRouter><MainMenuPage /></MemoryRouter>);
        fireEvent.click(screen.getByText(/Back to home/i));
        expect(mockNavigate).toHaveBeenCalledWith('/landing');
    });

    it('handles hover on the back-to-home button and the Nexus Fidei link', async () => {
        saves.list.mockResolvedValue({ data: { saves: [] } });
        render(<MemoryRouter><MainMenuPage /></MemoryRouter>);

        const backBtn = screen.getByText(/Back to home/i);
        fireEvent.mouseEnter(backBtn);
        fireEvent.mouseLeave(backBtn);

        await waitFor(() => screen.getByText(/Nexus Fidei/i));
        const nexusLink = screen.getByText(/Nexus Fidei/i);
        fireEvent.mouseEnter(nexusLink);
        fireEvent.mouseLeave(nexusLink);
    });

    it('handles hover on a save-list row', async () => {
        const mockSaves = [{ id: 'cloud-1', name: 'Cloud Save', timestamp: '2023-01-01', level: 1, map_name: 'M', room_title: 'R' }];
        saves.list.mockResolvedValue({ data: { saves: mockSaves } });

        render(<MemoryRouter><MainMenuPage /></MemoryRouter>);
        await waitFor(() => screen.getByText(/Load Game/i));
        fireEvent.click(screen.getByText(/Load Game/i));
        await waitFor(() => screen.getByText(/Cloud Save/i));

        const row = screen.getByText(/Cloud Save/i).closest('[style*="cursor: pointer"]');
        fireEvent.mouseEnter(row);
        fireEvent.mouseLeave(row);
    });

    it('marks a save with the Autosave badge when is_autosave is set', async () => {
        const mockSaves = [{ id: 'a', name: 'A', timestamp: '2023-01-01', level: 1, map_name: 'M', room_title: 'R', is_autosave: true }];
        saves.list.mockResolvedValue({ data: { saves: mockSaves } });

        render(<MemoryRouter><MainMenuPage /></MemoryRouter>);
        await waitFor(() => screen.getByText(/Load Game/i));
        fireEvent.click(screen.getByText(/Load Game/i));

        await waitFor(() => {
            expect(screen.getByText('(Autosave)')).toBeInTheDocument();
        });
    });

    it('shows a loading overlay while an action is in flight', async () => {
        let resolveNewGame;
        saves.list.mockResolvedValue({ data: { saves: [] } });
        saves.newGame.mockReturnValue(new Promise((resolve) => { resolveNewGame = resolve; }));

        render(<MemoryRouter><MainMenuPage /></MemoryRouter>);
        fireEvent.click(screen.getByText(/New Game/i));

        expect(screen.getByText('Loading...')).toBeInTheDocument();
        await waitFor(() => resolveNewGame({}));
    });
});

describe('MainMenuPage embers canvas effect', () => {
    let rafCallbacks;

    beforeEach(() => {
        vi.clearAllMocks();
        saves.list.mockResolvedValue({ data: { saves: [] } });

        HTMLCanvasElement.prototype.getContext = vi.fn(() => ({
            fillStyle: '',
            clearRect: vi.fn(),
            beginPath: vi.fn(),
            arc: vi.fn(),
            fill: vi.fn(),
            scale: vi.fn(),
        }));

        rafCallbacks = [];
        global.requestAnimationFrame = vi.fn((cb) => {
            rafCallbacks.push(cb);
            return rafCallbacks.length;
        });
        global.cancelAnimationFrame = vi.fn();
    });

    const renderMenu = () => render(<MemoryRouter><MainMenuPage /></MemoryRouter>);

    it('starts and ticks the ember particle animation', () => {
        renderMenu();
        expect(global.requestAnimationFrame).toHaveBeenCalled();
        expect(() => rafCallbacks[0]()).not.toThrow();
    });

    it('resizes the embers canvas on window resize', () => {
        renderMenu();
        expect(() => fireEvent(window, new Event('resize'))).not.toThrow();
    });

    it('stops the animation and removes the resize listener on unmount', () => {
        const { unmount } = renderMenu();
        unmount();
        expect(global.cancelAnimationFrame).toHaveBeenCalled();
    });

    it('does nothing when the canvas has no 2D context available', () => {
        HTMLCanvasElement.prototype.getContext = vi.fn(() => null);
        expect(() => renderMenu()).not.toThrow();
    });
});
