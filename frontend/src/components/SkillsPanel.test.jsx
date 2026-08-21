import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import SkillsPanel from './SkillsPanel';
import apiEndpoints from '../api/endpoints';
import { ToastProvider, useToast } from '../context/ToastContext';

// Mock apiEndpoints
vi.mock('../api/endpoints', () => ({
  default: {
    player: {
      getSkills: vi.fn(),
      learnSkill: vi.fn(),
    },
  },
}));

vi.mock('../context/ToastContext', () => ({
  ToastProvider: ({ children }) => <div>{children}</div>,
  useToast: vi.fn(() => ({
    error: vi.fn(),
    success: vi.fn(),
    info: vi.fn(),
    warning: vi.fn()
  }))
}));

describe('SkillsPanel', () => {
  const mockPlayer = {
    name: 'Hero',
    skill_points: 5,
  };

  /**
   * Shape of GameService.get_player_skills()
   * (src/api/services/game_service.py:~3066): every entry carries name,
   * display_name, description, required_exp, is_known and can_learn, and the
   * response is keyed by discipline alongside a `skill_exp` map.
   */
  const mockSkillsData = {
    skill_tree: {
      Combat: [
        {
          name: 'Power Strike',
          display_name: 'Power Strike',
          description: 'A powerful melee attack.',
          required_exp: 100,
          is_known: false,
          can_learn: true,
        },
        {
          name: 'Cleave',
          display_name: 'Cleave',
          description: 'Hit multiple enemies.',
          required_exp: 200,
          is_known: false,
          can_learn: false,
        },
      ],
      Magic: [
        {
          name: 'Fireball',
          display_name: 'Fireball',
          description: 'Shoot a ball of fire.',
          required_exp: 150,
          is_known: true,
          can_learn: false,
        },
      ],
    },
    skill_exp: {
      Combat: 100,
      Magic: 50,
    },
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders loading state initially', async () => {
    apiEndpoints.player.getSkills.mockReturnValue(new Promise(() => { })); // Never resolves
    render(
      <ToastProvider>
        <SkillsPanel player={mockPlayer} onClose={() => { }} />
      </ToastProvider>
    );
    expect(screen.getByText(/Accessing ancient scrolls/i).textContent)
      .toMatch(/Accessing ancient scrolls/i);
    // No skill list, and no error, while the request is still in flight.
    expect(screen.queryByText(/Failed to load skills/i)).toBeNull();
    expect(screen.queryByText(/LEARN/)).toBeNull();
  });

  it('renders error state if fetch fails', async () => {
    apiEndpoints.player.getSkills.mockRejectedValue(new Error('Fetch failed'));
    render(
      <ToastProvider>
        <SkillsPanel player={mockPlayer} onClose={() => { }} />
      </ToastProvider>
    );

    await waitFor(() => {
      expect(screen.getByText(/Failed to load skills/i)).toBeDefined();
    });
  });

  it('renders skills data correctly', async () => {
    apiEndpoints.player.getSkills.mockResolvedValue({
      data: {
        success: true,
        skills: mockSkillsData,
      },
    });

    render(
      <ToastProvider>
        <SkillsPanel player={mockPlayer} onClose={() => { }} />
      </ToastProvider>
    );

    await waitFor(() => {
      expect(screen.getByText(/⚡ ABILITIES & SKILLS/i).textContent)
        .toMatch(/⚡ ABILITIES & SKILLS/);
    });

    // The XP readout reflects the SELECTED discipline (Combat: 100), not the
    // other one (Magic: 50) and not a sum.
    expect(screen.getByText(/100 XP/).textContent).toMatch(/100 XP/);
    expect(screen.queryByText(/50 XP/)).toBeNull();

    // Both disciplines get a tab; Combat is auto-selected as the one with XP.
    expect(screen.getByText('Combat').textContent).toBe('Combat');
    expect(screen.getByText('Magic').textContent).toBe('Magic');

    // An affordable, unknown skill offers LEARN with its cost.
    expect(screen.getByText('Power Strike').textContent).toBe('Power Strike');
    expect(screen.getByText('A powerful melee attack.').textContent)
      .toBe('A powerful melee attack.');
    const learn = screen.getByText(/LEARN \(100\)/).closest('button');
    expect(learn.disabled).toBe(false);

    // An unaffordable one is listed but its button is dead, with the
    // requirement spelled out — this branch was previously untested.
    expect(screen.getByText('Cleave').textContent).toBe('Cleave');
    const cleaveBtn = screen.getByText(/LEARN \(200\)/).closest('button');
    expect(cleaveBtn.disabled).toBe(true);
    expect(screen.getByText(/Requires 200 Combat XP/).textContent)
      .toMatch(/Requires 200 Combat XP/);

    // Nothing from the other discipline leaks in.
    expect(screen.queryByText('Fireball')).toBeNull();
  });

  it('switches categories when clicked', async () => {
    apiEndpoints.player.getSkills.mockResolvedValue({
      data: {
        success: true,
        skills: mockSkillsData,
      },
    });

    render(
      <ToastProvider>
        <SkillsPanel player={mockPlayer} onClose={() => { }} />
      </ToastProvider>
    );

    await waitFor(() => {
      expect(screen.getAllByText(/Combat/i).length).toBeGreaterThan(0);
    });


    fireEvent.click(screen.getByText('Magic'));

    expect(screen.getByText('Fireball').textContent).toBe('Fireball');
    expect(screen.getByText('Shoot a ball of fire.').textContent).toBe('Shoot a ball of fire.');
    // A known skill shows the learned badge instead of a LEARN button.
    expect(screen.getByText(/✓ Learned/).textContent).toMatch(/✓ Learned/);
    expect(screen.queryByText(/LEARN \(/)).toBeNull();

    // Switching disciplines swaps the list AND the XP readout (Magic: 50).
    expect(screen.queryByText('Power Strike')).toBeNull();
    expect(screen.queryByText('Cleave')).toBeNull();
    expect(screen.getByText(/50 XP/).textContent).toMatch(/50 XP/);
  });

  it('calls learnSkill when Learn button is clicked', async () => {
    apiEndpoints.player.getSkills.mockResolvedValue({
      data: {
        success: true,
        skills: mockSkillsData,
      },
    });

    apiEndpoints.player.learnSkill.mockResolvedValue({
      data: {
        success: true,
        skills: {
          ...mockSkillsData,
          skill_tree: {
            ...mockSkillsData.skill_tree,
            Combat: [
              {
                ...mockSkillsData.skill_tree.Combat[0],
                is_known: true,
              },
              mockSkillsData.skill_tree.Combat[1],
            ],
          },
        },
      },
    });

    render(
      <ToastProvider>
        <SkillsPanel player={mockPlayer} onClose={() => { }} />
      </ToastProvider>
    );

    await waitFor(() => {
      expect(screen.getByText(/Power Strike/i)).toBeDefined();
    });

    const learnButton = screen.getByText(/LEARN \(100\)/i);
    fireEvent.click(learnButton);

    // The skill's `name` and the SELECTED category — not the display name, and
    // not the category the skill happens to be listed under in the fixture.
    expect(apiEndpoints.player.learnSkill).toHaveBeenCalledTimes(1);
    expect(apiEndpoints.player.learnSkill).toHaveBeenCalledWith('Power Strike', 'Combat');

    await waitFor(() => {
      // The response's refreshed tree replaces the list in place: Power Strike
      // flips to learned and loses its LEARN button.
      expect(screen.getByText(/✓ Learned/).textContent).toMatch(/✓ Learned/);
    });
    expect(screen.queryByText(/LEARN \(100\)/)).toBeNull();
    // Cleave is untouched.
    expect(screen.getByText(/LEARN \(200\)/).closest('button').disabled).toBe(true);
  });

  it('handles learnSkill error', async () => {
    apiEndpoints.player.getSkills.mockResolvedValue({
      data: {
        success: true,
        skills: mockSkillsData,
      },
    });

    const mockError = vi.fn();
    useToast.mockReturnValue({
      error: mockError,
      success: vi.fn(),
      info: vi.fn(),
      warning: vi.fn()
    });

    apiEndpoints.player.learnSkill.mockRejectedValue({
      response: {
        data: {
          error: 'Not enough skill points',
        },
      },
    });

    render(
      <ToastProvider>
        <SkillsPanel player={mockPlayer} onClose={() => { }} />
      </ToastProvider>
    );

    await waitFor(() => {
      expect(screen.getByText(/Power Strike/i)).toBeDefined();
    });

    fireEvent.click(screen.getByText(/LEARN \(100\)/i));

    await waitFor(() => {
      expect(mockError).toHaveBeenCalledWith('Not enough skill points');
    });
    // A failed learn leaves the button live so the player can retry.
    expect(screen.getByText(/LEARN \(100\)/).closest('button').disabled).toBe(false);
    expect(screen.queryByText(/✓ Learned/)).toBeNull();
  });

  it('calls onClose when close button is clicked', async () => {
    apiEndpoints.player.getSkills.mockResolvedValue({
      data: {
        success: true,
        skills: mockSkillsData,
      },
    });

    const mockOnClose = vi.fn();
    render(
      <ToastProvider>
        <SkillsPanel player={mockPlayer} onClose={mockOnClose} />
      </ToastProvider>
    );

    await waitFor(() => {
      expect(screen.getByText(/✕/i)).toBeDefined();
    });

    fireEvent.click(screen.getByText(/✕/i));
    expect(mockOnClose).toHaveBeenCalledTimes(1);
    // Closing is not a learn.
    expect(apiEndpoints.player.learnSkill).not.toHaveBeenCalled();
  });

  it('returns null when there is no player', () => {
    const { container } = render(
      <ToastProvider>
        <SkillsPanel player={null} onClose={() => {}} />
      </ToastProvider>
    );
    expect(container.firstChild.firstChild).toBeNull();
  });

  it('shows "No skill data available" when the fetch succeeds without data', async () => {
    apiEndpoints.player.getSkills.mockResolvedValue({ data: { success: false } });
    render(
      <ToastProvider>
        <SkillsPanel player={mockPlayer} onClose={() => {}} />
      </ToastProvider>
    );

    await waitFor(() => {
      expect(screen.getByText(/No skill data available/i)).toBeInTheDocument();
    });
  });

  it('does not auto-select a category when no discipline has any XP', async () => {
    apiEndpoints.player.getSkills.mockResolvedValue({
      data: {
        success: true,
        skills: { skill_tree: { Combat: [] }, skill_exp: { Combat: 0 } },
      },
    });
    render(
      <ToastProvider>
        <SkillsPanel player={mockPlayer} onClose={() => {}} />
      </ToastProvider>
    );

    await waitFor(() => {
      expect(screen.getByText(/⚡ ABILITIES & SKILLS/i)).toBeInTheDocument();
    });
    expect(screen.queryByText(/Available .* XP/i)).not.toBeInTheDocument();
  });

  it('shows the empty-discipline message when the selected category has no skills', async () => {
    apiEndpoints.player.getSkills.mockResolvedValue({
      data: {
        success: true,
        skills: { skill_tree: { Combat: [] }, skill_exp: { Combat: 50 } },
      },
    });
    render(
      <ToastProvider>
        <SkillsPanel player={mockPlayer} onClose={() => {}} />
      </ToastProvider>
    );

    await waitFor(() => {
      expect(screen.getByText(/No skills currently available in this discipline\./i)).toBeInTheDocument();
    });
  });

  it('shows 0 XP when the selected category has no entry in skill_exp after an update', async () => {
    apiEndpoints.player.getSkills.mockResolvedValue({
      data: { success: true, skills: mockSkillsData },
    });
    apiEndpoints.player.learnSkill.mockResolvedValue({
      data: {
        success: true,
        skills: {
          skill_tree: mockSkillsData.skill_tree,
          skill_exp: { Magic: 50 }, // Combat entry removed after spending all XP
        },
      },
    });

    render(
      <ToastProvider>
        <SkillsPanel player={mockPlayer} onClose={() => {}} />
      </ToastProvider>
    );

    await waitFor(() => expect(screen.getByText(/100 XP/i)).toBeInTheDocument());
    fireEvent.click(screen.getByText(/LEARN \(100\)/i));

    await waitFor(() => expect(screen.getByText(/0 XP/i)).toBeInTheDocument());
  });

  it('falls back to a generic message when learnSkill fails without a server error', async () => {
    apiEndpoints.player.getSkills.mockResolvedValue({
      data: { success: true, skills: mockSkillsData },
    });
    const mockError = vi.fn();
    useToast.mockReturnValue({ error: mockError, success: vi.fn(), info: vi.fn(), warning: vi.fn() });
    apiEndpoints.player.learnSkill.mockRejectedValue(new Error('network down'));

    render(
      <ToastProvider>
        <SkillsPanel player={mockPlayer} onClose={() => {}} />
      </ToastProvider>
    );

    await waitFor(() => expect(screen.getByText(/Power Strike/i)).toBeInTheDocument());
    fireEvent.click(screen.getByText(/LEARN \(100\)/i));

    await waitFor(() => {
      expect(mockError).toHaveBeenCalledWith('Failed to learn skill');
    });
  });
});
