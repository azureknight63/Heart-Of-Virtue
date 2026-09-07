import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import LevelUpModal from './LevelUpModal'

/**
 * LevelUpModal.test.jsx mocks BaseDialog wholesale (a plain <div><h2>title</h2>
 * ...) to isolate LevelUpModal's own logic, so it cannot verify BaseDialog's
 * real aria-labelledby wiring. This file renders the REAL component tree —
 * a separate test file gets a separate module registry, so LevelUpModal.test.jsx's
 * `vi.mock('./BaseDialog', ...)` never reaches here — to verify (not assume)
 * the QA report's claim that the LEVEL UP dialog reads as a bare, unnamed
 * `dialog` role. BaseDialog already wires aria-labelledby whenever it
 * receives a truthy `title`, and LevelUpModal always passes one
 * ("⭐ LEVEL UP"), so this is expected to already pass — see
 * BaseDialog.test.jsx for the underlying mechanism's own coverage.
 */
vi.mock('../context/AudioContext', () => ({
  useAudio: () => ({ playSFX: vi.fn() }),
}))

describe('LevelUpModal (real BaseDialog integration)', () => {
  it('gives the dialog an accessible name (issue #536)', () => {
    render(
      <LevelUpModal
        player={{ pending_attribute_points: 3, pending_level_ups: [] }}
        onAllocatePoints={vi.fn()}
      />
    )
    expect(screen.getByRole('dialog', { name: '⭐ LEVEL UP' })).toBeInTheDocument()
  })
})
