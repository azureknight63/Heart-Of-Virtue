import { useEffect, useState } from 'react';
import { CLIP_FPS, LOOPING_CLIPS, facingRow, spriteAssetUrl } from '../utils/sprites';

/**
 * Advance a frame counter for `clip` at its frame rate. Loops wrap; one-shot
 * clips (attack, hurt, death, ...) hold their last frame. The counter resets
 * whenever the clip changes so an attack always starts from its wind-up.
 */
export function useSpriteFrame(clip, frames, running = true) {
  // The counter is stored with the clip it belongs to, so a clip change reads
  // as frame 0 immediately (derived during render) instead of needing a
  // reset-in-effect that would render one stale frame first.
  const [tick, setTick] = useState({ clip, frame: 0 });
  const frame = tick.clip === clip ? tick.frame : 0;
  useEffect(() => {
    if (!running || !frames || frames <= 1) return undefined;
    const fps = CLIP_FPS[clip] || 6;
    const loop = LOOPING_CLIPS.has(clip);
    const id = setInterval(() => {
      setTick((t) => {
        const current = t.clip === clip ? t.frame : 0;
        if (current + 1 < frames) return { clip, frame: current + 1 };
        return loop ? { clip, frame: 0 } : (t.clip === clip ? t : { clip, frame: current });
      });
    }, 1000 / fps);
    return () => clearInterval(id);
  }, [clip, frames, running]);
  return frame;
}

/**
 * One animated sprite drawn from a manifest sheet set.
 *
 * The strip for `clip` is `frames` columns x `rows` facings; the frame is
 * selected with percentage background-position (valid for any cell size, so
 * the token scales with the grid) and the east facing mirrors the west row.
 * When the requested clip has no sheet the idle strip stands in, so a partial
 * delivery never blanks a token.
 */
export default function SpriteToken({ sprite, clip = 'idle', facing = 'S', rows = ['south', 'west', 'north'], running = true, className = '', style = {} }) {
  const clipEntry = sprite?.clips?.[clip] || sprite?.clips?.idle;
  const activeClip = sprite?.clips?.[clip] ? clip : 'idle';
  const frames = Math.max(1, Number(clipEntry?.frames) || 1);
  const sheetRows = Math.max(1, Number(clipEntry?.rows) || rows.length);
  const frame = useSpriteFrame(activeClip, frames, running);
  if (!clipEntry?.file) return null;
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
        backgroundImage: `url("${spriteAssetUrl(clipEntry.file)}")`,
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
