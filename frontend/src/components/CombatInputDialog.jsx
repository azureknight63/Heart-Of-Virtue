import React, { useState } from 'react';
import { useAudio } from '../context/AudioContext';
import BaseDialog from './BaseDialog';
import GameButton from './GameButton';
import { colors, zIndex } from '../styles/theme';
import { hostilityTokenFor } from '../utils/combatEntities';
import HostilityChip from './HostilityChip';

const INPUT_TYPE_CONFIG = {
    target_selection: { title: '🎯 SELECT TARGET' },
    direction_selection: { title: '🧭 SELECT DIRECTION' },
    item_selection: { title: '🎒 SELECT ITEM' },
    number_input: { title: '🔢 ENTER VALUE' },
};

/**
 * HP-bar color by REAL percentage of current/max, not a fixed hue. A target
 * at full health must read as healthy, not as "about to die" — the same
 * threshold structure as the sibling PARTY panel and item-detail HP bars
 * (issue #536), but a deliberately different "healthy" shade (`colors.success`,
 * the brighter primary lime) tested and kept local to this dialog rather than
 * merged into `entityUtils.getHpBarColor`, which uses PartyPanel/
 * ItemDetailDialog's own `#44ff88`.
 */
function healthBarColor(current, max) {
    const pct = max > 0 ? current / max : 0;
    if (pct > 0.5) return colors.success;
    if (pct > 0.25) return colors.warning;
    return colors.danger;
}

/**
 * One target card in the target picker.
 *
 * Extracted because the `target_selection` case had grown to ~90 lines with
 * `switch -> map -> IIFE -> JSX` nesting, and it is the branch #558's ally
 * mis-target lived in -- the one place in this dialog worth being able to
 * read in a single screen.
 *
 * @param {object} target one entry of `options`
 * @param {string} confirmVerb the label for the confirm button
 * @param {Function} onHover called with the target id, or null on leave
 * @param {Function} onSelect called with the target id
 */
