import { render, screen, fireEvent } from '@testing-library/react'
import { expect, test, vi } from 'vitest'
import RoomContents from './RoomContents'

test('renders room description and links for entity names', () => {
    const onInteract = vi.fn()
    const location = {
        description: 'A dusty room with a wooden chest.',
        items: [],
        npcs: [],
        objects: [
            {
                name: 'wooden chest',
                description: 'A sturdy chest.',
                idle_message: 'A wooden chest is sitting here.',
                hidden: false,
                aliases: []
            }
        ]
    }

    render(<RoomContents location={location} onInteract={onInteract} />)

    // Check if "wooden chest" is rendered as a link (we find it in the idle message)
    // getAllByText will find the exact span with the text
    const links = screen.getAllByText('wooden chest')
    expect(links.length).toBeGreaterThan(0)

    // Click the link
    fireEvent.click(links[0])
    expect(onInteract).toHaveBeenCalled()
})

test('renders links for entity aliases', () => {
    const onInteract = vi.fn()
    const location = {
        description: 'There are words inscribed on the wall.',
        items: [],
        npcs: [],
        objects: [
            {
                name: 'Inscription',
                description: 'Ancient writing.',
                idle_message: 'There appears to be some words inscribed in the wall.',
                hidden: false,
                aliases: ['words inscribed']
            }
        ]
    }

    render(<RoomContents location={location} onInteract={onInteract} />)

    // "words inscribed" should be a link
    const links = screen.getAllByText('words inscribed')
    expect(links.length).toBe(1) // Only matches in the idle_message, as room description doesn't render links
    expect(links[0].style.textDecoration).toBe('underline')

    // Click one
    fireEvent.click(links[0])
    expect(onInteract).toHaveBeenCalled()
})

test('sorts aliases by length to avoid partial matches', () => {
    const onInteract = vi.fn()
    const location = {
        description: 'The small depression is near a larger depression.',
        items: [],
        npcs: [],
        objects: [
            {
                name: 'Small Switch',
                aliases: ['small depression'],
                idle_message: 'The small depression is near a larger depression.',
                hidden: false
            },
            {
                name: 'Large Switch',
                aliases: ['depression'],
                idle_message: 'There is a depression here.',
                hidden: false
            }
        ]
    }

    render(<RoomContents location={location} onInteract={onInteract} />)

    // "small depression" should match the first entity
    // We expect 1 in idle_message for Small Switch
    const smallLinks = screen.getAllByText('small depression')
    expect(smallLinks.length).toBe(1)
    fireEvent.click(smallLinks[0])
    expect(onInteract).toHaveBeenCalledWith(expect.objectContaining({ name: 'Small Switch' }))

    // "depression" (the second one) should match the second entity
    // We expect one match for "depression" in the idle_message for "Large Switch", plus the second part 
    // of "larger depression" in the Small Switch idle message (because "larger depression" gets split into "larger " + "depression" span)
    // Wait, the idle text for Small Switch is 'The small depression is near a larger depression.'
    // So 'depression' will be a link there too since it matches 'depression'.
    // We can just click the last one or getAllByText('depression') and click [1]
    const largeLinks = screen.getAllByText('depression')
    expect(largeLinks.length).toBeGreaterThan(0)

    // Test the first exact 'depression' match, which should map to the large switch object
    // Oh wait, in the first object's idle msg, "small depression" is the longer match. 
    // The second occurrence is "larger depression" -> "depression" is matched to 'Large Switch'.
    fireEvent.click(largeLinks[0])
    expect(onInteract).toHaveBeenCalledWith(expect.objectContaining({ name: 'Large Switch' }))
})

test('handles a location with no items/npcs/objects keys at all', () => {
    const location = { description: 'A bare, empty room.' }
    render(<RoomContents location={location} onInteract={vi.fn()} />)
    expect(screen.getByText('(Nothing else here...)')).toBeInTheDocument()
})

test('returns null when location is absent', () => {
    const { container } = render(<RoomContents location={null} onInteract={vi.fn()} />)
    expect(container.firstChild).toBeNull()
})

test('shows the empty-state message when there is nothing else in the room', () => {
    const location = { description: 'An empty stone chamber.', items: [], npcs: [], objects: [] }
    render(<RoomContents location={location} onInteract={vi.fn()} />)
    expect(screen.getByText('(Nothing else here...)')).toBeInTheDocument()
})

test('renders NPC idle messages and a default item-here message', () => {
    const location = {
        description: 'A quiet clearing.',
        items: [{ name: 'Gold Coin', hidden: false }],
        npcs: [{ name: 'Gorran', idle_message: 'Gorran stands watch nearby.', hidden: false }],
        objects: [],
    }
    const { container } = render(<RoomContents location={location} onInteract={vi.fn()} />)
    expect(container.textContent).toContain('Gorran stands watch nearby.')
    expect(container.textContent).toContain('There is a Gold Coin here.')
})

test('uses a custom announce message for items when provided', () => {
    const location = {
        description: 'A quiet clearing.',
        items: [{ name: 'Torch', announce: 'A torch flickers against the wall.', hidden: false }],
        npcs: [],
        objects: [],
    }
    const { container } = render(<RoomContents location={location} onInteract={vi.fn()} />)
    expect(container.textContent).toContain('A torch flickers against the wall.')
})

test('skips hidden items and NPCs/objects without idle messages', () => {
    const location = {
        description: 'A quiet clearing.',
        items: [{ name: 'Hidden Key', hidden: true }],
        npcs: [{ name: 'Silent Watcher' }],
        objects: [{ name: 'Plain Rock' }],
    }
    render(<RoomContents location={location} onInteract={vi.fn()} />)
    expect(screen.queryByText(/Hidden Key/)).not.toBeInTheDocument()
    expect(screen.getByText('(Nothing else here...)')).toBeInTheDocument()
})

test('prefixes the entity name when the idle message starts with a space', () => {
    const location = {
        description: 'A quiet clearing.',
        items: [],
        npcs: [],
        objects: [{ name: 'Rusty Lever', idle_message: ' juts out of the wall, caked in rust.', hidden: false }],
    }
    const { container } = render(<RoomContents location={location} onInteract={vi.fn()} />)
    expect(container.textContent).toContain('Rusty Lever juts out of the wall, caked in rust.')
})
