// Comments added to this file from 2026-09 on use ASCII `--` where the older
// ones use an em dash. Deliberate, not drift: two rounds of edits here arrived
// double-encoded through the shell, and one of them made a negative assertion
// vacuous. tests/test_content_encoding.py sweeps for the damage; this avoids
// creating it.
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import LeftPanel from './LeftPanel';
import BaseDialog from './BaseDialog';
import { CATEGORY_GROUPS } from '../utils/categories';
import {
    allyId,
    enemyId,
    makeAvailableOption,
    makeCheckEntry,
    makeCombat,
    makeCombatant,
    makeEnemy,
    makeLocation,
    makePlayer,
    makeSuggestedMove,
    makeTargetOption,
    twoTargets,
    NOT_ENOUGH_FATIGUE_REASON,
    TURN_DIRECTIONS,
    WAIT_DURATION_PROMPT,
} from '../test/payloads';
import { colors } from '../styles/theme';
import { FLEE_BREAK_AWAY_DISTANCE_FT } from '../utils/combatMoveStatus';

// Mock child components
vi.mock('./PartyPanel', () => ({ default: ({ onClose }) => <div data-testid="party-panel"><button onClick={onClose}>Close Party</button></div> }));
vi.mock('./InventoryDialog', () => ({ default: ({ onClose }) => <div data-testid="inventory-dialog"><button onClick={onClose}>Close Inv</button></div> }));
vi.mock('./AccountDialog', () => ({ default: ({ onClose }) => <div data-testid="account-dialog"><button onClick={onClose}>Close Acc</button></div> }));
vi.mock('./SettingsDialog', () => ({ default: ({ onClose }) => <div data-testid="audio-dialog"><button onClick={onClose}>Close Aud</button></div> }));
vi.mock('./JournalDialog', () => ({ default: ({ onClose }) => <div data-testid="journal-dialog"><button onClick={onClose}>Close Journal</button></div> }));
vi.mock('./StatsPanel', () => ({ default: ({ onClose }) => <div data-testid="stats-panel"><button onClick={onClose}>Close Stats</button></div> }));
vi.mock('./SkillsPanel', () => ({ default: ({ onClose }) => <div data-testid="skills-panel"><button onClick={onClose}>Close Skills</button></div> }));
vi.mock('./CollapsibleRoomDescription', () => ({
    default: ({ onInteract }) => (
        <div data-testid="room-contents">
            <button onClick={() => onInteract()}>Interact Button</button>
            <button onClick={() => onInteract('a rusty lever')}>Interact With Lever</button>
        </div>
    )
}));
vi.mock('./ActionsPanel', () => ({ default: ({ onClose }) => <div data-testid="actions-panel"><button onClick={onClose}>Close Actions</button></div> }));
vi.mock('./InteractPanel', () => ({
    default: ({ onClose, onOpenShop, initialTarget }) => (
        <div data-testid="interact-panel">
            {initialTarget && <span>target:{initialTarget}</span>}
            <button onClick={onClose}>Close Interact</button>
            <button onClick={() => onOpenShop('npc-1', 'Jambo', 'buy')}>Open Shop</button>
        </div>
    )
}));
vi.mock('./HeroPanel', () => ({
    default: (props) => (
        <div data-testid="hero-panel">
            <button onClick={props.onStatusClick}>Status Btn</button>
            <button onClick={props.onInventoryClick}>Inventory Btn</button>
            <button onClick={props.onSkillsClick}>Skills Btn</button>
            <button onClick={props.onAttributeClick}>Attributes Btn</button>
            <button onClick={props.onActionsClick}>Actions Btn</button>
            <button onClick={props.onInteractClick}>Interact Btn</button>
            <button onClick={props.onOffensiveClick}>Offensive Btn</button>
            <button onClick={props.onDefensiveClick}>Defensive Btn</button>
            <button onClick={props.onManeuverClick}>Maneuver Btn</button>
            <button onClick={props.onMiscellaneousClick}>Miscellaneous Btn</button>
            <button onClick={props.onSpecialClick}>Special Btn</button>
            <span data-testid="hero-player-hp">{props.player?.hp}</span>
            <span data-testid="hero-scale">{props.heroScale}</span>
            <span data-testid="hero-flags">
                {[
                    props.hasOffensiveMoves && 'offensive',
                    props.hasDefensiveMoves && 'defensive',
                    props.hasManeuverMoves && 'maneuver',
                    props.hasMiscellaneousMoves && 'misc',
                    props.hasSpecialMoves && 'special',
                ].filter(Boolean).join(',')}
            </span>
        </div>
    )
}));
vi.mock('./CombatLog', () => ({ default: ({ log }) => <div data-testid="combat-log">{log.map((e, i) => <div key={i}>{e.message}</div>)}</div> }));
// "Send Input" answers with an option actually offered, in the shape its
// input type gives it (ApiCombatAdapter): target cards carry an `id`, a
// direction prompt is a list of strings, and a number prompt is one dict of
// prompt/min/max/default. From a list it takes the LAST option, so a test
// offering two targets can tell "sends the picked target" from "sends the
// first one"; from a number prompt, its default.
vi.mock('./CombatInputDialog', () => ({
    default: ({ options, onSelect, onCancel, moveName, moveCategory }) => {
        const pick = () => {
            if (!Array.isArray(options)) return options?.default;
            const last = options.at(-1);
            return typeof last === 'string' ? last : last?.id;
        };
        return (
            <div data-testid="combat-input-dialog" data-move-name={moveName ?? ''} data-move-category={moveCategory ?? ''}>
                <button onClick={() => onSelect(pick())}>Send Input</button>
                <button onClick={onCancel}>Cancel Input</button>
            </div>
        );
    },
}));
vi.mock('./CombatMovePanel', () => ({
    default: ({ moves, category, onMoveClick, onClose }) => (
        <div data-testid="combat-move-panel">
            <span>{category}</span>
            {moves.map((m) => (
                <button key={m.id || m.name} onClick={() => onMoveClick(m)}>{m.name}</button>
            ))}
            <button onClick={onClose}>Close Moves</button>
        </div>
    ),
}));
vi.mock('./FeedbackDialog', () => ({ default: ({ onClose }) => <div data-testid="feedback-dialog"><button onClick={onClose}>Close Feedback</button></div> }));
vi.mock('./CooldownTray', () => ({ default: ({ moves }) => <div data-testid="cooldown-tray">{moves.length} on cooldown</div> }));
// The meter's own behaviour is covered in HeatMeter.test.jsx; here we only
// prove LeftPanel hands it the three battle_state fields it needs, since a
// silently-undefined prop is this repo's dominant bug class.
vi.mock('./HeatMeter', () => ({
    default: ({ heat, beat, combatId }) => (
        <div data-testid="heat-meter">{`${heat}|${beat}|${combatId}`}</div>
    )
}));
vi.mock('./FleeButton', () => ({ default: ({ onFlee }) => <button data-testid="flee-button" onClick={onFlee}>Flee</button> }));
vi.mock('./SuggestedMovesPanel', () => ({
    default: ({ onSuggestClick, blockedReasonFor }) => (
        <div data-testid="suggested-moves-panel">
            <button onClick={() => onSuggestClick({ move_name: 'repeat_last' })}>Repeat Last</button>
            <button onClick={() => onSuggestClick({ move_name: 'Slash', target_id: enemyId(1) })}>Suggest Slash</button>
            <span data-testid="slash-blocked-reason">{blockedReasonFor?.('Slash') || ''}</span>
        </div>
    )
}));
vi.mock('./ShopDialog', () => ({ default: ({ npcName, onClose }) => <div data-testid="shop-dialog">{npcName}<button onClick={onClose}>Close Shop</button></div> }));
vi.mock('./CombatCheckDialog', () => ({ default: ({ onClose }) => <div data-testid="combat-check-dialog"><button onClick={onClose}>Close Check</button></div> }));

// Mock useAudio
const mockPlaySFX = vi.fn();
const mockPlaySting = vi.fn();
vi.mock('../context/AudioContext', () => ({
    useAudio: () => ({
        playSFX: mockPlaySFX,
        playSting: mockPlaySting,
        playBGM: vi.fn(),
    }),
}));

const basePlayer = makePlayer({ hp: 100, max_hp: 100 });

const baseLocation = makeLocation({ name: 'Forest', description: 'Green trees.' });

/**
 * A combat object mid move-selection, in the client shape `makeCombat`
 * builds, offering `moves`. `extra` carries what a test varies (round, beat,
 * a log, ...) -- anything `makeCombat` will build, which excludes a nested
 * `battle_state`: the one test that wants that attaches it itself.
 */
const combatWith = (moves, extra = {}) => makeCombat({
    awaiting_input: true,
    input_type: 'move_selection',
    available_options: moves,
    ...extra,
});

/**
 * A combat awaiting a SERVER-driven target pick: `input_type`
 * 'target_selection', where `available_options` holds target cards rather
 * than moves. Two cards by default: the adapter enters this state only with
 * more than one viable target, and with one card the last-option mock could
 * not tell the picked target from the first.
 */
