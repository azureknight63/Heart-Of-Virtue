import { render, screen, fireEvent, within } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';

import AdminAnalyticsPage, { SECTION_IDS } from './AdminAnalyticsPage';
import useAdminAnalytics from '../hooks/useAdminAnalytics';

vi.mock('../hooks/useAdminAnalytics', async (importOriginal) => ({ ...(await importOriginal()), default: vi.fn() }));

// Field names are the ones analytics_report.build_report emits
// (tests/test_analytics_report.py::TestAdminPageContract pins them against real SQL).
const REPORT = {
    window_days: 30,
    scope: {
        players: 'rolling', daily: 'window', retention: 'all_time', progress: 'all_time',
        combat: 'window', sessions: 'window', npc_chat: 'window',
    },
    players: {
        total_accounts: 42,
        new_accounts: { '1d': 1, '7d': 6, '30d': 20 },
        started_playing: 35,
        active: { dau: 3, wau: 11, mau: 25 },
    },
    daily: [
        { day: '2026-09-25', signups: 2, active: 4, chat_turns: 10 },
        { day: '2026-09-26', signups: 5, active: 9, chat_turns: 30 },
    ],
    retention: [
        { day: 1, eligible: 20, returned: 10 },
        { day: 7, eligible: 10, returned: 3 },
        { day: 30, eligible: 0, returned: 0 },
    ],
    progress: {
        maps: [{ map: 'dark-grotto', players: 30 }, { map: 'grondia', players: 12 }],
        flags: [{ flag: 'met_gorran', players: 18 }],
        levels: [{ level: 1, players: 10 }, { level: 3, players: 5 }],
        stalled: [
            { map: 'dark-grotto', room: 'Wall Depression', x: 14, y: 5, players: 7 },
            { map: 'dark-grotto', room: 'Slime Pool', x: null, y: null, players: 2 },
        ],
    },
    combat: [
        {
            encounter: 'KingSlime', starts: 20, victories: 12, defeats: 6, flees: 1,
            abandoned: 1, avg_duration_s: 95, avg_beats: 14.5, avg_hp_pct_on_win: 42,
        },
    ],
    sessions: {
        count: 50, players: 25, avg_minutes: 22.4, median_minutes: 15.0, avg_minutes_per_player: 44.8,
    },
    npc_chat: {
        conversations: 60, turns: 240, players: 20, avg_duration_s: 180, avg_latency_ms: 1400,
        by_npc: [{ npc: 'Gorran', conversations: 40, turns: 200, players: 18, avg_turns: 5.0, avg_duration_s: 200 }],
    },
};

function hookState(overrides = {}) {
    return {
        report: REPORT,
        days: REPORT.window_days,
        selectDays: vi.fn(),
        isAdmin: true,
        isLoading: false,
        error: '',
        notFound: false,
        reload: vi.fn(),
        ...overrides,
    };
}

function renderPage(state) {
    useAdminAnalytics.mockReturnValue(state);
    return render(<MemoryRouter><AdminAnalyticsPage /></MemoryRouter>);
}

beforeEach(() => vi.clearAllMocks());

