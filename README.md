# Affluence-AI Affiliate Commission Agent

A full-stack affiliate commission system with a FastAPI backend and React + Tailwind dashboard.

## Features
- Product and rate scanning from affiliate network adapters
- Affiliate link generation and tracking codes
- Purchase logging with commission calculations
- Commission validation after refund windows
- Payout threshold monitoring and automated payout triggering (PayPal / M-Pesa adapters)
- Email/SMS payout threshold alerts
- Role-based dashboard/API access
- Encrypted credential storage for API keys
- Daily/weekly earnings and payout reports

## Architecture
- **Backend:** `backend/app` (FastAPI, SQLAlchemy, APScheduler)
- **Frontend:** `frontend` (React, TailwindCSS, Vite)
- **Deployment assets:** `deploy/nginx.conf`, `deploy/setup.sh`

## API Endpoints
- `POST /scan` — scan products and prepare affiliate links
- `POST /purchase` — record purchase from a tracking link
- `POST /validate` — validate commissions after refund period
- `POST /payout` — process payout via PayPal or M-Pesa
- `GET /report` — daily/weekly earnings and payout summary
- `POST /credentials` — encrypted API key storage

## Security
- API keys encrypted using `cryptography` (Fernet)
- Role-based access control (`admin`, `viewer`) via auth tokens
- Optional HTTPS enforcement using `REQUIRE_HTTPS=true`
- TLS termination intended at Nginx with Let's Encrypt certs

## Quick Start
See [SETUP.md](./SETUP.md).
