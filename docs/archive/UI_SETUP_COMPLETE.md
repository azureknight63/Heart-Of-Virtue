# Heart of Virtue - UI Setup Complete

## 🎮 Frontend Setup Summary

A complete React + Vite web UI has been created for Heart of Virtue, matching the retro terminal aesthetic of the UI mockup.

## 📁 New Directory Structure

```
Heart-Of-Virtue/
├── frontend/                    # NEW: Web UI
│   ├── src/
│   │   ├── api/                # API client and endpoints
│   │   ├── components/         # Reusable UI components
│   │   ├── hooks/              # Custom React hooks
│   │   ├── pages/              # Page components (login, game)
│   │   ├── styles/             # Global CSS + Tailwind
│   │   ├── App.jsx             # Root component
│   │   └── main.jsx            # React entry
│   ├── public/                 # Static assets
│   ├── index.html              # HTML entry point
│   ├── package.json            # Dependencies
│   ├── vite.config.js          # Vite build config
│   ├── tailwind.config.js      # Tailwind theme
│   └── README.md               # Frontend-specific docs
├── src/                        # Game engine (existing)
├── tests/                      # Tests (existing)
└── run_api.py                  # Flask API entry (existing)
```

## 🚀 Quick Start

### 1. Install Frontend Dependencies

```powershell
cd .\frontend
npm install
```

### 2. Start Both Backend & Frontend

**Terminal 1 - Backend API:**
```powershell
.venv\Scripts\Activate.ps1
python run_api.py
# Runs on http://localhost:5000
```

**Terminal 2 - Frontend Dev Server:**
```powershell
cd .\frontend
npm run dev
# Runs on http://localhost:3000
```

### 3. Access the Game

Open browser to **http://localhost:3000**

## 📦 Key Features

### Components Included

✅ **Authentication**
- Login/Registration form with validation
- Session token management
- Auto-redirect on auth failure

✅ **Game Interface (Main)**
- Left panel: Narrative box, player status, inventory
- Right panel: Battlefield (combat) or World map (exploration)
- Action buttons for exploration & combat
- Resizable combat log

✅ **Combat System**
- 10x10 battlefield grid
- Enemy list with HP bars
- Combat log with message filtering
- Tab switching (overview/enemies)

✅ **Exploration**
- ASCII world map display
- Location narrative box
- Directional movement buttons

✅ **Player Stats**
- HP/Fatigue bars with colors
- Level and EXP tracking
- Core stats (STR/AGI/INT)
- Equipment display

### Styling

