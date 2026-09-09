import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { VIEW_MODE_FOLLOW, VIEW_MODE_FIT } from '../components/BattlefieldGrid'

/**
 * Sentinel for "no camera claimed yet" (issue #561).
 *
 * A Symbol rather than `null`, because `null` is a REAL cameraKey: a combat
 * payload that omits `combat_id` yields one. Initialised to `null` the guard
 * would read as already-claimed for exactly those payloads and the auto-fit
 * would never fire at all.
 */
export const CAMERA_UNCLAIMED = Symbol('camera-unclaimed')

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
  const cameraClaimedForRef = useRef(CAMERA_UNCLAIMED)

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
   * The player's camera choice, which settles the camera for the rest of this
   * fight. Recording the claim is what keeps the auto-fit from being a bully:
   * a player who deliberately returns to Follow with an enemy still off-screen
   * has said something, and the next beat must not undo it.
   */
  const selectViewMode = useCallback((mode) => {
    cameraClaimedForRef.current = cameraKey
    setDidAutoFit(false)
    setShowOffScreenBanner(false)
    setZoom(mode)
  }, [cameraKey])

  // A new fight starts from the default camera. `zoom` and `didAutoFit` are
  // per-mount while the claim ref is per-fight, and that mismatch meant fight
  // two inherited fight one's Fit camera AND its didAutoFit -- so it opened
  // already widened and announced "view widened" when nothing had.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- a new fight is an external event (a new combat_id off a poll), not React-derived data; deriving the camera during render would discard the player's manual choice on every re-render.
    setZoom(VIEW_MODE_FOLLOW)
    setDidAutoFit(false)
  }, [cameraKey])

  // Entry geometry, read from THIS fight's own first beat state rather than
  // from `displayState`, which is set in an effect keyed on `combat` and so
  // still holds the PREVIOUS fight's positions on the commit a new fight
  // arrives -- the auto-fit below runs in that same commit. It is also the
  // right question on its own terms: entry framing is a property of how the
  // fight opened, not of whichever beat the player has since scrubbed to.
  const entryEnemyOutsideFollowView = useMemo(
    () => anyEnemyOffScreen(combat?.beat_states?.[0] ?? combat),
    [combat, anyEnemyOffScreen]
  )

  /**
   * Frame the fight the player was actually handed.
   *
   * Spawn distance is a per-encounter roll, so with Follow (±6 cells) as the
   * default a fight beginning at 7-8 ft opened on an empty map with a banner
   * telling the player to fix the framing themselves -- the application
   * detecting the problem and delegating it. Fit Fight is the answer it was
   * already recommending, so it takes it, once, and says so.
   */
  useEffect(() => {
    if (!entryEnemyOutsideFollowView) return
    if (cameraClaimedForRef.current === cameraKey) return
    cameraClaimedForRef.current = cameraKey
    // eslint-disable-next-line react-hooks/set-state-in-effect -- a deliberate one-shot on combat entry, guarded by the claim ref; it must happen exactly once per fight and must stay overridable, which render-derived state cannot express.
    setZoom(VIEW_MODE_FIT)
    setDidAutoFit(true)
  }, [entryEnemyOutsideFollowView, cameraKey])

  // Rising edge on "an enemy left the Follow viewport" -> flash a one-shot
  // banner. Keyed on the raw geometry rather than on `enemyOffScreen`, or the
  // auto-fit would clear the condition in the same commit and the player would
  // get a camera that moved with no explanation.
  useEffect(() => {
    if (enemyOutsideFollowView && !offScreenLatchRef.current) {
      offScreenLatchRef.current = true
      // eslint-disable-next-line react-hooks/set-state-in-effect -- a rising-edge, self-dismissing banner: it is a timed notification about a transition, not a function of current state, and the timeout below retires it.
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
