// Issue #668: token motion during a follow-camera settle.
//
// The camera lerps in RAF and re-indexes the rendered window a whole cell at a
// time (the content div carries the sub-cell remainder). A re-index changes
// every token's cell translate by one cell while the content div's offset
// jumps the opposite way in the same frame — net zero on screen, PROVIDED the
// token's new translate applies instantly. The token wrapper used to carry
// `transition: transform 0.5s`, so each re-index retriggered an eased slide
// from wherever the token was toward its re-indexed cell: the token jumped a
// cell with the content div, then drifted back. That is the jitter.
//
// jsdom runs no CSS transitions, so these tests assert the two properties the
// browser needs: (1) an element whose translate changes because the CAMERA
// moved must not transition that translate, and (2) a combatant's own world
// move is still tweened, on an element the camera re-index never touches.
import React from 'react';
import { render, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import BattlefieldGrid, { VIEW_SIZE } from './BattlefieldGrid';
import { TOKEN_MOVE_MS } from '../hooks/useTokenMoveTween';

vi.mock('../context/AudioContext', () => ({
    useAudio: () => ({ playSFX: vi.fn() }),
}));

const HALF = Math.floor(VIEW_SIZE / 2);

// Long enough for the tween's two-frame release under fake timers, whose
// requestAnimationFrame ticks every ~16ms.
const PAST_RELEASE_FRAMES_MS = 40;

const combatWithJeanAt = (x, y) => ({
    player: {
        id: 'player', name: 'Jean', hp: 100, max_hp: 100, fatigue: 0, max_fatigue: 100,
        position: { x, y, facing: 'N' },
    },
    enemies: [
        { id: 'goblin', name: 'Goblin', hp: 50, max_hp: 50, position: { x: 12, y: 10, facing: 'S' } },
    ],
});

/** The token wrapper for the marker showing `symbol`. */
const tokenOf = (container, symbol) => [...container.querySelectorAll('[data-testid="battlefield-token"]')]
    .find((el) => el.textContent.includes(symbol));

/** The camera's content div: the first `will-change: transform` div. */
const contentDiv = (container) => [...container.querySelectorAll('div')]
    .find((d) => d.style.willChange === 'transform');

/** Parse `translate(a%, b%)` into [a, b]; '' and 'none' are [0, 0]. */
const translatePct = (transform) => {
    const m = /translate\((-?[\d.]+)%,\s*(-?[\d.]+)%\)/.exec(transform || '');
    return m ? [parseFloat(m[1]), parseFloat(m[2])] : [0, 0];
};

const transitionsTransform = (el) => /(^|,\s*)(transform|all)\b/.test(el.style.transition || '');

describe('BattlefieldGrid token motion during a camera settle (#668)', () => {
    beforeEach(() => { vi.useFakeTimers(); });
    afterEach(() => { vi.useRealTimers(); });

    it('re-indexes tokens instantly when the camera crosses a cell, and they track the camera monotonically', () => {
        const { container, rerender } = render(
            <BattlefieldGrid combat={combatWithJeanAt(10, 10)} tab="overview" zoom={1} />
        );
        // Jean steps one cell east; the goblin stands still in the world.
        rerender(<BattlefieldGrid combat={combatWithJeanAt(11, 10)} tab="overview" zoom={1} />);

        const frames = [];
        for (let i = 0; i < 60; i++) {
            act(() => { vi.advanceTimersByTime(16); });
            const goblin = tokenOf(container, 'G');
            // The goblin's on-screen column, in cells: its own cell translate
            // (percent of one cell) plus the content div's sub-cell offset
            // (percent of the whole VIEW_SIZE-cell box).
            const [ownX] = translatePct(goblin.style.transform);
            const [camX] = translatePct(contentDiv(container).style.transform);
            frames.push({
                ownTransform: goblin.style.transform,
                transitions: transitionsTransform(goblin),
                screenX: ownX / 100 + (camX / 100) * VIEW_SIZE,
            });
        }

        // The camera really did re-index mid-settle, or this test proves nothing.
        const reindexes = frames.filter((f, i) => i > 0 && f.ownTransform !== frames[i - 1].ownTransform);
        expect(reindexes.length).toBeGreaterThan(0);

        // (1) The mechanism: a re-index must not retrigger an eased slide.
        for (const f of reindexes) expect(f.transitions).toBe(false);

        // (2) The effect: a world-stationary token slides one way only as the
        // camera follows Jean east — never jumps back.
        for (let i = 1; i < frames.length; i++) {
            expect(frames[i].screenX).toBeLessThanOrEqual(frames[i - 1].screenX + 1e-6);
        }
        // And it ends exactly one cell west of where it started.
        expect(frames.at(-1).screenX).toBeCloseTo((12 - (10 - HALF)) - 1, 5);
    });

    it("still tweens a combatant's own world move, on a layer the camera never re-indexes", () => {
        const { container, rerender } = render(
            <BattlefieldGrid combat={combatWithJeanAt(10, 10)} tab="overview" zoom={1} />
        );
        rerender(<BattlefieldGrid combat={combatWithJeanAt(11, 10)} tab="overview" zoom={1} />);

        const jean = tokenOf(container, 'J');
        const tween = jean.querySelector('[data-testid="token-move-tween"]');
        expect(tween).not.toBeNull();
        // Drawn back at her previous cell (one cell west) with no transition,
        // so the first painted frame is where she was.
        expect(translatePct(tween.style.transform)).toEqual([-100, 0]);
        expect(transitionsTransform(tween)).toBe(false);

        // Two frames later the offset is released and eases to her new cell.
        act(() => { vi.advanceTimersByTime(PAST_RELEASE_FRAMES_MS); });
        expect(tween.style.transform).toBe('');
        expect(transitionsTransform(tween)).toBe(true);

        // The camera's later re-index leaves the tween alone.
        const before = tween.style.cssText;
        act(() => { vi.advanceTimersByTime(2000); });
        expect(tween.style.cssText).toBe(before);
    });

    it('glides a world move at the combat speed (#674)', () => {
        const { container, rerender } = render(
            <BattlefieldGrid combat={combatWithJeanAt(10, 10)} tab="overview" zoom={1} combatSpeed={2} />
        );
        rerender(<BattlefieldGrid combat={combatWithJeanAt(11, 10)} tab="overview" zoom={1} combatSpeed={2} />);
        const tween = tokenOf(container, 'J').querySelector('[data-testid="token-move-tween"]');
        act(() => { vi.advanceTimersByTime(PAST_RELEASE_FRAMES_MS); });
        expect(tween.style.transition).toBe(`transform ${TOKEN_MOVE_MS / 2}ms ease-in-out`);
    });

    it('maps a world move north to a screen offset downward (rows grow south)', () => {
        const { container, rerender } = render(
            <BattlefieldGrid combat={combatWithJeanAt(10, 10)} tab="overview" zoom={1} />
        );
        rerender(<BattlefieldGrid combat={combatWithJeanAt(10, 11)} tab="overview" zoom={1} />);
        const tween = tokenOf(container, 'J').querySelector('[data-testid="token-move-tween"]');
        expect(translatePct(tween.style.transform)).toEqual([0, 100]);
    });

    it('does not tween a jump the camera snaps across', () => {
        const { container, rerender } = render(
            <BattlefieldGrid combat={combatWithJeanAt(10, 10)} tab="overview" zoom={1} />
        );
        rerender(<BattlefieldGrid combat={combatWithJeanAt(10 + HALF + 1, 10)} tab="overview" zoom={1} />);
        const tween = tokenOf(container, 'J').querySelector('[data-testid="token-move-tween"]');
        expect(tween.style.transform).toBe('');
    });
});
