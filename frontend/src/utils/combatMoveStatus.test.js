import { describe, it, expect } from 'vitest';
import {
  displayNameOf,
  formatCombatMoveStatus,
  isMovePending,
  beatsUntilResolve,
  moveAvailability,
  moveDamagePreview,
  telegraphSeverity,
  telegraphShortLabel,
  telegraphWarning,
  hostileTelegraphWarning,
  TELEGRAPH_SEVERITIES,
  NO_REACHABLE_TARGET_REASON,
} from './combatMoveStatus';

// Issue #586: King Slime's Tidal Surge (2.5x, a full-to-dead hit) was
// telegraphed identically to a routine NpcAttack wind-up because both are
// "Offensive". The serializer now carries Move.telegraph_severity
// (src/moves/_base.py) as `telegraph_severity`; these read it.
describe('telegraphSeverity', () => {
  it('passes the engine vocabulary through', () => {
    expect(telegraphSeverity({ telegraph_severity: 'heavy' })).toBe('heavy');
    expect(telegraphSeverity({ telegraph_severity: 'deadly' })).toBe('deadly');
    expect(telegraphSeverity({ telegraph_severity: 'normal' })).toBe('normal');
  });

  it('defaults to normal when the field is absent — the pre-#586 payload', () => {
    expect(telegraphSeverity({ name: 'NPC_Attack', current_stage: 0 })).toBe('normal');
  });

  it('treats no move, a legacy string move, and an unknown value as normal', () => {
    expect(telegraphSeverity(null)).toBe('normal');
    expect(telegraphSeverity(undefined)).toBe('normal');
    expect(telegraphSeverity('Attacking')).toBe('normal');
    // The vocabulary is closed on the Python side; a value outside it must
    // not be handed to a label lookup as though it were a severity.
    expect(telegraphSeverity({ telegraph_severity: 'apocalyptic' })).toBe('normal');
  });

  it('does not mistake an Object.prototype key for a severity', () => {
    // A bracket read of the label table would find `constructor` truthy and
    // pass it through as a severity; the table must be read prototype-safely
    // (utils/lookup.js), like every other table in the client.
    expect(telegraphSeverity({ telegraph_severity: 'constructor' })).toBe('normal');
    expect(telegraphWarning({ current_stage: 0, beats_until_resolve: 3, telegraph_severity: 'toString' })).toBeNull();
  });
});

describe('telegraphWarning', () => {
  const pending = (severity) => ({
    name: 'Tidal Surge', current_stage: 0, beats_until_resolve: 7, telegraph_severity: severity,
  });

  it('is null for a routine wind-up, so the glyph marks nothing ordinary', () => {
    expect(telegraphWarning(pending('normal'))).toBeNull();
    expect(telegraphWarning(pending(undefined))).toBeNull();
    expect(telegraphWarning(null)).toBeNull();
  });

  it('names a heavy and a deadly wind-up, in sentence and one-word form', () => {
    expect(telegraphWarning(pending('heavy'))).toEqual({ severity: 'heavy', label: 'Heavy move', shortLabel: 'HEAVY' });
    expect(telegraphWarning(pending('deadly'))).toEqual({ severity: 'deadly', label: 'Deadly move', shortLabel: 'DEADLY' });
  });

  it('is null once the move has resolved — a spent surge is not a threat', () => {
    expect(telegraphWarning({ ...pending('deadly'), current_stage: 3 })).toBeNull();
  });

  it('closes the vocabulary explicitly, normal included', () => {
    expect([...TELEGRAPH_SEVERITIES].sort()).toEqual(['deadly', 'heavy', 'normal']);
    expect(telegraphShortLabel('normal')).toBeNull();
    expect(telegraphShortLabel('constructor')).toBeNull();
  });
});

describe('hostileTelegraphWarning', () => {
  const surge = { name: 'Tidal Surge', current_stage: 0, beats_until_resolve: 7, telegraph_severity: 'deadly' };

  it("warns for an enemy's heavy move and not for an ally's — the glyph is a threat cue for Jean", () => {
    expect(hostileTelegraphWarning(surge, true)).toEqual(telegraphWarning(surge));
    expect(hostileTelegraphWarning(surge, false)).toBeNull();
  });

  it('still gates on the move being pending', () => {
    expect(hostileTelegraphWarning({ ...surge, current_stage: 2 }, true)).toBeNull();
  });
});

