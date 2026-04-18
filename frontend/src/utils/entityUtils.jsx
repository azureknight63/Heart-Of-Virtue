import { colors } from '../styles/theme'

/**
 * cleanTerminalLineBreaks - Clean up excessive/awkward line breaks from terminal-mode text
 * Converts hard line breaks to soft word wrapping for better web display
 * Preserves intentional paragraph breaks (double newlines)
 */
export const cleanTerminalLineBreaks = (text) => {
    if (!text) return text

    // Replace multiple consecutive newlines with a special marker to preserve paragraph breaks
    let cleaned = text.replace(/\n\n+/g, '\n~~~PARA_BREAK~~~\n')

    // Replace single newlines with spaces (soft wrapping)
    cleaned = cleaned.replace(/\n(?!~~~)/g, ' ')

    // Restore paragraph breaks
    cleaned = cleaned.replace(/\n~~~PARA_BREAK~~~\n/g, '\n\n')

    return cleaned
}

/**
 * getEntityColor - Returns the appropriate color for an entity type from the theme
 */
export const getEntityColor = (type) => {
    switch (type?.toLowerCase()) {
        case 'npc':
            return colors.entities.npc
        case 'item':
            return colors.entities.item
        case 'object':
        default:
            return colors.entities.object
    }
}

/**
 * renderTextWithLinks - Utility to wrap entity names and aliases in clickable spans
 * @param {string} text - The text to process
 * @param {Array} entities - List of interactable entities
 * @param {Function} onInteract - Callback when an entity link is clicked
 * @param {Object} preferredEntity - Entity to prioritize for matching
 * @returns {Array} Array of strings and JSX elements
 */
export const renderTextWithLinks = (text, entities = [], onInteract = null, preferredEntity = null) => {
    if (!text) return null
    if (!entities || entities.length === 0) return text

    // Create a mapping of all matchable terms (names and aliases) to their entities
    const termMap = []
    entities.forEach(entity => {
        if (!entity) return

        // Add the name
        termMap.push({ term: entity.name, entity })

        // Add aliases if they exist
        if (entity.aliases && Array.isArray(entity.aliases)) {
            entity.aliases.forEach(alias => {
                termMap.push({ term: alias, entity })
            })
        }
    })

    // Sort terms by length descending to avoid partial matches
    termMap.sort((a, b) => b.term.length - a.term.length)

    // Create a regex that matches any of the terms
    const terms = termMap.map(t => t.term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
    if (terms.length === 0) return text

    const regex = new RegExp(`(${terms.join('|')})`, 'gi')
    const parts = text.split(regex)

    return parts.map((part, i) => {
        let entity = null

        // 1. Check if it matches preferredEntity's name or aliases
        if (preferredEntity) {
            const isMatch = part.toLowerCase() === preferredEntity.name.toLowerCase() ||
                (preferredEntity.aliases && preferredEntity.aliases.some(a => a.toLowerCase() === part.toLowerCase()))
            if (isMatch) {
                entity = preferredEntity
            }
        }

        // 2. Otherwise search in termMap
        if (!entity) {
            const match = termMap.find(t => t.term.toLowerCase() === part.toLowerCase())
            if (match) {
                entity = match.entity
            }
        }

        if (entity) {
            const description = entity.description || `Interact with ${entity.name}`
            const truncatedDesc = description.length > 150
                ? `${description.substring(0, 147)}...`
                : description

            return (
                <span
                    key={i}
                    onClick={(e) => {
                        e.stopPropagation();
                        onInteract && onInteract(entity);
                    }}
                    style={{
                        cursor: 'pointer',
                        textDecoration: 'underline',
                        fontWeight: 'bold',
                        color: getEntityColor(entity.type)
                    }}
                    title={truncatedDesc}
                >
                    {part}
                </span>
            )
        }
        return part
    })
}
