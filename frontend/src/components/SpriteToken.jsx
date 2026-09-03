import { useEffect, useState } from 'react';
import {
  CLIP_FPS, DEFAULT_CLIP_FPS, DEFAULT_FACINGS, LOOPING_CLIPS, SPRITE_CLIPS,
  facingRow, spriteAssetUrl,
} from '../utils/sprites';

const MAX_FRAMES = 64;
const MIN_TICK_MS = 40;

const clipFps = (clip) => (
  Object.prototype.hasOwnProperty.call(CLIP_FPS, clip) ? CLIP_FPS[clip] : DEFAULT_CLIP_FPS
);

/**
 * Advance a frame counter for `clip` at its frame rate, scaled by `speed`
 * (the player's combat-speed multiplier, so a 2x fight plays its swing
 * frames before the animation phase ends). Loops wrap; one-shot clips
 * (attack, hurt, death, ...) hold their last frame and stop their timer.
 * The counter is stored with the clip it belongs to, so a clip change reads
 * as frame 0 immediately (derived during render).
 */
export function useSpriteFrame(clip, frames, running = true, speed = 1) {
  const [tick, setTick] = useState({ clip, frame: 0 });
  const frame = tick.clip === clip ? tick.frame : 0;
  useEffect(() => {
    if (!running || !frames || frames <= 1) return undefined;
    const rate = clipFps(clip) * (Number(speed) > 0 ? Number(speed) : 1);
    const loop = LOOPING_CLIPS.has(clip);
    const id = setInterval(() => {
      setTick((t) => {
        const current = t.clip === clip ? t.frame : 0;
        if (current + 1 < frames) return { clip, frame: current + 1 };
        if (loop) return { clip, frame: 0 };
        // Held on the last frame: nothing more to draw, stop ticking.
        clearInterval(id);
        return t.clip === clip ? t : { clip, frame: current };
      });
    }, Math.max(MIN_TICK_MS, 1000 / rate));
    return () => clearInterval(id);
  }, [clip, frames, running, speed]);
  return frame;
}

const boundedCount = (value, fallback) => {
  const n = Math.trunc(Number(value));
  return Number.isFinite(n) && n >= 1 ? Math.min(MAX_FRAMES, n) : fallback;
};

/**
 * One animated sprite drawn from a manifest sheet set.
 *
 * The strip for `clip` is `frames` columns x `rows` facings; the frame is
 * selected with percentage background-position (valid for any cell size, so
 * the token scales with the grid) and the east facing mirrors the west row.
 * When the requested clip has no sheet the idle strip stands in, so a partial
 * delivery never blanks a token.
 */
export default function SpriteToken({
  sprite,
  clip = 'idle',
  facing = 'S',
  rows = DEFAULT_FACINGS,
  running = true,
  speed = 1,
  className = '',
  style = {},
}) {
  const wanted = SPRITE_CLIPS.includes(clip) ? clip : 'idle';
  const requested = sprite?.clips?.[wanted];
  const clipEntry = requested || sprite?.clips?.idle;
  const activeClip = requested ? wanted : 'idle';
  const frames = boundedCount(clipEntry?.frames, 1);
  const sheetRows = boundedCount(clipEntry?.rows, rows.length);
  const frame = useSpriteFrame(activeClip, frames, running, speed);
  const url = spriteAssetUrl(clipEntry?.file);
  if (!url) return null;
  const { row, mirror } = facingRow(facing, rows);
  const x = frames > 1 ? (frame / (frames - 1)) * 100 : 0;
  const y = sheetRows > 1 ? (Math.min(row, sheetRows - 1) / (sheetRows - 1)) * 100 : 0;
  return (
    <div
      data-testid="sprite-token"
      data-clip={activeClip}
      data-frame={frame}
      data-row={row}
      data-mirror={mirror ? '1' : '0'}
      className={className}
      style={{
        width: '100%',
        height: '100%',
        backgroundImage: `url("${url}")`,
        backgroundRepeat: 'no-repeat',
        backgroundSize: `${frames * 100}% ${sheetRows * 100}%`,
        backgroundPosition: `${x}% ${y}%`,
        imageRendering: 'pixelated',
        transform: mirror ? 'scaleX(-1)' : 'none',
        pointerEvents: 'none',
        ...style,
      }}
    />
  );
}
