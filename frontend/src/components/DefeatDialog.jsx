import { useEffect, useMemo, useState } from 'react'
import apiEndpoints from '../api/endpoints'
import { useAuth } from '../hooks/useApi'
import BaseDialog from './BaseDialog'
import GameButton from './GameButton'

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
    <BaseDialog
      title="Defeat"
      variant="danger"
      maxWidth="720px"
      zIndex={2500}
      showCloseButton={false}
    >
      <div style={{ color: '#ffe6e6', marginBottom: '8px' }}>{message}</div>
      <div style={{ color: '#cccccc', marginBottom: '16px' }}>Reload a save or start over.</div>

      <div style={{ border: '1px solid #cc0000', borderRadius: '10px', padding: '12px', marginBottom: '16px' }}>
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

            <GameButton
              onClick={handleLoad}
              disabled={loading || !selectedSaveId}
              variant="danger"
            >
              {loading ? 'LOADING…' : 'LOAD'}
            </GameButton>
          </div>
        )}

        {error && <div style={{ marginTop: '10px', color: '#ff7777' }}>{error}</div>}
      </div>

      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <GameButton
          onClick={handleStartOver}
          disabled={loading}
          variant="secondary"
          style={{ border: '1px solid #cc0000', color: '#ff7777' }}
        >
          START OVER
        </GameButton>
      </div>
    </BaseDialog>
  )
}