describe('formatCombatMoveStatus', () => {
  it.each([
    [0, 'Preparing: Attack'],
    [1, 'Using: Attack'],
    [2, 'Just used: Attack'],
    [3, 'Cooling down from: Attack'],
  ])('formats stage %s as %s', (stage, expected) => {
    expect(formatCombatMoveStatus({ name: 'NPC_Attack', display_name: 'Attack', current_stage: stage })).toBe(expected);
  });

  it('returns null when no move is present', () => {
    expect(formatCombatMoveStatus(null)).toBeNull();
  });

  it('accepts a legacy move name without a known stage', () => {
    expect(formatCombatMoveStatus('Attacking')).toBe('Attacking');
  });

  it('prefers an explicitly supplied display name over the internal name', () => {
    expect(formatCombatMoveStatus({ name: 'NPC_Attack', current_stage: 1 }, undefined, 'Attack'))
      .toBe('Using: Attack');
  });

  it('resolves a player-facing display name with an internal fallback', () => {
    expect(displayNameOf({ name: 'NPC_Attack', display_name: 'Attack' })).toBe('Attack');
    expect(displayNameOf({ name: 'LegacyMove' })).toBe('LegacyMove');
  });
});

describe('isMovePending', () => {
  it.each([[0], [1]])('treats stage %s as unresolved intent', (stage) => {
    expect(isMovePending({ name: 'Reap', current_stage: stage })).toBe(true);
  });

  it.each([[2], [3]])('treats stage %s as aftermath, not a threat', (stage) => {
    expect(isMovePending({ name: 'Reap', current_stage: stage })).toBe(false);
  });

  it('treats a stage-less move as pending rather than dropping the telegraph', () => {
    expect(isMovePending({ name: 'Cackle' })).toBe(true);
  });

  it('is false for absent or legacy string moves', () => {
    expect(isMovePending(null)).toBe(false);
    expect(isMovePending('Attacking')).toBe(false);
  });
});

describe('beatsUntilResolve', () => {
  it('reports the engine-computed time until the move lands', () => {
    // beats_left is beats left in the CURRENT STAGE — for a move with a
    // 4-beat execute stage the real answer is 9, not 3. The engine computes
    // it (Move.beats_until_resolve); this is a passthrough.
    expect(beatsUntilResolve({ current_stage: 0, beats_left: 3, beats_until_resolve: 9 })).toBe(9);
    expect(beatsUntilResolve({ current_stage: 1, beats_left: 0, beats_until_resolve: 1 })).toBe(1);
  });

  it('never reports the much smaller in-stage count when the real one is present', () => {
    // Guards the regression directly: returning beats_left here would have
    // told the player they had 3 beats to react when they had 9.
    expect(beatsUntilResolve({ current_stage: 0, beats_left: 3, beats_until_resolve: 9 }))
      .not.toBe(3);
  });

  it('reports nothing for a move that has already resolved', () => {
    expect(beatsUntilResolve({ current_stage: 3, beats_left: 4, beats_until_resolve: null })).toBeNull();
  });

  it('reports nothing when the payload carries no countdown', () => {
    expect(beatsUntilResolve({ current_stage: 0 })).toBeNull();
    expect(beatsUntilResolve({ current_stage: 0, beats_left: -1 })).toBeNull();
  });

  it('never renders a zero — "lands this beat" is 1, not 0', () => {
    expect(beatsUntilResolve({ current_stage: 1, beats_left: 0 })).toBeNull();
    expect(beatsUntilResolve({ current_stage: 0, beats_left: 0, beats_until_resolve: 0 })).toBeNull();
  });

  it('falls back to beats_left for a stage-less payload, which carries no better answer', () => {
    expect(beatsUntilResolve({ name: 'Cackle', beats_left: 2 })).toBe(2);
  });
});

