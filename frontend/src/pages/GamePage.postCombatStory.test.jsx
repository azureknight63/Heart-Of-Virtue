/**
 * Issue #683: a won fight's post-combat story must reach the player even when
 * some other reader of `GET /combat/status` consumed the copy it used to ride.
 *
 * `AfterDefeatingKingSlime` ("The churning stilled...") needs no input, so it
 * is never in `/world/events/pending`; the server now hands it over in the
 * collect-loot response, which every browser victory path calls. This drives
 * that through the REAL useCombat, useCombatCoordinator and useEventManager —
 * only the HTTP client underneath is faked — so the post-kill status payload
 * arrives with its `events_triggered` already stolen, and the scene can only
 * come from collect-loot.
 */
import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import GamePage from './GamePage';
import apiClient from '../api/client';
import { capabilitiesDisabled } from '../test/mockHelpers';
import { makeCombatant, makeEnemy } from '../test/payloads';
import { useExploration, useExits, useAutosave } from '../hooks/useApi';
import { useAudio } from '../context/AudioContext';

vi.mock('../api/client', () => ({
    default: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}));

vi.mock('../hooks/useApi', async () => {
    const actual = await vi.importActual('../hooks/useApi');
    return {
        ...actual,
        useExploration: vi.fn(),
        useExits: vi.fn(),
        useAutosave: vi.fn(),
    };
});

vi.mock('../context/CapabilitiesContext', () => ({
    useCapabilities: vi.fn(() => capabilitiesDisabled),
}));

vi.mock('../context/AudioContext', () => ({
    useAudio: vi.fn(),
}));

vi.mock('../context/ToastContext', () => ({
    useToast: () => ({ showError: vi.fn(), showSuccess: vi.fn(), showInfo: vi.fn() }),
}));

// The event text is the assertion; the real dialog's typewriter is not.
vi.mock('../components/EventDialog', () => ({
    default: ({ event, onSubmitInput }) => (
        <div data-testid="event-dialog">
            <p>{event.output_text}</p>
            {event.input_options?.map((opt) => (
                <button key={opt.value} onClick={() => onSubmitInput(event.event_id, opt.value)}>
                    {opt.label}
                </button>
            ))}
        </div>
    ),
}));

const SCENE = {
    name: 'AfterDefeatingKingSlime',
    needs_input: false,
    output_text: 'The churning stilled.',
};

const VICTORY = {
    id: 'king-slime-win',
    status: 'victory',
    message: 'Victory!',
    exp_gained: {},
    items_dropped: [],
    level_ups: [],
    attribute_points_available: 0,
    attributes: {
        strength_base: 10, finesse_base: 10, speed_base: 10,
        endurance_base: 10, charisma_base: 10, intelligence_base: 10,
    },
};

const FIGHTING = {
    success: true,
    combat_active: true,
    battle_state: {
        combatants: [makeCombatant({ id: 'player_1', name: 'Jean' }), makeEnemy({ id: 'enemy_1', name: 'King Slime' })],
        player: makeCombatant({ name: 'Jean' }),
        enemies: [makeEnemy({ id: 'enemy_1', name: 'King Slime' })],
        input_type: 'move_selection',
        awaiting_input: true,
    },
    log: [],
};

// What the browser's own post-kill status read gets once a stray reader (a
// second tab, devtools, a harness) has already consumed the scene.
const WON_AND_ROBBED = {
    success: true,
    combat_active: false,
    battle_state: { status: 'ended', awaiting_input: false, input_type: null, enemies: [] },
    end_state: VICTORY,
    events_triggered: [],
    log: [],
};

const EXPLORING = { success: true, combat_active: false, battle_state: null, log: [] };

/**
 * Answer the client's HTTP calls. The fight is on until `fight.won` is set
 * (the test sets it once the encounter dialog is answered, standing in for
 * the killing blow); from then on status serves the robbed victory, and after
 * collect-loot the world.
 */
/**
 * Delayed `/world` responses still in flight. Closing Victory refetches the
 * room, so a test can pass while that 50ms response is pending; left alone it
 * lands after the environment is torn down and fails the run with an
 * unhandled "window is not defined". afterEach drains them.
 */
const worldInFlight = new Set();

function routeTheApi({ collectLootEvents, victoryStatusEvents = [], pendingAfterWin = [] }) {
    const fight = { won: false, collected: false };
    apiClient.get.mockImplementation((url) => {
        if (url === '/combat/status') {
            if (fight.collected) return Promise.resolve({ data: EXPLORING });
            if (!fight.won) return Promise.resolve({ data: FIGHTING });
            return Promise.resolve({ data: { ...WON_AND_ROBBED, events_triggered: victoryStatusEvents } });
        }
        if (url === '/full-state') {
            return Promise.resolve({
                data: {
                    success: true,
                    status: { name: 'Jean', hp: 100, max_hp: 100, fatigue: 0, max_fatigue: 150 },
                    stats: { strength: 10, finesse: 10, speed: 10, endurance: 10 },
                    skills: { offensive: [], defensive: [] },
                    inventory: { items: [] },
                },
            });
        }
        if (url === '/world') {
            // A real round trip: resolving instantly lets React batch the
            // loading flag's true -> false into one render, which hides the
            // loading-keyed effect the combat-end refetch triggers.
            const response = new Promise((resolve) => setTimeout(() => resolve({
                data: { success: true, room: { name: 'Grondelith Arena', description: 'Still water.', x: 2, y: 6, exits: [] } },
            }), 50));
            worldInFlight.add(response);
            response.finally(() => worldInFlight.delete(response));
            return response;
        }
        if (url === '/world/events/pending') {
            const events = fight.won ? pendingAfterWin : [];
            return Promise.resolve({ data: { success: true, events } });
        }
        // /world/commands, /world/explored, ...
        return Promise.resolve({ data: { success: true, events: [], commands: [], explored_tiles: [] } });
    });
    apiClient.post.mockImplementation((url) => {
        if (url === '/combat/collect-loot') {
            fight.collected = true;
            return Promise.resolve({
                data: { success: true, collected: [], skipped: [], events_triggered: collectLootEvents },
            });
        }
        return Promise.resolve({ data: { success: true, tiles: [] } });
    });
    return fight;
}

