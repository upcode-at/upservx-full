## Release v0.5.1 - Auth & Activity Reliability

**Release Date:** 2026-05-12

### 🎉 What's New in UpservX v0.5.1

This release focuses on authentication hardening and activity reliability: signed session-token auth replaces persisted Basic credentials, CLI auth now uses token-based sessions, and activity/progress handling in the sidebar has been improved for clearer operational visibility and lower noise.

### ✨ Highlights

#### 🔐 Signed Session Authentication
- Signed expiring session tokens (HMAC-SHA256) for user sessions
- Middleware validates Bearer/API/cluster/session tokens
- Login and 2FA complete return `session_token` and set session cookie

#### 🖥️ CLI Token-Based Login
- CLI now authenticates via `POST /auth/login`
- Stores `username` + token instead of Basic credentials
- Uses Bearer token for API calls

#### 🔔 Activity & Status Improvements
- Activity bell with larger overlay and notification-event filtering
- Recent backup/replication status timeline with running progress bars
- Terminal states (`completed`/`failed`) are no longer repeatedly polled
- Polling intervals normalized to 10 seconds where applicable

#### 🛠️ Reliability Fixes
- Recent status list is preserved on transient fetch errors
- Removed frontend Authorization header injection that caused stale-token 401s
- Standardized VPN profile storage path to `/etc/upservx/vpn`

### 📄 Full Release Notes
See [releases/0.5.1.md](releases/0.5.1.md) for complete details including API/auth changes and upgrade notes.