import EventDialog from './EventDialog'

/**
 * EventManager - Wrapper component for event-related UI rendering
 * 
 * Responsibilities:
 * - Render EventDialog when currentEvent exists
 * - Pass event state and handlers to dialog
 * 
 * @param {Object} props - Component props
 * @param {Object} props.currentEvent - Current event object to display
 * @param {Array} props.eventHistory - Array of past event text
 * @param {Function} props.onClose - Event close handler
 * @param {Function} props.onSubmitInput - Event input submission handler
 */
export default function EventManager({ currentEvent, eventHistory, onClose, onSubmitInput }) {
    if (!currentEvent) {
        return null
    }

    return (
        <EventDialog
            event={currentEvent}
            history={eventHistory}
            onClose={onClose}
            onSubmitInput={onSubmitInput}
        />
    )
}
