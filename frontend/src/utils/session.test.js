import { describe, it, expect, vi, afterEach } from 'vitest'
import {
  AUTH_TOKEN_KEY,
  USERNAME_KEY,
  SESSION_KEYS,
  clearLocalSession,
} from './session'

describe('SESSION_KEYS', () => {
  it('covers every key that constitutes a signed-in session', () => {
    // The set is the invariant, not the individual removals: a teardown path
    // that misses one strands a dead credential or leaks the prior account's
    // username to the next user on a shared machine.
    expect(SESSION_KEYS).toEqual([AUTH_TOKEN_KEY, USERNAME_KEY])
  })
})

describe('clearLocalSession', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('removes every session key', () => {
    const storage = { removeItem: vi.fn() }
    clearLocalSession(storage)
    expect(storage.removeItem.mock.calls.map(([k]) => k)).toEqual(SESSION_KEYS)
  })

  it('defaults to localStorage when no storage is passed', () => {
    // Both call sites (AuthContext.logout and the 401 interceptor) rely on the
    // default, so the parameterised form must not be the only tested path.
    const removeItem = vi.fn()
    vi.stubGlobal('localStorage', { removeItem })
    clearLocalSession()
    expect(removeItem.mock.calls.map(([k]) => k)).toEqual(SESSION_KEYS)
  })

  it('keeps clearing the remaining keys when one removal throws', () => {
    // Storage can throw for reasons that have nothing to do with the session
    // (Safari private mode, quota, a disabled-storage policy). Giving up on
    // the first failure would leave later keys behind.
    const removeItem = vi.fn((key) => {
      if (key === AUTH_TOKEN_KEY) throw new Error('storage disabled')
    })
    const storage = { removeItem }

    expect(() => clearLocalSession(storage)).not.toThrow()
    expect(removeItem.mock.calls.map(([k]) => k)).toEqual(SESSION_KEYS)
  })

  it('never propagates a storage failure to the caller', () => {
    // A failed cleanup must not stop a sign-out from completing and redirecting.
    const storage = {
      removeItem: () => {
        throw new Error('nope')
      },
    }
    expect(() => clearLocalSession(storage)).not.toThrow()
  })
})
