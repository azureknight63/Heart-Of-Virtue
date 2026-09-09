import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { VIEW_MODE_FOLLOW, VIEW_MODE_FIT } from '../components/BattlefieldGrid'

/**
 * Everything that decides how the battlefield is framed, in one place.
 *
 * This was three useState, two useRef, two effects, a callback and three
 * derived values inline in a 390-line component that also owns beat-state
 * accumulation and log-index sync. Their lifetimes had already diverged once
 * and produced a real bug (see the per-fight reset below), which is the usual
 * fee for spreading one concern across a component's whole body.
 *
 * @param {object} combat the combat payload
 * @param {object} displayState the beat state currently rendered
 * @param {Function} anyEnemyOffScreen geometry predicate, injected so this hook
 *   holds no opinion about viewport size
 * @returns {{zoom, selectViewMode, enemyOffScreen, bannerVisible, bannerMessage}}
 */
export function useBattlefieldCamera(combat, displayState, anyEnemyOffScreen) {
  const [zoom, setZoom] = useState(VIEW_MODE_FOLLOW)
  const [showOffScreenBanner, setShowOffScreenBanner] = useState(false)
  const [didAutoFit, setDidAutoFit] = useState(false)
  const offScreenLatchRef = useRef(false)

  // One fight, one identity. `combat_id` is minted per fight by the adapter.
  const cameraKey = combat?.combat_id ?? null

  // Raw geometry, independent of the current camera, so widening does not
  // retroactively erase the reason it widened.
  const enemyOutsideFollowView = useMemo(
    () => anyEnemyOffScreen(displayState),
    [displayState, anyEnemyOffScreen]
  )

  // Suppressed while already in Fit Fight: there is nothing left to ask for.
  const enemyOffScreen = zoom !== VIEW_MODE_FIT && enemyOutsideFollowView

  /**
   * The player's camera choice, which stands for the rest of this fight.
   *
   * Nothing needs to record it: the settle effect below runs only when
   * `cameraKey` changes, so a manual choice cannot be undone until a new fight
   * arrives. (This used to write a claim ref that nothing read — the ref, its
   * sentinel and two docstrings describing a claim-check outlived the guard
   * they described.)
   */
  const selectViewMode = useCallback((mode) => {
    setDidAutoFit(false)
    setShowOffScreenBanner(false)
    setZoom(mode)
  }, [])

  /**
   * Settle the camera for this fight, once, on the commit the fight arrives.
   *
   * Frames the fight the player was actually handed (#561): spawn distance is
   * a per-encounter roll, so with Follow (±6 cells) as the default a fight
   * beginning at 7-8 ft opened on an empty map with a banner telling the
   * player to fix the framing themselves.
   *
   * Keyed on `cameraKey` ALONE, and that is what makes it entry-only. An
   * earlier version ran whenever the geometry demanded it, so a fight that
   * opened fully in view could still be widened later. `beat_states` is
   * per-ACTION, not per-fight -- the adapter rebuilds it for every move, and
   * only the combat-start payload makes `[0]` the opening state -- so an
   * unclaimed camera would have re-read `[0]` mid-fight and widened on some
   * later action's first beat. Reading it here, on the one commit where
   * `cameraKey` changes, is the only moment `[0]` genuinely means "how this
   * fight opened".
   *
   * `zoom` and `didAutoFit` are set together for the same reason: they were
   * per-mount while the claim was per-fight, so fight two inherited fight
   * one's Fit camera and announced "view widened" when nothing had.
   */
  useEffect(() => {
    const outsideAtEntry = anyEnemyOffScreen(combat?.beat_states?.[0] ?? combat)
    // Set from an effect, not derived during render: this reads geometry that
    // is only correct on this one commit. A render-derived equivalent would
    // re-evaluate against later, per-action beat states -- the bug this replaced.
    setZoom(outsideAtEntry ? VIEW_MODE_FIT : VIEW_MODE_FOLLOW)
    setDidAutoFit(outsideAtEntry)
    // eslint-disable-next-line react-hooks/exhaustive-deps -- cameraKey ONLY, on purpose: `combat` changes on every poll, and re-running then is precisely the bug this replaced (beat_states is per-action, so a later payload's [0] is not how the fight opened). anyEnemyOffScreen is a module-level function and cannot change.
  }, [cameraKey])

  // Rising edge on "an enemy left the Follow viewport" -> flash a one-shot
  // banner. Keyed on the raw geometry rather than on `enemyOffScreen`, or the
  // auto-fit would clear the condition in the same commit and the player would
  // get a camera that moved with no explanation.
  useEffect(() => {
    if (enemyOutsideFollowView && !offScreenLatchRef.current) {
      offScreenLatchRef.current = true
      // A rising-edge, self-dismissing banner: a timed notification about a
      // transition, not a function of current state, retired by the timeout below.
      setShowOffScreenBanner(true)
      const t = setTimeout(() => setShowOffScreenBanner(false), 2500)
      return () => clearTimeout(t)
    }
    if (!enemyOutsideFollowView) {
      offScreenLatchRef.current = false
      setShowOffScreenBanner(false)
    }
  }, [enemyOutsideFollowView])

  return {
    zoom,
    selectViewMode,
    enemyOffScreen,
    // `didAutoFit || enemyOffScreen`, decided here rather than in a three-term
    // JSX guard: the auto-fit message is owed whenever the camera really moved,
    // and the nudge only makes sense while Fit Fight is NOT already on.
    bannerVisible: showOffScreenBanner && (didAutoFit || enemyOffScreen),
    bannerMessage: didAutoFit
      ? '⤢ Enemy off-screen — view widened to Fit Fight'
      : '⚠ Enemy off-screen — switch to Fit Fight',
  }
}
