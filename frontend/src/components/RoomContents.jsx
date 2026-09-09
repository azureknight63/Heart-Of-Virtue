import { colors, spacing } from '../styles/theme'
import { renderTextWithLinks, getEntityColor } from '../utils/entityUtils'
import { hostileOnlyTokenFor } from '../utils/combatEntities'
import HostilityChip from './HostilityChip'

/**
 * @file Room contents rendered inline with the room description, in the
 * narrative format the terminal game used.
 */

/**
 * Hostility marker for one content line, or null.
 *
 * Only the type guard is this panel's business. The badge policy itself is
 * documented once, on `HOSTILITY_TOKENS` (utils/combatEntities.js), and the
 * room's hostiles-only variant of it on `hostileOnlyTokenFor` beside it — one
 * place to read the rule, one entry point to ask it (issue #558).
 */
function hostileMarkerFor(content) {
  if (content.type !== 'npc') return null
  return hostileOnlyTokenFor(content.entity)
}

export default function RoomContents({ location, onInteract }) {
  if (!location) return null

  const items = (location.items || []).map(i => ({ ...i, type: 'item' }))
  const npcs = (location.npcs || []).map(n => ({ ...n, type: 'npc' }))
  const objects = (location.objects || []).map(o => ({ ...o, type: 'object' }))

  const allEntities = [...npcs, ...items, ...objects].filter(e => !e.hidden)

  // Build content descriptions array
  const contentDescriptions = []

  // NPCs and objects describe themselves the same way -- an `idle_message`,
  // or nothing at all. Items do not (they carry `announce` and a fallback),
  // which is why only these two share a helper. Call order is load-bearing:
  // the render depends on npc -> item -> object.
  const pushIdleLines = (entities, type) => entities.forEach(entity => {
    if (entity.idle_message) {
      contentDescriptions.push({
        type,
        text: entity.idle_message,
        name: entity.name,
        entity,
      })
    }
  })

  pushIdleLines(npcs, 'npc')

  // Add items with announce messages
  items.forEach(item => {
    if (item.hidden) return

    const text = item.announce || `There is a ${item.name} here.`
    contentDescriptions.push({
      type: 'item',
      text: text,
      name: item.name,
      entity: item,
      id: item.id
    })
  })

  pushIdleLines(objects, 'object')

  // Build combined description
  const roomDescriptionText = location.description
  const hasContentDescriptions = contentDescriptions.length > 0

  return (
    <div className="border-l-4 border-lime rounded px-2.5 py-2.5 text-lime text-sm leading-relaxed font-serif" style={{
      backgroundColor: 'rgba(0,100,50,0.2)',
    }}>
      {/* Room narrative and content all together */}

      {/* Combined narrative: room description + content descriptions */}
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        gap: spacing.md,
      }}>
        <div className="text-lg text-[#00ddaa]" style={{ lineHeight: '1.6' }}>
          {roomDescriptionText}
        </div>

        {/* Content descriptions immediately following */}
        {hasContentDescriptions && (
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            gap: spacing.xs,
          }}>
            {contentDescriptions.map((content, idx) => {
              const hostile = hostileMarkerFor(content)
              return (
                <div
                  key={idx}
                  data-testid="room-content-line"
                  style={{
                    color: hostile ? hostile.color : getEntityColor(content.type),
                    fontFamily: 'serif',
                    fontStyle: 'italic',
                    fontSize: '16px',
                    lineHeight: '1.5',
                  }}
                >
                  {renderTextWithLinks(
                    content.text.startsWith(' ') ? `${content.name}${content.text}` : content.text,
                    allEntities,
                    onInteract,
                    content.entity
                  )}
                  {hostile && (
                    <HostilityChip token={hostile} variant="inline" />
                  )}
                </div>
              )
            })}
          </div>
        )}

        {/* Empty state */}
        {!hasContentDescriptions && (
          <div style={{
            color: colors.text.muted,
            fontSize: '16px',
            fontStyle: 'italic',
          }}>
            (Nothing else here...)
          </div>
        )}
      </div>
    </div>
  )
}
