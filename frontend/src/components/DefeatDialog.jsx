import { useEffect, useRef } from 'react'
import { useAudio } from '../context/AudioContext'
import useDefeatRecovery from '../hooks/useDefeatRecovery'
import BaseDialog from './BaseDialog'
import GameButton from './GameButton'
import { colors, spacing, zIndex } from '../styles/theme'

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

/**
 * DefeatDialog — the end-of-run screen: reload a save, or start over.
 *
 * `onRunChanged` fires once either exit's request succeeds; its handler is
 * `GamePage.handleDefeatClose`, reached through CombatManager's
 * `onDefeatClose`. The state behind the two exits lives in
 * useDefeatRecovery; this component only renders it.
 */
export default function DefeatDialog({ endState, onRunChanged }) {
  const { playSFX } = useAudio()
  const {
    isLoadingSaves,
    isSubmitting,
    isRestoringSave,
    error,
    saveOptions,
    selectedSaveId,
    setSelectedSaveId,
    loadSave,
    startOver,
  } = useDefeatRecovery({ onRunChanged })

  const message = endState?.message || 'You have been defeated.'

  const playSFXRef = useRef(playSFX)
  useEffect(() => { playSFXRef.current = playSFX }, [playSFX])

  useEffect(() => {
    playSFXRef.current('player_death')
  }, [])

  return (
    <BaseDialog
      title="Defeat"
      variant="danger"
      maxWidth="720px"
      zIndex={zIndex.raisedDialog}
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

        {isLoadingSaves && <div style={{ color: colors.text.muted }}>Loading…</div>}

        {!isLoadingSaves && saveOptions.length === 0 && (
          <div style={{ color: colors.text.muted }}>No saves found.</div>
        )}

        {!isLoadingSaves && saveOptions.length > 0 && (
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
              onClick={loadSave}
              disabled={isSubmitting || !selectedSaveId}
              variant="danger"
            >
              {isRestoringSave ? 'LOADING…' : 'LOAD'}
            </GameButton>
          </div>
        )}
      </div>

      {/* Outside the "Load save" panel: this line also carries START OVER's
          failures, which have nothing to do with loading a save. */}
      {error && <div style={{ marginBottom: spacing.sm, color: colors.text.danger }}>{error}</div>}

      <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
        <GameButton
          onClick={startOver}
          disabled={isLoadingSaves || isSubmitting}
          variant="secondary"
          style={{ border: `1px solid ${colors.border.danger}`, color: colors.text.danger }}
        >
          START OVER
        </GameButton>
      </div>
    </BaseDialog>
  )
}