describe('moveAvailability', () => {
  it('reports an available move as available with no reason', () => {
    expect(moveAvailability({ name: 'Slash', available: true })).toEqual({ available: true, reason: '' });
  });

  it('passes a server refusal straight through', () => {
    expect(moveAvailability({ available: false, reason: 'Not enough fatigue' }))
      .toEqual({ available: false, reason: 'Not enough fatigue' });
  });

  it('reports an unavailable move with no reason as unavailable, not as available', () => {
    expect(moveAvailability({ available: false })).toEqual({ available: false, reason: '' });
  });

  // The #554 case: advertised available, nothing actually in reach.
  it('withholds a targeted move whose viable-target list is empty', () => {
    expect(moveAvailability({ available: true, targeted: true, viable_targets: [] }))
      .toEqual({ available: false, reason: NO_REACHABLE_TARGET_REASON });
  });

  it('treats a missing viable_targets on a targeted move the same way', () => {
    expect(moveAvailability({ available: true, targeted: true }).available).toBe(false);
  });

  it('prefers the server reason over the derived one when both apply', () => {
    expect(moveAvailability({
      available: true,
      targeted: true,
      viable_targets: [],
      reason: 'Enemy out of range (too far)',
    })).toEqual({ available: false, reason: 'Enemy out of range (too far)' });
  });

  it('leaves a non-targeted move alone — an empty list is not its target list', () => {
    expect(moveAvailability({ available: true, targeted: false, viable_targets: [] }).available).toBe(true);
    expect(moveAvailability({ available: true, viable_targets: [] }).available).toBe(true);
  });

  it('keeps a targeted move with something in reach', () => {
    expect(moveAvailability({ available: true, targeted: true, viable_targets: [{ id: 'enemy_1' }] }))
      .toEqual({ available: true, reason: '' });
  });

  it('treats nothing as unavailable rather than crashing', () => {
    expect(moveAvailability(null)).toEqual({ available: false, reason: '' });
    expect(moveAvailability(undefined)).toEqual({ available: false, reason: '' });
  });
});

// #576: the backend has computed and shipped `damage_preview` on every target
// card since #555, but it lives per-target (viable_targets / target_previews /
// affected_preview — see ApiCombatAdapter._build_target_entry), never on the
// move option itself, and nothing on the client read it. This is the
// selector a move card uses to show ONE honest range without pretending a
// move has a single number when it can face more than one candidate.
describe('moveDamagePreview', () => {
  it("returns the sole viable target's own preview for a targeted move", () => {
    const move = {
      targeted: true,
      viable_targets: [{ id: 'enemy_1', damage_preview: { min: 12, max: 18, lethal: false } }],
    };
    expect(moveDamagePreview(move)).toEqual({ min: 12, max: 18, lethal: false });
  });

  it('returns null when the sole viable target carries no preview', () => {
    const move = { targeted: true, viable_targets: [{ id: 'enemy_1', damage_preview: null }] };
    expect(moveDamagePreview(move)).toBeNull();
  });

  it('returns null for a targeted move with no viable targets', () => {
    expect(moveDamagePreview({ targeted: true, viable_targets: [] })).toBeNull();
  });

  it('returns null when more than one viable target makes the range ambiguous', () => {
    const move = {
      targeted: true,
      viable_targets: [
        { id: 'enemy_1', damage_preview: { min: 5, max: 8, lethal: false } },
        { id: 'enemy_2', damage_preview: { min: 6, max: 9, lethal: false } },
      ],
    };
    expect(moveDamagePreview(move)).toBeNull();
  });

  it("folds an area move's affected_preview into one min/max/lethal range", () => {
    const move = {
      targeted: false,
      affected_preview: [
        { id: 'enemy_1', damage_preview: { min: 5, max: 10, lethal: false } },
        { id: 'enemy_2', damage_preview: { min: 8, max: 14, lethal: true } },
      ],
    };
    expect(moveDamagePreview(move)).toEqual({ min: 5, max: 14, lethal: true });
  });

  it('ignores affected_preview entries with no preview of their own', () => {
    const move = {
      targeted: false,
      affected_preview: [
        { id: 'enemy_1', damage_preview: null },
        { id: 'enemy_2', damage_preview: { min: 3, max: 6, lethal: false } },
      ],
    };
    expect(moveDamagePreview(move)).toEqual({ min: 3, max: 6, lethal: false });
  });

  it('returns null for a non-targeted move with nothing in its affected_preview', () => {
    expect(moveDamagePreview({ targeted: false, affected_preview: [] })).toBeNull();
    expect(moveDamagePreview({ targeted: false })).toBeNull();
  });

  it('treats nothing as no preview rather than crashing', () => {
    expect(moveDamagePreview(null)).toBeNull();
    expect(moveDamagePreview(undefined)).toBeNull();
  });
});
