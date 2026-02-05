import React, { useState, useEffect } from 'react';
import StatusEffectsIconPanel from './StatusEffectsIconPanel';

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
    // red=Attack, blue=Maneuver, white=Misc, purple=Special, teal=Supernatural
    // Also ensuring border color matches the glow
    switch (cat) {
      case "Attack": return { boxShadow: "0 0 15px 5px rgba(220, 38, 38, 0.6)", borderColor: "#ef4444" }; // Red
      case "Maneuver": return { boxShadow: "0 0 15px 5px rgba(37, 99, 235, 0.6)", borderColor: "#3b82f6" }; // Blue
      case "Special": return { boxShadow: "0 0 15px 5px rgba(147, 51, 234, 0.6)", borderColor: "#a855f7" }; // Purple
      case "Supernatural": return { boxShadow: "0 0 15px 5px rgba(13, 148, 136, 0.6)", borderColor: "#14b8a6" }; // Teal
      case "Miscellaneous":
      default: return { boxShadow: "0 0 15px 5px rgba(255, 255, 255, 0.6)", borderColor: "#ffffff" }; // White
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
    ? "absolute top-[-2px] left-1/2 -translate-x-1/2 w-0 h-0 border-l-[2px] border-r-[2px] border-b-[3px] border-l-transparent border-r-transparent border-b-yellow-400 filter drop-shadow-sm opacity-90"
    : "absolute top-[-6px] left-1/2 -translate-x-1/2 w-0 h-0 border-l-[6px] border-r-[6px] border-b-[8px] border-l-transparent border-r-transparent border-b-yellow-400 filter drop-shadow opacity-90";

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
    <div className="relative w-[75%] h-[75%] rounded-full transition-all duration-300 transform-gpu bg-gray-900 border-2"
      style={{
        ...glowStyle,
        ...getAnimationStyle(),
        // If no move prepared, default border color is handled by className or style override
        borderColor: glowStyle.borderColor || '#4b5563'
      }}
    >
      {/* Background fill for circle */}
      <div className={`absolute inset-0 rounded-full opacity-80 ${isPlayer ? 'bg-cyan-900' : 'bg-red-900'}`}></div>

      {/* Inner Torus (HP/Fatigue) */}
      <svg className="absolute inset-0 w-full h-full p-[2px]" viewBox="0 0 100 100" style={{ transform: 'rotate(0deg)' }}>
        {/* Left Arc for HP (Green) 
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
          stroke="#22c55e" /* HP Color (green-500) */
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
        <div className={triangleClass} />
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
            <circle cx="50" cy="50" r="45" fill="none" stroke="#ffaa00" strokeWidth="2" strokeDasharray="10 5" opacity="0.8" />

            {/* Reticle lines */}
            <line x1="50" y1="5" x2="50" y2="20" stroke="#ffaa00" strokeWidth="3" />
            <line x1="50" y1="80" x2="50" y2="95" stroke="#ffaa00" strokeWidth="3" />
            <line x1="5" y1="50" x2="20" y2="50" stroke="#ffaa00" strokeWidth="3" />
            <line x1="80" y1="50" x2="95" y2="50" stroke="#ffaa00" strokeWidth="3" />
          </svg>

          {/* Inner pulsating crosshair */}
          <div className="absolute inset-0 flex items-center justify-center animate-pulse">
            <div className="w-[110%] h-[1px] bg-[#ffaa00] opacity-60" />
            <div className="w-[1px] h-[110%] bg-[#ffaa00] opacity-60 absolute" />
          </div>
        </div>
      )}
    </div>
  );
};

