import { readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import React from 'react';
import { render, screen, fireEvent, within } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import CombatLog, { LOG_ENTRY_COLORS } from './CombatLog';
import { colors } from '../styles/theme';

describe('CombatLog', () => {
  // Entry types the ENGINE emits. The fixture used to read
  // damage/heal/ability/other -- a vocabulary invented on this side, three
  // quarters of which no Python writer has ever produced -- so every rendering
  // test here was exercising the fallback branch and calling it coverage.
  const mockLog = [
    { type: 'info', message: 'Combat started', timestamp: '12:00:00' },
    { type: 'combat', message: 'Hero deals 10 damage', timestamp: '12:00:01' },
    { type: 'player_action', message: 'Hero heals 5 HP', timestamp: '12:00:02' },
    { type: 'system', message: 'Hero uses Fireball', timestamp: '12:00:03' },
    { type: 'other', message: 'Something happened', timestamp: '12:00:04' }
  ];

  it('renders combat log entries correctly', () => {
    render(<CombatLog log={mockLog} />);

    // Scoped to the list: the newest line also exists in the hidden
    // announcer (issue #563 item 1), so an unscoped getByText for the LAST
    // entry matches twice and cannot tell the list rendered it.
    const entries = within(screen.getByTestId('combat-log-entries'));
    expect(screen.getByText('Combat Log')).toBeDefined();
    expect(entries.getByText('Combat started')).toBeDefined();
    expect(entries.getByText('Hero deals 10 damage')).toBeDefined();
    expect(entries.getByText('Hero heals 5 HP')).toBeDefined();
    expect(entries.getByText('Hero uses Fireball')).toBeDefined();
    expect(entries.getByText('Something happened')).toBeDefined();
  });

  it('renders empty log message', () => {
    render(<CombatLog log={[]} />);
    expect(screen.getByText('Combat started...')).toBeDefined();
  });

  it('collapses and expands when header is clicked', () => {
    render(<CombatLog log={mockLog} />);
    const header = screen.getByText('Combat Log').parentElement;

    // Initially expanded
    expect(screen.getByText('▼')).toBeDefined();
    expect(screen.getByText('Combat started')).toBeDefined();

    // Collapse
    fireEvent.click(header);
    expect(screen.getByText('▶')).toBeDefined();
    expect(screen.queryByText('Combat started')).toBeNull();

    // Expand
    fireEvent.click(header);
    expect(screen.getByText('▼')).toBeDefined();
    expect(screen.getByText('Combat started')).toBeDefined();
  });

  it('handles resizing', () => {
    const { container } = render(<CombatLog log={mockLog} allowResize={true} />);
    const resizeHandle = container.querySelector('[style*="cursor: ns-resize"], [style*="ns-resize"]');

    // Resize handle must be present when allowResize=true
    expect(resizeHandle, 'resize handle not found — check CombatLog resize implementation').not.toBeNull();

    // Mock getBoundingClientRect for logRef
    const logElement = container.firstChild;
    vi.spyOn(logElement, 'getBoundingClientRect').mockReturnValue({
      bottom: 500
    });

    fireEvent.mouseDown(resizeHandle);

    // Move mouse down by 50px (delta = 550 - 500 = 50)
    // height = height - delta = 150 - 50 = 100
    fireEvent.mouseMove(document, { clientY: 550 });
    fireEvent.mouseUp(document);

    expect(logElement.style.height).toBe('100px');
  });

  it('ignores mousemove when not currently resizing', () => {
    const { container } = render(<CombatLog log={mockLog} allowResize={true} />);
    const logElement = container.firstChild;
    const originalHeight = logElement.style.height;

    // No mouseDown first, so isResizing is false — mousemove should be a no-op.
    fireEvent.mouseMove(document, { clientY: 999 });
    expect(logElement.style.height).toBe(originalHeight);
  });

  it('shows top/bottom scroll fade indicators when content overflows', () => {
    const { container } = render(<CombatLog log={mockLog} />);
    const contentEl = container.querySelector('div[style*="overflow-y: auto"]');

    Object.defineProperty(contentEl, 'scrollHeight', { value: 500, configurable: true });
    Object.defineProperty(contentEl, 'clientHeight', { value: 100, configurable: true });
    Object.defineProperty(contentEl, 'scrollTop', { value: 50, configurable: true });
    fireEvent.scroll(contentEl);

    expect(container.querySelector('[style*="position: absolute"]')).not.toBeNull();
  });

  // Issue #537 — CombatLog shares ScrollFadeIndicator/useScrollIndicators
  // with CollapsibleRoomDescription, so it shares the same overlap bug: the
  // persistent "▼ scroll ▼" hint painted directly over the last visible log
  // line instead of sitting below it. The content container must reserve
  // blank space below the lines once it overflows.
  it('reserves space below the log lines for the bottom scroll hint instead of overlapping them', () => {
    const { container } = render(<CombatLog log={mockLog} />);
    const contentEl = container.querySelector('div[style*="overflow-y: auto"]');
    const basePadding = parseInt(contentEl.style.paddingBottom || '0', 10);

    Object.defineProperty(contentEl, 'scrollHeight', { value: 500, configurable: true });
    Object.defineProperty(contentEl, 'clientHeight', { value: 100, configurable: true });
    Object.defineProperty(contentEl, 'scrollTop', { value: 0, configurable: true });
    fireEvent.scroll(contentEl);

    const paddingBottom = parseInt(contentEl.style.paddingBottom || '0', 10);
    expect(paddingBottom).toBeGreaterThan(basePadding);
  });

  it('respects allowResize prop', () => {
    const { container } = render(<CombatLog log={mockLog} allowResize={false} />);
    const resizeHandle = container.querySelector('[style*="cursor: ns-resize"], [style*="ns-resize"]');
    expect(resizeHandle).toBeNull();
    expect(container.firstChild.style.height).toBe('100%');
  });

  it('auto-scrolls to bottom when log updates', () => {
    const { rerender } = render(<CombatLog log={mockLog} />);
    
    // We can't easily test scrollTop in JSDOM without more complex mocking,
    // but we can verify the effect runs.
    const newLog = [...mockLog, { type: 'info', message: 'New entry' }];
    rerender(<CombatLog log={newLog} />);
    expect(within(screen.getByTestId('combat-log-entries')).getByText('New entry')).toBeDefined();
  });

  it('auto-scrolls to bottom when it becomes player turn', () => {
    // The previous version rerendered and asserted nothing ("// Effect runs"),
    // so it passed against a component with no scroll effect at all. The
    // observable outcome is that the scroll container is driven to its bottom.
    const { rerender, container } = render(<CombatLog log={mockLog} isMyTurn={false} />);
    const scroller = container.querySelector('[style*="overflow-y"]')
      || container.querySelector('div > div');
    Object.defineProperty(scroller, 'scrollHeight', { value: 500, configurable: true });
    Object.defineProperty(scroller, 'clientHeight', { value: 100, configurable: true });
    scroller.scrollTop = 0;

    rerender(<CombatLog log={mockLog} isMyTurn={true} />);

    expect(scroller.scrollTop).toBe(scroller.scrollHeight);
  });

  describe('empty-state placeholder', () => {
    // Two ways the panel could render completely blank -- no entries AND no
    // placeholder -- both of which the old `log?.length === 0` gate missed.
    it('shows the placeholder when the log prop is absent', () => {
      // `undefined === 0` is false, so the old gate suppressed the placeholder
      // and rendered an empty panel.
      render(<CombatLog />);
      expect(screen.getByText('Combat started...')).toBeDefined();
    });

    it('shows the placeholder when the log holds only animation entries', () => {
      // Animation entries are filtered out of the rendered list but still count
      // toward `log.length`, so the old gate saw a non-empty log and hid the
      // placeholder while the list rendered nothing. Reachable at combat start:
      // the reveal loop adds entries one at a time, so the first revealed entry
      // can be an animation.
      const animationOnly = [
        { type: 'animation', message: 'Slash animation', timestamp: '12:00:00' },
        { type: 'animation', message: 'Thrust animation', timestamp: '12:00:01' },
      ];
      render(<CombatLog log={animationOnly} />);

      expect(screen.getByText('Combat started...')).toBeDefined();
      expect(screen.queryByText('Slash animation')).toBeNull();
      expect(screen.queryByText('Thrust animation')).toBeNull();
    });

    it('hides the placeholder as soon as one renderable entry arrives', () => {
      // The complement: a log mixing animation with a real line must show the
      // line and drop the placeholder, so the fix cannot degrade into "always
      // show the placeholder".
      const mixed = [
        { type: 'animation', message: 'Slash animation', timestamp: '12:00:00' },
        { type: 'info', message: 'Jean strikes the slime', timestamp: '12:00:01' },
      ];
      render(<CombatLog log={mixed} />);

      expect(screen.queryByText('Combat started...')).toBeNull();
      const entries = within(screen.getByTestId('combat-log-entries'));
      expect(entries.getByText('Jean strikes the slime')).toBeDefined();
      expect(screen.queryByText('Slash animation')).toBeNull();
    });
  });

  // ---------------------------------------------------------------------------
  // The colour table is keyed on the engine's vocabulary
  // ---------------------------------------------------------------------------
  //
  // `entry.type` is a string the Python chooses. The table used to be keyed
  // damage/heal/ability/info/system, of which the engine emits two -- and NOT
  // `combat`, which is `_add_log_entry`'s default and therefore the type of
  // nearly every line in the log. Every fixture in this file spelled the
  // frontend's vocabulary back at it, so the drift was invisible: a mock cannot
  // catch a mock agreeing with itself.
  //
  // So the population is read out of the Python instead. Both directions: a
  // type the engine gains is an uncoloured line here, and a key nothing emits
  // is dead weight that makes the table look considered when it is not.
  describe("the engine's log-entry vocabulary", () => {
    const REPO_ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..');

    /** Text from `open` to its matching `)`, tracking nesting and strings. */
    const callArgs = (source, open) => {
      let depth = 0;
      let quote = null;
      for (let i = open; i < source.length; i += 1) {
        const ch = source[i];
        if (quote) {
          if (ch === quote && source[i - 1] !== '\\') quote = null;
          continue;
        }
        if (ch === '"' || ch === "'") { quote = ch; continue; }
        if (ch === '(') depth += 1;
        else if (ch === ')') {
          depth -= 1;
          if (depth === 0) return source.slice(open + 1, i);
        }
      }
      return null;
    };

    /**
     * Every `type` a combat-log entry can carry, read from the engine.
     *
     * Two mints, because the engine has two: the adapter's `_add_log_entry`
     * helper (its default, plus whatever each call passes), and the handful of
     * places that append a bare dict to `combat_log` directly.
     */
    const engineEntryTypes = () => {
      const read = (...parts) => readFileSync(join(REPO_ROOT, ...parts), 'utf8');
      const adapter = read('src', 'api', 'combat_adapter.py');
      const types = new Set();

      const fallback = adapter.match(/entry_type: str = "(\w+)"/);
      expect(
        fallback,
        'could not find _add_log_entry\'s entry_type default in src/api/combat_adapter.py'
      ).toBeTruthy();
      types.add(fallback[1]);

      // `entry_type` is the third parameter, so a call passes it either
      // positionally third or by keyword.
      let calls = 0;
      for (const match of adapter.matchAll(/_add_log_entry\(/g)) {
        const args = callArgs(adapter, match.index + match[0].length - 1);
        if (args === null) continue;
        calls += 1;
        const keyword = args.match(/entry_type\s*=\s*"(\w+)"/);
        if (keyword) { types.add(keyword[1]); continue; }
        // Third positional: the first two are round and message, neither of
        // which is ever a bare identifier-shaped literal.
        const positional = args.match(/,[\s\S]*?,\s*"(\w+)"/);
        if (positional) types.add(positional[1]);
      }
      // Guard-the-guard: a regex that stopped matching calls would silently
      // shrink the vocabulary to the default alone.
      expect(calls, 'found no _add_log_entry calls to read').toBeGreaterThan(5);

      // Direct appends, in the two modules that build the dict themselves.
      let appends = 0;
      for (const parts of [['src', 'moves', '_utility.py'], ['src', 'api', 'services', 'game_service.py']]) {
        const source = read(...parts);
        for (const match of source.matchAll(/combat_log\.append\(/g)) {
          const args = callArgs(source, match.index + match[0].length - 1);
          if (args === null || !args.includes('"message"')) continue;
          const type = args.match(/"type":\s*"(\w+)"/);
          if (!type) continue;
          appends += 1;
          types.add(type[1]);
        }
      }
      expect(appends, 'found no direct combat_log appends to read').toBeGreaterThan(0);

      return types;
    };

    it('colours exactly the types the engine can send, minus the one it hides', () => {
      const engine = engineEntryTypes();
      // Non-vacuity, and a check that the scan reached both mints.
      expect(engine.size).toBeGreaterThan(3);
      expect(engine).toContain('combat');

      // `animation` entries are bookkeeping and are filtered out before any
      // colour is chosen, so the one type deliberately absent from the table is
      // derived here too rather than hardcoded as an exception.
      render(<CombatLog log={[{ type: 'animation', message: 'Slash', timestamp: '12:00:00' }]} />);
      expect(screen.queryByText('Slash')).toBeNull();
      const rendered = [...engine].filter((type) => type !== 'animation');

      expect(
        Object.keys(LOG_ENTRY_COLORS).sort(),
        'CombatLog.jsx LOG_ENTRY_COLORS and the engine disagree about what a log '
        + `entry type is. Engine (rendered): ${rendered.sort().join(', ')}. `
        + `Table: ${Object.keys(LOG_ENTRY_COLORS).sort().join(', ')}`
      ).toEqual(rendered.sort());
    });

    it('paints each of them with its own colour rather than the fallback', () => {
      // Keys alone would pass for a table whose values were never wired up.
      // Every engine type is driven through the real render and read back off
      // the DOM.
      const engine = [...engineEntryTypes()].filter((type) => type !== 'animation');
      const log = engine.map((type, i) => ({
        type, message: `line ${type}`, timestamp: `12:00:0${i}`,
      }));
      render(<CombatLog log={log} />);
      // The list, not the container: the announcer holds an uncoloured copy
      // of the newest line and matched first, so the scan read '' as its
      // colour and the assertion below was testing the wrong span.
      const list = screen.getByTestId('combat-log-entries');

      for (const type of engine) {
        const span = [...list.querySelectorAll('span')]
          .find((el) => el.textContent === `line ${type}`);
        expect(span, `no rendered line for engine entry type "${type}"`).toBeTruthy();
        expect(span.style.color).not.toBe('');
      }

      // ...and an unknown type still reaches the fallback rather than throwing.
      const { container: odd } = render(
        <CombatLog log={[{ type: 'constructor', message: 'hostile', timestamp: '12:00:00' }]} />
      );
      const oddList = within(odd).getAllByTestId('combat-log-entries').at(-1);
      const fallbackSpan = [...oddList.querySelectorAll('span')]
        .find((el) => el.textContent === 'hostile');
      // jsdom re-serialises a hex colour as `rgb(...)`, so the expectation is
      // put through the same normalisation rather than compared as written.
      const asRendered = (hex) => {
        const n = parseInt(hex.slice(1), 16);
        return `rgb(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255})`;
      };
      expect(fallbackSpan.style.color).toBe(asRendered(colors.text.main));
    });
  });

  /**
   * Issue #563 item 1 — the log is the fight's primary feedback channel and it
   * was never announced. A screen-reader user committed a move and was told
   * nothing.
   *
   * The pattern is NpcChatPanel's `ReplyAnnouncer`, not an invention: a
   * visually-hidden polite region fed the newest COMPLETED line only. What is
   * being avoided is spelled out in Battlefield.jsx's own note on the beat
   * counter — "a live region would make a screen reader narrate the counter
   * continuously over the combat log it should be reading" — and putting
   * `aria-live` on the list itself is the same mistake one level down: the
   * whole log is re-read on every append, and on a beat scrub the list is
   * replaced wholesale.
   */
  describe('screen-reader announcements', () => {
    const announcer = () => screen.getByTestId('combat-log-announcer');

    it('announces the newest line through a polite atomic region', () => {
      render(<CombatLog log={mockLog} />);

      const region = announcer();
      expect(region.getAttribute('aria-live')).toBe('polite');
      // Atomic because the region is re-fed rather than appended to: without
      // it a reader announces only the changed text node, which is the same
      // string it just replaced.
      expect(region.getAttribute('aria-atomic')).toBe('true');
      expect(region.textContent).toContain('Something happened');
    });

    it('announces only the newest line, not the whole log', () => {
      // The failure mode this whole design exists to avoid: a 50-line log
      // re-read on every beat is worse than silence.
      render(<CombatLog log={mockLog} />);

      const spoken = announcer().textContent;
      expect(spoken).toContain('Something happened');
      expect(spoken).not.toContain('Combat started');
      expect(spoken).not.toContain('Hero deals 10 damage');
    });

    it('leaves the rendered list out of the live region', () => {
      // The list must stay silent, or both channels narrate every append.
      const { container } = render(<CombatLog log={mockLog} />);

      const live = [...container.querySelectorAll('[aria-live]')];
      expect(live).toHaveLength(1);
      expect(live[0].getAttribute('data-testid')).toBe('combat-log-announcer');
      expect(container.querySelector('[role="log"]')).toBeNull();
    });

    it('speaks the message without its timestamp', () => {
      // The timestamp is rendered beside every line; read aloud it prefixes
      // each announcement with eight digits before any of the content.
      render(<CombatLog log={[{ type: 'combat', message: 'Jean strikes', timestamp: '12:00:01' }]} />);

      expect(announcer().textContent.trim()).toBe('Jean strikes');
    });

    it('speaks the message as text, never as markup', () => {
      // Entries reach the list through dangerouslySetInnerHTML, so the engine
      // does emit markup; a reader should get the words, not the tags.
      render(<CombatLog log={[{ type: 'combat', message: 'Jean hits <b>hard</b>', timestamp: '12:00:01' }]} />);

      const region = announcer();
      expect(region.textContent).toBe('Jean hits hard');
      expect(region.innerHTML).not.toContain('<b>');
    });

    it('never announces animation bookkeeping', () => {
      // `animation` entries are carriers for the battlefield, not lines of
      // text — they are filtered out of the render and must not be spoken
      // either, or the newest "line" is regularly a non-line.
      render(<CombatLog log={[
        { type: 'combat', message: 'Jean strikes', timestamp: '12:00:01' },
        { type: 'animation', message: 'Sweep animation', timestamp: '12:00:02' },
      ]} />);

      expect(announcer().textContent).toBe('Jean strikes');
    });

    it('re-announces a line that repeats the previous one verbatim', () => {
      // Combat repeats itself constantly ("Jean misses." twice running). If
      // the region is fed the same string, React writes the identical text
      // node, the DOM does not mutate, and the reader says nothing at all —
      // silently dropping every repeated beat.
      const first = [{ type: 'combat', message: 'Jean misses', timestamp: '12:00:01' }];
      const { rerender, container } = render(<CombatLog log={first} />);
      const before = container.querySelector('[data-testid="combat-log-announcer"]').innerHTML;

      rerender(<CombatLog log={[...first, { type: 'combat', message: 'Jean misses', timestamp: '12:00:02' }]} />);
      const after = container.querySelector('[data-testid="combat-log-announcer"]').innerHTML;

      expect(announcer().textContent).toBe('Jean misses');
      // Something inside the region has to have changed for the announcement
      // to fire; identical markup means it did not.
      expect(after).not.toBe(before);
    });

    it('keeps announcing while the panel is collapsed', () => {
      // Collapsing hides the lines but is not a request to stop being told
      // what is happening in the fight.
      render(<CombatLog log={mockLog} />);
      fireEvent.click(screen.getByText('Combat Log'));

      expect(announcer().textContent).toContain('Something happened');
    });

    it('says nothing when there is nothing to say', () => {
      // An empty region is correct; the "Combat started..." placeholder is
      // visual furniture and announcing it would be a false first beat.
      render(<CombatLog log={[]} />);

      expect(announcer().textContent).toBe('');
    });

    it('stays out of the visual layout', () => {
      // Visually hidden, not `display: none` — the latter takes it out of the
      // accessibility tree too, which is the whole thing it is here for.
      render(<CombatLog log={mockLog} />);

      const { style } = announcer();
      expect(style.display).not.toBe('none');
      expect(style.visibility).not.toBe('hidden');
      expect(style.width).toBe('1px');
      expect(style.height).toBe('1px');
      expect(style.overflow).toBe('hidden');
    });
  });
});
