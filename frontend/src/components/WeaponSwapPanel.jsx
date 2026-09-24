import { colors, spacing, accessibility, fonts } from '../styles/theme'
import { getStageBeats, totalStageBeats, formatBeats, beatUnit } from '../utils/moveCommitment'
import { moveAvailability } from '../utils/combatMoveStatus'

/** Shown when the engine offers no weapon to draw (empty `weapon_options`). */
export const NO_WEAPON_TO_SWAP_REASON = 'No other weapon in your pack to draw.'
/** Shown when the swap is otherwise possible but it is not Jean's turn. */
export const NOT_YOUR_TURN_REASON = 'Wait for your turn to change weapons.'

/**
 * Why no weapon can be drawn right now, or null when one can.
 *
 * Order matters: an empty pack is the reason the player can act on (go find
 * a weapon), so it is stated first, in the panel's own words. Any other lock
 * shows the engine's reason (#627), with the shared client fallback when the
 * payload carries none. Off-turn comes last because it clears on its own.
 */
function blockedReason(swapMove, options, canAct) {
  if (options.length === 0) return NO_WEAPON_TO_SWAP_REASON
  if (!swapMove.available) return moveAvailability(swapMove).reason
  if (!canAct) return NOT_YOUR_TURN_REASON
  return null
}

/**
 * The full price of a swap, in words, before the player commits (#671).
 *
 * Every number is the engine's -- `stage_beats` and `fatigue_cost` from the
 * Swap Weapon move card -- so retuning SWAP_WEAPON_STAGE_BEATS in
 * src/moves/_utility.py changes this text with no client edit. Zero fatigue
 * and zero cooldown are stated rather than omitted: "no cooldown" is the
 * thing a player wants to know when they picked the wrong weapon.
 */
function costSummary(swapMove) {
  const stageBeats = getStageBeats(swapMove)
  const total = totalStageBeats(stageBeats)
  const fatigue = swapMove.fatigue_cost || 0
  const beats = `${formatBeats(total)} ${beatUnit(total)}`
  return {
    beats,
    headline: `Costs ${beats}`,
    breakdown: `Prep ${formatBeats(stageBeats.prep)} · Execute ${formatBeats(stageBeats.execute)} · Recoil ${formatBeats(stageBeats.recoil)}`,
    fatigue: fatigue > 0 ? `${fatigue} fatigue` : 'No fatigue',
    cooldown: stageBeats.cooldown > 0
      ? `${formatBeats(stageBeats.cooldown)} ${beatUnit(stageBeats.cooldown)} cooldown`
      : 'No cooldown',
  }
}

/**
 * Mid-combat weapon swap, rendered in the inventory's Weapons tab (#671).
 *
 * The weapons listed are the engine's own offer (`weapon_options` on the
 * Swap Weapon move card, built by ApiCombatAdapter from
 * SwapWeapon.swappable_weapons), not a client filter over the inventory --
 * which weapons count is an engine rule. Picking one submits the move; the
 * beats it costs are spent by the real beat machinery, and the free equip
 * route refuses weapons mid-fight, so this is the only way to change.
 */
export default function WeaponSwapPanel({ swapMove, equippedName, canAct, onSwap }) {
  const options = Array.isArray(swapMove?.weapon_options) ? swapMove.weapon_options : []
  const reason = blockedReason(swapMove, options, canAct)
  const cost = costSummary(swapMove)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: spacing.sm, fontFamily: fonts.main }}>
      <div style={{ color: colors.primary, fontSize: '11px', fontWeight: 'bold', textTransform: 'uppercase', borderBottom: `1px solid ${colors.border.main}` }}>
        ⚔ Swap Weapon
      </div>
      <div style={{ color: colors.text.main, fontSize: '13px' }}>
        In hand: <strong>{equippedName || 'bare hands'}</strong>
      </div>
      <div data-testid="weapon-swap-cost" style={{ color: colors.text.highlight, fontSize: '12px', lineHeight: 1.5 }}>
        <div><strong>⏱ {cost.headline}</strong> ({cost.breakdown}). The new weapon is in hand after Execute.</div>
        <div>{cost.fatigue} · {cost.cooldown}</div>
      </div>
      {reason && (
        <div role="status" style={{ color: colors.text.warning, fontSize: '12px' }}>
          ⚠ {reason}
        </div>
      )}
      {options.map((option) => (
        <button
          key={option.id}
          type="button"
          disabled={Boolean(reason)}
          aria-label={`Draw ${option.name} (costs ${cost.beats})`}
          onClick={() => onSwap(option.id)}
          style={{
            minHeight: accessibility.touchTarget,
            padding: `${spacing.xs} ${spacing.md}`,
            textAlign: 'left',
            backgroundColor: reason ? colors.bg.muted : colors.bg.positive,
            color: reason ? colors.text.muted : colors.primary,
            border: `1px solid ${reason ? colors.border.main : colors.primary}`,
            borderRadius: '6px',
            fontFamily: fonts.main,
            fontSize: '13px',
            fontWeight: 'bold',
            cursor: reason ? 'not-allowed' : 'pointer',
            touchAction: 'manipulation',
          }}
        >
          ⚔ Draw {option.name} · {cost.beats}
        </button>
      ))}
    </div>
  )
}
