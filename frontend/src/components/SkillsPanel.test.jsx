import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import SkillsPanel from './SkillsPanel';
import apiEndpoints from '../api/endpoints';

// Mock apiEndpoints
vi.mock('../api/endpoints', () => ({
  default: {
    player: {
      getSkills: vi.fn(),
      learnSkill: vi.fn(),
    },
  },
}));

describe('SkillsPanel', () => {
  const mockPlayer = {
    name: 'Hero',
    skill_points: 5,
  };

  const mockSkillsData = {
    skill_tree: {
      Combat: [
        {
          name: 'Power Strike',
          description: 'A powerful melee attack.',
          required_exp: 100,
          is_known: false,
          can_learn: true,
        },
        {
          name: 'Cleave',
          description: 'Hit multiple enemies.',
          required_exp: 200,
          is_known: false,
          can_learn: false,
        },
      ],
      Magic: [
        {
          name: 'Fireball',
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
    apiEndpoints.player.getSkills.mockReturnValue(new Promise(() => {})); // Never resolves
    render(<SkillsPanel player={mockPlayer} onClose={() => {}} />);
    expect(screen.getByText(/Loading skills.../i)).toBeDefined();
  });

  it('renders error state if fetch fails', async () => {
    apiEndpoints.player.getSkills.mockRejectedValue(new Error('Fetch failed'));
    render(<SkillsPanel player={mockPlayer} onClose={() => {}} />);
    
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

    render(<SkillsPanel player={mockPlayer} onClose={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText(/⚡ SKILLS/i)).toBeDefined();
      expect(screen.getByText(/EXP: 100/i)).toBeDefined();
    });

    // Check categories
    expect(screen.getByText(/Combat/i)).toBeDefined();
    expect(screen.getByText(/Magic/i)).toBeDefined();

    // Check skills in default category (Combat)
    expect(screen.getByText(/Power Strike/i)).toBeDefined();
    expect(screen.getByText(/A powerful melee attack./i)).toBeDefined();
    expect(screen.getByText(/LEARN \(100 XP\)/i)).toBeDefined();
  });

  it('switches categories when clicked', async () => {
    apiEndpoints.player.getSkills.mockResolvedValue({
      data: {
        success: true,
        skills: mockSkillsData,
      },
    });

    render(<SkillsPanel player={mockPlayer} onClose={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText(/Combat/i)).toBeDefined();
    });

    fireEvent.click(screen.getByText(/Magic/i));

    expect(screen.getByText(/Fireball/i)).toBeDefined();
    expect(screen.getByText(/Shoot a ball of fire./i)).toBeDefined();
    expect(screen.getByText(/\(LEARNED\)/i)).toBeDefined();
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

    render(<SkillsPanel player={mockPlayer} onClose={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText(/Power Strike/i)).toBeDefined();
    });

    const learnButton = screen.getByText(/LEARN \(100 XP\)/i);
    fireEvent.click(learnButton);

    expect(apiEndpoints.player.learnSkill).toHaveBeenCalledWith('Power Strike', 'Combat');

    await waitFor(() => {
      expect(screen.getAllByText(/\(LEARNED\)/i).length).toBeGreaterThan(0);
    });
  });

  it('handles learnSkill error', async () => {
    apiEndpoints.player.getSkills.mockResolvedValue({
      data: {
        success: true,
        skills: mockSkillsData,
      },
    });

    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});
    
    apiEndpoints.player.learnSkill.mockRejectedValue({
      response: {
        data: {
          error: 'Not enough skill points',
        },
      },
    });

    render(<SkillsPanel player={mockPlayer} onClose={() => {}} />);

    await waitFor(() => {
      expect(screen.getByText(/Power Strike/i)).toBeDefined();
    });

    fireEvent.click(screen.getByText(/LEARN \(100 XP\)/i));

    await waitFor(() => {
      expect(alertSpy).toHaveBeenCalledWith('Not enough skill points');
    });

    consoleSpy.mockRestore();
    alertSpy.mockRestore();
  });

  it('calls onClose when close button is clicked', async () => {
    apiEndpoints.player.getSkills.mockResolvedValue({
      data: {
        success: true,
        skills: mockSkillsData,
      },
    });

    const mockOnClose = vi.fn();
    render(<SkillsPanel player={mockPlayer} onClose={mockOnClose} />);

    await waitFor(() => {
      expect(screen.getByText(/✕/i)).toBeDefined();
    });

    fireEvent.click(screen.getByText(/✕/i));
    expect(mockOnClose).toHaveBeenCalled();
  });
});
