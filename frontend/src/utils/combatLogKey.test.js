import { describe, it, expect } from 'vitest';
import fs from 'fs';
import path from 'path';
import { logEntryKey, LOG_KEY_SEP } from './combatLogKey';

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
});

describe('no component keeps a private copy', () => {
  // Two byte-identical private definitions is exactly what this file replaced,
  // and nothing but a scan stops a third one appearing. If they drift, the
  // symptom is animations leading or trailing the revealed text -- which reads
  // as a timing bug and would be looked for anywhere but here.
  const components = ['LeftPanel.jsx', 'BattlefieldGrid.jsx'];

  it.each(components)('%s imports the shared key rather than defining one', (file) => {
    const source = fs.readFileSync(
      path.join(__dirname, '..', 'components', file),
      'utf8',
    );
    expect(source).not.toMatch(/const\s+logEntryKey\s*=/);
    expect(source).toMatch(/combatLogKey/);
  });

  it('the scan can actually find a private definition', () => {
    expect('const logEntryKey = (entry) =>').toMatch(/const\s+logEntryKey\s*=/);
  });
});
