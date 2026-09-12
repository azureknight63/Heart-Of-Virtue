import { describe, it, expect } from 'vitest'
import {
  makeAvailableOption,
  makeEnemy,
  makeMove,
  makePassive,
  makeTargetOption,
  twoTargets,
} from './payloads'
import { autoResolvedTargetId, moveAvailability } from '../utils/combatMoveStatus'

describe('makeAvailableOption', () => {
  it('derives the index from the id the card carries, including an explicit undefined', () => {
    // _get_available_moves emits `"id": str(i), "index": i` from one `i`, so
    // an overridden id beside an independent default index describes a card
    // no server can send. `in` rather than `??`, as for `name`: with `??`,
    // `{ id: undefined }` took its index from the default '0' while the
    // spread still left the id itself undefined.
    expect(makeAvailableOption()).toMatchObject({ id: '0', index: 0 })
    expect(makeAvailableOption({ id: '3' }).index).toBe(3)
    // An idless card has no index either, rather than NaN: index follows its
    // source's absence the way display_name follows name's.
    const idless = makeAvailableOption({ id: undefined })
    expect(idless.id).toBeUndefined()
    expect(idless.index).toBeUndefined()
  })

  it('survives an explicitly absent target list, as `provided` promises', () => {
    // `viable_targets: undefined` means "the caller named it and left it
    // out"; the two fields derived from it must not throw on the way past.
    const card = makeAvailableOption({ viable_targets: undefined })
    expect(card.viable_targets).toBeUndefined()
    expect(card.requires_target_selection).toBe(false)
    expect(card.target_previews).toEqual([])
  })

  it("defaults to the engine's Attack with one enemy in reach: castable, and aimed at that enemy", () => {
    // Attack is a targeted move (src/moves/_utility.py passes targeted=True),
    // so the realistic default card carries one viable target, which the
    // client submits without asking.
    const attack = makeAvailableOption()
    expect(attack.targeted).toBe(true)
    expect(moveAvailability(attack)).toEqual({ available: true, reason: '' })
    expect(autoResolvedTargetId(attack)).toBe(makeTargetOption().id)
  })

  it('publishes no targets and no previews for an untargeted move, as the adapter does', () => {
    // _get_available_moves fills viable_targets only for a targeted move, and
    // _get_target_previews returns [] for any other.
    const spin = makeAvailableOption({ targeted: false })
    expect(spin.viable_targets).toEqual([])
    expect(spin.target_previews).toEqual([])
  })

  it('previews the viable targets by default, so no preview sits in reach beside an empty allow-list', () => {
    // _get_target_previews lists every candidate, in reach or not, so it
    // always holds the viable targets; an in-reach preview beside an empty
    // viable_targets list describes no payload the adapter can send.
    const two = twoTargets()
    expect(makeAvailableOption({ viable_targets: two }).target_previews).toEqual(two)
    expect(makeAvailableOption({ viable_targets: [] }).target_previews).toEqual([])
  })

  it('derives requires_target_selection from the targets it lists, as the adapter does', () => {
    // `is_targeted and len(viable_targets) > 1` (combat_adapter.py). A card
    // offering two targets and claiming it needs no selection is a payload
    // _get_available_moves cannot send.
    const two = twoTargets()
    expect(makeAvailableOption({ viable_targets: two }).requires_target_selection).toBe(true)
    expect(makeAvailableOption().requires_target_selection).toBe(false)
    expect(makeAvailableOption({ targeted: false }).requires_target_selection).toBe(false)
  })

  it('hands out its own preview list, so a test that mutates one leaves the other', () => {
    // _get_available_targets and _get_target_previews build two lists; one
    // array in both fields is a fixture no adapter response looks like.
    const card = makeAvailableOption()
    expect(card.target_previews).not.toBe(card.viable_targets)
  })
})

describe('makeTargetOption', () => {
  it('derives `lethal` from the health the card carries, as the engine does', () => {
    // Move.preview_payload's test is `high >= target.hp`, so a healthier
    // target is simply not a one-shot kill; a fixed `lethal: true` beside an
    // overridden health described a preview no adapter can send.
    expect(makeTargetOption().damage_preview.lethal).toBe(true)
    const healthy = makeTargetOption({ health: { current: 500, max: 500 } })
    expect(healthy.damage_preview.lethal).toBe(false)
  })

  it('derives lethal even when the caller supplies the preview', () => {
    // The derivation used to run BEFORE `merge(base, overrides)`, so an
    // explicit preview replaced the derived one wholesale and the card came
    // back with no `lethal` key -- a shape Move.preview_payload never sends.
    const survivable = makeTargetOption({ damage_preview: { min: 1, max: 2 } })
    expect(survivable.damage_preview).toEqual({ min: 1, max: 2, lethal: false })

    const fatal = makeTargetOption({
      health: { current: 3, max: 3 },
      damage_preview: { min: 1, max: 4 },
    })
    expect(fatal.damage_preview.lethal).toBe(true)
  })

  it('sends what an out-of-reach entry sends, from the distance alone', () => {
    // One override, because the adapter derives the rest from the band:
    // `in_range` false, an integer shortfall, a null preview, and no
    // `hit_chance` KEY at all -- the one field _build_target_entry omits
    // rather than nulls.
    const far = makeTargetOption({ distance: 8 })

    expect(far.in_range).toBe(false)
    expect(far.shortfall_ft).toBe(3)
    expect(far.damage_preview).toBeNull()
    expect('damage_preview' in far).toBe(true)
    expect('hit_chance' in far).toBe(false)
  })

  it('leaves an out-of-reach entry without a preview, as the adapter does', () => {
    // _build_target_entry still SENDS `damage_preview` past the move's reach,
    // as null (combat_adapter.py gates the value on `in_range`, not the key).
    // `hit_chance` is the one it omits outright.
    expect(makeTargetOption({ damage_preview: null }).damage_preview).toBeNull()
  })
})

describe.each([
  ['makeAvailableOption', makeAvailableOption],
  ['makePassive', makePassive],
  ['makeMove', makeMove],
])('%s', (_name, build) => {
  it('makes display_name follow name, including an explicit undefined', () => {
    expect(build({ name: 'Iron Fist' }).display_name).toBe('Iron Fist')
    // A nameless move has no display name either. Falling back with `??`
    // resurrected the default 'Attack' as the label of a move with no name.
    const nameless = build({ name: undefined })
    expect(nameless.name).toBeUndefined()
    expect(nameless.display_name).toBeUndefined()
  })
})

describe('the default enemy', () => {
  it('is the same Slime in the fight and on its target card', () => {
    // `distance` included: one payload cannot put the same enemy at two
    // proximities, and that is the field the two builders used to disagree on.
    const { id, name, health, distance } = makeEnemy()
    expect(makeTargetOption()).toMatchObject({ id, name, health, distance })
  })
})