const awaitingTargetPick = (targets = twoTargets()) => makeCombat({
    awaiting_input: true,
    input_type: 'target_selection',
    available_options: targets,
});

/**
 * Lunge with two enemies in reach: a targeted move the adapter flags
 * `requires_target_selection` (it has more than one viable target), so
 * LeftPanel opens its own picker. `overrides` replace any of its fields.
 */
const lungeNeedingTarget = (overrides = {}) => makeAvailableOption({
    id: '1', name: 'Lunge', category: 'Offensive',
    targeted: true,
    viable_targets: twoTargets(),
    ...overrides,
});

/**
 * A targeted move with exactly one viable target, which the adapter therefore
 * flags `requires_target_selection: false` -- LeftPanel submits it without
 * asking. The one target is `enemyId(1)`; `overrides` replace any field.
 */
const singleTargetMove = (overrides = {}) => makeAvailableOption({
    id: '1', name: 'Slash', category: 'Offensive',
    targeted: true,
    viable_targets: [makeTargetOption({ id: enemyId(1) })],
    ...overrides,
});

/**
 * The two props every render in this file supplies. Spread rather than
 * retyped: they were spelled out at ~70 sites plus three partial extractions
 * of their own, so adding a prop the component starts requiring meant finding
 * all of them.
 */
const baseProps = { player: basePlayer, location: baseLocation };

/** The first log line every replay test seeds, before the entries it asserts on. */
const SEED_LOG_ENTRY = { message: 'Combat begins', round: 0, type: 'info' };

/**
 * The three budgets the log-replay tests run on, which have to stay ordered:
 * a wait for the seed line, a wait for the replayed lines, and vitest's own
 * per-test budget around both.
 *
 * The outer one is stated because vitest's default is 5000ms -- the same as
 * the inner wait -- so a replay test that relied on the default could never
 * reach its own waitFor, and a failure surfaced as a bare "test timed out"
 * instead of the element diff that says which line never appeared.
 */
const LOG_REVEAL_TIMEOUT = 3000;
const REPLAY_ASSERT_TIMEOUT = 5000;
const REPLAY_TEST_TIMEOUT = 10000;

/**
 * Render in combat with `SEED_LOG_ENTRY` already on the log and wait for it to
 * be revealed, then hand back a `replay(entries)` that rerenders with the seed
 * plus `entries`. Seven tests built this by hand, each restating the seed line
 * and the timeout.
 *
 * `combat` carries FIELDS merged into every payload (a hurt `player`, say),
 * not a finished one: both renders must agree about everything except the log,
 * or the replay silently resets what the first render set up.
 */
const renderWithSeededLog = async ({ combat: combatFields = {}, ...props } = {}) => {
    const withLog = (entries) =>
        makeCombat({ log: [SEED_LOG_ENTRY, ...entries], ...combatFields });
    const view = render(
        <LeftPanel {...baseProps} mode="combat" combat={withLog([])} {...props} />
    );
    await waitFor(() => {
        expect(screen.getByText(SEED_LOG_ENTRY.message)).toBeInTheDocument();
    }, { timeout: LOG_REVEAL_TIMEOUT });
    return {
        ...view,
        replay: (entries) => view.rerender(
            <LeftPanel {...baseProps} mode="combat" combat={withLog(entries)} {...props} />
        ),
    };
};

/**
 * Silence the console.error a test expects the component to emit. The
 * `afterEach` below restores it, so no test restores its own.
 */
const silenceConsoleError = () => vi.spyOn(console, 'error').mockImplementation(() => {});

/**
 * The cooldown a card's own `stage_beats` implies: the adapter ships
 * `stage_beat[3] + 1`, and makeAvailableOption's default cooldown is 4.
 */
const DEFAULT_COOLDOWN_MAX = 5;

/**
 * A move the adapter is holding back for `beats` more beats. Three of the
 * four fields follow from that number: `cooldown_remaining` and the number in
 * the sentence are one expression there (`beats_left + 1`), and a cooling
 * move is never `available`. The fourth is a maximum, which the adapter
 * raises to the remaining count when a card outlasts its own cooldown
 * (`max(stage_beat[3] + 1, cd_remaining)`) -- so it cannot be the lower of
 * the two whatever `beats` is asked for.
 */
const cooldownCard = ({ beats, ...overrides }) => makeAvailableOption({
    cooldown_remaining: beats,
    cooldown_max: Math.max(DEFAULT_COOLDOWN_MAX, beats),
    available: false,
    reason: `Available in ${beats} beats`,
    ...overrides,
});

/**
 * An untargeted Maneuver: no auto-target, no picker, so it takes the default
 * submit path. Two tests drive that path -- one on the success side, one on
 * the rejection side -- from the same card.
 */
const restCard = (overrides = {}) => makeAvailableOption({
    id: '1', name: 'Rest', category: 'Maneuver', targeted: false,
    ...overrides,
});

/**
 * The engine's Check as the adapter cards it: untargeted, free, Utility
 * (src/moves/_utility.py). `KEEP_TAB_MOVES` holds only this move, so it is
 * the one card that can exercise the instant-move branches.
 */
const checkCard = (overrides = {}) => makeAvailableOption({
    id: '1', name: 'Check', category: 'Utility',
    targeted: false, fatigue_cost: 0,
    ...overrides,
});

