# Local Development Setup — Heart of Virtue

This guide walks you through starting the Flask API backend and React frontend locally for browser-based testing.

## Prerequisites

- **Python 3.8+** (installed and on PATH)
- **Node.js 16+** (installed and on PATH, required for npm)
- **git** (installed)

Verify your setup:
```bash
python --version      # Python 3.8+
npm --version         # npm 7+
node --version        # Node 16+
```

## Step 1: Install Python Dependencies

From the project root:

```bash
pip install -r requirements-api.txt
```

This installs Flask, Flask-CORS, Flask-SocketIO, and other backend dependencies.

**Optional: If using a virtual environment**:
```bash
python -m venv venv
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Then install:
pip install -r requirements-api.txt
```

## Step 2: Configure Environment

The .env file is already configured for local development. If you need to reconfigure:

```bash
# Copy the example if needed
cp .env.example .env

# Edit .env and ensure:
FLASK_ENV=development
FLASK_DEBUG=true
PORT=5000
```

**For Rumbler bug testing specifically**, you'll want to start the server with the test configuration. See "Step 4: Run API Server with Test Config" below.

## Step 3: Install Frontend Dependencies

From the `frontend/` directory:

```bash
cd frontend
npm install
```

This installs React, Vite, Socket.IO client, Axios, and other frontend dependencies.

## Step 4: Run API Server (Terminal 1)

Start the Flask API server. For **normal testing**:

```bash
python tools/run_api.py
```

You should see:
```
============================================================
Heart of Virtue API - DEVELOPMENT
============================================================
Environment: development
Debug: true
Port: 5000
URL: http://localhost:5000
Health: http://localhost:5000/health
API Info: http://localhost:5000/api/info
============================================================
```

### For Rumbler Bug Testing Specifically

To test the Rumbler loot bug through the browser, start the API server **with the test configuration**:

```bash
CONFIG_FILE=config_rumbler_loot_test.ini python tools/run_api.py
```

This loads the pre-configured test map (`rumbler-loot-test`) where you'll spawn in a Rumbler Arena with a single enemy and no starting equipment.

**What the test config provides**:
- Starts on the `rumbler-loot-test` map (single-tile arena)
- 500 HP (survives easily)
- No starting equipment (clean slate)
- High attributes (50 strength, 50 finesse, 50 speed — reliable damage)
- All skills learned (can equip any item without restrictions)
- Test mode enabled (no animations, skip dialogs)

## Step 5: Run Frontend Dev Server (Terminal 2)

In another terminal, from the `frontend/` directory:

```bash
npm run dev
```

You should see:
```
VITE v6.x.x  ready in xxx ms

➜  Local:   http://localhost:3000/games/HeartOfVirtue/
```

The Vite dev server automatically proxies API calls from `http://localhost:3000/api/*` to `http://localhost:5000/api/*`.

## Step 6: Open Browser

Navigate to:
```
http://localhost:3000/games/HeartOfVirtue/
```

You'll see the login page. Create a test account or use the auto-login if you're running in test mode.

---

## Testing the Rumbler Loot Bug in the Browser

### Quick Reproduction

1. **Start API with test config**:
   ```bash
   CONFIG_FILE=config_rumbler_loot_test.ini python tools/run_api.py
   ```

2. **Start frontend**:
   ```bash
   cd frontend && npm run dev
   ```

3. **Open browser**: `http://localhost:3000/games/HeartOfVirtue/`

4. **Login/create account** → You'll spawn in the Rumbler Arena at `(0, 0)`

5. **Engage the Rumbler**:
   - See the `Test Rumbler` NPC in the center of the room
   - Click to attack or use `/attack` command
   - Fight until the Rumbler is defeated

6. **Attempt to equip dropped loot**:
   - After the Rumbler dies, it drops equipment
   - Click on the item or try to `take` it into inventory
   - Try to `equip` the item

**Bug occurs if**:
- Error appears on equip: `'dict' object has no attribute 'maintype'`
- Or: `list.remove(x): x not in list`
- Or item interaction silently fails

### Debugging Tips

**Browser Console** (F12 or Ctrl+Shift+K):
- Check JavaScript console for client-side errors
- Check Network tab to see API request/response

**Backend Logs**:
- Watch the terminal where you ran `python tools/run_api.py`
- Flask will print error tracebacks if the API fails

**Flask Debug Mode**:
- The server runs with `FLASK_DEBUG=true` (from .env)
- Exceptions will show detailed tracebacks
- Code reloads on file changes

---

## Stopping Servers

**To stop the API server** (Terminal 1):
```bash
Ctrl+C
```

**To stop the frontend server** (Terminal 2):
```bash
Ctrl+C
```

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'flask'"

→ Ensure you've run `pip install -r requirements-api.txt`

### "command not found: npm"

→ Node.js is not installed or not on PATH. Download from [nodejs.org](https://nodejs.org/)

### Frontend won't connect to backend

→ Ensure API is running on `http://localhost:5000/health` (visit in browser to confirm)
→ Check browser console (F12) for CORS errors or connection failures

### "Port 5000 already in use"

→ Another process is using port 5000. Either:
  - Kill the process: `lsof -i :5000` (macOS/Linux) or `netstat -ano | findstr :5000` (Windows)
  - Or start on a different port: `PORT=5001 python tools/run_api.py`

### "Port 3000 already in use"

→ Edit `frontend/vite.config.js` and change `port: 3000` to `port: 3001` (or another available port)

---

## Next Steps

- **Run automated tests** to verify the bug:
  ```bash
  python tools/test_rumbler_loot.py --repeat 10 --verbose
  ```

- **Read detailed reproduction guide**: [docs/RUMBLER_LOOT_BUG_REPRODUCTION.md](RUMBLER_LOOT_BUG_REPRODUCTION.md)

- **Check game logs** for detailed error messages:
  - Terminal game: check `game.log` (if enabled)
  - API: watch the Flask terminal output

---

## Environment Summary

| Component | Port | URL |
|-----------|------|-----|
| Flask API | 5000 | http://localhost:5000 |
| React Frontend | 3000 | http://localhost:3000/games/HeartOfVirtue/ |
| API Health Check | 5000 | http://localhost:5000/health |

Frontend proxy routes:
- `/api/*` → `http://localhost:5000/api/*`
- `/games/HeartOfVirtue/api/*` → `http://localhost:5000/api/*`
