/**
 * RoomContents - Display integrated room description with contents
 * Displays room contents descriptions inline with the main room description,
 * matching the terminal game's narrative format
 */

export default function RoomContents({ location }) {
  if (!location) return null

  const items = location.items || []
  const npcs = location.npcs || []
  const objects = location.objects || []

  // Build content descriptions array
  const contentDescriptions = []

  // Add NPCs with idle messages
  npcs.forEach(npc => {
    if (npc.idle_message) {
      contentDescriptions.push({
        type: 'npc',
        text: npc.idle_message,
        name: npc.name,
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
    })
  })

  // Add objects with idle messages
  objects.forEach(obj => {
    if (obj.idle_message) {
      contentDescriptions.push({
        type: 'object',
        text: obj.idle_message,
        name: obj.name,
      })
    }
  })

  // Build combined description
  const roomDescriptionText = location.description
  const hasContentDescriptions = contentDescriptions.length > 0

  return (
    <div className="bg-[rgba(0,100,50,0.2)] border-l-4 border-lime rounded px-2.5 py-2.5 text-lime text-sm leading-relaxed font-serif">
      {/* Room narrative and content all together */}

      {/* Combined narrative: room description + content descriptions */}
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        gap: '10px',
      }}>
        {/* Main room description */}
        <p className="text-lg text-[#00ddaa]" style={{ lineHeight: '1.6' }}>{roomDescriptionText}</p>

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
                {content.text.startsWith(' ') ? `${content.name}${content.text}` : content.text}
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
