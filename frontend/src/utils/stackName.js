/**
 * A space, then `x` or `×`, then a run of digits, at the very end.
 *
 * Module scope, and matched-then-compared rather than interpolating `size`
 * into the pattern. Built per call it allocated a RegExp for every rendered
 * row across six call sites; and interpolating the number meant a size that
 * stringifies in exponential form (`1e+21`) injected a `+` quantifier into
 * the pattern.
 */
const BAKED_COUNT = /\s[x×](\d+)$/i;

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
 * "Mineral Powder x3 x3" in a container, and the same doubling anywhere a
 * stackable name is rendered beside its own count (#565) -- the container and
 * target lists, the inventory card badge, the loot row, the item-detail panel,
 * the shop rows and the party inventory.
 *
 * No count of adopters is kept here on purpose: the last enumeration went stale
 * within the same pass, claiming the migration was complete while the shop and
 * party surfaces still doubled.
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

  const baked = name.match(BAKED_COUNT);
  return baked && Number(baked[1]) === size ? name.slice(0, baked.index) : name;
};

/**
 * The stack-count badge, in the one spelling the app uses.
 *
 * There were four (`(x3)`, `x3`, `×3`, `×{quantity}`) across six components,
 * with nothing marking which was canonical, so normalising one site gave no
 * clue what to normalise to. `×` wins on count and is the typographically
 * correct multiplication sign.
 *
 * Returns '' for an unstacked item so callers can render it unconditionally.
 */
export const stackCountLabel = (count) => (Number(count) > 1 ? `×${count}` : '')
