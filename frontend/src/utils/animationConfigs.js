/**
 * Animation configs shared between the battlefield grid and the combat-log
 * reveal loop. Keeping these in a single module means the log can hold off on
 * advancing to the next line while an animation is still playing, so text
 * describing an outcome doesn't appear before the user sees it.
 */
export const ANIMATION_CONFIGS = {
  attack: {
    duration: 800,
    phases: [
      { name: 'windup', duration: 100 },
      { name: 'strike', duration: 300 },
      { name: 'impact', duration: 200 },
      { name: 'return', duration: 200 },
    ],
  },
  pulse: {
    duration: 400,
    phases: [
      { name: 'expand', duration: 200 },
      { name: 'contract', duration: 200 },
    ],
  },
  death: {
    duration: 700,
    phases: [
      { name: 'explode', duration: 400 },
      { name: 'fade', duration: 300 },
    ],
  },
};

/** Duration in ms for an animation of the given type (default 0 when unknown). */
export const getAnimationDuration = (type) => ANIMATION_CONFIGS[type]?.duration ?? 0;
