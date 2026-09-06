import { describe, it, expect, vi, afterEach } from 'vitest'
import { readSourceFiles } from '../test/sourceAudit'
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


describe('every session key lives in utils/session.js', () => {
    /**
     * The set of localStorage keys is the invariant, and this module says so:
     * "every teardown path has to clear all of it". It named two callers --
     * `AuthContext.logout()` and the axios 401 interceptor -- and there were
     * THREE. `GamePage`'s `onSessionInvalid` carried its own hand-written key
     * list, and `AccountDialog` read `'username'` inline.
     *
     * Nothing leaked, because the lists happened to agree. The failure this
     * module exists to prevent is a fourth session-scoped key updating two
     * paths and not the third, where the miss strands a credential or hands
     * the prior account's identifier to the next user of a shared machine.
     *
     * `SESSION_KEYS` and `clearLocalSession` were already asserted. What was
     * not asserted is that everybody GOES THROUGH them -- so that is what this
     * scans for, over the whole shipped tree, with no registration and no
     * exemption list.
     */
    const OWNER = 'utils/session.js'

    // `readSourceFiles` already excludes test files and the test/
    // directory, so this is the shipped tree as it stands.
    const shipped = readSourceFiles()

    it('reads a real corpus', () => {
        // Non-vacuity: a scan over nothing finds no offenders.
        expect(shipped.length).toBeGreaterThan(100)
    })

    it('owns the literals it declares', () => {
        // The control on the scan below: if the owner ever stopped spelling
        // them, the ban would pass by describing an empty world.
        const owner = shipped.find((file) => file.path.endsWith(OWNER))
        expect(owner, `${OWNER} not found in the corpus`).toBeTruthy()
        expect(owner.content).toContain("'authToken'")
        expect(owner.content).toContain("'username'")
    })

    it('is the only module that spells them', () => {
        const offenders = []
        for (const file of shipped) {
            if (file.path.endsWith(OWNER)) continue
            for (const literal of ["'authToken'", "'username'"]) {
                if (file.content.includes(literal)) {
                    offenders.push(`${file.path} spells ${literal}`)
                }
            }
        }
        expect(
            offenders,
            `these modules reach a session key by its raw string instead of `
            + `importing AUTH_TOKEN_KEY / USERNAME_KEY / clearLocalSession from `
            + `${OWNER}. The set of keys is the invariant; a module holding its `
            + `own copy is the one that gets missed when a key is added:\n`
            + offenders.join('\n')
        ).toEqual([])
    })

    it('finds the offenders when they are there', () => {
        // Guard-the-guard, against the two shapes that were actually present:
        // a hand-written teardown list and an inline read.
        const planted = [
            {
                path: 'pages/Fake.jsx',
                content: "localStorage.removeItem('authToken')",
            },
            {
                path: 'components/Fake.jsx',
                content: "localStorage.getItem('username')",
            },
        ]
        const offenders = planted.filter((file) =>
            ["'authToken'", "'username'"].some((lit) =>
                file.content.includes(lit)
            )
        )
        expect(offenders).toHaveLength(2)
    })
})
