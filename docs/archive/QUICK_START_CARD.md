# Web UI Setup - Quick Reference Card

## 🎯 TL;DR - Start Here

### 1. Install & Run (2 terminals)

**Terminal A - Backend:**
```powershell
.venv\Scripts\Activate.ps1
python tools/run_api.py
```

**Terminal B - Frontend:**
```powershell
cd .\frontend
npm install     # First time only
npm run dev
```

### 2. Open Browser
```
http://localhost:3000
```

### 3. Login
Use any username/password to test

---

## 📁 What's New

```
frontend/           ← NEW WEB UI
├── src/            ← React components
├── package.json    ← Dependencies
├── vite.config.js  ← Build config
└── ...
```

**Total**: 25 new files, ~44 KB source code

---

## 🎮 Key Components

| Component | Purpose |
|-----------|---------|
| LoginPage | User authentication |
| GamePage | Main game interface |
| LeftPanel | Narrative + controls |
| RightPanel | Battle/map view |
| Battlefield | Combat grid |
| WorldMap | Exploration map |

---

## 🔌 API Integration

| Endpoint | Usage |
|----------|-------|
| `POST /api/auth/login` | User auth |
| `GET /api/player/status` | Player data |
| `GET /api/world/location` | Current location |
| `POST /api/world/move` | Movement |
| `GET /api/combat/status` | Combat state |
| See `src/api/endpoints.js` for all 18+ |

---

## 🎨 Color Palette

```
Primary  → Lime (#00ff88)
Secondary→ Cyan (#00ccff)
Accent   → Orange (#ff6600)
Dark     → #0a0a0a - #16213e
```

---

## 🆘 Troubleshooting

| Problem | Fix |
|---------|-----|
| Port 3000 in use | Change in vite.config.js |
| Can't login | Check backend is running |
| No data shows | Check API returns correct format |
| Styles broken | Clear cache, rebuild |
| Auth fails | Check localStorage has token |

---

## 📚 Full Documentation

| File | Read For |
|------|----------|
| `UI_SETUP_COMPLETE.md` | Full setup guide |
| `FRONTEND_SETUP_CHECKLIST.md` | Feature list |
| `frontend/README.md` | Dev guide |
| `BACKEND_API_INTEGRATION.md` | API contract |

---

## ⚡ Development Tips

### Hot Reload
Changes auto-refresh browser during `npm run dev`

### Debugging
Open DevTools (F12) → Console to see:
- Network requests
- Auth token issues
- API errors

### Adding a Component
1. Create `src/components/MyComponent.jsx`
2. Import in parent component
3. Use with props

### Styling
Use Tailwind classes:
```jsx
<div className="bg-dark-panel border-2 border-lime rounded p-4">
  <p className="text-lime font-bold">Title</p>
</div>
```

---

## 🚀 Production Build

```powershell
npm run build    # Creates dist/
npm run preview  # Test locally
```

Deploy `dist/` folder to web server

---

## 📊 File Overview

- **25 files** created
- **44 KB** source code
- **250 MB** with dependencies (npm install)
- **~50 KB** production build (minified + gzipped)

---

## ✅ What's Working

- ✅ Login/register
- ✅ Player status display
- ✅ Left panel with controls
- ✅ Right panel with modes
- ✅ Combat grid
- ✅ World map
- ✅ Combat log (resizable)
- ✅ API integration
- ✅ Auth token management

---

## 🔮 Coming Next

- WebSocket for real-time updates
- Equipment panel
- Skill tree UI
- NPC dialogue
- Quest log

---

## 📞 Quick Help

**Frontend won't start?**
→ Check Node.js installed: `node --version`
→ Clear cache: `npm cache clean --force`
→ Reinstall: `rm node_modules; npm install`

**Backend won't connect?**
→ Verify running: `python tools/run_api.py` shows no errors
→ Check port: Should be 5000
→ Test API: `curl http://localhost:5000/api/health`

**Login fails?**
→ Check API response: F12 → Network → POST /api/auth/login
→ Look for `session_id` in response
→ Check localStorage for `authToken` token

**Need more help?**
→ See `frontend/README.md`
→ Check `BACKEND_API_INTEGRATION.md`
→ Review component code in `src/components/`

---

## 🎊 Status

```
✅ Frontend Setup Complete
✅ Components Built
✅ API Integration Done
✅ Documentation Written

🎮 Ready to Play!
```

---

**Next Step:** Run the installation commands above!

