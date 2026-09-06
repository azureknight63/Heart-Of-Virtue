import PortraitImage from './PortraitImage'
import GameText from './GameText'
import { DEFAULT_EMOTION } from '../utils/conversationSegment'
import { colors, spacing, fonts, commonStyles } from '../styles/theme'

/**
 * Thumbnail sizes, in the two densities a transcript entry is used at:
 * `compact` for the recap strip that sits above a live conversation, `full`
 * for the scrollable history. Both are far below the stage portrait, whose
 * width lives in index.css under the custom property styles/theme.js's
 * `STAGE_PORTRAIT_WIDTH_VAR` names (and is wider still under the wide layout's
 * clamp) — these are identifiers, not performances.
 */
export const THUMB_SIZES = { compact: '40px', full: '56px' }

/**
 * Resolve a segment's speaker against the cast roster (name + which side they
 * stand on).
 *
 * `id` is echoed back deliberately: the return value is a complete
 * roster-shaped record a caller can pass on whole (and a test can assert as one
 * object), rather than a pair the caller then has to re-associate with the
 * speaker it asked about.
 */
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
 * Reads the shared conversation-segment contract (utils/conversationSegment):
 * `text`, `speaker`, `emotion` and `flavor`. `reactions`, `in_conversation`,
 * `thought`, `enter` and `exit` are DELIBERATELY not honoured here — a
 * transcript row is one speaker's line, with no stage for a listener to react
 * on and no beat-by-beat staging to change. That module records which renderer
 * honours what, so this is a documented decision rather than a silent drop.
 *
 * @param {import('../utils/conversationSegment').ConversationSegment} segment
 * @param {Array}  cast    - roster used to resolve display name and side
 * @param {'compact'|'full'} [variant] - density; compact clamps to two lines
 */
export function TranscriptEntry({ segment = {}, cast = [], variant = 'full' }) {
    const { text = '', speaker, emotion = DEFAULT_EMOTION, flavor = '' } = segment
    const isCompact = variant === 'compact'

    if (!speaker) {
        return (
            <GameText
                as="div"
                variant="muted"
                align="center"
                size={isCompact ? 'xs' : 'sm'}
                data-testid="transcript-entry"
                data-side="center"
                style={{
                    fontStyle: 'italic',
                    lineHeight: 1.6,
                    padding: spacing.sm,
                }}
            >
                {text}
            </GameText>
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
                // The full transcript mounts one of these per turn inside a
                // 65vh scroller, so all but the first screenful start off
                // screen. The compact recap strip is always visible.
                lazy={!isCompact}
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
                        ...commonStyles.eyebrowLabel,
                        alignSelf: variantStyles.labelAlign,
                        fontWeight: 'bold',
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
 * Reads the same segment list that drives `ConversationStage` (the shared
 * contract in utils/conversationSegment), so every turn carries its own emotion
 * — and therefore its own portrait — rather than the speaker's latest mood. See
 * `TranscriptEntry` above for which fields of that shape a row honours.
 *
 * @param {import('../utils/conversationSegment').ConversationSegment[]} [segments]
 * @param {Array} [cast]
 * @param {string} [emptyText] - copy for a conversation with nothing on record.
 *   No production caller overrides it today; it stays a parameter because the
 *   empty state is the one string that reads differently per surface (a live
 *   chat's history vs. an archived record), and the alternative is a literal
 *   buried mid-component.
 */
export default function ConversationTranscript({
    segments = [],
    cast = [],
    emptyText = 'Nothing has been said yet.',
}) {
    if (segments.length === 0) {
        return (
            <GameText
                as="div"
                variant="muted"
                align="center"
                size="sm"
                data-testid="transcript-empty"
                style={{ fontStyle: 'italic', padding: spacing.xl }}
            >
                {emptyText}
            </GameText>
        )
    }

    return (
        <div
            data-testid="conversation-transcript"
            style={{ display: 'flex', flexDirection: 'column', gap: spacing.md }}
        >
            {/* Index keys, unusually, are correct here: a transcript is
                append-only and is never reordered, filtered or de-duplicated,
                so the index IS each turn's stable identity. The text is not —
                two identical lines in one conversation are ordinary — and the
                wire carries no per-beat id. (Contrast NpcChatPanel's option
                buttons, where the list IS replaced wholesale every turn and an
                index key really does re-point a focused control at a different
                choice.) */}
            {segments.map((segment, idx) => (
                <TranscriptEntry key={idx} segment={segment} cast={cast} />
            ))}
        </div>
    )
}
