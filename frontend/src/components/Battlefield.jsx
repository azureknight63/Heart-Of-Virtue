import { useState, useEffect, useRef, useMemo } from 'react'
import { useBattlefieldCamera } from '../hooks/useBattlefieldCamera'

import BattlefieldGrid, { VIEW_SIZE, VIEW_MODE_FOLLOW, VIEW_MODE_FIT } from './BattlefieldGrid'
import BeatTimeline from './BeatTimeline'
import GlossaryHelpButton from './GlossaryHelpButton'
import { accessibility, colors, spacing } from '../styles/theme'
import { isLiving, anyEnemyOutsideView } from '../utils/combatEntities'
import { useFeatureFlag } from '../utils/featureFlags'
import { useMobile } from '../hooks/useMobile'
import { useCoarsePointer } from '../hooks/useCoarsePointer'

const HALF_VIEW = Math.floor(VIEW_SIZE / 2);
const MAX_BEAT_STATES = 200;

// Both view modes are always shown, each labelled with what it does. The old
// control was a single button captioned with the mode it was *currently in*
// ("View: Normal"), which reads as a state on a control that acts — so there
// was no way to tell whether the caption named where you were or where the
// click would take you.
const VIEW_MODE_OPTIONS = [
  {
    mode: VIEW_MODE_FOLLOW,
    label: 'Follow',
    title: `Keep the camera locked on Jean (${VIEW_SIZE}×${VIEW_SIZE} cells)`,
  },
  {
    mode: VIEW_MODE_FIT,
    label: 'Fit Fight',
    title: 'Frame every living combatant, however far apart they are',
  },
];

// The grid's half-extent is Battlefield's to know; the predicate itself lives
// with the other combatant helpers.
const anyEnemyOffScreen = (state) => anyEnemyOutsideView(state, HALF_VIEW);

