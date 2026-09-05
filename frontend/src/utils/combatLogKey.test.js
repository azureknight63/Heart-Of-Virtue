import { describe, it, expect } from 'vitest';
import fs from 'fs';
import path from 'path';
import { logEntryKey, LOG_KEY_SEP, distinctLogCount } from './combatLogKey';

describe('logEntryKey', () => {
  it('separates fields so no value can collide across a boundary', () => {
    // Without a separator "ab"+"c" and "a"+"bc" would key identically.
    expect(logEntryKey({ round: 'ab', type: 'c', message: '' })).not.toBe(
      logEntryKey({ round: 'a', type: 'bc', message: '' }),
    );
  });

  it('uses a separator the engine never emits inside a message', () => {
    expect(LOG_KEY_SEP).toBe(String.fromCharCode(31));
    expect(logEntryKey({ message: 'a b c' })).toContain('a b c');
  });

  it('treats the repeated carriers of one swing as the same key', () => {
    // Load-bearing, not incidental: LeftPanel collapses these to one revealed
    // line while BattlefieldGrid keeps every repeat, one per target landing.
    const carrier = { round: 2, type: 'animation', message: 'Sweep animation' };
    expect(logEntryKey(carrier)).toBe(logEntryKey({ ...carrier }));
  });

  it('tolerates a missing or partial entry rather than throwing', () => {
    expect(() => logEntryKey(undefined)).not.toThrow();
    expect(logEntryKey({})).toBe(logEntryKey(undefined));
  });

  it('distinguishes identical lines from two different sources', () => {
    // Two same-named NPCs swinging in the same round emit byte-identical
    // carriers; without the carrier's source_id in the key they collapsed to
    // one revealed line and one swing.
    const line = { round: 3, type: 'animation', message: 'NpcAttack animation' };
    const a = { ...line, animation: { type: 'attack', source_id: 'enemy_rat_1' } };
    const b = { ...line, animation: { type: 'attack', source_id: 'enemy_rat_2' } };
    expect(logEntryKey(a)).not.toBe(logEntryKey(b));
    expect(distinctLogCount([a, b])).toBe(2);
  });

  it('still collapses one swing\'s per-target carriers (same source)', () => {
    const line = { round: 3, type: 'animation', message: 'Sweep animation' };
    const a = { ...line, animation: { type: 'sweep', source_id: 'player', target_id: 'foe_a' } };
    const b = { ...line, animation: { type: 'sweep', source_id: 'player', target_id: 'foe_b' } };
    expect(logEntryKey(a)).toBe(logEntryKey(b));
    expect(distinctLogCount([a, b])).toBe(1);
  });

  it('strips control characters so no field can forge a boundary', () => {
    // A message containing the separator itself must not shift later fields
    // across a boundary: the key always holds exactly three separators.
    const forged = {
      round: 1,
      type: 'combat',
      message: `x${LOG_KEY_SEP}animation`,
      animation: { source_id: `s${LOG_KEY_SEP}1` },
    };
    const key = logEntryKey(forged);
    expect(key.split(LOG_KEY_SEP)).toHaveLength(4);
    expect(key).toBe(logEntryKey({
      round: 1, type: 'combat', message: 'xanimation', animation: { source_id: 's1' },
    }));
  });
});

describe('no module keeps a private copy', () => {
  // Two byte-identical private definitions is exactly what this file replaced,
  // and nothing but a scan stops a third one appearing. If they drift, the
  // symptom is animations leading or trailing the revealed text -- which reads
  // as a timing bug and would be looked for anywhere but here.
  //
  // INVERTED on purpose. The previous version named the consumers it expected
  // to be clean, which is the enumeration drift this codebase keeps paying
  // for: it listed two of the three real importers (hooks/useCombatCoordinator
  // imports distinctLogCount and was never listed), and a fourth consumer that
  // rolled its own key would pass by simply not appearing in the array. This
  // scans the whole of src/ and asserts the definition exists in exactly one
  // file, so a new copy fails wherever it lands and no list needs maintaining.
  const SRC = path.join(__dirname, '..');
  const PRIVATE_DEFINITION = /const\s+logEntryKey\s*=/;
  const OWNER = 'utils/combatLogKey.js';

  // Test files are excluded because they are not consumers: this very file
  // carries the pattern as a string literal in its own self-check below, and
  // matching that would make the scan permanently red for no defect.
  const walk = (dir) => fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const full = path.join(dir, e.name);
    if (e.isDirectory()) return walk(full);
    return /\.jsx?$/.test(e.name) && !/\.(test|spec)\.jsx?$/.test(e.name) ? [full] : [];
  });

  const sourceFiles = walk(SRC).map((f) => path.relative(SRC, f).split(path.sep).join('/'));

  it('scans a src/ tree it actually found', () => {
    // A walk that silently returned nothing would make the scan below
    // vacuously green -- the exact failure mode this describe block exists to
    // prevent, one level up.
    expect(sourceFiles.length).toBeGreaterThan(50);
    expect(sourceFiles).toContain(OWNER);
  });

  it(`defines logEntryKey in ${OWNER} and nowhere else in src/`, () => {
    const definers = sourceFiles.filter((file) => PRIVATE_DEFINITION.test(
      fs.readFileSync(path.join(SRC, file), 'utf8'),
    ));
    expect(definers).toEqual([OWNER]);
  });

  it('the scan can actually find a private definition', () => {
    expect('const logEntryKey = (entry) =>').toMatch(PRIVATE_DEFINITION);
  });
});

describe('distinctLogCount', () => {
  it('counts one swing\'s identical carriers as a single entry', () => {
    // A four-target sweep: four byte-identical carriers, one revealed line.
    const carrier = { round: 2, type: 'animation', message: 'Sweep animation' };
    const log = [
      { round: 1, type: 'combat', message: 'Jean swings.' },
      carrier, { ...carrier }, { ...carrier }, { ...carrier },
    ];
    expect(log.length).toBe(5);
    expect(distinctLogCount(log)).toBe(2);
  });

  it('is what a revealed-count comparison must use', () => {
    // The defect: raw length permanently exceeds LeftPanel's deduped count
    // once any multi-target swing lands, so `log.length > displayedLogCount`
    // never goes false and the victory dialog never fires.
    const carrier = { round: 2, type: 'animation', message: 'Sweep animation' };
    const log = [carrier, { ...carrier }, { ...carrier }];
    const displayedLogCount = distinctLogCount(log); // what LeftPanel reports
    expect(log.length > displayedLogCount).toBe(true); // the broken comparison
    expect(distinctLogCount(log) > displayedLogCount).toBe(false); // the fix
  });

  it('tolerates an empty or missing log', () => {
    expect(distinctLogCount([])).toBe(0);
    expect(distinctLogCount(undefined)).toBe(0);
  });
});
