import { useState, useRef } from 'react'
import BaseDialog from './BaseDialog'
import GameButton from './GameButton'
import { colors, spacing, fonts } from '../styles/theme'
import { feedback as feedbackApi } from '../api/endpoints'
import { useToast } from '../context/ToastContext'
import { apiErrorMessage } from '../utils/apiError'

const TYPES = [
  { id: 'bug', label: 'Bug Report' },
  { id: 'feature', label: 'Feature Request' },
  { id: 'general', label: 'General Feedback' },
]

const SEVERITY_OPTIONS = ['low', 'medium', 'high']

const RATING_DIMENSIONS = [
  { key: 'story', label: 'Story & Narrative' },
  { key: 'combat', label: 'Combat & Gameplay' },
  { key: 'audio', label: 'Audio & Music' },
  { key: 'visuals', label: 'Visuals & Aesthetics' },
  { key: 'difficulty', label: 'Difficulty & Balance' },
]

const inputStyle = {
  width: '100%',
  backgroundColor: colors.bg.input,
  color: colors.text.main,
  border: `1px solid ${colors.primary}66`,
  borderRadius: '4px',
  padding: `${spacing.sm} ${spacing.md}`,
  fontFamily: fonts.main,
  // issue #542: was 13px. iOS zooms the whole page on focus below 16px, and
  // this inline style overrode index.css's sitewide
  // `input, select, textarea { font-size: 16px }` safeguard, so that rule
  // never actually reached any field in this dialog (TITLE included, the
  // only always-visible free-text field on the beta route).
  fontSize: '16px',
  resize: 'vertical',
  boxSizing: 'border-box',
  outline: 'none',
  transition: 'border-color 0.2s',
}

const labelStyle = {
  display: 'block',
  color: colors.accent,
  fontSize: '11px',
  letterSpacing: '0.5px',
  marginBottom: spacing.xs,
  textTransform: 'uppercase',
}

/**
 * The visible caption above a field.
 *
 * Deliberately a <span> and NOT a <label htmlFor>: two of its uses caption a
 * button group ("Severity") and a set of star buttons ("Ratings (optional)"),
 * neither of which is a labelable form control, so `htmlFor` would be invalid
 * there. The controls carry their own `aria-label` instead — the established
 * idiom in this codebase — which is why every field must pass `ariaLabel`
 * matching its caption (#563 item 2).
 */
function FieldLabel({ children, required }) {
  return (
    <span style={labelStyle}>
      {children}
      {/* Visible required-indicator for a sighted user; the input's own
          aria-required carries the same fact to a screen reader (#540 item 11). */}
      {required && <span aria-hidden="true" style={{ color: colors.danger }}> *</span>}
    </span>
  )
}

function TextInput({ value, onChange, placeholder, style, error, required, inputRef, ariaLabel }) {
  return (
    <input
      ref={inputRef}
      type="text"
      value={value}
      onChange={onChange}
      placeholder={placeholder}
      // The placeholder is not a name: it vanishes as soon as the player types,
      // so without this the field had an empty accessible name (#563 item 2).
      aria-label={ariaLabel}
      required={required || undefined}
      aria-required={required || undefined}
      aria-invalid={error || undefined}
      style={{
        ...inputStyle,
        // The error state lives ON the field (border), not only in a toast
        // ~500px away with no visual cue on the field itself (#540 item 11).
        // Overrides the full `border` shorthand (not just borderColor) —
        // inputStyle sets `border`, and mixing the shorthand with a longhand
        // for the same value trips React's "removing a style property"
        // warning when the error clears on rerender.
        ...(error ? { border: `1px solid ${colors.danger}` } : {}),
        ...style,
      }}
      onFocus={(e) => (e.target.style.borderColor = error ? colors.danger : colors.primary)}
      onBlur={(e) => (e.target.style.borderColor = error ? colors.danger : `${colors.primary}66`)}
    />
  )
}

function TextArea({ value, onChange, placeholder, rows = 3, ariaLabel }) {
  return (
    <textarea
      rows={rows}
      value={value}
      onChange={onChange}
      placeholder={placeholder}
      aria-label={ariaLabel}
      style={inputStyle}
      onFocus={(e) => (e.target.style.borderColor = colors.primary)}
      onBlur={(e) => (e.target.style.borderColor = `${colors.primary}66`)}
    />
  )
}

