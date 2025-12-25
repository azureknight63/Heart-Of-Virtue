import { useEffect, useMemo, useState } from 'react'
import apiEndpoints from '../api/endpoints'
import { useAuth } from '../hooks/useApi'

export default function DefeatDialog({ endState, onLoadedSave }) {
  const { logout } = useAuth()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [saves, setSaves] = useState([])
  const [selectedSaveId, setSelectedSaveId] = useState('')

  const message = endState?.message || 'You have been defeated.'

  useEffect(() => {
    let mounted = true

    const fetchSaves = async () => {
      try {
        setLoading(true)
        setError('')
        const resp = await apiEndpoints.saves.list()
        const list = resp?.data?.saves || []
        if (!mounted) return
        setSaves(list)
        if (list.length > 0) {
          setSelectedSaveId(list[0].id)
        }
      } catch (e) {
        if (!mounted) return
        setError(e?.message || 'Failed to load saves.')
      } finally {
        if (mounted) setLoading(false)
      }
    }

    fetchSaves()

    return () => {
      mounted = false
    }
  }, [])

  const saveOptions = useMemo(() => {
    return saves.map((s) => {
      const parts = [s.name]
      if (typeof s.level === 'number') parts.push(`Lv ${s.level}`)
      if (s.location) parts.push(s.location)
      return { id: s.id, label: parts.join(' • ') }
    })
  }, [saves])

  const handleLoad = async () => {
    setError('')
    if (!selectedSaveId) {
      setError('Select a save to load.')
      return
    }

    try {
      setLoading(true)
      await apiEndpoints.saves.load(selectedSaveId)
      await onLoadedSave()
    } catch (e) {
      setError(e?.response?.data?.error || e?.message || 'Failed to load save.')
    } finally {
      setLoading(false)
    }
  }

  const handleStartOver = async () => {
    await logout()
  }

  return (
    <div
      style={{
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: 'rgba(0, 0, 0, 0.9)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 2500,
      }}
    >
      <div
        style={{
          backgroundColor: 'rgba(25, 10, 10, 0.98)',
          border: '3px solid #cc0000',
          borderRadius: '12px',
          padding: '24px',
          width: '90%',
          maxWidth: '720px',
          maxHeight: '80vh',
          display: 'flex',
          flexDirection: 'column',
          gap: '16px',
          boxShadow: '0 0 30px rgba(204, 0, 0, 0.6), inset 0 0 20px rgba(0, 0, 0, 0.8)',
          overflowY: 'auto',
          fontFamily: 'monospace',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            borderBottom: '2px solid #cc0000',
            paddingBottom: '12px',
          }}
        >
          <div
            style={{
              color: '#ff5555',
              fontWeight: 'bold',
              fontSize: '18px',
              textShadow: '0 0 8px rgba(255, 85, 85, 0.8)',
            }}
          >
            Defeat
          </div>
        </div>

        <div style={{ color: '#ffe6e6' }}>{message}</div>
        <div style={{ color: '#cccccc' }}>Reload a save or start over.</div>

        <div style={{ border: '1px solid #cc0000', borderRadius: '10px', padding: '12px' }}>
          <div style={{ color: '#ff7777', fontWeight: 'bold', marginBottom: '8px' }}>Load save</div>

          {loading && <div style={{ color: '#cccccc' }}>Loading…</div>}

          {!loading && saveOptions.length === 0 && (
            <div style={{ color: '#cccccc' }}>No saves found.</div>
          )}

          {!loading && saveOptions.length > 0 && (
            <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
              <select
                value={selectedSaveId}
                onChange={(e) => setSelectedSaveId(e.target.value)}
                style={{
                  padding: '8px',
                  backgroundColor: '#220000',
                  color: '#ff7777',
                  border: '1px solid #cc0000',
                  borderRadius: '6px',
                  minWidth: '320px',
                }}
              >
                {saveOptions.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.label}
                  </option>
                ))}
              </select>

              <button
                onClick={handleLoad}
                disabled={loading || !selectedSaveId}
                style={{
                  padding: '8px 12px',
                  backgroundColor: '#cc0000',
                  color: '#000000',
                  border: '1px solid #000000',
                  borderRadius: '6px',
                  cursor: loading || !selectedSaveId ? 'not-allowed' : 'pointer',
                  fontWeight: 'bold',
                }}
              >
                {loading ? 'LOADING…' : 'LOAD'}
              </button>
            </div>
          )}

          {error && <div style={{ marginTop: '10px', color: '#ff7777' }}>{error}</div>}
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
          <button
            onClick={handleStartOver}
            disabled={loading}
            style={{
              padding: '8px 12px',
              backgroundColor: '#222222',
              color: '#ff7777',
              border: '1px solid #cc0000',
              borderRadius: '6px',
              cursor: loading ? 'not-allowed' : 'pointer',
              fontWeight: 'bold',
            }}
          >
            START OVER
          </button>
        </div>
      </div>
    </div>
  )
}
