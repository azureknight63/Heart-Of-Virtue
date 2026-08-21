import { describe, it, expect } from 'vitest';
import { beatToAnimations } from './combatStreamAdapter';

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
});
