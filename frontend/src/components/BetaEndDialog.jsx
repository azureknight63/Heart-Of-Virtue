import BaseDialog from './BaseDialog'
import GameButton from './GameButton'
import { colors, spacing, fonts } from '../styles/theme'

/**
 * BetaEndDialog - Shown after defeating the Lurker to mark the end of the beta.
 * Thanks the tester and offers to open the feedback dialog or continue exploring.
 *
 * @param {Function} props.onSendFeedback - Opens the feedback dialog (preset to general)
 * @param {Function} props.onContinue - Dismisses this dialog and returns to the game
 */
export default function BetaEndDialog({ onSendFeedback = () => {}, onContinue = () => {} }) {
  return (
    <BaseDialog
      title="END OF BETA"
      maxWidth="500px"
      zIndex={3000}
      showCloseButton={false}
    >
      <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.lg }}>

        {/* Decorative divider */}
        <div style={{
          borderTop: `1px solid ${colors.primary}55`,
          marginTop: spacing.xs,
        }} />

        {/* Thank-you message */}
        <p style={{
          fontFamily: fonts.main,
          fontSize: '14px',
          color: colors.text.main,
          lineHeight: 1.7,
          margin: 0,
        }}>
          You've reached the end of the beta. The Lurker is defeated — Verdette Caverns is yours to
          explore, but the road onward opens with the full release.
        </p>

        <p style={{
          fontFamily: fonts.main,
          fontSize: '14px',
          color: colors.text.main,
          lineHeight: 1.7,
          margin: 0,
        }}>
          Thank you for playing. Every piece of feedback shapes what comes next — if you've got
          thoughts on the story, the combat, or anything else you noticed, we'd love to hear them.
        </p>

        {/* Button row */}
        <div style={{
          display: 'flex',
          gap: spacing.md,
          justifyContent: 'flex-end',
          marginTop: spacing.sm,
        }}>
          <GameButton variant="secondary" onClick={onContinue}>
            Continue Exploring
          </GameButton>
          <GameButton variant="primary" onClick={onSendFeedback}>
            Send Feedback
          </GameButton>
        </div>

      </div>
    </BaseDialog>
  )
}
