import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import WeaponSwapPanel, { NO_WEAPON_TO_SWAP_REASON, NOT_YOUR_TURN_REASON } from './WeaponSwapPanel';
import { makeAvailableOption } from '../test/payloads';
import { accessibility } from '../styles/theme';

// The engine's SwapWeapon card: SWAP_WEAPON_STAGE_BEATS is (1, 1, 1, 0) and it
// costs no fatigue (src/moves/_utility.py). `weapon_options` is the list
// ApiCombatAdapter._get_available_moves publishes for this move only.
const swapMove = (overrides = {}) => makeAvailableOption({
  id: '5',
  name: 'Swap Weapon',
  category: 'Utility',
  targeted: false,
  fatigue_cost: 0,
  stage_beats: { prep: 1, execute: 1, recoil: 1, cooldown: 0 },
  weapon_options: [
    { id: 'w-sword', name: 'Shortsword' },
    { id: 'w-bow', name: 'Shortbow' },
  ],
  ...overrides,
});

describe('WeaponSwapPanel', () => {
  it('states the full beat cost before the player commits', () => {
    render(<WeaponSwapPanel swapMove={swapMove()} canAct onSwap={vi.fn()} />);
    const cost = screen.getByTestId('weapon-swap-cost');
    expect(cost.textContent).toContain('3 beats');
    expect(cost.textContent).toContain('Prep 1');
    expect(cost.textContent).toContain('Execute 1');
    expect(cost.textContent).toContain('Recoil 1');
  });

  it('says plainly that the swap costs no fatigue and has no cooldown', () => {
    render(<WeaponSwapPanel swapMove={swapMove()} canAct onSwap={vi.fn()} />);
    const cost = screen.getByTestId('weapon-swap-cost');
    expect(cost.textContent).toContain('No fatigue');
    expect(cost.textContent).toContain('No cooldown');
  });

  it('shows a real cooldown and fatigue cost when the engine declares them', () => {
    render(
      <WeaponSwapPanel
        swapMove={swapMove({ fatigue_cost: 5, stage_beats: { prep: 1, execute: 1, recoil: 1, cooldown: 2 } })}
        canAct
        onSwap={vi.fn()}
      />
    );
    const cost = screen.getByTestId('weapon-swap-cost');
    expect(cost.textContent).toContain('5 fatigue');
    expect(cost.textContent).toContain('2 beats cooldown');
    expect(cost.textContent).toContain('5 beats');
  });

  it('lists exactly the weapons the engine offers and submits the picked one', () => {
    const onSwap = vi.fn();
    render(<WeaponSwapPanel swapMove={swapMove()} canAct onSwap={onSwap} />);
    const buttons = screen.getAllByRole('button', { name: /^Draw / });
    expect(buttons.map((b) => b.textContent)).toEqual([
      expect.stringContaining('Shortsword'),
      expect.stringContaining('Shortbow'),
    ]);
    fireEvent.click(screen.getByRole('button', { name: /Draw Shortbow/ }));
    expect(onSwap).toHaveBeenCalledWith('w-bow');
  });

  it('gives every draw button a 44px touch target', () => {
    render(<WeaponSwapPanel swapMove={swapMove()} canAct onSwap={vi.fn()} />);
    for (const button of screen.getAllByRole('button', { name: /^Draw / })) {
      expect(button.style.minHeight).toBe(accessibility.touchTarget);
    }
  });

  it('names the equipped weapon so the player knows what they are trading away', () => {
    render(<WeaponSwapPanel swapMove={swapMove()} equippedName="Dagger" canAct onSwap={vi.fn()} />);
    expect(screen.getByText(/In hand:/).textContent).toContain('Dagger');
  });

  it('explains, in words, why nothing can be drawn when the pack holds no other weapon', () => {
    const onSwap = vi.fn();
    render(
      <WeaponSwapPanel
        swapMove={swapMove({ available: false, reason: 'Cannot use this move', weapon_options: [] })}
        canAct
        onSwap={onSwap}
      />
    );
    expect(screen.getByRole('status').textContent).toContain(NO_WEAPON_TO_SWAP_REASON);
    expect(screen.queryAllByRole('button', { name: /^Draw / })).toHaveLength(0);
  });

  it('disables the draw buttons off-turn and says why', () => {
    const onSwap = vi.fn();
    render(<WeaponSwapPanel swapMove={swapMove()} canAct={false} onSwap={onSwap} />);
    expect(screen.getByRole('status').textContent).toContain(NOT_YOUR_TURN_REASON);
    const button = screen.getByRole('button', { name: /Draw Shortsword/ });
    expect(button).toBeDisabled();
    fireEvent.click(button);
    expect(onSwap).not.toHaveBeenCalled();
  });

  it("surfaces the engine's own reason when the move is unavailable for another cause", () => {
    render(
      <WeaponSwapPanel
        swapMove={swapMove({ available: false, reason: 'Available in 2 beats', cooldown_remaining: 2 })}
        canAct
        onSwap={vi.fn()}
      />
    );
    expect(screen.getByRole('status').textContent).toContain('Available in 2 beats');
    expect(screen.getByRole('button', { name: /Draw Shortsword/ })).toBeDisabled();
  });

  it('falls back to a generic reason when an unavailable move ships none', () => {
    render(<WeaponSwapPanel swapMove={swapMove({ available: false, reason: null })} canAct onSwap={vi.fn()} />);
    expect(screen.getByRole('status').textContent).toMatch(/not available/i);
  });

  it('treats a card with no weapon_options as having nothing to draw', () => {
    render(<WeaponSwapPanel swapMove={swapMove({ weapon_options: undefined })} canAct onSwap={vi.fn()} />);
    expect(screen.getByRole('status').textContent).toContain(NO_WEAPON_TO_SWAP_REASON);
  });
});
