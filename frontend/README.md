# Heart of Virtue - Web UI Frontend

A React + Vite web UI for the Heart of Virtue RPG, designed to match the retro terminal aesthetic of the game.

## Architecture

- **Framework**: React 18 with Vite
- **Styling**: Tailwind CSS
- **API Communication**: Axios with interceptors for auth
- **Real-time Updates**: Socket.IO (optional)
- **Routing**: React Router v6

## Project Structure

```
frontend/
├── src/
│   ├── api/
│   │   ├── client.js      # Axios client with interceptors
│   │   └── endpoints.js   # API endpoint definitions
│   ├── components/
│   │   ├── LeftPanel.jsx                 # Narrative & controls
│   │   ├── RightPanel.jsx                # Battlefield/Map view
│   │   ├── Battlefield.jsx               # Combat grid
│   │   ├── CombatLog.jsx                 # Resizable combat log
│   │   ├── WorldMap.jsx                  # Exploration map
│   │   ├── PlayerStatus.jsx              # HP/stats display
│   │   ├── Inventory.jsx                 # Item list
│   │   ├── ActionButtons.jsx             # Command buttons
│   │   ├── MobileTabBar.jsx              # Bottom tab bar for <768px
│   │   ├── CollapsibleRoomDescription.jsx # Collapsible tile description
│   │   └── LoadingScreen.jsx             # Loading state
│   ├── hooks/
│   │   ├── useApi.js      # Custom hooks for API calls
│   │   └── useMobile.js   # matchMedia breakpoint hook (<768px)
│   ├── pages/
│   │   ├── LoginPage.jsx  # Auth page
│   │   └── GamePage.jsx   # Main game interface
│   ├── styles/
│   │   └── index.css      # Global + Tailwind styles
│   ├── App.jsx            # Root component with routing
│   └── main.jsx           # React entry point
├── public/                # Static assets
├── index.html            # HTML entry point
├── package.json
├── vite.config.js        # Vite configuration
├── tailwind.config.js    # Tailwind theme
└── postcss.config.js     # PostCSS config
```

## Features

### Current Implementation
- ✅ Login/Registration UI
- ✅ Left panel with narrative box, player status, inventory
- ✅ Right panel with battlefield grid and map view
- ✅ Combat log with resizable height
- ✅ Action buttons (exploration & combat)
- ✅ Responsive grid layout (desktop + tablet + mobile)
- ✅ Mobile bottom tab bar navigation (<768px viewports) — `MobileTabBar` + `useMobile`
- ✅ Collapsible room description on mobile and desktop — `CollapsibleRoomDescription`
- ✅ Touch-optimized inputs (44px targets, no double-tap delay, no iOS zoom)
- ✅ Retro terminal styling with lime/cyan/orange colors
- ✅ Auth token management

### Planned Features
- ⏳ Real-time combat updates via WebSocket
- ⏳ Equipment/skill tree UI
- ⏳ NPC dialogue system
- ⏳ Quest log and tracking
- ⏳ Save/load game UI
- ⏳ Settings and preferences

## Setup & Development

### Prerequisites
- Node.js 18+
- npm or yarn
- Backend API running on localhost:5000

### Installation

```bash
cd frontend
npm install
```

### Development Server

```bash
npm run dev
```

Starts Vite dev server on http://localhost:3000
- Hot module replacement enabled
- Proxy to backend API at http://localhost:5000

### Build for Production

```bash
npm run build
```

Outputs optimized build to `dist/` directory.

### Preview Production Build

```bash
npm run preview
```

## API Integration

### Authentication Flow

1. User submits credentials on LoginPage
2. `useAuth.register()` or `useAuth.login()` called
3. API returns `session_id`
4. Token stored in localStorage
5. Axios client automatically includes `Authorization: Bearer {token}` header
6. On 401 response, token cleared and user redirected to login

### Component Integration Pattern

```jsx
import { usePlayer } from '../hooks/useApi'

export function MyComponent() {
  const { player, loading, error, refetch } = usePlayer()
  
  return (
    <>
      {loading && <p>Loading...</p>}
      {error && <p>Error: {error}</p>}
      {player && <p>HP: {player.hp}</p>}
    </>
  )
}
```

### Adding New API Endpoints

1. Add method to `src/api/endpoints.js`
2. Create hook in `src/hooks/useApi.js` if needed
3. Use in component with hook or direct `apiEndpoints` call

## Styling

### Color Palette
- **Primary (Lime)**: #00ff88
- **Secondary (Cyan)**: #00ccff
- **Accent (Orange)**: #ff6600
- **Dark Background**: #0a0a0a
- **Panel Background**: #1a1a2e

### Custom Utility Classes
```css
.text-lime          /* Lime green text */
.text-cyan          /* Cyan text */
.text-orange        /* Orange text */
.bg-dark-panel      /* Dark gradient panel */
.bg-lime-glow       /* Lime gradient background */
.btn-primary        /* Primary button style */
.btn-secondary      /* Secondary button style */
.hp-bar             /* Health bar container */
```

## Browser Support

- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)

## Environment Variables

```
VITE_API_URL        # Backend API base URL (default: http://localhost:5000/api)
VITE_WS_URL         # WebSocket URL for real-time updates (default: ws://localhost:5000)
```

## Troubleshooting

### CORS Errors
- Ensure backend has CORS enabled
- Check API proxy configuration in vite.config.js

### Auth Token Issues
- Check localStorage for `authToken` key
- Verify API returns `session_id` in response
- Check browser console for 401 errors

### Styling Not Applying
- Verify tailwind.config.js is correctly pointing to src files
- Run `npm run build` to check for production issues
- Clear browser cache (Ctrl+Shift+Delete)

## Deployment

### To Vercel
```bash
npm i -g vercel
vercel
```

### To Docker
```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build
EXPOSE 3000
CMD ["npm", "run", "preview"]
```

## Contributing

1. Create feature branch: `git checkout -b feature/my-feature`
2. Make changes following component structure
3. Test with dev server: `npm run dev`
4. Commit with descriptive message
5. Push and create PR

## License

Part of Heart of Virtue project.

