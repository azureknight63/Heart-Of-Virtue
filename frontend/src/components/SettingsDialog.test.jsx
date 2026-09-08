import { render, screen, fireEvent, within } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import SettingsDialog from './SettingsDialog';
import { useAudio } from '../context/AudioContext';
import { FEATURE_FLAGS, getFlag, resetFlags } from '../utils/featureFlags';
import { accessibility } from '../styles/theme';

// Mock useAudio
vi.mock('../context/AudioContext', () => ({
  useAudio: vi.fn()
}));

const mobileMock = vi.hoisted(() => ({ isMobile: false }));
vi.mock('../hooks/useMobile', () => ({ useMobile: () => mobileMock.isMobile }));

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
    mobileMock.isMobile = false;
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

  /**
   * Issue #563 item 2 — nothing in this dialog had an accessible name. The
   * file held no `id`, no `<label>`, no `aria-label`, no `aria-labelledby` and
   * no `title`, so the two sliders announced as bare "slider, 0.5" and the two
   * mute toggles announced as "ON" — the same name, twice, on one screen.
   *
   * `aria-label` rather than `htmlFor`: each MUSIC / SOUND EFFECTS heading
   * heads BOTH the mute button and the slider beneath it, so associating the
   * heading with the slider alone would announce the slider as "MUSIC" while
   * the button beside it stayed "ON". It is also this codebase's idiom.
   */
  describe('accessible names', () => {
    /**
     * An element's accessible name, computed the way a reader would resolve
     * it. Deliberately not `textContent`: the whole failure being guarded is
     * a control whose visible text is not its name (a slider has none at all,
     * and two buttons share the word "ON").
     */
    const accessibleName = (el) => {
      const label = el.getAttribute('aria-label');
      if (label) return label.trim();
      const ids = el.getAttribute('aria-labelledby');
      if (ids) {
        return ids
          .split(/\s+/)
          .map((id) => el.ownerDocument.getElementById(id)?.textContent ?? '')
          .join(' ')
          .trim();
      }
      return (el.getAttribute('title') || el.textContent || '').trim();
    };

    it('names both volume sliders', () => {
      render(<SettingsDialog onClose={mockOnClose} />);

      expect(screen.getByRole('slider', { name: 'Music volume' })).toBeInTheDocument();
      expect(screen.getByRole('slider', { name: 'Sound effects volume' })).toBeInTheDocument();
    });

    it('keeps the sliders in their existing order under the new names', () => {
      // The order the rest of this file indexes by. Naming them must not
      // reshuffle them, or every getAllByRole('slider')[n] above moves.
      render(<SettingsDialog onClose={mockOnClose} />);

      const names = screen.getAllByRole('slider').map(accessibleName);
      expect(names).toEqual(['Music volume', 'Sound effects volume']);
    });

    it('distinguishes the two mute toggles and exposes their pressed state', () => {
      // Both read "ON" before this. aria-pressed matches what the
      // combat-speed segments and the flag rows already do.
      render(<SettingsDialog onClose={mockOnClose} />);

      const music = screen.getByRole('button', { name: 'Mute music' });
      const sfx = screen.getByRole('button', { name: 'Mute sound effects' });
      expect(music.getAttribute('aria-pressed')).toBe('false');
      expect(sfx.getAttribute('aria-pressed')).toBe('false');

      fireEvent.click(music);
      expect(mockSetIsMusicMuted).toHaveBeenCalledWith(true);
      fireEvent.click(sfx);
      expect(mockSetIsSfxMuted).toHaveBeenCalledWith(true);
    });

    it('reports the pressed state of a muted toggle', () => {
      useAudio.mockReturnValue({ ...mockAudioContext, isMusicMuted: true, isSfxMuted: true });
      render(<SettingsDialog onClose={mockOnClose} />);

      expect(screen.getByRole('button', { name: 'Mute music' }).getAttribute('aria-pressed')).toBe('true');
      expect(screen.getByRole('button', { name: 'Mute sound effects' }).getAttribute('aria-pressed')).toBe('true');
    });

    it('names every feature-flag toggle after its flag', () => {
      // Three identically-named ON/OFF buttons, with the only distinguishing
      // text in an unassociated sibling div. Driven from the registry so a
      // new flag is covered the day it is added.
      render(<SettingsDialog onClose={mockOnClose} />);

      const names = Object.values(FEATURE_FLAGS).map((flag) => flag.label);
      expect(names.length).toBeGreaterThan(1);
      for (const label of names) {
        expect(screen.getByRole('button', { name: label })).toBeInTheDocument();
      }
    });

    it('groups the combat-speed segments under their heading', () => {
      // The segments are named ("1x", "0.5x") but say nothing about what they
      // set; the COMBAT SPEED heading above them was unassociated.
      render(<SettingsDialog onClose={mockOnClose} />);

      const group = screen.getByRole('group', { name: 'Combat speed' });
      expect(within(group).getByText('1x')).toBeInTheDocument();
    });

    it('leaves no interactive control unnamed', () => {
      // The sweep, so a control added later cannot ship nameless. #536 got
      // exploration and combat to zero unnamed of 21 and 14 elements; this
      // dialog was never measured.
      const { container } = render(<SettingsDialog onClose={mockOnClose} />);

      const controls = [...container.querySelectorAll('button, input, select, textarea, a[href]')];
      expect(controls.length).toBeGreaterThan(5);
      const unnamed = controls.filter((el) => accessibleName(el) === '');
      expect(
        unnamed.map((el) => `${el.tagName}${el.type ? `[type=${el.type}]` : ''}`),
        'these controls in SettingsDialog have an empty accessible name'
      ).toEqual([]);
    });
  });

});
