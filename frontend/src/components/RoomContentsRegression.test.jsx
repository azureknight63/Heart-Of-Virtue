import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import RoomContents from './RoomContents'
import React from 'react'

describe('RoomContents Regression', () => {
    const mockLocation = {
        description: 'This is a room with a depression.',
        items: [],
        npcs: [],
        objects: [{ id: '1', name: 'Wall Depression', idle_message: 'There is a depression here.', aliases: ['depression'] }]
    }

    it('should not render clickable links in the room description but should in announce messages', () => {
        const { container } = render(<RoomContents location={mockLocation} onInteract={vi.fn()} />)

        // Find the room description paragraph
        // It's the first <p> tag
        const descriptionP = container.querySelector('p')
        expect(descriptionP.textContent).toBe('This is a room with a depression.')

        // Check if there are any spans (links) inside the description
        const linksInDescription = descriptionP.querySelectorAll('span')
        expect(linksInDescription.length).toBe(0)

        // Now check for the announce message
        // It should be in a div, and should contain exactly "There is a depression here."
        // and SHOULD have at least one span (the link)
        const divs = container.querySelectorAll('div')
        let announceMessageDiv = null
        for (const div of divs) {
            if (div.textContent === 'There is a depression here.' && div.querySelector('span')) {
                announceMessageDiv = div
                break
            }
        }

        expect(announceMessageDiv).not.toBeNull()
        const linksInAnnounce = announceMessageDiv.querySelectorAll('span')
        expect(linksInAnnounce.length).toBeGreaterThan(0)
    })
})
