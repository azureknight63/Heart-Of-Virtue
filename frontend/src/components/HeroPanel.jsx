import React, { useState } from 'react'
import { colors, spacing, fonts, accessibility } from '../styles/theme'
import StatusEffectsIconPanel from './StatusEffectsIconPanel'
import GameText from './GameText'
import { CATEGORY_NAV_LABEL } from '../utils/categories'

/**
 * Each real control's pointer-events opt-in. HeroPanel's root is
 * click-through (see its comment, issue #575), so a control opts back in —
 * but only while the hero is interactive, so the opt-in cannot outlive
 * LeftPanel disabling the hero during the enemy's turn.
 *
 * EDITING RULE: any new clickable in this component must set
 * `pointerEvents: controlPointerEvents(interactive)`. The root punches a
 * click-through hole (see its comment below), so one that forgets is inert,
 * and the stacking sweep only catches the opposite mistake -- a surface that
 * opts back in when it should not.
 */
const controlPointerEvents = (interactive) => (interactive ? 'auto' : 'none')

/**
 * The hover-only icon surfaces (the desktop passive/status columns and the
 * mobile icon row) opt back in unconditionally, unlike the controls: they
 * carry no click handler, only hover tooltips, which stay readable during the
 * enemy's turn.
 *
 * They are also the one place #575's click-through hole is deliberately
 * re-armed, and that costs something: the desktop columns sit 135px out from a
 * 200px hero box, so they can overlap the centred CombatMovePanel, and a click
 * landing on one is lost rather than reaching a move card. Tooltips win here on
 * purpose. Gating them on `interactive` would not help (the overlap matters on
 * the player's turn), and 'none' would take the tooltips away.
 */
const HOVER_ONLY_POINTER_EVENTS = 'auto'

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
  interactive = true,
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
        pointerEvents: controlPointerEvents(interactive),
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

// The heading over an effect group, in both layouts. Smaller than anything
// on the type scale, which is why it stays a literal.
const EFFECT_HEADING_SIZE = '7px'

// How far out from the portrait the desktop effect columns sit. Named
// because HOVER_ONLY_POINTER_EVENTS's doc above reasons about this exact
// distance -- the columns hang outside a 200px hero box, which is what lets
// them overlap the move panel.
const EFFECT_COLUMN_OFFSET = '-135px'

/**
 * Where the six radial buttons sit around the portrait, in ring order:
 * top-left, top-right, left, right, bottom-left, bottom-right. Exploration
 * and combat draw DIFFERENT buttons in the SAME six places, so the geometry
 * is said once here and the two tables below carry only what differs (label,
 * handler, colour, and whether the category has any moves). They were two
 * hand-kept rows of six, with nothing asserting they matched.
 */
const RADIAL_SLOTS = [
  { top: '0px', left: '20%', transform: 'translateX(-50%)' },
  { top: '0px', left: 'calc(50% + 60px)', transform: 'translate(-50%, 0)' },
  { top: '50%', left: '-40px', transform: 'translateY(-50%)' },
  { top: '50%', left: 'calc(50% + 70px)', transform: 'translateY(-50%)' },
  { top: 'calc(50% + 80px)', left: '5px', transform: 'translate(0, -50%)' },
  { top: 'calc(50% + 80px)', left: 'calc(50% + 60px)', transform: 'translate(-50%, -50%)' },
]

/**
 * One ring's worth of buttons: `RADIAL_SLOTS` zipped onto what each ring
 * varies, BY INDEX -- a row's position in the table is its slot, so moving a
 * row moves that button and no test fails (the ring test compares the two
 * rings' position sequences, which are index-derived either way).
 *
 * Exactly six rows. A seventh takes `RADIAL_SLOTS[6]`, which is `undefined`;
 * spreading that is legal, so the button would render unpositioned and
 * silently -- add a slot first.
 *
 * A row's own `top`/`left`/`transform` wins over the slot. Nothing in
 * production uses that, and it is exported only so HeroPanel.test.jsx can
 * prove the ring is load-bearing at all: the rendered rings agree with each
 * other whether the geometry comes from here or from two hand-kept tables.
 */
export const inRadialSlots = (buttons) =>
  buttons.map((button, index) => ({ ...RADIAL_SLOTS[index], ...button }))

/**
 * The two effect groups the hero shows, in render order. Desktop draws them as
 * columns flanking the portrait, mobile as one row underneath, but WHICH groups
 * there are, what each is called and which player field it reads is said once,
 * here.
 */
const EFFECT_GROUPS = [
  { key: 'passives', heading: 'PASSIVES', side: 'left', testId: 'passives-column' },
  { key: 'status_effects', heading: 'STATUS', side: 'right', testId: 'status-effects-column' },
]

/**
 * EffectIconColumn — one of the two desktop icon columns flanking the
 * portrait: passives on the left, status effects on the right. Mobile shows
 * the same icons as a row below the hero instead.
 *
 * The two were near-duplicate blocks differing only in these props, edited in
 * lockstep. Hover-only, so they opt back in to pointer events unconditionally
 * (`HOVER_ONLY_POINTER_EVENTS`). The heading renders only when there is an
 * icon under it.
 */
function EffectIconColumn({ side, heading, effects, testId }) {
  return (
    <div data-testid={testId} style={{
      position: 'absolute',
      top: '50%',
      [side]: EFFECT_COLUMN_OFFSET,
      transform: 'translateY(-50%)',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      gap: '4px',
      zIndex: 10,
      pointerEvents: HOVER_ONLY_POINTER_EVENTS
    }}>
      {effects?.length > 0 && (
        <GameText variant="muted" size="xs" weight="bold" style={{ fontSize: EFFECT_HEADING_SIZE, marginBottom: '2px' }}>{heading}</GameText>
      )}
      <StatusEffectsIconPanel effects={effects} vertical />
    </div>
  )
}