function StarRating({ dimension, value, onChange }) {
  const [hovered, setHovered] = useState(0)

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: spacing.sm, marginBottom: spacing.xs }}>
      <span style={{ color: colors.text.muted, fontSize: '12px', width: '130px', flexShrink: 0 }}>
        {dimension.label}
      </span>
      <div style={{ display: 'flex', gap: '2px' }}>
        {[1, 2, 3, 4, 5].map((star) => {
          const filled = star <= (hovered || value)
          return (
            <button
              key={star}
              onClick={() => onChange(star === value ? 0 : star)}
              onMouseEnter={() => setHovered(star)}
              onMouseLeave={() => setHovered(0)}
              style={{
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                fontSize: '18px',
                color: filled ? colors.gold : colors.text.dim,
                padding: '0 1px',
                lineHeight: 1,
                transition: 'color 0.1s, transform 0.1s',
                transform: filled ? 'scale(1.15)' : 'scale(1)',
              }}
              title={`${star} star${star !== 1 ? 's' : ''}`}
            >
              {filled ? '★' : '☆'}
            </button>
          )
        })}
      </div>
      {value > 0 && (
        <span style={{ color: colors.text.muted, fontSize: '11px' }}>{value}/5</span>
      )}
    </div>
  )
}

function BugForm({ fields, onChange }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.md }}>
      <div>
        <FieldLabel>Steps to Reproduce</FieldLabel>
        <TextArea
          rows={3}
          ariaLabel="Steps to Reproduce"
          value={fields.steps}
          onChange={(e) => onChange('steps', e.target.value)}
          placeholder="1. Go to...&#10;2. Click...&#10;3. Observe..."
        />
      </div>
      <div>
        <FieldLabel>Expected Behavior</FieldLabel>
        <TextArea
          rows={2}
          ariaLabel="Expected Behavior"
          value={fields.expected}
          onChange={(e) => onChange('expected', e.target.value)}
          placeholder="What should have happened?"
        />
      </div>
      <div>
        <FieldLabel>Actual Behavior</FieldLabel>
        <TextArea
          rows={2}
          ariaLabel="Actual Behavior"
          value={fields.actual}
          onChange={(e) => onChange('actual', e.target.value)}
          placeholder="What actually happened?"
        />
      </div>
      <div>
        <FieldLabel>Severity</FieldLabel>
        {/* The caption is a <span>, so without this the three buttons read as
            three loose controls with no idea what they select (#563 item 2). */}
        <div role="group" aria-label="Severity" style={{ display: 'flex', gap: spacing.sm }}>
          {SEVERITY_OPTIONS.map((sev) => {
            const active = fields.severity === sev
            const severityColor = { low: colors.gold, medium: colors.secondary, high: colors.danger }[sev]
            return (
              <button
                key={sev}
                onClick={() => onChange('severity', sev)}
                aria-pressed={active}
                style={{
                  flex: 1,
                  // #564: these measured 96.8 x 28 at 375px — 64% of the 44px
                  // touch minimum. Height, not width: three flex:1 buttons have
                  // to keep sharing one row inside a ~330px dialog body, so a
                  // minWidth big enough to matter would wrap them instead.
                  minHeight: '44px',
                  padding: `${spacing.xs} ${spacing.sm}`,
                  backgroundColor: active ? `${severityColor}22` : 'transparent',
                  border: `1px solid ${active ? severityColor : colors.text.dim}`,
                  borderRadius: '4px',
                  color: active ? severityColor : colors.text.muted,
                  cursor: 'pointer',
                  fontFamily: fonts.main,
                  fontSize: '12px',
                  textTransform: 'uppercase',
                  transition: 'all 0.15s',
                }}
              >
                {sev}
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}

function FeatureForm({ fields, onChange }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.md }}>
      <div>
        <FieldLabel>Description</FieldLabel>
        <TextArea
          rows={3}
          ariaLabel="Description"
          value={fields.description}
          onChange={(e) => onChange('description', e.target.value)}
          placeholder="Describe the feature you'd like to see..."
        />
      </div>
      <div>
        <FieldLabel>Use Case / Why</FieldLabel>
        <TextArea
          rows={3}
          ariaLabel="Use Case / Why"
          value={fields.use_case}
          onChange={(e) => onChange('use_case', e.target.value)}
          placeholder="Why would this improve the game?"
        />
      </div>
    </div>
  )
}