describe('LeftPanel', () => {
    beforeEach(() => {
        vi.clearAllMocks();
    });

    // Restores any console.error spy a test installed, whether or not that
    // test's assertions passed, so no test restores its own.
    afterEach(() => {
        if (vi.isMockFunction(console.error)) console.error.mockRestore();
    });

    it.each([
        // [mode, header, panel shown below the hero, panel hidden, HP HeroPanel shows]
        ['exploration', 'Heart of Virtue - Exploration', 'room-contents', 'combat-log', '100'],
        ['combat', 'Heart of Virtue - Combat', 'combat-log', 'room-contents', '42'],
    ])('titles the panel for %s mode and forwards the live player to HeroPanel', (mode, title, shown, hidden, hp) => {
        render(
            <LeftPanel
                {...baseProps}
                mode={mode}
                combat={makeCombat({ player: makeCombatant({ hp: 42 }) })}
            />
        );
        // The exact header string (and the absence of the other mode's), not a
        // substring match behind a `toBeDefined()`: the old check passed as
        // long as SOME node matched /Heart of Virtue - Exploration/i.
        const other = mode === 'combat' ? 'Heart of Virtue - Exploration' : 'Heart of Virtue - Combat';
        expect(screen.getByText(title)).toBeInTheDocument();
        expect(screen.queryByText(other)).toBeNull();
        // ...and the live player really reaches HeroPanel rather than the panel
        // just being present with an undefined one: the base player while
        // exploring, with the combatant payload merged over it in combat.
        expect(screen.getByTestId('hero-player-hp')).toHaveTextContent(hp);
        // Each mode swaps the lower half: room contents while exploring, the
        // combat log while fighting.
        expect(screen.getByTestId(shown)).toBeInTheDocument();
        expect(screen.queryByTestId(hidden)).toBeNull();
    });

    it('exposes a main landmark with a header/h1 for the panel title (issue #536)', () => {
        // header/main/h1 all counted zero across the app's DOM. This panel is
        // the primary narrative/actions surface, so it becomes <main>, with
        // its title bar as <header>/<h1>.
        const { container } = render(
            <LeftPanel
                {...baseProps}
                mode="exploration"
                combat={makeCombat()}
            />
        );

        const main = container.querySelector('main');
        expect(main).not.toBeNull();
        const heading = screen.getByRole('heading', { level: 1, name: 'Heart of Virtue - Exploration' });
        expect(main.contains(heading)).toBe(true);
        expect(heading.closest('header')).not.toBeNull();
    });

    /**
     * Issue #563 item 5 — with a modal open the whole exploration screen
     * behind it was still readable by a screen reader.
     *
     * The marking is what this panel owns; BaseDialog owns the hiding, and
     * BaseDialog.test.jsx covers that half. Split that way because `<main>` is
     * NOT the region to hide: LeftPanel renders its own dialogs as siblings
     * inside it, so hiding the landmark would hide the modal too. The two
     * background regions are the title bar and the content well.
     */
    describe('modal background marking (issue #563)', () => {
        const renderPanel = () => render(
            <LeftPanel {...baseProps} mode="exploration" />
        );

        it('marks the header and the content well as modal background', () => {
            const { container } = renderPanel();

            const marked = [...container.querySelectorAll('[data-modal-background]')];
            expect(marked.length).toBe(2);
            expect(marked.some((el) => el.tagName === 'HEADER')).toBe(true);
            // The content well holds the room description and the hero ring.
            expect(marked.some((el) => el.contains(screen.getByTestId('hero-panel')))).toBe(true);
        });

        it('does not mark the landmark that contains the dialogs', () => {
            // The whole reason the marker is not simply on <main>.
            const { container } = renderPanel();

            const main = container.querySelector('main');
            expect(main.hasAttribute('data-modal-background')).toBe(false);
        });

        it('hides both regions once a real dialog opens over them', () => {
            // End to end through the real BaseDialog. Every dialog this panel
            // renders is mocked at the top of this file with a plain <div>, so
            // none of them registers on the modal stack — an actual dialog has
            // to be rendered alongside for the wiring to be observable at all.
            const { container } = renderPanel();
            const marked = [...container.querySelectorAll('[data-modal-background]')];
            // Asserted before the sweeps below: `[].every()` is true, so an
            // empty list would pass every one of them without marking a thing.
            expect(marked.length).toBe(2);
            expect(marked.every((el) => !el.hasAttribute('aria-hidden'))).toBe(true);

            const dialog = render(
                <BaseDialog title="Enemy Encounter" onClose={() => { }}>
                    <button>Fight</button>
                </BaseDialog>
            );
            expect(marked.every((el) => el.getAttribute('aria-hidden') === 'true')).toBe(true);

            dialog.unmount();
            expect(marked.every((el) => !el.hasAttribute('aria-hidden'))).toBe(true);
        });
    });

    /**
     * Issue #565 polish batch — a QA pass reported the Tactical Advisor
     * "absent at 375x812", with the mobile layout going COOLDOWN -> COMBAT LOG
     * in a fight where the panel renders at 1440x900.
     *
     * IT IS NOT A BREAKPOINT. There is no viewport gate anywhere on the path:
     * LeftPanel renders the advisor on `mode === 'combat' && isMyTurn`, and
     * SuggestedMovesPanel's only early return is `if (!isPlayerTurn) return
     * null` — its mobile branch still renders the words TACTICAL ADVISOR in a
     * collapsed strip. What differs between the advisor and its two
     * neighbours is the TURN: CooldownTray and CombatLog are gated on
     * `mode === 'combat'` alone, so on the enemy's turn exactly the reported
     * DOM appears — at any width.
     *
     * These cases pin that, so the finding cannot be re-filed as a layout bug.
     */
    describe('tactical advisor turn gating (issue #565)', () => {
        const playerTurn = combatWith(
            [cooldownCard({ id: '1', name: 'Slash', beats: 2 })],
            { log: [{ message: 'Jean attacks Slime', round: 1, type: 'combat' }] },
        );
        // The enemy's turn is simply "not awaiting input".
        const enemyTurn = { ...playerTurn, awaiting_input: false };

        const renderCombat = (combat, isMobile) => render(
            <LeftPanel
                {...baseProps}
                mode="combat"
                combat={combat}
                isMobile={isMobile}
            />
        );

        it('renders the advisor at a phone width on the player\'s turn', async () => {
            renderCombat(playerTurn, true);
            expect(await screen.findByTestId('suggested-moves-panel')).toBeInTheDocument();
        });

        it('renders it at desktop width on the same turn', async () => {
            renderCombat(playerTurn, false);
            expect(await screen.findByTestId('suggested-moves-panel')).toBeInTheDocument();
        });

        it('withholds it on the enemy turn at BOTH widths, which is the real gate', async () => {
            const mobile = renderCombat(enemyTurn, true);
            await waitFor(() => expect(screen.getByTestId('cooldown-tray')).toBeInTheDocument());
            expect(screen.queryByTestId('suggested-moves-panel')).toBeNull();
            mobile.unmount();

            renderCombat(enemyTurn, false);
            await waitFor(() => expect(screen.getByTestId('cooldown-tray')).toBeInTheDocument());
            expect(screen.queryByTestId('suggested-moves-panel')).toBeNull();
        });

        it('reproduces the reported DOM — cooldown then log, no advisor — from the turn alone', async () => {
            // The exact symptom the QA pass attributed to the viewport.
            renderCombat(enemyTurn, true);

            await waitFor(() => expect(screen.getByTestId('cooldown-tray')).toBeInTheDocument());
            expect(screen.getByTestId('combat-log')).toBeInTheDocument();
            expect(screen.queryByTestId('suggested-moves-panel')).toBeNull();
        });
    });

    // Each hero-panel button owns one panel; clicking it twice must close it
    // again. The old version clicked all six in a row and only checked each
    // panel appeared — it would have passed with every button wired to the
    // SAME panel, since nothing asserted the others stayed shut or that a
    // second click closed anything.
    it.each([
        ['Status Btn', 'party-panel'],
        ['Inventory Btn', 'inventory-dialog'],
        ['Skills Btn', 'skills-panel'],
        ['Attributes Btn', 'stats-panel'],
        ['Actions Btn', 'actions-panel'],
        ['Interact Btn', 'interact-panel'],
    ])('%s opens exactly %s and toggles it shut again', (button, testId) => {
        const ALL = [
            'party-panel', 'inventory-dialog', 'skills-panel',
            'stats-panel', 'actions-panel', 'interact-panel',
        ];
        render(<LeftPanel {...baseProps} mode="exploration" />);

        fireEvent.click(screen.getByText(button));
        const open = ALL.filter((id) => screen.queryByTestId(id) !== null);
        expect(open).toEqual([testId]);

        fireEvent.click(screen.getByText(button));
        expect(screen.queryByTestId(testId)).not.toBeInTheDocument();
    });

    it('opens audio and account dialogs from header', () => {
        render(<LeftPanel {...baseProps} mode="exploration" />);

        fireEvent.click(screen.getByTitle(/^Settings$/i));
        expect(screen.getByTestId('audio-dialog')).toBeInTheDocument();
        fireEvent.click(screen.getByText('Close Aud'));
        expect(screen.queryByTestId('audio-dialog')).toBeNull();

        fireEvent.click(screen.getByText('Account'));
        expect(screen.getByTestId('account-dialog')).toBeInTheDocument();
        fireEvent.click(screen.getByText('Close Acc'));
        expect(screen.queryByTestId('account-dialog')).toBeNull();
    });

    it('opens and closes the journal from the header (issue #538)', () => {
        // The journal lives in the header rather than on the HeroPanel action
        // star so it is reachable from combat too — hence the combat-mode half.
        render(<LeftPanel {...baseProps} mode="exploration" />);

        expect(screen.queryByTestId('journal-dialog')).toBeNull();
        fireEvent.click(screen.getByRole('button', { name: 'Open journal' }));
        expect(screen.getByTestId('journal-dialog')).toBeInTheDocument();
        fireEvent.click(screen.getByText('Close Journal'));
        expect(screen.queryByTestId('journal-dialog')).toBeNull();
    });

    it('keeps the journal reachable in combat', () => {
        const combat = makeCombat();
        render(<LeftPanel {...baseProps} mode="combat" combat={combat} />);

        fireEvent.click(screen.getByRole('button', { name: 'Open journal' }));
        expect(screen.getByTestId('journal-dialog')).toBeInTheDocument();
    });

    it('closes panels when their close buttons are clicked', () => {
        render(<LeftPanel {...baseProps} mode="exploration" />);

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
        const combat = makeCombat({
            log: [
                { message: 'Jean attacks Slime', round: 1, type: 'action' },
                { message: 'Jean hit Slime for 10 damage', round: 1, type: 'result' }
            ],
            awaiting_input: true,
            input_type: 'move_selection',
        });

        render(<LeftPanel {...baseProps} mode="combat" combat={combat} />);

        expect(await screen.findByText('Jean hit Slime for 10 damage', {}, { timeout: LOG_REVEAL_TIMEOUT }))
            .toBeInTheDocument();
        // The log must render in the order the backend sent it — checking each
        // line's mere presence passes for a reversed or reordered log.
        expect(
            [...screen.getByTestId('combat-log').children].map((n) => n.textContent)
        ).toEqual(['Jean attacks Slime', 'Jean hit Slime for 10 damage']);
    });

    it('calls onMoveSubmitted when a target is selected via CombatInputDialog', async () => {
        const onMoveSubmitted = vi.fn()
        const onCombatAction = vi.fn().mockResolvedValue({})
        const combat = awaitingTargetPick()
        render(
            <LeftPanel
                {...baseProps}
                mode="combat"
                combat={combat}
                onMoveSubmitted={onMoveSubmitted}
                onCombatAction={onCombatAction}
            />
        )
        await screen.findByTestId('combat-input-dialog', {}, { timeout: LOG_REVEAL_TIMEOUT })
        fireEvent.click(screen.getByText('Send Input'))
        await waitFor(() => {
            expect(onMoveSubmitted).toHaveBeenCalledTimes(1)
        }, { timeout: 1000 })
        // The selection must actually reach the API as a `target` command with
        // the chosen id — a bare "onMoveSubmitted fired" check passes even when
        // the wrong target, or nothing at all, is sent to the server.
        expect(onCombatAction).toHaveBeenCalledWith('target', { target_id: enemyId(2) })
    })

    it('renders nothing when player is not yet loaded', () => {
        const { container } = render(<LeftPanel player={null} location={baseLocation} mode="exploration" />);
        expect(container.firstChild).toBeNull();
    });

    it('opens and closes the feedback dialog', () => {
        render(<LeftPanel {...baseProps} mode="exploration" />);
        fireEvent.click(screen.getByText('Feedback'));
        expect(screen.getByTestId('feedback-dialog')).toBeInTheDocument();
        fireEvent.click(screen.getByText('Close Feedback'));
        expect(screen.queryByTestId('feedback-dialog')).not.toBeInTheDocument();
    });

    it('toggles the interact panel closed when the main interact button is clicked again', () => {
        render(<LeftPanel {...baseProps} mode="exploration" />);
        fireEvent.click(screen.getByText('Interact Btn'));
        expect(screen.getByTestId('interact-panel')).toBeInTheDocument();
        fireEvent.click(screen.getByText('Interact Btn'));
        expect(screen.queryByTestId('interact-panel')).not.toBeInTheDocument();
    });

    it('opens the interact panel with a specific target from the room description', () => {
        render(<LeftPanel {...baseProps} mode="exploration" />);
        fireEvent.click(screen.getByText('Interact With Lever'));
        expect(screen.getByText('target:a rusty lever')).toBeInTheDocument();
    });

    it('closes inventory when skills is opened and vice versa', () => {
        render(<LeftPanel {...baseProps} mode="exploration" />);
        fireEvent.click(screen.getByText('Inventory Btn'));
        expect(screen.getByTestId('inventory-dialog')).toBeInTheDocument();

        fireEvent.click(screen.getByText('Skills Btn'));
        expect(screen.getByTestId('skills-panel')).toBeInTheDocument();
        expect(screen.queryByTestId('inventory-dialog')).not.toBeInTheDocument();
    });

    it('opens the shop dialog via InteractPanel and closes it', () => {
        render(<LeftPanel {...baseProps} mode="exploration" />);
        fireEvent.click(screen.getByText('Interact Btn'));
        fireEvent.click(screen.getByText('Open Shop'));

        expect(screen.queryByTestId('interact-panel')).not.toBeInTheDocument();
        expect(screen.getByTestId('shop-dialog')).toBeInTheDocument();
        expect(screen.getByText('Jambo')).toBeInTheDocument();

        fireEvent.click(screen.getByText('Close Shop'));
        expect(screen.queryByTestId('shop-dialog')).not.toBeInTheDocument();
    });

    it('shows the cooldown tray when moves are on cooldown in combat', () => {
        const combat = combatWith([
            cooldownCard({ id: '1', name: 'Slash', category: 'Offensive', beats: 2 }),
            makeAvailableOption({ id: '2', name: 'Guard', category: 'Defensive', cooldown_remaining: 0 }),
        ]);
        render(<LeftPanel {...baseProps} mode="combat" combat={combat} />);
        expect(screen.getByTestId('cooldown-tray')).toHaveTextContent('1 on cooldown');
    });

    it('feeds the heat meter the player heat, beat and fight id from battle_state', () => {
        // These are the exact keys the serializer emits: `player.heat` is the
        // raw float multiplier (CombatantSerializer), NOT battle_state's own
        // `heat` (which is round(heat*100) and absent from beat states).
        const combat = makeCombat({ beat: 7, combat_id: 'fight-0001', player: makeCombatant({ heat: 1.62 }) });
        render(<LeftPanel {...baseProps} mode="combat" combat={combat} />);
        expect(screen.getByTestId('heat-meter')).toHaveTextContent('1.62|7|fight-0001');
    });

    it('hides the heat meter outside combat', () => {
        render(<LeftPanel {...baseProps} mode="exploration" combat={makeCombat()} />);
        expect(screen.queryByTestId('heat-meter')).toBeNull();
    });

    it('shows the flee button once every enemy is at the break-away distance', () => {
        const combat = makeCombat({
            awaiting_input: true,
            enemies: [makeEnemy({ distance: FLEE_BREAK_AWAY_DISTANCE_FT + 5 })],
        });
        const onCombatAction = vi.fn();
        render(<LeftPanel {...baseProps} mode="combat" combat={combat} onCombatAction={onCombatAction} />);
        fireEvent.click(screen.getByTestId('flee-button'));
        expect(onCombatAction).toHaveBeenCalledWith('flee', {});
    });

    it('does not show the flee button when an enemy is too close', () => {
        const combat = makeCombat({
            awaiting_input: true,
            enemies: [makeEnemy({ distance: FLEE_BREAK_AWAY_DISTANCE_FT - 1 })],
        });
        render(<LeftPanel {...baseProps} mode="combat" combat={combat} />);
        expect(screen.queryByTestId('flee-button')).not.toBeInTheDocument();
    });

    // Defensive: `serialize_combatant` emits `distance` unconditionally and
    // `_get_distance` falls back to 0 rather than omitting it, so the server
    // never sends this payload. Pinned so a truncated one reads as "adjacent"
    // -- refusing the flee -- instead of as "far enough to run".
    it('treats an enemy with no distance field as too close to flee (defaults to 0)', () => {
        const { distance: _distance, ...enemyWithoutDistance } = makeEnemy();
        const combat = makeCombat({ awaiting_input: true, enemies: [enemyWithoutDistance] });
        render(<LeftPanel {...baseProps} mode="combat" combat={combat} />);
        expect(screen.queryByTestId('flee-button')).not.toBeInTheDocument();
    });

    it('merges combat.player onto the base player for the hero panel', () => {
        const combat = makeCombat({ awaiting_input: true, player: makeCombatant({ hp: 42 }) });
        render(<LeftPanel {...baseProps} mode="combat" combat={combat} />);
        expect(screen.getByTestId('hero-player-hp')).toHaveTextContent('42');
    });

    it('opens the move panel for a category and toggles it closed on re-click', () => {
        const combat = combatWith([makeAvailableOption({ id: '1', name: 'Slash', category: 'Offensive' })]);
        render(<LeftPanel {...baseProps} mode="combat" combat={combat} />);

        fireEvent.click(screen.getByText('Offensive Btn'));
        expect(screen.getByTestId('combat-move-panel')).toBeInTheDocument();

        fireEvent.click(screen.getByText('Offensive Btn'));
        expect(screen.queryByTestId('combat-move-panel')).not.toBeInTheDocument();
    });

    // ---- move-category -> radial-button routing -------------------------------
    // CATEGORY_GROUPS (utils/categories.js) is the SINGLE source of truth for
    // which button a move appears under. It was once duplicated inside
    // LeftPanel and CombatMovePanel and drifted, leaving 8 castable moves with
    // no button at all. These cases are generated FROM the map, so adding a
    // category to it without teaching LeftPanel about it fails here rather than
    // shipping an unreachable move. (utils/categories.consumers.test.jsx guards
    // the other half: that the button and the panel agree.)

    /** Group key -> the token HeroPanel's `hasXMoves` flag renders as. */
    const FLAG_FOR_GROUP = {
        Offensive: 'offensive',
        Defensive: 'defensive',
        Maneuver: 'maneuver',
        Miscellaneous: 'misc',
        Special: 'special',
    };

    /** Every (group, engine category) pair the shared map declares. */
    const GROUP_CATEGORY_PAIRS = Object.entries(CATEGORY_GROUPS).flatMap(
        ([group, categories]) => categories.map((category) => [group, category])
    );

    it('has a hero-panel flag for every group the shared category map declares', () => {
        // Guards the table above against CATEGORY_GROUPS growing a group that
        // no button knows about — which is precisely how the original 8 moves
        // became unreachable.
        expect(Object.keys(FLAG_FOR_GROUP).sort()).toEqual(Object.keys(CATEGORY_GROUPS).sort());
    });

    it.each(GROUP_CATEGORY_PAIRS)(
        'lights ONLY the %s button for a %s move',
        (group, category) => {
            render(
                <LeftPanel
                    player={basePlayer}
                    location={baseLocation}
                    mode="combat"
                    combat={combatWith([makeAvailableOption({ id: '1', name: `A ${category} move`, category })])}
                />
            );
            // Exactly one flag: zero means the move has no button at all, two
            // means it is double-listed.
            const flags = screen.getByTestId('hero-flags').textContent.split(',').filter(Boolean);
            expect(flags).toEqual([FLAG_FOR_GROUP[group]]);
        }
    );

    it('lights every button at once when one move of each mapped category is available', () => {
        const moves = GROUP_CATEGORY_PAIRS.map(([, category], i) =>
            makeAvailableOption({ id: String(i), name: `Move ${i}`, category })
        );
        render(
            <LeftPanel {...baseProps} mode="combat" combat={combatWith(moves)} />
        );
        // HeroPanel renders the flags in a fixed order, so compare as a set.
        const flags = screen.getByTestId('hero-flags').textContent.split(',').filter(Boolean);
        expect(new Set(flags)).toEqual(new Set(Object.values(FLAG_FOR_GROUP)));
    });

    it('shows no category buttons for a category the shared map does not claim', () => {
        // `Passive` moves are never castable, so they must reach no button.
        render(
            <LeftPanel
                {...baseProps}
                mode="combat"
                combat={combatWith([makeAvailableOption({ id: '1', name: 'Iron Fist', category: 'Passive' })])}
            />
        );
        expect(screen.getByTestId('hero-flags')).toHaveTextContent('');
    });

    it('tolerates a nameless move while still routing it by category', () => {
        render(
            <LeftPanel
                {...baseProps}
                mode="combat"
                combat={combatWith([makeAvailableOption({ id: '1', name: undefined, category: 'Tactical' })])}
            />
        );
        expect(screen.getByTestId('hero-flags')).toHaveTextContent('misc');
    });

    it('shows no category buttons at all outside combat mode', () => {
        // hasGroup() is gated on mode === 'combat'; cached moves must not leak
        // combat buttons into exploration.
        render(
            <LeftPanel
                {...baseProps}
                mode="exploration"
                combat={combatWith([makeAvailableOption({ id: '1', name: 'Slash', category: 'Offensive' })])}
            />
        );
        expect(screen.getByTestId('hero-flags')).toHaveTextContent('');
    });

    // transformCombatData (utils/combatTransform.js) spreads battle_state flat
    // onto the combat object, so a nested battle_state never reaches this
    // component.
    it('reads moves from the flattened combat shape, not a nested battle_state', () => {
        // Attached outside makeCombat, which throws on a `battle_state`
        // override: no response carries one, and building the impossible
        // shape is this test's whole point.
        const combat = {
            ...combatWith([makeAvailableOption({ id: '1', name: 'Slash', category: 'Offensive' })]),
            battle_state: { available_options: [makeAvailableOption({ id: '2', name: 'Reap', category: 'Offensive' })] },
        };
        render(<LeftPanel {...baseProps} mode="combat" combat={combat} />);
        fireEvent.click(screen.getByText('Offensive Btn'));
        expect(screen.getByText('Slash')).toBeInTheDocument();
        expect(screen.queryByText('Reap')).not.toBeInTheDocument();
    });

    it('excludes the UseItem and "Use Item" moves from the combat move panel, and tolerates a nameless move', () => {
        const combat = combatWith([
            makeAvailableOption({ id: '1', name: 'Slash', category: 'Offensive' }),
            makeAvailableOption({ id: '2', name: 'UseItem', category: 'Offensive' }),
            makeAvailableOption({ id: '3', name: 'Use Item', category: 'Offensive' }),
            makeAvailableOption({ id: '4', name: undefined, category: 'Offensive' }),
        ]);
        render(<LeftPanel {...baseProps} mode="combat" combat={combat} />);
        fireEvent.click(screen.getByText('Offensive Btn'));
        expect(screen.getByText('Slash')).toBeInTheDocument();
        expect(screen.queryByText('UseItem')).not.toBeInTheDocument();
        expect(screen.queryByText('Use Item')).not.toBeInTheDocument();
    });

    // HeroPanel's base bounding box is 360x310; the wrapper scales by
    // min(width/360, height/310), clamped to [0.4, 2.8].
    const withContainerSize = (width, height, fn) => {
        const originalRect = Element.prototype.getBoundingClientRect;
        Element.prototype.getBoundingClientRect = () => ({
            width, height, top: 0, left: 0, right: 0, bottom: 0, x: 0, y: 0, toJSON() {},
        });
        try {
            fn();
        } finally {
            Element.prototype.getBoundingClientRect = originalRect;
        }
    };
    /** The wrapper <div> that carries the computed transform. */
    const heroScale = () =>
        screen.getByTestId('hero-panel').parentElement.style.transform;

    it.each([
        // [width, height, expected transform]
        // 720/360 = 2 and 620/310 = 2 — both axes agree.
        [720, 620, 'scale(2)'],
        // Fit uses the SMALLER axis: 720/360 = 2 but 465/310 = 1.5.
        [720, 465, 'scale(1.5)'],
        // Clamped to the 2.8 ceiling (raw would be 4).
        [1440, 1240, 'scale(2.8)'],
        // Clamped to the 0.4 floor (raw would be 0.25).
        [90, 77.5, 'scale(0.4)'],
    ])('scales the hero panel to fit a %sx%s container', (w, h, expected) => {
        withContainerSize(w, h, () => {
            render(<LeftPanel {...baseProps} mode="exploration" />);
            expect(heroScale()).toBe(expected);
        });
    });

    it('leaves the hero panel unscaled when the container reports zero bounds', () => {
        // A pre-layout measurement must not collapse the panel to the 0.4 floor.
        withContainerSize(0, 0, () => {
            render(<LeftPanel {...baseProps} mode="exploration" />);
            expect(heroScale()).toBe('scale(1)');
        });
    });

    // issue #542: HeroPanel counter-scales its own radial buttons by
    // 1/heroScale on mobile so a squeezed combat layout doesn't shrink their
    // effective touch target below 44px. That compensation only works if the
    // real computed scale factor actually reaches HeroPanel as a prop, not
    // just as the wrapper's own CSS transform.
    it('forwards the computed heroScale number to HeroPanel, matching the wrapper transform', () => {
        withContainerSize(720, 465, () => {
            render(<LeftPanel {...baseProps} mode="exploration" />);
            expect(heroScale()).toBe('scale(1.5)');
            expect(screen.getByTestId('hero-scale')).toHaveTextContent('1.5');
        });
    });

    it('auto-selects the single viable target for a targeted move without requiring selection', async () => {
        const onCombatAction = vi.fn().mockResolvedValue({});
        const onMoveSubmitted = vi.fn();
        const combat = combatWith([singleTargetMove()]);
        render(
            <LeftPanel
                {...baseProps} mode="combat" combat={combat}
                onCombatAction={onCombatAction} onMoveSubmitted={onMoveSubmitted}
            />
        );
        fireEvent.click(screen.getByText('Offensive Btn'));
        fireEvent.click(screen.getByText('Slash'));

        await waitFor(() => {
            expect(onCombatAction).toHaveBeenCalledWith('select_move_and_target', {
                move_name: 'Slash', target_id: enemyId(1),
            });
        });
        // Submitting a move flips the mobile view to the battlefield tab.
        expect(onMoveSubmitted).toHaveBeenCalledTimes(1);
    });

    it('does not notify onMoveSubmitted for instant/non-turn-consuming moves', async () => {
        const onCombatAction = vi.fn().mockResolvedValue({});
        const onMoveSubmitted = vi.fn();
        // Untargeted means no auto-target and no picker, so a real Check
        // takes the DEFAULT submit path -- which had no coverage at all while
        // this fixture claimed `targeted: true`.
        const combat = combatWith([checkCard()]);
        render(
            <LeftPanel
                {...baseProps} mode="combat" combat={combat}
                onCombatAction={onCombatAction} onMoveSubmitted={onMoveSubmitted}
            />
        );
        fireEvent.click(screen.getByText('Miscellaneous Btn'));
        fireEvent.click(screen.getByText('Check'));

        await waitFor(() => {
            // By id, the default flow's payload -- asserting it catches a
            // wrong move_id, which a bare toHaveBeenCalled() would wave through.
            expect(onCombatAction).toHaveBeenCalledWith('move', { move_id: '1' });
        });
        // ...and it does NOT flip the mobile view to the battlefield.
        expect(onMoveSubmitted).not.toHaveBeenCalled();
    });

    // Defensive: KEEP_TAB_MOVES holds only 'Check', and the engine's Check is
    // untargeted, so no card can be both instant and auto-targetable. Pinned
    // because the auto-target path carries its own copy of the notify guard,
    // and nothing else would fail if that copy stopped checking.
    it('does not notify onMoveSubmitted when an instant move auto-resolves a target', async () => {
        const onCombatAction = vi.fn().mockResolvedValue({});
        const onMoveSubmitted = vi.fn();
        // Only the targeting is impossible; the rest is the real card.
        const combat = combatWith([checkCard({
            targeted: true,
            viable_targets: [makeTargetOption({ id: enemyId(1) })],
        })]);
        render(
            <LeftPanel
                {...baseProps} mode="combat" combat={combat}
                onCombatAction={onCombatAction} onMoveSubmitted={onMoveSubmitted}
            />
        );
        fireEvent.click(screen.getByText('Miscellaneous Btn'));
        fireEvent.click(screen.getByText('Check'));

        await waitFor(() => {
            expect(onCombatAction).toHaveBeenCalledWith('select_move_and_target', {
                move_name: 'Check', target_id: enemyId(1),
            });
        });
        expect(onMoveSubmitted).not.toHaveBeenCalled();
    });

    it('ignores clicks on an unavailable move', () => {
        const onCombatAction = vi.fn();
        // Every unavailable branch of _get_available_moves assigns a reason,
        // so `available: false` with a null one is a card it cannot send.
        const combat = combatWith([makeAvailableOption({
            id: '1', name: 'Slash', category: 'Offensive',
            available: false, reason: NOT_ENOUGH_FATIGUE_REASON,
        })]);
        render(<LeftPanel {...baseProps} mode="combat" combat={combat} onCombatAction={onCombatAction} />);
        fireEvent.click(screen.getByText('Offensive Btn'));
        fireEvent.click(screen.getByText('Slash'));
        expect(onCombatAction).not.toHaveBeenCalled();
    });

    it('opens a local target-selection dialog for moves that require it', () => {
        const combat = combatWith([lungeNeedingTarget()]);
        render(<LeftPanel {...baseProps} mode="combat" combat={combat} />);
        fireEvent.click(screen.getByText('Offensive Btn'));
        fireEvent.click(screen.getByText('Lunge'));
        expect(screen.getByTestId('combat-input-dialog')).toBeInTheDocument();
    });

    // Issue #535 sub-item 2: CombatInputDialog needs the move's own name/
    // category to label its confirm button correctly (STRIKE only for a
    // genuine attack) instead of a fixed "STRIKE" for every move.
    it('forwards the selected move\'s name and category to the target-selection dialog', () => {
        const combat = combatWith([makeAvailableOption({
            id: '1', name: 'Advance', category: 'Maneuver',
            targeted: true,
            viable_targets: [makeTargetOption(), makeTargetOption({ id: allyId(1), name: 'Gorran', is_ally: true })],
        })]);
        render(<LeftPanel {...baseProps} mode="combat" combat={combat} />);
        fireEvent.click(screen.getByText('Maneuver Btn'));
        fireEvent.click(screen.getByText('Advance'));

        const dialog = screen.getByTestId('combat-input-dialog');
        expect(dialog.getAttribute('data-move-name')).toBe('Advance');
        expect(dialog.getAttribute('data-move-category')).toBe('Maneuver');
    });

    // Issue #535 sub-item 5 (optional cleanup): CombatMovePanel and
    // CombatInputDialog are independently absolutely-positioned over the same
    // screen region, so leaving the move panel mounted while the target
    // dialog is open reads as (and, per the a11y tree, nests as) one control
    // overlapping the other. The completion branch (handleInputSelection)
    // already closes the move panel; the opening branch did not.
    it('hides the combat move panel once the local target-selection dialog opens', () => {
        const combat = combatWith([lungeNeedingTarget()]);
        render(<LeftPanel {...baseProps} mode="combat" combat={combat} />);
        fireEvent.click(screen.getByText('Offensive Btn'));
        expect(screen.getByTestId('combat-move-panel')).toBeInTheDocument();

        fireEvent.click(screen.getByText('Lunge'));
        expect(screen.getByTestId('combat-input-dialog')).toBeInTheDocument();
        expect(screen.queryByTestId('combat-move-panel')).not.toBeInTheDocument();
    });

    it('sends the local target selection and clears it on success', async () => {
        const onCombatAction = vi.fn().mockResolvedValue({});
        const combat = combatWith([lungeNeedingTarget()]);
        render(<LeftPanel {...baseProps} mode="combat" combat={combat} onCombatAction={onCombatAction} />);
        fireEvent.click(screen.getByText('Offensive Btn'));
        fireEvent.click(screen.getByText('Lunge'));
        fireEvent.click(screen.getByText('Send Input'));

        // The mock picks the second of the two targets, so this is the one
        // picked, not merely the first one offered.
        await waitFor(() => {
            expect(onCombatAction).toHaveBeenCalledWith('select_move_and_target', {
                move_name: 'Lunge', target_id: enemyId(2),
            });
        });
        await waitFor(() => {
            expect(screen.queryByTestId('combat-input-dialog')).not.toBeInTheDocument();
        });
    });

    it('cancels a local target-selection dialog without calling the API', () => {
        const onCombatAction = vi.fn();
        const combat = combatWith([lungeNeedingTarget()]);
        render(<LeftPanel {...baseProps} mode="combat" combat={combat} onCombatAction={onCombatAction} />);
        fireEvent.click(screen.getByText('Offensive Btn'));
        fireEvent.click(screen.getByText('Lunge'));
        fireEvent.click(screen.getByText('Cancel Input'));

        expect(screen.queryByTestId('combat-input-dialog')).not.toBeInTheDocument();
        expect(onCombatAction).not.toHaveBeenCalled();
    });

    // The clearing effect used to key on turn_number/combat_id, neither of which
    // exists on the client combat object — so a picker outlived its own turn.
    it('closes a stale local target picker when the beat advances', () => {
        const combat = combatWith([lungeNeedingTarget()], { round: 1, beat: 1 });
        const { rerender } = render(
            <LeftPanel {...baseProps} mode="combat" combat={combat} />
        );
        fireEvent.click(screen.getByText('Offensive Btn'));
        fireEvent.click(screen.getByText('Lunge'));
        expect(screen.getByTestId('combat-input-dialog')).toBeInTheDocument();

        rerender(
            <LeftPanel
                {...baseProps}
                mode="combat"
                combat={{ ...combat, beat: 2, awaiting_input: false }}
            />
        );
        expect(screen.queryByTestId('combat-input-dialog')).not.toBeInTheDocument();
    });

    it('closes a stale local target picker when the round advances', () => {
        const combat = combatWith([lungeNeedingTarget()], { round: 1, beat: 3 });
        const { rerender } = render(
            <LeftPanel {...baseProps} mode="combat" combat={combat} />
        );
        fireEvent.click(screen.getByText('Offensive Btn'));
        fireEvent.click(screen.getByText('Lunge'));
        expect(screen.getByTestId('combat-input-dialog')).toBeInTheDocument();

        rerender(
            <LeftPanel
                {...baseProps}
                mode="combat"
                combat={{ ...combat, round: 2, awaiting_input: false }}
            />
        );
        expect(screen.queryByTestId('combat-input-dialog')).not.toBeInTheDocument();
    });

    // Defensive: the adapter sets requires_target_selection only when a move
    // has two or more viable targets, so the server never sends this payload.
    // Pinned so a flagged move arriving with an empty list still opens the
    // picker rather than crashing LeftPanel.
    it('still opens the target picker for a flagged move whose target list is empty', () => {
        // The flag is spelled out because the builder derives it from the
        // target list, and this payload's whole point is that the two disagree.
        const combat = combatWith([
            lungeNeedingTarget({ viable_targets: [], requires_target_selection: true }),
        ]);
        render(<LeftPanel {...baseProps} mode="combat" combat={combat} />);
        fireEvent.click(screen.getByText('Offensive Btn'));
        fireEvent.click(screen.getByText('Lunge'));
        expect(screen.getByTestId('combat-input-dialog')).toBeInTheDocument();
    });

    it('logs an error and resets pending state when auto-target selection fails', async () => {
        const errorSpy = silenceConsoleError();
        const onCombatAction = vi.fn().mockRejectedValue(new Error('network down'));
        const combat = combatWith([singleTargetMove()]);
        render(<LeftPanel {...baseProps} mode="combat" combat={combat} onCombatAction={onCombatAction} />);
        fireEvent.click(screen.getByText('Offensive Btn'));
        fireEvent.click(screen.getByText('Slash'));

        await waitFor(() => {
            expect(errorSpy).toHaveBeenCalledWith('Failed to auto-select target:', expect.any(Error));
        });
    });

    it('executes a non-targeted move via the default flow', async () => {
        const onCombatAction = vi.fn().mockResolvedValue({});
        const combat = combatWith([restCard()]);
        render(<LeftPanel {...baseProps} mode="combat" combat={combat} onCombatAction={onCombatAction} />);
        fireEvent.click(screen.getByText('Maneuver Btn'));
        fireEvent.click(screen.getByText('Rest'));

        await waitFor(() => {
            expect(onCombatAction).toHaveBeenCalledWith('move', { move_id: '1' });
        });
    });

    it('logs an error and does not crash when move execution rejects', async () => {
        const errorSpy = silenceConsoleError();
        const onCombatAction = vi.fn().mockRejectedValue(new Error('server error'));
        const combat = combatWith([restCard()]);
        render(<LeftPanel {...baseProps} mode="combat" combat={combat} onCombatAction={onCombatAction} />);
        fireEvent.click(screen.getByText('Maneuver Btn'));
        fireEvent.click(screen.getByText('Rest'));

        await waitFor(() => {
            expect(errorSpy).toHaveBeenCalledWith('Failed to execute move:', expect.any(Error));
        });
    });

    it('sends a direction selection through the combat input dialog', async () => {
        const onCombatAction = vi.fn().mockResolvedValue({});
        const combat = makeCombat({
            awaiting_input: true,
            input_type: 'direction_selection',
            available_options: TURN_DIRECTIONS,
        });
        render(<LeftPanel {...baseProps} mode="combat" combat={combat} onCombatAction={onCombatAction} />);
        await waitFor(() => screen.getByTestId('combat-input-dialog'));
        fireEvent.click(screen.getByText('Send Input'));
        // The last direction offered, which the mock picks.
        await waitFor(() => {
            expect(onCombatAction).toHaveBeenCalledWith('direction', { direction: 'west' });
        });
    });

    it('sends a number input through the combat input dialog', async () => {
        const onCombatAction = vi.fn().mockResolvedValue({});
        const combat = makeCombat({
            awaiting_input: true,
            input_type: 'number_input',
            available_options: WAIT_DURATION_PROMPT,
        });
        render(<LeftPanel {...baseProps} mode="combat" combat={combat} onCombatAction={onCombatAction} />);
        await waitFor(() => screen.getByTestId('combat-input-dialog'));
        fireEvent.click(screen.getByText('Send Input'));
        // The prompt's default, which the mock picks.
        await waitFor(() => {
            expect(onCombatAction).toHaveBeenCalledWith('number', { value: 5 });
        });
    });

    it('cancels the backend-driven input dialog and notifies the API', async () => {
        const onCombatAction = vi.fn().mockResolvedValue({});
        const combat = awaitingTargetPick();
        render(<LeftPanel {...baseProps} mode="combat" combat={combat} onCombatAction={onCombatAction} />);
        await waitFor(() => screen.getByTestId('combat-input-dialog'));
        fireEvent.click(screen.getByText('Cancel Input'));
        expect(onCombatAction).toHaveBeenCalledWith('cancel', {});
    });

    it('logs an error when sending backend input fails', async () => {
        const errorSpy = silenceConsoleError();
        const onCombatAction = vi.fn().mockRejectedValue(new Error('boom'));
        const combat = awaitingTargetPick();
        render(<LeftPanel {...baseProps} mode="combat" combat={combat} onCombatAction={onCombatAction} />);
        await waitFor(() => screen.getByTestId('combat-input-dialog'));
        fireEvent.click(screen.getByText('Send Input'));
        await waitFor(() => {
            expect(errorSpy).toHaveBeenCalledWith('Failed to send input:', expect.any(Error));
        });
    });

    it('shows the suggested moves panel and repeats the last move by name', () => {
        const onCombatAction = vi.fn();
        const combat = makeCombat({
            awaiting_input: true,
            last_move_name: 'Slash',
            last_move_target_id: enemyId(1),
        });
        render(<LeftPanel {...baseProps} mode="combat" combat={combat} onCombatAction={onCombatAction} />);
        fireEvent.click(screen.getByText('Repeat Last'));
        expect(onCombatAction).toHaveBeenCalledWith('select_move_and_target', {
            move_name: 'Slash', target_id: enemyId(1),
        });
    });

    it('falls back to the first suggested move when repeating with no last move on record', () => {
        const onCombatAction = vi.fn();
        const combat = makeCombat({
            awaiting_input: true,
            suggested_moves: [makeSuggestedMove({ move_name: 'Guard', target_id: enemyId(2) })],
        });
        render(<LeftPanel {...baseProps} mode="combat" combat={combat} onCombatAction={onCombatAction} />);
        fireEvent.click(screen.getByText('Repeat Last'));
        expect(onCombatAction).toHaveBeenCalledWith('select_move_and_target', {
            move_name: 'Guard', target_id: enemyId(2),
        });
    });

    it('dispatches a directly-suggested move', () => {
        const onCombatAction = vi.fn();
        const combat = makeCombat({ awaiting_input: true });
        render(<LeftPanel {...baseProps} mode="combat" combat={combat} onCombatAction={onCombatAction} />);
        fireEvent.click(screen.getByText('Suggest Slash'));
        expect(onCombatAction).toHaveBeenCalledWith('select_move_and_target', {
            move_name: 'Slash', target_id: enemyId(1),
        });
    });

    it('refuses to dispatch a suggested move the server has marked unavailable', () => {
        // Issue #505. The advisor suggested `Attack` with fatigue drained while
        // `available_options` reported it `available:false`; the click POSTed a
        // move the server answered 200 `success:false` — no state change, no
        // error, which reads as a dead button. The availability was already on
        // the wire; the panel just never looked at it.
        const onCombatAction = vi.fn();
        const combat = combatWith([
            makeAvailableOption({ id: '0', name: 'Slash', available: false, reason: NOT_ENOUGH_FATIGUE_REASON }),
            makeAvailableOption({ id: '1', name: 'Guard' }),
        ]);
        render(<LeftPanel {...baseProps} mode="combat" combat={combat} onCombatAction={onCombatAction} />);

        expect(screen.getByTestId('slash-blocked-reason')).toHaveTextContent(NOT_ENOUGH_FATIGUE_REASON);
        fireEvent.click(screen.getByText('Suggest Slash'));
        expect(onCombatAction).not.toHaveBeenCalled();
    });

    it('dispatches a suggested move the server reports as available', () => {
        const onCombatAction = vi.fn();
        const combat = combatWith([makeAvailableOption({ id: '0', name: 'Slash' })]);
        render(<LeftPanel {...baseProps} mode="combat" combat={combat} onCombatAction={onCombatAction} />);

        expect(screen.getByTestId('slash-blocked-reason')).toHaveTextContent('');
        fireEvent.click(screen.getByText('Suggest Slash'));
        expect(onCombatAction).toHaveBeenCalledWith('select_move_and_target', {
            move_name: 'Slash', target_id: enemyId(1),
        });
    });

    it('skips an unavailable first suggestion when repeating with no last move on record', () => {
        const onCombatAction = vi.fn();
        const combat = combatWith(
            [
                // On cooldown, not "not ready yet" -- that string is the
                // /move route's error body, never a card's `reason`.
                cooldownCard({ id: '0', name: 'Guard', beats: 2 }),
                makeAvailableOption({ id: '1', name: 'Slash' }),
            ],
            {
                suggested_moves: [
                    makeSuggestedMove({ move_name: 'Guard', target_id: enemyId(2) }),
                    makeSuggestedMove({ move_name: 'Slash', target_id: enemyId(1) }),
                ],
            },
        );
        render(<LeftPanel {...baseProps} mode="combat" combat={combat} onCombatAction={onCombatAction} />);
        fireEvent.click(screen.getByText('Repeat Last'));
        expect(onCombatAction).toHaveBeenCalledWith('select_move_and_target', {
            move_name: 'Slash', target_id: enemyId(1),
        });
    });

    it('shows the check dialog when the backend sends check_data and closes it', () => {
        const combat = makeCombat({ check_data: [makeCheckEntry()] });
        render(<LeftPanel {...baseProps} mode="combat" combat={combat} />);
        expect(screen.getByTestId('combat-check-dialog')).toBeInTheDocument();
        fireEvent.click(screen.getByText('Close Check'));
        expect(screen.queryByTestId('combat-check-dialog')).not.toBeInTheDocument();
    });

    /**
     * The log reveals one line at a time, so every test here seeds a line,
     * waits for it, then replays more on top -- `renderWithSeededLog` above.
     * Grouped so that shared shape, and the timeout budgets it runs on, are
     * scoped to the tests that actually use them.
     */
    describe('combat log replay', () => {
        // The log-replay tests below build their combat through `makeCombat`,
        // like every other fixture here, even though useCombatLogPlayback reads
        // only `log` and `combat_id`: a bare `{ log }` object is a shape
        // transformCombatData can never produce. LeftPanel merges `combat.player`
        // over the `player` prop and the hook reads the merge, so the low-health
        // case hands its hurt combatant to `makeCombat` rather than to the prop.
        it('plays SFX cues that correspond to log message keywords', async () => {
            // The very first batch of log lines a mount ever sees is treated as
            // page-reload recovery (displayed instantly, no SFX) — seed one line
            // first, then rerender with the real lines under test so they go
            // through the normal (SFX-playing) path instead.
            const { replay } = await renderWithSeededLog();

            replay([
                { message: 'Jean attacks Slime', round: 1, type: 'action' },
                { message: 'Jean hit Slime for 10 damage', round: 1, type: 'result' },
                { message: 'Jean missed the strike', round: 1, type: 'result' },
                { message: 'Jean parries the blow', round: 1, type: 'result' },
                { message: 'Slime was defeated', round: 1, type: 'result' },
                { message: 'Jean is poisoned', round: 1, type: 'status' },
                { message: 'Jean uses a Potion', round: 1, type: 'item' },
                { message: 'Jean quest complete', round: 1, type: 'quest' },
            ]);

            await waitFor(() => {
                expect(screen.getByText('Jean quest complete')).toBeInTheDocument();
                // Eight cues, revealed one at a time: the only replay in this
                // file that needs more than REPLAY_ASSERT_TIMEOUT.
            }, { timeout: 8000 });

            expect(mockPlaySFX).toHaveBeenCalledWith('attack_swipe');
            expect(mockPlaySFX).toHaveBeenCalledWith('attack_hit');
            expect(mockPlaySFX).toHaveBeenCalledWith('attack_miss');
            expect(mockPlaySFX).toHaveBeenCalledWith('attack_parry');
            expect(mockPlaySFX).toHaveBeenCalledWith('enemy_death');
            expect(mockPlaySFX).toHaveBeenCalledWith('status_hit');
            expect(mockPlaySFX).toHaveBeenCalledWith('item_use');
            expect(mockPlaySFX).toHaveBeenCalledWith('quest_complete');
        }, REPLAY_TEST_TIMEOUT);

        it('plays a heal SFX and notifies onLogProgress/onLogProcessingChange/onDisplayedLogCountChange', async () => {
            const onLogProgress = vi.fn();
            const onLogProcessingChange = vi.fn();
            const onDisplayedLogCountChange = vi.fn();
            const { replay } = await renderWithSeededLog({
                onLogProgress,
                onLogProcessingChange,
                onDisplayedLogCountChange,
            });

            replay([
                { message: 'Jean restores 20 HP', round: 1, type: 'result', beat_index: 3 },
            ]);

            await waitFor(() => {
                expect(mockPlaySFX).toHaveBeenCalledWith('heal');
            }, { timeout: REPLAY_ASSERT_TIMEOUT });
            expect(onLogProgress).toHaveBeenCalledWith(3);
            expect(onLogProcessingChange).toHaveBeenCalledWith(true);
            // Both log entries have been displayed by the time the SFX fires.
            expect(onDisplayedLogCountChange).toHaveBeenLastCalledWith(2);
        }, REPLAY_TEST_TIMEOUT);

        it('does not duplicate a log entry with the same message and round', async () => {
            const { replay } = await renderWithSeededLog();

            const dupEntry = { message: 'Jean attacks Slime', round: 1, type: 'action' };
            replay([dupEntry, { ...dupEntry }]);

            await waitFor(() => {
                expect(screen.getAllByText('Jean attacks Slime').length).toBe(1);
            }, { timeout: REPLAY_ASSERT_TIMEOUT });
        });

        it('does not play a quest SFX when "quest" appears without a completion keyword', async () => {
            const { replay } = await renderWithSeededLog();

            replay([{ message: 'A new quest is now available', round: 1, type: 'quest' }]);

            await waitFor(() => {
                expect(screen.getByText('A new quest is now available')).toBeInTheDocument();
            }, { timeout: REPLAY_ASSERT_TIMEOUT });
            expect(mockPlaySFX).not.toHaveBeenCalledWith('quest_complete');
        });

        it('plays a low-health warning when Jean is attacked below 30% HP', async () => {
            // On the combatant, not the prop: LeftPanel merges `combat.player`
            // over the prop, and the hook reads the merge.
            const hurt = makeCombatant({ hp: 20 });
            const { replay } = await renderWithSeededLog({ combat: { player: hurt } });

            replay([{ message: 'Slime attacks Jean', round: 1, type: 'action' }]);

            await waitFor(() => {
                expect(mockPlaySFX).toHaveBeenCalledWith('low_health_warning');
            }, { timeout: REPLAY_ASSERT_TIMEOUT });
        });

        it('skips the keyword SFX and holds the reveal for an animation-carrying log entry', async () => {
            const { replay } = await renderWithSeededLog();

            replay([
                { message: 'Jean attacks Slime', round: 1, type: 'result', animation: { type: 'attack' } },
            ]);

            await waitFor(() => {
                expect(screen.getByText('Jean attacks Slime')).toBeInTheDocument();
            }, { timeout: REPLAY_ASSERT_TIMEOUT });
            expect(mockPlaySFX).not.toHaveBeenCalledWith('attack_swipe');
        });

        it('plays the victory sting for a victory log line', async () => {
            const { replay } = await renderWithSeededLog();

            replay([{ message: 'Victory! The battle is won.', round: 1, type: 'result' }]);

            await waitFor(() => {
                expect(mockPlaySting).toHaveBeenCalledWith('fanfare');
            }, { timeout: REPLAY_ASSERT_TIMEOUT });
        }, REPLAY_TEST_TIMEOUT);
    });


    it('closes the Stats, Skills, Actions, and Interact panels via their onClose handlers', () => {
        render(<LeftPanel {...baseProps} mode="exploration" />);

        fireEvent.click(screen.getByText('Attributes Btn'));
        expect(screen.getByTestId('stats-panel')).toBeInTheDocument();
        fireEvent.click(screen.getByText('Close Stats'));
        expect(screen.queryByTestId('stats-panel')).not.toBeInTheDocument();

        fireEvent.click(screen.getByText('Skills Btn'));
        expect(screen.getByTestId('skills-panel')).toBeInTheDocument();
        fireEvent.click(screen.getByText('Close Skills'));
        expect(screen.queryByTestId('skills-panel')).not.toBeInTheDocument();

        fireEvent.click(screen.getByText('Actions Btn'));
        expect(screen.getByTestId('actions-panel')).toBeInTheDocument();
        fireEvent.click(screen.getByText('Close Actions'));
        expect(screen.queryByTestId('actions-panel')).not.toBeInTheDocument();

        fireEvent.click(screen.getByText('Interact Btn'));
        expect(screen.getByTestId('interact-panel')).toBeInTheDocument();
        fireEvent.click(screen.getByText('Close Interact'));
        expect(screen.queryByTestId('interact-panel')).not.toBeInTheDocument();
    });

    it('opens the Defensive and Special (Mastery) combat move panels', () => {
        const combat = combatWith([
            makeAvailableOption({ id: '1', name: 'Dodge', category: 'Defensive' }),
            makeAvailableOption({ id: '2', name: 'War Cry', category: 'Mastery' }),
        ]);
        render(<LeftPanel {...baseProps} mode="combat" combat={combat} />);

        // LeftPanel's job here is to hand CombatMovePanel the GROUP KEY — the
        // panel itself narrows the list with movesInGroup, so the mock (which
        // cannot filter) legitimately shows every move. The group key must be
        // one CATEGORY_GROUPS actually knows, or the real panel filters against
        // an unknown key and renders nothing at all.
        fireEvent.click(screen.getByText('Defensive Btn'));
        expect(screen.getByTestId('combat-move-panel').firstChild).toHaveTextContent('Defensive');
        expect(CATEGORY_GROUPS).toHaveProperty('Defensive');

        fireEvent.click(screen.getByText('Close Moves'));
        fireEvent.click(screen.getByText('Special Btn'));
        // Mastery moves route to the SPECIAL button — the exact regression that
        // left 7 Mastery moves plus Reaper's Mark with no button at all.
        expect(screen.getByTestId('combat-move-panel').firstChild).toHaveTextContent('Special');
        expect(CATEGORY_GROUPS.Special).toContain('Mastery');
    });

    // The three header buttons each hand-roll the same hover pair. Assert the
    // real theme colors on the way in AND the restore on the way out: the old
    // version entered/left all three but only checked that ONE background was
    // "not empty string", which a handler that set `red` would also satisfy —
    // and it never checked mouseLeave restored anything at all, so a button
    // stuck lit forever passed.
    it.each([
        ['Settings', () => screen.getByTitle('Settings')],
        ['Send Feedback', () => screen.getByTitle('Send Feedback')],
        ['Account', () => screen.getByText('Account')],
    ])('lights the %s header button on hover and restores it on leave', (_label, get) => {
        render(<LeftPanel {...baseProps} mode="exploration" />);
        const btn = get();
        const rgb = (hex) => {
            const n = parseInt(hex.slice(1), 16);
            return `rgb(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255})`;
        };

        expect(btn.style.backgroundColor).toBe(rgb(colors.primaryDark));

        fireEvent.mouseEnter(btn);
        expect(btn.style.backgroundColor).toBe(rgb(colors.primary));
        expect(btn.style.boxShadow).toContain(colors.primary);

        fireEvent.mouseLeave(btn);
        expect(btn.style.backgroundColor).toBe(rgb(colors.primaryDark));
    });
});

