import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import MobileTabBar from './MobileTabBar'
import { TAB_KEYS } from '../utils/mobileTabs'

// Theme tokens the component paints with, as jsdom serialises them.
const ACTIVE_LEFT = 'rgb(0, 255, 136)'   // colors.primary
const ACTIVE_RIGHT = 'rgb(255, 170, 0)'  // colors.secondary
const INACTIVE = 'rgb(136, 136, 136)'    // colors.text.muted

describe('MobileTabBar', () => {
  const renderBar = (props = {}) => {
    const onTabChange = vi.fn()
    const utils = render(
      <MobileTabBar
        activeTab={TAB_KEYS.left}
        onTabChange={onTabChange}
        mode="exploration"
        {...props}
      />
    )
    return { ...utils, onTabChange }
  }

  /** The two tab buttons, left slot first. */
  const tabs = () => screen.getAllByRole('button')

  /** How a tab is painted: an active tab takes its accent for text AND top rule. */
  const paint = (button) => ({
    color: button.style.color,
    borderTop: button.style.borderTop,
  })

  describe('labels', () => {
    it('labels the two panel slots CHARACTER / MAP in exploration', () => {
      renderBar({ mode: 'exploration' })

      expect(tabs().map((b) => b.textContent)).toEqual(['🧝CHARACTER', '🗺️MAP'])
    })

    it('relabels the same two slots COMBAT / BATTLEFIELD in combat', () => {
      renderBar({ mode: 'combat' })

      // Same icons, same slot order — only the words change.
      expect(tabs().map((b) => b.textContent)).toEqual(['🧝COMBAT', '🗺️BATTLEFIELD'])
    })

    it('treats any non-exploration mode as combat for labelling purposes', () => {
      // `mode` is a free-form string from GamePage; only 'exploration' is special.
      renderBar({ mode: 'unknown' })

      expect(tabs().map((b) => b.textContent)).toEqual(['🧝COMBAT', '🗺️BATTLEFIELD'])
    })
  })

  describe('tab keys (regression: the mid-combat blank screen)', () => {
    // These used to emit 'combat'/'battlefield'. GamePage's panelWrap() only
    // compares against TAB_KEYS.left/right, so those keys matched NEITHER panel
    // slot, hid both, and left the player staring at a blank screen mid-fight.
    it.each([
      ['exploration', 'CHARACTER', 'MAP'],
      ['combat', 'COMBAT', 'BATTLEFIELD'],
    ])('emits the panel-slot keys, not mode-specific ones, in %s mode', (mode, leftLabel, rightLabel) => {
      const { onTabChange } = renderBar({ mode, activeTab: null })

      fireEvent.click(screen.getByText(leftLabel))
      fireEvent.click(screen.getByText(rightLabel))

      expect(onTabChange.mock.calls.map((c) => c[0])).toEqual([TAB_KEYS.left, TAB_KEYS.right])
    })

    it('emits the identical key space across a mode switch', () => {
      const onTabChange = vi.fn()
      const { rerender } = render(
        <MobileTabBar activeTab={TAB_KEYS.left} onTabChange={onTabChange} mode="exploration" />
      )
      fireEvent.click(screen.getByText('MAP'))

      rerender(<MobileTabBar activeTab={TAB_KEYS.left} onTabChange={onTabChange} mode="combat" />)
      fireEvent.click(screen.getByText('BATTLEFIELD'))

      expect(onTabChange.mock.calls.map((c) => c[0])).toEqual([TAB_KEYS.right, TAB_KEYS.right])
    })

    it('re-emits the active tab key when the active tab is clicked again', () => {
      // Not a no-op guard: the component always reports the click, and GamePage
      // setting the state it already holds is a cheap no-op render.
      const { onTabChange } = renderBar({ activeTab: TAB_KEYS.left })

      fireEvent.click(screen.getByText('CHARACTER'))

      expect(onTabChange).toHaveBeenCalledTimes(1)
      expect(onTabChange).toHaveBeenCalledWith(TAB_KEYS.left)
    })

    it('reports every click in a rapid switch, in order', () => {
      const { onTabChange } = renderBar()

      fireEvent.click(screen.getByText('MAP'))
      fireEvent.click(screen.getByText('CHARACTER'))
      fireEvent.click(screen.getByText('MAP'))

      expect(onTabChange.mock.calls.map((c) => c[0])).toEqual([
        TAB_KEYS.right, TAB_KEYS.left, TAB_KEYS.right,
      ])
    })
  })

  describe('active-tab highlighting', () => {
    it('accents the left tab and mutes the right when the left slot is active', () => {
      renderBar({ activeTab: TAB_KEYS.left })
      const [left, right] = tabs()

      expect(paint(left)).toEqual({ color: ACTIVE_LEFT, borderTop: `3px solid ${ACTIVE_LEFT}` })
      expect(paint(right)).toEqual({ color: INACTIVE, borderTop: '3px solid transparent' })
    })

    it('accents the right tab and mutes the left when the right slot is active', () => {
      renderBar({ activeTab: TAB_KEYS.right })
      const [left, right] = tabs()

      expect(paint(left)).toEqual({ color: INACTIVE, borderTop: '3px solid transparent' })
      expect(paint(right)).toEqual({ color: ACTIVE_RIGHT, borderTop: `3px solid ${ACTIVE_RIGHT}` })
    })

    it('highlights in combat mode too, using the same panel keys', () => {
      // The old mode-specific keys also meant NEITHER tab ever highlighted
      // during combat — the bar looked dead for the whole fight.
      renderBar({ mode: 'combat', activeTab: TAB_KEYS.right })

      expect(screen.getByText('BATTLEFIELD').closest('button').style.color).toBe(ACTIVE_RIGHT)
      expect(screen.getByText('COMBAT').closest('button').style.color).toBe(INACTIVE)
    })

    it.each([
      ['undefined', undefined],
      ['null', null],
      ['an unrecognised key', 'battlefield'],
    ])('mutes both tabs when activeTab is %s', (_label, activeTab) => {
      renderBar({ activeTab })

      tabs().forEach((b) =>
        expect(paint(b)).toEqual({ color: INACTIVE, borderTop: '3px solid transparent' })
      )
    })

    it('repaints when activeTab changes without remounting', () => {
      const { rerender } = renderBar({ activeTab: TAB_KEYS.left })
      const [left] = tabs()
      expect(left.style.color).toBe(ACTIVE_LEFT)

      rerender(<MobileTabBar activeTab={TAB_KEYS.right} onTabChange={vi.fn()} mode="exploration" />)

      // Same node, new paint — React reuses the button rather than remounting.
      expect(tabs()[0]).toBe(left)
      expect(left.style.color).toBe(INACTIVE)
    })
  })

  describe('layout', () => {
    it('pins the bar to the bottom above every panel, with safe-area padding', () => {
      const { container } = renderBar()
      const bar = container.firstChild

      // A tab bar that scrolls away or sits under a dialog is unusable on
      // mobile, so the positioning is part of the contract.
      expect(bar.style.position).toBe('fixed')
      expect(bar.style.bottom).toBe('0px')
      expect(bar.style.zIndex).toBe('1000')
      expect(bar.style.height).toBe('56px')
      // NOTE: the `paddingBottom: env(safe-area-inset-bottom)` on this element
      // is deliberately not asserted — jsdom drops env() from both
      // CSSStyleDeclaration and the serialised style attribute, so any
      // assertion about it would only ever prove jsdom's limitation.
      // Exactly two equal-width slots.
      expect(tabs()).toHaveLength(2)
      tabs().forEach((b) => expect(b.style.flex).toBe('1 1 0%'))
    })

    it('gives each tab a touch-friendly hit target with no tap highlight', () => {
      renderBar()

      tabs().forEach((b) => {
        expect(b.style.touchAction).toBe('manipulation')
        expect(b.style.webkitTapHighlightColor).toBe('transparent')
      })
    })
  })
})
