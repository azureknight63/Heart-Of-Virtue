import { useState } from 'react'
import Battlefield from './Battlefield'
import WorldMap from './WorldMap'

export default function RightPanel({ mode, combat, location, onModeChange }) {
  const [modeToggle, setModeToggle] = useState('combat') // 'combat' or 'map'

  return (
    <div className="flex-1 flex flex-col bg-dark-panel border-2 border-orange rounded-lg overflow-hidden retro-glow">
      {/* Header */}
      <div className="bg-orange-glow text-white px-3 py-2.5 font-bold text-center text-sm border-b-2 border-orange">
        {modeToggle === 'combat' ? 'Battlefield Map' : 'World Map'}
      </div>

      {/* Mode Toggle */}
      <div className="flex gap-1.5 p-2 bg-[rgba(0,0,0,0.3)] border-b border-[#333]">
        <button
          onClick={() => setModeToggle('combat')}
          className={`px-3 py-1 text-xs font-bold rounded border-2 transition-all ${
            modeToggle === 'combat'
              ? 'bg-orange text-white border-orange'
              : 'bg-transparent text-orange border-orange hover:bg-orange hover:text-white'
          }`}
        >
          Combat
        </button>
        <button
          onClick={() => setModeToggle('map')}
          className={`px-3 py-1 text-xs font-bold rounded border-2 transition-all ${
            modeToggle === 'map'
              ? 'bg-orange text-white border-orange'
              : 'bg-transparent text-orange border-orange hover:bg-orange hover:text-white'
          }`}
        >
          Explore
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden p-2.5 relative">
        {modeToggle === 'combat' ? (
          <Battlefield combat={combat} />
        ) : (
          <WorldMap location={location} />
        )}
      </div>
    </div>
  )
}
