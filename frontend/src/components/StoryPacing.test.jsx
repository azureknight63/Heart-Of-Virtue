import React from 'react';
import { render, screen, fireEvent, act, cleanup } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

import ConversationStage from './ConversationStage';
import EventDialog from './EventDialog';
import TypewriterOutput from './TypewriterOutput';
import { usePreferences } from '../context/PreferencesContext';
import { DEFAULT_HOLD_MS } from '../hooks/useHoldToConfirm';
import {
    AUTO_ADVANCE_MIN_MS,
    BASE_MS_PER_CHAR,
    DEFAULT_TEXT_SPEED,
    INSTANT_TEXT_SPEED,
    autoAdvanceDelay,
} from '../utils/textPacing';

vi.mock('../context/PreferencesContext', () => ({ usePreferences: vi.fn() }));

const prefs = (overrides = {}) => ({
    textSpeed: DEFAULT_TEXT_SPEED,
    autoAdvance: false,
    ...overrides,
});

// The hold gauge drives itself with requestAnimationFrame + Date.now.
let now = 0;
beforeEach(() => {
    vi.clearAllMocks();
    usePreferences.mockReturnValue(prefs());
    now = 1_000_000;
    vi.spyOn(Date, 'now').mockImplementation(() => now);
    vi.stubGlobal('requestAnimationFrame', (cb) => setTimeout(cb, 16));
    vi.stubGlobal('cancelAnimationFrame', (id) => clearTimeout(id));
    vi.useFakeTimers();
});
afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    cleanup();
});

const tick = (ms) => act(() => vi.advanceTimersByTime(ms));

// React commits state updates when act() exits, so an interval created by a
// commit inside one advanceTimersByTime window is not itself advanced by that
// same window. Anything that has to cascade -- an auto-advance whose next beat
// must then type itself out -- needs successive ticks, not one long one.
const settle = (ms, times = 12) => {
    for (let i = 0; i < times; i += 1) tick(ms);
};

/** Begin a primary-button press on the hold control. */
const pressSkip = (button) => fireEvent.pointerDown(button, { button: 0, pointerId: 1 });

/** Run the gauge's clock past a full hold, one frame at a time. */
const elapseHold = () => {
    act(() => {
        for (let elapsed = 0; elapsed <= DEFAULT_HOLD_MS + 32; elapsed += 16) {
            now += 16;
            vi.advanceTimersByTime(16);
        }
    });
};

const holdOut = (button) => {
    pressSkip(button);
    elapseHold();
};

const SEGMENTS = [
    { text: 'Beat one.', in_conversation: false },
    { text: 'Beat two.', in_conversation: false },
    { text: 'Beat three, the last.', in_conversation: false },
];

// ---------------------------------------------------------------------------
// TEXT SPEED
// ---------------------------------------------------------------------------

describe('TEXT SPEED reaches every narrative typewriter (issue #538 item 1)', () => {
    it('types at the base rate at 1x', () => {
        render(<TypewriterOutput text="abcdef" />);
        const body = screen.getByTestId('event-text-container');

        tick(BASE_MS_PER_CHAR * 3);
        expect(body.textContent.replace(/\s/g, '')).toBe('abc');
    });

    it('types twice as fast at 2x', () => {
        usePreferences.mockReturnValue(prefs({ textSpeed: 2 }));
        render(<TypewriterOutput text="abcdef" />);
        const body = screen.getByTestId('event-text-container');

        tick(BASE_MS_PER_CHAR * 3);
        expect(body.textContent.replace(/\s/g, '')).toBe('abcdef');
    });

    it('renders the whole beat on the first frame at INSTANT', () => {
        // Not expressible as setInterval(fn, 0): browsers clamp nested timeouts
        // to ~4 ms, so a long beat would still crawl while claiming to be
        // instant.
        usePreferences.mockReturnValue(prefs({ textSpeed: INSTANT_TEXT_SPEED }));
        render(<TypewriterOutput text={'x'.repeat(400)} />);

        expect(screen.getByTestId('event-text-container').textContent).toContain('x'.repeat(400));
    });

    it('lets an explicit speed prop win over the setting', () => {
        // NpcChatPanel pairs its stage with its own tracker at a matched speed
        // (issue #531); that pair must not drift because a story setting moved.
        usePreferences.mockReturnValue(prefs({ textSpeed: INSTANT_TEXT_SPEED }));
        render(<TypewriterOutput text="abcdef" speed={100} />);
        const body = screen.getByTestId('event-text-container');

        // Pins the prop's rate, not merely "not instant".
        tick(300);
        expect(body.textContent.replace(/\s/g, '')).toBe('abc');
    });

    it('governs the conversation stage too', () => {
        usePreferences.mockReturnValue(prefs({ textSpeed: INSTANT_TEXT_SPEED }));
        render(<ConversationStage segments={SEGMENTS} onComplete={vi.fn()} />);

        expect(screen.getByText('Beat one.')).toBeInTheDocument();
    });
});

