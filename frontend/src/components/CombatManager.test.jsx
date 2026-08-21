import React from 'react'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import CombatManager from './CombatManager'

/**
 * CombatManager is a pure router: given four booleans and one `endState` it
 * decides which of four dialogs mount and which props each receives. So the
 * only two things worth proving here are (a) the visibility matrix and (b) that
 * every prop arrives intact at the right child.
 *
 * The child mocks below therefore ECHO the props they were handed into
 * `data-*` attributes. The previous version rendered mocks that read
 * `endState.dropped_items` and `endState.exp_gained` as a number, and the
 * fixture was written to match — but the real payload
 * (ApiCombatAdapter._build_victory_summary, src/api/combat_adapter.py:~2145)
 * emits `items_dropped`, and `exp_gained` is a DICT of {category: amount}.
 * VictoryDialog.jsx:19-25 and LootDialog.jsx:136 both read the real names.
 * The old test could never have noticed: the mock agreed with the fixture.
 * `playerWeight`/`weightLimit` were not echoed at all, so three tests claiming
 * to "pass weight info" asserted nothing about weight.
 */
const echo = (testid, props) => (
  <div
    data-testid={testid}
    data-endstate={JSON.stringify(props.endState ?? null)}
    data-player-weight={String(props.playerWeight)}
    data-weight-limit={String(props.weightLimit)}
    data-text={props.text ?? ''}
    data-handlers={Object.keys(props).filter((k) => typeof props[k] === 'function').sort().join(',')}
  />
)

vi.mock('./VictoryDialog', () => ({
  default: (props) => (
    <div data-testid="victory-dialog">
      {echo('victory-props', props)}
      <button onClick={() => props.onContinueToLoot()}>Continue to loot</button>
      <button onClick={() => props.onClose()}>Close victory</button>
      <button onClick={() => props.onAllocatePoints('strength')}>Allocate</button>
    </div>
  ),
}))

vi.mock('./DefeatDialog', () => ({
  default: (props) => (
    <div data-testid="defeat-dialog">
      {echo('defeat-props', props)}
      <button onClick={() => props.onLoadedSave()}>Retry</button>
    </div>
  ),
}))

vi.mock('./LootDialog', () => ({
  default: (props) => (
    <div data-testid="loot-dialog">
      {echo('loot-props', props)}
      <button onClick={() => props.onCollect()}>Collect</button>
      <button onClick={() => props.onSkip()}>Skip</button>
    </div>
  ),
}))

vi.mock('./PreVictoryNarrativeDialog', () => ({
  default: (props) => (
    <div data-testid="pre-victory-narrative-dialog">
      {echo('narrative-props', props)}
      <button onClick={() => props.onClose()}>Dismiss narrative</button>
    </div>
  ),
}))

/**
 * A victory `end_state` in the shape the engine actually produces.
 * Provenance: ApiCombatAdapter victory summary, src/api/combat_adapter.py —
 * `exp_gained` keyed by weapon subtype, `items_dropped` rows carrying
 * name/quantity plus the tile-enriched detail block.
 */
function makeVictoryEndState(overrides = {}) {
  return {
    id: 'end-0001',
    status: 'victory',
    message: 'Victory!',
    pre_victory_narrative: '',
    exp_gained: { Dagger: 60, general: 40 },
    items_dropped: [
      { name: 'Gold', quantity: 50, type: 'Consumable', subtype: 'Currency', weight: 0.0, value: 1 },
      { name: 'Rusty Dagger', quantity: 1, type: 'Weapon', subtype: 'Dagger', weight: 1.0, value: 10 },
    ],
    level_ups: [],
    ally_progression: [],
    attribute_points_available: 0,
    exp_to_next_level: 50,
    attributes: {
      strength_base: 10, finesse_base: 10, speed_base: 10,
      endurance_base: 10, charisma_base: 10, intelligence_base: 10,
    },
    ...overrides,
  }
}

const makeDefeatEndState = (overrides = {}) => ({
  id: 'end-0002',
  status: 'defeat',
  message: 'Jean has fallen.',
  ...overrides,
})

