import React from 'react';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import JournalDialog from './JournalDialog';
import { player as playerApi } from '../api/endpoints';

vi.mock('../api/endpoints', () => ({
    player: { getJournal: vi.fn() },
}));

const JOURNAL = {
    // Only the fields JournalDialog actually reads. The wire shape itself is
    // guarded against the real serializer in tests/test_wire_field_contract.py;
    // carrying extra keys here would imply a contract that is not one.
    objectives: [
        { key: 'ch03_walk_the_camp', text: 'Meet the rest of the camp, then return to Mara.' },
        { key: 'ch02_find_mara', text: 'Find Mara at the river camp.' },
    ],
    completed: [
        { key: 'ch02_king_slime', text: 'Defeat the King Slime.' },
    ],
    log: [
        { title: 'Camp Entry', lines: [{ speaker: null, text: 'Jean stopped at the edge.' }, { speaker: 'Jean', text: 'Tents.' }], tick: 3 },
        { title: "River's Edge", lines: [{ speaker: 'Mara', text: 'Crossing west?' }], tick: 9 },
    ],
};

const resolveWith = (journal) =>
    playerApi.getJournal.mockResolvedValue({ data: { success: true, journal } });

beforeEach(() => {
    vi.clearAllMocks();
    resolveWith(JOURNAL);
});
afterEach(cleanup);

describe('JournalDialog', () => {
    it('opens on the objectives tab and lists the active ones', async () => {
        render(<JournalDialog onClose={vi.fn()} />);

        expect(await screen.findByText(/Meet the rest of the camp/)).toBeInTheDocument();
        expect(screen.getByText('Find Mara at the river camp.')).toBeInTheDocument();
    });

    it('keeps completed objectives, struck through, rather than dropping them', async () => {
        // "What have I done here" is as much of an orientation question as
        // "what do I do next" — a list that empties itself answers neither.
        render(<JournalDialog onClose={vi.fn()} />);

        const done = await screen.findByText('Defeat the King Slime.');
        expect(done.style.textDecoration).toBe('line-through');
    });

    it('shows the transcript newest first on the story-log tab', async () => {
        render(<JournalDialog onClose={vi.fn()} />);
        await screen.findByText(/Meet the rest of the camp/);

        fireEvent.click(screen.getByText('STORY LOG'));

        const body = screen.getByTestId('journal-body');
        const headings = Array.from(body.querySelectorAll('p'))
            .map((el) => el.textContent)
            .filter((t) => t === 'CAMP ENTRY' || t === "RIVER'S EDGE");
        expect(headings).toEqual(["RIVER'S EDGE", 'CAMP ENTRY']);
    });

    it('keeps the speaker attribution the staged conversation showed', async () => {
        render(<JournalDialog onClose={vi.fn()} />);
        await screen.findByText(/Meet the rest of the camp/);

        fireEvent.click(screen.getByText('STORY LOG'));

        expect(screen.getByText('JEAN')).toBeInTheDocument();
        expect(screen.getByText('Tents.')).toBeInTheDocument();

        // Narration carries no speaker label — asserted, not just implied: a
        // dialogue row holds two inline runs (speaker + line), a narration row
        // holds one.
        const narration = screen.getByText('Jean stopped at the edge.');
        expect(narration.parentElement.querySelectorAll('span')).toHaveLength(1);
        const spoken = screen.getByText('Tents.');
        expect(spoken.parentElement.querySelectorAll('span')).toHaveLength(2);
    });

    it('explains an empty journal instead of showing a blank panel', async () => {
        resolveWith({ objectives: [], completed: [], log: [] });
        render(<JournalDialog onClose={vi.fn()} />);

        expect(await screen.findByText(/No objectives yet/i)).toBeInTheDocument();

        fireEvent.click(screen.getByText('STORY LOG'));
        expect(screen.getByText(/Nothing recorded yet/i)).toBeInTheDocument();
    });

    it('surfaces a load failure with a retry that actually refetches', async () => {
        playerApi.getJournal.mockRejectedValueOnce(new Error('server down'));
        render(<JournalDialog onClose={vi.fn()} />);

        expect(await screen.findByText(/Could not load the journal/i)).toBeInTheDocument();

        resolveWith(JOURNAL);
        fireEvent.click(screen.getByText('RETRY'));

        expect(await screen.findByText(/Meet the rest of the camp/)).toBeInTheDocument();
        expect(playerApi.getJournal).toHaveBeenCalledTimes(2);
    });

    it('prefers the API error prose over the generic fallback', async () => {
        playerApi.getJournal.mockRejectedValueOnce({
            response: { data: { error: 'Session expired.' } },
        });
        render(<JournalDialog onClose={vi.fn()} />);

        expect(await screen.findByText('Session expired.')).toBeInTheDocument();
    });

    it('tolerates a malformed payload rather than crashing', async () => {
        playerApi.getJournal.mockResolvedValue({ data: {} });
        render(<JournalDialog onClose={vi.fn()} />);

        expect(await screen.findByText(/No objectives yet/i)).toBeInTheDocument();
    });

    it('closes from CLOSE', async () => {
        const onClose = vi.fn();
        render(<JournalDialog onClose={onClose} />);
        await screen.findByText(/Meet the rest of the camp/);

        fireEvent.click(screen.getByText('CLOSE'));
        expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('does not mutate the log array while reversing it for display', async () => {
        // Asserted on the source array rather than on render order: a mutating
        // `reverse()` shows up in the DOM only on an odd number of renders, so
        // a display-order check tests render-count parity, not the bug.
        const journal = { ...JOURNAL, log: [...JOURNAL.log] };
        resolveWith(journal);
        render(<JournalDialog onClose={vi.fn()} />);
        await screen.findByText(/Meet the rest of the camp/);

        fireEvent.click(screen.getByText('STORY LOG'));

        expect(journal.log.map((scene) => scene.title))
            .toEqual(['Camp Entry', "River's Edge"]);
    });

    it('fetches once per open', async () => {
        render(<JournalDialog onClose={vi.fn()} />);
        await waitFor(() => expect(playerApi.getJournal).toHaveBeenCalledTimes(1));
    });
});