export default function Battlefield({ combat, currentLogIndex, displayedLogCount, hoveredTargetId, onAnimatingChange, streaming = false, streamedAnimations = [], combatSpeed = 1, isReloadRecovery = false }) {
  const beatTimelineEnabled = useFeatureFlag('beatTimeline')
  const [selectedTab, setSelectedTab] = useState('overview')
  // Both hooks unconditionally — `||` would short-circuit the second and
  // break hook order the first time the viewport is narrow.
  const isMobile = useMobile()
  const isCoarsePointer = useCoarsePointer()
  const needsLargeTargets = isMobile || isCoarsePointer

  // Display state - synchronized with combat log progress.
  // Initialise directly to the first beat state (same shape BattlefieldGrid expects)
  // so there is never a render where displayState has the top-level API response shape.
  const [displayState, setDisplayState] = useState(combat?.beat_states?.[0] ?? combat)

  // Framing lives in its own hook: five pieces of state, two effects and a
  // callback that all answer one question, in a component that also owns beat
  // accumulation and log-index sync.
  const { zoom, selectViewMode, enemyOffScreen, bannerVisible, bannerMessage } =
    useBattlefieldCamera(combat, displayState, anyEnemyOffScreen)

  // Accumulated beat states across multiple actions so trails persist across turns
  const [accBeatStates, setAccBeatStates] = useState([])
  const baseOffsetRef = useRef(0)
  const prevBeatStatesRef = useRef(null)

  useEffect(() => {
    // When combat data first loads, initialize to the first beat state (or current state if no beats)
    if (combat?.beat_states && combat.beat_states.length > 0) {
      // Start at the first beat state
      setDisplayState(combat.beat_states[0])
    } else {
      // No beat states, show current combat state
      setDisplayState(combat)
    }
  }, [combat])

  // Accumulate beat states so breadcrumb trails survive across player turns
  useEffect(() => {
    const incoming = combat?.beat_states
    if (!incoming || incoming === prevBeatStatesRef.current) return
    prevBeatStatesRef.current = incoming

    if (!combat?.combat_active) {
      // Combat ended — reset accumulation
      setAccBeatStates([])
      baseOffsetRef.current = 0
      return
    }

    setAccBeatStates(prev => {
      const next = [...prev, ...incoming]
      if (next.length > MAX_BEAT_STATES) {
        const dropped = next.length - MAX_BEAT_STATES
        baseOffsetRef.current = Math.max(0, prev.length - dropped)
        return next.slice(dropped)
      }
      baseOffsetRef.current = prev.length
      return next
    })
  }, [combat?.beat_states, combat?.combat_active])

  // Separate effect for log progress - this updates the map as log displays
  useEffect(() => {
    if (combat?.beat_states && combat.beat_states.length > 0 && currentLogIndex !== undefined) {
      // currentLogIndex contains the beat_index from the log entry
      // Clamp it to valid range
      const stateIndex = Math.min(Math.max(0, currentLogIndex), combat.beat_states.length - 1)
      setDisplayState(combat.beat_states[stateIndex] || combat.beat_states[0])
    }
  }, [currentLogIndex, combat?.beat_states])

  // Living enemy count and beat number: the two numbers that answer "where is
  // this fight at?" without reading back through the log.
  const livingEnemyCount = useMemo(
    () => (displayState?.enemies || []).filter(isLiving).length,
    [displayState?.enemies]
  );

  // 44px minimum on a phone or any coarse pointer. Measured at 375px before
  // this: Overview 75.6x28, Enemies 97.2x28, Follow 63.2x26, Fit Fight 84.8x26
  // — all about 60% of the required height (issue #564). Height only; the
  // widths already clear the minimum, so the row's total width is unchanged.
  const touchTargetStyle = needsLargeTargets
    ? { minHeight: accessibility.touchTarget, display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }
    : {};

  if (!displayState) {
    return (
      <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: colors.text.muted }}>
        <p>No active combat</p>
      </div>
    )
  }

  return (
    <div style={{ width: '100%', height: '100%', display: 'flex', flexDirection: 'column', gap: spacing.sm }}>
      {/* Tab Selector. `flexWrap` plus the row gap so the four controls can
          take two lines at 375px once they are 44px tall, rather than
          overflowing the map's width (issue #564). */}
      <div
        data-testid="battlefield-toolbar"
        style={{ display: 'flex', gap: '6px', rowGap: '6px', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between' }}
      >
        <div style={{ display: 'flex', gap: '6px' }}>
          <button
            onClick={() => setSelectedTab('overview')}
            style={{
              ...touchTargetStyle,
              padding: '4px 8px', fontSize: '12px', fontWeight: 'bold', borderRadius: '4px', border: `1px solid ${colors.secondary}`, transition: 'all 0.2s',
              backgroundColor: selectedTab === 'overview' ? colors.secondary : 'transparent',
              color: selectedTab === 'overview' ? '#fff' : colors.secondary,
              cursor: 'pointer'
            }}
          >
            Overview
          </button>
          <button
            onClick={() => setSelectedTab('enemies')}
            style={{
              ...touchTargetStyle,
              padding: '4px 8px', fontSize: '12px', fontWeight: 'bold', borderRadius: '4px', border: `1px solid ${colors.secondary}`, transition: 'all 0.2s',
              backgroundColor: selectedTab === 'enemies' ? colors.secondary : 'transparent',
              color: selectedTab === 'enemies' ? '#fff' : colors.secondary,
              cursor: 'pointer'
            }}
          >
            Enemies ({combat?.enemies?.length || 0})
          </button>
        </div>

        {/* View mode — a segmented control, so the available modes and the
            active one are both visible at a glance. */}
        {selectedTab === 'overview' && (
          <div
            role="group"
            aria-label="Battlefield view mode"
            className={enemyOffScreen ? 'battlefield-zoom-hint' : ''}
            style={{ display: 'flex', borderRadius: '4px', border: `1px solid ${colors.secondary}`, overflow: 'hidden' }}
          >
            {VIEW_MODE_OPTIONS.map(({ mode, label, title }) => {
              const active = zoom === mode;
              return (
                <button
                  key={mode}
                  onClick={() => selectViewMode(mode)}
                  aria-pressed={active}
                  style={{
                    ...touchTargetStyle,
                    padding: '4px 10px', fontSize: '12px', fontWeight: 'bold', border: 'none', transition: 'background-color 0.2s, color 0.2s',
                    backgroundColor: active ? colors.secondary : 'rgba(0,0,0,0.5)',
                    color: active ? '#fff' : colors.secondary,
                    cursor: 'pointer'
                  }}
                  title={enemyOffScreen && mode === VIEW_MODE_FIT
                    ? 'Enemies are off-screen — Fit Fight frames all of them'
                    : title}
                >
                  {label}
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Fight status strip: the raw counters, plus — when the `beatTimeline`
          flag is on (now the default) — a schedule of who resolves when.
          The two were originally mutually exclusive so the timeline could be
          A/B compared against the counter; they are complementary rather than
          redundant (the timeline carries ordering, the counters carry beat
          number and how many enemies are left), so both render together now
          and flipping the flag off drops only the schedule.
          `displayState`, not `combat`: BeatTimeline needs to agree with the
          living-enemy count and the grid above it, both of which already read
          the scrub-consistent per-beat snapshot rather than the live
          top-level state. */}
      {selectedTab === 'overview' && (
        <div
          style={{
            display: 'flex', gap: spacing.md, alignItems: 'center',
            fontSize: '10px', fontFamily: 'monospace', color: colors.text.muted,
            letterSpacing: '0.05em', textTransform: 'uppercase',
          }}
          // Deliberately not role="status": the beat number changes on every
          // beat and a live region would make a screen reader narrate the
          // counter continuously over the combat log it should be reading.
          aria-label="Fight status"
        >
          <span>Beat {combat?.beat ?? combat?.round ?? 0}</span>
          <span style={{ color: livingEnemyCount > 0 ? colors.danger : colors.primary }}>
            {livingEnemyCount} standing
          </span>
          {/* #507: the strip is the one place the word "Beat" already appears on
              screen, so the answer to "what is a beat?" sits beside the question. */}
          <GlossaryHelpButton style={{ marginLeft: 'auto' }} />
        </div>
      )}
      {selectedTab === 'overview' && beatTimelineEnabled && (
        <BeatTimeline combat={displayState} />
      )}

      {/* Battlefield Grid */}
      <div style={{ flex: 1, overflow: 'hidden', borderRadius: '4px', border: `1px solid ${colors.border.main}`, backgroundColor: 'rgba(0,0,0,0.3)', position: 'relative' }}>
        <BattlefieldGrid
          combat={displayState}
          // Passed explicitly, not read off `combat`: the grid receives
          // `displayState`, which is a BEAT state, and serialize_combat_state
          // emits neither of these. Reading them from the grid's own prop made
          // the pan-reset dep flip uuid <-> undefined as displayState alternated
          // between poll- and action-derived shapes, resetting the camera
          // repeatedly mid-fight instead of once per fight.
          combatId={combat?.combat_id}
          combatActive={combat?.combat_active}
          allBeatStates={accBeatStates}
          /* eslint-disable-next-line react-hooks/refs -- baseOffsetRef is written by the same setAccBeatStates updater that produces accBeatStates, so offset and window are one value; promoting it to state would render one frame pairing a new window with the old offset, jumping the grid to the wrong beat. */
          currentBeatIndex={baseOffsetRef.current + (currentLogIndex ?? 0)}
          combatLog={combat?.log || []}
          tab={selectedTab}
          zoom={zoom}
          displayedLogCount={displayedLogCount}
          hoveredTargetId={hoveredTargetId}
          mapSize={combat?.map_size}
          isReloadRecovery={isReloadRecovery}
          onAnimatingChange={onAnimatingChange}
          streaming={streaming}
          streamedAnimations={streamedAnimations}
          combatSpeed={combatSpeed}
        />

        {selectedTab === 'overview' && bannerVisible && (
          <div
            className="animate-in fade-in slide-in-from-top-2 duration-200"
            style={{ position: 'absolute', top: '8px', left: '50%', transform: 'translateX(-50%)', zIndex: 160, pointerEvents: 'none' }}
            role="status"
          >
            <div style={{ backgroundColor: 'rgba(0,0,0,0.9)', border: `1px solid ${colors.secondary}`, borderRadius: '4px', padding: '4px 12px', fontSize: '11px', fontWeight: 'bold', color: colors.secondary, boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)', backdropFilter: 'blur(4px)', whiteSpace: 'nowrap' }}>
              {bannerMessage}
            </div>
          </div>
        )}

        {selectedTab === 'overview' && (
          <div
            style={{ position: 'absolute', bottom: '6px', left: '8px', zIndex: 140, pointerEvents: 'none', fontSize: '9px', fontFamily: 'monospace', color: 'rgba(255,255,255,0.4)', userSelect: 'none', display: 'flex', alignItems: 'center', gap: '4px' }}
            aria-label="Trailing dots show recent movement paths"
          >
            <span style={{ display: 'inline-block', width: '6px', height: '6px', borderRadius: '50%', backgroundColor: colors.accent, opacity: 0.7 }}></span>
            <span style={{ display: 'inline-block', width: '6px', height: '6px', borderRadius: '50%', backgroundColor: colors.accent, opacity: 0.4 }}></span>
            <span style={{ display: 'inline-block', width: '6px', height: '6px', borderRadius: '50%', backgroundColor: colors.accent, opacity: 0.2 }}></span>
            <span style={{ marginLeft: '4px' }}>recent paths</span>
          </div>
        )}
      </div>

    </div>
  );
}
