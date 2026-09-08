import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import Battlefield from './Battlefield';
import { accessibility } from '../styles/theme';

const gridProps = [];
vi.mock('./BattlefieldGrid', () => ({
    VIEW_SIZE: 13,
    VIEW_MODE_FOLLOW: 'follow',
    VIEW_MODE_FIT: 'fit',
    default: (props) => {
        gridProps.push(props);
        return <div data-testid="grid">Zoom: {props.zoom}</div>;
    },
}));

const lastZoom = () => gridProps[gridProps.length - 1].zoom;

// HALF_VIEW = floor(13 / 2) = 6, so |dx| > 6 is outside the Follow viewport.
const fight = ({ id = 'fight-A', enemyX = 13 } = {}) => ({
    combat_id: id,
    combat_active: true,
    enemies: [{ id: 'e1', name: 'Rock Rumbler', hp: 10, max_hp: 10 }],
    beat_states: [{
        player: { name: 'Jean', position: { x: 5, y: 5 } },
        enemies: [{ id: 'e1', name: 'Rock Rumbler', hp: 10, max_hp: 10, position: { x: enemyX, y: 5 } }],
    }],
});

describe('Battlefield — framing the fight the player was handed (#561)', () => {
    beforeEach(() => {
        gridProps.length = 0;
        vi.clearAllMocks();
    });

    it('widens the camera itself instead of asking the player to', async () => {
        render(<Battlefield combat={fight()} currentLogIndex={0} />);
        await waitFor(() => expect(lastZoom()).toBe('fit'));
        expect(screen.getByRole('button', { name: 'Fit Fight' }).getAttribute('aria-pressed')).toBe('true');
    });

    it('says what it did rather than what the player should do', async () => {
        render(<Battlefield combat={fight()} currentLogIndex={0} />);
        const banner = await screen.findByRole('status');
        expect(banner).toHaveTextContent(/view widened/i);
    });

    it('leaves the default camera alone when every enemy is already framed', () => {
        render(<Battlefield combat={fight({ enemyX: 11 })} currentLogIndex={0} />);
        expect(lastZoom()).toBe('follow');
    });

    it('never overrides a camera the player chose for this fight', async () => {
        const { rerender } = render(<Battlefield combat={fight()} currentLogIndex={0} />);
        await waitFor(() => expect(lastZoom()).toBe('fit'));

        // The player disagrees and goes back to Follow with the enemy still
        // outside the viewport. That choice has to stick: the auto-fit fires
        // once per fight, not once per render.
        fireEvent.click(screen.getByRole('button', { name: 'Follow' }));
        expect(lastZoom()).toBe('follow');

        // Later beats of the SAME fight, enemy still off-screen.
        rerender(<Battlefield combat={fight()} currentLogIndex={0} />);
        rerender(<Battlefield combat={fight()} currentLogIndex={0} />);
        expect(lastZoom()).toBe('follow');
    });

    it('never tells the player to switch to Fit Fight while Fit Fight is on', async () => {
        // The nag's whole reason for existing (#561) is that the app knew the
        // framing was wrong and asked the player to fix it. Rendering it while
        // the player is ALREADY in Fit Fight is that same complaint: the
        // banner was keyed on raw geometry, which dropped the
        // `zoom !== 'fit'` term the old condition carried.
        const { rerender } = render(<Battlefield combat={fight({ enemyX: 6 })} currentLogIndex={0} />);
        // Enemy framed, so nothing auto-fitted; the player picks Fit Fight.
        fireEvent.click(screen.getByRole('button', { name: 'Fit Fight' }));
        expect(lastZoom()).toBe('fit');

        // The enemy now strays past the Follow viewport. Fit Fight is already
        // on, so there is nothing for the player to do.
        rerender(<Battlefield combat={fight({ enemyX: 13 })} currentLogIndex={0} />);

        await waitFor(() => expect(lastZoom()).toBe('fit'));
        expect(screen.queryByText(/switch to Fit Fight/i)).toBeNull();
    });

    it('re-fits for a new fight after the player claimed the last one', async () => {
        const { rerender } = render(<Battlefield combat={fight({ id: 'fight-A' })} currentLogIndex={0} />);
        await waitFor(() => expect(lastZoom()).toBe('fit'));
        fireEvent.click(screen.getByRole('button', { name: 'Follow' }));
        expect(lastZoom()).toBe('follow');

        // A different combat_id is a different fight; the camera claim from
        // the last one must not carry over.
        rerender(<Battlefield combat={fight({ id: 'fight-B' })} currentLogIndex={0} />);
        await waitFor(() => expect(lastZoom()).toBe('fit'));
    });

    it('does not re-fit when the player picks Follow before an enemy strays', () => {
        const { rerender } = render(<Battlefield combat={fight({ enemyX: 11 })} currentLogIndex={0} />);
        expect(lastZoom()).toBe('follow');

        // Explicitly claiming Follow while nothing is off-screen.
        fireEvent.click(screen.getByRole('button', { name: 'Follow' }));
        expect(lastZoom()).toBe('follow');

        // Now an enemy strays. The player has already spoken for this fight.
        rerender(<Battlefield combat={fight({ enemyX: 13 })} currentLogIndex={0} />);
        expect(lastZoom()).toBe('follow');
        expect(screen.getByRole('button', { name: 'Follow' }).getAttribute('aria-pressed')).toBe('true');
        // ...and because the camera is the player's choice now, the banner goes
        // back to the original nudge rather than claiming a widening that never
        // happened.
        expect(screen.getByRole('status')).toHaveTextContent(/switch to Fit Fight/i);
    });
});

describe('Battlefield — toolbar touch targets on a phone (#564)', () => {
    const originalMatchMedia = window.matchMedia;

    beforeEach(() => {
        gridProps.length = 0;
        window.matchMedia = (query) => ({
            // 375x812: a phone width AND a coarse pointer.
            matches: /max-width|pointer: coarse|hover: none/.test(query),
            media: query,
            onchange: null,
            addListener: () => {},
            removeListener: () => {},
            addEventListener: () => {},
            removeEventListener: () => {},
            dispatchEvent: () => false,
        });
    });

    afterEach(() => {
        window.matchMedia = originalMatchMedia;
    });

    it.each(['Overview', 'Enemies (1)', 'Follow', 'Fit Fight'])(
        'gives the %s control the 44px minimum',
        (label) => {
            render(<Battlefield combat={fight({ enemyX: 11 })} currentLogIndex={0} />);
            const button = screen.getByRole('button', { name: label });
            expect(button.style.minHeight).toBe(accessibility.touchTarget);
        }
    );

    it('lets the toolbar wrap rather than overflow at 375px', () => {
        const { container } = render(<Battlefield combat={fight({ enemyX: 11 })} currentLogIndex={0} />);
        const toolbar = container.querySelector('[data-testid="battlefield-toolbar"]');
        expect(toolbar.style.flexWrap).toBe('wrap');
    });

    it('leaves the desktop toolbar compact', () => {
        window.matchMedia = originalMatchMedia;
        render(<Battlefield combat={fight({ enemyX: 11 })} currentLogIndex={0} />);
        expect(screen.getByRole('button', { name: 'Overview' }).style.minHeight).toBe('');
    });
});
