import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import RoomContents from './RoomContents'
import { colors } from '../styles/theme'
import { hexToRgb } from '../test/hexToRgb'

/**
 * Issue #558: a Rock Rumbler and Gorran read as the same kind of thing in the
 * room panel — same lime, same italics, and idle verbs ("is shuffling about"
 * vs "is bumbling about") that are equally benign. `is_hostile` is already on
 * the wire from `NPCSerializer.serialize`, and nothing here read it.
 */
describe('RoomContents — friend and foe (#558)', () => {
  const location = {
    description: 'A high ledge over the descent.',
    items: [],
    objects: [],
    npcs: [
      {
        name: 'Rock Rumbler',
        description: 'A boulder with legs.',
        idle_message: 'A Rock Rumbler is shuffling about.',
        is_hostile: true,
        aliases: [],
      },
      {
        name: 'Gorran',
        description: 'A dwarf.',
        idle_message: 'Gorran is bumbling about.',
        is_hostile: false,
        aliases: [],
      },
    ],
  }

  const lineFor = (text) => screen.getByText(text, { exact: false }).closest('[data-testid="room-content-line"]')

  it('labels the hostile NPC with a word, not only a colour', () => {
    render(<RoomContents location={location} onInteract={vi.fn()} />)
    const chips = screen.getAllByText(/HOSTILE/)
    expect(chips).toHaveLength(1)
    expect(chips[0].closest('[data-testid="room-content-line"]')).toHaveTextContent('Rock Rumbler')
  })

  it('accents the hostile line and leaves the non-hostile one alone', () => {
    render(<RoomContents location={location} onInteract={vi.fn()} />)
    expect(lineFor('is shuffling about').style.color).toBe(hexToRgb(colors.danger))
    expect(lineFor('is bumbling about').style.color).not.toBe(hexToRgb(colors.danger))
  })

  it('marks nothing when the payload carries no hostility at all', () => {
    render(
      <RoomContents
        location={{
          description: 'A quiet room.',
          items: [],
          objects: [],
          npcs: [{ name: 'Stranger', idle_message: 'A Stranger waits here.', aliases: [] }],
        }}
        onInteract={vi.fn()}
      />
    )
    expect(screen.queryByText(/HOSTILE/)).toBeNull()
  })
})
