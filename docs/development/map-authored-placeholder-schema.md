# Map Authored Placeholder Schema (issue #463)

Documents the versioned placeholder format that replaced full-instance dumps
in Map Editor JSON, the class-level metadata contract that drives it, and the
runtime instantiation contract both loaders (`Universe` and the Map Editor)
share. See `src/map_placeholders.py` for the implementation; this doc is the
narrative overview referenced by the issue's acceptance criteria.

## Problem

`MapEditor.save_map()` used to walk every placed NPC/Item/Object/Event's
entire `__dict__` and write it verbatim: `{"__class__", "__module__",
"props"}`. A plain `Gold` pickup carried 18 keys nobody authored (`owner`,
`equip_states`, `interactions`, `skills`, ...); an `AfterDefeatingKingSlime`
event carried session bookkeeping (`thread`, `has_run`, `completed`,
`api_event_id`, ...) that has no business in a map template. `NPCSpawnerEvent`
(`src/story/effects.py`) was already the exception — class + count/params,
regenerated at runtime — and this issue generalizes that pattern to all four
map buckets.

## Schema

A placeholder is:

```json
{
  "class": "npc.MiloCurioDealer",
  "params": {
    "stock_count": 30,
    "overrides": { "hidden": false }
  }
}
```

- **`class`** — a bare `module.ClassName` string (same bare-module convention
  as legacy `__module__` fields and pickle saves; canonicalized through
  `functions.canonical_module_name()`). Also accepts the legacy `module:Class`
  separator (used by the pre-existing `{"__class_type__": "..."}` marker,
  which is otherwise unchanged and may still appear as a nested value).
- **`params`** — real constructor keyword arguments. May be omitted entirely
  for a zero-config placement (`{"class": "npc.Slime"}`) — no boilerplate
  empty `"params": {}` required.
- **`params.overrides`** — optional. Attributes applied via `setattr` *after*
  construction, for fields no constructor exposes (most enemy classes hardcode
  their entire stat block in a zero-arg `__init__`).
- Any value inside `params` (including inside `overrides`) may itself be a
  nested placeholder (container inventories, attached events) or the legacy
  `__class_type__` class-reference marker.
- Map-level: `"meta": {"schema_version": 2}` is written on every save as an
  informational marker (not load-bearing — format is detected per-element by
  shape, not by this flag).

## Class metadata contract

Each authorable class declares up to three class attributes (merged across
the MRO, so a subclass only needs to declare what it *adds* beyond its
family base):

