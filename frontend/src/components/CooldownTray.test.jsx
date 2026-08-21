import React from 'react'
import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent, within } from '@testing-library/react'
import CooldownTray from './CooldownTray'
import { categoryColor, categoryIcon } from '../utils/categories'
import { colors } from '../styles/theme'

/**
 * CooldownTray renders the moves LeftPanel filtered down to
 * `(m.cooldown_remaining || 0) > 0`.
 *
 * WIRE CONTRACT (ApiCombatAdapter._get_available_moves, combat_adapter.py):
 * a move option carries `cooldown_remaining` and `cooldown_max` — NOT
 * `beats_left`, which is the *skills* payload's field (get_player_skills) and
 * the status-effect field. The adapter derives them from beats_left:
 *
 *     cooldown_remaining = move.beats_left + 1 if beats_left > 0 else 1
 *     cooldown_max       = max(stage_beat[3] + 1, cooldown_remaining)
 *
 * so `cooldown_remaining` is never 0 for a move the tray actually receives.
 * `duration_remaining` vs `beats_left` was one of the six shipped wire-drift
 * bugs; these fixtures therefore use the adapter's names and its arithmetic.
 *
 * The `category` values below are the ones `grep -rE "category\s*=" src/moves/`
 * actually produces: Offensive, Maneuver, Mastery, Defensive, Utility,
 * Tactical, Miscellaneous. The previous fixtures in this file used 'Attack',
 * 'Special' and 'Misc' — categories the engine never emits — so every
 * "renders categories correctly" test was silently exercising the *fallback*
 * colour/icon while claiming to prove the mapping.
 */

/** Build a move option the way the adapter would, from an engine beats_left. */
function makeCooldownMove({ id, name, category, beats_left, stage3_beats, ...rest }) {
  const cooldownRemaining = beats_left > 0 ? beats_left + 1 : 1
  return {
    id,
    name,
    category,
    available: false,
    reason: beats_left > 0 ? `Available in ${beats_left + 1} beats` : 'Available next beat',
    cooldown_remaining: cooldownRemaining,
    cooldown_max: Math.max((stage3_beats ?? beats_left) + 1, cooldownRemaining),
    ...rest,
  }
}

const SLASH = makeCooldownMove({ id: '3', name: 'Slash', category: 'Offensive', beats_left: 1, stage3_beats: 2 })
const KEEP_AWAY = makeCooldownMove({ id: '7', name: 'KeepAway', display_name: 'Keep Away', category: 'Maneuver', beats_left: 0, stage3_beats: 3 })
const REAPERS_MARK = makeCooldownMove({ id: '11', name: "Reaper's Mark", category: 'Mastery', beats_left: 4, stage3_beats: 4 })

const MOVES = [SLASH, KEEP_AWAY, REAPERS_MARK]

/** The tray root (the element carrying the hover handlers). */
const trayRoot = (container) => container.firstChild

/** The one-pixel progress bar's fill div inside an expanded card. */
function fillOf(card) {
  const track = card.querySelector('div[style*="height: 3px"]')
  expect(track).not.toBeNull()
  return track.firstChild
}

/**
 * The base colour of an element's border, as a #rrggbb string.
 * The component writes `1px solid ${color}99`; jsdom normalises the 8-digit hex
 * to `rgba(r, g, b, 0.6)`, so compare the channels rather than the literal.
 */
function borderHex(el) {
  const m = el.style.border.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/)
  expect(m).not.toBeNull()
  return '#' + [1, 2, 3].map(i => Number(m[i]).toString(16).padStart(2, '0')).join('')
}

/** The expanded card containing a given move label. */
const cardFor = (label) => screen.getByText(label).closest('div[style*="padding: 7px 9px"]')

