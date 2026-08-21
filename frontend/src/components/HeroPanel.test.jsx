import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import HeroPanel from './HeroPanel';
import { makePlayer, makeCombatant, makeStatusEffect } from '../test/payloads';

describe('HeroPanel', () => {
  // Out of combat the `player` prop is usePlayer()'s merged status+stats object;
  // in combat LeftPanel overlays combat.player (a serialize_combatant payload)
  // on top of it, which is where `passives`/`status_effects` come from. Both
  // shapes come from src/test/payloads.js so a serializer rename breaks here.
  const mockPlayer = makePlayer({ hp: 80, max_hp: 100, fatigue: 120, max_fatigue: 150 });

  // Fresh spies per test. The previous version shared one frozen `mockProps`
  // object across the whole file and never cleared it, so a call recorded by an
  // earlier test satisfied a later `toHaveBeenCalled()` — the assertions could
  // not distinguish "this click fired the handler" from "some click did".
  const makeProps = (overrides = {}) => ({
    player: mockPlayer,
    inCombat: false,
    hasSpecialMoves: false,
    hasDefensiveMoves: false,
    hasOffensiveMoves: false,
    hasManeuverMoves: false,
    hasMiscellaneousMoves: false,
    onAttributeClick: vi.fn(),
    onStatusClick: vi.fn(),
    onSkillsClick: vi.fn(),
    onSpecialClick: vi.fn(),
    onInventoryClick: vi.fn(),
    onActionsClick: vi.fn(),
    onInteractClick: vi.fn(),
    onDefensiveClick: vi.fn(),
    onOffensiveClick: vi.fn(),
    onManeuverClick: vi.fn(),
    onMiscellaneousClick: vi.fn(),
    ...overrides,
  });

  const allCombatMoves = {
    inCombat: true,
    hasSpecialMoves: true,
    hasDefensiveMoves: true,
    hasOffensiveMoves: true,
    hasManeuverMoves: true,
    hasMiscellaneousMoves: true,
  };

  /**
   * Matcher for a VitalBar tooltip node: it renders `{label}<br/>{cur}/{max}`,
   * so it is the only element with this exact textContent whose sole child is
   * the <br> (every ancestor matches the text too).
   */
  const isTooltip = (text) => (_, el) =>
    el?.textContent === text && el.children.length === 1 && el.children[0].tagName === 'BR';

  /** Every radial button label currently on screen, in DOM order. */
  const buttonLabels = (container) =>
    Array.from(container.querySelectorAll('[style*="position: absolute"]'))
      .map((n) => n.textContent)
      .filter((t) => /^[A-Z]+$/.test(t));

  it('renders exactly the six exploration buttons, and no combat ones', () => {
    const { container } = render(<HeroPanel {...makeProps()} />);

    expect(buttonLabels(container)).toEqual([
      'ATTRIBUTES', 'PARTY', 'INVENTORY', 'SKILLS', 'COMMANDS', 'INTERACT',
    ]);
  });

  it('swaps the radial to the combat buttons, keeping INVENTORY in place', () => {
    const { container } = render(<HeroPanel {...makeProps(allCombatMoves)} />);

    // INVENTORY is the one slot shared between the two layouts.
    expect(buttonLabels(container)).toEqual([
      'OFFENSIVE', 'MANEUVER', 'INVENTORY', 'SPECIAL', 'MISC', 'DEFENSIVE',
    ]);
    expect(screen.queryByText('ATTRIBUTES')).toBeNull();
    expect(screen.queryByText('INTERACT')).toBeNull();
  });

  it('hides move category buttons in combat if not available', () => {
    const { container } = render(<HeroPanel {...makeProps({ inCombat: true })} />);

    // Only the always-present INVENTORY slot survives when the player knows no
    // castable move in any category.
    expect(buttonLabels(container)).toEqual(['INVENTORY']);
  });

  it.each([
    ['ATTRIBUTES', 'onAttributeClick'],
    ['PARTY', 'onStatusClick'],
    ['INVENTORY', 'onInventoryClick'],
    ['SKILLS', 'onSkillsClick'],
    ['COMMANDS', 'onActionsClick'],
    ['INTERACT', 'onInteractClick'],
  ])('routes the %s button to %s and to nothing else', (label, handlerName) => {
    const props = makeProps();
    render(<HeroPanel {...props} />);

    fireEvent.click(screen.getByText(label));

    expect(props[handlerName]).toHaveBeenCalledTimes(1);
    // Cross-wiring is the failure this catches: every other handler must be
    // untouched by this one click.
    Object.entries(props)
      .filter(([k, v]) => k !== handlerName && typeof v === 'function')
      .forEach(([, spy]) => expect(spy).not.toHaveBeenCalled());
  });

  it.each([
    ['OFFENSIVE', 'onOffensiveClick'],
    ['MANEUVER', 'onManeuverClick'],
    ['SPECIAL', 'onSpecialClick'],
    ['MISC', 'onMiscellaneousClick'],
    ['DEFENSIVE', 'onDefensiveClick'],
    ['INVENTORY', 'onInventoryClick'],
  ])('routes the combat %s button to %s and to nothing else', (label, handlerName) => {
    const props = makeProps(allCombatMoves);
    render(<HeroPanel {...props} />);

    fireEvent.click(screen.getByText(label));

    expect(props[handlerName]).toHaveBeenCalledTimes(1);
    Object.entries(props)
      .filter(([k, v]) => k !== handlerName && typeof v === 'function')
      .forEach(([, spy]) => expect(spy).not.toHaveBeenCalled());
  });

  it('calculates heart rate correctly (Exploration, High HP)', () => {
    const { container } = render(
      <HeroPanel {...makeProps({ player: makePlayer({ hp: 100, max_hp: 100 }) })} />
    );
    const heartImg = container.querySelector('img[alt="Hero Heart"]');
    // BPM = 60 + 0 (combat) + (1-1)*60 = 60  ->  duration 60/60 = 1s
    expect(heartImg.style.animation).toContain('1s');
  });

  it('calculates heart rate correctly (Combat, Low HP)', () => {
    const { container } = render(
      <HeroPanel {...makeProps({ inCombat: true, player: makePlayer({ hp: 0, max_hp: 100 }) })} />
    );
    const heartImg = container.querySelector('img[alt="Hero Heart"]');
    // BPM = 60 + 40 (combat) + (1-0)*80 = 180  ->  duration 60/180 = 0.333s
    expect(heartImg.style.animation).toContain('0.333');
  });

  it('handles button hover states', () => {
    render(<HeroPanel {...makeProps()} />);
    const button = screen.getByText('ATTRIBUTES');

    fireEvent.mouseEnter(button);
    // Hover accent #00ffaa
    expect(button.style.color).toBe('rgb(0, 255, 170)');

    fireEvent.mouseLeave(button);
    // Returns to colors.primary #00ff88
    expect(button.style.color).toBe('rgb(0, 255, 136)');
  });

  it('shows the HP tooltip on hover, pin-toggles it on click, and again on touch', () => {
    render(<HeroPanel {...makeProps()} />);
    const hpBar = screen.getByTestId('hp-bar');
    // The tooltip renders "<label><br/>current/max" in a single node, so its
    // only child is that <br> — which distinguishes it from every ancestor
    // that also has the same textContent.
    const tooltip = () => screen.queryByText(isTooltip('HP80/100'));

    fireEvent.mouseEnter(hpBar);
    expect(tooltip()).not.toBeNull();
    fireEvent.mouseLeave(hpBar);
    expect(tooltip()).toBeNull();

    fireEvent.click(hpBar); // pin
    expect(tooltip()).not.toBeNull();
    fireEvent.click(hpBar); // un-pin
    expect(tooltip()).toBeNull();

    fireEvent.touchStart(hpBar); // touch pins
    expect(tooltip()).not.toBeNull();
    fireEvent.touchStart(hpBar); // and un-pins
    expect(tooltip()).toBeNull();
  });

  it('shows the Fatigue tooltip independently of the HP bar', () => {
    render(<HeroPanel {...makeProps()} />);
    const hpBar = screen.getByTestId('hp-bar');
    const fatigueBar = screen.getByTestId('fatigue-bar');
    const fatigueTooltip = () => screen.queryByText(isTooltip('Fatigue120/150'));
    const hpTooltip = () => screen.queryByText(isTooltip('HP80/100'));

    fireEvent.mouseEnter(fatigueBar);
    expect(fatigueTooltip()).not.toBeNull();
    // The two bars keep separate state — hovering one must not reveal the other.
    expect(hpTooltip()).toBeNull();

    fireEvent.mouseLeave(fatigueBar);
    expect(fatigueTooltip()).toBeNull();

    fireEvent.click(fatigueBar); // pin
    expect(fatigueTooltip()).not.toBeNull();
    fireEvent.touchStart(fatigueBar); // touch un-pins from the pinned state
    expect(fatigueTooltip()).toBeNull();
    expect(hpBar).toBeInTheDocument();
  });

  it('fills each bar to the served ratio', () => {
    render(<HeroPanel {...makeProps()} />);

    // 80/100 and 120/150 -> 80%.
    expect(screen.getByTestId('hp-bar').firstElementChild.style.height).toBe('80%');
    expect(screen.getByTestId('fatigue-bar').firstElementChild.style.height).toBe('80%');
  });

  it('falls back to full 100/100 and 150/150 bars when no player is loaded yet', () => {
    render(<HeroPanel {...makeProps({ player: null })} />);

    fireEvent.mouseEnter(screen.getByTestId('hp-bar'));
    expect(screen.getByText(isTooltip('HP100/100'))).toBeInTheDocument();
    expect(screen.getByTestId('hp-bar').firstElementChild.style.height).toBe('100%');

    fireEvent.mouseEnter(screen.getByTestId('fatigue-bar'));
    expect(screen.getByText(isTooltip('Fatigue150/150'))).toBeInTheDocument();
  });

  describe('passive / status icon rows', () => {
    // These fields ride on the COMBAT payload (serialize_combatant), which
    // LeftPanel merges over the explored-mode player.
    const withEffects = makeCombatant({
      hp: 80,
      max_hp: 100,
      fatigue: 120,
      max_fatigue: 150,
      passives: [makeStatusEffect({ name: 'Iron Fist', type: 'passive' })],
      status_effects: [makeStatusEffect({ name: 'Burning', type: 'ailment', beats_left: 3 })],
    });

    it('renders the mobile inline row with both icon groups', () => {
      render(<HeroPanel {...makeProps({ isMobile: true, player: withEffects })} />);

      expect(screen.getByText('PASSIVES')).toBeInTheDocument();
      expect(screen.getByText('STATUS')).toBeInTheDocument();
      // StatusEffectsIconPanel derives the glyph from the effect NAME, so an
      // icon proves the effect array actually reached it.
      expect(screen.getByText('✨')).toBeInTheDocument();
      expect(screen.getByText('🔥')).toBeInTheDocument();
    });

    it('renders the desktop side columns rather than the mobile row', () => {
      const { container } = render(
        <HeroPanel {...makeProps({ isMobile: false, player: withEffects })} />
      );

      expect(screen.getByText('PASSIVES')).toBeInTheDocument();
      expect(screen.getByText('🔥')).toBeInTheDocument();
      // Desktop side columns are absolutely positioned; the mobile row is a
      // centered wrapping flex row.
      const mobileRow = Array.from(
        container.querySelectorAll('div[style*="flex-direction: row"]')
      ).find((d) => d.style.justifyContent === 'center' && d.style.flexWrap === 'wrap');
      expect(mobileRow).toBeUndefined();
    });

    it('renders no icon row at all when the player has neither passives nor effects', () => {
      render(<HeroPanel {...makeProps({ isMobile: true })} />);

      expect(screen.queryByText('PASSIVES')).toBeNull();
      expect(screen.queryByText('STATUS')).toBeNull();
    });
  });

  // usePlayer's error fallback ships hp:0/max_hp:0. Dividing by a zero max
  // previously produced height:"NaN%" and animation:"pulse NaNs".
  it('renders no NaN in any style when hp/fatigue maxima are zero', () => {
    const degraded = { hp: 0, max_hp: 0, fatigue: 0, max_fatigue: 0 };
    const { container } = render(<HeroPanel {...makeProps({ player: degraded })} />);

    const styled = container.querySelectorAll('[style]');
    expect(styled.length).toBeGreaterThan(0);
    styled.forEach((el) => {
      expect(el.getAttribute('style')).not.toMatch(/NaN/);
    });

    // The bars collapse to empty rather than rendering an invalid height.
    expect(screen.getByTestId('hp-bar').firstElementChild.style.height).toBe('0%');
    expect(screen.getByTestId('fatigue-bar').firstElementChild.style.height).toBe('0%');
  });
});
