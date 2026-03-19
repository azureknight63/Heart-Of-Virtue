import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import StatusEffectsIconPanel from './StatusEffectsIconPanel';
import { colors, spacing, shadows, fonts } from '../styles/theme';
import GameText from './GameText';

// ---------------------------------------------------------------------------
// Animation registry — module level so it is never recreated on render
// ---------------------------------------------------------------------------
const ANIMATION_CONFIGS = {
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
  },
  death: {
    duration: 700,
    phases: [
      { name: 'explode', duration: 400 },
      { name: 'fade', duration: 300 }
    ]
  }
};

// Fragment definitions for the death burst — module-level, never recreated
const DEATH_FRAGMENTS = Array.from({ length: 12 }, (_, i) => ({
  angle: i * 30,
  distance: 42 + (i % 3) * 12,
  size: i % 3 === 0 ? 5 : i % 3 === 1 ? 3 : 4,
  color: ['#ffffff', '#aaddff', '#88ccff', '#ffeedd'][i % 4],
}));

// ---------------------------------------------------------------------------
// Grid / camera constants — module level
// ---------------------------------------------------------------------------
const VIEW_SIZE = 13;  // viewport cell count in zoomed mode; shows enemies within attacking range (up to 9 cells) plus buffer
const HALF_VIEW = Math.floor(VIEW_SIZE / 2);
const CAMERA_LERP = 0.12;     // fraction of remaining distance per RAF frame
const CAMERA_EPSILON = 0.004; // settle threshold (cells)

/** Snap a float camera origin to the nearest valid integer cell. */
const computeSnapOrigin = (cam, cols, mapSz) => ({
  leftX: Math.round(Math.max(0, Math.min(mapSz - cols, cam.x))),
  topY:  Math.round(Math.min(mapSz - 1, Math.max(cols - 1, cam.y))),
});

// ---------------------------------------------------------------------------
// Pure helpers — module level, stable references, never re-created
// ---------------------------------------------------------------------------

/** Returns the grid position of an entity, defaulting to origin if absent. */
const getPos = (entity) => entity?.position || { x: 0, y: 0 };

