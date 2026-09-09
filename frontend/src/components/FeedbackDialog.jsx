import { useState, useRef } from 'react'
import BaseDialog from './BaseDialog'
import GameButton from './GameButton'
import { colors, spacing, fonts, accessibility, commonStyles } from '../styles/theme'
import { feedback as feedbackApi } from '../api/endpoints'
import { useToast } from '../context/ToastContext'
import { apiErrorMessage } from '../utils/apiError'

const SUBMIT_FAILED_MESSAGE = 'Could not submit feedback — please try again later.'

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
 * there. The controls carry their own `aria-label` (or, for the star buttons,
 * a `title`) instead — the established idiom in this codebase — which is why
 * every field must carry its caption as its own accessible name: the
 * `ariaLabel` prop on TextInput/TextArea, or `aria-label` on a `role="group"`
 * wrapper (#563 item 2). `LabeledField` below is what keeps the two in step.
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

/**
 * A captioned field: the caption text is written ONCE and reaches both the
 * visible label and the control's accessible name.
 *
 * Because the caption is a <span> rather than a <label htmlFor> (see
 * FieldLabel), every field here needs the string twice — and without this
 * wrapper it would be typed out twice at each of nine sites, which is the
 * shape that drifts silently: a reworded caption leaves a screen reader
 * announcing the old name and nothing fails. It had already happened once,
 * to the ratings group.
 *
 * `children` is a function of the caption so that a control naming itself
 * through a prop (`ariaLabel` on TextArea/TextInput) and one naming itself
 * through a DOM attribute (`aria-label` on a `role="group"` wrapper) can both
 * be spelled without a second copy.
 */
function LabeledField({ label, required, style, children }) {
  return (
    <div style={style}>
      <FieldLabel required={required}>{label}</FieldLabel>
      {children(label)}
    </div>
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

/**
 * One free-text field: caption, textarea, and the accessible name that has to
 * match it.
 *
 * The six of them differ only in caption, row count, state key and
 * placeholder, and each wrapped those four values in the same `LabeledField`
 * render-prop ceremony. The ceremony now exists once. `LabeledField` itself
 * stays for the other three fields: the two `role="group"` captions, which
 * name themselves through a DOM attribute rather than a prop, and the Title
 * input, which carries `required`/`error`/`inputRef` besides.
 */
function LabeledTextArea({ label, rows, fieldKey, placeholder, fields, onChange }) {
  return (
    <LabeledField label={label}>
      {(name) => (
        <TextArea
          rows={rows}
          ariaLabel={name}
          value={fields[fieldKey]}
          onChange={(e) => onChange(fieldKey, e.target.value)}
          placeholder={placeholder}
        />
      )}
    </LabeledField>
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
      <LabeledTextArea
        label="Steps to Reproduce"
        rows={3}
        fieldKey="steps"
        placeholder="1. Go to...&#10;2. Click...&#10;3. Observe..."
        fields={fields}
        onChange={onChange}
      />
      <LabeledTextArea
        label="Expected Behavior"
        rows={2}
        fieldKey="expected"
        placeholder="What should have happened?"
        fields={fields}
        onChange={onChange}
      />
      <LabeledTextArea
        label="Actual Behavior"
        rows={2}
        fieldKey="actual"
        placeholder="What actually happened?"
        fields={fields}
        onChange={onChange}
      />
      {/* The caption is a <span>, so without the group the three buttons read
          as three loose controls with no idea what they select (#563 item 2). */}
      <LabeledField label="Severity">
        {(name) => (
          <div role="group" aria-label={name} style={{ display: 'flex', gap: spacing.sm }}>
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
                    minHeight: accessibility.touchTarget,
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
        )}
      </LabeledField>
    </div>
  )
}

function FeatureForm({ fields, onChange }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.md }}>
      <LabeledTextArea
        label="Description"
        rows={3}
        fieldKey="description"
        placeholder="Describe the feature you'd like to see..."
        fields={fields}
        onChange={onChange}
      />
      <LabeledTextArea
        label="Use Case / Why"
        rows={3}
        fieldKey="use_case"
        placeholder="Why would this improve the game?"
        fields={fields}
        onChange={onChange}
      />
    </div>
  )
}

function GeneralForm({ fields, onChange, ratings, onRatingChange }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.md }}>
      <LabeledTextArea
        label="Message"
        rows={4}
        fieldKey="message"
        placeholder="Share your thoughts about the game..."
        fields={fields}
        onChange={onChange}
      />
      {/* The accessible name is the caption verbatim, "(optional)" included:
          the parenthetical is how a sighted player learns the stars can be
          skipped, and a screen-reader user has no other source for it. */}
      <LabeledField label="Ratings (optional)">
        {(name) => (
          <div
            role="group"
            aria-label={name}
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
            <div style={{ color: colors.text.muted, fontSize: '11px', marginTop: spacing.xs }}>
              Click a star again to clear it. Leave any dimension unrated to skip it.
            </div>
          </div>
        )}
      </LabeledField>
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
    // The panel says "your report is still here"; after a tab switch it is
    // not -- the title is wiped and a different form takes its place. (The
    // three bodies are separate states and DO survive a round trip, which is
    // deliberate, but the error the panel refers to belonged to the form the
    // player just left.)
    setSubmitError(null)
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
  // No `|| SUBMIT_FAILED_MESSAGE` fallback: both call sites already pass
  // `apiErrorMessage(x, SUBMIT_FAILED_MESSAGE)`, and that helper is total --
  // it never returns a falsy string when given a non-empty fallback. The arm
  // was therefore unexercisable, against a 95% branch gate.
  const failSubmit = (text) => {
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
        // Through apiErrorMessage, not res.data.error directly: `error` and
        // `message` are server-controlled and need not be strings, and this
        // value is rendered as a React child, where a non-string throws
        // "Objects are not valid as a React child" -- and with no
        // ErrorBoundary in the app that unmounts the SPA instead of showing
        // the error. The helper was already hardened against exactly this;
        // this branch was the one path bypassing it. It also restores the
        // documented message-before-error precedence.
        failSubmit(apiErrorMessage(res.data, SUBMIT_FAILED_MESSAGE))
        return
      }
      toastSuccess('Feedback submitted! Thank you.')
      onClose()
    } catch (err) {
      failSubmit(apiErrorMessage(err, SUBMIT_FAILED_MESSAGE))
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
      <LabeledField label="Title" required style={{ marginBottom: spacing.md }}>
        {(name) => (
          <TextInput
            inputRef={titleInputRef}
            ariaLabel={name}
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
        )}
      </LabeledField>

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
          style={{ ...commonStyles.errorBox, marginTop: spacing.md }}
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