const TargetCard = ({ target, confirmVerb, onHover, onSelect }) => {
  // Friend or foe, from the `is_ally` every target card
  // carries. Without it Gorran and a Rock Rumbler were
  // pixel-identical here and a pick landed on the ally
  // (issue #558). Null when the payload says nothing —
  // never guessed.
  const hostility = hostilityTokenFor(target);

  const hp = target.health;
  // Guard the divisor: a combatant serialized with max 0 would otherwise put
  // "Infinity%" into the style.
  const hpPct = hp && hp.max > 0 ? hp.current / hp.max : 0;
  const hpColor = hp ? healthBarColor(hp.current, hp.max) : null;

  return (
      <div
          data-testid="target-card"
          onMouseEnter={() => onHover(target.id)}
          onMouseLeave={() => onHover(null)}
          style={{
              backgroundColor: hostility ? hostility.tint : 'rgba(255, 255, 255, 0.03)',
              border: `1px solid ${hostility ? hostility.color : 'rgba(255, 255, 255, 0.1)'}`,
              borderRadius: '12px',
              padding: '16px',
              display: 'flex',
              flexDirection: 'column',
              gap: '12px',
              transition: 'all 0.2s ease',
              cursor: 'pointer'
          }}
          onClick={() => onSelect(target.id)}
      >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px' }}>
              <span style={{ fontWeight: 'bold', color: '#fff', fontSize: '15px' }}>{target.name}</span>
              {target.distance !== undefined && (
                  <span style={{ fontSize: '11px', color: '#aaa', backgroundColor: 'rgba(255,255,255,0.1)', padding: '2px 6px', borderRadius: '4px' }}>
                      {target.distance} ft
                  </span>
              )}
          </div>

          {hostility && (
              <HostilityChip token={hostility} variant="block" />
          )}

          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
              {hp && (
                  <div style={{ fontSize: '12px', color: hpColor, display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span style={{ minWidth: '30px', opacity: 0.6 }}>HP:</span>
                      <div style={{ flex: 1, height: '4px', backgroundColor: 'rgba(255,0,0,0.2)', borderRadius: '2px' }}>
                          <div style={{ width: `${hpPct * 100}%`, height: '100%', backgroundColor: hpColor, borderRadius: '2px' }} />
                      </div>
                      <span style={{ fontSize: '10px', color: hpColor }}>{hp.current}/{hp.max}</span>
                  </div>
              )}
              {target.hit_chance !== undefined && (
                  <div style={{ fontSize: '12px', color: '#00ffcc', display: 'flex', justifyContent: 'space-between' }}>
                      <span>Accuracy:</span>
                      {/* hit_chance is already an integer percentage, produced by
                          the ranged moves' calculate_hit_chance (src/moves/_ranged.py)
                          and passed through the adapter verbatim — do not rescale it.
                          Its [2, 100] clamp is applied before the shared facing /
                          HauntingPresence modifiers, so the final value can sit
                          slightly outside that band. */}
                      <span style={{ fontWeight: 'bold' }}>{Math.round(target.hit_chance)}%</span>
                  </div>
              )}
          </div>

          {/* The card itself is also clickable (see onClick above); this
              button used to be `pointerEvents: 'none'` and cosmetic-only,
              which made it invisible to real DOM hit-testing (Playwright's
              actionability check, elementFromPoint) and keyboard/
              screen-reader-inert. It now carries its own onClick — with
              stopPropagation so a real click is not ALSO handled by the
              ancestor card, which would submit the target twice. */}
          <GameButton
              variant="primary"
              style={{ width: '100%', padding: '8px' }}
              onClick={(e) => {
                  e.stopPropagation();
                  onSelect(target.id);
              }}
          >
              {confirmVerb}
          </GameButton>
      </div>
  );
};


/**
 * CombatInputDialog - Versatile dialog for combat-specific inputs (targeting, directions, etc.)
 */
const CombatInputDialog = ({ inputType, options, onSelect, onCancel, onTargetHover, moveName, moveCategory }) => {
    const { playSFX } = useAudio();

    const getTitle = () => {
        return INPUT_TYPE_CONFIG[inputType]?.title || '❓ SELECT OPTION';
    };

    // The confirm verb on a target card must match what the move actually
    // DOES. "STRIKE" is only honest for a genuine attack (category
    // "Offensive" — see utils/categories.js); every other move (Advance,
    // Guard, etc.) used to show "STRIKE" too, which reads as "attack" even
    // on an ally card. With no move info at all (e.g. a server-driven
    // target_selection state with no locally-tracked move), fall back to a
    // neutral verb rather than guessing "STRIKE".
    const getConfirmVerb = () => {
        if (moveCategory === 'Offensive') return 'STRIKE';
        if (moveName) return moveName;
        return 'Select';
    };

    const handleSelect = (option) => {
        playSFX('attack');
        // Clear hover when selecting
        if (onTargetHover) onTargetHover(null);
        onSelect(option);
    };

    const renderOptions = () => {
        if (!options || (Array.isArray(options) && options.length === 0)) {
            return (
                <div style={{ color: colors.text.muted, fontStyle: 'italic', textAlign: 'center', padding: '40px' }}>
                    No valid targets or options available.
                </div>
            );
        }

        switch (inputType) {
            case 'target_selection':
                return (
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '12px' }}>
                        {Array.isArray(options) && options.map((target) => (
                            <TargetCard
                                key={target.id}
                                target={target}
                                confirmVerb={getConfirmVerb()}
                                onHover={(id) => onTargetHover && onTargetHover(id)}
                                onSelect={handleSelect}
                            />
                        ))}
                    </div>
                );

            case 'direction_selection':
                return (
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '16px', maxWidth: '300px', margin: '0 auto' }}>
                        {Array.isArray(options) && options.map((direction) => (
                            <GameButton
                                key={direction}
                                onClick={() => handleSelect(direction)}
                                variant="secondary"
                                style={{ padding: '20px', fontSize: '16px' }}
                            >
                                {direction.toUpperCase()}
                            </GameButton>
                        ))}
                    </div>
                );

            case 'number_input':
                return <NumberInput options={options} onSubmit={handleSelect} />;

            default:
                return (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        {Array.isArray(options) && options.map((option) => {
                            const key = typeof option === 'object' ? (option.id ?? option.name ?? option.label) : option
                            return (
                                <GameButton
                                    key={key}
                                    onClick={() => handleSelect(typeof option === 'object' ? option.id : option)}
                                    variant="secondary"
                                    style={{ textAlign: 'left', justifyContent: 'flex-start', padding: '12px 20px' }}
                                >
                                    {typeof option === 'object' ? option.name || option.label : option}
                                </GameButton>
                            )
                        })}
                    </div>
                );
        }
    };

    return (
        <BaseDialog
            title={getTitle()}
            onClose={onCancel}
            maxWidth="600px"
            zIndex={zIndex.raisedDialog}
            variant={inputType === 'target_selection' ? 'no-blur' : undefined}
            containerCentered={true}
        >
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                <div style={{ overflowY: 'auto', maxHeight: '50vh', padding: '4px' }}>
                    {renderOptions()}
                </div>
                {onCancel && (
                    <div style={{ display: 'flex', justifyContent: 'center' }}>
                        <GameButton onClick={onCancel} variant="secondary">
                            CANCEL ACTION
                        </GameButton>
                    </div>
                )}
            </div>
        </BaseDialog>
    );
};

// Internal components for specific input types
const NumberInput = ({ options, onSubmit }) => {
    const [inputValue, setInputValue] = useState(options?.default ?? options?.min ?? 5);
    const min = options?.min ?? 1;
    const max = options?.max ?? 100;

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', alignItems: 'center' }}>
            {options?.prompt && (
                <div style={{ color: '#aaa', fontSize: '14px', textAlign: 'center', maxWidth: '300px' }}>
                    {options.prompt}
                </div>
            )}
            <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
                <GameButton
                    onClick={() => setInputValue(Math.max(min, inputValue - 1))}
                    variant="secondary"
                    style={{ padding: '10px 20px', fontSize: '24px' }}
                >
                    −
                </GameButton>
                <div style={{
                    fontSize: '32px',
                    fontWeight: 'bold',
                    color: '#ffaa00',
                    fontFamily: 'monospace',
                    minWidth: '80px',
                    textAlign: 'center'
                }}>
                    {inputValue}
                </div>
                <GameButton
                    onClick={() => setInputValue(Math.min(max, inputValue + 1))}
                    variant="secondary"
                    style={{ padding: '10px 20px', fontSize: '24px' }}
                >
                    +
                </GameButton>
            </div>
            <div style={{ fontSize: '11px', color: '#666', textTransform: 'uppercase', letterSpacing: '1px' }}>
                Range: {min} - {max}
            </div>
            <GameButton
                onClick={() => onSubmit(inputValue)}
                variant="primary"
                style={{ width: '200px', padding: '12px' }}
            >
                CONFIRM
            </GameButton>
        </div>
    );
};

export default CombatInputDialog;
