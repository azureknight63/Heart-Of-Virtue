# Interactive Event Input System - Implementation Summary

## Overview
Implemented a comprehensive interactive event input system that allows the backend to request user input from the frontend for game events. The system supports three input types: choice buttons, text input, and number input, with keyboard shortcuts, validation, and sanitization.

## Architecture

### Backend Changes

#### 1. Event Serialization (`src/api/serializers/event_serializer.py`)
- **Added `serialize_with_input()` method**: Detects events that require input and serializes their input requirements
- **Added `_detect_input_requirement()` helper**: Checks if an event needs input by examining `needs_input` flag or event class name against whitelist
- **Added `_infer_input_type()` helper**: Returns input type ('choice', 'text', 'number') based on event properties
- **Supported event classes**: WhisperingStatue, StMichael, DialogueChoice, MerchantNegotiation, PuzzleEvent, RiddleEvent

#### 2. Event Classes (`src/story/effects.py`)
- **WhisperingStatue**: Updated with input metadata
  - `needs_input = True`
  - `input_type = "choice"`
  - `input_options`: 3 riddle answer choices
  - Modified `process(user_input=None)` to accept optional user_input parameter
  - Falls back to input() for backward compatibility

- **StMichael**: Updated with input metadata
  - `needs_input = True`
  - `input_type = "choice"`
  - `_generate_weapon_choices()`: Randomly selects 3 weapons from 12 options at init time
  - `input_options`: Dynamic weapon choices with value/label pairs
  - Modified `process(user_input=None)` to accept optional user_input parameter
  - Includes input validation with bounds checking

#### 3. Game Service (`src/api/services/game_service.py`)
- **Updated `trigger_tile_events()` method**:
  - Now accepts `session_data` parameter
  - Calls `EventSerializer.serialize_with_input()` to detect input-requiring events
  - Generates unique event_id (UUID) for pending events
  - Stores pending events in `session.data["pending_events"]` without processing them
  - Returns event data with `needs_input=true` flag
  - Non-input events processed normally with output capture

- **Updated `move_player()` method**:
  - Now accepts `session_data` parameter
  - Passes session_data to `trigger_tile_events()`

- **Added `process_event_input()` method**:
  - Validates event_id exists in pending_events
  - Processes event with user_input parameter
  - Captures output with StringIO and patches
  - Removes event from pending_events after processing
  - Returns result with output_text

#### 4. World Routes (`src/api/routes/world.py`)
- **Updated `/world/move` endpoint**:
  - Passes `session.data` to `game_service.move_player()`
  - Saves session after movement to persist pending events

- **Added `/world/events/input` endpoint**:
  - Accepts `event_id` and `user_input` in request body
  - Calls `sanitize_event_input()` for validation
  - Calls `game_service.process_event_input()` to process event
  - Returns success/error response with optional output_text

#### 5. Input Sanitizer (`src/api/utils/input_sanitizer.py`)
- **`sanitize_event_input()` function**:
  - Type-specific validation and sanitization
  - **Choice input**: Validates against whitelist of allowed options
  - **Number input**: Parses as integer, checks bounds (min/max values)
  - **Text input**: 
    - Max 500 characters
    - Uses bleach.clean() to strip HTML/script tags
    - Removes null bytes
    - Validates non-empty
  - Returns tuple of (sanitized_input, validation_error)

### Frontend Changes

#### 6. EventDialog Component (`frontend/src/components/EventDialog.jsx`)
Complete rewrite with the following features:
- **Props**: `event`, `onClose`, `onSubmitInput`
- **State management**: Tracks displayedText, input values, validation messages, selected choice
- **Input types**:
  - **Choice buttons**: Dynamic grid layout, keyboard shortcuts (1-9), visual selection feedback
  - **Text input**: Textarea with character counter (500 max), real-time validation
  - **Number input**: Input field with +/- buttons, min/max bounds enforcement
- **Keyboard shortcuts**:
  - Keys 1-9: Select choice options (up to 9)
  - Enter: Submit input
  - Visual feedback for keypresses
- **Validation display**:
  - Yellow warnings for non-critical issues
  - Red errors for invalid input
  - Real-time character count for text input
- **Styling**:
  - Dark background (#0a140a)
  - Green accents (#00cc66, #00ff88)
  - Monospace font
  - Glowing borders and shadows

#### 7. GamePage (`frontend/src/pages/GamePage.jsx`)
- **Added `handleEventInput()` function**:
  - Submits user input to `/api/world/events/input`
  - Handles success/error responses
  - Shows result output in new event dialog if present
  - Refetches player and world state after processing
- **Updated EventDialog usage**:
  - Changed from `onChoice` to `onSubmitInput` callback
  - Passes `handleEventInput` function

### Dependencies
- **Added to `requirements.txt`**: `bleach>=6.0.0` for HTML sanitization

## Data Flow

1. **Player moves to tile with event**:
   - `POST /api/world/move`
   - `game_service.move_player()` calls `trigger_tile_events(session.data)`
   - Event detected as input-requiring
   - Event stored in `session.data["pending_events"][event_id]`
   - Response includes event with `needs_input: true`, `input_type`, `input_options`

2. **Frontend displays event**:
   - EventDialog renders with appropriate input UI (choice/text/number)
   - User interacts with input components
   - Keyboard shortcuts enabled (1-9, Enter)

3. **User submits input**:
   - Client-side validation in EventDialog
   - `POST /api/world/events/input` with `{event_id, user_input}`
   - Server-side sanitization in `input_sanitizer.py`
   - Event processing in `game_service.process_event_input()`
   - Output captured and returned
   - Event removed from pending_events

4. **Result displayed**:
   - If output_text present, show in new event dialog
   - Player/world state refetched
   - Frontend updates

## Security Features
- **Client-side validation**: Real-time feedback, max length checks
- **Server-side sanitization**: bleach.clean() for text, whitelist for choices, bounds for numbers
- **Session isolation**: Events stored per-session, not globally
- **Input bounds**: Min/max values for numbers, character limits for text

## Backward Compatibility
- Events can still call `input()` directly if not in API mode
- `process(user_input=None)` signature allows both modes
- Non-input events processed as before
- Legacy event choice handling preserved for combat transitions

## Testing Recommendations
1. Test WhisperingStatue event on Windswept Ridge (4,3)
2. Test StMichael event (location TBD)
3. Verify keyboard shortcuts (1-9, Enter)
4. Test validation messages (empty input, too long, out of bounds)
5. Test XSS prevention with `<script>alert('test')</script>` in text input
6. Test session isolation (multiple players shouldn't see each other's events)
7. Test event queue handling (multiple events in sequence)

## Future Enhancements
- Add timeout for input (currently none per requirements)
- Add input history (currently none per requirements)
- Support multi-step events with multiple input stages
- Add autocomplete for text inputs with suggestions
- Add custom validation rules per event type
- Add rich text formatting in event output
- Add sound effects for input submission/validation

## Files Modified
1. `src/api/serializers/event_serializer.py` - Added input detection and serialization
2. `src/story/effects.py` - Updated WhisperingStatue and StMichael classes
3. `src/api/services/game_service.py` - Updated event triggering and added input processing
4. `src/api/routes/world.py` - Updated move endpoint, added event input endpoint
5. `src/api/utils/input_sanitizer.py` - **NEW FILE** - Input sanitization utility
6. `frontend/src/components/EventDialog.jsx` - Complete rewrite for input system
7. `frontend/src/pages/GamePage.jsx` - Updated event handling flow
8. `requirements.txt` - Added bleach dependency
