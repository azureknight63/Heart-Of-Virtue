export default function PlayerStatus({ player }) {

  return (
    <div className="grid grid-cols-2 gap-2.5 text-xs">
      {/* Level & Experience */}
      <div className="col-span-2 bg-[rgba(100,50,0,0.2)] border border-[#ffaa00] rounded px-2 py-1.5">
        <div className="text-[#ffaa00] font-bold text-xs mb-1">
          Level {player.level} • EXP {player.exp} / {player.max_exp || 'N/A'}
        </div>
        <div className="hp-bar">
          <div
            className="h-full bg-gradient-to-r from-[#ffaa00] to-[#ffcc00]"
            style={{
              width: `${player.max_exp ? (player.exp / player.max_exp) * 100 : 0}%`
            }}
          ></div>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="col-span-2 grid grid-cols-3 gap-1 text-[10px]">
        <div className="bg-[rgba(0,50,100,0.2)] border border-cyan rounded px-1 py-0.5 text-center">
          <div className="text-cyan font-bold">STR</div>
          <div className="text-cyan">{player.strength || 10}</div>
        </div>
        <div className="bg-[rgba(0,50,100,0.2)] border border-cyan rounded px-1 py-0.5 text-center">
          <div className="text-cyan font-bold">AGI</div>
          <div className="text-cyan">{player.agility || 10}</div>
        </div>
        <div className="bg-[rgba(0,50,100,0.2)] border border-cyan rounded px-1 py-0.5 text-center">
          <div className="text-cyan font-bold">INT</div>
          <div className="text-cyan">{player.intelligence || 10}</div>
        </div>
      </div>
    </div>
  )
}
