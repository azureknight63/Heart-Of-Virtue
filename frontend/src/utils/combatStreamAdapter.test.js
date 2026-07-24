import { describe, it, expect } from 'vitest';
import { beatToAnimations } from './combatStreamAdapter';

const combat = {
  player: { id: 'player', position: { x: 6, y: 6 } },
  enemies: [
    { id: 'enemy_1', position: { x: 8, y: 6 } },
    { id: 'enemy_2', position: { x: 9, y: 7 } },
  ],
};

const beat = (over = {}) => ({
  seq: 1,
  web_animation: 'attack',
  actor_id: 'player',
  target_id: 'enemy_1',
  outcome: 'hit',
  killed: [],
  departed: [],
  sfx: [{ index: 0, kind: 'impact', outcome: 'hit' }],
  ...over,
});

describe('beatToAnimations', () => {
  it('produces the actor move animation carrying the beat', () => {
    const [anim] = beatToAnimations(beat(), combat);
    expect(anim).toMatchObject({
      type: 'attack',
      source_id: 'player',
      target_id: 'enemy_1',
      outcome: 'hit',
    });
    expect(anim.beat.seq).toBe(1);
  });

  it('appends a suppressed death burst for each killed id with a position', () => {
    const anims = beatToAnimations(beat({ killed: ['enemy_1'] }), combat);
    const death = anims.find((a) => a.type === 'death');
    expect(death).toMatchObject({
      type: 'death',
      target_id: 'enemy_1',
      position: { x: 8, y: 6 },
      suppressSfx: true,
    });
  });

  it('skips a death burst when the entity/position is unknown', () => {
    const anims = beatToAnimations(beat({ killed: ['ghost_x'] }), combat);
    expect(anims.filter((a) => a.type === 'death')).toEqual([]);
  });

  it('handles multiple kills', () => {
    const anims = beatToAnimations(
      beat({ killed: ['enemy_1', 'enemy_2'] }),
      combat
    );
    expect(anims.filter((a) => a.type === 'death').map((a) => a.target_id)).toEqual([
      'enemy_1',
      'enemy_2',
    ]);
  });

  it('returns empty for a null beat', () => {
    expect(beatToAnimations(null, combat)).toEqual([]);
  });
});
