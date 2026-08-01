import React, { useState } from 'react'
import BaseDialog from './BaseDialog'
import GameButton from './GameButton'
import TypewriterOutput from './TypewriterOutput'
import { colors, spacing } from '../styles/theme'

/**
 * PreVictoryNarrativeDialog - A single narration-only beat (CombatEventConfig.on_victory_text,
 * issue #427) shown immediately before VictoryDialog for scripted encounters that want a
 * story beat ("the crowd erupts in cheers") before the exp/loot screen takes over.
 */
export default function PreVictoryNarrativeDialog({ text, onClose }) {
    const [isComplete, setIsComplete] = useState(false)

    return (
        <BaseDialog
            title="✨ Victory"
            onClose={isComplete ? onClose : undefined}
            showCloseButton={isComplete}
            zIndex={2900}
            maxWidth="700px"
        >
            <div style={{ padding: spacing.lg }}>
                <TypewriterOutput
                    text={text}
                    speed={25}
                    onComplete={() => setIsComplete(true)}
                    style={{
                        border: `2px solid ${colors.secondary}`,
                        color: colors.success,
                        whiteSpace: 'pre-wrap',
                        fontSize: '16px',
                        padding: spacing.lg,
                    }}
                />
            </div>

            {isComplete && (
                <div style={{ textAlign: 'center', marginTop: spacing.md }}>
                    <GameButton onClick={onClose} variant="secondary" style={{ padding: '10px 40px' }}>
                        Continue
                    </GameButton>
                </div>
            )}
        </BaseDialog>
    )
}
