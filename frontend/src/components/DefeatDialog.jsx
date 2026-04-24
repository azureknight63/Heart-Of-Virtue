import React, { useEffect, useMemo, useState } from 'react'
import apiEndpoints from '../api/endpoints'
import { useAuth } from '../hooks/useApi'
import { useAudio } from '../context/AudioContext'
import BaseDialog from './BaseDialog'
import GameButton from './GameButton'
import { colors, spacing } from '../styles/theme'

const SKULL_ART = `
               .o oOOOOOOOo                                            OOOo
                Ob.OOOOOOOo  OOOo.      oOOo.                      .adOOOOOOO
                OboO"""""""""""".OOo. .oOOOOOo.    OOOo.oOOOOOo.."""""""""'OO
                OOP.oOOOOOOOOOOO "POOOOOOOOOOOo.   \`"OOOOOOOOOP,OOOOOOOOOOOB'
                \`O'OOOO'     \`OOOOo"OOOOOOOOOOO\` .adOOOOOOOOO"oOOO'    \`OOOOo
                .OOOO'            \`OOOOOOOOOOOOOOOOOOOOOOOOOO'            \`OO
                OOOOO                 '"OOOOOOOOOOOOOOOO"\`                oOO
               oOOOOOba.                .adOOOOOOOOOOba               .adOOOOo.
              oOOOOOOOOOOOOOba.    .adOOOOOOOOOO@^OOOOOOOba.     .adOOOOOOOOOOOO
             OOOOOOOOOOOOOOOOO.OOOOOOOOOOOOOO"\`  '"OOOOOOOOOOOOO.OOOOOOOOOOOOOO
             "OOOO"       "YOoOOOOOOOOOOOOO"\`  .   '"OOOOOOOOOOOOoOY"     "OOO"
                Y           'OOOOOOOOOOOOOO: .oOOo. :OOOOOOOOOOO?'         :\`
                :            .oO%OOOOOOOOOOo.OOOOOO.oOOOOOOOOOOOO?         .
                .            oOOP"%OOOOOOOOoOOOOOOO?oOOOOO?OOOO"OOo
                                 '%o  OOOO"%OOOO%"%OOOOO"OOOOOO"OOO':
                                      \`$"  \`OOOO' \`O"Y ' \`OOOO'  o             .
                .                  .     OP"          : o     .
                                              :
                                              .
`

export default function DefeatDialog({ endState, onLoadedSave }) {
  const { logout } = useAuth()
  const { playSFX } = useAudio()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [saves, setSaves] = useState([])
  const [selectedSaveId, setSelectedSaveId] = useState('')

  const message = endState?.message || 'You have been defeated.'

  const playSFXRef = React.useRef(playSFX)
  React.useEffect(() => { playSFXRef.current = playSFX }, [playSFX])

  useEffect(() => {
    playSFXRef.current('player_death')
  }, [])

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
      if (typeof onLoadedSave === 'function') {
        await onLoadedSave()
      }
    } catch (e) {
      setError(e?.response?.data?.error || e?.message || 'Failed to load save.')
    } finally {
      setLoading(false)
    }
  }

  const handleStartOver = async () => {
    try {
      setLoading(true)
      await logout()
    } catch (e) {
      setError(e?.message || 'Failed to start over.')
      setLoading(false)
    }
  }

  return (
    <BaseDialog
      title="Defeat"
      variant="danger"
      maxWidth="720px"
      zIndex={2500}
      showCloseButton={false}
    >
      <pre style={{
        color: colors.text.danger,
        fontFamily: 'monospace',
        fontSize: '9px',
        lineHeight: '1.2',
        whiteSpace: 'pre',
        overflowX: 'auto',
        textAlign: 'center',
        marginBottom: spacing.sm,
      }}>{SKULL_ART}</pre>
      <div style={{ color: colors.text.danger, marginBottom: spacing.sm }}>{message}</div>
      <div style={{ color: colors.text.muted, marginBottom: spacing.lg }}>Reload a save or start over.</div>

      <div style={{ border: `1px solid ${colors.border.danger}`, borderRadius: '10px', padding: spacing.md, marginBottom: spacing.lg }}>
        <div style={{ color: colors.text.danger, fontWeight: 'bold', marginBottom: spacing.sm }}>Load save</div>

        {loading && <div style={{ color: colors.text.muted }}>Loading…</div>}

        {!loading && saveOptions.length === 0 && (
          <div style={{ color: colors.text.muted }}>No saves found.</div>
        )}

        {!loading && saveOptions.length > 0 && (
          <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
            <select
              value={selectedSaveId}
              onChange={(e) => setSelectedSaveId(e.target.value)}
              style={{
                padding: spacing.sm,
                backgroundColor: colors.bg.main,
                color: colors.text.danger,
                border: `1px solid ${colors.border.danger}`,
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

        {error && <div style={{ marginTop: spacing.sm, color: colors.text.danger }}>{error}</div>}
      </div>

      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <GameButton
          onClick={handleStartOver}
          disabled={loading}
          variant="secondary"
          style={{ border: `1px solid ${colors.border.danger}`, color: colors.text.danger }}
        >
          START OVER
        </GameButton>
      </div>
    </BaseDialog>
  )
}
