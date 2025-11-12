export default function WorldMap({ location }) {
  return (
    <div className="w-full h-full flex flex-col items-center justify-center bg-[rgba(0,0,0,0.3)] rounded border border-[#333]">
      <div className="text-center space-y-4">
        <h2 className="text-lime text-xl font-bold">World Map</h2>
        <p className="text-cyan text-sm">{location?.name || 'Unknown Territory'}</p>

        {/* Simple ASCII map representation */}
        <div className="text-lime font-mono text-xs space-y-1 inline-block">
          <div>? · · ? · · · · · ?</div>
          <div>· · ● · · · · · · ·</div>
          <div>? · · · · · · · · ·</div>
          <div>· · · · · ● · · ? ·</div>
          <div>· · ● · · · · · · ·</div>
          <div>? · · · · · X · · ?</div>
          <div>· · · · · ● · · · ·</div>
          <div>· · · · · · · · · ·</div>
        </div>

        <div className="text-xs text-gray-400 mt-4 space-y-0.5">
          <p><span className="text-orange">X</span> = Your Position</p>
          <p><span className="text-lime">●</span> = Visited</p>
          <p><span className="text-[#ffaa00]">?</span> = Discovered</p>
          <p><span className="text-gray-500">·</span> = Unexplored</p>
        </div>
      </div>
    </div>
  )
}
