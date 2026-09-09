import { describe, it, expect } from 'vitest';
import { stackDisplayName } from './stackName';

describe('stackDisplayName', () => {
  // The engine's stack_grammar() bakes the count into the item's NAME for
  // stackable items (src/items.py: MineralPowder writes "Mineral Powder x3",
  // DriedCrystalSap writes "Dried Crystal Sap x3"), a leftover from the
  // terminal play mode where the name was the whole readout. The serializers
  // ship that name verbatim alongside a separate count/quantity field, so any
  // UI that renders both got "Mineral Powder x3 x3" (#565).
  it('drops a trailing count that duplicates the item stack size', () => {
    expect(stackDisplayName({ name: 'Mineral Powder x3', count: 3 })).toBe('Mineral Powder');
  });

  it('reads the stack size from `quantity` when that is the field present', () => {
    // The inventory and combat serializers emit `quantity`; the object/interact
    // serializer emits `count`. Same engine attribute, two wire names.
    expect(stackDisplayName({ name: 'Dried Crystal Sap x2', quantity: 2 })).toBe('Dried Crystal Sap');
  });

  it('accepts the multiplication sign as well as a plain x', () => {
    expect(stackDisplayName({ name: 'Mineral Powder ×4', count: 4 })).toBe('Mineral Powder');
  });

  it('leaves a trailing number that does NOT match the stack size alone', () => {
    // "Potion x3" with two in the stack is not a baked count — it is the name.
    // Stripping it would misreport the item.
    expect(stackDisplayName({ name: 'Potion x3', count: 2 })).toBe('Potion x3');
  });

  it('leaves the name alone for an unstacked item', () => {
    expect(stackDisplayName({ name: 'Iron Sword', count: 1 })).toBe('Iron Sword');
    expect(stackDisplayName({ name: 'Scroll x1', count: 1 })).toBe('Scroll x1');
  });

  it('does not eat a name that legitimately ends in x plus digits', () => {
    // Only a SPACE-separated suffix is a stack marker; "Elixir x9" glued as
    // "Elixirx9" is part of the name.
    expect(stackDisplayName({ name: 'Elixirx9', count: 9 })).toBe('Elixirx9');
  });

  it('survives a missing or non-string name', () => {
    expect(stackDisplayName({ count: 3 })).toBe('');
    expect(stackDisplayName(null)).toBe('');
    expect(stackDisplayName({ name: 42, count: 3 })).toBe('');
  });

  it('is idempotent, so it stays a no-op once the engine stops baking the count', () => {
    const once = stackDisplayName({ name: 'Mineral Powder x3', count: 3 });
    expect(stackDisplayName({ name: once, count: 3 })).toBe('Mineral Powder');
  });
});
