import { render, screen, within } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import BeatTimeline from './BeatTimeline';

const pendingMove = (overrides = {}) => ({
  name: 'NPC_Attack',
  display_name: 'Attack',
  category: 'Offensive',
  current_stage: 0,
  beats_left: 1,
  beats_until_resolve: 1,
  ...overrides,
});

describe('BeatTimeline', () => {
  it('shows a placeholder instead of a dead strip when nobody has a pending move', () => {
    render(<BeatTimeline combat={{ player: { id: 'player', name: 'Jean', hp: 10 }, enemies: [] }} />);
    expect(screen.getByText(/no moves committed/i)).toBeInTheDocument();
    expect(screen.queryByRole('list')).not.toBeInTheDocument();
  });

  it('renders one marker per pending combatant, labelled by name', () => {
    const combat = {
      player: { id: 'player', name: 'Jean', hp: 10, current_move: pendingMove({ beats_until_resolve: 2 }) },
      enemies: [
        { id: 'enemy_1', name: 'Slime', hp: 5, current_move: pendingMove({ beats_until_resolve: 4 }) },
      ],
    };
    render(<BeatTimeline combat={combat} />);
    expect(screen.getByText('Jean')).toBeInTheDocument();
    expect(screen.getByText('Slime')).toBeInTheDocument();
  });

  it('stacks colliding combatants into a single column instead of losing one', () => {
    const combat = {
      player: { id: 'player', name: 'Jean', hp: 10, current_move: pendingMove({ beats_until_resolve: 3 }) },
      enemies: [
        { id: 'enemy_1', name: 'Slime', hp: 5, current_move: pendingMove({ beats_until_resolve: 3 }) },
        { id: 'enemy_2', name: 'Cave Bat', hp: 5, current_move: pendingMove({ beats_until_resolve: 3 }) },
      ],
    };
    render(<BeatTimeline combat={combat} />);
    // All three collide on beat 3 — exactly one column (listitem), all three
    // markers present inside it.
    const [column] = screen.getAllByRole('listitem');
    expect(column).toBeInTheDocument();
    expect(screen.getByText('Jean')).toBeInTheDocument();
    expect(screen.getByText('Slime')).toBeInTheDocument();
    expect(screen.getByText('Cave Bat')).toBeInTheDocument();
    // DOM order within the collision, not just presence: Jean first (the
    // priority order the util's sort establishes), enemies alphabetically
    // after. A pure presence check would still pass if .map() rendered the
    // entries in a shuffled order (e.g. a broken sort upstream) — this
    // catches that. Note: this cannot observe the *visual* stacking order
    // (a CSS flex-direction choice), only the DOM/array order, since jsdom
    // does not lay out flexbox.
    const markerTexts = Array.from(column.querySelectorAll('[title]')).map((el) => el.textContent);
    expect(markerTexts).toEqual(['⚔Jean', '⚔Cave Bat', '⚔Slime']);
  });

  it('renders a separate column per distinct beat, ordered soonest first', () => {
    const combat = {
      enemies: [
        { id: 'enemy_1', name: 'Slime', hp: 5, current_move: pendingMove({ beats_until_resolve: 6 }) },
        { id: 'enemy_2', name: 'Cave Bat', hp: 5, current_move: pendingMove({ beats_until_resolve: 2 }) },
      ],
    };
    render(<BeatTimeline combat={combat} />);
    const columns = screen.getAllByRole('listitem');
    expect(columns).toHaveLength(2);
    // Cave Bat (beat 2) must appear in the first column, Slime (beat 6) in the second.
    expect(columns[0].textContent).toContain('Cave Bat');
    expect(columns[1].textContent).toContain('Slime');
  });

  it("labels Jean's own marker distinctly from an ally with the same name text convention", () => {
    const combat = {
      player: { id: 'player', name: 'Jean Claire', hp: 10, current_move: pendingMove({ beats_until_resolve: 1 }) },
    };
    render(<BeatTimeline combat={combat} />);
    // The player marker renders the fixed label "Jean", not the raw entity
    // name, so it reads identically regardless of save-file naming.
    expect(screen.getByText('Jean')).toBeInTheDocument();
    expect(screen.queryByText('Jean Claire')).not.toBeInTheDocument();
  });

  it('drops a dead enemy from the timeline even though it still carries a pending move', () => {
    const combat = {
      enemies: [
        { id: 'enemy_1', name: 'Slime', hp: 0, current_move: pendingMove({ beats_until_resolve: 2 }) },
      ],
    };
    render(<BeatTimeline combat={combat} />);
    expect(screen.getByText(/no moves committed/i)).toBeInTheDocument();
  });

  it('explains what the "next"/"+N" column labels mean (#540 item 15)', () => {
    const combat = {
      player: { id: 'player', name: 'Jean', hp: 10, current_move: pendingMove({ beats_until_resolve: 1 }) },
    };
    render(<BeatTimeline combat={combat} />);
    expect(screen.getByText(/beats until each action resolves/i)).toBeInTheDocument();
  });

  it('does not show the legend when the strip itself is empty', () => {
    render(<BeatTimeline combat={{ player: { id: 'player', name: 'Jean', hp: 10 }, enemies: [] }} />);
    expect(screen.queryByText(/beats until each action resolves/i)).not.toBeInTheDocument();
  });

  // Issue #586: a deadly enemy wind-up must read differently from a routine
  // one on the strip too, and by a glyph rather than colour alone.
  describe('heavy-move warning', () => {
    it('marks a deadly enemy wind-up with a warning glyph and names it in the title', () => {
      const combat = {
        enemies: [{
          id: 'enemy_1', name: 'King Slime', hp: 400,
          current_move: pendingMove({ display_name: 'Tidal Surge', beats_until_resolve: 7, telegraph_severity: 'deadly' }),
        }],
      };
      render(<BeatTimeline combat={combat} />);
      const marker = screen.getByTitle(/King Slime — Tidal Surge/);
      expect(marker.title).toMatch(/Deadly move/);
      expect(screen.getByLabelText('Deadly move')).toBeInTheDocument();
      expect(marker.textContent).toContain('⚠');
      // The severity WORD is visible, not only in the title/aria-label: on
      // touch there is no hover, and the glyph alone cannot tell a heavy
      // wind-up from a deadly one.
      expect(within(marker).getByText(/DEADLY/)).toBeInTheDocument();
    });

    it('spells out HEAVY for a heavy enemy wind-up', () => {
      const combat = {
        enemies: [{
          id: 'enemy_1', name: 'Gorgon', hp: 40,
          current_move: pendingMove({ display_name: 'Crush', beats_until_resolve: 3, telegraph_severity: 'heavy' }),
        }],
      };
      render(<BeatTimeline combat={combat} />);
      const marker = screen.getByTitle(/Gorgon — Crush/);
      expect(within(marker).getByText(/HEAVY/)).toBeInTheDocument();
      expect(within(marker).queryByText(/DEADLY/)).toBeNull();
    });

    it('leaves a routine wind-up unmarked (negative control)', () => {
      const combat = {
        enemies: [{ id: 'enemy_1', name: 'Slime', hp: 5, current_move: pendingMove({ beats_until_resolve: 2 }) }],
      };
      render(<BeatTimeline combat={combat} />);
      expect(screen.queryByLabelText(/move$/i)).toBeNull();
      expect(screen.getByTitle(/Slime — Attack/).textContent).not.toContain('⚠');
    });

    it('does not warn about a friendly heavy move — the glyph is a threat cue for Jean', () => {
      const combat = {
        allies: [{
          id: 'ally_1', name: 'Gorran', hp: 50,
          current_move: pendingMove({ display_name: 'Club Strike', beats_until_resolve: 2, telegraph_severity: 'heavy' }),
        }],
      };
      render(<BeatTimeline combat={combat} />);
      expect(screen.queryByLabelText('Heavy move')).toBeNull();
      expect(screen.getByTitle(/Gorran — Club Strike/).textContent).not.toContain('⚠');
    });
  });
});
