import BaseDialog from './BaseDialog'
import ConversationTranscript from './ConversationTranscript'
import { colors, spacing, fonts } from '../styles/theme'

/**
 * ConversationHistoryDialog — the full record of a conversation, on demand.
 *
 * Renders from the segment list the caller already holds rather than re-fetching
 * `/npc/chat/history/<key>`: the client-side segments carry the per-turn emotion
 * and flavor that the portraits and layout need, and the server record does not.
 *
 * Opens at the top (oldest turn first) on purpose — the live panel behind it
 * already shows the newest lines, so what the player came here for is the part
 * that has scrolled out of the scene.
 */
export default function ConversationHistoryDialog({
    title = 'Conversation History',
    segments = [],
    cast = [],
    onClose,
}) {
    const turns = segments.length

    return (
        <BaseDialog
            title={title}
            onClose={onClose}
            variant="default"
            maxWidth="720px"
            width="min(94vw, 720px)"
            padding={spacing.lg}
            zIndex={2200}
        >
            <div
                data-testid="conversation-history-count"
                style={{
                    color: colors.text.dim,
                    fontFamily: fonts.main,
                    fontSize: '11px',
                    letterSpacing: '1px',
                    textTransform: 'uppercase',
                    marginBottom: spacing.md,
                }}
            >
                {turns} {turns === 1 ? 'turn' : 'turns'} on record
            </div>
            <div
                data-testid="conversation-history"
                style={{ maxHeight: '65vh', overflowY: 'auto', paddingRight: spacing.xs }}
            >
                <ConversationTranscript
                    segments={segments}
                    cast={cast}
                    emptyText="Nothing has been said yet."
                />
            </div>
        </BaseDialog>
    )
}
