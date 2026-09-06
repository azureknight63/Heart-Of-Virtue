import { render, screen, fireEvent, within } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import StatsPanel from './StatsPanel';
import { makePlayerStats } from '../test/payloads';
import { GLOSSARY_ENTRIES } from '../data/combatGlossary';

describe('StatsPanel', () => {
  // Derived from the real GameService.get_player_stats payload
  // (src/test/payloads.js) rather than hand-written. The old literal carried
  // `attack`, `accuracy` and `evasion` — three keys no serializer emits (the
  // engine has hit_accuracy/evasion_chance and no `attack` stat at all), so the
  // fixture agreed with a component reading fields that never arrive.
  const mockPlayer = makePlayerStats({
    name: 'Hero',
    level: 5,
    exp: 1200,
    max_exp: 2000,
    hp: 80,
    max_hp: 100,
    fatigue: 40,
    max_fatigue: 50,
    protection: 10,
    weight: 15.5,
    max_weight: 50,
    attack_damage_min: 10,
    attack_damage_max: 20,
    hit_accuracy: 85,
    evasion_chance: 10,
    strength: 12,
    strength_base: 10,
    finesse: 8,
    finesse_base: 10,
    resistance: {
      physical: 0.1,
      fire: 0.05,
      cold: 0,
      lightning: -0.05,
    },
    status_resistance: {
      poison: 0.2,
      stun: 0.1,
    },
    // get_player_stats emits {name, steps_left} pairs here, not serialize_state dicts.
    states: [
      { name: 'Blessed', description: 'Increased stats', steps_left: 5 },
      { name: 'Poisoned', description: 'Taking damage over time' },
    ],
  });

  /** The tooltip-bearing tile that owns an attribute row. */
  const attributeTile = (tooltip) => screen.getByTitle(tooltip);
  const STRENGTH_TIP = /Increases melee damage, carrying capacity, armor effectiveness/i;
  const FINESSE_TIP = /Improves weapon damage.*hit accuracy/i;
  const SPEED_TIP = /Determines turn order and action preparation time/i;

  it('renders null if player is missing', () => {
    const { container } = render(<StatsPanel player={null} />);
    expect(container.firstChild).toBeNull();
  });

  it('renders player stats correctly', () => {
    render(<StatsPanel player={mockPlayer} />);

    expect(screen.getByText(/📊 CHARACTER STATS/i)).toBeInTheDocument();

    // Values read out of THEIR OWN tile. The old assertions were
    // `getAllByText(/5/i).length > 0` and friends — /5/ matches "15.5", "85"
    // and "5T" alike, so they passed no matter what number the level tile
    // rendered, or whether it rendered one at all.
    expect(screen.getByText('Level').closest('div')).toHaveTextContent('5');
    expect(within(attributeTile(STRENGTH_TIP)).getByText('12')).toBeInTheDocument();
    expect(within(attributeTile(STRENGTH_TIP)).getByText('BASE: 10')).toBeInTheDocument();
    expect(within(attributeTile(FINESSE_TIP)).getByText('8')).toBeInTheDocument();

    // Core stats
    expect(screen.getByText('80/100')).toBeInTheDocument();

    // Resistances render as a percentage of the 0-1 multiplier.
    expect(screen.getByText(/PHYSICAL: 10%/i)).toBeInTheDocument();
    expect(screen.getByText(/FIRE: 5%/i)).toBeInTheDocument();
    expect(screen.getByText(/LIGHTNING: -5%/i)).toBeInTheDocument();
    // A resistance of exactly 1 (the neutral multiplier) is filtered out.
    expect(screen.queryByText(/ICE:/i)).toBeNull();

    // Active effects, with the remaining-step counter for the one that has it.
    const blessed = screen.getByText('Blessed').closest('div');
    expect(blessed).toHaveTextContent('5T');
    // 'Poisoned' carries no steps_left, so no counter chip is rendered for it.
    expect(screen.getByText('Poisoned').closest('div').textContent).toBe('Poisoned');
  });

  it('applies correct colors for attributes', () => {
    render(<StatsPanel player={mockPlayer} />);

    // Strength is 12 (base 10) -> buffed color #00ff88
    const strengthContainer = attributeTile(STRENGTH_TIP);
    const strengthVal = within(strengthContainer).getByText('12');
    expect(strengthVal.style.color).toBe('rgb(0, 255, 136)'); // #00ff88

    // Finesse is 8 (base 10) -> debuffed color #ff6666
    const finesseContainer = attributeTile(FINESSE_TIP);
    const finesseVal = within(finesseContainer).getByText('8');
    expect(finesseVal.style.color).toBe('rgb(255, 68, 68)'); // #ff4444 (colors.danger)

    // Speed is 10 (base 10) -> normal color #ffcc00 (colors.gold)
    const speedContainer = attributeTile(SPEED_TIP);
    const speedVal = within(speedContainer).getByText('10');
    expect(speedVal.style.color).toBe('rgb(255, 204, 0)'); // #ffcc00
  });


  it('gives every attribute row an explanatory tooltip', () => {
    // The old test was named "handles hover effects for all stat rows" but
    // hovered nothing and checked ONE row's existence. What actually matters is
    // that no attribute ships without an explanation.
    render(<StatsPanel player={mockPlayer} />);

    const ATTRIBUTES = ['Strength', 'Finesse', 'Speed', 'Endurance', 'Charisma', 'Intelligence', 'Faith'];
    ATTRIBUTES.forEach((name) => {
      const tile = screen.getByText(name).closest('[title]');
      expect(tile, `${name} has no tooltip`).not.toBeNull();
      expect(tile.getAttribute('title').length).toBeGreaterThan(20);
    });
  });


  it.each([['✕'], ['CLOSE SHEET']])(
    'calls onClose exactly once from the %s control',
    (label) => {
      // Two separate affordances close this sheet; the old file only covered
      // the ✕, and did so with a bare `toHaveBeenCalled()` that could not tell
      // one call from five.
      const mockOnClose = vi.fn();
      render(<StatsPanel player={mockPlayer} onClose={mockOnClose} />);

      fireEvent.click(screen.getByText(label));
      expect(mockOnClose).toHaveBeenCalledTimes(1);
      expect(mockOnClose).toHaveBeenCalledWith(expect.anything());
    }
  );

  it('drops the resistance chips and shows the empty-effects copy when those fields are null', () => {
    // Asserting only that the header still rendered proved nothing about the
    // null branches this test exists for.
    const minimalPlayer = {
      ...mockPlayer,
      resistance: null,
      status_resistance: null,
      states: null,
    };
    render(<StatsPanel player={minimalPlayer} />);

    expect(screen.getByText(/📊 CHARACTER STATS/i)).toBeInTheDocument();
    // No resistance chips at all...
    expect(screen.queryByText(/PHYSICAL:/i)).toBeNull();
    expect(screen.queryByText(/FIRE:/i)).toBeNull();
    // ...and the explicit empty state instead of a bare panel.
    expect(screen.getByText('No active status effects')).toBeInTheDocument();
    expect(screen.queryByText('Blessed')).toBeNull();
    // The attributes still render, so this is a partial payload, not a blank sheet.
    expect(within(attributeTile(STRENGTH_TIP)).getByText('12')).toBeInTheDocument();
  });

  const sparsePlayer = {
    hp: 10, max_hp: 10, fatigue: 5, max_fatigue: 5,
    attack_damage_min: 1, attack_damage_max: 2, hit_accuracy: 50, evasion_chance: 10,
  };

  it('defaults protection and level when absent from the player object', () => {
    render(<StatsPanel player={sparsePlayer} />);

    // Read each default out of its own tile: a bare getByText('0') would be
    // satisfied by any zero anywhere on the sheet.
    expect(screen.getByText('Protection').closest('div')).toHaveTextContent('0');
    expect(screen.getByText('Level').closest('div')).toHaveTextContent('1');
  });

  it('defaults exp to 0 when absent, still rendering the EXP panel via max_exp', () => {
    const player = { ...sparsePlayer, max_exp: 100 };
    render(<StatsPanel player={player} />);

    expect(screen.getByText('0 / 100')).toBeInTheDocument();
    expect(screen.getByText('100 EXP to next level')).toBeInTheDocument();
  });

  it('defaults an attribute and its base to 10 when absent from the player object', () => {
    render(<StatsPanel player={sparsePlayer} />);

    const strengthContainer = attributeTile(STRENGTH_TIP);
    expect(within(strengthContainer).getByText('10')).toBeInTheDocument();
    expect(within(strengthContainer).getByText('BASE: 10')).toBeInTheDocument();
  });

  it('colors a resistance value above 1 as a weakness (danger color)', () => {
    const player = { ...sparsePlayer, resistance: { fire: 1.5 } };
    render(<StatsPanel player={player} />);

    const chip = screen.getByText(/FIRE: 150%/i);
    expect(chip.style.color).toBe('rgb(255, 68, 68)'); // colors.danger (#ff4444)
  });

  it('labels flat damage reduction with the word the combat glossary quotes (#507)', () => {
    // The glossary's "Protection & resistance" entry tells the player which row
    // on this panel it is talking about. Renaming the row without updating the
    // copy sends them looking for a label that is not there — the mockup
    // already said "Defense", which this panel has never used.
    render(<StatsPanel player={makePlayerStats()} />);
    const protectionEntry = GLOSSARY_ENTRIES.find(e => e.id === 'protection');
    expect(protectionEntry, 'no glossary entry with id "protection"').toBeDefined();

    // Take the label out of the glossary copy and require the panel to render
    // it, rather than spelling 'Protection' a third time here. Asserting in
    // this direction is what makes the test drift-proof: renaming the row
    // fails on getByText, and rewording the entry to quote a row that does not
    // exist fails too. Two literals agreeing with each other would catch
    // neither.
    const quoted = protectionEntry.body.match(/"([^"]+)" row/);
    expect(quoted, 'the entry should send the player to a named row on this panel').not.toBeNull();
    expect(screen.getByText(quoted[1])).toBeInTheDocument();
    // The mockup called this row "Defense", a word the panel has never used.
    expect(quoted[1]).not.toBe('Defense');
  });

  describe('Accuracy and Evasion presentation', () => {
    const withCombatStats = (over) => ({ ...mockPlayer, ...over });

    it('renders Accuracy and Evasion as ratings, not percentages', () => {
      // They are the two halves of one subtraction, not probabilities: a "%"
      // made Accuracy read as an impossible 108% and Evasion read as a dodge
      // chance it never was.
      render(<StatsPanel player={withCombatStats({ hit_accuracy: 108, evasion_chance: 10 })} onClose={vi.fn()} />);

      expect(screen.getByText('108')).toBeInTheDocument();
      expect(screen.queryByText('108%')).not.toBeInTheDocument();
      expect(screen.queryByText('10%')).not.toBeInTheDocument();
    });

    it('explains the hit formula and the evasion headroom in the Accuracy tooltip', () => {
      render(<StatsPanel player={withCombatStats({ hit_accuracy: 108, evasion_chance: 10 })} onClose={vi.fn()} />);

      const tip = screen.getByText('108').closest('[title]').getAttribute('title');
      expect(tip).toMatch(/Accuracy minus the target's Evasion/i);
      // Stated as approximate on purpose: the rating folds the attacker's terms
      // before evasion is subtracted, while the engine's roll subtracts evasion
      // first, so the two part company by a point for ~0.7% of stat pairs.
      expect(tip).toMatch(/about your Accuracy/i);
      // 108 - 100 = 8 points of evasion absorbed before any miss.
      expect(tip).toMatch(/Evasion is 8 or lower/i);
    });

    it('clamps the headroom at zero when accuracy is below the cap', () => {
      render(<StatsPanel player={withCombatStats({ hit_accuracy: 92, evasion_chance: 4 })} onClose={vi.fn()} />);

      const tip = screen.getByText('92').closest('[title]').getAttribute('title');
      expect(tip).toMatch(/Evasion is 0 or lower/i);
    });

    it('describes Evasion as subtracted from the attacker, not a dodge chance', () => {
      render(<StatsPanel player={withCombatStats({ hit_accuracy: 108, evasion_chance: 10 })} onClose={vi.fn()} />);

      const evasionTile = screen.getByText('Evasion').closest('[title]');
      expect(evasionTile.getAttribute('title')).toMatch(/Subtracted from an attacker/i);
    });
  });
});