describe('LeftPanel — revealed log resets per fight', () => {
  const combatWithLog = (combatId, messages) => makeCombat({
    combat_id: combatId,
    awaiting_input: true,
    enemies: [],
    player: makeCombatant({ hp: 10, max_hp: 10 }),
    log: messages.map((message, i) => ({ message, round: 1, type: 'combat', beat_index: i })),
  });

  // Its own small fixture: this block rerenders across two fights and reads
  // only the log and the displayed count, so it states a player and a
  // location of its own rather than leaning on the shared ones.
  const fightProps = {
    player: makePlayer({ hp: 10, max_hp: 10 }),
    location: makeLocation({ name: 'Arena' }),
    mode: 'combat',
    isMobile: false,
  };

  // This one assertion guards three downstream consequences: BattlefieldGrid's
  // animation cursor indexing a different space from the count, the revealed-key
  // dedup swallowing repeated lines in later fights, and hasPendingLogs comparing
  // a short new log against a cumulative count. A sibling test asserting that a
  // REPEATED line reappears was deleted as vacuous: with identical messages,
  // fight #1's leftover entry renders identically to fight #2's fresh one, so it
  // passed with the fix reverted.
  it('clears the revealed log when a new fight starts, and reports the new count', async () => {
    // The server clears combat_log per fight. If the client's revealed set does
    // not restart with it, displayedLogCount stays cumulative while
    // BattlefieldGrid's cursor resets on unmount — the two then index different
    // spaces and combat animations break from the second fight onward.
    const onDisplayedLogCountChange = vi.fn();
    const { rerender } = render(
      <LeftPanel
        {...fightProps}
        combat={combatWithLog('fight-1', ['one', 'two'])}
        onDisplayedLogCountChange={onDisplayedLogCountChange}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId('combat-log').textContent).toContain('two');
    });
    expect(onDisplayedLogCountChange).toHaveBeenLastCalledWith(2);

    rerender(
      <LeftPanel
        {...fightProps}
        combat={combatWithLog('fight-2', ['fresh'])}
        onDisplayedLogCountChange={onDisplayedLogCountChange}
      />
    );

    // Count must drop back, not continue from 2.
    await waitFor(() => {
      expect(onDisplayedLogCountChange).toHaveBeenCalledWith(0);
    });
    await waitFor(() => {
      const shown = screen.getByTestId('combat-log').textContent;
      expect(shown).toContain('fresh');
      expect(shown).not.toContain('one');
    });
  });
});
