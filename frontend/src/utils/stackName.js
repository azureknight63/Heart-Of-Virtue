/**
 * The name to SHOW for a stackable item, with the engine's baked-in count
 * removed.
 *
 * The engine's `stack_grammar()` rewrites an item's own `name` to carry its
 * stack size — `src/items.py` has `MineralPowder` produce "Mineral Powder x3"
 * and `DriedCrystalSap` produce "Dried Crystal Sap x3". That is a leftover
 * from the terminal play mode, where the name was the entire readout. The API
 * serializers ship the name verbatim *and* a separate `count`/`quantity`
 * field, so every UI that renders both rendered the quantity twice:
 * "Mineral Powder x3 x3" in a container, and the same doubling on the
 * inventory card badge, the loot row and the item-detail Qty cell (#565).
 *
 * This is the client half of that fix. The engine half — not mutating `name`
 * in `stack_grammar()` — belongs in `src/`, and once it lands this function
 * becomes a no-op rather than needing removal.
 *
 * Deliberately conservative: the suffix is dropped only when the number in it
 * equals the stack size the item itself reports, so an item genuinely named
 * "Potion x3" sitting two-to-a-stack keeps its name.
 *
 * @param {{name?: string, count?: number, quantity?: number}|null} item
 * @returns {string} the display name, or '' when there is no usable name
 */
export const stackDisplayName = (item) => {
  const name = item?.name;
  if (typeof name !== 'string') return '';

  const size = Number(item.count ?? item.quantity ?? 1);
  if (!Number.isFinite(size) || size <= 1) return name;

  // A space, then `x` or `×`, then exactly the stack size, at the very end.
  const bakedCount = new RegExp(`\\s[x×]${size}$`, 'i');
  return name.replace(bakedCount, '');
};

export default stackDisplayName;
