import React, { useState, useEffect } from 'react';
import StatusEffectsIconPanel from './StatusEffectsIconPanel';
import { colors, spacing, shadows, fonts } from '../styles/theme';
import GameText from './GameText';

// Helper to calculate torus path
const describeArc = (x, y, radius, startAngle, endAngle) => {
  const start = polarToCartesian(x, y, radius, endAngle);
  const end = polarToCartesian(x, y, radius, startAngle);
  const largeArcFlag = endAngle - startAngle <= 180 ? "0" : "1";
  return [
    "M", start.x, start.y,
    "A", radius, radius, 0, largeArcFlag, 0, end.x, end.y
  ].join(" ");
}

const polarToCartesian = (centerX, centerY, radius, angleInDegrees) => {
  const angleInRadians = (angleInDegrees - 90) * Math.PI / 180.0;
  return {
    x: centerX + (radius * Math.cos(angleInRadians)),
    y: centerY + (radius * Math.sin(angleInRadians))
  };
}

const CombatantMarker = ({ entity, isPlayer, isFullMode = false, isHovered = false, animationState = null }) => {
  // Determine Glow Color based on prepared/current move category
  const getGlowStyle = (move) => {
    if (!move) return {}; // No glow
    const cat = move.category || "Miscellaneous";
    switch (cat) {
      case "Attack": return { boxShadow: `0 0 15px 5px ${colors.alpha.danger[60]}`, borderColor: colors.danger };
      case "Maneuver": return { boxShadow: `0 0 15px 5px ${colors.alpha.primary[60]}`, borderColor: colors.primary };
      case "Special": return { boxShadow: `0 0 15px 5px ${colors.alpha.special[60]}`, borderColor: colors.special };
      case "Supernatural": return { boxShadow: `0 0 15px 5px ${colors.alpha.info[60]}`, borderColor: colors.info };
      case "Miscellaneous":
      default: return { boxShadow: `0 0 15px 5px ${colors.text.bright}99`, borderColor: colors.text.bright };
    }
  };

  const move = entity.current_move || entity.prepared_move;
  const glowStyle = getGlowStyle(move);

  // Facing
  // API might provide 'facing' as int (degrees) or string enum.
  // We handle both.
  let facing = 0;
  if (entity.position?.facing !== undefined) {
    if (typeof entity.position.facing === 'number') {
      facing = entity.position.facing;
    } else {
      // Fallback or mapping if strings are sent
      const map = { N: 0, NE: 45, E: 90, SE: 135, S: 180, SW: 225, W: 270, NW: 315 };
      facing = map[entity.position.facing] || 0;
    }
  }

  // Stats for Torus
  // Player has fatigue/maxfatigue
  // Enemies usually utilize health.current and health.max
  const hp = entity.hp !== undefined ? entity.hp : (entity.health?.current || 0);
  const maxHp = entity.max_hp !== undefined ? entity.max_hp : (entity.health?.max || 100);

  const fatigue = entity.fatigue || 0;
  // Fallback for max fatigue if not present (usually 100 or on object)
  const maxFatigue = entity.maxfatigue || entity.max_fatigue || 100;

  const hpPct = maxHp > 0 ? Math.min(1, Math.max(0, hp / maxHp)) : 0;
  const fatPct = maxFatigue > 0 ? Math.min(1, Math.max(0, fatigue / maxFatigue)) : 0;

  // Visual constants
  const content = (entity.name && entity.name[0]) || '?';

  // Triangle styling based on mode
  // Normal: border-l-[6px] border-r-[6px] border-b-[8px]
  // Full: Reduce to ~33% size
  const triangleClass = isFullMode
    ? "absolute top-[-2px] left-1/2 -translate-x-1/2 w-0 h-0 border-l-[2px] border-r-[2px] border-b-[3px] border-l-transparent border-r-transparent filter drop-shadow-sm opacity-90"
    : "absolute top-[-6px] left-1/2 -translate-x-1/2 w-0 h-0 border-l-[6px] border-r-[6px] border-b-[8px] border-l-transparent border-r-transparent filter drop-shadow opacity-90";

  const triangleStyle = {
    borderBottomColor: colors.secondary
  };

  // Animation styling
  const getAnimationStyle = () => {
    if (!animationState) return {};

    if (animationState.isTarget) {
      // Target flash based on outcome
      if (animationState.phase === 'impact') {
        switch (animationState.outcome) {
          case 'hit':
            return { backgroundColor: 'rgba(255, 0, 0, 0.7)', transition: 'background-color 0.1s', zIndex: 60 };
          case 'miss':
            return { opacity: 0.3, transition: 'opacity 0.2s', filter: 'blur(2px)' };
          case 'parry':
            return { backgroundColor: 'rgba(255, 200, 0, 0.7)', transition: 'background-color 0.1s', zIndex: 60 };
          default:
            return {};
        }
      }
    } else if (animationState.isSource) {
      // Source animation
      if (animationState.phase === 'windup') {
        return {
          transform: 'scale(1.15)',
          transition: 'transform 0.1s ease-out',
          zIndex: 100
        };
      } else if (animationState.phase === 'strike') {
        return {
          transform: 'scale(1.1)',
          zIndex: 100
        };
      } else if (animationState.phase === 'expand') {
        return {
          transform: 'scale(1.25)',
          boxShadow: '0 0 25px rgba(255, 215, 0, 0.9)',
          transition: 'all 0.15s ease-out',
          zIndex: 100
        };
      } else if (animationState.phase === 'contract' || animationState.phase === 'return') {
        return {
          transform: 'scale(1)',
          transition: 'all 0.2s ease-in'
        };
      }
    }

    return {};
  };

  return (
    <div className="relative w-[75%] h-[75%] rounded-full transition-all duration-300 transform-gpu border-2"
      style={{
        ...glowStyle,
        ...getAnimationStyle(),
        backgroundColor: colors.bg.panelDeep,
        borderColor: glowStyle.borderColor || colors.border.main
      }}
    >
      {/* Background fill for circle */}
      <div
        className="absolute inset-0 rounded-full opacity-80"
        style={{ backgroundColor: isPlayer ? colors.alpha.primary[20] : colors.alpha.danger[20] }}
      ></div>

      {/* Inner Torus (HP/Fatigue) */}
      <svg className="absolute inset-0 w-full h-full p-[2px]" viewBox="0 0 100 100" style={{ transform: 'rotate(0deg)' }}>
        {/* Left Arc for HP (Red) 
              M 50 95 A 45 45 0 0 1 50 5  (This draws left semi-circle from bottom to top)
          */}
        <path
          d="M 50 95 A 45 45 0 0 1 50 5"
          fill="none"
          stroke="#111827" /* Track darker */
          strokeWidth="8"
          strokeLinecap="butt"
        />
        <path
          d="M 50 95 A 45 45 0 0 1 50 5"
          fill="none"
          stroke="#ff4444" /* HP Color (red) - consistent with HeroPanel.jsx */
          strokeWidth="8"
          strokeDasharray={`${hpPct * 141.4} 141.4`}
          strokeDashoffset="0"
          strokeLinecap="butt"
          style={{ transition: 'stroke-dasharray 0.5s ease-in-out' }}
        />

        {/* Right Arc for Fatigue (Orange/Yellow) 
              M 50 95 A 45 45 0 0 0 50 5 (Right semi-circle)
          */}
        <path
          d="M 50 95 A 45 45 0 0 0 50 5"
          fill="none"
          stroke="#111827"
          strokeWidth="8"
          strokeLinecap="butt"
        />
        <path
          d="M 50 95 A 45 45 0 0 0 50 5"
          fill="none"
          stroke="#f59e0b" /* Fatigue Color */
          strokeWidth="8"
          strokeDasharray={`${fatPct * 141.4} 141.4`}
          strokeDashoffset="0"
          strokeLinecap="butt"
          style={{ transition: 'stroke-dasharray 0.5s ease-in-out' }}
        />
      </svg>

      {/* Facing Indicator Triangle - Orbits around border 
          The triangle needs to be ON the border.
          At 0 deg (North), it should be at Top (50, 0).
          Container center is 50, 50.
      */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{ transform: `rotate(${facing}deg)` }}
      >
        {/* Triangle positioned at top center */}
        <div className={triangleClass} style={triangleStyle} />
      </div>

      {/* Content Label - Hide on full mode if obscured/too small */}
      <div className="absolute inset-0 flex items-center justify-center text-white font-bold text-xs select-none z-10 pointer-events-none">
        {!isFullMode && content}
      </div>

      {/* Status Effects - Floating above marker */}
      {!isFullMode && (
        <div
          className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 pointer-events-auto transition-opacity duration-200"
          style={{
            opacity: 0.35,
          }}
          onMouseEnter={(e) => e.currentTarget.style.opacity = '1'}
          onMouseLeave={(e) => e.currentTarget.style.opacity = '0.35'}
        >
          <StatusEffectsIconPanel effects={entity.status_effects} />
        </div>
      )}

      {/* Target Reticle Overlay */}
      {isHovered && (
        <div className="absolute inset-[-12px] pointer-events-none z-20">
          <svg className="w-full h-full animate-[spin_4s_linear_infinite]" viewBox="0 0 100 100">
            {/* Outer circle */}
            <circle cx="50" cy="50" r="45" fill="none" stroke={colors.secondary} strokeWidth="2" strokeDasharray="10 5" opacity="0.8" />

            {/* Reticle lines */}
            <line x1="50" y1="5" x2="50" y2="20" stroke={colors.secondary} strokeWidth="3" />
            <line x1="50" y1="80" x2="50" y2="95" stroke={colors.secondary} strokeWidth="3" />
            <line x1="5" y1="50" x2="20" y2="50" stroke={colors.secondary} strokeWidth="3" />
            <line x1="80" y1="50" x2="95" y2="50" stroke={colors.secondary} strokeWidth="3" />
          </svg>

          {/* Inner pulsating crosshair */}
          <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', animation: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite' }}>
            <div style={{ width: '110%', height: '1px', backgroundColor: colors.secondary, opacity: 0.6 }} />
            <div style={{ width: '1px', height: '110%', backgroundColor: colors.secondary, opacity: 0.6, position: 'absolute' }} />
          </div>
        </div>
      )}
    </div>
  );
};

