import React from 'react'
import { describe, it, expect, vi } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { CATEGORY_GROUPS, groupHasMoves } from './categories'
import CombatMovePanel from '../components/CombatMovePanel'

vi.mock('../context/AudioContext', () => ({ useAudio: () => ({ playSFX: vi.fn() }) }))

/**
 * Cross-consumer contract for move-category → radial-button routing.
 *
 * CATEGORY_GROUPS has exactly two consumers:
 *   - LeftPanel.jsx  — decides WHICH radial buttons exist (via groupHasMoves)
 *   - CombatMovePanel.jsx — decides WHICH moves the opened panel lists
 *     (via movesInGroup)
 *
 * That mapping used to be duplicated in both files, and it drifted: the SPECIAL
 * filter matched three categories the engine never emits, so 8 castable moves
 * (7 Mastery + Reaper's Mark) had NO button at all. Each component's own test
 * file exercises its own half, and both halves passing is exactly the state the
 * bug shipped in — nothing asserted that the two AGREE.
 *
 * The engine-side half of the guard (every castable category maps to some
 * group, and no group filters for a category the engine never emits) is
 * tests/test_move_categories_ui_contract.py, which AST-parses src/moves/.
 * This file is the client-side half: given a move, the button LeftPanel would
 * show and the panel that would list it are the same one.
 */

/** Every engine category CATEGORY_GROUPS claims, flattened. */
const MAPPED_CATEGORIES = Object.values(CATEGORY_GROUPS).flat()
const GROUPS = Object.keys(CATEGORY_GROUPS)

/** Groups whose button LeftPanel would render for this move (its real gate). */
const gateGroupsFor = (move) => GROUPS.filter((group) => groupHasMoves([move], group))

/** Groups whose opened panel actually lists this move (the real component). */
const panelGroupsFor = (move) =>
  GROUPS.filter((group) => {
    render(
      <CombatMovePanel moves={[move]} category={group} onMoveClick={vi.fn()} onClose={vi.fn()} />
    )
    const listed = screen.queryByText(move.name) !== null
    cleanup()
    return listed
  })

describe('CATEGORY_GROUPS consumers agree', () => {
  it.each(MAPPED_CATEGORIES.map((c) => [c]))(
    'a %s move reaches exactly one button, and that button opens the panel that lists it',
    (category) => {
      const move = { id: category, name: `Test ${category} Move`, category, available: true }

      const gated = gateGroupsFor(move)
      const listed = panelGroupsFor(move)

      // Exactly one button — two would double-list the move, zero is the
      // original bug (a castable move with nowhere to click).
      expect(gated).toHaveLength(1)
      // …and the button LeftPanel shows is the panel that has the move.
      expect(listed).toEqual(gated)
    }
  )

  it.each([['Passive'], ['Supernatural'], ['Spiritual'], ['Special']])(
    'a %s move surfaces under no button and in no panel',
    (category) => {
      // `Passive` is non-castable by design (PassiveMove.viable() -> False).
      // `Supernatural`/`Spiritual`/`Special` have styling entries in
      // MOVE_CATEGORY_COLOR et al. but no engine move emits them yet; a group
      // filtering for one would be a button that opens an empty panel.
      const move = { id: category, name: `Test ${category} Move`, category, available: true }
      expect(gateGroupsFor(move)).toEqual([])
      expect(panelGroupsFor(move)).toEqual([])
    }
  )

  it('routes a mixed roster so every move is reachable from exactly one button', () => {
    const moves = MAPPED_CATEGORIES.map((category) => ({
      id: category,
      name: `Test ${category} Move`,
      category,
      available: true,
    }))

    const reachable = new Map()
    for (const group of GROUPS) {
      render(
        <CombatMovePanel moves={moves} category={group} onMoveClick={vi.fn()} onClose={vi.fn()} />
      )
      for (const move of moves) {
        if (screen.queryByText(move.name)) {
          reachable.set(move.name, [...(reachable.get(move.name) ?? []), group])
        }
      }
      cleanup()
    }

    expect(reachable.size).toBe(moves.length)
    for (const [name, groups] of reachable) {
      expect({ name, groups }).toEqual({ name, groups: [expect.any(String)] })
    }
  })

  it('both consumers read the shared map instead of re-implementing it', () => {
    // The drift happened because each file carried its own category list. A
    // component that filters on `category ===` or its own array literal has
    // reintroduced exactly that.
    const read = (p) => readFileSync(resolve(process.cwd(), p), 'utf8')
    const leftPanel = read('src/components/LeftPanel.jsx')
    const movePanel = read('src/components/CombatMovePanel.jsx')

    expect(leftPanel).toMatch(/import \{[^}]*groupHasMoves[^}]*\} from '\.\.\/utils\/categories'/)
    expect(movePanel).toMatch(/import \{[^}]*movesInGroup[^}]*\} from '\.\.\/utils\/categories'/)

    // A consumer naming a *group key* ('Offensive', 'Maneuver', ...) is correct
    // usage -- that is the button identity it passes to hasGroup/movesInGroup.
    // The drift signature is naming an engine category that is NOT a group key
    // (e.g. 'Mastery', 'Utility', 'Tactical'), because the only reason to write
    // one of those down is to re-decide membership locally.
    const groupKeys = new Set(Object.keys(CATEGORY_GROUPS))
    const nonGroupCategories = MAPPED_CATEGORIES.filter((c) => !groupKeys.has(c))
    expect(nonGroupCategories.length).toBeGreaterThan(0)

    for (const [file, source] of [['LeftPanel.jsx', leftPanel], ['CombatMovePanel.jsx', movePanel]]) {
      for (const category of nonGroupCategories) {
        expect(
          source.includes(`'${category}'`) || source.includes(`"${category}"`),
          `${file} names the engine category "${category}" directly; category membership belongs in utils/categories.js`
        ).toBe(false)
      }
    }
  })
})
