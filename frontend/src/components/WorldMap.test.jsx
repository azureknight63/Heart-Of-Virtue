import React from 'react'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import WorldMap from './WorldMap'
import { makeLocation } from '../test/payloads'

/**
 * WorldMap's entire job is (a) gating on a missing location and (b) forwarding
 * props to MapGrid. So the MapGrid mock is a PROP RECORDER, not a stub.
 *
 * The previous version of this file mocked MapGrid with a stub that ignored
 * `exits`, `exploredTiles` and `loading` outright, then asserted
 * `getByTestId('map-grid')).toBeInTheDocument()` — under tests named "passes
 * exits from location to MapGrid", "passes exploredTiles to MapGrid" and
 * "passes loading prop as false to MapGrid". Deleting every prop from
 * WorldMap.jsx's <MapGrid> call would have left all of them green, which is
 * the entire behaviour of the component.
 */
const receivedProps = []

vi.mock('./MapGrid', () => ({
  default: (props) => {
    receivedProps.push(props)
    return (
      <div data-testid="map-grid">
        <p>{props.location?.map_name}</p>
        <button onClick={() => props.onMove('north')}>Move North</button>
      </div>
    )
  },
}))

/** The props MapGrid was handed on its most recent render. */
const lastProps = () => receivedProps[receivedProps.length - 1]

describe('WorldMap', () => {
  const onMoveToLocation = vi.fn()
  // Realistic post-transformLocationData shape: useApi.js normalises the
  // server's `exits` dict into an array of direction names before any
  // component sees it (see src/test/payloads.js).
  const location = makeLocation({ map_name: 'Starting Village', x: 10, y: 10 })

  beforeEach(() => {
    vi.clearAllMocks()
    receivedProps.length = 0
  })

  describe('loading gate', () => {
    it.each([[null], [undefined]])(
      'renders the loading message and no grid when location is %p',
      (missing) => {
        render(<WorldMap location={missing} onMoveToLocation={onMoveToLocation} exploredTiles={new Map()} />)
        expect(screen.getByText('Loading location...')).toBeInTheDocument()
        expect(screen.queryByTestId('map-grid')).not.toBeInTheDocument()
        expect(receivedProps).toHaveLength(0)
      }
    )

    it('swaps the loading message for the grid once a location arrives', () => {
      const { rerender } = render(
        <WorldMap location={null} onMoveToLocation={onMoveToLocation} exploredTiles={new Map()} />
      )
      expect(screen.getByText('Loading location...')).toBeInTheDocument()

      rerender(<WorldMap location={location} onMoveToLocation={onMoveToLocation} exploredTiles={new Map()} />)

      expect(screen.queryByText('Loading location...')).not.toBeInTheDocument()
      expect(lastProps().location).toBe(location)
    })

    it('renders the loading message in the cyan info color', () => {
      const { container } = render(
        <WorldMap location={null} onMoveToLocation={onMoveToLocation} exploredTiles={new Map()} />
      )
      // The loading branch has its own wrapper; its color is the only visual
      // state distinguishing it from an error/empty panel.
      expect(container.firstChild).toHaveStyle({ color: '#00ccff' })
    })
  })

  describe('prop forwarding to MapGrid', () => {
    it('forwards location, onMove, exits and exploredTiles by identity', () => {
      const exploredTiles = new Map([['Dark Grotto:0,0', { items: [], npcs: [], objects: [] }]])
      render(<WorldMap location={location} onMoveToLocation={onMoveToLocation} exploredTiles={exploredTiles} />)

      const props = lastProps()
      expect(props.location).toBe(location)
      expect(props.onMove).toBe(onMoveToLocation)
      expect(props.exits).toEqual(['north', 'east'])
      expect(props.exploredTiles).toBe(exploredTiles)
    })

    it('always reports loading as false — WorldMap has already gated on it', () => {
      render(<WorldMap location={location} onMoveToLocation={onMoveToLocation} exploredTiles={new Map()} />)
      expect(lastProps().loading).toBe(false)
    })

    it.each([
      ['a populated exits array', ['north', 'east', 'south', 'west'], ['north', 'east', 'south', 'west']],
      ['an empty exits array', [], []],
      // `location.exits || []` is the only defaulting WorldMap does; a room
      // with no exits at all must not hand MapGrid `undefined`, which would
      // throw on the `exits.includes(...)` reads inside it.
      ['an absent exits field', undefined, []],
    ])('normalises %s before forwarding', (_label, exits, expected) => {
      render(
        <WorldMap
          location={makeLocation({ exits })}
          onMoveToLocation={onMoveToLocation}
          exploredTiles={new Map()}
        />
      )
      expect(lastProps().exits).toEqual(expected)
    })

    it('forwards an undefined exploredTiles rather than substituting a value', () => {
      // MapGrid owns the empty-map default; WorldMap inventing one here would
      // mask a genuinely missing exploration payload.
      render(<WorldMap location={location} onMoveToLocation={onMoveToLocation} />)
      expect(lastProps().exploredTiles).toBeUndefined()
    })
  })

  describe('layout', () => {
    it('fills its parent as a vertical flex column with padding', () => {
      const { container } = render(
        <WorldMap location={location} onMoveToLocation={onMoveToLocation} exploredTiles={new Map()} />
      )
      expect(container.firstChild).toHaveStyle({
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        padding: '16px',
      })
    })
  })

  describe('interaction and updates', () => {
    it('routes a MapGrid move up through onMoveToLocation with the direction', () => {
      render(<WorldMap location={location} onMoveToLocation={onMoveToLocation} exploredTiles={new Map()} />)
      fireEvent.click(screen.getByText('Move North'))
      expect(onMoveToLocation).toHaveBeenCalledWith('north')
    })

    it('forwards the current callback after it is replaced, not a stale capture', () => {
      const first = vi.fn()
      const { rerender } = render(
        <WorldMap location={location} onMoveToLocation={first} exploredTiles={new Map()} />
      )
      const second = vi.fn()
      rerender(<WorldMap location={location} onMoveToLocation={second} exploredTiles={new Map()} />)

      fireEvent.click(screen.getByText('Move North'))
      expect(second).toHaveBeenCalledWith('north')
      expect(first).not.toHaveBeenCalled()
    })

    it('re-forwards a changed location and exploredTiles on rerender', () => {
      const { rerender } = render(
        <WorldMap location={location} onMoveToLocation={onMoveToLocation} exploredTiles={new Map()} />
      )
      expect(screen.getByText('Starting Village')).toBeInTheDocument()

      const nextLocation = makeLocation({ map_name: 'Dark Forest', exits: ['south'] })
      const nextTiles = new Map([['Dark Forest:0,0', {}]])
      rerender(
        <WorldMap location={nextLocation} onMoveToLocation={onMoveToLocation} exploredTiles={nextTiles} />
      )

      expect(screen.getByText('Dark Forest')).toBeInTheDocument()
      expect(lastProps().location).toBe(nextLocation)
      expect(lastProps().exits).toEqual(['south'])
      expect(lastProps().exploredTiles).toBe(nextTiles)
    })
  })
})