function HeroPanel({
  player,
  isMobile,
  inCombat,
  // Whether the real controls (nav buttons, VitalBar) accept input. LeftPanel
  // passes false during the enemy's turn; the pointer-events opt-in and the
  // buttons' `disabled` both key off it — see the root div's comment (#575).
  // Defaults to true, so callers that omit it (the tests that render HeroPanel
  // on its own) get live controls.
  interactive = true,
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

  const explorationButtons = inRadialSlots([
    { key: 'attributes', label: 'ATTRIBUTES', onClick: onAttributeClick },
    { key: 'status', label: 'PARTY', onClick: onStatusClick },
    { key: 'inventory', label: 'INVENTORY', onClick: onInventoryClick },
    { key: 'skills', label: 'SKILLS', onClick: onSkillsClick },
    { key: 'actions', label: 'COMMANDS', onClick: onActionsClick },
    { key: 'interact', label: 'INTERACT', onClick: onInteractClick },
  ])

  // The ring's colours are its OWN, not `MOVE_CATEGORY_COLOR`: three of the
  // five differ on purpose (the ring reads as a HUD, the move cards as
  // categories), so do not "fix" them to match utils/categories.js.
  const combatButtons = inRadialSlots([
    { key: 'offensive', label: 'OFFENSIVE', onClick: onOffensiveClick, color: colors.danger, show: hasOffensiveMoves },
    { key: 'maneuver', label: 'MANEUVER', onClick: onManeuverClick, color: colors.text.highlight, show: hasManeuverMoves },
    { key: 'inventory', label: 'INVENTORY', onClick: onInventoryClick },
    { key: 'special', label: 'SPECIAL', onClick: onSpecialClick, color: colors.special, show: hasSpecialMoves },
    { key: 'miscellaneous', label: 'MISC', onClick: onMiscellaneousClick, color: colors.text.muted, show: hasMiscellaneousMoves },
    { key: 'defensive', label: 'DEFENSIVE', onClick: onDefensiveClick, color: colors.secondary, show: hasDefensiveMoves },
  ])

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
    <div data-testid="hero-panel-root" style={{
      display: 'flex',
      flexDirection: 'column',
      gap: spacing.md,
      alignItems: 'center',
      padding: `${spacing.xl} ${spacing.md}`,
      position: 'relative',
      // Issue #575: LeftPanel raises the box this whole component renders in
      // above CombatMovePanel so the category nav can never be covered by an
      // open move flyout. That lifts ALL of this component's inert chrome —
      // this root's padding ring, the Hero Head Container's blank space, the
      // portrait — above the panel too, where it would swallow clicks meant
      // for a move card underneath. `pointer-events` inherits, so 'none' here
      // punches the hole through every descendant, and each real control
      // opts back in through `controlPointerEvents`. The hover-only icon
      // surfaces are the deliberate exception (`HOVER_ONLY_POINTER_EVENTS`).
      // Set here rather than relying on LeftPanel's layer also being 'none',
      // so HeroPanel is click-through whoever renders it.
      pointerEvents: 'none',
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
        {/* Passive (left) and status (right) icons — see EffectIconColumn
            above. Desktop only; on mobile they render in a row below. */}
        {!isMobile && EFFECT_GROUPS.map(({ key, heading, side, testId }) => (
          <EffectIconColumn
            key={key}
            side={side}
            heading={heading}
            effects={player?.[key]}
            testId={testId}
          />
        ))}

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
          interactive={interactive}
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
          interactive={interactive}
        />

        {/* Surrounding Buttons — issue #536 item 3: the app had zero <nav>
            landmarks anywhere. This radial ring IS the primary in-game
            navigation between panels/move categories, so it gets one.
            display:'contents' means the <nav> contributes no box of its own,
            so every button's `position: absolute` still resolves against
            this Hero Head Container exactly as before. */}
        <nav aria-label={CATEGORY_NAV_LABEL} style={{ display: 'contents' }}>
        {/* Deliberately inline, unlike VitalBar and EffectIconColumn above.
            A RadialNavButton would need ten props -- the four slot fields,
            label, onClick, colour, interactive, isHovered and the hover
            setter, plus touchCompensation -- for one call site three lines
            away: a wide signature bought with nothing. Extract the STYLE
            object first if this grows again; the hover state is what makes
            the component awkward, not the markup. */}
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
              // Inert during the enemy's turn in every input modality, not just
              // the pointer: the `controlPointerEvents` opt-out below still
              // leaves the button focusable, and Enter/Space would stage a
              // category that pops open the instant it is the player's turn
              // again. It also exposes the inert state to assistive tech; the
              // visible dimming is the stacking layer's opacity/grayscale
              // (LeftPanel.jsx).
              disabled={!interactive}
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
                pointerEvents: controlPointerEvents(interactive),
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
      {isMobile && EFFECT_GROUPS.some(({ key }) => player?.[key]?.length > 0) && (
        <div data-testid="mobile-effect-row" style={{ display: 'flex', flexDirection: 'row', gap: '12px', justifyContent: 'center', flexWrap: 'wrap', pointerEvents: HOVER_ONLY_POINTER_EVENTS }}>
          {EFFECT_GROUPS.map(({ key, heading }) => player?.[key]?.length > 0 && (
            <div key={key} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '2px' }}>
              <GameText variant="muted" size="xs" weight="bold" style={{ fontSize: EFFECT_HEADING_SIZE }}>{heading}</GameText>
              <StatusEffectsIconPanel effects={player[key]} />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default React.memo(HeroPanel)