export default function BattlefieldGrid({ combat, combatLog, tab, zoom = 1, displayedLogCount = 0, hoveredTargetId = null }) {
  const [activeAnimation, setActiveAnimation] = useState(null);
  const [animationPhase, setAnimationPhase] = useState(null);
  const [lastProcessedLogIndex, setLastProcessedLogIndex] = useState(0);
  const [animationQueue, setAnimationQueue] = useState([]);

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
        <div className="p-4 overflow-y-auto h-full">
          <div className="space-y-2">
            {combat.enemies?.map((enemy, idx) => (
              <div key={idx} className="bg-[rgba(255,68,68,0.1)] border border-red-600 rounded p-2">
                <div className="flex justify-between items-start">
                  <div>
                    <div className="text-orange font-bold text-sm">{enemy.name}</div>
                    <div className="text-xs text-orange mt-1">HP: {enemy.hp} / {enemy.max_hp}</div>
                  </div>
                  <StatusEffectsIconPanel effects={enemy.status_effects} />
                </div>
                <div className="hp-bar mt-1">
                  <div
                    className="h-full bg-gradient-to-r from-[#ff4444] to-[#ffaa44]"
                    style={{ width: `${(enemy.hp / enemy.max_hp) * 100}%` }}
                  ></div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )
    }

    // Map constants
    const MAP_SIZE = 13 // Coordinates 0-12 (12x12 grid for small battles)
    const VIEW_SIZE = 15 // Base view size (Normal mode)
    const isFullMode = zoom === 'full'

    // Helper to get position safely
    const getPos = (entity) => {
      // Handle both backend structure (entity.position) and potential missing data
      return entity?.position || { x: 6, y: 6 } // Center of 12x12 grid
    }

    const playerPos = getPos(combat?.player)

    // Calculate Grid & Viewport
    let gridCols, leftX, topY

    if (isFullMode) {
      // Full Map Mode: Show entire grid
      gridCols = MAP_SIZE
      leftX = 0
      topY = MAP_SIZE - 1 // Top row is Y=12
    } else {
      // Normal Mode: 15x15 centered on player
      gridCols = VIEW_SIZE
      const halfView = Math.floor(gridCols / 2)

      leftX = playerPos.x - halfView
      leftX = Math.max(0, Math.min(MAP_SIZE - gridCols, leftX))

      topY = playerPos.y + halfView
      topY = Math.min(MAP_SIZE - 1, Math.max(gridCols - 1, topY))
    }

    // Helper to calculate style position % for any entity
    const getEntityStyle = (entity) => {
      const p = getPos(entity)
      // Check if in view
      if (p.x < leftX || p.x >= leftX + gridCols || p.y > topY || p.y <= topY - gridCols) {
        return null // Out of view
      }

      const col = p.x - leftX
      const row = topY - p.y // Y is inverted (topY is highest)

      return {
        left: `${(col / gridCols) * 100}%`,
        top: `${(row / gridCols) * 100}%`,
        width: `${(1 / gridCols) * 100}%`,
        height: `${(1 / gridCols) * 100}%`
      }
    }

    const totalCells = gridCols * gridCols

    // Gather all entities to render
    const entitiesToRender = []
    if (combat?.player) {
      const style = getEntityStyle(combat.player)
      if (style) entitiesToRender.push({ entity: combat.player, style, isPlayer: true })
    }
    combat?.enemies?.forEach(enemy => {
      if (enemy.hp === undefined || enemy.hp > 0 || ((enemy.health?.current ?? 0) > 0)) {
        const style = getEntityStyle(enemy)
        if (style) entitiesToRender.push({ entity: enemy, style, isPlayer: false })
      }
    })

    return (
      <div className="relative w-full h-full bg-gray-950 overflow-hidden">
        {/* Grid Background Layer */}
        <div
          className="absolute inset-0 grid gap-px p-2"
          style={{
            gridTemplateColumns: `repeat(${gridCols}, minmax(0, 1fr))`,
            gridTemplateRows: `repeat(${gridCols}, minmax(0, 1fr))` // Explicit rows for sizing
          }}
        >
          {Array(totalCells).fill(null).map((_, idx) => {
            // Just render empty cells for the grid lines
            return (
              <div key={idx} className="bg-[rgba(255,255,255,0.03)] rounded-sm"></div>
            )
          })}
        </div>

        {/* Entity Layer (Overlay) */}
        <div className="absolute inset-0 p-2 pointer-events-none">
          {entitiesToRender.map((item, idx) => {
            const entityId = item.entity.id;

            // Determine animation state for this entity
            let animState = null;
            if (activeAnimation && animationPhase) {
              if (activeAnimation.source_id === entityId) {
                animState = {
                  isSource: true,
                  isTarget: false,
                  phase: animationPhase,
                  outcome: activeAnimation.outcome
                };
              } else if (activeAnimation.target_id === entityId) {
                animState = {
                  isSource: false,
                  isTarget: true,
                  phase: animationPhase,
                  outcome: activeAnimation.outcome
                };
              }
            }

            // Calculate translation for strike phase
            let transformStyle = {};
            if (animState?.isSource && animState.phase === 'strike' && activeAnimation.target_id) {
              // Find target position
              const target = entitiesToRender.find(e => e.entity.id === activeAnimation.target_id);
              if (target) {
                const sourcePos = getPos(item.entity);
                const targetPos = getPos(target.entity);

                // Calculate directional vector (40% of the distance)
                const dx = (targetPos.x - sourcePos.x) * 40;
                const dy = (sourcePos.y - targetPos.y) * 40;

                transformStyle = {
                  transform: `translate(${dx}px, ${dy}px)`,
                  transition: 'transform 0.2s cubic-bezier(0.1, 0.7, 1.0, 0.1)',
                  zIndex: 100
                };
              }
            } else if (animState?.isSource && animState.phase === 'return') {
              transformStyle = {
                transform: 'translate(0, 0)',
                transition: 'transform 0.2s ease-in-out'
              };
            }

            return (
              <div
                key={`${item.entity.id || idx}-${item.isPlayer ? 'player' : 'enemy'}`}
                className="absolute flex items-center justify-center transition-all duration-500 ease-in-out will-change-[top,left]"
                style={{
                  ...item.style,
                  ...transformStyle
                }}
              >
                <CombatantMarker
                  entity={item.entity}
                  isPlayer={item.isPlayer}
                  isFullMode={isFullMode}
                  isHovered={hoveredTargetId === item.entity.id}
                  animationState={animState}
                />
              </div>
            );
          })}
        </div>
      </div>
    )
  }

  return renderGrid()
}