// ---------------------------------------------------------------------------
// AUTO-ADVANCE
// ---------------------------------------------------------------------------

describe('AUTO-ADVANCE (issue #538 item 1)', () => {
    it('does nothing when the setting is off', () => {
        // `settle`, not one long tick: the auto-advance timer is armed by an
        // effect that only commits when act() exits, so a single window can
        // never fire it and this assertion would hold with the setting forced
        // ON -- the exact fail-open the helper exists to avoid.
        const onComplete = vi.fn();
        render(<ConversationStage segments={SEGMENTS} onComplete={onComplete} />);
        settle(2000);
        expect(screen.getByText('Beat one.')).toBeInTheDocument();
        expect(onComplete).not.toHaveBeenCalled();
    });

    it('walks a finished beat on by itself when enabled', () => {
        usePreferences.mockReturnValue(prefs({ autoAdvance: true }));
        render(<ConversationStage segments={SEGMENTS} onComplete={vi.fn()} />);

        tick(BASE_MS_PER_CHAR * 20); // finish typing beat one
        expect(screen.getByText('Beat one.')).toBeInTheDocument();

        tick(autoAdvanceDelay('Beat one.') + 32); // dwell elapses, beat two begins
        tick(BASE_MS_PER_CHAR * 20); // beat two types itself out
        expect(screen.getByText('Beat two.')).toBeInTheDocument();
    });

    it('waits at least the floor even for a one-word beat', () => {
        usePreferences.mockReturnValue(prefs({ autoAdvance: true }));
        render(
            <ConversationStage
                segments={[{ text: 'Tents.', in_conversation: false }, ...SEGMENTS]}
                onComplete={vi.fn()}
            />
        );

        tick(BASE_MS_PER_CHAR * 10); // finish typing
        tick(AUTO_ADVANCE_MIN_MS - 200);
        expect(screen.getByText('Tents.')).toBeInTheDocument();
    });

    it('stops at the final beat instead of walking past it', () => {
        const onComplete = vi.fn();
        usePreferences.mockReturnValue(prefs({ autoAdvance: true }));
        render(<ConversationStage segments={SEGMENTS} onComplete={onComplete} />);

        settle(2000);
        expect(onComplete).toHaveBeenCalledTimes(1);
        expect(screen.getByText('Beat three, the last.')).toBeInTheDocument();
    });

    it('never auto-advances the live chat stage', () => {
        usePreferences.mockReturnValue(prefs({ autoAdvance: true }));
        const authoredComplete = vi.fn();
        const liveComplete = vi.fn();

        // The positive control: the same segments, the same settle, in the mode
        // that DOES auto-advance. Without it, a harness that advanced nothing
        // would satisfy the negative assertion below.
        const authored = render(
            <ConversationStage segments={SEGMENTS} onComplete={authoredComplete} />
        );
        settle(2000);
        expect(authoredComplete).toHaveBeenCalledTimes(1);
        authored.unmount();

        render(<ConversationStage segments={SEGMENTS} mode="live" onComplete={liveComplete} />);
        settle(2000);
        expect(liveComplete).not.toHaveBeenCalled();
    });
});