// ---------------------------------------------------------------------------
// CombatantMarker — renders a single entity token on the grid
// ---------------------------------------------------------------------------
const CombatantMarker = React.memo(({ entity, isPlayer, isFullMode = false, isHovered = false, animationState = null }) => {
  const getGlowStyle = (move) => {
    if (!move) return {};
    const cat = move.category || 'Miscellaneous';
    switch (cat) {
      case 'Attack': return { boxShadow: `0 0 15px 5px ${colors.alpha.danger[60]}`, borderColor: colors.danger };
      case 'Maneuver': return { boxShadow: `0 0 15px 5px ${colors.alpha.primary[60]}`, borderColor: colors.primary };
      case 'Special': return { boxShadow: `0 0 15px 5px ${colors.alpha.special[60]}`, borderColor: colors.special };
      case 'Supernatural': return { boxShadow: `0 0 15px 5px ${colors.alpha.info[60]}`, borderColor: colors.info };
      default: return { boxShadow: `0 0 15px 5px ${colors.text.bright}99`, borderColor: colors.text.bright };
    }
  };

  const move = entity.current_move || entity.prepared_move;
  const glowStyle = getGlowStyle(move);

  // Facing — API may send degrees (int) or a cardinal string
  let facing = 0;
  if (entity.position?.facing !== undefined) {
    if (typeof entity.position.facing === 'number') {
      facing = entity.position.facing;
    } else {
      const FACING_MAP = { N: 0, NE: 45, E: 90, SE: 135, S: 180, SW: 225, W: 270, NW: 315 };
      facing = FACING_MAP[entity.position.facing] || 0;
    }
  }

  // HP / Fatigue stats — support both player and enemy field names
  const hp = entity.hp !== undefined ? entity.hp : (entity.health?.current || 0);
  const maxHp = entity.max_hp !== undefined ? entity.max_hp : (entity.health?.max || 100);
  const fatigue = entity.fatigue || 0;
  const maxFatigue = entity.max_fatigue || entity.maxfatigue || 100;

  const hpPct = maxHp > 0 ? Math.min(1, Math.max(0, hp / maxHp)) : 0;
  const fatPct = maxFatigue > 0 ? Math.min(1, Math.max(0, fatigue / maxFatigue)) : 0;

  const content = (entity.name && entity.name[0]) || '?';

  const triangleClass = isFullMode
    ? 'absolute top-[-2px] left-1/2 -translate-x-1/2 w-0 h-0 border-l-[2px] border-r-[2px] border-b-[3px] border-l-transparent border-r-transparent filter drop-shadow-sm opacity-90'
    : 'absolute top-[-6px] left-1/2 -translate-x-1/2 w-0 h-0 border-l-[6px] border-r-[6px] border-b-[8px] border-l-transparent border-r-transparent filter drop-shadow opacity-90';

  const getAnimationStyle = () => {
    if (!animationState) return {};
    if (animationState.isTarget && animationState.phase === 'impact') {
      switch (animationState.outcome) {
        case 'hit': return { backgroundColor: 'rgba(255, 0, 0, 0.7)', transition: 'background-color 0.1s', zIndex: 60 };
        case 'miss': return { opacity: 0.3, transition: 'opacity 0.2s', filter: 'blur(2px)' };
        case 'parry': return { backgroundColor: 'rgba(255, 200, 0, 0.7)', transition: 'background-color 0.1s', zIndex: 60 };
        default: return {};
      }
    }
    if (animationState.isSource) {
      if (animationState.phase === 'windup')
        return { transform: 'scale(1.15)', transition: 'transform 0.1s ease-out', zIndex: 100 };
      if (animationState.phase === 'strike')
        return { transform: 'scale(1.1)', zIndex: 100 };
      if (animationState.phase === 'expand')
        return { transform: 'scale(1.25)', boxShadow: '0 0 25px rgba(255, 215, 0, 0.9)', transition: 'all 0.15s ease-out', zIndex: 100 };
      if (animationState.phase === 'contract' || animationState.phase === 'return')
        return { transform: 'scale(1)', transition: 'all 0.2s ease-in' };
    }
    return {};
  };

  return (
    <div
      className="relative w-[75%] h-[75%] rounded-full transition-all duration-300 transform-gpu border-2"
      style={{
        ...glowStyle,
        ...getAnimationStyle(),
        backgroundColor: colors.bg.panelDeep,
        borderColor: glowStyle.borderColor || colors.border.main
      }}
    >
      {/* Background fill */}
      <div
        className="absolute inset-0 rounded-full opacity-80"
        style={{ backgroundColor: isPlayer ? colors.alpha.primary[20] : colors.alpha.danger[20] }}
      />

      {/* HP / Fatigue torus */}
      <svg className="absolute inset-0 w-full h-full p-[2px]" viewBox="0 0 100 100">
        {/* HP — left semi-circle */}
        <path d="M 50 95 A 45 45 0 0 1 50 5" fill="none" stroke="#111827" strokeWidth="8" strokeLinecap="butt" />
        <path
          d="M 50 95 A 45 45 0 0 1 50 5"
          fill="none"
          stroke="#ff4444"
          strokeWidth="8"
          strokeDasharray={`${hpPct * 141.4} 141.4`}
          strokeLinecap="butt"
          style={{ transition: 'stroke-dasharray 0.5s ease-in-out' }}
        />
        {/* Fatigue — right semi-circle */}
        <path d="M 50 95 A 45 45 0 0 0 50 5" fill="none" stroke="#111827" strokeWidth="8" strokeLinecap="butt" />
        <path
          d="M 50 95 A 45 45 0 0 0 50 5"
          fill="none"
          stroke="#f59e0b"
          strokeWidth="8"
          strokeDasharray={`${fatPct * 141.4} 141.4`}
          strokeLinecap="butt"
          style={{ transition: 'stroke-dasharray 0.5s ease-in-out' }}
        />
      </svg>

      {/* Facing indicator */}
      <div className="absolute inset-0 pointer-events-none" style={{ transform: `rotate(${facing}deg)` }}>
        <div className={triangleClass} style={{ borderBottomColor: colors.secondary }} />
      </div>

      {/* Entity initial */}
      <div className="absolute inset-0 flex items-center justify-center text-white font-bold text-xs select-none z-10 pointer-events-none">
        {content}
      </div>

      {/* Status effects — fade to full on hover */}
      {!isFullMode && (
        <div
          className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 pointer-events-auto transition-opacity duration-200"
          style={{ opacity: 0.35 }}
          onMouseEnter={(e) => { e.currentTarget.style.opacity = '1'; }}
          onMouseLeave={(e) => { e.currentTarget.style.opacity = '0.35'; }}
        >
          <StatusEffectsIconPanel effects={entity.status_effects} />
        </div>
      )}

      {/* Target reticle overlay */}
      {isHovered && (
        <div className="absolute inset-[-12px] pointer-events-none z-20">
          <svg className="w-full h-full animate-[spin_4s_linear_infinite]" viewBox="0 0 100 100">
            <circle cx="50" cy="50" r="45" fill="none" stroke={colors.secondary} strokeWidth="2" strokeDasharray="10 5" opacity="0.8" />
            <line x1="50" y1="5" x2="50" y2="20" stroke={colors.secondary} strokeWidth="3" />
            <line x1="50" y1="80" x2="50" y2="95" stroke={colors.secondary} strokeWidth="3" />
            <line x1="5" y1="50" x2="20" y2="50" stroke={colors.secondary} strokeWidth="3" />
            <line x1="80" y1="50" x2="95" y2="50" stroke={colors.secondary} strokeWidth="3" />
          </svg>
          <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', animation: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite' }}>
            <div style={{ width: '110%', height: '1px', backgroundColor: colors.secondary, opacity: 0.6 }} />
            <div style={{ width: '1px', height: '110%', backgroundColor: colors.secondary, opacity: 0.6, position: 'absolute' }} />
          </div>
        </div>
      )}
    </div>
  );
});

