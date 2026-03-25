import { useState, useRef } from 'react'
import BaseDialog from './BaseDialog'
import GameButton from './GameButton'
import { colors, spacing, fonts } from '../styles/theme'
import { feedback as feedbackApi } from '../api/endpoints'
import { useToast } from '../context/ToastContext'

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
  fontSize: '13px',
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

function FieldLabel({ children }) {
  return <span style={labelStyle}>{children}</span>
}

function TextInput({ value, onChange, placeholder, style }) {
  return (
    <input
      type="text"
      value={value}
      onChange={onChange}
      placeholder={placeholder}
      style={{ ...inputStyle, ...style }}
      onFocus={(e) => (e.target.style.borderColor = colors.primary)}
      onBlur={(e) => (e.target.style.borderColor = `${colors.primary}66`)}
    />
  )
}

function TextArea({ value, onChange, placeholder, rows = 3 }) {
  return (
    <textarea
      rows={rows}
      value={value}
      onChange={onChange}
      placeholder={placeholder}
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
          value={fields.steps}
          onChange={(e) => onChange('steps', e.target.value)}
          placeholder="1. Go to...&#10;2. Click...&#10;3. Observe..."
        />
      </div>
      <div>
        <FieldLabel>Expected Behavior</FieldLabel>
        <TextArea
          rows={2}
          value={fields.expected}
          onChange={(e) => onChange('expected', e.target.value)}
          placeholder="What should have happened?"
        />
      </div>
      <div>
        <FieldLabel>Actual Behavior</FieldLabel>
        <TextArea
          rows={2}
          value={fields.actual}
          onChange={(e) => onChange('actual', e.target.value)}
          placeholder="What actually happened?"
        />
      </div>
      <div>
        <FieldLabel>Severity</FieldLabel>
        <div style={{ display: 'flex', gap: spacing.sm }}>
          {SEVERITY_OPTIONS.map((sev) => {
            const active = fields.severity === sev
            const severityColor = { low: colors.gold, medium: colors.secondary, high: colors.danger }[sev]
            return (
              <button
                key={sev}
                onClick={() => onChange('severity', sev)}
                style={{
                  flex: 1,
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
          value={fields.description}
          onChange={(e) => onChange('description', e.target.value)}
          placeholder="Describe the feature you'd like to see..."
        />
      </div>
      <div>
        <FieldLabel>Use Case / Why</FieldLabel>
        <TextArea
          rows={3}
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

export default function FeedbackDialog({ onClose }) {
  const { success: toastSuccess, error: toastError } = useToast()

  const [activeType, setActiveType] = useState('bug')
  const [title, setTitle] = useState('')
  const [anonymous, setAnonymous] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const [bugFields, setBugFields] = useState({ ...EMPTY_BUG })
  const [featureFields, setFeatureFields] = useState({ ...EMPTY_FEATURE })
  const [generalFields, setGeneralFields] = useState({ ...EMPTY_GENERAL })
  const [ratings, setRatings] = useState({ ...EMPTY_RATINGS })
  const submittingRef = useRef(false)

  const handleTypeChange = (type) => {
    setActiveType(type)
    setTitle('')
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

  const handleSubmit = async () => {
    if (submittingRef.current) return
    if (!title.trim()) {
      toastError('Please enter a title for your feedback.')
      return
    }
    submittingRef.current = true
    setSubmitting(true)
    try {
      const fields = getActiveFields()
      await feedbackApi.submitIssue(activeType, title.trim(), fields, anonymous)
      toastSuccess('Feedback submitted! Thank you.')
      onClose()
    } catch (err) {
      const msg = err?.response?.data?.error || 'Could not submit feedback — please try again later.'
      toastError(msg)
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
        <FieldLabel>Title</FieldLabel>
        <TextInput
          value={title}
          onChange={(e) => setTitle(e.target.value)}
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
