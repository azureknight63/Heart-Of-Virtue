# Backend API Requirements for Frontend

This document ensures the Flask backend API is properly configured to support the frontend web UI.

## ✅ Backend Checklist

### CORS Configuration
- [x] Flask-CORS is installed (`requirements-api.txt`)
- [x] CORS is enabled on the Flask app
- [ ] **TODO**: Verify CORS headers allow frontend origin (http://localhost:3000)

**Check in `src/api/app.py`:**
```python
from flask_cors import CORS

app = Flask(__name__)
CORS(app, 
     origins=['http://localhost:3000', 'http://localhost:5000'],
     supports_credentials=True)
```

### Auth Endpoints
The frontend expects these endpoints:

```
POST /api/auth/register
POST /api/auth/login    → Returns: { success: true, data: { session_id: "..." } }
POST /api/auth/logout
```

**Session Token Format:**
- Token: UUID or similar unique string
- Storage: LocalStorage key = `authToken`
- Header: `Authorization: Bearer {token}`

### Player Endpoints
```
GET /api/player/status   → { hp, max_hp, fatigue, max_fatigue, level, experience, ... }
GET /api/player/inventory → { items: [...] }
GET /api/player/equipment → { equipped: {...} }
GET /api/player/stats     → { strength, agility, intelligence, ... }
```

### World Endpoints
```
GET /api/world/location   → { name, description, exits: [...] }
POST /api/world/move      → Body: { direction: "north"|"south"|"east"|"west" }
GET /api/world/exits      → { available: [...] }
```

### Combat Endpoints
```
GET /api/combat/status    → { in_combat: bool, enemies: [...], player_hp, ... }
POST /api/combat/start    → Initiates combat
POST /api/combat/end      → Ends combat
POST /api/combat/action   → Body: { action, target }
```

### Inventory Endpoints
```
POST /api/inventory/use       → Body: { item_id }
POST /api/inventory/drop      → Body: { item_id }
POST /api/inventory/pickup    → Body: { item_id }
```

### Equipment Endpoints
```
POST /api/equipment/equip     → Body: { item_id, slot }
POST /api/equipment/unequip   → Body: { slot }
```

### Save/Load Endpoints
```
POST /api/saves/save          → Body: { save_name }
POST /api/saves/load          → Body: { save_id }
GET /api/saves/list           → Returns list of saves
DELETE /api/saves/delete/{id} → Delete a save
```

## 🔌 API Response Format

All endpoints should follow this format:

### Success Response (2xx)
```json
{
  "success": true,
  "data": {
    "field1": "value1",
    "field2": "value2"
  }
}
```

### Error Response (4xx/5xx)
```json
{
  "success": false,
  "error": "error_code",
  "message": "Human-readable error message"
}
```

## 🔐 Authentication Flow

1. User fills login form
2. Frontend POSTs to `/api/auth/login`
3. Backend validates credentials
4. Backend creates session and returns `session_id`
5. Frontend stores `session_id` in localStorage as `authToken`
6. Frontend includes `Authorization: Bearer {session_id}` header on all requests
7. Backend validates token on each request
8. If token invalid/expired, return 401
9. Frontend intercepts 401 and redirects to login

## ⚙️ Configuration

### Environment Variables (for API server)
```bash
FLASK_ENV=development
FLASK_HOST=127.0.0.1
FLASK_PORT=5000
```

### Frontend Environment Variables (frontend/.env)
```bash
VITE_API_URL=http://localhost:5000/api
VITE_WS_URL=ws://localhost:5000
```

## 🧪 Testing the Backend

### Via Browser (Frontend)
1. Start backend: `python tools/run_api.py`
2. Start frontend: `cd frontend; npm run dev`
3. Open http://localhost:3000
4. Test login flow
5. Verify data appears in UI

### Via cURL (Direct API Testing)
```powershell
# Register
curl -X POST http://localhost:5000/api/auth/register `
  -H "Content-Type: application/json" `
  -d '{"username":"test","password":"test"}'

# Login
$response = curl -X POST http://localhost:5000/api/auth/login `
  -H "Content-Type: application/json" `
  -d '{"username":"test","password":"test"}'

# Extract token and test protected endpoint
curl -X GET http://localhost:5000/api/player/status `
  -H "Authorization: Bearer {token_from_response}"
```

### Via Postman
1. Create environment with variables:
   - `api_url`: http://localhost:5000/api
   - `session_id`: (populate after login)
2. Create requests for each endpoint
3. Use `{{api_url}}` and `Bearer {{session_id}}}` in headers

## 📊 Data Structure Examples

### Player Status Response
```json
{
  "success": true,
  "data": {
    "id": "player_1",
    "name": "Jean",
    "hp": 75,
    "max_hp": 100,
    "fatigue": 60,
    "max_fatigue": 100,
    "level": 3,
    "experience": 1240,
    "next_level_exp": 2000,
    "strength": 15,
    "agility": 12,
    "intelligence": 10,
    "inventory": [
      { "id": "item_1", "name": "Shortsword", "quantity": 1, "equipped": true },
      { "id": "item_2", "name": "Leather Armor", "quantity": 1, "equipped": true },
      { "id": "item_3", "name": "Healing Potion", "quantity": 3 }
    ]
  }
}
```

### Combat Status Response
```json
{
  "success": true,
  "data": {
    "in_combat": true,
    "player_hp": 75,
    "player_max_hp": 100,
    "enemies": [
      { "id": "enemy_1", "name": "Bat", "hp": 18, "max_hp": 30 },
      { "id": "enemy_2", "name": "Goblin", "hp": 5, "max_hp": 25 }
    ],
    "log": [
      { "type": "ability", "message": "Jean uses Attack!" },
      { "type": "damage", "message": "Bat takes 12 damage" }
    ]
  }
}
```

## 🚀 Running Together

### Terminal 1 - Backend
```powershell
.venv\Scripts\Activate.ps1
python tools/run_api.py
# Output: WARNING in app.run() is not recommended ...
#         Running on http://127.0.0.1:5000
```

### Terminal 2 - Frontend
```powershell
cd .\frontend
npm install  # (first time only)
npm run dev
# Output: ✓ built in 0.23s
#         ➜  Local:   http://localhost:3000/
```

## 🔗 API Documentation

**Swagger UI** (if available):
- URL: http://localhost:5000/api/docs
- Provides interactive API testing

**OpenAPI Schema**:
- URL: http://localhost:5000/api/openapi.json
- Machine-readable API specification

## 🐛 Debugging

### Enable Debug Logging
```python
# In src/api/app.py
app.logger.setLevel(logging.DEBUG)
logging.basicConfig(level=logging.DEBUG)
```

### Check CORS Headers
```powershell
curl -i -X GET http://localhost:5000/api/player/status `
  -H "Authorization: Bearer test-token"