// ---------------------------------------------------------------------------
// EnemiesList — flat list view used when tab === 'enemies'
// ---------------------------------------------------------------------------
const EnemiesList = React.memo(({ enemies }) => (
  <div style={{ padding: spacing.md, overflowY: 'auto', height: '100%', backgroundColor: colors.bg.main }}>
    <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.sm }}>
      {enemies?.map((enemy, idx) => {
        const hpPct = enemy.max_hp > 0
          ? Math.min(1, Math.max(0, enemy.hp / enemy.max_hp)) * 100
          : 0;
        return (
          <div
            key={enemy.id ?? `${enemy.name}-${idx}`}
            style={{
              backgroundColor: colors.alpha.danger[10],
              border: `1px solid ${colors.alpha.danger[40]}`,
              borderRadius: '4px',
              padding: spacing.sm
            }}
          >
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
                  width: `${hpPct}%`
                }}
              />
            </div>
          </div>
        );
      })}
    </div>
  </div>
));

// ---------------------------------------------------------------------------
// BreadcrumbLayer — ghost dots showing recent movement history
// ---------------------------------------------------------------------------
const BreadcrumbLayer = React.memo(({ breadcrumbs }) => (
  <div style={{ position: 'absolute', inset: 0, padding: spacing.sm, pointerEvents: 'none' }}>
    {breadcrumbs.map((bc) => (
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
));

// ---------------------------------------------------------------------------
// EntityLayer — renders all live combatants with interactions and animations
// ---------------------------------------------------------------------------
const EntityLayer = React.memo(({
  entitiesToRender,
  activeAnimation,
  animationPhase,
  hoveredEntity,
  selectedEntity,
  hoveredTargetId,
  isFullMode,
  onHoverEntity,
  onClearHover,
  onSelectEntity,
}) => (
  <div style={{ position: 'absolute', inset: 0, padding: spacing.sm, pointerEvents: 'none' }}>
    {entitiesToRender.map((item, idx) => {
      const entityId = item.entity.id;

      // Derive per-entity animation state
      let animState = null;
      if (activeAnimation && animationPhase) {
        if (activeAnimation.source_id === entityId) {
          animState = { isSource: true, isTarget: false, phase: animationPhase, outcome: activeAnimation.outcome };
        } else if (activeAnimation.target_id === entityId) {
          animState = { isSource: false, isTarget: true, phase: animationPhase, outcome: activeAnimation.outcome };
        }
      }

      // Strike lunge: push attacker towards target during 'strike' phase
      let transformStyle = {};
      if (animState?.isSource && animState.phase === 'strike' && activeAnimation?.target_id) {
        const target = entitiesToRender.find((e) => e.entity.id === activeAnimation.target_id);
        if (target) {
          const sPos = getPos(item.entity);
          const tPos = getPos(target.entity);
          transformStyle = {
            transform: `translate(${(tPos.x - sPos.x) * 100}%, ${(sPos.y - tPos.y) * 100}%)`,
            transition: 'transform 0.2s cubic-bezier(0.1, 0.7, 1.0, 0.1)',
            zIndex: 100
          };
        }
      } else if (animState?.isSource && animState.phase === 'return') {
        transformStyle = { transform: 'translate(0, 0)', transition: 'transform 0.2s ease-in-out' };
      }

      const isHighlighted = hoveredEntity?.id === entityId || selectedEntity?.id === entityId;

      return (
        <div
          key={`${entityId || idx}-${item.isPlayer ? 'player' : 'enemy'}`}
          onMouseEnter={() => onHoverEntity(item.entity)}
          onMouseLeave={onClearHover}
          onClick={(e) => { e.stopPropagation(); onSelectEntity(item.entity); }}
          style={{
            position: 'absolute',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            opacity: item.isDying ? 0 : 1,
            transition: item.isDying
              ? 'opacity 0.65s ease-out, transform 0.5s ease-in-out'
              : 'transform 0.5s ease-in-out',
            willChange: 'transform',
            cursor: item.isDying ? 'default' : 'pointer',
            pointerEvents: item.isDying ? 'none' : 'auto',
            ...item.style,
            zIndex: isHighlighted ? 50 : (item.style.zIndex || 20)
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

          {/* Hover tooltip */}
          {hoveredEntity?.id === entityId && !selectedEntity && (
            <div className="absolute top-full left-1/2 -translate-x-1/2 mt-4 z-[100] animate-in fade-in slide-in-from-top-2 duration-200 pointer-events-none">
              <div className="bg-black/90 border border-orange/40 rounded px-2 py-1 shadow-2xl backdrop-blur-md min-w-[120px]">
                <div className="text-white text-[10px] font-bold uppercase tracking-wider border-b border-white/10 pb-1 mb-1">
                  {item.entity.name}
                </div>
                <div className="text-orange/80 text-[9px] flex justify-between gap-2">
                  <span>Prep:</span>
                  <span className="font-mono">{item.entity.prepared_move?.name || '---'}</span>
                </div>
              </div>
              {/* Arrow */}
              <div className="w-0 h-0 border-l-[6px] border-r-[6px] border-b-[6px] border-l-transparent border-r-transparent border-b-black/90 absolute left-1/2 -translate-x-1/2 bottom-full" />
            </div>
          )}
        </div>
      );
    })}
  </div>
));

// ---------------------------------------------------------------------------
// SelectedEntityPanel — detailed stats card shown when a combatant is clicked
// ---------------------------------------------------------------------------
const SelectedEntityPanel = React.memo(({ entity, onClose }) => {
  const hp = entity.hp ?? entity.health?.current ?? 0;
  const maxHp = entity.max_hp ?? entity.health?.max ?? 1;
  const maxFatigue = entity.max_fatigue || entity.maxfatigue || 100;

  const hpPct = maxHp > 0 ? Math.min(1, Math.max(0, hp / maxHp)) * 100 : 0;
  const fatiguePct = maxFatigue > 0 ? Math.min(1, Math.max(0, (entity.fatigue || 0) / maxFatigue)) * 100 : 0;

  return (
    <div
      className="absolute top-4 right-4 z-[150] w-[200px] animate-in slide-in-from-right-4 fade-in duration-300 pointer-events-auto"
      onClick={(e) => e.stopPropagation()}
    >
      <div className="bg-black/95 border-2 border-orange/50 rounded-lg p-3 shadow-2xl backdrop-blur-xl">
        {/* Header */}
        <div className="flex justify-between items-start mb-3 border-b border-white/10 pb-2">
          <GameText weight="bold" size="sm" variant="secondary">{entity.name}</GameText>
          <button onClick={onClose} className="text-white/40 hover:text-white transition-colors">
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="space-y-3">
          {/* HP */}
          <div>
            <div className="flex justify-between text-[10px] mb-1">
              <span className="text-white/60">INTEGRITY (HP)</span>
              <span className="text-red-400 font-mono">{hp}/{maxHp}</span>
            </div>
            <div className="h-1.5 w-full bg-red-900/30 rounded-full overflow-hidden">
              <div className="h-full bg-red-500 transition-all duration-500" style={{ width: `${hpPct}%` }} />
            </div>
          </div>

          {/* Fatigue */}
          <div>
            <div className="flex justify-between text-[10px] mb-1">
              <span className="text-white/60">STAMINA (FAT)</span>
              <span className="text-orange-400 font-mono">{entity.fatigue || 0}/{maxFatigue}</span>
            </div>
            <div className="h-1.5 w-full bg-orange-900/30 rounded-full overflow-hidden">
              <div className="h-full bg-orange-500 transition-all duration-500" style={{ width: `${fatiguePct}%` }} />
            </div>
          </div>

          {/* Status Effects */}
          <div>
            <div className="text-[10px] text-white/60 mb-1.5 uppercase tracking-wider">Status Effects</div>
            <div className="flex flex-wrap gap-1">
              <StatusEffectsIconPanel effects={entity.status_effects} />
              {(!entity.status_effects || entity.status_effects.length === 0) && (
                <span className="text-[10px] text-white/30 italic">None active</span>
              )}
            </div>
          </div>

          {/* Current Move */}
          <div className="pt-2 border-t border-white/10">
            <div className="text-[10px] text-white/60 mb-1">CURRENT ACTION</div>
            <div className="text-orange text-xs font-bold">
              {entity.current_move?.name || entity.prepared_move?.name || 'Idle'}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
});

// ---------------------------------------------------------------------------
// DeathBurst — fragment particle explosion rendered at a dying entity's cell
// ---------------------------------------------------------------------------
const DeathBurst = () => {
  const [phase, setPhase] = useState(0); // 0=hidden, 1=burst, 2=fade

  useEffect(() => {
    let raf1 = requestAnimationFrame(() => {
      const raf2 = requestAnimationFrame(() => setPhase(1));
      return () => cancelAnimationFrame(raf2);
    });
    const fadeTimer = setTimeout(() => setPhase(2), 350);
    return () => {
      cancelAnimationFrame(raf1);
      clearTimeout(fadeTimer);
    };
  }, []);

  return (
    <svg
      className="absolute inset-0 w-full h-full overflow-visible"
      viewBox="-100 -100 200 200"
      style={{ pointerEvents: 'none' }}
    >
      {/* Central flash */}
      <circle
        cx="0" cy="0" r="28" fill="white"
        style={{
          opacity: phase === 1 ? 0.9 : 0,
          transition: phase === 1 ? 'opacity 0.12s ease-in' : 'opacity 0.3s ease-out',
        }}
      />
      {/* Fragment particles */}
      {DEATH_FRAGMENTS.map((f, i) => {
        const rad = (f.angle - 90) * Math.PI / 180;
        const tx = phase >= 1 ? Math.cos(rad) * f.distance : 0;
        const ty = phase >= 1 ? Math.sin(rad) * f.distance : 0;
        return (
          <circle
            key={i}
            cx="0" cy="0"
            r={f.size}
            fill={f.color}
            style={{
              transform: `translate(${tx}px, ${ty}px)`,
              opacity: phase === 0 ? 0 : phase === 1 ? 1 : 0,
              transition: phase === 1
                ? 'transform 0.4s cubic-bezier(0.1, 0.7, 1, 0.1), opacity 0.1s'
                : 'opacity 0.3s ease-in',
            }}
          />
        );
      })}
    </svg>
  );
};

// ---------------------------------------------------------------------------
// DeathAnimationLayer — renders burst effects at positions of dying entities
// ---------------------------------------------------------------------------
const DeathAnimationLayer = React.memo(({ dyingEntities, getEntityStyle }) => {
  if (dyingEntities.length === 0) return null;
  return (
    <div style={{ position: 'absolute', inset: 0, padding: spacing.sm, pointerEvents: 'none', zIndex: 150 }}>
      {dyingEntities.map((dying) => {
        const style = getEntityStyle(dying.position, 150);
        if (!style) return null;
        return (
          <div
            key={dying.id}
            style={{ position: 'absolute', ...style, display: 'flex', alignItems: 'center', justifyContent: 'center' }}
          >
            <DeathBurst />
          </div>
        );
      })}
    </div>
  );
});

// ---------------------------------------------------------------------------
// BattlefieldGrid — main exported component
// ---------------------------------------------------------------------------
function BattlefieldGrid({
  combat,
  allBeatStates,
  currentBeatIndex,
  combatLog,
  tab,
  zoom = 1,
  displayedLogCount = 0,
  hoveredTargetId = null,
  mapSize = null,
}) {
  const [activeAnimation, setActiveAnimation] = useState(null);
  const [animationPhase, setAnimationPhase] = useState(null);
  const [lastProcessedLogIndex, setLastProcessedLogIndex] = useState(0);
  const [animationQueue, setAnimationQueue] = useState([]);
  const [dyingEntities, setDyingEntities] = useState([]);
  // Guard ref: set to true on unmount to prevent stale setTimeout callbacks
  const animationCancelRef = useRef(false);

  const [hoveredEntity, setHoveredEntity] = useState(null);
  const [selectedEntity, setSelectedEntity] = useState(null);

  // Smooth camera — zoomed mode only. All mutable values live in refs so the
  // RAF loop never needs to be recreated and only drives a React re-render
  // when the integer snap cell actually changes (i.e. Jean crosses a cell
  // boundary), keeping frame-level CPU cost off the React scheduler.
  const cameraRef    = useRef(null); // { x: float, y: float } — current smooth position
  const targetCamRef = useRef(null); // { x: float, y: float } — desired position
  const snapCellRef  = useRef(null); // { leftX, topY } — last committed integer snap
  const contentDivRef = useRef(null); // wrapper div that receives the sub-cell CSS transform
  const cameraRafRef  = useRef(null);
  const [snapState, setSnapState] = useState(null); // triggers re-render on cell boundary cross

  // Resolve effective map size: API value → bounding box of entity positions → 9
  const resolvedMapSize = useMemo(() => {
    if (mapSize && mapSize > 0) return mapSize;
    let maxCoord = 8; // floor at 9×9
    const entities = [combat?.player, ...(combat?.allies || []), ...(combat?.enemies || [])];
    for (const e of entities) {
      if (e?.position) maxCoord = Math.max(maxCoord, e.position.x, e.position.y);
    }
    return Math.min(100, maxCoord + 1);
  }, [mapSize, combat?.player, combat?.allies, combat?.enemies]);

  // Keep a ref so the RAF loop can read the latest value without being recreated
  const mapSizeRef = useRef(resolvedMapSize);
  useEffect(() => { mapSizeRef.current = resolvedMapSize; }, [resolvedMapSize]);

  const handleGridClick = useCallback((e) => {
    if (e.target === e.currentTarget) setSelectedEntity(null);
  }, []);

  const handleClearHover = useCallback(() => setHoveredEntity(null), []);
  const handleCloseSelectedEntity = useCallback(() => setSelectedEntity(null), []);

  // Set/clear the unmount guard
  useEffect(() => {
    animationCancelRef.current = false;
    return () => { animationCancelRef.current = true; };
  }, []);

  // Enqueue new animations from the combat log as entries are revealed
  useEffect(() => {
    const log = combatLog || combat?.log;
    if (!log) return;
    if (displayedLogCount > lastProcessedLogIndex) {
      const newEntries = log.slice(lastProcessedLogIndex, displayedLogCount);
      const animations = [];
      const killedIds = new Set(); // guard against duplicate death animations in one batch

      newEntries.forEach((entry) => {
        if (!entry.animation) return;
        const anim = entry.animation;
        animations.push(anim);

        // Detect a killing blow — chain a death animation immediately after the attack
        if (anim.target_id && allBeatStates && !killedIds.has(anim.target_id)) {
          const beatIdx = entry.beat_index ?? 0;
          const stateBefore = allBeatStates[Math.max(0, beatIdx - 1)];
          const stateAt = allBeatStates[beatIdx];
          const wasAlive = stateBefore?.enemies?.some(
            (en) => en.id === anim.target_id && (en.hp ?? en.health?.current ?? 1) > 0
          );
          const isNowDead = !stateAt?.enemies?.some(
            (en) => en.id === anim.target_id && (en.hp ?? en.health?.current ?? 0) > 0
          );
          if (wasAlive && isNowDead) {
            const lastKnown = stateBefore.enemies.find((en) => en.id === anim.target_id);
            if (lastKnown?.position) {
              animations.push({ type: 'death', target_id: anim.target_id, position: lastKnown.position, entity: lastKnown });
              killedIds.add(anim.target_id);
            }
          }
        }
      });

      if (animations.length > 0) {
        setAnimationQueue((prev) => [...prev, ...animations]);
      }
      setLastProcessedLogIndex(displayedLogCount);
    }
  }, [combatLog, combat?.log, lastProcessedLogIndex, displayedLogCount, allBeatStates]);

  // Run one animation at a time from the queue
  const playAnimation = useCallback((animData) => {
    const config = ANIMATION_CONFIGS[animData.type] || ANIMATION_CONFIGS.pulse;
    setActiveAnimation({ ...animData, config });
    setAnimationPhase(config.phases[0].name);

    // Register the entity as dying so DeathAnimationLayer can render the burst
    // and EntityLayer can fade out the marker
    if (animData.type === 'death' && animData.position) {
      setDyingEntities((prev) => [...prev, { id: animData.target_id, position: animData.position, entity: animData.entity }]);
    }

    let currentPhaseIndex = 0;

    const advancePhase = () => {
      if (animationCancelRef.current) return; // component unmounted — bail out
      if (currentPhaseIndex >= config.phases.length) {
        setActiveAnimation(null);
        setAnimationPhase(null);
        if (animData.type === 'death') {
          setDyingEntities((prev) => prev.filter((d) => d.id !== animData.target_id));
        }
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
    // State setters are stable; ANIMATION_CONFIGS and animationCancelRef are module/ref level
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!activeAnimation && animationQueue.length > 0) {
      const nextAnim = animationQueue[0];
      setAnimationQueue((prev) => prev.slice(1));
      playAnimation(nextAnim);
    }
  }, [activeAnimation, animationQueue, playAnimation]);

  // Compute player position before camera effect (needed for camera target calculation)
  const playerPos = getPos(combat?.player);

  // Smooth camera RAF loop — reads only refs, drives contentDivRef transform
  // directly (no React state per frame). setSnapState is called only when the
  // integer cell boundary changes (~once per combat beat at most).
  const animateCamera = useCallback(() => {
    const cam = cameraRef.current;
    const tgt = targetCamRef.current;
    if (!cam || !tgt || !contentDivRef.current) {
      cameraRafRef.current = null;
      return;
    }

    const dx = tgt.x - cam.x;
    const dy = tgt.y - cam.y;

    if (Math.abs(dx) < CAMERA_EPSILON && Math.abs(dy) < CAMERA_EPSILON) {
      // Settled — snap to exact target and clear the transform offset
      cameraRef.current = { x: tgt.x, y: tgt.y };
      cameraRafRef.current = null;
      contentDivRef.current.style.transform = '';
      const snap = computeSnapOrigin(cameraRef.current, VIEW_SIZE, mapSizeRef.current);
      if (!snapCellRef.current || snap.leftX !== snapCellRef.current.leftX || snap.topY !== snapCellRef.current.topY) {
        snapCellRef.current = snap;
        setSnapState({ ...snap });
      }
      return;
    }

    // Lerp one step toward target
    cameraRef.current = { x: cam.x + dx * CAMERA_LERP, y: cam.y + dy * CAMERA_LERP };
    const snap = computeSnapOrigin(cameraRef.current, VIEW_SIZE, mapSizeRef.current);

    // Sub-cell offset: shift the content div to cover the fractional remainder
    // fracX > 0 ⇒ shift right (snap over-stepped left);  fracY < 0 ⇒ shift up
    const fracX = (snap.leftX - cameraRef.current.x) / VIEW_SIZE * 100;
    const fracY = (cameraRef.current.y - snap.topY) / VIEW_SIZE * 100;
    contentDivRef.current.style.transform = `translate(${fracX.toFixed(3)}%, ${fracY.toFixed(3)}%)`;

    if (!snapCellRef.current || snap.leftX !== snapCellRef.current.leftX || snap.topY !== snapCellRef.current.topY) {
      snapCellRef.current = snap;
      setSnapState({ ...snap });
    }

    cameraRafRef.current = requestAnimationFrame(animateCamera);
    // No deps — all state accessed via refs; setSnapState is a stable setter
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Update camera target whenever Jean moves or zoom changes
  useEffect(() => {
    if (zoom === 'full') {
      // Full map — no camera animation; clear any residual transform
      if (cameraRafRef.current) { cancelAnimationFrame(cameraRafRef.current); cameraRafRef.current = null; }
      if (contentDivRef.current) contentDivRef.current.style.transform = '';
      cameraRef.current = null;
      snapCellRef.current = null;
      setSnapState(null);
      return;
    }

    const tgtX = Math.max(0, Math.min(resolvedMapSize - VIEW_SIZE, playerPos.x - HALF_VIEW));
    const tgtY = Math.min(resolvedMapSize - 1, Math.max(VIEW_SIZE - 1, playerPos.y + HALF_VIEW));
    targetCamRef.current = { x: tgtX, y: tgtY };

    const snapImmediately = () => {
      if (cameraRafRef.current) { cancelAnimationFrame(cameraRafRef.current); cameraRafRef.current = null; }
      cameraRef.current = { x: tgtX, y: tgtY };
      if (contentDivRef.current) contentDivRef.current.style.transform = '';
      const snap = computeSnapOrigin(cameraRef.current, VIEW_SIZE, resolvedMapSize);
      snapCellRef.current = snap;
      setSnapState({ ...snap });
    };

    if (!cameraRef.current) {
      // First mount in zoomed mode — snap immediately, no animation
      snapImmediately();
      return;
    }

    // If Jean would leave the viewport during a smooth animation (jump > HALF_VIEW
    // cells), snap instead. Moves ≤ HALF_VIEW always keep Jean within the 9-cell
    // window; larger jumps (log skipping, combat start) would make her invisible.
    const pendingX = Math.abs(tgtX - cameraRef.current.x);
    const pendingY = Math.abs(tgtY - cameraRef.current.y);
    if (pendingX > HALF_VIEW || pendingY > HALF_VIEW) {
      snapImmediately();
      return;
    }

    // Start the RAF loop if it is not already running
    if (!cameraRafRef.current) {
      cameraRafRef.current = requestAnimationFrame(animateCamera);
    }
  }, [zoom, playerPos.x, playerPos.y, animateCamera, resolvedMapSize]);

  // Cancel camera RAF on unmount
  useEffect(() => () => {
    if (cameraRafRef.current) cancelAnimationFrame(cameraRafRef.current);
  }, []);

  // -------------------------------------------------------------------------
  // Viewport computations — done unconditionally (before any early return) so
  // the hooks below are always called in the same order.
  // -------------------------------------------------------------------------
  const isFullMode = zoom === 'full';
  const gridCols = isFullMode ? resolvedMapSize : VIEW_SIZE;
  let leftX, topY;
  if (isFullMode) {
    leftX = 0;
    topY = resolvedMapSize - 1;
  } else if (snapState) {
    leftX = snapState.leftX;
    topY  = snapState.topY;
  } else {
    leftX = Math.max(0, Math.min(resolvedMapSize - VIEW_SIZE, playerPos.x - HALF_VIEW));
    topY  = Math.min(resolvedMapSize - 1, Math.max(VIEW_SIZE - 1, playerPos.y + HALF_VIEW));
  }

  /** Convert a world grid position to the absolute-CSS style needed by the layers. */
  const getEntityStyle = useCallback((pos, baseZ = 20) => {
    if (!pos || pos.x < leftX || pos.x >= leftX + gridCols || pos.y > topY || pos.y <= topY - gridCols) return null;
    const col = pos.x - leftX;
    const row = topY - pos.y;
    return {
      left: 0, top: 0,
      transform: `translate(${col * 100}%, ${row * 100}%)`,
      width: `${(1 / gridCols) * 100}%`,
      height: `${(1 / gridCols) * 100}%`,
      zIndex: baseZ
    };
  }, [leftX, topY, gridCols]);

  // Memoized breadcrumb trail — only recomputed when beat history or viewport changes
  const breadcrumbs = useMemo(() => {
    const result = [];
    if (allBeatStates && currentBeatIndex !== undefined) {
      const historyLength = 10;
      const startIdx = Math.max(0, currentBeatIndex - historyLength);
      for (let i = startIdx; i < currentBeatIndex; i++) {
        const beatState = allBeatStates[i];
        if (!beatState) continue;
        const opacity = 0.2 + ((i - startIdx) / historyLength) * 0.4;
        if (beatState.player) {
          const style = getEntityStyle(getPos(beatState.player), 5);
          if (style) result.push({ style, color: colors.primary, opacity, id: `p-${i}` });
        }
        beatState.enemies?.forEach((enemy) => {
          const style = getEntityStyle(getPos(enemy), 5);
          if (style) result.push({ style, color: colors.danger, opacity, id: `${enemy.id}-${i}` });
        });
      }
    }
    return result;
  }, [allBeatStates, currentBeatIndex, getEntityStyle]);

  // Memoized entity list — only recomputed when combatants or viewport changes
  const entitiesToRender = useMemo(() => {
    const dyingIds = new Set(dyingEntities.map((d) => d.id));
    const result = [];
    if (combat?.player) {
      const style = getEntityStyle(getPos(combat.player));
      if (style) result.push({ entity: combat.player, style, isPlayer: true });
    }
    combat?.allies?.forEach((ally) => {
      if (ally.hp === undefined || ally.hp > 0 || (ally.health?.current ?? 0) > 0) {
        const style = getEntityStyle(getPos(ally));
        if (style) result.push({ entity: ally, style, isPlayer: true });
      }
    });
    combat?.enemies?.forEach((enemy) => {
      if (dyingIds.has(enemy.id)) return;
      if (enemy.hp === undefined || enemy.hp > 0 || (enemy.health?.current ?? 0) > 0) {
        const style = getEntityStyle(getPos(enemy));
        if (style) result.push({ entity: enemy, style, isPlayer: false });
      }
    });
    // Dying enemies rendered from last-known snapshot during fade-out
    dyingEntities.forEach((dying) => {
      if (!dying.entity) return;
      const style = getEntityStyle(dying.position);
      if (style) result.push({ entity: dying.entity, style, isPlayer: false, isDying: true });
    });
    return result;
  }, [combat?.player, combat?.allies, combat?.enemies, dyingEntities, getEntityStyle]);

  // Memoized background cell array — avoids reallocating on every render
  const gridBgCells = useMemo(() => Array.from({ length: gridCols * gridCols }), [gridCols]);

  // -------------------------------------------------------------------------
  // Enemies tab: flat list view
  // -------------------------------------------------------------------------
  if (tab === 'enemies') {
    return <EnemiesList enemies={combat.enemies} />;
  }

  return (
    <div
      onClick={handleGridClick}
      style={{ position: 'relative', width: '100%', height: '100%', backgroundColor: colors.bg.main, overflow: 'hidden' }}
    >
      {/*
        contentDivRef receives a sub-cell CSS transform each RAF frame,
        smoothly sliding the grid between integer snap positions without
        triggering a React re-render. The outer container clips the overflow
        so the edges of the map never become visible.
      */}
      <div ref={contentDivRef} style={{ position: 'absolute', inset: 0, willChange: 'transform' }}>
        {/* Background grid */}
        <div style={{
          position: 'absolute', inset: 0,
          display: 'grid', gap: '1px', padding: spacing.sm,
          gridTemplateColumns: `repeat(${gridCols}, minmax(0, 1fr))`,
          gridTemplateRows: `repeat(${gridCols}, minmax(0, 1fr))`,
          pointerEvents: 'none'
        }}>
          {gridBgCells.map((_, i) => (
            <div key={i} style={{ backgroundColor: 'rgba(255,255,255,0.03)', borderRadius: '2px' }} />
          ))}
        </div>

        <BreadcrumbLayer breadcrumbs={breadcrumbs} />

        <EntityLayer
          entitiesToRender={entitiesToRender}
          activeAnimation={activeAnimation}
          animationPhase={animationPhase}
          hoveredEntity={hoveredEntity}
          selectedEntity={selectedEntity}
          hoveredTargetId={hoveredTargetId}
          isFullMode={isFullMode}
          onHoverEntity={setHoveredEntity}
          onClearHover={handleClearHover}
          onSelectEntity={setSelectedEntity}
        />

        <DeathAnimationLayer dyingEntities={dyingEntities} getEntityStyle={getEntityStyle} />
      </div>

      {/* SelectedEntityPanel lives outside contentDivRef — it is screen-fixed
          relative to the grid container and must not be translated with the map. */}
      {selectedEntity && (
        <SelectedEntityPanel
          entity={selectedEntity}
          onClose={handleCloseSelectedEntity}
        />
      )}
    </div>
  );
}

export default React.memo(BattlefieldGrid);