export default function BattlefieldGrid({
  combat,
  allBeatStates,
  currentBeatIndex,
  combatLog,
  tab,
  zoom = 1,
  displayedLogCount = 0,
  hoveredTargetId = null
}) {
  const [activeAnimation, setActiveAnimation] = useState(null);
  const [animationPhase, setAnimationPhase] = useState(null);
  const [lastProcessedLogIndex, setLastProcessedLogIndex] = useState(0);
  const [animationQueue, setAnimationQueue] = useState([]);

  // Interaction state
  const [hoveredEntity, setHoveredEntity] = useState(null);
  const [selectedEntity, setSelectedEntity] = useState(null);

  // Clear selection on click outside (this will be handled by a wrapper div)
  const handleGridClick = (e) => {
    if (e.target === e.currentTarget) {
      setSelectedEntity(null);
    }
  };

  // Animation registry - maps animation types to configurations
  const animationConfigs = {
    attack: {
      duration: 800,
      phases: [
        { name: 'windup', duration: 100 },
        { name: 'strike', duration: 300 },
        { name: 'impact', duration: 200 },
        { name: 'return', duration: 200 }
      ]
    },
    pulse: {
      duration: 400,
      phases: [
        { name: 'expand', duration: 200 },
        { name: 'contract', duration: 200 }
      ]
    }
  };

  // Trigger animations from combat log
  useEffect(() => {
    const log = combatLog || combat?.log;
    if (!log) return;

    // Check for new log entries WITH A CEILING of what's currently displayed
    // This ensures animations don't "spoil" the log timing
    if (displayedLogCount > lastProcessedLogIndex) {
      const newEntries = log.slice(lastProcessedLogIndex, displayedLogCount);
      const animations = newEntries.filter(entry => entry.animation).map(entry => entry.animation);

      if (animations.length > 0) {
        setAnimationQueue(prev => [...prev, ...animations]);
      }

      setLastProcessedLogIndex(displayedLogCount);
    }
  }, [combatLog, combat?.log, lastProcessedLogIndex, displayedLogCount]);

  // Process animation queue
  useEffect(() => {
    if (!activeAnimation && animationQueue.length > 0) {
      const nextAnim = animationQueue[0];
      setAnimationQueue(prev => prev.slice(1));
      playAnimation(nextAnim);
    }
  }, [activeAnimation, animationQueue]);

  const playAnimation = (animData) => {
    const config = animationConfigs[animData.type] || animationConfigs.pulse;
    setActiveAnimation({ ...animData, config });
    setAnimationPhase(config.phases[0].name);

    // Sequence through animation phases
    let currentPhaseIndex = 0;
    let elapsed = 0;

    const advancePhase = () => {
      if (currentPhaseIndex >= config.phases.length) {
        // Animation complete
        setActiveAnimation(null);
        setAnimationPhase(null);
        return;
      }

      const phase = config.phases[currentPhaseIndex];
      setAnimationPhase(phase.name);

      setTimeout(() => {
        currentPhaseIndex++;
        advancePhase();
      }, phase.duration);
    };

    advancePhase();
  };

  const renderGrid = () => {
    if (tab === 'enemies') {
      return (
        <div style={{ padding: spacing.md, overflowY: 'auto', height: '100%', backgroundColor: colors.bg.main }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.sm }}>
            {combat.enemies?.map((enemy, idx) => (
              <div key={idx} style={{
                backgroundColor: colors.alpha.danger[10],
                border: `1px solid ${colors.alpha.danger[40]}`,
                borderRadius: '4px',
                padding: spacing.sm
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
                  <div>
                    <GameText variant="secondary" weight="bold" size="sm">{enemy.name}</GameText>
                    <GameText variant="secondary" size="xs" style={{ marginTop: spacing.xs }}>
                      HP: {enemy.hp} / {enemy.max_hp}
                    </GameText>
                  </div>
                  <StatusEffectsIconPanel effects={enemy.status_effects} />
                </div>
                <div className="hp-bar" style={{ marginTop: spacing.xs }}>
                  <div
                    style={{
                      height: '100%',
                      background: `linear-gradient(to right, ${colors.danger}, ${colors.secondary})`,
                      width: `${(enemy.hp / enemy.max_hp) * 100}%`
                    }}
                  ></div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )
    }

    // Map constants
    const MAP_SIZE = 13 // Coordinates 0-12
    const VIEW_SIZE = 15 // Base view size
    const isFullMode = zoom === 'full'

    const getPos = (entity) => entity?.position || { x: 6, y: 6 }
    const playerPos = getPos(combat?.player)

    // Calculate Grid & Viewport
    let gridCols, leftX, topY
    if (isFullMode) {
      gridCols = MAP_SIZE
      leftX = 0
      topY = MAP_SIZE - 1
    } else {
      gridCols = VIEW_SIZE
      const halfView = Math.floor(gridCols / 2)
      leftX = Math.max(0, Math.min(MAP_SIZE - gridCols, playerPos.x - halfView))
      topY = Math.min(MAP_SIZE - 1, Math.max(gridCols - 1, playerPos.y + halfView))
    }

    const getEntityStyle = (pos, baseZ = 20) => {
      if (!pos || pos.x < leftX || pos.x >= leftX + gridCols || pos.y > topY || pos.y <= topY - gridCols) return null
      const col = pos.x - leftX
      const row = topY - pos.y
      return {
        left: 0,
        top: 0,
        transform: `translate(${col * 100}%, ${row * 100}%)`,
        width: `${(1 / gridCols) * 100}%`,
        height: `${(1 / gridCols) * 100}%`,
        zIndex: baseZ
      }
    }

    // --- Breadcrumbs Calculation ---
    const breadcrumbs = []
    if (allBeatStates && currentBeatIndex !== undefined) {
      const historyLength = 4
      const startIdx = Math.max(0, currentBeatIndex - historyLength)

      for (let i = startIdx; i < currentBeatIndex; i++) {
        const beatState = allBeatStates[i]
        if (!beatState) continue

        const opacity = 0.2 + ((i - startIdx) / historyLength) * 0.4 // 0.2 to 0.6 fading

        // Player breadcrumb
        if (beatState.player) {
          const style = getEntityStyle(getPos(beatState.player), 5)
          if (style) breadcrumbs.push({ style, color: colors.primary, opacity, id: `p-${i}` })
        }

        // Enemy breadcrumbs
        beatState.enemies?.forEach(enemy => {
          const style = getEntityStyle(getPos(enemy), 5)
          if (style) breadcrumbs.push({ style, color: colors.danger, opacity, id: `${enemy.id}-${i}` })
        })
      }
    }

    // --- Entity Gathering ---
    const entitiesToRender = []
    if (combat?.player) {
      const style = getEntityStyle(getPos(combat.player))
      if (style) entitiesToRender.push({ entity: combat.player, style, isPlayer: true })
    }
    combat?.enemies?.forEach(enemy => {
      if (enemy.hp === undefined || enemy.hp > 0 || (enemy.health?.current ?? 0) > 0) {
        const style = getEntityStyle(getPos(enemy))
        if (style) entitiesToRender.push({ entity: enemy, style, isPlayer: false })
      }
    })

    return (
      <div
        onClick={handleGridClick}
        style={{ position: 'relative', width: '100%', height: '100%', backgroundColor: colors.bg.main, overflow: 'hidden' }}
      >
        {/* Grid Background Layer */}
        <div style={{
          position: 'absolute',
          inset: 0,
          display: 'grid',
          gap: '1px',
          padding: spacing.sm,
          gridTemplateColumns: `repeat(${gridCols}, minmax(0, 1fr))`,
          gridTemplateRows: `repeat(${gridCols}, minmax(0, 1fr))`,
          pointerEvents: 'none'
        }}>
          {Array(gridCols * gridCols).fill(null).map((_, idx) => (
            <div key={idx} style={{ backgroundColor: 'rgba(255,255,255,0.03)', borderRadius: '2px' }}></div>
          ))}
        </div>

        {/* Breadcrumb Layer */}
        <div style={{ position: 'absolute', inset: 0, padding: spacing.sm, pointerEvents: 'none' }}>
          {breadcrumbs.map(bc => (
            <div
              key={bc.id}
              style={{
                position: 'absolute',
                ...bc.style,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                zIndex: 5
              }}
            >
              <div
                style={{
                  width: '30%',
                  height: '30%',
                  borderRadius: '50%',
                  backgroundColor: bc.color,
                  opacity: bc.opacity,
                  filter: 'blur(1px)'
                }}
              />
            </div>
          ))}
        </div>

        {/* Entity Layer */}
        <div style={{ position: 'absolute', inset: 0, padding: spacing.sm, pointerEvents: 'none' }}>
          {entitiesToRender.map((item, idx) => {
            const entityId = item.entity.id;
            let animState = null;
            if (activeAnimation && animationPhase) {
              if (activeAnimation.source_id === entityId) {
                animState = { isSource: true, isTarget: false, phase: animationPhase, outcome: activeAnimation.outcome };
              } else if (activeAnimation.target_id === entityId) {
                animState = { isSource: false, isTarget: true, phase: animationPhase, outcome: activeAnimation.outcome };
              }
            }

            let transformStyle = {};
            if (animState?.isSource && animState.phase === 'strike' && activeAnimation.target_id) {
              const target = entitiesToRender.find(e => e.entity.id === activeAnimation.target_id);
              if (target) {
                const sPos = getPos(item.entity);
                const tPos = getPos(target.entity);
                transformStyle = {
                  transform: `translate(${(tPos.x - sPos.x) * 40}px, ${(sPos.y - tPos.y) * 40}px)`,
                  transition: 'transform 0.2s cubic-bezier(0.1, 0.7, 1.0, 0.1)',
                  zIndex: 100
                };
              }
            } else if (animState?.isSource && animState.phase === 'return') {
              transformStyle = { transform: 'translate(0, 0)', transition: 'transform 0.2s ease-in-out' };
            }

            return (
              <div
                key={`${item.entity.id || idx}-${item.isPlayer ? 'player' : 'enemy'}`}
                onMouseEnter={() => setHoveredEntity(item.entity)}
                onMouseLeave={() => setHoveredEntity(null)}
                onClick={(e) => {
                  e.stopPropagation();
                  setSelectedEntity(item.entity);
                }}
                style={{
                  position: 'absolute',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  transition: 'transform 0.5s ease-in-out',
                  willChange: 'transform',
                  cursor: 'pointer',
                  pointerEvents: 'auto',
                  ...item.style,
                  zIndex: (hoveredEntity?.id === entityId || selectedEntity?.id === entityId) ? 50 : (item.style.zIndex || 20)
                }}
              >
                <div style={{
                  width: '100%',
                  height: '100%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  zIndex: animState?.phase === 'strike' ? 100 : 1,
                  ...transformStyle
                }}>
                  <CombatantMarker
                    entity={item.entity}
                    isPlayer={item.isPlayer}
                    isFullMode={isFullMode}
                    isHovered={hoveredTargetId === entityId || hoveredEntity?.id === entityId}
                    animationState={animState}
                  />
                </div>

                {/* Hover Tooltip */}
                {hoveredEntity?.id === entityId && !selectedEntity && (
                  <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-4 z-[100] animate-in fade-in slide-in-from-bottom-2 duration-200">
                    <div className="bg-black/90 border border-orange/40 rounded px-2 py-1 shadow-2xl backdrop-blur-md min-w-[120px]">
                      <div className="text-white text-[10px] font-bold uppercase tracking-wider border-b border-white/10 pb-1 mb-1">
                        {item.entity.name}
                      </div>
                      <div className="text-orange/80 text-[9px] flex justify-between gap-2">
                        <span>Prep:</span>
                        <span className="font-mono">{item.entity.prepared_move?.name || '---'}</span>
                      </div>
                    </div>
                    {/* Tooltip arrow */}
                    <div className="w-0 h-0 border-l-[6px] border-r-[6px] border-t-[6px] border-l-transparent border-r-transparent border-t-black/90 absolute left-1/2 -translate-x-1/2 top-full" />
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Selected Entity Details Panel */}
        {selectedEntity && (
          <div
            className="absolute top-4 right-4 z-[150] w-[200px] animate-in slide-in-from-right-4 fade-in duration-300 pointer-events-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="bg-black/95 border-2 border-orange/50 rounded-lg p-3 shadow-2xl backdrop-blur-xl">
              <div className="flex justify-between items-start mb-3 border-b border-white/10 pb-2">
                <GameText weight="bold" size="sm" variant="secondary">{selectedEntity.name}</GameText>
                <button
                  onClick={() => setSelectedEntity(null)}
                  className="text-white/40 hover:text-white transition-colors"
                >
                  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M18 6L6 18M6 6l12 12" />
                  </svg>
                </button>
              </div>

              <div className="space-y-3">
                {/* HP Section */}
                <div>
                  <div className="flex justify-between text-[10px] mb-1">
                    <span className="text-white/60">INTEGRITY (HP)</span>
                    <span className="text-red-400 font-mono">{selectedEntity.hp || selectedEntity.health?.current}/{selectedEntity.max_hp || selectedEntity.health?.max}</span>
                  </div>
                  <div className="h-1.5 w-full bg-red-900/30 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-red-500 transition-all duration-500"
                      style={{ width: `${((selectedEntity.hp || selectedEntity.health?.current) / (selectedEntity.max_hp || selectedEntity.health?.max)) * 100}%` }}
                    />
                  </div>
                </div>

                {/* Fatigue Section */}
                <div>
                  <div className="flex justify-between text-[10px] mb-1">
                    <span className="text-white/60">STAMINA (FAT)</span>
                    <span className="text-orange-400 font-mono">{selectedEntity.fatigue || 0}/{selectedEntity.maxfatigue || 100}</span>
                  </div>
                  <div className="h-1.5 w-full bg-orange-900/30 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-orange-500 transition-all duration-500"
                      style={{ width: `${(selectedEntity.fatigue / (selectedEntity.maxfatigue || 100)) * 100}%` }}
                    />
                  </div>
                </div>

                {/* Status Effects */}
                <div>
                  <div className="text-[10px] text-white/60 mb-1.5 uppercase tracking-wider">Status Effects</div>
                  <div className="flex flex-wrap gap-1">
                    <StatusEffectsIconPanel effects={selectedEntity.status_effects} />
                    {(!selectedEntity.status_effects || selectedEntity.status_effects.length === 0) && (
                      <span className="text-[10px] text-white/30 italic">None active</span>
                    )}
                  </div>
                </div>

                {/* Current Move */}
                <div className="pt-2 border-t border-white/10">
                  <div className="text-[10px] text-white/60 mb-1">CURRENT ACTION</div>
                  <div className="text-orange text-xs font-bold">
                    {selectedEntity.current_move?.name || selectedEntity.prepared_move?.name || 'Idle'}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    )
  }

  return renderGrid()
}
