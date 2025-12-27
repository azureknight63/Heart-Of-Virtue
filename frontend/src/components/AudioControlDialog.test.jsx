import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import AudioControlDialog from './AudioControlDialog';
import { useAudio } from '../context/AudioContext';

// Mock useAudio
vi.mock('../context/AudioContext', () => ({
  useAudio: vi.fn()
}));

describe('AudioControlDialog', () => {
  const mockSetMusicVolume = vi.fn();
  const mockSetSfxVolume = vi.fn();
  const mockSetIsMusicMuted = vi.fn();
  const mockSetIsSfxMuted = vi.fn();
  const mockOnClose = vi.fn();

  const mockAudioContext = {
    musicVolume: 0.5,
    setMusicVolume: mockSetMusicVolume,
    sfxVolume: 0.7,
    setSfxVolume: mockSetSfxVolume,
    isMusicMuted: false,
    setIsMusicMuted: mockSetIsMusicMuted,
    isSfxMuted: false,
    setIsSfxMuted: mockSetIsSfxMuted
  };

  beforeEach(() => {
    vi.clearAllMocks();
    useAudio.mockReturnValue(mockAudioContext);
  });

  it('renders audio settings correctly', () => {
    render(<AudioControlDialog onClose={mockOnClose} />);

    expect(screen.getByText('🔊 Audio Settings')).toBeDefined();
    expect(screen.getByText('MUSIC')).toBeDefined();
    expect(screen.getByText('SOUND EFFECTS')).toBeDefined();
    expect(screen.getByText('50%')).toBeDefined();
    expect(screen.getByText('70%')).toBeDefined();
  });

  it('handles music volume change', () => {
    render(<AudioControlDialog onClose={mockOnClose} />);
    const sliders = screen.getAllByRole('slider');
    const musicSlider = sliders[0];

    fireEvent.change(musicSlider, { target: { value: '0.8' } });
    expect(mockSetMusicVolume).toHaveBeenCalledWith(0.8);
  });

  it('handles sfx volume change', () => {
    render(<AudioControlDialog onClose={mockOnClose} />);
    const sliders = screen.getAllByRole('slider');
    const sfxSlider = sliders[1];

    fireEvent.change(sfxSlider, { target: { value: '0.3' } });
    expect(mockSetSfxVolume).toHaveBeenCalledWith(0.3);
  });

  it('handles music mute toggle', () => {
    render(<AudioControlDialog onClose={mockOnClose} />);
    const muteBtns = screen.getAllByText('ON');
    const musicMuteBtn = muteBtns[0];

    fireEvent.click(musicMuteBtn);
    expect(mockSetIsMusicMuted).toHaveBeenCalledWith(true);
  });

  it('handles sfx mute toggle', () => {
    render(<AudioControlDialog onClose={mockOnClose} />);
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

    render(<AudioControlDialog onClose={mockOnClose} />);
    
    const mutedBtns = screen.getAllByText('MUTED');
    expect(mutedBtns.length).toBe(2);

    const sliders = screen.getAllByRole('slider');
    expect(sliders[0].disabled).toBe(true);
    expect(sliders[1].disabled).toBe(true);
  });

  it('calls onClose when Close button is clicked', () => {
    render(<AudioControlDialog onClose={mockOnClose} />);
    const closeBtn = screen.getByText('Close');
    fireEvent.click(closeBtn);
    expect(mockOnClose).toHaveBeenCalled();
  });

  it('closes when clicking the overlay', () => {
    const { container } = render(<AudioControlDialog onClose={mockOnClose} />);
    const overlay = container.firstChild;
    fireEvent.click(overlay);
    expect(mockOnClose).toHaveBeenCalled();
  });

  it('does not close when clicking the dialog content', () => {
    render(<AudioControlDialog onClose={mockOnClose} />);
    const dialogContent = screen.getByText('🔊 Audio Settings').parentElement;
    fireEvent.click(dialogContent);
    expect(mockOnClose).not.toHaveBeenCalled();
  });

  it('handles hover effects on close button', () => {
    render(<AudioControlDialog onClose={mockOnClose} />);
    const closeBtn = screen.getByText('Close');
    
    fireEvent.mouseEnter(closeBtn);
    expect(closeBtn.style.backgroundColor).toBe('rgba(0, 204, 255, 0.2)');
    
    fireEvent.mouseLeave(closeBtn);
    expect(closeBtn.style.backgroundColor).toBe('transparent');
  });
});
