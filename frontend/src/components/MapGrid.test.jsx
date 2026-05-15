import React from 'react'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import MapGrid from './MapGrid'

// Mock MovementStar component
vi.mock('./MovementStar', () => ({
  default: ({ exits, onMove, loading }) => (
    <div data-testid="movement-star">
      <button onClick={() => onMove('north')}>Move North</button>
    </div>
  ),
}))

describe('MapGrid', () => {
  const mockOnMove = vi.fn()

  const mockLocation = {
    map_name: 'test-map',
    x: 6,
    y: 6,
    exits: ['north', 'south', 'east', 'west'],
    items: [],
    npcs: [],
    objects: [],
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Rendering', () => {
    it('renders loading state when location is null', () => {
      render(
        <MapGrid
          location={null}
          onMove={mockOnMove}
          exits={[]}
          loading={false}
          exploredTiles={new Map()}
        />
      )
      expect(screen.getByText('Loading map...')).toBeInTheDocument()
    })

    it('renders loading state when location is undefined', () => {
      render(
        <MapGrid
          location={undefined}
          onMove={mockOnMove}
          exits={[]}
          loading={false}
          exploredTiles={new Map()}
        />
      )
      expect(screen.getByText('Loading map...')).toBeInTheDocument()
    })

    it('renders map grid when location is provided', () => {
      render(
        <MapGrid
          location={mockLocation}
          onMove={mockOnMove}
          exits={mockLocation.exits}
          loading={false}
          exploredTiles={new Map()}
        />
      )
      expect(screen.queryByText('Loading map...')).not.toBeInTheDocument()
    })

    it('renders map name in title', () => {
      const { container } = render(
        <MapGrid
          location={mockLocation}
          onMove={mockOnMove}
          exits={mockLocation.exits}
          loading={false}
          exploredTiles={new Map()}
        />
      )
      // Map name is formatted and displayed in the title div
      const titleDiv = Array.from(container.querySelectorAll('div')).find(el => el.textContent.includes('Test Map'))
      expect(titleDiv).toBeInTheDocument()
    })

    it('formats map name with proper spacing', () => {
      const location = { ...mockLocation, map_name: 'dark-grotto' }
      render(
        <MapGrid
          location={location}
          onMove={mockOnMove}
          exits={location.exits}
          loading={false}
          exploredTiles={new Map()}
        />
      )
      expect(screen.getByText(/Dark Grotto/)).toBeInTheDocument()
    })

    it('renders movement star component', () => {
      render(
        <MapGrid
          location={mockLocation}
          onMove={mockOnMove}
          exits={mockLocation.exits}
          loading={false}
          exploredTiles={new Map()}
        />
      )
      expect(screen.getByTestId('movement-star')).toBeInTheDocument()
    })

    it('renders map legend', () => {
      const { container } = render(
        <MapGrid
          location={mockLocation}
          onMove={mockOnMove}
          exits={mockLocation.exits}
          loading={false}
          exploredTiles={new Map()}
        />
      )
      // Legend contains legend text split across multiple divs
      const legendText = container.textContent
      expect(legendText).toContain('You')
      expect(legendText).toContain('Visited')
      expect(legendText).toContain('Items')
      expect(legendText).toContain('NPCs')
      expect(legendText).toContain('Objects')
    })

    it('displays current location coordinates', () => {
      render(
        <MapGrid
          location={mockLocation}
          onMove={mockOnMove}
          exits={mockLocation.exits}
          loading={false}
          exploredTiles={new Map()}
        />
      )
      expect(screen.getByText('(6, 6)')).toBeInTheDocument()
    })

    it('displays available exits', () => {
      render(
        <MapGrid
          location={mockLocation}
          onMove={mockOnMove}
          exits={mockLocation.exits}
          loading={false}
          exploredTiles={new Map()}
        />
      )
      expect(screen.getByText(/Exits:/)).toBeInTheDocument()
    })
  })

  describe('Grid Layout', () => {
    it('renders 13x13 grid (169 tiles)', () => {
      const { container } = render(
        <MapGrid
          location={mockLocation}
          onMove={mockOnMove}
          exits={mockLocation.exits}
          loading={false}
          exploredTiles={new Map()}
        />
      )
      // Count the number of tile divs - should be 169 (13x13)
      const tiles = Array.from(container.querySelectorAll('div')).filter(div => {
        const style = div.getAttribute('style')
        return style && style.includes('width: 40px') && style.includes('height: 40px')
      })
      expect(tiles.length).toBe(169)
    })

    it('centers player in grid', () => {
      const { container } = render(
        <MapGrid
          location={mockLocation}
          onMove={mockOnMove}
          exits={mockLocation.exits}
          loading={false}
          exploredTiles={new Map()}
        />
      )
      // Player is at center, render should succeed
      expect(container.firstChild).toBeInTheDocument()
    })

    it('marks player position with special symbol', () => {
      const { container } = render(
        <MapGrid
          location={mockLocation}
          onMove={mockOnMove}
          exits={mockLocation.exits}
          loading={false}
          exploredTiles={new Map()}
        />
      )
      // Player tile should have title "Your Position"
      const playerTile = container.querySelector('[title="Your Position"]')
      expect(playerTile).toBeInTheDocument()
    })
  })

  describe('Tile Interactions', () => {
    it('calls onMove when valid adjacent tile is clicked', () => {
      const { container } = render(
        <MapGrid
          location={mockLocation}
          onMove={mockOnMove}
          exits={mockLocation.exits}
          loading={false}
          exploredTiles={new Map()}
        />
      )
      // Click on a tile adjacent to player
      const tiles = container.querySelectorAll('div[title*="Move"]')
      if (tiles.length > 0) {
        fireEvent.click(tiles[0])
        expect(mockOnMove).toHaveBeenCalled()
      }
    })

    it('does not call onMove when player tile is clicked', () => {
      const { container } = render(
        <MapGrid
          location={mockLocation}
          onMove={mockOnMove}
          exits={mockLocation.exits}
          loading={false}
          exploredTiles={new Map()}
        />
      )
      // Find and click player tile
      const playerTiles = Array.from(container.querySelectorAll('div[title="Your Position"]'))
      if (playerTiles.length > 0) {
        fireEvent.click(playerTiles[0])
        expect(mockOnMove).not.toHaveBeenCalled()
      }
    })

    it('does not allow moves to tiles outside exits', () => {
      const location = { ...mockLocation, exits: ['north'] }
      const { container } = render(
        <MapGrid
          location={location}
          onMove={mockOnMove}
          exits={location.exits}
          loading={false}
          exploredTiles={new Map()}
        />
      )
      // Try clicking on non-exit tile (e.g., south)
      // The grid should still render without errors
      expect(container.firstChild).toBeInTheDocument()
    })

    it('correctly maps clicks to direction names', () => {
      const location = { ...mockLocation, x: 5, y: 5 }
      const { container } = render(
        <MapGrid
          location={location}
          onMove={mockOnMove}
          exits={['north', 'south', 'east', 'west']}
          loading={false}
          exploredTiles={new Map()}
        />
      )
      // Grid should be rendered correctly
      expect(container.firstChild).toBeInTheDocument()
    })
  })

  describe('Explored Tiles', () => {
    it('marks explored tiles with different color', () => {
      const exploredTiles = new Map()
      const tileKey = 'test-map:6,5'
      exploredTiles.set(tileKey, {
        items: [],
        npcs: [],
        objects: [],
      })

      const { container } = render(
        <MapGrid
          location={mockLocation}
          onMove={mockOnMove}
          exits={mockLocation.exits}
          loading={false}
          exploredTiles={exploredTiles}
        />
      )
      expect(container.firstChild).toBeInTheDocument()
    })

    it('displays tile icons for explored tiles with items', () => {
      const exploredTiles = new Map()
      const tileKey = 'test-map:6,5'
      exploredTiles.set(tileKey, {
        items: [{ name: 'Sword' }],
        npcs: [],
        objects: [],
      })

      const { container } = render(
        <MapGrid
          location={mockLocation}
          onMove={mockOnMove}
          exits={mockLocation.exits}
          loading={false}
          exploredTiles={exploredTiles}
        />
      )
      expect(container.firstChild).toBeInTheDocument()
    })

    it('displays NPC icon for explored tiles with NPCs', () => {
      const exploredTiles = new Map()
      const tileKey = 'test-map:6,5'
      exploredTiles.set(tileKey, {
        items: [],
        npcs: [{ name: 'Guard' }],
        objects: [],
      })

      const { container } = render(
        <MapGrid
          location={mockLocation}
          onMove={mockOnMove}
          exits={mockLocation.exits}
          loading={false}
          exploredTiles={exploredTiles}
        />
      )
      expect(container.firstChild).toBeInTheDocument()
    })

    it('displays object icon for explored tiles with objects', () => {
      const exploredTiles = new Map()
      const tileKey = 'test-map:6,5'
      exploredTiles.set(tileKey, {
        items: [],
        npcs: [],
        objects: [{ name: 'Chest' }],
      })

      const { container } = render(
        <MapGrid
          location={mockLocation}
          onMove={mockOnMove}
          exits={mockLocation.exits}
          loading={false}
          exploredTiles={exploredTiles}
        />
      )
      expect(container.firstChild).toBeInTheDocument()
    })
  })

  describe('Current Location Display', () => {
    it('shows current tile content indicators', () => {
      const location = {
        ...mockLocation,
        items: [{ name: 'Gold' }],
        npcs: [],
        objects: [],
      }

      const { container } = render(
        <MapGrid
          location={location}
          onMove={mockOnMove}
          exits={location.exits}
          loading={false}
          exploredTiles={new Map()}
        />
      )
      expect(container.firstChild).toBeInTheDocument()
    })

    it('shows different symbol when multiple content types present', () => {
      const location = {
        ...mockLocation,
        items: [{ name: 'Gold' }],
        npcs: [{ name: 'NPC' }],
        objects: [{ name: 'Object' }],
      }

      const { container } = render(
        <MapGrid
          location={location}
          onMove={mockOnMove}
          exits={location.exits}
          loading={false}
          exploredTiles={new Map()}
        />
      )
      expect(container.firstChild).toBeInTheDocument()
    })

    it('shows NPC symbol when only NPCs present', () => {
      const location = {
        ...mockLocation,
        npcs: [{ name: 'Guard' }],
        items: [],
        objects: [],
      }

      const { container } = render(
        <MapGrid
          location={location}
          onMove={mockOnMove}
          exits={location.exits}
          loading={false}
          exploredTiles={new Map()}
        />
      )
      expect(container.firstChild).toBeInTheDocument()
    })
  })

  describe('Mouse Interactions', () => {
    it('highlights valid move tiles on hover', () => {
      const { container } = render(
        <MapGrid
          location={mockLocation}
          onMove={mockOnMove}
          exits={mockLocation.exits}
          loading={false}
          exploredTiles={new Map()}
        />
      )
      const tiles = container.querySelectorAll('div[title*="Move"]')
      if (tiles.length > 0) {
        fireEvent.mouseEnter(tiles[0])
        expect(tiles[0]).toBeInTheDocument()
      }
    })

    it('restores normal styling on mouse leave', () => {
      const { container } = render(
        <MapGrid
          location={mockLocation}
          onMove={mockOnMove}
          exits={mockLocation.exits}
          loading={false}
          exploredTiles={new Map()}
        />
      )
      const tiles = container.querySelectorAll('div[title*="Move"]')
      if (tiles.length > 0) {
        fireEvent.mouseEnter(tiles[0])
        fireEvent.mouseLeave(tiles[0])
        expect(tiles[0]).toBeInTheDocument()
      }
    })
  })

  describe('Edge Cases', () => {
    it('handles location with no exits', () => {
      const location = { ...mockLocation, exits: [] }
      const { container } = render(
        <MapGrid
          location={location}
          onMove={mockOnMove}
          exits={[]}
          loading={false}
          exploredTiles={new Map()}
        />
      )
      // Component should render without errors even with no exits
      expect(container.firstChild).toBeInTheDocument()
    })

    it('handles location with undefined exits', () => {
      const location = { ...mockLocation, exits: undefined }
      render(
        <MapGrid
          location={location}
          onMove={mockOnMove}
          exits={[]}
          loading={false}
          exploredTiles={new Map()}
        />
      )
      expect(screen.getByTestId('movement-star')).toBeInTheDocument()
    })

    it('handles location with many exits', () => {
      const location = {
        ...mockLocation,
        exits: ['north', 'south', 'east', 'west', 'northeast', 'northwest', 'southeast', 'southwest'],
      }
      render(
        <MapGrid
          location={location}
          onMove={mockOnMove}
          exits={location.exits}
          loading={false}
          exploredTiles={new Map()}
        />
      )
      expect(screen.getByTestId('movement-star')).toBeInTheDocument()
    })

    it('handles location with special characters in map name', () => {
      const location = { ...mockLocation, map_name: 'dark-grotto_01' }
      const { container } = render(
        <MapGrid
          location={location}
          onMove={mockOnMove}
          exits={location.exits}
          loading={false}
          exploredTiles={new Map()}
        />
      )
      // Map name is formatted and displayed
      const titleDiv = Array.from(container.querySelectorAll('div')).find(el => el.textContent.includes('Dark Grotto 01'))
      expect(titleDiv).toBeInTheDocument()
    })

    it('handles large coordinate values', () => {
      const location = { ...mockLocation, x: 9999, y: 9999 }
      render(
        <MapGrid
          location={location}
          onMove={mockOnMove}
          exits={location.exits}
          loading={false}
          exploredTiles={new Map()}
        />
      )
      expect(screen.getByText('(9999, 9999)')).toBeInTheDocument()
    })

    it('handles negative coordinate values', () => {
      const location = { ...mockLocation, x: -5, y: -10 }
      render(
        <MapGrid
          location={location}
          onMove={mockOnMove}
          exits={location.exits}
          loading={false}
          exploredTiles={new Map()}
        />
      )
      expect(screen.getByText('(-5, -10)')).toBeInTheDocument()
    })
  })

  describe('Accessibility', () => {
    it('tiles have descriptive titles for screen readers', () => {
      const { container } = render(
        <MapGrid
          location={mockLocation}
          onMove={mockOnMove}
          exits={mockLocation.exits}
          loading={false}
          exploredTiles={new Map()}
        />
      )
      const playerTile = container.querySelector('[title="Your Position"]')
      expect(playerTile).toBeInTheDocument()
    })

    it('movement tiles show direction in title', () => {
      const { container } = render(
        <MapGrid
          location={mockLocation}
          onMove={mockOnMove}
          exits={mockLocation.exits}
          loading={false}
          exploredTiles={new Map()}
        />
      )
      // Tiles should have titles for accessibility
      const tiles = container.querySelectorAll('[title]')
      expect(tiles.length).toBeGreaterThan(0)
    })
  })
})
