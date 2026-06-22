# Local Keycloak Testing Setup

This directory contains configuration for running a local Keycloak instance to test authentication flows without using an external Keycloak server.

## Quick Start (VS Code)

Use the **"Full Stack (Local Keycloak)"** launch configuration in VS Code:
1. Press **Cmd+Shift+D** to open Run and Debug
2. Select **"Full Stack (Local Keycloak) - Backend:8080 + Frontend"**
3. Press **F5**

This uses your existing local MongoDB and MinIO, and just adds Keycloak for authentication.

## Quick Start (Manual)

1. **Start Keycloak only** (uses existing MongoDB/MinIO):
   ```bash
   cd docker
   docker compose -f docker-compose.keycloak-only.yml up -d
   ```

2. **Wait for Keycloak to be ready** (~60 seconds):
   ```bash
   docker logs -f fstvlpress-keycloak-local
   # Wait until you see "Running the server in development mode"
   ```

3. **Start the backend** with local Keycloak config:
   ```bash
   cd backend
   ENVIRONMENT=local-keycloak APP_TOKEN_SECRET=local-dev-app-token-secret python -m uvicorn app.main:app --reload --port 8080
   ```

4. **Start the frontend** with local Keycloak enabled:
   ```bash
   cd frontend
   VITE_USE_LOCAL_KEYCLOAK=true npm run dev
   ```

5. **Test the login flow:**
   - Open http://localhost:5173
   - Click Login
   - Use one of the test accounts (see below)

## Test Accounts

| Email | Password | Roles |
|-------|----------|-------|
| admin@example.local | admin123 | admin, editor |
| editor@example.local | editor123 | editor |
| viewer@example.local | viewer123 | viewer |

## Keycloak Admin Console

- **URL:** http://localhost:8180
- **Username:** admin
- **Password:** local-admin-password

Use the admin console to:
- View/edit users
- Modify realm settings
- View active sessions
- Check client configurations

## Configuration Details

### Realm: FstvlPressLocal

The `realm-local.json` file pre-configures:

- **Clients:**
  - `fstvlpress-web` - Public client for the Vue.js frontend
  - `fstvlpress-api` - Confidential client for the FastAPI backend

- **Realm Roles:**
  - `admin` - Full administrative access
  - `editor` - Content management access
  - `viewer` - Read-only access

- **Groups:**
  - `/admins` - Maps to admin role
  - `/editors` - Maps to editor role
  - `/viewers` - Maps to viewer role

### Frontend Configuration

When `VITE_USE_LOCAL_KEYCLOAK=true` is set:
- Keycloak URL: http://localhost:8180
- Realm: FstvlPressLocal
- Client ID: fstvlpress-web

### Backend Configuration

With `.env.local.keycloak.example`:
- Environment: local-keycloak
- Keycloak URL: http://localhost:8180
- Realm: FstvlPressLocal
- Client ID: fstvlpress-api
- Client Secret: local-dev-client-secret
- JWT Audience: account

## Troubleshooting

### Keycloak won't start
```bash
# Check logs
docker logs fstvlpress-keycloak-local

# Ensure port 8180 is not in use
lsof -i :8180
```

### Login redirect fails
- Ensure frontend is running on http://localhost:5173 (configured redirect URI)
- Check browser console for CORS or network errors
- Verify Keycloak is healthy: http://localhost:8180/health/ready

### Token validation fails
- Ensure backend is configured with `ENVIRONMENT=local-keycloak`
- Check that the token issuer is reachable from the backend
- The backend expects `aud=account` by default
- If logs show `Audience mismatch`, update the `fstvlpress-web` client audience mapper to include `account`, then log out and back in to get a fresh token.
- Existing local realms are not overwritten by `--import-realm`; recreate the local Keycloak container if it was imported with an older audience.
- Verify the backend can reach Keycloak:
  ```bash
  curl http://localhost:8180/realms/FstvlPressLocal/.well-known/openid-configuration
  ```

### Reset everything
```bash
cd docker
docker compose -f docker-compose.keycloak-only.yml down -v
docker compose -f docker-compose.keycloak-only.yml up -d
```

## Customizing the Realm

To modify the realm configuration:

1. Edit `realm-local.json`
2. Restart Keycloak:
   ```bash
   docker compose -f docker-compose.keycloak-only.yml restart keycloak
   ```

Or use the admin console for runtime changes (they won't persist across container restarts).

To export changes made in admin console:
```bash
docker exec fstvlpress-keycloak-local /opt/keycloak/bin/kc.sh export --dir /tmp/export --realm FstvlPressLocal
docker cp fstvlpress-keycloak-local:/tmp/export/FstvlPressLocal-realm.json ./realm-local.json
```