// ---------------------------------------------------------------------------
// AUTO-ADVANCE progress bar (issue #658)
// ---------------------------------------------------------------------------

describe('AUTO-ADVANCE progress bar (issue #658)', () => {
    const bar = () => screen.queryByRole('progressbar', { name: /auto-advance/i });

    it('is never shown when the setting is off', () => {
        render(<ConversationStage segments={SEGMENTS} onComplete={vi.fn()} />);
        tick(BASE_MS_PER_CHAR * 20); // beat one finished typing
        expect(screen.getByText('Beat one.')).toBeInTheDocument();
        expect(bar()).toBeNull();
    });

    it('appears only once the beat has finished typing, i.e. once the timer is armed', () => {
        usePreferences.mockReturnValue(prefs({ autoAdvance: true }));
        render(<ConversationStage segments={SEGMENTS} onComplete={vi.fn()} />);

        expect(bar()).toBeNull(); // still typing: nothing is armed yet
        tick(BASE_MS_PER_CHAR * 20);
        expect(bar()).toBeInTheDocument();
    });

    it('runs for exactly the dwell the auto-advance timer uses', () => {
        usePreferences.mockReturnValue(prefs({ autoAdvance: true }));
        render(<ConversationStage segments={SEGMENTS} onComplete={vi.fn()} />);
        tick(BASE_MS_PER_CHAR * 20);

        const delay = autoAdvanceDelay('Beat one.', DEFAULT_TEXT_SPEED);
        const fill = screen.getByTestId('auto-advance-fill');
        expect(fill.style.animationDuration).toBe(`${delay}ms`);
        expect(bar()).toHaveAttribute('aria-valuemax', String(delay));

        // And the timer really does fire on that same value.
        tick(delay - 1);
        expect(screen.getByText('Beat one.')).toBeInTheDocument();
        tick(1);
        expect(screen.queryByText('Beat one.')).toBeNull();
    });

    it('follows the TEXT SPEED setting, like the timer does', () => {
        // Long enough that both speeds clear the 900ms floor, so the two
        // dwells genuinely differ and a bar pinned to one speed would fail.
        const line = 'The camp fires burn low, and the wind carries ash off the ridge.';
        const fast = 2;
        expect(autoAdvanceDelay(line, fast)).not.toBe(autoAdvanceDelay(line, DEFAULT_TEXT_SPEED));
        usePreferences.mockReturnValue(prefs({ autoAdvance: true, textSpeed: fast }));
        render(<ConversationStage segments={[{ text: line, in_conversation: false }, ...SEGMENTS]} onComplete={vi.fn()} />);
        tick(BASE_MS_PER_CHAR * 80);

        expect(screen.getByTestId('auto-advance-fill').style.animationDuration)
            .toBe(`${autoAdvanceDelay(line, fast)}ms`);
    });

    it('restarts the fill when TEXT SPEED changes mid-dwell, as the timer re-arms (#674)', () => {
        // The timer effect re-arms on `autoAdvanceMs`; the bar was keyed on the
        // beat alone, so a mid-dwell speed change kept the old element — and a
        // changed animation-duration does not restart a running CSS animation —
        // leaving the bar out of step with the timer it depicts. INSTANT is
        // the step that exposes it: the typewriter re-shows the whole beat in
        // the same commit, so the beat stays complete and the bar stays
        // mounted while its dwell drops to the floor.
        const line = 'The camp fires burn low, and the wind carries ash off the ridge.';
        const fast = INSTANT_TEXT_SPEED;
        expect(autoAdvanceDelay(line, fast)).toBe(AUTO_ADVANCE_MIN_MS);
        expect(autoAdvanceDelay(line, DEFAULT_TEXT_SPEED)).toBeGreaterThan(AUTO_ADVANCE_MIN_MS);
        usePreferences.mockReturnValue(prefs({ autoAdvance: true }));
        const segments = [{ text: line, in_conversation: false }, ...SEGMENTS];
        const { rerender } = render(<ConversationStage segments={segments} onComplete={vi.fn()} />);
        tick(BASE_MS_PER_CHAR * 80);
        const before = screen.getByTestId('auto-advance-fill');

        tick(300); // part-way through the dwell
        usePreferences.mockReturnValue(prefs({ autoAdvance: true, textSpeed: fast }));
        rerender(<ConversationStage segments={segments} onComplete={vi.fn()} />);

        const after = screen.getByTestId('auto-advance-fill');
        expect(after.style.animationDuration).toBe(`${autoAdvanceDelay(line, fast)}ms`);
        expect(after).not.toBe(before);
    });

    it('disappears once the scene is complete, and never shows in live mode', () => {
        usePreferences.mockReturnValue(prefs({ autoAdvance: true }));
        const onComplete = vi.fn();
        const authored = render(<ConversationStage segments={SEGMENTS} onComplete={onComplete} />);
        settle(2000);
        expect(onComplete).toHaveBeenCalledTimes(1);
        expect(bar()).toBeNull();
        authored.unmount();

        render(<ConversationStage segments={SEGMENTS} mode="live" onComplete={vi.fn()} />);
        tick(BASE_MS_PER_CHAR * 40);
        expect(bar()).toBeNull();
    });
});

