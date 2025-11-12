import { useState, useRef, useEffect } from 'react'

export default function CombatLog({ log }) {
  const [isCollapsed, setIsCollapsed] = useState(false)
  const [height, setHeight] = useState(100)
  const [isResizing, setIsResizing] = useState(false)
  const logRef = useRef(null)

  const handleMouseDown = () => {
    setIsResizing(true)
  }

  useEffect(() => {
    const handleMouseUp = () => setIsResizing(false)
    const handleMouseMove = (e) => {
      if (!isResizing) return
      const delta = e.clientY - (logRef.current?.getBoundingClientRect().bottom || 0)
      setHeight(Math.max(30, Math.min(200, height - delta)))
    }

    document.addEventListener('mouseup', handleMouseUp)
    document.addEventListener('mousemove', handleMouseMove)
    return () => {
      document.removeEventListener('mouseup', handleMouseUp)
      document.removeEventListener('mousemove', handleMouseMove)
    }
  }, [isResizing, height])

  return (
    <div
      ref={logRef}
      className="bg-[rgba(0,0,0,0.7)] border border-orange rounded flex flex-col"
      style={{ height: isCollapsed ? '24px' : `${height}px` }}
    >
      <div
        onClick={() => setIsCollapsed(!isCollapsed)}
        className="flex justify-between items-center px-2 py-1.5 bg-[rgba(0,0,0,0.7)] border-b border-orange cursor-pointer hover:bg-[rgba(0,0,0,0.9)]"
      >
        <span className="text-orange font-bold text-xs">Combat Log</span>
        <span className="text-[#ffaa00] text-xs">{isCollapsed ? '▶' : '▼'}</span>
      </div>

      {!isCollapsed && (
        <>
          <div className="flex-1 overflow-y-auto p-2 text-xs space-y-0.5">
            {log?.map((entry, idx) => (
              <div
                key={idx}
                className={`${
                  entry.type === 'damage'
                    ? 'text-red-400'
                    : entry.type === 'heal'
                    ? 'text-lime'
                    : entry.type === 'ability'
                    ? 'text-cyan'
                    : 'text-yellow-300'
                }`}
              >
                {entry.message}
              </div>
            ))}
          </div>
          <div
            onMouseDown={handleMouseDown}
            className="h-1 bg-gradient-to-r from-transparent via-orange to-transparent cursor-ns-resize hover:bg-gradient-to-r hover:from-transparent hover:via-red-500 hover:to-transparent"
          ></div>
        </>
      )}
    </div>
  )
}
