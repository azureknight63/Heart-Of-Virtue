import { useState, useEffect } from 'react'
import MovementStar from './MovementStar'

export default function MapGrid({ location, onMove, exits, loading, exploredTiles }) {
  const GRID_SIZE = 13 // Odd number centers player
  const TILE_SIZE = 40

  if (!location) {
    return (
      <div style={{
        width: '100%',
        height: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: 'rgba(0,0,0,0.3)',
        borderRadius: '4px',
        border: '1px solid #333'
      }}>
        <p style={{ color: '#00ccff' }}>Loading map...</p>
      </div>
    )
  }

  const centerIndex = Math.floor(GRID_SIZE / 2)
  const startX = location.x - centerIndex
  const startY = location.y - centerIndex

  const getTileContent = (x, y) => {
    const tileKey = `${x},${y}`
    const isPlayerHere = x === location.x && y === location.y
    const isExplored = exploredTiles && exploredTiles.has(tileKey)

    let bgColor = '#1a1a2e'
    let symbol = '.'
    let textColor = '#666'

    if (isPlayerHere) {
      bgColor = '#00ff88'
      textColor = '#000000'
      
      // Show indicators for items, NPCs, objects on current location
      const items = location.items || []
      const npcs = location.npcs || []
      const objects = location.objects || []
      
      if ((items.length > 0 ? 1 : 0) + (npcs.length > 0 ? 1 : 0) + (objects.length > 0 ? 1 : 0) >= 2) {
        // Multiple types present
        symbol = '✦'
      } else if (npcs.length > 0) {
        symbol = '◉'
      } else if (objects.length > 0) {
        symbol = '◾'
      } else if (items.length > 0) {
        symbol = '◆'
      } else {
        symbol = '©'
      }
    } else if (isExplored) {
      bgColor = 'rgba(0, 255, 136, 0.2)'
      symbol = '●'
      textColor = '#00ff88'
    }

    return { bgColor, symbol, textColor }
  }

  const handleTileClick = (x, y) => {
    if (x === location.x && y === location.y) return

    // Determine direction relative to player
    const dx = x - location.x
    const dy = y - location.y

    // Map to direction name
    const directionMap = {
      '0,-1': 'north',
      '0,1': 'south',
      '-1,0': 'west',
      '1,0': 'east',
      '-1,-1': 'northwest',
      '1,-1': 'northeast',
      '-1,1': 'southwest',
      '1,1': 'southeast',
    }

    const direction = directionMap[`${dx},${dy}`]
    
    // Check if this direction is in available exits
    if (direction && location.exits && location.exits.includes(direction)) {
      onMove(direction)
    }
  }

  return (
    <div style={{
      position: 'relative',
      width: '100%',
      height: '100%',
      minHeight: '500px',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      backgroundColor: '#0a0a0a',
      borderRadius: '4px',
      border: '2px solid #ff6600',
      padding: '16px',
      boxShadow: '0 0 20px rgba(255, 102, 0, 0.3)',
    }}>
      {/* Movement Star - Left of Top Left Corner */}
      <div style={{
        position: 'absolute',
        top: '4px',
        left: '-30px',
        zIndex: 10
      }}>
        <MovementStar 
          exits={exits || []} 
          onMove={onMove}
          loading={loading}
        />
      </div>
      {/* Title */}
      <div style={{
        color: '#ff6600',
        fontSize: '14px',
        fontWeight: 'bold',
        marginBottom: '12px',
        fontFamily: 'monospace',
      }}>
        ⛰️ {location.name || 'World Map'}
      </div>

      {/* Grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: `repeat(${GRID_SIZE}, ${TILE_SIZE}px)`,
        gap: '1px',
        backgroundColor: '#000',
        padding: '4px',
        borderRadius: '4px',
        border: '1px solid #333',
      }}>
        {Array.from({ length: GRID_SIZE }).map((_, row) =>
          Array.from({ length: GRID_SIZE }).map((_, col) => {
            const x = startX + col
            const y = startY + row
            const { bgColor, symbol, textColor } = getTileContent(x, y)
            const isPlayerHere = x === location.x && y === location.y
            const canMove = location.exits && location.exits.length > 0
            const dx = x - location.x
            const dy = y - location.y
            const directionMap = {
              '0,-1': 'north',
              '0,1': 'south',
              '-1,0': 'west',
              '1,0': 'east',
              '-1,-1': 'northwest',
              '1,-1': 'northeast',
              '-1,1': 'southwest',
              '1,1': 'southeast',
            }
            const direction = directionMap[`${dx},${dy}`]
            const isValidMove = direction && location.exits && location.exits.includes(direction)

            return (
              <div
                key={`${x},${y}`}
                onClick={() => handleTileClick(x, y)}
                style={{
                  width: `${TILE_SIZE}px`,
                  height: `${TILE_SIZE}px`,
                  backgroundColor: bgColor,
                  border: isPlayerHere ? '2px solid #ffaa00' : isValidMove ? '1px solid #00ff88' : '1px solid #333',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: isValidMove ? 'pointer' : 'default',
                  fontSize: '20px',
                  color: textColor,
                  fontWeight: 'bold',
                  transition: 'all 0.2s',
                  boxShadow: isValidMove ? '0 0 8px rgba(0, 255, 136, 0.5) inset' : 'none',
                }}
                onMouseEnter={(e) => {
                  if (isValidMove) {
                    e.target.style.backgroundColor = 'rgba(0, 255, 136, 0.4)'
                    e.target.style.boxShadow = '0 0 12px rgba(0, 255, 136, 0.8) inset'
                  }
                }}
                onMouseLeave={(e) => {
                  e.target.style.backgroundColor = bgColor
                  e.target.style.boxShadow = isValidMove ? '0 0 8px rgba(0, 255, 136, 0.5) inset' : 'none'
                }}
                title={isPlayerHere ? 'Your Position' : isValidMove ? `Move ${direction}` : `(${x}, ${y})`}
              >
                {symbol}
              </div>
            )
          })
        )}
      </div>

      {/* Legend */}
      <div style={{
        marginTop: '12px',
        fontSize: '11px',
        color: '#ff6600',
        fontFamily: 'monospace',
        textAlign: 'center',
        display: 'grid',
        gridTemplateColumns: '1fr 1fr 1fr 1fr 1fr',
        gap: '8px',
      }}>
        <div>
          <span style={{ color: '#ffaa00', fontWeight: 'bold' }}>©</span> = You
        </div>
        <div>
          <span style={{ color: '#00ff88', fontWeight: 'bold' }}>●</span> = Visited
        </div>
        <div>
          <span style={{ color: '#00ddaa', fontWeight: 'bold' }}>◆</span> = Items
        </div>
        <div>
          <span style={{ color: '#ff9999', fontWeight: 'bold' }}>◉</span> = NPCs
        </div>
        <div>
          <span style={{ color: '#ffcc88', fontWeight: 'bold' }}>◾</span> = Objects
        </div>
      </div>

      {/* Current Location Info */}
      {location && (
        <div style={{
          marginTop: '12px',
          fontSize: '12px',
          color: '#00ccff',
          fontFamily: 'monospace',
          borderTop: '1px solid #333',
          paddingTop: '8px',
          maxWidth: '100%',
          textAlign: 'center',
        }}>
          <div style={{ color: '#ffaa00', fontWeight: 'bold' }}>
            {location.name || 'Unknown Location'}
          </div>
          {location.exits && location.exits.length > 0 && (
            <div style={{ fontSize: '10px', marginTop: '4px' }}>
              Exits: {location.exits.join(', ')}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
