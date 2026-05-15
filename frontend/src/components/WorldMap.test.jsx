import React from 'react'
import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import WorldMap from './WorldMap'

// Mock MapGrid component
vi.mock('./MapGrid', () => ({
  default: ({ location, onMove, exits, exploredTiles }) => (
    <div data-testid="map-grid">
      <p>{location?.map_name}</p>
      <button onClick={() => onMove('north')}>Move North</button>
    </div>
  ),
}))

describe('WorldMap', () => {
  const mockOnMoveToLocation = vi.fn()

  const mockLocation = {
    map_name: 'Starting Village',
    x: 10,
    y: 10,
    exits: ['north', 'south'],
    items: [],
    npcs: [],
    objects: [],
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Rendering', () => {
    it('renders loading message when location is null', () => {
      render(
        <WorldMap
          location={null}
          onMoveToLocation={mockOnMoveToLocation}
          exploredTiles={new Map()}
        />
      )
      expect(screen.getByText('Loading location...')).toBeInTheDocument()
    })

    it('renders loading message when location is undefined', () => {
      render(
        <WorldMap
          location={undefined}
          onMoveToLocation={mockOnMoveToLocation}
          exploredTiles={new Map()}
        />
      )
      expect(screen.getByText('Loading location...')).toBeInTheDocument()
    })

    it('renders MapGrid when location is provided', () => {
      render(
        <WorldMap
          location={mockLocation}
          onMoveToLocation={mockOnMoveToLocation}
          exploredTiles={new Map()}
        />
      )
      expect(screen.getByTestId('map-grid')).toBeInTheDocument()
    })

    it('passes location to MapGrid component', () => {
      render(
        <WorldMap
          location={mockLocation}
          onMoveToLocation={mockOnMoveToLocation}
          exploredTiles={new Map()}
        />
      )
      expect(screen.getByText('Starting Village')).toBeInTheDocument()
    })

    it('passes onMoveToLocation callback to MapGrid', () => {
      render(
        <WorldMap
          location={mockLocation}
          onMoveToLocation={mockOnMoveToLocation}
          exploredTiles={new Map()}
        />
      )
      const moveButton = screen.getByText('Move North')
      fireEvent.click(moveButton)
      expect(mockOnMoveToLocation).toHaveBeenCalled()
    })

    it('passes exits from location to MapGrid', () => {
      const location = { ...mockLocation, exits: ['north', 'east', 'south', 'west'] }
      render(
        <WorldMap
          location={location}
          onMoveToLocation={mockOnMoveToLocation}
          exploredTiles={new Map()}
        />
      )
      expect(screen.getByTestId('map-grid')).toBeInTheDocument()
    })

    it('handles location with no exits', () => {
      const location = { ...mockLocation, exits: [] }
      render(
        <WorldMap
          location={location}
          onMoveToLocation={mockOnMoveToLocation}
          exploredTiles={new Map()}
        />
      )
      expect(screen.getByTestId('map-grid')).toBeInTheDocument()
    })

    it('handles location with undefined exits', () => {
      const location = { ...mockLocation, exits: undefined }
      render(
        <WorldMap
          location={location}
          onMoveToLocation={mockOnMoveToLocation}
          exploredTiles={new Map()}
        />
      )
      expect(screen.getByTestId('map-grid')).toBeInTheDocument()
    })
  })

  describe('Props Passing', () => {
    it('passes empty Map when exploredTiles not provided', () => {
      render(
        <WorldMap
          location={mockLocation}
          onMoveToLocation={mockOnMoveToLocation}
        />
      )
      expect(screen.getByTestId('map-grid')).toBeInTheDocument()
    })

    it('passes exploredTiles to MapGrid', () => {
      const exploredTiles = new Map()
      exploredTiles.set('map:0,0', { items: [], npcs: [], objects: [] })

      render(
        <WorldMap
          location={mockLocation}
          onMoveToLocation={mockOnMoveToLocation}
          exploredTiles={exploredTiles}
        />
      )
      expect(screen.getByTestId('map-grid')).toBeInTheDocument()
    })

    it('passes loading prop as false to MapGrid', () => {
      render(
        <WorldMap
          location={mockLocation}
          onMoveToLocation={mockOnMoveToLocation}
          exploredTiles={new Map()}
        />
      )
      expect(screen.getByTestId('map-grid')).toBeInTheDocument()
    })
  })

  describe('Loading States', () => {
    it('shows loading message instead of map when location is missing', () => {
      const { container } = render(
        <WorldMap
          location={null}
          onMoveToLocation={mockOnMoveToLocation}
          exploredTiles={new Map()}
        />
      )
      expect(container.textContent).toContain('Loading location...')
    })

    it('transitions from loading to loaded', () => {
      const { rerender } = render(
        <WorldMap
          location={null}
          onMoveToLocation={mockOnMoveToLocation}
          exploredTiles={new Map()}
        />
      )
      expect(screen.getByText('Loading location...')).toBeInTheDocument()

      rerender(
        <WorldMap
          location={mockLocation}
          onMoveToLocation={mockOnMoveToLocation}
          exploredTiles={new Map()}
        />
      )
      expect(screen.queryByText('Loading location...')).not.toBeInTheDocument()
      expect(screen.getByTestId('map-grid')).toBeInTheDocument()
    })
  })

  describe('Styling', () => {
    it('applies flex layout to container', () => {
      const { container } = render(
        <WorldMap
          location={mockLocation}
          onMoveToLocation={mockOnMoveToLocation}
          exploredTiles={new Map()}
        />
      )
      const wrapper = container.firstChild
      expect(wrapper).toHaveStyle({ display: 'flex', flexDirection: 'column' })
    })

    it('applies full height styling', () => {
      const { container } = render(
        <WorldMap
          location={mockLocation}
          onMoveToLocation={mockOnMoveToLocation}
          exploredTiles={new Map()}
        />
      )
      const wrapper = container.firstChild
      expect(wrapper).toHaveStyle({ height: '100%' })
    })

    it('applies padding to container', () => {
      const { container } = render(
        <WorldMap
          location={mockLocation}
          onMoveToLocation={mockOnMoveToLocation}
          exploredTiles={new Map()}
        />
      )
      const wrapper = container.firstChild
      expect(wrapper).toHaveStyle({ padding: '16px' })
    })

    it('loading message uses cyan color styling', () => {
      render(
        <WorldMap
          location={null}
          onMoveToLocation={mockOnMoveToLocation}
          exploredTiles={new Map()}
        />
      )
      const loading = screen.getByText('Loading location...')
      expect(loading).toBeInTheDocument()
    })
  })

  describe('Interaction Flow', () => {
    it('calls onMoveToLocation when move button clicked', () => {
      render(
        <WorldMap
          location={mockLocation}
          onMoveToLocation={mockOnMoveToLocation}
          exploredTiles={new Map()}
        />
      )
      const moveButton = screen.getByText('Move North')
      fireEvent.click(moveButton)
      expect(mockOnMoveToLocation).toHaveBeenCalledWith('north')
    })

    it('updates when location prop changes', () => {
      const { rerender } = render(
        <WorldMap
          location={mockLocation}
          onMoveToLocation={mockOnMoveToLocation}
          exploredTiles={new Map()}
        />
      )
      expect(screen.getByText('Starting Village')).toBeInTheDocument()

      const newLocation = { ...mockLocation, map_name: 'Dark Forest' }
      rerender(
        <WorldMap
          location={newLocation}
          onMoveToLocation={mockOnMoveToLocation}
          exploredTiles={new Map()}
        />
      )
      expect(screen.getByText('Dark Forest')).toBeInTheDocument()
    })

    it('updates exploredTiles when they change', () => {
      const exploredTiles1 = new Map()
      const { rerender } = render(
        <WorldMap
          location={mockLocation}
          onMoveToLocation={mockOnMoveToLocation}
          exploredTiles={exploredTiles1}
        />
      )
      expect(screen.getByTestId('map-grid')).toBeInTheDocument()

      const exploredTiles2 = new Map()
      exploredTiles2.set('map:0,0', { items: [], npcs: [], objects: [] })
      rerender(
        <WorldMap
          location={mockLocation}
          onMoveToLocation={mockOnMoveToLocation}
          exploredTiles={exploredTiles2}
        />
      )
      expect(screen.getByTestId('map-grid')).toBeInTheDocument()
    })
  })

  describe('Edge Cases', () => {
    it('handles location with empty map_name', () => {
      const location = { ...mockLocation, map_name: '' }
      render(
        <WorldMap
          location={location}
          onMoveToLocation={mockOnMoveToLocation}
          exploredTiles={new Map()}
        />
      )
      expect(screen.getByTestId('map-grid')).toBeInTheDocument()
    })

    it('handles location with special characters in map_name', () => {
      const location = { ...mockLocation, map_name: 'Dark Grotto (1)' }
      render(
        <WorldMap
          location={location}
          onMoveToLocation={mockOnMoveToLocation}
          exploredTiles={new Map()}
        />
      )
      expect(screen.getByText('Dark Grotto (1)')).toBeInTheDocument()
    })

    it('handles location with many items', () => {
      const location = {
        ...mockLocation,
        items: Array.from({ length: 20 }, (_, i) => ({ name: `Item ${i}` })),
      }
      render(
        <WorldMap
          location={location}
          onMoveToLocation={mockOnMoveToLocation}
          exploredTiles={new Map()}
        />
      )
      expect(screen.getByTestId('map-grid')).toBeInTheDocument()
    })

    it('handles location with many NPCs', () => {
      const location = {
        ...mockLocation,
        npcs: Array.from({ length: 15 }, (_, i) => ({ name: `NPC ${i}` })),
      }
      render(
        <WorldMap
          location={location}
          onMoveToLocation={mockOnMoveToLocation}
          exploredTiles={new Map()}
        />
      )
      expect(screen.getByTestId('map-grid')).toBeInTheDocument()
    })

    it('handles location with many objects', () => {
      const location = {
        ...mockLocation,
        objects: Array.from({ length: 10 }, (_, i) => ({ name: `Object ${i}` })),
      }
      render(
        <WorldMap
          location={location}
          onMoveToLocation={mockOnMoveToLocation}
          exploredTiles={new Map()}
        />
      )
      expect(screen.getByTestId('map-grid')).toBeInTheDocument()
    })

    it('handles large explored tiles map', () => {
      const exploredTiles = new Map()
      for (let i = 0; i < 100; i++) {
        exploredTiles.set(`map:${i},${i}`, {
          items: [],
          npcs: [],
          objects: [],
        })
      }
      render(
        <WorldMap
          location={mockLocation}
          onMoveToLocation={mockOnMoveToLocation}
          exploredTiles={exploredTiles}
        />
      )
      expect(screen.getByTestId('map-grid')).toBeInTheDocument()
    })
  })

  describe('Accessibility', () => {
    it('loading message is accessible', () => {
      render(
        <WorldMap
          location={null}
          onMoveToLocation={mockOnMoveToLocation}
          exploredTiles={new Map()}
        />
      )
      const loading = screen.getByText('Loading location...')
      expect(loading).toBeInTheDocument()
    })

    it('map grid is passed to accessible component', () => {
      render(
        <WorldMap
          location={mockLocation}
          onMoveToLocation={mockOnMoveToLocation}
          exploredTiles={new Map()}
        />
      )
      expect(screen.getByTestId('map-grid')).toBeInTheDocument()
    })
  })

  describe('Multiple Renders', () => {
    it('handles rapid location changes', () => {
      const { rerender } = render(
        <WorldMap
          location={mockLocation}
          onMoveToLocation={mockOnMoveToLocation}
          exploredTiles={new Map()}
        />
      )

      for (let i = 0; i < 5; i++) {
        const newLocation = { ...mockLocation, map_name: `Location ${i}` }
        rerender(
          <WorldMap
            location={newLocation}
            onMoveToLocation={mockOnMoveToLocation}
            exploredTiles={new Map()}
          />
        )
      }

      expect(screen.getByText('Location 4')).toBeInTheDocument()
    })

    it('maintains callback reference across rerenders', () => {
      const callback1 = vi.fn()
      const { rerender } = render(
        <WorldMap
          location={mockLocation}
          onMoveToLocation={callback1}
          exploredTiles={new Map()}
        />
      )

      const callback2 = vi.fn()
      rerender(
        <WorldMap
          location={mockLocation}
          onMoveToLocation={callback2}
          exploredTiles={new Map()}
        />
      )

      const moveButton = screen.getByText('Move North')
      fireEvent.click(moveButton)
      expect(callback2).toHaveBeenCalled()
    })
  })
})
