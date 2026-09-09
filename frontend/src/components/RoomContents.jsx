import { colors, spacing } from '../styles/theme'
import { renderTextWithLinks, getEntityColor } from '../utils/entityUtils'
import { HOSTILITY_TOKENS, isHostileEntity } from '../utils/combatEntities'
import HostilityChip from './HostilityChip'

/**
 * RoomContents - Display integrated room description with contents
 * Displays room contents descriptions inline with the main room description,
 * matching the terminal game's narrative format
 */

/**
 * Hostility marker for one content line, or null.
 *
 * Only HOSTILES are marked here, unlike the combat target picker. A room NPC
 * with `is_hostile: false` is merely not aggressive — a villager, a merchant,
 * a passer-by — and is not the player's ally, so badging it "ALLY" would state
 * something the payload never said. The absence of the chip is the "nothing to
 * worry about" signal, and it is the chip (a word plus a glyph), not the
 * colour, that carries the warning (issue #558).
 */
function hostileMarkerFor(content) {
  if (content.type !== 'npc') return null
  return isHostileEntity(content.entity) === true ? HOSTILITY_TOKENS.hostile : null
}

export default function RoomContents({ location, onInteract }) {
  if (!location) return null

  const items = (location.items || []).map(i => ({ ...i, type: 'item' }))
  const npcs = (location.npcs || []).map(n => ({ ...n, type: 'npc' }))
  const objects = (location.objects || []).map(o => ({ ...o, type: 'object' }))

  const allEntities = [...npcs, ...items, ...objects].filter(e => !e.hidden)

  // Build content descriptions array
  const contentDescriptions = []

  // Add NPCs with idle messages
  npcs.forEach(npc => {
    if (npc.idle_message) {
      contentDescriptions.push({
        type: 'npc',
        text: npc.idle_message,
        name: npc.name,
        entity: npc,
      })
    }
  })

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

  // Add objects with idle messages
  objects.forEach(obj => {
    if (obj.idle_message) {
      contentDescriptions.push({
        type: 'object',
        text: obj.idle_message,
        name: obj.name,
        entity: obj,
      })
    }
  })

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
