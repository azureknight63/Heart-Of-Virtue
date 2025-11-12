import { useState, useEffect } from 'react'
import { usePlayer, useWorld, useCombat } from '../hooks/useApi'
import LeftPanel from '../components/LeftPanel'
import RightPanel from '../components/RightPanel'

export default function GamePage() {
  const { player, loading: playerLoading, refetch: refetchPlayer } = usePlayer()
  const { location, loading: worldLoading, move } = useWorld()
  const { combat, inCombat, fetchCombatStatus } = useCombat()
  const [mode, setMode] = useState('exploration') // 'exploration' or 'combat'

  useEffect(() => {
    if (inCombat) {
      setMode('combat')
      fetchCombatStatus()
    } else {
      setMode('exploration')
    }
  }, [inCombat])

  if (playerLoading || worldLoading) {
    return (
      <div className="w-screen h-screen bg-dark-900 flex items-center justify-center">
        <p className="text-lime animate-pulse-glow">Loading your adventure...</p>
      </div>
    )
  }

  return (
    <div className="w-screen h-screen bg-dark-900 flex gap-2.5 p-2.5 overflow-hidden">
      {/* Left Panel - Narrative & Controls */}
      <LeftPanel
        player={player}
        location={location}
        mode={mode}
        onMove={move}
        onRefetch={refetchPlayer}
      />

      {/* Right Panel - Battlefield/Map */}
      <RightPanel
        mode={mode}
        combat={combat}
        location={location}
        onModeChange={setMode}
      />
    </div>
  )
}