describe('CooldownTray', () => {
  describe('visibility', () => {
    it.each([
      ['an empty array', []],
      ['undefined', undefined],
      ['null', null],
    ])('renders nothing for %s', (_label, moves) => {
      const { container } = render(<CooldownTray moves={moves} />)
      expect(container.firstChild).toBeNull()
    })

    it('labels the section and counts exactly the moves it was given', () => {
      const { container } = render(<CooldownTray moves={MOVES} />)
      expect(screen.getByText('Cooldown')).toBeInTheDocument()
      // The badge is the move COUNT, not a cooldown value — with 3 moves whose
      // remaining beats are 2/1/5 it must read 3.
      const header = screen.getByText('Cooldown').parentElement
      expect(within(header).getByText('3')).toBeInTheDocument()
      // One collapsed card per move.
      expect(trayRoot(container).lastChild.children).toHaveLength(3)
    })
  })

  describe('collapsed cards', () => {
    it('shows each move\'s remaining beats and category icon, and no move names', () => {
      const { container } = render(<CooldownTray moves={MOVES} />)
      const cards = trayRoot(container).lastChild.children

      // Slash: beats_left 1 -> cooldown_remaining 2.
      expect(cards[0].textContent).toBe(`${categoryIcon('Offensive')}2`)
      // KeepAway: beats_left 0 -> "available next beat" -> 1, never 0.
      expect(cards[1].textContent).toBe(`${categoryIcon('Maneuver')}1`)
      // Reaper's Mark: beats_left 4 -> 5.
      expect(cards[2].textContent).toBe(`${categoryIcon('Mastery')}5`)

      // Collapsed is the compact form: names appear only once expanded.
      expect(screen.queryByText('Slash')).toBeNull()
      expect(screen.queryByText('Keep Away')).toBeNull()
    })

    it('colours each collapsed card by its engine category', () => {
      const { container } = render(<CooldownTray moves={MOVES} />)
      const cards = trayRoot(container).lastChild.children
      // Offensive is danger red, Maneuver is primary lime, Mastery is special
      // purple — three distinct values, so a collapsed mapping would fail here.
      expect(borderHex(cards[0])).toBe(colors.danger)
      expect(borderHex(cards[1])).toBe(colors.primary)
      expect(borderHex(cards[2])).toBe(colors.special)
      expect(categoryColor('Offensive')).toBe(colors.danger)
    })

    it('falls back to the muted colour and ◈ icon for a category the engine does not emit', () => {
      // 'Attack' is NOT an engine category (the real ones are Offensive,
      // Maneuver, Mastery, Defensive, Utility, Tactical, Miscellaneous), so it
      // must take the fallback rather than silently rendering as Offensive.
      const { container } = render(
        <CooldownTray moves={[makeCooldownMove({ id: '1', name: 'Punch', category: 'Attack', beats_left: 1 })]} />
      )
      const card = trayRoot(container).lastChild.firstChild
      expect(card.textContent).toBe('◈2')
      expect(borderHex(card)).toBe(colors.text.muted)
    })
  })

  describe('expanded cards', () => {
    it('expands on hover and collapses again on mouse leave', () => {
      const { container } = render(<CooldownTray moves={MOVES} />)
      const tray = trayRoot(container)

      expect(screen.queryByText('Slash')).toBeNull()
      fireEvent.mouseEnter(tray)
      expect(screen.getByText('Slash')).toBeInTheDocument()

      fireEvent.mouseLeave(tray)
      // The previous version of this test asserted NOTHING after the leave, so
      // a tray that never collapsed passed it.
      expect(screen.queryByText('Slash')).toBeNull()
      expect(screen.queryByText("Reaper's Mark")).toBeNull()
      // The count badge survives both states.
      expect(within(screen.getByText('Cooldown').parentElement).getByText('3')).toBeInTheDocument()
    })

    it('prefers display_name over the engine move name', () => {
      const { container } = render(<CooldownTray moves={MOVES} />)
      fireEvent.mouseEnter(trayRoot(container))
      // KeepAway ships display_name "Keep Away"; showing the raw class name
      // would be the regression.
      expect(screen.getByText('Keep Away')).toBeInTheDocument()
      expect(screen.queryByText('KeepAway')).toBeNull()
    })

    it('shows the remaining beats beside a "beats" unit label for every move', () => {
      const { container } = render(<CooldownTray moves={MOVES} />)
      fireEvent.mouseEnter(trayRoot(container))

      expect(within(cardFor('Slash')).getByText('2')).toBeInTheDocument()
      expect(within(cardFor('Keep Away')).getByText('1')).toBeInTheDocument()
      expect(within(cardFor("Reaper's Mark")).getByText('5')).toBeInTheDocument()
      expect(screen.getAllByText('beats')).toHaveLength(3)
    })

    it('updates the rendered countdown when the poll returns fewer beats', () => {
      const { container, rerender } = render(<CooldownTray moves={[SLASH]} />)
      fireEvent.mouseEnter(trayRoot(container))
      expect(within(cardFor('Slash')).getByText('2')).toBeInTheDocument()
      expect(fillOf(cardFor('Slash')).style.width).toBe('33%')

      rerender(<CooldownTray moves={[{ ...SLASH, cooldown_remaining: 1 }]} />)
      expect(within(cardFor('Slash')).getByText('1')).toBeInTheDocument()
      // 1 - 1/3 = 67% elapsed: the bar must advance with the countdown.
      expect(fillOf(cardFor('Slash')).style.width).toBe('67%')
      expect(screen.queryByText('2')).toBeNull()
    })
  })

  describe('progress bar', () => {
    // fillPct = round((1 - cooldown_remaining / cooldown_max) * 100), i.e. the
    // share of the cooldown ALREADY SERVED. Every one of the four tests this
    // replaces was named after a percentage and asserted only that the move's
    // name rendered — deleting the whole fillPct expression left them green.
    it.each([
      ['just started — 0% served', 5, 5, '0%'],
      ['half served', 2, 4, '50%'],
      ['one beat left of three', 1, 3, '67%'],
      ['about to expire', 1, 5, '80%'],
      // Rounding: 1 - 2/3 = 0.666… -> 67, not 66 (Math.round, not truncation).
      ['rounds to nearest, not down', 1, 3, '67%'],
    ])('fills the bar for a cooldown %s', (_label, remaining, max, expectedWidth) => {
      const move = { id: '1', name: 'Timed', category: 'Offensive', cooldown_remaining: remaining, cooldown_max: max }
      const { container } = render(<CooldownTray moves={[move]} />)
      fireEvent.mouseEnter(trayRoot(container))
      const fill = fillOf(cardFor('Timed'))
      expect(fill.style.width).toBe(expectedWidth)
      expect(fill.style.background).toBe('rgb(255, 68, 68)') // Offensive
    })

    it('renders a 0%-wide bar rather than NaN%/Infinity% when cooldown_max is 0', () => {
      const move = { id: '1', name: 'Odd', category: 'Offensive', cooldown_remaining: 2, cooldown_max: 0 }
      const { container } = render(<CooldownTray moves={[move]} />)
      fireEvent.mouseEnter(trayRoot(container))
      expect(fillOf(cardFor('Odd')).style.width).toBe('0%')
    })

    it('renders a move with no cooldown fields at all as an empty countdown, not "undefined"', () => {
      // Defensive: LeftPanel filters on cooldown_remaining, so this shape should
      // never reach the tray — but if it does, the card must not print the
      // string "undefined" at the player.
      const { container } = render(<CooldownTray moves={[{ id: 'x', name: 'Incomplete' }]} />)
      const collapsed = trayRoot(container).lastChild.firstChild
      expect(collapsed.textContent).toBe('◈')
      expect(collapsed.textContent).not.toContain('undefined')

      fireEvent.mouseEnter(trayRoot(container))
      expect(screen.getByText('Incomplete')).toBeInTheDocument()
      expect(fillOf(cardFor('Incomplete')).style.width).toBe('0%')
    })
  })

  describe('layout', () => {
    it('lays collapsed cards out in a wrapping row and expanded cards in a column', () => {
      const { container } = render(<CooldownTray moves={MOVES} />)
      const collapsedList = trayRoot(container).lastChild
      expect(collapsedList.style.flexWrap).toBe('wrap')
      expect(collapsedList.style.flexDirection).toBe('')

      fireEvent.mouseEnter(trayRoot(container))
      const expandedList = trayRoot(container).lastChild
      expect(expandedList.style.flexDirection).toBe('column')
      expect(expandedList.children).toHaveLength(3)
    })

    it('separates itself from the panel above with a top border and padding', () => {
      const { container } = render(<CooldownTray moves={MOVES} />)
      const tray = trayRoot(container)
      expect(tray.style.borderTop.replace(/\s+/g, '')).toBe('1pxsolidrgba(0,255,136,0.15)')
      expect(tray.style.paddingTop).toBe('8px')
      // flexShrink 0 keeps the tray from being squeezed out of a full LeftPanel.
      expect(tray.style.flexShrink).toBe('0')
    })

    it('renders one card per move for a long cooldown list without collapsing duplicates', () => {
      const many = Array.from({ length: 20 }, (_, i) =>
        makeCooldownMove({ id: `m${i}`, name: `Move ${i}`, category: 'Offensive', beats_left: i % 3 })
      )
      const { container } = render(<CooldownTray moves={many} />)
      expect(within(screen.getByText('Cooldown').parentElement).getByText('20')).toBeInTheDocument()
      expect(trayRoot(container).lastChild.children).toHaveLength(20)

      fireEvent.mouseEnter(trayRoot(container))
      expect(screen.getAllByText('beats')).toHaveLength(20)
      expect(screen.getByText('Move 19')).toBeInTheDocument()
    })
  })
})
