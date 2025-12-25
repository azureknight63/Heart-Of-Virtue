/**
 * RoomContents - Display integrated room description with contents
 * Displays room contents descriptions inline with the main room description,
 * matching the terminal game's narrative format
 */

export default function RoomContents({ location, onInteract }) {
  if (!location) return null

  const items = (location.items || []).map(i => ({ ...i, type: 'item' }))
  const npcs = (location.npcs || []).map(n => ({ ...n, type: 'npc' }))
  const objects = (location.objects || []).map(o => ({ ...o, type: 'object' }))

  const allEntities = [...npcs, ...items, ...objects].filter(e => !e.hidden)

  // Helper to render text with clickable entity names
  const renderTextWithLinks = (text, preferredEntity = null) => {
    if (!text) return null

    // Sort entities by name length descending to avoid partial matches
    const sortedEntities = [...allEntities].sort((a, b) => b.name.length - a.name.length)

    // Create a regex that matches any of the entity names
    const names = sortedEntities.map(e => e.name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
    if (names.length === 0) return text

    const regex = new RegExp(`(${names.join('|')})`, 'gi')
    const parts = text.split(regex)

    return parts.map((part, i) => {
      // Find the entity for this part. If it matches the preferredEntity's name, use that specific one.
      let entity = null
      if (preferredEntity && preferredEntity.name.toLowerCase() === part.toLowerCase()) {
        entity = preferredEntity
      } else {
        entity = sortedEntities.find(e => e.name.toLowerCase() === part.toLowerCase())
      }

      if (entity) {
        const description = entity.description || `Interact with ${entity.name}`
        const truncatedDesc = description.length > 150 
          ? `${description.substring(0, 147)}...` 
          : description

        return (
          <span
            key={i}
            onClick={() => onInteract && onInteract(entity)}
            style={{
              cursor: 'pointer',
              textDecoration: 'underline',
              fontWeight: 'bold',
              // Use specific colors for different types
              color: entity.type === 'npc' ? '#ff9999' :
                entity.type === 'item' ? '#00ddaa' :
                  '#ffcc88'
            }}
            title={truncatedDesc}
          >
            {part}
          </span>
        )
      }
      return part
    })
  }

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
    <div className="bg-[rgba(0,100,50,0.2)] border-l-4 border-lime rounded px-2.5 py-2.5 text-lime text-sm leading-relaxed font-serif" style={{
      maxHeight: '30vh',
      overflowY: 'auto',
    }}>
      {/* Room narrative and content all together */}

      {/* Combined narrative: room description + content descriptions */}
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '10px',
      }}>
        {/* Main room description */}
        <p className="text-lg text-[#00ddaa]" style={{ lineHeight: '1.6' }}>
          {renderTextWithLinks(roomDescriptionText)}
        </p>

        {/* Content descriptions immediately following */}
        {hasContentDescriptions && (
          <div style={{
            display: 'flex',
            flexDirection: 'column',
            gap: '6px',
          }}>
            {contentDescriptions.map((content, idx) => (
              <div
                key={idx}
                style={{
                  color: content.type === 'npc' ? '#ff9999' :
                    content.type === 'item' ? '#00ddaa' :
                      '#ffcc88',
                  fontFamily: 'serif',
                  fontStyle: 'italic',
                  fontSize: '16px',
                  lineHeight: '1.5',
                }}
              >
                {renderTextWithLinks(
                  content.text.startsWith(' ') ? `${content.name}${content.text}` : content.text,
                  content.entity
                )}
              </div>
            ))}
          </div>
        )}

        {/* Empty state */}
        {!hasContentDescriptions && (
          <div style={{
            color: '#666666',
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
