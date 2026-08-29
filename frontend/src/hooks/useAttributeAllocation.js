import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useAudio } from '../context/AudioContext'
import { apiErrorMessage } from '../utils/apiError'

/**
 * The seven allocatable attributes, in display order. Both the level-up modal
 * and the post-combat victory dialog offer exactly this set — they differ only
 * in where the current values are read from.
 */
export const ATTRIBUTE_OPTIONS = [
  { key: 'strength_base', label: 'Strength' },
  { key: 'finesse_base', label: 'Finesse' },
  { key: 'speed_base', label: 'Speed' },
  { key: 'endurance_base', label: 'Endurance' },
  { key: 'charisma_base', label: 'Charisma' },
  { key: 'intelligence_base', label: 'Intelligence' },
  { key: 'faith_base', label: 'Faith' },
]

const DEFAULT_ATTR = ATTRIBUTE_OPTIONS[0].key

/**
 * Shared attribute-point allocation logic.
 *
 * @param {object}   params
 * @param {object}   params.source          Object carrying the current `*_base` values
 *                                          (the player, or endState.attributes).
 * @param {number}   params.remainingPoints Points still available to spend.
 * @param {Function} params.onAllocatePoints async (attrKey|'randomize', amount) -> {success, error?}
 * @param {number}   [params.levelUpCount]  When this goes above 0, the level-up sting plays once.
 * @param {Function} [params.onAllocated]   Called with the successful result. Return true to
 *                                          signal the caller has taken over (e.g. it is closing
 *                                          the dialog), which skips the input reset.
 * @returns state and handlers for <AttributePointAllocator>.
 */
export function useAttributeAllocation({
  source,
  remainingPoints,
  onAllocatePoints,
  levelUpCount = 0,
  onAllocated,
}) {
  const [selectedAttr, setSelectedAttr] = useState(DEFAULT_ATTR)
  const [amount, setAmount] = useState('1')
  const [error, setError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)

  const { playSFX } = useAudio()

  // Held in a ref so a new playSFX identity can't re-fire the sting.
  const playSFXRef = useRef(playSFX)
  useEffect(() => { playSFXRef.current = playSFX }, [playSFX])

  useEffect(() => {
    if (levelUpCount > 0) playSFXRef.current('level_up')
  }, [levelUpCount])

  const attrOptions = useMemo(
    () => ATTRIBUTE_OPTIONS.map((o) => ({ ...o, value: source?.[o.key] })),
    [source]
  )

  // Both actions share submit/response/error handling; only the arguments and
  // the failure wording differ.
  const submit = useCallback(async (attrKey, amt, failureMessage) => {
    setError('')
    try {
      setIsSubmitting(true)
      const result = await onAllocatePoints(attrKey, amt)
      if (result && result.success) {
        // The caller may take over on success (VictoryDialog advances to the
        // loot phase once the last point is spent); if so, don't reset inputs
        // on a component that is about to unmount.
        if (onAllocated?.(result)) return
        setAmount('1')
        setError('')
      } else {
        setError(apiErrorMessage(result, failureMessage))
      }
    } catch (e) {
      setError(apiErrorMessage(e, e.message || failureMessage))
    } finally {
      setIsSubmitting(false)
    }
  }, [onAllocatePoints, onAllocated])

  const handleAllocate = useCallback(async () => {
    setError('')
    const amt = parseInt(amount, 10)
    if (Number.isNaN(amt) || amt <= 0) {
      setError('Enter a valid point amount.')
      return
    }
    if (amt > remainingPoints) {
      setError('Not enough points available.')
      return
    }
    await submit(selectedAttr, amt, 'Failed to allocate points.')
  }, [amount, remainingPoints, selectedAttr, submit])

  const handleRandomize = useCallback(
    () => submit('randomize', remainingPoints, 'Failed to randomize points.'),
    [remainingPoints, submit]
  )

  // Clears a stale "not enough points" error as soon as the typed value fits.
  const handleAmountChange = useCallback((next) => {
    setAmount(next)
    if (parseInt(next, 10) <= remainingPoints) setError('')
  }, [remainingPoints])

  return {
    selectedAttr,
    setSelectedAttr,
    amount,
    handleAmountChange,
    error,
    isSubmitting,
    attrOptions,
    handleAllocate,
    handleRandomize,
  }
}
