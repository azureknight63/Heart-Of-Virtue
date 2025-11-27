import { useState, useRef, useEffect } from 'react'

export default function CombatLog({ log, className = '', allowResize = true }) {
  const [isCollapsed, setIsCollapsed] = useState(false)
  const [height, setHeight] = useState(150)
  const [isResizing, setIsResizing] = useState(false)
  const logRef = useRef(null)
  const contentRef = useRef(null)

  const handleMouseDown = () => {
    if (allowResize) setIsResizing(true)
  }

  useEffect(() => {
    const handleMouseUp = () => setIsResizing(false)
    const handleMouseMove = (e) => {
      if (!isResizing) return
      const delta = e.clientY - (logRef.current?.getBoundingClientRect().bottom || 0)
      setHeight(Math.max(50, Math.min(400, height - delta)))
    }

    document.addEventListener('mouseup', handleMouseUp)
    document.addEventListener('mousemove', handleMouseMove)
    return () => {
      document.removeEventListener('mouseup', handleMouseUp)
      document.removeEventListener('mousemove', handleMouseMove)
    }
  }, [isResizing, height])

  // Auto-scroll to bottom when log updates
  useEffect(() => {
    if (contentRef.current) {
      contentRef.current.scrollTop = contentRef.current.scrollHeight
    }
  }, [log])

  return (
    <div
      ref={logRef}
      className={`bg-[rgba(0,0,0,0.8)] border border-orange rounded flex flex-col ${className}`}
      style={{ height: isCollapsed ? '32px' : allowResize ? `${height}px` : '100%' }}
    >
      <div
        onClick={() => setIsCollapsed(!isCollapsed)}
        className="flex justify-between items-center px-3 py-1.5 bg-[rgba(0,0,0,0.6)] border-b border-orange/50 cursor-pointer hover:bg-[rgba(0,0,0,0.8)] transition-colors"
      >
        <span className="text-orange font-bold text-xs tracking-wider uppercase">Combat Log</span>
        <span className="text-[#ffaa00] text-xs">{isCollapsed ? '▶' : '▼'}</span>
      </div>

      {!isCollapsed && (
        <>
          <div
            ref={contentRef}
            className="flex-1 overflow-y-auto p-2 text-xs space-y-1 font-mono"
          >
            {log?.length === 0 && (
              <div className="text-gray-500 italic text-center py-2">Combat started...</div>
            )}
            {log?.map((entry, idx) => (
              <div
                key={idx}
                className={`${entry.type === 'damage'
                    ? 'text-red-400'
                    : entry.type === 'heal'
                      ? 'text-green-400'
                      : entry.type === 'ability'
                        ? 'text-cyan-400'
                        : entry.type === 'info'
                          ? 'text-gray-300'
                          : 'text-yellow-300'
                  }`}
              >
                <span className="opacity-50 mr-2">[{entry.timestamp || new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}]</span>
                <span dangerouslySetInnerHTML={{ __html: entry.message }} />
              </div>
            ))}
          </div>
          {allowResize && (
            <div
              onMouseDown={handleMouseDown}
              className="h-1.5 bg-gradient-to-r from-transparent via-orange/30 to-transparent cursor-ns-resize hover:via-orange/70 transition-colors"
            ></div>
          )}
        </>
      )}
    </div>
  )
}
