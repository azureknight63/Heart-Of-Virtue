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
