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

    // Check if "wooden chest" is rendered as a link
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

    // "words inscribed" should be a link (there are two occurrences)
    const links = screen.getAllByText('words inscribed')
    expect(links.length).toBe(2)
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
                hidden: false
            },
            {
                name: 'Large Switch',
                aliases: ['depression'],
                hidden: false
            }
        ]
    }

    render(<RoomContents location={location} onInteract={onInteract} />)

    // "small depression" should match the first entity
    const smallLink = screen.getByText('small depression')
    fireEvent.click(smallLink)
    expect(onInteract).toHaveBeenCalledWith(expect.objectContaining({ name: 'Small Switch' }))

    // "depression" (the second one) should match the second entity
    const largeLink = screen.getByText('depression')
    fireEvent.click(largeLink)
    expect(onInteract).toHaveBeenCalledWith(expect.objectContaining({ name: 'Large Switch' }))
})
