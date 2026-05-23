import { useState, useEffect, useCallback } from 'react'

const CHARS_PER_PAGE = 800

function paginateText(text) {
  if (!text || text.length <= CHARS_PER_PAGE) {
    return [text || '']
  }

  const pages = []
  let currentPage = ''

  const textWithMarkers = text.replace(/\n/g, '<!NL!>')

  const sentences = textWithMarkers
    .replace(/! /g, '! |')
    .replace(/\? /g, '? |')
    .replace(/\. /g, '. |')
    .split('|')

  for (let sentence of sentences) {
    sentence = sentence.replace(/<!NL!>/g, '\n')

    if (sentence.length > CHARS_PER_PAGE) {
      if (currentPage.trim()) {
        pages.push(currentPage.trimEnd())
        currentPage = ''
      }
      let remaining = sentence
      while (remaining.length > CHARS_PER_PAGE) {
        pages.push(remaining.slice(0, CHARS_PER_PAGE).trimEnd())
        remaining = remaining.slice(CHARS_PER_PAGE)
      }
      if (remaining.trim()) currentPage = remaining
      continue
    }

    if (currentPage.length + sentence.length > CHARS_PER_PAGE && currentPage) {
      pages.push(currentPage.trimEnd())
      currentPage = sentence
    } else {
      currentPage += sentence
    }
  }

  if (currentPage.trim()) pages.push(currentPage.trimEnd())

  return pages.length > 0 ? pages : [text]
}

export default function BookReaderDialog({ title, text, onClose }) {
  const pages = paginateText(text)
  const totalPages = pages.length
  const [currentPage, setCurrentPage] = useState(0)

  const handlePrev = useCallback(() => setCurrentPage(p => Math.max(0, p - 1)), [])
  const handleNext = useCallback(() => setCurrentPage(p => Math.min(totalPages - 1, p + 1)), [totalPages])

  useEffect(() => {
    const handleKey = (e) => {
      if (e.key === 'ArrowLeft') handlePrev()
      else if (e.key === 'ArrowRight') handleNext()
      else if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [handlePrev, handleNext, onClose])

  // Reset to first page if text changes
  useEffect(() => { setCurrentPage(0) }, [text])

  return (
    <div style={{
      position: 'fixed',
      top: 0, left: 0, right: 0, bottom: 0,
      backgroundColor: 'rgba(0, 0, 0, 0.92)',
      display: 'flex',
      justifyContent: 'center',
      alignItems: 'center',
      zIndex: 1800,
    }}>
      <div style={{
        backgroundColor: 'rgba(5, 3, 0, 0.98)',
        border: '2px solid #00ffff',
        borderRadius: '4px',
        padding: '24px 32px',
        width: '90%',
        maxWidth: '680px',
        maxHeight: '85vh',
        display: 'flex',
        flexDirection: 'column',
        gap: '16px',
        boxShadow: '0 0 30px rgba(0, 255, 255, 0.15)',
      }}>
        {/* Header */}
        <div style={{
          borderBottom: '1px solid rgba(0, 255, 255, 0.25)',
          paddingBottom: '12px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexShrink: 0,
        }}>
          <span style={{
            color: '#00ffff',
            fontFamily: 'monospace',
            fontSize: '15px',
            fontWeight: 'bold',
            letterSpacing: '0.04em',
          }}>
            {title}
          </span>
          {totalPages > 1 && (
            <span style={{
              color: 'rgba(0, 255, 255, 0.5)',
              fontFamily: 'monospace',
              fontSize: '12px',
            }}>
              Page {currentPage + 1} / {totalPages}
            </span>
          )}
        </div>

        {/* Content */}
        <div style={{
          flex: 1,
          overflowY: 'auto',
          color: '#c8ffc8',
          fontFamily: 'monospace',
          fontSize: '14px',
          lineHeight: '1.75',
          whiteSpace: 'pre-wrap',
          minHeight: '160px',
        }}>
          {pages[currentPage]}
        </div>

        {/* Navigation */}
        <div style={{
          borderTop: '1px solid rgba(0, 255, 255, 0.25)',
          paddingTop: '12px',
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          gap: '12px',
          flexShrink: 0,
        }}>
          <button
            onClick={handlePrev}
            disabled={currentPage === 0}
            style={{
              padding: '7px 18px',
              backgroundColor: currentPage === 0 ? 'transparent' : '#001833',
              color: currentPage === 0 ? 'rgba(0, 204, 255, 0.25)' : '#00ccff',
              border: `1px solid ${currentPage === 0 ? 'rgba(0, 204, 255, 0.15)' : '#00ccff'}`,
              borderRadius: '3px',
              cursor: currentPage === 0 ? 'default' : 'pointer',
              fontSize: '12px',
              fontFamily: 'monospace',
              fontWeight: 'bold',
              minWidth: '80px',
            }}
            onMouseEnter={(e) => {
              if (currentPage > 0) {
                e.target.style.backgroundColor = '#002a4d'
                e.target.style.boxShadow = '0 0 8px rgba(0, 204, 255, 0.4)'
              }
            }}
            onMouseLeave={(e) => {
              if (currentPage > 0) {
                e.target.style.backgroundColor = '#001833'
                e.target.style.boxShadow = 'none'
              }
            }}
          >
            ← PREV
          </button>

          <button
            onClick={onClose}
            style={{
              padding: '7px 20px',
              backgroundColor: '#1a0000',
              color: '#ff6644',
              border: '1px solid #ff6644',
              borderRadius: '3px',
              cursor: 'pointer',
              fontSize: '12px',
              fontFamily: 'monospace',
              fontWeight: 'bold',
            }}
            onMouseEnter={(e) => {
              e.target.style.backgroundColor = '#330000'
              e.target.style.boxShadow = '0 0 8px rgba(255, 100, 68, 0.4)'
            }}
            onMouseLeave={(e) => {
              e.target.style.backgroundColor = '#1a0000'
              e.target.style.boxShadow = 'none'
            }}
          >
            CLOSE BOOK
          </button>

          <button
            onClick={handleNext}
            disabled={currentPage === totalPages - 1}
            style={{
              padding: '7px 18px',
              backgroundColor: currentPage === totalPages - 1 ? 'transparent' : '#001833',
              color: currentPage === totalPages - 1 ? 'rgba(0, 204, 255, 0.25)' : '#00ccff',
              border: `1px solid ${currentPage === totalPages - 1 ? 'rgba(0, 204, 255, 0.15)' : '#00ccff'}`,
              borderRadius: '3px',
              cursor: currentPage === totalPages - 1 ? 'default' : 'pointer',
              fontSize: '12px',
              fontFamily: 'monospace',
              fontWeight: 'bold',
              minWidth: '80px',
            }}
            onMouseEnter={(e) => {
              if (currentPage < totalPages - 1) {
                e.target.style.backgroundColor = '#002a4d'
                e.target.style.boxShadow = '0 0 8px rgba(0, 204, 255, 0.4)'
              }
            }}
            onMouseLeave={(e) => {
              if (currentPage < totalPages - 1) {
                e.target.style.backgroundColor = '#001833'
                e.target.style.boxShadow = 'none'
              }
            }}
          >
            NEXT →
          </button>
        </div>
      </div>
    </div>
  )
}
