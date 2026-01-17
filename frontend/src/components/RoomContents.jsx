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

    // Create a mapping of all matchable terms (names and aliases) to their entities
    const termMap = []
    allEntities.forEach(entity => {
      // Add the name
      termMap.push({ term: entity.name, entity })
      // Add aliases if they exist
      if (entity.aliases && Array.isArray(entity.aliases)) {
        entity.aliases.forEach(alias => {
          termMap.push({ term: alias, entity })
        })
      }
    })

    // Sort terms by length descending to avoid partial matches
    termMap.sort((a, b) => b.term.length - a.term.length)

    // Create a regex that matches any of the terms
    const terms = termMap.map(t => t.term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
    if (terms.length === 0) return text

    const regex = new RegExp(`(${terms.join('|')})`, 'gi')
    const parts = text.split(regex)

    return parts.map((part, i) => {
      // Find the entity for this part.
      let entity = null

      // 1. Check if it matches preferredEntity's name or aliases
      if (preferredEntity) {
        const isMatch = part.toLowerCase() === preferredEntity.name.toLowerCase() ||
          (preferredEntity.aliases && preferredEntity.aliases.some(a => a.toLowerCase() === part.toLowerCase()))
        if (isMatch) {
          entity = preferredEntity
        }
      }

      // 2. Otherwise search in termMap
      if (!entity) {
        const match = termMap.find(t => t.term.toLowerCase() === part.toLowerCase())
        if (match) {
          entity = match.entity
        }
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
        {/* Main room description - no links to avoid confusion with non-interactable flavor text */}
        <p className="text-lg text-[#00ddaa]" style={{ lineHeight: '1.6' }}>
          {roomDescriptionText}
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
