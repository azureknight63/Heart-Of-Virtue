import React from 'react'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import MapGrid from './MapGrid'
import { makeLocation } from '../test/payloads'

// MovementStar is exercised by its own suite; here it is a spy so this file can
// assert what MapGrid HANDS it (the exits array and the loading flag) rather
// than re-testing the star's internals.
const starProps = { current: null }
vi.mock('./MovementStar', () => ({
  default: (props) => {
    starProps.current = props
    return (
      <div data-testid="movement-star">
        <button onClick={() => props.onMove('north')}>Move North</button>
      </div>
    )
  },
}))

const GRID_SIZE = 13
const CENTER = Math.floor(GRID_SIZE / 2) // 6

// `makeLocation()` is the post-transformLocationData shape: `exits` is an array
// of direction NAMES (the server sends a dict; useApi normalises it), and
// `map_name`/`x`/`y`/`items`/`npcs`/`objects` are the keys the room serializer
// actually emits. Building from it is what makes a field rename fail here.
const LOCATION = makeLocation({
  map_name: 'test-map',
  x: 6,
  y: 6,
  exits: ['north', 'south', 'east', 'west'],
})

/** The CSS-grid element holding the 169 tiles, in row-major order. */
const gridOf = (container) => container.querySelector('div[style*="grid-template-columns"]')

/** The tile div for world coordinate (x, y), relative to `loc`'s centred player. */
function tileAt(container, x, y, loc = LOCATION) {
  const col = x - (loc.x - CENTER)
  const row = y - (loc.y - CENTER)
  expect(col).toBeGreaterThanOrEqual(0)
  expect(row).toBeGreaterThanOrEqual(0)
  return gridOf(container).children[row * GRID_SIZE + col]
}

/** Render helper: every test needs the same five props. */
function renderGrid(opts = {}) {
  // NB: `'location' in opts`, not a default parameter — the loading-state tests
  // pass an explicit `undefined`, which a default would silently replace.
  const { exploredTiles = new Map(), onMove, exits, loading = false } = opts
  const location = 'location' in opts ? opts.location : LOCATION
  return render(
    <MapGrid
      location={location}
      onMove={onMove}
      exits={exits === undefined ? location?.exits : exits}
      loading={loading}
      exploredTiles={exploredTiles}
    />
  )
}

