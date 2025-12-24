# Heart of Virtue: Web Deployment Roadmap

**Goal**: Launch the game as a playable web experience for users  
**Current Status**: ✅ REST API complete (797/799 tests), ❌ Frontend missing, ❌ Database missing  
**Estimated Effort**: 3-6 weeks for MVP

---

## Quick Summary: What's Missing

| Component | Status | Effort | Why Needed |
|-----------|--------|--------|-----------|
| **Web Frontend** | ❌ | 2-3 weeks | Users need UI to play (can't call API directly) |
| **Database Layer** | ❌ | 1 week | Current in-memory sessions expire in 24h |
| **User Auth** | 🟡 Partial | 3 days | Current: username only, need passwords + registration |
| **Deployment Setup** | ❌ | 1 week | Backend + frontend + database hosting |
| **WebSockets/Real-time** | 🟡 Partial | 3 days | Flask-SocketIO installed but not integrated |
| **Security Hardening** | 🟡 Partial | 3 days | Need HTTPS, rate limiting, input sanitization |

---

## Phase 1: Minimum Viable Product (MVP) - 2-3 Weeks

### 1.1 Web Frontend (Priority: CRITICAL)

**What it needs to do:**
- Display the game map (tile-based world)
- Show player character, inventory, stats
- Handle player movement (north, south, east, west, diagonals)
- Display NPCs and combat encounters
- Show dialogue trees and options
- Render combat UI in real-time

**Technology Choices (pick one):**

**Option A: React (Recommended)**
- Pros: Large ecosystem, many UI component libraries, good for complex state
- Cons: Larger bundle size, steeper learning curve
- Estimated effort: 2-3 weeks
- Tools: Vite (build), Axios (API calls), Redux or Zustand (state)
- UI Library: Material-UI or Tailwind CSS

**Option B: Vue 3 (Good Middle Ground)**
- Pros: Easier to learn than React, good documentation
- Cons: Smaller ecosystem than React
- Estimated effort: 2-3 weeks
- Tools: Vite, Axios, Pinia (state)
- UI Library: Vuetify or Tailwind CSS

**Option C: Svelte (Simplest)**
- Pros: Least boilerplate, excellent performance
- Cons: Smaller community, fewer libraries
- Estimated effort: 1-2 weeks
- Tools: Vite, Axios, Svelte stores
- UI Library: Skeleton or Tailwind CSS

**Recommended structure:**
```
frontend/
├── src/
│   ├── components/
│   │   ├── MapDisplay.jsx          (Tile grid, player position)
│   │   ├── PlayerStatus.jsx        (HP, stats, level)
│   │   ├── InventoryPanel.jsx      (Items, equipment)
│   │   ├── NPCList.jsx             (NPCs on current tile)
│   │   ├── CombatUI.jsx            (Combat display & actions)
│   │   ├── DialoguePanel.jsx       (Conversation display)
│   │   └── ChatLog.jsx             (Action history)
│   ├── services/
│   │   ├── api.js                  (API client wrapper)
│   │   ├── auth.js                 (Login/session management)
│   │   └── game.js                 (Game state logic)
│   ├── pages/
│   │   ├── LoginPage.jsx
│   │   ├── GamePage.jsx            (Main game loop)
│   │   └── CharacterCreation.jsx
│   └── App.jsx
├── package.json
├── vite.config.js
└── index.html
```

**MVP Frontend Features:**
1. ✅ Login screen with username/password
2. ✅ Game world display (tile-based grid)
3. ✅ Movement controls (arrow keys, buttons)
4. ✅ Player status panel (HP, stats, level)
5. ✅ Basic inventory display
6. ✅ NPC interaction (click → dialogue)
7. ✅ Combat mode (display enemies, show action buttons)
8. ✅ Dialogue display (show text, click choice)
9. ✅ Action log (what just happened)
10. ✅ Basic styling (not beautiful, but playable)

---

### 1.2 Persistent Database (Priority: HIGH)

**Current Problem:**
- Sessions stored in-memory (RAM only)
- Sessions expire after 24 hours
- No save persistence between server restarts
- Multiple API instances would need shared session storage

**Solution: Add PostgreSQL**

**Migration Path:**
```
Phase 1a: Add SQLAlchemy ORM
├── Install: flask-sqlalchemy
├── Create models:
│   ├── User (username, password_hash, email)
│   ├── PlayerProfile (user_id, character_name, level, exp, gold)
│   ├── PlayerSave (user_id, game_state_json, created_at, updated_at)
│   └── Session (session_id, user_id, expires_at)
└── Migrate session manager to use DB

Phase 1b: Setup PostgreSQL
├── Local development: Docker container
│   docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=dev postgres
├── Production: Managed service (AWS RDS, Heroku Postgres, etc.)
└── Create migrations (Alembic)
```

**New Models:**
```python
# src/api/models/user.py
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(120), unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow)

class PlayerProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    player_object = db.Column(db.LargeBinary)  # Pickled Player instance
    last_played = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class GameSession(db.Model):
    session_id = db.Column(db.String(32), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    expires_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
```

**Updated SessionManager:**
- Move from in-memory dict to database queries
- Add session expiration cleanup job (background task)
- Support multi-server deployments
- Add player persistence across sessions

---

### 1.3 User Authentication Enhancement (Priority: HIGH)

**Current State:**
- Username-only login (no password)
- Session created immediately

**Needed Improvements:**
```python
# Update: src/api/routes/auth.py

@auth_bp.route('/register', methods=['POST'])
def register():
    """Register new user with password."""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    email = data.get('email')
    
    # Validate input
    # Hash password (use werkzeug.security.generate_password_hash)
    # Check username not taken
    # Create user in database
    # Return success or error
    
@auth_bp.route('/login', methods=['POST'])
def login():
    """Enhanced login with password verification."""
    # Get username and password
    # Look up user in database
    # Verify password hash
    # Create session with 7-day expiration
    # Return Bearer token
    
@auth_bp.route('/refresh', methods=['POST'])
def refresh_token():
    """Refresh expired session token."""
    # Validate current token
    # If valid but expiring soon, issue new token
    # Return new Bearer token
```

**Dependencies:**
```bash
pip install werkzeug  # Password hashing
pip install python-dotenv  # Environment variables
```

---

## Phase 2: Launch-Ready Features - 1-2 Weeks

### 2.1 WebSocket Real-Time Updates

**Current Issue:** Frontend polls API every second (wasteful)  
**Solution:** Use Flask-SocketIO for bi-directional communication

**Implementation:**
```python
# src/api/app.py - Already has Flask-SocketIO installed

from flask_socketio import emit, join_room

@socketio.on('connect')
def handle_connect(auth):
    """Player connects to game."""
    session_id = auth.get('session_id')
    session = session_manager.get_session(session_id)
    if not session:
        return False
    join_room(session_id)

@socketio.on('player_moved')
def handle_movement(data):
    """Broadcast movement to all connected clients."""
    direction = data.get('direction')
    # Process movement on backend
    # Emit new position to all clients
    emit('position_updated', {...}, room=session_id)

@socketio.on('combat_action')
def handle_combat(data):
    """Handle combat in real-time."""
    action = data.get('action')
    # Process combat
    # Emit combat state update
    emit('combat_updated', {...}, room=session_id)
```

**Frontend (React example):**
```javascript
import io from 'socket.io-client';

const socket = io(API_URL, {
    auth: { session_id: localStorage.getItem('session_id') }
});

socket.on('position_updated', (newPosition) => {
    setPlayerPosition(newPosition);
});

socket.emit('player_moved', { direction: 'north' });
```

---

### 2.2 Security Hardening

**Add to deployment:**
1. **HTTPS/TLS** - Use Let's Encrypt (free)
2. **CORS Configuration** - Already in Flask app, verify settings
3. **Rate Limiting** - Prevent API abuse
4. **Input Sanitization** - Prevent injection attacks
5. **CSRF Protection** - If using cookies
6. **Security Headers** - X-Content-Type-Options, X-Frame-Options, etc.

**Code additions:**
```python
# src/api/app.py
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman

# Rate limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# Security headers
Talisman(app, 
    force_https=True,
    strict_transport_security=True,
    strict_transport_security_max_age=31536000
)

# CORS
CORS(app, 
    resources={"/api/*": {"origins": ["https://yourdomain.com"]}},
    supports_credentials=True
)
```

---

## Phase 3: Deployment Infrastructure - 1 Week

### 3.1 Containerization (Docker)

**Create Dockerfile:**
```dockerfile
FROM python:3.13-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt requirements-api.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-api.txt

# Copy app
COPY src/ src/
COPY ai/ ai/
COPY run_api.py .

# Expose port
EXPOSE 5000

# Start app
CMD ["python", "run_api.py"]
```

**Docker Compose (for local testing):**
```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_PASSWORD: devpassword
      POSTGRES_DB: heart_of_virtue
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  backend:
    build: .
    ports:
      - "5000:5000"
    environment:
      DATABASE_URL: postgresql://postgres:devpassword@postgres:5432/heart_of_virtue
      FLASK_ENV: development
    depends_on:
      - postgres

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      REACT_APP_API_URL: http://localhost:5000/api

volumes:
  postgres_data:
```

### 3.2 Hosting Options

**Option A: AWS (Most Scalable)**
- Backend: Elastic Container Service (ECS) or Lightsail
- Database: RDS (PostgreSQL)
- Frontend: CloudFront + S3
- Estimated cost: $20-50/month

**Option B: Heroku (Easiest to Start)**
- Backend: Heroku dyno
- Database: Heroku Postgres
- Frontend: Heroku static buildpack or separate CDN
- Estimated cost: $7-50/month (free tier available)

**Option C: DigitalOcean (Good Balance)**
- Backend: App Platform or Droplet
- Database: Managed PostgreSQL
- Frontend: Spaces (S3-compatible) + CDN
- Estimated cost: $5-25/month

**Option D: Azure (Enterprise)**
- Backend: Container Instances or App Service
- Database: Azure Database for PostgreSQL
- Frontend: Static Web Apps
- Estimated cost: $5-50/month

---

## Implementation Checklist

### Pre-Development
- [ ] Choose frontend framework (React/Vue/Svelte)
- [ ] Set up project structure
- [ ] Choose hosting provider
- [ ] Design database schema

### Frontend Development (Week 1-2)
- [ ] Create login/registration screens
- [ ] Build map display component
- [ ] Implement movement controls
- [ ] Create inventory panel
- [ ] Build combat UI
- [ ] Implement dialogue system
- [ ] Add action log/chat display
- [ ] Style with CSS framework

### Backend Enhancement (Days 1-3)
- [ ] Add PostgreSQL support to `SessionManager`
- [ ] Implement password hashing in auth routes
- [ ] Add user registration endpoint
- [ ] Create database models (User, PlayerProfile, GameSession)
- [ ] Add rate limiting and security headers
- [ ] Integrate WebSocket handlers

### Deployment (Days 4-7)
- [ ] Create Dockerfile
- [ ] Set up Docker Compose locally
- [ ] Create CI/CD pipeline (GitHub Actions)
- [ ] Deploy to staging environment
- [ ] Run end-to-end testing
- [ ] Deploy to production
- [ ] Set up monitoring and logging

### Post-Launch
- [ ] Monitor error rates
- [ ] Gather user feedback
- [ ] Fix bugs and performance issues
- [ ] Plan Stage 6 features

---

## Estimated Delivery Timeline

| Phase | Duration | Milestone |
|-------|----------|-----------|
| Phase 1: MVP | 2-3 weeks | **Playable web game** |
| Phase 2: Launch-ready | 1-2 weeks | Security + WebSockets |
| Phase 3: Deployment | 1 week | Live on web |
| **Total to MVP** | **4-6 weeks** | Users can play online |

---

## Key Decisions to Make Now

1. **Frontend Framework?** React (safest), Vue (balanced), or Svelte (simplest)
2. **Hosting Provider?** AWS (scalable), Heroku (easy), DigitalOcean (balanced), Azure (enterprise)
3. **Database?** PostgreSQL (traditional, tested), MongoDB (flexible), or managed service?
4. **Start with MVP or full-featured?** (Recommendation: MVP first, iterate)

---

## Questions to Ask

1. How many concurrent users do you expect? (affects hosting choice)
2. Do you need real-time PvP? (affects WebSocket complexity)
3. What's your budget for hosting?
4. Do you want to maintain the game post-launch?
5. Should players be able to download the game client?

---

## Resources

**Frontend:**
- React: https://react.dev
- Vue: https://vuejs.org
- Svelte: https://svelte.dev
- Vite: https://vitejs.dev

**Backend:**
- Flask: https://flask.palletsprojects.com
- SQLAlchemy: https://sqlalchemy.org
- Flask-SocketIO: https://flask-socketio.readthedocs.io

**Deployment:**
- Docker: https://docs.docker.com
- Heroku: https://devcenter.heroku.com
- AWS: https://docs.aws.amazon.com

**Database:**
- PostgreSQL: https://www.postgresql.org/docs
- Alembic (migrations): https://alembic.sqlalchemy.org

