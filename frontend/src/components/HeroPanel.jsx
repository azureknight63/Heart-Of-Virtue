import React, { useState } from 'react'
import { colors, spacing, fonts, accessibility } from '../styles/theme'
import StatusEffectsIconPanel from './StatusEffectsIconPanel'
import GameText from './GameText'
import { CATEGORY_NAV_LABEL } from '../utils/categories'

/**
 * VitalBar — one of the two curved bars flanking the hero portrait.
 *
 * The HP and Fatigue bars were ~55-line near-duplicates differing only in the
 * values below. That is a drift risk with a track record here: the divide-by-
 * zero guard on the fill height had to be applied to two separate expressions,
 * and any change to the hover/touch/tooltip behaviour needed both copies edited
 * in lockstep.
 *
 * `side` drives every left/right mirror (position, both border radii, and the
 * tooltip's anchor). The tooltip glow is derived from `color`, as the bar's own
 * border and fill already are, so both bars glow in their own colour. Fatigue
 * previously used the orange `shadows.glow` token against its cyan border; that
 * mismatch was an oversight and was unified deliberately (issue #494).
 */
function VitalBar({
  side,
  label,
  color,
  trackColor,
  fillRatio,
  current,
  max,
  active,
  onHoverChange,
  onToggle,
  testId,
}) {
  const isLeft = side === 'left'
  // issue #536 item 1: this bar rendered as a bare, unlabeled capsule — no
  // text, no title, no aria-label, no role. A screen reader had nothing to
  // read, and a sighted player had to hover/click/touch it (see `active`
  // below) just to learn the number. role="progressbar" plus aria-valuenow/
  // min/max exposes the live value directly; the label/title give every
  // player (not just assistive tech) an always-available accessible name,
  // independent of the pinned tooltip.
  // Coerce once: `current` comes straight off the wire, and while a guard
  // upstream handles null/undefined, it doesn't guarantee a number —
  // a malformed payload calling .toFixed() directly would crash the whole
  // HUD render rather than just this bar's tooltip.
  const currentValue = Number(current) || 0
  // Two formats on purpose, both built from one reading of the value. The
  // visual sites (the persistent number and the pinned tooltip) share the
  // compact form, because the bar is 15px wide; the accessible name keeps the
  // spaced form, which a screen reader renders as "80 of 100" rather than
  // running the digits together. They were previously spelled out at three
  // separate sites, which is how the spacing came to differ by accident
  // rather than by decision.
  const shownValue = currentValue.toFixed(0)
  const readout = `${shownValue}/${max}`
  const accessibleLabel = `${label}: ${shownValue} / ${max}`
  return (
    <div
      role="progressbar"
      aria-valuenow={shownValue}
      aria-valuemin={0}
      aria-valuemax={max}
      aria-label={accessibleLabel}
      title={accessibleLabel}
      onMouseEnter={() => onHoverChange(true)}
      onMouseLeave={() => onHoverChange(false)}
      onClick={onToggle}
      onTouchStart={(e) => {
        e.preventDefault()
        onToggle()
      }}
      style={{
        position: 'absolute',
        [isLeft ? 'left' : 'right']: '-75px',
        top: '50%',
        transform: 'translateY(-50%)',
        width: '15px',
        height: '150px',
        borderRadius: isLeft ? '15px 0 0 15px' : '0 15px 15px 0',
        border: `2px solid ${color}`,
        backgroundColor: trackColor,
        boxShadow: `0 0 10px ${color}88, inset 0 0 8px ${color}44`,
        zIndex: 3,
        display: 'flex',
        flexDirection: 'column-reverse',
        overflow: 'visible',
        cursor: 'pointer',
      }}
      data-testid={testId}
    >
      <div style={{
        width: '100%',
        height: `${fillRatio * 100}%`,
        backgroundColor: color,
        borderRadius: isLeft ? '12px 0 0 12px' : '0 12px 12px 0',
        boxShadow: `0 0 8px ${color}, inset 0 0 4px rgba(255, 255, 255, 0.3)`,
      }} />

      {/* issue #563 item 7: a persistently visible number.
          #536 served assistive tech (role/aria-valuenow/aria-label above) but
          left a SIGHTED player with colour and nothing else — the value
          rendered only while `active`, i.e. on hover, click or touch, and a
          touch screen has no hover at all. Colour alone is exactly what the
          accessibility rules here forbid.

          Rendered AFTER the fill deliberately: the assertions in
          HeroPanel.test.jsx read the fill as the bar's `firstElementChild`.

          `aria-hidden` because the bar's own aria-label already reads
          "HP: 80 / 100"; without it every vital is announced twice. The
          pinned tooltip below still adds the label, which this cannot fit.

          Sits at -16px, clear of that tooltip at -35px. The bar's own colour
          carries it: #ff4444 is 5.8:1 on the app ground and #ffaa00 is
          10.4:1, so both clear AA on their own. */}
      <div
        data-testid={`${testId}-value`}
        aria-hidden="true"
        style={{
          position: 'absolute',
          left: '50%',
          bottom: '-16px',
          transform: 'translateX(-50%)',
          color,
          fontSize: '10px',
          fontWeight: 'bold',
          fontFamily: fonts.main,
          lineHeight: 1,
          whiteSpace: 'nowrap',
          textShadow: `0 0 4px ${colors.bg.main}, 0 0 2px ${colors.bg.main}`,
          pointerEvents: 'none',
        }}
      >
        {readout}
      </div>

      {active && (
        <div style={{
          position: 'absolute',
          [isLeft ? 'left' : 'right']: '50%',
          bottom: '-35px',
          transform: `translateX(${isLeft ? '-50%' : '50%'})`,
          backgroundColor: colors.bg.main,
          border: `1.5px solid ${color}`,
          borderRadius: '3px',
          padding: '4px 6px',
          color,
          fontSize: '8px',
          fontWeight: 'bold',
          fontFamily: fonts.main,
          whiteSpace: 'nowrap',
          boxShadow: `0 0 8px ${color}99`,
          zIndex: 20,
        }}>
          {label}<br />{readout}
        </div>
      )}
    </div>
  )
}

