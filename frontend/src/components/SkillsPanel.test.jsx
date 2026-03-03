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
    apiEndpoints.player.getSkills.mockReturnValue(new Promise(() => { })); // Never resolves
    render(
      <ToastProvider>
        <SkillsPanel player={mockPlayer} onClose={() => { }} />
      </ToastProvider>
    );
    expect(screen.getByText(/Accessing ancient scrolls/i)).toBeDefined();
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
      expect(screen.getByText(/⚡ ABILITIES & SKILLS/i)).toBeDefined();
      expect(screen.getByText(/100 XP/i)).toBeDefined();
    });

    // Check categories
    expect(screen.getAllByText(/Combat/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Magic/i).length).toBeGreaterThan(0);


    // Check skills in default category (Combat)
    expect(screen.getByText(/Power Strike/i)).toBeDefined();
    expect(screen.getByText(/A powerful melee attack./i)).toBeDefined();
    expect(screen.getByText(/LEARN \(100\)/i)).toBeDefined();
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


    fireEvent.click(screen.getByText(/Magic/i));

    expect(screen.getByText(/Fireball/i)).toBeDefined();
    expect(screen.getByText(/Shoot a ball of fire./i)).toBeDefined();
    expect(screen.getByText(/✓ Learned/i)).toBeDefined();
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

    expect(apiEndpoints.player.learnSkill).toHaveBeenCalledWith('Power Strike', 'Combat');

    await waitFor(() => {
      expect(screen.getAllByText(/✓ Learned/i).length).toBeGreaterThan(0);
    });
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
    expect(mockOnClose).toHaveBeenCalled();
  });
});