// ---------------------------------------------------------------------------
// SKIP SCENE
// ---------------------------------------------------------------------------

describe('SKIP SCENE (issue #538 item 1)', () => {
    const stagedEvent = {
        event_id: 'skip-1',
        name: 'CampEntryGreeting',
        type: 'CampEntryGreeting',
        output_text: 'Beat one.\nBeat two.\nBeat three, the last.',
        needs_input: false,
        segments: SEGMENTS,
    };

    const renderDialog = (event = stagedEvent, props = {}) =>
        render(
            <EventDialog
                event={event}
                onClose={props.onClose || vi.fn()}
                onSubmitInput={props.onSubmitInput || vi.fn()}
                history={props.history || []}
            />
        );

    const skipButton = () => screen.getByRole('button', { name: /Hold to skip/i });

    it('offers the control while a scene is still running', () => {
        renderDialog();
        expect(skipButton()).toBeInTheDocument();
    });

    it('needs a full hold — a click alone does nothing', () => {
        renderDialog();
        tick(BASE_MS_PER_CHAR * 20); // beat one types itself out

        // A full click, so a regression to a plain onClick control is caught.
        fireEvent.pointerDown(skipButton(), { button: 0, pointerId: 1 });
        fireEvent.pointerUp(skipButton(), { pointerId: 1 });
        fireEvent.click(skipButton());
        tick(100);

        // Still parked on the first beat, with no way out yet.
        expect(screen.getByText('Beat one.')).toBeInTheDocument();
        expect(screen.queryByText('Beat three, the last.')).toBeNull();
        expect(screen.queryByRole('button', { name: /^CLOSE$/ })).toBeNull();
    });

    it('lands on the final beat, whole, and ends the scene', () => {
        renderDialog();
        holdOut(skipButton());

        expect(screen.getByText('Beat three, the last.')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /^CLOSE$/ })).toBeInTheDocument();
    });

    it('completes the hold even though the typing scene moves the button out from under the pointer (issue #583)', () => {
        // The dialog is vertically centred and grows upward as each line
        // types out, so a pointer that never moves ends up outside the button
        // within a few frames. The gesture must ride that out: it is only
        // offered while the scene is typing, which is exactly when it moves.
        renderDialog();
        const button = skipButton();

        pressSkip(button);
        tick(DEFAULT_HOLD_MS / 3);
        fireEvent.mouseLeave(button);
        fireEvent.pointerLeave(button, { pointerId: 1 });
        elapseHold();

        expect(screen.getByText('Beat three, the last.')).toBeInTheDocument();
        expect(screen.getByRole('button', { name: /^CLOSE$/ })).toBeInTheDocument();
    });

    it('stays mounted, and disabled, once the hold completes', () => {
        // The structural guard against a real-browser bug jsdom cannot stage.
        // A browser finishes the gesture with mouseup + click, and when the
        // mousedown target has been removed it retargets that click to the
        // nearest still-connected ancestor -- here the dialog body, whose
        // handler dismisses a completed event. Unmounting the control on
        // confirm therefore made "skip this scene" CLOSE it instead of landing
        // on its final beat. A disabled button dispatches no mouse events and
        // stays connected, so there is nothing left to retarget: asserting it
        // is still in the tree, and disabled, is what holds that fix in place.
        renderDialog();
        holdOut(skipButton());

        expect(skipButton()).toBeDisabled();
        expect(screen.getByText('Beat three, the last.')).toBeInTheDocument();
    });

    it('keeps focus inside the dialog when the skip control goes dead', () => {
        // The focus trap no longer parks initial focus on the skip control
        // (issue #584), so this stages what a keyboard user does: Tab onto
        // the button, then hold it. jsdom does not move focus on Tab, so the
        // focus() call stands in for the keystroke.
        renderDialog(stagedEvent);
        expect(document.activeElement).toBe(document.querySelector('.modal-content'));
        act(() => skipButton().focus());
        expect(document.activeElement).toBe(skipButton());

        holdOut(skipButton());

        // Asserted as the exact post-condition, not merely "somewhere inside
        // the dialog": without the hand-back focus stays on the disabled
        // button (jsdom) or falls to <body> (a real browser), and the first of
        // those is still *contained* by the dialog, so a containment check
        // could not tell the fix from its absence.
        expect(document.activeElement).toBe(document.querySelector('.modal-content'));
    });

    it('does not close the dialog on the click that ends the skip hold, even if it lands on the body (issue #583)', () => {
        // The gesture is press → hold → release, and the release still
        // produces a click. If the layout has shifted by then the browser
        // can retarget that click to the dialog body, whose handler dismisses
        // a completed event — so skipping a scene would close it. The press
        // began on the skip control, so the click it ends with is not a
        // "continue" gesture, wherever it lands.
        const onClose = vi.fn();
        renderDialog(stagedEvent, { onClose });
        holdOut(skipButton());
        expect(screen.getByText('Beat three, the last.')).toBeInTheDocument();
        const body = document.querySelector('.event-dialog-body');

        fireEvent.click(body);
        expect(onClose).not.toHaveBeenCalled();

        // The next, genuine click on the body is still a dismissal.
        fireEvent.pointerDown(body, { button: 0, pointerId: 1 });
        fireEvent.click(body);
        expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('swallows only the click that ends the hold; the next click on the body, with no press of its own, still dismisses', () => {
        // The press-origin record is consumed by the click it was made for.
        // Left latched, every later click on the body would be swallowed until
        // some other pointerdown happened to overwrite it — including a click
        // synthesised without one (assistive tech, a keyboard-driven click).
        const onClose = vi.fn();
        renderDialog(stagedEvent, { onClose });
        holdOut(skipButton());
        const body = document.querySelector('.event-dialog-body');

        fireEvent.click(body);
        expect(onClose).not.toHaveBeenCalled();

        fireEvent.click(body);
        expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('forgets a press that began on the controls row once the engine hands over the next stage', () => {
        // A hold whose click never arrived (a touch the browser cancelled)
        // leaves the record set. The next stage is a new scene: its first
        // genuine click on the body must not be paid for by the last one's.
        const onClose = vi.fn();
        const { rerender } = renderDialog(
            {
                ...stagedEvent,
                needs_input: true,
                input_type: 'choice',
                input_options: [{ label: 'Go on', value: 'go' }],
            },
            { onClose }
        );
        holdOut(skipButton());
        expect(screen.getByText('Go on')).toBeInTheDocument();

        rerender(
            <EventDialog
                event={{
                    ...stagedEvent,
                    event_id: 'skip-2',
                    output_text: 'Stage two.',
                    segments: [{ text: 'Stage two.', in_conversation: false }],
                }}
                onClose={onClose}
                onSubmitInput={vi.fn()}
                history={[]}
            />
        );
        // Walk stage two to its end from the keyboard: the key path never
        // touches the click handler, so nothing here can consume the record
        // by accident.
        fireEvent.keyDown(document.activeElement, { key: 'Enter' }); // finish typing
        fireEvent.keyDown(document.activeElement, { key: 'Enter' }); // complete the stage
        expect(screen.getByRole('button', { name: /^CLOSE$/ })).toBeInTheDocument();

        fireEvent.click(document.querySelector('.event-dialog-body'));
        expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('does not close the dialog when the controls row is clicked', () => {
        // The row swallows its own clicks; the dialog body behind it dismisses
        // a completed event.
        const onClose = vi.fn();
        renderDialog(stagedEvent, { onClose });
        holdOut(skipButton());

        fireEvent.click(skipButton().parentElement);
        expect(onClose).not.toHaveBeenCalled();
    });

    it('is not offered for a death scene, which is already shown whole', () => {
        renderDialog({ ...stagedEvent, is_death_scene: true, segments: undefined });
        expect(screen.queryByRole('button', { name: /Hold to skip/i })).toBeNull();
    });

    it('reveals the plain typewriter path instantly too', () => {
        renderDialog({ ...stagedEvent, segments: undefined });
        holdOut(skipButton());

        expect(screen.getByTestId('event-text-container').textContent)
            .toContain('Beat three, the last.');
    });

    it('stops at a choice rather than answering it, even held from the keyboard', () => {
        // The failure this guards: a keyboard hold streams auto-repeat
        // keydowns, and the moment the skip reveals the choice the next repeat
        // reaches EventDialog's Enter handler and answers it unseen.
        const onSubmitInput = vi.fn();
        renderDialog(
            {
                ...stagedEvent,
                needs_input: true,
                input_type: 'choice',
                input_options: [{ label: 'Go on', value: 'go' }],
            },
            { onSubmitInput }
        );
        const button = skipButton();

        fireEvent.keyDown(button, { key: 'Enter' });
        act(() => {
            for (let elapsed = 0; elapsed <= DEFAULT_HOLD_MS + 200; elapsed += 16) {
                now += 16;
                vi.advanceTimersByTime(16);
                fireEvent.keyDown(button, { key: 'Enter', repeat: true });
            }
        });

        expect(onSubmitInput).not.toHaveBeenCalled();
        expect(screen.getByText('Go on')).toBeInTheDocument();
    });

    it('stops at a choice rather than answering it', () => {
        const onSubmitInput = vi.fn();
        renderDialog(
            {
                ...stagedEvent,
                needs_input: true,
                input_type: 'choice',
                input_options: [{ label: 'Touch it', value: 'touch' }, { label: 'Leave it', value: 'leave' }],
            },
            { onSubmitInput }
        );
        holdOut(skipButton());

        // The choice is offered, not answered.
        const touch = screen.getAllByRole('button').find((b) => /Touch it/.test(b.textContent));
        expect(touch.textContent).toBe('[1] Touch it');
        expect(onSubmitInput).not.toHaveBeenCalled();
    });

    it('can be used again on the next stage of a multi-stage event', () => {
        const { rerender } = renderDialog({
            ...stagedEvent,
            needs_input: true,
            input_type: 'choice',
            input_options: [{ label: 'Go on', value: 'go' }],
        });
        holdOut(skipButton());
        expect(screen.getByText('Go on')).toBeInTheDocument();

        rerender(
            <EventDialog
                event={{
                    ...stagedEvent,
                    output_text: 'Stage two.',
                    segments: [
                        { text: 'Stage two, beat one.', in_conversation: false },
                        { text: 'Stage two, beat two.', in_conversation: false },
                    ],
                }}
                onClose={vi.fn()}
                onSubmitInput={vi.fn()}
                history={[]}
            />
        );

        holdOut(skipButton());
        expect(screen.getByText('Stage two, beat two.')).toBeInTheDocument();
    });
});
