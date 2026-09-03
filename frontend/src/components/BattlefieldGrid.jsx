import React, { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import StatusEffectsIconPanel from './StatusEffectsIconPanel';
import { colors, spacing, shadows, fonts } from '../styles/theme';
import GameText from './GameText';
import { useAudio } from '../context/AudioContext';
import { getAnimationConfig, impactSfxFor, strikeFlashFor } from '../utils/animationConfigs';
import { logEntryKey, LOG_KEY_SEP } from '../utils/combatLogKey';
import { categoryColor, categoryColorOrNull, categoryGlowOrNull } from '../utils/categories';
import { beatSfxFor, animationImpactCue } from '../utils/combatSfx';
import {
  scheduleSfxChain,
  scheduleAnimationLayers,
  effectiveDuration,
  MAX_CONCURRENT_LAYERS,
} from '../utils/combatTiming';
import { SFX_DURATIONS } from '../utils/sfxDurations';
import useDoubleRaf from '../hooks/useDoubleRaf';
import { formatCombatMoveStatus, isMovePending, beatsUntilResolve } from '../utils/combatMoveStatus';
import { useFeatureFlag } from '../utils/featureFlags';
import {
  hasTerrain, terrainReader, terrainLabel, terrainVariant, terrainKindsPresent,
  regionLabel, legendNotes, TERRAIN_STYLE, RAISED_KINDS, ELEVATION_RIM_SHADOW,
} from '../utils/terrain';
import { spriteFor, spriteClipFor, terrainTileUrl, facingDegrees } from '../utils/sprites';
import { useSpriteManifest } from '../hooks/useSpriteManifest';
import SpriteToken from './SpriteToken';
import { isLiving } from '../utils/combatEntities';

// Fragment definitions for the death burst — module-level, never recreated
const DEATH_FRAGMENTS = Array.from({ length: 12 }, (_, i) => ({
  angle: i * 30,
  distance: 42 + (i % 3) * 12,
  size: i % 3 === 0 ? 5 : i % 3 === 1 ? 3 : 4,
  color: ['#ffffff', '#aaddff', '#88ccff', '#ffeedd'][i % 4],
}));

// Opt-in debug flag — enabled via `?debug=anim` in the URL. Used to render a
// tiny overlay exposing the current animation phase so pacing complaints can
// be reproduced and triaged without a dev build.
const ANIM_DEBUG = typeof window !== 'undefined'
  && /[?&]debug=anim\b/.test(window.location.search);

// ---------------------------------------------------------------------------
// Grid / camera constants — module level
// ---------------------------------------------------------------------------
export const VIEW_SIZE = 13;  // viewport cell count in follow mode; shows enemies within attacking range (up to 9 cells) plus buffer
const HALF_VIEW = Math.floor(VIEW_SIZE / 2);
const CAMERA_LERP = 0.12;     // fraction of remaining distance per RAF frame
const CAMERA_EPSILON = 0.004; // settle threshold (cells)

// ---------------------------------------------------------------------------
// View modes
// ---------------------------------------------------------------------------
// `follow` keeps a fixed VIEW_SIZE window centered on Jean. `fit` frames every
// living combatant, NOT the whole arena: arenas scale to 3 cells per combatant
// (src/coordinate_config.py) and reach 100x100, so arena framing yields
// thousands of empty cells and pea-sized tokens outside a full-map brawl.
// Framing the action keeps tokens legible at every roster size.
export const VIEW_MODE_FOLLOW = 'follow';
export const VIEW_MODE_FIT = 'fit';

// Pointer travel above which a mouseup is treated as the end of a pan gesture
// rather than a click on the map.
const DRAG_CLICK_THRESHOLD_PX = 6;

// Arena ceiling, mirroring get_dynamic_grid_size's clamp in
// src/coordinate_config.py. Bounds a gridCols^2 loop and DOM-node count.
const MAX_MAP_SIZE = 100;

// Cells of breathing room around the combatant bounding box in fit mode.
const FIT_PADDING = 2;
// Fit framing is quantized to this many cells and only re-derived when the
// current frame stops working (see fitBox below), so the map does not visibly
// rescale every single beat as combatants shuffle a cell.
const FIT_STEP = 4;
// Ceiling on queued animations. Draining is ~1-2/sec (phase totals are
// 500-1050ms), so a faster beat stream accumulates without this.
const MAX_ANIMATION_QUEUE = 200;

/**
 * Normalize the `zoom` prop onto a named view mode. The legacy encoding
 * (`1` = follow, `'full'` = fit) is still accepted so callers and existing
 * tests keep working.
 */
const normalizeViewMode = (zoom) =>
  (zoom === VIEW_MODE_FIT || zoom === 'full') ? VIEW_MODE_FIT : VIEW_MODE_FOLLOW;

/** "in 2 beats" / "in 1 beat" — one place, so the badge, its accessible name
 *  and the enemies list can never disagree about pluralization. */
const formatBeatCountdown = (beats) => `in ${beats} beat${beats === 1 ? '' : 's'}`;


/**
 * Snap a float camera origin to the nearest valid integer cell.
 * In follow mode (the only path that reaches this) Jean is always centered —
 * no edge-clamping — so off-map cells render as empty/dimmed rather than the
 * camera stopping short near map edges.
 */
const computeSnapOrigin = (cam) => ({
  leftX: Math.round(cam.x),
  topY:  Math.round(cam.y),
});

// ---------------------------------------------------------------------------
// Pure helpers — module level, stable references, never re-created
// ---------------------------------------------------------------------------

/** Returns the grid position of an entity, defaulting to origin if absent. */
const getPos = (entity) => entity?.position || { x: 0, y: 0 };

/** Phase duration lookup on a config; falls back when the phase is unknown. */
const phaseDurationOf = (config, phaseName, fallback = 200) =>
  config?.phases?.find((p) => p.name === phaseName)?.duration ?? fallback;

/**
 * The revealed slice of the combat log, each entry paired with a stable id.
 *
 * Two problems this solves, both of which used to be one arithmetic expression
 * (`log.slice(lastProcessedLogIndex, displayedLogCount)`):
 *
 * 1. `displayedLogCount` is NOT an index into this log. It is the length of
 *    LeftPanel's revealed list, which dedups by `logEntryKey` — and the N
 *    carrier entries of one multi-target swing are byte-identical (same round,
 *    same `"<Move> animation"` message), so the revealed list holds one and the
 *    raw log holds N. Slicing the raw log by that count cut the window short and
 *    dropped every resolution after the second. So the frontier is recovered
 *    properly here: walk the log counting DISTINCT keys until the count is
 *    reached, keeping the duplicates along the way — they are exactly the
 *    per-target landings the battlefield has to animate.
 *
 * 2. The adapter now bounds `player.combat_log` and trims it from the FRONT, so
 *    absolute indices shift under the cursor and skew it permanently. When the
 *    carrier brings its own `animation.seq` (monotonic per fight, streamed by
 *    the adapter) that IS the id — genuinely trim-proof. Otherwise the id is
 *    positional only WITHIN one beat (`beat_index` + key + which repeat it is),
 *    so trimming whole older beats moves nothing; only a trim landing inside a
 *    beat can disturb that beat's own repeats.
 */
export const revealedLogEntries = (log, displayedLogCount) => {
  const seenKeys = new Set();
  const repeats = new Map();
  let distinct = 0;
  const revealed = [];
  for (const entry of log || []) {
    const key = logEntryKey(entry);
    if (!seenKeys.has(key)) {
      if (distinct >= displayedLogCount) break;
      seenKeys.add(key);
      distinct += 1;
    }
    // Repeat ordinals are tracked for EVERY entry (even seq-carrying ones), so
    // a mixed log cannot shift the ordinals of the entries that need them.
    const scope = `${entry?.beat_index ?? 0}${LOG_KEY_SEP}${key}`;
    const repeat = repeats.get(scope) || 0;
    repeats.set(scope, repeat + 1);
    const seq = entry?.animation?.seq;
    const id = Number.isFinite(seq)
      ? `seq${LOG_KEY_SEP}${seq}`
      : `${scope}${LOG_KEY_SEP}${repeat}`;
    revealed.push({ entry, id });
  }
  return revealed;
};

/** Stable empty default for `animationStates`: a token that is in no animation
 *  would otherwise hand React.memo a fresh array identity on every render and
 *  re-render the whole roster — and each layer ticks its own phase, so that
 *  churn is multiplied by layers x phases per swing. */
const NO_ANIMATION_STATES = Object.freeze([]);

/**
 * Every animation state one entity is involved in on this frame, as
 * `{ anim, isSource, isTarget }` — all animation fields are read through
 * `anim` (one access path; the record used to also mirror phase/outcome/config
 * at the top level and consumers mixed the two).
 *
 * Animations play CONCURRENTLY (one move resolves once per target and each
 * resolution animates in full — see playAnimations), so an entity can be the
 * source of one layer while being the target of another, or the target of
 * several landings at once. This used to pick a single match with an if/else
 * chain over one active animation; with N in flight, picking one silently drops
 * the rest and a target hit twice in one swing flashes once.
 *
 * A layer that has not started its own phase clock yet (`phase == null` — it is
 * in the active set but still inside its stagger) contributes nothing, so
 * queued layers render as if absent. Source still wins over target *within one
 * animation*: a self-targeted move must not fight its own strike flash.
 */
export const collectAnimationStates = (activeAnimations, entityId) => {
  const states = [];
  if (entityId == null) return NO_ANIMATION_STATES;
  for (const anim of activeAnimations || []) {
    if (!anim?.phase) continue;
    if (anim.source_id === entityId) {
      states.push({ anim, isSource: true, isTarget: false });
    } else if (anim.target_id === entityId) {
      states.push({ anim, isSource: false, isTarget: true });
    }
  }
  return states.length ? states : NO_ANIMATION_STATES;
};

/**
 * Fold the styles of an entity's concurrent animation states into one.
 *
 * Later states win on conflicting properties, EXCEPT `transform`, which is
 * composed: a token scaling as a source while skidding as a glance target needs
 * both, and a plain spread would silently drop the earlier one — the same
 * quiet-failure shape as this file's documented drift bugs. `undefined` values
 * are skipped so an absent property in a later state can't blank an earlier
 * one (strikeFlashFor and the source-phase styles both emit `undefined` keys).
 *
 * Byte-identical transform strings are applied ONCE: transforms multiply, so
 * two overlapping landings on one token would otherwise square the glance
 * skid (`translate(8%,-8%) scale(0.94)`, twice) — the same compounding bug the
 * lead gate in animationStyleFor closes on the source side.
 */
export const mergeAnimationStyles = (styles) => {
  const merged = {};
  const transforms = [];
  for (const style of styles || []) {
    for (const key of Object.keys(style || {})) {
      const value = style[key];
      if (value === undefined) continue;
      if (key === 'transform') {
        if (!transforms.includes(value)) transforms.push(value);
        continue;
      }
      merged[key] = value;
    }
  }
  if (transforms.length) merged.transform = transforms.join(' ');
  return merged;
};

/**
 * Marker styling for ONE animation state: source phases read scale/glow from
 * the animation config; the target gets an outcome flash (or a fixed glow for
 * buff/debuff-style effects) during the config's impact phase.
 *
 * Source styling belongs to the LEAD layer alone, like the token's motion and
 * the swing's non-impact cues: one swing is one movement of the caster, and
 * every follower emitting the config's `scale()` too compounded them in the
 * merge — a 4-layer heavy_attack rendered the caster at 1.28^4 ≈ 2.7x.
 */
const animationStyleFor = (state) => {
  const { anim } = state;
  const cfg = anim.config;

  if (state.isTarget) {
    if (anim.phase !== 'impact') return {};
    const treatment = cfg?.target;
    if (treatment && treatment !== 'strike') {
      // Fixed treatment (debuff hex, drain wither, ...)
      return {
        transform: treatment.scale ? `scale(${treatment.scale})` : undefined,
        boxShadow: treatment.glow ? `0 0 18px 6px ${treatment.glow}` : undefined,
        transition: 'all 0.2s ease-out',
        zIndex: 60,
      };
    }
    // Outcome-dependent strike flash. Resolved in animationConfigs so the
    // visual treatment and the impact SFX cue for an outcome are declared
    // together and stay in step with the engine's OUTCOMES vocabulary.
    return strikeFlashFor(anim.outcome);
  }

  if (state.isSource && anim.isLead) {
    const phaseStyle = cfg?.source?.[anim.phase];
    if (phaseStyle) {
      return {
        transform: phaseStyle.scale ? `scale(${phaseStyle.scale})` : undefined,
        boxShadow: phaseStyle.glow ? `0 0 22px 8px ${phaseStyle.glow}` : undefined,
        transition: 'transform 0.18s ease-out, box-shadow 0.18s ease-out',
        zIndex: 100,
      };
    }
    if (anim.phase === 'return' || anim.phase === 'contract')
      return { transform: 'scale(1)', transition: 'all 0.2s ease-in' };
  }
  return {};
};

/** Heavy hits and shockwaves rattle the target cell — but never on a miss. */
const isShakingTarget = (state) => Boolean(
  state.isTarget
  && state.anim.config?.shake
  && state.anim.phase === 'impact'
  && state.anim.outcome !== 'miss'
);

/**
 * Split the head of the animation queue into the layers that play together and
 * the ones that wait. Returns `[batch, rest]` (`[[], []]` for an empty queue).
 *
 * One swing = one batch. An area move reports one resolution per target, all
 * carrying the same `type`, `source_id` and `swing_key`, and the owner wants
 * every one of them to animate in full, layered. Two *different* actors in the
 * same beat are two events, though, so they stay sequential — overlapping them
 * would make the battlefield unreadable, which is the opposite of the point.
 * `swing_key` scopes the batch to ONE swing: without it, two separate swings
 * by the same actor merged, and the second lost its windup, motion and whoosh.
 * Strict equality keeps unstamped payloads batching as before (undefined ===
 * undefined), so an adapter that does not yet send the key degrades to the
 * old behaviour rather than serializing everything.
 *
 * The batch is clamped to MAX_CONCURRENT_LAYERS: a deep queue must never
 * start hundreds of Audio elements/overlays/timer chains inside one lead
 * window. Overflow falls through to `rest` and plays as a follow-up batch.
 *
 * A death chained onto a member of the swing is pushed back behind the whole
 * batch rather than splitting it: an arc that kills its second of four targets
 * must still land on the other two before anyone falls over. "The whole batch"
 * includes the clamp's overflow — a death deferred before the batch filled
 * must also sit behind any same-swing carriers that overflowed past
 * MAX_CONCURRENT_LAYERS, or a >cap swing drops its victim before landings
 * cap+1..N play.
 */
export const takeAnimationBatch = (queue) => {
  if (!queue || queue.length === 0) return [[], []];
  const head = queue[0];
  const batch = [head];
  const deferredDeaths = [];
  let cursor = 1;
  // Deaths and sourceless entries are events in their own right, never a swing.
  if (head.type !== 'death' && head.source_id != null) {
    for (; cursor < queue.length && batch.length < MAX_CONCURRENT_LAYERS; cursor++) {
      const next = queue[cursor];
      if (next.type === 'death') { deferredDeaths.push(next); continue; }
      if (
        next.type === head.type
        && next.source_id === head.source_id
        && next.swing_key === head.swing_key
      ) {
        batch.push(next);
        continue;
      }
      break;
    }
  }
  const remainder = queue.slice(cursor);
  // Deferred deaths go behind the same swing's clamp overflow: the contiguous
  // same-swing prefix of the remainder holds this swing's landings that did
  // not fit the batch, and they must play before the target falls over.
  // Everything past that prefix is a different event and keeps its queue
  // order after the deaths.
  let overflowEnd = 0;
  if (deferredDeaths.length) {
    while (
      overflowEnd < remainder.length
      && remainder[overflowEnd].type !== 'death'
      && remainder[overflowEnd].type === head.type
      && remainder[overflowEnd].source_id === head.source_id
      && remainder[overflowEnd].swing_key === head.swing_key
    ) overflowEnd += 1;
  }
  const rest = [
    ...remainder.slice(0, overflowEnd),
    ...deferredDeaths,
    ...remainder.slice(overflowEnd),
  ];
  return [batch, rest];
};

/**
 * Remove exactly the drained batch from the live queue, by enqueue-time
 * identity (`queueId`).
 *
 * INVARIANT: the queue snapshot a batch was computed from is NOT necessarily a
 * prefix of the live queue by the time this functional update runs — the
 * bounded-append helper trims the queue from the FRONT, and the per-fight
 * reset can have emptied it in the same commit. Identity filtering is correct
 * under all of those; the positional arithmetic it replaced
 * (`prev.slice(snapshot.length)`) resurrected cleared queues and replayed
 * front-trimmed ones.
 */
export const removeBatchByIdentity = (queue, batch) => {
  const drained = new Set(batch.map((item) => item.queueId));
  return queue.filter((item) => !drained.has(item.queueId));
};

/** Append to the animation queue under its ceiling. Trims from the FRONT —
 *  which is exactly why the drain removes by queueId, never by position. */
const appendBounded = (queue, items) => [...queue, ...items].slice(-MAX_ANIMATION_QUEUE);

/** Finite number or the supplied default. A non-numeric field must not reach
 *  the percentages: `Math.min(1, Math.max(0, NaN))` is `NaN`, which CSS and SVG
 *  discard as invalid — so a broken HP field would render as *full* health in
 *  the torus, the bars and the numerals. */
const finiteOr = (value, fallback) => {
  const n = Number(value);
  return Number.isFinite(n) ? n : fallback;
};

/**
 * Normalizes a combatant's HP/fatigue across both serialized shapes: flat
 * `hp`/`max_hp`/`max_fatigue` and the nested legacy `health.{current,max}` /
 * `maxfatigue` — src/api/serializers/combat.py emits all of them.
 *
 * The single derivation of these six values; every HP torus, bar and numeral
 * in this file routes through it so a bar can never disagree with the numbers
 * printed beside it. `hpPct`/`fatPct` are 0-1 fractions — multiply by 100
 * before using either as a CSS width.
 */
function resolveEntityStats(entity) {
  if (!entity) return { hp: 0, maxHp: 1, fatigue: 0, maxFatigue: 1, hpPct: 0, fatPct: 0 };
  const hp = finiteOr(entity.hp ?? entity.health?.current, 0);
  const maxHp = finiteOr(entity.max_hp ?? entity.health?.max, 100);
  const fatigue = finiteOr(entity.fatigue, 0);
  const maxFatigue = finiteOr(entity.max_fatigue ?? entity.maxfatigue, 100);

  const hpPct = maxHp > 0 ? Math.min(1, Math.max(0, hp / maxHp)) : 0;
  const fatPct = maxFatigue > 0 ? Math.min(1, Math.max(0, fatigue / maxFatigue)) : 0;

  return { hp, maxHp, fatigue, maxFatigue, hpPct, fatPct };
}

// ---------------------------------------------------------------------------
// CombatantMarker — renders a single entity token on the grid
// ---------------------------------------------------------------------------

const CombatantMarker = React.memo(({
  entity,
  // True for Jean AND for every ally — this is side, not identity. Named
  // `isPlayer` originally, which read as "this token is Jean" and invited
  // changes meant for Jean alone to land on the whole friendly side.
  // `isHero` is the one that means Jean.
  isFriendly,
  isHero = false,
  isCompact = false,
  isHovered = false,
  isSelected = false,
  animationStates = NO_ANIMATION_STATES,
  displaySymbol = null,
  // Sheet set from the sprite manifest (utils/sprites.spriteFor) and the clip
  // to play; null sprite = draw the glyph token.
  sprite = null,
  spriteClip = 'idle',
  spriteRows = undefined,
  combatSpeed = 1,
}) => {
  const move = entity.current_move;
  // Only an unresolved move is intent. A combatant in recoil/cooldown must not
  // glow like one charging an attack — this is the strongest signal on the map.
  const pending = isMovePending(move);
  const moveCategory = pending ? (move.category || 'Miscellaneous') : null;
  const pendingGlowColor = moveCategory ? categoryGlowOrNull(moveCategory) : null;
  const pendingBorderColor = moveCategory ? categoryColorOrNull(moveCategory) : null;
  const beatsToResolve = beatsUntilResolve(move);
  const [isHoveredEffect, setIsHoveredEffect] = useState(false);

  // Alignment border: lime for friend/player, red for enemy. When a pending
  // move is set, its category color takes precedence on the border.
  const alignmentBorder = isFriendly ? colors.primary : colors.danger;

  // Facing — API sends a cardinal string (pos.facing.name); degrees are
  // accepted defensively. One normalisation, shared with the sprite row pick.
  const facing = facingDegrees(entity.position?.facing);

  // HP / Fatigue stats
  const { hpPct, fatPct } = resolveEntityStats(entity);

  const content = displaySymbol || entity.battle_symbol || (entity.name && entity.name[0]) || '?';

  const triangleClass = isCompact
    ? 'absolute top-[-2px] left-1/2 -translate-x-1/2 w-0 h-0 border-l-[2px] border-r-[2px] border-b-[3px] border-l-transparent border-r-transparent filter drop-shadow-sm opacity-90'
    : 'absolute top-[-6px] left-1/2 -translate-x-1/2 w-0 h-0 border-l-[6px] border-r-[6px] border-b-[8px] border-l-transparent border-r-transparent filter drop-shadow opacity-90';

  // Config-driven marker styling, folded across every animation this token is
  // currently part of (it can be the source of the swing and the target of a
  // concurrent landing at the same time).
  const animationStyle = useMemo(
    () => mergeAnimationStyles(animationStates.map(animationStyleFor)),
    [animationStates]
  );

  // Target shake — heavy hits and shockwaves rattle the target cell. Any one
  // qualifying landing is enough; the CSS class is not additive.
  const targetShake = animationStates.some(isShakingTarget);

  return (
    <div
      className={`relative w-[75%] h-[75%] rounded-full transition-all duration-300 transform-gpu border-[3px]${
        pendingGlowColor ? ' battlefield-pending-glow' : ''
      }${targetShake ? ' battlefield-target-shake' : ''}`}
      style={{
        // Slightly lighter than panelDeep so the pulsing glow reads through the
        // token edge. panelHeavy keeps the marker legible without muddying the glow.
        backgroundColor: colors.bg.panelHeavy,
        borderColor: pendingBorderColor || alignmentBorder,
        // CSS var drives the pulsing glow animation; falls back to a static
        // thin halo (alignment-colored) when no move is prepared so friend/foe
        // remains visible even without move intent.
        ['--pending-glow']: pendingGlowColor || 'transparent',
        boxShadow: pendingGlowColor
          ? undefined
          : `0 0 6px 1px ${isFriendly ? colors.alpha.primary[40] : colors.alpha.danger[40]}`,
        // Spread last so an active animation's backgroundColor/boxShadow/transform
        // (hit flash, parry/block flash, debuff/drain glow, per-phase source glow)
        // actually take effect instead of being clobbered by the defaults above.
        ...animationStyle,
      }}
    >
      {/* Background fill — saturated by alignment for high-contrast friend/foe.
          Under a sprite it thins to a tint so the art reads. */}
      <div
        className="absolute inset-0 rounded-full"
        style={{
          backgroundColor: isFriendly ? colors.alpha.primary[30] : colors.alpha.danger[30],
          opacity: sprite ? 0.35 : 0.85,
        }}
      />

      {/* Animated sprite (art pipeline) — replaces the initial when the
          manifest has a sheet set for this combatant. Inset so the HP/fatigue
          torus stays visible around it. */}
      {sprite && (
        <div className="absolute inset-[10%] z-10 pointer-events-none">
          <SpriteToken
            sprite={sprite}
            clip={spriteClip}
            facing={facing}
            rows={spriteRows}
            running={!isCompact}
            speed={combatSpeed}
          />
        </div>
      )}

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

      {/* Entity initial — the token's identity when no sprite sheet exists */}
      {!sprite && (
        <div className="absolute inset-0 flex items-center justify-center text-white font-bold text-xs select-none z-10 pointer-events-none">
          {content}
        </div>
      )}

      {/* Hero marker — tiny gold star above Jean so players can always locate
          her amid a crowd of allies. */}
      {isHero && (
        <div
          className="absolute pointer-events-none z-20 select-none"
          style={{
            top: isCompact ? '-4px' : '-10px',
            right: isCompact ? '-2px' : '-4px',
            fontSize: isCompact ? '8px' : '14px',
            lineHeight: 1,
            color: colors.gold,
            textShadow: '0 0 4px rgba(0,0,0,0.9)',
          }}
          aria-label="Jean"
        >
          ★
        </div>
      )}

      {/* Beat countdown — how many beats until this combatant's in-progress
          move resolves. The pulsing category glow says "something is coming";
          this says *when*, which is the half the player actually needs to
          decide between blocking, closing distance, or getting clear. */}
      {!isCompact && beatsToResolve !== null && (
        <div
          className="absolute pointer-events-none select-none z-20 flex items-center justify-center rounded-full"
          style={{
            bottom: '-5px',
            right: '-7px',
            minWidth: '15px',
            height: '15px',
            padding: '0 3px',
            fontSize: '10px',
            lineHeight: 1,
            fontWeight: 'bold',
            fontFamily: 'monospace',
            color: '#000',
            backgroundColor: pendingBorderColor || colors.secondary,
            border: '1px solid rgba(0,0,0,0.6)',
            textShadow: 'none',
          }}
          title={`Resolves ${formatBeatCountdown(beatsToResolve)}`}
          aria-label={`Move resolves ${formatBeatCountdown(beatsToResolve)}`}
        >
          {beatsToResolve}
        </div>
      )}

      {/* Status effects — fade to full on hover. Gated on there being any:
          StatusEffectsIconPanel renders null for an empty list, so without
          this every marker on the field carries an empty positioned div, two
          mouse listeners and an opacity transition that can never show. */}
      {!isCompact && entity.status_effects?.length > 0 && (
        <div
          className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 pointer-events-auto transition-opacity duration-200"
          style={{ opacity: isHoveredEffect ? 1 : 0.35 }}
          onMouseEnter={() => setIsHoveredEffect(true)}
          onMouseLeave={() => setIsHoveredEffect(false)}
        >
          <StatusEffectsIconPanel effects={entity.status_effects} />
        </div>
      )}

      {/* Hover reticle — rotating orange circle with crosshairs. Transient:
          appears only while the cursor is over the token. */}
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

      {/* Selection brackets — static gold L-shaped corners. Persistent: stays
          while the entity remains selected, visually distinct from hover. */}
      {isSelected && (
        <div
          className="absolute inset-[-8px] pointer-events-none z-20"
          aria-hidden="true"
        >
          <svg className="w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="none">
            <g fill="none" stroke={colors.gold} strokeWidth="4" strokeLinecap="square">
              {/* top-left */}
              <polyline points="5,20 5,5 20,5" />
              {/* top-right */}
              <polyline points="80,5 95,5 95,20" />
              {/* bottom-right */}
              <polyline points="95,80 95,95 80,95" />
              {/* bottom-left */}
              <polyline points="20,95 5,95 5,80" />
            </g>
          </svg>
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
        // Bar AND numerals both come from resolveEntityStats. Routing only
        // one through it is worse than routing neither: an enemy in the nested
        // legacy shape renders a correct bar above "HP: undefined / undefined".
        // Local is `hpPercent` because the helper's `hpPct` is a 0-1 fraction
        // and mixing the two silently multiplies by 100.
        const { hp, maxHp, hpPct } = resolveEntityStats(enemy);
        const hpPercent = hpPct * 100;
        const move = enemy.current_move;
        const category = isMovePending(move) ? (move.category || 'Miscellaneous') : null;
        const moveColor = category ? categoryColorOrNull(category) : null;
        const beatsToResolve = beatsUntilResolve(move);
        return (
          <div
            key={enemy.id ?? `${enemy.name}-${idx}`}
            style={{
              backgroundColor: colors.alpha.danger[10],
              border: `1px solid ${colors.alpha.danger[40]}`,
              borderLeft: moveColor
                ? `4px solid ${moveColor}`
                : `1px solid ${colors.alpha.danger[40]}`,
              borderRadius: '4px',
              padding: spacing.sm
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
              <div>
                <GameText variant="secondary" weight="bold" size="sm">{enemy.name}</GameText>
                <GameText variant="secondary" size="xs" style={{ marginTop: spacing.xs }}>
                  HP: {hp} / {maxHp}
                  {enemy.distance !== undefined && (
                    <span style={{ color: colors.text.muted }}> · {enemy.distance} ft</span>
                  )}
                </GameText>
                {/* The stage label carries its own meaning ("Preparing" vs
                    "Cooling down from"), so an already-resolved move still
                    earns a line — it just loses the category color that marks
                    live intent, and the countdown. */}
                {move && (
                  <GameText size="xs" style={{ marginTop: spacing.xs, color: moveColor || colors.text.muted }}>
                    ◆ {formatCombatMoveStatus(move)}
                    {category && <span style={{ opacity: 0.6 }}> ({category})</span>}
                    {beatsToResolve !== null && (
                      <span style={{ opacity: 0.85 }}> — resolves {formatBeatCountdown(beatsToResolve)}</span>
                    )}
                  </GameText>
                )}
              </div>
              <StatusEffectsIconPanel effects={enemy.status_effects} />
            </div>
            <div className="hp-bar" style={{ marginTop: spacing.xs }}>
              <div
                style={{
                  height: '100%',
                  background: `linear-gradient(to right, ${colors.danger}, ${colors.secondary})`,
                  width: `${hpPercent}%`
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
// EntityTooltip — hover card above a combatant token
// ---------------------------------------------------------------------------
const EntityTooltip = React.memo(({ entity, showDistance }) => {
  const { hp, maxHp } = resolveEntityStats(entity);
  return (
    <div className="absolute top-full left-1/2 -translate-x-1/2 mt-4 z-[100] animate-in fade-in slide-in-from-top-2 duration-200 pointer-events-none">
      <div className="bg-black/90 border border-orange/40 rounded px-2 py-1 shadow-2xl backdrop-blur-md min-w-[120px]">
        <div className="text-white text-[10px] font-bold uppercase tracking-wider border-b border-white/10 pb-1 mb-1">
          {entity.name}
        </div>
        {/* Distance is what the positional layer turns on — every move carries
            an mvrange and ranged accuracy decays with it — so it belongs on
            the hover card. */}
        <div className="text-white/70 text-[9px] font-mono flex justify-between gap-3">
          <span>{hp}/{maxHp} HP</span>
          {showDistance && entity.distance !== undefined && <span>{entity.distance} ft</span>}
        </div>
        <div className="text-orange/80 text-[9px] flex justify-between gap-2">
          <span className="font-mono">
            {formatCombatMoveStatus(entity.current_move) || 'Idle'}
          </span>
        </div>
        {/* What the token stands on (src.terrain.standing_on). Only shown
            for ground that changes something -- open floor says nothing. */}
        {entity.terrain?.label && entity.terrain.kind !== 'open' && (
          <div className="text-white/60 text-[9px] font-mono" data-testid="tooltip-terrain">
            on {entity.terrain.label}
          </div>
        )}
      </div>
      {/* Arrow */}
      <div className="w-0 h-0 border-l-[6px] border-r-[6px] border-b-[6px] border-l-transparent border-r-transparent border-b-black/90 absolute left-1/2 -translate-x-1/2 bottom-full" />
    </div>
  );
});

// ---------------------------------------------------------------------------
// EntityLayer — renders all live combatants with interactions and animations
// ---------------------------------------------------------------------------
const EntityLayer = React.memo(({
  entitiesToRender,
  activeAnimations,
  hoveredEntity,
  selectedEntity,
  hoveredTargetId,
  isCompact,
  onHoverEntity,
  onClearHover,
  onSelectEntity,
  spriteManifest = null,
  combatSpeed = 1,
}) => (
  <div style={{ position: 'absolute', inset: 0, padding: spacing.sm, pointerEvents: 'none' }}>
    {entitiesToRender.map((item, idx) => {
      const entityId = item.entity.id;
      const sprite = spriteFor(spriteManifest, item.entity.sprite_key);
      const spriteClip = sprite
        ? spriteClipFor({
          animationStates: collectAnimationStates(activeAnimations, entityId),
          isDying: item.isDying,
          currentMove: item.entity.current_move,
        })
        : 'idle';
      const isEntityHovered = hoveredEntity != null && (
        entityId != null ? hoveredEntity.id === entityId : hoveredEntity === item.entity
      );

      // Derive per-entity animation state — ALL of them, see collectAnimationStates
      const animStates = collectAnimationStates(activeAnimations, entityId);

      // Config-driven source motion: recoil away from the target on windup,
      // travel toward it on the strike/rush phase, hold there through impact
      // so the hit connects visually, then ease back on return. Spin motions
      // rotate in place instead of travelling.
      //
      // A token has ONE position, so only one layer may drive it: the lead of
      // the swing, tagged in playAnimations. Selecting "the first source layer
      // still in flight" instead looks equivalent and is not -- the lead is
      // removed from activeAnimations the moment its phases end, after which a
      // follower aimed at a different cell inherits the token and the marker
      // snaps toward the new target mid-arc.
      let transformStyle = {};
      const motionState = animStates.find(
        (s) => s.isSource && s.anim.config?.motion && s.anim.isLead
      );
      if (motionState) {
        const { config: cfg, phase } = motionState.anim;
        const motion = cfg.motion;
        const targetId = motionState.anim.target_id;
        const targetItem = targetId
          ? entitiesToRender.find((e) => e.entity.id === targetId)
          : null;
        const sPos = getPos(item.entity);
        const tPos = targetItem ? getPos(targetItem.entity) : null;
        // Cell deltas in screen space (y axis inverted vs world coords)
        const dx = tPos ? tPos.x - sPos.x : 0;
        const dy = tPos ? sPos.y - tPos.y : 0;
        const travel = motion.travel || 0;
        const rotate = motion.spinDegrees ? ` rotate(${motion.spinDegrees}deg)` : '';

        if (phase === motion.windupPhase && motion.recoil) {
          // Recoil directly away from the target; small upward coil when untargeted
          const len = Math.hypot(dx, dy) || 1;
          transformStyle = {
            transform: tPos
              ? `translate(${(-dx / len) * motion.recoil * 100}%, ${(-dy / len) * motion.recoil * 100}%)`
              : `translate(0, -${motion.recoil * 60}%)`,
            transition: `transform ${phaseDurationOf(cfg, phase)}ms ease-out`,
            zIndex: 100,
          };
        } else if (phase === motion.travelPhase) {
          transformStyle = {
            transform: `translate(${dx * travel * 100}%, ${dy * travel * 100}%)${rotate}`,
            transition: `transform ${phaseDurationOf(cfg, phase)}ms ${motion.easing || 'ease-in'}`,
            zIndex: 100,
          };
        } else if (phase === 'impact' && travel && tPos) {
          // Hold at the target through impact — no snap-back mid-hit
          transformStyle = {
            transform: `translate(${dx * travel * 100}%, ${dy * travel * 100}%)${rotate}`,
            zIndex: 100,
          };
        } else if (phase === 'return') {
          transformStyle = {
            transform: 'translate(0, 0) rotate(0deg)',
            transition: `transform ${phaseDurationOf(cfg, 'return')}ms ease-in-out`,
          };
        }
      }

      const isHighlighted = isEntityHovered || (entityId != null && selectedEntity?.id === entityId);

      return (
        <div
          key={`${entityId ?? idx}-${item.isFriendly ? 'friend' : 'enemy'}`}
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
            // The animating token must lift above the one it is striking.
            // This has to live on the wrapper: it is absolutely positioned
            // with a numeric z-index, so it forms a stacking context and any
            // z-index set on the inner motion div is scoped inside it.
            zIndex: animStates.length ? 100 : (isHighlighted ? 50 : (item.style.zIndex || 20))
          }}
        >
          <div style={{
            width: '100%',
            height: '100%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1,
            ...transformStyle
          }}>
            <CombatantMarker
              entity={item.entity}
              isFriendly={item.isFriendly}
              isHero={item.isHero}
              isCompact={isCompact}
              isHovered={(entityId != null && hoveredTargetId === entityId) || isEntityHovered}
              isSelected={entityId != null && selectedEntity?.id === entityId}
              animationStates={animStates}
              displaySymbol={item.displaySymbol}
              sprite={sprite}
              spriteClip={spriteClip}
              spriteRows={spriteManifest?.facings}
              combatSpeed={combatSpeed}
            />
          </div>

          {/* Hover tooltip, suppressed only for the entity already open in
              the selection panel. Suppressing on any selection would blind
              the player to every other token on the field. */}
          {isEntityHovered && selectedEntity?.id !== entityId && (
            <EntityTooltip entity={item.entity} showDistance={!item.isHero} />
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
  // resolveEntityStats is the single derivation of these five values.
  const { hp, maxHp, fatigue, maxFatigue, hpPct: hpFrac, fatPct } = resolveEntityStats(entity);
  const hpPct = hpFrac * 100;
  const fatiguePct = fatPct * 100;

  return (
    <div
      className="absolute top-4 right-4 z-[150] w-[200px] animate-in slide-in-from-right-4 fade-in duration-300 pointer-events-auto"
      onClick={(e) => e.stopPropagation()}
    >
      <div className="bg-black/95 border-2 border-orange/50 rounded-lg p-3 shadow-2xl backdrop-blur-xl">
        {/* Header */}
        <div className="flex justify-between items-start mb-3 border-b border-white/10 pb-2">
          <div>
            <GameText weight="bold" size="sm" variant="secondary">{entity.name}</GameText>
            {entity.distance !== undefined && (
              <div className="text-white/50 text-[10px] font-mono mt-0.5">{entity.distance} ft away</div>
            )}
          </div>
          <button
            onClick={onClose}
            className="text-white/40 hover:text-white transition-colors"
            title="Close (Esc or click map background)"
            aria-label="Close selected entity panel"
          >
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
              <span className="text-orange-400 font-mono">{fatigue}/{maxFatigue}</span>
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

          {/* Move in progress */}
          <div className="pt-2 border-t border-white/10">
            <div className="text-[10px] text-white/60 mb-1">MOVE IN PROGRESS</div>
            <div className="text-orange text-xs font-bold">
              {formatCombatMoveStatus(entity.current_move) || 'Idle'}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
});

// ---------------------------------------------------------------------------
// TravelDot — a glowing dot that streaks from one cell to another. Used for
// projectiles (source → target) and drain streams (target → source, staggered).
// ---------------------------------------------------------------------------
const TravelDot = ({ fromStyle, toStyle, color, duration, delay = 0, size = 1 }) => {
  const [launched, setLaunched] = useState(false);

  // Double-RAF so the browser paints the dot at its origin before the
  // transition to the destination begins.
  useDoubleRaf(useCallback(() => setLaunched(true), []));

  // Extract the cell translations; the dot interpolates between them.
  const style = launched ? toStyle : fromStyle;
  return (
    <div
      style={{
        position: 'absolute',
        left: 0,
        top: 0,
        width: fromStyle.width,
        height: fromStyle.height,
        transform: style.transform,
        transition: launched ? `transform ${duration}ms linear ${delay}ms` : 'none',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        pointerEvents: 'none',
        opacity: launched ? 1 : 0,
      }}
    >
      <div
        style={{
          width: `${18 * size}%`,
          height: `${18 * size}%`,
          borderRadius: '50%',
          backgroundColor: color,
          boxShadow: `0 0 8px 3px ${color}`,
        }}
      />
    </div>
  );
};

// ---------------------------------------------------------------------------
// EffectsLayer — transient overlay visuals driven by the active animation's
// config.effect: projectile streaks, expanding shockwave rings, rising buff
// particles, and drain streams. Rendered only during the effect's phase.
// ---------------------------------------------------------------------------
const EffectsLayer = React.memo(({ activeAnimations, getEntityStyle, combat }) => {
  // Deliberately not the parent's `allCombatants` memo. Two reasons, both
  // load-bearing: EffectsLayer is a separate React.memo component and cannot
  // see that memo without prop-drilling it, and this lookup accepts the
  // literal sentinel 'player' as an id — animation payloads use it for the
  // source/target of player-originated effects — which a plain id lookup
  // would not resolve. The id→entity map turns the per-overlay pool scans
  // into O(1) lookups (a 12-layer batch does 24 of them per render).
  const entityById = useMemo(() => {
    const map = new Map();
    for (const pool of [[combat?.player], combat?.allies, combat?.enemies]) {
      for (const entity of pool || []) {
        if (entity?.id != null) map.set(entity.id, entity);
      }
    }
    return map;
  }, [combat?.player, combat?.allies, combat?.enemies]);

  const findEntity = (id) => {
    if (!id || !combat) return null;
    if (id === 'player') return combat.player || null;
    return entityById.get(id) || null;
  };

  // One overlay per animation currently inside its effect phase. This rendered
  // exactly one effect for one active animation; a four-target arc now has four
  // landings in flight, each entitled to its own ring/streak on its own cell.
  const renderEffect = (anim) => {
    const cfg = anim?.config;
    const effect = cfg?.effect;
    if (!effect || anim?.phase !== effect.phase) return null;

    const duration = phaseDurationOf(cfg, effect.phase, 300);
    const source = findEntity(anim.source_id);
    const target = findEntity(anim.target_id);
    const sourceStyle = source ? getEntityStyle(getPos(source), 140) : null;
    const targetStyle = target ? getEntityStyle(getPos(target), 140) : null;

    let content = null;
    switch (effect.kind) {
      case 'projectile': {
        if (!sourceStyle || !targetStyle) break;
        content = (
          <TravelDot
            fromStyle={sourceStyle}
            toStyle={targetStyle}
            color={effect.color}
            duration={duration}
          />
        );
        break;
      }
      case 'drain': {
        if (!sourceStyle || !targetStyle) break;
        // Three staggered motes flowing target → source
        content = [0, 1, 2].map((i) => (
          <TravelDot
            key={i}
            fromStyle={targetStyle}
            toStyle={sourceStyle}
            color={effect.color}
            duration={Math.max(120, duration - i * 120)}
            delay={i * 120}
            size={0.7}
          />
        ));
        break;
      }
      case 'ring': {
        // The effect config declares which cell the ring sits on: 'target' for
        // impact rings, caster (default) for sweep arcs / defensive shells /
        // shockwaves radiating outward.
        const anchor = (effect.anchor === 'target' && targetStyle) ? targetStyle : sourceStyle;
        if (!anchor) break;
        content = (
          <div
            style={{
              position: 'absolute',
              ...anchor,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              pointerEvents: 'none',
            }}
          >
            <div
              className="battlefield-effect-ring"
              style={{
                width: '90%',
                height: '90%',
                border: `3px solid ${effect.color}`,
                boxShadow: `0 0 12px 2px ${effect.color}`,
                ['--bf-ring-scale']: (effect.size || 1) * 2.6,
                animationDuration: `${duration}ms`,
              }}
            />
          </div>
        );
        break;
      }
      case 'rise': {
        if (!sourceStyle) break;
        // Sparks climbing off the caster — offsets in % of the cell
        content = (
          <div
            style={{
              position: 'absolute',
              ...sourceStyle,
              pointerEvents: 'none',
            }}
          >
            {[{ left: '25%', d: 0 }, { left: '50%', d: 120 }, { left: '70%', d: 60 }].map((p, i) => (
              <div
                key={i}
                className="battlefield-effect-rise"
                style={{
                  position: 'absolute',
                  left: p.left,
                  bottom: '20%',
                  width: '12%',
                  height: '12%',
                  borderRadius: '50%',
                  backgroundColor: effect.color,
                  boxShadow: `0 0 6px 2px ${effect.color}`,
                  animationDuration: `${Math.max(200, duration - p.d)}ms`,
                  animationDelay: `${p.d}ms`,
                }}
              />
            ))}
          </div>
        );
        break;
      }
      default:
        break;
    }

    if (!content) return null;
    return (
      <div
        key={anim.animId}
        style={{ position: 'absolute', inset: 0, padding: spacing.sm, pointerEvents: 'none', zIndex: 140 }}
      >
        {content}
      </div>
    );
  };

  const overlays = (activeAnimations || []).map(renderEffect).filter(Boolean);
  return overlays.length ? overlays : null;
});

// ---------------------------------------------------------------------------
// DeathBurst — fragment particle explosion rendered at a dying entity's cell
// ---------------------------------------------------------------------------
const DeathBurst = () => {
  const [phase, setPhase] = useState(0); // 0=hidden, 1=burst, 2=fade

  useDoubleRaf(useCallback(() => setPhase(1), []));

  useEffect(() => {
    const fadeTimer = setTimeout(() => setPhase(2), 350);
    return () => clearTimeout(fadeTimer);
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
// JeanSpotlight — pulsing ring overlaid on Jean's cell whenever tokens are
// compact (see `isCompact`), so the player can still locate her when they are
// too small to read.
// ---------------------------------------------------------------------------
const JeanSpotlight = React.memo(({ player, getEntityStyle }) => {
  const pos = getPos(player);
  const style = getEntityStyle(pos, 40);
  if (!style) return null;
  return (
    <div style={{ position: 'absolute', inset: 0, padding: spacing.sm, pointerEvents: 'none' }}>
      <div
        style={{
          position: 'absolute',
          ...style,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
        }}
      >
        <div
          className="battlefield-jean-spotlight"
          style={{ width: '220%', height: '220%' }}
        />
      </div>
    </div>
  );
});

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
// OffScreenMarkers — edge chevrons pointing at living enemies outside the
// viewport. Ranged moves reach 40–50 ft while follow mode shows 13 cells, so
// a fight can legitimately be happening entirely off-screen; these chevrons
// carry where the enemies are and how many.
// ---------------------------------------------------------------------------
const MAX_OFFSCREEN_MARKERS = 6;

const OffScreenMarkers = React.memo(({ enemies, leftX, topY, gridCols }) => {
  const markers = useMemo(() => {
    // Viewport center in world coordinates.
    const cx = leftX + (gridCols - 1) / 2;
    const cy = topY - (gridCols - 1) / 2;
    const out = [];
    for (const enemy of enemies) {
      const pos = enemy.position;
      if (!pos) continue;
      const onScreen = pos.x >= leftX && pos.x < leftX + gridCols
        && pos.y <= topY && pos.y > topY - gridCols;
      if (onScreen) continue;

      const dx = pos.x - cx;
      const dy = pos.y - cy;
      const len = Math.hypot(dx, dy) || 1;
      const nx = dx / len;
      const ny = dy / len;
      // Project onto the edge of the inset box: dividing by the dominant axis
      // puts the marker on whichever border the enemy actually lies beyond.
      const k = 0.44 / Math.max(Math.abs(nx), Math.abs(ny));
      out.push({
        id: enemy.id ?? `${enemy.name}-${pos.x}-${pos.y}`,
        name: enemy.name,
        // Screen y grows downward, world y grows upward.
        left: `${50 + nx * k * 100}%`,
        top: `${50 - ny * k * 100}%`,
        // 0deg = pointing up (north); atan2(dx, dy) turns clockwise from north.
        angle: (Math.atan2(dx, dy) * 180) / Math.PI,
        distance: enemy.distance,
        // Nearest-first, so a capped list keeps the enemies that matter most.
        // `distance` is feet from Jean and `len` is cells from the viewport
        // center — different origins, but a grid cell is ~1 ft
        // (src/positions.py distance_from_coords), so they rank together
        // closely enough for a tie-break over which few markers to draw.
        sortKey: enemy.distance ?? len,
      });
    }
    out.sort((a, b) => a.sortKey - b.sortKey);
    return out.slice(0, MAX_OFFSCREEN_MARKERS);
  }, [enemies, leftX, topY, gridCols]);

  if (markers.length === 0) return null;

  return (
    <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 145 }}>
      {markers.map((m) => (
        <div
          key={m.id}
          style={{
            position: 'absolute',
            left: m.left,
            top: m.top,
            transform: 'translate(-50%, -50%)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '1px',
          }}
          title={`${m.name}${m.distance !== undefined ? ` — ${m.distance} ft` : ''} (off-screen)`}
          aria-label={`${m.name} off-screen${m.distance !== undefined ? `, ${m.distance} feet away` : ''}`}
        >
          <div
            style={{
              width: 0,
              height: 0,
              borderLeft: '5px solid transparent',
              borderRight: '5px solid transparent',
              borderBottom: `9px solid ${colors.danger}`,
              transform: `rotate(${m.angle}deg)`,
              filter: 'drop-shadow(0 0 3px rgba(0,0,0,0.9))',
            }}
          />
          {m.distance !== undefined && (
            <span
              style={{
                fontSize: '8px',
                fontFamily: 'monospace',
                color: colors.danger,
                backgroundColor: 'rgba(0,0,0,0.75)',
                borderRadius: '2px',
                padding: '0 2px',
                lineHeight: 1.3,
                whiteSpace: 'nowrap',
              }}
            >
              {m.distance}ft
            </span>
          )}
        </div>
      ))}
    </div>
  );
});

// ---------------------------------------------------------------------------
// ThreatLineLayer — a line from each combatant with a pending move to that
// move's target, so intent gets a *who* to go with the existing beat-
// countdown badge's *when*. Only drawn when both ends are actually on screen
// (entitiesToRender already excludes anything getEntityStyle couldn't place).
// Enemy-on-Jean lines are the ones the player has to react to, so they render
// thicker and brighter; everything else stays subdued so the field doesn't
// turn into a thicket of lines. Rendered below EntityLayer so a line never
// sits on top of a token.
// ---------------------------------------------------------------------------
const ThreatLineLayer = React.memo(({ entitiesToRender, getEntityCenterPct }) => {
  const lines = useMemo(() => {
    const itemById = new Map();
    for (const item of entitiesToRender) {
      if (item.entity.id != null) itemById.set(item.entity.id, item);
    }

    const result = [];
    for (const item of entitiesToRender) {
      if (item.isDying) continue;
      const source = item.entity;
      const move = source.current_move;
      if (!isMovePending(move)) continue;
      const targetId = move.target_id;
      if (!targetId || targetId === source.id) continue; // untargeted / self-target

      const targetItem = itemById.get(targetId);
      // Absent = off-screen or already gone. `isDying` is the third case the
      // map cannot express: the target is still in entitiesToRender for its
      // 0.65s fade, and a threat line drawn onto a corpse reads as live intent.
      if (!targetItem || targetItem.isDying) continue;

      const from = getEntityCenterPct(getPos(source));
      const to = getEntityCenterPct(getPos(targetItem.entity));
      if (!from || !to) continue;

      // The lines the player has to react to: an enemy aimed at Jean.
      // `isHero` is set only for combat.player, and `isFriendly` covers the
      // whole friendly side — so this is "an enemy, targeting Jean".
      const dominant = targetItem.isHero && !item.isFriendly;
      result.push({
        id: `${source.id}->${targetId}`,
        sourceId: source.id,
        targetId,
        x1: from.xPct, y1: from.yPct,
        x2: to.xPct, y2: to.yPct,
        color: categoryColor(move.category),
        dominant,
      });
    }
    return result;
  }, [entitiesToRender, getEntityCenterPct]);

  if (lines.length === 0) return null;

  return (
    <div style={{ position: 'absolute', inset: 0, padding: spacing.sm, pointerEvents: 'none', zIndex: 6 }}>
      <svg
        width="100%" height="100%"
        viewBox="0 0 100 100"
        preserveAspectRatio="none"
        style={{ overflow: 'visible' }}
        aria-hidden="true"
      >
        {lines.map((line) => (
          <line
            key={line.id}
            data-testid="threat-line"
            data-source-id={line.sourceId}
            data-target-id={line.targetId}
            data-dominant={line.dominant ? 'true' : 'false'}
            x1={line.x1} y1={line.y1} x2={line.x2} y2={line.y2}
            stroke={line.color}
            strokeWidth={line.dominant ? 2.5 : 1}
            strokeOpacity={line.dominant ? 0.9 : 0.32}
            strokeDasharray={line.dominant ? undefined : '4 3'}
            strokeLinecap="round"
            vectorEffect="non-scaling-stroke"
          />
        ))}
      </svg>
    </div>
  );
});

// ---------------------------------------------------------------------------
// RangeRingLayer — what the selected combatant's move threatens.
//
// Two shapes, because the engine has two kinds of reach:
//
//   Bounded move (no falloff): a hard edge at mvrange.max. A crisp ring is
//   honest — inside is in range, outside is not.
//
//   Decaying move (falloff present): reach is *unbounded*. A bow can be fired
//   at any distance; accuracy simply bleeds away at `per_ft` hit-chance points
//   for every foot past `start`, down to the engine's 2% floor. Drawing a ring
//   at mvrange.max would invent a wall that does not exist. It renders instead
//   as a disc that is solid out to `start` — the plateau where accuracy is
//   untouched — and then dissolves outward, reaching transparent exactly where
//   the falloff would have eaten a full 100 points. The gradient IS the hit
//   chance: how solid the fill is at a given radius is how likely the shot is.
//
// Anchored like JeanSpotlight: a getEntityStyle cell rect flex-centers a
// percentage-sized element, so both shapes inherit camera/pan/fit position.
// ---------------------------------------------------------------------------

// Fill alpha at full accuracy. The gradient's outer stop is this scaled by the
// accuracy actually remaining there, so the fill's density is a direct readout
// of hit chance rather than a decorative fade.
// Kept low deliberately: this fill can cover the entire viewport. It sits
// under the tokens (z 20+) and over the breadcrumb (z 5) and threat-line
// (z 6) layers, so it must not compete with either.
const FALLOFF_CORE_ALPHA = 0.12;
// Radius percentage at which the fill stops encoding retention and starts
// feathering out, so the disc has no hard rim.
const FALLOFF_EDGE_FEATHER_PCT = 88;
// Ceiling on the plateau's share of the drawn radius. It is the feather stop,
// not a round number: a plateau past that point would emit gradient stops in
// descending order (`… plateau%, 88%, 100%`), which CSS resolves by clamping
// the later stop up — collapsing the feather span and giving the disc the hard
// rim this whole treatment exists to avoid.
const MAX_PLATEAU_FRACTION = FALLOFF_EDGE_FEATHER_PCT / 100;

/** `#rrggbb` + a 0-1 alpha as the two-digit hex suffix the theme uses. */
const withAlpha = (hex, alpha) => {
  // Non-finite would survive the clamp and produce `#rrggbbNaN`, a 9-digit
  // colour that invalidates the whole gradient declaration.
  if (!Number.isFinite(alpha)) return `${hex}00`;
  const clamped = Math.round(Math.min(1, Math.max(0, alpha)) * 255);
  return `${hex}${clamped.toString(16).padStart(2, '0')}`;
};

const RangeRingLayer = React.memo(({ entity, getEntityStyle, gridCols }) => {
  const move = entity?.current_move;
  const maxRange = move?.mvrange?.max;
  if (!entity || !Number.isFinite(maxRange) || maxRange <= 0) return null;
  // Gate on pending like every other telegraph: move_in_progress hands back
  // recoil/cooldown moves by design (src/combatant.py), and a spent move must
  // not draw a live threat radius.
  if (!isMovePending(move)) return null;

  const style = getEntityStyle(getPos(entity), 15);
  if (!style) return null; // selected entity currently off screen

  const falloff = move.falloff;
  const decays = falloff && Number.isFinite(falloff.start) && falloff.per_ft > 0
    && Number.isFinite(falloff.per_ft);

  if (!decays) {
    const diameterCells = maxRange * 2;
    // A hard ring wider than the viewport reads as an edge-to-edge wash rather
    // than a legible "here's the threat radius" cue, so it is suppressed
    // instead of drawn illegibly large. A decaying move has no such edge to
    // miss, which is why the gradient below is not subject to this.
    if (diameterCells > gridCols) return null;
    return (
      <div style={{ position: 'absolute', inset: 0, padding: spacing.sm, pointerEvents: 'none' }}>
        <div style={{ position: 'absolute', ...style, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <div
            data-testid="range-ring"
            data-shape="ring"
            style={{
              width: `${diameterCells * 100}%`,
              height: `${diameterCells * 100}%`,
              borderRadius: '50%',
              border: `1px solid ${colors.gold}`,
              opacity: 0.35,
            }}
          />
        </div>
      </div>
    );
  }

  // The decay is gradual relative to arena size: a bow plateaus to ~20 ft and
  // then sheds 0.05 points/ft, while an arena is 9-100 cells across (~1 ft per
  // cell). Sizing the element to mvrange.max (2020 ft => 4040 cells) would put
  // the entire viewport inside the plateau — a flat wash with no visible
  // gradient and no information. So the indicator is drawn at *viewport*
  // scale, and is suppressed outright when the whole visible field is at full
  // accuracy, because then there is genuinely nothing to depict.
  const visibleRadiusCells = gridCols / 2;
  if (falloff.start >= visibleRadiusCells) return null;

  // The drawn extent is the circle inscribed in the viewport: large enough to
  // cover the field the player is looking at, small enough that its edge — and
  // so the outer ring drawn on it — stays on screen.
  const drawRadius = Math.min(maxRange, visibleRadiusCells);
  const plateauFraction = Math.min(MAX_PLATEAU_FRACTION, Math.max(0, falloff.start / drawRadius));
  // Remaining hit chance at the drawn edge, as a fraction of a full 100
  // points. This is the engine's own linear decay, so the alpha at any radius
  // really is how likely the shot is at that distance.
  const edgeRetention = Math.max(0, 1 - ((drawRadius - falloff.start) * falloff.per_ft) / 100);
  const diameterCells = drawRadius * 2;

  return (
    <div style={{ position: 'absolute', inset: 0, padding: spacing.sm, pointerEvents: 'none' }}>
      <div style={{ position: 'absolute', ...style, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <div
          data-testid="range-ring"
          data-shape="falloff"
          style={{
            width: `${diameterCells * 100}%`,
            height: `${diameterCells * 100}%`,
            borderRadius: '50%',
            // Solid to the plateau edge, then a linear bleed to whatever
            // accuracy is actually left at the drawn edge: the outer stop is
            // the core alpha scaled by real retention.
            // With current engine constants a bow sheds under 3 points across
            // anything the player can see, so this is deliberately a near-flat
            // tint: a strong visible dissolve would overstate the decay by an
            // order of magnitude, which is worse than showing nothing.
            // The last stop is a feather to nothing over the outermost few
            // percent. That is a *drawing* boundary, not an accuracy claim —
            // it stops the disc from ending in a hard circle that would read
            // as the very wall this whole treatment exists to deny. The
            // informative span (centre to FALLOFF_EDGE_FEATHER_PCT) is where
            // alpha tracks retention.
            // closest-side, not the default farthest-corner: it puts the
            // gradient's 100% exactly on the box edge, which is where the
            // SVG rings' r=50 lands. With the default the stops sat at the
            // half-diagonal and the rings never agreed with the fill.
            background: `radial-gradient(closest-side, `
              + `${withAlpha(colors.secondary, FALLOFF_CORE_ALPHA)} 0%, `
              + `${withAlpha(colors.secondary, FALLOFF_CORE_ALPHA)} ${(plateauFraction * 100).toFixed(2)}%, `
              + `${withAlpha(colors.secondary, FALLOFF_CORE_ALPHA * edgeRetention)} ${FALLOFF_EDGE_FEATHER_PCT}%, `
              + `${withAlpha(colors.secondary, 0)} 100%)`,
          }}
        />
        {/* Two dashed rings, drawn as SVG because CSS `border-style: dashed`
            gives no control over dash length or gap — and the gap is the whole
            point here. The inner ring is tightly dashed: a real transition,
            the last distance at full accuracy. The outer one is drawn with
            long gaps between short dashes, so it reads as a boundary that is
            porous rather than a wall — the shot carries on past it, just less
            and less reliably. Together they say "solid to here, thinning out
            to there, and still going" in a way a single ring cannot.

            The outer ring marks the edge of the drawn falloff, not a range
            limit — there isn't one. Its sparseness is doing the talking; the
            plateau ring is the one carrying an actual number. */}
        <svg
          style={{
            position: 'absolute',
            width: `${diameterCells * 100}%`,
            height: `${diameterCells * 100}%`,
            overflow: 'visible',
          }}
          viewBox="0 0 100 100"
          // Without this the rings render as true circles (xMidYMid meet)
          // while the fill beside them is an ellipse whenever cells are not
          // square — which is the default, squareBattlefieldCells being off.
          preserveAspectRatio="none"
          aria-hidden="true"
        >
          {/* non-scaling-stroke keeps stroke width AND the dash pattern in
              screen pixels; without it both would be multiplied by the
              element's scale (up to ~20x a cell) and the dashes would smear
              into a solid line. */}
          <circle
            data-testid="range-plateau"
            cx="50" cy="50" r={plateauFraction * 50}
            fill="none"
            stroke={colors.secondary}
            strokeWidth="1"
            strokeDasharray="4 3"
            vectorEffect="non-scaling-stroke"
            opacity="0.45"
          />
          <circle
            data-testid="range-outer"
            cx="50" cy="50" r="49"
            fill="none"
            stroke={colors.secondary}
            strokeWidth="1"
            strokeDasharray="2 14"
            vectorEffect="non-scaling-stroke"
            opacity="0.3"
          />
        </svg>
      </div>
    </div>
  );
});

// ---------------------------------------------------------------------------
// GridBackgroundLayer — the cell lattice, with off-map cells dimmed.
//
// Its own memoized component, not an array mapped inline in the render body.
// Both props are stable across poll/phase/hover/selection renders, so the
// shallow compare skips reconciling up to gridCols^2 keyed children (~2,300 in
// a mid-size fit-mode fight) on every one of the ~15 renders per beat.
//
// Keep it a component rather than a memoized array: reconcileChildrenArray
// still walks and clones every child fiber even when each one bails.
// ---------------------------------------------------------------------------
// The lattice every cell-aligned layer shares: one CSS grid of gridCols^2
// equal cells over the viewport box.
const latticeGridStyle = (gridCols) => ({
  position: 'absolute', inset: 0,
  display: 'grid', gap: '1px', padding: spacing.sm,
  gridTemplateColumns: `repeat(${gridCols}, minmax(0, 1fr))`,
  gridTemplateRows: `repeat(${gridCols}, minmax(0, 1fr))`,
  pointerEvents: 'none',
});

const GridBackgroundLayer = React.memo(({ cells, gridCols }) => (
  <div style={latticeGridStyle(gridCols)}>
    {cells.map((onMap, i) => (
      <div
        key={i}
        style={{
          backgroundColor: onMap ? 'rgba(255,255,255,0.03)' : 'rgba(0,0,0,0.35)',
          borderRadius: '2px'
        }}
      />
    ))}
  </div>
));

// ---------------------------------------------------------------------------
// TerrainLayer — per-cell terrain under the tokens
// ---------------------------------------------------------------------------
// Same memo discipline as GridBackgroundLayer, but only feature cells are
// rendered, each placed explicitly on the lattice (open ground paints
// nothing until a floor tile exists), so the node count follows the number
// of features rather than gridCols^2. Feature cells carry a native `title`
// so hovering a boulder or a slime pool names it; they take pointer events
// for that alone -- clicks bubble to the grid's own handler unchanged, and
// the drag pan listens on the window, so neither gesture is affected.
//
// Elevation is drawn as a lit top-left rim on raised cells so a shelf reads
// as "up" even before the tileset art lands. Delivered tile art replaces the
// procedural fill; the rim stays either way.
const terrainCellStyle = (cell, isCompact) => {
  const style = TERRAIN_STYLE[cell.kind];
  const tiled = Boolean(cell.tile);
  return {
    gridColumnStart: cell.col + 1,
    gridRowStart: cell.row + 1,
    backgroundColor: tiled ? 'transparent' : style.fill,
    backgroundImage: tiled ? `url("${cell.tile}")` : undefined,
    backgroundSize: tiled ? 'cover' : undefined,
    imageRendering: tiled ? 'pixelated' : undefined,
    borderRadius: tiled ? '2px' : style.radius,
    boxShadow: cell.elevation > 0 ? ELEVATION_RIM_SHADOW : 'none',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    color: style.glyphColor,
    fontSize: isCompact ? '6px' : '11px',
    lineHeight: 1,
    userSelect: 'none',
    pointerEvents: cell.kind === 'open' ? 'none' : 'auto',
  };
};

const TerrainLayer = React.memo(({ cells, gridCols, isCompact }) => (
  <div data-testid="terrain-layer" style={{ ...latticeGridStyle(gridCols), zIndex: 1 }}>
    {cells.map((cell) => (
      <div
        key={cell.index}
        data-terrain={cell.kind}
        data-variant={cell.variant}
        data-tiled={cell.tile ? '1' : undefined}
        title={cell.title}
        style={terrainCellStyle(cell, isCompact)}
      >
        {(isCompact || cell.tile) ? '' : TERRAIN_STYLE[cell.kind].glyph}
      </div>
    ))}
  </div>
));
TerrainLayer.displayName = 'TerrainLayer';

// ---------------------------------------------------------------------------
// TerrainLegend — which kinds are on this field and what they do
// ---------------------------------------------------------------------------
// Pinned top-left on a translucent plate (the off-screen banner sits centred
// above it and the edge markers can reach this corner) and kept narrow so
// neither overdraws it for long.
const TerrainLegend = React.memo(({ terrain }) => {
  const kinds = useMemo(() => terrainKindsPresent(terrain), [terrain]);
  if (kinds.length === 0) return null;
  return (
    <div
      data-testid="terrain-legend"
      aria-label="Terrain legend"
      style={{
        position: 'absolute', top: '6px', left: '8px', zIndex: 140,
        pointerEvents: 'none', display: 'flex', flexWrap: 'wrap', gap: '4px 8px',
        fontSize: '9px', fontFamily: 'monospace', color: 'rgba(255,255,255,0.65)',
        userSelect: 'none', maxWidth: '45%', padding: '3px 6px', borderRadius: '3px',
        backgroundColor: 'rgba(0,0,0,0.55)',
      }}
    >
      <span style={{ color: colors.secondary, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        {regionLabel(terrain)}
      </span>
      {kinds.map((kind) => {
        const style = TERRAIN_STYLE[kind];
        const notes = legendNotes(terrain, kind);
        return (
          <span key={kind} style={{ display: 'inline-flex', alignItems: 'center', gap: '3px' }}>
            <span style={{
              display: 'inline-block', width: '8px', height: '8px', borderRadius: '2px',
              backgroundColor: style.fill,
              boxShadow: RAISED_KINDS.includes(kind) ? ELEVATION_RIM_SHADOW : 'none',
            }} />
            <span>{terrainLabel(terrain, kind)}{notes.length ? ` (${notes.join(', ')})` : ''}</span>
          </span>
        );
      })}
    </div>
  );
});
TerrainLegend.displayName = 'TerrainLegend';

// ---------------------------------------------------------------------------
// BattlefieldGrid — main exported component
// ---------------------------------------------------------------------------
function BattlefieldGrid({
  combat,
  allBeatStates,
  currentBeatIndex,
  combatLog,
  // Fight identity, supplied by Battlefield from the top-level combat object.
  // `combat` below is a beat state and carries neither.
  combatId = null,
  combatActive = false,
  tab,
  zoom = 1,
  displayedLogCount = 0,
  hoveredTargetId = null,
  mapSize = null,
  // battle_state.terrain (src/terrain.py TerrainGrid.to_payload), forwarded
  // by Battlefield exactly like mapSize: the grid is handed a BEAT state,
  // which never carries it. Null in a terrain-free fight.
  terrain = null,
  onAnimatingChange = null,
  // Engine-driven combat streaming (issue #436). When `streaming` is true the
  // log-spooler animation path is bypassed: pre-built animations arrive via
  // `streamedAnimations` (each may carry the source `beat` so its 75% SFX chain
  // fires at animation start, or `suppressSfx` to stay silent). `combatSpeed`
  // scales SFX timing (issue #460). Off by default — production is unchanged.
  streaming = false,
  streamedAnimations = [],
  combatSpeed = 1,
}) {
  /**
   * @typedef {Object} AnimationLayer
   * One queued or in-flight animation layer. Field groups, by origin:
   *  - strike payload (log carrier or stream): `type`, `source_id`,
   *    `target_id`, `outcome`, `swing_key?` (scopes batching to one swing),
   *    `seq?` (monotonic per fight, adapter-stamped);
   *  - streaming extras: `beat?` (drives the 75% SFX chain), `suppressSfx?`;
   *  - death payload: `type: 'death'`, `target_id`, `position`, `entity`,
   *    `friendly`, `suppressSfx?`;
   *  - queue stamps (enqueueAnimations): `queueId` (drain identity),
   *    `generation` (fight the item belongs to);
   *  - in-flight stamps (playAnimations): `config`, `animId`, `phase`
   *    (null until the layer's stagger elapses), `isLead`.
   */
  // Every animation currently in flight. One move resolves once per target and
  // each resolution animates IN FULL, layered — so this is a set, not a single
  // animation with a single shared phase, and each member carries its own
  // `phase` clock (null until its stagger elapses).
  const [activeAnimations, setActiveAnimations] = useState([]);
  const [animationQueue, setAnimationQueue] = useState([]);
  // Which log entries have already been turned into animations, by identity —
  // never by list index. See revealedLogEntries: the raw log is front-trimmed
  // by the adapter, so an index cursor skews under it permanently.
  const processedLogIdsRef = useRef(new Set());
  // Monotonic key for the in-flight set. Identity can't come from the payload:
  // two resolutions of one swing can be byte-identical on the wire (Chip Away
  // landing twice on one target for the same outcome).
  const animIdRef = useRef(0);
  // Monotonic enqueue-time identity for queue items — what the drain removes
  // by (see removeBatchByIdentity).
  const queueIdRef = useRef(0);
  // Which fight the pipeline is animating. Bumped by the per-fight reset;
  // queue items are stamped with it at enqueue, and the drain/players refuse
  // items from a moved generation — closing the race where the reset and a
  // drain of the pre-reset queue snapshot land in the same commit.
  const fightGenerationRef = useRef(0);
  // Kills already given a death burst this fight, keyed `${beat}:${target}`.
  // A per-enqueue-pass set forgot earlier passes, so a kill whose carriers
  // arrived across two polls chained two bursts.
  const killedTargetsRef = useRef(new Set());
  // Early-out signature for the log-enqueue walk (see that effect).
  const logSignatureRef = useRef(null);
  const [dyingEntities, setDyingEntities] = useState([]);
  // Guard ref: set to true on unmount to prevent stale setTimeout callbacks
  const animationCancelRef = useRef(false);
  const animationTimeoutsRef = useRef([]);
  // Distinguish "a new fight started" from "this fight ended" -- the pan/reset
  // effect below runs for both, and only the first may reset the animation
  // cursor. See the comment there.
  const prevCombatIdRef = useRef(null);
  const prevCombatActiveRef = useRef(false);

  const [hoveredEntity, setHoveredEntity] = useState(null);
  // Store the id, not the entity object. Every beat replaces `combat` with freshly
  // deserialized entities, so a stored object reference would freeze the panel on
  // the stats captured at click time — HP, current action and status effects would
  // never update, and would keep displaying after the combatant died.
  const [selectedEntityId, setSelectedEntityId] = useState(null);

  const isFitMode = normalizeViewMode(zoom) === VIEW_MODE_FIT;
  const squareCells = useFeatureFlag('squareBattlefieldCells');
  // Sprite sheets + region tilesets (public/assets/sprites/manifest.json).
  // Null until loaded, or forever when no art has been delivered; every
  // consumer falls back to glyph tokens and procedural terrain on null.
  const spriteManifest = useSpriteManifest();

  // One place the "every combatant on the field" list is built. It was assembled
  // inline at three sites with slightly different shapes, in a file whose
  // documented bug history is precisely this kind of same-shape-built-three-ways
  // drift.
  const allCombatants = useMemo(
    () => [combat?.player, ...(combat?.allies || []), ...(combat?.enemies || [])].filter(Boolean),
    [combat?.player, combat?.allies, combat?.enemies]
  );

  const selectedEntity = useMemo(() => {
    if (!selectedEntityId) return null;
    return allCombatants.find((e) => e?.id === selectedEntityId) || null;
  }, [selectedEntityId, allCombatants]);

  const setSelectedEntity = useCallback(
    (entity) => setSelectedEntityId(entity?.id ?? null),
    []
  );

  const { playSFX } = useAudio();

  // Notify parent when animation busy-state changes so end-of-combat timing
  // can wait for the death animation to finish before starting the grace timer.
  // prevAnimatingRef skips the callback when the boolean hasn't changed (e.g.
  // phase transitions within a single animation — the in-flight set stays
  // non-empty throughout). This avoids unnecessary GamePage
  // re-renders on every phase. Cleanup resets to false on unmount so GamePage
  // never gets stuck with isBattlefieldAnimating=true.
  const prevAnimatingRef = useRef(false);
  const onAnimatingChangeRef = useRef(onAnimatingChange);
  useEffect(() => {
    onAnimatingChangeRef.current = onAnimatingChange;
  }, [onAnimatingChange]);

  // Change detection only — deliberately no cleanup here. A cleanup would run on
  // every dep change, not just unmount, emitting `false` mid-sequence while
  // prevAnimatingRef still reads `true`, so the guard below would suppress the
  // corrective `true` and leave the parent believing animation had finished.
  useEffect(() => {
    // The LAST layer, not the first: a four-target arc is still animating long
    // after its lead resolution has finished its return phase.
    const isAnimating = activeAnimations.length > 0 || animationQueue.length > 0;
    if (onAnimatingChange && isAnimating !== prevAnimatingRef.current) {
      prevAnimatingRef.current = isAnimating;
      onAnimatingChange(isAnimating)
    }
  }, [activeAnimations, animationQueue, onAnimatingChange]);

  // Unmount-only reset, so the parent never gets stuck with isBattlefieldAnimating=true.
  useEffect(() => () => {
    onAnimatingChangeRef.current?.(false)
  }, []);

  // Smooth camera — follow mode only. All mutable values live in refs so the
  // RAF loop never needs to be recreated and only drives a React re-render
  // when the integer snap cell actually changes (i.e. Jean crosses a cell
  // boundary), keeping frame-level CPU cost off the React scheduler.
  const cameraRef    = useRef(null); // { x: float, y: float } — current smooth position
  const targetCamRef = useRef(null); // { x: float, y: float } — desired position
  const snapCellRef  = useRef(null); // { leftX, topY } — last committed integer snap
  const contentDivRef = useRef(null); // wrapper div that receives the sub-cell CSS transform
  const cameraRafRef  = useRef(null);
  // Deliberately write-only: the render path reads `snapCellRef.current` (always
  // current, unlike state during a RAF frame), so this value is never consumed.
  // It exists solely to re-render when the camera crosses a cell boundary.
  // Do NOT "clean up" as unused state — deleting it freezes the camera at its
  // first snap, and no test catches that because the ref keeps reading correctly.
  const [, forceSnapRender] = useState(0);
  const bumpSnapRender = useCallback(() => forceSnapRender((n) => n + 1), []);

  // Touch pan — a separate layer that moves independently of the RAF camera,
  // so panning doesn't interfere with the smooth camera animation.
  const panLayerRef = useRef(null);
  const gridContainerRef = useRef(null);
  const touchPanRef = useRef({ x: 0, y: 0 }); // current pan offset in pixels
  const touchStartRef = useRef(null);           // { x, y } of last touch point
  const panDecayRafRef = useRef(null);
  // Accumulated pointer travel for the current drag. A drag that ends over the
  // map background also fires a click; without this the gesture would clear
  // the selected-combatant panel every time the player panned.
  const dragTravelRef = useRef(0);
  // Pan clamp bounds, captured at gesture start — see applyDelta.
  const dragBoundsRef = useRef(null);
  // Mirrors "pan is non-zero" into React so the recenter affordance can render.
  // Panning is sticky (it used to spring back to center the instant you let
  // go, which made the advertised "drag to pan" do nothing), so the player
  // needs a way back — and needs to know they are looking away from Jean.
  const [isPanned, setIsPanned] = useState(false);

  // Resolve effective map size: API value → bounding box of entity positions → 9
  const resolvedMapSize = useMemo(() => {
    // Clamped like the derived branch below: this value drives a gridCols^2
    // cell loop and that many DOM nodes, so an out-of-range map_size from a
    // regressed server would hang the tab rather than degrade.
    if (mapSize && mapSize > 0) return Math.min(MAX_MAP_SIZE, Math.floor(mapSize));
    let maxCoord = 8; // floor at 9×9
    for (const e of allCombatants) {
      if (e?.position) maxCoord = Math.max(maxCoord, e.position.x, e.position.y);
    }
    return Math.min(MAX_MAP_SIZE, maxCoord + 1);
  }, [mapSize, allCombatants]);

  // Touch pan handlers — attached via useEffect so touchmove can be non-passive
  const applyPanTransform = useCallback(() => {
    const { x, y } = touchPanRef.current;
    if (panLayerRef.current) {
      panLayerRef.current.style.transform = `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px)`;
    }
    // React bails out when the value is unchanged, so calling this per frame
    // during a drag costs nothing beyond the comparison.
    const panned = Math.abs(x) > 2 || Math.abs(y) > 2;
    setIsPanned((prev) => (prev === panned ? prev : panned));
  }, []);

  /** Ease the pan offset back to zero (the recenter affordance). */
  const recenterPan = useCallback(() => {
    const pan = touchPanRef.current;
    if (Math.abs(pan.x) < 0.5 && Math.abs(pan.y) < 0.5) {
      touchPanRef.current = { x: 0, y: 0 };
      applyPanTransform();
      panDecayRafRef.current = null;
      return;
    }
    touchPanRef.current = { x: pan.x * 0.82, y: pan.y * 0.82 };
    applyPanTransform();
    panDecayRafRef.current = requestAnimationFrame(recenterPan);
  }, [applyPanTransform]);

  useEffect(() => {
    const el = gridContainerRef.current;
    if (!el) return;

    const applyDelta = (dx, dy) => {
      // Bounds are captured once per gesture, not per move: the container is
      // 100% of the panel and cannot resize mid-drag, and reading the rect on
      // every pointer move (60-120/s) forces a synchronous layout flush over a
      // subtree holding up to thousands of grid cells. Lazily initialised so a
      // synthetic move with no preceding down-event still clamps.
      if (!dragBoundsRef.current) {
        const { width, height } = el.getBoundingClientRect();
        dragBoundsRef.current = { maxX: width * 0.4, maxY: height * 0.4 };
      }
      const { maxX, maxY } = dragBoundsRef.current;
      dragTravelRef.current += Math.abs(dx) + Math.abs(dy);
      touchPanRef.current = {
        x: Math.max(-maxX, Math.min(maxX, touchPanRef.current.x + dx)),
        y: Math.max(-maxY, Math.min(maxY, touchPanRef.current.y + dy)),
      };
      applyPanTransform();
    };

    const beginDrag = (x, y) => {
      if (panDecayRafRef.current) { cancelAnimationFrame(panDecayRafRef.current); panDecayRafRef.current = null; }
      const { width, height } = el.getBoundingClientRect();
      dragBoundsRef.current = { maxX: width * 0.4, maxY: height * 0.4 };
      dragTravelRef.current = 0;
      touchStartRef.current = { x, y };
    };

    // Touch handlers
    const onTouchStart = (e) => {
      if (e.touches.length !== 1) return;
      beginDrag(e.touches[0].clientX, e.touches[0].clientY);
    };
    const onTouchMove = (e) => {
      if (!touchStartRef.current || e.touches.length !== 1) return;
      e.preventDefault();
      const dx = e.touches[0].clientX - touchStartRef.current.x;
      const dy = e.touches[0].clientY - touchStartRef.current.y;
      touchStartRef.current = { x: e.touches[0].clientX, y: e.touches[0].clientY };
      applyDelta(dx, dy);
    };
    // Pan is sticky: releasing keeps the view where the player put it. The
    // recenter button (and starting a new fight) is what returns it.
    const onTouchEnd = () => {
      touchStartRef.current = null;
    };

    // Mouse drag handlers
    const onMouseDown = (e) => {
      if (e.button !== 0) return;
      beginDrag(e.clientX, e.clientY);
      el.style.cursor = 'grabbing';
    };
    const onMouseMove = (e) => {
      if (!touchStartRef.current) return;
      const dx = e.clientX - touchStartRef.current.x;
      const dy = e.clientY - touchStartRef.current.y;
      touchStartRef.current = { x: e.clientX, y: e.clientY };
      applyDelta(dx, dy);
    };
    const onMouseUp = () => {
      if (!touchStartRef.current) return;
      touchStartRef.current = null;
      el.style.cursor = '';
    };

    el.addEventListener('touchstart', onTouchStart, { passive: true });
    el.addEventListener('touchmove', onTouchMove, { passive: false });
    el.addEventListener('touchend', onTouchEnd, { passive: true });
    el.addEventListener('mousedown', onMouseDown);
    // mousemove/mouseup on window so drag works when cursor leaves the grid
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
    return () => {
      el.removeEventListener('touchstart', onTouchStart);
      el.removeEventListener('touchmove', onTouchMove);
      el.removeEventListener('touchend', onTouchEnd);
      el.removeEventListener('mousedown', onMouseDown);
      window.removeEventListener('mousemove', onMouseMove);
      window.removeEventListener('mouseup', onMouseUp);
      if (panDecayRafRef.current) cancelAnimationFrame(panDecayRafRef.current);
    };
    // `tab` is load-bearing: the enemies tab early-returns a different tree, so
    // the container this effect binds to unmounts and a NEW one mounts on the
    // way back. Without re-running, the listeners stay attached to the detached
    // node and panning is silently dead for the rest of the session.
  }, [applyPanTransform, tab]);

  // New-fight housekeeping: (1) reset the touch-pan offset, on EVERY fight
  // boundary; (2) reset the animation pipeline (queue, cursor, in-flight
  // layers, kill registry), only when a genuinely NEW fight starts. The two
  // share one effect because the prev-ref update below (prevCombatIdRef /
  // prevCombatActiveRef) must run exactly once per transition: split into two
  // effects keyed on the same deps, each would have to record the transition
  // itself, and the duplicate recording means whichever compares second sees
  // prev === current and misses the fight boundary.
  //
  // Keyed on the props Battlefield passes from the top-level combat object,
  // NOT on `combat` — that prop is a beat state here, and
  // serialize_combat_state emits neither field, so reading them off it made
  // this dep flip uuid <-> undefined every time displayState alternated shape,
  // resetting the camera mid-fight.
  useEffect(() => {
    if (panDecayRafRef.current) { cancelAnimationFrame(panDecayRafRef.current); panDecayRafRef.current = null; }
    touchPanRef.current = { x: 0, y: 0 };
    applyPanTransform();

    // This effect also runs when a fight ENDS: `combatActive` flips to false
    // while the grid stays mounted. Resetting the animation cursor on that
    // transition replays the whole fight -- Battlefield clears accBeatStates,
    // which re-runs the enqueue effect against an emptied processed set, so
    // every still-revealed carrier is treated as new and the fight animates
    // again from the top, holding onAnimatingChange open through the victory
    // grace timer. Only a genuinely NEW fight may reset the cursor.
    const startingNewFight =
      (combatId != null && combatId !== prevCombatIdRef.current) ||
      (combatActive && !prevCombatActiveRef.current);
    // Record only REAL ids. combat:ended is synthesized with no combat_id
    // (useApi.applyCombatState), so combatId blips to undefined at every
    // fight end; recording that blip made the next ordinary poll read as
    // undefined -> same-id, a fake "new fight" that cleared the cursor and
    // replayed the whole revealed log -- the replay bug's side door.
    if (combatId != null) prevCombatIdRef.current = combatId;
    prevCombatActiveRef.current = combatActive;
    if (!startingNewFight) return;

    // Retire the previous fight's generation FIRST: any queue snapshot still
    // in flight this commit carries the old stamp, and the drain refuses it.
    fightGenerationRef.current += 1;
    // The queue is per-fight. Without this it lives for the whole session,
    // replaying a finished fight's animations into the next one.
    setAnimationQueue([]);
    setLastProcessedStreamIndex(0);
    // Same reason, and it must be cleared alongside the queue: the server
    // clears combat_log per fight and LeftPanel restarts its count, so the new
    // fight's opening entries carry the same ids as the old one's and would be
    // mistaken for already-animated.
    processedLogIdsRef.current = new Set();
    // Per-fight like the processed set: a respawned roster reuses entity ids,
    // and a stale kill registry would swallow the new fight's death bursts.
    killedTargetsRef.current = new Set();
    // Force the next log-enqueue pass to walk the (possibly identical-looking)
    // new fight's log.
    logSignatureRef.current = null;
    // In-flight layers are per-fight too. Clearing only the queue left the
    // previous fight's stagger timeouts (up to MAX_LAYER_LEAD_MS) and phase
    // chains running: they fired into the new arena, and because
    // activeAnimations stayed non-empty the new fight's first batch could
    // never drain -- leaving onAnimatingChange latched true.
    animationTimeoutsRef.current.forEach(clearTimeout);
    animationTimeoutsRef.current = [];
    setActiveAnimations([]);
    setDyingEntities([]);
  }, [combatId, combatActive, applyPanTransform]);

  // Clicking the map background clears the selection — as the panel's own
  // close-button tooltip promised. The previous `e.target === e.currentTarget`
  // test never passed: the pan and content layers are full-bleed children with
  // default pointer-events, so a background click always resolved to one of
  // them and Escape was the only way out. Entity and panel clicks stop
  // propagation, so anything that reaches this handler *is* the background.
  const handleGridClick = useCallback(() => {
    if (dragTravelRef.current > DRAG_CLICK_THRESHOLD_PX) return; // a pan, not a click
    setSelectedEntity(null);
  }, [setSelectedEntity]);

  const handleClearHover = useCallback(() => setHoveredEntity(null), []);
  const handleCloseSelectedEntity = useCallback(() => setSelectedEntity(null), [setSelectedEntity]);

  // Escape closes the selected-entity panel — the ✕ button is small and not
  // everyone notices that clicking the map background also clears selection.
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') setSelectedEntity(null); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [setSelectedEntity]);

  // Set/clear the unmount guard
  useEffect(() => {
    animationCancelRef.current = false;
    return () => {
      animationCancelRef.current = true;
      animationTimeoutsRef.current.forEach(clearTimeout);
      animationTimeoutsRef.current = [];
    };
  }, []);

  // Schedule a timeout tracked for unmount cleanup, self-pruning its id once it
  // fires. Without the self-prune the tracking array grows unbounded across a
  // whole play session (BattlefieldGrid never unmounts between fights), holding
  // dead ids forever; only unmount cleared it.
  const trackTimeout = useCallback((fn, delay) => {
    const id = setTimeout(() => {
      animationTimeoutsRef.current = animationTimeoutsRef.current.filter(
        (t) => t !== id
      );
      fn();
    }, delay);
    animationTimeoutsRef.current.push(id);
    return id;
  }, []);

  /**
   * Stamp queue identity + fight generation onto animation payloads and append
   * them under the queue bound. Every enqueue goes through here: the stamps
   * are what the drain and the reset-race guards key on.
   */
  const enqueueAnimations = useCallback((items) => {
    const stamped = items.map((item) => ({
      ...item,
      queueId: (queueIdRef.current += 1),
      generation: fightGenerationRef.current,
    }));
    setAnimationQueue((prev) => appendBounded(prev, stamped));
  }, []);

  // Streaming (issue #436): enqueue pre-built animations as the engine's beats
  // arrive. Replaces the log-spooler path below; deaths/departures are built by
  // the parent from the engine's authoritative killed/departed, not diffed here.
  // A streamed animation's `swing_key` (adapter-stamped) rides through the
  // spread in enqueueAnimations untouched.
  const [lastProcessedStreamIndex, setLastProcessedStreamIndex] = useState(0);
  useEffect(() => {
    if (!streaming) return;
    // The parent resets streamedAnimations to [] between fights. Without
    // re-syncing the cursor, a shorter (or empty) buffer would sit below the
    // stale index and the next combat's beats would never enqueue.
    if (streamedAnimations.length < lastProcessedStreamIndex) {
      setLastProcessedStreamIndex(streamedAnimations.length);
      return;
    }
    if (streamedAnimations.length > lastProcessedStreamIndex) {
      enqueueAnimations(streamedAnimations.slice(lastProcessedStreamIndex));
      setLastProcessedStreamIndex(streamedAnimations.length);
    }
  }, [streaming, streamedAnimations, lastProcessedStreamIndex, enqueueAnimations]);

  // Enqueue new animations from the combat log as entries are revealed
  useEffect(() => {
    if (streaming) return; // beats drive animation instead (see effect above)
    const log = combatLog || combat?.log;
    if (!log) return;

    // Early out when nothing can have changed: `combat.log` is a freshly
    // deserialized array on every poll, so without this the full (~800-entry)
    // log was re-walked through revealedLogEntries per poll even when idle.
    // What each component covers: length + tail key/beat/seq catch plain
    // appends and most trims; the HEAD entry's key and the tail's within-beat
    // repeat ordinal catch a front-trim that removes k entries while k
    // byte-identical UNSTAMPED carriers append (length, tail identity, reveal
    // count and generation all match in that shape, and skipping it dropped
    // the new landing); the reveal count covers LeftPanel progress; the fight
    // generation covers a new fight with an identical-looking log. A log
    // change this signature still cannot see is one whose positional entry
    // ids are byte-identical too, and the enqueue walk below would find
    // nothing new in that case either — the signature is exactly as
    // discriminating as the id scheme it gates.
    const lastEntry = log.length ? log[log.length - 1] : null;
    // The tail's within-beat repeat ordinal: how many earlier entries of the
    // tail's own beat share its key. Walks back only through the tail's beat
    // (a handful of entries), so the idle-poll cost stays O(beat), not O(log).
    let tailRepeat = 0;
    if (lastEntry) {
      const tailKey = logEntryKey(lastEntry);
      const tailBeat = lastEntry.beat_index ?? 0;
      for (let i = log.length - 2; i >= 0; i--) {
        if ((log[i]?.beat_index ?? 0) !== tailBeat) break;
        if (logEntryKey(log[i]) === tailKey) tailRepeat += 1;
      }
    }
    const signature = [
      log.length,
      log.length ? logEntryKey(log[0]) : '',
      lastEntry ? logEntryKey(lastEntry) : '',
      lastEntry?.beat_index ?? '',
      lastEntry?.animation?.seq ?? '',
      tailRepeat,
      displayedLogCount,
      fightGenerationRef.current,
    ].join(LOG_KEY_SEP);
    if (logSignatureRef.current === signature) return;
    logSignatureRef.current = signature;

    const processed = processedLogIdsRef.current;
    const killed = killedTargetsRef.current;
    const animations = [];
    // Every animation-carrier id in the current window — what `processed` is
    // pruned against below.
    const windowIds = new Set();

    revealedLogEntries(log, displayedLogCount).forEach(({ entry, id }) => {
      // Prose-only lines are never tracked: their ids embed the full message
      // text, and recording them held every revealed line's prose in the set
      // for the whole fight.
      if (!entry.animation) return;
      windowIds.add(id);
      if (processed.has(id)) return;
      processed.add(id);
      // The batch predicate needs a per-swing key (see takeAnimationBatch).
      // The beat index alone is NOT a fight-wide swing identity: the server
      // resets beat_index to 0 at the top of EVERY player action, so two
      // successive same-type swings by one actor (kill A, immediately attack
      // B with no intervening carriers) would share it and merge into one
      // batch — the second swing losing its windup and whoosh. `round` is
      // monotonic per fight, so compounding round:beat scopes the key to one
      // swing; an adapter-stamped key wins if present.
      const anim = {
        ...entry.animation,
        swing_key: entry.animation.swing_key
          ?? `${entry.round ?? 0}:${entry.beat_index ?? 0}`,
      };
      animations.push(anim);

      // Detect a killing blow — chain a death animation after the attack.
      // The kill registry is per FIGHT (`killedTargetsRef`), not per pass:
      // a kill whose carriers arrive across two polls must still burst once.
      const beatIdx = entry.beat_index ?? 0;
      const killKey = `${beatIdx}:${anim.target_id}`;
      if (anim.target_id && allBeatStates && !killed.has(killKey)) {
        const stateBefore = allBeatStates[Math.max(0, beatIdx - 1)];
        const stateAt = allBeatStates[beatIdx];
        // Both liveness checks must read a missing hp field identically.
        // Divergent defaults across these two lines make an enemy count as
        // alive before the blow and dead after it, firing a death burst on a
        // combatant that is still fighting.
        const wasAlive = stateBefore?.enemies?.some(
          (en) => en.id === anim.target_id && isLiving(en)
        );
        const isNowDead = !stateAt?.enemies?.some(
          (en) => en.id === anim.target_id && isLiving(en)
        );
        if (wasAlive && isNowDead) {
          const lastKnown = stateBefore.enemies.find((en) => en.id === anim.target_id);
          if (lastKnown?.position) {
            // friendly: false is sound here — this branch only inspects
            // `stateBefore.enemies`, so it can only ever synthesize an
            // enemy death. Streamed deaths (which can be an ally or Jean)
            // carry their own alignment from `beatToAnimations`.
            animations.push({
              type: 'death',
              target_id: anim.target_id,
              position: lastKnown.position,
              entity: lastKnown,
              friendly: false,
            });
            killed.add(killKey);
          }
        }
      }
    });

    // Prune ids whose entries have left the revealed window (front-trimmed
    // away): the set tracks the window, not the whole fight, so it cannot grow
    // without bound across a long brawl. Within a fight an id never re-enters
    // the window — it only grows at the tail and shrinks at the front — with
    // ONE exception: the synthesized combat:ended payload blips `log: []`
    // while the next poll still serves the finished fight's log. Pruning
    // against that empty window would wipe the set and replay the whole fight,
    // so an empty window prunes nothing (there is nothing worth keeping it in
    // step with anyway).
    if (windowIds.size > 0) {
      for (const id of processed) {
        if (!windowIds.has(id)) processed.delete(id);
      }
    }

    if (animations.length > 0) {
      enqueueAnimations(animations);
    }
    // `combatId` is a real dependency, not decoration: the reset effect above
    // empties the processed-id set when a fight changes, and this effect is
    // what refills it. Without it, a new fight whose log array happened to be
    // reference-equal to the old one would never re-enqueue.
  }, [streaming, combatLog, combat?.log, displayedLogCount, allBeatStates, combatId, enqueueAnimations]);

  // Start one layer's own phase clock. `entry.isLead` (stamped by
  // playAnimations) gates the swing's NON-IMPACT SFX cues here — followers
  // play only their landing. The lead's other roles (token motion, source
  // scale/glow) are read from the same flag by EntityLayer and
  // animationStyleFor, not by this function.
  const startAnimationLayer = useCallback((entry) => {
    if (animationCancelRef.current) return; // component unmounted — bail out
    // A layer whose fight was reset between scheduling and its staggered start
    // belongs to an arena that no longer exists — let it die silently.
    if (entry.generation !== undefined && entry.generation !== fightGenerationRef.current) return;
    const config = entry.config;

    // Streaming (issue #436): fire this beat's ordered SFX as a 75% partial
    // stack at layer start (the engine authored the emissions, including
    // whether a follow-up resolution carries a swing); this replaces the
    // phase-keyed cues below. `suppressSfx` entries stay silent (e.g. a
    // streamed death whose sound already played in the attack's chain).
    if (entry.beat) {
      const schedule = scheduleSfxChain(
        beatSfxFor(entry.beat),
        (cue) => SFX_DURATIONS[cue] || 0,
        combatSpeed
      );
      for (const { cue, startMs } of schedule) {
        // scheduleSfxChain already divides startMs by combatSpeed internally.
        trackTimeout(() => playSFX(cue, combatSpeed), startMs);
      }
    }

    // Register the entity as dying so DeathAnimationLayer can render the burst
    // and EntityLayer can fade out the marker
    if (entry.type === 'death' && entry.position) {
      setDyingEntities((prev) => [...prev, {
        id: entry.target_id,
        position: entry.position,
        entity: entry.entity,
        friendly: entry.friendly === true,
      }]);
      // Enemy death SFX — play once per kill (streamed deaths are sounded by the
      // attack beat's SFX chain instead, so they carry suppressSfx).
      if (!entry.suppressSfx) playSFX('enemy_death', combatSpeed);
    }

    let currentPhaseIndex = 0;

    const advancePhase = () => {
      if (animationCancelRef.current) return; // component unmounted — bail out
      if (currentPhaseIndex >= config.phases.length) {
        setActiveAnimations((prev) => prev.filter((a) => a.animId !== entry.animId));
        if (entry.type === 'death') {
          setDyingEntities((prev) => prev.filter((d) => d.id !== entry.target_id));
        }
        return;
      }
      const phase = config.phases[currentPhaseIndex];
      setActiveAnimations((prev) => prev.map(
        (a) => (a.animId === entry.animId ? { ...a, phase: phase.name } : a)
      ));

      // Phase-aligned SFX cues, declared on the animation config. The special
      // cue 'outcome' resolves through the animation's outcome
      // ('hit' | 'miss' | 'parry' | ...) to the matching pre-baked WAV.
      // Skipped for streaming beats: their SFX is the 75% chain fired at start
      // (entry.beat), or intentionally silent (suppressSfx).
      //
      // A follower layer plays its landing and nothing else: one arc is one
      // movement of the weapon, so four resolutions must not stack four
      // whooshes. Their landings still layer — the layer stagger IS the SFX
      // chain's spacing (see playAnimations), so the impact cues arrive as the
      // partial stack rather than on one frame or one after another.
      const usesChain = entry.beat || entry.suppressSfx;
      const silent = usesChain || (!entry.isLead && phase.name !== 'impact');
      const cue = silent ? null : config.sfx?.[phase.name];
      if (cue) {
        playSFX(cue === 'outcome' ? impactSfxFor(entry.outcome) : cue, combatSpeed);
      }

      trackTimeout(() => {
        currentPhaseIndex++;
        advancePhase();
      }, effectiveDuration(phase.duration, combatSpeed));
    };

    advancePhase();
    // Omitted deps are stable by construction: state setters, animationCancelRef
    // (a ref), and trackTimeout (empty-dep useCallback). Only playSFX and
    // combatSpeed change this callback's behaviour.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playSFX, combatSpeed]);

  // Play one swing's resolutions concurrently, dealt out on the SFX chain's
  // spacing. Every layer joins the in-flight set immediately (so `isAnimating`
  // covers the whole volley and the queue can't drain early) but stays
  // phase-less, and therefore invisible, until its own start.
  const playAnimations = useCallback((batch) => {
    // A batch whose fight was reset between being taken and this call belongs
    // to an arena that no longer exists.
    if (batch.length === 0) return;
    if (batch[0].generation !== undefined && batch[0].generation !== fightGenerationRef.current) return;
    const entries = batch.map((animData, index) => ({
      ...animData,
      config: getAnimationConfig(animData.type),
      animId: (animIdRef.current += 1),
      phase: null,
      // The lead owns the token's motion and the swing's non-impact cues. It
      // travels WITH the layer rather than being derived at read time: the
      // lead leaves activeAnimations when its phases finish, and a "first
      // still in flight" rule then promotes a follower whose target_id is a
      // different cell, snapping the token mid-arc.
      isLead: index === 0,
    }));
    setActiveAnimations((prev) => [...prev, ...entries]);

    const layers = scheduleAnimationLayers(
      entries.map(animationImpactCue),
      (cue) => SFX_DURATIONS[cue] || 0,
      combatSpeed
    );

    entries.forEach((entry, index) => {
      const begin = () => startAnimationLayer(entry);
      // scheduleAnimationLayers already divides startMs by combatSpeed.
      const startMs = layers[index]?.startMs || 0;
      if (startMs > 0) trackTimeout(begin, startMs);
      else begin();
    });
    // trackTimeout is an empty-dep useCallback; setActiveAnimations is a setter.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [startAnimationLayer, combatSpeed]);

  // Stale-generation guard shared by the drain's two filters below. Unstamped
  // items (generation undefined) predate the stamp and always pass. Stable
  // identity: it reads only a ref, so it can sit in effect deps harmlessly.
  const isCurrentGeneration = useCallback(
    (item) => item.generation === undefined || item.generation === fightGenerationRef.current,
    []
  );

  // Queue drain: when nothing is in flight, take the next batch and play it.
  useEffect(() => {
    if (activeAnimations.length !== 0 || animationQueue.length === 0) return;
    // The snapshot can hold items from a fight that was reset EARLIER IN THIS
    // SAME COMMIT (the reset effect runs first, bumps the generation and
    // schedules the state clear — but this effect's deps still show the old
    // queue). Stale-generation items must be dropped, never played.
    const fresh = animationQueue.filter(isCurrentGeneration);
    if (fresh.length === 0) {
      // Nothing playable — sweep the stale items out of the live queue.
      // Return `prev` untouched when there is nothing to remove, or the fresh
      // array identity would re-run this effect forever.
      setAnimationQueue((prev) => {
        const kept = prev.filter(isCurrentGeneration);
        return kept.length === prev.length ? prev : kept;
      });
      return;
    }
    const [batch] = takeAnimationBatch(fresh);
    // Remove by enqueue-time identity, never by position: the live queue may
    // have been front-trimmed, appended to, or reset since this snapshot —
    // see removeBatchByIdentity's invariant.
    setAnimationQueue((prev) => removeBatchByIdentity(prev, batch));
    playAnimations(batch);
  }, [activeAnimations, animationQueue, playAnimations, isCurrentGeneration]);

  // Compute player position before camera effect (needed for camera target calculation)
  const playerPos = getPos(combat?.player);

  // Smooth camera RAF loop — reads only refs, drives contentDivRef transform
  // directly (no React state per frame). bumpSnapRender is called only when the
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
      const snap = computeSnapOrigin(cameraRef.current);
      if (!snapCellRef.current || snap.leftX !== snapCellRef.current.leftX || snap.topY !== snapCellRef.current.topY) {
        snapCellRef.current = snap;
        bumpSnapRender();
      }
      return;
    }

    // Lerp one step toward target
    cameraRef.current = { x: cam.x + dx * CAMERA_LERP, y: cam.y + dy * CAMERA_LERP };
    const snap = computeSnapOrigin(cameraRef.current);

    // Sub-cell offset: shift the content div to cover the fractional remainder
    // fracX > 0 ⇒ shift right (snap over-stepped left);  fracY < 0 ⇒ shift up
    const fracX = (snap.leftX - cameraRef.current.x) / VIEW_SIZE * 100;
    const fracY = (cameraRef.current.y - snap.topY) / VIEW_SIZE * 100;
    contentDivRef.current.style.transform = `translate(${fracX.toFixed(3)}%, ${fracY.toFixed(3)}%)`;

    if (!snapCellRef.current || snap.leftX !== snapCellRef.current.leftX || snap.topY !== snapCellRef.current.topY) {
      snapCellRef.current = snap;
      bumpSnapRender();
    }

    cameraRafRef.current = requestAnimationFrame(animateCamera);
    // Safe: animateCamera only reads mutable refs; bumpSnapRender is a stable
    // useCallback, so animateCamera's own identity stays stable too.
  }, [bumpSnapRender]);

  // Update camera target whenever Jean moves or the view mode changes
  useEffect(() => {
    if (isFitMode) {
      // Fit mode frames the roster, not Jean — no camera animation; clear any
      // residual transform
      if (cameraRafRef.current) { cancelAnimationFrame(cameraRafRef.current); cameraRafRef.current = null; }
      if (contentDivRef.current) contentDivRef.current.style.transform = '';
      cameraRef.current = null;
      snapCellRef.current = null;
      bumpSnapRender();
      return;
    }

    // Jean is always centered — no edge-clamping. Off-map cells at the
    // edges render dimmed so players can see the map boundary.
    const tgtX = playerPos.x - HALF_VIEW;
    const tgtY = playerPos.y + HALF_VIEW;
    targetCamRef.current = { x: tgtX, y: tgtY };

    const snapImmediately = () => {
      if (cameraRafRef.current) { cancelAnimationFrame(cameraRafRef.current); cameraRafRef.current = null; }
      cameraRef.current = { x: tgtX, y: tgtY };
      if (contentDivRef.current) contentDivRef.current.style.transform = '';
      const snap = computeSnapOrigin(cameraRef.current);
      snapCellRef.current = snap;
      bumpSnapRender();
    };

    if (!cameraRef.current) {
      // First mount in follow mode — snap immediately, no animation
      snapImmediately();
      return;
    }

    // If Jean would leave the viewport during a smooth animation (jump > HALF_VIEW
    // cells), snap instead. Moves ≤ HALF_VIEW always keep Jean within the
    // VIEW_SIZE-cell window; larger jumps (log skipping, combat start) would
    // make her invisible.
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
  }, [isFitMode, playerPos.x, playerPos.y, animateCamera, bumpSnapRender]);

  // Cancel camera RAF on unmount
  useEffect(() => () => {
    if (cameraRafRef.current) cancelAnimationFrame(cameraRafRef.current);
  }, []);

  // -------------------------------------------------------------------------
  // Fit-mode framing — the square window containing every living combatant.
  //
  // Hysteresis via fitBoxRef: the current frame is kept as long as everyone is
  // still inside it and it is no more than one quantization step larger than
  // needed. Without it the framing would be re-derived every beat and the
  // whole map would visibly rescale each time a combatant shuffled one cell.
  // Writing the ref during the memo is safe because the check is idempotent —
  // a repeated evaluation sees the box it just produced and returns it.
  // -------------------------------------------------------------------------
  const fitBoxRef = useRef(null);
  const fitBox = useMemo(() => {
    if (!isFitMode) {
      fitBoxRef.current = null;
      return null;
    }
    const positioned = allCombatants.filter((e) => e?.position && isLiving(e));
    // Nothing to frame (combat ending, or a payload with no positions at all):
    // fall back to the whole arena rather than an undefined viewport. Clearing
    // the ref matters — otherwise the next roster to appear would be validated
    // against a frame left over from the previous fight.
    if (positioned.length === 0) {
      fitBoxRef.current = null;
      return { size: resolvedMapSize, leftX: 0, topY: resolvedMapSize - 1 };
    }

    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    for (const e of positioned) {
      minX = Math.min(minX, e.position.x);
      maxX = Math.max(maxX, e.position.x);
      minY = Math.min(minY, e.position.y);
      maxY = Math.max(maxY, e.position.y);
    }

    const needed = Math.max(maxX - minX, maxY - minY) + 1 + FIT_PADDING * 2;
    const size = Math.min(
      // Never wider than the arena itself (but always at least a follow-mode
      // window, so a melee scrum doesn't zoom in past the default view).
      Math.max(resolvedMapSize, VIEW_SIZE),
      Math.max(VIEW_SIZE, Math.ceil(needed / FIT_STEP) * FIT_STEP)
    );

    const prev = fitBoxRef.current;
    const stillFits = prev
      && prev.size <= size + FIT_STEP
      && minX >= prev.leftX && maxX <= prev.leftX + prev.size - 1
      && maxY <= prev.topY && minY > prev.topY - prev.size;
    if (stillFits) return prev;

    // Center on the combatants, then slide the frame back inside the arena so
    // the viewport isn't spent on out-of-bounds void. When the frame is wider
    // than the arena (small arenas, where the VIEW_SIZE floor wins) there is
    // nothing to clamp against, so center on the arena instead.
    // Returns the low edge (leftmost column / bottom row) of the frame on one axis.
    const lowEdge = (center) => {
      if (size >= resolvedMapSize) return Math.round((resolvedMapSize - size) / 2);
      return Math.max(0, Math.min(resolvedMapSize - size, Math.round(center - (size - 1) / 2)));
    };

    // topY is the frame's top row, so the y axis is clamped on its bottom edge
    // and converted back up.
    const box = {
      size,
      leftX: lowEdge((minX + maxX) / 2),
      topY: lowEdge((minY + maxY) / 2) + size - 1,
    };
    fitBoxRef.current = box;
    return box;
  }, [isFitMode, allCombatants, resolvedMapSize]);

  // -------------------------------------------------------------------------
  // Viewport computations — done unconditionally (before any early return) so
  // the hooks below are always called in the same order.
  // -------------------------------------------------------------------------
  let gridCols, leftX, topY;
  if (isFitMode) {
    ({ size: gridCols, leftX, topY } = fitBox);
  } else if (snapCellRef.current) {
    // Use the ref directly (always current) instead of state (which may lag during RAF)
    gridCols = VIEW_SIZE;
    leftX = snapCellRef.current.leftX;
    topY  = snapCellRef.current.topY;
  } else {
    // No snap committed yet (first frame, or a fit->follow switch) — Jean
    // centered, no edge-clamping
    gridCols = VIEW_SIZE;
    leftX = playerPos.x - HALF_VIEW;
    topY  = playerPos.y + HALF_VIEW;
  }

  // Tokens shrink with the viewport, so the detail a marker can carry is a
  // function of cell size, not of which mode produced it — fit mode is
  // full-detail for a skirmish and compact for a 30-cell brawl.
  const isCompact = gridCols > VIEW_SIZE;

  /**
   * The viewport cell a world position falls in, or null when it is off
   * screen. Single source of the visibility test — everything that places
   * something on the map goes through here, so no layer can drift into its
   * own idea of what is on screen.
   */
  const cellOf = useCallback((pos) => {
    // Finiteness first: every comparison below is false for NaN, so a
    // malformed coordinate would pass the off-screen test and place the token
    // at the viewport origin instead of being culled — and NaN then propagates
    // into the transform percentages, which CSS silently discards.
    if (!pos || !Number.isFinite(pos.x) || !Number.isFinite(pos.y)) return null;
    if (pos.x < leftX || pos.x >= leftX + gridCols || pos.y > topY || pos.y <= topY - gridCols) return null;
    return { col: pos.x - leftX, row: topY - pos.y };
  }, [leftX, topY, gridCols]);

  /** Convert a world grid position to the absolute-CSS style the layers need. */
  const getEntityStyle = useCallback((pos, baseZ = 20) => {
    const cell = cellOf(pos);
    if (!cell) return null;
    return {
      left: 0, top: 0,
      transform: `translate(${cell.col * 100}%, ${cell.row * 100}%)`,
      width: `${(1 / gridCols) * 100}%`,
      height: `${(1 / gridCols) * 100}%`,
      zIndex: baseZ
    };
  }, [cellOf, gridCols]);

  /**
   * The center of a world position as a percentage of the padded viewport
   * box — the coordinate space the SVG overlay layers draw in.
   *
   * Threat lines need a bare point rather than a cell rect. Deriving it here
   * from the same `cellOf` the styles use keeps it camera/pan/fit-aware and
   * shares the off-screen check, without parsing the CSS strings
   * getEntityStyle just formatted: a regex round-trip through
   * `translate(x%, y%)` would silently yield no lines at all the first time
   * that template changed shape.
   */
  const getEntityCenterPct = useCallback((pos) => {
    const cell = cellOf(pos);
    if (!cell) return null;
    const cellPct = 100 / gridCols;
    return {
      xPct: cell.col * cellPct + cellPct / 2,
      yPct: cell.row * cellPct + cellPct / 2,
    };
  }, [cellOf, gridCols]);

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
    // A combatant mid-fade is rendered from its dying snapshot below, so the
    // live pools skip it. This has to cover the friendly side too: allies and
    // Jean can be killed, and rendering both copies collides their React keys
    // (same id, same side suffix) as well as painting two tokens on one cell.
    if (combat?.player && !dyingIds.has(combat.player.id)) {
      const style = getEntityStyle(getPos(combat.player));
      if (style) result.push({ entity: combat.player, style, isFriendly: true, isHero: true });
    }
    combat?.allies?.forEach((ally) => {
      if (dyingIds.has(ally.id)) return;
      if (isLiving(ally)) {
        const style = getEntityStyle(getPos(ally));
        if (style) result.push({ entity: ally, style, isFriendly: true, isHero: false });
      }
    });
    combat?.enemies?.forEach((enemy) => {
      if (dyingIds.has(enemy.id)) return;
      if (isLiving(enemy)) {
        const style = getEntityStyle(getPos(enemy));
        if (style) result.push({ entity: enemy, style, isFriendly: false });
      }
    });
    // Dying combatants rendered from last-known snapshot during fade-out.
    // Alignment travels on the snapshot: by this point the entity is gone from
    // combat.allies/enemies, so there is no pool left to infer it from, and
    // assuming "enemy" painted a dying ally (or Jean) hostile red for the fade.
    dyingEntities.forEach((dying) => {
      if (!dying.entity) return;
      const style = getEntityStyle(dying.position);
      if (style) {
        result.push({
          entity: dying.entity,
          style,
          isFriendly: dying.friendly === true,
          isDying: true,
        });
      }
    });

    // Disambiguate colliding single-letter initials (e.g. two "Rat"s) by
    // appending subscript digits in insertion order. Player is inserted first
    // so Jean always keeps the bare symbol.
    const SUBSCRIPTS = ['', '₂', '₃', '₄', '₅', '₆', '₇', '₈', '₉'];
    const seenCount = new Map();
    for (const item of result) {
      const base = item.entity.battle_symbol || (item.entity.name && item.entity.name[0]) || '?';
      const n = seenCount.get(base) || 0;
      item.displaySymbol = `${base}${SUBSCRIPTS[n] || ''}`;
      seenCount.set(base, n + 1);
    }
    return result;
  }, [combat?.player, combat?.allies, combat?.enemies, dyingEntities, getEntityStyle]);

  // Memoized background cell array — each cell knows whether it lies inside
  // the real map so off-map viewport cells can render slightly dimmer, giving
  // the player an implicit sense of map boundaries near an edge. Computed in
  // both modes now: fit framing pads past the arena edge just like follow
  // mode does, so it needs the same dimming to read as a boundary.
  const gridBgCells = useMemo(() => {
    const cells = [];
    for (let row = 0; row < gridCols; row++) {
      for (let col = 0; col < gridCols; col++) {
        const worldX = leftX + col;
        const worldY = topY - row;
        const onMap = worldX >= 0 && worldX < resolvedMapSize && worldY >= 0 && worldY < resolvedMapSize;
        cells.push(onMap);
      }
    }
    return cells;
  }, [gridCols, leftX, topY, resolvedMapSize]);

  // Terrain cells for the current viewport: the same row/col walk as
  // gridBgCells, resolved through a bound reader (validated once) and a
  // per-kind cache for labels/variants/tiles (seven kinds, thousands of
  // cells). Only feature cells -- and, once a floor tile exists, open cells
  // -- are emitted; each carries its lattice row/col for explicit placement.
  // `terrain` is held stable per fight by Battlefield (useStableTerrain), so
  // this recomputes on viewport moves, not on every poll.
  const terrainActive = hasTerrain(terrain);
  const terrainCells = useMemo(() => {
    const reader = terrainReader(terrain);
    if (!reader) return null;
    const region = terrain.region;
    const perKind = new Map();
    const describe = (kind) => {
      let entry = perKind.get(kind);
      if (!entry) {
        const variant = terrainVariant(terrain, kind);
        entry = {
          label: terrainLabel(terrain, kind),
          variant,
          tile: terrainTileUrl(spriteManifest, region, variant),
        };
        perKind.set(kind, entry);
      }
      return entry;
    };
    const cells = [];
    for (let row = 0; row < gridCols; row++) {
      for (let col = 0; col < gridCols; col++) {
        const kind = reader.kindAt(leftX + col, topY - row);
        if (!kind) continue;
        const info = describe(kind);
        if (kind === 'open' && !info.tile) continue;
        cells.push({
          index: row * gridCols + col,
          row,
          col,
          kind,
          elevation: reader.elevationAt(leftX + col, topY - row),
          variant: info.variant,
          tile: info.tile,
          title: kind === 'open' ? undefined : info.label,
        });
      }
    }
    return cells;
  }, [terrain, gridCols, leftX, topY, spriteManifest]);

  // Living enemies drive the off-screen edge markers.
  const livingEnemies = useMemo(
    () => (combat?.enemies || []).filter(isLiving),
    [combat?.enemies]
  );

  // The arena boundary rectangle is worth drawing exactly when the viewport
  // pokes outside the arena on some side — i.e. when the edge is on screen.
  const showArenaBounds = leftX < 0
    || topY > resolvedMapSize - 1
    || leftX + gridCols > resolvedMapSize
    || topY - gridCols + 1 < 0;

  // -------------------------------------------------------------------------
  // Enemies tab: flat list view
  // -------------------------------------------------------------------------
  if (tab === 'enemies') {
    // livingEnemies, not combat.enemies: the roster keeps HP-0 entries for a
    // beat, and the map already drops them. Passing the raw list left corpses
    // listed as "HP: 0 / 30" with their last move after the token was gone.
    return <EnemiesList enemies={livingEnemies} />;
  }

  return (
    <div
      ref={gridContainerRef}
      onClick={handleGridClick}
      style={{
        position: 'relative', width: '100%', height: '100%',
        backgroundColor: colors.bg.main, overflow: 'hidden',
        touchAction: 'none', cursor: 'grab',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        // Square-cell mode measures the largest square that fits via container
        // query units, so `containerType` only exists while the flag is on.
        containerType: squareCells ? 'size' : undefined,
      }}
    >
      {/*
        The map viewport. Every layer below sizes itself in percentages of this
        box, so making it square is all it takes for one grid cell to be square.
        Off (the default) it fills the panel, and cells inherit the panel's
        aspect ratio — a 9x9 arena renders as a rectangle and diagonals read
        shorter than they are. On, the map is letterboxed to a square at the
        cost of unused space in a tall panel. Feature-flagged because that
        trade is a look-at-it-both-ways call, not an obvious win.
      */}
      <div
        style={squareCells
          ? { position: 'relative', width: 'min(100cqw, 100cqh)', height: 'min(100cqw, 100cqh)' }
          : { position: 'absolute', inset: 0 }}
        data-testid="battlefield-viewport"
        // The square sizing is a `min()` of container-query units, which jsdom
        // cannot hold — this attribute is what tests and QA scripts assert the
        // active layout on.
        data-layout={squareCells ? 'square' : 'fill'}
      >
      {/*
        panLayerRef: touch-drag pan offset layer. Translates independently of the
        RAF camera so finger panning doesn't interfere with smooth camera animation.
        contentDivRef sits inside it and receives the per-frame sub-cell transform.
      */}
      <div ref={panLayerRef} style={{ position: 'absolute', inset: 0 }}>
      <div ref={contentDivRef} style={{ position: 'absolute', inset: 0, willChange: 'transform' }}>
        <GridBackgroundLayer cells={gridBgCells} gridCols={gridCols} />

        {terrainCells && (
          <TerrainLayer cells={terrainCells} gridCols={gridCols} isCompact={isCompact} />
        )}

        {/* Arena extent marker — faint dashed rectangle around the real map,
            drawn whenever the viewport reaches past the world's edge, so the
            boundary is visible without having to change view mode. */}
        {showArenaBounds && (
          <div style={{ position: 'absolute', inset: 0, padding: spacing.sm, pointerEvents: 'none' }}>
            <div style={{
              position: 'absolute',
              left: `${(-leftX / gridCols) * 100}%`,
              top: `${((topY - (resolvedMapSize - 1)) / gridCols) * 100}%`,
              width: `${(resolvedMapSize / gridCols) * 100}%`,
              height: `${(resolvedMapSize / gridCols) * 100}%`,
              border: `1px dashed ${colors.alpha.primary[40]}`,
              borderRadius: '2px',
              zIndex: 2,
            }} />
          </div>
        )}

        <BreadcrumbLayer breadcrumbs={breadcrumbs} />

        {/* Jean gets a spotlight whenever tokens are too small to pick her out
            by her star alone. */}
        {isCompact && combat?.player && (
          <JeanSpotlight player={combat.player} getEntityStyle={getEntityStyle} />
        )}

        <ThreatLineLayer
          entitiesToRender={entitiesToRender}
          getEntityCenterPct={getEntityCenterPct}
        />

        {selectedEntity && (
          <RangeRingLayer
            entity={selectedEntity}
            getEntityStyle={getEntityStyle}
            gridCols={gridCols}
          />
        )}

        <EntityLayer
          entitiesToRender={entitiesToRender}
          activeAnimations={activeAnimations}
          hoveredEntity={hoveredEntity}
          selectedEntity={selectedEntity}
          hoveredTargetId={hoveredTargetId}
          isCompact={isCompact}
          onHoverEntity={setHoveredEntity}
          onClearHover={handleClearHover}
          onSelectEntity={setSelectedEntity}
          spriteManifest={spriteManifest}
          combatSpeed={combatSpeed}
        />

        <EffectsLayer
          activeAnimations={activeAnimations}
          getEntityStyle={getEntityStyle}
          combat={combat}
        />

        <DeathAnimationLayer dyingEntities={dyingEntities} getEntityStyle={getEntityStyle} />
      </div>
      </div>{/* end panLayerRef */}

      {/* Edge markers for enemies outside the viewport. Outside panLayerRef so
          they stay pinned to the visible border while the map is panned, but
          inside the viewport box so they hug the map edge rather than the
          panel edge when the map is letterboxed.

          Known limitation: the on/off-screen test uses the unpanned
          leftX/topY, so after a drag (capped at 40% of the box, ~5 cells) the
          marker set can disagree with what is actually visible by a few
          columns. Do NOT "fix" this by adding touchPanRef to the memo deps —
          it is a ref precisely so dragging does not re-render per frame, so
          that edit would compile, look right, and do nothing. */}
      <OffScreenMarkers
        enemies={livingEnemies}
        leftX={leftX}
        topY={topY}
        gridCols={gridCols}
      />

      {/* Terrain legend: region name plus every kind on this field and what
          it does. Pinned to the viewport like the edge markers so it stays
          put while the map pans. */}
      {terrainActive && <TerrainLegend terrain={terrain} />}
      </div>{/* end viewport */}

      {/* SelectedEntityPanel and overlays are panel chrome — they sit outside
          the viewport box so they stay pinned to the panel's own corners. */}
      {selectedEntity && (
        <SelectedEntityPanel
          entity={selectedEntity}
          onClose={handleCloseSelectedEntity}
        />
      )}

      {ANIM_DEBUG && (
        <div
          className="absolute top-1 left-1 z-[200] pointer-events-none text-[10px] font-mono px-1.5 py-0.5 rounded bg-black/80 text-lime-400 select-none"
          aria-hidden="true"
        >
          anim: {activeAnimations.length
            ? activeAnimations.map((a) => `${a.type}${a.phase ? `/${a.phase}` : ''}`).join(' + ')
            : 'idle'}
          {` · q${animationQueue.length}`}
        </div>
      )}

      {/* Pan affordance. While centered this is a hint; once the player has
          dragged, it becomes the way back — pan is sticky now, so without it
          there would be no route home from a corner of the arena. */}
      {isPanned ? (
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); recenterPan(); }}
          style={{
            position: 'absolute', bottom: '24px', right: '6px',
            zIndex: 155, pointerEvents: 'auto',
            fontSize: '10px', fontFamily: 'monospace', fontWeight: 'bold',
            color: colors.secondary, backgroundColor: 'rgba(0,0,0,0.85)',
            border: `1px solid ${colors.secondary}`, borderRadius: '3px',
            padding: '2px 6px', cursor: 'pointer', userSelect: 'none',
          }}
          title="Recenter the map"
        >
          ⌖ recenter
        </button>
      ) : (
        <div
          style={{
            position: 'absolute', bottom: '28px', right: '6px',
            zIndex: 140, pointerEvents: 'none',
            fontSize: '9px', fontFamily: 'monospace',
            color: 'rgba(255,255,255,0.35)', userSelect: 'none',
            display: 'flex', alignItems: 'center', gap: '3px',
          }}
          aria-label="Drag to pan the map"
        >
          <span>drag to pan</span>
        </div>
      )}
    </div>
  );
}

export default React.memo(BattlefieldGrid);

// React.memo wrapping an arrow function produces an anonymous component,
// which shows up as "Anonymous" in DevTools and in component stack traces.
CombatantMarker.displayName = 'CombatantMarker'
EnemiesList.displayName = 'EnemiesList'
BreadcrumbLayer.displayName = 'BreadcrumbLayer'
EntityLayer.displayName = 'EntityLayer'
SelectedEntityPanel.displayName = 'SelectedEntityPanel'
GridBackgroundLayer.displayName = 'GridBackgroundLayer'
EntityTooltip.displayName = 'EntityTooltip'
OffScreenMarkers.displayName = 'OffScreenMarkers'
EffectsLayer.displayName = 'EffectsLayer'
JeanSpotlight.displayName = 'JeanSpotlight'
DeathAnimationLayer.displayName = 'DeathAnimationLayer'
ThreatLineLayer.displayName = 'ThreatLineLayer'
RangeRingLayer.displayName = 'RangeRingLayer'