describe('AdminAnalyticsPage', () => {
    it('shows the headline player numbers', () => {
        renderPage(hookState());
        const tiles = screen.getByRole('region', { name: /players/i });
        expect(within(tiles).getByText('42')).toBeInTheDocument();
        expect(within(tiles).getByText(/accounts/i)).toBeInTheDocument();
        expect(within(tiles).getByText('35')).toBeInTheDocument();
        expect(within(tiles).getByText('3')).toBeInTheDocument();
        expect(within(tiles).getByText('11')).toBeInTheDocument();
        expect(within(tiles).getByText('25')).toBeInTheDocument();
        expect(within(tiles).getByText('6')).toBeInTheDocument(); // new_accounts['7d']
        // Rolling windows, not calendar periods.
        expect(within(tiles).getByText('active in 24h')).toBeInTheDocument();
    });

    it('labels each section with the scope the report says it has', () => {
        renderPage(hookState({ days: 30 }));
        expect(screen.getByRole('region', { name: 'Combat (last 30 days)' })).toBeInTheDocument();
        expect(screen.getByRole('region', { name: 'Progress (all time)' })).toBeInTheDocument();
        expect(screen.getByRole('region', { name: 'Retention (all time)' })).toBeInTheDocument();
        expect(screen.getByRole('region', { name: 'Players (rolling 24h / 7d / 30d)' })).toBeInTheDocument();
    });

    it('labels every daily bar with its date and value', () => {
        renderPage(hookState());
        expect(screen.getByLabelText('2026-09-26: 9 active players')).toBeInTheDocument();
        expect(screen.getByLabelText('2026-09-25: 2 signups')).toBeInTheDocument();
    });

    it('offers the daily numbers as a table too', () => {
        renderPage(hookState());
        const table = screen.getByRole('table', { name: /daily/i });
        expect(within(table).getByText('2026-09-26')).toBeInTheDocument();
        expect(within(table).getByText('30')).toBeInTheDocument();
    });

    it('renders retention as percent with its denominator', () => {
        renderPage(hookState());
        const table = screen.getByRole('table', { name: /retention/i });
        expect(within(table).getByText('50%')).toBeInTheDocument();
        expect(within(table).getByText('D1+')).toBeInTheDocument(); // cumulative, not "on day 1"
        expect(within(table).getByText('10 of 20')).toBeInTheDocument();
        expect(within(table).getByText('—')).toBeInTheDocument(); // D30: nobody eligible yet
    });

    it('shows progression, stalls, combat, sessions and chat', () => {
        renderPage(hookState());
        expect(screen.getByRole('table', { name: /maps reached/i })).toHaveTextContent('grondia');
        expect(screen.getByRole('table', { name: /story flags/i })).toHaveTextContent('met_gorran');
        expect(screen.getByRole('table', { name: /levels/i })).toHaveTextContent('3');
        expect(screen.getByRole('table', { name: /stalled/i })).toHaveTextContent('Wall Depression');
        const combat = screen.getByRole('table', { name: /combat/i });
        expect(combat).toHaveTextContent('KingSlime');
        expect(combat).toHaveTextContent('30%'); // 6 deaths in 20 fights
        expect(combat).toHaveTextContent('42%'); // HP left on win
        expect(screen.getByRole('region', { name: /sessions/i })).toHaveTextContent('15');
        const chat = screen.getByRole('table', { name: /npc chat/i });
        expect(chat).toHaveTextContent('Gorran');
        expect(screen.getByRole('region', { name: /npc chat/i })).toHaveTextContent('1400');
    });

    it('marks a failed section unavailable without hiding the rest', () => {
        renderPage(hookState({ report: { ...REPORT, combat: { error: 'unavailable' } } }));
        expect(screen.getByRole('region', { name: /combat/i })).toHaveTextContent(/unavailable/i);
        expect(screen.getByRole('region', { name: /players/i })).toHaveTextContent('42');
    });

    it('says so when a section has no rows yet', () => {
        renderPage(hookState({ report: { ...REPORT, combat: [] } }));
        expect(screen.getByRole('region', { name: /combat/i })).toHaveTextContent(/no data yet/i);
    });

    it('renders a fresh deploy with no events yet', () => {
        renderPage(hookState({
            report: {
                ...REPORT,
                daily: [{ day: '2026-09-26', signups: 0, active: 0, chat_turns: 0 }],
                progress: { maps: [], flags: [], levels: [], stalled: [] },
                npc_chat: { ...REPORT.npc_chat, by_npc: [] },
            },
        }));
        // A zero day still gets a labelled (empty) bar rather than vanishing.
        expect(screen.getByLabelText('2026-09-26: 0 active players')).toBeInTheDocument();
        expect(screen.getByRole('region', { name: /progress/i })).toHaveTextContent(/no data yet/i);
        expect(screen.queryByRole('table', { name: /maps reached/i })).not.toBeInTheDocument();
        expect(screen.queryByRole('table', { name: /npc chat/i })).not.toBeInTheDocument();
    });

    it('says so when there are no days at all', () => {
        renderPage(hookState({ report: { ...REPORT, daily: [] } }));
        expect(screen.getByRole('region', { name: /daily/i })).toHaveTextContent(/no data yet/i);
    });

    it('switches the window', () => {
        const state = hookState();
        renderPage(state);
        const seven = screen.getByRole('button', { name: '7 days' });
        expect(screen.getByRole('button', { name: '30 days' })).toHaveAttribute('aria-pressed', 'true');
        expect(seven).toHaveAttribute('aria-pressed', 'false');
        fireEvent.click(seven);
        expect(state.selectDays).toHaveBeenCalledWith(7);
    });

    it('refreshes', () => {
        const state = hookState();
        renderPage(state);
        fireEvent.click(screen.getByRole('button', { name: /refresh/i }));
        expect(state.reload).toHaveBeenCalled();
    });

    it('reveals nothing about the page before the server has confirmed an admin', () => {
        renderPage(hookState({ report: null, isLoading: true, isAdmin: false }));
        expect(screen.getByText('Loading…')).toBeInTheDocument();
        expect(screen.queryByRole('heading', { name: /analytics/i })).not.toBeInTheDocument();
        expect(screen.queryByRole('button')).not.toBeInTheDocument();
    });

    it('keeps its header while a confirmed admin switches windows', () => {
        renderPage(hookState({ report: null, isLoading: true, isAdmin: true, days: 7 }));
        expect(screen.getByRole('heading', { name: /analytics/i })).toBeInTheDocument();
        expect(screen.getByText(/loading analytics/i)).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /loading/i })).toBeDisabled();
    });

    it('shows a dash, not a number, for an average with nothing to average', () => {
        const noWins = { ...REPORT.combat[0], victories: 0, avg_hp_pct_on_win: null, avg_duration_s: null };
        renderPage(hookState({ report: { ...REPORT, combat: [noWins] } }));
        const table = screen.getByRole('table', { name: /combat/i });
        const headers = within(table).getAllByRole('columnheader').map((h) => h.textContent);
        const cells = within(within(table).getAllByRole('row')[1]).getAllByRole('cell');
        const cell = (label) => cells[headers.indexOf(label)].textContent;
        // Not "0%": no wins is not "won with no health left".
        expect(cell('HP left on win')).toBe('—');
        expect(cell('Avg secs')).toBe('—');
    });

    it('treats a missing sub-list as empty rather than crashing', () => {
        renderPage(hookState({ report: { ...REPORT, progress: { maps: [] }, npc_chat: { conversations: 1 } } }));
        expect(screen.getByRole('region', { name: /progress/i })).toHaveTextContent(/no data yet/i);
        expect(screen.getByRole('region', { name: /npc chat/i })).toHaveTextContent(/no data yet/i);
    });

    it('locates each stalled room by its tile coordinates', () => {
        renderPage(hookState());
        const table = screen.getByRole('table', { name: /stalled/i });
        expect(within(table).getByText('Wall Depression (14, 5)')).toBeInTheDocument();
        // A save from before coordinates were recorded shows the room alone.
        expect(within(table).getByText('Slime Pool')).toBeInTheDocument();
    });

    it('shows a dash, not "null", for a tile whose room has no name', () => {
        const stalled = [{ map: 'dark-grotto', room: null, x: 3, y: 4, players: 1 }];
        renderPage(hookState({ report: { ...REPORT, progress: { ...REPORT.progress, stalled } } }));
        const table = screen.getByRole('table', { name: /stalled/i });
        expect(within(table).getByText('— (3, 4)')).toBeInTheDocument();
    });

    it('treats a sub-list sent as null as empty', () => {
        renderPage(hookState({ report: { ...REPORT, progress: { ...REPORT.progress, maps: null } } }));
        expect(screen.getByRole('region', { name: /progress/i })).toHaveTextContent(/no data yet/i);
    });

    it('labels the stall threshold from the report', () => {
        renderPage(hookState({ report: { ...REPORT, progress: { ...REPORT.progress, stalled_after_days: 14 } } }));
        expect(screen.getByText(/untouched 14\+ days/i)).toBeInTheDocument();
    });

    it('shows nothing useful to a non-admin', () => {
        renderPage(hookState({ report: null, notFound: true }));
        expect(screen.getByText(/nothing here/i)).toBeInTheDocument();
        expect(screen.queryByRole('region', { name: /players/i })).not.toBeInTheDocument();
        expect(screen.getByRole('link', { name: /back to the game/i })).toHaveAttribute('href', '/game');
    });

    it('offers a retry on failure', () => {
        const state = hookState({ report: null, error: 'Report unavailable' });
        renderPage(state);
        expect(screen.getByRole('alert')).toHaveTextContent('Report unavailable');
        fireEvent.click(screen.getByRole('button', { name: /retry/i }));
        expect(state.reload).toHaveBeenCalled();
    });

    it('marks every missing section unavailable', () => {
        renderPage(hookState({ report: { window_days: 30 } }));
        const regions = screen.getAllByRole('region');
        expect(regions).toHaveLength(SECTION_IDS.length);
        for (const region of regions) expect(region).toHaveTextContent(/unavailable/i);
    });

    it('shows a dash rather than crashing on a section missing a field', () => {
        renderPage(hookState({ report: { ...REPORT, sessions: { count: 2, players: 1 } } }));
        expect(screen.getByRole('region', { name: /sessions/i })).toHaveTextContent('—');
    });
});
