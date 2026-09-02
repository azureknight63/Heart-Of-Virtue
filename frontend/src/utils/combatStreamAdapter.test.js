import { describe, it, expect } from 'vitest';
import { beatToAnimations } from './combatStreamAdapter';
import { MAX_BEAT_RESOLUTIONS } from './combatBeatSchema';

const combat = {
  player: { id: 'player', position: { x: 6, y: 6 } },
  enemies: [
    { id: 'enemy_1', position: { x: 8, y: 6 } },
    { id: 'enemy_2', position: { x: 9, y: 7 } },
  ],
  allies: [{ id: 'ally_1', position: { x: 5, y: 6 } }],
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

  it('tags the death burst with the side the dead combatant fought on', () => {
    // The fading token is drawn from this snapshot after the combatant has
    // left combat.allies/enemies, so alignment has to be carried here. Getting
    // it wrong paints a dying ally (or Jean) in hostile red for the fade.
    const sideOf = (id) =>
      beatToAnimations(beat({ killed: [id] }), combat).find((a) => a.type === 'death')
        ?.friendly;
    expect(sideOf('enemy_1')).toBe(false);
    expect(sideOf('ally_1')).toBe(true);
    expect(sideOf('player')).toBe(true);
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

  it('resolves the literal "player" sentinel as the killed entity', () => {
    // Engine beats address Jean as the string 'player', not by his id, so the
    // sentinel branch is the one that fires for a player death burst.
    const out = beatToAnimations(
      { web_animation: 'attack', actor_id: 'enemy_1', killed: ['player'] },
      combat
    );
    expect(out).toHaveLength(2);
    expect(out[1]).toMatchObject({ type: 'death', target_id: 'player' });
  });

  it('resolves the player by id as well as by sentinel', () => {
    const byId = {
      ...combat,
      player: { id: 'jean_1', position: { x: 2, y: 2 } },
    };
    const out = beatToAnimations(
      { web_animation: 'attack', actor_id: 'enemy_1', killed: ['jean_1'] },
      byId
    );
    expect(out[1]).toMatchObject({ type: 'death', position: { x: 2, y: 2 } });
  });

  it('emits no death burst when there is no combat snapshot to read from', () => {
    // The snapshot is what supplies the burst position; with none, the actor
    // animation must still survive rather than the whole beat being dropped.
    const out = beatToAnimations(
      { web_animation: 'attack', actor_id: 'enemy_1', killed: ['enemy_2'] },
      null
    );
    expect(out).toHaveLength(1);
    expect(out[0].type).toBe('attack');
  });

  it('treats a beat with no killed field as a plain move', () => {
    const out = beatToAnimations({ web_animation: 'attack', actor_id: 'enemy_1' }, combat);
    expect(out).toHaveLength(1);
  });

  it('returns empty for a null beat', () => {
    expect(beatToAnimations(null, combat)).toEqual([]);
  });

  // ── per-target fan-out (issue: an arc animated once and sounded 4×) ──────

  it('fans one full animation per impact resolution, each with its own target', () => {
    const anims = beatToAnimations(
      beat({
        web_animation: 'sweep',
        sfx: [
          { index: 0, kind: 'swing' },
          { index: 1, kind: 'impact', outcome: 'hit', target_id: 'enemy_1' },
          { index: 2, kind: 'impact', outcome: 'parry', target_id: 'enemy_2' },
        ],
      }),
      combat
    );
    const swings = anims.filter((a) => a.type === 'sweep');
    expect(swings).toHaveLength(2);
    expect(swings.map((a) => [a.source_id, a.target_id, a.outcome])).toEqual([
      ['player', 'enemy_1', 'hit'],
      ['player', 'enemy_2', 'parry'],
    ]);
  });

  it('only the first fanned animation carries the beat (SFX chain fires once)', () => {
    const anims = beatToAnimations(
      beat({
        sfx: [
          { index: 0, kind: 'impact', outcome: 'hit', target_id: 'enemy_1' },
          { index: 1, kind: 'impact', outcome: 'miss', target_id: 'enemy_2' },
        ],
      }),
      combat
    );
    expect(anims[0].beat).toBeTruthy();
    expect(anims[1].beat).toBeUndefined();
    expect(anims[1].suppressSfx).toBe(true);
  });

  it('stamps every emitted animation with swing_key = String(beat.seq)', () => {
    const anims = beatToAnimations(
      beat({
        seq: 42,
        killed: ['enemy_2'],
        sfx: [
          { index: 0, kind: 'impact', outcome: 'hit', target_id: 'enemy_1' },
          { index: 1, kind: 'impact', outcome: 'hit', target_id: 'enemy_2' },
        ],
      }),
      combat
    );
    expect(anims.length).toBeGreaterThanOrEqual(3); // 2 swings + 1 death burst
    for (const anim of anims) {
      expect(anim.swing_key).toBe('42');
    }
  });

  it('leaves swing_key undefined when the beat has no seq (back-compat match)', () => {
    const [anim] = beatToAnimations(
      { web_animation: 'attack', actor_id: 'enemy_1' },
      combat
    );
    expect(anim.swing_key).toBeUndefined();
  });

  it('falls back to the beat-level target/outcome for impacts without their own', () => {
    const [anim] = beatToAnimations(beat(), combat);
    expect(anim.target_id).toBe('enemy_1');
    expect(anim.outcome).toBe('hit');
  });

  it('caps the fan-out at MAX_BEAT_RESOLUTIONS', () => {
    const anims = beatToAnimations(
      beat({
        sfx: Array.from({ length: 100 }, (_, i) => ({
          index: i,
          kind: 'impact',
          outcome: 'hit',
          target_id: `enemy_${i}`,
        })),
      }),
      combat
    );
    expect(anims.filter((a) => a.type === 'attack')).toHaveLength(
      MAX_BEAT_RESOLUTIONS
    );
  });
});
