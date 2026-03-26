# Heart of Virtue: Frontend Documentation

Complete reference for the React + Vite web UI for Heart of Virtue.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Architecture](#architecture)
3. [Project Structure](#project-structure)
4. [Components](#components)
5. [Hooks & State Management](#hooks--state-management)
6. [Styling](#styling)
7. [Running the Frontend](#running-the-frontend)
8. [Development](#development)
9. [Building & Deployment](#building--deployment)
10. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Prerequisites

- Node.js 16+ (includes npm)
- Frontend directory: `./frontend/`
- Backend running on http://localhost:5000

### Installation (First Time Only)

```powershell
# Navigate to frontend
cd .\frontend

# Install dependencies
npm install

# Output shows:
# added 400+ packages
# audited X packages in Xm Xs
```

### Running Development Server

```powershell
cd .\frontend
npm run dev

# Output:
# ✓ built in 0.23s
# ➜ Local: http://localhost:3000/
# ➜ Press h + enter to show help
```

Then open **http://localhost:3000** in your browser.

### Stopping the Server

```powershell
# In the terminal where npm run dev is running
Press Ctrl+C
```

---

## Architecture

### Technology Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Framework | React | 18.2.0 |
| Build Tool | Vite | 5.0.0 |
| Styling | Tailwind CSS | 3.4.0 |
| HTTP Client | Axios | 1.6.0 |
| Routing | React Router | 6.20.0 |
| Real-time | Socket.IO Client | 4.7.0 |

### High-Level Data Flow

```
User Interaction (Click Button)
        ↓
Component Event Handler
        ↓
Call Custom Hook (usePlayer, useCombat, etc)
        ↓
Hook calls API endpoint via Axios
        ↓
Backend returns JSON response
        ↓
Hook updates React state
        ↓
Component re-renders with new data
        ↓
User sees updated UI
```

### Frontend Architecture

```
┌─────────────────────────────────────┐
│  React Component Hierarchy          │
├─────────────────────────────────────┤
│                                     │
│  App.jsx (Root)                     │
│   ├─ BrowserRouter                 │
│   └─ Routes                         │
│       ├─ /login → LoginPage        │
│       └─ / → GamePage              │
│          ├─ LeftPanel (40%)        │
│          │  ├─ Narrative           │
│          │  ├─ PlayerStatus        │
│          │  ├─ Inventory           │
│          │  └─ ActionButtons       │
│          │                         │
│          └─ RightPanel (60%)       │
│             ├─ Battlefield        │
│             │  ├─ BattlefieldGrid │
│             │  └─ CombatLog       │
│             └─ WorldMap           │
│                                     │
├─────────────────────────────────────┤
│  Custom Hooks (State Management)    │
├─────────────────────────────────────┤
│  useAuth() - Authentication         │
│  usePlayer() - Player status        │
│  useCombat() - Combat state         │
│  useWorld() - Location & movement   │
│                                     │
├─────────────────────────────────────┤
│  API Layer (Axios)                  │
├─────────────────────────────────────┤
│  GET/POST requests to backend       │
│  Bearer token auth interceptor      │
│  Error handling & 401 redirect      │
│                                     │
└─────────────────────────────────────┘
```

---

## Project Structure

```
frontend/
├── index.html                    # HTML entry point
├── package.json                  # Dependencies & scripts
├── package-lock.json             # Locked dependency versions
├── vite.config.js                # Vite build configuration
├── tailwind.config.js            # Tailwind CSS theme
├── postcss.config.js             # PostCSS plugins
├── .env                          # Environment variables
├── .gitignore                    # Git ignore rules
│
└── src/
    ├── main.jsx                  # React DOM entry point
    ├── App.jsx                   # Root router component
    │
    ├── pages/                    # Page-level components
    │   ├── LoginPage.jsx         # Authentication
    │   └── GamePage.jsx          # Main game wrapper
    │
    ├── components/               # Reusable UI components
    │   ├── LeftPanel.jsx         # Left sidebar (40% width)
    │   ├── RightPanel.jsx        # Right sidebar (60% width)
    │   ├── PlayerStatus.jsx      # HP/Stats display
    │   ├── Inventory.jsx         # Item list
    │   ├── ActionButtons.jsx     # Command buttons
    │   ├── Battlefield.jsx       # Combat layout
    │   ├── BattlefieldGrid.jsx   # 10x10 combat grid
    │   ├── CombatLog.jsx         # Combat message log
    │   ├── WorldMap.jsx          # ASCII map view
    │   ├── FeedbackDialog.jsx    # In-game feedback form (→ GitHub Issues)
    │   └── LoadingScreen.jsx     # Loading state
    │
    ├── api/                      # API client
    │   ├── client.js             # Axios instance with auth
    │   └── endpoints.js          # API endpoint definitions
    │
    ├── hooks/                    # Custom React hooks
    │   └── useApi.js             # useAuth, usePlayer, useCombat, useWorld
    │
    └── styles/
        └── index.css             # Global styling & Tailwind
```

---

## Components

### Page Components

#### `LoginPage.jsx`
Authentication form with register toggle.

**Features:**
- Username/password input
- Register/Login toggle
- Error display
- Loading state during submission
- Redirect to game on success

**Props:** None (uses `useAuth` hook)

**Example:**
```jsx
import LoginPage from './pages/LoginPage'

<Route path="/login" element={<LoginPage />} />
```

---

#### `GamePage.jsx`
Main game interface wrapper.

**Features:**
- Fetches player, location, and combat data
- Manages exploration/combat mode
- Dual-panel layout

**Props:** None (uses hooks: `usePlayer`, `useWorld`, `useCombat`)

**Hooks Used:**
- `usePlayer()` - Get/update player data
- `useWorld()` - Get/update location and movement
- `useCombat()` - Get/update combat state

---

### Layout Components

#### `LeftPanel.jsx`
Left sidebar (40% width) with narrative, stats, and controls.

**Features:**
- Narrative description box
- Player status bar
- Inventory preview (expandable)
- Action button grid

**Props:**
```javascript
{
  player,        // Player object from usePlayer
  location,      // Location object from useWorld
  mode,          // 'exploration' or 'combat'
  onMove,        // Function to handle movement
  onRefetch      // Function to refetch data
}
```

**Example:**
```jsx
<LeftPanel
  player={player}
  location={location}
  mode={mode}
  onMove={move}
  onRefetch={refetchPlayer}
/>
```

---

#### `RightPanel.jsx`
Right sidebar (60% width) with battlefield or world map.

**Features:**
- Combat/Explore mode toggle
- Battlefield (during combat)
- World map (during exploration)
- Tab switching

**Props:**
```javascript
{
  mode,           // 'exploration' or 'combat'
  combat,         // Combat state object
  location,       // Current location
  onModeChange    // Function to change mode
}
```

---

### Game UI Components

#### `PlayerStatus.jsx`
Displays player statistics with health/fatigue bars.

**Features:**
- HP bar with color coding (green/yellow/red)
- Fatigue bar
- Level and experience tracking
- Stat display (STR/AGI/INT)

**Props:**
```javascript
{
  player    // Player object with hp, max_hp, fatigue, stats, etc
}
```

**Example:**
```jsx
<PlayerStatus player={player} />
```

---

#### `Inventory.jsx`
Expandable inventory display.

**Features:**
- Item list with quantities
- Close button
- Scroll overflow handling
- Empty state

**Props:**
```javascript
{
  items,      // Array of item objects
  onClose     // Function to close inventory
}
```

---

#### `ActionButtons.jsx`
Context-aware command button grid.

**Features:**
- Exploration mode: 2-column grid with movement/examine/inventory
- Combat mode: 3-column grid with attack/defend/skill/item/retreat
- Save button
- Hover effects

**Props:**
```javascript
{
  mode,           // 'exploration' or 'combat'
  location,       // Current location
  onMove,         // Movement callback
  onInventory     // Inventory toggle callback
}
```

---

#### `Battlefield.jsx`
Combat interface with grid and log.

**Features:**
- Tab selector (overview/enemies)
- Combat grid display
- Enemy list with HP bars
- Combat log integration

**Props:**
```javascript
{
  combat    // Combat state object with enemies and log
}
```

---

#### `BattlefieldGrid.jsx`
10x10 CSS grid for combat positioning.

**Features:**
- Grid-based rendering
- Enemy/player positioning
- Color-coded tiles
- Click handler support

**Props:**
```javascript
{
  combat,   // Combat state
  tab       // 'overview' or 'enemies'
}
```

---

#### `CombatLog.jsx`
Resizable, collapsible combat message log.

**Features:**
- Collapsible header
- Resizable (drag bottom edge)
- Color-coded message types (damage/heal/ability)
- Auto-scroll to latest
- Type-based filtering

**Props:**
```javascript
{
  log       // Array of log entry objects
}
```

**Log Entry Format:**
```javascript
{
  type: 'damage' | 'heal' | 'ability' | 'status',
  message: 'Human-readable message'
}
```

---

#### `WorldMap.jsx`
ASCII representation of game world.

**Features:**
- ASCII map display
- Legend with visited/discovered/unexplored markers
- Current position indicator
- Location name display

**Props:**
```javascript
{
  location  // Current location object
}
```

---

#### `LoadingScreen.jsx`
Animated loading screen.

**Features:**
- Title with pulse glow effect
- Animated bouncing dots
- Subtitle text

**No props required.**

---

### Component Usage Example

```jsx
// GamePage.jsx - How components are used together
export default function GamePage() {
  const { player, loading: playerLoading, refetch: refetchPlayer } = usePlayer()
  const { location, loading: worldLoading, move } = useWorld()
  const { combat, inCombat, fetchCombatStatus } = useCombat()
  const [mode, setMode] = useState('exploration')

  return (
    <div className="w-screen h-screen bg-dark-900 flex gap-2.5 p-2.5">
      <LeftPanel
        player={player}
        location={location}
        mode={mode}
        onMove={move}
        onRefetch={refetchPlayer}
      />
      <RightPanel
        mode={mode}
        combat={combat}
        location={location}
        onModeChange={setMode}
      />
    </div>
  )
}
```

---

## Hooks & State Management

### Custom Hooks

All hooks are defined in `src/hooks/useApi.js` and provide state management for different aspects of the game.

#### `useAuth()`

Manages user authentication (login, register, logout).

**Returns:**
```javascript
{
  isAuthenticated,    // Boolean - user is logged in
  loading,            // Boolean - auth state is loading
  login,              // Function(username, password) → Promise
  logout,             // Function() → Promise
  register            // Function(username, password) → Promise
}
```

**Usage:**
```jsx
const { isAuthenticated, loading, login, register, logout } = useAuth()

// Check auth status
if (loading) return <LoadingScreen />

// Login
const handleLogin = async (username, password) => {
  try {
    await login(username, password)
    // Redirects to game page
  } catch (error) {
    console.error('Login failed:', error)
  }
}
```

**How it works:**
1. On mount: Check localStorage for `authToken`
2. If token exists: `isAuthenticated = true`
3. On login: POST to `/api/auth/login`
4. Store returned `session_id` in localStorage
5. On logout: Remove token and POST to `/api/auth/logout`

---

#### `usePlayer()`

Manages player status and statistics.

**Returns:**
```javascript
{
  player,       // Player object (hp, stats, inventory, etc)
  loading,      // Boolean - data is loading
  error,        // String - error message if failed
  refetch       // Function() → Promise - manually refresh data
}
```

**Usage:**
```jsx
const { player, loading, error, refetch } = usePlayer()

if (loading) return <div>Loading player data...</div>

return (
  <div>
    <h1>{player.name}</h1>
    <div>Level {player.level}</div>
    <button onClick={refetch}>Refresh</button>
  </div>
)
```

**Endpoints called:**
- `GET /api/player/status` - Initial load and refetch
- `GET /api/player/inventory` - Item list
- `GET /api/player/equipment` - Equipped items
- `GET /api/player/stats` - Detailed stats

---

#### `useCombat()`

Manages combat state and actions.

**Returns:**
```javascript
{
  combat,                 // Combat state object
  loading,               // Boolean - action in progress
  inCombat,              // Boolean - currently in combat
  fetchCombatStatus,     // Function() → Promise - get status
  performAction          // Function(action, target) → Promise
}
```

**Usage:**
```jsx
const { combat, loading, inCombat, performAction } = useCombat()

// Attack an enemy
const handleAttack = async (enemyId) => {
  await performAction('attack', enemyId)
  // UI updates with new combat state
}

return (
  <div>
    {inCombat && (
      <button onClick={() => handleAttack('enemy_1')} disabled={loading}>
        Attack
      </button>
    )}
  </div>
)
```

**Endpoints called:**
- `GET /api/combat/status` - Get current combat state
- `POST /api/combat/start` - Initiate combat
- `POST /api/combat/action` - Perform action
- `POST /api/combat/end` - End combat

---

#### `useWorld()`

Manages player location and world exploration.

**Returns:**
```javascript
{
  location,     // Current location object (name, description, exits)
  loading,      // Boolean - location is loading
  error,        // String - error message if failed
  move,         // Function(direction) → Promise - move to adjacent tile
  refetch       // Function() → Promise - reload current location
}
```

**Usage:**
```jsx
const { location, loading, move, refetch } = useWorld()

// Move north
const handleMove = async () => {
  try {
    await move('north')
    // UI updates with new location
  } catch (error) {
    console.error('Movement failed:', error)
  }
}

return (
  <div>
    <h1>{location.name}</h1>
    <p>{location.description}</p>
    <button onClick={handleMove}>Go North</button>
  </div>
)
```

**Endpoints called:**
- `GET /api/world/location` - Current location details
- `POST /api/world/move` - Move to adjacent tile
- `GET /api/world/exits` - Available exits
- `GET /api/world/map` - Discovered map

---

### State Management Pattern

Each hook follows this pattern:

```javascript
export const useMyHook = () => {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  // Fetch data on mount
  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    try {
      setLoading(true)
      const response = await apiClient.get('/endpoint')
      setData(response.data.data)
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return { data, loading, error, refetch: fetchData }
}
```

---

## Styling

### Tailwind CSS Configuration

Tailwind is configured in `tailwind.config.js` with custom colors:

```javascript
{
  colors: {
    dark: {
      900: '#0a0a0a',  // Dark background
      800: '#1a1a2e',
      700: '#16213e',
    },
    accent: {
      orange: '#ff6600',  // Orange accent
      cyan: '#00ccff',    // Cyan accent
      lime: '#00ff88',    // Lime green
    }
  }
}
```

### Color Scheme

| Color | Hex | Use |
|-------|-----|-----|
| Lime | #00ff88 | Primary UI, text, borders |
| Cyan | #00ccff | Secondary info, stats |
| Orange | #ff6600 | Right panel, secondary borders |
| Dark | #0a0a0a | Main background |
| Dark-800 | #1a1a2e | Panel backgrounds |
| Red | #ff4444 | Damage, critical status |
| Green | #44ff44 | Healing, full health |

### Custom CSS Classes

Global custom classes in `src/styles/index.css`:

```css
/* Text colors */
.text-lime { color: #00ff88; }
.text-cyan { color: #00ccff; }
.text-orange { color: #ff6600; }

/* Background */
.bg-dark-panel { background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); }
.bg-lime-glow { background: linear-gradient(90deg, #00cc66 0%, #00ff88 100%); }

/* Effects */
.retro-glow { box-shadow: 0 10px 25px -5px rgba(0, 255, 136, 0.3); }
.retro-border { border-width: 2px; }

/* Animations */
.animate-pulse-glow { animation: pulse-glow 2s infinite; }
.animate-fade-in { animation: fade-in 0.3s ease-out; }

/* HP Bars */
.hp-bar { /* Base bar styling */ }
.hp-fill-full { /* Green fill for full health */ }
.hp-fill-partial { /* Yellow fill for partial health */ }
.hp-fill-critical { /* Red fill for low health */ }
```

### Using Styles

**Tailwind utility classes:**
```jsx
<div className="w-full h-screen bg-dark-900 flex gap-2.5 p-2.5">
  <div className="flex-1 rounded-lg border-2 border-lime">
    Content
  </div>
</div>
```

**Custom classes:**
```jsx
<div className="bg-dark-panel retro-glow">
  <span className="text-lime font-bold">Header</span>
</div>
```

**Inline styles (when needed):**
```jsx
<div style={{
  backgroundColor: '#0a0a0a',
  borderWidth: '2px',
  borderColor: '#00ff88'
}}>
  Content
</div>
```

---

## Running the Frontend

### Development Server

```powershell
cd .\frontend
npm run dev
```

**Features:**
- Hot module replacement (HMR) - Changes reflect instantly
- Source maps for debugging
- Port 3000 (configurable in `vite.config.js`)
- Proxy to backend API on `/api`

### Production Build

```powershell
cd .\frontend
npm run build
```

**Output:**
- `dist/` directory with minified files
- Optimized bundle (~50KB gzipped)
- Ready for static hosting

### Preview Production Build

```powershell
cd .\frontend
npm run preview
```

Opens built files in dev server for testing.

### Environment Variables

Frontend configuration in `.env`:

```bash
VITE_API_URL=http://localhost:5000/api
VITE_WS_URL=ws://localhost:5000
```

**Usage in code:**
```javascript
const apiUrl = import.meta.env.VITE_API_URL
```

---

## Development

### Development Workflow

1. **Start backend:**
   ```powershell
   .venv\Scripts\Activate.ps1
   python tools/run_api.py
   ```

2. **Start frontend (separate terminal):**
   ```powershell
   cd .\frontend
   npm run dev
   ```

3. **Open browser:**
   ```
   http://localhost:3000
   ```

4. **Make changes:**
   - Edit component files in `src/`
   - Changes auto-refresh in browser
   - Check browser console (F12) for errors

### Adding a New Component

1. Create file in `src/components/`:
   ```jsx
   // src/components/MyComponent.jsx
   export default function MyComponent({ prop1, prop2 }) {
     return <div>{prop1}</div>
   }
   ```

2. Import in parent component:
   ```jsx
   import MyComponent from '../components/MyComponent'
   ```

3. Use in JSX:
   ```jsx
   <MyComponent prop1="value" prop2={data} />
   ```

### Adding a New Page

1. Create file in `src/pages/`:
   ```jsx
   // src/pages/MyPage.jsx
   export default function MyPage() {
     return <div>My Page</div>
   }
   ```

2. Import in `App.jsx`:
   ```jsx
   import MyPage from './pages/MyPage'
   ```

3. Add route:
   ```jsx
   <Route path="/mypage" element={<MyPage />} />
   ```

### Adding a New Hook

1. Add function to `src/hooks/useApi.js`:
   ```javascript
   export const useMyHook = () => {
     const [data, setData] = useState(null)
     // ... implementation
     return { data }
   }
   ```

2. Import in component:
   ```jsx
   import { useMyHook } from '../hooks/useApi'
   ```

3. Use in component:
   ```jsx
   const { data } = useMyHook()
   ```

### Adding API Endpoints

1. Add to `src/api/endpoints.js`:
   ```javascript
   export const myFeature = {
     getStatus: () => apiClient.get('/myfeature/status'),
     doAction: (id) => apiClient.post('/myfeature/action', { id })
   }
   ```

2. Use in hook or component:
   ```javascript
   const response = await apiEndpoints.myFeature.getStatus()
   ```

### Debugging

**Browser DevTools (F12):**
- Network tab: See API requests/responses
- Console tab: See errors and logs
- React DevTools extension: Inspect component hierarchy

**VS Code Debugging:**
1. Install "Debugger for Chrome" extension
2. Create `.vscode/launch.json`:
   ```json
   {
     "version": "0.2.0",
     "configurations": [
       {
         "type": "chrome",
         "request": "attach",
         "name": "Attach",
         "port": 9222,
         "pathMapping": {
           "/": "${workspaceRoot}/frontend/src/",
           "/static": "${workspaceRoot}/frontend/dist/"
         }
       }
     ]
   }
   ```

---

## Building & Deployment

### Production Build

```powershell
cd .\frontend
npm run build

# Output:
# vite v5.0.0 building for production...
# ✓ 123 modules transformed.
# dist/index.html                 0.50 kB
# dist/assets/index.abc123.js     45.23 kB │ gzip: 15.2 kB
```

### Deploy to Static Hosting

The `dist/` directory contains everything needed:

```
dist/
├── index.html
├── assets/
│   ├── index.abc123.js      # Bundled JavaScript
│   └── index.def456.css     # Bundled CSS
└── favicon.ico
```

**Deploy options:**
- Netlify: Drag & drop `dist/` folder
- Vercel: Connect Git repository
- AWS S3: Upload `dist/` contents
- GitHub Pages: Push `dist/` to `gh-pages` branch

### Environment-Specific Configuration

**Development:**
```bash
VITE_API_URL=http://localhost:5000/api
```

**Production:**
```bash
VITE_API_URL=https://api.hearofvirtue.com/api
```

Rebuild for production with different env:

```powershell
# Create .env.production
echo "VITE_API_URL=https://api.example.com/api" | Out-File .env.production

# Build uses .env.production
npm run build
```

---

## Troubleshooting

### "Cannot find module" Error

**Cause:** Missing dependency or wrong import path

**Solution:**
1. Check import statement matches file name (case-sensitive)
2. Verify file exists in correct directory
3. Reinstall dependencies: `npm install`
4. Clear Vite cache: `rm -r node_modules/.vite`

### "Port 3000 already in use"

**Cause:** Another process using port 3000

**Solution:**
```powershell
# Find process using port 3000
Get-NetTCPConnection -LocalPort 3000

# Kill process
Stop-Process -Id {pid} -Force

# Or change port in vite.config.js
```

### Styling not applying

**Cause:** Tailwind classes not recognized or CSS not loaded

**Solution:**
1. Restart dev server
2. Clear browser cache (Ctrl+Shift+Delete)
3. Check class names are spelled correctly
4. Verify `src/styles/index.css` is imported in `main.jsx`

### Components not rendering

**Cause:** React error, wrong prop types, or import issue

**Solution:**
1. Open browser console (F12) - look for red errors
2. Check browser DevTools → React tab
3. Verify component receives required props
4. Check import statements

### API calls failing (401, 403, 500)

**Cause:** Backend issue or auth problem

**Solution:**
1. Verify backend is running
2. Check network tab in DevTools for actual response
3. Verify token is in localStorage (DevTools → Application → Storage)
4. Check `Authorization` header is being sent correctly

### Hot reload not working

**Cause:** Vite isn't detecting file changes

**Solution:**
1. Restart dev server
2. Make sure editing files in `src/` directory
3. Try hard refresh (Ctrl+Shift+R)
4. Check file isn't in `.gitignore`

### TypeScript/JSX Syntax Errors

**Cause:** ESLint or TypeScript misconfiguration

**Solution:**
1. Install ESLint: `npm install --save-dev eslint`
2. Initialize: `npx eslint --init`
3. Or disable ESLint temporarily for development

---

## Performance Optimization

### Bundle Analysis

```powershell
# Install analyzer
npm install --save-dev rollup-plugin-visualizer

# Build and analyze
npm run build
```

### Code Splitting

Vite automatically splits code at component boundaries:

```javascript
// Lazy load component
const HeavyComponent = lazy(() => import('./HeavyComponent'))
```

### Image Optimization

Place images in `public/`:

```jsx
<img src="/images/sprite.png" alt="Game sprite" />
```

Vite optimizes them during build.

---

## Production Checklist

Before deploying:

- [ ] No console errors (F12 → Console)
- [ ] All API endpoints functional
- [ ] Login/logout working
- [ ] Player data displays correctly
- [ ] Movement and combat work
- [ ] Images and CSS load properly
- [ ] No `console.error()` or `console.warn()`
- [ ] Build succeeds: `npm run build`
- [ ] Bundle size reasonable (~50KB gzipped)
- [ ] Backend API is deployed and accessible
- [ ] CORS configured for production domain
- [ ] Environment variables set correctly

---

## Support

**Documentation:**
- `API_DOCUMENTATION.md` - Backend API reference
- `src/components/` - Component source code
- Browser DevTools (F12) - Debugging

**Resources:**
- [React Docs](https://react.dev)
- [Vite Docs](https://vitejs.dev)
- [Tailwind Docs](https://tailwindcss.com)
- [Axios Docs](https://axios-http.com)
- [React Router Docs](https://reactrouter.com)

---

**Last Updated:** November 2025
**Status:** Production Ready ✅

