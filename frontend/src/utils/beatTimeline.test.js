import { describe, it, expect } from 'vitest';
import { getBeatTimelineEntries, groupTimelineColumns, buildBeatTimelineColumns } from './beatTimeline';

const pendingMove = (overrides = {}) => ({
  name: 'NPC_Attack',
  display_name: 'Attack',
  category: 'Offensive',
  current_stage: 0,
  beats_left: 1,
  beats_until_resolve: 5,
  ...overrides,
});

describe('getBeatTimelineEntries', () => {
  it('orders entries by soonest beat first', () => {
    const combat = {
      player: { id: 'player', name: 'Jean', hp: 10, current_move: pendingMove({ beats_until_resolve: 8 }) },
      enemies: [
        { id: 'enemy_1', name: 'Slime', hp: 5, current_move: pendingMove({ beats_until_resolve: 2 }) },
      ],
    };
    const entries = getBeatTimelineEntries(combat);
    expect(entries.map((e) => e.name)).toEqual(['Slime', 'Jean']);
    expect(entries.map((e) => e.beat)).toEqual([2, 8]);
  });

  it('breaks a beat tie with Jean first, then allies, then enemies', () => {
    const combat = {
      player: { id: 'player', name: 'Jean', hp: 10, current_move: pendingMove({ beats_until_resolve: 3 }) },
      allies: [
        { id: 'ally_1', name: 'Gorran', hp: 10, current_move: pendingMove({ beats_until_resolve: 3 }) },
      ],
      enemies: [
        { id: 'enemy_1', name: 'Slime', hp: 5, current_move: pendingMove({ beats_until_resolve: 3 }) },
      ],
    };
    const entries = getBeatTimelineEntries(combat);
    expect(entries.map((e) => e.name)).toEqual(['Jean', 'Gorran', 'Slime']);
  });

  it('distinguishes friend from foe by alignment, read from the pool the combatant came from', () => {
    const combat = {
      player: { id: 'player', name: 'Jean', hp: 10, current_move: pendingMove({ beats_until_resolve: 1 }) },
      allies: [
        { id: 'ally_1', name: 'Gorran', hp: 10, current_move: pendingMove({ beats_until_resolve: 2 }) },
      ],
      enemies: [
        { id: 'enemy_1', name: 'Slime', hp: 5, current_move: pendingMove({ beats_until_resolve: 2 }) },
      ],
    };
    const entries = getBeatTimelineEntries(combat);
    const jean = entries.find((e) => e.name === 'Jean');
    const gorran = entries.find((e) => e.name === 'Gorran');
    const slime = entries.find((e) => e.name === 'Slime');
    expect(jean.alignment).toBe('friendly');
    expect(jean.isPlayer).toBe(true);
    expect(gorran.alignment).toBe('friendly');
    expect(gorran.isPlayer).toBe(false);
    expect(slime.alignment).toBe('enemy');
  });

  it('excludes a combatant with no pending move', () => {
    const combat = {
      player: { id: 'player', name: 'Jean', hp: 10, current_move: null },
      enemies: [
        { id: 'enemy_1', name: 'Slime', hp: 5, current_move: pendingMove({ current_stage: 3 }) },
      ],
    };
    expect(getBeatTimelineEntries(combat)).toEqual([]);
  });

  it('excludes a dead combatant even if its stale move payload is still pending', () => {
    const combat = {
      enemies: [
        { id: 'enemy_1', name: 'Slime', hp: 0, current_move: pendingMove() },
      ],
    };
    expect(getBeatTimelineEntries(combat)).toEqual([]);
  });

  it('returns an empty list for missing/undefined combat', () => {
    expect(getBeatTimelineEntries(null)).toEqual([]);
    expect(getBeatTimelineEntries(undefined)).toEqual([]);
    expect(getBeatTimelineEntries({})).toEqual([]);
  });

  it('carries the move display name and category through onto the entry', () => {
    const combat = {
      enemies: [
        { id: 'enemy_1', name: 'Slime', hp: 5, current_move: pendingMove({ display_name: 'Tidal Surge', category: 'Supernatural', beats_until_resolve: 4 }) },
      ],
    };
    const [entry] = getBeatTimelineEntries(combat);
    expect(entry.moveName).toBe('Tidal Surge');
    expect(entry.category).toBe('Supernatural');
  });
});

describe('groupTimelineColumns', () => {
  it('collapses several combatants landing on the same beat into one column', () => {
    const entries = [
      { key: 'a', beat: 3, name: 'A' },
      { key: 'b', beat: 3, name: 'B' },
      { key: 'c', beat: 5, name: 'C' },
    ];
    const columns = groupTimelineColumns(entries);
    expect(columns).toHaveLength(2);
    expect(columns[0]).toEqual({ beat: 3, entries: [entries[0], entries[1]] });
    expect(columns[1]).toEqual({ beat: 5, entries: [entries[2]] });
  });

  it('caps at maxColumns distinct beats, not at a beat-value cutoff', () => {
    // Every beat value here is enormous (commitments run up to ~101 beats
    // per CLAUDE.md) — a cutoff of "beat <= 10" would produce zero columns.
    // The cap must count distinct beats present, not filter by their value.
    const entries = Array.from({ length: 15 }, (_, i) => ({
      key: `e${i}`, beat: 50 + i * 3, name: `E${i}`,
    }));
    const columns = groupTimelineColumns(entries, 10);
    expect(columns).toHaveLength(10);
    expect(columns[0].beat).toBe(50);
    expect(columns[9].beat).toBe(50 + 9 * 3);
  });

  it('returns an empty array for an empty entry list', () => {
    expect(groupTimelineColumns([])).toEqual([]);
  });
});

describe('buildBeatTimelineColumns', () => {
  it('composes entry-derivation and grouping for the component to consume directly', () => {
    const combat = {
      player: { id: 'player', name: 'Jean', hp: 10, current_move: pendingMove({ beats_until_resolve: 1 }) },
      enemies: [
        { id: 'enemy_1', name: 'Slime', hp: 5, current_move: pendingMove({ beats_until_resolve: 1 }) },
      ],
    };
    const columns = buildBeatTimelineColumns(combat);
    expect(columns).toEqual([
      {
        beat: 1,
        entries: [
          expect.objectContaining({ name: 'Jean', isPlayer: true }),
          expect.objectContaining({ name: 'Slime', alignment: 'enemy' }),
        ],
      },
    ]);
  });
});