function HeroPanel({
  player,
  isMobile,
  inCombat,
  heroScale = 1,
  hasSpecialMoves,
  hasDefensiveMoves,
  hasOffensiveMoves,
  hasManeuverMoves,
  hasMiscellaneousMoves,
  onAttributeClick,
  onStatusClick,
  onSkillsClick,
  onSpecialClick,
  onInventoryClick,
  onActionsClick,
  onInteractClick,
  onDefensiveClick,
  onOffensiveClick,
  onManeuverClick,
  onMiscellaneousClick
}) {
  const [hoveredButton, setHoveredButton] = useState(null)
  const [hoveredBar, setHoveredBar] = useState(null)
  const [focusedBar, setFocusedBar] = useState(null)

  // Get player stats or use defaults
  const hp = {
    current: player?.hp ?? 100,
    max: player?.max_hp ?? 100,
  }
  const fatigue = {
    current: player?.fatigue ?? 150,
    max: player?.max_fatigue ?? 150,
  }

  // usePlayer's error fallback ships hp:0/max_hp:0, and `?? 100` lets a real 0
  // through — dividing by it yields NaN, which leaks into height:"NaN%" and
  // animationDuration:"NaNs". Treat a zero/absent max as an empty bar.
  const ratio = (current, max) => (max > 0 ? Math.max(0, Math.min(1, current / max)) : 0)

  // Calculate heart rate based on HP and Combat status
  const hpPercent = ratio(hp.current, hp.max)
  const fatiguePercent = ratio(fatigue.current, fatigue.max)
  const baseBpm = 60
  const combatBonus = inCombat ? 40 : 0
  const stressBonus = (1 - hpPercent) * (inCombat ? 80 : 60)
  const bpm = baseBpm + combatBonus + stressBonus
  const animationDuration = `${60 / bpm}s`

  const explorationButtons = [
    { key: 'attributes', label: 'ATTRIBUTES', top: '0px', left: '20%', transform: 'translateX(-50%)', onClick: onAttributeClick },
    { key: 'status', label: 'PARTY', top: '0px', left: 'calc(50% + 60px)', transform: 'translate(-50%, 0)', onClick: onStatusClick },
    { key: 'inventory', label: 'INVENTORY', top: '50%', left: '-40px', transform: 'translateY(-50%)', onClick: onInventoryClick },
    { key: 'skills', label: 'SKILLS', top: '50%', left: 'calc(50% + 70px)', transform: 'translateY(-50%)', onClick: onSkillsClick },
    { key: 'actions', label: 'COMMANDS', top: 'calc(50% + 80px)', left: '5px', transform: 'translate(0, -50%)', onClick: onActionsClick },
    { key: 'interact', label: 'INTERACT', top: 'calc(50% + 80px)', left: 'calc(50% + 60px)', transform: 'translate(-50%, -50%)', onClick: onInteractClick },
  ]

  const combatButtons = [
    { key: 'offensive', label: 'OFFENSIVE', top: '0px', left: '20%', transform: 'translateX(-50%)', onClick: onOffensiveClick, color: colors.danger, show: hasOffensiveMoves },
    { key: 'maneuver', label: 'MANEUVER', top: '0px', left: 'calc(50% + 60px)', transform: 'translate(-50%, 0)', onClick: onManeuverClick, color: colors.text.highlight, show: hasManeuverMoves },
    { key: 'inventory', label: 'INVENTORY', top: '50%', left: '-40px', transform: 'translateY(-50%)', onClick: onInventoryClick },
    { key: 'special', label: 'SPECIAL', top: '50%', left: 'calc(50% + 70px)', transform: 'translateY(-50%)', onClick: onSpecialClick, color: colors.special, show: hasSpecialMoves },
    { key: 'miscellaneous', label: 'MISC', top: 'calc(50% + 80px)', left: '5px', transform: 'translate(0, -50%)', onClick: onMiscellaneousClick, color: colors.text.muted, show: hasMiscellaneousMoves },
    { key: 'defensive', label: 'DEFENSIVE', top: 'calc(50% + 80px)', left: 'calc(50% + 60px)', transform: 'translate(-50%, -50%)', onClick: onDefensiveClick, color: colors.secondary, show: hasDefensiveMoves },
  ]

  const buttons = inCombat ? combatButtons.filter(btn => btn.show !== false) : explorationButtons

  // Mobile touch-target compensation (issue #542).
  //
  // LeftPanel wraps this whole component in `transform: scale(heroScale)` so
  // the radial layout fits whatever room a tight mobile combat screen leaves
  // it (see useHeroAutoScale) — CombatLog/HeatMeter/SuggestedMovesPanel can
  // squeeze that container well below its 360x310 base size. That ancestor
  // scale shrinks these buttons' EFFECTIVE on-screen size right along with
  // the portrait, even though their own CSS already declares the 44px
  // minimum (`accessibility.touchTarget` below): a QA pass measured 40x25px
  // rendered buttons at the then-70px width and heroScale ~0.57
  // (70*0.57≈40, 44*0.57≈25). The width is 80px now, so read those figures
  // as the history that motivated this, not as current measurements.
  // Counter-scaling each button by 1/heroScale cancels the ancestor's shrink
  // for just these interactive elements, restoring the declared 44px+ target
  // regardless of how small the portrait itself has to get. A no-op on
  // desktop (isMobile is false there) and a no-op whenever the panel isn't
  // actually shrunk (heroScale >= 1), so neither is affected.
  const touchCompensation = (isMobile && heroScale > 0 && heroScale < 1) ? 1 / heroScale : 1

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      gap: spacing.md,
      alignItems: 'center',
      padding: `${spacing.xl} ${spacing.md}`,
      position: 'relative',
    }}>
      {/* Hero Head Container */}
      <div style={{
        position: 'relative',
        width: '200px',
        height: '200px',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        overflow: 'visible',
      }}>
        {/* Passive Effects Icons — side column on desktop, hidden here on mobile (shown below) */}
        {!isMobile && (
          <div style={{
            position: 'absolute',
            top: '50%',
            left: '-135px',
            transform: 'translateY(-50%)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '4px',
            zIndex: 10,
            pointerEvents: 'auto'
          }}>
            {player?.passives?.length > 0 && (
              <GameText variant="muted" size="xs" weight="bold" style={{ fontSize: '7px', marginBottom: '2px' }}>PASSIVES</GameText>
            )}
            <StatusEffectsIconPanel effects={player?.passives} vertical />
          </div>
        )}

        {/* Status Effects Icons — side column on desktop, hidden here on mobile (shown below) */}
        {!isMobile && (
          <div style={{
            position: 'absolute',
            top: '50%',
            right: '-135px',
            transform: 'translateY(-50%)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '4px',
            zIndex: 10,
            pointerEvents: 'auto'
          }}>
            {player?.status_effects?.length > 0 && (
              <GameText variant="muted" size="xs" weight="bold" style={{ fontSize: '7px', marginBottom: '2px' }}>STATUS</GameText>
            )}
            <StatusEffectsIconPanel effects={player?.status_effects} vertical />
          </div>
        )}

        <img
          src={`${import.meta.env.BASE_URL}hero-heart.png`}
          alt="Hero Heart"
          style={{
            width: '140px',
            height: '140px',
            objectFit: 'contain',
            filter: `drop-shadow(0 0 10px ${colors.primary}44)`,
            zIndex: 1,
            animation: `hero-heartbeat ${animationDuration} infinite ease-in-out`,
          }}
        />
        <style>
          {`
            /* Namespaced, and deliberately not named "pulse": keyframe names are
               document-global regardless of which component's <style> declares them,
               and last-injected wins. index.css already owns a "pulse" (scale + opacity)
               that BattlefieldGrid's targeting reticle uses. Because HeroPanel sits in
               the persistent HUD, a "pulse" declared here mounted after the stylesheet
               and silently replaced the reticle's animation with this heartbeat.

               This one stays inline rather than moving to index.css because it
               interpolates colors.primary from the JS theme, and index.css exposes no
               token for it. */
            @keyframes hero-heartbeat {
              0% { transform: scale(1); filter: drop-shadow(0 0 10px ${colors.primary}44); }
              10% { transform: scale(1.007); filter: drop-shadow(0 0 14px ${colors.primary}66); }
              20% { transform: scale(1); filter: drop-shadow(0 0 10px ${colors.primary}44); }
              30% { transform: scale(1.007); filter: drop-shadow(0 0 14px ${colors.primary}66); }
              50% { transform: scale(1); filter: drop-shadow(0 0 10px ${colors.primary}44); }
              100% { transform: scale(1); filter: drop-shadow(0 0 10px ${colors.primary}44); }
            }
          `}
        </style>

        {/* HP (left) and Fatigue (right) — see VitalBar above. */}
        <VitalBar
          side="left"
          label="HP"
          color={colors.danger}
          trackColor={colors.bg.negativeLight}
          fillRatio={hpPercent}
          current={hp.current}
          max={hp.max}
          active={hoveredBar === 'hp' || focusedBar === 'hp'}
          onHoverChange={(on) => setHoveredBar(on ? 'hp' : null)}
          onToggle={() => setFocusedBar(focusedBar === 'hp' ? null : 'hp')}
          testId="hp-bar"
        />

        <VitalBar
          side="right"
          label="Fatigue"
          color={colors.secondary}
          trackColor={colors.bg.highlightLight}
          fillRatio={fatiguePercent}
          current={fatigue.current}
          max={fatigue.max}
          active={hoveredBar === 'fatigue' || focusedBar === 'fatigue'}
          onHoverChange={(on) => setHoveredBar(on ? 'fatigue' : null)}
          onToggle={() => setFocusedBar(focusedBar === 'fatigue' ? null : 'fatigue')}
          testId="fatigue-bar"
        />

        {/* Surrounding Buttons — issue #536 item 3: the app had zero <nav>
            landmarks anywhere. This radial ring IS the primary in-game
            navigation between panels/move categories, so it gets one.
            display:'contents' means the <nav> contributes no box of its own,
            so every button's `position: absolute` still resolves against
            this Hero Head Container exactly as before. */}
        <nav aria-label={CATEGORY_NAV_LABEL} style={{ display: 'contents' }}>
        {buttons.map(({ key, label, top, left, transform, onClick, color }) => {
          const isHovered = hoveredButton === key
          const baseColor = color || colors.primary
          const hoverColor = color || '#00ffaa'
          const buttonTransform = touchCompensation !== 1
            ? `${transform} scale(${touchCompensation})`
            : transform

          return (
            <button
              key={key}
              onClick={onClick}
              onMouseEnter={() => setHoveredButton(key)}
              onMouseLeave={() => setHoveredButton(null)}
              style={{
                position: 'absolute',
                top,
                left,
                transform: buttonTransform,
                // issue #563 item 8: 80px, up from 70px. The labels rendered
                // at 9px uppercase on the game's most-used controls, and
                // "ATTRIBUTES" (10 characters at 0.6em advance) already
                // filled the old 58px content box at that size — so raising
                // the type at all required the box to grow.
                //
                // It costs nothing in layout: the ring's horizontal extent is
                // set by the HP and Fatigue bars at left/right -75px, not by
                // these buttons. The widest button (SKILLS, at 50% + 70px)
                // still ends at 250px inside a 275px reach, so the footprint
                // useHeroAutoScale measures against is unchanged, and the
                // 44px touch height below is untouched.
                width: '80px',
                height: accessibility.touchTarget,
                minHeight: accessibility.touchTarget,
                borderRadius: '6px',
                border: `2px solid ${isHovered ? hoverColor : baseColor}`,
                backgroundColor: isHovered
                  ? `${baseColor}4D`
                  : `${baseColor}1A`,
                color: isHovered ? hoverColor : baseColor,
                fontSize: '11px',
                fontWeight: 'bold',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                boxShadow: isHovered
                  ? `0 0 12px ${baseColor}B3`
                  : `0 0 6px ${baseColor}44`,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontFamily: fonts.main,
                zIndex: 5,
                textAlign: 'center',
                // Horizontal padding trimmed to 2px to buy the wider type its
                // room; the vertical 4px is what keeps the label off the
                // border inside a 44px box.
                padding: '4px 2px',
                lineHeight: '1.2',
                textTransform: 'uppercase'
              }}
            >
              {label}
            </button>
          )
        })}
        </nav>
      </div>

      {/* Mobile-only: passives + status icons as a compact inline row */}
      {isMobile && (player?.passives?.length > 0 || player?.status_effects?.length > 0) && (
        <div style={{ display: 'flex', flexDirection: 'row', gap: '12px', justifyContent: 'center', flexWrap: 'wrap' }}>
          {player?.passives?.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '2px' }}>
              <GameText variant="muted" size="xs" weight="bold" style={{ fontSize: '7px' }}>PASSIVES</GameText>
              <StatusEffectsIconPanel effects={player.passives} />
            </div>
          )}
          {player?.status_effects?.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '2px' }}>
              <GameText variant="muted" size="xs" weight="bold" style={{ fontSize: '7px' }}>STATUS</GameText>
              <StatusEffectsIconPanel effects={player.status_effects} />
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default React.memo(HeroPanel)
