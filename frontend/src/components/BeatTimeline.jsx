import { useMemo } from 'react';

import { colors, spacing } from '../styles/theme';
import { categoryIcon } from '../utils/categories';
import { buildBeatTimelineColumns, DEFAULT_MAX_COLUMNS } from '../utils/beatTimeline';

/**
 * Horizontal beat-timeline strip — a schedule of what resolves when, shown
 * alongside the "Beat N / X standing" counter. Modelled on FFX's CTB timeline and
 * The Banner Saga's turn-order strip (see CLAUDE.md): the player reads who
 * acts next and how their own choice shifts the order, instead of deriving it
 * from the countdown badges scattered across the map.
 *
 * On by default, behind the `beatTimeline` flag so it stays switchable from
 * the settings dialog. The two strips are complementary, not alternatives:
 * this one carries ordering, the counter carries the beat number and how many
 * enemies are left. Turning the flag off drops only the schedule.
 */
export default function BeatTimeline({ combat }) {
  const columns = useMemo(() => buildBeatTimelineColumns(combat, DEFAULT_MAX_COLUMNS), [combat]);

  if (columns.length === 0) {
    return (
      <div
        style={{
          fontSize: '10px', fontFamily: 'monospace', color: colors.text.muted,
          letterSpacing: '0.05em', textTransform: 'uppercase', padding: '2px 0',
        }}
        aria-label="Beat timeline"
      >
        No moves committed yet
      </div>
    );
  }

  return (
    <div
      style={{
        display: 'flex', alignItems: 'flex-end', gap: spacing.sm,
        overflowX: 'auto', padding: '2px 2px 4px',
      }}
      aria-label="Beat timeline"
      role="list"
    >
      {columns.map(({ beat, entries }) => (
        <div
          key={beat}
          role="listitem"
          style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '3px', flex: '0 0 auto' }}
        >
          {/* Collisions stack vertically within the column, soonest-priority
              order already applied (Jean, allies, enemies) by the util —
              plain 'column' so that priority order reads top-to-bottom,
              matching the sort order rather than reversing it. */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
            {entries.map((entry) => (
              <TimelineMarker key={entry.key} entry={entry} />
            ))}
          </div>
          <div style={{ fontSize: '9px', color: colors.text.dim, fontFamily: 'monospace', whiteSpace: 'nowrap' }}>
            {beat === 1 ? 'next' : `+${beat}`}
          </div>
        </div>
      ))}
    </div>
  );
}

function TimelineMarker({ entry }) {
  const isFriendly = entry.alignment === 'friendly';
  const baseColor = isFriendly ? colors.primary : colors.danger;
  const bg = isFriendly ? colors.alpha.primary[20] : colors.alpha.danger[20];

  return (
    <div
      title={`${entry.name} — ${entry.moveName} (lands in ${entry.beat} beat${entry.beat === 1 ? '' : 's'})`}
      style={{
        display: 'flex', alignItems: 'center', gap: '4px',
        padding: entry.isPlayer ? '4px 8px' : '2px 6px',
        borderRadius: '4px',
        border: `${entry.isPlayer ? 2 : 1}px solid ${baseColor}`,
        backgroundColor: bg,
        // Jean's own resolving move is the most prominent marker on the
        // strip — bigger padding/border above, a glow here, on top of the
        // shared friend/foe color coding everything else uses.
        boxShadow: entry.isPlayer ? `0 0 8px 1px ${colors.alpha.primary[40]}` : 'none',
        fontSize: entry.isPlayer ? '11px' : '9px',
        fontWeight: entry.isPlayer ? 'bold' : 'normal',
        color: colors.text.main,
        whiteSpace: 'nowrap',
        fontFamily: 'monospace',
      }}
    >
      <span aria-hidden="true">{categoryIcon(entry.category)}</span>
      <span>{entry.isPlayer ? 'Jean' : entry.name}</span>
    </div>
  );
}
