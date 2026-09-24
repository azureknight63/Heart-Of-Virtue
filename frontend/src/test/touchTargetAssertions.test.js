import { describe, it, expect } from 'vitest'

import { findUndersizedButtons } from './touchTargetAssertions'

const build = (html) => {
    const div = document.createElement('div')
    div.innerHTML = html
    return div
}

describe('findUndersizedButtons', () => {
    it('reports buttons with no floor, a sub-44px floor, or a non-px floor', () => {
        const container = build([
            '<button aria-label="bare" style="padding: 10px">x</button>',
            '<button style="min-height: 36px">short</button>',
            '<button style="min-height: 2.75rem">rem</button>',
        ].join(''))
        expect(findUndersizedButtons(container)).toEqual([
            { label: 'bare', minHeight: '(none)' },
            { label: 'short', minHeight: '36px' },
            { label: 'rem', minHeight: '2.75rem' },
        ])
    })

    it('is quiet on a min-height or height at or above the token', () => {
        const container = build([
            '<button style="min-height: 44px">a</button>',
            '<button style="height: 48px">b</button>',
        ].join(''))
        expect(findUndersizedButtons(container)).toEqual([])
    })
})