| Attribute | Meaning |
|---|---|
| `MAP_AUTHORED_PARAMS` | Names that are genuine constructor kwargs for *some* class in the family. Only actually used for a concrete class if its own `__init__` accepts that name (checked via `inspect.signature`). |
| `MAP_AUTHORED_OVERRIDES` | Names that may be `setattr`'d after construction. This is a security boundary, not just a convenience — map JSON is attacker-influenceable, so a key not on this allow-list is dropped, never applied. |
| `MAP_AUTHORED_ATTR_ALIASES` | `{authored_name: actual_attribute_name}`, for the rare case where the two differ (e.g. `Book`'s `text` authored name must read the private `_text` cache, not the `text` property, which lazily loads the whole file from disk on access). |

A name may be declared in **both** `MAP_AUTHORED_PARAMS` and
`MAP_AUTHORED_OVERRIDES` — this is the common case for a family base class
(e.g. `NPC`) whose own constructor accepts a field, while a hardcoded
zero-arg subclass (`Slime`, `KingSlime`, ...) can only reach that same field
via `setattr`. Per concrete class, each name resolves to exactly one bucket:
`params` if that class's constructor accepts it, otherwise `overrides` if
declared there — never both.

### Default pruning

Before writing `overrides`, each candidate value is compared against a
freshly-constructed *reference* instance of the same class (built with the
same authored `params`). A value that matches the reference's default is
dropped — only genuine authored deltas survive. Without this, every
hardcoded-stat enemy would dump its entire stat/resistance block on *every*
placement, even completely untouched ones. Comparison happens on the
serialized form (not raw Python `!=`), since most engine classes don't define
`__eq__` and two independently-constructed but structurally-identical values
(e.g. a merchant's hardcoded `always_stock` item list) would otherwise always
compare as "different" by object identity.

If a reference instance can't be constructed without runtime context this
function doesn't have (most `Object`/`Event` classes require `player`/`tile`
positionally), every override candidate is kept rather than risk silently
dropping real customization — pruning is an optimization, never a
correctness requirement.

## Runtime instantiation contract

`map_placeholders.instantiate_placeholder(payload, player=None, tile=None)`:

1. Resolve `class` through `canonical_module_name()` + the shared
   `secure_pickle._is_allowed()` allow-list — the exact same trust boundary
   `Universe`'s pickle-save loader uses. A `src.`-prefixed reference is
   rejected outright (persisted data must store bare names by contract).
2. Recursively resolve any nested placeholder / class-type marker found in
   `params` before building the parent's constructor kwargs.
3. Build kwargs from `params` filtered to `MAP_AUTHORED_PARAMS ∩ __init__`'s
   real signature; inject `player`/`tile` if the constructor accepts them and
   the caller supplied them (mirrors `MapTile.spawn_npc/item/object/event`).
4. Construct the instance.
5. Apply `params.overrides` via `setattr`, filtered to
   `MAP_AUTHORED_OVERRIDES` — an unrecognized key is dropped, never applied.

Both real map-JSON readers — `Universe._deserialize_saved_instance` (the
game's boot loader) and the Map Editor's `load_map()` — call into this same
module, so they can't silently diverge on which classes are trusted or how a
reference resolves.

## Backward compatibility

Format is detected **per element** by shape, not by a global file version:

- `{"class", "params"}` → placeholder (this issue).
- `{"__class__", "__module__", "props"}` → legacy, reconstructed exactly as
  before.
- `{"__class_type__"}` → bare class reference, unchanged.

Nothing forces a migration. An element loaded from a legacy map is tagged
`_hov_placeholder_format = False` on the live instance; `save_map()` checks
this tag and keeps writing legacy shape for it until the user runs **Convert
Elements**, even if the class has since gained authored metadata. A newly
placed element (no tag yet) defaults to placeholder shape if its class
supports it.

## Convert Elements

A Map Editor action (`MapEditor.convert_elements()` /
`compute_convert_elements_report()` in `utils/map_generator.py`) converts
every not-yet-placeholder element on the *currently loaded* map in one pass,
then shows a review dialog before anything is saved to disk:

- **converted** — cleanly represented, nothing of note dropped.
- **needs review** — converted, but some non-standard attribute (not covered
  by the class's declared metadata, and not on the generic
  `_CONVERT_ELEMENTS_EXPECTED_DROPS` allow-list of expected runtime/circular
  names) was dropped — worth a manual look, listed by name.
- **skipped** — left as legacy shape entirely; the class has no authored
  metadata registered at all yet.

Save Map remains a separate, explicit step — Convert Elements only flips the
in-memory tag and shows the report.

## Security fix bundled with this change

`MapEditor.load_map()` previously had **no allow-list gate at all** —
unconditional `importlib.import_module` + `getattr` on whatever
`__module__`/`__class__` a map file contained. It's now routed through the
same `resolve_class()` (and therefore the same `secure_pickle` allow-list)
`Universe` already used, closing a gap the issue #463 audit surfaced
independently of the placeholder format itself. The two loaders also now
agree on module-prefix strictness (both reject a `src.`-prefixed reference
rather than the editor's previous tolerant stripping).

A related pre-existing bug was fixed alongside this: `WallSwitch` (unlike its
five sibling one-shot-attached-event objects — `Shrine`, `HealingSpring`,
`MarketBell`, `Fountain`, `StreetLantern`, `PrayerCandleRack`, `MarketGong`)
never cleared its fired `event_on`/`event_off` reference, leaving a dangling
reference to an already-consumed event.

## Measured results

Converting and re-saving all 17 real map files in `src/resources/maps/`
through Convert Elements + Save:

```
TOTAL: 792,754 -> 334,577 bytes  (57.8% smaller)
```

Every individual map file shrank (range: ~5%–82% smaller depending on how
NPC/Item-heavy the map is), with no change to authored gameplay behavior —
covered by `tests/test_map_placeholders.py`.

## Known limitations (documented, not fixed here)

- **`Gorran.name`** is a computed `@property` reading story-state flags
  ("Rock-Man" vs "Gorran"); an authored `name` override is meaningless for
  this one class since the getter ignores whatever was stored.
- **`MiloCurioDealer`**'s starting inventory includes a procedurally-enchanted
  item — the roll happens fresh on every load/conversion (matches existing
  shop-restock behavior), so `always_stock`/`inventory` never fully prunes to
  empty for this class even when nothing was authored-tweaked.
- Classes whose constructor requires `player`/`tile` positionally (most
  `Object`/`Event` classes) don't benefit from override pruning, since a
  reference instance can't be built without that runtime context — they fall
  back to keeping every override candidate (safe, just not maximally
  compact).
