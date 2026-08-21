import { render, screen } from '@testing-library/react';
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
});
