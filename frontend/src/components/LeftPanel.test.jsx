import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import LeftPanel from './LeftPanel';
import React from 'react';

// Mock child components
vi.mock('./PartyPanel', () => ({ default: ({ onClose }) => <div data-testid="party-panel"><button onClick={onClose}>Close Party</button></div> }));
vi.mock('./InventoryDialog', () => ({ default: ({ onClose }) => <div data-testid="inventory-dialog"><button onClick={onClose}>Close Inv</button></div> }));
vi.mock('./AccountDialog', () => ({ default: ({ onClose }) => <div data-testid="account-dialog"><button onClick={onClose}>Close Acc</button></div> }));
vi.mock('./AudioControlDialog', () => ({ default: ({ onClose }) => <div data-testid="audio-dialog"><button onClick={onClose}>Close Aud</button></div> }));
vi.mock('./StatsPanel', () => ({ default: ({ onClose }) => <div data-testid="stats-panel"><button onClick={onClose}>Close Stats</button></div> }));
vi.mock('./SkillsPanel', () => ({ default: ({ onClose }) => <div data-testid="skills-panel"><button onClick={onClose}>Close Skills</button></div> }));
vi.mock('./RoomContents', () => ({ default: ({ onInteract }) => <div data-testid="room-contents"><button onClick={() => onInteract()}>Interact Button</button></div> }));
vi.mock('./ActionsPanel', () => ({ default: ({ onClose }) => <div data-testid="actions-panel"><button onClick={onClose}>Close Actions</button></div> }));
vi.mock('./InteractPanel', () => ({ default: ({ onClose }) => <div data-testid="interact-panel"><button onClick={onClose}>Close Interact</button></div> }));
vi.mock('./HeroPanel', () => ({
    default: (props) => (
        <div data-testid="hero-panel">
            <button onClick={props.onStatusClick}>Status Btn</button>
            <button onClick={props.onInventoryClick}>Inventory Btn</button>
            <button onClick={props.onSkillsClick}>Skills Btn</button>
            <button onClick={props.onAttributeClick}>Attributes Btn</button>
            <button onClick={props.onActionsClick}>Actions Btn</button>
            <button onClick={props.onInteractClick}>Interact Btn</button>
        </div>
    )
}));
vi.mock('./CombatLog', () => ({ default: ({ log }) => <div data-testid="combat-log">{log.map((e, i) => <div key={i}>{e.message}</div>)}</div> }));

// Mock useAudio
vi.mock('../context/AudioContext', () => ({
    useAudio: () => ({
        playSFX: vi.fn(),
        playBGM: vi.fn(),
    }),
}));

const mockPlayer = {
    name: 'Jean',
    level: 1,
    hp: 100,
    max_hp: 100,
    inventory: []
};

const mockLocation = {
    name: 'Forest',
    description: 'Green trees.'
};

describe('LeftPanel', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    it('renders basic info in exploration mode', () => {
        render(<LeftPanel player={mockPlayer} location={mockLocation} mode="exploration" />);
        expect(screen.getByText(/Heart of Virtue - Exploration/i)).toBeDefined();
        expect(screen.getByTestId('hero-panel')).toBeDefined();
        expect(screen.getByTestId('room-contents')).toBeDefined();
    });

    it('toggles different panels', async () => {
        render(<LeftPanel player={mockPlayer} location={mockLocation} mode="exploration" />);

        // Status
        fireEvent.click(screen.getByText('Status Btn'));
        expect(screen.getByTestId('party-panel')).toBeDefined();

        // Inventory
        fireEvent.click(screen.getByText('Inventory Btn'));
        expect(screen.getByTestId('inventory-dialog')).toBeDefined();

        // Skills
        fireEvent.click(screen.getByText('Skills Btn'));
        expect(screen.getByTestId('skills-panel')).toBeDefined();

        // Attributes
        fireEvent.click(screen.getByText('Attributes Btn'));
        expect(screen.getByTestId('stats-panel')).toBeDefined();

        // Actions
        fireEvent.click(screen.getByText('Actions Btn'));
        expect(screen.getByTestId('actions-panel')).toBeDefined();

        // Interact
        fireEvent.click(screen.getByText('Interact Btn'));
        expect(screen.getByTestId('interact-panel')).toBeDefined();
    });

    it('opens audio and account dialogs from header', () => {
        render(<LeftPanel player={mockPlayer} location={mockLocation} mode="exploration" />);

        fireEvent.click(screen.getByTitle(/Audio Settings/i));
        expect(screen.getByTestId('audio-dialog')).toBeDefined();
        fireEvent.click(screen.getByText('Close Aud'));
        expect(screen.queryByTestId('audio-dialog')).toBeNull();

        fireEvent.click(screen.getByText('Account'));
        expect(screen.getByTestId('account-dialog')).toBeDefined();
        fireEvent.click(screen.getByText('Close Acc'));
        expect(screen.queryByTestId('account-dialog')).toBeNull();
    });

    it('closes panels when their close buttons are clicked', () => {
        render(<LeftPanel player={mockPlayer} location={mockLocation} mode="exploration" />);

        fireEvent.click(screen.getByText('Status Btn'));
        expect(screen.getByTestId('party-panel')).toBeDefined();
        fireEvent.click(screen.getByText('Close Party'));
        expect(screen.queryByTestId('party-panel')).toBeNull();

        fireEvent.click(screen.getByText('Inventory Btn'));
        expect(screen.getByTestId('inventory-dialog')).toBeDefined();
        fireEvent.click(screen.getByText('Close Inv'));
        expect(screen.queryByTestId('inventory-dialog')).toBeNull();
    });

    it('handles combat mode and log processing', async () => {
        const combat = {
            log: [
                { message: 'Jean attacks Slime', round: 1, type: 'action' },
                { message: 'Jean hit Slime for 10 damage', round: 1, type: 'result' }
            ],
            awaiting_input: true,
            input_type: 'move_selection',
            beat_states: [{ enemies: [] }]
        };

        render(<LeftPanel player={mockPlayer} location={mockLocation} mode="combat" combat={combat} />);

        expect(screen.getByText(/Heart of Virtue - Combat/i)).toBeDefined();

        await waitFor(() => {
            expect(screen.getByText('Jean attacks Slime')).toBeDefined();
        }, { timeout: 3000 });

        await waitFor(() => {
            expect(screen.getByText('Jean hit Slime for 10 damage')).toBeDefined();
        }, { timeout: 3000 });
    });
});
