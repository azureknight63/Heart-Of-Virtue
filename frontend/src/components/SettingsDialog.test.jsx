import { render, screen, fireEvent, within } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import SettingsDialog from './SettingsDialog';
import { usePreferences } from '../context/PreferencesContext';
import { FEATURE_FLAGS, getFlag, resetFlags } from '../utils/featureFlags';
import { accessibility } from '../styles/theme';

vi.mock('../context/PreferencesContext', () => ({
  usePreferences: vi.fn()
}));

const mobileMock = vi.hoisted(() => ({ isMobile: false }));
vi.mock('../hooks/useMobile', () => ({ useMobile: () => mobileMock.isMobile }));

describe('SettingsDialog', () => {
  const mockSetMusicVolume = vi.fn();
  const mockSetSfxVolume = vi.fn();
  const mockSetIsMusicMuted = vi.fn();
  const mockSetIsSfxMuted = vi.fn();
  const mockSetCombatSpeed = vi.fn();
  const mockSetTextSpeed = vi.fn();
  const mockSetAutoAdvance = vi.fn();
  const mockOnClose = vi.fn();

  const mockPreferences = {
    musicVolume: 0.5,
    setMusicVolume: mockSetMusicVolume,
    sfxVolume: 0.7,
    setSfxVolume: mockSetSfxVolume,
    isMusicMuted: false,
    setIsMusicMuted: mockSetIsMusicMuted,
    isSfxMuted: false,
    setIsSfxMuted: mockSetIsSfxMuted,
    combatSpeed: 1,
    setCombatSpeed: mockSetCombatSpeed,
    textSpeed: 1,
    setTextSpeed: mockSetTextSpeed,
    autoAdvance: false,
    setAutoAdvance: mockSetAutoAdvance
  };

  beforeEach(() => {
    vi.clearAllMocks();
    usePreferences.mockReturnValue(mockPreferences);
    mobileMock.isMobile = false;
  });

  // Issue #538 item 1: Settings had music, SFX, combat speed and two
  // experimental toggles -- and nothing at all for text, in a game whose
  // primary delivery vehicle is text.
  describe('text pacing controls (issue #538)', () => {
    it('renders a TEXT SPEED row with the current step pressed', () => {
      render(<SettingsDialog onClose={mockOnClose} />);

      expect(screen.getByText('TEXT SPEED')).toBeDefined();
      expect(screen.getByRole('button', { name: 'NORMAL' }).getAttribute('aria-pressed')).toBe('true');
      expect(screen.getByRole('button', { name: 'FAST' }).getAttribute('aria-pressed')).toBe('false');
    });

    it('offers an INSTANT end-stop', () => {
      render(<SettingsDialog onClose={mockOnClose} />);
      fireEvent.click(screen.getByRole('button', { name: 'INSTANT' }));
      expect(mockSetTextSpeed).toHaveBeenCalledWith(0);
    });

    it('sets the text speed when a step is clicked', () => {
      render(<SettingsDialog onClose={mockOnClose} />);
      fireEvent.click(screen.getByRole('button', { name: 'FAST' }));
      expect(mockSetTextSpeed).toHaveBeenCalledWith(2);
    });

    it('does not reuse the combat-speed labels beside it', () => {
      // Two adjacent rows of "0.5x / 1x / 2x" buttons are ambiguous to a
      // reader and unresolvable to a screen reader.
      render(<SettingsDialog onClose={mockOnClose} />);
      expect(screen.getAllByRole('button', { name: '1x' })).toHaveLength(1);
      expect(screen.getAllByRole('button', { name: '2x' })).toHaveLength(1);
    });

    it('renders auto-advance off by default and toggles it on', () => {
      render(<SettingsDialog onClose={mockOnClose} />);
      const toggle = screen.getByRole('button', { name: 'Auto-advance story' });
      expect(toggle.getAttribute('aria-pressed')).toBe('false');
      expect(toggle.textContent).toBe('OFF');

      fireEvent.click(toggle);
      expect(mockSetAutoAdvance).toHaveBeenCalledWith(true);
    });

    it('reflects auto-advance already being on', () => {
      usePreferences.mockReturnValue({ ...mockPreferences, autoAdvance: true });
      render(<SettingsDialog onClose={mockOnClose} />);

      const toggle = screen.getByRole('button', { name: 'Auto-advance story', pressed: true });
      expect(toggle.textContent).toBe('ON');
      fireEvent.click(toggle);
      expect(mockSetAutoAdvance).toHaveBeenCalledWith(false);
    });

    it('grows the text-speed segments to the touch-target minimum on mobile', () => {
      mobileMock.isMobile = true;
      render(<SettingsDialog onClose={mockOnClose} />);
      expect(screen.getByRole('button', { name: 'INSTANT' }).style.minHeight)
        .toBe(accessibility.touchTarget);
    });
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
    usePreferences.mockReturnValue({
      ...mockPreferences,
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
    const closeBtn = screen.getByText('CLOSE');
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

  describe('mobile touch targets (issue #542)', () => {
    // `getAllByText('ON')` also matches the "beatTimeline" experimental flag
    // toggle (default: true, see utils/featureFlags.js) — that control is
    // out of scope for this issue, so only check the first two matches
    // (MUSIC then SFX, by DOM order), same as the existing mute-toggle tests
    // above index into this same query.
    const muteToggles = () => screen.getAllByText('ON').slice(0, 2);

    it('grows the MUSIC and SFX mute toggles to 44px on mobile', () => {
      mobileMock.isMobile = true;
      render(<SettingsDialog onClose={mockOnClose} />);

      muteToggles().forEach((toggle) => {
        expect(toggle.style.minWidth).toBe(accessibility.touchTarget);
        expect(toggle.style.minHeight).toBe(accessibility.touchTarget);
      });
    });

    it('grows each combat-speed segment to 44px tall on mobile', () => {
      mobileMock.isMobile = true;
      render(<SettingsDialog onClose={mockOnClose} />);

      expect(screen.getByText('1x').style.minHeight).toBe(accessibility.touchTarget);
      expect(screen.getByText('0.5x').style.minHeight).toBe(accessibility.touchTarget);
    });

    it('leaves the toggles and segments at their native size on desktop', () => {
      render(<SettingsDialog onClose={mockOnClose} />);

      muteToggles().forEach((toggle) => {
        expect(toggle.style.minWidth).toBe('');
      });
      expect(screen.getByText('1x').style.minHeight).toBe('');
    });
  });

  describe('experimental feature flags', () => {
    afterEach(() => {
      resetFlags();
    });

    it('renders a row for every registered flag, driven by the registry', () => {
      render(<SettingsDialog onClose={mockOnClose} />);

      const names = Object.keys(FEATURE_FLAGS);
      expect(names.length).toBeGreaterThan(0);
      for (const name of names) {
        expect(screen.getByText(FEATURE_FLAGS[name].label)).toBeInTheDocument();
      }
    });

    it('toggles a flag on and back off, reflecting the live value', () => {
      render(<SettingsDialog onClose={mockOnClose} />);
      const label = FEATURE_FLAGS.squareBattlefieldCells.label;
      const row = screen.getByText(label).parentElement;
      const toggle = within(row).getByRole('button');

      expect(toggle).toHaveTextContent('OFF');
      expect(toggle.getAttribute('aria-pressed')).toBe('false');

      fireEvent.click(toggle);
      expect(getFlag('squareBattlefieldCells')).toBe(true);
      expect(toggle).toHaveTextContent('ON');
      expect(toggle.getAttribute('aria-pressed')).toBe('true');

      fireEvent.click(toggle);
      expect(getFlag('squareBattlefieldCells')).toBe(false);
      expect(toggle).toHaveTextContent('OFF');
    });
  });

});
