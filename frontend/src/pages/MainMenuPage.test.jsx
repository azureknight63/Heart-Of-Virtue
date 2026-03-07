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
    });
});