describe('CombatManager', () => {
  const mockCallbacks = {
    onAllocatePoints: vi.fn(),
    onVictoryClose: vi.fn(),
    onDefeatClose: vi.fn(),
    onContinueToLoot: vi.fn(),
    onCollectLoot: vi.fn(),
    onSkipLoot: vi.fn(),
    onPreVictoryNarrativeClose: vi.fn(),
  }

  const victory = makeVictoryEndState()
  const defeat = makeDefeatEndState()

  /** All four flags default to false so each case states only what it turns on. */
  const renderManager = (props = {}) =>
    render(
      <CombatManager
        showVictoryDialog={false}
        showDefeatDialog={false}
        showLootDialog={false}
        showPreVictoryNarrative={false}
        endState={null}
        playerWeight={0}
        weightLimit={100}
        {...mockCallbacks}
        {...props}
      />
    )

  /** The exact set of dialogs currently mounted, in DOM order. */
  const mounted = () =>
    Array.from(document.querySelectorAll('[data-testid$="-dialog"]'))
      .map((n) => n.getAttribute('data-testid'))

  const propsOf = (testid) => {
    const n = screen.getByTestId(testid)
    return {
      endState: JSON.parse(n.getAttribute('data-endstate')),
      playerWeight: n.getAttribute('data-player-weight'),
      weightLimit: n.getAttribute('data-weight-limit'),
      text: n.getAttribute('data-text'),
      handlers: n.getAttribute('data-handlers'),
    }
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('visibility matrix', () => {
    // Each row is (label, props, expected mounted dialogs). This replaces ~20
    // one-assertion tests that each rendered the same component with one flag
    // flipped; every distinct claim survives, and a dialog that leaks in
    // wrongly now fails the case that did not name it.
    it.each([
      ['nothing shown, no endState', {}, []],
      ['nothing shown even with a victory endState', { endState: victory }, []],
      ['victory only', { showVictoryDialog: true, endState: victory }, ['victory-dialog']],
      ['victory suppressed without an endState', { showVictoryDialog: true, endState: null }, []],
      ['loot only', { showLootDialog: true, endState: victory }, ['loot-dialog']],
      ['loot suppressed without an endState', { showLootDialog: true, endState: null }, []],
      ['defeat only', { showDefeatDialog: true, endState: defeat }, ['defeat-dialog']],
      ['defeat suppressed without an endState', { showDefeatDialog: true, endState: null }, []],
      [
        'defeat suppressed when the endState says victory',
        { showDefeatDialog: true, endState: victory },
        [],
      ],
      [
        'victory and loot can overlap during the hand-off',
        { showVictoryDialog: true, showLootDialog: true, endState: victory },
        ['victory-dialog', 'loot-dialog'],
      ],
      [
        'victory wins over defeat when the endState is a victory',
        { showVictoryDialog: true, showDefeatDialog: true, endState: victory },
        ['victory-dialog'],
      ],
      [
        'narrative only, and it precedes the victory dialog',
        {
          showPreVictoryNarrative: true,
          endState: makeVictoryEndState({ pre_victory_narrative: 'The camp erupts in cheers.' }),
        },
        ['pre-victory-narrative-dialog'],
      ],
      [
        'narrative suppressed when the endState carries no narrative text',
        { showPreVictoryNarrative: true, endState: victory },
        [],
      ],
      [
        'narrative suppressed when the flag is off, victory takes over',
        {
          showPreVictoryNarrative: false,
          showVictoryDialog: true,
          endState: makeVictoryEndState({ pre_victory_narrative: 'The camp erupts in cheers.' }),
        },
        ['victory-dialog'],
      ],
    ])('%s', (_label, props, expected) => {
      renderManager(props)
      expect(mounted()).toEqual(expected)
    })

    it('renders no DOM at all when every dialog is off', () => {
      // Replaces a test whose only assertion was `expect(true).toBe(true)`.
      const { container } = renderManager({ endState: victory })
      expect(container.innerHTML).toBe('')
    })
  })

  describe('prop forwarding', () => {
    it('hands VictoryDialog the whole endState untouched', () => {
      renderManager({ showVictoryDialog: true, endState: victory })
      // Deep equality, not a single field: a manager that reshapes or drops
      // part of the summary (exp_gained, level_ups, attributes) breaks the
      // dialog silently, because every read there sits behind `|| {}`.
      expect(propsOf('victory-props').endState).toEqual(victory)
    })

    it('hands LootDialog the endState AND both weight numbers', () => {
      renderManager({ showLootDialog: true, endState: victory, playerWeight: 45.5, weightLimit: 50 })
      const p = propsOf('loot-props')
      expect(p.endState.items_dropped).toEqual(victory.items_dropped)
      // LootDialog computes its encumbrance bar from these two; dropping
      // either silently defaults them (0 / 100) and the bar lies.
      expect(p.playerWeight).toBe('45.5')
      expect(p.weightLimit).toBe('50')
    })

    it.each([
      ['zero limits', 0, 0],
      ['large values', 9999, 10000],
    ])('forwards %s verbatim rather than substituting a default', (_label, w, limit) => {
      renderManager({ showLootDialog: true, endState: victory, playerWeight: w, weightLimit: limit })
      const p = propsOf('loot-props')
      expect(p.playerWeight).toBe(String(w))
      expect(p.weightLimit).toBe(String(limit))
    })

    it('hands DefeatDialog the defeat endState', () => {
      renderManager({ showDefeatDialog: true, endState: defeat })
      expect(propsOf('defeat-props').endState).toEqual(defeat)
    })

    it('hands PreVictoryNarrativeDialog the narrative TEXT, not the endState', () => {
      const endState = makeVictoryEndState({ pre_victory_narrative: 'The camp erupts in cheers.' })
      renderManager({ showPreVictoryNarrative: true, endState })
      expect(propsOf('narrative-props').text).toBe('The camp erupts in cheers.')
      expect(propsOf('narrative-props').endState).toBeNull()
    })

    it('re-forwards a replaced endState while the dialog stays mounted', () => {
      const first = makeVictoryEndState({ exp_gained: { Dagger: 100 } })
      const { rerender } = render(
        <CombatManager
          showVictoryDialog={true} showDefeatDialog={false} showLootDialog={false}
          endState={first} playerWeight={0} weightLimit={100} {...mockCallbacks}
        />
      )
      expect(propsOf('victory-props').endState.exp_gained).toEqual({ Dagger: 100 })

      const second = makeVictoryEndState({ exp_gained: { Dagger: 250, general: 5 } })
      rerender(
        <CombatManager
          showVictoryDialog={true} showDefeatDialog={false} showLootDialog={false}
          endState={second} playerWeight={0} weightLimit={100} {...mockCallbacks}
        />
      )
      expect(propsOf('victory-props').endState.exp_gained).toEqual({ Dagger: 250, general: 5 })
    })

    it('survives an endState whose optional fields are null', () => {
      const sparse = { status: 'victory', exp_gained: null, items_dropped: null }
      renderManager({ showVictoryDialog: true, showLootDialog: true, endState: sparse })
      expect(mounted()).toEqual(['victory-dialog', 'loot-dialog'])
      expect(propsOf('victory-props').endState).toEqual(sparse)
    })
  })

  describe('callback wiring', () => {
    // These handlers all take no arguments in production, so there is nothing
    // to assert about their payload; what matters is that each button reaches
    // its OWN handler and no other — the failure mode is a copy-paste swap.
    it.each([
      ['Continue to loot', { showVictoryDialog: true, endState: victory }, 'onContinueToLoot'],
      ['Close victory', { showVictoryDialog: true, endState: victory }, 'onVictoryClose'],
      ['Retry', { showDefeatDialog: true, endState: defeat }, 'onDefeatClose'],
      ['Collect', { showLootDialog: true, endState: victory }, 'onCollectLoot'],
      ['Skip', { showLootDialog: true, endState: victory }, 'onSkipLoot'],
      [
        'Dismiss narrative',
        {
          showPreVictoryNarrative: true,
          endState: makeVictoryEndState({ pre_victory_narrative: 'Cheers.' }),
        },
        'onPreVictoryNarrativeClose',
      ],
    ])('"%s" fires only %s', (label, props, expectedKey) => {
      renderManager(props)
      fireEvent.click(screen.getByText(label))

      expect(mockCallbacks[expectedKey]).toHaveBeenCalledTimes(1)
      Object.entries(mockCallbacks)
        .filter(([key]) => key !== expectedKey)
        .forEach(([, fn]) => expect(fn).not.toHaveBeenCalled())
    })

    it('forwards the allocation argument to onAllocatePoints', () => {
      renderManager({ showVictoryDialog: true, endState: victory })
      fireEvent.click(screen.getByText('Allocate'))
      // The one callback here that carries a payload: the attribute chosen.
      expect(mockCallbacks.onAllocatePoints).toHaveBeenCalledWith('strength')
    })

    it('passes handler props straight through instead of substituting no-ops', () => {
      renderManager({ showVictoryDialog: true, endState: victory })
      expect(propsOf('victory-props').handlers)
        .toBe('onAllocatePoints,onClose,onContinueToLoot')

      render(
        <CombatManager
          showVictoryDialog={true} showDefeatDialog={false} showLootDialog={false}
          endState={victory} playerWeight={0} weightLimit={100}
        />
      )
      // With nothing wired, the child sees no handlers at all — CombatManager
      // does not paper over a missing callback with a silent no-op, which
      // would hide a mis-wired GamePage.
      expect(screen.getAllByTestId('victory-props')[1].getAttribute('data-handlers')).toBe('')
    })
  })
})
