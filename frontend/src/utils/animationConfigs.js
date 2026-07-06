/**
 * Animation configs shared between the battlefield grid and the combat-log
 * reveal loop. Keeping these in a single module means the log can hold off on
 * advancing to the next line while an animation is still playing, so text
 * describing an outcome doesn't appear before the user sees it.
 *
 * Every castable move in the engine declares a `web_animation` type from this
 * table (src/moves — see the backend contract test); unknown types fall back
 * to `pulse` at play time so a new backend type can never break the client.
 *
 * Config shape (all fields except `duration` and `phases` are optional):
 *   duration      total ms — must equal the sum of phase durations
 *   phases        [{ name, duration }] — played strictly in sequence
 *   motion        how the SOURCE token travels during the animation:
 *     windupPhase   phase in which the token recoils away from the target
 *     recoil        fraction of one cell to pull back during windupPhase
 *     travelPhase   phase in which the token moves toward the target
 *     travel        fraction of source→target distance covered (1 = on top)
 *     easing        CSS timing function for the travel transition
 *     spinDegrees   full rotation applied during travelPhase (spin attacks)
 *   source        per-phase marker styling for the acting entity:
 *     { [phaseName]: { scale, glow } }   glow = CSS color for a box-shadow halo
 *   target        treatment of the target marker during the 'impact' phase:
 *     'strike'      outcome-dependent flash (hit red / miss blur / parry gold)
 *     { glow, scale }  fixed styling (buff/debuff/drain style effects)
 *   shake         true → target cell shakes during the impact phase
 *   effect        overlay drawn by the battlefield effects layer:
 *     kind          'projectile' | 'ring' | 'rise' | 'drain'
 *     phase         phase during which the overlay plays
 *     color         primary CSS color of the overlay
 *     size          ring end-radius / particle size multiplier (default 1)
 *     anchor        'source' (default) | 'target' — which cell a ring sits on
 *   sfx           { [phaseName]: cue } — cue is an sfx_<name>.wav basename, or
 *                 the special value 'outcome' which resolves via the
 *                 animation's outcome (hit/miss/parry) at play time
 */

/** Map an attack outcome to the corresponding impact SFX cue name. */
export const impactSfxFor = (outcome) => {
  switch (outcome) {
    case 'miss': return 'attack_miss';
    case 'parry':
    case 'block':
    case 'deflect':
      return 'attack_parry';
    case 'hit':
    default:
      return 'attack_hit';
  }
};

