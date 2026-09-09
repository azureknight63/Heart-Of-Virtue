import React, { useState } from 'react'

import BaseDialog from './BaseDialog'
import GameButton from './GameButton'
import GameText from './GameText'
import useJournal from '../hooks/useJournal'
import { colors, spacing } from '../styles/theme'

const TABS = [
    { key: 'objectives', label: 'OBJECTIVES' },
    { key: 'log', label: 'STORY LOG' },
]

/**
 * One objective row. A completed objective is kept and struck through rather
 * than removed: "what have I done here" is as much of an orientation question
 * as "what do I do next", and a list that empties itself tells the player
 * nothing about where they are in the chapter.
 */
function ObjectiveRow({ objective, done = false }) {
    return (
        <li
            style={{
                display: 'flex',
                alignItems: 'flex-start',
                gap: spacing.sm,
                padding: `${spacing.xs} 0`,
                opacity: done ? 0.55 : 1,
            }}
        >
            <span aria-hidden="true" style={{ color: done ? colors.text.muted : colors.secondary }}>
                {done ? '✓' : '▸'}
            </span>
            <GameText
                variant={done ? 'muted' : 'success'}
                size="sm"
                style={{ textDecoration: done ? 'line-through' : 'none', lineHeight: 1.5 }}
            >
                {objective.text}
            </GameText>
        </li>
    )
}

/** One recorded scene: its location heading and its attributed lines. */
function SceneEntry({ scene }) {
    return (
        <div
            style={{
                borderLeft: `2px solid ${colors.border.light}`,
                paddingLeft: spacing.md,
                marginBottom: spacing.lg,
            }}
        >
            <GameText variant="secondary" size="xs" weight="bold" style={{ letterSpacing: '0.08em' }}>
                {String(scene.title || '').toUpperCase()}
            </GameText>
            <div style={{ marginTop: spacing.xs, display: 'flex', flexDirection: 'column', gap: spacing.xs }}>
                {(scene.lines || []).map((line, idx) => (
                    <div key={idx} style={{ whiteSpace: 'pre-wrap', lineHeight: 1.55 }}>
                        {line.speaker && (
                            <GameText
                                as="span"
                                variant="secondary"
                                size="xs"
                                weight="bold"
                                style={{ marginRight: spacing.sm }}
                            >
                                {String(line.speaker).toUpperCase()}
                            </GameText>
                        )}
                        <GameText as="span" variant={line.speaker ? 'main' : 'muted'} size="sm">
                            {line.text}
                        </GameText>
                    </div>
                ))}
            </div>
        </div>
    )
}

/**
 * JournalDialog — standing objectives and the transcript of scripted scenes.
 *
 * Both halves exist because story text used to be write-only: an objective was
 * spoken once in a modal that closed, and the event dialog's own LOG button was
 * cleared as soon as the event queue drained, so a player who stepped away had
 * no way back to either (issue #538 item 4).
 *
 * The newest scene is shown first. A transcript is consulted, not read
 * front-to-back, and what the player just clicked past is overwhelmingly what
 * they are looking for.
 */
export default function JournalDialog({ onClose }) {
    const [tab, setTab] = useState(TABS[0].key)
    const { journal, isLoading, error, reload } = useJournal()

    const objectives = journal?.objectives || []
    const completed = journal?.completed || []
    // Newest first; `slice` because `reverse` mutates, and this array is the
    // one held in state.
    const scenes = (journal?.log || []).slice().reverse()

    return (
        <BaseDialog title="📖 JOURNAL" onClose={onClose} maxWidth="760px">
            <div style={{ display: 'flex', gap: spacing.sm, marginBottom: spacing.md }}>
                {TABS.map(({ key, label }) => (
                    <GameButton
                        key={key}
                        onClick={() => setTab(key)}
                        variant={tab === key ? 'primary' : 'secondary'}
                        size="small"
                    >
                        {label}
                    </GameButton>
                ))}
            </div>

            <div
                data-testid="journal-body"
                style={{
                    minHeight: '260px',
                    maxHeight: '52vh',
                    overflowY: 'auto',
                    padding: spacing.md,
                    backgroundColor: colors.bg.panelDeep,
                    border: `1px solid ${colors.border.light}`,
                    borderRadius: '6px',
                }}
            >
                {isLoading && <GameText variant="muted" size="sm">Reading the journal…</GameText>}

                {!isLoading && error && (
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start', gap: spacing.sm }}>
                        <GameText variant="danger" size="sm">{error}</GameText>
                        <GameButton onClick={reload} variant="secondary" size="small">RETRY</GameButton>
                    </div>
                )}

                {!isLoading && !error && tab === 'objectives' && (
                    objectives.length === 0 && completed.length === 0 ? (
                        <GameText variant="muted" size="sm">
                            No objectives yet. They appear as the story gives Jean something to do.
                        </GameText>
                    ) : (
                        <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
                            {objectives.map((objective) => (
                                <ObjectiveRow key={objective.key} objective={objective} />
                            ))}
                            {completed.map((objective) => (
                                <ObjectiveRow key={objective.key} objective={objective} done />
                            ))}
                        </ul>
                    )
                )}

                {!isLoading && !error && tab === 'log' && (
                    scenes.length === 0 ? (
                        <GameText variant="muted" size="sm">
                            Nothing recorded yet. Scenes are kept here as Jean lives them.
                        </GameText>
                    ) : (
                        scenes.map((scene, idx) => (
                            // The transcript has no id of its own; title+tick+index is
                            // stable enough that a refetch does not reshuffle subtrees.
                            <SceneEntry key={`${scene.title}-${scene.tick}-${idx}`} scene={scene} />
                        ))
                    )
                )}
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: spacing.md }}>
                <GameButton onClick={onClose} variant="secondary">CLOSE</GameButton>
            </div>
        </BaseDialog>
    )
}
