import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
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

// Mock useAudio
vi.mock('../context/AudioContext', () => ({
    useAudio: () => ({
        playBGM: vi.fn(),
        playSFX: vi.fn(),
    }),
    AudioProvider: ({ children }) => <div>{children}</div>,
}));

// Mock saves API
vi.mock('../api/endpoints', () => ({
    saves: {
        list: vi.fn(),
        load: vi.fn(),
        delete: vi.fn(),
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

    it('does not render Continue button when no saves exist', async () => {
        saves.list.mockResolvedValue({ data: { saves: [] } });

        render(
            <MemoryRouter>
                <MainMenuPage />
            </MemoryRouter>
        );

        await waitFor(() => {
            expect(screen.queryByText(/Continue/i)).toBeNull();
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
        expect(mockNavigate).toHaveBeenCalledWith('/game');
    });

    it('opens load modal on Load Game click', async () => {
        saves.list.mockResolvedValue({ data: { saves: [] } });

        render(
            <MemoryRouter>
                <MainMenuPage />
            </MemoryRouter>
        );

        const menuButtons = screen.getAllByText(/Load Game/i);
        fireEvent.click(menuButtons[0]);

        await waitFor(() => {
            expect(screen.getByText(/No saves found/i)).toBeDefined();
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
        const newSaveSlot = screen.getByText(/New Save/i).closest('.save-slot');
        const deleteNewButton = within(newSaveSlot).getByText(/Delete/i);

        fireEvent.click(deleteNewButton);
        expect(saves.delete).toHaveBeenCalledWith('new');

        await waitFor(() => {
            expect(screen.queryByText(/New Save/i)).toBeNull();
        });
    });
});