```

Look for:
```
Access-Control-Allow-Origin: http://localhost:3000
Access-Control-Allow-Credentials: true
```

### Frontend Network Tab
1. Open DevTools (F12)
2. Go to Network tab
3. Make API request from frontend
4. Click request → Response tab
5. Verify response format and status code

## 📋 Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| CORS error in console | CORS not enabled | Enable CORS in Flask |
| 401 Unauthorized | Bad/missing token | Check token generation |
| 404 Not Found | Wrong endpoint URL | Verify endpoint path |
| 500 Server Error | Backend crash | Check server logs |
| Empty response | Wrong response format | Return JSON dict |

## ✅ Verification Checklist

- [ ] Backend runs on http://localhost:5000
- [ ] CORS headers present in responses
- [ ] `/api/auth/login` returns session_id
- [ ] Auth token works in `Authorization` header
- [ ] All player/combat/world endpoints respond
- [ ] Responses are valid JSON
- [ ] 401 returns on expired tokens
- [ ] Frontend can login and see player data
- [ ] Frontend can move and fetch new locations
- [ ] Combat transitions work

## 📞 If Issues Arise

1. Check backend is running: `python tools/run_api.py` should show no errors
2. Test endpoint directly with curl (see Testing section)
3. Check browser console for error messages
4. Check server logs for stack traces
5. Verify response format matches examples above
6. Re-read auth flow section above

---

**Backend Status**: Ready to support frontend
**Frontend Status**: Ready to consume API
**Integration Status**: Ready to test together!