describe('MapGrid', () => {
  let onMove

  beforeEach(() => {
    vi.clearAllMocks()
    onMove = vi.fn()
    starProps.current = null
  })

  describe('loading state', () => {
    it.each([['null', null], ['undefined', undefined]])(
      'shows "Loading map..." and no grid when location is %s',
      (_label, location) => {
        const { container } = renderGrid({ location, onMove, exits: [] })
        expect(screen.getByText('Loading map...')).toBeInTheDocument()
        expect(gridOf(container)).toBeNull()
        expect(screen.queryByTestId('movement-star')).toBeNull()
      }
    )
  })

  describe('header, legend and footer', () => {
    it('title-cases the map name and replaces hyphens, keeping underscores', () => {
      renderGrid({ location: makeLocation({ ...LOCATION, map_name: 'dark-grotto_01' }), onMove })
      expect(screen.getByText('⛰️ Dark Grotto_01')).toBeInTheDocument()
    })

    it('falls back to location.name, then to "World Map", when map_name is absent', () => {
      const { unmount } = renderGrid({
        location: { ...LOCATION, map_name: undefined, name: 'The Ruins' },
        onMove,
      })
      expect(screen.getByText('⛰️ The Ruins')).toBeInTheDocument()
      unmount()

      renderGrid({ location: { ...LOCATION, map_name: undefined, name: undefined }, onMove })
      expect(screen.getByText('⛰️ World Map')).toBeInTheDocument()
    })

    it('renders the legend keyed to the symbols the grid actually draws', () => {
      const { container } = renderGrid({ onMove })
      // Each legend glyph must match the symbol getTileContent/TileIcons emit;
      // a legend that drifts from the grid is worse than none.
      const legend = container.querySelector('div[style*="1fr 1fr 1fr 1fr 1fr"]')
      expect(Array.from(legend.children, el => el.textContent)).toEqual([
        '© = You',
        '● = Visited',
        '◆ = Items',
        '◉ = NPCs',
        '◾ = Objects',
      ])
    })

    it.each([
      ['ordinary', 6, 6],
      ['large', 9999, 9999],
      ['negative', -5, -10],
    ])('prints the player\'s %s coordinates and its exit list', (_label, x, y) => {
      const location = makeLocation({ ...LOCATION, x, y })
      renderGrid({ location, onMove })
      expect(screen.getByText(`(${x}, ${y})`)).toBeInTheDocument()
      expect(screen.getByText('Exits: north, south, east, west')).toBeInTheDocument()
    })

    it('omits the exits line entirely when the room is a dead end', () => {
      renderGrid({ location: makeLocation({ ...LOCATION, exits: [] }), onMove })
      expect(screen.queryByText(/^Exits:/)).toBeNull()
      expect(screen.getByText('(6, 6)')).toBeInTheDocument()
    })

    it('hands MovementStar the exit list and loading flag, defaulting exits to []', () => {
      const { unmount } = renderGrid({ onMove, loading: true })
      expect(starProps.current.exits).toEqual(['north', 'south', 'east', 'west'])
      expect(starProps.current.loading).toBe(true)
      expect(starProps.current.onMove).toBe(onMove)
      unmount()

      renderGrid({ onMove, exits: undefined, location: { ...LOCATION, exits: undefined } })
      expect(starProps.current.exits).toEqual([])
    })
  })

  describe('grid layout', () => {
    it('renders a 13x13 grid centred on the player', () => {
      const { container } = renderGrid({ onMove })
      const grid = gridOf(container)
      expect(grid.children).toHaveLength(GRID_SIZE * GRID_SIZE)
      expect(grid.style.gridTemplateColumns).toBe('repeat(13, 40px)')

      // Centring is the whole point of the odd GRID_SIZE: the player must sit
      // at index 6,6, and the corners must be player ± 6 on both axes.
      expect(grid.children[CENTER * GRID_SIZE + CENTER].title).toBe('Your Position')
      expect(grid.children[0].title).toBe('(0, 0)')
      expect(grid.children[GRID_SIZE * GRID_SIZE - 1].title).toBe('(12, 12)')
    })

    it('re-centres on the player after a move, shifting the visible window', () => {
      const { container, rerender } = renderGrid({ onMove })
      expect(gridOf(container).children[0].title).toBe('(0, 0)')

      // Player walks north: the window follows, so the top-left is now (0, -1).
      rerender(
        <MapGrid
          location={makeLocation({ ...LOCATION, y: 5 })}
          onMove={onMove}
          exits={LOCATION.exits}
          loading={false}
          exploredTiles={new Map()}
        />
      )
      expect(gridOf(container).children[0].title).toBe('(0, -1)')
      expect(gridOf(container).children[CENTER * GRID_SIZE + CENTER].title).toBe('Your Position')
    })
  })

  describe('player tile symbol', () => {
    // getTileContent's symbol ladder. Every one of these cases previously had a
    // test named after its symbol that asserted only
    // `expect(container.firstChild).toBeInTheDocument()` — the whole ladder
    // could be replaced by a hardcoded '©' and all five stayed green.
    const GOLD = [{ name: 'Gold' }]
    it.each([
      ['empty room', {}, '©'],
      ['items only', { items: GOLD }, '◆'],
      ['npcs only', { npcs: [{ name: 'Guard' }] }, '◉'],
      ['objects only', { objects: [{ name: 'Chest' }] }, '◾'],
      ['two content types', { items: GOLD, npcs: [{ name: 'Guard' }] }, '✦'],
      ['all three content types', { items: GOLD, npcs: [{ name: 'Guard' }], objects: [{ name: 'Chest' }] }, '✦'],
      // npcs outrank objects outrank items when exactly one type is present…
      ['npcs beat objects at a count of one type', { npcs: [{ name: 'Guard' }] }, '◉'],
    ])('draws %s as %s', (_label, contents, symbol) => {
      const location = makeLocation({ ...LOCATION, items: [], npcs: [], objects: [], ...contents })
      const { container } = renderGrid({ location, onMove })
      const tile = tileAt(container, 6, 6, location)
      expect(tile.textContent).toBe(symbol)
      expect(tile.style.backgroundColor).toBe('rgb(0, 255, 136)')
      expect(tile.style.color).toBe('rgb(0, 0, 0)')
      expect(tile.style.border).toContain('rgb(255, 170, 0)')
    })

    it('treats missing items/npcs/objects arrays as empty rather than crashing', () => {
      const location = { map_name: 'test-map', x: 6, y: 6, exits: ['north'] }
      const { container } = renderGrid({ location, onMove })
      expect(tileAt(container, 6, 6, location).textContent).toBe('©')
    })
  })

  describe('explored tiles', () => {
    const explored = (entries) => new Map(entries.map(([x, y, data]) => [`test-map:${x},${y}`, data]))

    it('draws a visited tile in the visited colour with its own symbol', () => {
      const { container } = renderGrid({
        onMove,
        exploredTiles: explored([[6, 5, { items: [], npcs: [], objects: [] }]]),
      })
      const visited = tileAt(container, 6, 5)
      expect(visited.textContent).toBe('●')
      expect(visited.style.backgroundColor).toBe('rgba(0, 255, 136, 0.2)')
      expect(visited.style.color).toBe('rgb(0, 255, 136)')

      // An unvisited neighbour keeps the dim placeholder.
      const unvisited = tileAt(container, 5, 5)
      expect(unvisited.textContent).toBe('.')
      expect(unvisited.style.backgroundColor).toBe('rgb(26, 26, 46)')
      expect(unvisited.style.color).toBe('rgb(102, 102, 102)')
    })

    it('keys explored tiles by map, so the same coords on another map stay dark', () => {
      // The key is `${map_name}:${x},${y}` — dropping the map prefix would leak
      // one map's exploration onto every other map at the same coordinates.
      const other = new Map([['other-map:6,5', { items: [], npcs: [], objects: [] }]])
      const { container } = renderGrid({ onMove, exploredTiles: other })
      expect(tileAt(container, 6, 5).textContent).toBe('.')
    })

    it.each([
      ['items', { items: [{ name: 'Sword' }] }, '◆'],
      ['npcs', { npcs: [{ name: 'Guard' }] }, '◉'],
      ['objects', { objects: [{ name: 'Chest' }] }, '◾'],
    ])('badges a visited tile that holds %s with %s', (_label, contents, icon) => {
      const { container } = renderGrid({
        onMove,
        exploredTiles: explored([[6, 5, { items: [], npcs: [], objects: [], ...contents }]]),
      })
      // The badge sits alongside the '●' visited symbol.
      expect(tileAt(container, 6, 5).textContent).toBe(`${icon}●`)
    })

    it('badges a visited tile holding all three content types with all three icons', () => {
      const { container } = renderGrid({
        onMove,
        exploredTiles: explored([[6, 5, {
          items: [{ name: 'Sword' }], npcs: [{ name: 'Guard' }], objects: [{ name: 'Chest' }],
        }]]),
      })
      expect(tileAt(container, 6, 5).textContent).toBe('◆◉◾●')
    })

    it('never badges the player\'s own tile — its symbol already encodes contents', () => {
      const location = makeLocation({ ...LOCATION, items: [{ name: 'Gold' }] })
      const { container } = renderGrid({
        location,
        onMove,
        exploredTiles: explored([[6, 6, { items: [{ name: 'Gold' }], npcs: [], objects: [] }]]),
      })
      expect(tileAt(container, 6, 6, location).textContent).toBe('◆')
    })
  })

  describe('movement', () => {
    it.each([
      ['north', 6, 5],
      ['south', 6, 7],
      ['west', 5, 6],
      ['east', 7, 6],
    ])('moves %s when the tile at that offset is clicked', (direction, x, y) => {
      const { container } = renderGrid({ onMove })
      const tile = tileAt(container, x, y)
      expect(tile.title).toBe(`Move ${direction}`)
      fireEvent.click(tile)
      // The previous version clicked "tiles[0]" and asserted only
      // toHaveBeenCalled(), so a grid that mapped every click to 'north' passed.
      expect(onMove).toHaveBeenCalledTimes(1)
      expect(onMove).toHaveBeenCalledWith(direction)
    })

    it.each([
      ['northwest', 5, 5],
      ['northeast', 7, 5],
      ['southwest', 5, 7],
      ['southeast', 7, 7],
    ])('moves %s on the diagonal offsets', (direction, x, y) => {
      const location = makeLocation({
        ...LOCATION,
        exits: ['northwest', 'northeast', 'southwest', 'southeast'],
      })
      const { container } = renderGrid({ location, onMove })
      fireEvent.click(tileAt(container, x, y, location))
      expect(onMove).toHaveBeenCalledWith(direction)
    })

    it('ignores a click on the player\'s own tile', () => {
      const { container } = renderGrid({ onMove })
      fireEvent.click(tileAt(container, 6, 6))
      expect(onMove).not.toHaveBeenCalled()
    })

    it('ignores a click on a neighbour that is not an exit', () => {
      const location = makeLocation({ ...LOCATION, exits: ['north'] })
      const { container } = renderGrid({ location, onMove })
      const south = tileAt(container, 6, 7, location)
      // No exit south: no affordance and no move.
      expect(south.title).toBe('(6, 7)')
      expect(south.style.cursor).toBe('default')
      fireEvent.click(south)
      expect(onMove).not.toHaveBeenCalled()

      fireEvent.click(tileAt(container, 6, 5, location))
      expect(onMove).toHaveBeenCalledExactlyOnceWith('north')
    })

    it('ignores a click on a non-adjacent tile even when that direction is an exit', () => {
      const { container } = renderGrid({ onMove })
      // Two tiles north is not a single move, so DIRECTION_BY_OFFSET has no
      // entry for it and the click must be inert.
      const twoNorth = tileAt(container, 6, 4)
      expect(twoNorth.title).toBe('(6, 4)')
      fireEvent.click(twoNorth)
      expect(onMove).not.toHaveBeenCalled()
    })

    it('renders no move affordances at all when the room has no exits', () => {
      const location = makeLocation({ ...LOCATION, exits: [] })
      const { container } = renderGrid({ location, onMove })
      expect(container.querySelectorAll('div[title^="Move "]')).toHaveLength(0)
      fireEvent.click(tileAt(container, 6, 5, location))
      expect(onMove).not.toHaveBeenCalled()
    })

    it('survives a location whose exits key is missing entirely', () => {
      const location = { ...LOCATION, exits: undefined }
      const { container } = renderGrid({ location, onMove, exits: [] })
      fireEvent.click(tileAt(container, 6, 5, location))
      expect(onMove).not.toHaveBeenCalled()
      expect(screen.queryByText(/^Exits:/)).toBeNull()
    })
  })

  describe('hover affordances', () => {
    it('highlights a valid move tile on hover and restores it on leave', () => {
      const { container } = renderGrid({ onMove })
      const north = tileAt(container, 6, 5)
      expect(north.style.cursor).toBe('pointer')
      expect(north.style.boxShadow).toBe('0 0 8px rgba(0, 255, 136, 0.5) inset')

      fireEvent.mouseEnter(north)
      expect(north.style.backgroundColor).toBe('rgba(0, 255, 136, 0.4)')
      expect(north.style.boxShadow).toBe('0 0 12px rgba(0, 255, 136, 0.8) inset')

      fireEvent.mouseLeave(north)
      // Back to the unexplored base colour, not the hover tint.
      expect(north.style.backgroundColor).toBe('rgb(26, 26, 46)')
      expect(north.style.boxShadow).toBe('0 0 8px rgba(0, 255, 136, 0.5) inset')
    })

    it('does not highlight a tile that is not a legal move', () => {
      const location = makeLocation({ ...LOCATION, exits: ['north'] })
      const { container } = renderGrid({ location, onMove })
      const south = tileAt(container, 6, 7, location)
      fireEvent.mouseEnter(south)
      expect(south.style.backgroundColor).toBe('rgb(26, 26, 46)')
      expect(south.style.boxShadow).toBe('none')
    })

    it('restores an explored tile to its visited tint, not the unexplored one', () => {
      const { container } = renderGrid({
        onMove,
        exploredTiles: new Map([['test-map:6,5', { items: [], npcs: [], objects: [] }]]),
      })
      const north = tileAt(container, 6, 5)
      fireEvent.mouseEnter(north)
      fireEvent.mouseLeave(north)
      expect(north.style.backgroundColor).toBe('rgba(0, 255, 136, 0.2)')
    })
  })
})