export const ANIMATION_CONFIGS = {
  // --- Melee strikes ---------------------------------------------------
  // Standard swing: readable windup, snappy accelerating strike, held
  // impact so the outcome flash registers, relaxed return.
  attack: {
    duration: 800,
    phases: [
      { name: 'windup', duration: 200 },
      { name: 'strike', duration: 160 },
      { name: 'impact', duration: 220 },
      { name: 'return', duration: 220 },
    ],
    motion: {
      windupPhase: 'windup',
      recoil: 0.18,
      travelPhase: 'strike',
      travel: 0.65,
      easing: 'cubic-bezier(0.5, 0, 0.9, 0.4)',
    },
    source: {
      windup: { scale: 1.12 },
      strike: { scale: 1.08 },
    },
    target: 'strike',
    sfx: { strike: 'attack_swipe', impact: 'outcome' },
  },

  // Fast jabs and bites: everything compressed, small travel.
  quick_attack: {
    duration: 500,
    phases: [
      { name: 'windup', duration: 90 },
      { name: 'strike', duration: 110 },
      { name: 'impact', duration: 160 },
      { name: 'return', duration: 140 },
    ],
    motion: {
      windupPhase: 'windup',
      recoil: 0.1,
      travelPhase: 'strike',
      travel: 0.55,
      easing: 'cubic-bezier(0.6, 0, 1, 0.6)',
    },
    source: {
      windup: { scale: 1.06 },
      strike: { scale: 1.05 },
    },
    target: 'strike',
    sfx: { strike: 'attack_swipe', impact: 'outcome' },
  },

  // Slow crushing blows: long telegraphed windup with a building glow,
  // violent strike, extended impact with target shake.
  heavy_attack: {
    duration: 1050,
    phases: [
      { name: 'windup', duration: 380 },
      { name: 'strike', duration: 150 },
      { name: 'impact', duration: 280 },
      { name: 'return', duration: 240 },
    ],
    motion: {
      windupPhase: 'windup',
      recoil: 0.25,
      travelPhase: 'strike',
      travel: 0.75,
      easing: 'cubic-bezier(0.7, 0, 1, 0.5)',
    },
    source: {
      windup: { scale: 1.28, glow: 'rgba(255, 136, 0, 0.85)' },
      strike: { scale: 1.15 },
    },
    target: 'strike',
    shake: true,
    effect: { kind: 'ring', phase: 'impact', color: 'rgba(255, 136, 0, 0.8)', size: 1.2, anchor: 'target' },
    sfx: { strike: 'attack_swipe', impact: 'outcome' },
  },

  // Linear thrusts (spears, rapiers, backstabs): short pull-back then a
  // near-instant straight-line stab covering most of the distance.
  pierce: {
    duration: 660,
    phases: [
      { name: 'windup', duration: 160 },
      { name: 'strike', duration: 120 },
      { name: 'impact', duration: 200 },
      { name: 'return', duration: 180 },
    ],
    motion: {
      windupPhase: 'windup',
      recoil: 0.22,
      travelPhase: 'strike',
      travel: 0.8,
      easing: 'cubic-bezier(0.9, 0, 1, 0.7)',
    },
    source: {
      windup: { scale: 1.05 },
      strike: { scale: 1.02 },
    },
    target: 'strike',
    sfx: { strike: 'attack_swipe', impact: 'outcome' },
  },

  // Spinning area attacks (whirl, sweep, halberd spin, reap): the source
  // token rotates a full turn while an arc ring flares around it.
  sweep: {
    duration: 960,
    phases: [
      { name: 'windup', duration: 180 },
      { name: 'spin', duration: 420 },
      { name: 'impact', duration: 200 },
      { name: 'return', duration: 160 },
    ],
    motion: {
      windupPhase: 'windup',
      recoil: 0,
      travelPhase: 'spin',
      travel: 0,
      spinDegrees: 360,
      easing: 'cubic-bezier(0.4, 0, 0.6, 1)',
    },
    source: {
      windup: { scale: 1.1 },
      spin: { scale: 1.15, glow: 'rgba(0, 255, 255, 0.6)' },
    },
    target: 'strike',
    effect: { kind: 'ring', phase: 'spin', color: 'rgba(0, 255, 255, 0.7)', size: 1.4 },
    sfx: { spin: 'attack_swipe', impact: 'outcome' },
  },

  // Full-body rush (bull charge, flanking assault): crouch, then barrel
  // nearly the whole way into the target.
  charge: {
    duration: 1040,
    phases: [
      { name: 'windup', duration: 260 },
      { name: 'rush', duration: 320 },
      { name: 'impact', duration: 240 },
      { name: 'return', duration: 220 },
    ],
    motion: {
      windupPhase: 'windup',
      recoil: 0.15,
      travelPhase: 'rush',
      travel: 0.85,
      easing: 'cubic-bezier(0.5, 0, 0.8, 0.3)',
    },
    source: {
      windup: { scale: 0.9, glow: 'rgba(255, 136, 0, 0.6)' },
      rush: { scale: 1.15 },
    },
    target: 'strike',
    shake: true,
    sfx: { rush: 'attack_swipe', impact: 'outcome' },
  },

  // --- Ranged ----------------------------------------------------------
  // Bow/crossbow shots and spit attacks: brief aim hold, a projectile dot
  // streaks from source to target, outcome flash on arrival.
  projectile: {
    duration: 840,
    phases: [
      { name: 'aim', duration: 220 },
      { name: 'launch', duration: 280 },
      { name: 'impact', duration: 200 },
      { name: 'return', duration: 140 },
    ],
    motion: {
      windupPhase: 'launch',
      recoil: 0.08,
    },
    source: {
      aim: { scale: 1.08, glow: 'rgba(255, 255, 255, 0.5)' },
    },
    target: 'strike',
    effect: { kind: 'projectile', phase: 'launch', color: '#ffee88' },
    sfx: { launch: 'attack_swipe', impact: 'outcome' },
  },

  // --- Area bursts -------------------------------------------------------
  // Ground slams and surging waves: rise, slam down, expanding shockwave
  // ring washes outward over everything nearby.
  shockwave: {
    duration: 960,
    phases: [
      { name: 'windup', duration: 260 },
      { name: 'slam', duration: 160 },
      { name: 'impact', duration: 360 },
      { name: 'return', duration: 180 },
    ],
    source: {
      windup: { scale: 1.3, glow: 'rgba(255, 200, 80, 0.7)' },
      slam: { scale: 0.85 },
    },
    target: 'strike',
    shake: true,
    effect: { kind: 'ring', phase: 'impact', color: 'rgba(255, 200, 80, 0.8)', size: 2.2 },
    sfx: { slam: 'attack_swipe', impact: 'outcome' },
  },

  // --- Repositioning -----------------------------------------------------
  // Advances, withdrawals, tactical movement: the grid position transition
  // does the real travel — this adds an anticipatory squash and a lime
  // motion glow so the move reads as deliberate rather than a teleport.
  dash: {
    duration: 500,
    phases: [
      { name: 'windup', duration: 120 },
      { name: 'dashout', duration: 240 },
      { name: 'return', duration: 140 },
    ],
    source: {
      windup: { scale: 0.88 },
      dashout: { scale: 1.1, glow: 'rgba(0, 255, 0, 0.6)' },
    },
    sfx: { dashout: 'move' },
  },

  // --- Stances & self-effects ---------------------------------------------
  // Dodges, parries, braces, bulwarks: a cyan shield halo raised and held
  // long enough to read as a defensive posture (retro terminal palette).
  defend: {
    duration: 760,
    phases: [
      { name: 'windup', duration: 180 },
      { name: 'hold', duration: 420 },
      { name: 'return', duration: 160 },
    ],
    source: {
      windup: { scale: 1.1, glow: 'rgba(0, 255, 255, 0.55)' },
      hold: { scale: 1.05, glow: 'rgba(0, 255, 255, 0.75)' },
    },
    effect: { kind: 'ring', phase: 'hold', color: 'rgba(0, 255, 255, 0.55)', size: 0.9 },
    sfx: { windup: 'attack_parry' },
  },

  // War cries, oaths, insights: gold energy gathers then bursts upward.
  buff: {
    duration: 780,
    phases: [
      { name: 'windup', duration: 260 },
      { name: 'burst', duration: 320 },
      { name: 'return', duration: 200 },
    ],
    source: {
      windup: { scale: 1.08, glow: 'rgba(255, 215, 0, 0.6)' },
      burst: { scale: 1.22, glow: 'rgba(255, 215, 0, 0.95)' },
    },
    effect: { kind: 'rise', phase: 'burst', color: '#ffd700' },
    sfx: { burst: 'level_up' },
  },

  // Marks, hexes, stuns aimed at a target: purple flash sinks onto them
  // (theme.js colors.special #9944ff — the special/supernatural hue).
  debuff: {
    duration: 800,
    phases: [
      { name: 'windup', duration: 240 },
      { name: 'impact', duration: 380 },
      { name: 'return', duration: 180 },
    ],
    source: {
      windup: { scale: 1.06, glow: 'rgba(153, 68, 255, 0.7)' },
    },
    target: { glow: 'rgba(153, 68, 255, 0.9)', scale: 0.92 },
    sfx: { impact: 'status_hit' },
  },

  // Life/soul drain: a particle stream flows from the target back to the
  // caster while the target withers and the caster brightens.
  drain: {
    duration: 900,
    phases: [
      { name: 'windup', duration: 240 },
      { name: 'impact', duration: 460 },
      { name: 'return', duration: 200 },
    ],
    source: {
      impact: { scale: 1.12, glow: 'rgba(170, 255, 170, 0.8)' },
    },
    target: { glow: 'rgba(153, 68, 255, 0.9)', scale: 0.88 },
    effect: { kind: 'drain', phase: 'impact', color: 'rgba(170, 255, 170, 0.9)' },
    sfx: { impact: 'status_hit' },
  },

  // Rest and recovery: soft green mending glow.
  heal: {
    duration: 800,
    phases: [
      { name: 'windup', duration: 240 },
      { name: 'mend', duration: 380 },
      { name: 'return', duration: 180 },
    ],
    source: {
      windup: { scale: 1.04, glow: 'rgba(80, 255, 120, 0.5)' },
      mend: { scale: 1.1, glow: 'rgba(80, 255, 120, 0.85)' },
    },
    effect: { kind: 'rise', phase: 'mend', color: '#66ff88' },
    sfx: { mend: 'heal' },
  },

  // --- Generic -------------------------------------------------------------
  // Fallback for utility actions (Check, Wait, item use) and any animation
  // type the client doesn't recognize.
  pulse: {
    duration: 400,
    phases: [
      { name: 'expand', duration: 200 },
      { name: 'contract', duration: 200 },
    ],
    source: {
      expand: { scale: 1.25, glow: 'rgba(255, 215, 0, 0.9)' },
    },
  },

  death: {
    duration: 700,
    phases: [
      { name: 'explode', duration: 400 },
      { name: 'fade', duration: 300 },
    ],
  },
};

/** Resolve a config for the given type, falling back to `pulse` when unknown. */
export const getAnimationConfig = (type) => ANIMATION_CONFIGS[type] || ANIMATION_CONFIGS.pulse;

/** Duration in ms for an animation of the given type (default 0 when unknown). */
export const getAnimationDuration = (type) => ANIMATION_CONFIGS[type]?.duration ?? 0;
