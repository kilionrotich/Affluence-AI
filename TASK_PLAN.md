# Active Social Accounts & System Logs Modules - Implementation Plan

## Information Gathered

The codebase already has significant implementation:
- **Backend**: SocialAccount model, PostingQueue, PostingModeConfig, SocialAccountManager service (CRUD + encrypted creds), PostingController (auto/manual routing + analytics), ComplianceEngine, AuditLogger
- **Frontend**: App.jsx with SocialAccountTab (add/list/delete/verify), PostingQueueTab (approve/reject/mode toggle), AccountAnalyticsTab (per-account analytics)
- **API**: All REST endpoints for social accounts, posting mode, posting queue, analytics are in main.py

## What Needs to Be Built/Enhanced

### Module 1: System Logs (New)
- **Backend**: Enhanced logging endpoints with action-type categories, real-time SSE/WebSocket endpoint for live log streaming
- **Frontend**: New "System Logs" tab that shows all AI actions with filtering by action type (Posting, Validation, Payment, Compliance), timestamps, account aliases
- **Enhancement**: Silent real-time notifications via Server-Sent Events (SSE) that update logs without interrupting

### Module 2: Active Social Accounts Enhancements
- **Credential Types**: Support both username/email+password AND API credentials with platform-specific form fields
- **Custom Alias**: Enhanced UI for assigning custom usernames/aliases (e.g., "Twitter-Tech", "LinkedIn-Business")
- **Account Selection per Post**: UI to select which accounts receive each post when posting content
- **Re-auth Alerts**: Enhanced notification handling for expired tokens

### Module 3: Integration & Dashboard
- **Logs Feed**: Feed system logs into main dashboard reporting
- **Analytics**: Per-account performance metrics integrated into overview

## Plan

### Step 1: Backend - System Logs Enhancement
- Add `action_category` field to AuditLog for filtering by type (Posting, Validation, Payment, Compliance)
- Add SSE endpoint `/logs/stream` for real-time log updates
- Add enhanced filtering endpoints for logs by action_category
- Add logging calls in key services (scanning, posting, validation, compliance)

### Step 2: Frontend - System Logs Tab
- Create new "System Logs" tab with:
  - Real-time log stream via SSE
  - Filter dropdown by action type (Posting, Validation, Payment, Compliance)
  - Search by account alias
  - Timestamp, action detail, status columns
  - Auto-scroll for new logs
  - Silent notification indicator (non-intrusive badge)

### Step 3: Frontend - Enhanced Social Accounts UI
- Add credential type selector (username/password vs API credentials)
- Show platform-specific credential fields
- Enhanced alias assignment with validation
- Account selection checkboxes when posting content

### Step 4: Integration
- Link logs with main dashboard
- Ensure compliance events appear in logs
- Connect account analytics to main reporting

## Files to Edit
1. `backend/app/models.py` - Add action_category to AuditLog
2. `backend/app/schemas.py` - Update log schemas with categories
3. `backend/app/main.py` - Add SSE endpoint, enhanced log routes
4. `backend/app/services/audit_logger.py` - Add category support, AI-specific log methods
5. `frontend/src/App.jsx` - Add SystemLogsTab, enhance SocialAccountTab
6. `frontend/src/index.css` - Styles for new components