- **Color Theme**: Lime (#00ff88), Cyan (#00ccff), Orange (#ff6600), Dark (#0a0a0a)
- **Typography**: Courier New (mono), EB Garamond (serif for narrative)
- **Responsive**: Flexible grid layout
- **Animations**: Pulse glow, fade-in transitions

## 🔌 API Integration

The frontend automatically connects to your Flask API:

```
Frontend (http://localhost:3000)
         ↓ (Axios with Bearer token)
Backend API (http://localhost:5000/api)
         ↓
Game Engine & Database
```

**Endpoints Used:**
- `POST /api/auth/register` - Account creation
- `POST /api/auth/login` - User authentication
- `GET /api/player/status` - Player data
- `GET /api/world/location` - Current location
- `POST /api/world/move` - Movement
- `GET /api/combat/status` - Combat state
- `POST /api/combat/action` - Combat actions

See `frontend/src/api/endpoints.js` for full list.

## 📝 Development Guide

### Adding a New Component

```jsx
// frontend/src/components/MyComponent.jsx
export default function MyComponent({ prop1, prop2 }) {
  return (
    <div className="bg-dark-panel border-2 border-lime rounded p-4">
      {/* Content */}
    </div>
  )
}

// Use in parent
import MyComponent from '../components/MyComponent'

<MyComponent prop1="value" prop2={123} />
```

### Using API Hooks

```jsx
import { usePlayer, useCombat, useWorld } from '../hooks/useApi'

export function MyGameComponent() {
  const { player, loading, refetch } = usePlayer()
  const { combat, performAction } = useCombat()
  const { location, move } = useWorld()
  
  return (
    <>
      <p>HP: {player?.hp}</p>
      <button onClick={() => move('north')}>Go North</button>
    </>
  )
}
```

### Styling with Tailwind

```jsx
<div className="bg-dark-panel border-2 border-lime rounded-lg p-4 retro-glow">
  <p className="text-lime text-sm font-bold">Title</p>
  <p className="text-cyan text-xs">Description</p>
</div>
```

### Custom CSS Classes

See `frontend/src/styles/index.css` for:
- `.text-lime`, `.text-cyan`, `.text-orange`
- `.bg-dark-panel`, `.bg-lime-glow`, `.bg-orange-glow`
- `.btn-primary`, `.btn-secondary`, `.btn-danger`
- `.hp-bar`, `.hp-fill-*` (health bar styling)
- `.status-badge`, `.status-*` (status indicators)

## 🔧 Build & Deployment

### Development Build
```bash
npm run dev        # Hot-reload server
```

### Production Build
```bash
npm run build      # Creates dist/ folder
npm run preview    # Test production build locally
```

### Docker Deployment
```dockerfile
# Dockerfile
FROM node:18-alpine
WORKDIR /app
COPY frontend/package*.json ./
RUN npm install --production
COPY frontend . .
RUN npm run build
ENV VITE_API_URL=https://api.yourdomain.com
CMD ["npm", "run", "preview"]
```

## 🧪 Testing

### Unit Tests (via Vitest - to add)
```bash
npm run test
```

### Manual Testing Checklist
- [ ] Login with credentials works
- [ ] Player stats display correctly
- [ ] Movement buttons update location
- [ ] Combat transitions work
- [ ] Inventory displays items
- [ ] Resizable combat log works
- [ ] Tab switching works
- [ ] Responsive on different screen sizes

## 📱 Browser Compatibility

- ✅ Chrome/Edge 90+
- ✅ Firefox 88+
- ✅ Safari 14+
- ❌ IE 11 (not supported)

## 🎨 Design Decisions

1. **React + Vite**: Fast development, minimal config
2. **Tailwind CSS**: Rapid prototyping with utility classes
3. **Axios**: Simplified API calls with interceptor support
4. **Custom Hooks**: Reusable API logic across components
5. **Component-Based**: Easy to maintain and extend
6. **Retro Aesthetic**: Matches terminal-based game style

## 📚 File Reference

### Frontend Files
- `frontend/src/App.jsx` - Main app with routing
- `frontend/src/pages/LoginPage.jsx` - Authentication
- `frontend/src/pages/GamePage.jsx` - Main game view
- `frontend/src/components/LeftPanel.jsx` - Narrative/controls
- `frontend/src/components/RightPanel.jsx` - Battle/map
- `frontend/src/api/endpoints.js` - API definitions
- `frontend/src/hooks/useApi.js` - Custom hooks

### Configuration Files
- `frontend/package.json` - Dependencies
- `frontend/vite.config.js` - Vite settings
- `frontend/tailwind.config.js` - Tailwind theme
- `frontend/.env` - Environment variables
- `frontend/tsconfig.json` - TypeScript (if using TS)

## 🔮 Next Steps

1. **Integrate WebSocket** for real-time updates
   - See `frontend/README.md` for Socket.IO setup

2. **Add Equipment/Skill UI**
   - Create `EquipmentPanel.jsx`
   - Add to RightPanel tabs

3. **Implement NPC Dialogue**
   - Create `DialogueModal.jsx`
   - Wire to `/api/npc/talk` endpoint

4. **Add Quest System**
   - Create `QuestLog.jsx`
   - Wire to `/api/quests/list` endpoint

5. **Build Save/Load UI**
   - Create `SaveManager.jsx`
   - Implement save list and load functionality

6. **Add Settings & Preferences**
   - Font switcher (already in mockup.html)
   - Theme selector
   - Audio/visual settings

## 🐛 Troubleshooting

### Port Already in Use
```powershell
# Kill process on port 3000
Get-Process -Id (Get-NetTCPConnection -LocalPort 3000).OwningProcess | Stop-Process
```

### CORS Error
- Check Flask API has `CORS` enabled
- Verify `vite.config.js` proxy settings
- Check `Access-Control-*` headers in API response

### Auth Token Lost
- Check browser localStorage
- Verify API returns `session_id`
- Check axios interceptors in `client.js`

### Styles Not Loading
- Clear browser cache (F12 → Application → Clear Storage)
- Rebuild: `npm run build`
- Check browser console for CSS errors

## 📞 Support

For issues or questions:
1. Check `frontend/README.md` for detailed docs
2. Review component code in `src/components/`
3. Check API integration in `src/api/`
4. Test API directly with Postman/curl

---

**Frontend Setup:** ✅ Complete
**Status:** Ready for development
**Next Milestone:** WebSocket integration for real-time combat