describe('post-combat story rides collect-loot (issue #683)', () => {
    beforeEach(() => {
        vi.clearAllMocks();
        useExploration.mockReturnValue({ exploredTiles: new Map(), setExploredTiles: vi.fn(), loading: false, refetch: vi.fn() });
        useExits.mockReturnValue({ exits: [], loading: false, refetch: vi.fn() });
        useAutosave.mockReturnValue({ triggerTick: vi.fn() });
        useAudio.mockReturnValue({ playSFX: vi.fn(), playBGM: vi.fn(), stopBGM: vi.fn() });
    });

    afterEach(async () => {
        // A refetch can start while the last one drains, so loop until quiet.
        while (worldInFlight.size) {
            await act(async () => { await Promise.all([...worldInFlight]); });
        }
    });

    it('shows the victory scene collect-loot returns after a stray status read stole it', async () => {
        const fight = routeTheApi({ collectLootEvents: [SCENE] });

        render(
            <MemoryRouter>
                <GamePage />
            </MemoryRouter>
        );

        // The poll moves the fight to its (robbed) victory; close the dialog.
        fireEvent.click(await screen.findByText('FIGHT FOR YOUR LIFE', {}, { timeout: 8000 }));
        fight.won = true;

        // VictoryDialog waits VICTORY_DIALOG_DELAY_MS (5s) after the fight ends.
        fireEvent.click(await screen.findByText('CLOSE', {}, { timeout: 12000 }));

        expect(apiClient.post).toHaveBeenCalledWith('/combat/collect-loot', { item_names: [] });
        expect(await screen.findByText(SCENE.output_text, {}, { timeout: 8000 })).toBeInTheDocument();
    }, 30000);

    it('leaves the status echo of a held scene to collect-loot, so it is not shown under the Victory dialog', async () => {
        // The level-up path: handleAllocatePoints polls status while the
        // Victory dialog is open, and status echoes the held scene tagged
        // `post_combat`. Queued from there it would play behind the dialog and
        // then again when collect-loot delivers it.
        const fight = routeTheApi({
            collectLootEvents: [SCENE],
            victoryStatusEvents: [{ ...SCENE, post_combat: true }],
        });

        render(
            <MemoryRouter>
                <GamePage />
            </MemoryRouter>
        );

        fireEvent.click(await screen.findByText('FIGHT FOR YOUR LIFE', {}, { timeout: 8000 }));
        fight.won = true;

        const close = await screen.findByText('CLOSE', {}, { timeout: 12000 });
        expect(screen.queryByText(SCENE.output_text)).toBeNull();

        fireEvent.click(close);
        expect(await screen.findAllByText(SCENE.output_text, {}, { timeout: 8000 })).toHaveLength(1);
    }, 30000);
    it('keeps a pending story event from surfacing under the Victory dialog (scrub of #694 x #683)', async () => {
        // #694 refetches the room as soon as the fight ends. That refetch
        // toggles worldLoading, and the loading-keyed effect then polls
        // /world/events/pending -- while Victory is still on screen. A
        // needs-input post-combat event (the memory flash) must wait for the
        // dialog to close, behind collect-loot's scene.
        const FLASH = {
            event_id: 'flash-1',
            name: 'Ch02KingSlimeMemoryFlash',
            needs_input: true,
            input_type: 'choice',
            input_options: [{ label: 'Continue', value: 'continue' }],
            description: 'A MEMORY STIRS',
            output_text: 'A MEMORY STIRS',
        };
        const fight = routeTheApi({ collectLootEvents: [SCENE], pendingAfterWin: [FLASH] });

        render(
            <MemoryRouter>
                <GamePage />
            </MemoryRouter>
        );

        fireEvent.click(await screen.findByText('FIGHT FOR YOUR LIFE', {}, { timeout: 8000 }));
        const atWin = apiClient.get.mock.calls.length;
        fight.won = true;

        await screen.findByText('CLOSE', {}, { timeout: 12000 });
        // Give the combat-end refetch and any loading-keyed poll time to land.
        await new Promise((resolve) => setTimeout(resolve, 1500));
        // Non-vacuity: the combat-end room refetch really did run while the
        // dialog was up (else this test proves nothing about it).
        const afterWin = apiClient.get.mock.calls.slice(atWin).map(([u]) => u);
        expect(afterWin).toContain('/world');
        expect(screen.queryByText(FLASH.output_text)).toBeNull();

        // And once Victory closes, collect-loot's scene plays first; the
        // flash (which chains after it in the story) must not jump the queue.
        fireEvent.click(screen.getByText('CLOSE'));
        await screen.findByText(SCENE.output_text, {}, { timeout: 8000 });
        expect(screen.queryByText(FLASH.output_text)).toBeNull();
    }, 30000);
});
