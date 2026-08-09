# Comprehensive Activity Logging — Implementation TODO

## Goal
Record EVERYTHING in the system logs — every user click and every AI action — persistently in the audit_logs database.

## Steps

### 1. Expand log taxonomy (models.py)
- [x] Add new action categories: `user_action`, `ai_action`, `request`, `content`, `link_generation`
- [x] Add `source`, `metadata_json` fields to AuditLog model

### 2. Update AuditLogger service (audit_logger.py)
- [x] Add `source` and `metadata` params to `log()`
- [x] Add helper methods: log_user_action, log_request, log_ai_scan, log_link_generated, log_content_generated, log_network_fetch

### 3. Global HTTP request logging middleware (main.py)
- [x] Add middleware to log every API request persistently

### 4. New endpoint to capture user clicks (main.py)
- [x] Add `POST /log/user-action` endpoint
- [x] Update audit-logs endpoints + SSE stream to include source/metadata

### 5. Deep AI-action logging in all services
- [x] market_scanner.py — log each product scan
- [x] networks.py — log each network adapter search
- [x] link_generator.py — log every link generated/retrieved
- [x] click_tracker.py — log every click recorded
- [x] content_distribution.py — log content gen/draft/publish
- [x] social_account_manager.py — log account actions
- [x] withdrawal_handler.py — log payout attempts
- [x] forecasting.py — log forecast generation
- [x] reporting.py — log report generation

### 6. Instrument the frontend (App.jsx)
- [x] Add global click listener to send user interactions to `/log/user-action`
- [x] Wrap `api()` helper to log every API call
- [x] Add source badge display in System Logs rows

### 7. Update frontend System Logs tab
- [x] Add badges/filters for new categories (user_action, ai_action, request, content, link_generation)

### 8. Update CSS for new pill colors
- [x] Add cyan, teal, orange pill color classes

### 9. Test & verify
- [x] All modified backend files compile
- [x] Build frontend to confirm JSX compiles
- [x] All 62 backend tests pass
- [x] Smoke test: request logging persists (source=request)
- [x] Smoke test: user-action logging persists (source=user)
- [x] Smoke test: AI scan/link-generation logging persists (source=ai)
- [x] Smoke test: click recording logs source/metadata (referrer, country, IP)
