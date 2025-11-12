export default function BattlefieldGrid({ combat, tab }) {
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

    // Combat overview grid (10x10)
    return (
      <div className="grid grid-cols-10 gap-0.5 p-2 h-full overflow-auto">
        {Array(100).fill(null).map((_, idx) => {
          let content = ''
          let bgColor = 'bg-[rgba(50,50,50,0.3)]'
          let borderColor = 'border-gray-700'

          // Placeholder logic for combatants
          if (idx === 45) {
            content = 'J'
            bgColor = 'bg-gradient-to-br from-lime to-cyan'
            borderColor = 'border-lime'
          } else if (idx === 37) {
            content = 'E'
            bgColor = 'bg-gradient-to-br from-red-500 to-red-600'
            borderColor = 'border-red-500'
          }

          return (
            <div
              key={idx}
              className={`aspect-square ${bgColor} border ${borderColor} rounded text-white text-xs font-bold flex items-center justify-center cursor-pointer hover:opacity-75 transition-opacity`}
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
