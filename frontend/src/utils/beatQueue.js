/**
 * Paced combat-beat playback (issue #436).
 *
 * The engine ships a move's beats in a burst; this controller plays them back
 * one at a time — each beat "holds" for its (speed-adjusted) animation duration
 * before the next starts, and each beat's SFX fire as a 75% partial stack. It's
 * the anti-desync gate: `onDrain` fires only when the queue empties, so the
 * caller defers applying authoritative `resolved` state / re-enabling input /
 * showing the victory dialog until playback has caught up.
 *
 * Timer functions are injected so tests drive it with fake timers. No React.
 */
import { scheduleSfxChain } from './combatTiming';

/**
 * Classify an incoming event seq against the last one seen:
 *  - 'duplicate': already processed (seq <= lastSeq) — ignore.
 *  - 'gap': one or more events were missed (seq > lastSeq + 1) — resync.
 *  - 'next': the expected next event.
 */
export function classifySeq(lastSeq, seq) {
  if (lastSeq == null) return 'next';
  if (seq <= lastSeq) return 'duplicate';
  if (seq > lastSeq + 1) return 'gap';
  return 'next';
}

export class BeatQueueController {
  constructor({
    playBeat,
    playSfx,
    beatSfxFor,
    durationForBeat,
    durationForCue,
    onDrain = () => {},
    getSpeed = () => 1,
    setTimer = setTimeout,
    clearTimer = clearTimeout,
  }) {
    this._playBeat = playBeat;
    this._playSfx = playSfx;
    this._beatSfxFor = beatSfxFor;
    this._durationForBeat = durationForBeat;
    this._durationForCue = durationForCue;
    this._onDrain = onDrain;
    this._getSpeed = getSpeed;
    this._setTimer = setTimer;
    this._clearTimer = clearTimer;

    this._queue = [];
    this._playing = false;
    this._holdTimer = null;
    this._sfxTimers = [];
  }

  /** True while a beat is animating or beats are waiting to play. */
  get isAnimating() {
    return this._playing || this._queue.length > 0;
  }

  /** Enqueue a beat and start playback if idle. */
  push(beat) {
    this._queue.push(beat);
    this._pump();
  }

  /**
   * Drop everything and cancel scheduled SFX (used on reconnect/resync so a
   * backlog of stale beats never plays or sounds, and on teardown).
   */
  clear() {
    if (this._holdTimer) this._clearTimer(this._holdTimer);
    this._holdTimer = null;
    this._cancelSfxTimers();
    this._queue = [];
    this._playing = false;
  }

  _cancelSfxTimers() {
    for (const t of this._sfxTimers) this._clearTimer(t);
    this._sfxTimers = [];
  }

  _pump() {
    if (this._playing) return;
    const beat = this._queue.shift();
    if (!beat) return;

    this._playing = true;
    this._playBeat(beat);
    this._scheduleBeatSfx(beat);

    const hold = this._durationForBeat(beat);
    this._holdTimer = this._setTimer(() => {
      this._holdTimer = null;
      this._playing = false;
      if (this._queue.length === 0) {
        this._onDrain();
      } else {
        this._pump();
      }
    }, hold);
  }

  _scheduleBeatSfx(beat) {
    const cues = this._beatSfxFor(beat);
    const schedule = scheduleSfxChain(
      cues,
      this._durationForCue,
      this._getSpeed()
    );
    for (const { cue, startMs } of schedule) {
      const timer = this._setTimer(() => this._playSfx(cue), startMs);
      this._sfxTimers.push(timer);
    }
  }
}
