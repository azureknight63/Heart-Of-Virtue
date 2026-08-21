import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import SettingsDialog from './SettingsDialog';
import { useAudio } from '../context/AudioContext';

// Mock useAudio
vi.mock('../context/AudioContext', () => ({
  useAudio: vi.fn()
}));

describe('SettingsDialog', () => {
  const mockSetMusicVolume = vi.fn();
  const mockSetSfxVolume = vi.fn();
  const mockSetIsMusicMuted = vi.fn();
  const mockSetIsSfxMuted = vi.fn();
  const mockSetCombatSpeed = vi.fn();
  const mockOnClose = vi.fn();

  const mockAudioContext = {
    musicVolume: 0.5,
    setMusicVolume: mockSetMusicVolume,
    sfxVolume: 0.7,
    setSfxVolume: mockSetSfxVolume,
    isMusicMuted: false,
    setIsMusicMuted: mockSetIsMusicMuted,
    isSfxMuted: false,
    setIsSfxMuted: mockSetIsSfxMuted,
    combatSpeed: 1,
    setCombatSpeed: mockSetCombatSpeed
  };

  beforeEach(() => {
    vi.clearAllMocks();
    useAudio.mockReturnValue(mockAudioContext);
  });

  it('renders audio settings correctly', () => {
    render(<SettingsDialog onClose={mockOnClose} />);

    expect(screen.getByText('⚙️ SETTINGS')).toBeDefined();
    expect(screen.getByText('MUSIC')).toBeDefined();
    expect(screen.getByText('SOUND EFFECTS')).toBeDefined();
    expect(screen.getByText('50%')).toBeDefined();
    expect(screen.getByText('70%')).toBeDefined();
  });

  it('handles music volume change', () => {
    render(<SettingsDialog onClose={mockOnClose} />);
    const sliders = screen.getAllByRole('slider');
    const musicSlider = sliders[0];

    fireEvent.change(musicSlider, { target: { value: '0.8' } });
    expect(mockSetMusicVolume).toHaveBeenCalledWith(0.8);
  });

  it('handles sfx volume change', () => {
    render(<SettingsDialog onClose={mockOnClose} />);
    const sliders = screen.getAllByRole('slider');
    const sfxSlider = sliders[1];

    fireEvent.change(sfxSlider, { target: { value: '0.3' } });
    expect(mockSetSfxVolume).toHaveBeenCalledWith(0.3);
  });

  it('handles music mute toggle', () => {
    render(<SettingsDialog onClose={mockOnClose} />);
    const muteBtns = screen.getAllByText('ON');
    const musicMuteBtn = muteBtns[0];

    fireEvent.click(musicMuteBtn);
    expect(mockSetIsMusicMuted).toHaveBeenCalledWith(true);
  });

  it('handles sfx mute toggle', () => {
    render(<SettingsDialog onClose={mockOnClose} />);
    const muteBtns = screen.getAllByText('ON');
    const sfxMuteBtn = muteBtns[1];

    fireEvent.click(sfxMuteBtn);
    expect(mockSetIsSfxMuted).toHaveBeenCalledWith(true);
  });

  it('renders muted state correctly', () => {
    useAudio.mockReturnValue({
      ...mockAudioContext,
      isMusicMuted: true,
      isSfxMuted: true
    });

    render(<SettingsDialog onClose={mockOnClose} />);

    const mutedBtns = screen.getAllByText('MUTED');
    expect(mutedBtns.length).toBe(2);

    const sliders = screen.getAllByRole('slider');
    expect(sliders[0].disabled).toBe(true);
    expect(sliders[1].disabled).toBe(true);
  });

  it('calls onClose when Close button is clicked', () => {
    render(<SettingsDialog onClose={mockOnClose} />);
    const closeBtn = screen.getByText('Close');
    fireEvent.click(closeBtn);
    expect(mockOnClose).toHaveBeenCalledTimes(1);
  });

  it('renders the combat speed control with the current step active', () => {
    render(<SettingsDialog onClose={mockOnClose} />);

    expect(screen.getByText('COMBAT SPEED')).toBeDefined();
    const activeBtn = screen.getByText('1x');
    expect(activeBtn.getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByText('0.5x').getAttribute('aria-pressed')).toBe('false');
  });

  it('sets combat speed when a step is clicked', () => {
    render(<SettingsDialog onClose={mockOnClose} />);

    fireEvent.click(screen.getByText('2x'));
    expect(mockSetCombatSpeed).toHaveBeenCalledWith(2);
  });

  it('closes when clicking the overlay', () => {
    const { container } = render(<SettingsDialog onClose={mockOnClose} />);
    const overlay = container.firstChild;
    fireEvent.click(overlay);
    expect(mockOnClose).toHaveBeenCalledTimes(1);
  });

  it('does not close when clicking the dialog content', () => {
    render(<SettingsDialog onClose={mockOnClose} />);
    const dialogContent = screen.getByText('⚙️ SETTINGS').parentElement;
    fireEvent.click(dialogContent);
    expect(mockOnClose).not.toHaveBeenCalled();
  });

});
