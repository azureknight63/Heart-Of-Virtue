export default function BattlefieldGrid({ combat, tab, zoom = 1 }) {
  const renderGrid = () => {
    if (tab === 'enemies') {
      return (
        <div className="p-4 overflow-y-auto h-full">
          <div className="space-y-2">
            {combat.enemies?.map((enemy, idx) => (
              <div key={idx} className="bg-[rgba(255,68,68,0.1)] border border-red-600 rounded p-2">
                <div className="text-orange font-bold text-sm">{enemy.name}</div>
                <div className="text-xs text-orange mt-1">HP: {enemy.hp} / {enemy.max_hp}</div>
                <div className="hp-bar mt-1">
                  <div
                    className="h-full bg-gradient-to-r from-[#ff4444] to-[#ffaa44]"
                    style={{ width: `${(enemy.hp / enemy.max_hp) * 100}%` }}
                  ></div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )
    }

    // Combat overview grid - zoom affects grid size
    // Full battlefield is 10x10 (100 cells)
    // Player is at position 45 (row 4, col 5)
    const playerPos = 45

    // Calculate grid dimensions based on zoom
    // zoom = 0.5 -> 20x20 grid (more cells, smaller)
    // zoom = 1.0 -> 10x10 grid (default)
    // zoom = 2.0 -> 5x5 grid (fewer cells, larger)
    const baseCols = 10
    const gridCols = Math.max(3, Math.round(baseCols / zoom))
    const totalCells = gridCols * gridCols

    // Calculate which cells to show (centered on player)
    const playerRow = Math.floor(playerPos / baseCols)
    const playerCol = playerPos % baseCols

    // Calculate the top-left corner of the visible area
    const startRow = Math.max(0, Math.min(baseCols - gridCols, playerRow - Math.floor(gridCols / 2)))
    const startCol = Math.max(0, Math.min(baseCols - gridCols, playerCol - Math.floor(gridCols / 2)))

    return (
      <div
        className="grid gap-0.5 p-2 h-full overflow-auto transition-all duration-200"
        style={{
          gridTemplateColumns: `repeat(${gridCols}, minmax(0, 1fr))`,
        }}
      >
        {Array(totalCells).fill(null).map((_, idx) => {
          // Map visible grid index to full battlefield index
          const visibleRow = Math.floor(idx / gridCols)
          const visibleCol = idx % gridCols
          const fullRow = startRow + visibleRow
          const fullCol = startCol + visibleCol
          const fullIdx = fullRow * baseCols + fullCol

          let content = ''
          let bgColor = 'bg-[rgba(50,50,50,0.3)]'
          let borderColor = 'border-gray-700'

          // Placeholder logic for combatants
          if (fullIdx === 45) {
            content = 'J'
            bgColor = 'bg-gradient-to-br from-lime to-cyan'
            borderColor = 'border-lime'
          } else if (fullIdx === 37) {
            content = 'E'
            bgColor = 'bg-gradient-to-br from-red-500 to-red-600'
            borderColor = 'border-red-500'
          }

          // Calculate font size based on zoom
          const fontSize = zoom >= 1.5 ? 'text-base' : zoom >= 1 ? 'text-sm' : 'text-xs'

          return (
            <div
              key={idx}
              className={`aspect-square ${bgColor} border ${borderColor} rounded text-white ${fontSize} font-bold flex items-center justify-center cursor-pointer hover:opacity-75 transition-opacity`}
            >
              {content}
            </div>
          )
        })}
      </div>
    )
  }

  return renderGrid()
}