function GeneralForm({ fields, onChange, ratings, onRatingChange }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.md }}>
      <div>
        <FieldLabel>Message</FieldLabel>
        <TextArea
          rows={4}
          ariaLabel="Message"
          value={fields.message}
          onChange={(e) => onChange('message', e.target.value)}
          placeholder="Share your thoughts about the game..."
        />
      </div>
      <div>
        <FieldLabel>Ratings (optional)</FieldLabel>
        <div
          style={{
            backgroundColor: colors.bg.panel,
            border: `1px solid ${colors.primary}22`,
            borderRadius: '6px',
            padding: spacing.md,
          }}
        >
          {RATING_DIMENSIONS.map((dim) => (
            <StarRating
              key={dim.key}
              dimension={dim}
              value={ratings[dim.key] || 0}
              onChange={(val) => onRatingChange(dim.key, val)}
            />
          ))}
          <div style={{ color: colors.text.dim, fontSize: '11px', marginTop: spacing.xs }}>
            Click a star again to clear it. Leave any dimension unrated to skip it.
          </div>
        </div>
      </div>
    </div>
  )
}

const EMPTY_BUG = { steps: '', expected: '', actual: '', severity: 'medium' }
const EMPTY_FEATURE = { description: '', use_case: '' }
const EMPTY_GENERAL = { message: '' }
const EMPTY_RATINGS = { story: 0, combat: 0, audio: 0, visuals: 0, difficulty: 0 }

