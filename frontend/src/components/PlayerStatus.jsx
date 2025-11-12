export default function PlayerStatus({ player }) {
  const hpPercent = player.hp && player.max_hp ? (player.hp / player.max_hp) * 100 : 0
  const fatiguePercent = player.fatigue && player.max_fatigue ? (player.fatigue / player.max_fatigue) * 100 : 0

  return (
    <div className="grid grid-cols-2 gap-2.5 text-xs">
      {/* Health */}
      <div className="bg-[rgba(0,50,100,0.2)] border border-cyan rounded px-2 py-1.5">
        <div className="text-cyan font-bold text-xs uppercase">HP</div>
        <div className="text-cyan mt-1 text-xs">{player.hp} / {player.max_hp}</div>
        <div className="hp-bar mt-1">
          <div
            className={`${
              hpPercent > 50 ? 'hp-fill-full' : hpPercent > 25 ? 'hp-fill-partial' : 'hp-fill-critical'
            }`}
            style={{ width: `${hpPercent}%` }}
          ></div>
        </div>
      </div>

      {/* Fatigue */}
      <div className="bg-[rgba(0,50,100,0.2)] border border-cyan rounded px-2 py-1.5">
        <div className="text-cyan font-bold text-xs uppercase">Fatigue</div>
        <div className="text-cyan mt-1 text-xs">{player.fatigue} / {player.max_fatigue}</div>
        <div className="hp-bar mt-1">
          <div
            className="h-full bg-gradient-to-r from-[#4488ff] to-[#44ffff]"
            style={{ width: `${fatiguePercent}%` }}
          ></div>
        </div>
      </div>

      {/* Level & Experience */}
      <div className="col-span-2 bg-[rgba(100,50,0,0.2)] border border-[#ffaa00] rounded px-2 py-1.5">
        <div className="text-[#ffaa00] font-bold text-xs mb-1">
          Level {player.level} • EXP {player.experience} / {player.next_level_exp || 'N/A'}
        </div>
        <div className="hp-bar">
          <div
            className="h-full bg-gradient-to-r from-[#ffaa00] to-[#ffcc00]"
            style={{
              width: `${player.next_level_exp ? (player.experience / player.next_level_exp) * 100 : 0}%`
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
