import PortraitImage from './PortraitImage'
import { colors, spacing, fonts } from '../styles/theme'

/**
 * Thumbnail sizes, in the two densities a transcript entry is used at:
 * `compact` for the recap strip that sits above a live conversation, `full`
 * for the scrollable history. Both are far below the 130px stage portrait —
 * these are identifiers, not performances.
 */
export const THUMB_SIZES = { compact: '40px', full: '56px' }

/** Resolve a segment's speaker against the cast roster (name + which side they stand on). */
export function castMember(cast, speaker) {
    const found = (cast || []).find((member) => member.id === speaker)
    return {
        id: speaker,
        // An LLM turn can name a speaker the roster never staged; fall back to
        // the raw id rather than rendering a nameless line.
        name: found?.name || speaker,
        side: found?.side || 'right',
    }
}

/**
 * TranscriptEntry — one spoken turn: portrait thumbnail, speaker, flavor, line.
 *
 * Jean's side of the conversation reads left with the lime accent, everyone
 * else reads right in amber, mirroring where they stand on `ConversationStage`
 * so the transcript and the live scene agree at a glance. Speaker-less beats
 * (narration) render as centered prose with no portrait.
 *
 * @param {Object} segment - `{ text, speaker, emotion, flavor }`
 * @param {Array}  cast    - roster used to resolve display name and side
 * @param {'compact'|'full'} [variant] - density; compact clamps to two lines
 */
export function TranscriptEntry({ segment = {}, cast = [], variant = 'full' }) {
    const { text = '', speaker, emotion = 'neutral', flavor = '' } = segment
    const isCompact = variant === 'compact'

    if (!speaker) {
        return (
            <div
                data-testid="transcript-entry"
                data-side="center"
                style={{
                    color: colors.text.muted,
                    fontFamily: fonts.main,
                    fontSize: isCompact ? '12px' : '13px',
                    fontStyle: 'italic',
                    lineHeight: 1.6,
                    textAlign: 'center',
                    padding: spacing.sm,
                }}
            >
                {text}
            </div>
        )
    }

    const { name, side } = castMember(cast, speaker)
    const isLeft = side === 'left'
    const accent = isLeft ? colors.primary : colors.secondary
    const size = isCompact ? THUMB_SIZES.compact : THUMB_SIZES.full

    // Every density/side-dependent style is resolved once here rather than
    // re-checking isCompact/isLeft at each of the properties below.
    const variantStyles = {
        portraitOpacity: isCompact ? 0.85 : 1,
        bubbleGap: isCompact ? spacing.sm : spacing.md,
        // The bubble hugs its speaker's side rather than filling the row:
        // side + accent carry the identity, so the prose itself can stay
        // left-aligned instead of going ragged-left.
        bubbleFlex: isCompact ? 1 : '0 1 auto',
        bubbleMaxWidth: isCompact ? '100%' : '82%',
        bubblePadding: isCompact ? `${spacing.xs} ${spacing.sm}` : spacing.md,
        // All four border edges are declared longhand on purpose: the same
        // DOM node is reused as the recap strip switches speakers, and
        // dropping a `borderLeft`/`borderRight` while a `border` shorthand is
        // set makes React warn and can leave the old edge painted.
        borderLeft: isLeft ? `3px solid ${accent}` : `1px solid ${colors.border.light}`,
        borderRight: isLeft ? `1px solid ${colors.border.light}` : `3px solid ${accent}`,
        // The label sits nearest its own portrait; only the prose below it is
        // always left-aligned.
        labelAlign: isLeft ? 'flex-start' : 'flex-end',
        labelOpacity: isCompact ? 0.8 : 1,
        textColor: isCompact ? colors.text.muted : colors.text.main,
        textFontSize: isCompact ? '13px' : '14px',
        // The recap is a reminder, not a re-read: clamp it to two lines so a
        // long turn can't push the live stage off screen.
        textClamp: isCompact
            ? { display: '-webkit-box', WebkitBoxOrient: 'vertical', WebkitLineClamp: 2, overflow: 'hidden' }
            : {},
    }

    return (
        <div
            data-testid="transcript-entry"
            data-side={side}
            data-speaker={speaker}
            style={{
                display: 'flex',
                flexDirection: isLeft ? 'row' : 'row-reverse',
                alignItems: 'flex-start',
                gap: variantStyles.bubbleGap,
            }}
        >
            <PortraitImage
                speaker={speaker}
                name={name}
                emotion={emotion}
                style={{
                    width: size,
                    // Portrait art is a framed card (328x468 with a drawn
                    // border), so it scales rather than crops — a square crop
                    // would slice the frame off mid-rivet.
                    height: 'auto',
                    flexShrink: 0,
                    borderRadius: '6px',
                    border: `1px solid ${accent}55`,
                    opacity: variantStyles.portraitOpacity,
                }}
            />
            <div
                style={{
                    flex: variantStyles.bubbleFlex,
                    minWidth: 0,
                    maxWidth: variantStyles.bubbleMaxWidth,
                    display: 'flex',
                    flexDirection: 'column',
                    gap: spacing.xs,
                    padding: variantStyles.bubblePadding,
                    backgroundColor: colors.bg.panelLight,
                    borderRadius: '8px',
                    borderTop: `1px solid ${colors.border.light}`,
                    borderBottom: `1px solid ${colors.border.light}`,
                    borderLeft: variantStyles.borderLeft,
                    borderRight: variantStyles.borderRight,
                }}
            >
                <span
                    style={{
                        alignSelf: variantStyles.labelAlign,
                        fontFamily: fonts.main,
                        fontSize: '11px',
                        fontWeight: 'bold',
                        letterSpacing: '1px',
                        textTransform: 'uppercase',
                        color: accent,
                        opacity: variantStyles.labelOpacity,
                    }}
                >
                    {name}
                </span>
                {flavor && (
                    <div
                        style={{
                            color: colors.text.muted,
                            fontFamily: fonts.main,
                            fontSize: '12px',
                            fontStyle: 'italic',
                            lineHeight: 1.45,
                        }}
                    >
                        {flavor}
                    </div>
                )}
                <div
                    style={{
                        color: variantStyles.textColor,
                        fontFamily: fonts.main,
                        fontSize: variantStyles.textFontSize,
                        lineHeight: 1.6,
                        whiteSpace: 'pre-wrap',
                        ...variantStyles.textClamp,
                    }}
                >
                    {text}
                </div>
            </div>
        </div>
    )
}

/**
 * ConversationTranscript — the full record of a conversation, oldest first.
 *
 * Reads the same segment list that drives `ConversationStage`, so every turn
 * carries its own emotion (and therefore its own portrait) rather than the
 * speaker's latest mood.
 */
export default function ConversationTranscript({
    segments = [],
    cast = [],
    emptyText = 'Nothing has been said yet.',
}) {
    if (segments.length === 0) {
        return (
            <div
                data-testid="transcript-empty"
                style={{
                    color: colors.text.muted,
                    fontFamily: fonts.main,
                    fontSize: '13px',
                    fontStyle: 'italic',
                    textAlign: 'center',
                    padding: spacing.xl,
                }}
            >
                {emptyText}
            </div>
        )
    }

    return (
        <div
            data-testid="conversation-transcript"
            style={{ display: 'flex', flexDirection: 'column', gap: spacing.md }}
        >
            {segments.map((segment, idx) => (
                <TranscriptEntry key={idx} segment={segment} cast={cast} />
            ))}
        </div>
    )
}