export default function FeedbackDialog({ onClose, initialType = 'bug' }) {
  const { success: toastSuccess, error: toastError } = useToast()

  const validInitialType = TYPES.some(t => t.id === initialType) ? initialType : 'bug'
  const [activeType, setActiveType] = useState(validInitialType)
  const [title, setTitle] = useState('')
  const [titleError, setTitleError] = useState(false)
  const [submitError, setSubmitError] = useState(null)
  const [anonymous, setAnonymous] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const [bugFields, setBugFields] = useState({ ...EMPTY_BUG })
  const [featureFields, setFeatureFields] = useState({ ...EMPTY_FEATURE })
  const [generalFields, setGeneralFields] = useState({ ...EMPTY_GENERAL })
  const [ratings, setRatings] = useState({ ...EMPTY_RATINGS })
  const submittingRef = useRef(false)
  const titleInputRef = useRef(null)

  const handleTypeChange = (type) => {
    setActiveType(type)
    setTitle('')
    setTitleError(false)
  }

  const handleTitleChange = (e) => {
    setTitle(e.target.value)
    if (titleError) setTitleError(false)
  }

  const handleFieldChange = (setter) => (key, value) => {
    setter((prev) => ({ ...prev, [key]: value }))
  }

  const handleRatingChange = (key, value) => {
    setRatings((prev) => ({ ...prev, [key]: value }))
  }

  const getActiveFields = () => {
    if (activeType === 'bug') return bugFields
    if (activeType === 'feature') return featureFields
    const enriched = { ...generalFields }
    const hasRatings = Object.values(ratings).some((v) => v > 0)
    if (hasRatings) enriched.ratings = ratings
    return enriched
  }

  /**
   * #556: a toast was the ONLY notice of a failed submit, and it auto-dismisses
   * after 5s while the filled-in report stays on screen behind an overlay whose
   * own onClick discards it -- so the notice expired while the thing it was
   * about was still destructible. Keep the toast for immediacy and add a
   * durable in-dialog panel that outlives it.
   */
  const failSubmit = (message) => {
    const text = message || 'Could not submit feedback — please try again later.'
    setSubmitError(text)
    toastError(text)
  }

  const handleSubmit = async () => {
    if (submittingRef.current) return
    if (!title.trim()) {
      // The toast alone put the error ~500px from the empty field with no
      // border/focus cue on the field itself (#540 item 11) — put the error
      // state ON the field too, and move focus there.
      setTitleError(true)
      titleInputRef.current?.focus()
      toastError('Please enter a title for your feedback.')
      return
    }
    setTitleError(false)
    setSubmitError(null)
    submittingRef.current = true
    setSubmitting(true)
    try {
      const fields = getActiveFields()
      const res = await feedbackApi.submitIssue(activeType, title.trim(), fields, anonymous)
      // A 2xx body can still carry success:false. No current route returns
      // that -- every failure here is a 400, 429 or 503 -- but the thank-you
      // used to fire unconditionally, so the day one does, the report is lost
      // silently all over again (#556).
      if (res?.data?.success === false) {
        failSubmit(res.data.error || res.data.message)
        return
      }
      toastSuccess('Feedback submitted! Thank you.')
      onClose()
    } catch (err) {
      failSubmit(apiErrorMessage(err, 'Could not submit feedback — please try again later.'))
    } finally {
      submittingRef.current = false
      setSubmitting(false)
    }
  }

  const tabBase = {
    flex: 1,
    padding: `${spacing.xs} ${spacing.sm}`,
    border: 'none',
    cursor: 'pointer',
    fontFamily: fonts.main,
    fontSize: '12px',
    fontWeight: 'bold',
    textTransform: 'uppercase',
    letterSpacing: '0.5px',
    transition: 'all 0.15s',
    borderBottom: '2px solid transparent',
  }

  return (
    <BaseDialog title="Send Feedback" onClose={onClose} maxWidth="520px">
      {/* Type tabs */}
      <div
        style={{
          display: 'flex',
          marginBottom: spacing.lg,
          borderBottom: `1px solid ${colors.primary}33`,
        }}
      >
        {TYPES.map((t) => {
          const active = activeType === t.id
          return (
            <button
              key={t.id}
              onClick={() => handleTypeChange(t.id)}
              style={{
                ...tabBase,
                backgroundColor: active ? `${colors.primary}15` : 'transparent',
                color: active ? colors.primary : colors.text.muted,
                borderBottom: active ? `2px solid ${colors.primary}` : '2px solid transparent',
              }}
              onMouseEnter={(e) => {
                if (!active) e.currentTarget.style.color = colors.text.main
              }}
              onMouseLeave={(e) => {
                if (!active) e.currentTarget.style.color = colors.text.muted
              }}
            >
              {t.label}
            </button>
          )
        })}
      </div>

      {/* Title */}
      <div style={{ marginBottom: spacing.md }}>
        <FieldLabel required>Title</FieldLabel>
        <TextInput
          inputRef={titleInputRef}
          ariaLabel="Title"
          value={title}
          onChange={handleTitleChange}
          error={titleError}
          required
          placeholder={
            activeType === 'bug'
              ? 'Short description of the bug...'
              : activeType === 'feature'
              ? 'What feature would you like?'
              : 'Summary of your feedback...'
          }
        />
      </div>

      {/* Type-specific fields */}
      {activeType === 'bug' && (
        <BugForm fields={bugFields} onChange={handleFieldChange(setBugFields)} />
      )}
      {activeType === 'feature' && (
        <FeatureForm fields={featureFields} onChange={handleFieldChange(setFeatureFields)} />
      )}
      {activeType === 'general' && (
        <GeneralForm
          fields={generalFields}
          onChange={handleFieldChange(setGeneralFields)}
          ratings={ratings}
          onRatingChange={handleRatingChange}
        />
      )}

      {/* Anonymous toggle */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: spacing.sm,
          marginTop: spacing.lg,
          padding: `${spacing.sm} ${spacing.md}`,
          backgroundColor: anonymous ? colors.bg.highlight : colors.bg.panel,
          border: `1px solid ${anonymous ? colors.secondary + '66' : colors.primary + '22'}`,
          borderRadius: '4px',
          cursor: 'pointer',
          transition: 'all 0.15s',
        }}
        onClick={() => setAnonymous((prev) => !prev)}
      >
        <div
          style={{
            width: '16px',
            height: '16px',
            border: `2px solid ${anonymous ? colors.secondary : colors.text.muted}`,
            borderRadius: '3px',
            backgroundColor: anonymous ? colors.secondary : 'transparent',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
            transition: 'all 0.15s',
          }}
        >
          {anonymous && (
            <span style={{ color: colors.text.inverse, fontSize: '11px', fontWeight: 'bold', lineHeight: 1 }}>
              ✓
            </span>
          )}
        </div>
        <span style={{ color: anonymous ? colors.secondary : colors.text.muted, fontSize: '12px', userSelect: 'none' }}>
          Submit anonymously (your username will not appear on the issue)
        </span>
      </div>

      {submitError && (
        <div
          role="alert"
          style={{
            color: colors.danger,
            fontSize: '0.75rem',
            padding: '8px 12px',
            marginTop: spacing.md,
            background: 'rgba(255,68,68,0.1)',
            border: '1px solid rgba(255,68,68,0.3)',
            borderRadius: '6px',
          }}
        >
          ⚠ {submitError} Your report is still here — you can try again.
        </div>
      )}

      {/* Actions */}
      <div
        style={{
          display: 'flex',
          gap: spacing.md,
          justifyContent: 'flex-end',
          marginTop: spacing.lg,
          paddingTop: spacing.md,
          borderTop: `1px solid ${colors.primary}22`,
        }}
      >
        <GameButton onClick={onClose} variant="secondary" disabled={submitting}>
          Cancel
        </GameButton>
        <GameButton onClick={handleSubmit} variant="primary" disabled={submitting}>
          {submitting ? 'Submitting...' : 'Submit Feedback'}
        </GameButton>
      </div>
    </BaseDialog>
  )
}
