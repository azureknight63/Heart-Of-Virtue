import { useState, useEffect, useRef, useMemo } from 'react'

import BattlefieldGrid, { VIEW_SIZE } from './BattlefieldGrid'

const HALF_VIEW = Math.floor(VIEW_SIZE / 2);

// Any living enemy whose position lies outside the zoomed viewport centered on Jean.
function anyEnemyOffScreen(state) {
  const player = state?.player;
  const enemies = state?.enemies;
  if (!player?.position || !enemies?.length) return false;
  const px = player.position.x;
  const py = player.position.y;
  for (const e of enemies) {
    const hp = e.hp ?? e.health?.current;
    if (hp !== undefined && hp <= 0) continue;
    const ep = e.position;
    if (!ep) continue;
    if (Math.abs(ep.x - px) > HALF_VIEW || Math.abs(ep.y - py) > HALF_VIEW) return true;
  }
  return false;
}

export default function Battlefield({ combat, currentLogIndex, displayedLogCount, hoveredTargetId }) {
  const [selectedTab, setSelectedTab] = useState('overview')
  const [zoom, setZoom] = useState(1)
  // Transient banner shown once per "enemy goes off-screen" transition, auto-
  // dismissed after 2.5s or on zoom toggle so players who already understand
  // the affordance aren't nagged.
  const [showOffScreenBanner, setShowOffScreenBanner] = useState(false)
  const offScreenLatchRef = useRef(false)

  // Display state - synchronized with combat log progress.
  // Initialise directly to the first beat state (same shape BattlefieldGrid expects)
  // so there is never a render where displayState has the top-level API response shape.
  const [displayState, setDisplayState] = useState(combat?.beat_states?.[0] ?? combat)

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
      const MAX_BEAT_STATES = 200
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

  // Hint the player to expand the view when a living enemy is beyond the
  // zoomed viewport. The glow is suppressed while already in full-map mode.
  const enemyOffScreen = useMemo(
    () => zoom !== 'full' && anyEnemyOffScreen(displayState),
    [zoom, displayState]
  );

  // Rising edge on enemyOffScreen → flash a one-shot banner explaining the hint.
  useEffect(() => {
    if (enemyOffScreen && !offScreenLatchRef.current) {
      offScreenLatchRef.current = true;
      setShowOffScreenBanner(true);
      const t = setTimeout(() => setShowOffScreenBanner(false), 2500);
      return () => clearTimeout(t);
    }
    if (!enemyOffScreen) {
      offScreenLatchRef.current = false;
      setShowOffScreenBanner(false);
    }
  }, [enemyOffScreen]);

  if (!displayState) {
    return (
      <div className="w-full h-full flex items-center justify-center text-gray-500">
        <p>No active combat</p>
      </div>
    )
  }

  return (
    <div className="w-full h-full flex flex-col gap-2">
      {/* Tab Selector */}
      <div className="flex gap-1.5 items-center justify-between">
        <div className="flex gap-1.5">
          <button
            onClick={() => setSelectedTab('overview')}
            className={`px-2 py-1 text-xs font-bold rounded border transition-all ${selectedTab === 'overview'
              ? 'bg-orange text-white border-orange'
              : 'bg-transparent text-orange border-orange hover:bg-orange hover:text-white'
              }`}
          >
            Overview
          </button>
          <button
            onClick={() => setSelectedTab('enemies')}
            className={`px-2 py-1 text-xs font-bold rounded border transition-all ${selectedTab === 'enemies'
              ? 'bg-orange text-white border-orange'
              : 'bg-transparent text-orange border-orange hover:bg-orange hover:text-white'
              }`}
          >
            Enemies ({combat?.enemies?.length || 0})
          </button>
        </div>

        {/* Zoom Controls */}
        {selectedTab === 'overview' && (
          <div className="flex gap-1">
            <button
              onClick={() => setZoom(zoom === 1 ? 'full' : 1)}
              className={`px-3 py-1 text-xs font-bold rounded border transition-colors ${zoom === 'full'
                ? 'bg-orange text-white border-orange'
                : 'border-orange text-orange hover:bg-orange hover:text-white bg-[rgba(0,0,0,0.5)]'
                }${enemyOffScreen ? ' battlefield-zoom-hint' : ''}`}
              title={enemyOffScreen
                ? 'Enemies are off-screen — switch to Full Map to see everything'
                : 'Toggle View Mode'}
            >
              {zoom === 'full' ? 'View: Full Map' : 'View: Normal'}
            </button>
          </div>
        )}
      </div>

      {/* Battlefield Grid */}
      <div className="flex-1 overflow-hidden rounded border border-[#333] bg-[rgba(0,0,0,0.3)] relative">
        <BattlefieldGrid
          combat={displayState}
          allBeatStates={accBeatStates}
          currentBeatIndex={baseOffsetRef.current + (currentLogIndex ?? 0)}
          combatLog={combat?.log || []}
          tab={selectedTab}
          zoom={zoom}
          displayedLogCount={displayedLogCount}
          hoveredTargetId={hoveredTargetId}
          mapSize={combat?.map_size}
        />

        {selectedTab === 'overview' && showOffScreenBanner && (
          <div
            className="absolute top-2 left-1/2 -translate-x-1/2 z-[160] pointer-events-none animate-in fade-in slide-in-from-top-2 duration-200"
            role="status"
          >
            <div className="bg-black/90 border border-orange/70 rounded px-3 py-1 text-[11px] font-bold text-orange shadow-lg backdrop-blur-sm whitespace-nowrap">
              ⚠ Enemy off-screen — switch to Full Map
            </div>
          </div>
        )}

        {selectedTab === 'overview' && (
          <div
            className="absolute bottom-1.5 left-2 z-[140] pointer-events-none text-[9px] font-mono text-white/40 select-none flex items-center gap-1"
            aria-label="Trailing dots show recent movement paths"
          >
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-[#00ff88] opacity-70"></span>
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-[#00ff88] opacity-40"></span>
            <span className="inline-block w-1.5 h-1.5 rounded-full bg-[#00ff88] opacity-20"></span>
            <span className="ml-1">recent paths</span>
          </div>
        )}
      </div>

    </div>
  );
}
